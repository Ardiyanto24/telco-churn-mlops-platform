"""Operate the M18 aggregate metrics store without accepting raw customer data."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

from telco_churn.metrics_store import MetricRecord, MetricsStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="SQLite database path for local/candidate operation.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("--input", type=Path, required=True, help="M18 aggregate-record JSON document.")
    retention = commands.add_parser("retention")
    retention.add_argument("--days", type=int, default=395)
    retention.add_argument("--now", required=True, help="UTC ISO-8601 timestamp.")
    args = parser.parse_args(argv)

    store = MetricsStore.open_sqlite(str(args.database))
    migrated = store.upgrade()
    if args.command == "migrate":
        _write({"migrated": migrated, "database": str(args.database)})
        return 0
    if args.command == "ingest":
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        records = payload.get("records")
        if not isinstance(records, list):
            raise ValueError("input must contain a records list")
        outcomes = [store.ingest(_record(item)) for item in records]
        _write({"migrated": migrated, "ingested": [{"result_id": item.result_id, "reused": item.reused} for item in outcomes]})
        return 0
    deleted = store.apply_retention(now=_timestamp(args.now), retention=timedelta(days=args.days))
    _write({"migrated": migrated, "deleted": deleted, "retention_days": args.days})
    return 0


def _record(value: object) -> MetricRecord:
    if not isinstance(value, dict):
        raise ValueError("each record must be an object")
    return MetricRecord(
        result_id=_required(value, "result_id"), result_type=_required(value, "result_type"), status=_required(value, "status"),
        data_origin=_required(value, "data_origin"), window_start=_timestamp(_required(value, "window_start")),
        window_end=_timestamp(_required(value, "window_end")), computed_at=_timestamp(_required(value, "computed_at")),
        sample_size=_required(value, "sample_size"), label_coverage=value.get("label_coverage"),
        method_version=_required(value, "method_version"), config_version=_required(value, "config_version"),
        model_version=_required(value, "model_version"), baseline_id=value.get("baseline_id"), deployment_id=value.get("deployment_id"),
        summary=_required(value, "summary"), distribution=_required(value, "distribution"),
    )


def _required(value: dict[str, object], key: str):
    if key not in value:
        raise ValueError(f"record is missing {key}")
    return value[key]


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _write(value: dict[str, object]) -> None:
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"metrics-store error: {exc}", file=sys.stderr)
        raise SystemExit(2)
