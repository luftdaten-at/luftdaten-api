# Plan: Require `station_ids` on `GET /station/historical`

## 1. Goal

- **`station_ids` must always be provided** and must resolve to **at least one** non-empty device ID after parsing.
- **Remove** the behaviour where an **empty** `station_ids` (missing, `""`, or effectively empty after parsing) returns data for **all** stations.

**Rationale:** Full-table historical queries are expensive, hard to cache, and easy to abuse. Forcing callers to name stations keeps load predictable and aligns with least-surprise for large datasets.

---

## 2. Current behaviour (as implemented)

**File:** `code/routers/station.py` — `get_historical_station_data` (`GET /historical`).

| Input | Effect |
|--------|--------|
| Default / omitted `station_ids` | `devices == []` |
| `station_ids=""` | `devices == []` |
| Query filter | `.filter(or_(not devices, Station.device.in_(devices)))` → if `devices` is empty, **all stations** match |

**OpenAPI / docstring** today explicitly says: *“Empty string returns all stations.”*

### 2.1 Special case: `end=current`

When `end == "current"`, the handler **does not use the main SQLAlchemy query** for the data path; it runs **raw SQL** (approx. lines 803–812) that selects from `stations` / `measurements` / `values` with **no `station_ids` filter**.

So today, **`station_ids` is effectively ignored** for `end=current`. Any change that only tightens the ORM branch would leave **`end=current` still returning all stations** unless that SQL path is updated too.

---

## 3. New API contract

1. **Required query parameter:** `station_ids` (string).
2. **Parsing:** Split on `,`, strip whitespace, **drop empty segments**.
3. **Validation:** After parsing, **`len(devices) >= 1`**. Otherwise respond with **`422 Unprocessable Entity`** (preferred for “invalid input”) or **`400 Bad Request`** with a clear message, e.g.  
   `"station_ids is required and must contain at least one device ID"`.
4. **Rejected inputs (examples):**
   - Parameter omitted (if using `Query(...)` without default, FastAPI returns 422; still document).
   - `station_ids=`
   - `station_ids=,,`
   - Only whitespace / commas.

5. **Blacklist:** Existing rule unchanged: blacklisted IDs are excluded from results (may yield **empty** result set — that is OK; do not treat as “missing station_ids”).

6. **No new “all stations” escape hatch** on this route. Callers that need discovery should use **`GET /station/all`** (or other listing endpoints) first, then call `/historical` with explicit IDs.

---

## 4. Implementation steps

### 4.1 Shared parsing helper (recommended)

Add a small function (e.g. in `station.py` or `utils/`) used only by this endpoint (or reused later):

```text
parse_comma_separated_ids(raw: str) -> list[str]
  - split on ","
  - strip each part
  - omit empty strings
```

### 4.2 `get_historical_station_data`

1. Change **`station_ids`** from `Query("", ...)` to **required**:
   - `station_ids: str = Query(..., description="Comma-separated device IDs; at least one required.")`
2. After parsing, **validate** non-empty list; raise `HTTPException` if not.
3. Replace  
   `.filter(or_(not devices, Station.device.in_(devices)))`  
   with  
   `.filter(Station.device.in_(devices))`  
   (since `devices` is never empty).

### 4.3 Fix `end=current` branch

Extend the raw SQL (and parameters) to restrict to the requested devices, e.g.:

- `AND s.device IN (:d0, :d1, ...)` with bound parameters, **or**
- Prefer refactoring this branch to reuse the same ORM query + filters as the non-`current` path for consistency (larger change; only if you want one code path).

**Must** apply blacklist consistently (already partially handled via `NOT IN` for blacklist).

### 4.4 Documentation

- Update the **endpoint docstring** and **`Query` descriptions** (remove “empty = all”).
- Update **`tests/README.md`** if it describes this endpoint.
- **CHANGELOG / version:** bump API minor version or document breaking change in release notes.

---

## 5. Tests (`code/tests/test_station.py`)

| Change | Action |
|--------|--------|
| `test_get_historical_station_data_current` | Add valid `station_ids` (e.g. `test_station_1` from fixtures); optionally assert response only contains that device. |
| New test | Missing `station_ids` → **422**. |
| New test | `station_ids=` or `station_ids=,,` → **422** or **400** (match implementation). |
| Existing test with explicit `station_ids` | Keep; should still **200**. |

If `end=current` is updated to honour IDs, add a test that **without** filtering would differ from “all stations” (e.g. two stations in DB, request one ID, assert only that device appears).

---

## 6. Related endpoints (out of scope unless you decide otherwise)

| Endpoint | Note |
|----------|------|
| **`GET /station/history`** (deprecated) | Still allows “all stations” when `station_ids` omitted. Optionally align in a follow-up for consistency. |
| **`GET /station/current`** | Different product semantics (“all active”); not part of this plan. |

---

## 7. Consumer migration

1. Search clients for `/station/historical` without `station_ids` or with empty value.
2. Replace with explicit IDs from **`/station/all`**, **`/station/current`**, or user selection.
3. For **`end=current`**, clients must pass **`station_ids`** even though some stacks previously ignored it.

---

## 8. Checklist

- [x] Implement parsing + validation on `GET /historical`
- [x] Replace `or_(not devices, …)` with `Station.device.in_(devices)`
- [x] Apply `station_ids` filter to **`end=current`** SQL (or unify with ORM)
- [x] Update OpenAPI descriptions / docstrings
- [x] Fix and extend tests
- [ ] Document breaking change for API consumers (release notes / changelog when you ship)

---

## 9. Summary

| Topic | Decision |
|-------|----------|
| **Empty / missing `station_ids`** | **Not allowed** — error response |
| **ORM historical query** | Always `Station.device.in_(devices)` |
| **`end=current`** | Must filter by the same `devices` list (currently missing) |
| **Discovery of IDs** | Use other endpoints; `/historical` is not a bulk-export shortcut |
