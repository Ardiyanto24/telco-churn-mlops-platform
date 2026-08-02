"""M8 quality-gate contract tests."""

from __future__ import annotations

import unittest


class EvaluationGateTests(unittest.TestCase):
    def _config(self):
        from telco_churn.evaluation.gates import GateConfig

        return GateConfig.from_dict({
            "version": "evaluation-gates/v1",
            "absolute": {"average_precision": 0.74, "recall": 0.75, "precision": 0.60, "f1": 0.68,
                         "roc_auc": 0.90, "brier_score": 0.16, "expected_calibration_error": 0.05},
            "regression": {"average_precision": 0.01, "recall": 0.02, "precision": 0.03, "f1": 0.015,
                           "roc_auc": 0.01, "brier_score": 0.01, "expected_calibration_error": 0.01},
            "ece_bins": 10,
        })

    def test_good_candidate_passes_absolute_gates_without_a_champion(self) -> None:
        from telco_churn.evaluation.gates import evaluate_probabilities

        result = evaluate_probabilities(
            [0, 0, 1, 1, 0, 1, 0, 1], [0.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0], 0.5, self._config(),
        )

        self.assertEqual(result.status, "not_comparable")
        self.assertEqual(result.failures, ())
        self.assertGreaterEqual(result.metrics["average_precision"], 0.74)

    def test_candidate_below_absolute_threshold_fails(self) -> None:
        from telco_churn.evaluation.gates import evaluate_probabilities

        result = evaluate_probabilities(
            [0, 0, 1, 1, 0, 1, 0, 1], [0.51, 0.52, 0.50, 0.49, 0.48, 0.51, 0.52, 0.50], 0.5, self._config(),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("absolute.average_precision", result.failures)

    def test_invalid_probability_is_a_hard_failure(self) -> None:
        from telco_churn.evaluation.gates import evaluate_probabilities

        result = evaluate_probabilities([0, 1], [0.2, float("nan")], 0.5, self._config())

        self.assertEqual(result.status, "invalid")
        self.assertIn("probability_validity", result.failures)

    def test_checked_in_policy_includes_versioned_latency_limits(self) -> None:
        from pathlib import Path
        import json
        from telco_churn.evaluation.gates import GateConfig

        policy = json.loads(Path("configs/evaluation/m8-gates-v1.json").read_text(encoding="utf-8"))
        config = GateConfig.from_dict(policy)

        self.assertEqual(config.latency, {"single_p95_ms": 100.0, "batch_100_p95_ms": 500.0})

    def test_regression_against_champion_fails_even_when_absolute_gates_pass(self) -> None:
        from telco_churn.evaluation.gates import evaluate_probabilities

        target = [0, 0, 1, 1, 0, 1, 0, 1, 0, 1]
        champion = [0.01, 0.02, 0.99, 0.98, 0.03, 0.97, 0.04, 0.96, 0.05, 0.95]
        candidate = [0.15, 0.20, 0.85, 0.70, 0.25, 0.75, 0.30, 0.80, 0.35, 0.65]

        result = evaluate_probabilities(target, candidate, 0.5, self._config(), champion_probabilities=champion, champion_threshold=0.5)

        self.assertEqual(result.status, "failed")
        self.assertTrue(any(item.startswith("regression.") for item in result.failures))

    def test_pipeline_reconstructs_the_m6_test_split_and_writes_an_immutable_report(self) -> None:
        from tests.support import temporary_workspace
        from tests.test_training_pipeline import TrainingPipelineTests
        from telco_churn.evaluation.pipeline import evaluate_candidate
        from telco_churn.training.pipeline import run_training
        import json

        with temporary_workspace() as workspace:
            helper = TrainingPipelineTests()
            dataset, manifest = helper._verified_data(workspace)
            candidate = run_training(helper._config(), dataset, manifest, workspace / "candidate").output_dir
            config = workspace / "gates.json"
            config.write_text(json.dumps({
                "version": "evaluation-gates/v1",
                "absolute": {name: (0.0 if name not in {"brier_score", "expected_calibration_error"} else 1.0)
                             for name in ("average_precision", "recall", "precision", "f1", "roc_auc", "brier_score", "expected_calibration_error")},
                "regression": {name: 1.0 for name in ("average_precision", "recall", "precision", "f1", "roc_auc", "brier_score", "expected_calibration_error")},
                "ece_bins": 10,
            }), encoding="utf-8")
            report = evaluate_candidate(candidate, dataset, manifest, config, workspace / "evaluation")
            self.assertTrue((workspace / "evaluation" / "evaluation_report.json").is_file())
            self.assertTrue((workspace / "evaluation" / "model_card.md").is_file())

        self.assertEqual(report["status"], "not_comparable")
        self.assertEqual(report["data_origin"], "offline_test")

    def test_approval_requires_a_passing_report_digest_before_assigning_champion(self) -> None:
        from tests.support import temporary_workspace
        from telco_churn.evaluation.promotion import approve_report
        import json

        class Client:
            def __init__(self): self.calls = []
            def set_model_version_tag(self, *args): self.calls.append(("tag", args))
            def set_registered_model_alias(self, *args): self.calls.append(("alias", args))

        with temporary_workspace() as workspace:
            report = workspace / "report.json"
            report.write_text(json.dumps({"status": "passed", "candidate": {"model_version": "candidate-v1"}}), encoding="utf-8")
            decision = approve_report(report, workspace / "decision.json", approver="ml-engineer@example.test")
            client = Client()
            approve_report(report, workspace / "applied.json", approver="ml-engineer@example.test", decision=decision, client=client, model_name="telco-churn", model_version="3")

        self.assertEqual(decision["status"], "approved")
        self.assertEqual(client.calls[-1][0], "alias")

    def test_apply_rejects_a_forged_approval_for_a_failed_report(self) -> None:
        from hashlib import sha256
        from tests.support import temporary_workspace
        from telco_churn.evaluation.promotion import PromotionError, approve_report
        import json

        class Client:
            def set_model_version_tag(self, *args): raise AssertionError("registry must not be changed")
            def set_registered_model_alias(self, *args): raise AssertionError("registry must not be changed")

        with temporary_workspace() as workspace:
            report = workspace / "report.json"
            contents = json.dumps({"status": "failed", "candidate": {"model_version": "candidate-v1"}}).encode()
            report.write_bytes(contents)
            forged = {"status": "approved", "report_sha256": sha256(contents).hexdigest(), "candidate_model_version": "candidate-v1", "approver": "ml-engineer@example.test"}
            with self.assertRaises(PromotionError):
                approve_report(report, workspace / "applied.json", approver="ml-engineer@example.test", decision=forged, client=Client(), model_name="telco-churn", model_version="3")


if __name__ == "__main__":
    unittest.main()
