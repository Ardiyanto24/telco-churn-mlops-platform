import unittest

from baseline.runner import compare_snapshots


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


if __name__ == "__main__":
    unittest.main()
