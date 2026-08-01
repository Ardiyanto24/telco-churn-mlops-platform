"""FastAPI application factory for the stable Prediction API v1 contract."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from telco_churn.api.schemas import (
    CustomerInput,
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionResult,
    PredictionSummary,
    VersionResponse,
)
from telco_churn.api.service import PredictionNotReadyError, PredictionService
from telco_churn.settings import Settings, load_settings


SERVICE_VERSION = "0.1.0"


def create_app(
    *, service: PredictionService | None = None, settings: Settings | None = None
) -> FastAPI:
    """Create the M2 application without triggering M3 artifact loading."""
    service = PredictionService.unavailable() if service is None else service
    settings = load_settings() if settings is None else settings
    app = FastAPI(
        title="Telco Churn Prediction API",
        version=SERVICE_VERSION,
        description="Versioned, validated prediction contract. Artifact loading follows in M3.",
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request payload does not satisfy the v1 prediction contract.",
            details=jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(PredictionNotReadyError)
    async def not_ready_error_handler(
        request: Request, exc: PredictionNotReadyError
    ) -> JSONResponse:
        return _error_response(
            status_code=503,
            code="MODEL_NOT_READY",
            message="Prediction model is not ready.",
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="An unexpected server error occurred.",
        )

    @app.get("/health/live", response_model=HealthResponse)
    def live() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse, "description": "Model is unavailable."}},
    )
    def ready() -> HealthResponse:
        if not service.is_ready:
            raise PredictionNotReadyError()
        return HealthResponse(status="ok")

    @app.get("/version", response_model=VersionResponse)
    def version() -> VersionResponse:
        return VersionResponse(
            service_version=SERVICE_VERSION,
            model_version=service.model_version,
        )

    @app.post(
        "/v1/predict",
        response_model=PredictionResponse,
        responses={
            422: {"model": ErrorResponse, "description": "Invalid request."},
            503: {"model": ErrorResponse, "description": "Model is unavailable."},
            500: {"model": ErrorResponse, "description": "Unexpected server error."},
        },
    )
    def predict(request: PredictionRequest) -> PredictionResponse:
        probabilities = service.predict(request.inputs)
        results = [
            _build_result(record=record, probability=probability, settings=settings)
            for record, probability in zip(request.inputs, probabilities, strict=True)
        ]
        predicted_churn = sum(result.churn_binary for result in results)
        return PredictionResponse(
            request_id=str(uuid4()),
            model_version=service.model_version,
            timestamp_utc=_utc_timestamp(),
            decision_threshold=settings.decision_threshold,
            summary=PredictionSummary(
                total_customers=len(results),
                predicted_churn=predicted_churn,
                churn_rate_pct=round(predicted_churn / len(results) * 100, 2),
                avg_churn_probability=round(sum(probabilities) / len(probabilities), 4),
            ),
            results=results,
        )

    return app


def _build_result(
    *, record: CustomerInput, probability: float, settings: Settings
) -> PredictionResult:
    churn_binary = int(probability >= settings.decision_threshold)
    return PredictionResult(
        customer_id=record.customer_id,
        churn_binary=churn_binary,
        churn_prediction="CHURN" if churn_binary else "NO_CHURN",
        churn_probability=round(probability, 4),
        risk_level=_risk_level(probability, settings),
    )


def _risk_level(probability: float, settings: Settings) -> str:
    if probability >= settings.high_risk_threshold:
        return "HIGH"
    if probability >= settings.decision_threshold:
        return "MEDIUM"
    if probability >= settings.low_risk_threshold:
        return "LOW"
    return "SAFE"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        request_id=str(uuid4()), error=ErrorBody(code=code, message=message, details=details)
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))
