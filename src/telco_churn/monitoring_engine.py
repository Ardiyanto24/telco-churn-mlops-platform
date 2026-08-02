"""Privacy-minimised, batch data-quality and drift monitoring for M14."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import chisquare, false_discovery_control, wasserstein_distance

from .monitoring_baseline import BaselineError, validate_baseline


MONITORING_RESULT_VERSION = "telco-churn-monitoring/v1"
_SEVERITY = {"stable": 0, "watch": 1, "warning": 2, "critical": 3, "insufficient_data": -1, "unknown": 4}


@dataclass(frozen=True)
class MonitoringConfig:
    """Provisional M14 thresholds retained for M15 calibration, never production alerts."""

    version: str = "m14-experimental/v1"
    status: str = "experimental"
    minimum_sample_size: int = 30
    max_prediction_rows: int = 10_000
    fdr_method: str = "bh"
    fdr_alpha: float = 0.05
    quality_delta: tuple[float, float, float] = (0.01, 0.05, 0.15)
    psi: tuple[float, float, float] = (0.10, 0.20, 0.30)
    jensen_shannon: tuple[float, float, float] = (0.05, 0.10, 0.20)
    wasserstein_normalized: tuple[float, float, float] = (0.05, 0.10, 0.20)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_monitoring(
    frame: pd.DataFrame, *, baseline: dict[str, Any], bundle: Any,
    config: MonitoringConfig | None = None, current_window: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Return one auditable result; unsafe prerequisites become ``unknown``."""
    config = config or MonitoringConfig()
    key = _idempotency_key(baseline, bundle, config, current_window)
    if output_dir:
        existing = output_dir / f"{key}.json"
        if existing.exists():
            result = json.loads(existing.read_text(encoding="utf-8"))
            return {**result, "reused": True}
    try:
        result = _analyze(frame, baseline=baseline, bundle=bundle, config=config, current_window=current_window, key=key)
    except BaselineError:
        result = _unknown_result(key, baseline, bundle, config, current_window, "baseline_incompatible")
    except (KeyError, TypeError, ValueError):
        result = _unknown_result(key, baseline, bundle, config, current_window, "current_window_incompatible")
    except Exception:
        result = _unknown_result(key, baseline, bundle, config, current_window, "monitoring_failure")
    if output_dir:
        _write_result(result, output_dir)
    return {**result, "reused": False}


def render_markdown(result: dict[str, Any]) -> str:
    """Render only aggregate, lineage-safe monitoring evidence."""
    lines = [
        "# M14 Monitoring Report", "", f"Run status: **{result['run_status']}**",
        f"Mode: `{result['config']['status']}`", "",
        "## Lineage", "",
        f"- Baseline: `{result['lineage'].get('baseline_id', 'unavailable')}`",
        f"- Model: `{result['lineage'].get('model_version', 'unavailable')}`",
        f"- Window checksum: `{result['current_window'].get('sha256', 'unavailable')}`", "",
        "## Feature status", "", "| Feature | Quality | Distribution | Overall |", "|---|---|---|---|",
    ]
    for feature, item in result.get("feature_results", {}).items():
        lines.append(f"| {feature} | {item['quality']['status']} | {item['distribution']['status']} | {item['status']} |")
    if result.get("error"):
        lines.extend(["", "## Safe error", "", f"- Classification: `{result['error']['classification']}`"])
    lines.extend(["", "## Limitation", "", "- Severity is experimental until M15 calibration; this report does not trigger production alerts or retraining.", ""])
    return "\n".join(lines)


