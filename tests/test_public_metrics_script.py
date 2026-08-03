"""M19 public-export command boundary contract."""

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
MANAGE = ROOT / "scripts" / "manage_metrics_store.py"
EXPORT = ROOT / "scripts" / "export_public_metrics.py"


class PublicMetricsScriptTests(unittest.TestCase):
    def test_export_command_publishes_a_versioned_snapshot_without_exposing_input_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            database = temporary / "metrics.db"
            source = temporary / "records.json"
            source.write_text(json.dumps({"records": [_record()]}), encoding="utf-8")
            ingested = _run([str(MANAGE), "--database", str(database), "ingest", "--input", str(source)])
            exported = _run([str(EXPORT), "--database", str(database), "--now", NOW.isoformat()])

        self.assertEqual(ingested.returncode, 0, ingested.stderr)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        output = json.loads(exported.stdout)
        self.assertEqual(output["schema_version"], "public_metrics/v1")
        self.assertEqual(output["freshness"]["state"], "fresh")
        self.assertNotIn("internal_note", exported.stdout)


def _run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *arguments], cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True, check=False)


def _record() -> dict[str, object]:
    return {
        "result_id": "public-script-001", "result_type": "monitoring", "status": "stable", "data_origin": "replayed",
        "window_start": (NOW - timedelta(days=1)).isoformat(), "window_end": NOW.isoformat(), "computed_at": NOW.isoformat(),
        "sample_size": 500, "label_coverage": None, "method_version": "monitoring/v1", "config_version": "m19-candidate/v1",
        "model_version": "m6-logistic-v1", "baseline_id": "baseline-v1", "deployment_id": "local",
        "summary": {"drifted_feature_count": 0, "internal_note": "not public"}, "distribution": {},
    }


if __name__ == "__main__":
    unittest.main()
