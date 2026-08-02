"""M10 GitHub Actions policy contract checks."""

from __future__ import annotations

from pathlib import Path
import unittest


class CiWorkflowTests(unittest.TestCase):
    def test_workflow_has_required_parallel_jobs_and_least_privilege(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(encoding="utf-8")

        for job in ("fast:", "model:", "container-smoke:", "security:", "required-checks:"):
            self.assertIn(job, workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("retention-days: 14", workflow)

    def test_workflow_uses_sha_tag_and_expected_negative_controls(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(encoding="utf-8")

        self.assertIn("telco-churn-api:${{ github.sha }}", workflow)
        self.assertIn("tests.does_not_exist", workflow)
        self.assertIn("test_evaluation_gates", workflow)
        self.assertIn("docker compose", workflow)
