import json
import os
import tempfile
import unittest
from pathlib import Path

from baseline.runner import (
    build_capture_command,
    capture_snapshot,
    compare_snapshots,
    load_fixture,
)


class CompareSnapshotsTests(unittest.TestCase):
    def test_accepts_equal_snapshot_values(self):
        expected = {"score": 0.8411, "prediction": "Churn"}
        actual = {"score": 0.8411, "prediction": "Churn"}

        self.assertEqual(compare_snapshots(actual, expected), [])

    def test_reports_numeric_values_outside_tolerance(self):
        expected = {"score": 0.8411}
        actual = {"score": 0.8413}

        mismatches = compare_snapshots(actual, expected, tolerance=0.0001)

        self.assertEqual(len(mismatches), 1)
        self.assertIn("score", mismatches[0])


class FixtureContractTests(unittest.TestCase):
    def test_loads_the_anonymous_golden_fixture(self):
        fixture_path = Path("baseline/fixtures/golden_inputs.json")

        fixture = load_fixture(fixture_path)

        self.assertEqual(fixture["schema_version"], 1)
        self.assertEqual(
            {scenario["name"] for scenario in fixture["scenarios"]},
            {
                "single_standard",
                "boundary_zero_tenure",
                "batch_customers",
                "dict_of_lists",
                "invalid_empty_inputs",
            },
        )

        fixture_json = json.dumps(fixture)
        self.assertNotIn("7590-VHVEG", fixture_json)
        self.assertIn("BASELINE-", fixture_json)

    def test_rejects_duplicate_scenario_names(self):
        duplicate_fixture = {
            "schema_version": 1,
            "scenarios": [
                {"name": "duplicate", "payload": {"inputs": []}},
                {"name": "duplicate", "payload": {"inputs": []}},
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(duplicate_fixture), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unique"):
                load_fixture(fixture_path)


class DockerCaptureCommandTests(unittest.TestCase):
    def test_mounts_the_capture_script_read_only_and_disables_bytecode(self):
        command = build_capture_command(
            image="example-baseline:1",
            baseline_dir=Path("baseline").resolve(),
        )

        self.assertEqual(command[:3], ["docker", "run", "--rm"])
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", command)
        self.assertIn("example-baseline:1", command)
        self.assertTrue(any("target=/baseline,readonly" in part for part in command))
        self.assertEqual(command[-1], "/baseline/container_capture.py")


class DockerCaptureIntegrationTests(unittest.TestCase):
    def test_captures_all_golden_scenarios_from_the_legacy_image(self):
        fixture = load_fixture(Path("baseline/fixtures/golden_inputs.json"))

        snapshot = capture_snapshot(
            image=os.environ.get("M0_BASELINE_IMAGE", "telco-churn-baseline:local"),
            baseline_dir=Path("baseline"),
            fixture=fixture,
        )

        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["runtime"]["python"], "3.10.20")
        self.assertEqual(len(snapshot["scenarios"]), len(fixture["scenarios"]))
        self.assertEqual(snapshot["scenarios"][-1]["response"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
