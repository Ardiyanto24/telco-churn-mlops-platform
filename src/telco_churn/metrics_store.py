"""M18 private, aggregate-only metrics storage with SQLite test support."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3
from threading import RLock
from typing import Any, Literal


ResultType = Literal["telemetry", "monitoring", "performance", "alert", "recommendation", "public_snapshot"]
EvidenceStatus = Literal["stable", "warning", "critical", "unknown", "insufficient_data", "not_available"]
DataOrigin = Literal["offline_test", "replayed", "synthetic", "production"]
_FORBIDDEN_FIELD_FRAGMENTS = ("customer", "entity_key", "prediction_id", "raw_payload", "payload", "secret", "token", "stack_trace")
_RESULT_TABLES = {
    "telemetry": "telemetry_rollups",
    "monitoring": "monitoring_results",
    "performance": "performance_results",
    "alert": "alert_revisions",
    "recommendation": "alert_revisions",
    "public_snapshot": "public_snapshots",
}


class MetricsStoreError(ValueError):
    """Raised when aggregate metrics violate the M18 storage boundary."""


@dataclass(frozen=True)
class MetricRecord:
    """One immutable, privacy-safe result suitable for M18 persistence."""

    result_id: str
    result_type: ResultType
    status: EvidenceStatus
    data_origin: DataOrigin
    window_start: datetime
    window_end: datetime
    computed_at: datetime
    sample_size: int
    label_coverage: float | None
    method_version: str
    config_version: str
    model_version: str
    baseline_id: str | None
    deployment_id: str | None
    summary: Mapping[str, Any]
    distribution: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not all((self.result_id, self.method_version, self.config_version, self.model_version)):
            raise MetricsStoreError("result identity and lineage fields are required")
        if self.result_type not in _RESULT_TABLES:
            raise MetricsStoreError("result_type is unsupported")
        if self.status not in {"stable", "warning", "critical", "unknown", "insufficient_data", "not_available"}:
            raise MetricsStoreError("status is unsupported")
        if self.data_origin not in {"offline_test", "replayed", "synthetic", "production"}:
            raise MetricsStoreError("data_origin is unsupported")
        start, end, computed = (_utc(self.window_start, "window_start"), _utc(self.window_end, "window_end"), _utc(self.computed_at, "computed_at"))
        if start >= end or computed < end:
            raise MetricsStoreError("metric window and calculation time are invalid")
        if self.sample_size < 0 or self.label_coverage is not None and not 0 <= self.label_coverage <= 1:
            raise MetricsStoreError("sample_size or label_coverage is invalid")
        _assert_safe_aggregate(self.summary)
        _assert_safe_aggregate(self.distribution)


@dataclass(frozen=True)
class IngestResult:
    result_id: str
    idempotency_key: str
    reused: bool


class MetricsStore:
    """Transactional aggregate store. SQLite is the deterministic local adapter."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._lock = RLock()

    @classmethod
    def open_sqlite(cls, path: str = ":memory:") -> "MetricsStore":
        """Create the local/test adapter safe for FastAPI worker-thread reads."""
        return cls(sqlite3.connect(path, check_same_thread=False))

    def upgrade(self) -> list[str]:
        with self._lock:
            self._connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
            applied = {row["version"] for row in self._connection.execute("SELECT version FROM schema_migrations")}
            executed: list[str] = []
            if "0001" not in applied:
                self._connection.executescript(_MIGRATION_0001)
                self._connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)", ("0001", _iso(datetime.now(timezone.utc))))
                self._connection.commit()
                executed.append("0001")
            return executed

    def downgrade_for_test(self) -> None:
        """Remove the M18 schema only in an isolated local/test database."""
        with self._lock:
            self._connection.executescript("""
            DROP TABLE IF EXISTS public_snapshots;
            DROP TABLE IF EXISTS alert_revisions;
            DROP TABLE IF EXISTS performance_results;
            DROP TABLE IF EXISTS monitoring_results;
            DROP TABLE IF EXISTS telemetry_rollups;
            DROP TABLE IF EXISTS metric_results;
            DROP TABLE IF EXISTS deployments;
            DROP TABLE IF EXISTS model_versions;
            DROP TABLE IF EXISTS schema_migrations;
            """)
            self._connection.commit()

    def ingest(self, record: MetricRecord) -> IngestResult:
        self._require_schema()
        key = _idempotency_key(record)
        with self._lock:
            existing = self._connection.execute("SELECT result_id FROM metric_results WHERE idempotency_key = ?", (key,)).fetchone()
            if existing is not None:
                return IngestResult(result_id=existing["result_id"], idempotency_key=key, reused=True)
            try:
                with self._connection:
                    self._connection.execute(
                        "INSERT OR IGNORE INTO model_versions(model_version, created_at) VALUES (?, ?)",
                        (record.model_version, _iso(record.computed_at)),
                    )
                    if record.deployment_id:
                        self._connection.execute(
                            "INSERT OR IGNORE INTO deployments(deployment_id, model_version, created_at) VALUES (?, ?, ?)",
                            (record.deployment_id, record.model_version, _iso(record.computed_at)),
                        )
                    self._connection.execute(
                        """INSERT INTO metric_results(
                            result_id, result_type, status, data_origin, window_start, window_end,
                            computed_at, sample_size, label_coverage, method_version, config_version,
                            model_version, baseline_id, deployment_id, summary_json, distribution_json,
                            idempotency_key, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            record.result_id, record.result_type, record.status, record.data_origin,
                            _iso(record.window_start), _iso(record.window_end), _iso(record.computed_at),
                            record.sample_size, record.label_coverage, record.method_version, record.config_version,
                            record.model_version, record.baseline_id, record.deployment_id,
                            _canonical(record.summary), _canonical(record.distribution), key,
                            _iso(datetime.now(timezone.utc)),
                        ),
                    )
                    self._connection.execute(f"INSERT INTO {_RESULT_TABLES[record.result_type]}(result_id) VALUES (?)", (record.result_id,))
            except sqlite3.IntegrityError as exc:
                raise MetricsStoreError("metric record conflicts with existing immutable result") from exc
        return IngestResult(result_id=record.result_id, idempotency_key=key, reused=False)

    def count_results(self, *, result_type: ResultType | None = None) -> int:
        self._require_schema()
        with self._lock:
            if result_type is None:
                return int(self._connection.execute("SELECT COUNT(*) FROM metric_results").fetchone()[0])
            return int(self._connection.execute("SELECT COUNT(*) FROM metric_results WHERE result_type = ?", (result_type,)).fetchone()[0])

    def dashboard_snapshot(self, *, now: datetime, expected_interval: timedelta) -> dict[str, Any]:
        """Return safe, read-only aggregate data for the internal dashboard."""
        self._require_schema()
        if expected_interval <= timedelta(0):
            raise MetricsStoreError("expected_interval must be positive")
        current = _utc(now, "now")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM metric_results ORDER BY window_end DESC, result_id ASC LIMIT 50"
            ).fetchall()
        results = [_dashboard_row(row) for row in rows]
        if not results:
            return {"state": "not_available", "reason": "no_metrics_ingested", "freshness": {"state": "not_available"}, "results": []}
        latest = results[0]
        age = current - _parse_utc(latest["window_end"])
        freshness = "fresh" if age <= expected_interval else "late" if age <= expected_interval * 2 else "stale"
        return {
            "state": latest["status"],
            "freshness": {"state": freshness, "window_end": latest["window_end"], "age_seconds": int(age.total_seconds())},
            "results": results,
        }

    def apply_retention(self, *, now: datetime, retention: timedelta) -> int:
        self._require_schema()
        if retention <= timedelta(0):
            raise MetricsStoreError("retention must be positive")
        cutoff = _utc(now, "now") - retention
        with self._lock:
            with self._connection:
                cursor = self._connection.execute(
                    "DELETE FROM metric_results WHERE window_end < ?", (_iso(cutoff),)
                )
        return cursor.rowcount

    def _require_schema(self) -> None:
        with self._lock:
            if self._connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metric_results'").fetchone() is None:
                raise MetricsStoreError("M18 schema has not been migrated")


def _dashboard_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "result_id": row["result_id"], "result_type": row["result_type"], "status": row["status"],
        "data_origin": row["data_origin"], "window_start": row["window_start"], "window_end": row["window_end"],
        "computed_at": row["computed_at"], "sample_size": row["sample_size"], "label_coverage": row["label_coverage"],
        "method_version": row["method_version"], "config_version": row["config_version"], "model_version": row["model_version"],
        "baseline_id": row["baseline_id"], "deployment_id": row["deployment_id"],
        "summary": json.loads(row["summary_json"]), "distribution": json.loads(row["distribution_json"]),
    }


def _assert_safe_aggregate(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in _FORBIDDEN_FIELD_FRAGMENTS):
                raise MetricsStoreError(f"aggregate contains forbidden field {key!r}")
            _assert_safe_aggregate(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_safe_aggregate(child)
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise MetricsStoreError("aggregate values must be JSON primitives")


def _idempotency_key(record: MetricRecord) -> str:
    content = {
        "result_id": record.result_id, "result_type": record.result_type, "status": record.status,
        "data_origin": record.data_origin, "window_start": _iso(record.window_start), "window_end": _iso(record.window_end),
        "method_version": record.method_version, "config_version": record.config_version, "model_version": record.model_version,
        "baseline_id": record.baseline_id, "deployment_id": record.deployment_id,
        "summary": record.summary, "distribution": record.distribution,
    }
    return sha256(_canonical(content).encode("utf-8")).hexdigest()


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MetricsStoreError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


_MIGRATION_0001 = """
CREATE TABLE model_versions (
    model_version TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE deployments (
    deployment_id TEXT PRIMARY KEY,
    model_version TEXT NOT NULL REFERENCES model_versions(model_version),
    created_at TEXT NOT NULL
);
CREATE TABLE metric_results (
    result_id TEXT PRIMARY KEY,
    result_type TEXT NOT NULL CHECK(result_type IN ('telemetry','monitoring','performance','alert','recommendation','public_snapshot')),
    status TEXT NOT NULL CHECK(status IN ('stable','warning','critical','unknown','insufficient_data','not_available')),
    data_origin TEXT NOT NULL CHECK(data_origin IN ('offline_test','replayed','synthetic','production')),
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    sample_size INTEGER NOT NULL CHECK(sample_size >= 0),
    label_coverage REAL CHECK(label_coverage IS NULL OR (label_coverage >= 0 AND label_coverage <= 1)),
    method_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    model_version TEXT NOT NULL REFERENCES model_versions(model_version),
    baseline_id TEXT,
    deployment_id TEXT REFERENCES deployments(deployment_id),
    summary_json TEXT NOT NULL,
    distribution_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE telemetry_rollups (result_id TEXT PRIMARY KEY REFERENCES metric_results(result_id) ON DELETE CASCADE);
CREATE TABLE monitoring_results (result_id TEXT PRIMARY KEY REFERENCES metric_results(result_id) ON DELETE CASCADE);
CREATE TABLE performance_results (result_id TEXT PRIMARY KEY REFERENCES metric_results(result_id) ON DELETE CASCADE);
CREATE TABLE alert_revisions (result_id TEXT PRIMARY KEY REFERENCES metric_results(result_id) ON DELETE CASCADE);
CREATE TABLE public_snapshots (result_id TEXT PRIMARY KEY REFERENCES metric_results(result_id) ON DELETE CASCADE);
CREATE INDEX metric_results_window_end_idx ON metric_results(window_end DESC);
CREATE INDEX metric_results_lineage_idx ON metric_results(model_version, deployment_id, result_type);
CREATE INDEX metric_results_status_idx ON metric_results(result_type, status);
"""
