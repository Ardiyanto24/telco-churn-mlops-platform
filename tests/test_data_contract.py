"""Behavioral tests for the M5 training-data contract and lineage manifest."""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys
import unittest


if find_spec("pandas"):
    import pandas as pd


@unittest.skipUnless(find_spec("pandas"), "requires pandas")
class DataContractTests(unittest.TestCase):
    def _valid_frame(self):
        return pd.DataFrame(
            [{
                "id": "DEMO-0001", "gender": "Female", "SeniorCitizen": 0,
                "Partner": "Yes", "Dependents": "No", "tenure": 1,
                "PhoneService": "No", "MultipleLines": "No phone service",
                "InternetService": "DSL", "OnlineSecurity": "No", "OnlineBackup": "Yes",
                "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "No",
                "StreamingMovies": "No", "Contract": "Month-to-month",
                "PaperlessBilling": "Yes", "PaymentMethod": "Electronic check",
                "MonthlyCharges": 29.85, "TotalCharges": 29.85, "Churn": "No",
            }]
        )

    def test_validates_canonical_training_data_and_returns_a_report(self) -> None:
        from telco_churn.data_contract import validate_training_data

        validated, report = validate_training_data(self._valid_frame())

        self.assertEqual(validated.shape, (1, 21))
        self.assertEqual(report.schema_version, "telco-churn-training/v1")
        self.assertEqual(report.row_count, 1)

    def test_rejects_missing_required_column(self) -> None:
        from telco_churn.data_contract import DataContractError, validate_training_data

        with self.assertRaisesRegex(DataContractError, "MonthlyCharges"):
            validate_training_data(self._valid_frame().drop(columns="MonthlyCharges"))

    def test_rejects_unknown_category_and_duplicate_id(self) -> None:
        from telco_churn.data_contract import DataContractError, validate_training_data

        invalid = pd.concat([self._valid_frame(), self._valid_frame()], ignore_index=True)
        invalid.loc[0, "Contract"] = "Two-year-ish"
        with self.assertRaises(DataContractError) as captured:
            validate_training_data(invalid)

        self.assertIn("Contract", str(captured.exception))
        self.assertIn("id", str(captured.exception))

    def test_rejects_inconsistent_phone_and_internet_services(self) -> None:
        from telco_churn.data_contract import DataContractError, validate_training_data

        invalid = self._valid_frame()
        invalid.loc[0, "MultipleLines"] = "Yes"
        invalid.loc[0, "InternetService"] = "No"
        with self.assertRaisesRegex(DataContractError, "cross-field"):
            validate_training_data(invalid)

    def test_manifest_checksum_changes_when_dataset_changes(self) -> None:
        from telco_churn.data_contract import build_dataset_manifest
        from tests.support import temporary_workspace

        with temporary_workspace() as workspace:
            first = workspace / "first.csv"
            second = workspace / "second.csv"
            self._valid_frame().to_csv(first, index=False)
            altered = self._valid_frame()
            altered.loc[0, "Churn"] = "Yes"
            altered.to_csv(second, index=False)

            first_manifest = build_dataset_manifest(first, code_revision="abc123")
            second_manifest = build_dataset_manifest(second, code_revision="abc123")

        self.assertNotEqual(first_manifest.sha256, second_manifest.sha256)
        self.assertEqual(first_manifest.code_revision, "abc123")

    def test_verified_dataset_load_refuses_unvalidated_or_tampered_data(self) -> None:
        from telco_churn.data_contract import (
            DataContractError,
            build_dataset_manifest,
            load_verified_dataset,
            write_dataset_manifest,
        )
        from tests.support import temporary_workspace

        with temporary_workspace() as workspace:
            dataset = workspace / "validated.csv"
            manifest_path = workspace / "dataset-manifest.json"
            self._valid_frame().to_csv(dataset, index=False)
            write_dataset_manifest(build_dataset_manifest(dataset, code_revision="abc123"), manifest_path)
            dataset.write_text(dataset.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            with self.assertRaisesRegex(DataContractError, "checksum"):
                load_verified_dataset(dataset, manifest_path)

    def test_validation_cli_writes_validated_csv_and_manifest(self) -> None:
        from tests.support import temporary_workspace

        repository_root = Path(__file__).resolve().parents[1]
        with temporary_workspace() as workspace:
            source = workspace / "raw.csv"
            output = workspace / "validated.csv"
            manifest = workspace / "dataset-manifest.json"
            self._valid_frame().to_csv(source, index=False)

            completed = subprocess.run(
                [
                    sys.executable, str(repository_root / "scripts" / "validate_dataset.py"),
                    "--input", str(source), "--output", str(output),
                    "--manifest", str(manifest), "--code-revision", "abc123",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["code_revision"], "abc123")


if __name__ == "__main__":
    unittest.main()
