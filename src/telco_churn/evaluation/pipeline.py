"""Reproducible M8 evaluation for M3/M6 candidate bundles."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from telco_churn.artifacts import VerifiedArtifactLoader
from telco_churn.data_contract import TARGET_COLUMN, load_verified_dataset
from telco_churn.evaluation.gates import GateConfig, evaluate_probabilities
from telco_churn.training.pipeline import TrainingConfig, _split


class EvaluationError(RuntimeError):
    """Raised when an M8 evaluation cannot be reproduced safely."""


def evaluate_candidate(
    candidate_dir: Path, dataset: Path, manifest_path: Path, gate_config_path: Path,
    output_dir: Path, *, champion_dir: Path | None = None,
) -> dict[str, Any]:
    """Evaluate a verified candidate on its reconstructed M6 test partition."""
    if output_dir.exists():
        raise EvaluationError("evaluation output directory must not already exist")
    record = _read_json(candidate_dir / "training_run.json", "candidate training run")
    config = TrainingConfig.from_dict(record.get("config", {}))
    data = load_verified_dataset(dataset, manifest_path)
    data_manifest = _read_json(manifest_path, "dataset manifest")
    if record.get("dataset_manifest", {}).get("sha256") != data_manifest.get("sha256"):
        raise EvaluationError("candidate dataset manifest does not match evaluation dataset")
    features = data.drop(columns=TARGET_COLUMN)
    target = data[TARGET_COLUMN].eq("Yes").astype(int)
    _, _, test_x, _, _, test_y = _split(features, target, config)
    loader = VerifiedArtifactLoader()
    candidate = loader.load(candidate_dir / "bundle")
    gates = GateConfig.from_dict(_read_json(gate_config_path, "gate config"))
    test_records = test_x.to_dict(orient="records")
    probabilities = candidate.predict_probabilities(test_records)
    latency_metrics = _measure_latency(candidate, test_records, gates.latency)

    champion_probabilities = None
    champion_threshold = None
    champion_version = None
    if champion_dir is not None:
        champion = loader.load(champion_dir / "bundle")
        if candidate.manifest.feature_order != champion.manifest.feature_order or candidate.manifest.schema_version != champion.manifest.schema_version:
            raise EvaluationError("candidate and champion feature contracts are incompatible")
        champion_probabilities = champion.predict_probabilities(test_records)
        champion_threshold = champion.manifest.decision_threshold
        champion_version = champion.manifest.model_version

    result = evaluate_probabilities(
        test_y.tolist(), probabilities, candidate.manifest.decision_threshold, gates,
        champion_probabilities=champion_probabilities, champion_threshold=champion_threshold,
    )
    failures = list(result.failures)
    if gates.latency is not None:
        if latency_metrics["single_p95_ms"] > gates.latency["single_p95_ms"]:
            failures.append("latency.single_p95_ms")
        if latency_metrics["batch_100_p95_ms"] > gates.latency["batch_100_p95_ms"]:
            failures.append("latency.batch_100_p95_ms")
    status = result.status if not failures or result.status == "invalid" else "failed"
    report = {
        "report_version": "m8-evaluation-report/v1",
        "data_origin": "offline_test",
        "status": status,
        "failures": failures,
        "gate_config_version": gates.version,
        "dataset_manifest_sha256": data_manifest["sha256"],
        "candidate": {
            "model_version": candidate.manifest.model_version,
            "model_family": candidate.manifest.model_family,
            "schema_version": candidate.manifest.schema_version,
            "decision_threshold": candidate.manifest.decision_threshold,
        },
        "champion": None if champion_version is None else {"model_version": champion_version},
        "metrics": result.metrics,
        "champion_metrics": result.champion_metrics,
        "latency_ms": latency_metrics,
        "test_row_count": len(test_x),
    }
    output_dir.mkdir(parents=True)
    (output_dir / "evaluation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "model_card.md").write_text(_model_card(report), encoding="utf-8")
    return report


def _measure_latency(bundle: Any, records: list[dict[str, Any]], limits: dict[str, float] | None) -> dict[str, float]:
    """Measure online-shaped inference calls only when the policy enables it."""
    if limits is None:
        return {}
    if not records:
        raise EvaluationError("cannot measure latency without evaluation records")
    singles: list[float] = []
    for index in range(100):
        started = perf_counter()
        bundle.predict_probabilities([records[index % len(records)]])
        singles.append((perf_counter() - started) * 1000)
    batch = [records[index % len(records)] for index in range(100)]
    batches: list[float] = []
    for _ in range(20):
        started = perf_counter()
        bundle.predict_probabilities(batch)
        batches.append((perf_counter() - started) * 1000)
    return {"single_p95_ms": float(np.percentile(singles, 95)), "batch_100_p95_ms": float(np.percentile(batches, 95))}


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise EvaluationError(f"{label} must be an object")
    return value


def _model_card(report: dict[str, Any]) -> str:
    metrics = "\n".join(f"- {name}: {value:.6f}" for name, value in sorted(report["metrics"].items()))
    return (
        "# M8 Candidate Model Card\n\n"
        f"- Data origin: `{report['data_origin']}`\n"
        f"- Gate status: `{report['status']}`\n"
        f"- Candidate: `{report['candidate']['model_version']}`\n"
        f"- Gate config: `{report['gate_config_version']}`\n\n"
        "## Offline test metrics\n\n"
        f"{metrics}\n\n"
        "This report is offline evaluation evidence and is not production performance.\n"
    )
