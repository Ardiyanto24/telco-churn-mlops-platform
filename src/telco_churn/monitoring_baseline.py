"""Deterministic, immutable reference-baseline artifacts for M13."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd


BASELINE_VERSION = "telco-churn-baseline/v1"
_PROBABILITY_EDGES = [round(index / 10, 1) for index in range(11)]
_TELEMETRY_FEATURES = {"Contract", "InternetService", "PaymentMethod", "tenure", "MonthlyCharges"}


class BaselineError(ValueError):
    """Raised when a reference baseline is malformed or incompatible."""


def build_baseline(
    frame: pd.DataFrame,
    *,
    dataset_manifest: dict[str, Any],
    bundle: Any,
    model_manifest_sha256: str | None = None,
    reference_population: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build canonical baseline content without storing source rows or identifiers."""
    manifest = bundle.manifest
    features = tuple(column for column in frame.columns if column not in {"id", "customerID", "Churn"})
    if not features:
        raise BaselineError("reference data has no non-identifier inference features")
    if not isinstance(dataset_manifest.get("sha256"), str):
        raise BaselineError("verified dataset manifest checksum is required")

    feature_reference = {feature: _feature_stats(frame[feature]) for feature in features}
    records = frame.loc[:, list(features)].to_dict(orient="records")
    probabilities = list(bundle.predict_probabilities(records))
    if len(probabilities) != len(records) or any(not 0 <= value <= 1 for value in probabilities):
        raise BaselineError("bundle predictions do not match the reference population")
    population = reference_population or {"split": "train", "filters": [], "origin": "M5 validated training split"}
    content: dict[str, Any] = {
        "baseline_version": BASELINE_VERSION,
        "status": "provisional",
        "lineage": {
            "dataset_manifest_sha256": dataset_manifest["sha256"],
            "model_version": manifest.model_version,
            "model_manifest_sha256": model_manifest_sha256 or _manifest_identity(manifest),
            "schema_version": manifest.schema_version,
            "raw_feature_order": list(features),
            "transformed_feature_signature": list(manifest.feature_order),
            "decision_threshold": manifest.decision_threshold,
            "risk_bands": {"low": manifest.low_risk_threshold, "high": manifest.high_risk_threshold},
        },
        "reference_population": {**population, "sample_size": len(frame)},
        "input_reference": {"features": feature_reference},
        "telemetry_reference": {
            "coverage": sorted(feature for feature in features if feature in _TELEMETRY_FEATURES),
            "features": {feature: feature_reference[feature] for feature in features if feature in _TELEMETRY_FEATURES},
        },
        "prediction_reference": _prediction_stats(probabilities, manifest),
    }
    identity = _canonical_hash(content)
    return {**content, "baseline_id": identity, "sha256": identity}


def validate_baseline(
    baseline: dict[str, Any], *, model_version: str, schema_version: str,
    feature_order: Sequence[str],
) -> None:
    """Fail closed unless baseline content is intact and matches the serving contract."""
    try:
        content = {key: value for key, value in baseline.items() if key not in {"baseline_id", "sha256"}}
        if baseline["baseline_version"] != BASELINE_VERSION or baseline["status"] not in {"provisional", "approved"}:
            raise BaselineError("baseline has an unsupported version or status")
        if baseline["baseline_id"] != baseline["sha256"] or baseline["sha256"] != _canonical_hash(content):
            raise BaselineError("baseline checksum does not match content")
        lineage = baseline["lineage"]
        if lineage["model_version"] != model_version or lineage["schema_version"] != schema_version:
            raise BaselineError("baseline model or schema version is incompatible")
        if tuple(lineage["raw_feature_order"]) != tuple(feature_order):
            raise BaselineError("baseline feature contract is incompatible")
        if set(baseline["input_reference"]["features"]) != set(feature_order):
            raise BaselineError("baseline feature statistics are incomplete")
    except (KeyError, TypeError) as error:
        raise BaselineError("baseline artifact is malformed") from error


def write_baseline(baseline: dict[str, Any], destination: Path) -> Path:
    """Write once; callers must create a new content-addressed destination."""
    if destination.exists():
        raise BaselineError("baseline artifacts are immutable; destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def _feature_stats(series: pd.Series) -> dict[str, Any]:
    missing_rate = round(float(series.isna().mean()), 8)
    if pd.api.types.is_numeric_dtype(series):
        values = series.dropna().astype(float)
        edges = _quantile_edges(values)
        return {
            "type": "numeric", "sample_size": len(series), "missing_rate": missing_rate,
            "summary": {name: round(float(values.quantile(q)), 8) for name, q in {"min": 0, "p01": .01, "p05": .05, "p25": .25, "p50": .5, "p75": .75, "p95": .95, "p99": .99, "max": 1}.items()},
            "mean": round(float(values.mean()), 8), "std": round(float(values.std(ddof=0)), 8),
            "bin_edges": edges, "bin_counts": _bin_counts(values, edges),
        }
    values = series.fillna("__MISSING__").astype(str)
    counts = values.value_counts().sort_index()
    return {
        "type": "categorical", "sample_size": len(series), "missing_rate": missing_rate,
        "category_counts": {str(key): int(value) for key, value in counts.items()},
        "category_proportions": {str(key): round(float(value / len(series)), 8) for key, value in counts.items()},
        "unknown_rate": 0.0,
    }


def _prediction_stats(probabilities: list[float], manifest: Any) -> dict[str, Any]:
    series = pd.Series(probabilities, dtype=float)
    risk = {"SAFE": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for value in probabilities:
        risk["HIGH" if value >= manifest.high_risk_threshold else "MEDIUM" if value >= manifest.decision_threshold else "LOW" if value >= manifest.low_risk_threshold else "SAFE"] += 1
    return {"probability": {"bin_edges": _PROBABILITY_EDGES, "bin_counts": _bin_counts(series, _PROBABILITY_EDGES), "mean": round(float(series.mean()), 8), "quantiles": {"p50": round(float(series.quantile(.5)), 8), "p95": round(float(series.quantile(.95)), 8)}}, "churn_rate": round(float((series >= manifest.decision_threshold).mean()), 8), "risk_band_counts": risk}


def _quantile_edges(values: pd.Series) -> list[float]:
    edges = sorted({round(float(values.quantile(index / 10)), 8) for index in range(11)})
    return edges if len(edges) > 1 else [edges[0], edges[0] + 1.0]


def _bin_counts(values: pd.Series, edges: list[float]) -> dict[str, int]:
    categories = pd.cut(values, bins=edges, include_lowest=True, duplicates="drop")
    return {str(key): int(value) for key, value in categories.value_counts(sort=False).items()}


def _manifest_identity(manifest: Any) -> str:
    return _canonical_hash({"model_version": manifest.model_version, "schema_version": manifest.schema_version, "feature_order": list(manifest.feature_order), "decision_threshold": manifest.decision_threshold, "risk_bands": [manifest.low_risk_threshold, manifest.high_risk_threshold]})


def _canonical_hash(value: dict[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
