# ADR-0009: Propose M13 reference-baseline design v1

## Status

Accepted

## Date

2026-08-02

## Context

M12 now produces privacy-minimised prediction telemetry, while M14 must later
calculate data and prediction drift from a stable reference. A comparison is
only meaningful when its reference population, bin edges, model lineage, and
feature policy are frozen. M13 must therefore create an immutable baseline
artifact, not an alert threshold or a mutable dashboard view.

The current telemetry allowlist covers only a derived subset of inference
features. Full feature monitoring remains possible only when M14 receives a
validated batch from an approved internal source. This design deliberately
records that coverage boundary instead of claiming full live-feature
observability.

## Decision

This ADR adopts the following thirteen M13 design decisions. Generated baseline
artifacts themselves remain `provisional` until their reference population is
reviewed for representativeness.

### 1. Baseline population: validated training split only

Build the primary reference baseline from the M5-validated training split used
to fit the paired model. Store the exact dataset manifest, split seed, filter,
sample size, and source period.

Using the training split best represents the distribution the model learned
while retaining validation/test data as independent M8 evidence. Using the
whole dataset is not selected because it weakens separation between training
and evaluation governance. Using live traffic is not selected because no
approved production population exists and it would make the reference mutable.

### 2. Baseline state: provisional first, explicit approval later

Generate an immutable `provisional` artifact first. Promote its status to
`approved` only after a documented review confirms that the training population
is representative for the intended use case.

Immediately treating a generated artifact as approved is not selected because
statistical reproducibility does not establish business representativeness.
Keeping a permanently mutable draft is not selected because M14 needs a stable
reference to produce auditable results.

### 3. Scope: two aligned baseline layers

Store an `input_reference` for every non-identifier inference feature and a
`telemetry_reference` only for M12's allowlisted derived observations. The
artifact explicitly declares coverage for each layer.

A telemetry-only baseline is not selected because it cannot monitor the full
feature contract in an approved batch workflow. A full raw-payload telemetry
baseline is not selected because it violates M12 minimisation and privacy
boundaries.

### 4. Identifier policy: exclude customer identifiers completely

Exclude `customer_id`, pseudonymous entity keys, and any direct identifier from
all baseline feature distributions. They may appear only in separately governed
M16 join workflows, never as drift features.

Including identifiers is not selected because their cardinality makes drift
statistics meaningless and increases privacy risk. Hashing identifiers into a
baseline is not selected because it still creates a persistent identifier
inventory without monitoring value.

### 5. Numeric statistics: descriptive summary plus frozen bins

For each numeric feature, store non-missing count, missing/invalid rate, min,
max, mean, standard deviation, P01/P05/P25/P50/P75/P95/P99, fixed bin edges,
and bin counts/proportions. Initial bins use deterministic training-population
quantiles and are persisted unchanged.

Summary-only statistics are not selected because PSI needs comparable bins.
Recomputing quantile bins from each current window is not selected because the
reference itself would move and hide distribution changes.

### 6. Categorical statistics: explicit known, missing, and unknown buckets

For each categorical feature, store the allowlisted category set and counts/
proportions for each category, `__MISSING__`, and `__UNKNOWN__`. Unknown is a
first-class monitoring outcome rather than being silently mapped to a known
value.

Only storing observed categories is not selected because a new category cannot
then be measured consistently. Dropping unknown values is not selected because
it hides schema/data-quality regressions that can look like stable drift.

### 7. Prediction baseline: bind outputs to the exact serving policy

Generate baseline predictions with the same verified model bundle, schema, and
decision/risk thresholds as the artifact lineage. Store fixed probability-bin
counts, mean/quantiles, churn-decision rate, and risk-band distribution.

Input-only baselines are not selected because prediction drift can occur even
when individual input summaries look stable. Recomputing outputs with a mutable
model alias is not selected because the baseline would no longer identify what
served the reference predictions.

### 8. Data-quality reference: retain rates, not customer rows

Store missing, invalid, unknown, and out-of-range rates per feature, along with
the validation/range policy needed to interpret them. Do not persist individual
reference rows in the baseline artifact.

Row-level baseline snapshots are not selected because they duplicate governed
data and increase privacy/storage exposure. Omitting quality rates is not
selected because a feature can appear distributionally stable while becoming
invalid or unknown more often.

### 9. Drift-method readiness: preserve sufficient statistics for multiple methods

Persist counts, fixed bins, category support, and descriptive numeric summaries
so M14 can calculate PSI for binned data; KS/Wasserstein for approved raw
numeric batch windows; and Jensen-Shannon or chi-square for categorical and
prediction distributions.

Selecting one universal statistic is not selected because continuous, binned,
and categorical data have different assumptions. Storing only p-values is not
selected because it loses effect size, sample size, and reproducibility inputs.

### 10. Threshold separation: no warning or critical cutoff in M13

M13 records reference statistics and method parameters but does not decide
`watch`, `warning`, or `critical` thresholds. M15 calibrates those thresholds
through backtesting and false-positive analysis.

Copying generic PSI or p-value cutoffs into M13 is not selected because their
sensitivity depends on feature distribution, sample size, and window policy.
Leaving thresholds undocumented is not selected; their absence is explicit and
the result remains `provisional` until M15.

### 11. Lineage and identity: content-addressed immutable artifact

Derive `baseline_id` and manifest checksum from canonical baseline content and
bind it to model version/checksum, dataset manifest checksum, schema version,
preprocessing/feature-engineering version, source split, and generator version.

Timestamp-only or model-version-only IDs are not selected because they cannot
reconstruct exact content. Overwriting a baseline for the same model is not
selected because old monitoring results and releases must remain auditable.

### 12. Compatibility: fail closed on incompatible model or contract

Provide a validator that rejects a baseline when model manifest, schema,
feature list/type, preprocessing version, or prediction threshold policy does
not match. Compatible replacement requires a newly generated artifact and an
explicit lineage link.

Best-effort matching is not selected because it can produce a plausible but
invalid drift result. Automatically reusing a previous model's baseline is not
selected because feature preprocessing and decision policy may have changed.

### 13. Validation: determinism and synthetic negative controls

Tests must prove equal validated inputs produce byte-identical baseline content
and checksum; a changed model/schema/feature fails validation; missing or
unknown inputs are represented; and prediction distributions use the correct
model thresholds.

Manual inspection alone is not selected because binning and lineage defects are
easy to miss. Positive tests alone are not selected because M13's safety value
comes from rejecting incompatible baseline use before M14 emits drift claims.

## Consequences

- M13 will produce an immutable reference artifact, with explicit coverage
  boundaries, that M14 can use without inspecting raw customer payloads.
- Drift results can distinguish input quality, feature-distribution, and
  prediction-distribution changes while preserving model lineage.
- M15, not M13, owns calibrated alert thresholds; M17 must not treat any M13
  statistic as a retraining trigger before that calibration exists.

## References

- https://docs.scipy.org/doc/scipy-1.15.0/reference/generated/scipy.stats.ks_2samp.html
- https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.stats.wasserstein_distance.html
- ADR-0005 (M9 runtime lineage), ADR-0008 (M12 telemetry minimisation).
