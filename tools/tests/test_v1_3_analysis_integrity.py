#!/usr/bin/env python3
"""Fail closed when transfer statistics receive incomplete evaluation panels."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "analyze_v1_3_transfer", ROOT / "tools" / "analyze_v1_3_transfer.py"
)
assert SPEC is not None and SPEC.loader is not None
STATS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATS)
HYBRID = "hybrid-grep-120k-rtk-tail-v3"


def panel(methods=("raw", HYBRID), cases=("a", "b")) -> dict:
    return {
        ("dev", method, case): {"diagnosis_score_v1_1": 0.5}
        for method in methods for case in cases
    }


class AnalysisIntegrityTests(unittest.TestCase):
    def test_missing_case_within_method_is_rejected(self) -> None:
        rows = panel()
        del rows[("dev", HYBRID, "b")]
        with self.assertRaisesRegex(ValueError, "incomplete case/method panel"):
            STATS.validate_panel(rows, "fixture")

    def test_missing_raw_or_hybrid_method_is_rejected(self) -> None:
        for method in ("raw", HYBRID):
            with self.subTest(method=method):
                with self.assertRaisesRegex(ValueError, "missing required comparison method"):
                    STATS.validate_comparison_panels(panel((method,)), panel())

    def test_missing_paired_case_is_rejected_in_either_direction(self) -> None:
        full, partial = panel(), panel(cases=("a",))
        for left, right in ((full, partial), (partial, full)):
            with self.assertRaisesRegex(ValueError, "missing paired comparison rows"):
                STATS.paired_deltas(left, "raw", right, HYBRID)

    def test_missing_historical_split_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing paired historical comparison rows"):
            STATS.validate_comparison_panels(panel(), panel(cases=("a",)))

    def test_historical_models_must_have_identical_panels(self) -> None:
        for partial in (panel(cases=("a",)), panel(methods=("raw",))):
            with mock.patch.object(STATS, "load_eval", side_effect=[(panel(), {}), (partial, {})]):
                with self.assertRaisesRegex(ValueError, "incomplete historical panel"):
                    STATS.historical_panel(["first", "second"], Path("unused"))

    def test_historical_models_must_be_nonempty_and_unique(self) -> None:
        for models in ([], ["first", "first"]):
            with self.assertRaisesRegex(ValueError, "nonempty and unique"):
                STATS.historical_panel(models, Path("unused"))

    def test_complete_history_keeps_equal_model_weight(self) -> None:
        first, second = panel(), panel()
        second[("dev", "raw", "a")]["diagnosis_score_v1_1"] = 1.0
        with mock.patch.object(STATS, "load_eval", side_effect=[(first, {}), (second, {})]):
            rows, means = STATS.historical_panel(["first", "second"], Path("unused"))
        self.assertEqual(rows[("dev", "raw", "a")]["diagnosis_score_v1_1"], 0.75)
        self.assertEqual(means["raw"]["diagnosis_score_v1_1"], 0.625)

    def test_new_method_without_history_is_allowed(self) -> None:
        STATS.validate_comparison_panels(panel(("raw", HYBRID, "drain3")), panel())

    def test_pair_order_is_preserved_for_seeded_bootstrap(self) -> None:
        left = panel(cases=("b", "a"))
        left[("dev", "raw", "b")]["diagnosis_score_v1_1"] = 0.75
        self.assertEqual(STATS.paired_deltas(left, "raw", panel(), HYBRID), [0.25, 0.0])

    def test_empty_or_invalid_score_panel_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty evaluation panel"):
            STATS.validate_panel({}, "empty")
        for value in (None, float("nan"), float("inf")):
            rows = panel()
            rows[("dev", "raw", "a")]["diagnosis_score_v1_1"] = value
            with self.assertRaisesRegex(ValueError, "missing or non-finite diagnosis score"):
                STATS.validate_panel(rows, "invalid")

    def test_missing_eval_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "empty evaluation panel"):
                STATS.load_eval("missing", Path(tmp))

    def test_duplicate_rows_and_empty_methods_are_rejected(self) -> None:
        case = {"case_id": "a", "diagnosis_score_v1_1": 0.5}
        for cases, message in (([case, case], "duplicate evaluation row"), ([], "empty evaluation method")):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "eval_diagnosis_fixture.json").write_text(json.dumps({
                    "methods": [{"context_method": "raw", "cases": cases}]
                }))
                with self.assertRaisesRegex(ValueError, message):
                    STATS.load_eval("fixture", root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
