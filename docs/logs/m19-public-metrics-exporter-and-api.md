# M19 Public Metrics Exporter and API Engineering Log

## Context and assumptions

M19 implements the public boundary after M18. The internal store remains
private; the browser consumes only M19 snapshots. The separate
`../public-dashboard` repository was empty (no commits or remote) at the start
of this work, so a dependency-free static consumer was added there without
assuming a React/Next hosting decision. M15 remains candidate and M16 has no
production delayed-label package; public origin and candidate state remain
visible.

## Plan and actions

1. Added a test-first public exporter/API contract, including sanitisation,
   suppression, stale fallback, CORS, cache, and rate-limit cases.
2. Added M18 migration `0002` for immutable public snapshot documents and a
   small current-publication state record; no internal table is exposed.
3. Implemented `telco_churn.public_metrics`, `telco_churn.public_api`, export
   and serve commands, candidate configuration, JSON contract, and fixture.
4. Added the static `../public-dashboard` consumer that calls only
   `/public/v1`, with loading, error, empty, stale, and candidate disclosures.

## Evidence and findings

- The first test run failed as intended because the pre-existing
  `telco_churn.public_metrics` package had no M19 contract.
- Focused locked-container verification passed 11 tests for exporter, API,
  export CLI, and M18-store regression.
- Locked-container API category passed 27 tests after the review fixes.
- Locked-container model category passed 64 tests.
- `node --check ../public-dashboard/app.js` passed.

## Errors and handling

- The M18 migration test initially expected only `0001`. M19's snapshot tables
  require `0002`, so the test was updated to assert both versioned migrations
  and tables. The subsequent regression suite passed.
- No browser DevTools MCP server is configured. JavaScript syntax and API
  contracts were verified, but an interactive browser visual QA remains a
  handoff item before hosted release.

## Decisions and deviations

- ADR-0015 governs public allowlisting, group suppression, provenance,
  snapshot atomicity, stale fallback, API versioning, CORS, caching, and
  rate limiting.
- The empty public-dashboard repository receives static HTML/CSS/JavaScript
  rather than a new frontend framework. This avoids an unapproved dependency
  and hosting choice while providing a contract consumer.

## Risks, limitations, and follow-up

- SQLite is a local/test adapter only; M19 does not provision PostgreSQL or a
  hosted persistent snapshot store.
- The in-process limiter is suitable for local/demo use; a hosted deployment
  needs a reverse-proxy or shared-store limiter.
- The public-dashboard repository has no remote yet, so its initial commit
  cannot be pushed until a repository/remote is explicitly created.
- M20 should harden deployed secret, deployment, privacy, and abuse controls.

## Trace references

- ADR-0015 and `configs/monitoring/m19-candidate-v1.json`.
- JSON contract: `contracts/public_metrics/v1/`.
- Backend feature commit: `79bb08f`.
- Verification commands: `python -m unittest tests.test_public_metrics
  tests.test_public_metrics_script tests.test_metrics_store -v`,
  `python scripts/run_tests.py api`, and `python scripts/run_tests.py model`
  in `telco-churn-m8-runtime:local`.
