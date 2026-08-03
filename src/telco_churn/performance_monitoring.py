"""M16 delayed-label joins and privacy-minimised performance evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Literal

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


PERFORMANCE_RESULT_VERSION = "telco-churn-performance-monitoring/v1"
DataOrigin = Literal["offline_test", "replayed", "synthetic", "production"]


class PerformanceMonitoringError(ValueError):
    """Raised when external delayed-label data violates the M16 contract."""


@dataclass(frozen=True)
class PerformanceConfig:
    version: str = "m16-candidate/v1"
    maturity_horizon_days: int = 90
    ingestion_grace_hours: int = 24
    minimum_mature_labels: int = 500
    minimum_label_coverage: float = .80
    probability_bin_edges: tuple[float, ...] = (0.0, .2, .4, .6, .8, 1.0)
    maximum_rolling_cohorts: int = 3
    allow_production_origin: bool = False

    def __post_init__(self) -> None:
        if self.maturity_horizon_days < 1 or self.ingestion_grace_hours < 0:
            raise PerformanceMonitoringError("maturity configuration must be positive")
        if self.minimum_mature_labels < 1 or not 0 < self.minimum_label_coverage <= 1:
            raise PerformanceMonitoringError("minimum evidence configuration is invalid")
        if not 1 <= self.maximum_rolling_cohorts <= 3:
            raise PerformanceMonitoringError("rolling cohorts must be between one and three months")
        if self.probability_bin_edges[0] != 0 or self.probability_bin_edges[-1] != 1:
            raise PerformanceMonitoringError("probability bins must start at 0 and end at 1")
        if any(left >= right for left, right in zip(self.probability_bin_edges, self.probability_bin_edges[1:])):
            raise PerformanceMonitoringError("probability bins must be strictly increasing")


@dataclass(frozen=True)
class PredictionEvent:
    prediction_id: str
    entity_key: str
    key_id: str
    prediction_at: datetime
    probability: float
    decision_threshold: float
    model_version: str
    model_bundle_sha256: str
    schema_version: str
    threshold_version: str
    risk_policy_version: str

    def __post_init__(self) -> None:
        if not self.prediction_id or not self.entity_key or not self.key_id:
            raise PerformanceMonitoringError("prediction identity fields are required")
        if not 0 <= self.probability <= 1 or not 0 < self.decision_threshold < 1:
            raise PerformanceMonitoringError("prediction probability or decision threshold is invalid")
        _utc(self.prediction_at, "prediction_at")
        _sha(self.model_bundle_sha256, "model_bundle_sha256")


@dataclass(frozen=True)
class DelayedLabel:
    prediction_id: str
    entity_key: str
    key_id: str
    churned_within_horizon: bool
    outcome_at: datetime
    received_at: datetime
    label_revision: int
    label_definition_version: str

    def __post_init__(self) -> None:
        if not self.prediction_id or not self.entity_key or not self.key_id or not self.label_definition_version:
            raise PerformanceMonitoringError("label identity and definition fields are required")
        if type(self.churned_within_horizon) is not bool or self.label_revision < 1:
            raise PerformanceMonitoringError("label value or revision is invalid")
        _utc(self.outcome_at, "outcome_at")
        _utc(self.received_at, "received_at")


def run_performance_monitoring(
    predictions: Iterable[PredictionEvent], labels: Iterable[DelayedLabel], *,
    config: PerformanceConfig | None = None, as_of: datetime,
    data_origin: DataOrigin, output_dir: Path | None = None,
) -> dict[str, Any]:
    """Join matured predictions to labels and return an immutable evidence report."""
    config = config or PerformanceConfig()
    now = _utc(as_of, "as_of")
    if data_origin not in {"offline_test", "replayed", "synthetic", "production"}:
        raise PerformanceMonitoringError("data_origin is unsupported")
    if data_origin == "production" and not config.allow_production_origin:
        raise PerformanceMonitoringError("production origin requires an approved source-mapping configuration")
    prediction_rows, duplicate_predictions, conflicting_predictions = _deduplicate_predictions(predictions)
    label_rows, duplicate_labels, conflicting_labels = _deduplicate_labels(labels, as_of=now)
    key = _idempotency_key(prediction_rows, label_rows, config, now, data_origin)
    if output_dir:
        existing = output_dir / f"{key}.json"
        if existing.exists():
            return {**json.loads(existing.read_text(encoding="utf-8")), "reused": True}

    matured, immature = _mature_predictions(prediction_rows, config, now)
    _validate_single_lineage(matured)
    matched, unmatched_predictions, unmatched_labels = _join(matured, label_rows)
    _validate_label_definitions(matched)
    coverage = len(matched) / len(matured) if matured else 0.0
    status = _status(matured, matched, coverage, config)
    result = {
        "performance_result_version": PERFORMANCE_RESULT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": key,
        "reused": False,
        "status": status,
        "data_origin": data_origin,
        "as_of": now.isoformat(),
        "config": asdict(config),
        "lineage": _lineage(matured, matched),
        "cohort": _cohort(matured, config),
        "coverage": {
            "mature_prediction_count": len(matured), "joined_label_count": len(matched),
            "ratio": _round(coverage), "minimum_required": config.minimum_label_coverage,
        },
        "reconciliation": {
            "unmatched_prediction_count": len(unmatched_predictions), "unmatched_label_count": len(unmatched_labels),
            "immature_prediction_count": len(immature), "duplicate_prediction_records": duplicate_predictions,
            "duplicate_label_records": duplicate_labels, "conflicting_prediction_records": conflicting_predictions,
            "conflicting_label_records": conflicting_labels,
            "selected_label_revisions": {prediction.prediction_id: label.label_revision for prediction, label in matched},
        },
        "metrics": _metrics(matched, config) if status == "stable" else None,
    }
    if output_dir:
        _write_result(result, output_dir)
    return result


def render_markdown(result: dict[str, Any]) -> str:
    """Render only aggregate M16 evidence, never joined row-level records."""
    coverage = result["coverage"]
    lines = [
        "# M16 Performance Monitoring Report", "", f"Status: **{result['status']}**", f"Data origin: `{result['data_origin']}`", "",
        "## Evidence", "", f"- Mature predictions: `{coverage['mature_prediction_count']}`", f"- Joined labels: `{coverage['joined_label_count']}`", f"- Label coverage: `{coverage['ratio']}`", "",
    ]
    if result["metrics"] is None:
        lines.extend(["## Metrics", "", "Metrics are unavailable until maturity, sample, and coverage requirements are met.", ""])
    else:
        metrics = result["metrics"]
        lines.extend(["## Metrics", "", f"- PR-AUC: `{metrics['pr_auc']}`", f"- ROC-AUC: `{metrics['roc_auc']}`", f"- Brier score: `{metrics['brier_score']}`", ""])
    return "\n".join(lines)


def _deduplicate_predictions(records: Iterable[PredictionEvent]) -> tuple[list[PredictionEvent], int, int]:
    grouped: dict[str, list[PredictionEvent]] = {}
    for record in records:
        grouped.setdefault(record.prediction_id, []).append(record)
    unique: list[PredictionEvent] = []
    duplicates = conflicts = 0
    for _, group in sorted(grouped.items()):
        fingerprints = {_canonical(asdict(record)) for record in group}
        if len(fingerprints) == 1:
            unique.append(group[0]); duplicates += len(group) - 1
        else:
            conflicts += len(group) - 1
    return unique, duplicates, conflicts


def _deduplicate_labels(records: Iterable[DelayedLabel], *, as_of: datetime) -> tuple[list[DelayedLabel], int, int]:
    grouped: dict[tuple[str, int], list[DelayedLabel]] = {}
    for record in records:
        if _utc(record.received_at, "received_at") <= as_of:
            grouped.setdefault((record.prediction_id, record.label_revision), []).append(record)
    latest: dict[str, DelayedLabel] = {}
    duplicates = conflicts = 0
    for (prediction_id, _), group in sorted(grouped.items()):
        fingerprints = {_canonical(asdict(record)) for record in group}
        if len(fingerprints) != 1:
            conflicts += len(group)
            continue
        duplicates += len(group) - 1
        candidate = group[0]
        if prediction_id not in latest or candidate.label_revision > latest[prediction_id].label_revision:
            latest[prediction_id] = candidate
    return [latest[key] for key in sorted(latest)], duplicates, conflicts


def _mature_predictions(records: list[PredictionEvent], config: PerformanceConfig, as_of: datetime) -> tuple[list[PredictionEvent], list[PredictionEvent]]:
    delay = timedelta(days=config.maturity_horizon_days, hours=config.ingestion_grace_hours)
    mature: list[PredictionEvent] = []
    immature: list[PredictionEvent] = []
    for record in records:
        (mature if _utc(record.prediction_at, "prediction_at") + delay <= as_of else immature).append(record)
    return mature, immature


def _validate_single_lineage(records: list[PredictionEvent]) -> None:
    fields = ("model_version", "model_bundle_sha256", "schema_version", "threshold_version", "risk_policy_version", "decision_threshold")
    if any(len({getattr(record, field) for record in records}) > 1 for field in fields):
        raise PerformanceMonitoringError("an evaluation cohort must have one immutable serving lineage")


def _validate_label_definitions(records: list[tuple[PredictionEvent, DelayedLabel]]) -> None:
    if len({label.label_definition_version for _, label in records}) > 1:
        raise PerformanceMonitoringError("an evaluation cohort must have one label definition version")


def _join(predictions: list[PredictionEvent], labels: list[DelayedLabel]) -> tuple[list[tuple[PredictionEvent, DelayedLabel]], list[PredictionEvent], list[DelayedLabel]]:
    labels_by_id = {label.prediction_id: label for label in labels}
    matched: list[tuple[PredictionEvent, DelayedLabel]] = []
    unmatched_predictions: list[PredictionEvent] = []
    for prediction in predictions:
        label = labels_by_id.get(prediction.prediction_id)
        if label is None or (label.entity_key, label.key_id) != (prediction.entity_key, prediction.key_id):
            unmatched_predictions.append(prediction)
        else:
            matched.append((prediction, label))
    matched_label_ids = {label.prediction_id for _, label in matched}
    unmatched_labels = [label for label in labels if label.prediction_id not in matched_label_ids]
    return matched, unmatched_predictions, unmatched_labels


def _status(predictions: list[PredictionEvent], matched: list[tuple[PredictionEvent, DelayedLabel]], coverage: float, config: PerformanceConfig) -> str:
    if not matched:
        return "not_available"
    if len(matched) < config.minimum_mature_labels or coverage < config.minimum_label_coverage:
        return "insufficient_data"
    return "stable"


def _metrics(matched: list[tuple[PredictionEvent, DelayedLabel]], config: PerformanceConfig) -> dict[str, Any]:
    labels = np.array([int(label.churned_within_horizon) for _, label in matched])
    probabilities = np.array([prediction.probability for prediction, _ in matched])
    threshold = matched[0][0].decision_threshold
    decisions = (probabilities >= threshold).astype(int)
    matrix = confusion_matrix(labels, decisions, labels=[0, 1]).ravel()
    roc_auc = float(roc_auc_score(labels, probabilities)) if len(set(labels)) == 2 else None
    return {
        "pr_auc": _round(float(average_precision_score(labels, probabilities))), "roc_auc": _round(roc_auc) if roc_auc is not None else None,
        "precision": _round(float(precision_score(labels, decisions, zero_division=0))), "recall": _round(float(recall_score(labels, decisions, zero_division=0))),
        "f1": _round(float(f1_score(labels, decisions, zero_division=0))), "brier_score": _round(float(brier_score_loss(labels, probabilities))),
        "decision_threshold": threshold, "confusion_matrix": {"tn": int(matrix[0]), "fp": int(matrix[1]), "fn": int(matrix[2]), "tp": int(matrix[3])},
        "calibration": _calibration(labels, probabilities, config.probability_bin_edges),
    }


def _calibration(labels: np.ndarray, probabilities: np.ndarray, edges: tuple[float, ...]) -> list[dict[str, Any]]:
    bins = np.digitize(probabilities, edges[1:-1], right=False)
    return [{"lower": edges[index], "upper": edges[index + 1], "count": int((bins == index).sum()),
             "mean_probability": _round(float(probabilities[bins == index].mean())) if (bins == index).any() else None,
             "observed_rate": _round(float(labels[bins == index].mean())) if (bins == index).any() else None}
            for index in range(len(edges) - 1)]


def _lineage(predictions: list[PredictionEvent], matched: list[tuple[PredictionEvent, DelayedLabel]]) -> dict[str, Any]:
    if not predictions:
        return {}
    prediction = predictions[0]
    definitions = sorted({label.label_definition_version for _, label in matched})
    return {"model_version": prediction.model_version, "model_bundle_sha256": prediction.model_bundle_sha256,
            "schema_version": prediction.schema_version, "threshold_version": prediction.threshold_version,
            "risk_policy_version": prediction.risk_policy_version, "label_definition_versions": definitions}


def _cohort(predictions: list[PredictionEvent], config: PerformanceConfig) -> dict[str, Any]:
    if not predictions:
        return {"kind": "monthly", "utc_months": [], "prediction_count": 0}
    months = sorted({prediction.prediction_at.astimezone(timezone.utc).strftime("%Y-%m") for prediction in predictions})
    indices = [int(month[:4]) * 12 + int(month[5:]) for month in months]
    if len(months) > config.maximum_rolling_cohorts or any(right - left != 1 for left, right in zip(indices, indices[1:])):
        raise PerformanceMonitoringError("evaluation months must be contiguous and within the rolling-cohort limit")
    return {"kind": "monthly" if len(months) == 1 else "rolling", "utc_months": months, "prediction_count": len(predictions)}


def _idempotency_key(predictions: list[PredictionEvent], labels: list[DelayedLabel], config: PerformanceConfig, as_of: datetime, origin: str) -> str:
    value = {"predictions": sorted((_canonical(asdict(item)) for item in predictions)), "labels": sorted((_canonical(asdict(item)) for item in labels)),
             "config": asdict(config), "as_of": as_of.isoformat(), "data_origin": origin}
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_result(result: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_dir / result["idempotency_key"]
    stem.with_suffix(".json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(result), encoding="utf-8")


def _canonical(value: Any) -> str:
    return json.dumps(value, default=lambda item: item.isoformat() if isinstance(item, datetime) else item, sort_keys=True, separators=(",", ":"))


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PerformanceMonitoringError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _sha(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value.lower()):
        raise PerformanceMonitoringError(f"{name} must be a SHA-256 hex digest")


def _round(value: float) -> float:
    return round(value, 8)
