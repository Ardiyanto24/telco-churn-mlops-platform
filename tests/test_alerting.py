"""M17 candidate alerting and retraining-recommendation contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from telco_churn.alerting import (
    AlertConfig,
    AlertEvidence,
    AlertingError,
    evaluate_alerts,
    transition_alert,
)


UTC = timezone.utc
BASE_TIME = datetime(2026, 8, 1, tzinfo=UTC)


def _evidence(
    result_id: str, *, domain: str = "drift", severity: str = "warning",
    window: str = "2026-08-01", offset: int = 0, origin: str = "synthetic",
    sample_size: int = 500, coverage: float | None = 1.0,
) -> AlertEvidence:
    return AlertEvidence(
        source_result_id=result_id,
        domain=domain,
        source_status=severity,
        signal="tenure" if domain in {"drift", "data_quality"} else "performance",
        window_id=window,
        window_end=BASE_TIME + timedelta(days=offset),
        sample_size=sample_size,
        label_coverage=coverage,
        model_version="m6-logistic-v1",
        baseline_id="baseline-v1",
        config_version="candidate-v1",
        data_origin=origin,
    )


class AlertingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AlertConfig(minimum_performance_sample_size=4, minimum_performance_coverage=.8)

    def test_one_warning_is_suppressed_but_two_consecutive_windows_open_one_alert(self) -> None:
        single = evaluate_alerts([_evidence("r1")], config=self.config)
        persistent = evaluate_alerts([
            _evidence("r1", window="2026-08-01"),
            _evidence("r2", window="2026-08-02", offset=1),
            _evidence("r3", window="2026-08-03", offset=2),
        ], config=self.config)

        self.assertEqual(single["alerts"], [])
        self.assertEqual(len(persistent["alerts"]), 1)
        alert = persistent["alerts"][0]
        self.assertEqual(alert["severity"], "warning")
        self.assertEqual(alert["persistence_count"], 3)
        self.assertEqual(alert["state"], "open")

    def test_operational_failure_is_critical_operational_alert_not_drift_alert(self) -> None:
        result = evaluate_alerts([
            _evidence("job-failed", domain="operational", severity="unknown", window="2026-08-01"),
        ], config=self.config)

        alert = result["alerts"][0]
        self.assertEqual(alert["domain"], "operational")
        self.assertEqual(alert["severity"], "critical")
        self.assertEqual(alert["persistence_count"], 1)

    def test_critical_performance_creates_candidate_recommendation_without_promotion(self) -> None:
        result = evaluate_alerts([
            _evidence("performance-critical", domain="performance", severity="critical", sample_size=4, coverage=.9),
            _evidence("drift-critical", domain="drift", severity="critical", window="2026-08-02", offset=1),
        ], config=self.config)

        self.assertEqual(len(result["recommendations"]), 1)
        recommendation = result["recommendations"][0]
        self.assertEqual(recommendation["status"], "candidate")
        self.assertFalse(recommendation["promotion_approved"])
        self.assertIn("M8", recommendation["required_next_steps"])

    def test_acknowledge_and_resolve_are_append_only_and_actor_attributed(self) -> None:
        alert = evaluate_alerts([
            _evidence("r1"), _evidence("r2", window="2026-08-02", offset=1),
        ], config=self.config)["alerts"][0]
        acknowledged = transition_alert(alert, action="acknowledge", actor_id="ml-engineer-1", reason="triage", at=BASE_TIME)
        resolved = transition_alert(acknowledged, action="resolve", actor_id="ml-engineer-1", reason="source fixed", at=BASE_TIME + timedelta(days=2))

        self.assertEqual(resolved["state"], "resolved")
        self.assertEqual(len(resolved["history"]), 2)
        self.assertEqual(resolved["history"][-1]["actor_id"], "ml-engineer-1")
        with self.assertRaises(AlertingError):
            transition_alert(alert, action="resolve", actor_id="ml-engineer-1", reason="skip ack", at=BASE_TIME)

    def test_identical_evidence_reuses_an_immutable_output(self) -> None:
        evidence = [_evidence("r1"), _evidence("r2", window="2026-08-02", offset=1)]
        with tempfile.TemporaryDirectory() as directory:
            first = evaluate_alerts(evidence, config=self.config, output_dir=Path(directory))
            second = evaluate_alerts(evidence, config=self.config, output_dir=Path(directory))

        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])


if __name__ == "__main__":
    unittest.main()
