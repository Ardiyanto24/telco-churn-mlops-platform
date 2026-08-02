# Milestone M12 Completion Report

Status: done
Tanggal: 2026-08-02

## Deliverable

- Versioned structured JSON Lines telemetry for request, prediction, error, and
  telemetry-write failure domains.
- One ingress request ID and optional valid W3C trace correlation across API
  response and telemetry.
- Privacy-minimised prediction metadata, aggregate monitoring observations,
  HMAC pseudonymisation helper, and in-process OpenMetrics-compatible metrics.
- Bounded asynchronous emitter whose sink failure cannot fail inference.

## Test evidence

- `python -m unittest tests.test_telemetry.TelemetryUnitTests -v`: 3 pass.
- `docker run ... telco-churn-m8-runtime:local -m unittest
  tests.test_telemetry tests.test_prediction_api -v`: 16 pass.

## Exit criteria

- [x] Telemetry records service status, latency, batch volume, model/schema
  lineage, prediction aggregates, and derived current-distribution inputs.
- [x] Pseudonymisation method and key-rotation boundary are documented in
  ADR-0008.
- [x] Event-level 30-day and aggregate 13-month retention policy is documented
  in ADR-0008; no local telemetry is committed.
- [x] Sink failures and queue saturation are measurable and do not make
  inference unavailable.

## Decisions made

- ADR-0008.

## Known limitations

- Metrics have no public HTTP endpoint and telemetry has no hosted sink. This
  is intentional until M18/M20 define storage, authentication, and exposure.
- Entity-key generation is available only for a future trusted internal ingress
  with an approved HMAC secret; it does not accept raw customer identifiers.

## Handoff

- M13 can create an immutable reference baseline using the versioned monitoring
  observations. M14 can then resolve current windows from M12 telemetry.
