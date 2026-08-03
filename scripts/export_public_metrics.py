"""Build one M19 sanitised public snapshot from the private aggregate store."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from telco_churn.metrics_store import MetricsStore
from telco_churn.public_metrics import PublicMetricsError, config_from_mapping, export_public_snapshot


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "monitoring" / "m19-candidate-v1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="M18 SQLite database path for local/candidate operation.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--now", required=True, help="UTC ISO-8601 calculation timestamp.")
    args = parser.parse_args(argv)
    config = config_from_mapping(json.loads(args.config.read_text(encoding="utf-8")))
    store = MetricsStore.open_sqlite(str(args.database))
    store.upgrade()
    snapshot = export_public_snapshot(store=store, config=config, now=_timestamp(args.now))
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "schema_version": snapshot["schema_version"], "freshness": snapshot["freshness"]}, sort_keys=True))
    return 0


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, PublicMetricsError) as exc:
        print(f"public-metrics error: {exc}", file=sys.stderr)
        raise SystemExit(2)
