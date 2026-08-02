"""M12 telemetry contract tests."""

from __future__ import annotations

import json
import unittest
from importlib.util import find_spec


FASTAPI_AVAILABLE = find_spec("fastapi") is not None

from telco_churn.telemetry import ServiceMetrics, TelemetryEmitter, pseudonymous_entity_key

if FASTAPI_AVAILABLE:
    from fastapi.testclient import TestClient

    from telco_churn.api.app import create_app
    from telco_churn.api.service import PredictionService
    from telco_churn.settings import load_settings


VALID_CUSTOMER = {
    "customer_id": "CUSTOMER-SECRET-001",
    "gender": "Female",
    "senior_citizen": 0,
    "partner": "Yes",
    "dependents": "No",
    "tenure": 1,
    "phone_service": "No",
    "multiple_lines": "No phone service",
    "internet_service": "DSL",
    "online_security": "No",
    "online_backup": "Yes",
    "device_protection": "No",
    "tech_support": "No",
    "streaming_tv": "No",
    "streaming_movies": "No",
    "contract": "Month-to-month",
    "paperless_billing": "Yes",
    "payment_method": "Electronic check",
    "monthly_charges": 29.85,
    "total_charges": 29.85,
}


@unittest.skipUnless(FASTAPI_AVAILABLE, "requires the locked M2 runtime (FastAPI)")
class TelemetryApiTests(unittest.TestCase):
    def _client(self, sink):
        service = PredictionService(
            predict_probabilities=lambda records: [0.8411 for _ in records],
            model_version="telemetry-test-model",
        )
        emitter = TelemetryEmitter(sink=sink)
        app = create_app(service=service, settings=load_settings({}), telemetry=emitter)
        return TestClient(app), emitter

    def test_success_event_is_correlated_parseable_and_minimised(self) -> None:
        lines: list[str] = []
        client, emitter = self._client(lines.append)

        response = client.post("/v1/predict", json={"inputs": [VALID_CUSTOMER]})
        emitter.flush()

        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in lines]
        prediction = next(event for event in events if event["event_name"] == "prediction_completed")
        self.assertEqual(prediction["request_id"], response.json()["request_id"])
        self.assertEqual(prediction["model_version"], "telemetry-test-model")
        self.assertEqual(prediction["schema_version"], "v1")
        self.assertEqual(prediction["batch_size"], 1)
        self.assertIn("request_latency_ms", prediction)
        self.assertIn("inference_latency_ms", prediction)
        self.assertNotIn("customer_id", prediction)
        serialised = json.dumps(events)
        self.assertNotIn("CUSTOMER-SECRET-001", serialised)
        self.assertNotIn('"inputs"', serialised)

    def test_invalid_request_uses_one_correlation_id_for_response_and_error_event(self) -> None:
        lines: list[str] = []
        client, emitter = self._client(lines.append)

        response = client.post("/v1/predict", json={"inputs": []})
        emitter.flush()

        self.assertEqual(response.status_code, 422)
        events = [json.loads(line) for line in lines]
        failed = next(event for event in events if event["event_name"] == "request_failed")
        self.assertEqual(failed["request_id"], response.json()["request_id"])
        self.assertEqual(failed["error_code"], "VALIDATION_ERROR")

    def test_valid_w3c_traceparent_is_preserved_in_prediction_event(self) -> None:
        lines: list[str] = []
        client, emitter = self._client(lines.append)
        trace_id = "0af7651916cd43dd8448eb211c80319c"

        response = client.post(
            "/v1/predict",
            json={"inputs": [VALID_CUSTOMER]},
            headers={"traceparent": f"00-{trace_id}-b7ad6b7169203331-01"},
        )
        emitter.flush()

        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in lines]
        prediction = next(event for event in events if event["event_name"] == "prediction_completed")
        self.assertEqual(prediction["trace_id"], trace_id)

    def test_sink_failure_does_not_fail_prediction_and_is_counted(self) -> None:
        def broken_sink(_: str) -> None:
            raise OSError("simulated sink failure")

        client, emitter = self._client(broken_sink)

        response = client.post("/v1/predict", json={"inputs": [VALID_CUSTOMER]})
        emitter.flush()

        self.assertEqual(response.status_code, 200)
        self.assertGreater(emitter.metrics.value("telemetry_write_failures_total"), 0)


class TelemetryUnitTests(unittest.TestCase):
    def test_metrics_render_latency_histogram_buckets(self) -> None:
        metrics = ServiceMetrics()
        metrics.observe_latency("request_latency_ms", 12.5)

        rendered = metrics.render_openmetrics()

        self.assertIn("request_latency_ms_count 1", rendered)
        self.assertIn('request_latency_ms_bucket{le="25"} 1', rendered)

    def test_sink_failure_emits_one_safe_non_recursive_fallback_event(self) -> None:
        fallback_lines: list[str] = []
        emitter = TelemetryEmitter(
            sink=lambda _: (_ for _ in ()).throw(OSError("sink unavailable")),
            failure_sink=fallback_lines.append,
        )

        emitter.emit("prediction_completed", request_id="request-123", customer_id="must-not-leak")
        emitter.flush()

        self.assertEqual(emitter.metrics.value("telemetry_write_failures_total"), 1)
        fallback = json.loads(fallback_lines[0])
        self.assertEqual(fallback["event_name"], "telemetry_write_failed")
        self.assertEqual(fallback["failed_event_name"], "prediction_completed")
        self.assertNotIn("must-not-leak", json.dumps(fallback))

    def test_hmac_entity_key_is_stable_without_retaining_source_identifier(self) -> None:
        key = pseudonymous_entity_key("opaque-id-123", secret=b"test-secret", key_id="k1")

        self.assertEqual(key["key_id"], "k1")
        self.assertNotIn("opaque-id-123", key["entity_key"])
        self.assertEqual(key, pseudonymous_entity_key("opaque-id-123", secret=b"test-secret", key_id="k1"))


if __name__ == "__main__":
    unittest.main()
