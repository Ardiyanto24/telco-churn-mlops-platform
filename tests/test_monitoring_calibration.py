"""M15 calibration configuration and controlled-scenario contracts."""

from __future__ import annotations

import unittest

import pandas as pd

from telco_churn.monitoring_calibration import (
    CalibrationConfig, build_monitoring_config, inject_categorical_shift,
    inject_missingness, inject_numeric_shift, score_calibration,
)


class MonitoringCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame({"tenure": list(range(100)), "Contract": ["Month-to-month"] * 50 + ["One year"] * 50})

    def test_config_identity_changes_when_a_calibrated_policy_changes(self) -> None:
        first = build_monitoring_config(CalibrationConfig())
        second = build_monitoring_config(CalibrationConfig(max_prediction_rows=20_000))

        self.assertEqual(first["status"], "candidate")
        self.assertNotEqual(first["monitoring_config_version"], second["monitoring_config_version"])
        self.assertEqual(first["minimum_sample_size"], 500)

    def test_controlled_shifts_are_seeded_and_preserve_unrelated_columns(self) -> None:
        numeric = inject_numeric_shift(self.frame, "tenure", shift=100)
        categorical = inject_categorical_shift(self.frame, "Contract", value="Two year", fraction=.4, seed=7)
        missing = inject_missingness(self.frame, "tenure", fraction=.2, seed=7)

        self.assertEqual(numeric["tenure"].iloc[0], 100)
        self.assertEqual(categorical["Contract"].eq("Two year").sum(), 40)
        self.assertEqual(missing["tenure"].isna().sum(), 20)
        self.assertTrue(categorical["tenure"].equals(self.frame["tenure"]))

    def test_calibration_score_enforces_false_positive_and_sensitivity_targets(self) -> None:
        accepted = score_calibration(
            stable_statuses=["stable"] * 20,
            material_statuses=["warning"] * 8 + ["stable"] * 2,
            detection_windows=[1] * 8,
            config=CalibrationConfig(),
        )
        rejected = score_calibration(
            stable_statuses=["warning"] * 2 + ["stable"] * 18,
            material_statuses=["warning"] * 7 + ["stable"] * 3,
            detection_windows=[3] * 7,
            config=CalibrationConfig(),
        )

        self.assertTrue(accepted["accepted"])
        self.assertFalse(rejected["accepted"])


if __name__ == "__main__":
    unittest.main()
