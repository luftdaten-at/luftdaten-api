import csv
import json
import io
import logging
import numpy as np
from fastapi import APIRouter, Depends, Response, HTTPException, Query
from dependencies import get_blacklist
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, text, case, select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from database import get_db
from collections import defaultdict

from models import Station, Location, Measurement, CalibrationMeasurement, Values, StationStatus, City
from schemas import StationDataCreate, SensorsCreate, StationStatusCreate
from utils import get_or_create_station, standard_output_to_csv, standard_output_to_json, as_naive_utc, max_as_naive_utc
from enums import Precision, OutputFormat, Order, Dimension, CURRENT_TIME_RANGE_MINUTES


router = APIRouter()


def _parse_required_station_ids(station_ids: str) -> list[str]:
    devices = [part.strip() for part in station_ids.split(",")]
    devices = [d for d in devices if d]
    if not devices:
        raise HTTPException(
            status_code=422,
            detail="station_ids is required and must contain at least one device ID",
        )
    return devices


@router.get('/calibration', response_class=Response, tags=['station', 'calibration'])
async def get_calibration_data(
    station_ids: str = Query(None, description="Comma-separated list of station device IDs to filter by. If not provided, all stations with calibration data are returned."),
    data: bool = Query(True, description="If True, returns calibration measurement data. If False, returns only station device IDs."),
    hours: int = Query(1, description="Number of hours to look back for calibration measurements. Default is 1 hour."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist)
):
    stmt = select(Station).join(Station.calibration_measurements).distinct()
    r = await db.execute(stmt)
    stations = list(r.scalars().unique().all())
    if station_ids is not None:
        station_id_list = [s.strip() for s in station_ids.split(",") if s.strip()]
        stmt = select(Station).where(Station.device.in_(station_id_list))
        r = await db.execute(stmt)
        stations = list(r.scalars().all())
    if blacklist:
        stations = [s for s in stations if s.device not in blacklist]
    csv_lines = []
    lower = as_naive_utc(datetime.now(timezone.utc) - timedelta(hours=hours))
    if data:
        measurements = []
        for station in stations:
            mr = await db.execute(
                select(CalibrationMeasurement)
                .where(
                    CalibrationMeasurement.station_id == station.id,
                    CalibrationMeasurement.time_measured >= lower
                )
                .options(selectinload(CalibrationMeasurement.values), selectinload(CalibrationMeasurement.station))
            )
            measurements.extend(mr.scalars().all())
        for m in measurements:
            for v in m.values:
                csv_lines.append(','.join(str(x) for x in [
                    m.station.device,
                    m.sensor_model,
                    v.dimension,
                    v.value,
                    m.time_measured,
                ]))
    else:
        for station in stations:
            csv_lines.append(str(station.device))

    return Response(content='\n'.join(csv_lines), media_type="text/csv")


@router.get("/info", response_class=Response, tags=['station'])
async def get_station_info(
    station_id: str = Query(..., description="The device ID of the station to get information for."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist)
):
    if station_id in blacklist:
        raise HTTPException(status_code=404, detail="Station not found")
    r = await db.execute(
        select(Station)
        .where(Station.device == station_id)
        .options(selectinload(Station.location))
    )
    station = r.scalar_one_or_none()
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    r = await db.execute(
        select(Measurement)
        .where(Measurement.station_id == station.id, Measurement.time_measured == station.last_active)
        .options(selectinload(Measurement.values))
    )
    measurements = r.scalars().all()
    j = {
        "station": {
            "time": station.last_active.isoformat(),
            "device": station.device,
            "firmware": station.firmware,
            "location": {
                "lat": station.location.lat,
                "lon": station.location.lon,
                "height": station.location.height
            }
        },
        "sensors": {
            idx: {"type": m.sensor_model, "data": {v.dimension: v.value for v in m.values}}
            for idx, m in enumerate(measurements)
        }
    }
    return Response(content=json.dumps(j), media_type='application/json')


