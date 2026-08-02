"""Validate and atomically activate an immutable M11 release manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from telco_churn.release_control import ReleaseLedger, ReleaseManifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--ledger-dir", type=Path, default=ROOT / "deployments")
    args = parser.parse_args()
    release = ReleaseManifest.from_dict(json.loads(args.manifest.read_text(encoding="utf-8")))
    release.validate_bundle(args.bundle_dir)
    pointer = ReleaseLedger(args.ledger_dir).activate(release)
    print(json.dumps({"release_id": release.release_id, "current_pointer": str(pointer)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
