"""Create an M6 candidate bundle from the M5-validated training data."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/training/m6-legacy-voting-v1.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/validated/telco_churn.csv"))
    parser.add_argument("--manifest", type=Path, default=Path("data/validated/dataset-manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/candidates/m6-legacy-voting-v1"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from telco_churn.training.pipeline import TrainingConfig, run_training

    result = run_training(TrainingConfig.from_json(args.config), args.dataset, args.manifest, args.output)
    print(f"candidate bundle created: {result.output_dir / 'bundle'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
