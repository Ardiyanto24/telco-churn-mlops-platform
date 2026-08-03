"""M19 sanitised public-snapshot exporter contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any

from telco_churn.metrics_store import MetricsStore, MetricsStoreError


class PublicMetricsError(ValueError):
    """Raised when a public snapshot would violate the v1 contract."""


@dataclass(frozen=True)
class PublicMetricsConfig:
    """Conservative, versioned M19 policy supplied by trusted deployment config."""

    allowed_origins: tuple[str, ...]
    minimum_group_size: int = 100
    freshness_target: timedelta = timedelta(days=1)
    rate_limit_per_minute: int = 60
    candidate_mode: bool = True

    def __post_init__(self) -> None:
        if not self.allowed_origins or any(not item.startswith(("https://", "http://localhost")) for item in self.allowed_origins):
            raise PublicMetricsError("allowed_origins must contain explicit HTTP(S) origins")
        if self.minimum_group_size < 1 or self.freshness_target <= timedelta(0) or self.rate_limit_per_minute < 1:
            raise PublicMetricsError("public metrics configuration is invalid")


def config_from_mapping(value: object) -> PublicMetricsConfig:
    """Validate trusted JSON configuration at the script boundary."""
    if not isinstance(value, Mapping):
        raise PublicMetricsError("public metrics config must be an object")
    allowed_origins = value.get("allowed_origins")
    if not isinstance(allowed_origins, list) or not all(isinstance(item, str) for item in allowed_origins):
        raise PublicMetricsError("allowed_origins must be a string list")
    if not isinstance(value.get("candidate_mode", True), bool):
        raise PublicMetricsError("candidate_mode must be a boolean")
    return PublicMetricsConfig(
        allowed_origins=tuple(allowed_origins), minimum_group_size=value.get("minimum_group_size", 100),
        freshness_target=timedelta(seconds=value.get("freshness_target_seconds", 86400)),
        rate_limit_per_minute=value.get("rate_limit_per_minute", 60), candidate_mode=value.get("candidate_mode", True),
    )


_PUBLIC_METRICS = {
    "telemetry": {"request_count", "success_rate", "error_rate", "latency_p95_ms"},
    "monitoring": {"drifted_feature_count", "quality_issue_count", "prediction_psi"},
    "performance": {"roc_auc", "pr_auc", "precision", "recall", "f1", "brier_score"},
    "alert": {"open_alert_count", "critical_alert_count"},
    "recommendation": {"recommendation_count"},
}


def export_public_snapshot(
    *, store: MetricsStore, config: PublicMetricsConfig, now: datetime,
    source_loader: Callable[[], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Build, validate, and atomically publish one public snapshot.

    Any source/export failure preserves the previous completed snapshot as stale.
    """
    current = _utc(now, "now")
    try:
        records = (source_loader or store.public_source_records)()
        snapshot = _build_snapshot(records=records, config=config, now=current)
        store.publish_public_snapshot(snapshot)
        return snapshot
    except (MetricsStoreError, PublicMetricsError, OSError, RuntimeError, TypeError, KeyError, json.JSONDecodeError):
        return store.retain_public_snapshot_after_failure(now=current, reason="export_failed")


def _build_snapshot(*, records: list[dict[str, Any]], config: PublicMetricsConfig, now: datetime) -> dict[str, Any]:
    if not isinstance(records, list):
        raise PublicMetricsError("export source must be a record list")
    source_rows = [_validated_source(item) for item in records]
    origins = sorted({item["data_origin"] for item in source_rows})
    categorized = {"service": [], "monitoring": [], "performance": [], "alerts": [], "recommendations": []}
    for item in source_rows:
        result = _public_result(item, config.minimum_group_size)
        destination = {"telemetry": "service", "monitoring": "monitoring", "performance": "performance", "alert": "alerts", "recommendation": "recommendations"}.get(item["result_type"])
        if destination and len(categorized[destination]) < 100:
            categorized[destination].append(result)
    latest = source_rows[0] if source_rows else None
    snapshot: dict[str, Any] = {
        "schema_version": "public_metrics/v1",
        "generated_at": _iso(now),
        "freshness": {"state": "fresh", "target_seconds": int(config.freshness_target.total_seconds())},
        "overview": {
            "evidence_state": latest["status"] if latest else "not_available",
            "data_origins": origins,
            "latest_observed_window_end": latest["window_end"] if latest else None,
            "candidate_mode": config.candidate_mode,
        },
        "models": {"current": _current_model(latest), "history": _model_history(source_rows)},
        "service": {"history": categorized["service"]},
        "monitoring": {"history": categorized["monitoring"]},
        "performance": {"history": categorized["performance"]},
        "alerts": {"history": categorized["alerts"]},
        "recommendations": {"history": categorized["recommendations"]},
        "methodology": {"candidate_mode": config.candidate_mode, "minimum_group_size": config.minimum_group_size, "data_origin_required": True},
    }
    snapshot["snapshot_id"] = _snapshot_id(snapshot)
    return snapshot


def _validated_source(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicMetricsError("source result must be an object")
    required = {"result_id", "result_type", "status", "data_origin", "window_start", "window_end", "sample_size", "model_version", "summary"}
    if not required.issubset(value):
        raise PublicMetricsError("source result misses public-export lineage")
    if value["result_type"] not in _PUBLIC_METRICS or value["status"] not in {"stable", "warning", "critical", "unknown", "insufficient_data", "not_available"}:
        raise PublicMetricsError("source result type or evidence state is unsupported")
    if value["data_origin"] not in {"offline_test", "replayed", "synthetic", "production"} or not isinstance(value["sample_size"], int):
        raise PublicMetricsError("source result origin or sample size is invalid")
    if not isinstance(value["summary"], Mapping):
        raise PublicMetricsError("source summary is invalid")
    return dict(value)


def _public_result(source: Mapping[str, Any], minimum_group_size: int) -> dict[str, Any]:
    if source["sample_size"] < minimum_group_size:
        return {"data_origin": source["data_origin"], "evidence_state": "suppressed", "result_type": source["result_type"], "suppression_reason": "minimum_group_size"}
    metrics = {key: value for key, value in source["summary"].items() if key in _PUBLIC_METRICS[source["result_type"]] and isinstance(value, (int, float)) and not isinstance(value, bool)}
    return {
        "result_type": source["result_type"], "evidence_state": source["status"], "data_origin": source["data_origin"],
        "observed_window": {"start": source["window_start"], "end": source["window_end"]},
        "sample_size": source["sample_size"], "label_coverage": source.get("label_coverage"), "metrics": metrics,
    }


def _current_model(latest: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if latest is None:
        return None
    return {"model_version": latest["model_version"], "data_origin": latest["data_origin"], "observed_window_end": latest["window_end"]}


def _model_history(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    history: list[dict[str, Any]] = []
    for row in rows:
        model_version = row["model_version"]
        if model_version not in seen:
            seen.add(model_version)
            history.append({"model_version": model_version, "data_origin": row["data_origin"], "latest_observed_window_end": row["window_end"]})
    return history


def _snapshot_id(snapshot: Mapping[str, Any]) -> str:
    return "public-" + sha256(_canonical(snapshot).encode("utf-8")).hexdigest()[:20]


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PublicMetricsError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
