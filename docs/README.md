# API documentation

Human-readable reference for the HTTP API exposed by **luftdaten-api** (FastAPI).

| Resource | Guide |
|----------|--------|
| Full route list (methods, paths, parameters, responses) | [endpoints.md](endpoints.md) |
| Database (tables, views, indexes) | [database/README.md](database/README.md) |

## Interactive OpenAPI

When the app is running, the same surface is described interactively:

- **Swagger UI:** `{base_url}/docs`
- **ReDoc:** `{base_url}/redoc`
- **OpenAPI JSON:** `{base_url}/openapi.json`

Replace `{base_url}` with your deployment origin (for local Docker, often `http://localhost:8000`).

Versioned API routes are mounted under **`/v1`** (for example `GET /v1/station/current`). Prometheus HTTP metrics are exposed at **`/metrics`** (not under `/v1`).
