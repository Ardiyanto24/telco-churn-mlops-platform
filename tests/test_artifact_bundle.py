"""Contract tests for immutable M3 artifact bundles."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from importlib.util import find_spec


RUNTIME_AVAILABLE = all(find_spec(name) for name in ("joblib", "pandas", "sklearn"))

if RUNTIME_AVAILABLE:
    import joblib
    import pandas as pd

    from telco_churn.artifacts import ArtifactLoadError, VerifiedArtifactLoader, write_manifest


class _Preprocessor:
    _last_output_columns_ = ["feature_a", "feature_b"]

    def transform(self, records):
        return pd.DataFrame([[1.0, 2.0] for _ in records], columns=self._last_output_columns_)


class _Model:
    n_features_in_ = 2

    def predict_proba(self, records):
        return [[0.2, 0.8] for _ in range(len(records))]


@unittest.skipUnless(RUNTIME_AVAILABLE, "requires the locked M3 runtime")
class VerifiedArtifactLoaderTests(unittest.TestCase):
    def _create_bundle(self, directory: Path) -> Path:
        joblib.dump(_Preprocessor(), directory / "preprocessor.joblib")
        joblib.dump(_Model(), directory / "model.joblib")
        write_manifest(
            directory,
            model_version="legacy-migrated-v1",
            schema_version="v1",
            baseline_id="m0-legacy-snapshot-v1",
            feature_order=["feature_a", "feature_b"],
            decision_threshold=0.6238,
            low_risk_threshold=0.35,
            high_risk_threshold=0.75,
        )
        return directory

    def test_loads_a_valid_bundle_and_predicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = self._create_bundle(Path(temp_dir))

            loaded = VerifiedArtifactLoader().load(bundle)

            self.assertEqual(loaded.manifest.model_version, "legacy-migrated-v1")
            self.assertEqual(loaded.predict_probabilities([{"value": "unused"}]), [0.8])

    def test_rejects_a_tampered_artifact_before_deserialization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = self._create_bundle(Path(temp_dir))
            (bundle / "model.joblib").write_bytes(b"tampered")

            with self.assertRaisesRegex(ArtifactLoadError, "checksum"):
                VerifiedArtifactLoader().load(bundle)

    def test_rejects_missing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ArtifactLoadError, "manifest"):
                VerifiedArtifactLoader().load(Path(temp_dir))

    def test_rejects_feature_signature_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = self._create_bundle(Path(temp_dir))
            manifest_path = bundle / "model_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["feature_order"] = ["feature_a"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ArtifactLoadError, "feature"):
                VerifiedArtifactLoader().load(bundle)

    def test_rejects_model_and_preprocessor_from_different_signatures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = self._create_bundle(Path(temp_dir))
            model = _Model()
            model.n_features_in_ = 3
            joblib.dump(model, bundle / "model.joblib")
            self._refresh_checksum(bundle, "model.joblib")

            with self.assertRaisesRegex(ArtifactLoadError, "feature"):
                VerifiedArtifactLoader().load(bundle)

    def _refresh_checksum(self, bundle: Path, filename: str) -> None:
        manifest_path = bundle / "model_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"][filename]["sha256"] = hashlib.sha256(
            (bundle / filename).read_bytes()
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
