# M18 Internal Metrics Store and Dashboard Report

## Status

Completed in candidate/internal mode on 2026-08-03.

## Deliverables

- `telco_churn.metrics_store`: versioned M18 schema, clean migration,
  test-only rollback, immutable aggregate records, database idempotency,
  model/deployment lineage, safe dashboard query, and retention.
- `telco_churn.internal_dashboard`: separate read-only FastAPI dashboard with
  token authentication and security headers.
- `scripts/manage_metrics_store.py`: migrate, safe aggregate ingest, and
  retention commands for the local adapter.
- `scripts/serve_internal_dashboard.py`: separately runs the dashboard using a
  token supplied only through `TELCO_CHURN_INTERNAL_DASHBOARD_TOKEN`.
- `configs/monitoring/m18-candidate-v1.json` and
  `docs/m18-internal-dashboard.md`.

## Verification evidence

| Command | Result |
| --- | --- |
| Locked container `python -m unittest tests.test_metrics_store tests.test_metrics_store_script tests.test_internal_dashboard -v` | 11 passed |
| Locked container `python scripts/run_tests.py api` | 20 passed |
| Locked container `python scripts/run_tests.py model` | 63 passed |

The tests prove clean migration/rollback, retry idempotency, rejection of raw
identifier/payload fields, `not_available` rendering, baseline/current
distribution context, dashboard token protection, retention preservation of
model/deployment lineage, and Prediction API liveness during dashboard failure.

## Exit criteria

| Criterion | Evidence | Status |
| --- | --- | --- |
| Internal metrics store is the monitoring source of truth | Immutable aggregate M18 schema and idempotent ingestion | Met for local/candidate adapter |
| Dashboard is not required for monitoring jobs | Ingestion CLI/store do not import dashboard; dashboard is separate app | Met |
| Dashboard failure does not affect Prediction API | Explicit container test; `/health/live` remains 200 when dashboard store is unavailable | Met |
| Schema is ready for public exporter | Explicit `public_snapshots` boundary; M19 remains the only exporter owner | Met as private schema contract |

## ADR and configuration

- ADR-0014: `docs/decisions/0014-m18-internal-metrics-store-and-dashboard-policy.md`
- Candidate config: `configs/monitoring/m18-candidate-v1.json`
- Aggregate retention: 395 days; M16 row-level join linkage remains 30 days.

## Limitations and handoff

- PostgreSQL is the approved deployment target but was not provisioned here:
  the locked runtime has no pinned PostgreSQL driver, DSN, credentials, or
  managed service. The SQLite adapter is explicitly local/test only.
- The server-side token is a local/internal boundary, not a replacement for a
  future corporate identity provider and role mapping.
- M15 baseline remains candidate and M16 lacks supplied production delayed
  labels. Dashboard origin and evidence state make these limits visible.
- M19 should implement the explicit sanitised snapshot exporter/public API;
  public clients must never query M18 tables.

## Trace references

- Engineering log:
  `docs/logs/m18-internal-metrics-store-and-dashboard.md`
- Local operation guide: `docs/m18-internal-dashboard.md`
