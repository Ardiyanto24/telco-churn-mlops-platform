"""M9 runtime policy checks that do not require a running container."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LocalRuntimePolicyTests(unittest.TestCase):
    def test_compose_keeps_model_bundle_read_only_and_api_localhost_only(self) -> None:
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

        self.assertIn("127.0.0.1:${TELCO_CHURN_API_PORT:-8000}:8000", compose)
        self.assertIn("${TELCO_CHURN_BUNDLE_DIR:?", compose)
        self.assertIn(":/opt/telco-churn/model:ro", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("no-new-privileges:true", compose)

    def test_runtime_image_is_multistage_non_root_and_excludes_sensitive_context(self) -> None:
        dockerfile = (ROOT / "docker" / "api.Dockerfile").read_text(encoding="utf-8")
        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8")

        self.assertIn("AS builder", dockerfile)
        self.assertIn("AS runtime", dockerfile)
        self.assertIn("USER app", dockerfile)
        self.assertIn(".env*", ignored)
        self.assertIn("artifacts/", ignored)
