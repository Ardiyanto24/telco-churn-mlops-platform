# Implementation Plan: M18 Internal Metrics Store and Dashboard

## Overview

Build a privacy-minimised internal source of truth for the aggregate outputs of
M12, M14, M16, and M17, plus a read-only technical dashboard. The first
implementation uses the standard-library SQLite adapter for deterministic local
verification and exposes a PostgreSQL deployment contract through migrations
and documented configuration. It does not process raw customer payloads or
alter the Prediction API request path.

## Architecture decisions

- Apply ADR-0014: immutable aggregate records, explicit lineage/origin, and
  idempotent ingestion are the core store contract.
- Keep database access behind a small `MetricsStore` interface; the test adapter
  is SQLite and migration SQL stays deliberately portable where possible.
- Mount the dashboard in a separate internal app factory, protected by an
  explicit server-side token and disabled unless a store and token are supplied.
- Dashboard queries are read-only and return safe aggregate fields only.

## Task list

### Phase 1: Store foundation

- [x] Task 1: Add versioned migration runner and SQLite metrics schema.
- [x] Task 2: Add typed, idempotent ingestion for models, deployments, and
  aggregate monitoring results.

### Checkpoint: Store foundation

- [x] Empty database upgrades successfully; duplicate ingestion reuses a row.
- [x] No raw identifier/payload field is accepted by the store contract.

### Phase 2: Queries and internal dashboard

- [x] Task 3: Add read-only dashboard queries that preserve evidence states,
  freshness, lineage, and distribution summaries.
- [x] Task 4: Add an authenticated internal FastAPI dashboard with accessible,
  responsive HTML views and no write routes.

### Checkpoint: Dashboard

- [x] Missing evidence renders as not available, never stable.
- [x] An unauthorised request cannot obtain internal metrics.
- [x] Dashboard/database errors do not change prediction-serving behaviour.

### Phase 3: Operational tooling and handoff

- [x] Task 5: Add ingestion/retention scripts and a candidate configuration.
- [x] Task 6: Run focused tests, review the diff, record the engineering log,
  and create the milestone completion report.

### Checkpoint: Complete

- [x] M18 success tests and relevant existing API/model suites pass.
- [x] Migration, retention, dashboard, and ingestion evidence is reproducible.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| PostgreSQL service is not available locally | Medium | Exercise the same store contract against SQLite and retain portable migration SQL; document PostgreSQL provisioning separately. |
| Candidate/replayed evidence is mistaken for production | High | Require `data_origin` and evidence state in each stored and rendered result. |
| Dashboard expands privacy boundary | High | Allowlist aggregate fields; reject identifiers/payloads; use server-side authentication and read-only queries. |
| Metrics failure affects predictions | High | Keep all store/dashboard work outside the existing Prediction API factory and request path. |

## Open questions

- Production PostgreSQL endpoint, credentials, and internal identity provider are intentionally deferred; no secret or account configuration is committed in M18.
