"""M18 metrics-store command-line boundary contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


UTC = timezone.utc
NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "manage_metrics_store.py"


class MetricsStoreScriptTests(unittest.TestCase):
    def test_ingests_a_safe_aggregate_record_and_reports_idempotent_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            database = temporary / "metrics.db"
            source = temporary / "records.json"
            source.write_text(json.dumps({"records": [_record()]}), encoding="utf-8")
            first = _run(database, source)
            second = _run(database, source)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertFalse(json.loads(first.stdout)["ingested"][0]["reused"])
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue(json.loads(second.stdout)["ingested"][0]["reused"])

    def test_rejects_customer_identifier_before_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            database = temporary / "metrics.db"
            source = temporary / "unsafe.json"
            payload = _record()
            payload["summary"] = {"customer_id": "forbidden"}
            source.write_text(json.dumps({"records": [payload]}), encoding="utf-8")
            result = _run(database, source)

        self.assertEqual(result.returncode, 2)
        self.assertIn("forbidden", result.stderr)


def _run(database: Path, source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--database", str(database), "ingest", "--input", str(source)],
        cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True, check=False,
    )


def _record() -> dict[str, object]:
    return {
        "result_id": "script-run-001", "result_type": "monitoring", "status": "stable", "data_origin": "synthetic",
        "window_start": (NOW - timedelta(days=1)).isoformat(), "window_end": NOW.isoformat(), "computed_at": NOW.isoformat(),
        "sample_size": 10, "label_coverage": None, "method_version": "telco-churn-monitoring/v1", "config_version": "m18-candidate/v1",
        "model_version": "m6-logistic-v1", "baseline_id": "baseline-v1", "deployment_id": "local", "summary": {"status": "stable"}, "distribution": {},
    }


if __name__ == "__main__":
    unittest.main()
