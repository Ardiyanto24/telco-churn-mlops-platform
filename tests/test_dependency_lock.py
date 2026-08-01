"""Guardrails for the reproducible Milestone 1 runtime."""

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LOCK = REPOSITORY_ROOT / "requirements" / "runtime.lock"


class DependencyLockTests(unittest.TestCase):
    def test_runtime_lock_contains_only_exact_pins(self) -> None:
        lines = [
            line.strip()
            for line in RUNTIME_LOCK.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]

        self.assertGreater(len(lines), 0)
        self.assertTrue(all("==" in line for line in lines))

    def test_lock_pins_the_sklearn_version_used_for_artifact_serialization(self) -> None:
        contents = RUNTIME_LOCK.read_text(encoding="utf-8")
        self.assertIn("scikit-learn==1.6.1", contents)


if __name__ == "__main__":
    unittest.main()
