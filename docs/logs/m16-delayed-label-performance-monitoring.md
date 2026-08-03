# M16 Engineering Log — Delayed-label performance monitoring

## Context and assumptions

- M16 will establish the delayed-label monitoring framework before the user
  supplies the external delayed-label data package.
- No available artifact proves the pending source's churn definition, join
  identifier, arrival pattern, or label-maturity interval.
- Synthetic or replayed evidence must never be represented as production
  performance.

## Plan and actions

- Read the M16 plan and target architecture sections.
- Record the durable M16 policy and its rejected alternatives in ADR-0012.
- Implement a small, validated M16 contract for prediction events, delayed
  labels, immutable evaluation results, and aggregate Markdown reports.
- Add the protected JSON Lines entry point and candidate configuration. The
  origin gate rejects `production` by default.

## Evidence and findings

- The M16 plan requires matured labels, idempotent prediction-label joins,
  coverage reporting, rolling evaluation, data-origin labels, and explicit
  `not_available`/`insufficient_data` behavior.
- M12 already defines pseudonymous `entity_key` and immutable release lineage,
  which are the approved starting point for the protected join contract.
- Focused M16 test suite passed: 7 tests covering known synthetic metrics,
  maturity, exact retry deduplication, conflict quarantine, low/no label
  states, idempotency, source-origin guard, aggregate report minimisation,
  rolling cohorts, and label-definition consistency.
- Model category verification passed: 49 tests in 33.684 seconds. The
  `run_performance_monitoring.py --help` CLI check also passed in the locked
  runtime image.
- After the final rolling-cohort and source-origin guards, the model category
  and combined M12--M16 contract suites passed again in the locked runtime.

## Errors and handling

- No delayed-label data is available yet, so real join compatibility,
  production coverage, and maturity horizon cannot be verified. This is
  recorded as a scope constraint rather than inferred from existing datasets.
- `scripts/run_tests.py all` was intentionally attempted in the locked runtime
  but failed only at M0's `test_baseline_runner`: that integration test invokes
  Docker from inside the test container, where the Docker executable is not
  present. M16's own tests passed in the same run. The relevant model and
  M12--M16 suites were then run successfully; no M16 code change was made for
  this pre-existing verification-environment constraint.

## Decisions and deviations

- ADR-0012 adopts twenty production-candidate decisions. Its 90-day maturity
  horizon and 80% coverage threshold are explicitly candidate configuration,
  pending validation against the incoming data package.
- M16 accepts at most three contiguous monthly cohorts per immutable rolling
  result. It does not silently mix model, threshold, risk-policy, or label
  definition versions.

## Risks, limitations, and follow-up

- Do not label any M16 result `production` until the authoritative source,
  identifier mapping, and churn definition have been reviewed.
- When the package arrives, inspect its schema and update/supersede the ADR if
  the source requires different join or maturity semantics.
- The current M12 request-level aggregate telemetry is not itself sufficient
  for the per-prediction protected join export. Connecting its durable source
  is a required integration step when delayed-label data is available.

## Trace references

- ADR: `docs/decisions/0012-m16-delayed-label-performance-monitoring-policy.md`
- Upstream contracts: ADR-0008 and ADR-0011.
- Plan: `MLOPS_IMPLEMENTATION_PLAN.md`, M16.
- Candidate config: `configs/monitoring/m16-candidate-v1.json`.
- Commands: `python -m unittest tests.test_performance_monitoring -v` and
  `python scripts/run_tests.py model` in `telco-churn-m8-runtime:local`.
