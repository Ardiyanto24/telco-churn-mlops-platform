# Progress Tracking — Telco Churn MLOps

> Last updated: 2026-08-01
>
> This is a short navigation and status document, not a substitute for evidence or detailed implementation history.

## Current snapshot

- Overall program: **M0–M1 complete; M2 is the next recommended milestone.**
- Current implementation foundation: Python package structure, validated settings, stable future transformer module path, reproducible Docker runtime, and frozen legacy inference oracle.
- Active branch at last update: `codex/m1-package-foundation`.
- The legacy deployment remains isolated in `../legacy-deployment/` and is not yet replaced by the new package.

## Milestone status

| Milestone | Area | Status | Notes |
|---|---|---|---|
| M0 | Legacy baseline | Done | Golden fixtures, snapshot, checksums, and Docker verifier recorded. |
| M1 | Package and configuration foundation | Done | Runtime lock tested with scikit-learn 1.6.1; M0 prediction scenarios remain identical. |
| M2 | Prediction API contract | Next | Versioned API schemas, health/version endpoints, validation, and stable error semantics. |
| M3 | Artifact contract and loading | Not started | Manifest, checksum, compatibility loader, and migration plan for legacy Joblib. |
| M4–M21 | Remaining MLOps lifecycle | Not started | Follow dependency order in the implementation plan. |

`Done` means the milestone has a completion report and recorded verification evidence. `Next` is a recommendation, not a claim that work has started.

## Read this before working

AI agents and contributors must read, in order:

1. [AGENTS.md](AGENTS.md) — mandatory operating rules, repository boundaries, skills, testing, security, and Git conventions.
2. [Implementation plan](MLOPS_IMPLEMENTATION_PLAN.md) — scope, dependencies, tests, and exit criteria for the target milestone.
3. Relevant architecture sections in [end-to-end design](MLOPS_END_TO_END_DESIGN.md).
4. Relevant decisions in [docs/decisions](docs/decisions/).
5. The latest process log in [docs/logs](docs/logs/) and final report in [docs/milestones](docs/milestones/).

At the beginning of **every milestone**, agents must use the `using-agent-skills` skill as required by `AGENTS.md`.

## Documentation guide

| Question | Read |
|---|---|
| What should the completed system look like? | [MLOPS_END_TO_END_DESIGN.md](MLOPS_END_TO_END_DESIGN.md) |
| What is in/out of scope and how is success tested? | [MLOPS_IMPLEMENTATION_PLAN.md](MLOPS_IMPLEMENTATION_PLAN.md) |
| Why was a technical direction chosen? | [docs/decisions](docs/decisions/) |
| What actually happened while implementing a milestone? | [docs/logs](docs/logs/) |
| What was delivered and verified at the end? | [docs/milestones](docs/milestones/) |
| What must every agent follow? | [AGENTS.md](AGENTS.md) |

## Rules for updating this file

- Update the status only after the corresponding completion report has been verified.
- Keep this document concise; link to detailed evidence rather than duplicating it.
- If a milestone becomes blocked, state the blocker and link to the log/ADR with details.
- Update `docs/logs/` during work and `docs/milestones/` when the milestone closes.
