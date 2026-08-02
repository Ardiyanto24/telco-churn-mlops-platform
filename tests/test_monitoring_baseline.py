"""M13 immutable reference baseline tests."""

from __future__ import annotations

import unittest

from telco_churn.monitoring_baseline import BaselineError, build_baseline, validate_baseline


class _Manifest:
    model_version = "m13-test"
    schema_version = "v1"
    feature_order = ("tenure", "MonthlyCharges", "Contract")
    decision_threshold = 0.6
    low_risk_threshold = 0.3
    high_risk_threshold = 0.8


class _Bundle:
    manifest = _Manifest()

    def predict_probabilities(self, records):
        return [0.9 if record["tenure"] < 12 else 0.2 for record in records]


class MonitoringBaselineTests(unittest.TestCase):
    def _frame(self):
        import pandas as pd

        return pd.DataFrame({
            "id": ["a", "b", "c", "d"], "Churn": ["Yes", "No", "Yes", "No"],
            "tenure": [1, 12, 36, 60], "MonthlyCharges": [20.0, 50.0, 80.0, 110.0],
            "Contract": ["Month-to-month", "One year", "Two year", "Month-to-month"],
        })

    def test_same_reference_inputs_produce_identical_immutable_baseline(self) -> None:
        first = build_baseline(self._frame(), dataset_manifest={"sha256": "a" * 64}, bundle=_Bundle())
        second = build_baseline(self._frame(), dataset_manifest={"sha256": "a" * 64}, bundle=_Bundle())

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "provisional")
        self.assertNotIn("id", first["input_reference"]["features"])
        self.assertIn("probability", first["prediction_reference"])
        self.assertEqual(first["sha256"], first["baseline_id"])

    def test_incompatible_model_or_feature_contract_fails_closed(self) -> None:
        baseline = build_baseline(self._frame(), dataset_manifest={"sha256": "a" * 64}, bundle=_Bundle())

        with self.assertRaises(BaselineError):
            validate_baseline(baseline, model_version="other", schema_version="v1", feature_order=_Manifest.feature_order)
        with self.assertRaises(BaselineError):
            validate_baseline(baseline, model_version="m13-test", schema_version="v1", feature_order=("tenure",))

