# M18 Internal Metrics Store and Dashboard

M18 persists privacy-minimised, aggregate monitoring evidence and renders it in
a separate read-only technical dashboard. It is internal-only and candidate
mode; a `synthetic`, `replayed`, or `not_available` result is never presented
as live production health.

## Local candidate workflow

1. Migrate a local SQLite adapter:

   ```powershell
   python scripts/manage_metrics_store.py --database .\artifacts\m18-metrics.db migrate
   ```

2. Ingest a validated M18 aggregate-record JSON document. The document must
   contain `records`; each record requires lineage, explicit UTC window bounds,
   evidence status, origin, aggregate summary, and distribution. Customer IDs,
   raw payloads, labels, predictions, secrets, and stack traces are rejected.

   ```powershell
   python scripts/manage_metrics_store.py --database .\artifacts\m18-metrics.db ingest --input .\safe-aggregate-records.json
   ```

3. Set a local token outside source control and start the separate dashboard:

   ```powershell
   $env:TELCO_CHURN_INTERNAL_DASHBOARD_TOKEN = 'replace-with-a-local-secret'
   python scripts/serve_internal_dashboard.py --database .\artifacts\m18-metrics.db
   ```

   Open `http://127.0.0.1:8018/internal/dashboard` with the HTTP header
   `X-Internal-Metrics-Token`. The dashboard never creates, promotes, rolls
   back, retrains, or changes thresholds.

## Safety and retention

- Use PostgreSQL for a deployed store; SQLite is only the local/test adapter
  exercised in this milestone.
- Dashboard access requires a server-side token and all dashboard queries are
  read-only. It sends no CORS policy or browser database credentials.
- The candidate configuration retains aggregate records for 395 days (about 13
  months). Retention removes eligible results only, not model/deployment audit
  lineage.
- Dashboard/store failures are isolated from the Prediction API. M19 is the
  only future path for an explicitly sanitised public snapshot/export.

## Verification

Run `python scripts/run_tests.py api` and `python scripts/run_tests.py model`
in the locked runtime. The M18 tests cover migration/rollback, idempotent
ingestion, forbidden raw fields, evidence states, distribution display,
dashboard access, retention, and Prediction API isolation.