def _analyze(frame: pd.DataFrame, *, baseline: dict[str, Any], bundle: Any, config: MonitoringConfig,
             current_window: dict[str, Any], key: str) -> dict[str, Any]:
    manifest = bundle.manifest
    features = tuple(baseline["lineage"]["raw_feature_order"])
    validate_baseline(baseline, model_version=manifest.model_version, schema_version=manifest.schema_version, feature_order=features)
    _validate_window(frame, features, current_window)
    if len(frame) < config.minimum_sample_size:
        return _base_result(key, baseline, manifest, config, current_window, "insufficient_data", {})
    results = {
        feature: _feature_result(frame[feature], baseline["input_reference"]["features"][feature], config)
        for feature in features
    }
    _apply_fdr(results, config)
    prediction_frame = _prediction_sample(frame.loc[:, list(features)], config, current_window)
    records = prediction_frame.to_dict(orient="records")
    probabilities = list(bundle.predict_probabilities(records))
    if len(probabilities) != len(prediction_frame) or any(not 0 <= value <= 1 for value in probabilities):
        raise ValueError("prediction output is incompatible")
    prediction = _prediction_result(probabilities, baseline["prediction_reference"], baseline["lineage"], config)
    run_status = _maximum_status([item["status"] for item in results.values()] + [prediction["status"]])
    return _base_result(key, baseline, manifest, config, current_window, run_status, results, prediction)


def _feature_result(series: pd.Series, reference: dict[str, Any], config: MonitoringConfig) -> dict[str, Any]:
    quality = _quality(series, reference, config)
    if reference["type"] == "numeric":
        distribution = _numeric_distribution(series, reference, config)
    else:
        distribution = _categorical_distribution(series, reference, config)
    return {"quality": quality, "distribution": distribution, "status": _maximum_status([quality["status"], distribution["status"]])}


def _quality(series: pd.Series, reference: dict[str, Any], config: MonitoringConfig) -> dict[str, Any]:
    missing = float(series.isna().mean())
    invalid = unknown = out_of_range = 0.0
    if reference["type"] == "numeric":
        numeric = pd.to_numeric(series, errors="coerce")
        invalid = float((series.notna() & numeric.isna()).mean())
        summary = reference["summary"]
        out_of_range = float(((numeric < summary["min"]) | (numeric > summary["max"])).fillna(False).mean())
    else:
        values = series.fillna("__MISSING__").astype(str)
        known = set(reference["category_counts"])
        unknown = float((~values.isin(known)).mean())
    deltas = [
        max(0.0, missing - float(reference.get("missing_rate", 0.0))), invalid,
        max(0.0, unknown - float(reference.get("unknown_rate", 0.0))), out_of_range,
    ]
    return {"missing_rate": _round(missing), "invalid_rate": _round(invalid), "unknown_rate": _round(unknown),
            "out_of_range_rate": _round(out_of_range), "baseline_missing_rate": reference.get("missing_rate", 0.0),
            "status": _status(max(deltas), config.quality_delta), "parameters": {"thresholds": list(config.quality_delta)}}


def _numeric_distribution(series: pd.Series, reference: dict[str, Any], config: MonitoringConfig) -> dict[str, Any]:
    current = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if len(current) < config.minimum_sample_size:
        return {"status": "insufficient_data", "reason": "too_few_valid_numeric_values"}
    edges = [float(value) for value in reference["bin_edges"]]
    ref_counts = _ordered_bin_counts(reference["bin_counts"], edges)
    current_counts = _cut_counts(current, edges)
    psi = _psi(ref_counts, current_counts)
    centers = np.array([(edges[index] + edges[index + 1]) / 2 for index in range(len(edges) - 1)])
    span = max(edges[-1] - edges[0], 1.0)
    if current_counts.sum() > 0:
        wasserstein = float(wasserstein_distance(centers, centers, u_weights=ref_counts, v_weights=current_counts))
        normalized = wasserstein / span
        wasserstein_result: dict[str, Any] = {"effect_size": _round(wasserstein), "normalized_effect_size": _round(normalized), "p_value": None,
                                               "sample_size": int(len(current)), "parameters": {"reference": "frozen_bin_midpoints", "normalizer": span}}
        wasserstein_status = _status(normalized, config.wasserstein_normalized)
    else:
        wasserstein_result = {"status": "not_applicable", "reason": "no_current_values_within_frozen_reference_bins"}
        wasserstein_status = "stable"
    return {
        "status": _maximum_status([_status(psi, config.psi), wasserstein_status]),
        "psi": {"effect_size": _round(psi), "p_value": None, "sample_size": int(len(current)), "parameters": {"bin_edges": edges, "epsilon": 1e-6}},
        "wasserstein": wasserstein_result,
        "ks": {"status": "not_applicable", "reason": "aggregate_baseline_has_no_raw_reference_sample"},
    }


