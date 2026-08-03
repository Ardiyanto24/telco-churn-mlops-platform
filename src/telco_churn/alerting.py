"""M17 candidate alerting and retraining-recommendation workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Literal


ALERT_RESULT_VERSION = "telco-churn-alerting/v1"
AlertDomain = Literal["operational", "data_quality", "drift", "performance"]


class AlertingError(ValueError):
    """Raised for invalid alert evidence or lifecycle transitions."""


@dataclass(frozen=True)
class AlertConfig:
    version: str = "m17-candidate/v1"
    candidate_mode: bool = True
    persistence_windows: int = 2
    maximum_consecutive_gap_days: int = 2
    minimum_performance_sample_size: int = 500
    minimum_performance_coverage: float = .80

    def __post_init__(self) -> None:
        if self.persistence_windows < 2 or self.maximum_consecutive_gap_days < 1:
            raise AlertingError("persistence configuration is invalid")
        if self.minimum_performance_sample_size < 1 or not 0 < self.minimum_performance_coverage <= 1:
            raise AlertingError("performance evidence configuration is invalid")
        if not self.candidate_mode:
            raise AlertingError("production alert delivery requires a future approved M17 policy")


@dataclass(frozen=True)
class AlertEvidence:
    source_result_id: str
    domain: AlertDomain
    source_status: Literal["stable", "warning", "critical", "unknown", "insufficient_data", "not_available"]
    signal: str
    window_id: str
    window_end: datetime
    sample_size: int
    label_coverage: float | None
    model_version: str
    baseline_id: str | None
    config_version: str
    data_origin: Literal["offline_test", "replayed", "synthetic", "production"]

    def __post_init__(self) -> None:
        if not all((self.source_result_id, self.signal, self.window_id, self.model_version, self.config_version)):
            raise AlertingError("alert evidence identity and lineage fields are required")
        if self.domain not in {"operational", "data_quality", "drift", "performance"}:
            raise AlertingError("alert evidence domain is unsupported")
        if self.sample_size < 0 or self.label_coverage is not None and not 0 <= self.label_coverage <= 1:
            raise AlertingError("alert evidence sample or coverage is invalid")
        _utc(self.window_end, "window_end")


def evaluate_alerts(evidence: Iterable[AlertEvidence], *, config: AlertConfig | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    """Produce idempotent candidate alerts and non-actioning recommendations."""
    config = config or AlertConfig()
    evidence_rows = sorted(evidence, key=lambda item: (item.window_end, item.source_result_id))
    key = _idempotency_key(evidence_rows, config)
    if output_dir:
        existing = output_dir / f"{key}.json"
        if existing.exists():
            return {**json.loads(existing.read_text(encoding="utf-8")), "reused": True}
    alerts = _qualify_alerts(evidence_rows, config)
    recommendations = [_recommendation(alert, config) for alert in alerts if _should_recommend(alert, config)]
    result = {
        "alerting_result_version": ALERT_RESULT_VERSION,
        "idempotency_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reused": False,
        "mode": "candidate",
        "config": asdict(config),
        "alerts": alerts,
        "recommendations": recommendations,
    }
    if output_dir:
        _write_result(result, output_dir)
    return result


def transition_alert(alert: dict[str, Any], *, action: Literal["acknowledge", "resolve", "suppress"], actor_id: str, reason: str, at: datetime) -> dict[str, Any]:
    """Append an attributable lifecycle action without mutating the source alert."""
    if not actor_id or not reason:
        raise AlertingError("actor_id and reason are required")
    state = alert.get("state")
    allowed = {"open": {"acknowledge", "suppress"}, "acknowledged": {"resolve", "suppress"}}
    if action not in allowed.get(state, set()):
        raise AlertingError(f"cannot {action} an alert in state {state!r}")
    history = [*alert.get("history", []), {"action": action, "actor_id": actor_id, "reason": reason, "at": _utc(at, "at").isoformat()}]
    next_state = {"acknowledge": "acknowledged", "resolve": "resolved", "suppress": "suppressed"}[action]
    return {**alert, "state": next_state, "history": history}


def render_markdown(result: dict[str, Any]) -> str:
    """Render aggregate candidate alert evidence without row-level data."""
    lines = ["# M17 Alerting Report", "", f"Mode: `{result['mode']}`", f"Alerts: `{len(result['alerts'])}`", "", "## Alerts", ""]
    for alert in result["alerts"]:
        lines.append(f"- `{alert['severity']}` `{alert['domain']}` / `{alert['signal']}`: `{alert['state']}`")
    lines.extend(["", "## Safety boundary", "", "- Recommendations are candidates; they do not retrain, promote, roll back, or change thresholds.", ""])
    return "\n".join(lines)


def _qualify_alerts(evidence: list[AlertEvidence], config: AlertConfig) -> list[dict[str, Any]]:
    grouped: dict[str, list[AlertEvidence]] = {}
    for item in evidence:
        if _is_qualifying(item):
            grouped.setdefault(_family_key(item), []).append(item)
    alerts: list[dict[str, Any]] = []
    for family, group in sorted(grouped.items()):
        group.sort(key=lambda item: (item.window_end, item.source_result_id))
        latest = group[-1]
        immediate = _is_immediate(latest)
        count = _consecutive_count(group, config)
        if immediate or count >= config.persistence_windows:
            alerts.append(_alert(family, latest, count, config))
    return alerts


def _is_qualifying(item: AlertEvidence) -> bool:
    return item.source_status in {"warning", "critical", "unknown"}


def _is_immediate(item: AlertEvidence) -> bool:
    return item.domain == "operational" and item.source_status == "unknown" or item.domain == "data_quality" and item.source_status == "critical" or item.domain == "performance" and item.source_status == "critical"


def _consecutive_count(group: list[AlertEvidence], config: AlertConfig) -> int:
    count = 1
    for current, previous in zip(reversed(group), reversed(group[:-1])):
        if _utc(current.window_end, "window_end") - _utc(previous.window_end, "window_end") > timedelta(days=config.maximum_consecutive_gap_days):
            break
        count += 1
    return count


def _alert(family: str, item: AlertEvidence, count: int, config: AlertConfig) -> dict[str, Any]:
    severity = "critical" if _is_immediate(item) else "warning"
    alert_id = sha256(json.dumps({"family": family, "config": asdict(config)}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "alert_id": alert_id, "domain": item.domain, "severity": severity, "state": "open", "signal": item.signal,
        "reason": f"{item.domain}:{item.source_status}", "source_result_id": item.source_result_id,
        "window": {"id": item.window_id, "end": _utc(item.window_end, "window_end").isoformat()},
        "sample_size": item.sample_size, "label_coverage": item.label_coverage, "model_version": item.model_version,
        "baseline_id": item.baseline_id, "config_version": item.config_version, "data_origin": item.data_origin,
        "persistence_count": count, "policy_version": config.version, "history": [],
    }


def _should_recommend(alert: dict[str, Any], config: AlertConfig) -> bool:
    return alert["domain"] == "performance" and alert["severity"] == "critical" and alert["sample_size"] >= config.minimum_performance_sample_size and (alert["label_coverage"] or 0) >= config.minimum_performance_coverage


def _recommendation(alert: dict[str, Any], config: AlertConfig) -> dict[str, Any]:
    content = {"alert_id": alert["alert_id"], "policy_version": config.version, "source_result_id": alert["source_result_id"]}
    identifier = sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "recommendation_id": identifier, "status": "candidate", "alert_id": alert["alert_id"], "source_result_id": alert["source_result_id"],
        "data_origin": alert["data_origin"], "model_version": alert["model_version"], "baseline_id": alert["baseline_id"],
        "sample_size": alert["sample_size"], "label_coverage": alert["label_coverage"], "promotion_approved": False,
        "required_next_steps": ["M5", "M6", "M7", "M8", "M11"],
    }


def _family_key(item: AlertEvidence) -> str:
    value = {"domain": item.domain, "signal": item.signal, "model_version": item.model_version, "baseline_id": item.baseline_id,
             "config_version": item.config_version, "data_origin": item.data_origin}
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _idempotency_key(evidence: list[AlertEvidence], config: AlertConfig) -> str:
    value = {"evidence": [_canonical(asdict(item)) for item in evidence], "config": asdict(config)}
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
        raise AlertingError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)
