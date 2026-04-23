# Checklist: luftdaten-api

Use this when adding or changing HTTP endpoints. It ties together [endpoints.md](../endpoints.md), `code/main.py`, and the routers under `code/routers/`.

## OpenAPI and code

- [ ] **Tags:** Every new `tags=[...]` value has a corresponding entry in `openapi_tags` in `code/main.py` *if* you want a group description and stable ordering in `/docs`.
- [ ] **Deprecation:** If a route is legacy, set `deprecated=True` and mention replacement paths in the human doc section.
- [ ] **Hidden duplicates:** Trailing-slash variants use `include_in_schema=False` on the duplicate so OpenAPI does not list two identical operations.
- [ ] **Status codes:** Success and error codes in implementation match `status_code=`, `responses={…}`, and [endpoints.md](../endpoints.md) tables.
- [ ] **Response types:** `response_class` and actual `Content-Type` match (CSV, GeoJSON, JSON); custom types get examples or `responses` when helpful.

## Human documentation ([endpoints.md](../endpoints.md))

- [ ] New or changed **query/body** parameters, **response shape**, and **caching/ETag** behavior are described in the right subsection.
- [ ] **Cross-cutting behavior** (blacklist, CORS, time zones) is not repeated on every line unless a specific endpoint *differs*; link or refer to the global notes at the top of [endpoints.md](../endpoints.md).
- [ ] **Version** in [endpoints.md](../endpoints.md) stays in sync with `version=` in `FastAPI()` in `code/main.py` when you bump the API.

## Security and operations

- [ ] If an endpoint is **admin-only** or needs a key/header, the requirement is clear in the OpenAPI text (or security scheme) *and* in [endpoints.md](../endpoints.md).
- [ ] **Internal-only** paths (e.g. monitoring) are either documented as operational or intentionally omitted from public consumer docs—be consistent.
- [ ] For production, decide whether `openapi_url` / `docs_url` / `redoc_url` stay enabled (see [02-app-metadata-and-servers.md](02-app-metadata-and-servers.md)).

## When to edit what

| Change | Prefer |
|--------|--------|
| Request/response shape, validation, status codes | Code + Pydantic + path `responses` |
| Grouping, intro text per tag | `openapi_tags` + `tags=` on routes |
| Operational context (CORS, blacklist, time zones) | [endpoints.md](../endpoints.md) or `FastAPI.description` for global pointers |
| Long examples for copy-paste | Pydantic `examples` and/or [endpoints.md](../endpoints.md) |

[← Security and versioning](06-security-and-versioning.md) · [Index](README.md)