def _categorical_distribution(series: pd.Series, reference: dict[str, Any], config: MonitoringConfig) -> dict[str, Any]:
    values = series.fillna("__MISSING__").astype(str)
    known = set(reference["category_counts"])
    aligned = sorted(known | {"__UNKNOWN__"})
    current_counts = np.array([int((values == category).sum()) if category != "__UNKNOWN__" else int((~values.isin(known)).sum()) for category in aligned], dtype=float)
    reference_counts = np.array([float(reference["category_counts"].get(category, 0)) for category in aligned], dtype=float)
    jsd = float(jensenshannon(reference_counts, current_counts))
    expected = reference_counts / reference_counts.sum() * current_counts.sum()
    chi = {"status": "not_applicable", "reason": "expected_count_below_five"}
    if len(current_counts) > 1 and np.all(expected >= 5):
        statistic, pvalue = chisquare(current_counts, f_exp=expected)
        chi = {"status": "measured", "effect_size": _round(float(statistic)), "p_value": _round(float(pvalue)), "sample_size": int(current_counts.sum()), "parameters": {"expected_count_minimum": 5}}
    return {"status": _status(jsd, config.jensen_shannon),
            "jensen_shannon": {"effect_size": _round(jsd), "p_value": None, "sample_size": int(current_counts.sum()), "parameters": {"support": aligned}},
            "chi_square": chi}


def _prediction_result(probabilities: list[float], reference: dict[str, Any], lineage: dict[str, Any], config: MonitoringConfig) -> dict[str, Any]:
    series = pd.Series(probabilities, dtype=float)
    edges = [float(value) for value in reference["probability"]["bin_edges"]]
    psi = _psi(_ordered_bin_counts(reference["probability"]["bin_counts"], edges), _cut_counts(series, edges))
    threshold = float(lineage["decision_threshold"])
    bands = lineage["risk_bands"]
    return {"status": _status(psi, config.psi), "probability": {"psi": {"effect_size": _round(psi), "p_value": None, "sample_size": len(series), "parameters": {"bin_edges": edges}}, "mean": _round(float(series.mean()))},
            "churn_rate": _round(float((series >= threshold).mean())),
            "risk_band_counts": _risk_bands(probabilities, reference, threshold=threshold, low=float(bands["low"]), high=float(bands["high"]))}


def _apply_fdr(results: dict[str, dict[str, Any]], config: MonitoringConfig) -> None:
    candidates = [(feature, item["distribution"]["chi_square"]) for feature, item in results.items()
                  if item["distribution"].get("chi_square", {}).get("status") == "measured"]
    if not candidates:
        return
    adjusted = false_discovery_control([item["p_value"] for _, item in candidates], method=config.fdr_method)
    for (_, item), value in zip(candidates, adjusted):
        item["adjusted_p_value"] = _round(float(value))
        item["parameters"]["multiple_testing"] = {"method": config.fdr_method, "alpha": config.fdr_alpha}


