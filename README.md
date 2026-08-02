# Telco Churn MLOps Platform

A portfolio-grade MLOps foundation for Telco Customer Churn prediction. The
project evolves a legacy model into a reproducible lifecycle: data validation,
training, verified model bundles, model evaluation gates, local serving, and
continuous-integration controls.

> Status: **in progress, not production-ready.** Milestones M0–M10 are
> implemented locally. Production deployment, telemetry, drift/performance
> monitoring, security hardening, and operational readiness are intentionally
> still planned for later milestones. The GitHub Actions workflow also needs its
> first remote run after this repository is published.

## What exists today

- Frozen legacy behavior oracle and anonymous golden fixtures (M0).
- Versioned FastAPI prediction contract and verified M3 artifact loading.
- Validated/versioned dataset workflow and reproducible candidate training.
- Local MLflow experiment lineage and registry with explicit promotion gates.
- Offline candidate quality gates: ranking, classification, calibration,
  probability validity, latency, and champion regression checks.
- Hardened local Docker/Compose API runtime with a read-only model bundle mount.
- GitHub Actions CI policy for fast, model, container-smoke, and security checks.

## Repository map

| Path | Purpose |
|---|---|
| `src/telco_churn/` | New MLOps Python package. |
| `baseline/` | Frozen M0 legacy fixtures and compatibility evidence. |
| `configs/` | Versioned training and evaluation configuration. |
| `docker/`, `compose.yaml` | Local API runtime definitions. |
| `docs/decisions/` | Architecture Decision Records (ADRs). |
| `docs/milestones/` | Completion reports and verification evidence. |
| `MLOPS_IMPLEMENTATION_PLAN.md` | Canonical M0–M21 roadmap. |

## Quick start: local API runtime

Prerequisites: Docker Desktop and a verified M3/M6 bundle produced locally.
The bundle is mounted read-only and is never embedded in the image.

```powershell
$env:TELCO_CHURN_IMAGE_TAG = "local"
$env:TELCO_CHURN_BUNDLE_DIR = "<absolute-path-to-bundle>"
$env:TELCO_CHURN_DECISION_THRESHOLD = "<model_manifest decision_threshold>"
$env:TELCO_CHURN_LOW_RISK_THRESHOLD = "<model_manifest risk_bands.low>"
$env:TELCO_CHURN_HIGH_RISK_THRESHOLD = "<model_manifest risk_bands.high>"
docker compose up --build --wait
```

Check `http://127.0.0.1:8000/health/ready`, then stop with:

```powershell
docker compose down
```

See [M9 local runtime documentation](docs/m9-local-runtime.md) for details.

## Verification

Model and artifact tests require the locked runtime image. For example:

```powershell
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m8-runtime:local scripts/run_tests.py model
```

The CI workflow is defined in `.github/workflows/ci.yml`. It is intentionally
least-privilege, uses synthetic CI artifacts, and does not publish images or
deploy the service.

## Project status and roadmap

Read [PROGRESS_TRACKING.md](PROGRESS_TRACKING.md) for the concise current
status, [MLOPS_IMPLEMENTATION_PLAN.md](MLOPS_IMPLEMENTATION_PLAN.md) for the
full roadmap, and [docs/decisions](docs/decisions/) for durable engineering
decisions.

Contributions must preserve anonymous fixtures, avoid committing secrets or
customer data, and keep changes aligned with [AGENTS.md](AGENTS.md).
