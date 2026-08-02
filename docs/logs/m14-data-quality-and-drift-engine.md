# M14 Engineering Log — Data quality and drift engine

## Context and assumptions

- M13 provides the immutable provisional baseline
  `cb915da23b430f6c9f0bab2b7d5b5967fa3270a8d1a44bf6025e8e7ae87079de`.
- M14 processes an explicitly supplied, validated internal batch as its main
  current window. M12 telemetry remains a partial, privacy-minimised source.
- Severity configuration is experimental until M15; no M14 output may trigger
  production alerting or retraining.

## Plan and actions

- Inspect the M13 artifact contract and SciPy 1.15.3 statistical APIs before
  implementing the batch engine.
- Add contract tests first, then implement the smallest JSON-first monitoring
  path, idempotency, and Markdown rendering in independently verified slices.

## Evidence and findings

- The M13 baseline retains frozen numeric bins/counts and categorical counts,
  but does not retain raw numeric reference observations.
- Therefore PSI, categorical Jensen-Shannon/chi-square, and
  histogram-weighted Wasserstein evidence are available; a raw two-sample KS
  test is not applicable to this baseline.
- `docker run ... -m unittest discover -s tests -p test_monitoring_engine.py
  -v` passed 8 controlled contract tests: stable, numeric/categorical shift,
  data-quality degradation, insufficient data, fail-closed baseline/schema,
  idempotency, config-aware retry, bounded deterministic prediction sampling,
  and extra-column rejection.
- A locked-runtime benchmark on 10,000 validated rows completed in 24.46
  seconds. Full-batch data-quality/feature calculations remain enabled; a
  594,194-row replay exceeded the local two-minute interactive budget and was
  stopped by the tool timeout, not reported as a successful smoke run.

## Errors and handling

- No implementation error yet. A contract/design mismatch was found before
  code was written: the original M14 method list included KS, while the M13
  aggregate-only artifact cannot support it validly.

## Decisions and deviations

- User approved the aggregate-only baseline path. ADR-0010 records that KS is
  `not_applicable`, while preserving an explicit governed path to a future
  superseding baseline version if M15 calibration requires retained samples.
- Prediction scoring is deterministically capped at 10,000 rows in the
  experimental M14 config after measurement showed 10,000 rows took 24.46
  seconds. Full-window quality and input-distribution calculations are not
  sampled. The cap is versioned/config-hashed and requires M15 calibration.

## Risks, limitations, and follow-up

- Histogram evidence may be less sensitive than an approved retained-sample
  reference for some local continuous shifts. M15 must test this limitation.
- A full local replay requires a longer execution environment or a scheduled
  batch worker; it was not declared successful from a timed-out interactive run.

## Trace references

- ADR-0010.
- SciPy 1.15.3 `ks_2samp`, `wasserstein_distance`,
  `chi2_contingency`, and `false_discovery_control` documentation.
