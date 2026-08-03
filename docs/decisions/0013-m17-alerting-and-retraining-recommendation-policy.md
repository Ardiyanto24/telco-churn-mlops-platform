# ADR-0013: Adopt M17 alerting and retraining-recommendation policy v1

## Status

Accepted

## Date

2026-08-03

## Context

M14 and M15 produce data-quality and drift evidence, while M16 produces
delayed-label performance evidence. Those outputs are deliberately not alerts:
they may be provisional, insufficient, or caused by an operational failure.
M17 must turn qualified evidence into an auditable operator workflow without
allowing a monitoring signal to overwrite the deployed production model.

The M15 baseline/configuration remains a candidate, and M16 has no validated
production delayed-label source. Therefore M17 must support synthetic/replayed
exercise now, keep production delivery fail-closed, and preserve enough context
for a future operator to distinguish an alert from an approved model action.

## Decision

M17 adopts the following twenty decisions.

### 1. Alert taxonomy: four non-overlapping domains

Create one alert domain per primary cause: `operational`, `data_quality`,
`drift`, and `performance`. A monitoring-job failure is operational even when
the affected job normally calculates drift or performance.

A single catch-all model-health alert is not selected because it hides the
first responder and corrective action. Creating an alert for every metric line
is not selected because it would turn one incident into alert noise.

### 2. Severity vocabulary: warning and critical, with evidence states outside alerts

Use alert severities `warning` and `critical`; retain `not_available`,
`insufficient_data`, `unknown`, and `stable` as monitoring evidence states,
not alert severities. An alert must have an actionable reason at or above
warning.

Mapping every non-stable status to an alert is not selected because lack of
evidence is not an incident. Adding an `info` alert severity is not selected
because reports/logs already carry low-priority context without requiring
operator acknowledgement.

### 3. Critical triggers: operational failure, severe quality break, or calibrated performance decay

Allow `critical` only for a failed required monitoring job, a critical
data-quality/contract signal, or a calibrated critical M16 performance-decay
result with mature labels. Drift effect size alone cannot be critical without
the M15-approved policy and persistence evidence.

Making every warning critical is not selected because it destroys triage
priority. Treating a single uncalibrated drift result as critical is not
selected because drift is a hypothesis, not proof that the model is failing.

### 4. Monitoring status and alert state: separate contracts

Preserve the source monitoring status unchanged and create an alert only when
the M17 policy qualifies it. Alert lifecycle state is separate from severity,
so an acknowledged critical issue remains critical until resolved.

Overwriting a source result with alert state is not selected because it loses
statistical evidence. Closing an alert merely because an operator acknowledged
it is not selected because acknowledgement is not remediation.

### 5. Drift/data-quality persistence: two consecutive complete windows

Open a warning-or-higher drift or non-critical data-quality alert only when the
same deduplication key qualifies in two consecutive complete windows. This
implements the M15 candidate persistence decision and is configurable by an
immutable M17 policy version.

One-window alerts are not selected because isolated batch noise creates alert
fatigue. Requiring more than two daily windows is not selected because it
delays investigation of a sustained issue.

### 6. Immediate exception: critical quality and operational alerts bypass persistence

Open a critical contract/data-quality failure and a required-job operational
failure immediately, with the persistence count recorded as one. These events
can invalidate downstream monitoring or make the system blind.

Forcing them to wait for a second window is not selected because the operator
would lose a day of visibility. Treating ordinary warning-quality movement the
same way is not selected because it would reintroduce noise.

### 7. Deduplication identity: domain, signal, feature, lineage, and window family

Deduplicate by alert domain, signal/feature, model version, baseline ID,
monitoring/performance config version, and contiguous window family. The key
is content-addressed and stored with every alert revision.

Deduplicating only by message text is not selected because wording changes are
not identity. Deduplicating across model or baseline versions is not selected
because those are distinct investigations.

### 8. Debounce: one open alert per key, 24-hour repeat suppression

While an alert is open, append new qualifying windows as evidence instead of
creating a new alert. Suppress duplicate delivery attempts for 24 hours unless
severity escalates; record each suppression decision.

Sending every batch result is not selected because it spams responders.
Suppressing indefinitely is not selected because an unresolved issue still
needs periodic visibility.

### 9. Escalation: warning becomes critical only through policy-qualified evidence

Escalate an open warning when a source result reaches a critical condition or
when a configured persistence/escalation threshold is met; never downgrade
severity automatically while the alert is open. The evidence that triggered
the escalation is immutable.

Escalating merely by elapsed time is not selected because age alone does not
prove increased business risk. Automatically lowering severity on one clean
window is not selected because it hides an unresolved intermittent failure.

### 10. State machine: open, acknowledged, resolved, and suppressed

Use `open` as the default, `acknowledged` when an authorised actor accepts
ownership, `resolved` after evidence-based closure, and `suppressed` only for
a documented temporary maintenance/silencing rule with expiry.

A boolean `resolved` flag is not selected because ownership and suppression
would be indistinguishable. Permanent suppression is not selected because it
silently disables a safety control.

### 11. Resolution: two clean complete windows or documented manual remediation

