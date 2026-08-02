"""Create a new immutable M11 deployment manifest from a verified M3 bundle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from telco_churn.release_control import ReleaseManifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--source-git-sha", required=True)
    parser.add_argument("--evaluation-report-sha256", required=True)
    parser.add_argument("--promotion-decision-sha256", required=True)
    parser.add_argument("--environment", choices=("staging", "production_simulated"), required=True)
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output is immutable and already exists")
    release = ReleaseManifest.create(
        bundle_dir=args.bundle_dir, image_ref=args.image_ref, image_digest=args.image_digest,
        source_git_sha=args.source_git_sha, evaluation_report_sha256=args.evaluation_report_sha256,
        promotion_decision_sha256=args.promotion_decision_sha256, environment=args.environment,
        created_at=args.created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(release.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"release_id": release.release_id, "manifest": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