@router.get("/current/all", response_class=Response, tags=["station", "current"], deprecated=True)
async def get_current_station_data_all(
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist),
):
    PM2_5_LOWER_BOUND, PM2_5_UPPER_BOUND = Dimension.get_filter_threshold(Dimension.PM2_5)

    stmt = (
        select(
            Station.device,
            Location.lat,
            Location.lon,
            func.avg(case((Values.dimension == Dimension.PM1_0, Values.value))).label("PM1"),
            func.avg(case((Values.dimension == Dimension.PM2_5, Values.value))).label("PM2_5"),
            func.avg(case((Values.dimension == Dimension.PM10_0, Values.value))).label("PM10"),
        )
        .join(Measurement, Measurement.station_id == Station.id)
        .join(Location, Location.id == Measurement.location_id)
        .join(Values, Values.measurement_id == Measurement.id)
        .where(Station.last_active == Measurement.time_measured)
        .group_by(
            Station.id,
            Station.device,
            Measurement.id,
            Measurement.time_measured,
            Location.lat,
            Location.lon
        )
        .having(func.avg(case((Values.dimension == Dimension.PM2_5, Values.value))) > PM2_5_LOWER_BOUND)
        .having(func.avg(case((Values.dimension == Dimension.PM2_5, Values.value))) < PM2_5_UPPER_BOUND)
        .order_by(Measurement.time_measured)
    )
    if blacklist:
        stmt = stmt.where(~Station.device.in_(blacklist))

    r = await db.execute(stmt)
    rows = r.all()

    csv_out = "sid,latitude,longitude,pm1,pm25,pm10\n"
    csv_out += "\n".join(",".join([str(y) for y in x]) for x in rows)

    return Response(content=csv_out, media_type="text/csv")


@router.get("/history", response_class=Response, tags=["station"], deprecated=True)
async def get_history_station_data(
    station_ids: str = Query(None, description="Comma-separated list of station device IDs. If not provided, all stations are included."),
    smooth: str = Query("100", description="Smoothing parameter (currently not used, maintained for compatibility)."),
    start: str = Query(None, description="Start time in ISO format: YYYY-MM-DDThh:mm+xx:xx. If not provided, returns all available data."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist),
):
    start_time = datetime.fromisoformat(start) if start else None
    sid_list = station_ids.split(',') if station_ids else None

    stmt = (
        select(
            Measurement.time_measured,
            Station.device,
            Location.lat,
            Location.lon,
            func.avg(case((Values.dimension == 2, Values.value))).label("PM1"),
            func.avg(case((Values.dimension == 3, Values.value))).label("PM2_5"),
            func.avg(case((Values.dimension == 5, Values.value))).label("PM10"),
        )
        .join(Measurement, Measurement.station_id == Station.id)
        .join(Location, Location.id == Measurement.location_id)
        .join(Values, Values.measurement_id == Measurement.id)
        .group_by(
            Station.id,
            Station.device,
            Measurement.id,
            Measurement.time_measured,
            Location.lat,
            Location.lon
        )
        .having(func.avg(case((Values.dimension == 2, Values.value))).isnot(None))
        .having(func.avg(case((Values.dimension == 3, Values.value))).isnot(None))
        .having(func.avg(case((Values.dimension == 5, Values.value))).isnot(None))
        .order_by(Measurement.time_measured)
    )

    if sid_list:
        stmt = stmt.where(Station.device.in_(sid_list))
    if blacklist:
        stmt = stmt.where(~Station.device.in_(blacklist))

    if start_time:
        stmt = stmt.where(Measurement.time_measured >= start_time)

    r = await db.execute(stmt)
    rows = r.all()

    csv_out = "timestamp,sid,latitude,longitude,pm1,pm25,pm10\n"
    csv_out += "\n".join(
        ",".join([time.isoformat()] + [str(o) for o in other])
        for time, *other in rows
    )

    return Response(content=csv_out, media_type="text/csv")


