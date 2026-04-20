# Views, materialized views, functions, indexes, extensions

Supplementary database objects beyond the [base tables](tables.md).

---

## Normal view: `hourly_avg`

Defined in migration `8e1c45de1275_create_hourly_avg_view.py`.

- **Purpose:** Per-station, per-hour aggregates of `values` joined to `measurements`, rolled into a JSON object of dimension → average.
- **Columns:** `station_id`, `hour` (timestamp truncated to hour), `dimension_avg` (jsonb).
- **Note:** The old `hourly_averages` **table** was removed (`2df6cd6bb99c`); the ORM in `code/models.py` targets this **view** name `hourly_avg`.

---

## Materialized views

Refreshed with **`REFRESH MATERIALIZED VIEW CONCURRENTLY`** where a unique index exists (see migrations `cb023e559c7`, `b3ba2ef0fc0`, `8d4c2b1a9f0e`).

| Materialized view | Role |
|---------------------|------|
| `statistics_summary` | Single-row aggregates: entity counts, earliest/latest `time_measured`, `last_refresh`. |
| `active_stations_summary` | Single row: distinct stations with `last_active` in last 1h / 24h / 7d / 30d (vs `NOW()`). |
| `stations_by_country_summary` | `country_name` → `station_count`. |
| `top_cities_summary` | Top 10 cities by station count (`city_name`, `country_name`, `station_count`). |
| `dimension_statistics_summary` | Per-`dimension`: `value_count`, `avg_value`, `min_value`, `max_value` from `values`. |
| `sensor_models_summary` | Per `sensor_model` on `measurements`: distinct measurement count. |
| `calibration_sensors_summary` | Same for `calibration_measurements`. |
| `status_by_level_summary` | Per `level` on `"stationStatus"`: row counts. |
| `stations_by_source_summary` | Per `source` on `stations`: row counts. |
| `measurements_timeframe_summary` | Single row: measurement counts in last 24h / 7d / 30d. |
| `stations_summary` | Per station: `station_id`, `device`, `last_active`, location fields, `measurements_count`, `last_refresh`. Feeds **`GET /station/all`**. |
| `statistics_endpoint_snapshot` | Single row (`id = 1`), column **`payload`** (jsonb): pre-built JSON for **`GET /statistics`** when no blacklist. |

---

## SQL functions

| Function | Returns | Behavior |
|----------|---------|----------|
| `refresh_statistics_views()` | void | Refreshes all statistics-related materialized views **including** `statistics_endpoint_snapshot`, in dependency-safe order (see `8d4c2b1a9f0e`). Invoked by the app scheduler / `utils.cache.refresh_statistics_views`. |
| `refresh_stations_summary()` | void | Refreshes `stations_summary` only. Invoked by `utils.cache.refresh_stations_summary`. |

---

## Notable indexes

Created across migrations `4e691bbe683`, `b3ba2ef0fc0`, `cb023e559c7`, `8d4c2b1a9f0e`, `b8e4a1c0f2d3`, `f2edce7f694` (partial list; see migrations for `IF NOT EXISTS` and exact definitions).

**Stations / locations**

- `idx_stations_last_active` on `stations(last_active)` where `last_active IS NOT NULL` (partial).
- `idx_stations_location_id`, `idx_stations_source`.
- `idx_locations_city_id`, `idx_locations_country_id`.

**Measurements / calibration**

- `idx_measurements_time_measured`, `idx_measurements_time_station` (`time_measured`, `station_id`).
- `idx_measurements_station_id`, `idx_measurements_location_id`, `idx_measurements_sensor_model`.
- **`idx_measurements_station_time_sensor`** — `(station_id, time_measured, sensor_model)` for ingest dedup lookups (`b8e4a1c0f2d3`).
- **`idx_calibration_measurements_station_time_sensor`** — same shape on `calibration_measurements`.

**Values**

- `idx_values_measurement_id`, `idx_values_calibration_measurement_id`, `idx_values_dimension`.
- `idx_values_dimension_value` partial on `(dimension, value)` where `value` is not null and not nan.

**Station status**

- `idx_station_status_station_id`, `idx_station_status_level` on `"stationStatus"`.

**Materialized view support**

- Unique indexes on refresh-key or natural keys (e.g. `idx_statistics_summary_refresh`, `idx_stations_summary_station_id`, `idx_statistics_endpoint_snapshot_id`, etc.) so **`CONCURRENTLY`** refresh is valid.

---

## Extensions

| Extension | Migration | Notes |
|-----------|-----------|--------|
| `pg_stat_statements` | `7f3a9c2e1d0b` | Requires `shared_preload_libraries` to include `pg_stat_statements` in PostgreSQL config (see Docker `db` service if used). |

---

## Maintenance

- **Statistics bundle:** `SELECT refresh_statistics_views();` (hourly in production per `code/main.py` scheduler).
- **Stations list:** `SELECT refresh_stations_summary();` (e.g. every 10 minutes in default scheduler).
- After major data loads, refreshing these views improves API latency for `/statistics` and `/station/all`.
