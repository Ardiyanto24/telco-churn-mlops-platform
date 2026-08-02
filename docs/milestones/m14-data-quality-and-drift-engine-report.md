# Milestone M14 Completion Report

Status: done
Tanggal: 2026-08-03

## Deliverable

- Batch monitoring engine with separate data-quality, input-feature drift, and
  prediction-drift result domains.
- Versioned JSON-first report, privacy-safe Markdown rendering, complete
  baseline/model/config/window lineage, and idempotency-keyed immutable files.
- CLI runner for a supplied batch, baseline artifact, and verified model bundle.
- Experimental PSI, histogram-weighted Wasserstein, Jensen-Shannon, eligible
  chi-square, Benjamini-Hochberg metadata, and explicit KS `not_applicable`
  evidence for M13's aggregate-only reference.

## Test evidence

- `docker run ... -m unittest discover -s tests -p test_monitoring_engine.py
  -v`: 8 pass.
- Locked-runtime benchmark: 10,000 validated rows completed in 24.46 seconds.
- The full 594,194-row local replay exceeded the two-minute interactive tool
  budget and was stopped; it is not presented as a successful smoke result.

## Exit criteria

- [x] Data quality, feature drift, and prediction drift have distinct result
  domains and aggregate statuses.
- [x] Every result records baseline/model/config/window lineage and method
  evidence; p-values are not the sole status input.
- [x] Raw input features are primary; transformed features are not used as the
  monitoring surface.
- [x] Missing/unknown/out-of-range increases, insufficient samples, incompatible
  baselines, unsupported windows, and idempotent retries are contract-tested.
- [x] Thresholds and sampling policy are explicitly `experimental`; M15 owns
  production calibration.

## Decisions made

- ADR-0010.

## Known limitations

- The M13 aggregate baseline cannot support a valid raw two-sample KS test.
- Prediction drift uses a deterministic 10,000-row cap while full-batch input
  checks remain unsampled; M15 must validate its sensitivity and cost.
- A long-running worker is needed to collect a full 594,194-row replay outside
  the interactive environment.

## Handoff

- M15 should run controlled backtests to approve baseline status, window size,
  minimum samples, metric thresholds, FDR target, and the prediction sample cap.
