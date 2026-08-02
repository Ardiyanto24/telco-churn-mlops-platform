"""Validate a raw Telco CSV and emit a verified dataset plus lineage manifest."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from telco_churn.data_contract import build_dataset_manifest, validate_csv, write_dataset_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--code-revision", default=_git_revision())
    args = parser.parse_args()

    validated, report = validate_csv(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    validated.to_csv(args.output, index=False)
    manifest = build_dataset_manifest(args.output, code_revision=args.code_revision)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    write_dataset_manifest(manifest, args.manifest)
    print(f"validated {report.row_count} rows with {report.schema_version}")
    return 0


def _git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted"


if __name__ == "__main__":
    raise SystemExit(main())
