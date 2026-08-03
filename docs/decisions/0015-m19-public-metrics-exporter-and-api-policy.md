# ADR-0015: Adopt M19 public metrics exporter and API policy v1

## Status

Accepted

## Date

2026-08-03

## Context

M18 provides a private, aggregate metrics-store boundary for telemetry,
monitoring, delayed-label performance, alerts, and recommendations. The public
web is a separate repository and must not hold an internal token, inspect an
internal dashboard, or query the M18 database. M19 therefore needs a stable,
read-only contract that is useful for a portfolio dashboard while preserving
privacy and accurately communicating candidate, replayed, synthetic, missing,
or stale evidence.

The project remains candidate mode: the M15 baseline is not approved and M16
has no supplied production delayed labels. M19 must not turn those limits into
an implied production-health claim.

## Decision

M19 adopts the following twenty decisions.

### 1. Public source boundary: versioned snapshots only

Serve public data only from a completed, sanitised public snapshot produced by
a dedicated exporter. The public API receives a read-only snapshot repository
or view, never arbitrary M18 tables or live monitoring reports.

Direct public queries to the internal store are not selected because a new
internal field could become public accidentally. Copying values manually into
the web is not selected because it cannot be reproduced, audited, or retried.

### 2. Public allowlist: coarse model, service, monitoring, and methodology metadata

Allow only: schema version; generated and observed-window timestamps; bounded
model/deployment display identifiers; aggregate counts; aggregate service and
monitoring statuses; approved aggregate metric values; freshness; data origin;
evidence state; and short methodology/version references. Export no free-form
internal diagnostic text.

An allow-all-with-denylist policy is not selected because new source fields
would be public by default. A headline-only API is not selected because a web
user needs window, sample, origin, and freshness to interpret a metric safely.

### 3. Absolute exclusion: no customer-level, secret, or internal-operational fields

Reject identifiers, quasi-identifiers, raw features, prediction or label rows,
request metadata, IP addresses, internal URIs, database keys, source paths,
tokens, exception details, stack traces, and arbitrary payloads before a
snapshot can be published.

Hashing identifiers is not selected because stable hashes remain linkable.
Relying on a frontend to hide sensitive fields is not selected because data
already delivered to a browser is public.

### 4. Aggregation threshold: suppress groups below 100 observations

Publish a segmented or distribution value only when its contributing group has
at least 100 observations. Represent smaller groups as `suppressed` with a
reason and no value, bin, category, or count that could disclose the group.

A threshold of one or ten is not selected because it offers weak protection
against inference and unstable rates. A much higher default such as 1,000 is
not selected because the current portfolio data would hide most useful
aggregate evidence; the threshold can be raised by a future privacy review.

### 5. Aggregation grain: no public customer cohorts or high-cardinality slices

Publish only whole-service/model-window aggregates and a small, fixed set of
approved low-risk metric dimensions. Do not expose geography, tenure, contract,
payment, demographic, or other customer-derived cohort breakdowns in v1.

Arbitrary dashboard filters are not selected because combinations can defeat a
minimum group threshold. Rich cohort analytics are not selected because M19 is
a public model-observability contract, not a customer analytics product.

### 6. Data provenance: controlled origin labels are mandatory

Every snapshot result carries one of `production`, `replayed`, `synthetic`, or
`offline_test`, and public presentation must expose it. Candidate configuration
and evidence limitations remain visible in methodology metadata.

Omitting origin is not selected because replayed evidence could be mistaken for
live production monitoring. Free-text origin is not selected because clients
could not reliably render or filter it.

### 7. Evidence states: preserve absence, insufficiency, and failure

Expose controlled states including `stable`, `drift_detected`, `warning`,
`critical`, `unknown`, `insufficient_data`, `not_available`, `suppressed`, and
`stale` as applicable. `stable` is valid only when the source policy qualified
the completed result.

Mapping absent or failed monitoring to stable is not selected because it makes
an outage appear healthy. Exposing only a Boolean health flag is not selected
because the public web must distinguish insufficient labels from a failed job.

### 8. Schema contract: JSON Schema-backed public snapshot v1

Define a strict JSON Schema with `schema_version: public_metrics/v1`, required
top-level metadata, and endpoint-shaped resources. Publish a static contract
fixture and an example payload for the separate web repository.

An undocumented JSON response is not selected because frontend changes would
depend on implementation details. A generic internal M18 record schema is not
selected because it has a different privacy and lifecycle contract.

### 9. Compatibility: additive changes within v1; breaking changes require v2

Within `/public/v1`, add optional fields only and retain semantics of existing
fields. Remove, rename, or change a field's meaning only through `/public/v2`,
with the prior version supported for at least one public release cycle.

Silent breaking edits are not selected because the separate web deploys
independently. Versioning every additive field is not selected because it
creates unnecessary client and operational complexity.

### 10. Export cadence: publish after valid source updates with a daily safety run

Run the exporter after a successfully ingested eligible M18 result and on a
daily scheduled safety run. It is idempotent for unchanged source identities
and does not create a new snapshot solely because a retry occurred.

