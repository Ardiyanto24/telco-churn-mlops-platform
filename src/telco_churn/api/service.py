"""Prediction boundary for API v1; artifact loading is intentionally M3 scope."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from telco_churn.api.schemas import CustomerInput


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
