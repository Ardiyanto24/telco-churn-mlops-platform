"""Serve the separate local/demo M19 Public Metrics API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from telco_churn.metrics_store import MetricsStore
from telco_churn.public_api import create_public_api
from telco_churn.public_metrics import config_from_mapping


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "monitoring" / "m19-candidate-v1.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8019)
    args = parser.parse_args()
    config = config_from_mapping(json.loads(args.config.read_text(encoding="utf-8")))
    store = MetricsStore.open_sqlite(str(args.database))
    store.upgrade()
    uvicorn.run(create_public_api(store=store, config=config), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
