"""Evaluate one immutable M16 delayed-label cohort from protected JSON Lines."""

from __future__ import annotations

import argparse
from dataclasses import fields
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from telco_churn.performance_monitoring import (
    DelayedLabel,
    PerformanceConfig,
    PredictionEvent,
    run_performance_monitoring,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True, help="Protected prediction-event JSONL; never commit this file.")
    parser.add_argument("--labels", type=Path, required=True, help="Protected delayed-label JSONL; never commit this file.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="UTC ISO-8601 evaluation cutoff.")
    parser.add_argument("--data-origin", choices=("offline_test", "replayed", "synthetic", "production"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_performance_monitoring(
        _load_predictions(args.predictions), _load_labels(args.labels),
        config=_load_config(args.config), as_of=_timestamp(args.as_of),
        data_origin=args.data_origin, output_dir=args.output_dir,
    )
    print(f"performance result: {args.output_dir / (result['idempotency_key'] + '.json')}")
    print(f"status: {result['status']}")
    return 0 if result["status"] not in {"unknown"} else 2


def _load_config(path: Path) -> PerformanceConfig:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["probability_bin_edges"] = tuple(value.get("probability_bin_edges", ()))
    return PerformanceConfig(**{field.name: value[field.name] for field in fields(PerformanceConfig) if field.name in value})


def _load_predictions(path: Path) -> list[PredictionEvent]:
    return [PredictionEvent(**_timestamps(value, "prediction_at")) for value in _json_lines(path)]


def _load_labels(path: Path) -> list[DelayedLabel]:
    return [DelayedLabel(**_timestamps(_timestamps(value, "outcome_at"), "received_at")) for value in _json_lines(path)]


def _json_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _timestamps(value: dict[str, Any], *names: str) -> dict[str, Any]:
    return {**value, **{name: _timestamp(value[name]) for name in names}}


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
