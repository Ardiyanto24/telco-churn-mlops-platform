# AGENTS.md — Telco Churn MLOps Repository

## Project profile

This repository evolves the Telco Customer Churn prediction deployment into an end-to-end, portfolio-grade MLOps system. The target lifecycle covers reproducible training, model artifacts, serving, telemetry, statistical drift/performance monitoring, internal observability, and a read-only Public Metrics API for a separate public-dashboard repository.

The project plan is deliberately milestone-driven. The canonical architecture and scope are in `MLOPS_END_TO_END_DESIGN.md`; the execution order and exit criteria are in `MLOPS_IMPLEMENTATION_PLAN.md`.

## Repository boundaries

- `src/telco_churn/`: new MLOps package. New implementation belongs here.
- `baseline/`: frozen M0 behavior fixtures, capture code, and evidence.
- `requirements/`: direct inputs and fully pinned runtime dependencies.
- `docker/`: reproducible verification/runtime image definitions.
- `docs/decisions/`: ADRs for durable architectural decisions.
- `docs/milestones/`: final completion reports and exit-criteria evidence.
- `docs/logs/`: chronological engineering logs of actual work, including deviations and failures.
- `../legacy-deployment/`: legacy serving project. Treat it as read-only unless the user explicitly asks to modify it.
- `../public-dashboard/`: separate repository for the public web. It must not access MLOps internals or databases directly.

## Mandatory workflow for every milestone

1. Read this file, the relevant section of `MLOPS_IMPLEMENTATION_PLAN.md`, relevant ADRs, and prior engineering logs.
2. **Use the `using-agent-skills` skill at the start of every milestone.** Discover and apply all relevant skills before taking task actions. Announce the skills being used and why.
3. State any material assumptions before non-trivial implementation. If requirements conflict or a decision would change scope, stop and ask the user rather than guessing.
4. Work in small, testable increments. For behavioral changes, write a failing test first, then implement the smallest change that passes.
5. Record actual work in `docs/logs/m<id>-<slug>.md` as it happens, following the required trace categories in `docs/logs/README.md`: context/assumptions, plan, actions and evidence, findings, errors and handling, decisions/deviations, risks/limitations, artifacts/commits, and handoff. Do not reconstruct or claim activity without evidence.
6. At milestone completion, update/create `docs/milestones/m<id>-<slug>-report.md` with deliverables, test evidence, exit criteria, ADR/config versions, limitations, and handoff.
7. Run milestone-appropriate verification before committing. Review the diff for secrets, unintended files, and whitespace errors.
8. Commit one focused logical change at a time with a descriptive Conventional Commit message. Do not commit generated caches, `.env` files, credentials, or customer data.

## Current foundation and compatibility rules

- M0 is the behavior oracle for the legacy inference path. Do not overwrite `baseline/expected/legacy_snapshot.json` merely because output changes. Explain and obtain approval for intentional changes.
- Legacy artifacts were serialized with scikit-learn `1.6.1`. The M1 runtime lock pins this version and is proven against M0 scenarios.
- New transformer classes must live under `telco_churn.preprocessing`; do not add `__main__` rebinding to new package code.
- Legacy Joblib compatibility/migration is M3 scope. Do not replace the legacy loader in M1/M2 work without an approved artifact contract.
- Decision threshold and risk-band settings have one source of truth: `telco_churn.settings`. Do not duplicate production values elsewhere.
- Statistical drift thresholds, reference populations, window policies, and performance-decay thresholds remain provisional until their designated milestones. Never present synthetic, replayed, offline, or unlabeled results as live production performance.

## Verification commands

Use the bundled host Python for dependency-free tests when needed:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -v
```

Tests requiring the locked M1 dependencies must run in the verification container:

```powershell
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m1-runtime:local `
  -m unittest tests.test_import_graph tests.test_preprocessing tests.test_settings tests.test_dependency_lock -v
```

When changing package structure, dependencies, artifact loading, preprocessing, or prediction behavior, also run the relevant M0 golden comparison. Capture any candidate evidence to a new file; preserve the legacy oracle.

## Security and data handling

- Never commit secrets, access tokens, `.env` files, private URLs, or raw customer/prediction payloads.
- Use anonymous/synthetic fixtures for tests and documentation.
- Treat all external data, config, logs, and browser/API payloads as untrusted input.
- Public-dashboard integration must use only the future versioned Public Metrics API/snapshot. No browser client may hold internal credentials or directly query internal stores.
- Do not perform destructive Git or filesystem actions without explicit user authorization.

## Git conventions

- Work on a branch prefixed `codex/` unless the user specifies otherwise.
- Keep commits small and reversible; do not mix unrelated refactors, dependency changes, and features.
- Before committing, inspect `git diff --staged`, run relevant tests, and use `git diff --check`.
- Preserve user changes in a dirty worktree. Do not reset, checkout, delete, or overwrite unrelated work.

## Documentation map

| Need | Source of truth |
|---|---|
| End-to-end target architecture | `MLOPS_END_TO_END_DESIGN.md` |
| Milestone scope, dependencies, tests, exit criteria | `MLOPS_IMPLEMENTATION_PLAN.md` |
| Why a durable design decision was made | `docs/decisions/` |
| Final result of a completed milestone | `docs/milestones/` |
| What was actually done during a milestone | `docs/logs/` |

If this file conflicts with an explicit user instruction, follow the user instruction and record the divergence in the engineering log.

## Documentation traceability rule

Every milestone log must make it possible to answer: what was intended, what
actually happened, why a decision changed, what failed, how it was handled, and
what remains unresolved. Record each material item under these categories:

1. **Context and assumptions** — scope, constraints, and assumptions that guide work.
2. **Plan and actions** — work performed, relevant commands, and affected files.
3. **Evidence and findings** — test output, measurements, inspected artifacts, or other verifiable facts.
4. **Errors and handling** — symptom, likely/root cause when known, mitigation, verification, and unresolved impact.
5. **Decisions and deviations** — choices that differ from a prior plan/design, their rationale, alternatives when material, and the authority/source of the decision.
6. **Risks, limitations, and follow-up** — claims that cannot be made, missing inputs, technical debt, and the next owner/milestone.
7. **Trace references** — config/data/model/artifact versions, commit IDs, issue/ADR links, and commands required to reproduce evidence.

Create or update an ADR in `docs/decisions/` for a durable architectural decision. Logs may summarize it but must link to the ADR. Never record secrets or raw customer payloads.
