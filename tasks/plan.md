# Implementation Plan: M19 Public Metrics Exporter and API

## Overview

Build a versioned, read-only public snapshot and API from the private M18
aggregate store, plus a separate static public-dashboard consumer. It exposes
only sanitised aggregate evidence and does not alter the Prediction API request
path or grant browser access to internal credentials/databases.

## Architecture decisions

- Apply ADR-0015: allowlist-only export, origin/suppression states, immutable
  snapshots, and versioned `/public/v1` endpoints.
- Keep M18 internal tables private; only a public snapshot document crosses
  the boundary.
- Keep browser access anonymous and read-only; use explicit CORS origins,
  caching, ETag, and local/demo rate limiting.

## Task list

### Phase 1: Public snapshot foundation

- [x] Task 1: Add a versioned immutable public snapshot migration and exporter.
- [x] Task 2: Add allowlist, origin, suppression, stale-fallback, and schema contracts.

### Checkpoint: Snapshot foundation

- [x] Empty database migrates through M19 and export retries reuse immutable content.
- [x] Internal fields, distributions, and low-count metrics do not enter a snapshot.

### Phase 2: API and public consumer

- [x] Task 3: Add GET-only Public Metrics API with cache, CORS, and rate limit.
- [x] Task 4: Add a static public-dashboard consumer with explicit evidence and error states.

### Checkpoint: Public boundary

- [x] Failed/empty source is never rendered as stable.
- [x] Browser receives no secret or internal source payload.
- [x] Public API/exporter failure remains isolated from prediction serving.

### Phase 3: Operational tooling and handoff

- [x] Task 5: Add local export/serve commands, candidate config, and JSON contract fixture.
- [x] Task 6: Run focused tests, regression suites, review, log, and completion report.

### Checkpoint: Complete

- [x] M19 contract tests and relevant API/model suites pass.
- [x] Snapshot, API, and consumer integration are reproducible locally.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Internal fields leak into public output | High | Allowlist exporter, negative-field tests, immutable snapshot contract, and no direct M18 queries. |
| Candidate/replayed evidence is mistaken for production | High | Require origin, candidate mode, freshness, and non-stable evidence state in API and UI. |
| Public endpoint is abused | Medium | Explicit CORS, GET-only routes, ETag/cache, and a conservative rate limiter. |
| Export/API failure affects predictions | High | Separate app factory and no dependency from prediction request path. |

## Open questions

- Hosted PostgreSQL/public API/static-web provider and shared production rate limiter remain deployment decisions; no secret or account configuration is committed in M19.
