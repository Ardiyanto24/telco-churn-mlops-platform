# M7 Experiment Tracking and Model Registry Report

## Status

Verified on 2026-08-02.

## Delivered

- Local MLflow OSS tracking/registry integration on SQLite.
- Verified-candidate registration with complete training/data/model lineage.
- Immutable MLflow run artifacts containing the M3 serving bundle and plots.
- Registered model versions plus the `candidate` alias convention.
- A pinned M7 Docker runtime, CLI, ADR, usage documentation, and tests.

## Test evidence

| Check | Result |
|---|---|
| RED registry test on M6 image | Failed as expected: module did not exist. |
| Unit registration contract | Passed: 2 tests. |
| Real SQLite registry integration | Passed: two runs and two distinct model versions; bundle retained as an artifact. |
| M7 model suite | Passed: 22 tests in `telco-churn-m7-runtime:local`. |
| Full suite / baseline verifier | 45 tests passed; one nested-Docker baseline test cannot run inside the container, while direct host baseline verification passed. |

## Exit criteria

- [x] Dataset, commit, run, model, and artifact references are traceable in both directions.
- [x] Registry lifecycle labels are separate from deployment state.
- [x] SQLite backend and local artifact root persist across process restarts.

## Decisions made

- ADR-0003: local MLflow registry retains the M3 bundle as the serving contract.
- Runtime lock: `requirements/m7-runtime.lock`, MLflow 3.15.0.

## Known limitations

- The local SQLite/artifact-root profile is not a multi-user production service.
- M7 neither evaluates gates nor promotes/deploys a version; those actions begin at M8.

## Handoff to M8

- Input: registered immutable candidate version, source run ID, and
  `runs:/<run-id>/bundle` URI with M3 manifest/checksums.
- Preserve: artifact verification, source lineage, and the separation between
  registry labels and deployment state.
