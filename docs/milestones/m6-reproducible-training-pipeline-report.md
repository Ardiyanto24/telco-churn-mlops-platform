# M6 Reproducible Training Pipeline Report

## Status

Verified on 2026-08-02.

## Delivered

- One-command training CLI: `python scripts/train_model.py`.
- Versioned deterministic configs in `configs/training/`; default CLI uses `m6-legacy-voting-v1.json`.
- Stratified train/validation/test split with explicit seed, train-only fitting, validation-only threshold selection, and test-only final evaluation.
- Candidate bundle compatible with the M3 verified artifact loader, plus `metrics.json`, `training_run.json`, and precision-recall SVG.
- Configurable model factory for Logistic Regression, LightGBM, XGBoost, and the
  legacy-composition Voting Ensemble. Each candidate records `model_family`.

## Reproducibility contract

Two runs with identical verified data, config, runtime lock, and seed must have identical serialized metrics in this locked runtime. Tests use exact equality; cross-platform or changed-BLAS runs should be compared with absolute tolerance `1e-12`. A changed seed or model parameter is recorded as a distinct run input.

## Candidate result

The metrics below are historical evidence from the pre-revision Logistic Regression candidate; they are not the result of the current default Voting Ensemble.

The generated local candidate (`artifacts/candidates/m6-logistic-v1/`) used the M5 dataset manifest SHA-256 `0eea83d4…4d52da5c` (594194 rows). Its test-set metrics were AP `0.7461341275`, ROC-AUC `0.9138487697`, F1 `0.6980450923`, and validation-selected threshold `0.3909368362`. This is evaluation evidence only; it is not a promotion decision.

## Test evidence

| Check | Result |
|---|---|
| Multi-model M6 model/contract suite | 19 passed in `telco-churn-m6-runtime:local`. |
| Full-data Logistic Regression CLI (pre-revision) | Completed in 155.5 seconds from commit `e4da1aa`. |
| M3 loader on final candidate | Loaded successfully; 29 features. |
| Broad regression suite | 41 passed; one baseline integration cannot invoke Docker from inside the verification container, unrelated to M6. |

## Exit criteria

- [x] Training runs non-interactively through one command.
- [x] Config, seed, dataset manifest, code revision, split counts, metrics, and candidate files are captured in the run outputs.
- [x] No notebook state is required.
- [x] Reproducibility tolerance is documented and enforced by tests.

## Limitations and handoff

- M6 has no experiment tracker, immutable remote artifact registry, or quality promotion gate; those are M7 and M8 responsibilities.
- Candidate artifacts are ignored by Git intentionally. M7 should copy their immutable URI and metadata into the registry/tracker before any promotion.
- The legacy artifact exposes an estimator named `xgboost_smote`, but not the original SMOTE recipe. The default M6 ensemble preserves its estimator composition, weights, and available hyperparameters, but is not a bit-for-bit retraining claim. A full-data run of the new default ensemble must be recorded as a new candidate before M7 registration.
