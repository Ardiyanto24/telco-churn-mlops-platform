"""Deterministic category runner for the M4 unittest suite."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import unittest


CATEGORIES = {
    "fast": ("test_settings.py", "test_dependency_lock.py"),
    "unit": ("test_settings.py", "test_dependency_lock.py"),
    "api": ("test_prediction_api.py", "test_telemetry.py"),
    "model": ("test_preprocessing.py", "test_artifact_bundle.py", "test_data_contract.py", "test_training_pipeline.py", "test_experiment_registry.py", "test_evaluation_gates.py"),
    "integration": ("test_baseline_runner.py", "test_prediction_api.py", "test_local_runtime.py", "test_release_control.py"),
    "all": (
        "test_settings.py", "test_dependency_lock.py", "test_data_contract.py", "test_import_graph.py",
        "test_preprocessing.py", "test_artifact_bundle.py", "test_prediction_api.py", "test_telemetry.py", "test_training_pipeline.py", "test_experiment_registry.py", "test_evaluation_gates.py",
        "test_baseline_runner.py", "test_local_runtime.py", "test_release_control.py",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("category", choices=sorted(CATEGORIES))
    parser.add_argument("--coverage-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "src"))
    if args.coverage_dir:
        import trace
        tracer = trace.Trace(count=True, trace=False)
        result = tracer.runfunc(_run, CATEGORIES[args.category])
        tracer.results().write_results(show_missing=True, coverdir=str(args.coverage_dir))
    else:
        result = _run(CATEGORIES[args.category])
    return 0 if result.wasSuccessful() else 1


def _run(patterns: tuple[str, ...]) -> unittest.TestResult:
    test_dir = Path(__file__).resolve().parents[1] / "tests"
    suite = unittest.TestSuite(
        unittest.defaultTestLoader.discover(str(test_dir), pattern=pattern)
        for pattern in patterns
    )
    return unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == "__main__":
    raise SystemExit(main())
