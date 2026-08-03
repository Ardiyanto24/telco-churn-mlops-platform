# Milestone M17 Completion Report

Status: done (candidate workflow; production delivery pending)

Tanggal: 2026-08-03

Commit/PR: pending

## Deliverable

- Candidate alert engine with separate operational, data-quality, drift, and
  performance domains.
- Two-window persistence, one-alert-per-family deduplication, idempotent
  aggregate output, and append-only acknowledgement/resolution/suppression
  state transitions.
- Candidate retraining recommendation record that explicitly requires M5--M8
  and M11; it cannot retrain, promote, roll back, or alter thresholds.
- Versioned policy/JSONL runner and [investigation checklist](../m17-alert-investigation-checklist.md).

## Test evidence

- Command: `python -m unittest tests.test_alerting -v` in
  `telco-churn-m8-runtime:local`.
- Result: 5 tests passed.
- Command: `python scripts/run_tests.py model` in the same locked runtime.
- Result: passed after M17 changes.
- Entry point: `python scripts/run_alerting.py --help` passed.

## Exit criteria

- [x] Alert carries reason, window, sample, model, baseline, config, and
  source-origin lineage without raw customer data.
- [x] Retraining recommendation is structurally distinct from promotion
  approval and has no model-changing action.
- [x] Replay/synthetic tests prove persistence and idempotency noise control.
- [x] Investigation checklist is available.

## Decisions made

- ADR-0013 and `configs/monitoring/m17-candidate-v1.json`.

## Known limitations

- External/paging delivery is disabled until M18/M20 provide durable storage,
  recipient ownership, authentication, and secret handling.
- M15 remains candidate and M16 lacks validated production delayed labels; all
  M17 output therefore remains candidate and must not be described as a live
  production alert or automatic model action.

## Handoff to milestone berikutnya

- Input tersedia: alert/recommendation JSON schema, candidate policy, CLI,
  aggregate reports, and investigation workflow.
- Constraint: retain the separation among evidence, alert, recommendation,
  M8 evaluation, and M11 approval/deployment.
