# Milestone M8 Completion Report

Status: done
Tanggal: 2026-08-02
Commit/PR: recorded in repository history on `codex/m8-evaluation-gate-policy`

## Deliverable

- Versioned absolute, regression, calibration, probability-validity, and latency gates.
- Reproducible candidate-versus-champion offline evaluation report and model card.
- Immutable human promotion decision artifact tied to the report digest.
- Explicit MLflow champion-alias application path, separate from deployment.

## Test evidence

- Command: `docker build -t telco-churn-m8-runtime:local -f mlops/docker/m8-runtime.Dockerfile .`
- Result: succeeded.
- Command: `docker run --rm -e PYTHONPATH=/workspace/src ... telco-churn-m8-runtime:local python -m unittest tests.test_evaluation_gates -v`
- Result: 8 M8 tests passed; the complete `model` category also passed (30 tests).
- Command: `docker run ... telco-churn-m8-runtime:local python scripts/evaluate_candidate.py --help` and `scripts/approve_candidate.py --help`
- Result: both CLI entry points succeeded.

## Exit criteria

- [x] No promotion path assigns the champion alias before a successful M8 report and explicit approval artifact.
- [x] Gate values are versioned and justified in ADR-0004.
- [x] Evaluation/model-card output labels metrics as offline, never production performance.

## Decisions made

- ADR-0004 and `configs/evaluation/m8-gates-v1.json`.

## Known limitations

- No claim about live production latency or performance is made.
- Statistical bootstrap confidence intervals remain supporting analysis, outside deterministic hard gate v1.

## Handoff ke milestone berikutnya

- M9 can use the M8 runtime and immutable evaluation artifacts as inputs.
- M10 should run the `model` suite, including M8 negative gate tests, in CI.
