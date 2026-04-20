from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, distinct, text, select, cast, String
from database import get_db, _agent_log, _async_pool_stats
from utils.helpers import as_naive_utc, format_datetime_vienna_iso
from utils.response_cache import get_statistics_cache
from dependencies import get_blacklist
from datetime import datetime, timezone, timedelta
from typing import Optional
from starlette.responses import JSONResponse
import hashlib
import json
import math
from models import (
    Country, City, Location, Station, Measurement,
    CalibrationMeasurement, Values, StationStatus
)
from enums import Source, SensorModel, Dimension

router = APIRouter()

_STATISTICS_CACHE_CONTROL = "public, max-age=900, stale-while-revalidate=120"


def _statistics_cache_key(blacklist: frozenset[str]) -> str:
    """Stable in-process cache key; varies with blacklist so subtracted counts stay correct."""
    if not blacklist:
        return "statistics:v1"
    digest = hashlib.sha256(",".join(sorted(blacklist)).encode()).hexdigest()[:24]
    return f"statistics:v1:bl:{digest}"


def _statistics_json_response(data: dict, now: datetime) -> JSONResponse:
    """JSON body with request-time timestamp, ETag over payload excluding timestamp, shared Cache-Control."""
    out = dict(json.loads(json.dumps(data, default=str)))
    out["timestamp"] = format_datetime_vienna_iso(now)
    body_etag = {k: v for k, v in out.items() if k != "timestamp"}
    etag_val = hashlib.md5(
        json.dumps(body_etag, sort_keys=True, default=str).encode()
    ).hexdigest()
    return JSONResponse(
        content=out,
        headers={
            "Cache-Control": _STATISTICS_CACHE_CONTROL,
            "ETag": f'W/"{etag_val}"',
        },
    )


def _statistics_snapshot_response(payload: object, now: datetime) -> JSONResponse:
    """Build HTTP response from precomputed jsonb snapshot; timestamp reflects request time."""
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = json.loads(json.dumps(payload, default=str))
    return _statistics_json_response(data, now)


async def _try_load_statistics_snapshot(
    db: AsyncSession, now: datetime
) -> Optional[JSONResponse]:
    try:
        res = await db.execute(
            text("SELECT payload FROM statistics_endpoint_snapshot WHERE id = 1")
        )
        row = res.first()
        if row is None or row.payload is None:
            return None
        return _statistics_snapshot_response(row.payload, now)
    except Exception:
        await db.rollback()
        return None


async def _blacklisted_station_pk_ids(db: AsyncSession, blacklist: frozenset[str]) -> list[int]:
    """Primary keys for blacklisted devices (small list → ``IN (id1,…)`` in follow-up SQL)."""
    if not blacklist:
        return []
    r = await db.execute(select(Station.id).where(Station.device.in_(blacklist)))
    return [row[0] for row in r.all()]


async def _counts_for_blacklisted_devices(
    db: AsyncSession, blacklist: frozenset[str]
) -> dict[str, int]:
    """Counts rows for blacklisted stations only, using ``station_id IN (…pk…)`` for index-friendly plans."""
    if not blacklist:
        return {"stations": 0, "measurements": 0, "calibration": 0, "values": 0, "statuses": 0}
    ids = await _blacklisted_station_pk_ids(db, blacklist)
    if not ids:
        return {"stations": 0, "measurements": 0, "calibration": 0, "values": 0, "statuses": 0}

    stations = len(ids)
    # ``IN (many ids)`` can devolve into a parallel seq scan on the whole table (~9s+ in prod);
    # per-station counts use idx_measurements_station_id reliably.
    measurements = 0
    for sid in ids:
        r = await db.execute(select(func.count(Measurement.id)).where(Measurement.station_id == sid))
        measurements += int(r.scalar() or 0)
    calibration = 0
    for sid in ids:
        r = await db.execute(
            select(func.count(CalibrationMeasurement.id)).where(
                CalibrationMeasurement.station_id == sid
            )
        )
        calibration += int(r.scalar() or 0)
    # Per-station nested-loop (measurements → values index) is ~1s for moderate stations; without
    # hints Postgres may choose hash join + seq scan on ``values`` (~100s+) for huge station_id.
    # Disable hash/merge join inside this savepoint only (reverts when nested tx ends).
    values = 0
    async with db.begin_nested():
        await db.execute(text("SET LOCAL max_parallel_workers_per_gather = 0"))
        await db.execute(text("SET LOCAL enable_hashjoin = off"))
        await db.execute(text("SET LOCAL enable_mergejoin = off"))
        for sid in ids:
            r = await db.execute(
                select(func.count(Values.id))
                .select_from(Values)
                .join(Measurement, Values.measurement_id == Measurement.id)
                .where(Measurement.station_id == sid)
            )
            values += int(r.scalar() or 0)
    r = await db.execute(select(func.count(StationStatus.id)).where(StationStatus.station_id.in_(ids)))
    statuses = int(r.scalar() or 0)
    return {
        "stations": stations,
        "measurements": measurements,
        "calibration": calibration,
        "values": values,
        "statuses": statuses,
    }


