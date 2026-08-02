"""Versioned validation and lineage metadata for Telco training datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa


SCHEMA_VERSION = "telco-churn-training/v1"
TARGET_COLUMN = "Churn"
INTERNET_SERVICE_COLUMNS = (
    "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport",
    "StreamingTV", "StreamingMovies",
)


class DataContractError(ValueError):
    """Raised when a dataset is unsafe to use for model training."""


@dataclass(frozen=True)
class ValidationReport:
    schema_version: str
    row_count: int
    column_count: int


@dataclass(frozen=True)
class DatasetManifest:
    schema_version: str
    format_version: str
    source_name: str
    sha256: str
    row_count: int
    column_count: int
    code_revision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_valid_total_charges(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    return text.eq("") | text.str.fullmatch(r"\d+(\.\d+)?", na=False)


TRAINING_DATA_SCHEMA = pa.DataFrameSchema(
    {
        "id": pa.Column(str, unique=True),
        "gender": pa.Column(str, checks=pa.Check.isin(["Female", "Male"])),
        "SeniorCitizen": pa.Column(int, checks=pa.Check.isin([0, 1])),
        "Partner": pa.Column(str, checks=pa.Check.isin(["Yes", "No"])),
        "Dependents": pa.Column(str, checks=pa.Check.isin(["Yes", "No"])),
        "tenure": pa.Column(int, checks=pa.Check.in_range(0, 72)),
        "PhoneService": pa.Column(str, checks=pa.Check.isin(["Yes", "No"])),
        "MultipleLines": pa.Column(str, checks=pa.Check.isin(["Yes", "No", "No phone service"])),
        "InternetService": pa.Column(str, checks=pa.Check.isin(["DSL", "Fiber optic", "No"])),
        **{
            column: pa.Column(str, checks=pa.Check.isin(["Yes", "No", "No internet service"]))
            for column in INTERNET_SERVICE_COLUMNS
        },
        "Contract": pa.Column(str, checks=pa.Check.isin(["Month-to-month", "One year", "Two year"])),
        "PaperlessBilling": pa.Column(str, checks=pa.Check.isin(["Yes", "No"])),
        "PaymentMethod": pa.Column(
            str,
            checks=pa.Check.isin([
                "Electronic check", "Mailed check", "Bank transfer (automatic)",
                "Credit card (automatic)",
            ]),
        ),
        "MonthlyCharges": pa.Column(float, checks=pa.Check.greater_than_or_equal_to(0)),
        "TotalCharges": pa.Column(object, checks=pa.Check(_is_valid_total_charges)),
        TARGET_COLUMN: pa.Column(str, checks=pa.Check.isin(["Yes", "No"])),
    },
    strict=True,
    coerce=True,
)


def validate_training_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """Validate canonical raw data before it can enter a training pipeline."""
    try:
        validated = TRAINING_DATA_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        raise DataContractError(_format_schema_errors(exc)) from exc
    except pa.errors.SchemaError as exc:
        raise DataContractError(str(exc)) from exc

    violations: list[str] = []
    no_phone = validated["PhoneService"].eq("No")
    if not validated.loc[no_phone, "MultipleLines"].eq("No phone service").all():
        violations.append("PhoneService=No requires MultipleLines=No phone service")

    no_internet = validated["InternetService"].eq("No")
    if not validated.loc[no_internet, list(INTERNET_SERVICE_COLUMNS)].eq("No internet service").all(axis=None):
        violations.append("InternetService=No requires all internet services=No internet service")

    blank_total = validated["TotalCharges"].astype(str).str.strip().eq("")
    if not validated.loc[blank_total, "tenure"].eq(0).all():
        violations.append("blank TotalCharges is only allowed when tenure=0")

    if violations:
        raise DataContractError("cross-field validation failed: " + "; ".join(violations))

    report = ValidationReport(SCHEMA_VERSION, len(validated), len(validated.columns))
    return validated, report


def validate_csv(source: Path) -> tuple[pd.DataFrame, ValidationReport]:
    """Load and validate a CSV dataset without silently accepting bad input."""
    return validate_training_data(pd.read_csv(source, keep_default_na=False))


def build_dataset_manifest(dataset: Path, *, code_revision: str) -> DatasetManifest:
    """Create deterministic lineage metadata from validated CSV contents."""
    if not code_revision.strip():
        raise DataContractError("code_revision is required for dataset lineage")
    validated, _ = validate_csv(dataset)
    return DatasetManifest(
        schema_version=SCHEMA_VERSION,
        format_version="v1",
        source_name=dataset.name,
        sha256=_sha256_file(dataset),
        row_count=len(validated),
        column_count=len(validated.columns),
        code_revision=code_revision,
    )


def write_dataset_manifest(manifest: DatasetManifest, destination: Path) -> None:
    """Persist the explicit data-to-code lineage record as stable JSON."""
    destination.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_verified_dataset(dataset: Path, manifest_path: Path) -> pd.DataFrame:
    """Refuse training input whose manifest, checksum, or contract is invalid."""
    try:
        manifest = DatasetManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DataContractError("dataset manifest is missing or invalid") from exc
    if manifest.schema_version != SCHEMA_VERSION:
        raise DataContractError("dataset manifest schema version is not supported")
    if manifest.source_name != dataset.name:
        raise DataContractError("dataset manifest source name does not match dataset")
    if manifest.sha256 != _sha256_file(dataset):
        raise DataContractError("dataset checksum does not match its manifest")
    validated, report = validate_csv(dataset)
    if (manifest.row_count, manifest.column_count) != (report.row_count, report.column_count):
        raise DataContractError("dataset shape does not match its manifest")
    return validated


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_schema_errors(error: pa.errors.SchemaErrors) -> str:
    failures = error.failure_cases
    columns = sorted({str(column) for column in failures.get("column", []) if column is not None})
    checks = sorted({str(check) for check in failures.get("check", []) if check is not None})
    details = ", ".join(columns + checks)
    if not details or "column_in_dataframe" in checks:
        details = failures.to_string(index=False)
    return f"training data contract failed: {details}"
