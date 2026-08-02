import unittest
from unittest.mock import patch
from pathlib import Path

from telco_churn.settings import SettingsError, load_settings, risk_bands_for_threshold


class SettingsTests(unittest.TestCase):
    def test_uses_safe_development_defaults(self):
        settings = load_settings({})

        self.assertEqual(settings.artifact_dir, Path("artifacts"))
        self.assertEqual(settings.model_filename, "model_final.joblib")
        self.assertEqual(settings.preprocessor_filename, "preprocessor.joblib")
        self.assertEqual(settings.decision_threshold, 0.6238)
        self.assertEqual(settings.low_risk_threshold, 0.35)
        self.assertEqual(settings.high_risk_threshold, 0.75)

    def test_accepts_environment_overrides(self):
        settings = load_settings(
            {
                "TELCO_CHURN_ARTIFACT_DIR": "runtime-artifacts",
                "TELCO_CHURN_DECISION_THRESHOLD": "0.65",
                "TELCO_CHURN_LOW_RISK_THRESHOLD": "0.45",
                "TELCO_CHURN_HIGH_RISK_THRESHOLD": "0.85",
            }
        )

        self.assertEqual(settings.artifact_dir, Path("runtime-artifacts"))
        self.assertEqual(settings.decision_threshold, 0.65)
        self.assertEqual(settings.low_risk_threshold, 0.45)
        self.assertEqual(settings.high_risk_threshold, 0.85)

    def test_accepts_m9_verified_bundle_directory_override(self):
        settings = load_settings({"TELCO_CHURN_BUNDLE_DIR": "/opt/telco-churn/model"})

        self.assertEqual(settings.artifact_dir, Path("/opt/telco-churn/model"))

    def test_reads_process_environment_when_no_mapping_is_supplied(self):
        with patch.dict(
            "os.environ", {"TELCO_CHURN_DECISION_THRESHOLD": "0.65"}, clear=True
        ):
            settings = load_settings()

        self.assertEqual(settings.decision_threshold, 0.65)

    def test_rejects_non_numeric_threshold(self):
        with self.assertRaisesRegex(SettingsError, "DECISION_THRESHOLD"):
            load_settings({"TELCO_CHURN_DECISION_THRESHOLD": "not-a-number"})

    def test_rejects_threshold_outside_risk_band(self):
        with self.assertRaisesRegex(SettingsError, "between"):
            load_settings({"TELCO_CHURN_DECISION_THRESHOLD": "0.9"})

    def test_derives_ordered_candidate_risk_bands_from_a_selected_threshold(self):
        self.assertEqual(risk_bands_for_threshold(0.9), (0.7, 1.0))
