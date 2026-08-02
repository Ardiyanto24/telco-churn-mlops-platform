"""M7 experiment-tracking and model-registry contract tests."""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
import unittest


class _Manifest:
    model_version = "m6-test"
    model_family = "logistic_regression"
    schema_version = "v1"
    baseline_id = "m6-dataset-abc123"
    feature_order = ("tenure", "monthly_charges")


class _Bundle:
    manifest = _Manifest()
    model = object()


class _Loader:
    def load(self, bundle_dir: Path) -> _Bundle:
        return _Bundle()


class _Run:
    class info:
        run_id = "run-123"

    def __enter__(self) -> "_Run":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class _Client:
    def __init__(self) -> None:
        self.version_tags: dict[str, str] = {}
        self.aliases: dict[str, str] = {}

    def set_model_version_tag(self, name: str, version: str, key: str, value: str) -> None:
        self.version_tags[key] = value

    def set_registered_model_alias(self, name: str, alias: str, version: str) -> None:
        self.aliases[alias] = version

    def get_experiment_by_name(self, name: str):
        return None

    def create_experiment(self, name: str, artifact_location: str) -> str:
        self.experiment = (name, artifact_location)
        return "1"


class _Mlflow:
    def __init__(self) -> None:
        self.client = _Client()
        self.params: dict[str, str] = {}
        self.metrics: dict[str, float] = {}
        self.tags: dict[str, str] = {}
        self.artifacts: list[tuple[str, str | None]] = []
        self.tracking_uri = ""
        self.registry_uri = ""
        self.experiment = ""
        self.sklearn = self

    def set_tracking_uri(self, uri: str) -> None:
        self.tracking_uri = uri

    def set_registry_uri(self, uri: str) -> None:
        self.registry_uri = uri

    def set_experiment(self, name: str) -> None:
        self.experiment = name

    def start_run(self, run_name: str) -> _Run:
        return _Run()

    def log_params(self, params: dict[str, str]) -> None:
        self.params.update(params)

    def log_metrics(self, metrics: dict[str, float]) -> None:
        self.metrics.update(metrics)

    def set_tags(self, tags: dict[str, str]) -> None:
        self.tags.update(tags)

    def log_artifact(self, path: str, artifact_path: str | None = None) -> None:
        self.artifacts.append((path, artifact_path))

    def log_artifacts(self, path: str, artifact_path: str | None = None) -> None:
        self.artifacts.append((path, artifact_path))

    def log_model(self, model: object, name: str) -> None:
        self.model_name = name

    def register_model(self, model_uri: str, name: str):
        self.registered = (model_uri, name)
        return type("Version", (), {"version": "7"})()

    def tracking(self):
        return self.client


class ExperimentRegistryTests(unittest.TestCase):
    def _candidate(self, workspace: Path) -> Path:
        candidate = workspace / "candidate"
        (candidate / "bundle").mkdir(parents=True)
        (candidate / "plots").mkdir()
        (candidate / "metrics.json").write_text(
            json.dumps({"average_precision": 0.7, "f1": 0.6, "roc_auc": 0.9, "decision_threshold": 0.4}),
            encoding="utf-8",
        )
        (candidate / "training_run.json").write_text(json.dumps({
            "config": {"run_name": "m6-test", "seed": 42, "model": {"type": "logistic_regression", "params": {"C": 1.0}}},
            "model_family": "logistic_regression",
            "dataset_manifest": {"sha256": "a" * 64, "schema_version": "telco-churn-training/v1"},
            "code_revision": "abc123", "metrics": {"average_precision": 0.7, "f1": 0.6, "roc_auc": 0.9, "decision_threshold": 0.4},
        }), encoding="utf-8")
        return candidate

    def test_registers_verified_candidate_with_lineage_and_candidate_alias(self) -> None:
        from tests.support import temporary_workspace
        from telco_churn.experiment_registry import RegistryConfig, register_candidate

        with temporary_workspace() as workspace:
            client = _Mlflow()
            result = register_candidate(
                self._candidate(workspace),
                RegistryConfig(tracking_uri="sqlite:///mlflow.db", artifact_root=workspace / "artifacts"),
                mlflow_module=client, bundle_loader=_Loader(), client_factory=lambda _: client.client,
            )

        self.assertEqual(result.run_id, "run-123")
        self.assertEqual(result.model_version, "7")
        self.assertEqual(client.registered, ("runs:/run-123/model", "telco-churn"))
        self.assertEqual(client.client.aliases, {"candidate": "7"})
        self.assertEqual(client.tags["dataset_sha256"], "a" * 64)
        self.assertEqual(client.tags["model_family"], "logistic_regression")
        self.assertEqual(client.client.version_tags["bundle_uri"], "runs:/run-123/bundle")

    def test_rejects_candidate_without_required_lineage_before_creating_a_run(self) -> None:
        from tests.support import temporary_workspace
        from telco_churn.experiment_registry import RegistryConfig, RegistrationError, register_candidate

        with temporary_workspace() as workspace:
            candidate = self._candidate(workspace)
            record = json.loads((candidate / "training_run.json").read_text(encoding="utf-8"))
            del record["code_revision"]
            (candidate / "training_run.json").write_text(json.dumps(record), encoding="utf-8")
            client = _Mlflow()

            with self.assertRaisesRegex(RegistrationError, "code_revision"):
                register_candidate(
                    candidate, RegistryConfig(tracking_uri="sqlite:///mlflow.db", artifact_root=workspace / "artifacts"),
                    mlflow_module=client, bundle_loader=_Loader(), client_factory=lambda _: client.client,
                )
        self.assertEqual(client.tags, {})

    @unittest.skipUnless(find_spec("mlflow"), "requires the locked M7 runtime")
    def test_real_mlflow_registry_keeps_model_version_and_run_lineage(self) -> None:
        from tests.support import temporary_workspace
        from tests.test_training_pipeline import TrainingPipelineTests
        from telco_churn.experiment_registry import RegistryConfig, register_candidate

        with temporary_workspace() as workspace:
            helper = TrainingPipelineTests()
            dataset, manifest = helper._verified_data(workspace)
            from telco_churn.training.pipeline import run_training
            candidate = run_training(helper._config(), dataset, manifest, workspace / "candidate").output_dir
            tracking_uri = f"sqlite:///{workspace / 'mlflow.db'}"
            first = register_candidate(candidate, RegistryConfig(tracking_uri, workspace / "artifacts"))
            result = register_candidate(candidate, RegistryConfig(tracking_uri, workspace / "artifacts"))

            from mlflow import MlflowClient
            registry = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
            version = registry.get_model_version(
                result.model_name, result.model_version,
            )
            first_artifacts = registry.list_artifacts(first.run_id)

        self.assertEqual(version.run_id, result.run_id)
        self.assertEqual(version.tags["registry_lifecycle"], "candidate")
        self.assertNotEqual(first.run_id, result.run_id)
        self.assertNotEqual(first.model_version, result.model_version)
        self.assertIn("bundle", [artifact.path for artifact in first_artifacts])


if __name__ == "__main__":
    unittest.main()
