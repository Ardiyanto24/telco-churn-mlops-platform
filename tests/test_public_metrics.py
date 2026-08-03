"""M19 public snapshot sanitisation and read-only API contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
import sqlite3
import unittest

from telco_churn.metrics_store import MetricRecord, MetricsStore
from telco_churn.public_metrics import PublicMetricsConfig, PublicMetricsError, config_from_mapping, export_public_snapshot


UTC = timezone.utc
NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)
FASTAPI_AVAILABLE = find_spec("fastapi") is not None

if FASTAPI_AVAILABLE:
    from fastapi.testclient import TestClient
    from telco_churn.public_api import create_public_api


def _record(**overrides: object) -> MetricRecord:
    values: dict[str, object] = {
        "result_id": "public-monitoring-001", "result_type": "monitoring", "status": "stable", "data_origin": "replayed",
        "window_start": NOW - timedelta(days=1), "window_end": NOW, "computed_at": NOW, "sample_size": 500,
        "label_coverage": None, "method_version": "monitoring/v1", "config_version": "m14-candidate/v1",
        "model_version": "m6-logistic-v1", "baseline_id": "baseline-internal", "deployment_id": "deployment-local",
        "summary": {"drifted_feature_count": 0, "internal_note": "must not be public"}, "distribution": {"tenure": {"baseline": [1, 2]}},
    }
    values.update(overrides)
    return MetricRecord(**values)


class PublicMetricsExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.store = MetricsStore(self.connection)
        self.store.upgrade()
        self.config = PublicMetricsConfig(allowed_origins=("https://dashboard.example",), minimum_group_size=100)

    def tearDown(self) -> None:
        self.connection.close()

    def test_exporter_uses_allowlist_and_keeps_candidate_origin_visible(self) -> None:
        self.store.ingest(_record())

        snapshot = export_public_snapshot(store=self.store, config=self.config, now=NOW)
        encoded = str(snapshot)

        self.assertEqual(snapshot["schema_version"], "public_metrics/v1")
        self.assertEqual(snapshot["overview"]["data_origins"], ["replayed"])
        self.assertEqual(snapshot["monitoring"]["history"][0]["metrics"], {"drifted_feature_count": 0})
        self.assertNotIn("baseline-internal", encoded)
        self.assertNotIn("deployment-local", encoded)
        self.assertNotIn("internal_note", encoded)
        self.assertNotIn("tenure", encoded)

    def test_small_group_is_suppressed_without_a_count_or_metric_value(self) -> None:
        self.store.ingest(_record(sample_size=99))

        snapshot = export_public_snapshot(store=self.store, config=self.config, now=NOW)
        result = snapshot["monitoring"]["history"][0]

        self.assertEqual(result, {"data_origin": "replayed", "evidence_state": "suppressed", "result_type": "monitoring", "suppression_reason": "minimum_group_size"})

    def test_failed_export_keeps_last_snapshot_but_marks_it_stale(self) -> None:
        self.store.ingest(_record())
        successful = export_public_snapshot(store=self.store, config=self.config, now=NOW)
        stale = export_public_snapshot(
            store=self.store, config=self.config, now=NOW + timedelta(minutes=1),
            source_loader=lambda: (_ for _ in ()).throw(RuntimeError("source unavailable")),
        )

        self.assertEqual(stale["snapshot_id"], successful["snapshot_id"])
        self.assertEqual(stale["freshness"]["state"], "stale")
        self.assertEqual(stale["freshness"]["reason"], "export_failed")

    def test_exporter_bounds_each_public_history_to_100_results(self) -> None:
        self.store.ingest(_record())
        source = self.store.public_source_records()[0]
        rows = [{**source, "result_id": f"monitoring-{index:03d}"} for index in range(101)]

        snapshot = export_public_snapshot(store=self.store, config=self.config, now=NOW, source_loader=lambda: rows)

        self.assertEqual(len(snapshot["monitoring"]["history"]), 100)

    def test_config_rejects_non_boolean_candidate_mode(self) -> None:
        with self.assertRaises(PublicMetricsError):
            config_from_mapping({"allowed_origins": ["https://dashboard.example"], "candidate_mode": "yes"})


@unittest.skipUnless(FASTAPI_AVAILABLE, "requires the locked FastAPI runtime")
class PublicMetricsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.store = MetricsStore(self.connection)
        self.store.upgrade()
        config = PublicMetricsConfig(allowed_origins=("https://dashboard.example",), minimum_group_size=100, rate_limit_per_minute=2)
        self.store.ingest(_record(result_type="telemetry", summary={"request_count": 500, "success_rate": 0.99}))
        export_public_snapshot(store=self.store, config=config, now=NOW)
        self.client = TestClient(create_public_api(store=self.store, config=config, now=lambda: NOW))

    def tearDown(self) -> None:
        self.connection.close()

    def test_public_api_is_read_only_and_has_safe_cors_cache_and_contract_headers(self) -> None:
        response = self.client.get("/public/v1/overview", headers={"Origin": "https://dashboard.example"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://dashboard.example")
        self.assertIn("max-age=300", response.headers["cache-control"])
        self.assertIn("etag", response.headers)
        self.assertEqual(response.json()["schema_version"], "public_metrics/v1")
        self.assertEqual(self.client.post("/public/v1/overview").status_code, 405)
        self.assertEqual(self.client.get("/public/v1/overview", headers={"Origin": "https://untrusted.example"}).headers.get("access-control-allow-origin"), None)

    def test_rate_limit_returns_retry_after_without_leaking_error_details(self) -> None:
        self.client.get("/public/v1/overview")
        self.client.get("/public/v1/overview")
        limited = self.client.get("/public/v1/overview")

        self.assertEqual(limited.status_code, 429)
        self.assertIn("retry-after", limited.headers)
        self.assertEqual(limited.headers["x-content-type-options"], "nosniff")
        self.assertEqual(limited.json(), {"error": {"code": "RATE_LIMITED", "message": "Too many requests."}})


if __name__ == "__main__":
    unittest.main()