Automatically resolve persistence-based alerts only after two complete clean
windows for the same key. An authorised operator may resolve earlier only with
a remediation note, actor, timestamp, and linked evidence; a future qualifying
window opens a new revision.

Resolving after one clean window is not selected because intermittent issues
flap. Requiring manual resolution for every normal recovery is not selected
because it creates stale-alert backlog.

### 12. Ownership: internal ML/operations role with immutable actor metadata

Require an internal authorised ML Engineer or operations role to acknowledge,
resolve, or suppress an alert. Store actor ID, action time, action reason, and
the policy version; future M18 storage/authentication enforces the role.

Anonymous acknowledgement is not selected because accountability disappears.
Allowing the model service to resolve its own alerts is not selected because it
creates a conflict between inference availability and oversight.

### 13. Minimum alert context: reproduce the incident without raw customer data

Each alert records reason, domain, severity, source result ID, window, sample
and coverage, model/baseline/config lineage, source origin, persistence count,
and links to aggregate reports. It excludes raw features, labels, entity keys,
payloads, secrets, and stack traces.

A human-only prose message is not selected because it cannot be queried or
reproduced. Attaching raw monitoring records is not selected because alerting
does not justify expanding the privacy boundary.

### 14. Delivery: durable internal report/output first, no external notification by default

Write versioned alert records and aggregate Markdown reports to the internal
output boundary first. External email, chat, webhook, paging, and public
delivery remain disabled until M18/M20 provide a durable store, recipient
ownership, authentication, and secret management.

Hard-coding a personal webhook or email is not selected because it couples a
portfolio system to ungoverned credentials. No delivery record at all is not
selected because operators need an auditable queue even in local mode.

### 15. Delivery failures: bounded retry and operational alert, never inference failure

Delivery is asynchronous/bounded; failure records an operational alert or
safe local fallback and retries with a finite policy outside inference. It
must not recursively notify through the failed transport.

Making alert delivery synchronous is not selected because an alerting outage
could affect predictions. Unlimited retries are not selected because they can
exhaust resources and create duplicate notifications.

### 16. Idempotency and revisioning: immutable event-derived alert records

An identical source event and M17 policy produce the same alert identity and
reuse the prior record. Additional evidence, escalation, acknowledgement,
resolution, or suppression creates an append-only revision linked to the
original identity.

Mutable alert rows are not selected because audit history would be lost.
Creating a new alert for every retry is not selected because retry behavior
would become indistinguishable from new incidents.

### 17. Retraining recommendation: evidence-based candidate, not a command

Create a `retraining_recommendation` only for calibrated critical performance
decay with mature labels, or persistent Tier-1 drift/data-quality evidence
after data validation confirms the source is legitimate and enough new data is
available. It is a candidate investigation record, never a training job or
promotion command.

Recommending retraining for every drift alert is not selected because drift
may reflect a correct model under a changed population. Auto-starting training
is not selected because data quality, labels, and business definition may need
human review first.

### 18. Recommendation evidence: explicit alternatives and gates

Require the triggering alert/revisions, source-result lineage, data-origin,
coverage/sample, proposed training data window, expected objective, and the
next M5--M8 validation steps. The record must explicitly say that M8 gates,
registry lifecycle, M11 staging, and production approval remain required.

A short "retrain now" message is not selected because it cannot be audited or
acted on safely. Treating a recommendation as approval is not selected because
it bypasses independent evaluation and deployment controls.

### 19. Automation boundary: no automatic retraining, promotion, rollback, or threshold change

M17 may open alerts and write candidate recommendations, but it cannot retrain,
alter a production threshold, promote a candidate, or roll back a deployment.
Those actions retain their M6--M8 and M11 approvals/runbooks.

End-to-end automation is not selected because the present signals are
candidate/replayed and can be wrong. A purely manual, undocumented workflow
is not selected because the structured recommendation still shortens and
standardises investigation.

### 20. Retention and modes: 13-month aggregate audit, candidate mode fail-closed

Retain aggregate alert/recommendation/audit history for 13 months under the
M12 aggregate policy, while row-level join linkage follows M16's 30-day rule.
The initial M17 policy runs in `candidate` mode: it accepts synthetic/replayed
evidence but blocks production notification and operational action until M15
and M16 production prerequisites are approved.

Indefinite raw retention is not selected because it increases privacy risk.
Treating candidate evidence as production is not selected because it would
misrepresent the current state of the system.

## Consequences

- M17 gives operators a reproducible incident/recommendation workflow while
  preserving the separation between monitoring, training, promotion, and
  deployment.
- The first implementation can be exercised with replay/synthetic fixtures;
  its output must remain candidate until approved M15/M16 evidence exists.
- M18 can later persist and visualise these same immutable records without
  changing their privacy or lineage contract.

## References

- ADR-0008 (M12 telemetry and prediction-metadata policy).
- ADR-0011 (M15 statistical-monitoring calibration policy).
- ADR-0012 (M16 delayed-label performance-monitoring policy).
- `MLOPS_IMPLEMENTATION_PLAN.md`, M17.
- `MLOPS_END_TO_END_DESIGN.md`, sections 15--17.
