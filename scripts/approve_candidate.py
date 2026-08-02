"""Create or apply a human M8 promotion decision for an evaluation report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--apply", action="store_true", help="apply an existing decision to the MLflow registry")
    parser.add_argument("--tracking-uri", default="sqlite:///mlflow/mlflow.db")
    parser.add_argument("--model-name", default="telco-churn")
    parser.add_argument("--model-version", help="MLflow registered model version required with --apply")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from telco_churn.evaluation.promotion import approve_report

    if not args.apply:
        decision = approve_report(args.report, args.decision, approver=args.approver)
        print(f"approval recorded ({args.decision}); initial baseline: {decision['initial_baseline']}")
        return 0
    if not args.model_version:
        parser.error("--model-version is required with --apply")
    decision = json.loads(args.decision.read_text(encoding="utf-8"))
    from mlflow import MlflowClient

    applied_path = args.decision.with_name(f"{args.decision.stem}.applied.json")
    approve_report(
        args.report, applied_path, approver=args.approver, decision=decision,
        client=MlflowClient(args.tracking_uri), model_name=args.model_name, model_version=args.model_version,
    )
    print(f"approval applied; {args.model_name}@{args.model_version} is now champion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