@router.get("/current", response_class=Response, tags=["station", "current"])
async def get_current_station_data(
    station_ids: str = Query(None, description="Comma-separated list of station device IDs to filter by. If not provided, all active stations are returned."),
    last_active: int = Query(3600, description="Time window in seconds. Stations with last_active within this window are considered active. Default is 3600 seconds (1 hour)."),
    output_format: str = Query("geojson", description="Output format: 'geojson' or 'csv'. Default is 'geojson'."),
    calibration_data: bool = Query(False, description="If true, includes calibration sensor data in the response."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist)
):
    time_threshold = as_naive_utc(
        datetime.now(tz=ZoneInfo("Europe/Vienna")) - timedelta(seconds=last_active)
    )

    if station_ids:
        station_id_list = [s.strip() for s in station_ids.split(",") if s.strip()]
        station_id_list = [s for s in station_id_list if s not in blacklist]
        if station_id_list:
            stmt = select(Station).join(Location).where(Station.device.in_(station_id_list)).options(
                selectinload(Station.location)
            )
            r = await db.execute(stmt)
            stations = list(r.scalars().all())
        else:
            stations = []
    else:
        stmt = select(Station).join(Location).where(Station.last_active >= time_threshold).options(
            selectinload(Station.location)
        )
        r = await db.execute(stmt)
        stations = list(r.scalars().all())
    if blacklist:
        stations = [s for s in stations if s.device not in blacklist]
    if not stations:
        raise HTTPException(status_code=404, detail="No stations found")

    if output_format == "geojson":
        features = []
        for station in stations:
            r = await db.execute(
                select(Measurement)
                .where(
                    Measurement.station_id == station.id,
                    Measurement.time_measured == station.last_active
                )
                .options(selectinload(Measurement.values))
            )
            measurements = r.scalars().all()

            sensors = []
            for measurement in measurements:
                values = measurement.values
                sensors.append({
                    "sensor_model": measurement.sensor_model,
                    "values": [{"dimension": value.dimension, "value": value.value} for value in values]
                })

            calibration_sensors = []
            if calibration_data:
                cr = await db.execute(
                    select(CalibrationMeasurement)
                    .where(
                        CalibrationMeasurement.station_id == station.id,
                        CalibrationMeasurement.time_measured == station.last_active
                    )
                    .options(selectinload(CalibrationMeasurement.values))
                )
                for calibration_measurement in cr.scalars().all():
                    calibration_values = calibration_measurement.values
                    calibration_sensors.append({
                        "sensor_model": calibration_measurement.sensor_model,
                        "values": [{"dimension": value.dimension, "value": value.value} for value in calibration_values]
                    })

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [station.location.lon, station.location.lat],
                },
                "properties": {
                    "device": station.device,
                    "time": str(station.last_active),
                    "height": station.location.height,
                    "sensors": sensors
                }
            })

            if calibration_data and calibration_sensors:
                features[-1]["properties"]["calibration_sensors"] = calibration_sensors

        content = {
            "type": "FeatureCollection",
            "features": features,
        }
        content = json.dumps(content)
        media_type = "application/geo+json"

    elif output_format == "csv":
        csv_data = "device,lat,lon,last_active,height,sensor_model,dimension,value"
        if calibration_data:
            csv_data += ",calibration"
        csv_data += "\n"

        for station in stations:
            r = await db.execute(
                select(Measurement)
                .where(
                    Measurement.station_id == station.id,
                    Measurement.time_measured == station.last_active
                )
                .options(selectinload(Measurement.values))
            )
            measurements = r.scalars().all()

            for measurement in measurements:
                values = measurement.values
                for value in values:
                    csv_data += f"{station.device},{station.location.lat},{station.location.lon},{station.last_active},{station.location.height},{measurement.sensor_model},{value.dimension},{value.value}"
                    if calibration_data:
                        csv_data += f',{False}'
                    csv_data += "\n"

            if calibration_data:
                cr = await db.execute(
                    select(CalibrationMeasurement)
                    .where(
                        CalibrationMeasurement.station_id == station.id,
                        CalibrationMeasurement.time_measured == station.last_active
                    )
                    .options(selectinload(CalibrationMeasurement.values))
                )
                for calibration_measurement in cr.scalars().all():
                    calibration_values = calibration_measurement.values
                    for value in calibration_values:
                        csv_data += f"{station.device},{station.location.lat},{station.location.lon},{station.last_active},{station.location.height},{calibration_measurement.sensor_model},{value.dimension},{value.value},{True}\n"

        content = csv_data
        media_type = "text/csv"

    else:
        return Response(content="Invalid output format", media_type="text/plain", status_code=400)

    return Response(content=content, media_type=media_type)


