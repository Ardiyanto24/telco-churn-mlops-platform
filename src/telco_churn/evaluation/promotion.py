"""Auditable M8 approval gate for registry champion aliases."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any


class PromotionError(RuntimeError):
    """Raised when a promotion decision is incomplete or tampered."""


def approve_report(
    report_path: Path, destination: Path, *, approver: str, decision: dict[str, Any] | None = None,
    client: Any | None = None, model_name: str | None = None, model_version: str | None = None,
) -> dict[str, Any]:
    """Create or apply an immutable approval tied to one exact gate report."""
    report_bytes = report_path.read_bytes()
    report = _read_report(report_bytes)
    digest = sha256(report_bytes).hexdigest()
    if destination.exists():
        raise PromotionError("promotion decision destination must be new")
    if decision is None:
        if report["status"] not in {"passed", "not_comparable"}:
            raise PromotionError("only passing or initial-baseline reports can be approved")
        decision = {
            "decision_version": "m8-promotion-decision/v1", "status": "approved",
            "report_sha256": digest, "candidate_model_version": report["candidate"]["model_version"],
            "approver": approver,
            "initial_baseline": report["status"] == "not_comparable",
        }
    else:
        _validate_decision(decision, digest, report, approver)
        if client is None or not model_name or not model_version:
            raise PromotionError("registry client, model name, and model version are required to apply approval")
        client.set_model_version_tag(model_name, model_version, "validation_status", "approved")
        client.set_model_version_tag(model_name, model_version, "promotion_decision_sha256", sha256(json.dumps(decision, sort_keys=True).encode()).hexdigest())
        client.set_registered_model_alias(model_name, "champion", model_version)
    destination.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision


def _read_report(contents: bytes) -> dict[str, Any]:
    try:
        report = json.loads(contents)
    except json.JSONDecodeError as error:
        raise PromotionError("evaluation report is unreadable") from error
    if not isinstance(report, dict) or not isinstance(report.get("candidate"), dict) or not report["candidate"].get("model_version"):
        raise PromotionError("evaluation report has no candidate identity")
    return report


def _validate_decision(decision: dict[str, Any], digest: str, report: dict[str, Any], approver: str) -> None:
    if report.get("status") not in {"passed", "not_comparable"}:
        raise PromotionError("only passing or initial-baseline reports can be applied")
    if decision.get("status") != "approved" or decision.get("report_sha256") != digest:
        raise PromotionError("approval does not match the exact evaluation report")
    if decision.get("candidate_model_version") != report["candidate"]["model_version"] or decision.get("approver") != approver:
        raise PromotionError("approval candidate or approver does not match")
