# Experiment Tracking and Model Registry v1

M7 uses MLflow OSS with a local SQLite backend and a local artifact root. This
is a development/portfolio profile; a shared deployment must replace the paths
with persistent managed storage before claiming multi-user availability.

## Register a candidate

Create an M6 candidate first, then run this command in the locked M7 runtime:

```powershell
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/workspace" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m7-runtime:local `
  scripts/register_candidate.py --candidate artifacts/candidates/m6-legacy-voting-v1
```

The command rejects candidates without a complete `training_run.json`, matching
`metrics.json`, plots, and a bundle that passes the M3 verified loader.

## Stored lineage

Each MLflow run records the training config/model parameters, metrics, source
Git revision, dataset manifest SHA-256, model family, M3 feature signature,
schema/baseline identifiers, plots, and the full M3 candidate bundle. The
registered MLflow `sklearn` model links the fitted estimator to the same run;
the immutable `runs:/<run-id>/bundle` artifact remains the serving bundle with
the preprocessor and checksum manifest.

## Registry lifecycle convention

| Name | Meaning | Owner |
|---|---|---|
| `candidate` alias | Most recently registered candidate; not deployed. | M7 |
| `champion` alias | Candidate approved by M8 gates. | M8 |
| `archived` tag | Version no longer eligible for selection. | M8+ |

Aliases are registry labels, not a deployment environment. M7 never chooses a
production artifact or writes a deployment manifest.

MLflow model versions, aliases, tags, and run lineage follow the official
[MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/) and
[Model Registry workflow](https://www.mlflow.org/docs/latest/ml/model-registry/workflow/).
