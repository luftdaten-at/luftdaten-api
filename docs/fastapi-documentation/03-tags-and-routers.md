# Tags and routers

## Why tags

**Tags** group path operations in Swagger UI and ReDoc. They are the main navigation tool for large APIs.

## `openapi_tags` on `FastAPI()`

Pass a list of dicts, each with at least `name` and usually `description` (Markdown allowed):

- **Order matters:** the order of entries in the list is the order of tag sections in the UIs.
- Optional **`externalDocs`**: `description` + `url` to link out (e.g. product wiki).

You do not need an entry for every tag string you use, but if you skip one, that tag appears without a group description in some UIs.

## Route-level `tags`

Set `tags=[...]` on each `@router.get` / `@app.post` / … (or on `APIRouter` defaults). A route can have **multiple** tags (e.g. `station` and `current`); it will appear under each group.

## Avoiding typos at scale

For many routes, use a small **`Enum`** of tag values and pass `tags=[TagEnum.station]` so misspellings fail at import time. FastAPI accepts Enums in place of string tags.

## Consistency in luftdaten-api

- Central definitions live in `openapi_tags` in `code/main.py`.
- Every **distinct** tag used on path operations should either appear in `openapi_tags` with a short description, or you accept default empty metadata for that tag.
- If you add a new tag in routers (e.g. `calibration`), add a matching `openapi_tags` entry when you want it documented consistently.

[← App metadata](02-app-metadata-and-servers.md) · [Index](README.md) · [Next: Path operations →](04-path-operations.md)
