# ADR-0008: Adopt M12 telemetry and prediction-metadata policy v1

## Status

Accepted

## Date

2026-08-02

## Context

M2 provides a versioned prediction API and M11 provides an auditable,
production-simulated release boundary. M12 must create the minimum trustworthy
operational evidence for monitoring without turning request logs into an
uncontrolled customer-data store. The resulting telemetry is an internal input
to M14 drift monitoring, M16 delayed-label performance monitoring, and M18
internal metrics visibility; it is not a public analytics API.

There is no approved hosted observability vendor, customer-data retention
agreement, authenticated public ingress, or production traffic volume yet.

## Decision

M12 adopts the following twenty decisions.

### 1. Log format: versioned JSON Lines on stdout

Emit one structured JSON object per event to stdout, with an explicit
`telemetry_schema_version`. Container runtimes already collect stdout reliably,
and JSON Lines is simple to parse locally now and by a future collector.

Free-form text logs are not selected because field extraction is fragile and
cannot be validated as a contract. Sending directly to a hosted vendor is not
selected because no vendor, credentials, retention agreement, or network
authority has been approved.

### 2. Event taxonomy: separate request, prediction, error, and telemetry-failure events

Use stable event names `request_completed`, `prediction_completed`,
`request_failed`, and `telemetry_write_failed`. Each event has common identity
and lineage fields plus event-specific fields.

One catch-all event is not selected because it makes dashboards and failure
ownership ambiguous. A log line for every internal function is not selected
because it increases volume and the risk of accidentally serialising customer
data without improving service-health monitoring.

### 3. Correlation standard: W3C trace context when supplied, UUID request ID otherwise

Accept a syntactically valid W3C `traceparent` as correlation context and
generate a UUID4 `request_id` for every request. The API response and every
event carry that request ID; trace integration can later add spans without
changing the event contract.

An application-specific header alone is not selected because it does not
interoperate with standard proxies and tracing tools. Reusing a caller value
without validation is not selected because malformed or attacker-controlled
values could poison logs and correlation searches.

### 4. Request-ID lifecycle: create once at ingress and preserve it on errors

Create the request ID in middleware before validation, then attach it to the
request context, success response, error response, and all telemetry events.

Generating independent IDs in success and error handlers is not selected
because one failed request becomes impossible to follow. Returning no request
ID to callers is not selected because support cannot correlate a reported API
failure with internal evidence.

### 5. Common event envelope: UTC timestamp, service identity, and outcome

Every event records UTC RFC 3339 timestamp, event name, schema version,
request ID, optional trace ID, service name/environment, outcome, and release
identity when available. These fields are metadata, not customer content.

Ad-hoc field sets per event are not selected because downstream monitoring
would require brittle special cases. Local-time timestamps are not selected
because cross-runner comparisons and incident timelines become ambiguous.

### 6. Prediction metadata: record decision evidence, not the response payload

For each prediction request, record model version, schema version, release ID,
decision threshold/risk-policy version, batch size, latency, HTTP outcome, and
aggregated prediction/risk-band counts. Do not log response objects, row-level
probabilities, or feature payloads.

Storing the complete API response is not selected because it duplicates
customer-derived information with little monitoring benefit. Recording only
model version is not selected because it cannot explain latency, failed calls,
or changing prediction distributions.

### 7. Monitoring observations: allowlisted, derived feature values only

Where M14 needs current distributions, emit only an allowlisted set of
normalised monitoring observations: missing/unknown indicators, categorical
codes, and pre-defined numeric bins. The raw request body is never serialised,
and the allowlist is versioned with the telemetry schema.

No feature observations are not selected because M14 could not calculate data
quality or feature drift. Recording every raw input field is not selected
because the combination can be identifying and violates the minimisation goal.

### 8. Pseudonymous entity key: keyed HMAC-SHA-256, optional by design

Use an HMAC-SHA-256 of a trusted opaque entity reference, with a `key_id`, when
an approved internal ingress supplies one. The raw reference is discarded; when
none is supplied, `entity_key` is absent rather than invented from request
content.

An unsalted hash is not selected because small or predictable identifier spaces
are susceptible to dictionary attacks. Deriving an entity key from customer
features is not selected because it is unstable, privacy-invasive, and can
silently join unrelated people.

### 9. Entity-key scope and rotation: stable join within a controlled key epoch

Keep the HMAC key stable for the approved delayed-label join period and record
only its non-secret `key_id`. Rotation creates a new key epoch; any cross-epoch
join requires an explicit, access-controlled migration rather than dual-writing
raw identifiers.

Per-request random keys are not selected because M16 could not join outcomes.
Indefinitely reusing one undocumented key is not selected because it prevents
key rotation and turns a pseudonym into a permanent identifier.

### 10. Model lineage: bind events to the deployed immutable release

Record model version, schema version, bundle-manifest checksum, and M11 release
ID/image digest where the deployment manifest supplies them. A startup check
must make these fields available before the service is ready.

A mutable model alias is not selected because it cannot reconstruct what served
an event. Version-only lineage is not selected because two bundles or images
can share a human-readable model version while differing in content.

