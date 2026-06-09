"""Static (no-LLM) evaluation: score reducer output directly vs ground truth.

Reuses score_case() from tools/evaluate_signal_recall.py so the headline
metric matches what the technical report cites. We force the
text-fallback path (line_mapping_available=False, no included_line_ranges)
because a Python callable reducer can't preserve line-number metadata
the way grep / hybrid baselines do.
"""
from __future__ import annotations

import importlib.util
import sys

from .corpus import find_repo_root


def _load_static_evaluator():
    if "logdx_ci._signal_recall_evaluator" in sys.modules:
        return sys.modules["logdx_ci._signal_recall_evaluator"]
    path = find_repo_root() / "tools" / "evaluate_signal_recall.py"
    spec = importlib.util.spec_from_file_location(
        "logdx_ci._signal_recall_evaluator", path
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["logdx_ci._signal_recall_evaluator"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def score_case_static(case_id: str, ground_truth: dict, reduced_context: str) -> dict:
    """Score a reducer output via signal_recall (no LLM).

    Returns:
      critical_signal_recall: fraction of critical signals preserved (headline)
      signal_recall: fraction of ALL signals preserved
      per_signal: list of {type, importance, preserved, preserved_via}
      missed_signals: list of un-preserved signals (for debugging)
    """
    ev = _load_static_evaluator()
    # Synthesize a manifest_row that forces the text-fallback path.
    manifest_row = {
        "case_id": case_id,
        "line_mapping_available": False,
        "included_line_ranges": [],
        "reduction_ratio": 0.0,
    }
    return ev.score_case(
        manifest_row=manifest_row,
        ground_truth=ground_truth,
        context_text=reduced_context,
    )
