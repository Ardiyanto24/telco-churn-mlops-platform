# M13 Reference Baseline Generation Log

## Context dan assumptions

- ADR-0009 is accepted: a generated artifact is immutable and starts as
  `provisional`; M15 owns drift thresholds.
- The M3 manifest's feature signature is transformed-feature lineage, while
  data drift requires raw inference features. These contracts are recorded
  separately in the baseline.

## Plan dan actions

- Added a deterministic baseline builder, checksum/compatibility validator, and
  immutable writer in `telco_churn.monitoring_baseline`.
- Added `scripts/generate_baseline.py` to consume only a verified M5 dataset,
  its manifest, and a verified M3 bundle.
- Added M13 tests to the model/all test runner categories.

## Evidence dan findings

- `docker run ... -m unittest discover -s tests -p
  test_monitoring_baseline.py -v`: 2 pass.
- Tests prove deterministic content-addressed output, identifier exclusion,
  prediction baseline generation, and fail-closed model/feature incompatibility.

## Errors dan handling

- Inspection of the verified M6 bundle showed `model_manifest.feature_order`
  is the transformed signature. The first design incorrectly treated it as raw
  data columns. The generator now derives raw features from the validated data
  contract and records the transformed signature separately.
- Generating the full local M6 baseline exceeded this environment's 64-second
  Docker command limit. The generator was then run as a hidden local Docker
  process and completed successfully without changing the code or inputs.

## Decisions dan deviations

- Baseline lineage contains both `raw_feature_order` and
  `transformed_feature_signature`; M14 must use the former for raw feature
  monitoring and retain the latter for model compatibility diagnostics.

## Risks, limitations, dan follow-up

- The resulting local artifact is
  `artifacts/baselines/cb915da23b430f6c9f0bab2b7d5b5967fa3270a8d1a44bf6025e8e7ae87079de/baseline.json`.
  It has 594194 reference rows, status `provisional`, and passed its
  checksum/compatibility validation. Do not commit bundle, dataset, or
  generated baseline artifact.

## Trace references

- ADR-0009; `src/telco_churn/monitoring_baseline.py`;
  `scripts/generate_baseline.py`; `tests/test_monitoring_baseline.py`.
