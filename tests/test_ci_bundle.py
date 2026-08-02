"""Regression coverage for the standalone CI synthetic-bundle generator."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.support import temporary_workspace


class CiBundleTests(unittest.TestCase):
    def test_generator_runs_without_a_pythonpath_override(self) -> None:
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        with temporary_workspace() as workspace:
            result = subprocess.run(
                [sys.executable, "scripts/create_ci_bundle.py", "--output", str(workspace / "bundle")],
                cwd=root, capture_output=True, text=True, check=True, env=environment,
            )

        metadata = json.loads(result.stdout)
        self.assertTrue(metadata["bundle"].endswith("candidate/bundle"))
