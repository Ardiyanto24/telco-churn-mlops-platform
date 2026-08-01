"""Contract tests for the versioned prediction API."""

from __future__ import annotations

import unittest
import json
from importlib.util import find_spec
from pathlib import Path

FASTAPI_AVAILABLE = find_spec("fastapi") is not None

if FASTAPI_AVAILABLE:
    from fastapi.testclient import TestClient

    from telco_churn.api.app import create_app
    from telco_churn.api.service import PredictionService
    from telco_churn.settings import load_settings


VALID_CUSTOMER = {
    "customer_id": "API-0001",
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
class PredictionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        service = PredictionService(
            predict_probabilities=lambda records: [0.8411 for _ in records],
            model_version="legacy-m0-compatible",
        )
        self.client = TestClient(create_app(service=service, settings=load_settings({})))

    def test_predicts_one_valid_customer_with_versioned_response(self) -> None:
        response = self.client.post("/v1/predict", json={"inputs": [VALID_CUSTOMER]})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(payload["model_version"], "legacy-m0-compatible")
        self.assertEqual(payload["summary"]["total_customers"], 1)
        self.assertEqual(payload["summary"]["predicted_churn"], 1)
        self.assertEqual(payload["results"][0]["customer_id"], "API-0001")
        self.assertEqual(payload["results"][0]["churn_binary"], 1)
        self.assertEqual(payload["results"][0]["risk_level"], "HIGH")
        self.assertEqual(payload["decision_threshold"], 0.6238)
        self.assertTrue(payload["request_id"])
        self.assertTrue(payload["timestamp_utc"].endswith("Z"))

    def test_predicts_a_batch_with_one_result_per_customer(self) -> None:
        second_customer = {**VALID_CUSTOMER, "customer_id": "API-0002", "tenure": 0}

        response = self.client.post(
            "/v1/predict", json={"inputs": [VALID_CUSTOMER, second_customer]}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["total_customers"], 2)
        self.assertEqual(len(response.json()["results"]), 2)

    def test_rejects_missing_fields_with_stable_validation_error(self) -> None:
        invalid_customer = dict(VALID_CUSTOMER)
        invalid_customer.pop("monthly_charges")

        response = self.client.post("/v1/predict", json={"inputs": [invalid_customer]})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertNotIn("traceback", str(response.json()).lower())

    def test_rejects_unknown_categories_with_stable_validation_error(self) -> None:
        invalid_customer = {**VALID_CUSTOMER, "contract": "Lifetime"}

        response = self.client.post("/v1/predict", json={"inputs": [invalid_customer]})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_rejects_empty_and_over_limit_batches_deterministically(self) -> None:
        empty_response = self.client.post("/v1/predict", json={"inputs": []})
        oversized_response = self.client.post(
            "/v1/predict", json={"inputs": [VALID_CUSTOMER] * 101}
        )

        self.assertEqual(empty_response.status_code, 422)
        self.assertEqual(oversized_response.status_code, 422)
        self.assertEqual(empty_response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(oversized_response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_liveness_does_not_depend_on_prediction_readiness(self) -> None:
        unavailable_client = TestClient(
            create_app(service=PredictionService.unavailable(), settings=load_settings({}))
        )

        self.assertEqual(unavailable_client.get("/health/live").status_code, 200)
        self.assertEqual(unavailable_client.get("/health/ready").status_code, 503)
        self.assertEqual(
            unavailable_client.get("/health/ready").json()["error"]["code"],
            "MODEL_NOT_READY",
        )

    def test_version_endpoint_exposes_only_public_version_metadata(self) -> None:
        response = self.client.get("/version")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schema_version"], "v1")
        self.assertEqual(response.json()["model_version"], "legacy-m0-compatible")
        self.assertNotIn("artifact", response.text.lower())

    def test_internal_failures_return_a_generic_stable_error(self) -> None:
        failing_service = PredictionService(
            predict_probabilities=lambda records: (_ for _ in ()).throw(RuntimeError("secret")),
            model_version="test-model",
        )
        client = TestClient(
            create_app(service=failing_service, settings=load_settings({})),
            raise_server_exceptions=False,
        )

        response = client.post("/v1/predict", json={"inputs": [VALID_CUSTOMER]})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("secret", response.text)

    def test_openapi_documents_versioned_prediction_and_error_contracts(self) -> None:
        schema = self.client.get("/openapi.json").json()
        snapshot_path = Path("tests/expected/openapi_v1_snapshot.json")
        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        actual = {
            "info": schema["info"],
            "paths": {
                path: {
                    method: {"responses": sorted(operation["responses"])}
                    for method, operation in methods.items()
                }
                for path, methods in schema["paths"].items()
            },
        }

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
