"""Run one M14 experimental monitoring comparison from immutable inputs."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from telco_churn.artifacts import VerifiedArtifactLoader
from telco_churn.monitoring_engine import MonitoringConfig, run_monitoring


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-window", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-period", required=True)
    parser.add_argument("--minimum-sample-size", type=int, default=30)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    frame = pd.read_csv(args.current_window, keep_default_na=False)
    result = run_monitoring(
        frame, baseline=baseline, bundle=VerifiedArtifactLoader().load(args.bundle_dir),
        config=MonitoringConfig(minimum_sample_size=args.minimum_sample_size),
        current_window={"sha256": _sha256(args.current_window), "source_period": args.source_period, "source_name": args.current_window.name},
        output_dir=args.output_dir,
    )
    print(f"monitoring result: {args.output_dir / (result['idempotency_key'] + '.json')}")
    print(f"run status: {result['run_status']}")
    return 0 if result["run_status"] != "unknown" else 2


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
