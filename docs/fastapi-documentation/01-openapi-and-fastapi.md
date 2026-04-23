# OpenAPI and FastAPI

## What is OpenAPI?

**OpenAPI** (formerly Swagger) is a machine-readable description of an HTTP API: paths, methods, parameters, request bodies, responses, security schemes, and metadata (title, version). Version 3.x is the common baseline; FastAPI can emit **OpenAPI 3.0** or **3.1** depending on configuration and FastAPI/Starlette versions.

Consumers use this schema to:

- Render **Swagger UI** and **ReDoc** “try it out” experiences
- Generate **client SDKs** and **mock servers**
- Validate that implementations match a published contract

## What FastAPI generates automatically

For each path operation, FastAPI typically infers:

- **HTTP method and path** from the decorator (`@app.get`, `@router.post`, …)
- **Query parameters, headers, and path parameters** from function arguments and their types
- **Request body** from Pydantic models or `Body()` annotations
- **Response** from return type annotations, `response_model`, and `response_class`
- **Validation errors** (e.g. 422) for invalid input, documented in the schema

Anything you do not declare explicitly (extra error shapes, custom media types) may be missing or generic in the generated document.

## Default URLs in a FastAPI app

| URL | Role |
|-----|------|
| `/openapi.json` | Raw OpenAPI schema (JSON) |
| `/docs` | **Swagger UI** (interactive) |
| `/redoc` | **ReDoc** (read-oriented layout) |

These paths can be changed or disabled via `openapi_url`, `docs_url`, and `redoc_url` on the `FastAPI()` constructor (see [02-app-metadata-and-servers.md](02-app-metadata-and-servers.md)).

## Single source of truth

Treat the **code + models** that produce the OpenAPI document as the **contract** for request/response shapes. Human markdown ([endpoints.md](../endpoints.md) in this repo) adds narrative that the schema does not carry well (deployment notes, time zone rules, blacklist behavior). When the two conflict, **fix the code/schema first**, then align prose.

[← Back to index](README.md) · [Next: App metadata →](02-app-metadata-and-servers.md)
