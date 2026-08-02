"""Regenerate an immutable M15 reference baseline from the exact M6 training split."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from telco_churn.artifacts import VerifiedArtifactLoader
from telco_churn.data_contract import load_verified_dataset
from telco_churn.monitoring_baseline import build_baseline, write_baseline
from telco_churn.training.pipeline import TrainingConfig, reconstruct_training_split


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--training-config", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--approval-record", type=Path, required=True)
    args = parser.parse_args()
    if not args.approval_record.is_file():
        raise SystemExit("approval record is required before creating an approved baseline")
    frame = load_verified_dataset(args.dataset, args.dataset_manifest)
    config = TrainingConfig.from_json(args.training_config)
    train = reconstruct_training_split(frame, config)
    baseline = build_baseline(
        train, dataset_manifest=json.loads(args.dataset_manifest.read_text(encoding="utf-8")),
        bundle=VerifiedArtifactLoader().load(args.bundle_dir), model_manifest_sha256=_sha256(args.bundle_dir / "model_manifest.json"),
        status="approved", reference_population={"split": "train", "seed": config.seed, "filters": [], "origin": "M6 reconstructed fit split", "approval_record_sha256": _sha256(args.approval_record)},
    )
    destination = args.output_dir / baseline["baseline_id"] / "baseline.json"
    write_baseline(baseline, destination)
    print(f"approved baseline created: {destination}")
    return 0


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
