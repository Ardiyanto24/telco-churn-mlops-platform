"""Immutable, checksummed model bundles for serving trusted Joblib artifacts.

Joblib uses pickle internally, so this module verifies an already trusted manifest
and every artifact digest *before* deserializing either artifact. The release
directory itself must remain write-restricted after publication.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Sequence

import joblib
import pandas as pd


MANIFEST_FILENAME = "model_manifest.json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.joblib$")


class ArtifactLoadError(RuntimeError):
    """Raised when an artifact bundle cannot be safely verified or loaded."""


@dataclass(frozen=True)
class ArtifactManifest:
    model_version: str
    schema_version: str
    baseline_id: str
    feature_order: tuple[str, ...]
    decision_threshold: float
    low_risk_threshold: float
    high_risk_threshold: float
    artifacts: dict[str, dict[str, str]]
    runtime: dict[str, str]

    @classmethod
    def read(cls, bundle_dir: Path) -> ArtifactManifest:
        manifest_path = bundle_dir / MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise ArtifactLoadError("model manifest is missing")
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ArtifactLoadError("model manifest is unreadable") from error

        required = {
            "manifest_version", "model_version", "schema_version", "baseline_id",
            "feature_order", "decision_threshold", "risk_bands", "artifacts", "runtime",
        }
        if set(data) != required or data["manifest_version"] != 1:
            raise ArtifactLoadError("model manifest has an unsupported schema")
        feature_order = data["feature_order"]
        if not isinstance(feature_order, list) or not feature_order or not all(
            isinstance(feature, str) and feature for feature in feature_order
        ) or len(set(feature_order)) != len(feature_order):
            raise ArtifactLoadError("model manifest has an invalid feature signature")
        bands = data["risk_bands"]
        if not isinstance(bands, dict) or set(bands) != {"low", "high"}:
            raise ArtifactLoadError("model manifest has invalid risk bands")
        try:
            threshold = float(data["decision_threshold"])
            low = float(bands["low"])
            high = float(bands["high"])
        except (TypeError, ValueError) as error:
            raise ArtifactLoadError("model manifest has invalid decision settings") from error
        if not 0 <= low < threshold < high <= 1:
            raise ArtifactLoadError("model manifest has inconsistent decision settings")
        artifacts = data["artifacts"]
        if set(artifacts) != {"model.joblib", "preprocessor.joblib"}:
            raise ArtifactLoadError("model manifest must describe model and preprocessor")
        for filename, metadata in artifacts.items():
            if not _SAFE_FILENAME.fullmatch(filename) or not isinstance(metadata, dict):
                raise ArtifactLoadError("model manifest has an unsafe artifact filename")
            if set(metadata) != {"sha256"} or not isinstance(metadata["sha256"], str):
                raise ArtifactLoadError("model manifest has invalid artifact metadata")
            if not _SHA256.fullmatch(metadata["sha256"]):
                raise ArtifactLoadError("model manifest has an invalid artifact checksum")
        runtime = data["runtime"]
        if not isinstance(runtime, dict) or set(runtime) != {"python", "joblib", "scikit_learn"}:
            raise ArtifactLoadError("model manifest has invalid runtime metadata")
        if not all(isinstance(value, str) and value for value in runtime.values()):
            raise ArtifactLoadError("model manifest has invalid runtime metadata")
        for key in ("model_version", "schema_version", "baseline_id"):
            if not isinstance(data[key], str) or not data[key]:
                raise ArtifactLoadError("model manifest has invalid release metadata")
        return cls(
            model_version=data["model_version"], schema_version=data["schema_version"],
            baseline_id=data["baseline_id"], feature_order=tuple(feature_order),
            decision_threshold=threshold, low_risk_threshold=low, high_risk_threshold=high,
            artifacts=artifacts, runtime=runtime,
        )


@dataclass(frozen=True)
class LoadedArtifactBundle:
    manifest: ArtifactManifest
    model: Any
    preprocessor: Any

    def predict_probabilities(self, records: Sequence[dict[str, Any]]) -> list[float]:
        frame = pd.DataFrame(records)
        frame = frame.drop(columns=[name for name in ("customerID", "id", "Churn") if name in frame], errors="ignore")
        transformed = self.preprocessor.transform(frame)
        probabilities = self.model.predict_proba(transformed)
        return [float(row[1]) for row in probabilities]


class VerifiedArtifactLoader:
    """Verify a trusted immutable release directory before invoking Joblib."""

    def load(self, bundle_dir: Path) -> LoadedArtifactBundle:
        manifest = ArtifactManifest.read(bundle_dir)
        self._verify_runtime(manifest)
        for filename, metadata in manifest.artifacts.items():
            artifact_path = bundle_dir / filename
            if not artifact_path.is_file():
                raise ArtifactLoadError(f"artifact is missing: {filename}")
            if _sha256(artifact_path) != metadata["sha256"]:
                raise ArtifactLoadError(f"artifact checksum mismatch: {filename}")
        try:
            model = joblib.load(bundle_dir / "model.joblib")
            preprocessor = joblib.load(bundle_dir / "preprocessor.joblib")
        except Exception as error:
            raise ArtifactLoadError("verified artifact failed to deserialize") from error
        self._verify_loaded_objects(manifest, model, preprocessor)
        return LoadedArtifactBundle(manifest=manifest, model=model, preprocessor=preprocessor)

    def _verify_runtime(self, manifest: ArtifactManifest) -> None:
        actual = {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "joblib": importlib.metadata.version("joblib"),
            "scikit_learn": importlib.metadata.version("scikit-learn"),
        }
        if actual != manifest.runtime:
            raise ArtifactLoadError("artifact runtime is incompatible with the locked runtime")

    def _verify_loaded_objects(self, manifest: ArtifactManifest, model: Any, preprocessor: Any) -> None:
        feature_order = getattr(preprocessor, "_last_output_columns_", None)
        if list(manifest.feature_order) != feature_order:
            raise ArtifactLoadError("preprocessor feature signature does not match manifest")
        if getattr(model, "n_features_in_", None) != len(manifest.feature_order):
            raise ArtifactLoadError("model feature signature does not match manifest")
        if not callable(getattr(preprocessor, "transform", None)) or not callable(getattr(model, "predict_proba", None)):
            raise ArtifactLoadError("artifact does not implement the prediction contract")
        if _uses_main_module(preprocessor) or _uses_main_module(model):
            raise ArtifactLoadError("artifact still depends on __main__ and must be migrated")


def write_manifest(
    bundle_dir: Path, *, model_version: str, schema_version: str, baseline_id: str,
    feature_order: list[str], decision_threshold: float, low_risk_threshold: float,
    high_risk_threshold: float,
) -> Path:
    """Write a new manifest only for a newly-created release directory."""
    manifest_path = bundle_dir / MANIFEST_FILENAME
    if manifest_path.exists():
        raise ArtifactLoadError("artifact releases are immutable; manifest already exists")
    data = {
        "manifest_version": 1, "model_version": model_version, "schema_version": schema_version,
        "baseline_id": baseline_id, "feature_order": feature_order,
        "decision_threshold": decision_threshold,
        "risk_bands": {"low": low_risk_threshold, "high": high_risk_threshold},
        "artifacts": {
            filename: {"sha256": _sha256(bundle_dir / filename)}
            for filename in ("model.joblib", "preprocessor.joblib")
        },
        "runtime": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "joblib": importlib.metadata.version("joblib"),
            "scikit_learn": importlib.metadata.version("scikit-learn"),
        },
    }
    manifest_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ArtifactManifest.read(bundle_dir)
    return manifest_path


def migrate_legacy_bundle(
    source_dir: Path,
    destination_dir: Path,
    *,
    model_version: str,
    schema_version: str = "v1",
    baseline_id: str = "m0-legacy-snapshot-v1",
    decision_threshold: float = 0.6238,
    low_risk_threshold: float = 0.35,
    high_risk_threshold: float = 0.75,
) -> Path:
    """Create a new immutable bundle from trusted legacy artifacts.

    The temporary aliases only resolve historic pickle references while this
    migration command runs. They are removed before returning; the resaved
    classes retain their stable ``telco_churn.preprocessing`` module path.
    """
    if destination_dir.exists():
        raise ArtifactLoadError("destination release directory must not already exist")
    source_model = source_dir / "model_final.joblib"
    source_preprocessor = source_dir / "preprocessor.joblib"
    if not source_model.is_file() or not source_preprocessor.is_file():
        raise ArtifactLoadError("trusted legacy model and preprocessor are required")
    destination_dir.mkdir(parents=True)
    import __main__
    from telco_churn import preprocessing

    aliases = {
        name: getattr(preprocessing, name)
        for name in (
            "FeatureEngineer", "ColumnDropper", "StructuralEncoder", "BinaryEncoder",
            "OHEWrapper", "ScalerWrapper", "PreprocessingPipeline",
        )
    }
    previous = {name: getattr(__main__, name, None) for name in aliases}
    try:
        for name, value in aliases.items():
            setattr(__main__, name, value)
        model = joblib.load(source_model)
        preprocessor = joblib.load(source_preprocessor)
    except Exception as error:
        shutil.rmtree(destination_dir)
        raise ArtifactLoadError("trusted legacy artifacts could not be migrated") from error
    finally:
        for name, value in previous.items():
            if value is None:
                delattr(__main__, name)
            else:
                setattr(__main__, name, value)
    joblib.dump(model, destination_dir / "model.joblib")
    # Legacy serialized the pipeline steps as ``(name, transformer)`` pairs.
    # The stable package deliberately stores transformers directly.
    if hasattr(preprocessor, "_steps"):
        preprocessor._steps = tuple(
            step[1] if isinstance(step, tuple) else step for step in preprocessor._steps
        )
    joblib.dump(preprocessor, destination_dir / "preprocessor.joblib")
    feature_order = getattr(preprocessor, "_last_output_columns_", None)
    if not isinstance(feature_order, list):
        shutil.rmtree(destination_dir)
        raise ArtifactLoadError("legacy preprocessor has no fitted feature signature")
    return write_manifest(
        destination_dir, model_version=model_version, schema_version=schema_version,
        baseline_id=baseline_id, feature_order=feature_order,
        decision_threshold=decision_threshold, low_risk_threshold=low_risk_threshold,
        high_risk_threshold=high_risk_threshold,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _uses_main_module(value: Any) -> bool:
    if value.__class__.__module__ == "__main__":
        return True
    for child in getattr(value, "__dict__", {}).values():
        if child.__class__.__module__ == "__main__":
            return True
    return False
