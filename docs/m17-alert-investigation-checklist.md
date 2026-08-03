# M17 Alert Investigation Checklist

Use this checklist for an aggregate M17 alert. Do not attach raw customer
payloads, entity keys, labels, credentials, or stack traces to this record.

## 1. Establish the evidence

- Confirm alert ID, domain, severity, source-result ID, policy/config version,
  model version, baseline ID, source origin, window, sample size, and coverage.
- Confirm whether the alert is candidate/replay/synthetic evidence or approved
  production evidence.
- Acknowledge only after an authorised ML/operations actor owns the next step.

## 2. Route by domain

### Operational

- Check job/runtime failure classification and safe logs.
- Restore the monitoring job first; do not describe missing monitoring as
  stable model behavior.

### Data quality

- Check contract, missing/unknown/out-of-range evidence and upstream schema.
- Resolve the data issue or document the legitimate business/schema change.

### Drift

- Verify persistence across complete windows and data-source legitimacy.
- Compare affected Tier-1 features with the approved baseline/configuration.
- Do not infer model failure from drift alone.

### Performance

- Confirm label maturity, coverage, source origin, model/threshold lineage,
  and calibration/ranking evidence.
- Treat a retraining recommendation as an investigation input, not approval.

## 3. Decide and record

- Record acknowledgement, remediation, resolution/suppression reason, actor,
  and UTC timestamp in the append-only alert history.
- For a retraining candidate, follow M5--M8 validation and M11 staging/
  approval. Never promote directly from an M17 recommendation.
- Resolve persistence-based alerts only after two clean complete windows, unless
  an authorised actor records verified manual remediation.
