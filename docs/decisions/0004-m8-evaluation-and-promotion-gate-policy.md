# ADR-0004: Adopt M8 offline evaluation and promotion gate policy v1

## Status

Accepted

## Date

2026-08-02

## Context

M8 must prevent a candidate trained successfully in M6 from becoming a
registry champion when it is invalid, materially worse than the champion, or
insufficient for the churn-retention use case. The project has validated
offline data and historical legacy metrics, but no mature production labels.
This policy is therefore an offline candidate-selection contract, not a claim
about live production performance.

The values below are deliberately versioned and reproducible. They are initial
portfolio-grade controls based on the documented legacy validation performance
(PR-AUC 0.7525, recall 0.7820, precision 0.6377, F1 0.7025, ROC-AUC 0.9155).
They must be recalibrated when business costs and delayed production labels are
available in M16; a changed value requires a new gate-config version and ADR.

## Decision

M8 implements `evaluation-gates/v1` with the following ten decisions.

### 1. Primary and supporting metrics

- Primary ranking metric: Average Precision / PR-AUC.
- Supporting metrics: recall, precision, F1, ROC-AUC, Brier score, expected
  calibration error (ECE), threshold, and latency.
- PR-AUC decides ranking because churn is an imbalanced positive-class problem;
  no single supporting metric may compensate for a failed hard threshold.

### 2. Absolute acceptance thresholds

On the immutable test split, at the candidate's stored validation-selected
threshold, all of the following must hold:

| Metric | Gate |
|---|---:|
| PR-AUC | >= 0.740 |
| Recall | >= 0.750 |
| Precision | >= 0.600 |
| F1 | >= 0.680 |
| ROC-AUC | >= 0.900 |
| Brier score | <= 0.160 |
| ECE, 10 equal-frequency bins | <= 0.050 |

### 3. Regression gates against a champion

When a valid `champion` exists for the same evaluation dataset and protocol, a
candidate must also satisfy all of these absolute deltas:

| Metric | Maximum allowed regression |
|---|---:|
| PR-AUC | 0.010 |
| Recall | 0.020 |
| F1 | 0.015 |
| Precision | 0.030 |
| ROC-AUC | 0.010 |
| Brier score | 0.010 increase |
| ECE | 0.010 increase |

The report uses 2,000 deterministic stratified bootstrap resamples (seed 42)
and records the 95% confidence interval for every candidate-minus-champion
delta. A regression gate fails when its observed delta exceeds the tolerance;
confidence intervals are evidence, not a way to waive the limit.

### 4. Comparator and evaluation protocol

- Candidate and champion must use the same M5 dataset-manifest SHA-256, target
  definition, M6 test partition, preprocessing contract, and gate-config
  version.
- External legacy validation numbers are context only and are never a champion
  comparator because they were not evaluated on this immutable protocol.
- If no compatible champion exists, the outcome is `not_comparable`; absolute
  gates still run, but no alias changes automatically.

### 5. Threshold policy

- The gate consumes the decision threshold already stored in the verified M3
  bundle. It never selects or retunes a threshold on the test split.
- Threshold-specific precision, recall, and F1 are measured at that value.
- A candidate that needs a different threshold must be retrained/re-evaluated
  from validation data; it cannot alter a registered bundle in place.

### 6. Hard validity and robustness gates

The following are non-negotiable failures:

- M3 verified loader failure, manifest/checksum/runtime mismatch, or changed
  feature signature/order/count.
- Any transformed feature or probability that is NaN or infinite, or a
  probability outside `[0, 1]`.
- Any failure on the complete M0 anonymous golden fixture, M2 valid request
  fixture, or defined numeric/category boundary fixture.
- Non-deterministic probabilities beyond absolute tolerance `1e-12` when the
  candidate is evaluated twice in the locked runtime.

### 7. Calibration and latency protocol

- Compute Brier and ECE on the untouched test split. ECE uses ten
  equal-frequency bins and records bin counts; no bin with zero samples is
  silently discarded.
- Measure warm-process prediction latency on the locked reference CPU runtime:
  100 single-record calls and 20 batches of 100 records, excluding model-load
  time. Gates are p95 <= 100 ms for one record and p95 <= 500 ms for batch 100.
- Image-size and vulnerability gates remain M9/M10 concerns, not M8 shortcuts.

### 8. Approval and alias authority

- A passing report creates only `eligible_for_review`; it never deploys a model.
- An ML Engineer must explicitly approve an immutable promotion-decision
  artifact containing the candidate version, report digest, gate-config
  version, evaluator, and UTC timestamp.
- Only that approval command may assign or reassign `champion`; it must first
  verify the exact report digest and `passed` status. `champion` remains a
  registry selection label, not a production deployment action.

### 9. Decision statuses

| Status | Meaning |
|---|---|
| `invalid` | A hard validity, compatibility, or robustness gate failed. |
| `failed` | Valid candidate, but an absolute or regression metric gate failed. |
| `not_comparable` | Absolute/hard gates passed but no compatible champion exists. |
| `passed` | All hard, absolute, and applicable regression gates passed. |
| `approved` | A human approved a `passed` report, or explicitly selected the first `not_comparable` baseline champion. |

All non-`approved` states leave the current `champion` unchanged. An initial
champion selected from `not_comparable` must be labelled `initial_baseline` in
the decision artifact.

### 10. Governance, reproducibility, and scope

- Gate config, evaluation dataset manifest, candidate/champion URIs, seeds,
  report digest, tool/runtime versions, and all results are immutable artifacts.
- Every report labels its data origin `offline_test`; no M8 value may be shown
  as production performance.
- Failed candidates receive `validation_status=failed`; M8 does not delete or
  overwrite their run artifacts. Archive decisions occur only through an
  auditable later action.

## Alternatives Considered

### Promote by the highest PR-AUC alone

- Rejected: it can accept an operationally unusable model with inadequate
  recall, invalid probabilities, poor calibration, or excessive latency.

### Use legacy validation metrics as the first champion comparator

- Rejected: the split and evaluation protocol differ, so a numerical delta
  would not be defensible.

### Automatically assign `champion` after a passing test

- Rejected: gates provide evidence, while promotion remains an accountable
  decision. MLflow aliases are mutable and must not bypass approval.

### Tune the threshold on the M8 test split

- Rejected: it leaks test information and makes the reported metrics optimistic.

## Consequences

- M8 has a complete, deterministic acceptance contract and negative-test cases.
- The first compatible candidate can establish a registry baseline only through
  explicit human approval; later candidates must satisfy regression controls.
- The numeric policy is intentionally revisitable, but changes are versioned
  rather than silently replacing evidence.

## References

- https://scikit-learn.org/stable/modules/calibration.html
- https://mlflow.org/docs/latest/ml/model-registry/
- https://www.mlflow.org/docs/latest/ml/model-registry/workflow/
