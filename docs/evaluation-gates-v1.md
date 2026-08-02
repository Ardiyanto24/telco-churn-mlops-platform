# M8 Evaluation and Promotion Gates

`configs/evaluation/m8-gates-v1.json` is the versioned policy for an offline
candidate evaluation. It evaluates the deterministic M6 test partition from
the candidate's own training configuration; the test split is never retuned.

The policy uses average precision as the primary metric and also gates recall,
precision, F1, ROC-AUC, Brier score, equal-frequency ECE, and p95 inference
latency. When a compatible champion is supplied, each metric is additionally
checked against the configured regression tolerance.

## Run an evaluation

```powershell
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/workspace" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  telco-churn-m8-runtime:local python scripts/evaluate_candidate.py `
  --candidate artifacts/candidates/<candidate> `
  --dataset data/validated/telco_churn.csv `
  --manifest data/validated/dataset_manifest.json `
  --output artifacts/evaluations/<candidate>-m8
```

Add `--champion artifacts/candidates/<champion>` only when its M3 feature
contract and its M5 dataset manifest match the candidate. Output paths are
immutable: choose a new directory for every run. The command returns non-zero
for `failed` or `invalid`; `not_comparable` is valid offline evidence but still
needs an explicit initial-baseline approval.

## Approval flow

Human review creates a decision artifact tied to the exact report bytes:

```powershell
python scripts/approve_candidate.py --report artifacts/evaluations/<candidate>-m8/evaluation_report.json `
  --decision artifacts/evaluations/<candidate>-m8/promotion-decision.json --approver <reviewer>
```

Only a second, explicit `--apply` invocation may assign MLflow's mutable
`champion` alias. It validates the approved decision digest and records the
approval as tags before moving the alias. Registry promotion is not a deployment
action.

Evaluation results are strictly offline test evidence, not production
performance. See [ADR-0004](decisions/0004-m8-evaluation-and-promotion-gate-policy.md)
for rationale and exact policy semantics.
