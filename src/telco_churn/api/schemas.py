"""Pydantic schemas that define the public Prediction API v1 contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SchemaVersion = Literal["v1"]


class CustomerInput(BaseModel):
    """One validated customer record accepted by ``POST /v1/predict``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    customer_id: str = Field(min_length=1, max_length=128)
    gender: Literal["Female", "Male"]
    senior_citizen: Literal[0, 1]
    partner: Literal["Yes", "No"]
    dependents: Literal["Yes", "No"]
    tenure: int = Field(ge=0, le=72)
    phone_service: Literal["Yes", "No"]
    multiple_lines: Literal["Yes", "No", "No phone service"]
    internet_service: Literal["DSL", "Fiber optic", "No"]
    online_security: Literal["Yes", "No", "No internet service"]
    online_backup: Literal["Yes", "No", "No internet service"]
    device_protection: Literal["Yes", "No", "No internet service"]
    tech_support: Literal["Yes", "No", "No internet service"]
    streaming_tv: Literal["Yes", "No", "No internet service"]
    streaming_movies: Literal["Yes", "No", "No internet service"]
    contract: Literal["Month-to-month", "One year", "Two year"]
    paperless_billing: Literal["Yes", "No"]
    payment_method: Literal[
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)",
    ]
    monthly_charges: float = Field(ge=0, le=1_000)
    total_charges: float = Field(ge=0, le=100_000)

    @model_validator(mode="after")
    def validate_service_dependencies(self) -> CustomerInput:
        if self.phone_service == "No" and self.multiple_lines != "No phone service":
            raise ValueError("multiple_lines must be 'No phone service' when phone_service is 'No'")
        if self.internet_service == "No":
            internet_features = (
                self.online_security,
                self.online_backup,
                self.device_protection,
                self.tech_support,
                self.streaming_tv,
                self.streaming_movies,
            )
            if any(value != "No internet service" for value in internet_features):
                raise ValueError(
                    "internet feature values must be 'No internet service' when internet_service is 'No'"
                )
        return self


class PredictionRequest(BaseModel):
    """Version 1 request body with a deterministic bounded batch."""

    model_config = ConfigDict(extra="forbid")

    inputs: list[CustomerInput] = Field(min_length=1, max_length=100)


class PredictionResult(BaseModel):
    customer_id: str
    churn_binary: Literal[0, 1]
    churn_prediction: Literal["CHURN", "NO_CHURN"]
    churn_probability: float = Field(ge=0, le=1)
    risk_level: Literal["SAFE", "LOW", "MEDIUM", "HIGH"]


class PredictionSummary(BaseModel):
    total_customers: int = Field(ge=1)
    predicted_churn: int = Field(ge=0)
    churn_rate_pct: float = Field(ge=0, le=100)
    avg_churn_probability: float = Field(ge=0, le=1)


class PredictionResponse(BaseModel):
    request_id: str
    model_version: str
    schema_version: SchemaVersion = "v1"
    timestamp_utc: str
    decision_threshold: float = Field(ge=0, le=1)
    summary: PredictionSummary
    results: list[PredictionResult]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class VersionResponse(BaseModel):
    service_version: str
    model_version: str
    schema_version: SchemaVersion = "v1"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, object]] | None = None


class ErrorResponse(BaseModel):
    request_id: str
    error: ErrorBody
