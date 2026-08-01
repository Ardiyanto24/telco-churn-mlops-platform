"""Package imports must stay free of serving and training side effects."""

import importlib
import sys
import unittest
from importlib.util import find_spec


MODULES = (
    "telco_churn",
    "telco_churn.settings",
    "telco_churn.constants",
    "telco_churn.preprocessing",
    "telco_churn.api",
    "telco_churn.training",
    "telco_churn.evaluation",
    "telco_churn.monitoring",
    "telco_churn.public_metrics",
)


@unittest.skipUnless(
    find_spec("sklearn"), "requires the locked M1 runtime (scikit-learn)"
)
class ImportGraphTests(unittest.TestCase):
    def test_all_milestone_one_modules_import_without_legacy_handler(self) -> None:
        for module_name in MODULES:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

        self.assertNotIn("handler", sys.modules)


if __name__ == "__main__":
    unittest.main()
