"""Versioned offline metric gates for M8 candidate evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score


METRIC_NAMES = (
    "average_precision", "recall", "precision", "f1", "roc_auc",
    "brier_score", "expected_calibration_error",
)
HIGHER_IS_BETTER = {"average_precision", "recall", "precision", "f1", "roc_auc"}


@dataclass(frozen=True)
class GateConfig:
    version: str
    absolute: dict[str, float]
    regression: dict[str, float]
    ece_bins: int
    latency: dict[str, float] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "GateConfig":
        latency = data.get("latency")
        if latency is not None:
            if not isinstance(latency, dict) or set(latency) != {"single_p95_ms", "batch_100_p95_ms"}:
                raise ValueError("latency must contain exactly single_p95_ms and batch_100_p95_ms")
            latency = {name: float(value) for name, value in latency.items()}
            if any(value <= 0 for value in latency.values()):
                raise ValueError("latency thresholds must be positive")
        config = cls(str(data.get("version", "")), dict(data.get("absolute", {})), dict(data.get("regression", {})), int(data.get("ece_bins", 0)), latency)
        if config.version != "evaluation-gates/v1" or set(config.absolute) != set(METRIC_NAMES) or set(config.regression) != set(METRIC_NAMES):
            raise ValueError("evaluation gate config has an unsupported schema")
        if config.ece_bins < 2 or any(not np.isfinite(value) or value < 0 for value in (*config.absolute.values(), *config.regression.values())):
            raise ValueError("evaluation gate config has invalid thresholds")
        return config


@dataclass(frozen=True)
class EvaluationResult:
    status: str
    metrics: dict[str, float]
    failures: tuple[str, ...]
    champion_metrics: dict[str, float] | None = None


def evaluate_probabilities(
    target: Iterable[int], probabilities: Iterable[float], threshold: float, config: GateConfig,
    *, champion_probabilities: Iterable[float] | None = None, champion_threshold: float | None = None,
) -> EvaluationResult:
    """Apply M8 hard, absolute, and optional champion-regression gates."""
    labels = np.asarray(list(target), dtype=int)
    scores = np.asarray(list(probabilities), dtype=float)
    if len(labels) == 0 or labels.shape != scores.shape or set(labels) - {0, 1} or not 0 <= threshold <= 1:
        return EvaluationResult("invalid", {}, ("evaluation_input",))
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        return EvaluationResult("invalid", {}, ("probability_validity",))
    if len(np.unique(labels)) != 2:
        return EvaluationResult("invalid", {}, ("target_class_coverage",))

    metrics = _metrics(labels, scores, threshold, config.ece_bins)
    failures = list(_absolute_failures(metrics, config))
    if champion_probabilities is None:
        return EvaluationResult("failed" if failures else "not_comparable", metrics, tuple(failures))

    champion_scores = np.asarray(list(champion_probabilities), dtype=float)
    if champion_scores.shape != scores.shape or not np.isfinite(champion_scores).all() or ((champion_scores < 0) | (champion_scores > 1)).any():
        return EvaluationResult("invalid", metrics, ("champion_probability_validity",))
    if champion_threshold is None or not 0 <= champion_threshold <= 1:
        return EvaluationResult("invalid", metrics, ("champion_threshold",))
    champion_metrics = _metrics(labels, champion_scores, champion_threshold, config.ece_bins)
    failures.extend(_regression_failures(metrics, champion_metrics, config))
    return EvaluationResult("failed" if failures else "passed", metrics, tuple(failures), champion_metrics)


def _metrics(labels: np.ndarray, scores: np.ndarray, threshold: float, bins: int) -> dict[str, float]:
    predictions = (scores >= threshold).astype(int)
    return {
        "average_precision": float(average_precision_score(labels, scores)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, scores)),
        "brier_score": float(brier_score_loss(labels, scores)),
        "expected_calibration_error": _expected_calibration_error(labels, scores, bins),
    }


def _expected_calibration_error(labels: np.ndarray, scores: np.ndarray, bins: int) -> float:
    order = np.argsort(scores, kind="mergesort")
    parts = np.array_split(order, bins)
    return float(sum(len(part) / len(scores) * abs(float(scores[part].mean()) - float(labels[part].mean())) for part in parts if len(part)))


def _absolute_failures(metrics: dict[str, float], config: GateConfig) -> tuple[str, ...]:
    failures = []
    for name, value in metrics.items():
        threshold = config.absolute[name]
        if (name in HIGHER_IS_BETTER and value < threshold) or (name not in HIGHER_IS_BETTER and value > threshold):
            failures.append(f"absolute.{name}")
    return tuple(failures)


def _regression_failures(candidate: dict[str, float], champion: dict[str, float], config: GateConfig) -> tuple[str, ...]:
    failures = []
    for name, value in candidate.items():
        regression = champion[name] - value if name in HIGHER_IS_BETTER else value - champion[name]
        if regression > config.regression[name]:
            failures.append(f"regression.{name}")
    return tuple(failures)
