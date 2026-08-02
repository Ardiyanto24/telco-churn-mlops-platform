"""Immutable release manifests and append-only local release history for M11."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40,64}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_ENVIRONMENTS = {"staging", "production_simulated"}
_MANIFEST_VERSION = "deployment-manifest/v1"


class ReleaseControlError(ValueError):
    """Raised when release metadata cannot safely control a deployment."""


@dataclass(frozen=True)
class ReleaseManifest:
    """An immutable image, verified-model, and source-code release pair."""

    release_id: str
    environment: str
    created_at: str
    image_ref: str
    image_digest: str
    source_git_sha: str
    model_version: str
    schema_version: str
    model_manifest_sha256: str
    decision_threshold: float
    low_risk_threshold: float
    high_risk_threshold: float
    evaluation_report_sha256: str
    promotion_decision_sha256: str

    @property
    def identity_sha256(self) -> str:
        return _sha256_json({
            "image_digest": self.image_digest,
            "model_manifest_sha256": self.model_manifest_sha256,
            "source_git_sha": self.source_git_sha,
        })

    @classmethod
    def create(
        cls,
        *,
        bundle_dir: Path,
        image_ref: str,
        image_digest: str,
        source_git_sha: str,
        evaluation_report_sha256: str,
        promotion_decision_sha256: str,
        environment: str,
        created_at: str,
    ) -> "ReleaseManifest":
        model = _read_model_manifest(bundle_dir)
        manifest_sha = _sha256_file(bundle_dir / "model_manifest.json")
        release_id = "release-" + _sha256_json({
            "image_digest": image_digest,
            "model_manifest_sha256": manifest_sha,
            "source_git_sha": source_git_sha,
        })[:12]
        result = cls(
            release_id=release_id,
            environment=environment,
            created_at=created_at,
            image_ref=image_ref,
            image_digest=image_digest,
            source_git_sha=source_git_sha,
            model_version=model["model_version"],
            schema_version=model["schema_version"],
            model_manifest_sha256=manifest_sha,
            decision_threshold=float(model["decision_threshold"]),
            low_risk_threshold=float(model["risk_bands"]["low"]),
            high_risk_threshold=float(model["risk_bands"]["high"]),
            evaluation_report_sha256=evaluation_report_sha256,
            promotion_decision_sha256=promotion_decision_sha256,
        )
        result._validate_fields()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseManifest":
        required = {
            "manifest_version", "release_id", "environment", "created_at", "image_ref", "image_digest",
            "source_git_sha", "model_version", "schema_version", "model_manifest_sha256",
            "decision_threshold", "risk_bands", "evaluation_report_sha256", "promotion_decision_sha256",
        }
        if set(data) != required or data.get("manifest_version") != _MANIFEST_VERSION:
            raise ReleaseControlError("deployment manifest has an unsupported schema")
        bands = data["risk_bands"]
        if not isinstance(bands, dict) or set(bands) != {"low", "high"}:
            raise ReleaseControlError("deployment manifest has invalid risk bands")
        try:
            result = cls(
                release_id=data["release_id"], environment=data["environment"], created_at=data["created_at"],
                image_ref=data["image_ref"], image_digest=data["image_digest"], source_git_sha=data["source_git_sha"],
                model_version=data["model_version"], schema_version=data["schema_version"],
                model_manifest_sha256=data["model_manifest_sha256"], decision_threshold=float(data["decision_threshold"]),
                low_risk_threshold=float(bands["low"]), high_risk_threshold=float(bands["high"]),
                evaluation_report_sha256=data["evaluation_report_sha256"], promotion_decision_sha256=data["promotion_decision_sha256"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ReleaseControlError("deployment manifest has invalid values") from error
        result._validate_fields()
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": _MANIFEST_VERSION,
            "release_id": self.release_id,
            "environment": self.environment,
            "created_at": self.created_at,
            "image_ref": self.image_ref,
            "image_digest": self.image_digest,
            "source_git_sha": self.source_git_sha,
            "model_version": self.model_version,
            "schema_version": self.schema_version,
            "model_manifest_sha256": self.model_manifest_sha256,
            "decision_threshold": self.decision_threshold,
            "risk_bands": {"low": self.low_risk_threshold, "high": self.high_risk_threshold},
            "evaluation_report_sha256": self.evaluation_report_sha256,
            "promotion_decision_sha256": self.promotion_decision_sha256,
        }

    def validate_bundle(self, bundle_dir: Path) -> None:
        model = _read_model_manifest(bundle_dir)
        if _sha256_file(bundle_dir / "model_manifest.json") != self.model_manifest_sha256:
            raise ReleaseControlError("model manifest checksum does not match release")
        if model["model_version"] != self.model_version:
            raise ReleaseControlError("model version does not match release")
        if model["schema_version"] != self.schema_version:
            raise ReleaseControlError("model schema does not match release")
        if (float(model["decision_threshold"]), float(model["risk_bands"]["low"]), float(model["risk_bands"]["high"])) != (
            self.decision_threshold, self.low_risk_threshold, self.high_risk_threshold,
        ):
            raise ReleaseControlError("model decision settings do not match release")

    def _validate_fields(self) -> None:
        if self.environment not in _ENVIRONMENTS:
            raise ReleaseControlError("deployment environment is not allowed")
        if not all(isinstance(value, str) and value for value in (self.release_id, self.created_at, self.image_ref, self.model_version, self.schema_version)):
            raise ReleaseControlError("deployment manifest has empty identity metadata")
        if "latest" in self.image_ref.lower() or "@sha256:" in self.image_ref:
            raise ReleaseControlError("image reference must be an immutable non-latest tag")
        if not _IMAGE_DIGEST.fullmatch(self.image_digest):
            raise ReleaseControlError("image digest is invalid")
        if not _GIT_SHA.fullmatch(self.source_git_sha):
            raise ReleaseControlError("source git SHA is invalid")
        if not all(_SHA256.fullmatch(value) for value in (
            self.model_manifest_sha256, self.evaluation_report_sha256, self.promotion_decision_sha256,
        )):
            raise ReleaseControlError("release evidence checksum is invalid")
        if self.release_id != "release-" + self.identity_sha256[:12]:
            raise ReleaseControlError("release ID does not match immutable identity")
        if not 0 <= self.low_risk_threshold < self.decision_threshold < self.high_risk_threshold <= 1:
            raise ReleaseControlError("release decision settings are inconsistent")


class ReleaseLedger:
    """Filesystem-backed append-only manifests plus an atomic current pointer."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def record(self, release: ReleaseManifest) -> Path:
        path = self.root / "history" / f"{release.release_id}.json"
        if path.exists():
            existing = self._read(path)
            if existing != release:
                raise ReleaseControlError("release ID already records different content")
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_new(path, release.to_dict())
        return path

    def activate(self, release: ReleaseManifest) -> Path:
        self.record(release)
        path = self.root / "current" / f"{release.environment}.json"
        _write_json_atomic(path, release.to_dict())
        return path

    def current(self, environment: str) -> ReleaseManifest:
        if environment not in _ENVIRONMENTS:
            raise ReleaseControlError("deployment environment is not allowed")
        return self._read(self.root / "current" / f"{environment}.json")

    def rollback(self, *, to_release_id: str, operator: str) -> ReleaseManifest:
        if not isinstance(operator, str) or not operator:
            raise ReleaseControlError("rollback operator is required")
        target = self._read(self.root / "history" / f"{to_release_id}.json")
        previous = self.current(target.environment)
        self.activate(target)
        event_path = self.root / "events" / f"rollback-{previous.release_id}-to-{target.release_id}.json"
        _write_json_new(event_path, {
            "event_version": "release-event/v1", "action": "rollback", "operator": operator,
            "environment": target.environment, "from_release_id": previous.release_id,
            "to_release_id": target.release_id,
        })
        return target

    @staticmethod
    def _read(path: Path) -> ReleaseManifest:
        try:
            return ReleaseManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as error:
            raise ReleaseControlError("release manifest is unreadable") from error


def _read_model_manifest(bundle_dir: Path) -> dict[str, Any]:
    path = bundle_dir / "model_manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseControlError("model manifest is unreadable") from error
    required = {"model_version", "schema_version", "decision_threshold", "risk_bands"}
    if not isinstance(data, dict) or not required <= set(data):
        raise ReleaseControlError("model manifest lacks deployment metadata")
    if not isinstance(data["risk_bands"], dict) or set(data["risk_bands"]) != {"low", "high"}:
        raise ReleaseControlError("model manifest has invalid risk bands")
    return data


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_json_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
    except FileExistsError as error:
        raise ReleaseControlError("append-only release record already exists") from error


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
