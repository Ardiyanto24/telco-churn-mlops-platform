# Milestone M16 Completion Report

Status: done (framework; production source integration pending)

Tanggal: 2026-08-03

Commit/PR: pending

## Deliverable

- Validated, privacy-minimised prediction-event and delayed-label contracts.
- Idempotent prediction-label join with duplicate detection, conflict
  quarantine, immutable result revisions, coverage, and reconciliation counts.
- Monthly/rolling (up to three contiguous months) performance evaluation with
  PR-AUC, ROC-AUC, precision, recall, F1, confusion matrix, Brier score, and
  fixed-bin calibration data.
- Protected JSON Lines job entry point, candidate M16 configuration, aggregate
  JSON/Markdown report, and explicit origin label.

## Test evidence

- Command/workflow: `python -m unittest tests.test_performance_monitoring -v`
  in `telco-churn-m8-runtime:local`.
- Result: 7 tests passed.
- Command/workflow: `python scripts/run_tests.py model` in
  `telco-churn-m8-runtime:local`.
- Result: 49 tests passed in 33.684 seconds.
- Re-run after the final M16 guards: model category and the combined M12--M16
  contract suites passed in the locked runtime.
- Entry point: `python scripts/run_performance_monitoring.py --help` in the
  same locked runtime image.

## Exit criteria

- [x] Results require matured labels; immature predictions are excluded.
- [x] Duplicate deliveries do not increase the evaluated population; conflicts
  are quarantined.
- [x] One result uses one immutable model/threshold/risk-policy and label
  definition lineage.
- [x] Known synthetic labels prove manually computed ranking, classification,
  calibration, and confusion-matrix metrics.
- [x] Low coverage/sample produces `insufficient_data`; no joined labels
  produces `not_available`.
- [x] Results carry `offline_test`, `replayed`, `synthetic`, or controlled
  `production` origin; production is disabled in the candidate config.

## Decisions made

- ADR-0012: delayed-label performance-monitoring policy v1.
- `configs/monitoring/m16-candidate-v1.json`.

## Known limitations

- No delayed-label package has been supplied, so no identifier mapping,
  business churn definition, production coverage, or production maturity claim
  has been validated.
- The M12 durable protected per-prediction join export must be connected before
  a real source can be ingested. Normal aggregate request telemetry is not a
  substitute.
- M17 owns calibrated performance-decay severity and alert/retraining policy;
  M16 records evidence only.
- The full category runner's M0 Docker-capture integration cannot run from
  inside the locked test container because it requires Docker-in-Docker. This
  does not affect the M16 unit/model verification above.

## Handoff to milestone berikutnya

- Input yang tersedia: versioned M16 contracts, candidate configuration,
  protected JSONL runner, aggregate result schema, and synthetic tests.
- Constraint yang harus dipertahankan: do not enable `production` origin or
  label a result as live performance without approved source mapping and
  matured authoritative labels.

## References

- [scikit-learn average_precision_score](https://scikit-learn.org/1.6/modules/generated/sklearn.metrics.average_precision_score.html)
- [scikit-learn roc_auc_score](https://scikit-learn.org/1.6/modules/generated/sklearn.metrics.roc_auc_score.html)
- [scikit-learn brier_score_loss](https://scikit-learn.org/1.6/modules/generated/sklearn.metrics.brier_score_loss.html)