Exporting only on manual request is not selected because freshness becomes
operator-dependent. Publishing on every prediction is not selected because
M18 deliberately operates on aggregate windows and serving must stay isolated.

### 11. Atomic publication: validate first, then commit one immutable snapshot

Construct and validate the entire snapshot in memory or a staging record,
calculate a content hash and source lineage, then atomically mark it current.
The API serves either the prior complete snapshot or the next complete one.

In-place partial updates are not selected because endpoint resources could show
different calculation moments. Replacing the current snapshot before schema
and sanitisation validation is not selected because a bad export could remove
the last trustworthy public evidence.

### 12. Failure handling: retain the last valid snapshot and mark it stale

If export, sanitisation, or schema validation fails, keep the most recent
valid snapshot readable, compute freshness from its generation time, and
return a visible `stale` state and safe failure reason class. Do not publish an
empty replacement snapshot.

Returning a fresh-looking empty response is not selected because it masks data
failure. Returning internal exception messages is not selected because they
may disclose system details.

### 13. Freshness: 24-hour target with explicit stale transition

Treat a snapshot as `fresh` through 24 hours after generation, `late` through
48 hours, and `stale` thereafter; always include `generated_at` and latest
observed window. The API must not infer health from a cached timestamp alone.

No freshness threshold is not selected because clients cannot distinguish a
current daily export from an abandoned demo. A short hourly target is not
selected because the monitoring inputs are aggregate and can be daily.

### 14. API surface: fixed read-only GET endpoints under `/public/v1`

Expose `overview`, `models/current`, `models/history`, `monitoring/history`,
`service/history`, and `methodology` as bounded GET-only resources. Requests
accept only documented pagination and time-range parameters; no query language
or write route is present.

A single unstructured mega-endpoint is not selected because it prevents useful
caching and client evolution. POST-based public querying is not selected
because M19 has no public write or arbitrary-query use case.

### 15. Caching: public cache headers and ETags tied to immutable snapshot hashes

Return `ETag` derived from the immutable snapshot hash, support conditional
GET, and use `Cache-Control: public, max-age=300, stale-while-revalidate=600`.
Responses also include their snapshot ID and freshness so caching never hides
their evidence age.

No cache is not selected because static public dashboard traffic would cause
unnecessary database reads. Long opaque caching is not selected because it
would keep stale evidence invisible after a new snapshot is published.

### 16. CORS: explicit configured public-web origins, never production wildcard

Allow only configured HTTPS origins for the public web and localhost development
origins; allow GET, HEAD, and OPTIONS with no credentials. The allowed-origin
list is deployment configuration, not browser-supplied input.

`*` in production is not selected because it permits any site to consume the
API and complicates abuse control. Credentialed cross-origin requests are not
selected because the v1 public API deliberately needs no browser secret.

### 17. Abuse control: application-level token-bucket rate limit of 60 requests/minute/IP

Apply a deterministic 60 requests per minute per source IP limit, return 429
with `Retry-After`, and exempt no undocumented endpoint. Keep it adaptable to
a reverse-proxy implementation during hosted deployment.

No rate limit is not selected because an unauthenticated public endpoint can be
scraped or exhausted cheaply. User-account quotas are not selected because
requiring accounts or browser secrets conflicts with public read-only access.

### 18. Service identity: unauthenticated public reads with least-privilege server access

Permit anonymous read access to the versioned public endpoints; the server,
not browser code, holds any credentials needed to read the public snapshot
store. Give the API only read access to public snapshots, while the exporter
has a narrowly scoped publication role.

Embedding a token in the web is not selected because it becomes public.
Giving the API broad M18 read access is not selected because a public service
compromise must not expose private operational tables.

### 19. Observability and audit: privacy-safe exporter/API evidence

Record exporter run identity, source snapshot lineage, outcome class, duration,
published snapshot ID/hash, and aggregate API request/status/rate-limit
counters. Log no request payload, IP address, secret, raw metric input, or
internal exception trace in public responses.

No audit trail is not selected because stale snapshots cannot be investigated.
Full request and exception capture is not selected because it expands privacy
and disclosure risk without improving public functionality.

### 20. Consumer contract: fixture-driven integration and explicit non-production copy

Ship positive and negative JSON fixtures, schema validation, and contract tests
that a separate public web can consume without internal access. The
methodology/overview contract must state origin, candidate status, freshness,
and that monitoring is not a guarantee of model correctness.

Testing only server implementation is not selected because an independently
deployed web can still break on a valid-looking change. Publishing dashboards
without limitations copy is not selected because portfolio users could mistake
candidate or replayed metrics for live production assurance.

## Consequences

- M19 will create a narrow public contract rather than expose M18 data models.
- Public clients need neither internal credentials nor database connectivity.
- Stale, insufficient, suppressed, replayed, and candidate evidence remain
  truthful and visible to the user.
- M20 can harden a materially smaller public attack and privacy surface.

## References

- ADR-0014: M18 internal metrics store and dashboard policy.
- `MLOPS_IMPLEMENTATION_PLAN.md`, M19.
- `MLOPS_END_TO_END_DESIGN.md`, sections 19--20 and 23.
