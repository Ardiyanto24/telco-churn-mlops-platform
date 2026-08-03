"""Read-only M19 Public Metrics API over sanitised immutable snapshots."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from telco_churn.metrics_store import MetricsStore, MetricsStoreError
from telco_churn.public_metrics import PublicMetricsConfig


def create_public_api(*, store: MetricsStore, config: PublicMetricsConfig, now: Callable[[], datetime] | None = None) -> FastAPI:
    """Create the deliberately separate public API; it has no write routes."""
    clock = now or (lambda: datetime.now(timezone.utc))
    limiter = _RateLimiter(config.rate_limit_per_minute)
    app = FastAPI(title="Telco Churn Public Metrics API", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=list(config.allowed_origins), allow_credentials=False, allow_methods=["GET", "HEAD", "OPTIONS"], allow_headers=["If-None-Match", "Content-Type"], max_age=600)

    @app.middleware("http")
    async def public_safety(request: Request, call_next):
        if request.method in {"GET", "HEAD"} and request.url.path.startswith("/public/v1"):
            if not limiter.allow(request.client.host if request.client else "unknown"):
                return JSONResponse(
                    {"error": {"code": "RATE_LIMITED", "message": "Too many requests."}}, status_code=429,
                    headers={"Retry-After": "60", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"},
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def snapshot_response(request: Request, resource: str, nested: str | None = None) -> Response:
        try:
            snapshot = store.current_public_snapshot()
        except MetricsStoreError:
            return _error("SNAPSHOT_UNAVAILABLE", "Public metrics are not available.", 503)
        if snapshot is None:
            return _error("SNAPSHOT_UNAVAILABLE", "Public metrics are not available.", 503)
        payload: Any = snapshot[resource] if nested is None else snapshot[resource][nested]
        response = {key: snapshot[key] for key in ("schema_version", "snapshot_id", "generated_at", "freshness")}
        response["data"] = payload
        etag = '"' + snapshot["snapshot_id"] + '"'
        headers = {"ETag": etag, "Cache-Control": "public, max-age=300, stale-while-revalidate=600"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return JSONResponse(response, headers=headers)

    @app.get("/public/v1/overview", include_in_schema=False)
    def overview(request: Request) -> Response:
        return snapshot_response(request, "overview")

    @app.get("/public/v1/models/current", include_in_schema=False)
    def current_model(request: Request) -> Response:
        return snapshot_response(request, "models", "current")

    @app.get("/public/v1/models/history", include_in_schema=False)
    def model_history(request: Request) -> Response:
        return snapshot_response(request, "models", "history")

    @app.get("/public/v1/monitoring/history", include_in_schema=False)
    def monitoring_history(request: Request) -> Response:
        return snapshot_response(request, "monitoring", "history")

    @app.get("/public/v1/service/history", include_in_schema=False)
    def service_history(request: Request) -> Response:
        return snapshot_response(request, "service", "history")

    @app.get("/public/v1/methodology", include_in_schema=False)
    def methodology(request: Request) -> Response:
        return snapshot_response(request, "methodology")

    return app


class _RateLimiter:
    """Process-local bounded limiter for local/demo use; proxy may replace it."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def allow(self, client: str) -> bool:
        current = monotonic()
        with self._lock:
            bucket = self._requests[client]
            while bucket and bucket[0] <= current - 60:
                bucket.popleft()
            if len(bucket) >= self._limit:
                return False
            bucket.append(current)
            return True


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code, headers={"Cache-Control": "no-store"})
