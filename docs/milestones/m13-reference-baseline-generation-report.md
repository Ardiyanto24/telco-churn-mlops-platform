# Milestone M13 Completion Report

Status: done
Tanggal: 2026-08-02

## Deliverable

- Deterministic baseline artifact builder, immutable writer, and fail-closed
  compatibility validator.
- Verified-data/bundle baseline-generation command.
- Versioned raw-feature, telemetry-coverage, prediction-distribution, and
  lineage schema.

## Test evidence

- `docker run ... -m unittest discover -s tests -p
  test_monitoring_baseline.py -v`: 2 pass.

## Exit criteria

- [x] Baseline content is immutable, content-addressed, and model/schema
  compatible.
- [x] Artifact records sample size, reference origin, data/model lineage,
  raw-feature coverage, and prediction policy.
- [x] Incompatible model or feature contract fails closed.
- [x] M6 candidate baseline
  `cb915da23b430f6c9f0bab2b7d5b5967fa3270a8d1a44bf6025e8e7ae87079de`
  was generated locally from verified inputs, has 594194 reference rows, and
  passed checksum/compatibility validation.

## Decisions made

- ADR-0009.

## Known limitations

- No drift thresholds are defined; this is intentionally deferred to M15.
- The baseline remains `provisional` until a later representativeness review;
  this is the accepted M13 baseline-state policy, not an implementation gap.

## Handoff

- Use the M6 provisional baseline as M14's immutable reference input; M15 may
  later approve or supersede it after calibration.
