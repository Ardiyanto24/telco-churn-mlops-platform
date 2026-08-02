"""FastAPI application factory for the stable Prediction API v1 contract."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from time import perf_counter
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
from telco_churn.telemetry import RequestTelemetryContext, TelemetryEmitter, monitoring_observations


SERVICE_VERSION = "0.1.0"
_TRACEPARENT_PATTERN = re.compile(r"^[\da-f]{2}-([\da-f]{32})-[\da-f]{16}-[\da-f]{2}$")


def create_app(
    *, service: PredictionService | None = None, settings: Settings | None = None,
    telemetry: TelemetryEmitter | None = None,
) -> FastAPI:
    """Create the M2 application without triggering M3 artifact loading."""
    settings = load_settings() if settings is None else settings
    service = PredictionService.from_artifact_dir(settings.artifact_dir, settings) if service is None else service
    telemetry = TelemetryEmitter() if telemetry is None else telemetry
    app = FastAPI(
        title="Telco Churn Prediction API",
        version=SERVICE_VERSION,
        description="Versioned, validated prediction contract backed by verified M3 artifacts.",
    )
    app.state.telemetry = telemetry

    @app.middleware("http")
    async def correlate_and_measure(request: Request, call_next):
        context = RequestTelemetryContext(
            request_id=str(uuid4()), started_at=perf_counter(),
            trace_id=_trace_id(request.headers.get("traceparent")),
        )
        request.state.telemetry_context = context
        response = await call_next(request)
        response.headers["X-Request-ID"] = context.request_id
        latency_ms = round((perf_counter() - context.started_at) * 1_000, 3)
        telemetry.metrics.increment("requests_total")
        if response.status_code >= 400:
            telemetry.metrics.increment("request_failures_total")
        telemetry.emit(
            "request_completed", request_id=context.request_id, trace_id=context.trace_id,
            http_status=response.status_code, outcome="success" if response.status_code < 400 else "error",
            request_latency_ms=latency_ms,
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(request=request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request payload does not satisfy the v1 prediction contract.",
            details=jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(PredictionNotReadyError)
    async def not_ready_error_handler(
        request: Request, exc: PredictionNotReadyError
    ) -> JSONResponse:
        return _error_response(request=request,
            status_code=503,
            code="MODEL_NOT_READY",
            message="Prediction model is not ready.",
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(request=request,
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
    def predict(prediction_request: PredictionRequest, request: Request) -> PredictionResponse:
        inference_started = perf_counter()
        probabilities = service.predict(prediction_request.inputs)
        inference_latency_ms = round((perf_counter() - inference_started) * 1_000, 3)
        results = [
            _build_result(record=record, probability=probability, settings=settings)
            for record, probability in zip(prediction_request.inputs, probabilities, strict=True)
        ]
        predicted_churn = sum(result.churn_binary for result in results)
        context = _telemetry_context(request)
        telemetry.metrics.increment("prediction_requests_total")
        telemetry.metrics.increment("prediction_rows_total", len(results))
        telemetry.emit(
            "prediction_completed", request_id=context.request_id, trace_id=context.trace_id,
            outcome="success", model_version=service.model_version, schema_version="v1",
            batch_size=len(results), inference_latency_ms=inference_latency_ms,
            request_latency_ms=round((perf_counter() - context.started_at) * 1_000, 3),
            predicted_churn_count=predicted_churn,
            risk_band_counts={band: sum(result.risk_level == band for result in results) for band in ("SAFE", "LOW", "MEDIUM", "HIGH")},
            monitoring_observations=monitoring_observations(prediction_request.inputs),
        )
        return PredictionResponse(
            request_id=context.request_id,
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
    *, request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> JSONResponse:
    context = _telemetry_context(request)
    telemetry: TelemetryEmitter = request.app.state.telemetry
    telemetry.emit(
        "request_failed", request_id=context.request_id, trace_id=context.trace_id,
        outcome="error", error_code=code, http_status=status_code,
        request_latency_ms=round((perf_counter() - context.started_at) * 1_000, 3),
    )
    payload = ErrorResponse(
        request_id=context.request_id, error=ErrorBody(code=code, message=message, details=details)
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def _telemetry_context(request: Request) -> RequestTelemetryContext:
    context = getattr(request.state, "telemetry_context", None)
    if context is None:
        context = RequestTelemetryContext(request_id=str(uuid4()), started_at=perf_counter())
        request.state.telemetry_context = context
    return context


def _trace_id(traceparent: str | None) -> str | None:
    if traceparent is None:
        return None
    match = _TRACEPARENT_PATTERN.fullmatch(traceparent.lower())
    return None if match is None else match.group(1)
