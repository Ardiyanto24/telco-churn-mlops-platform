"""Create M17 candidate alerts from privacy-minimised evidence JSON Lines."""

from __future__ import annotations

import argparse
from dataclasses import fields
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from telco_churn.alerting import AlertConfig, AlertEvidence, evaluate_alerts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True, help="Aggregate/replay evidence JSONL; never use raw customer records.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_alerts(_load_evidence(args.evidence), config=_load_config(args.config), output_dir=args.output_dir)
    print(f"alerting result: {args.output_dir / (result['idempotency_key'] + '.json')}")
    print(f"alerts: {len(result['alerts'])}; recommendations: {len(result['recommendations'])}")
    return 0


def _load_config(path: Path) -> AlertConfig:
    value = json.loads(path.read_text(encoding="utf-8"))
    return AlertConfig(**{field.name: value[field.name] for field in fields(AlertConfig) if field.name in value})


def _load_evidence(path: Path) -> list[AlertEvidence]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [AlertEvidence(**{**row, "window_end": _timestamp(row["window_end"])}) for row in rows]


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
