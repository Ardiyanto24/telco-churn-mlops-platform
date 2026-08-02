# ADR-0010: Adopt M14 data-quality and drift-engine policy v1

## Status

Accepted

## Date

2026-08-03

## Context

M13 produces an immutable, model-compatible, but still `provisional` reference
baseline. M14 must compare a current population to that reference in a batch
job, distinguish data-quality regressions from distribution shifts, and emit
auditable results without storing raw customer payloads. The system must not
mistake a failed or incompatible comparison for a healthy population.

M15 owns calibration of the production reference population, current-window
policy, sample minima, test/feature thresholds, and multiple-testing settings.
M14 therefore needs an explicit, safe, `experimental` execution policy that
preserves all evidence necessary for calibration rather than prematurely
claiming production alerts.

## Decision

M14 adopts the following twenty decisions.

### 1. Primary current-data source: validated internal batch

Use a schema-validated internal batch as the primary source for full raw-feature
monitoring. M12 telemetry may supply a separate, explicitly partial monitoring
view only for its allowlisted fields.

Telemetry alone is not selected because privacy minimisation intentionally
excludes most inference features. Raw request-payload logging is not selected
because it would violate the M12 privacy boundary. An internal validated batch
provides complete feature coverage without changing serving telemetry retention.

### 2. Initial window unit: one immutable supplied batch per monitoring run

Treat every supplied current batch as one immutable window identified by its
manifest checksum, source period, and filter metadata. A later resolver may
select daily or rolling windows, but M14 does not silently derive time windows
from an unordered file.

Daily, weekly, or rolling windows are not selected as hard-coded defaults
because the source cadence and population period have not been calibrated in
M15. Using file arrival time alone is not selected because retries or delayed
delivery would create different comparisons for the same data.

### 3. Strict current-window contract

Require the baseline's raw feature set and compatible schema/model lineage;
reject missing required features or incompatible feature types. Permit only
explicitly declared non-monitoring metadata columns, and record their presence
without treating them as drift features.

Best-effort column matching is not selected because a plausible comparison on a
misaligned schema is misleading. Silently including arbitrary extra columns is
not selected because it expands the monitoring surface without baseline support.

### 4. Deterministic resolver and window identity

Resolve a window from an explicit input path/manifest and calculate its
idempotency key from baseline ID, model version, monitoring-config version, and
canonical current-window identity. A repeated equivalent invocation returns the
existing completed result rather than creating a second run.

Random run IDs are not selected because they make retries unauditable. A key
based only on a filename is not selected because the contents can change while
the name remains the same.

### 5. Raw features are the principal drift surface

Measure every compatible raw non-identifier inference feature in the M13
`input_reference`; retain transformed-feature observations only as optional
diagnostics tied to the paired preprocessing bundle.

Transformed-only monitoring is not selected because it hides source data and
schema regressions behind preprocessing. Monitoring identifiers is not selected
because high-cardinality identity shifts have no useful model-quality meaning
and increase privacy exposure.

### 6. Data-quality taxonomy is explicit and separate

Report `missing`, `invalid`, `unknown`, and `out_of_range` rates independently
per feature before assessing distributional drift. `invalid` means a value that
cannot meet the expected type/format; `unknown` is a categorical value outside
the baseline support; `out_of_range` applies to numeric values outside the
recorded reference range.

One combined "bad data" rate is not selected because it obscures corrective
action. Coercing invalid values to missing or a known category is not selected
because it conceals upstream contract failures.

### 7. Numeric drift uses complementary effect-size methods

Compute binned Population Stability Index (PSI) using M13 frozen bins for every
numeric batch feature; when raw numeric values are available, also compute
two-sample Kolmogorov-Smirnov (KS) and Wasserstein distance. Record each
method's inputs, statistic, p-value where applicable, and sample counts.

PSI alone is not selected because binning can hide local changes. KS alone is
not selected because it is highly sample-size sensitive and does not quantify
transport magnitude. Wasserstein alone is not selected because it has no
native hypothesis-test p-value. The three together preserve complementary
evidence for M15 calibration.

### 8. Categorical drift uses divergence and goodness-of-fit evidence

Compute Jensen-Shannon divergence on the aligned baseline/current category
support, including `__MISSING__` and `__UNKNOWN__`; compute chi-square only
when its expected-count assumptions hold. Categories absent from the baseline
remain in the explicit unknown bucket.

Chi-square for every categorical window is not selected because sparse expected
counts invalidate its approximation. Jensen-Shannon alone is not selected
because it supplies effect size but no goodness-of-fit significance evidence.
Dropping novel categories is not selected because it hides a material quality
signal.

### 9. Prediction drift uses the serving-policy distribution

Re-score approved current batch inputs with the baseline-compatible model and
compare fixed probability bins, probability quantiles, churn-decision rate, and
risk-band distribution. Use PSI for binned probabilities and Jensen-Shannon/
chi-square eligibility rules for discrete decision and risk-band distributions.

Comparing only final labels is not selected because probability shifts can
precede threshold crossings. Reusing a prediction distribution from a mutable
model alias is not selected because it breaks the baseline's model lineage.

### 10. Quality and drift receive independent result domains

Emit data-quality findings independently from feature-distribution and
prediction-distribution findings. A feature may therefore have quality
degradation with no measured distribution shift, or drift with otherwise valid
values.

One blended score is not selected because it cannot distinguish a schema defect
from population movement. Ignoring quality if a drift statistic is stable is not
selected because invalid/unknown rates can rise while valid-value distributions
remain unchanged.

### 11. Multiple-testing correction is configurable and experimental

