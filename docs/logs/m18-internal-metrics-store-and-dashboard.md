# M18 Internal Metrics Store and Dashboard Engineering Log

## Context and assumptions

- Scope follows `MLOPS_IMPLEMENTATION_PLAN.md` M18 and ADR-0014.
- The initial implementation is candidate/internal only. M15 remains
  unapproved and production delayed-label data has not been supplied.
- PostgreSQL is the deployment target, but the locked runtime has no PostgreSQL
  driver and no configured service. SQLite is used only as a deterministic
  local/test adapter; no production database claim is made.
- Raw customer identifiers, payloads, predictions, labels, and secrets are out
  of scope for the metrics-store and dashboard contracts.

## Plan and actions

1. Create a migration-backed aggregate metrics store with database-enforced
   idempotency and lineage/origin fields.
2. Add safe read-only queries and a separately constructed internal dashboard.
3. Add ingestion and retention tooling, then verify M18 and relevant regressions.

## Evidence and findings

- Pre-implementation inspection confirmed that M12, M14, M16, and M17 already
  emit aggregate, lineage-bearing candidate outputs suitable for M18 ingestion.
- `requirements/runtime.lock` contains no PostgreSQL driver; therefore runtime
  installation is not changed before a pinned driver/provisioning decision.
- `python -m unittest tests.test_metrics_store tests.test_metrics_store_script
  tests.test_internal_dashboard -v` in `telco-churn-m8-runtime:local` passed
  11 tests.
- `scripts/run_tests.py api` in the locked runtime passed 20 tests.
- `scripts/run_tests.py model` in the locked runtime passed 63 tests.

## Errors and handling

- A broad recursive file inspection entered `.dvc-tools` and encountered access
  denials. It did not modify files; subsequent inspection is restricted to
  repository source/config paths.
- The first dashboard container test raised SQLite's cross-thread connection
  error because FastAPI executes synchronous handlers in worker threads. The
  local adapter now uses `check_same_thread=False` only when explicitly opened
  through `MetricsStore.open_sqlite`, and serialises access with `RLock`.
  The regression tests passed after this change. PostgreSQL remains the
  production target and is not represented as this SQLite adapter.

## Decisions and deviations

- The implementation plan records a SQLite adapter for tests/local use rather
  than silently treating it as the PostgreSQL production store. This follows
  ADR-0014 decision 1.
- The dashboard is a separate application factory with server-side token
  comparison, read-only routes, no API schema/docs endpoint, `no-store`, CSP,
  frame-denial, and content-type headers. It has no dependency on the
  Prediction API app factory.

## Risks, limitations, and follow-up

- Internal token/identity provisioning and PostgreSQL credentials are deployment
  concerns and remain unconfigured. The dashboard will fail closed unless its
  server-side access token is supplied.
- M19 remains responsible for any public metrics export.
- Browser-level visual QA was not run because no Chrome DevTools MCP server is
  configured in this workspace. The FastAPI container contracts verify rendered
  content, authentication, evidence states, and availability isolation; a
  human/browser QA pass remains advisable before a production UI launch.

## Trace references

- ADR-0014: M18 internal metrics store and dashboard policy.
- `tasks/plan.md` and `tasks/todo.md`.
- M18 config: `configs/monitoring/m18-candidate-v1.json`.
- M18 commands: `scripts/manage_metrics_store.py` and
  `scripts/serve_internal_dashboard.py`.
