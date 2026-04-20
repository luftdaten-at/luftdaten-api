# HTTP endpoints reference

**API version:** `0.3` (see `code/main.py`).  
**URL prefix:** all routers below are called with the **`/v1`** prefix (e.g. `GET /v1/station/current`). A middleware strips `/v1` internally before routing.

**Station blacklist:** excluded stations are configured server-side (`config/station_blacklist.json`, loaded at startup). Read endpoints omit blacklisted devices where noted; write endpoints are unchanged.

**CORS:** `GET` and `POST` only; origins from `CORS_ORIGINS` or defaults (see `README.md` / `.env.example`).

### Dates and timezones

- **GET responses:** Instants are serialized as **ISO-8601 with `Europe/Vienna` offset** (e.g. `2026-04-10T14:30:00+02:00`) unless noted otherwise.
- **POST `/v1/station/data` (and related writes):** `time` must represent the measurement instant in **UTC**. Prefer a `Z` suffix or explicit offset (`+00:00`). If the value has **no timezone**, it is interpreted as **UTC wall clock** (not local Vienna).
- **sensor.community static import** (`data.json`): `timestamp` strings (`YYYY-MM-DD HH:MM:SS`, no offset) are interpreted as **UTC** wall clock, then stored as UTC-naive in the database (internal batch job only).

---

## Station (`/v1/station`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/station/calibration` | Calibration data or device list as CSV. |
| GET | `/v1/station/info` | Latest measurement snapshot for one device (JSON). |
| GET | `/v1/station/current` | Current measurements for active or selected stations (GeoJSON or CSV). |
| GET | `/v1/station/current/all` | **Deprecated.** All stations’ current PM averages as CSV. |
| GET | `/v1/station/history` | **Deprecated.** Historical PM time series as CSV. |
| GET | `/v1/station/topn` | Top *n* stations by a dimension (CSV or JSON). |
| GET | `/v1/station/historical` | Aggregated historical series (CSV or JSON). |
| GET | `/v1/station/all` | All stations metadata (CSV or JSON). |
| POST | `/v1/station/data` | Ingest measurement payload (JSON body). |
| POST | `/v1/station/status` | Ingest station status events (JSON body). |

### `GET /v1/station/calibration`

Returns **text/csv**.

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `station_ids` | string | — | Comma-separated device IDs; omit for all stations that have calibration data. |
| `data` | bool | `true` | If `true`, CSV rows of measurements; if `false`, one device ID per line. |
| `hours` | int | `1` | Lookback window for measurements when `data=true`. |

Respects blacklist (blacklisted devices omitted).

---

### `GET /v1/station/info`

Returns **application/json**.

| Query | Type | Description |
|-------|------|-------------|
| `station_id` | string | **Required.** Device ID. |

`404` if unknown or blacklisted.

---

### `GET /v1/station/current`

Returns **application/geo+json** or **text/csv**; supports **304** with `If-None-Match` (ETag). Cache-Control includes `max-age=60`.

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `station_ids` | string | — | Comma-separated device IDs; omit for all stations active in window. |
| `last_active` | int | `3600` | Seconds: stations with `last_active` within this window count as active. |
| `output_format` | string | `geojson` | `geojson` or `csv`. |
| `calibration_data` | bool | `false` | Include calibration sensor readings in the payload. |

`404` if no stations match. Blacklist applied.

---

### `GET /v1/station/current/all` (deprecated)

Returns **text/csv** (`sid,latitude,longitude,pm1,pm25,pm10`). No required query params. Blacklist applied.

---

### `GET /v1/station/history` (deprecated)

Returns **text/csv** (`timestamp,sid,latitude,longitude,pm1,pm25,pm10`).

| Query | Type | Description |
|-------|------|-------------|
| `station_ids` | string | Comma-separated devices; omit for all. |
| `smooth` | string | `100` (compatibility; not used). |
| `start` | string | ISO datetime lower bound; omit for full history. |

Blacklist applied.

---

### `GET /v1/station/topn`

Returns **text/csv** or **application/json**.

| Query | Type | Description |
|-------|------|-------------|
| `n` | int | **Required.** Limit ≥ 1. |
| `dimension` | int | **Required.** Dimension ID (e.g. PM axes). |
| `order` | enum | `min` or `max` (`Order`). |
| `output_format` | enum | `csv` or `json` (`OutputFormat`). |

