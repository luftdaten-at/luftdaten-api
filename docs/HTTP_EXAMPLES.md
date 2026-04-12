# HTTP API examples (`curl`)

Copy-paste examples for manual checks. Replace hosts, query parameters, and bodies (especially `device`, `time`, and `apikey`) with values that match your environment.

All paths use the **`/v1`** prefix (see [`code/main.py`](../code/main.py) version middleware).

---

## Development (`localhost`)

Base URL: `http://localhost` (or `http://127.0.0.1` if your stack listens there).

### POST `/v1/station/data` — ingest measurements

```bash
curl -sS -X POST 'http://localhost/v1/station/data' \
  -H 'Content-Type: application/json' \
  -d @- <<'EOF'
{
  "station": {
    "time": "2024-09-30T23:04:20.766Z",
    "device": "00112233AABDE",
    "firmware": "1.2",
    "apikey": "aaaaaaaaaaaaaaaaaaaa",
    "location": {
      "lat": 48.20194899118807,
      "lon": 16.337324948208199,
      "height": 5.3
    }
  },
  "sensors": {
    "1": { "type": 1, "data": { "2": 9.0, "3": 10.0, "5": 13.0, "6": 0.45, "7": 22.0, "8": 200 } },
    "2": { "type": 6, "data": { "6": 0.4, "7": 22.1 } }
  }
}
EOF
```

`/v1/station/data/` (trailing slash) is also accepted.

### GET `/v1/station/current` — current measurements (filtered)

```bash
curl -sS 'http://localhost/v1/station/current?last_active=3600'
```

### GET `/v1/station/current/all` — all stations current snapshot

```bash
curl -sS 'http://localhost/v1/station/current/all'
```

### GET `/v1/station/historical` — historical series (CSV example)

`station_ids` is required (comma-separated device IDs).

```bash
curl -sS 'http://localhost/v1/station/historical?station_ids=1,2,3&start=2024-10-01T08:00&end=2024-10-05T18:00&output_format=csv'
```

### GET `/v1/station/history` — legacy history endpoint

```bash
curl -sS 'http://localhost/v1/station/history?station_ids=85619&start=2024-03-12T13:23:07.015Z'
```

### GET `/v1/city/all`

```bash
curl -sS 'http://localhost/v1/city/all'
```

### GET `/v1/city/current`

```bash
curl -sS 'http://localhost/v1/city/current?city_slug=wien'
```

---

## Staging

### POST `/v1/station/data` — `staging.api.luftdaten.at`

The original staging sample omitted `apikey`; the API requires it for this route. Example with `apikey` added:

```bash
curl -sS -X POST 'https://staging.api.luftdaten.at/v1/station/data' \
  -H 'Content-Type: application/json' \
  -d @- <<'EOF'
{
  "station": {
    "time": "2024-04-29T08:25:20.766Z",
    "device": "00112233AABB",
    "firmware": "1.2",
    "apikey": "YOUR_API_KEY",
    "location": {
      "lat": 48.20194899118805,
      "lon": 16.337324948208195,
      "height": 5.3
    }
  },
  "sensors": {
    "1": { "type": 1, "data": { "2": 5.0, "3": 6.0, "5": 7.0, "6": 0.67, "7": 20.0, "8": 100 } },
    "2": { "type": 6, "data": { "6": 0.72, "7": 20.1 } }
  }
}
EOF
```

---

## Production

### POST `/v1/station/data` — `api.luftdaten.at`

```bash
curl -sS -X POST 'https://api.luftdaten.at/v1/station/data' \
  -H 'Content-Type: application/json' \
  -d @- <<'EOF'
{
  "station": {
    "time": "2024-09-30T23:04:20.766Z",
    "device": "00112233AABDE",
    "firmware": "1.2",
    "apikey": "aaaaaaaaaaaaaaaaaaaa",
    "location": {
      "lat": 48.20194899118807,
      "lon": 16.337324948208199,
      "height": 5.3
    }
  },
  "sensors": {
    "1": { "type": 1, "data": { "2": 9.0, "3": 10.0, "5": 13.0, "6": 0.45, "7": 22.0, "8": 200 } },
    "2": { "type": 6, "data": { "6": 0.4, "7": 22.1 } }
  }
}
EOF
```

Use a real `apikey` and avoid reusing the same `device` + `time_measured` + sensor combination (duplicate insert returns **422**).

---

## Optional flags

| Flag | Use |
|------|-----|
| `-i` | Print response status and headers |
| `-v` | Verbose (TLS, redirects, connection) |
| `-k` | Allow insecure TLS (local dev only) |

For ingest debugging on the server, set **`LOG_STATION_INGEST=true`** in the app environment (see [`.env.example`](../.env.example)).
