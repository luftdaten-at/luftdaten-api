# Base tables

All tables below are ordinary PostgreSQL tables unless noted. Primary keys are surrogate integers unless stated. Integer codes for `source`, `sensor_model`, and `dimension` are defined in [`code/enums.py`](../../code/enums.py).

---

## `countries`

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `name` | text | unique, indexed |
| `slug` | text | unique, indexed |
| `code` | text | unique, indexed (e.g. ISO country code) |

**Relationships:** one-to-many `cities`, optional link from `locations.country_id`.

---

## `cities`

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `name` | text | indexed |
| `slug` | text | unique, indexed |
| `tz` | text | nullable; IANA timezone name |
| `country_id` | integer | FK → `countries.id` |
| `lat`, `lon` | float | nullable coordinates |

**Relationships:** one-to-many `locations` via `locations.city_id`.

---

## `locations`

Physical site; stations and measurements reference it.

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `lat`, `lon`, `height` | float | `height` nullable |
| `city_id` | integer | FK → `cities.id`, nullable |
| `country_id` | integer | FK → `countries.id`, nullable |

**Relationships:** `stations`, `measurements`, `calibration_measurements`.

---

## `stations`

One row per sensing device (identified by `device` string).

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `device` | text | unique, indexed (external device id) |
| `firmware` | text | |
| `apikey` | text | used to authorize writes |
| `last_active` | timestamp | last measurement time (UTC naive) |
| `source` | integer | `Source` enum |
| `location_id` | integer | FK → `locations.id` |

**Relationships:** `measurements`, `calibration_measurements`, `stationStatus`, optional ORM link to `hourly_avg` view (see views doc).

---

## `measurements`

One row per (station, time measured, sensor model) sample for normal (non-calibration) data.

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `time_received` | timestamp | server ingest time (UTC naive) |
| `time_measured` | timestamp | device-reported sample time (UTC naive) |
| `sensor_model` | integer | `SensorModel` enum |
| `location_id` | integer | FK → `locations.id` |
| `station_id` | integer | FK → `stations.id` |

**Relationships:** one-to-many `values` via `values.measurement_id`.

---

## `calibration_measurements`

Same shape as `measurements` for calibration uploads (`calibration_mode` on ingest).

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `time_received` | timestamp | |
| `time_measured` | timestamp | |
| `sensor_model` | integer | |
| `location_id` | integer | FK → `locations.id` |
| `station_id` | integer | FK → `stations.id` |

**Relationships:** one-to-many `values` via `values.calibration_measurement_id`.

---

## `values`

Individual dimension readings for one measurement (normal or calibration).

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `dimension` | integer | `Dimension` enum |
| `value` | float | |
| `measurement_id` | integer | FK → `measurements.id`, nullable |
| `calibration_measurement_id` | integer | FK → `calibration_measurements.id`, nullable |

Exactly one of `measurement_id` / `calibration_measurement_id` should be non-null for a given row in application use.

---

## `stationStatus`

Operational status messages from devices (table name is camelCase in PostgreSQL: `"stationStatus"`).

| Column | Type | Notes |
|--------|------|--------|
| `id` | integer | PK |
| `station_id` | integer | FK → `stations.id` |
| `timestamp` | timestamp | event time |
| `level` | integer | |
| `message` | text | |

---

## ORM-only mapping: `hourly_avg`

SQLAlchemy class `HourlyDimensionAverages` maps to the PostgreSQL **view** named `hourly_avg` (not a base table). See [views-indexes-extensions.md](views-indexes-extensions.md).