Blacklist applied.

---

### `GET /v1/station/historical`

Returns **text/csv** or **application/json**.

| Query | Type | Description |
|-------|------|-------------|
| `station_ids` | string | **Required.** Comma-separated device IDs (at least one non-empty). |
| `start` | string | ISO start; optional. |
| `end` | string | ISO end, or literal `current` for “latest row” behaviour with outlier filtering. |
| `precision` | enum | `all`, `hour`, `day`, `week`, `month`, `year` (`Precision`). |
| `city_slugs` | string | Optional comma-separated city slugs filter. |
| `output_format` | enum | `csv` or `json`. |
| `include_location` | bool | `false`; for JSON, include coordinates when `true`. |

Blacklist applied. `400` on invalid date format.

---

### `GET /v1/station/all`

Returns **application/json** or **text/csv** (CSV sets `Content-Disposition` for download).

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `output_format` | enum | `csv` | `json` or `csv`. |

Uses `stations_summary` MV when available; falls back to live queries. May return **503** when the database is temporarily unavailable. Blacklist applied.

---

### `POST /v1/station/data`

**Body:** JSON matching `StationDataCreate` + `SensorsCreate` (see `code/schemas.py` and OpenAPI `/docs`). The station `time` field is **UTC** (see *Dates and timezones* above).

Creates measurements (or calibration measurements if `calibration_mode`). **422** if duplicate measurement for same station/time/sensor. Returns `{"status": "success"}`.

Aliases: `POST /v1/station/data/` (hidden from schema, same handler).

---

### `POST /v1/station/status`

**Body:** JSON: station payload (`StationDataCreate`) + list of `StationStatusCreate` entries.

Returns `{"status": "success"}`.

Aliases: `POST /v1/station/status/` (hidden from schema).

---

## City (`/v1/city`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/city/all` | All cities with country metadata (JSON). |
| GET | `/v1/city/current` | City-level current averages (GeoJSON Feature). |

### `GET /v1/city/all`

Returns **application/json**. In-memory cache (~5 min). **404** if no cities.

---

### `GET /v1/city/current`

Returns **application/geo+json**.

| Query | Type | Description |
|-------|------|-------------|
| `city_slug` | string | **Required.** City slug from `/city/all`. |

Uses last hour of measurements; blacklist applied. **404** if city not found.

---

## Health (`/v1/health`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/health/` | Deep check: API, database `SELECT 1`, scheduler. |
| GET | `/v1/health/simple` | Lightweight liveness JSON. |

### `GET /v1/health/`

Returns JSON with `status`, `timestamp`, `version`, `checks` (api, database, scheduler). **503** with detail payload if any check fails.

---

### `GET /v1/health/simple`

Returns JSON: `status`, `timestamp`, `version` (always 200 if the process responds).

---

## Statistics (`/v1/statistics`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/statistics/` | Aggregated database statistics and distributions (JSON). |

Returns JSON with `timestamp`, `totals`, `active_stations`, `data_coverage`, `distribution`, `dimensions`. Uses materialized views / snapshot when possible; subtracts blacklist server-side when non-empty. In-process cache (~15 min) and HTTP `Cache-Control` aligned to that TTL; ETag excludes `timestamp`. See `code/routers/statistics.py`.

---

## Monitor (`/v1/monitor`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/monitor` | Operational snapshot: DB size, connections, cache hit ratio, top tables, in-process API counters, uptime, scheduler job count, blacklist size. |

Returns JSON. Excluded from default Prometheus latency metrics (see `code/main.py`).

---

## Prometheus metrics (no `/v1` prefix)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metrics` | Prometheus exposition format (default + custom HTTP metrics). |

Registered by `prometheus-fastapi-instrumentator` on the app directly.

---

## Summary counts

| Tag (OpenAPI) | Endpoints |
|---------------|-----------|
| `station` | Calibration, info, current, topn, historical, all, POST data/status |
| `calibration` | `GET /station/calibration` |
| `current` | `GET /station/current`, `GET /station/current/all`, `GET /city/current` |
| `city` | `GET /city/all`, `GET /city/current` |
| `health` | `GET /health/`, `GET /health/simple` |
| `statistics` | `GET /statistics/` |
| `monitor` | `GET /monitor` |

For request/response models and enums, use **`/docs`** or **`openapi.json`** against a running instance.
