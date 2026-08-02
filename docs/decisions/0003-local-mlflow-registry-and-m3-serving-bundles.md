# ADR-0003: Use local MLflow registry while retaining M3 bundles as serving artifacts

## Status

Accepted

## Date

2026-08-02

## Context

M7 needs durable experiment lineage and immutable model versions, while M3 has
already defined a trusted serving bundle containing both the model and
preprocessor plus a checksum manifest. MLflow OSS needs a database-backed
backend for Model Registry operations. Replacing the M3 loader with an MLflow
flavor would duplicate or weaken that existing artifact contract.

## Decision

- Use MLflow OSS with SQLite for the local-first M7 tracking and registry profile.
- Log the complete verified M3 bundle as a run artifact and register the fitted
  scikit-learn estimator as the MLflow model linked to that same run.
- Keep `runs:/<run-id>/bundle` as the immutable serving-bundle reference.
- Use `candidate`, `champion`, and `archived` lifecycle labels; M7 sets only
  `candidate`. These labels never express deployment state.

## Alternatives Considered

### File-backed MLflow store

- Rejected because MLflow documents a database-backed backend as necessary for
  self-hosted Model Registry access.

### Make the MLflow model artifact the serving contract

- Rejected because it would separate the estimator from M3's preprocessor and
  manifest, bypassing the checksum/runtime verification required before serving.

## Consequences

- M7 provides local persistent lineage and registry versions without external credentials.
- SQLite/artifact paths must be moved to managed persistent storage for shared
  or production use.
- M8 can evaluate immutable version and bundle references, then assign a
  champion alias without changing deployment state.

## References

- https://mlflow.org/docs/latest/ml/model-registry/
- https://www.mlflow.org/docs/latest/ml/model-registry/workflow/
