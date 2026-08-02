"""M14 batch monitoring contract tests using controlled synthetic windows."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from telco_churn.monitoring_baseline import build_baseline
from telco_churn.monitoring_engine import MonitoringConfig, run_monitoring


class _Manifest:
    model_version = "m14-test"
    schema_version = "v1"
    feature_order = ("tenure", "MonthlyCharges", "Contract")
    decision_threshold = 0.55
    low_risk_threshold = 0.2
    high_risk_threshold = 0.7


class _Bundle:
    manifest = _Manifest()

    def predict_probabilities(self, records):
        return [0.9 if record["tenure"] < 12 else 0.2 for record in records]


class MonitoringEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = pd.DataFrame({
            "id": [f"ref-{index}" for index in range(40)],
            "Churn": ["No"] * 40,
            "tenure": list(range(1, 41)),
            "MonthlyCharges": [float(20 + index) for index in range(40)],
            "Contract": ["Month-to-month"] * 20 + ["One year"] * 20,
        })
        self.baseline = build_baseline(
            self.reference, dataset_manifest={"sha256": "a" * 64}, bundle=_Bundle(),
        )
        self.config = MonitoringConfig(minimum_sample_size=10)

    def test_identical_window_is_stable_and_records_auditable_methods(self) -> None:
        result = run_monitoring(
            self.reference, baseline=self.baseline, bundle=_Bundle(), config=self.config,
            current_window={"sha256": "b" * 64, "source_period": "synthetic-identical"},
        )

        self.assertEqual(result["run_status"], "stable")
        self.assertEqual(result["config"]["status"], "experimental")
        tenure = result["feature_results"]["tenure"]
        self.assertAlmostEqual(tenure["distribution"]["psi"]["effect_size"], 0.0)
        self.assertEqual(tenure["distribution"]["ks"]["status"], "not_applicable")
        self.assertIn("baseline_id", result["lineage"])
        self.assertIn("prediction", result)
        self.assertEqual(result["prediction"]["risk_band_counts"]["LOW"], 29)

    def test_controlled_numeric_and_categorical_shifts_are_detected(self) -> None:
        shifted = self.reference.copy()
        shifted["tenure"] = shifted["tenure"] + 200
        shifted["Contract"] = "Two year"

        result = run_monitoring(
            shifted, baseline=self.baseline, bundle=_Bundle(), config=self.config,
            current_window={"sha256": "c" * 64, "source_period": "synthetic-shift"},
        )

        self.assertIn(result["feature_results"]["tenure"]["status"], {"warning", "critical"})
        self.assertGreater(result["feature_results"]["tenure"]["distribution"]["psi"]["effect_size"], 0.2)
        self.assertGreater(result["feature_results"]["Contract"]["distribution"]["jensen_shannon"]["effect_size"], 0.1)

    def test_missing_and_unknown_categories_are_quality_findings(self) -> None:
        degraded = self.reference.copy()
        degraded.loc[:9, "MonthlyCharges"] = None
        degraded.loc[:9, "Contract"] = "New contract"

        result = run_monitoring(
            degraded, baseline=self.baseline, bundle=_Bundle(), config=self.config,
            current_window={"sha256": "d" * 64, "source_period": "synthetic-quality"},
        )

        charges = result["feature_results"]["MonthlyCharges"]
        contract = result["feature_results"]["Contract"]
        self.assertGreater(charges["quality"]["missing_rate"], 0.0)
        self.assertGreater(contract["quality"]["unknown_rate"], 0.0)
        self.assertIn(charges["quality"]["status"], {"warning", "critical"})

    def test_small_window_is_insufficient_and_incompatible_baseline_is_unknown(self) -> None:
        small = self.reference.head(2)
        insufficient = run_monitoring(
            small, baseline=self.baseline, bundle=_Bundle(), config=self.config,
            current_window={"sha256": "e" * 64, "source_period": "synthetic-small"},
        )
        self.assertEqual(insufficient["run_status"], "insufficient_data")

        incompatible = {**self.baseline, "lineage": {**self.baseline["lineage"], "model_version": "other"}}
        unknown = run_monitoring(
            self.reference, baseline=incompatible, bundle=_Bundle(), config=self.config,
            current_window={"sha256": "f" * 64, "source_period": "synthetic-failure"},
        )
        self.assertEqual(unknown["run_status"], "unknown")
        self.assertEqual(unknown["error"]["classification"], "baseline_incompatible")

    def test_unsupported_current_column_fails_closed(self) -> None:
        window = self.reference.assign(unexpected_metadata="not-approved")
        result = run_monitoring(
            window, baseline=self.baseline, bundle=_Bundle(), config=self.config,
            current_window={"sha256": "9" * 64, "source_period": "synthetic-extra-column"},
        )

        self.assertEqual(result["run_status"], "unknown")
        self.assertEqual(result["error"]["classification"], "current_window_incompatible")

    def test_equivalent_retry_reuses_the_same_persisted_run(self) -> None:
        window = {"sha256": "1" * 64, "source_period": "synthetic-retry"}
        with tempfile.TemporaryDirectory() as directory:
            first = run_monitoring(
                self.reference, baseline=self.baseline, bundle=_Bundle(), config=self.config,
                current_window=window, output_dir=Path(directory),
            )
            second = run_monitoring(
                self.reference, baseline=self.baseline, bundle=_Bundle(), config=self.config,
                current_window=window, output_dir=Path(directory),
            )

        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertTrue(second["reused"])

    def test_changed_monitoring_configuration_does_not_reuse_a_prior_run(self) -> None:
        window = {"sha256": "2" * 64, "source_period": "synthetic-config-change"}
        with tempfile.TemporaryDirectory() as directory:
            first = run_monitoring(
                self.reference, baseline=self.baseline, bundle=_Bundle(), config=MonitoringConfig(minimum_sample_size=10),
                current_window=window, output_dir=Path(directory),
            )
            second = run_monitoring(
                self.reference, baseline=self.baseline, bundle=_Bundle(), config=MonitoringConfig(minimum_sample_size=50),
                current_window=window, output_dir=Path(directory),
            )

        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(second["run_status"], "insufficient_data")

    def test_prediction_drift_uses_a_deterministic_bounded_sample(self) -> None:
        config = MonitoringConfig(minimum_sample_size=10, max_prediction_rows=10)
        window = {"sha256": "3" * 64, "source_period": "synthetic-prediction-sample"}
        first = run_monitoring(self.reference, baseline=self.baseline, bundle=_Bundle(), config=config, current_window=window)
        second = run_monitoring(self.reference, baseline=self.baseline, bundle=_Bundle(), config=config, current_window=window)

        self.assertEqual(first["prediction"]["probability"]["psi"]["sample_size"], 10)
        self.assertEqual(first["prediction"], second["prediction"])


if __name__ == "__main__":
    unittest.main()
