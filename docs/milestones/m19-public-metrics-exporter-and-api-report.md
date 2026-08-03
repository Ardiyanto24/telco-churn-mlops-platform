# M19 Public Metrics Exporter and API Report

## Status

Completed in local/candidate mode on 2026-08-03.

## Deliverables

- `telco_churn.public_metrics`: explicit field allowlist, minimum group-size
  suppression, provenance/evidence rendering, immutable snapshot generation,
  and stale-last-known-good fallback.
- `telco_churn.public_api`: bounded GET-only `/public/v1` API with ETags,
  cache controls, restricted CORS, safe errors, and rate limiting.
- M18 migration `0002` for immutable public snapshot documents/publication
  state, plus local export/serve commands and M19 candidate configuration.
- JSON Schema and example contract in `contracts/public_metrics/v1/`.
- A separate static public consumer in `../public-dashboard`.

## Verification evidence

| Command | Result |
| --- | --- |
| Locked container `python -m unittest tests.test_public_metrics tests.test_public_metrics_script tests.test_metrics_store -v` | 11 passed |
| Locked container `python scripts/run_tests.py api` | 27 passed |
| Locked container `python scripts/run_tests.py model` | 64 passed |
| `node --check ../public-dashboard/app.js` | Passed |

The tests prove allowlist/negative-field handling, origin labels, suppression,
last-known-good stale fallback, GET-only API, CORS denial by omission, rate
limit, cache/ETag headers, and export CLI operation.

## Exit criteria

| Criterion | Evidence | Status |
| --- | --- | --- |
| Public web has no internal database/tool access | Snapshot-only API and separate static consumer | Met |
| Browser has no secret | Anonymous GET-only API; server-side store access only | Met |
| Versioned and compatible contract | `public_metrics/v1` JSON Schema; additive-v1 ADR policy | Met |
| Public failure does not affect Prediction API | Separate FastAPI factory/no serving dependency; M18 availability isolation test remains green | Met |

## Limitations and handoff

- Candidate/replayed/synthetic evidence must not be presented as live
  production health; public origin, candidate mode, and freshness make this
  explicit.
- No hosted PostgreSQL, public API host, static-web host, reverse-proxy rate
  limiter, or public-dashboard Git remote is configured in this milestone.
- A human browser visual/accessibility check remains advisable before a public
  launch because Chrome DevTools MCP is unavailable in this workspace.

## Trace references

- ADR-0015: `docs/decisions/0015-m19-public-metrics-exporter-and-api-policy.md`
- Operation guide: `docs/m19-public-metrics-api.md`
- Engineering log: `docs/logs/m19-public-metrics-exporter-and-api.md`