@router.post("/status", tags=["station"])
async def create_station_status(
    station: StationDataCreate,
    status_list: list[StationStatusCreate],
    db: AsyncSession = Depends(get_db)
):
    db_station = await get_or_create_station(
        db=db,
        station=station
    )

    for status in status_list:
        db_status = StationStatus(
            station_id=db_station.id,
            timestamp=as_naive_utc(status.time),
            level=status.level,
            message=status.message
        )
        db.add(db_status)

    await db.commit()

    return {"status": "success"}


@router.post("/data", tags=["station"])
async def create_station_data(
    station: StationDataCreate,
    sensors: SensorsCreate,
    db: AsyncSession = Depends(get_db)
):
    MeasurementClass = Measurement

    if station.calibration_mode:
        MeasurementClass = CalibrationMeasurement

    db_station = await get_or_create_station(
        db=db,
        station=station
    )

    time_received = as_naive_utc(datetime.now(timezone.utc))

    for sensor_id, sensor_data in sensors.root.items():
        measured_at = as_naive_utc(station.time)
        r = await db.execute(
            select(MeasurementClass).where(
                MeasurementClass.station_id == db_station.id,
                MeasurementClass.time_measured == measured_at,
                MeasurementClass.sensor_model == sensor_data.type
            )
        )
        existing_measurement = r.scalar_one_or_none()

        if existing_measurement:
            raise HTTPException(
                status_code=422,
                detail="Measurement already in Database"
            )

        db_measurement = MeasurementClass(
            sensor_model=sensor_data.type,
            station_id=db_station.id,
            time_measured=measured_at,
            time_received=time_received,
            location_id=db_station.location_id
        )
        db.add(db_measurement)
        await db.flush()

        for dimension, value in sensor_data.data.items():
            if station.calibration_mode:
                db_value = Values(
                    dimension=dimension,
                    value=value,
                    calibration_measurement_id=db_measurement.id
                )
            else:
                db_value = Values(
                    dimension=dimension,
                    value=value,
                    measurement_id=db_measurement.id
                )

            db.add(db_value)

    db_station.last_active = max_as_naive_utc(db_station.last_active, station.time)

    await db.commit()

    return {"status": "success"}


@router.get("/topn", response_class=Response, tags=["station"])
async def get_topn_stations_by_dim(
    n: int = Query(..., description="Number of stations to return (limit).", ge=1),
    dimension: int = Query(..., description="Dimension ID to compare (e.g., 2=PM1.0, 3=PM2.5, 5=PM10)."),
    order: Order = Query(Order.MIN, description="Order by minimum ('min') or maximum ('max') value."),
    output_format: OutputFormat = Query(OutputFormat.CSV, description="Output format: 'csv' or 'json'. Default is 'csv'."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist)
):
    LOWER_BOUND, UPPER_BOUND = Dimension.get_filter_threshold(dimension)

    compare = Values.value
    if order == Order.MAX:
        compare = Values.value.desc()
    stmt = (
        select(
            Station.device,
            Measurement.time_measured,
            Values.dimension,
            Values.value,
        )
        .join(Measurement, Measurement.station_id == Station.id)
        .join(Values, Values.measurement_id == Measurement.id)
        .where(Station.last_active == Measurement.time_measured)
        .where(Values.dimension == dimension)
        .where(Values.value > LOWER_BOUND)
        .where(Values.value < UPPER_BOUND)
        .order_by(compare)
        .limit(n)
    )
    if blacklist:
        stmt = stmt.where(~Station.device.in_(blacklist))

    r = await db.execute(stmt)
    rows = r.all()

    if output_format == 'csv':
        return Response(content=standard_output_to_csv(rows), media_type="text/csv")
    elif output_format == 'json':
        return Response(content=await standard_output_to_json(rows, db), media_type="application/json")


