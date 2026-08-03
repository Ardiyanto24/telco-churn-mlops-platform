# M19 Public Metrics API

M19 is the only browser-facing boundary for public model evidence. It reads an
immutable, sanitised snapshot; it never reads M18 tables directly and requires
no browser secret.

## Local candidate demonstration

Create/migrate an M18 local database, ingest only safe aggregate records, then
publish a snapshot:

```powershell
python scripts/manage_metrics_store.py --database artifacts/m19-metrics.db migrate
python scripts/export_public_metrics.py --database artifacts/m19-metrics.db --now 2026-08-03T12:00:00Z
python scripts/serve_public_metrics_api.py --database artifacts/m19-metrics.db
```

The public API listens on `http://127.0.0.1:8019` by default. It exposes only:

- `GET /public/v1/overview`
- `GET /public/v1/models/current`
- `GET /public/v1/models/history`
- `GET /public/v1/monitoring/history`
- `GET /public/v1/service/history`
- `GET /public/v1/methodology`

The static consumer is in `../public-dashboard`. Serve it from localhost port
5500 (or 4173), both of which are explicitly allowed by the candidate config.

## Contract and safety

- JSON schema: `contracts/public_metrics/v1/public-metrics.schema.json`.
- Example endpoint response: `contracts/public_metrics/v1/example-overview.json`.
- Snapshot schema version: `public_metrics/v1`; v1 changes are additive only.
- Groups below 100 observations are `suppressed` and expose no count or metric
  value.
- `production`, `replayed`, `synthetic`, and `offline_test` origins are always
  visible. Candidate/replayed data is not production-health evidence.
- A failed exporter retains the last valid snapshot but marks it `stale`.
- API responses have ETags, five-minute public caching, explicit CORS origins,
  and a local/demo 60 requests/minute/IP limiter.

The local SQLite adapter is for deterministic development/testing. A deployed
service must use the M18 PostgreSQL target and external persistent storage.
