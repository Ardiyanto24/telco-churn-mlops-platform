"""Produce one immutable M8 offline evaluation report for a verified candidate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gates", type=Path, default=Path("configs/evaluation/m8-gates-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--champion", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from telco_churn.evaluation.pipeline import evaluate_candidate

    report = evaluate_candidate(
        args.candidate, args.dataset, args.manifest, args.gates, args.output,
        champion_dir=args.champion,
    )
    print(f"evaluation status: {report['status']} ({args.output / 'evaluation_report.json'})")
    return 0 if report["status"] in {"passed", "not_comparable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