Apply Benjamini-Hochberg false-discovery-rate correction to families of
eligible p-values, separately for numeric and categorical feature tests.
Persist raw p-values, adjusted p-values, family membership, and correction
parameters. The target FDR remains experimental until M15.

No correction is not selected because many per-feature tests inflate false
positives. Bonferroni is not selected as the default because it is unnecessarily
conservative for correlated tabular features and can miss useful signals.

### 12. Evidence fields are mandatory for every measurement

Every per-feature result records method, parameters, baseline/current sample
size, missing/unknown counts where relevant, effect size, p-value when defined,
adjusted p-value when eligible, and result reason. Aggregate status may never
be inferred from a p-value alone.

Boolean drift flags are not selected because they lose reproducibility and
calibration evidence. P-value-only decisions are not selected because practical
materiality and sample size are not represented by significance alone.

### 13. Insufficient samples are an explicit non-success state

When a window or method lacks the configured experimental minimum sample count,
or violates a method assumption such as required expected counts, emit
`insufficient_data` for that measurement and exclude its p-value from
multiple-testing correction.

Treating small samples as stable is not selected because absence of evidence is
not evidence of absence. Automatically pooling unrelated windows is not
selected because it changes the population comparison without recorded policy.

### 14. Statuses are evidence-bearing and provisional

Support `stable`, `watch`, `warning`, `critical`, `insufficient_data`, and
`unknown`. Before M15, `stable` means no experimental rule was triggered, not a
claim that the population is production-stable; `watch` through `critical` are
experimental severities only.

A binary stable/drift state is not selected because it loses escalation context.
Final operational thresholds are not selected now because M15 must derive them
from backtests, controlled shifts, and false-positive analysis.

### 15. Fail closed on unavailable or incompatible prerequisites

If the baseline cannot be loaded or validated, model/bundle lineage is
incompatible, the current-window contract fails, scoring fails, or the job
cannot complete, emit an auditable run-level `unknown` outcome with a safe error
classification. Do not emit synthetic feature results in place of the failed
comparison.

Falling back to `stable` is not selected because it creates a false assurance.
Automatically selecting another baseline is not selected because monitoring
would compare against a reference the caller did not authorize.

### 16. Idempotency preserves a single authoritative completed run

Persist a run index keyed by the canonical idempotency key. A retry returns the
prior completed report if its immutable inputs match; interrupted or failed
runs are recorded separately and may be retried without overwriting evidence.

Always recomputing retries is not selected because it duplicates reports and
can yield inconsistent timestamps. Overwriting a failed run is not selected
because it erases operational evidence needed to diagnose monitoring gaps.

### 17. Result schema is versioned and lineage-complete

Use a versioned JSON result schema with run ID, idempotency key, timestamps,
current-window identity, baseline ID/checksum/status, model/schema version,
monitoring-config version/status, measurement results, run status, and safe
error metadata. Human-readable rendering must be generated from this JSON,
not maintained as a second source of truth.

Unversioned ad-hoc JSON is not selected because downstream consumers cannot
validate contract evolution. A prose-only report is not selected because it is
not machine-auditable or suitable for future dashboard/API consumers.

### 18. Reports are JSON-first with a privacy-safe Markdown summary

Write immutable machine-readable JSON for each completed run and a Markdown
summary that shows coverage, status counts, notable experimental findings,
lineage, and limitations. Neither format includes customer rows, entity keys,
or raw feature values.

Dashboard-only output is not selected because M18 is the dedicated internal
visibility milestone. Logs-only output is not selected because it is hard to
query and lacks a durable result contract.

### 19. Monitoring artifacts keep aggregate statistics only

Store counts, proportions, statistics, bins, categories, model/baseline/config
identifiers, and safe error classifications only. Exclude raw current records,
prediction payloads, correlation IDs, hashed entities, and user-controlled
strings from reports and run indexes.

Storing raw windows for debugging is not selected because governed source data
already owns that responsibility and duplicate copies expand exposure. Retaining
identifiers or trace IDs is not selected because they do not improve aggregate
drift diagnosis.

### 20. Provisional baseline and configuration are surfaced end-to-end

M14 accepts the M13 provisional baseline only when explicitly requested and
marks every resulting run/report as `experimental`. Results based on a
provisional baseline or configuration cannot feed production alerting,
retraining, or external metrics until M15 approves replacement configuration
and baseline status.

Treating a successful calculation as approval is not selected because technical
determinism does not prove reference representativeness or calibrated
sensitivity. Refusing all provisional work is not selected because it would
block the measurements M15 needs to perform calibration.

## Consequences

- M14 can produce reproducible, privacy-minimised drift evidence while clearly
  separating quality regressions, feature drift, and prediction drift.
- The initial implementation must expose configuration and evidence rather than
  hard-code unvalidated production thresholds.
- M15 can calibrate concrete sample minima, windows, test selection, FDR, and
  severity thresholds from M14 reports and controlled experiments.
- M17 must not turn M14 experimental severities into operational alerts without
  the approved M15 configuration and its own persistence policy.

## References

- ADR-0008 (M12 telemetry and prediction metadata policy).
- ADR-0009 (M13 reference baseline design).
- https://docs.scipy.org/doc/scipy-1.15.0/reference/generated/scipy.stats.ks_2samp.html
- https://docs.scipy.org/doc/scipy-1.15.0/reference/generated/scipy.stats.wasserstein_distance.html
- https://docs.scipy.org/doc/scipy-1.15.0/reference/generated/scipy.stats.chisquare.html
- https://docs.scipy.org/doc/scipy-1.15.0/reference/generated/scipy.stats.false_discovery_control.html
