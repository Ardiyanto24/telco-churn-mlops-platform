"""Prediction boundary for API v1; artifact loading is intentionally M3 scope."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from telco_churn.api.schemas import CustomerInput
from telco_churn.artifacts import ArtifactLoadError, VerifiedArtifactLoader
from telco_churn.settings import Settings


class PredictionNotReadyError(RuntimeError):
    """Raised when no verified model runtime is available to serve predictions."""


@dataclass(frozen=True)
class PredictionService:
    """A readiness-aware adapter around the eventually M3-provided predictor."""

    predict_probabilities: Callable[[Sequence[CustomerInput]], Sequence[float]] | None
    model_version: str = "unavailable"

    @classmethod
    def unavailable(cls) -> PredictionService:
        return cls(predict_probabilities=None)

    @classmethod
    def from_artifact_dir(cls, artifact_dir, settings: Settings) -> PredictionService:
        try:
            bundle = VerifiedArtifactLoader().load(artifact_dir)
        except ArtifactLoadError:
            return cls.unavailable()
        if (
            bundle.manifest.decision_threshold != settings.decision_threshold
            or bundle.manifest.low_risk_threshold != settings.low_risk_threshold
            or bundle.manifest.high_risk_threshold != settings.high_risk_threshold
        ):
            return cls.unavailable()
        return cls(
            predict_probabilities=lambda records: bundle.predict_probabilities(
                [_legacy_record(record) for record in records]
            ),
            model_version=bundle.manifest.model_version,
        )

    @property
    def is_ready(self) -> bool:
        return self.predict_probabilities is not None

    def predict(self, records: Sequence[CustomerInput]) -> list[float]:
        if self.predict_probabilities is None:
            raise PredictionNotReadyError("model runtime is unavailable")

        probabilities = list(self.predict_probabilities(records))
        if len(probabilities) != len(records):
            raise RuntimeError("predictor result count does not match input count")
        if any(not 0 <= probability <= 1 for probability in probabilities):
            raise RuntimeError("predictor returned a probability outside [0, 1]")
        return probabilities


def _legacy_record(record: CustomerInput) -> dict[str, object]:
    return {
        "customerID": record.customer_id, "gender": record.gender,
        "SeniorCitizen": record.senior_citizen, "Partner": record.partner,
        "Dependents": record.dependents, "tenure": record.tenure,
        "PhoneService": record.phone_service, "MultipleLines": record.multiple_lines,
        "InternetService": record.internet_service, "OnlineSecurity": record.online_security,
        "OnlineBackup": record.online_backup, "DeviceProtection": record.device_protection,
        "TechSupport": record.tech_support, "StreamingTV": record.streaming_tv,
        "StreamingMovies": record.streaming_movies, "Contract": record.contract,
        "PaperlessBilling": record.paperless_billing, "PaymentMethod": record.payment_method,
        "MonthlyCharges": record.monthly_charges, "TotalCharges": record.total_charges,
    }
