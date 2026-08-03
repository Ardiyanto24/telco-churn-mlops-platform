# ADR-0012: Adopt M16 delayed-label performance-monitoring policy v1

## Status

Accepted

## Date

2026-08-03

## Context

M12 emits privacy-minimised, versioned prediction metadata, while M14 and M15
measure data and prediction drift. Neither is evidence that the deployed churn
model is still accurate: that conclusion requires actual outcomes whose
observation period has completed. M16 establishes the contract and evaluation
framework for those delayed labels before the external delayed-label dataset is
available.

The dataset's exact identifier, outcome timestamps, arrival behavior, and
business churn definition are not yet supplied. Consequently this ADR defines
a safe, versioned production-candidate contract. Its values must be validated
against the real source before any result is labelled `production`; synthetic
and replay fixtures are used only to prove the framework.

## Decision

M16 adopts the following twenty decisions.

### 1. Ground truth: versioned business churn outcome

Use a binary `churned_within_horizon` outcome defined by the approved business
churn policy, with its definition version stored on every label and evaluation
result. The initial contract leaves the human-readable definition configurable
rather than inferring it from cancellation-like fields.

Treating a missing future activity as churn is not selected because absence can
be an ingestion or observation problem. Hard-coding a dataset-specific column
is not selected because the pending source may use a different business event.

### 2. Label source: authoritative outcome feed, not inference payloads

Ingest delayed labels from a separately versioned, access-controlled outcome
feed. The feed is the authority for label values and revisions; M16 never
derives labels from prediction requests or prediction decisions.

Using prediction payloads is not selected because it creates circular evidence.
Letting each monitoring job synthesize outcomes is not selected because it
removes source lineage and makes correction impossible.

### 3. Join key: keyed pseudonymous entity reference plus prediction identity

Join labels to predictions using the M12 `entity_key` within its recorded key
epoch, plus a stable `prediction_id` (or a source-provided equivalent). The
raw customer identifier remains outside the monitoring store and join job.

Joining on customer attributes is not selected because it is privacy-invasive
and can create false matches. Using only an entity key is not selected because
one customer can legitimately receive more than one prediction.

### 4. Prediction-event identity: immutable UUID generated at serving ingress

Require a unique opaque `prediction_id` for every prediction event, generated
once at API ingress and retained with its lineage metadata. Batch requests
receive one event identity per evaluated row in the protected join export,
even though M12's normal telemetry remains aggregate per request.

Reusing `request_id` alone is not selected because it identifies a batch rather
than a decision. Constructing an ID later from timestamps and features is not
selected because it is unstable and exposes customer-derived data.

### 5. Maturity horizon: configurable 90 calendar days from prediction time

Set the initial candidate maturity horizon to 90 UTC calendar days after
`prediction_at`. A label may enter performance calculation only once that
horizon and the 24-hour ingestion grace period have elapsed; both values are
versioned configuration.

Immediate outcome evaluation is not selected because churn is inherently a
delayed business outcome. An unbounded wait is not selected because results
would never become operationally useful. The 90-day value is a candidate to be
validated against the supplied data, not a claim about the business today.

### 6. Temporal authority: UTC event time with received-at audit time

Use UTC `prediction_at` to determine the maturity deadline and window; retain
source `outcome_at` and `label_received_at` for audit and late-arrival
classification. Invalid or missing event times are quarantined with reasons.

Using collector receipt time as the primary clock is not selected because
transport delay would change eligibility. Local times are not selected because
day boundaries and daylight-saving conversions become ambiguous.

### 7. Label revisions: append-only versions, latest eligible revision wins

Store labels append-only with a `label_revision` and source timestamp. For a
sealed evaluation run, use the latest eligible revision known at its declared
cutoff; a later correction produces a new result revision rather than mutating
history.

Overwriting labels in place is not selected because prior reports lose their
audit trail. Ignoring corrections is not selected because known ground-truth
errors would permanently bias performance evidence.

### 8. Duplicate policy: deterministic deduplication and explicit quarantine

Deduplicate exact repeated prediction or label deliveries by their immutable
source/event identities and payload checksum. Conflicting duplicates are
quarantined and counted as `conflicting_records`, not selected arbitrarily.

Counting every delivery is not selected because retries inflate samples and
metrics. Choosing the first conflicting label silently is not selected because
it hides upstream data-quality failures.

### 9. Evaluation unit: one scored prediction per entity and horizon

Evaluate one immutable scored prediction per `entity_key`, model version, and
prediction horizon. If multiple eligible scores exist, select the latest score
before the horizon starts using a deterministic documented rule and report
superseded counts.

Counting all repeated scores as independent samples is not selected because it
overweights repeatedly contacted customers. Collapsing all customer history
forever is not selected because it would conceal legitimate future decisions.

### 10. Model and policy lineage: evaluate by immutable served version

Group results by immutable model-bundle checksum, release ID, schema version,
threshold version, risk-policy version, and label-definition version. Never
combine versions into one performance metric without an explicit comparison
report.

Using a mutable champion alias is not selected because it cannot reconstruct
the serving decision. Re-scoring rows with the current model is not selected
because it would measure a model that did not make the historical prediction.

