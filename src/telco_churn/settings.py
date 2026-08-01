"""Validated runtime settings without model-loading side effects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_ARTIFACT_DIR = Path("artifacts")
DEFAULT_MODEL_FILENAME = "model_final.joblib"
DEFAULT_PREPROCESSOR_FILENAME = "preprocessor.joblib"
DEFAULT_DECISION_THRESHOLD = 0.6238
DEFAULT_LOW_RISK_THRESHOLD = 0.35
DEFAULT_HIGH_RISK_THRESHOLD = 0.75


class SettingsError(ValueError):
    """Raised when runtime settings are invalid."""


@dataclass(frozen=True)
class Settings:
    artifact_dir: Path
    model_filename: str
    preprocessor_filename: str
    decision_threshold: float
    low_risk_threshold: float
    high_risk_threshold: float


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Load settings from an explicit environment mapping for deterministic tests."""
    decision_threshold = _read_float(
        environ, "TELCO_CHURN_DECISION_THRESHOLD", DEFAULT_DECISION_THRESHOLD
    )
    settings = Settings(
        artifact_dir=Path(environ.get("TELCO_CHURN_ARTIFACT_DIR", DEFAULT_ARTIFACT_DIR)),
        model_filename=environ.get(
            "TELCO_CHURN_MODEL_FILENAME", DEFAULT_MODEL_FILENAME
        ),
        preprocessor_filename=environ.get(
            "TELCO_CHURN_PREPROCESSOR_FILENAME", DEFAULT_PREPROCESSOR_FILENAME
        ),
        decision_threshold=decision_threshold,
        low_risk_threshold=DEFAULT_LOW_RISK_THRESHOLD,
        high_risk_threshold=DEFAULT_HIGH_RISK_THRESHOLD,
    )
    _validate(settings)
    return settings


def _read_float(environ: Mapping[str, str], name: str, default: float) -> float:
    raw_value = environ.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError as error:
        raise SettingsError(f"{name} must be numeric") from error


def _validate(settings: Settings) -> None:
    if not settings.model_filename or not settings.preprocessor_filename:
        raise SettingsError("artifact filenames must not be empty")
    if not (
        settings.low_risk_threshold
        < settings.decision_threshold
        < settings.high_risk_threshold
    ):
        raise SettingsError(
            "TELCO_CHURN_DECISION_THRESHOLD must be between "
            "the low and high risk thresholds"
        )
