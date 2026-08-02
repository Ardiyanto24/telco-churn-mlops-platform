# Engineering Log - M7: Experiment Tracking and Model Registry

## Context and assumptions

- M7 must register only an M3-verified M6 candidate and must not perform M8
  promotion or any deployment action.
- MLflow OSS runs locally on SQLite with a local artifact root; no external
  credential is required.

## Plan and actions

- Added `telco_churn.experiment_registry`, a registration CLI, MLflow 3.15.0,
  a fully pinned M7 runtime lock, and an M7 Docker image.
- Registration validates `training_run.json`, `metrics.json`, plots, and the M3
  bundle before creating an MLflow run.
- Each run logs parameters, metrics, Git/data/model metadata, plots, and the
  full M3 bundle. The fitted estimator is registered as an MLflow model version.
- Added ADR-0003 and the registry usage/lineage documentation.

## Evidence and findings

- RED: `tests.test_experiment_registry` failed on the M6 image with
  `ModuleNotFoundError: telco_churn.experiment_registry`.
- GREEN unit tests passed after the implementation.
- Real MLflow SQLite integration created two distinct runs and registry versions
  from one candidate, with the complete bundle retained as a run artifact.
- Final M7 model suite passed 22 tests. The full suite passed 45 tests; its one
  baseline integration failure is the known nested-Docker limitation. Direct
  host `baseline/runner.py --verify` passed against the frozen M0 snapshot.

## Errors and handling

- Docker access initially required explicit local Docker approval; after
  approval, the locked M6/M7 images built and ran normally.
- MLflow 3 emits an informational registration warning that it resolves the
  logged model through its MLflow model ID. The registry version still retains
  the source run ID; M7 records the serving-bundle run URI explicitly.

## Decisions and deviations

- ADR-0003 selects SQLite because MLflow's self-hosted registry requires a
  database backend. The M3 bundle stays the serving contract rather than the
  MLflow flavor artifact.

## Risks, limitations, and follow-up

- SQLite/local artifacts are a local-first profile only; a shared or production
  setup needs managed persistent storage.
- M7 assigns only `candidate`; M8 owns evaluation gates and `champion`/archive
  lifecycle changes.

## Trace references

- MLflow: 3.15.0
- Runtime image: `telco-churn-m7-runtime:local`
- Commit: `b8a2739` (`feat: add MLflow experiment registry`)
- ADR: `docs/decisions/0003-local-mlflow-registry-and-m3-serving-bundles.md`
- Verification commands: recorded in `docs/testing.md` and the M7 report.
