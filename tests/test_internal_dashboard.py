"""M18 internal dashboard access and rendering contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
import sqlite3
import unittest

from telco_churn.metrics_store import MetricRecord, MetricsStore


FASTAPI_AVAILABLE = find_spec("fastapi") is not None
if FASTAPI_AVAILABLE:
    from fastapi.testclient import TestClient
    from telco_churn.internal_dashboard import create_internal_dashboard
    from telco_churn.api.app import create_app
    from telco_churn.api.service import PredictionService
    from telco_churn.settings import load_settings


UTC = timezone.utc
NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


@unittest.skipUnless(FASTAPI_AVAILABLE, "requires the locked FastAPI runtime")
class InternalDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.store = MetricsStore(self.connection)
        self.store.upgrade()
        self.client = TestClient(create_internal_dashboard(store=self.store, access_token="test-internal-token", now=lambda: NOW))

    def tearDown(self) -> None:
        self.connection.close()

    def test_dashboard_rejects_requests_without_internal_token(self) -> None:
        response = self.client.get("/internal/dashboard")

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("metric", response.text.lower())

    def test_dashboard_renders_lineage_distribution_and_explicit_evidence_state(self) -> None:
        self.store.ingest(MetricRecord(
            result_id="dashboard-monitoring", result_type="monitoring", status="not_available", data_origin="synthetic",
            window_start=NOW - timedelta(days=1), window_end=NOW, computed_at=NOW, sample_size=0, label_coverage=None,
            method_version="telco-churn-monitoring/v1", config_version="m14-candidate/v1", model_version="m6-logistic-v1",
            baseline_id="baseline-v1", deployment_id="deployment-local", summary={"reason": "labels_pending"},
            distribution={"tenure": {"baseline": [20, 30], "current": None}},
        ))

        response = self.client.get("/internal/dashboard", headers={"X-Internal-Metrics-Token": "test-internal-token"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Internal MLOps Metrics", response.text)
        self.assertIn("not_available", response.text)
        self.assertIn("m6-logistic-v1", response.text)
        self.assertIn("baseline-v1", response.text)
        self.assertIn("tenure", response.text)
        self.assertIn("Sample size", response.text)

    def test_dashboard_no_data_is_not_rendered_as_stable(self) -> None:
        response = self.client.get("/internal/dashboard", headers={"X-Internal-Metrics-Token": "test-internal-token"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("not_available", response.text)
        self.assertNotIn("Current evidence: <strong>stable</strong>", response.text)

    def test_dashboard_data_failure_does_not_affect_prediction_api_liveness(self) -> None:
        self.store.downgrade_for_test()
        dashboard = self.client.get("/internal/dashboard", headers={"X-Internal-Metrics-Token": "test-internal-token"})
        prediction = TestClient(create_app(service=PredictionService.unavailable(), settings=load_settings({}))).get("/health/live")

        self.assertEqual(dashboard.status_code, 503)
        self.assertEqual(prediction.status_code, 200)


if __name__ == "__main__":
    unittest.main()
