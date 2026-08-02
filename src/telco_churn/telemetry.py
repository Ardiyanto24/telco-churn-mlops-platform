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

    _LATENCY_BUCKETS = (10, 25, 50, 100, 250, 500, 1_000)

    def __init__(self) -> None:
        self._values: Counter[str] = Counter()
        self._histograms: dict[str, list[int]] = {}
        self._histogram_sums: Counter[str] = Counter()
        self._lock = Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._values[name] += amount

    def value(self, name: str) -> int:
        with self._lock:
            return self._values[name]

    def observe_latency(self, name: str, milliseconds: float) -> None:
        with self._lock:
            buckets = self._histograms.setdefault(name, [0] * (len(self._LATENCY_BUCKETS) + 1))
            for index, upper_bound in enumerate(self._LATENCY_BUCKETS):
                if milliseconds <= upper_bound:
                    buckets[index] += 1
            buckets[-1] += 1
            self._histogram_sums[name] += milliseconds

    def render_openmetrics(self) -> str:
        with self._lock:
            values = dict(self._values)
            histograms = {name: list(buckets) for name, buckets in self._histograms.items()}
            histogram_sums = dict(self._histogram_sums)
        counters = "".join(f"# TYPE {name} counter\n{name} {value}\n" for name, value in sorted(values.items()))
        histogram_lines: list[str] = []
        for name, buckets in sorted(histograms.items()):
            histogram_lines.append(f"# TYPE {name} histogram\n")
            for upper_bound, value in zip(self._LATENCY_BUCKETS, buckets[:-1], strict=True):
                histogram_lines.append(f'{name}_bucket{{le="{upper_bound}"}} {value}\n')
            histogram_lines.append(f'{name}_bucket{{le="+Inf"}} {buckets[-1]}\n')
            histogram_lines.append(f"{name}_sum {histogram_sums[name]:.3f}\n")
            histogram_lines.append(f"{name}_count {buckets[-1]}\n")
        return counters + "".join(histogram_lines)


@dataclass(frozen=True)
class RequestTelemetryContext:
    request_id: str
    started_at: float
    trace_id: str | None = None


@dataclass
class TelemetryEmitter:
    """Queue events so a failed or slow output sink cannot block inference."""

    sink: Callable[[str], None] = field(default=lambda line: _stdout_sink(line))
    failure_sink: Callable[[str], None] = field(default=lambda line: _stderr_sink(line))
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
                self._emit_failure_fallback(event)
            finally:
                self._queue.task_done()

    def _emit_failure_fallback(self, event: Mapping[str, Any]) -> None:
        fallback = {
            "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
            "event_name": "telemetry_write_failed",
            "timestamp_utc": utc_timestamp(),
            "service_name": self.service_name,
            "environment": self.environment,
            "failed_event_name": event["event_name"],
        }
        for correlation_field in ("request_id", "trace_id"):
            if event.get(correlation_field) is not None:
                fallback[correlation_field] = event[correlation_field]
        try:
            self.failure_sink(json.dumps(fallback, sort_keys=True, separators=(",", ":")))
        except Exception:
            # The fallback is intentionally terminal to avoid recursive failure logging.
            pass


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


def _stderr_sink(line: str) -> None:
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
