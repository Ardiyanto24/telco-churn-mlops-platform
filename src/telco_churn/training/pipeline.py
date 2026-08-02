"""Deterministic M6 training pipeline for a candidate Telco churn bundle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve, roc_auc_score
from sklearn.model_selection import train_test_split

from telco_churn.artifacts import write_manifest
from telco_churn.data_contract import TARGET_COLUMN, load_verified_dataset
from telco_churn.preprocessing import PreprocessingPipeline
from telco_churn.settings import risk_bands_for_threshold
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier


@dataclass(frozen=True)
class SplitConfig:
    train_fraction: float
    validation_fraction: float
    test_fraction: float


@dataclass(frozen=True)
class ModelConfig:
    type: str
    params: dict[str, Any]


@dataclass(frozen=True)
class TrainingConfig:
    run_name: str
    seed: int
    split: SplitConfig
    model: ModelConfig

    @classmethod
    def from_json(cls, path: Path) -> "TrainingConfig":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainingConfig":
        try:
            config = cls(
                run_name=str(data["run_name"]), seed=int(data["seed"]),
                split=SplitConfig(**data["split"]), model=ModelConfig(**data["model"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("training config is incomplete or invalid") from error
        if not config.run_name or config.model.type not in {"logistic_regression", "lightgbm", "xgboost", "voting_ensemble"}:
            raise ValueError("training config has an unsupported run or model type")
        if not isinstance(config.model.params, dict):
            raise ValueError("model params must be an object")
        fractions = config.split
        if min(fractions.train_fraction, fractions.validation_fraction, fractions.test_fraction) <= 0:
            raise ValueError("split fractions must be positive")
        if not np.isclose(sum(asdict(fractions).values()), 1.0):
            raise ValueError("split fractions must sum to 1.0")
        return config


@dataclass(frozen=True)
class TrainingResult:
    output_dir: Path
    metrics: dict[str, float]


def run_training(config: TrainingConfig, dataset: Path, manifest_path: Path, output_dir: Path) -> TrainingResult:
    """Train only from an M5-verified dataset and create one immutable bundle."""
    frame = load_verified_dataset(dataset, manifest_path)
    if output_dir.exists():
        raise ValueError("training output directory must not already exist")

    features = frame.drop(columns=TARGET_COLUMN)
    target = frame[TARGET_COLUMN].eq("Yes").astype(int)
    train_x, validation_x, test_x, train_y, validation_y, test_y = _split(features, target, config)

    preprocessor = PreprocessingPipeline().fit(train_x, train_y)
    train_features = preprocessor.transform(train_x)
    validation_features = preprocessor.transform(validation_x)
    test_features = preprocessor.transform(test_x)
    model = build_model(config)
    model.fit(train_features, train_y)

    validation_probabilities = model.predict_proba(validation_features)[:, 1]
    threshold, precision, recall, thresholds = _select_f1_threshold(validation_y, validation_probabilities)
    test_probabilities = model.predict_proba(test_features)[:, 1]
    metrics = _evaluate(test_y, test_probabilities, threshold)
    low_risk_threshold, high_risk_threshold = risk_bands_for_threshold(threshold)

    output_dir.mkdir(parents=True)
    bundle_dir = output_dir / "bundle"
    bundle_dir.mkdir()
    joblib.dump(model, bundle_dir / "model.joblib")
    joblib.dump(preprocessor, bundle_dir / "preprocessor.joblib")
    dataset_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    write_manifest(
        bundle_dir, model_version=config.run_name, model_family=config.model.type, schema_version="v1",
        baseline_id=f"m6-dataset-{dataset_manifest['sha256'][:12]}",
        feature_order=preprocessor._last_output_columns_, decision_threshold=threshold,
        low_risk_threshold=low_risk_threshold, high_risk_threshold=high_risk_threshold,
    )
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_plot(output_dir / "plots" / "precision_recall.svg", precision, recall)
    record = {
        "config": asdict(config), "model_family": config.model.type, "dataset_manifest": dataset_manifest,
        "code_revision": _git_revision(), "fit_split": "train",
        "threshold_selection_split": "validation", "evaluation_split": "test",
        "split_row_counts": {"train": len(train_x), "validation": len(validation_x), "test": len(test_x)},
        "selected_threshold": threshold, "validation_threshold_count": len(thresholds),
        "metrics": metrics,
    }
    (output_dir / "training_run.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return TrainingResult(output_dir=output_dir, metrics=metrics)


def build_model(config: TrainingConfig):
    """Create an unfitted, allowlisted estimator from versioned training config."""
    params = config.model.params
    if config.model.type == "logistic_regression":
        return LogisticRegression(random_state=config.seed, **params)
    if config.model.type == "lightgbm":
        return _lightgbm(params, config.seed)
    if config.model.type == "xgboost":
        return _xgboost(params, config.seed)
    required = {"lightgbm", "xgboost_class_weight", "xgboost_smote"}
    if not required.issubset(params):
        raise ValueError("voting_ensemble requires lightgbm and two xgboost parameter objects")
    return VotingClassifier(
        estimators=[
            ("lightgbm", _lightgbm(params["lightgbm"], config.seed)),
            ("xgboost_class_weight", _xgboost(params["xgboost_class_weight"], config.seed)),
            ("xgboost_smote", _xgboost(params["xgboost_smote"], config.seed)),
        ], voting="soft", weights=params.get("weights", [5, 3, 1]), n_jobs=1,
    )


def _lightgbm(params: dict[str, Any], seed: int) -> LGBMClassifier:
    values = {"random_state": seed, "verbosity": -1, **params}
    return LGBMClassifier(**values)


def _xgboost(params: dict[str, Any], seed: int) -> XGBClassifier:
    values = {"random_state": seed, "objective": "binary:logistic", "eval_metric": "aucpr", "n_jobs": 1, **params}
    return XGBClassifier(**values)


def _split(features, target, config: TrainingConfig):
    train_x, remaining_x, train_y, remaining_y = train_test_split(
        features, target, train_size=config.split.train_fraction, random_state=config.seed, stratify=target,
    )
    validation_share = config.split.validation_fraction / (config.split.validation_fraction + config.split.test_fraction)
    validation_x, test_x, validation_y, test_y = train_test_split(
        remaining_x, remaining_y, train_size=validation_share, random_state=config.seed, stratify=remaining_y,
    )
    return train_x, validation_x, test_x, train_y, validation_y, test_y


def _select_f1_threshold(target, probabilities):
    precision, recall, thresholds = precision_recall_curve(target, probabilities)
    f1_scores = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    best_index = int(np.argmax(f1_scores))
    return float(thresholds[best_index]), precision, recall, thresholds


def _evaluate(target, probabilities, threshold: float) -> dict[str, float]:
    predictions = (probabilities >= threshold).astype(int)
    return {
        "average_precision": float(average_precision_score(target, probabilities)),
        "f1": float(f1_score(target, predictions)),
        "roc_auc": float(roc_auc_score(target, probabilities)),
        "decision_threshold": float(threshold),
    }


def _write_plot(destination: Path, precision, recall) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    points = " ".join(
        f"{30 + 500 * float(recall[index]):.2f},{270 - 240 * float(precision[index]):.2f}"
        for index in np.linspace(0, len(precision) - 1, num=min(250, len(precision)), dtype=int)
    )
    destination.write_text(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"560\" height=\"320\" viewBox=\"0 0 560 320\">"
        "<rect width=\"100%\" height=\"100%\" fill=\"white\"/><text x=\"30\" y=\"20\">Precision–Recall (validation)</text>"
        "<line x1=\"30\" y1=\"270\" x2=\"530\" y2=\"270\" stroke=\"black\"/><line x1=\"30\" y1=\"30\" x2=\"30\" y2=\"270\" stroke=\"black\"/>"
        f"<polyline fill=\"none\" stroke=\"#f97316\" stroke-width=\"2\" points=\"{points}\"/>"
        "<text x=\"250\" y=\"305\">Recall</text><text x=\"4\" y=\"150\" transform=\"rotate(-90 4,150)\">Precision</text></svg>\n",
        encoding="utf-8",
    )


def _git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        git_dir = Path(".git")
        if git_dir.is_file():
            marker = git_dir.read_text(encoding="utf-8").strip()
            if marker.startswith("gitdir: "):
                git_dir = (git_dir.parent / marker.removeprefix("gitdir: ")).resolve()
        try:
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
            if head.startswith("ref: "):
                return (git_dir / head.removeprefix("ref: ")).read_text(encoding="utf-8").strip()
            return head
        except OSError:
            return os.environ.get("TELCO_CHURN_CODE_REVISION", "unavailable")