@router.get("/historical", response_class=Response, tags=["station"])
async def get_historical_station_data(
    station_ids: str = Query(
        ...,
        description="Comma-separated station device IDs. At least one non-empty ID is required (empty or all-blank is rejected).",
    ),
    start: str = Query(None, description="Start time in ISO format: YYYY-MM-DDThh:mm+xx:xx. If not provided, returns all available data."),
    end: str = Query(None, description="End time in ISO format: YYYY-MM-DDThh:mm+xx:xx, or 'current' for latest measurements. If not provided, returns all available data."),
    precision: Precision = Query(Precision.MAX, description="Time precision for aggregation: 'all' (max), 'hour', 'day', 'week', 'month', 'year'. Default is 'all'."),
    city_slugs: str = Query(None, description="Comma-separated list of city slugs to filter by. If not provided, all cities are included."),
    output_format: OutputFormat = Query(OutputFormat.CSV, description="Output format: 'csv' or 'json'. Default is 'csv'."),
    include_location: bool = Query(False, description="If True, includes location coordinates in JSON response (only applies to JSON format)."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist)
):
    devices = _parse_required_station_ids(station_ids)
    cities = [c.strip() for c in city_slugs.split(",") if c.strip()] if city_slugs else []

    try:
        start_date = datetime.fromisoformat(start) if start else None
        end_date = datetime.fromisoformat(end) if end else None
    except ValueError:
        if end != 'current':
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DDThh:mm")

    time_fram = Precision.get_time_frame(precision)
    truncated_time = func.date_trunc(time_fram, Measurement.time_measured).label('time')

    city_filter = or_(len(cities) == 0, City.slug.in_(cities))

    stmt = (
        select(
            Station.device,
            truncated_time,
            Values.dimension,
            func.avg(Values.value).label('avg_value')
        )
        .select_from(Measurement)
        .join(Values, Values.measurement_id == Measurement.id)
        .join(Station, Measurement.station_id == Station.id)
        .where(Station.device.in_(devices))
        .join(Location, Location.id == Measurement.location_id)
        .outerjoin(City, City.id == Location.city_id)
        .where(city_filter)
        .group_by(Measurement.station_id, Station.device, truncated_time, Values.dimension)
        .order_by(Measurement.station_id, Station.device, truncated_time, Values.dimension)
    )
    if blacklist:
        stmt = stmt.where(~Station.device.in_(blacklist))
    data_list = []
    if end == "current":
        start_cutoff = as_naive_utc(
            datetime.now(tz=timezone.utc) - timedelta(minutes=CURRENT_TIME_RANGE_MINUTES)
        )

        sql = """select s.device, m.time_measured, v.dimension, avg(v.value) from stations as s
inner join measurements m on m.station_id = s.id
inner join values v on v.measurement_id = m.id
where s.last_active = m.time_measured"""
        device_placeholders = ", ".join(f":d{i}" for i in range(len(devices)))
        sql += f" AND s.device IN ({device_placeholders})"
        params = {f"d{i}": dev for i, dev in enumerate(devices)}
        if blacklist:
            placeholders = ", ".join(f":b{i}" for i in range(len(blacklist)))
            sql += f" AND s.device NOT IN ({placeholders})"
            params.update({f"b{i}": bid for i, bid in enumerate(blacklist)})
        sql += " group by s.id, s.device, m.time_measured, v.dimension;"
        r = await db.execute(text(sql), params)
        data = r.all()

        dim_group = defaultdict(list)
        low = {}
        high = {}

        for _, _, dim, val in data:
            dim_group[dim].append(val)

        for dim, val_list in dim_group.items():
            a = np.array(val_list)
            low[dim] = np.percentile(a, 100 * (0.01 / 2))
            high[dim] = np.percentile(a, 100 * (1 - (0.01 / 2)))

        data_list = [
            (
                device,
                time,
                dim,
                val if (time if time.tzinfo is None else as_naive_utc(time)) >= start_cutoff
                and low[dim] < val < high[dim]
                else None
            ) for (device, time, dim, val) in data
        ]
    else:
        if start_date is not None:
            stmt = stmt.where(truncated_time >= start_date)
        if end_date is not None:
            stmt = stmt.where(truncated_time <= end_date)
        r = await db.execute(stmt)
        data_list = r.all()

    if output_format == 'csv':
        return Response(content=standard_output_to_csv(data_list), media_type="text/csv")
    elif output_format == 'json':
        return Response(
            content=await standard_output_to_json(data_list, db, include_location=include_location),
            media_type="application/json"
        )


