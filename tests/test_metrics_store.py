"""M18 internal aggregate metrics-store contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from telco_churn.metrics_store import MetricRecord, MetricsStore, MetricsStoreError


UTC = timezone.utc
NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


def _record(**overrides: object) -> MetricRecord:
    values: dict[str, object] = {
        "result_id": "monitoring-run-001",
        "result_type": "monitoring",
        "status": "stable",
        "data_origin": "synthetic",
        "window_start": NOW - timedelta(days=1),
        "window_end": NOW,
        "computed_at": NOW,
        "sample_size": 500,
        "label_coverage": None,
        "method_version": "telco-churn-monitoring/v1",
        "config_version": "m14-candidate/v1",
        "model_version": "m6-logistic-v1",
        "baseline_id": "baseline-v1",
        "deployment_id": "deployment-local",
        "summary": {"run_status": "stable"},
        "distribution": {"tenure": {"baseline": [20, 30], "current": [19, 31]}},
    }
    values.update(overrides)
    return MetricRecord(**values)


class MetricsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.store = MetricsStore(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_migrates_an_empty_database_and_records_version(self) -> None:
        self.assertEqual(self.store.upgrade(), ["0001"])
        self.assertEqual(self.store.upgrade(), [])
        tables = {row[0] for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"schema_migrations", "model_versions", "deployments", "metric_results", "monitoring_results", "performance_results", "telemetry_rollups", "alert_revisions", "public_snapshots"}.issubset(tables))
        self.store.downgrade_for_test()
        self.assertIsNone(self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metric_results'").fetchone())

    def test_retrying_the_same_aggregate_result_does_not_duplicate_rows(self) -> None:
        self.store.upgrade()
        first = self.store.ingest(_record())
        second = self.store.ingest(_record())

        self.assertFalse(first.reused)
        self.assertTrue(second.reused)
        self.assertEqual(self.store.count_results(), 1)
        self.assertEqual(self.store.count_results(result_type="monitoring"), 1)

    def test_rejects_raw_identifiers_and_payloads_before_storage(self) -> None:
        self.store.upgrade()
        with self.assertRaises(MetricsStoreError):
            self.store.ingest(_record(summary={"customer_id": "must-not-store"}))
        with self.assertRaises(MetricsStoreError):
            self.store.ingest(_record(distribution={"raw_payload": {"x": 1}}))
        self.assertEqual(self.store.count_results(), 0)

    def test_dashboard_snapshot_preserves_not_available_and_required_context(self) -> None:
        self.store.upgrade()
        self.store.ingest(_record(status="not_available", sample_size=0, distribution={"tenure": {"baseline": [20, 30], "current": None}}))

        snapshot = self.store.dashboard_snapshot(now=NOW + timedelta(hours=49), expected_interval=timedelta(days=1))

        self.assertEqual(snapshot["state"], "not_available")
        self.assertEqual(snapshot["freshness"]["state"], "stale")
        result = snapshot["results"][0]
        self.assertEqual(result["sample_size"], 0)
        self.assertEqual(result["model_version"], "m6-logistic-v1")
        self.assertEqual(result["baseline_id"], "baseline-v1")
        self.assertIn("tenure", result["distribution"])

    def test_retention_expires_eligible_results_without_removing_audit_lineage(self) -> None:
        self.store.upgrade()
        self.store.ingest(_record(window_start=NOW - timedelta(days=401), window_end=NOW - timedelta(days=400), computed_at=NOW - timedelta(days=400)))
        self.store.ingest(_record(result_id="recent", window_start=NOW - timedelta(days=1), window_end=NOW, computed_at=NOW))

        deleted = self.store.apply_retention(now=NOW, retention=timedelta(days=365))

        self.assertEqual(deleted, 1)
        self.assertEqual(self.store.count_results(), 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM deployments").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
