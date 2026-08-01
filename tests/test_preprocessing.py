"""Contract tests for the stable preprocessing module path."""

import unittest

import pandas as pd

from telco_churn.preprocessing import FeatureEngineer, PreprocessingPipeline


class FeatureEngineerTests(unittest.TestCase):
    def test_creates_expected_domain_features(self) -> None:
        source = pd.DataFrame(
            [
                {
                    "tenure": 2,
                    "MonthlyCharges": 50.0,
                    "TotalCharges": "",
                    "PaymentMethod": "Credit card (automatic)",
                    "OnlineSecurity": "Yes",
                    "OnlineBackup": "No",
                    "DeviceProtection": "Yes",
                }
            ]
        )

        transformed = FeatureEngineer().fit_transform(source)

        self.assertEqual(transformed.loc[0, "tc_residual"], 0.0)
        self.assertAlmostEqual(transformed.loc[0, "monthly_to_total_ratio"], 0.5)
        self.assertEqual(transformed.loc[0, "tenure_group"], "G1_0_2")
        self.assertEqual(transformed.loc[0, "is_auto_payment"], 1)
        self.assertEqual(transformed.loc[0, "service_count"], 2)
        self.assertEqual(transformed.loc[0, "has_any_addon"], 1)

    def test_custom_transformers_have_a_stable_package_module_path(self) -> None:
        self.assertEqual(FeatureEngineer.__module__, "telco_churn.preprocessing")
        self.assertEqual(PreprocessingPipeline.__module__, "telco_churn.preprocessing")


if __name__ == "__main__":
    unittest.main()