### 11. Error taxonomy: stable, low-cardinality error codes

Use an allowlisted code family for validation, unsupported media, model-load,
inference, timeout, internal-service, and telemetry-write failures. The client
safe error response and event code use the same stable classification; detailed
exception text stays out of normal telemetry.

Raw exception messages are not selected because they may contain input,
filesystem, or dependency detail and create unbounded cardinality. HTTP status
alone is not selected because distinct operational causes can share one status.

### 12. Latency measurement: monotonic end-to-end and inference durations

Measure `request_latency_ms` with a monotonic clock from ingress to response,
and separately measure `inference_latency_ms`. Event timestamps remain UTC wall
clock values for correlation only.

Wall-clock duration is not selected because clock adjustments can produce
negative or distorted latency. Inference-only latency is not selected because
validation, serialisation, and telemetry overhead also affect API users.

### 13. Batch semantics: aggregate outcomes per API request

Emit one prediction event per API request with `batch_size` and aggregate
counts by churn decision/risk band. Event volume therefore scales with requests,
not rows, while still supporting prediction-distribution monitoring.

One event per customer row is not selected because it increases privacy exposure
and log cost. Omitting batch size is not selected because a slow batch and a
slow single prediction have materially different diagnoses.

### 14. Metrics instrumentation: in-process Prometheus/OpenMetrics, private by default

Instrument request totals, failures, latency histograms, prediction batch size,
and telemetry-write failures using an OpenMetrics-compatible in-process
registry. Any `/metrics` endpoint is bound to private/local infrastructure
until M18/M20 define storage, authentication, and external exposure.

Logs-only instrumentation is not selected because counters and histograms are
expensive and error-prone to reconstruct from logs. A public metrics endpoint is
not selected because it exposes operational information before access controls
are designed.

### 15. Logging failure policy: best effort with a bounded non-blocking path

Inference and its HTTP response complete independently of telemetry delivery.
The service uses a bounded non-blocking queue or equivalent guarded emitter;
on saturation or write failure it increments a local failure metric and emits a
minimal safe fallback event when possible.

Making telemetry synchronous and mandatory is not selected because an
observability outage would become a prediction outage. An unbounded queue is
not selected because a failed sink could exhaust service memory.

### 16. Failure containment: no recursive logging and no request-path retries

Telemetry-emitter exceptions are caught at the boundary, classified once, and
never recursively re-emitted through the failing emitter. Do not retry writes
on the prediction request path; later asynchronous transport may have its own
bounded retry policy.

Recursive error logging is not selected because it can create a log storm.
Blocking retries are not selected because they inflate tail latency and can
still fail after holding request resources.

### 17. Sampling: retain all errors and use configurable success sampling only when needed

Record every failure and every aggregate metric update. Successful prediction
events are unsampled at current portfolio-scale traffic, with a documented
deterministic/configurable sampling control reserved for higher volume.

Sampling all events from day one is not selected because M12 needs complete
baseline evidence and traffic is not yet large. Never sampling is not selected
as a permanent rule because future high-volume serving could create avoidable
cost and telemetry load.

### 18. Retention and minimisation: short event retention, longer aggregates

Set the policy draft to retain sanitised event-level telemetry for 30 days and
aggregated, non-entity metrics for up to 13 months. Actual storage enforcement
is implemented only when an approved sink exists; local development logs remain
ephemeral and must not be committed.

Indefinite event retention is not selected because pseudonymous data still has
privacy and breach value. Deleting all evidence immediately is not selected
because it prevents incident investigation and delayed monitoring runs.

### 19. Access and audit: internal least-privilege access with redaction tests

Telemetry is an internal operational dataset. Access is limited to approved ML
Engineering/operations roles in a future sink, and CI redaction tests must
prove that secrets, raw payloads, and original customer identifiers are absent.

Making telemetry public is not selected because it reveals operational and
potentially customer-derived information. Relying on reviewer inspection alone
is not selected because privacy regressions need automated prevention.

### 20. Compatibility and completion: schema validation plus failure-mode evidence

Version telemetry schemas and validate them in unit/API tests. M12 is complete
only when successful and failed requests produce parseable correlated events,
lineage is present, PII-redaction tests pass, and induced sink failure leaves
prediction available while making failure visible in metrics/events.

Treating a printed JSON line as sufficient is not selected because it does not
prove correlation, redaction, lineage, or non-blocking failure behaviour.
Deferring all validation to M14/M18 is not selected because downstream systems
cannot safely repair an unstable telemetry contract.

## Consequences

- M12 establishes a privacy-minimised event contract that M14, M16, and M18 can
  consume without receiving raw API payloads.
- The serving path remains available when the telemetry path degrades, while
  the degradation itself becomes measurable.
- A later collector, trace backend, authenticated entity ingress, or retention
  change requires an ADR addendum and must preserve the schema, minimisation,
  and immutable-release lineage invariants.

## References

- https://www.w3.org/TR/trace-context/
- https://opentelemetry.io/docs/specs/otel/logs/data-model/
- https://prometheus.io/docs/instrumenting/exposition_formats/
- https://csrc.nist.gov/pubs/sp/800/122/final
