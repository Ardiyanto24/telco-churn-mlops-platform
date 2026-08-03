# ADR-0014: Adopt M18 internal metrics store and dashboard policy v1

## Status

Accepted

## Date

2026-08-03

## Context

M12 produces privacy-minimised telemetry rollups, M14 produces data-quality
and drift evidence, M16 produces delayed-label performance evidence, and M17
produces immutable alert and recommendation records. Their current local files
are useful outputs but are not a consistent, queryable source of truth for an
internal investigation. M18 must persist those aggregates, preserve their
lineage, and expose a technical dashboard without making a dashboard or
metrics-store failure affect the Prediction API.

The project remains in candidate mode: the M15 baseline is not yet approved
and production delayed labels are not yet supplied. The first M18 store and
dashboard must therefore make origin and evidence sufficiency explicit rather
than present replayed or synthetic results as live production health.

## Decision

M18 adopts the following twenty decisions.

### 1. Primary store: PostgreSQL in deployed environments, SQLite only for local tests

Use PostgreSQL as the deployed internal metrics store because it provides
concurrent writers, transactional constraints, durable backups, and a clear
path to managed operation. Use SQLite only as an isolated test/local developer
adapter where its zero-configuration setup makes migration tests fast.

Using SQLite as the production store is not selected because its single-writer
and filesystem-operational model does not suit scheduled ingestion and an
internal dashboard. Introducing a cloud-only proprietary store is not selected
because it would make the portfolio project harder to reproduce locally.

### 2. Schema change control: versioned, forward-only migrations with tested downgrade paths

Manage the store with ordered, version-controlled migrations. Each migration
must apply to an empty database, be recorded in a schema-version table, and
have a tested downgrade path during local development before it is used in a
release.

Manual SQL changes are not selected because environments would drift and the
schema could not be reproduced. Destructive automatic rollback in production
is not selected because reverting a migration can lose audit evidence; the
rollback path is a verified recovery tool, not an unattended operation.

### 3. Internal boundary: a dedicated metrics schema and service-owned access layer

Place M18 tables in a dedicated internal metrics schema/database boundary and
access them through a service-owned ingestion/query layer. The Prediction API
and the future public exporter must not receive general table credentials.

Mixing metrics rows into prediction-serving tables is not selected because it
couples availability, permissions, and retention of two different workloads.
Allowing dashboards to issue arbitrary database queries is not selected because
it weakens data minimisation and makes query contracts unreviewable.

### 4. Stored grain: immutable aggregate runs plus normalised lineage entities

Store immutable aggregate result records at the completed monitoring or
telemetry-window grain, linked to normalised model-version and deployment
entities. Keep only aggregates and approved distribution summaries required
for investigation.

Storing every prediction event in M18 is not selected because M12 deliberately
minimises payloads and aggregates telemetry. A single unstructured JSON blob
per report is not selected because uniqueness, retention, and dashboard
queries would become unreliable.

### 5. Canonical entities: model, deployment, rollup, monitoring, performance, alert, recommendation, and public snapshot

Create explicit schema entities for model versions, deployments, telemetry
rollups, monitoring results, performance results, alerts and their revisions,
retraining recommendations, and public-export snapshots. Each entity has a
stable identifier and referential lineage.

One generic `metrics` table is not selected because it cannot express the
different lifecycle and constraints of deployments, alerts, and snapshots.
Duplicating model/deployment attributes into every result is not selected
because corrections would create inconsistent audit history.

### 6. Idempotent ingestion: source-result identity and database unique constraints

Derive an ingestion identity from source result ID, result type, policy/config
version, model/deployment lineage, and completed window. Enforce it with a
database unique constraint and use an upsert/reuse outcome for retries.

Application-only duplicate checks are not selected because concurrent workers
can race. A new row for every retry is not selected because operational retry
noise would be indistinguishable from new monitoring evidence.

### 7. Mandatory lineage: version and origin fields on every result

Persist run ID, model version, deployment ID when applicable, configuration
version, baseline ID, data origin, source report identity, and window bounds
with each aggregate result. Origin is one of controlled values such as
`production`, `replay`, or `synthetic`.

Displaying only a metric value and date is not selected because investigators
could not determine whether evidence is comparable or live. Free-text origin
is not selected because it prevents safe filtering and validation.

### 8. Time semantics: UTC timestamps and closed, explicit windows

Store all instants in UTC and represent every aggregation window by an
inclusive start and exclusive end. Record the calculation completion time
separately from the observed window.

Local server time is not selected because a future deployment or daylight
saving conversion would create ambiguous windows. Inferring a window from
ingestion time is not selected because delayed jobs can otherwise be presented
as current evidence.

### 9. Read model: dashboard queries versioned rollups, never raw event streams

The dashboard reads versioned aggregate tables and curated read-only views;
it does not scan raw telemetry, predictions, labels, or customer records.
Ingestion jobs produce the rollups independently of dashboard availability.

Querying raw events gives more apparent detail but is not selected because it
expands the privacy boundary and makes interactive use expensive. Calculating
monitoring statistics inside dashboard requests is not selected because the
same screen could show different answers and become an operational dependency.

### 10. Retention: tiered retention with protected model and deployment audit trail

Retain aggregate monitoring, performance, alert, recommendation, and lineage
audit records for 13 months; retain short-lived row-level join linkage only
for the 30-day M16 policy; and preserve model/deployment audit history beyond
aggregate expiry. Retention runs are logged and constrained to eligible rows.

Indefinite retention of all metrics is not selected because it increases cost
and privacy exposure. Deleting model/deployment records together with expired
rollups is not selected because later investigation must still identify what
was deployed.

