"""Reuse the canonical scoring logic from tools/evaluate_diagnosis.py.

We import the score_case / diagnosis_score_v1_1 / macro functions directly
so the SDK score matches what the published leaderboard uses bit-for-bit.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .corpus import find_repo_root


def _load_evaluator_module():
    """Import tools/evaluate_diagnosis.py as a module."""
    if "logdx_ci._evaluator" in sys.modules:
        return sys.modules["logdx_ci._evaluator"]
    eval_path = find_repo_root() / "tools" / "evaluate_diagnosis.py"
    spec = importlib.util.spec_from_file_location(
        "logdx_ci._evaluator", eval_path
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["logdx_ci._evaluator"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def score_case(diagnosis: dict, ground_truth: dict, reduced_context: str) -> dict:
    """Score one (diagnosis, ground_truth, context) triple.

    Returns a dict with `diagnosis_score_v1_1`, `category_match_score_v1_1`,
    `confident_error_v1_1`, and the underlying recall components.
    """
    ev = _load_evaluator_module()
    return ev.score_case(
        diagnosis=diagnosis,
        ground_truth=ground_truth,
        context_text=reduced_context,
    )


def macro(values):
    """Mean ignoring None, rounded to 4 decimals."""
    ev = _load_evaluator_module()
    return ev.macro(values)