async def _blacklist_active_station_counts(
    db: AsyncSession,
    blacklist: frozenset[str],
    one_hour_ago,
    one_day_ago,
    seven_days_ago,
    thirty_days_ago,
) -> tuple[int, int, int, int]:
    if not blacklist:
        return (0, 0, 0, 0)

    async def _in_window(since):
        q = select(func.count(distinct(Station.id))).where(
            Station.device.in_(blacklist),
            Station.last_active.isnot(None),
            Station.last_active >= since,
        )
        r = await db.execute(q)
        return int(r.scalar() or 0)

    return (
        await _in_window(one_hour_ago),
        await _in_window(one_day_ago),
        await _in_window(seven_days_ago),
        await _in_window(thirty_days_ago),
    )


async def _blacklist_measurement_timeframe_counts(
    db: AsyncSession,
    blacklist: frozenset[str],
    one_day_ago,
    seven_days_ago,
    thirty_days_ago,
) -> tuple[int, int, int]:
    if not blacklist:
        return (0, 0, 0)
    ids = await _blacklisted_station_pk_ids(db, blacklist)
    if not ids:
        return (0, 0, 0)

    async def _cnt(since):
        q = select(func.count(Measurement.id)).where(
            Measurement.station_id.in_(ids),
            Measurement.time_measured >= since,
        )
        r = await db.execute(q)
        return int(r.scalar() or 0)

    return (
        await _cnt(one_day_ago),
        await _cnt(seven_days_ago),
        await _cnt(thirty_days_ago),
    )


async def _blacklist_stations_by_source_counts(
    db: AsyncSession, blacklist: frozenset[str]
) -> dict[int, int]:
    if not blacklist:
        return {}
    r = await db.execute(
        select(Station.source, func.count(Station.id))
        .where(Station.device.in_(blacklist))
        .group_by(Station.source)
    )
    out: dict[int, int] = {}
    for src, c in r.all():
        if src is not None:
            out[int(src)] = int(c or 0)
    return out


