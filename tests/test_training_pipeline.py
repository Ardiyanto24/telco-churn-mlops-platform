"""M6 reproducible training-pipeline contract tests."""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
import unittest


RUNTIME_AVAILABLE = all(
    find_spec(name) for name in ("joblib", "lightgbm", "pandas", "pandera", "sklearn", "xgboost")
)

if RUNTIME_AVAILABLE:
    import pandas as pd

    from telco_churn.artifacts import VerifiedArtifactLoader
    from telco_churn.data_contract import build_dataset_manifest, write_dataset_manifest
    from telco_churn.training.pipeline import TrainingConfig, build_model, run_training


@unittest.skipUnless(RUNTIME_AVAILABLE, "requires the locked M6 runtime")
class TrainingPipelineTests(unittest.TestCase):
    def _frame(self, rows: int = 40):
        records = []
        for index in range(rows):
            churn = "Yes" if index % 3 == 0 else "No"
            records.append({
                "id": f"TRAIN-{index:04d}", "gender": "Female" if index % 2 else "Male",
                "SeniorCitizen": index % 2, "Partner": "Yes" if index % 2 else "No",
                "Dependents": "No", "tenure": index % 36 + 1, "PhoneService": "Yes",
                "MultipleLines": "Yes" if index % 2 else "No", "InternetService": "DSL",
                "OnlineSecurity": "Yes" if index % 2 else "No", "OnlineBackup": "No",
                "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "No",
                "StreamingMovies": "No", "Contract": "Month-to-month",
                "PaperlessBilling": "Yes", "PaymentMethod": "Electronic check",
                "MonthlyCharges": float(30 + index), "TotalCharges": float((30 + index) * (index % 36 + 1)),
                "Churn": churn,
            })
        return pd.DataFrame(records)

    def _config(self, model_type: str = "logistic_regression") -> TrainingConfig:
        params = {
            "logistic_regression": {"C": 1.0, "max_iter": 200},
            "lightgbm": {"n_estimators": 3, "n_jobs": 1},
            "xgboost": {"n_estimators": 3, "max_depth": 2, "n_jobs": 1},
            "voting_ensemble": {
                "weights": [5, 3, 1],
                "lightgbm": {"n_estimators": 3, "n_jobs": 1},
                "xgboost_class_weight": {"n_estimators": 3, "max_depth": 2, "n_jobs": 1},
                "xgboost_smote": {"n_estimators": 3, "max_depth": 2, "n_jobs": 1},
            },
        }
        return TrainingConfig.from_dict({
            "run_name": "m6-test", "seed": 42,
            "split": {"train_fraction": 0.70, "validation_fraction": 0.15, "test_fraction": 0.15},
            "model": {"type": model_type, "params": params[model_type]},
        })

    def _verified_data(self, workspace: Path) -> tuple[Path, Path]:
        dataset, manifest = workspace / "validated.csv", workspace / "dataset-manifest.json"
        self._frame().to_csv(dataset, index=False)
        write_dataset_manifest(build_dataset_manifest(dataset, code_revision="test-revision"), manifest)
        return dataset, manifest

    def test_repeated_runs_have_same_metrics_and_a_loadable_candidate_bundle(self) -> None:
        from tests.support import temporary_workspace

        with temporary_workspace() as workspace:
            dataset, manifest = self._verified_data(workspace)
            first = run_training(self._config(), dataset, manifest, workspace / "first")
            second = run_training(self._config(), dataset, manifest, workspace / "second")

            self.assertEqual(first.metrics, second.metrics)
            self.assertTrue((first.output_dir / "metrics.json").is_file())
            self.assertTrue((first.output_dir / "plots" / "precision_recall.svg").is_file())
            self.assertEqual(
                VerifiedArtifactLoader().load(first.output_dir / "bundle").manifest.model_version,
                "m6-test",
            )

    def test_each_supported_model_type_produces_a_loadable_bundle_with_its_family(self) -> None:
        from tests.support import temporary_workspace

        with temporary_workspace() as workspace:
            dataset, manifest = self._verified_data(workspace)
            for model_type in ("logistic_regression", "lightgbm", "xgboost", "voting_ensemble"):
                result = run_training(self._config(model_type), dataset, manifest, workspace / model_type)
                bundle = VerifiedArtifactLoader().load(result.output_dir / "bundle")
                self.assertEqual(bundle.manifest.model_family, model_type)
                self.assertTrue(callable(getattr(build_model(self._config(model_type)), "predict_proba", None)))

    def test_run_records_strict_split_boundaries(self) -> None:
        from tests.support import temporary_workspace

        with temporary_workspace() as workspace:
            dataset, manifest = self._verified_data(workspace)
            result = run_training(self._config(), dataset, manifest, workspace / "run")
            record = json.loads((result.output_dir / "training_run.json").read_text(encoding="utf-8"))

            self.assertEqual(record["fit_split"], "train")
            self.assertEqual(record["threshold_selection_split"], "validation")
            self.assertEqual(record["evaluation_split"], "test")
            self.assertEqual(sum(record["split_row_counts"].values()), 40)
            self.assertNotEqual(record["code_revision"], "unavailable")

    def test_changed_seed_is_captured_as_a_different_run_input(self) -> None:
        from tests.support import temporary_workspace

        with temporary_workspace() as workspace:
            dataset, manifest = self._verified_data(workspace)
            first = run_training(self._config(), dataset, manifest, workspace / "first")
            changed = TrainingConfig.from_dict({
                "run_name": "m6-test-seed-99", "seed": 99,
                "split": {"train_fraction": 0.70, "validation_fraction": 0.15, "test_fraction": 0.15},
                "model": {"type": "logistic_regression", "params": {"C": 1.0, "max_iter": 200}},
            })
            second = run_training(changed, dataset, manifest, workspace / "second")

            first_record = json.loads((first.output_dir / "training_run.json").read_text(encoding="utf-8"))
            second_record = json.loads((second.output_dir / "training_run.json").read_text(encoding="utf-8"))
            self.assertNotEqual(first_record["config"]["seed"], second_record["config"]["seed"])
            self.assertEqual(first_record["model_family"], "logistic_regression")

    def test_contract_failure_halts_before_creating_output(self) -> None:
        from tests.support import temporary_workspace

        with temporary_workspace() as workspace:
            dataset, manifest = self._verified_data(workspace)
            dataset.write_text(dataset.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            output = workspace / "must-not-exist"

            with self.assertRaisesRegex(Exception, "checksum"):
                run_training(self._config(), dataset, manifest, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
