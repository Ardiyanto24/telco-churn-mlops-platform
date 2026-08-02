# Progress Tracking - Telco Churn MLOps

> Last updated: 2026-08-02
>
> This is a concise status index. Completion reports and engineering logs hold
> the detailed evidence.

## Current snapshot

- Overall program: **M0-M9 complete; M10 is the next recommended milestone.**
- The foundation now includes a verified legacy oracle, versioned data,
  reproducible training, M3 artifact bundles, and local MLflow experiment
  lineage/model registry.
- The legacy deployment remains isolated in `../legacy-deployment/`; M7 does
  not select a deployment or replace that service.
- M8 gates produce offline evaluation evidence only; a registry champion is not
  a deployed production model.

## Milestone status

| Milestone | Area | Status | Notes |
|---|---|---|---|
| M0 | Legacy baseline | Done | Golden fixtures, snapshot, checksums, and Docker verifier. |
| M1 | Package and configuration | Done | Stable package and locked scikit-learn 1.6.1 runtime. |
| M2 | Prediction API contract | Done | Versioned HTTP schemas and stable errors. |
| M3 | Artifact contract/loading | Done | Immutable manifest, checksums, stable-path migration. |
| M4 | Test foundation | Done | Categorized runner, isolated fixtures, coverage support. |
| M5 | Data contract/versioning | Done | Validated dataset, DVC lineage, R2 sync. |
| M6 | Reproducible training | Done | Config-driven candidate bundles and deterministic training. |
| M7 | Experiment tracking/registry | Done | MLflow SQLite lineage, immutable versions, candidate alias. |
| M8 | Evaluation/promotion gates | Done | Versioned offline gates, model card, approval artifact, champion alias control. |
| M9 | Container/local runtime | Done | Verified local API image, Compose profile, and read-only bundle mount. |
| M10-M21 | Remaining lifecycle | Not started | Follow dependency order in the implementation plan. |

`Done` means a completion report with recorded verification evidence exists.

## Read this before working

1. [AGENTS.md](AGENTS.md)
2. [Implementation plan](MLOPS_IMPLEMENTATION_PLAN.md)
3. Relevant architecture in [end-to-end design](MLOPS_END_TO_END_DESIGN.md)
4. Relevant decisions in [docs/decisions](docs/decisions/)
5. The latest log in [docs/logs](docs/logs/) and report in [docs/milestones](docs/milestones/)

At the beginning of every milestone, agents must use the `using-agent-skills`
skill as required by `AGENTS.md`.