def _base_result(key: str, baseline: dict[str, Any], manifest: Any, config: MonitoringConfig,
                 current_window: dict[str, Any], status: str, features: dict[str, Any], prediction: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"monitoring_result_version": MONITORING_RESULT_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "idempotency_key": key, "reused": False,
            "run_status": status, "config": config.to_dict(), "current_window": dict(current_window),
            "lineage": {"baseline_id": baseline.get("baseline_id"), "baseline_sha256": baseline.get("sha256"),
                        "baseline_status": baseline.get("status"), "model_version": getattr(manifest, "model_version", None),
                        "schema_version": getattr(manifest, "schema_version", None)}, "feature_results": features,
            "prediction": prediction or {"status": "unknown", "reason": "monitoring_not_completed"}}


def _unknown_result(key: str, baseline: dict[str, Any], bundle: Any, config: MonitoringConfig,
                    current_window: dict[str, Any], classification: str) -> dict[str, Any]:
    result = _base_result(key, baseline, getattr(bundle, "manifest", None), config, current_window, "unknown", {})
    result["error"] = {"classification": classification}
    return result


def _validate_window(frame: pd.DataFrame, features: tuple[str, ...], current_window: dict[str, Any]) -> None:
    if not isinstance(current_window.get("sha256"), str) or len(current_window["sha256"]) != 64:
        raise ValueError("current window checksum is required")
    missing = set(features) - set(frame.columns)
    if missing:
        raise ValueError("current window feature contract is incomplete")
    unsupported = set(frame.columns) - set(features) - {"id", "customerID", "Churn"}
    if unsupported:
        raise ValueError("current window contains unsupported monitoring columns")


def _prediction_sample(frame: pd.DataFrame, config: MonitoringConfig, current_window: dict[str, Any]) -> pd.DataFrame:
    if config.max_prediction_rows < config.minimum_sample_size:
        raise ValueError("max prediction rows must not be lower than the minimum sample size")
    if len(frame) <= config.max_prediction_rows:
        return frame
    seed = int(str(current_window["sha256"])[:16], 16) % (2**32)
    return frame.sample(n=config.max_prediction_rows, random_state=seed).sort_index()


def _idempotency_key(baseline: dict[str, Any], bundle: Any, config: MonitoringConfig, current_window: dict[str, Any]) -> str:
    value = {"baseline_id": baseline.get("baseline_id"), "model_version": getattr(getattr(bundle, "manifest", None), "model_version", None),
             "config": config.to_dict(), "current_window": current_window}
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_result(result: dict[str, Any], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / result["idempotency_key"]
    stem.with_suffix(".json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(result), encoding="utf-8")


def _ordered_bin_counts(counts: dict[str, int], edges: list[float]) -> np.ndarray:
    return np.array([float(value) for value in counts.values()], dtype=float)


def _cut_counts(values: pd.Series, edges: list[float]) -> np.ndarray:
    bins = pd.cut(values, bins=edges, include_lowest=True, duplicates="drop")
    return bins.value_counts(sort=False).to_numpy(dtype=float)


def _psi(reference: np.ndarray, current: np.ndarray) -> float:
    reference = reference / max(reference.sum(), 1.0)
    current = current / max(current.sum(), 1.0)
    epsilon = 1e-6
    return float(np.sum((current - reference) * np.log((current + epsilon) / (reference + epsilon))))


def _risk_bands(probabilities: list[float], reference: dict[str, Any], *, threshold: float, low: float, high: float) -> dict[str, int]:
    counts = {name: 0 for name in reference["risk_band_counts"]}
    # The exact serving thresholds are bound in baseline lineage; no raw predictions are retained.
    for value in probabilities:
        counts["HIGH" if value >= high else "MEDIUM" if value >= threshold else "LOW" if value >= low else "SAFE"] += 1
    return counts


def _status(value: float, thresholds: tuple[float, float, float]) -> str:
    if value >= thresholds[2]: return "critical"
    if value >= thresholds[1]: return "warning"
    if value >= thresholds[0]: return "watch"
    return "stable"


def _maximum_status(statuses: list[str]) -> str:
    return max(statuses, key=lambda status: _SEVERITY[status]) if statuses else "stable"


def _round(value: float) -> float:
    return round(value, 8)