### 11. Query performance: time-oriented indexes and monthly partitions where volume warrants them

Index aggregate results by window end, model/deployment lineage, result type,
and alert severity/state. Use monthly PostgreSQL partitions for high-volume
time-series aggregate tables only after volume justifies the operational cost.

No indexing is not selected because investigation views would degrade as
history grows. Partitioning every small reference table from day one is not
selected because it adds operational complexity without a measured benefit.

### 12. Privacy contract: no identifiers or raw payloads in the store/dashboard contract

Reject customer identifiers, raw feature values, raw predictions, raw labels,
secrets, stack traces, and free-form payload captures at M18 ingestion. Store
only approved aggregate values, counts, distribution bins/categories permitted
by M12/M14, and privacy-safe report links.

Hashing identifiers is not selected as a substitute because stable hashes can
still enable linkage. Making raw data available to internal investigators is
not selected because dashboard convenience does not justify expanding the data
handling boundary.

### 13. Access control: internal authentication, least-privilege roles, and read-only investigation access

Require internal authentication for the dashboard. Grant ingestion a narrowly
scoped write role, grant investigators read-only access to curated views, and
reserve migration/retention administration for operations. Public consumers
receive only future M19-exported snapshots.

Anonymous internal access is not selected because alerts and model context can
still be sensitive operational information. Reusing a database owner account
for the dashboard is not selected because a UI compromise would gain write or
schema privileges.

### 14. Dashboard architecture: internal, read-only technical UI over a stable query API

Build a small internal dashboard backed by read-only application query
endpoints, with no write controls or automatic operational actions. It is a
technical investigation interface, not a public product dashboard.

Direct browser-to-database access is not selected because it exposes
credentials and bypasses query controls. Using the public dashboard as the
internal tool is not selected because public consumers require a smaller,
sanitised contract and different availability expectations.

### 15. Investigation views: service health, telemetry, quality/drift, performance, coverage, alerts, and lineage

Provide focused views for service health and ingestion freshness, telemetry
volume, data-quality and drift distributions, delayed-label performance and
coverage, alert/recommendation history, and model/deployment lineage. Views
cross-link only through stable aggregate identifiers.

A single undifferentiated chart page is not selected because it hides the
causal path from deployment to evidence to alert. Building retraining,
promotion, rollback, or threshold-control screens is not selected because M18
remains read-only under the M17 automation boundary.

### 16. Evidence-state rendering: distinguish stable from absence or insufficiency

Render `stable`, `unknown`, `insufficient_data`, and `not_available` as
distinct states with their source reason. Only a policy-qualified source result
may be rendered as stable.

Treating no row as stable is not selected because absence can mean a late job,
failed ingestion, or unavailable labels. Collapsing all non-stable states into
an error is not selected because operators need to know whether to wait,
investigate data quality, or repair the pipeline.

### 17. Required context: show sample, coverage, window, method, lineage, and freshness beside each result

Every dashboard result must display sample size, label coverage where relevant,
observed window, calculation method and policy version, model/baseline/config
lineage, data origin, and freshness status. Distribution views show baseline
and current values from the same stored result.

Minimal headline-only charts are not selected because they encourage incorrect
comparisons. Requiring an operator to find metadata in logs is not selected
because it makes routine investigation slow and error-prone.

### 18. Freshness policy: explicit SLA states based on expected completed windows

Compute freshness from the newest successfully ingested completed window and
the source schedule, rendering `fresh`, `late`, or `stale/not_available` with
the expected and actual timestamps. A delayed source is not silently replaced
by an older green result.

Showing only "last updated" is not selected because users cannot judge whether
the age violates an expected cadence. Treating every late batch as an incident
is not selected because the M17 operational policy, not dashboard colour
alone, owns alert qualification.

### 19. Availability isolation: asynchronous ingestion and failure-contained dashboard operation

Run ingestion and dashboard read paths outside the Prediction API request
path. Database, dashboard, and rendering failures are logged and surface as
internal evidence gaps; prediction serving continues under its existing
runtime contract.

Synchronous metrics writes on each prediction are not selected because an
observability outage could raise prediction latency or failure rate. Failing
closed for the prediction API when the dashboard is unavailable is not
selected because it converts an investigation-tool outage into customer impact.

### 20. Public boundary: snapshot-only export with explicit sanitisation and provenance

Treat M18 internal tables as private. M19 may create versioned public
snapshots only through a dedicated exporter that selects approved aggregate
fields, validates sanitisation, and records source-store/version provenance.

Giving the public API read access to internal tables is not selected because a
future schema change could expose operational or sensitive fields. Manually
copying dashboard values into public output is not selected because it is not
reproducible or auditable.

## Consequences

- M18 becomes the durable internal source of truth for the aggregate outputs
  of M12, M14, M16, and M17, without changing their statistical policies.
- The dashboard is a read-only investigation aid and remains optional for
  prediction serving.
- The first implementation must visibly identify replayed, synthetic,
  candidate, insufficient, and unavailable evidence.
- M19 can consume a controlled, sanitised snapshot boundary rather than couple
  a public service to internal monitoring tables.

## References

- ADR-0008 (M12 telemetry and prediction-metadata policy).
- ADR-0009 (M13 reference baseline design).
- ADR-0010 (M14 data-quality and drift engine policy).
- ADR-0011 (M15 statistical-monitoring calibration policy).
- ADR-0012 (M16 delayed-label performance-monitoring policy).
- ADR-0013 (M17 alerting and retraining-recommendation policy).
- `MLOPS_IMPLEMENTATION_PLAN.md`, M18.
- `MLOPS_END_TO_END_DESIGN.md`, sections 15--18.
