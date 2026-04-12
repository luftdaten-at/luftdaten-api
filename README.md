# luftdaten-api

## About luftdaten-api
luftdaten-api ist an open source database for air quality data build on the FastAPI Framework.

## Documentation

### Development
Environment variables: copy **`.env.example`** to **`.env`** and adjust (database credentials, `DB_HOST`, optional `LOG_LEVEL`, monitoring vars for prod).

Development version:

    cp .env.example .env
    docker compose up -d


#### Database migration
Setup alembic folder and config files:
    
    docker compose exec app alembic init alembic

Generate and apply migrations:
    
    docker compose exec app alembic revision --autogenerate -m "Initial migration"
    docker compose exec app alembic upgrade head

Rollback migrations:
    
    docker compose exec app alembic downgrade

#### Database reset

    docker compose down
    docker volume ls
    docker volume rm luftdaten-api_postgres_data
    docker compose up -d
    docker compose exec app alembic upgrade head

#### Running Tests

Run all unit tests via Docker:

    docker compose run --rm test

Or use the convenience script:

    ./run_tests.sh

Run specific test files:

    docker compose run --rm test pytest tests/test_city.py -v
    docker compose run --rm test pytest tests/test_health.py -v
    docker compose run --rm test pytest tests/test_station.py -v

Run tests with coverage (requires pytest-cov in requirements.txt):

    docker compose run --rm test pytest tests/ --cov=. --cov-report=html --cov-report=term

The test service uses a separate test database (`db_test`) that is automatically set up and torn down.

#### Station blacklist

Stations can be excluded from API responses via a blacklist config file. Blacklisted stations are omitted from all station, city, and statistics endpoints.

**Location:** `config/station_blacklist.json`

**Format:** JSON array of device IDs, e.g.:
```json
["12345", "67890"]
```

**Editing:** Add or remove device IDs, save the file, then restart the app. With Docker Compose, the `config/` folder is mounted, so changes take effect after `docker compose restart app`.

**Environment variable:** `STATION_BLACKLIST_FILE` — override the blacklist file path (e.g. `/app/config/station_blacklist.json` in Docker).

**Behavior:**
- Missing file or empty array → no stations excluded
- Invalid JSON → startup fails
- Blacklisted stations return 404 on `/station/info`; they are filtered from all other endpoints

**Station ingest (measurements / status):** Use **POST** to `/v1/station/data` and `/v1/station/status` with the JSON body shape from OpenAPI (`/docs`). **GET** on these paths returns **405** — they will not show up as successful “reads” in traffic summaries. With or without a **trailing slash** is supported (a slash-only route used to **307**-redirect and break some embedded HTTP stacks). Set **`LOG_STATION_INGEST=true`** in `.env` to log each ingest attempt (`path` + HTTP status, including **422**).

#### Monitoring

**Built-in monitor endpoint** (`GET /v1/monitor`):
- Database usage: size, connections, cache hit ratio, transactions, top tables by size
- API stats: request counts by endpoint and status code (since startup)
- Application: uptime, scheduler jobs, blacklist size

**Prometheus metrics** (`GET /v1/metrics` or `/metrics` without `/v1` prefix):
- **HTTP (instrumentator):** `http_requests_total` (labels `handler`, `method`, `status` with `2xx`/`4xx` buckets), `http_request_duration_seconds` (per `handler`), `http_request_duration_highr_seconds` (global latency)
- **Custom `luftdaten_*`:** `luftdaten_http_requests_total{area,method,status}` for roll-up by API area; gauges `luftdaten_blacklist_size`, `luftdaten_scheduler_jobs`, `luftdaten_db_up` (refreshed every minute)
- Scrape noise (`/metrics`, `/health/simple`, `/monitor`) is excluded from default HTTP metrics but still visible in logs; custom area counter follows the same exclusions
- Design details and example PromQL: [`docs/PROMETHEUS_GRAFANA_ENDPOINTS_PLAN.md`](docs/PROMETHEUS_GRAFANA_ENDPOINTS_PLAN.md)

**Optional monitoring stack** (Postgres exporter, Prometheus, Grafana):
- Start with: `docker compose --profile monitoring up -d`
- Grafana: http://localhost:3000 (default login: admin/admin) — datasource and dashboard **Luftdaten API** are provisioned from `monitoring/grafana/`
- Prometheus: http://localhost:9090 — config in `monitoring/prometheus.yml`, optional recording rules in `monitoring/prometheus/rules.yml`
- Grafana panels filter metrics with `job="<name>"`. The **Luftdaten API** dashboard exposes **API Prometheus job** (from `label_values(http_requests_total, job)`); pick the value that matches your scrape config’s `job_name` (default in repo: `luftdaten-api`). If panels show *No data*, check **Status → Targets** in Prometheus and run `http_requests_total` in **Graph** to see the real `job` label. The app must register **`metrics.default()`** alongside the custom `luftdaten_*` instrumentation (see [`code/main.py`](code/main.py)); otherwise `http_requests_total` and latency histograms are never emitted and Grafana stays empty regardless of `job`.
- **`handler="none"`** for most traffic: prometheus-fastapi-instrumentator resolves the route **before** inner middleware runs. `/v1/...` must be stripped **outside** that middleware (see `VersionPrefixMiddleware` in [`code/main.py`](code/main.py)); otherwise routes registered as `/station/...` never match and Grafana shows `none` instead of `/station/current`, etc.

#### Deployment

Build and push to Dockerhub.

    docker build -f Dockerfile.prod -t luftdaten/api:tagname --platform linux/amd64 .
    docker push luftdaten/api:tagname

Currently automaticly done by Github Workflow.
Tags:
    - **staging**: latest version for testing
    - **x.x.x**: released versions for production

### Production

Create docker-compose.prod.yml from example-docker-compose.prod.yml by setting the secret key. Then run:

    docker compose -f docker-compose.prod.yml up -d

Optional **monitoring** (Prometheus, Grafana, postgres_exporter): copy `monitoring/` from the repo next to your compose file, set `GRAFANA_ADMIN_PASSWORD` in `.env`, then:

    docker compose -f docker-compose.prod.yml --profile monitoring up -d

Production example compose exposes Grafana via Traefik at `grafana.staging.api.luftdaten.at` (override with `GF_SERVER_ROOT_URL` in `.env` if your host differs). Traefik’s `loadbalancer.server.port` for Grafana must be **3000** (Grafana’s default HTTP port), not 80 — otherwise Traefik returns **502 Bad Gateway**.

Create database structure:
    
    docker compose exec app alembic upgrade head    

## API Documentation

Open API Standard 3.1

/docs
https://api.luftdaten.at/docs

**Note:** `GET /v1/station/historical` requires **`station_ids`** with at least one device ID (comma-separated). Omitting it or sending an empty value returns **422**; use `GET /v1/station/all` (or similar) to discover IDs first.

## License
This project is licensed under GNU General Public License v3.0.