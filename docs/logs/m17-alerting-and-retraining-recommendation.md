# M17 Engineering Log — Alerting and retraining recommendation

## Context and assumptions

- M17 translates qualified monitoring evidence into operator actions without
  granting an automatic model-change path.
- M15's baseline/configuration remains candidate and M16 has no validated
  production delayed-label source; M17 therefore starts in candidate mode.

## Plan and actions

- Read M17 scope, upstream M15/M16 logs, and decisions.
- Record the twenty durable alerting/retraining choices in ADR-0013 before
  implementation.
- Implement the candidate alert engine, immutable output/reuse, lifecycle
  transitions, recommendation records, JSONL runner, and policy config.
- Add synthetic/replay contracts and an operator investigation checklist.

## Evidence and findings

- The plan requires persistence/debounce/deduplication, separate operational
  alerts, traceable acknowledgement/resolution, and a retraining
  recommendation that is not promotion approval.
- M15 already supplies the candidate two-consecutive-window persistence rule;
  M16 provides data-origin, coverage, and lineage constraints for performance
  evidence.
- Focused M17 verification passed: 5 tests cover warning persistence,
  operational failure classification, candidate performance recommendation,
  append-only acknowledgement/resolution, and idempotent output reuse.
- `run_alerting.py --help` and the complete model test category passed in
  `telco-churn-m8-runtime:local` after the M17 changes.

## Errors and handling

- No implementation error occurred during this milestone. External delivery
  remains intentionally unimplemented because no durable recipient/auth/secret
  boundary has been approved.

## Decisions and deviations

- ADR-0013 adopts a candidate, fail-closed M17 policy. It blocks external
  production delivery and all automatic model-changing actions.
- The implementation writes only aggregate JSON/Markdown records. It does not
  accept raw customer data, invoke training, change a threshold, or promote a
  model.

## Risks, limitations, and follow-up

- Validate/supersede the candidate policy when M15 has an approved baseline
  and M16 delayed-label source mapping is available.
- Implement alert state, idempotency, replay tests, recommendation records,
- Connect a durable internal store, authenticated recipient/delivery policy,
  and approved M15/M16 production evidence before enabling production mode.

## Trace references

- ADR: `docs/decisions/0013-m17-alerting-and-retraining-recommendation-policy.md`
- Upstream: ADR-0011 and ADR-0012.
- Config: `configs/monitoring/m17-candidate-v1.json`.
- Commands: `python -m unittest tests.test_alerting -v` and `python
  scripts/run_tests.py model` in `telco-churn-m8-runtime:local`.
