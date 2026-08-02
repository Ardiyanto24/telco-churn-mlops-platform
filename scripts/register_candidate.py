"""Register one verified M6 candidate in the local M7 MLflow registry."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("artifacts/candidates/m6-legacy-voting-v1"))
    parser.add_argument("--tracking-uri", default="sqlite:///mlflow/mlflow.db")
    parser.add_argument("--artifact-root", type=Path, default=Path("mlflow/artifacts"))
    parser.add_argument("--experiment", default="telco-churn-training")
    parser.add_argument("--model-name", default="telco-churn")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from telco_churn.experiment_registry import RegistryConfig, register_candidate

    result = register_candidate(
        args.candidate,
        RegistryConfig(args.tracking_uri, args.artifact_root, args.experiment, args.model_name),
    )
    print(f"registered {result.model_name} version {result.model_version} from run {result.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