@router.get("/all", response_class=Response, tags=["station"])
async def get_all_stations(
    output_format: str = Query(default="csv", enum=["json", "csv"], description="Output format: 'csv' or 'json'. Default is 'csv'."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist)
):
    use_materialized_view = True
    result = []

    try:
        r = await db.execute(text("""
            SELECT
                station_id,
                device,
                last_active,
                location_lat,
                location_lon,
                location_height,
                measurements_count
            FROM stations_summary
            ORDER BY device
        """))
        stations_summary = r.all()

        if stations_summary:
            for row in stations_summary:
                if blacklist and row.device in blacklist:
                    continue
                station_data = {
                    "id": row.device,
                    "last_active": row.last_active,
                    "location": {
                        "lat": row.location_lat,
                        "lon": row.location_lon
                    },
                    "measurements_count": row.measurements_count
                }
                result.append(station_data)
        else:
            use_materialized_view = False
    except Exception as e:
        await db.rollback()
        use_materialized_view = False
        logging.getLogger(__name__).debug(f"Materialized view not available, using direct queries: {e}")

    if not use_materialized_view:
        stmt = select(Station).options(selectinload(Station.location))
        if blacklist:
            stmt = stmt.where(~Station.device.in_(blacklist))
        r = await db.execute(stmt)
        stations = r.scalars().all()

        result = []
        for station in stations:
            cr = await db.execute(
                select(func.count(Measurement.id)).where(Measurement.station_id == station.id)
            )
            measurements_count = cr.scalar() or 0

            station_data = {
                "id": station.device,
                "last_active": station.last_active,
                "location": {
                    "lat": station.location.lat if station.location else None,
                    "lon": station.location.lon if station.location else None
                },
                "measurements_count": measurements_count
            }
            result.append(station_data)

    if output_format == "json":
        json_result = []
        for station_data in result:
            json_station = {
                "id": station_data["id"],
                "last_active": station_data["last_active"].isoformat() if station_data["last_active"] else None,
                "location": station_data["location"],
                "measurements_count": station_data["measurements_count"]
            }
            json_result.append(json_station)
        return Response(content=json.dumps(json_result), media_type="application/json")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["id", "last_active", "location_lat", "location_lon", "measurements_count"])

    for station in result:
        writer.writerow([
            station["id"],
            station["last_active"],
            station["location"]["lat"],
            station["location"]["lon"],
            station["measurements_count"]
        ])

    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=stations.csv"
    return response
