# ADR-0011: Adopt M15 statistical-monitoring calibration policy v1

## Status

Accepted

## Date

2026-08-03

## Context

M14 can calculate privacy-minimised quality and drift evidence, but its
thresholds, window behavior, sample minimum, and 10,000-row prediction sample
cap are explicitly experimental. M15 must convert that evidence into a
versioned initial monitoring configuration using reproducible experiments.

There is also a lineage discrepancy: ADR-0009 requires a training-split
reference, while the existing M13 artifact was generated from the complete
validated dataset. It remains useful for controlled calibration, but cannot be
silently promoted as the approved production reference.

## Decision

M15 adopts the following eighteen decisions.

### 1. Baseline approval: retain current baseline for calibration only

Keep the existing M13 artifact `provisional` for M15 experiments. Approve no
baseline until its population, split, lineage, and calibration results meet the
criteria in this ADR.

Promoting it immediately is not selected because its documented intended
training-split provenance conflicts with its actual full-validated-data
generation. Discarding it is not selected because it remains reproducible
evidence for controlled comparisons.

### 2. Production reference population: regenerate from the immutable training split

Generate a new baseline from the exact M5 training split used to fit the paired
model, with split seed, filter, source period, manifest checksum, and model
manifest recorded. Promotion to `approved` requires a representativeness review
and successful M15 calibration.

Using all validated rows is not selected because it contaminates the separation
between training reference and independent evaluation. A live mutable baseline
is not selected because it would hide population movement and defeat auditability.

### 3. Current-window policy: non-overlapping daily batches

Use one immutable UTC-day batch per monitoring run when production timestamps
are available; retain M14's explicit supplied-batch identity for backtests and
sources without timestamps. Do not overlap production windows.

Hourly windows are not selected because expected volume and labels do not
justify alert noise. Weekly windows are not selected because they delay
detection. Rolling overlapping windows are not selected because repeated rows
inflate correlated alerts and complicate idempotency.

### 4. Late-arrival policy: close after a 24-hour grace period

Allow late records for a UTC-day window until 24 hours after its close, then
seal a new versioned window manifest and recompute once. Later arrivals are
reported in the next window with an explicit late-data count.

Infinite mutation is not selected because reports cease to be reproducible.
Dropping late data immediately is not selected because ordinary delivery lag
would become artificial drift.

### 5. Global minimum current sample: 500 rows

Require 500 current rows before issuing a run-level distribution status. Below
that level, emit `insufficient_data` while still reporting quality counts.

The M14 development minimum of 30 is not selected because it is too noisy for a
production population claim. A much larger universal minimum is not selected
because it would delay monitoring for smaller but legitimate daily cohorts.

### 6. Per-method eligibility: 500 numeric, expected categorical cells >= 5

Require 500 valid numeric observations for PSI/Wasserstein and retain the
chi-square expected-count-at-least-five rule. Jensen-Shannon remains available
as descriptive effect size when categorical significance is ineligible.

Using a single rule for every method is not selected because their assumptions
differ. Treating sparse chi-square results as significant is not selected
because its asymptotic approximation is unreliable.

### 7. Critical-feature policy: equal monitoring, tiered triage

Calculate every raw non-identifier feature equally. Mark `tenure`,
`MonthlyCharges`, `TotalCharges`, `Contract`, `InternetService`, and
`PaymentMethod` as Tier 1 for report ordering and M17 triage, not for lowering
their statistical thresholds.

Weighted aggregate scores are not selected because they can hide a severe
non-weighted feature issue. Treating every report line equally is not selected
because these features have direct business/model relevance and deserve faster
human attention.

### 8. Numeric primary method: PSI plus normalized histogram Wasserstein

Use frozen-bin PSI as the primary comparable effect size and normalized
histogram-weighted Wasserstein as a complementary movement measure. Require both
to be recorded; severity is the higher calibrated effect, subject to quality
status.

PSI alone is not selected because binning can conceal positional movement.
Wasserstein alone is not selected because its scale depends on the feature range.
Raw KS is not selected because the approved aggregate-only baseline will not
retain raw reference samples.

### 9. KS policy: remain not applicable; no retained raw samples in v1

Do not expand baseline retention merely to enable KS in M15. Keep KS explicitly
`not_applicable` and assess whether PSI/Wasserstein detect every controlled
numeric scenario chosen for this model.

Adding raw feature samples now is not selected because it expands privacy and
retention scope before evidence demonstrates need. Pretending a histogram is a
raw KS sample is not selected because it would produce invalid significance.

### 10. Categorical primary method: Jensen-Shannon plus eligible chi-square

