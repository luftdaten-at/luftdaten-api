# Security and versioning

## Security in OpenAPI

**Runtime auth** in FastAPI uses **dependencies** (`Depends` with OAuth2, API key headers, etc.). The OpenAPI spec should still advertise **how** to authenticate:

- **`openapi_components`** and security scheme definitions, or
- high-level `FastAPI(dependencies=[...])` combined with schema customization where needed

so `/docs` shows the **Authorize** flow or required headers. If the schema does not list a scheme, clients may discover auth only from prose or by trial and error.

When an endpoint is **admin-only** or requires a special header, document it in the path operation’s `description` or security requirements so it matches the real dependency (see [07-checklist-luftdaten-api.md](07-checklist-luftdaten-api.md) for this project).

Official overview: [Security - FastAPI](https://fastapi.tiangolo.com/tutorial/security/).

## Versioning in luftdaten-api

- Public HTTP paths use the **`/v1`** prefix (e.g. `GET /v1/station/current`).
- **`VersionPrefixMiddleware`** in `code/main.py` **strips** `/v1` from the request path before routing, while routers are mounted without that prefix. Internally, routes look like `/station/...`, `/city/...`.
- **`servers`** in `FastAPI()` includes `url: /v1` so relative path display in UIs is consistent with the external prefix.
- **Prometheus** and some health or monitor paths may live **outside** `/v1` (e.g. `/metrics`); treat them as a separate “surface” in human docs when describing URLs.

Narrative detail for this API (blacklist, CORS, time zones) lives in [endpoints.md](../endpoints.md); keep cross-cutting rules there or in a short `description` on `FastAPI()` so they are discoverable.

[← Models and responses](05-models-parameters-responses.md) · [Index](README.md) · [Next: Checklist →](07-checklist-luftdaten-api.md)
