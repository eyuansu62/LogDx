#!/usr/bin/env python3
"""Regression tests for the one pinned LogDx v1.3 Drain3 baseline."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "run_drain3_baseline", ROOT / "tools" / "run_drain3_baseline.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load Drain3 baseline")
BASELINE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASELINE)


class Drain3BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            (ROOT / "configs" / "drain3" / "drain3-templates.json").read_text()
        )

    def test_output_is_deterministic(self) -> None:
        raw = "job 101 failed\njob 102 failed\nexit 1\n"
        first, first_details = BASELINE.reduce_log(raw, self.config)
        second, second_details = BASELINE.reduce_log(raw, self.config)
        self.assertEqual(first, second)
        self.assertEqual(first_details, second_details)

    def test_numeric_values_are_parameterized(self) -> None:
        raw = "job 101 failed\njob 102 failed\n"
        output, _ = BASELINE.reduce_log(raw, self.config)
        self.assertIn("<*>", output)
        self.assertNotIn("101", output)
        self.assertNotIn("102", output)

    def test_configuration_is_single_and_pinned(self) -> None:
        self.assertEqual(self.config["drain3_version"], "0.9.11")
        self.assertEqual(
            self.config["configuration_scope"], "one fixed corpus-wide configuration"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
