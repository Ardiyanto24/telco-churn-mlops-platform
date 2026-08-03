"""Run the separately hosted, read-only M18 internal dashboard."""

from __future__ import annotations

import argparse
from datetime import timedelta
import os
from pathlib import Path

import uvicorn

from telco_churn.internal_dashboard import create_internal_dashboard
from telco_churn.metrics_store import MetricsStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8018)
    parser.add_argument("--expected-interval-hours", type=int, default=24)
    args = parser.parse_args()
    if args.expected_interval_hours < 1:
        parser.error("--expected-interval-hours must be at least one")
    token = os.environ.get("TELCO_CHURN_INTERNAL_DASHBOARD_TOKEN")
    if not token:
        parser.error("TELCO_CHURN_INTERNAL_DASHBOARD_TOKEN is required")
    store = MetricsStore.open_sqlite(str(args.database))
    app = create_internal_dashboard(store=store, access_token=token, expected_interval=timedelta(hours=args.expected_interval_hours))
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
