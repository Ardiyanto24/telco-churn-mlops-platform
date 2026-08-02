# M12 Structured Telemetry and Prediction Metadata Log

## Context dan assumptions

- M12 implements the internal telemetry boundary defined by ADR-0008. It does
  not create a hosted collector, a public metrics endpoint, or a customer-data
  store.
- Existing M2 request and response bodies contain customer identifiers. They
  remain necessary to the prediction API contract but are deliberately excluded
  from telemetry events.

## Plan dan actions

- Added `telco_churn.telemetry` with versioned JSON Lines event emission,
  bounded asynchronous delivery, an in-process metrics registry, derived
  allowlisted monitoring observations, and HMAC entity-key helper.
- Added ingress middleware that creates one request ID, captures valid W3C
  trace context, measures monotonic latency, and preserves correlation in
  success and error responses.
- Emitted prediction metadata with model/schema version, request and inference
  latency, batch size, risk counts, and aggregate monitoring observations.
- Added telemetry tests to the API test category.

## Evidence dan findings

- The HMAC and latency-histogram unit tests pass with the bundled Python.
- `docker run ... telco-churn-m8-runtime:local -m unittest
  tests.test_telemetry tests.test_prediction_api -v` passed 16 tests.
- The focused Docker suite covered parseable success and failure events,
  request/response correlation, W3C trace propagation, PII/payload
  minimisation, HMAC stability, histogram rendering, and a deliberately
  failing telemetry sink that did not fail inference.

## Errors dan handling

- The initial host run skipped FastAPI tests because the host runtime does not
  contain the locked M2 dependencies. The same tests were run in the M8 locked
  runtime container instead.
- A trace-context test initially failed because the middleware generated a
  request ID but did not parse `traceparent`. A narrow parser and regression
  test were added; the focused suite then passed.
- Review found that a sink failure incremented a metric but did not produce the
  promised fallback event. A terminal stderr fallback now emits a sanitised
  `telemetry_write_failed` event and is covered by a regression test.

## Decisions dan deviations

- The metrics registry exposes OpenMetrics-compatible text in-process, but no
  HTTP metrics route was added. This follows ADR-0008: metrics remain private
  until M18/M20 define storage and access control.
- Monitoring observations use an allowlisted categorical subset and fixed
  numeric bins. Raw request bodies, customer IDs, predictions, exception text,
  secrets, and entity references are never serialised.

## Risks, limitations, dan follow-up

- The HMAC helper awaits a future approved internal ingress and secret source;
  no untrusted public header is accepted as an entity identifier in M12.
- Queue saturation and sink failure are visible through counters, but a hosted
  collector, retention enforcement, alerting, and dashboard belong to later
  milestones.

## Trace references

- ADR-0008.
- `src/telco_churn/telemetry.py`, `src/telco_churn/api/app.py`, and
  `tests/test_telemetry.py`.
- Commits: `2f8b7ec`, `2995f40`, `f69cc0e`, `f139ce5` plus the final fallback
  feature/test and documentation commits.
