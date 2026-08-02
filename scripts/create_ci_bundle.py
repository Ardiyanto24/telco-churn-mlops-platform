"""Create a synthetic verified M3 bundle for an ephemeral CI smoke test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "src"))
    from tests.test_training_pipeline import TrainingPipelineTests
    from telco_churn.training.pipeline import run_training

    helper = TrainingPipelineTests()
    dataset, manifest = helper._verified_data(args.output)
    result = run_training(helper._config(), dataset, manifest, args.output / "candidate")
    model_manifest = json.loads((result.output_dir / "bundle" / "model_manifest.json").read_text(encoding="utf-8"))
    print(json.dumps({"bundle": str(result.output_dir / "bundle"), "threshold": model_manifest["decision_threshold"], "low": model_manifest["risk_bands"]["low"], "high": model_manifest["risk_bands"]["high"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
