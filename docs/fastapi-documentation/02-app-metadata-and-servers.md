# App metadata and servers

## `FastAPI()` constructor

Set API-wide fields used in OpenAPI and on the doc UIs:

| Parameter | Purpose |
|-----------|---------|
| `title` | API name (shown in Swagger/ReDoc) |
| `version` | Your **application** version (not the OpenAPI spec version) |
| `description` | Long text; **Markdown** is supported |
| `summary` | Short blurb (OpenAPI 3.1 + recent FastAPI) |
| `terms_of_service` | URL to terms |
| `contact` | `name`, `url`, `email` |
| `license_info` | `name` plus `url` **or** SPDX `identifier` (3.1) |
| `servers` | Base URLs and labels (e.g. `/v1`, staging vs production) |

**Tip:** The `description` string is a good place for links to your human docs repository path or public site, without duplicating every endpoint.

## Example pattern

```python
app = FastAPI(
    title="Example API",
    description="## Overview\n\nFull docs: [endpoints](...).",
    version="1.0.0",
    servers=[
        {"url": "/v1", "description": "Versioned API"},
    ],
)
```

In **luftdaten-api**, `servers` includes `{"url": "/v1", ...}` in `code/main.py` so relative paths in UIs line up with the public prefix (see [06-security-and-versioning.md](06-security-and-versioning.md) for how `/v1` is applied).

## Controlling schema and UI exposure

| Parameter | Default | Typical use |
|-----------|---------|-------------|
| `openapi_url` | `"/openapi.json"` | Set a custom path or `None` to **disable** OpenAPI and both UIs |
| `docs_url` | `"/docs"` | Custom path or `None` to hide Swagger UI |
| `redoc_url` | `"/redoc"` | Custom path or `None` to hide ReDoc |

Disabling `openapi_url` removes the JSON schema and the documentation interfaces that depend on it—use when production policy requires no public spec.

[← OpenAPI and FastAPI](01-openapi-and-fastapi.md) · [Index](README.md) · [Next: Tags and routers →](03-tags-and-routers.md)
