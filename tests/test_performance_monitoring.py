"""M16 delayed-label join and performance-evaluation contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from telco_churn.performance_monitoring import (
    DelayedLabel,
    PerformanceConfig,
    PerformanceMonitoringError,
    PredictionEvent,
    render_markdown,
    run_performance_monitoring,
)


UTC = timezone.utc
AS_OF = datetime(2026, 8, 1, tzinfo=UTC)


def _prediction(
    prediction_id: str, probability: float, *, entity_key: str | None = None,
    predicted_at: datetime = datetime(2026, 4, 1, tzinfo=UTC),
) -> PredictionEvent:
    return PredictionEvent(
        prediction_id=prediction_id,
        entity_key=entity_key or f"entity-{prediction_id}",
        key_id="m12-test-key",
        prediction_at=predicted_at,
        probability=probability,
        decision_threshold=.5,
        model_version="synthetic-model-v1",
        model_bundle_sha256="a" * 64,
        schema_version="v1",
        threshold_version="threshold-v1",
        risk_policy_version="risk-v1",
    )


def _label(prediction_id: str, churned: bool, *, entity_key: str | None = None, revision: int = 1) -> DelayedLabel:
    return DelayedLabel(
        prediction_id=prediction_id,
        entity_key=entity_key or f"entity-{prediction_id}",
        key_id="m12-test-key",
        churned_within_horizon=churned,
        outcome_at=datetime(2026, 7, 1, tzinfo=UTC),
        received_at=datetime(2026, 7, 2, tzinfo=UTC),
        label_revision=revision,
        label_definition_version="churn-v1",
    )


class PerformanceMonitoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = PerformanceConfig(minimum_mature_labels=4, minimum_label_coverage=.8)
        self.predictions = [_prediction("p1", .9), _prediction("p2", .8), _prediction("p3", .4), _prediction("p4", .1)]
        self.labels = [_label("p1", True), _label("p2", True), _label("p3", False), _label("p4", False)]

    def test_synthetic_fixture_calculates_known_ranking_threshold_and_calibration_metrics(self) -> None:
        result = run_performance_monitoring(
            self.predictions, self.labels, config=self.config, as_of=AS_OF, data_origin="synthetic",
        )

        self.assertEqual(result["status"], "stable")
        self.assertEqual(result["coverage"]["ratio"], 1.0)
        self.assertEqual(result["metrics"]["pr_auc"], 1.0)
        self.assertEqual(result["metrics"]["roc_auc"], 1.0)
        self.assertEqual(result["metrics"]["precision"], 1.0)
        self.assertEqual(result["metrics"]["recall"], 1.0)
        self.assertEqual(result["metrics"]["f1"], 1.0)
        self.assertEqual(result["metrics"]["brier_score"], .055)
        self.assertEqual(result["metrics"]["confusion_matrix"], {"tn": 2, "fp": 0, "fn": 0, "tp": 2})

    def test_immature_and_duplicate_events_do_not_inflate_joined_population(self) -> None:
        immature = _prediction("p5", .9, predicted_at=datetime(2026, 7, 15, tzinfo=UTC))
        result = run_performance_monitoring(
            [*self.predictions, self.predictions[0], immature],
            [*self.labels, self.labels[0], _label("p5", True)],
            config=self.config,
            as_of=AS_OF,
            data_origin="synthetic",
        )

        self.assertEqual(result["coverage"]["mature_prediction_count"], 4)
        self.assertEqual(result["coverage"]["joined_label_count"], 4)
        self.assertEqual(result["reconciliation"]["duplicate_prediction_records"], 1)
        self.assertEqual(result["reconciliation"]["duplicate_label_records"], 1)
        self.assertEqual(result["reconciliation"]["immature_prediction_count"], 1)

    def test_low_coverage_is_insufficient_and_no_labels_are_not_available(self) -> None:
        insufficient = run_performance_monitoring(
            self.predictions, self.labels[:2], config=self.config, as_of=AS_OF, data_origin="synthetic",
        )
        unavailable = run_performance_monitoring(
            self.predictions, [], config=self.config, as_of=AS_OF, data_origin="synthetic",
        )

        self.assertEqual(insufficient["status"], "insufficient_data")
        self.assertIsNone(insufficient["metrics"])
        self.assertEqual(unavailable["status"], "not_available")
        self.assertIsNone(unavailable["metrics"])

    def test_conflicting_records_are_quarantined_and_latest_label_revision_is_selected(self) -> None:
        conflicting = _prediction("p1", .2)
        revised = _label("p2", False, revision=2)
        result = run_performance_monitoring(
            [*self.predictions, conflicting], [*self.labels, revised],
            config=self.config, as_of=AS_OF, data_origin="synthetic",
        )

        self.assertEqual(result["reconciliation"]["conflicting_prediction_records"], 1)
        self.assertEqual(result["coverage"]["mature_prediction_count"], 3)
        self.assertEqual(result["reconciliation"]["selected_label_revisions"]["p2"], 2)
        self.assertEqual(result["status"], "insufficient_data")

    def test_identical_input_reuses_the_same_immutable_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = run_performance_monitoring(
                self.predictions, self.labels, config=self.config, as_of=AS_OF,
                data_origin="synthetic", output_dir=Path(directory),
            )
            second = run_performance_monitoring(
                self.predictions, self.labels, config=self.config, as_of=AS_OF,
                data_origin="synthetic", output_dir=Path(directory),
            )

        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_unapproved_production_origin_is_rejected_and_reports_stay_aggregate(self) -> None:
        with self.assertRaises(PerformanceMonitoringError):
            run_performance_monitoring(
                self.predictions, self.labels, config=self.config, as_of=AS_OF, data_origin="production",
            )

        result = run_performance_monitoring(
            self.predictions, [*self.labels[:-1], _label("p4", False, entity_key="wrong-entity")],
            config=self.config, as_of=AS_OF, data_origin="synthetic",
        )
        report = render_markdown(result)

        self.assertEqual(result["reconciliation"]["unmatched_label_count"], 1)
        self.assertNotIn("entity-p1", report)
        self.assertNotIn("prediction_id", report)

    def test_rolling_window_requires_contiguous_months_and_one_label_definition(self) -> None:
        may_prediction = _prediction("p5", .7, predicted_at=datetime(2026, 5, 1, tzinfo=UTC))
        may_label = _label("p5", True)
        rolling = run_performance_monitoring(
            [*self.predictions, may_prediction], [*self.labels, may_label],
            config=PerformanceConfig(minimum_mature_labels=5, minimum_label_coverage=.8),
            as_of=AS_OF, data_origin="synthetic",
        )

        self.assertEqual(rolling["cohort"]["kind"], "rolling")
        self.assertEqual(rolling["cohort"]["utc_months"], ["2026-04", "2026-05"])
        with self.assertRaises(PerformanceMonitoringError):
            run_performance_monitoring(
                self.predictions,
                [*self.labels[:-1], DelayedLabel(
                    prediction_id="p4", entity_key="entity-p4", key_id="m12-test-key",
                    churned_within_horizon=False, outcome_at=datetime(2026, 7, 1, tzinfo=UTC),
                    received_at=datetime(2026, 7, 2, tzinfo=UTC), label_revision=1,
                    label_definition_version="churn-v2",
                )],
                config=self.config, as_of=AS_OF, data_origin="synthetic",
            )


if __name__ == "__main__":
    unittest.main()
