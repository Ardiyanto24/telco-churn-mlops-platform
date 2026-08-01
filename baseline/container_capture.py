"""Capture deterministic legacy inference evidence inside the baseline image."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import warnings
from pathlib import Path

# The mounted capture script lives in /baseline; legacy application modules live in /code.
sys.path.insert(0, "/code")

import fastapi
import joblib
import lightgbm
import numpy
import pandas
import sklearn
import xgboost

from handler import EndpointHandler


ARTIFACTS = ("model_final.joblib", "preprocessor.joblib")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def processed_feature_metadata(handler: EndpointHandler, payload: dict) -> dict | None:
    dataframe = handler.parse_payload_to_dataframe(payload)
    if dataframe.empty:
        return None

    excluded = [
        column
        for column in ("customerID", "id", "Unnamed: 0", "Churn")
        if column in dataframe.columns
    ]
    transformed = handler.preprocessor.transform(
        dataframe.drop(columns=excluded, errors="ignore")
    )
    return {
        "column_count": len(transformed.columns),
        "columns": transformed.columns.tolist(),
    }


def main() -> None:
    fixture = json.load(sys.stdin)
    redirected_stdout = io.StringIO()
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(redirected_stdout):
            handler = EndpointHandler(path=".")
            scenarios = []
            for scenario in fixture["scenarios"]:
                payload = scenario["payload"]
                scenarios.append(
                    {
                        "name": scenario["name"],
                        "response": handler(payload),
                        "processed_features": processed_feature_metadata(handler, payload),
                    }
                )

    result = {
        "schema_version": 1,
        "runtime": {
            "python": sys.version.split()[0],
            "fastapi": fastapi.__version__,
            "joblib": joblib.__version__,
            "lightgbm": lightgbm.__version__,
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
        "artifacts": {artifact: sha256(Path(artifact)) for artifact in ARTIFACTS},
        "warnings": [
            {"category": warning.category.__name__, "message": str(warning.message)}
            for warning in caught_warnings
        ],
        "scenarios": scenarios,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
