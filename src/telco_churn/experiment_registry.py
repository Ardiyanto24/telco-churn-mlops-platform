"""M7 lineage registration for verified M3/M6 candidate bundles.

MLflow tracks a run and registers only the fitted estimator.  The M3 bundle is
logged as a separate run artifact because it remains the serving contract: it
contains the preprocessor, manifest, checksums, and decision settings.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

from telco_churn.artifacts import LoadedArtifactBundle, VerifiedArtifactLoader


class RegistrationError(RuntimeError):
    """Raised when a candidate cannot be traced or registered safely."""


@dataclass(frozen=True)
class RegistryConfig:
    tracking_uri: str
    artifact_root: Path
    experiment_name: str = "telco-churn-training"
    registered_model_name: str = "telco-churn"
    candidate_alias: str = "candidate"

    def __post_init__(self) -> None:
        if not self.tracking_uri.startswith("sqlite:///"):
            raise ValueError("M7 requires a local SQLite tracking URI")
        if not self.experiment_name or not self.registered_model_name or not self.candidate_alias:
            raise ValueError("experiment, registered model, and candidate alias are required")


@dataclass(frozen=True)
class RegistrationResult:
    run_id: str
    model_name: str
    model_version: str
    model_uri: str
    bundle_uri: str


def register_candidate(
    candidate_dir: Path,
    config: RegistryConfig,
    *,
    mlflow_module: Any | None = None,
    bundle_loader: VerifiedArtifactLoader | None = None,
    client_factory: Callable[[str], Any] | None = None,
) -> RegistrationResult:
    """Register one verified immutable candidate and its complete lineage.

    Registration is intentionally additive.  It never selects a production
    deployment, and it sets only the ``candidate`` alias; M8 owns evaluation
    gates and any later champion/archive decision.
    """
    record, metrics = _read_candidate_record(candidate_dir)
    bundle = (bundle_loader or VerifiedArtifactLoader()).load(candidate_dir / "bundle")
    _validate_candidate_against_bundle(record, bundle)

    mlflow = mlflow_module or _import_mlflow()
    mlflow.set_tracking_uri(config.tracking_uri)
    mlflow.set_registry_uri(config.tracking_uri)
    client = (client_factory or _mlflow_client)(config.tracking_uri)
    _ensure_experiment(mlflow, client, config)

    with mlflow.start_run(run_name=record["config"]["run_name"]) as run:
        run_id = run.info.run_id
        mlflow.log_params(_parameters(record))
        mlflow.log_metrics(metrics)
        mlflow.set_tags(_tags(record, bundle))
        mlflow.log_artifact(str(candidate_dir / "training_run.json"), artifact_path="lineage")
        mlflow.log_artifact(str(candidate_dir / "metrics.json"), artifact_path="lineage")
        mlflow.log_artifacts(str(candidate_dir / "bundle"), artifact_path="bundle")
        mlflow.log_artifacts(str(candidate_dir / "plots"), artifact_path="plots")
        mlflow.sklearn.log_model(bundle.model, name="model")

    model_uri = f"runs:/{run_id}/model"
    version = mlflow.register_model(model_uri=model_uri, name=config.registered_model_name)
    bundle_uri = f"runs:/{run_id}/bundle"
    for key, value in _version_tags(record, bundle, bundle_uri).items():
        client.set_model_version_tag(config.registered_model_name, version.version, key, value)
    client.set_registered_model_alias(config.registered_model_name, config.candidate_alias, version.version)
    return RegistrationResult(run_id, config.registered_model_name, str(version.version), model_uri, bundle_uri)


def _read_candidate_record(candidate_dir: Path) -> tuple[dict[str, Any], dict[str, float]]:
    record = _read_json(candidate_dir / "training_run.json", "training run")
    metrics = _read_json(candidate_dir / "metrics.json", "metrics")
    required = {"config", "model_family", "dataset_manifest", "code_revision", "metrics"}
    missing = required - set(record)
    if missing:
        raise RegistrationError(f"training run is missing required lineage: {sorted(missing)[0]}")
    config = record["config"]
    if not isinstance(config, dict) or not isinstance(config.get("run_name"), str) or not config["run_name"]:
        raise RegistrationError("training run has an invalid config.run_name")
    model = config.get("model")
    if not isinstance(model, dict) or not isinstance(model.get("type"), str) or not isinstance(model.get("params"), dict):
        raise RegistrationError("training run has an invalid config.model")
    dataset = record["dataset_manifest"]
    if not isinstance(dataset, dict) or not isinstance(dataset.get("sha256"), str) or len(dataset["sha256"]) != 64:
        raise RegistrationError("training run has an invalid dataset_manifest.sha256")
    if not isinstance(record["code_revision"], str) or not record["code_revision"]:
        raise RegistrationError("training run has an invalid code_revision")
    if not isinstance(record["model_family"], str) or not record["model_family"]:
        raise RegistrationError("training run has an invalid model_family")
    if not isinstance(metrics, dict) or set(metrics) != {"average_precision", "f1", "roc_auc", "decision_threshold"}:
        raise RegistrationError("metrics have an unsupported schema")
    try:
        parsed_metrics = {key: float(value) for key, value in metrics.items()}
    except (TypeError, ValueError) as error:
        raise RegistrationError("metrics must be numeric") from error
    if record["metrics"] != metrics:
        raise RegistrationError("training run metrics do not match metrics.json")
    if not (candidate_dir / "plots").is_dir():
        raise RegistrationError("candidate plots are missing")
    return record, parsed_metrics


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RegistrationError(f"candidate {label} is unreadable") from error
    if not isinstance(data, dict):
        raise RegistrationError(f"candidate {label} must be an object")
    return data


def _validate_candidate_against_bundle(record: dict[str, Any], bundle: LoadedArtifactBundle) -> None:
    manifest = bundle.manifest
    if record["config"]["run_name"] != manifest.model_version:
        raise RegistrationError("training run name does not match bundle model version")
    if record["model_family"] != manifest.model_family or record["config"]["model"]["type"] != manifest.model_family:
        raise RegistrationError("training run model family does not match bundle manifest")


def _parameters(record: dict[str, Any]) -> dict[str, str]:
    model = record["config"]["model"]
    return {
        "seed": str(record["config"].get("seed")),
        "model.type": model["type"],
        **{f"model.params.{key}": json.dumps(value, sort_keys=True) for key, value in model["params"].items()},
    }


def _tags(record: dict[str, Any], bundle: LoadedArtifactBundle) -> dict[str, str]:
    manifest = bundle.manifest
    return {
        "code_revision": record["code_revision"],
        "dataset_sha256": record["dataset_manifest"]["sha256"],
        "model_family": manifest.model_family,
        "schema_version": manifest.schema_version,
        "baseline_id": manifest.baseline_id,
        "feature_signature": json.dumps(manifest.feature_order),
        "lineage_status": "complete",
    }


def _version_tags(record: dict[str, Any], bundle: LoadedArtifactBundle, bundle_uri: str) -> dict[str, str]:
    return {
        **_tags(record, bundle),
        "bundle_uri": bundle_uri,
        "registry_lifecycle": "candidate",
    }


def _ensure_experiment(mlflow: Any, client: Any, config: RegistryConfig) -> None:
    if client.get_experiment_by_name(config.experiment_name) is None:
        config.artifact_root.mkdir(parents=True, exist_ok=True)
        client.create_experiment(config.experiment_name, artifact_location=config.artifact_root.resolve().as_uri())
    mlflow.set_experiment(config.experiment_name)


def _import_mlflow() -> Any:
    try:
        import mlflow
    except ImportError as error:
        raise RegistrationError("MLflow is unavailable; use the locked M7 runtime") from error
    return mlflow


def _mlflow_client(tracking_uri: str) -> Any:
    from mlflow import MlflowClient

    return MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
