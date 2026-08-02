# M9 Local Runtime

Set the bundle path and copy its threshold/risk-band values from
`model_manifest.json`, then build and run locally:

```powershell
$env:TELCO_CHURN_IMAGE_TAG = "<git-sha>"
$env:TELCO_CHURN_BUNDLE_DIR = "<absolute-path-to-bundle>"
$env:TELCO_CHURN_DECISION_THRESHOLD = "<manifest value>"
$env:TELCO_CHURN_LOW_RISK_THRESHOLD = "<manifest value>"
$env:TELCO_CHURN_HIGH_RISK_THRESHOLD = "<manifest value>"
docker compose up --build --wait
```

The API is available only at `http://127.0.0.1:8000`. Check
`/health/live` and `/health/ready`; the latter remains 503 for an invalid or
incompatible bundle. Stop the demo with `docker compose down`. Add
`--profile registry` only to inspect local MLflow metadata.

The mounted bundle is read-only and the image does not contain model data.
This is local/offline runtime evidence, not production deployment.
