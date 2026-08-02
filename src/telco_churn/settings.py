"""Validated runtime settings without model-loading side effects."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


DEFAULT_ARTIFACT_DIR = Path("artifacts")
DEFAULT_MODEL_FILENAME = "model_final.joblib"
DEFAULT_PREPROCESSOR_FILENAME = "preprocessor.joblib"
DEFAULT_DECISION_THRESHOLD = 0.6238
DEFAULT_LOW_RISK_THRESHOLD = 0.35
DEFAULT_HIGH_RISK_THRESHOLD = 0.75
DEFAULT_CANDIDATE_RISK_MARGIN = 0.20


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


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load settings from an explicit mapping or the current process environment."""
    environ = os.environ if environ is None else environ
    decision_threshold = _read_float(
        environ, "TELCO_CHURN_DECISION_THRESHOLD", DEFAULT_DECISION_THRESHOLD
    )
    settings = Settings(
        artifact_dir=Path(environ.get("TELCO_CHURN_BUNDLE_DIR", environ.get("TELCO_CHURN_ARTIFACT_DIR", DEFAULT_ARTIFACT_DIR))),
        model_filename=environ.get(
            "TELCO_CHURN_MODEL_FILENAME", DEFAULT_MODEL_FILENAME
        ),
        preprocessor_filename=environ.get(
            "TELCO_CHURN_PREPROCESSOR_FILENAME", DEFAULT_PREPROCESSOR_FILENAME
        ),
        decision_threshold=decision_threshold,
        low_risk_threshold=_read_float(environ, "TELCO_CHURN_LOW_RISK_THRESHOLD", DEFAULT_LOW_RISK_THRESHOLD),
        high_risk_threshold=_read_float(environ, "TELCO_CHURN_HIGH_RISK_THRESHOLD", DEFAULT_HIGH_RISK_THRESHOLD),
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


def risk_bands_for_threshold(threshold: float) -> tuple[float, float]:
    """Derive valid candidate risk bands around a validation-selected threshold."""
    if not 0 < threshold < 1:
        raise SettingsError("candidate decision threshold must be between 0 and 1")
    return (
        max(0.0, threshold - DEFAULT_CANDIDATE_RISK_MARGIN),
        min(1.0, threshold + DEFAULT_CANDIDATE_RISK_MARGIN),
    )


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