Use Jensen-Shannon divergence as the always-available categorical effect size;
add chi-square p-values only where expected-count eligibility holds. New values
remain an explicit unknown-quality signal and are not folded into known classes.

Chi-square-only is not selected because sparse categories are common. A
divergence-only policy is not selected because it loses useful significance
evidence where assumptions are met.

### 11. Prediction drift: probability PSI primary, decision/risk distributions diagnostic

Use probability-bin PSI as the primary prediction-drift statistic. Record churn
decision-rate and risk-band shifts as diagnostic distributions bound to the
serving threshold policy; they cannot independently create a critical status.

Decision-rate-only monitoring is not selected because probability shifts can
occur before a threshold crossing. Treating risk bands as the primary metric is
not selected because they discard probability resolution.

### 12. Prediction sample cap: 10,000 deterministic rows, minimum 500

Retain the M14 checksum-seeded cap of 10,000 rows and require at least 500 rows
for prediction distribution results. Calibrate it by comparing fixed-seed
samples against larger offline samples; record the sample size in every result.

Full-window re-scoring is not selected because M14 measurement showed it is
operationally expensive on 594,194 rows. A smaller cap is not selected because
it increases sampling variance without a demonstrated operational benefit.

### 13. Multiple testing: Benjamini-Hochberg at FDR 5 percent

Apply Benjamini-Hochberg correction at `q=0.05` separately to eligible numeric
and categorical feature-test families. Preserve raw and adjusted p-values;
effect-size thresholds remain mandatory.

No correction is not selected because many feature tests inflate false alarms.
Bonferroni is not selected because it is overly conservative for correlated
tabular features and reduces sensitivity.

### 14. Calibrated thresholds: method-specific, effect-first

Start calibration targets at PSI `0.10/0.20/0.30`, normalized Wasserstein
`0.05/0.10/0.20`, Jensen-Shannon `0.05/0.10/0.20`, and quality-rate delta
`0.01/0.05/0.15` for `watch/warning/critical`. Accept each only if backtests
meet the targets below; otherwise issue a new config version with evidence.

One universal threshold is not selected because metrics have different ranges
and meanings. P-value-only thresholds are not selected because large samples
can make negligible shifts statistically significant.

### 15. Severity combination: quality can escalate, drift needs effect evidence

Set a feature's severity to the maximum of calibrated quality and distribution
severity. Distribution `warning` or `critical` requires its calibrated effect
threshold; an adjusted p-value below 0.05 may elevate `watch` to `warning` but
cannot create `critical` alone.

A blended opaque score is not selected because operators need to know whether
to repair data or investigate population change. Ignoring a serious quality
regression when distribution drift is low is not selected because monitoring
input itself may be broken.

### 16. Calibration targets: FPR <= 5%, sensitivity >= 80%, daily detection <= 2 windows

Accept a candidate configuration only if stable controlled/historical windows
produce at most five percent warning-or-higher runs, material controlled shifts
are detected in at least 80 percent of seeded repetitions, and daily material
shifts are detected within two completed windows.

Zero false positives is not selected because it usually implies unusably weak
sensitivity. Maximising sensitivity without an FPR bound is not selected because
it creates alert fatigue and undermines M17.

### 17. Persistence: two consecutive warning-or-higher windows for operational escalation

Retain individual M15 severities immediately, but define an M17-ready candidate
escalation only when the same feature/domain is warning-or-higher in two
consecutive complete windows. A single critical data-quality failure remains an
exception candidate for immediate human review, subject to M17 policy.

One-window escalation is not selected because isolated batch noise can trigger
unnecessary action. A longer persistence requirement is not selected because it
materially increases detection delay for daily monitoring.

### 18. Reproducibility and config governance: immutable experiment packs

Every calibration scenario must record dataset/baseline/model/config checksums,
fixed seed, injected-shift parameters, results, and code revision. Any change
to thresholds, eligibility, sample cap, FDR, or severity logic creates a new
immutable `monitoring_config_version`; no config is edited in place.

Notebook-only conclusions are not selected because they cannot be rerun in CI
or audited. Mutable configuration files are not selected because historic
monitoring results would become uninterpretable.

## Consequences

- M15 must regenerate a training-split baseline before it can mark a baseline
  `approved` for the paired model.
- The first production-candidate configuration has explicit statistical and
  operational targets, while remaining revisable through a new version.
- M16/M17 can consume a stable monitoring contract without treating a single
  uncalibrated M14 signal as an alert or retraining recommendation.

## References

- ADR-0009 (M13 reference baseline design).
- ADR-0010 (M14 data-quality and drift-engine policy).
- https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.false_discovery_control.html
- https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.chi2_contingency.html
