"""Restore a prior complete release pair from the M11 append-only history."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from telco_churn.release_control import ReleaseLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to-release-id", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--ledger-dir", type=Path, default=ROOT / "deployments")
    args = parser.parse_args()
    release = ReleaseLedger(args.ledger_dir).rollback(to_release_id=args.to_release_id, operator=args.operator)
    print(json.dumps({"restored_release_id": release.release_id, "environment": release.environment}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