### 11. Window strategy: non-overlapping monthly prediction cohorts

Evaluate mature predictions in immutable, non-overlapping UTC calendar-month
cohorts. Publish results only after all rows in the cohort pass maturity and
grace rules; an implementation may also provide a rolling three-cohort view as
a clearly derived aggregate.

Daily performance windows are not selected because delayed labels and expected
volume make them too noisy. An unbounded cumulative metric is not selected
because it masks recent degradation.

### 12. Coverage: publish eligible-label coverage and reconciliation counts

Every result must include eligible prediction count, joined mature-label count,
coverage ratio, unmatched predictions, unmatched labels, duplicates, and
quarantined conflicts. Coverage is a condition of interpretation, not merely
debug metadata.

Reporting only matched samples is not selected because selection bias becomes
invisible. Treating unmatched predictions as non-churn is not selected because
it creates artificial performance.

### 13. Minimum evidence: 500 mature joined labels and 80% coverage

Require at least 500 mature joined labels and 80% label coverage for a
run-level performance status. Below either condition, retain descriptive counts
but return `insufficient_data`; zero mature labels returns `not_available`.

The M14 sample rule alone is not selected because labels can be selectively
missing. A much higher universal threshold is not selected because it would
unnecessarily delay feedback for valid monthly cohorts.

### 14. Primary discrimination metric: PR-AUC

Use PR-AUC as the primary score-ranking metric because churn is normally an
imbalanced positive class. Compute it from the probability produced at serving
time, never a later rescore.

ROC-AUC alone is not selected because it can appear strong under severe class
imbalance. Accuracy is not selected because it can reward an always-retain
classifier when churn is uncommon.

### 15. Supporting metrics: ROC-AUC, threshold metrics, and confusion matrix

Report ROC-AUC plus precision, recall, F1, decision rate, and a confusion
matrix at the served immutable threshold. These are supporting diagnostics and
must display the threshold/version used.

One composite score is not selected because it conceals precision-recall
trade-offs. Re-optimising the threshold inside monitoring is not selected
because monitoring should assess the deployed decision policy, not rewrite it.

### 16. Calibration: reliability curve, Brier score, and fixed probability bins

Evaluate calibration using fixed versioned probability bins, calibration table,
reliability curve data, and Brier score. Suppress bins below the configured
minimum group size while preserving aggregate coverage/count metadata.

Calibration plots without counts are not selected because they exaggerate
small-sample noise. Adaptive bins per report are not selected because trends
cannot be compared consistently across cohorts.

### 17. Performance status: evidence states before decay severity

Use `not_available` for no mature labels, `insufficient_data` for failed sample
or coverage eligibility, and `unknown` for processing failure. `stable`,
`watch`, `warning`, and `critical` are reserved for M17's calibrated
performance-decay policy after a future baseline/comparator is approved.

Calling inadequate evidence `stable` is not selected because it is misleading.
Setting decay thresholds in M16 is not selected because M17 owns alert
calibration and no delayed-label distribution is available yet.

### 18. Data-origin labelling: never conflate evidence sources

Require one of `offline_test`, `replayed`, `synthetic`, or `production` on
every report and artifact. `production` is permitted only after the actual
authoritative delayed-label feed and contract mapping pass validation.

Labelling all delayed labels as production is not selected because a replay can
look operational while lacking production collection guarantees. Omitting an
origin is not selected because readers could mistake fixture performance for
live model performance.

### 19. Privacy and retention: minimised join record, 30-day event linkage

Keep only pseudonymous keys, event/label identities, timestamps, versions,
probability, decision, outcome, and audit hashes needed for the join. Retain
row-level join linkage for 30 days after evaluation, then retain approved
aggregate/audit results according to the M12 13-month aggregate policy.

Keeping raw customer features or labels indefinitely is not selected because
it expands privacy risk without being needed for aggregate performance. Deleting
all linkage immediately is not selected because reconciliation and correction
are impossible.

### 20. Reproducibility: idempotent immutable result revisions

Make ingestion, join, and evaluation idempotent using source identities,
checksums, configuration version, input snapshot checksum, and evaluation-run
ID. A rerun with identical inputs produces the same result; changed labels or
configuration create a new immutable revision linked to the prior result.

Mutable in-place reports are not selected because historical performance claims
cannot be audited. Job-run timestamps alone are not selected because they do
not identify the exact prediction and label populations used.

## Consequences

- M16 can implement and test its framework now with synthetic/replayed data,
  but cannot claim live performance until the delayed-label package is supplied
  and mapped to this contract.
- M12 must expose a protected per-prediction join export; aggregate telemetry
  by itself cannot support a reliable delayed-label join.
- M17 may consume M16 evidence only after it has a calibrated decay policy;
  M16 does not automatically recommend retraining or promote a model.

## References

- ADR-0008 (M12 telemetry and prediction-metadata policy).
- ADR-0011 (M15 statistical-monitoring calibration policy).
- `MLOPS_IMPLEMENTATION_PLAN.md`, M16.
- `MLOPS_END_TO_END_DESIGN.md`, sections 15--17.
