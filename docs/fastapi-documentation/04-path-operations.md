# Path operations

Path operation configuration is set on the **route decorator** (`@router.get`, etc.), not only on the function. See the official [Path Operation Configuration](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/) tutorial.

## Summaries and descriptions

| Mechanism | Role |
|-----------|------|
| `summary="…"` | Short title in the operation list |
| `description="…"` | Longer text on the operation detail |
| **Function docstring** | If you omit `description`, FastAPI can use the docstring; **Markdown** in docstrings is rendered in the UIs. |

Prefer **one** of: long `description=` parameter, or a structured docstring—avoid duplicating the same text twice.

## Response wording

- **`response_description`**: specifically describes the **default success** response (OpenAPI requires a response description; if omitted, FastAPI supplies a generic phrase).
- Distinguish from **`description`**, which describes the operation as a whole.

## Status codes

Set **`status_code=…`** (e.g. `201`, `204`, or `fastapi.status.HTTP_201_CREATED`) so the OpenAPI spec matches real responses. Mismatches confuse clients and generated SDKs.

## Deprecation

**`deprecated=True`** marks a route in OpenAPI; UIs show a warning. Use when phasing out paths but keeping them available—**luftdaten-api** uses this for legacy station routes.

## Schema visibility

**`include_in_schema=False`**: hide a path from OpenAPI (e.g. duplicate route with/without trailing slash, internal-only callback). Hiding a route does not remove the URL at runtime; it only affects documentation.

[← Tags and routers](03-tags-and-routers.md) · [Index](README.md) · [Next: Models and responses →](05-models-parameters-responses.md)
