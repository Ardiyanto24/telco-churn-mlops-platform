"""Privacy-minimised, non-blocking telemetry primitives for M12."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from queue import Full, Queue
import sys
from threading import Lock, Thread
from typing import Any


TELEMETRY_SCHEMA_VERSION = "telco-churn-telemetry/v1"


class ServiceMetrics:
    """Small in-process counter registry with OpenMetrics-compatible output."""

    def __init__(self) -> None:
        self._values: Counter[str] = Counter()
        self._lock = Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._values[name] += amount

    def value(self, name: str) -> int:
        with self._lock:
            return self._values[name]

    def render_openmetrics(self) -> str:
        with self._lock:
            values = dict(self._values)
        return "".join(f"# TYPE {name} counter\n{name} {value}\n" for name, value in sorted(values.items()))


@dataclass(frozen=True)
class RequestTelemetryContext:
    request_id: str
    started_at: float
    trace_id: str | None = None


@dataclass
class TelemetryEmitter:
    """Queue events so a failed or slow output sink cannot block inference."""

    sink: Callable[[str], None] = field(default=lambda line: _stdout_sink(line))
    metrics: ServiceMetrics = field(default_factory=ServiceMetrics)
    service_name: str = "telco-churn-api"
    environment: str = "local"
    queue_size: int = 1_000

    def __post_init__(self) -> None:
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=self.queue_size)
        self._worker = Thread(target=self._drain, name="telemetry-emitter", daemon=True)
        self._worker.start()

    def emit(self, event_name: str, **fields: Any) -> None:
        event = {
            "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
            "event_name": event_name,
            "timestamp_utc": utc_timestamp(),
            "service_name": self.service_name,
            "environment": self.environment,
            **fields,
        }
        try:
            self._queue.put_nowait(event)
        except Full:
            self.metrics.increment("telemetry_dropped_events_total")

    def flush(self) -> None:
        """Wait for queued events; intended for shutdown and deterministic tests."""
        self._queue.join()

    def _drain(self) -> None:
        while True:
            event = self._queue.get()
            try:
                self.sink(json.dumps(event, sort_keys=True, separators=(",", ":")))
            except Exception:
                # Do not recursively emit through the same failing boundary.
                self.metrics.increment("telemetry_write_failures_total")
            finally:
                self._queue.task_done()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def pseudonymous_entity_key(reference: str, *, secret: bytes, key_id: str) -> dict[str, str]:
    """Return a keyed pseudonym; callers must discard the source reference."""
    if not reference or not secret or not key_id:
        raise ValueError("reference, secret, and key_id are required")
    digest = hmac.new(secret, reference.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"entity_key": digest, "key_id": key_id}


def monitoring_observations(records: Sequence[Any]) -> dict[str, Mapping[str, int]]:
    """Aggregate an allowlisted, derived subset of inputs without identifiers."""
    observations: dict[str, Counter[str]] = {
        "contract": Counter(),
        "internet_service": Counter(),
        "payment_method": Counter(),
        "tenure_bin": Counter(),
        "monthly_charges_bin": Counter(),
    }
    for record in records:
        observations["contract"][record.contract] += 1
        observations["internet_service"][record.internet_service] += 1
        observations["payment_method"][record.payment_method] += 1
        observations["tenure_bin"][_tenure_bin(record.tenure)] += 1
        observations["monthly_charges_bin"][_charges_bin(record.monthly_charges)] += 1
    return {name: dict(sorted(values.items())) for name, values in observations.items()}


def _tenure_bin(value: int) -> str:
    if value < 12:
        return "0-11"
    if value < 24:
        return "12-23"
    if value < 48:
        return "24-47"
    return "48-72"


def _charges_bin(value: float) -> str:
    if value < 35:
        return "0-34.99"
    if value < 70:
        return "35-69.99"
    if value < 100:
        return "70-99.99"
    return "100+"


def _stdout_sink(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
