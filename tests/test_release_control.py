"""M11 contract tests for audited release manifests and rollback."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest


class ReleaseControlTests(unittest.TestCase):
    def _bundle(self, root: Path, *, version: str = "candidate-v1") -> Path:
        bundle = root / "bundle"
        bundle.mkdir()
        manifest = {
            "manifest_version": 2,
            "model_version": version,
            "model_family": "logistic_regression",
            "schema_version": "v1",
            "baseline_id": "m0-legacy-snapshot-v1",
            "feature_order": ["feature_a"],
            "decision_threshold": 0.5,
            "risk_bands": {"low": 0.25, "high": 0.75},
            "artifacts": {
                "model.joblib": {"sha256": "a" * 64},
                "preprocessor.joblib": {"sha256": "b" * 64},
            },
            "runtime": {"python": "3.10", "joblib": "1.5.3", "scikit_learn": "1.6.1"},
        }
        (bundle / "model_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return bundle

    def test_manifest_binds_image_model_and_source_identity(self) -> None:
        from telco_churn.release_control import ReleaseManifest

        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = self._bundle(Path(temp_dir))
            release = ReleaseManifest.create(
                bundle_dir=bundle,
                image_ref="telco-churn-api:abc123",
                image_digest="sha256:" + "1" * 64,
                source_git_sha="2" * 40,
                evaluation_report_sha256="3" * 64,
                promotion_decision_sha256="4" * 64,
                environment="staging",
                created_at="2026-08-02T00:00:00Z",
            )

            self.assertEqual(release.model_version, "candidate-v1")
            self.assertEqual(release.release_id, "release-" + release.identity_sha256[:12])
            self.assertEqual(release.model_manifest_sha256, hashlib.sha256((bundle / "model_manifest.json").read_bytes()).hexdigest())
            self.assertNotIn("latest", release.image_ref)

    def test_manifest_rejects_bundle_checksum_or_version_mismatch(self) -> None:
        from telco_churn.release_control import ReleaseControlError, ReleaseManifest

        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = self._bundle(Path(temp_dir))
            release = ReleaseManifest.create(
                bundle_dir=bundle,
                image_ref="telco-churn-api:abc123",
                image_digest="sha256:" + "1" * 64,
                source_git_sha="2" * 40,
                evaluation_report_sha256="3" * 64,
                promotion_decision_sha256="4" * 64,
                environment="staging",
                created_at="2026-08-02T00:00:00Z",
            )
            payload = release.to_dict()
            payload["model_version"] = "forged-v2"

            with self.assertRaisesRegex(ReleaseControlError, "model version"):
                ReleaseManifest.from_dict(payload).validate_bundle(bundle)

    def test_rollback_restores_the_previous_complete_release_pair(self) -> None:
        from telco_churn.release_control import ReleaseLedger, ReleaseManifest

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundle = self._bundle(root)
            first = ReleaseManifest.create(
                bundle_dir=bundle, image_ref="telco-churn-api:first", image_digest="sha256:" + "1" * 64,
                source_git_sha="2" * 40, evaluation_report_sha256="3" * 64,
                promotion_decision_sha256="4" * 64, environment="production_simulated", created_at="2026-08-02T00:00:00Z",
            )
            second = ReleaseManifest.create(
                bundle_dir=bundle, image_ref="telco-churn-api:second", image_digest="sha256:" + "5" * 64,
                source_git_sha="6" * 40, evaluation_report_sha256="7" * 64,
                promotion_decision_sha256="8" * 64, environment="production_simulated", created_at="2026-08-02T00:01:00Z",
            )
            ledger = ReleaseLedger(root / "deployments")
            ledger.record(first)
            ledger.record(second)
            ledger.activate(first)
            ledger.activate(second)

            restored = ledger.rollback(to_release_id=first.release_id, operator="ml-engineer@example.test")

            self.assertEqual(restored.release_id, first.release_id)
            self.assertEqual(ledger.current("production_simulated").image_digest, first.image_digest)
            self.assertEqual(ledger.current("production_simulated").model_manifest_sha256, first.model_manifest_sha256)
            self.assertTrue((root / "deployments" / "events").is_dir())


if __name__ == "__main__":
    unittest.main()
