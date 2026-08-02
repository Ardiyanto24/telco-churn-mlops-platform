"""Deterministic M15 calibration policy and controlled drift scenarios."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class CalibrationConfig:
    seed: int = 20260803
    minimum_sample_size: int = 500
    max_prediction_rows: int = 10_000
    fdr_q: float = .05
    psi_thresholds: tuple[float, float, float] = (.10, .20, .30)
    wasserstein_thresholds: tuple[float, float, float] = (.05, .10, .20)
    jensen_shannon_thresholds: tuple[float, float, float] = (.05, .10, .20)
    quality_delta_thresholds: tuple[float, float, float] = (.01, .05, .15)
    target_false_positive_rate: float = .05
    target_sensitivity: float = .80
    max_detection_windows: int = 2


def build_monitoring_config(config: CalibrationConfig) -> dict[str, Any]:
    """Build a content-addressed candidate configuration; it is never mutable."""
    content = {"monitoring_config_schema": "telco-churn-monitoring-config/v1", "status": "candidate", **asdict(config),
               "numeric_methods": ["psi", "histogram_wasserstein"], "categorical_methods": ["jensen_shannon", "eligible_chi_square"],
               "prediction_method": "probability_psi", "multiple_testing": {"method": "benjamini-hochberg", "q": config.fdr_q},
               "ks": "not_applicable_aggregate_reference"}
    version = sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {**content, "monitoring_config_version": version, "sha256": version}


def inject_numeric_shift(frame: pd.DataFrame, column: str, *, shift: float) -> pd.DataFrame:
    result = frame.copy()
    result[column] = pd.to_numeric(result[column]) + shift
    return result


def inject_categorical_shift(frame: pd.DataFrame, column: str, *, value: str, fraction: float, seed: int) -> pd.DataFrame:
    count = _count(frame, fraction)
    result = frame.copy()
    indices = result.sample(n=count, random_state=seed).index
    result.loc[indices, column] = value
    return result


def inject_missingness(frame: pd.DataFrame, column: str, *, fraction: float, seed: int) -> pd.DataFrame:
    count = _count(frame, fraction)
    result = frame.copy()
    result.loc[result.sample(n=count, random_state=seed).index, column] = None
    return result


def score_calibration(*, stable_statuses: list[str], material_statuses: list[str], detection_windows: list[int], config: CalibrationConfig) -> dict[str, Any]:
    """Score aggregate scenario outcomes against the M15 acceptance targets."""
    alert = {"warning", "critical"}
    fpr = sum(status in alert for status in stable_statuses) / max(len(stable_statuses), 1)
    sensitivity = sum(status in alert for status in material_statuses) / max(len(material_statuses), 1)
    delay = max(detection_windows, default=config.max_detection_windows + 1)
    return {"false_positive_rate": round(fpr, 8), "sensitivity": round(sensitivity, 8), "max_detection_windows": delay,
            "accepted": fpr <= config.target_false_positive_rate and sensitivity >= config.target_sensitivity and delay <= config.max_detection_windows}


def _count(frame: pd.DataFrame, fraction: float) -> int:
    if not 0 <= fraction <= 1:
        raise ValueError("fraction must be between zero and one")
    return int(round(len(frame) * fraction))
