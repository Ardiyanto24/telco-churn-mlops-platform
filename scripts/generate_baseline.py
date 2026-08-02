"""Generate one immutable M13 reference-baseline artifact from verified inputs."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from telco_churn.artifacts import VerifiedArtifactLoader
from telco_churn.data_contract import load_verified_dataset
from telco_churn.monitoring_baseline import build_baseline, write_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    frame = load_verified_dataset(args.dataset, args.dataset_manifest)
    dataset_manifest = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    bundle = VerifiedArtifactLoader().load(args.bundle_dir)
    model_manifest = args.bundle_dir / "model_manifest.json"
    baseline = build_baseline(
        frame, dataset_manifest=dataset_manifest, bundle=bundle,
        model_manifest_sha256=_sha256(model_manifest),
    )
    destination = args.output_dir / baseline["baseline_id"] / "baseline.json"
    write_baseline(baseline, destination)
    print(f"baseline created: {destination}")
    return 0


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