@router.get("/", tags=["statistics"])
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist),
):
    now = datetime.now(timezone.utc)
    one_hour_ago = as_naive_utc(now - timedelta(hours=1))
    one_day_ago = as_naive_utc(now - timedelta(days=1))
    seven_days_ago = as_naive_utc(now - timedelta(days=7))
    thirty_days_ago = as_naive_utc(now - timedelta(days=30))

    cache = get_statistics_cache()
    cache_key = _statistics_cache_key(blacklist)
    cached = cache.get(cache_key)
    if cached is not None:
        return _statistics_json_response(json.loads(cached.decode("utf-8")), now)

    if not blacklist:
        snap = await _try_load_statistics_snapshot(db, now)
        if snap is not None:
            cache.set(cache_key, snap.body.decode("utf-8"))
            return snap

    use_materialized_views = False

    try:
        res = await db.execute(text("SELECT * FROM statistics_summary LIMIT 1"))
        stats_summary = res.first()
        if stats_summary:
            use_materialized_views = True
            total_countries = stats_summary.total_countries or 0
            total_cities = stats_summary.total_cities or 0
            total_locations = stats_summary.total_locations or 0
            total_stations = stats_summary.total_stations or 0
            total_measurements = stats_summary.total_measurements or 0
            total_calibration_measurements = stats_summary.total_calibration_measurements or 0
            total_values = stats_summary.total_values or 0
            total_station_statuses = stats_summary.total_station_statuses or 0
            earliest_measurement = stats_summary.earliest_measurement
            latest_measurement = stats_summary.latest_measurement
            if blacklist:
                sub = await _counts_for_blacklisted_devices(db, blacklist)
                total_stations = max(0, total_stations - sub["stations"])
                total_measurements = max(0, total_measurements - sub["measurements"])
                total_calibration_measurements = max(
                    0, total_calibration_measurements - sub["calibration"]
                )
                total_values = max(0, total_values - sub["values"])
                total_station_statuses = max(0, total_station_statuses - sub["statuses"])
        else:
            use_materialized_views = False
    except Exception:
        await db.rollback()
        use_materialized_views = False

    if not use_materialized_views:
        # region agent log
        _agent_log(
            "H3",
            "statistics.py:get_statistics:fallback",
            "live_count_branch",
            {
                "use_materialized_views": use_materialized_views,
                "blacklist_nonempty": bool(blacklist),
                "pool": _async_pool_stats(),
            },
        )
        # endregion
        r = await db.execute(select(func.count(Country.id)))
        total_countries = r.scalar() or 0
        r = await db.execute(select(func.count(City.id)))
        total_cities = r.scalar() or 0
        r = await db.execute(select(func.count(Location.id)))
        total_locations = r.scalar() or 0
        sq = select(func.count(Station.id))
        if blacklist:
            sq = sq.where(~Station.device.in_(blacklist))
        r = await db.execute(sq)
        total_stations = r.scalar() or 0
        if blacklist:
            r = await db.execute(
                select(func.count(Measurement.id)).join(Station).where(~Station.device.in_(blacklist))
            )
            total_measurements = r.scalar() or 0
            r = await db.execute(
                select(func.count(CalibrationMeasurement.id)).join(Station).where(~Station.device.in_(blacklist))
            )
            total_calibration_measurements = r.scalar() or 0
            r = await db.execute(
                select(func.count(Values.id)).join(Measurement).join(Station).where(~Station.device.in_(blacklist))
            )
            total_values = r.scalar() or 0
            r = await db.execute(
                select(func.count(StationStatus.id)).join(Station).where(~Station.device.in_(blacklist))
            )
            total_station_statuses = r.scalar() or 0
        else:
            r = await db.execute(select(func.count(Measurement.id)))
            total_measurements = r.scalar() or 0
            r = await db.execute(select(func.count(CalibrationMeasurement.id)))
            total_calibration_measurements = r.scalar() or 0
            r = await db.execute(select(func.count(Values.id)))
            total_values = r.scalar() or 0
            r = await db.execute(select(func.count(StationStatus.id)))
            total_station_statuses = r.scalar() or 0
        r = await db.execute(select(func.min(Measurement.time_measured)))
        earliest_measurement = r.scalar()
        r = await db.execute(select(func.max(Measurement.time_measured)))
        latest_measurement = r.scalar()

    try:
        if not use_materialized_views:
            raise ValueError("skip")
        res = await db.execute(text("SELECT * FROM active_stations_summary LIMIT 1"))
        active_summary = res.first()
        if active_summary:
            active_stations_1h = active_summary.last_hour or 0
            active_stations_24h = active_summary.last_24_hours or 0
            active_stations_7d = active_summary.last_7_days or 0
            active_stations_30d = active_summary.last_30_days or 0
            if blacklist:
                s1, s24, s7, s30 = await _blacklist_active_station_counts(
                    db, blacklist, one_hour_ago, one_day_ago, seven_days_ago, thirty_days_ago
                )
                active_stations_1h = max(0, active_stations_1h - s1)
                active_stations_24h = max(0, active_stations_24h - s24)
                active_stations_7d = max(0, active_stations_7d - s7)
                active_stations_30d = max(0, active_stations_30d - s30)
        else:
            aq = select(func.count(distinct(Station.id))).where(
                Station.last_active.isnot(None),
                Station.last_active >= one_hour_ago
            )
            if blacklist:
                aq = aq.where(~Station.device.in_(blacklist))
            r = await db.execute(aq)
            active_stations_1h = r.scalar() or 0
            aq = select(func.count(distinct(Station.id))).where(
                Station.last_active.isnot(None),
                Station.last_active >= one_day_ago
            )
            if blacklist:
                aq = aq.where(~Station.device.in_(blacklist))
            r = await db.execute(aq)
            active_stations_24h = r.scalar() or 0
            aq = select(func.count(distinct(Station.id))).where(
                Station.last_active.isnot(None),
                Station.last_active >= seven_days_ago
            )
            if blacklist:
                aq = aq.where(~Station.device.in_(blacklist))
            r = await db.execute(aq)
            active_stations_7d = r.scalar() or 0
            aq = select(func.count(distinct(Station.id))).where(
                Station.last_active.isnot(None),
                Station.last_active >= thirty_days_ago
            )
            if blacklist:
                aq = aq.where(~Station.device.in_(blacklist))
            r = await db.execute(aq)
            active_stations_30d = r.scalar() or 0
    except Exception:
        await db.rollback()
        aq = select(func.count(distinct(Station.id))).where(
            Station.last_active.isnot(None),
            Station.last_active >= one_hour_ago
        )
        if blacklist:
            aq = aq.where(~Station.device.in_(blacklist))
        r = await db.execute(aq)
        active_stations_1h = r.scalar() or 0
        aq = select(func.count(distinct(Station.id))).where(
            Station.last_active.isnot(None),
            Station.last_active >= one_day_ago
        )
        if blacklist:
            aq = aq.where(~Station.device.in_(blacklist))
        r = await db.execute(aq)
        active_stations_24h = r.scalar() or 0
        aq = select(func.count(distinct(Station.id))).where(
            Station.last_active.isnot(None),
            Station.last_active >= seven_days_ago
        )
        if blacklist:
            aq = aq.where(~Station.device.in_(blacklist))
        r = await db.execute(aq)
        active_stations_7d = r.scalar() or 0
        aq = select(func.count(distinct(Station.id))).where(
            Station.last_active.isnot(None),
            Station.last_active >= thirty_days_ago
        )
        if blacklist:
            aq = aq.where(~Station.device.in_(blacklist))
        r = await db.execute(aq)
        active_stations_30d = r.scalar() or 0

    try:
        if not use_materialized_views:
            raise ValueError("skip")
        res = await db.execute(text("SELECT * FROM measurements_timeframe_summary LIMIT 1"))
        measurements_summary = res.first()
        if measurements_summary:
            measurements_24h = measurements_summary.last_24h or 0
            measurements_7d = measurements_summary.last_7d or 0
            measurements_30d = measurements_summary.last_30d or 0
            if blacklist:
                m24, m7, m30 = await _blacklist_measurement_timeframe_counts(
                    db, blacklist, one_day_ago, seven_days_ago, thirty_days_ago
                )
                measurements_24h = max(0, measurements_24h - m24)
                measurements_7d = max(0, measurements_7d - m7)
                measurements_30d = max(0, measurements_30d - m30)
        else:
            r = await db.execute(select(func.count(Measurement.id)).where(Measurement.time_measured >= one_day_ago))
            measurements_24h = r.scalar() or 0
            r = await db.execute(select(func.count(Measurement.id)).where(Measurement.time_measured >= seven_days_ago))
            measurements_7d = r.scalar() or 0
            r = await db.execute(select(func.count(Measurement.id)).where(Measurement.time_measured >= thirty_days_ago))
            measurements_30d = r.scalar() or 0
    except Exception:
        await db.rollback()
        if blacklist:
            mq = select(func.count(Measurement.id)).join(Station).where(
                Measurement.time_measured >= one_day_ago, ~Station.device.in_(blacklist)
            )
            r = await db.execute(mq)
            measurements_24h = r.scalar() or 0
            mq = select(func.count(Measurement.id)).join(Station).where(
                Measurement.time_measured >= seven_days_ago, ~Station.device.in_(blacklist)
            )
            r = await db.execute(mq)
            measurements_7d = r.scalar() or 0
            mq = select(func.count(Measurement.id)).join(Station).where(
                Measurement.time_measured >= thirty_days_ago, ~Station.device.in_(blacklist)
            )
            r = await db.execute(mq)
            measurements_30d = r.scalar() or 0
        else:
            r = await db.execute(select(func.count(Measurement.id)).where(Measurement.time_measured >= one_day_ago))
            measurements_24h = r.scalar() or 0
            r = await db.execute(select(func.count(Measurement.id)).where(Measurement.time_measured >= seven_days_ago))
            measurements_7d = r.scalar() or 0
            r = await db.execute(select(func.count(Measurement.id)).where(Measurement.time_measured >= thirty_days_ago))
            measurements_30d = r.scalar() or 0

    try:
        if not use_materialized_views:
            raise ValueError("skip")
        res = await db.execute(text("SELECT source, count FROM stations_by_source_summary"))
        source_results = res.all()
        stations_by_source = {}
        for source_id, count in source_results:
            if count > 0:
                stations_by_source[Source.get_name(source_id)] = count
        if blacklist and stations_by_source:
            bl_src = await _blacklist_stations_by_source_counts(db, blacklist)
            for src_id, c in bl_src.items():
                name = Source.get_name(src_id)
                if name not in stations_by_source:
                    continue
                new_c = stations_by_source[name] - c
                if new_c <= 0:
                    del stations_by_source[name]
                else:
                    stations_by_source[name] = new_c
    except Exception:
        await db.rollback()
        stations_by_source = {}
        for source_id in [Source.LD, Source.LDTTN, Source.SC]:
            sq = select(func.count(Station.id)).where(Station.source == source_id)
            if blacklist:
                sq = sq.where(~Station.device.in_(blacklist))
            r = await db.execute(sq)
            count = r.scalar() or 0
            if count > 0:
                stations_by_source[Source.get_name(source_id)] = count

    try:
        if not use_materialized_views:
            raise ValueError("skip")
        res = await db.execute(text("SELECT country_name, station_count FROM stations_by_country_summary"))
        country_results = res.all()
        stations_by_country_dict = {country: count for country, count in country_results}
    except Exception:
        await db.rollback()
        try:
            cq = (
                select(
                    Country.name,
                    func.count(distinct(Station.id)).label('station_count')
                )
                .join(City, Country.id == City.country_id)
                .join(Location, City.id == Location.city_id)
                .join(Station, Location.id == Station.location_id)
            )
            if blacklist:
                cq = cq.where(~Station.device.in_(blacklist))
            cq = cq.group_by(Country.name)
            r = await db.execute(cq)
            stations_by_country = r.all()
            stations_by_country_dict = {country: count for country, count in stations_by_country}
        except Exception:
            await db.rollback()
            stations_by_country_dict = {}

    try:
        if not use_materialized_views:
            raise ValueError("skip")
        res = await db.execute(text("SELECT city_name, country_name, station_count FROM top_cities_summary"))
        top_cities_results = res.all()
        top_cities_list = [
            {"city": city, "country": country, "station_count": count}
            for city, country, count in top_cities_results
        ]
    except Exception:
        await db.rollback()
        try:
            tcq = (
                select(
                    City.name,
                    Country.name.label('country'),
                    func.count(distinct(Station.id)).label('station_count')
                )
                .join(Country, City.country_id == Country.id)
                .join(Location, City.id == Location.city_id)
                .join(Station, Location.id == Station.location_id)
            )
            if blacklist:
                tcq = tcq.where(~Station.device.in_(blacklist))
            tcq = tcq.group_by(City.name, Country.name).order_by(
                func.count(distinct(Station.id)).desc()
            ).limit(10)
            r = await db.execute(tcq)
            top_cities = r.all()
            top_cities_list = [
                {"city": city, "country": country, "station_count": count}
                for city, country, count in top_cities
            ]
        except Exception:
            await db.rollback()
            top_cities_list = []

    try:
        res = await db.execute(text("SELECT sensor_model, count FROM sensor_models_summary"))
        sensor_results = res.all()
        sensor_models_dict = {}
        for sensor_id, count in sensor_results:
            sensor_name = SensorModel.get_sensor_name(sensor_id)
            sensor_models_dict[sensor_name] = count
    except Exception:
        await db.rollback()
        try:
            r = await db.execute(
                select(
                    Measurement.sensor_model,
                    func.count(distinct(Measurement.id)).label('count')
                ).group_by(Measurement.sensor_model)
            )
            sensor_models_dist = r.all()
            sensor_models_dict = {}
            for sensor_id, count in sensor_models_dist:
                sensor_name = SensorModel.get_sensor_name(sensor_id)
                sensor_models_dict[sensor_name] = count
        except Exception:
            await db.rollback()
            sensor_models_dict = {}

    def safe_float(value):
        if value is None:
            return None
        try:
            fval = float(value)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
        except (ValueError, TypeError):
            return None

    try:
        res = await db.execute(
            text("SELECT dimension, value_count, avg_value, min_value, max_value FROM dimension_statistics_summary")
        )
        dimension_results = res.all()
        dimensions_list = []
        for dim_id, count, avg_val, min_val, max_val in dimension_results:
            dimensions_list.append({
                "dimension_id": dim_id,
                "dimension_name": Dimension.get_name(dim_id),
                "unit": Dimension.get_unit(dim_id),
                "value_count": count,
                "average_value": safe_float(avg_val),
                "min_value": safe_float(min_val),
                "max_value": safe_float(max_val)
            })
        dimensions_list.sort(key=lambda x: x['value_count'], reverse=True)
    except Exception:
        await db.rollback()
        r = await db.execute(
            select(
                Values.dimension,
                func.count(Values.id).label('count'),
                func.avg(Values.value).label('avg_value'),
                func.min(Values.value).label('min_value'),
                func.max(Values.value).label('max_value')
            ).where(
                Values.value.isnot(None),
                cast(Values.value, String) != 'nan'
            ).group_by(Values.dimension)
        )
        dimensions_dist = r.all()
        dimensions_list = []
        for dim_id, count, avg_val, min_val, max_val in dimensions_dist:
            dimensions_list.append({
                "dimension_id": dim_id,
                "dimension_name": Dimension.get_name(dim_id),
                "unit": Dimension.get_unit(dim_id),
                "value_count": count,
                "average_value": safe_float(avg_val),
                "min_value": safe_float(min_val),
                "max_value": safe_float(max_val)
            })
        dimensions_list.sort(key=lambda x: x['value_count'], reverse=True)

    try:
        res = await db.execute(text("SELECT sensor_model, count FROM calibration_sensors_summary"))
        calibration_results = res.all()
        calibration_sensors_dict = {}
        for sensor_id, count in calibration_results:
            sensor_name = SensorModel.get_sensor_name(sensor_id)
            calibration_sensors_dict[sensor_name] = count
    except Exception:
        await db.rollback()
        try:
            r = await db.execute(
                select(
                    CalibrationMeasurement.sensor_model,
                    func.count(distinct(CalibrationMeasurement.id)).label('count')
                ).group_by(CalibrationMeasurement.sensor_model)
            )
            calibration_by_sensor = r.all()
            calibration_sensors_dict = {}
            for sensor_id, count in calibration_by_sensor:
                sensor_name = SensorModel.get_sensor_name(sensor_id)
                calibration_sensors_dict[sensor_name] = count
        except Exception:
            await db.rollback()
            calibration_sensors_dict = {}

    try:
        res = await db.execute(text('SELECT level, count FROM status_by_level_summary'))
        status_results = res.all()
        status_by_level_dict = {f"level_{level}": count for level, count in status_results}
    except Exception:
        await db.rollback()
        try:
            r = await db.execute(
                select(
                    StationStatus.level,
                    func.count(StationStatus.id).label('count')
                ).group_by(StationStatus.level)
            )
            status_by_level = r.all()
            status_by_level_dict = {f"level_{level}": count for level, count in status_by_level}
        except Exception:
            await db.rollback()
            status_by_level_dict = {}

    statistics = {
        "timestamp": format_datetime_vienna_iso(now),
        "totals": {
            "countries": total_countries,
            "cities": total_cities,
            "locations": total_locations,
            "stations": total_stations,
            "measurements": total_measurements,
            "calibration_measurements": total_calibration_measurements,
            "values": total_values,
            "station_statuses": total_station_statuses
        },
        "active_stations": {
            "last_hour": active_stations_1h,
            "last_24_hours": active_stations_24h,
            "last_7_days": active_stations_7d,
            "last_30_days": active_stations_30d
        },
        "data_coverage": {
            "earliest_measurement": format_datetime_vienna_iso(earliest_measurement)
            if earliest_measurement
            else None,
            "latest_measurement": format_datetime_vienna_iso(latest_measurement)
            if latest_measurement
            else None,
            "measurements_last_24h": measurements_24h,
            "measurements_last_7d": measurements_7d,
            "measurements_last_30d": measurements_30d
        },
        "distribution": {
            "stations_by_source": stations_by_source,
            "stations_by_country": stations_by_country_dict,
            "top_cities": top_cities_list,
            "sensor_models": sensor_models_dict,
            "calibration_sensors": calibration_sensors_dict,
            "status_by_level": status_by_level_dict
        },
        "dimensions": dimensions_list
    }

    cache.set(cache_key, json.dumps(statistics, default=str).encode("utf-8"))
    return _statistics_json_response(statistics, now)
