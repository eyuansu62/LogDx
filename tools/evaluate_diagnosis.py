"""
Score a diagnoser's outputs against per-case ground truth.

Inputs (per context method):
    results/<split>/diagnoses/<diagnoser>/<context_method>.jsonl
    cases/<split>/<case_id>/ground_truth.json

Outputs:
    results/<split>/eval_diagnosis_<diagnoser>.json

Metrics (per case, then macro-averaged per context method):
    1.  diagnosis_success                 — non-empty + no provider_error
    2.  category_accuracy                 — exact category match
    3.  required_signal_mention_recall    — fraction of required signals
                                             whose value/alias/file appears
                                             in the diagnosis text
    4.  critical_signal_mention_recall    — same, for importance=critical
    5.  relevant_file_recall              — gt.relevant_files seen in diag
    6.  relevant_test_recall              — gt.relevant_tests seen in diag
    7.  must_mention_coverage             — gt.expected_diagnosis.must_mention
    8.  forbidden_claim_violations        — gt.expected_diagnosis.must_not_claim
                                             strings that appear in diag text
    9.  valid_evidence_quote_rate         — diag.evidence quotes that actually
                                             appear in the context (>=8 chars)
    10. abstention_rate                   — unknown category or confidence<0.25
    11. confident_error_rate              — confidence>=0.70 AND (wrong category
                                             OR forbidden violation > 0)

Metrics that cannot be computed are null (reported as N/A), not 0.

An optional composite `diagnosis_score_v1` is emitted alongside the
individual metrics but is marked experimental; do NOT treat it as a
leaderboard yet.

No LLM judge. This evaluator is deterministic.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")
WS_RUN_RE = re.compile(r"\s+")

MIN_EVIDENCE_QUOTE_LEN = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_text(s: str) -> str:
    s = ANSI_RE.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


def normalize_for_quote_match(s: str) -> str:
    """For evidence-quote validation we collapse whitespace runs so that a
    model quoting a line with a single space instead of a tab still counts."""
    s = normalize_text(s)
    return WS_RUN_RE.sub(" ", s).strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def discover_diagnosis_methods(diag_root: Path) -> list[str]:
    if not diag_root.is_dir():
        return []
    return sorted(p.stem for p in diag_root.glob("*.jsonl"))


# ---------------------------------------------------------------------------
# Text blob assembly for a single diagnosis
# ---------------------------------------------------------------------------


def diagnosis_text_blob(diag: dict) -> str:
    parts: list[str] = [
        diag.get("summary", ""),
        diag.get("root_cause", ""),
        *(diag.get("relevant_files") or []),
        *(diag.get("relevant_tests") or []),
    ]
    for ev in diag.get("evidence") or []:
        parts.append(ev.get("quote", ""))
        parts.append(ev.get("reason", ""))
    parts.append(diag.get("suggested_fix", ""))
    return normalize_text("\n".join(parts))


# ---------------------------------------------------------------------------
# Per-signal preservation (shared logic with signal-recall evaluator)
# ---------------------------------------------------------------------------


def signal_mentioned(sig: dict, blob: str) -> bool:
    """True iff the signal's value, any alias, or its file appears in blob."""
    v = (sig.get("value") or "").strip()
    if v and v in blob:
        return True
    for alt in sig.get("aliases") or []:
        a = (alt or "").strip()
        if a and a in blob:
            return True
    f = (sig.get("file") or "").strip()
    if f and f in blob:
        return True
    return False


def list_recall(items: list[str], blob: str) -> float | None:
    items = [x for x in items if x and x.strip()]
    if not items:
        return None
    hit = sum(1 for x in items if x.strip() in blob)
    return hit / len(items)


def substring_hits(needles: list[str], blob: str) -> int:
    return sum(1 for n in needles if n and n.strip() and n.strip() in blob)


# ---------------------------------------------------------------------------
# Per-case scoring
# ---------------------------------------------------------------------------


CATEGORY_ALIASES: dict[str, str] = {
    # If the ground truth uses an older failure_category name that does not
    # exactly match the diagnosis enum, map it here. Additions must be
    # justified in docs/evaluation/diagnosis_eval_v1.md.
    "lint_error": "lint_failure",
    "snapshot_diff": "test_assertion",
    "generic_error": "other",
}


def align_category(gt_category: str) -> str:
    return CATEGORY_ALIASES.get(gt_category, gt_category)


# v1.1 calibration: load the partial-match compatibility table once at import.
# Used only by category_match_score_v1_1 / confident_error_v1_1 / diagnosis_score_v1_1.
# Does NOT rewrite ground truth.
_CATEGORY_COMPAT_PATH = ROOT / "configs" / "evaluation" / "category_compatibility_v1_1.json"
try:
    _CATEGORY_COMPAT = (
        json.loads(_CATEGORY_COMPAT_PATH.read_text(encoding="utf-8")).get("compatibility", {})
        if _CATEGORY_COMPAT_PATH.exists() else {}
    )
except Exception:
    _CATEGORY_COMPAT = {}


def category_match_score_v1_1(pred: str, gt: str) -> float | None:
    """Return 1.0 / 0.5 / 0.0 based on the v1.1 compatibility table.
    None means: ground truth has no category, so the score is undefined."""
    if not gt:
        return None
    if pred == "unknown" and gt != "unknown":
        return 0.0
    if pred == gt:
        return 1.0
    partial = (_CATEGORY_COMPAT.get(gt) or {}).get("partial") or []
    if pred in partial:
        return 0.5
    # Symmetric: if gt is in pred's partial list, also score 0.5.
    rev_partial = (_CATEGORY_COMPAT.get(pred) or {}).get("partial") or []
    if gt in rev_partial:
        return 0.5
    return 0.0


def score_case(
    *,
    diagnosis: dict,
    ground_truth: dict,
    context_text: str,
) -> dict:
    case_id = diagnosis["case_id"]
    provider_error = (diagnosis.get("metadata") or {}).get("provider_error")
    diagnosis_success = provider_error is None and bool(
        (diagnosis.get("summary") or "").strip()
        or (diagnosis.get("root_cause") or "").strip()
    )
    # The unknown-only "I don't know" answer still counts as successful
    # delivery (the diagnoser ran), but it will be flagged via abstention.
    diag_blob = diagnosis_text_blob(diagnosis)

    # 2. category accuracy
    gt_cat_raw = ((ground_truth.get("root_cause") or {}).get("category") or "").strip()
    if not gt_cat_raw:
        category_accuracy: float | None = None
    else:
        gt_cat = align_category(gt_cat_raw)
        pred = diagnosis.get("root_cause_category", "")
        if pred == "unknown" and gt_cat != "unknown":
            category_accuracy = 0.0
        else:
            category_accuracy = 1.0 if pred == gt_cat else 0.0

    # 3 + 4. signal mention recall
    signals = ground_truth.get("required_signals") or []
    if signals:
        mentioned = sum(1 for s in signals if signal_mentioned(s, diag_blob))
        required_recall: float | None = mentioned / len(signals)
    else:
        required_recall = None

    critical = [s for s in signals if s.get("importance") == "critical"]
    if critical:
        critical_mentioned = sum(1 for s in critical if signal_mentioned(s, diag_blob))
        critical_recall: float | None = critical_mentioned / len(critical)
    else:
        critical_recall = None

    missed_signals = [
        {
            "type": s.get("type"),
            "value": s.get("value"),
            "file": s.get("file"),
            "importance": s.get("importance"),
        }
        for s in signals if not signal_mentioned(s, diag_blob)
    ]

    # 5 + 6. relevant file / test recall
    rel_files = ground_truth.get("relevant_files") or []
    rel_tests = ground_truth.get("relevant_tests") or []
    file_recall = list_recall(rel_files, diag_blob)
    test_recall = list_recall(rel_tests, diag_blob)

    # 7 + 8. must_mention coverage + forbidden claims
    exp = ground_truth.get("expected_diagnosis") or {}
    must_mention = [s for s in (exp.get("must_mention") or []) if s and s.strip()]
    must_not_claim = [s for s in (exp.get("must_not_claim") or []) if s and s.strip()]
    if must_mention:
        hits = substring_hits(must_mention, diag_blob)
        must_mention_coverage: float | None = hits / len(must_mention)
    else:
        must_mention_coverage = None
    forbidden_violations = [s for s in must_not_claim if s.strip() in diag_blob]

    # 9. valid evidence quote rate
    evidence = diagnosis.get("evidence") or []
    quotes = [(ev.get("quote") or "").strip() for ev in evidence]
    quotes = [q for q in quotes if len(q) >= MIN_EVIDENCE_QUOTE_LEN]
    if quotes:
        normalized_ctx_for_quotes = normalize_for_quote_match(context_text)
        valid = 0
        for q in quotes:
            if normalize_for_quote_match(q) in normalized_ctx_for_quotes:
                valid += 1
        valid_quote_rate: float | None = valid / len(quotes)
    else:
        valid_quote_rate = None

    # 10. abstention
    abstained = (
        diagnosis.get("root_cause_category") == "unknown"
        or float(diagnosis.get("confidence") or 0.0) < 0.25
    )

    # 11. confident error (v1)
    confidence = float(diagnosis.get("confidence") or 0.0)
    wrong_category = (
        category_accuracy is not None and category_accuracy == 0.0
    )
    confident_error = (
        confidence >= 0.70 and (wrong_category or len(forbidden_violations) > 0)
    )

    # v1.1 calibration: partial category match + stricter confident-error rule.
    if not gt_cat_raw:
        category_match_score: float | None = None
    else:
        gt_cat_v1_1 = align_category(gt_cat_raw)
        pred_v1_1 = diagnosis.get("root_cause_category", "")
        category_match_score = category_match_score_v1_1(pred_v1_1, gt_cat_v1_1)

    cms_zero = (category_match_score is not None and category_match_score == 0.0)
    crit_low = (critical_recall is not None and critical_recall < 0.5)
    must_low = (must_mention_coverage is not None and must_mention_coverage < 0.5)
    confident_error_v1_1_flag = bool(
        confidence >= 0.70 and (
            len(forbidden_violations) > 0
            or (cms_zero and crit_low and must_low)
        )
    )

    context_tokens = int((diagnosis.get("input") or {}).get("context_tokens_estimate") or 0)
    diag_tokens = int((diagnosis.get("usage") or {}).get("output_tokens_estimate") or 0)

    per_case: dict = {
        "case_id": case_id,
        "diagnosis_success": diagnosis_success,
        "provider_error": provider_error,
        "root_cause_category": diagnosis.get("root_cause_category", ""),
        "confidence": confidence,
        "category_accuracy": category_accuracy,
        "required_signal_mention_recall":
            None if required_recall is None else round(required_recall, 4),
        "critical_signal_mention_recall":
            None if critical_recall is None else round(critical_recall, 4),
        "relevant_file_recall":
            None if file_recall is None else round(file_recall, 4),
        "relevant_test_recall":
            None if test_recall is None else round(test_recall, 4),
        "must_mention_coverage":
            None if must_mention_coverage is None else round(must_mention_coverage, 4),
        "forbidden_claim_violations": forbidden_violations,
        "valid_evidence_quote_rate":
            None if valid_quote_rate is None else round(valid_quote_rate, 4),
        "abstained": abstained,
        "confident_error": confident_error,
        "category_match_score_v1_1":
            None if category_match_score is None else round(category_match_score, 4),
        "confident_error_v1_1": confident_error_v1_1_flag,
        "missed_signals": missed_signals,
        "context_tokens": context_tokens,
        "diagnosis_tokens": diag_tokens,
    }

    per_case["diagnosis_score_v1"] = round(diagnosis_score_v1(per_case), 4)
    per_case["diagnosis_score_v1_1"] = round(diagnosis_score_v1_1(per_case), 4)
    return per_case


def diagnosis_score_v1(case: dict) -> float:
    """Experimental composite. Clamped to [0,1]. See docs/evaluation/
    diagnosis_eval_v1.md for the exact formula and caveats."""
    def g(name: str, default: float = 0.0) -> float:
        v = case.get(name)
        return float(default if v is None else v)
    forbidden_bin = 1.0 if case.get("forbidden_claim_violations") else 0.0
    confident_err_bin = 1.0 if case.get("confident_error") else 0.0
    raw = (
        0.25 * g("category_accuracy")
        + 0.30 * g("critical_signal_mention_recall")
        + 0.20 * g("must_mention_coverage")
        + 0.10 * g("relevant_file_recall")
        + 0.10 * g("relevant_test_recall")
        + 0.05 * g("valid_evidence_quote_rate")
        - 0.25 * forbidden_bin
        - 0.25 * confident_err_bin
    )
    return max(0.0, min(1.0, raw))


def diagnosis_score_v1_1(case: dict) -> float:
    """v1.1 calibration: same weights as v1 but with category_match_score
    (1.0/0.5/0.0) replacing category_accuracy and the stricter
    confident_error_v1_1 trigger. Preserves v1 alongside.

    Score change drivers vs v1:
      1. Wrong-but-related category lifts from 0 -> 0.5 on the 0.25 weight.
      2. Wrong category alone no longer fires the -0.25 confident-error
         penalty unless evidence is also missing.
    """
    def g(name: str, default: float = 0.0) -> float:
        v = case.get(name)
        return float(default if v is None else v)
    forbidden_bin = 1.0 if case.get("forbidden_claim_violations") else 0.0
    confident_err_bin = 1.0 if case.get("confident_error_v1_1") else 0.0
    raw = (
        0.25 * g("category_match_score_v1_1")
        + 0.30 * g("critical_signal_mention_recall")
        + 0.20 * g("must_mention_coverage")
        + 0.10 * g("relevant_file_recall")
        + 0.10 * g("relevant_test_recall")
        + 0.05 * g("valid_evidence_quote_rate")
        - 0.25 * forbidden_bin
        - 0.25 * confident_err_bin
    )
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Macro + runner
# ---------------------------------------------------------------------------


def macro(values: Iterable[float | None]) -> float | None:
    pool = [v for v in values if v is not None]
    if not pool:
        return None
    return round(sum(pool) / len(pool), 4)


def macro_mean_int(values: Iterable[int]) -> float | None:
    arr = list(values)
    if not arr:
        return None
    return round(sum(arr) / len(arr), 2)


def _load_historical_exclusions() -> list[dict]:
    """Per Codex 2026-06-15 F1 [high]: read
    `configs/historical_provider_error_exclusions.json` so the
    evaluator can inject synthetic zero-score "failed" rows for
    cases that were removed from diagnosis manifests by the
    2026-06-09 / 2026-06-10 cleanups. Pre-fix, the eval denominator
    silently shrank — failures vanished instead of being scored as
    zero. Now: every (split, diagnoser, method, case_id) in the
    exclusion list contributes a provider_error-shaped row to the
    method's cases array, scored through the normal score_case
    path so the macro means reflect the true denominator.

    Returns the raw list from the file (each item has split,
    diagnoser, method, case_id, provider_error_prefix). Returns
    [] if the file doesn't exist (back-compat for repos without
    the exclusion manifest).
    """
    excl_path = ROOT / "configs" / "historical_provider_error_exclusions.json"
    if not excl_path.exists():
        return []
    try:
        data = json.loads(excl_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return list(data.get("exclusions") or [])


def _synthesize_excluded_case_row(
    *, case_id: str, method: str, diagnoser: str,
    provider_error_prefix: str, cases_dir: Path, split: str,
) -> dict:
    """Build a provider_error-shaped diagnosis row for a documented
    historical exclusion. Mirrors what the runner wrote pre-cleanup
    when the model produced a transient failure: stub "unknown"
    diagnosis body + metadata.provider_error set. The score_case
    pipeline then produces a zero-score abstention entry that
    properly contributes to the macro denominator."""
    return {
        "case_id": case_id,
        "context_method": method,
        "diagnoser": diagnoser,
        "mode": "root_cause_diagnosis",
        "summary": "Diagnoser failed (historical exclusion).",
        "root_cause_category": "unknown",
        "root_cause": "unknown",
        "confidence": 0.0,
        "relevant_files": [],
        "relevant_tests": [],
        "evidence": [],
        "suggested_fix": "",
        "input": {"context_tokens_estimate": 0, "context_path": ""},
        "usage": {"output_tokens_estimate": 0},
        "metadata": {
            "provider_error": f"{provider_error_prefix} [historical exclusion]",
            "_excluded_by_historical_manifest": True,
        },
    }


def evaluate_method(
    *,
    split: str,
    diag_path: Path,
    cases_dir: Path,
    results_dir: Path,
    diagnoser: str | None = None,
    exclusions: list[dict] | None = None,
) -> dict:
    rows = load_manifest_rows(diag_path)
    method = diag_path.stem
    cases: list[dict] = []
    for row in rows:
        case_id = row["case_id"]
        gt_path = cases_dir / split / case_id / "ground_truth.json"
        ground_truth = load_json(gt_path) if gt_path.exists() else {}
        ctx_path = ROOT / ((row.get("input") or {}).get("context_path") or "")
        ctx_text = (
            ctx_path.read_text(encoding="utf-8", errors="replace")
            if ctx_path.exists() else ""
        )
        cases.append(
            score_case(diagnosis=row, ground_truth=ground_truth,
                       context_text=ctx_text)
        )
    # Per Codex 2026-06-15 F1 [high]: inject zero-score rows for
    # historical exclusions. The diagnoser/method combination is
    # matched from the exclusion manifest; the synthesized row is
    # scored via the standard score_case path so the resulting
    # case entry is indistinguishable from a real provider_error
    # row from the runner.
    if diagnoser and exclusions:
        existing_ids = {c["case_id"] for c in cases}
        for excl in exclusions:
            if (excl.get("split") != split
                    or excl.get("diagnoser") != diagnoser
                    or excl.get("method") != method):
                continue
            case_id = excl.get("case_id")
            if not case_id or case_id in existing_ids:
                continue
            gt_path = cases_dir / split / case_id / "ground_truth.json"
            ground_truth = load_json(gt_path) if gt_path.exists() else {}
            synthetic = _synthesize_excluded_case_row(
                case_id=case_id, method=method, diagnoser=diagnoser,
                provider_error_prefix=excl.get(
                    "provider_error_prefix", "historical_provider_error"
                ),
                cases_dir=cases_dir, split=split,
            )
            cases.append(
                score_case(diagnosis=synthetic, ground_truth=ground_truth,
                           context_text="")
            )

    n = len(cases)
    success_rate = sum(1 for c in cases if c["diagnosis_success"]) / n if n else None
    abstention = sum(1 for c in cases if c["abstained"]) / n if n else None
    conf_err = sum(1 for c in cases if c["confident_error"]) / n if n else None
    conf_err_v1_1 = sum(1 for c in cases if c.get("confident_error_v1_1")) / n if n else None
    forbidden_any = [1 if c["forbidden_claim_violations"] else 0 for c in cases]
    forbidden_rate = (sum(forbidden_any) / n) if n else None

    return {
        "context_method": diag_path.stem,
        "diagnosis_success_rate":
            None if success_rate is None else round(success_rate, 4),
        "macro_category_accuracy": macro(c["category_accuracy"] for c in cases),
        "macro_required_signal_mention_recall":
            macro(c["required_signal_mention_recall"] for c in cases),
        "macro_critical_signal_mention_recall":
            macro(c["critical_signal_mention_recall"] for c in cases),
        "macro_relevant_file_recall":
            macro(c["relevant_file_recall"] for c in cases),
        "macro_relevant_test_recall":
            macro(c["relevant_test_recall"] for c in cases),
        "macro_must_mention_coverage":
            macro(c["must_mention_coverage"] for c in cases),
        "macro_forbidden_claim_violations":
            None if forbidden_rate is None else round(forbidden_rate, 4),
        "macro_valid_evidence_quote_rate":
            macro(c["valid_evidence_quote_rate"] for c in cases),
        "abstention_rate":
            None if abstention is None else round(abstention, 4),
        "confident_error_rate":
            None if conf_err is None else round(conf_err, 4),
        "confident_error_rate_v1_1":
            None if conf_err_v1_1 is None else round(conf_err_v1_1, 4),
        "macro_context_tokens": macro_mean_int(c["context_tokens"] for c in cases),
        "macro_diagnosis_tokens": macro_mean_int(c["diagnosis_tokens"] for c in cases),
        "macro_category_match_score_v1_1":
            macro(c.get("category_match_score_v1_1") for c in cases),
        "diagnosis_score_v1": macro(c["diagnosis_score_v1"] for c in cases),
        "diagnosis_score_v1_1": macro(c.get("diagnosis_score_v1_1") for c in cases),
        "cases": cases,
    }


def evaluate(
    *, split: str, diagnoser: str, cases_dir: Path, results_dir: Path,
) -> int:
    diag_root = results_dir / split / "diagnoses" / diagnoser
    methods = discover_diagnosis_methods(diag_root)
    if not methods:
        print(f"ERROR: no diagnosis manifests under {diag_root}", file=sys.stderr)
        return 1
    # Per Codex 2026-06-15 F1 [high]: load historical exclusions
    # once; evaluate_method threads them into per-method scoring.
    exclusions = _load_historical_exclusions()
    method_blocks: list[dict] = []
    case_count = 0
    for m in methods:
        block = evaluate_method(
            split=split,
            diag_path=diag_root / f"{m}.jsonl",
            cases_dir=cases_dir,
            results_dir=results_dir,
            diagnoser=diagnoser,
            exclusions=exclusions,
        )
        case_count = max(case_count, len(block["cases"]))
        method_blocks.append(block)

    out = {
        "split": split,
        "diagnoser": diagnoser,
        "case_count": case_count,
        "methods": method_blocks,
    }
    out_path = results_dir / split / f"eval_diagnosis_{diagnoser}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    for b in method_blocks:
        def fmt(x: float | None) -> str:
            return "N/A" if x is None else f"{x:.3f}"
        print(
            f"  {b['context_method']:25s} "
            f"succ={fmt(b['diagnosis_success_rate'])} "
            f"cat={fmt(b['macro_category_accuracy'])} "
            f"crit={fmt(b['macro_critical_signal_mention_recall'])} "
            f"must={fmt(b['macro_must_mention_coverage'])} "
            f"abstain={fmt(b['abstention_rate'])} "
            f"confErr={fmt(b['confident_error_rate'])} "
            f"score_v1={fmt(b['diagnosis_score_v1'])}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Deterministically score a diagnoser's outputs."
    )
    ap.add_argument("--split", default="dev")
    ap.add_argument("--diagnoser", required=True,
                    help="Diagnoser name (matches results/<split>/diagnoses/<name>/).")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    args = ap.parse_args(argv)
    return evaluate(split=args.split, diagnoser=args.diagnoser,
                     cases_dir=args.cases_dir, results_dir=args.results_dir)


if __name__ == "__main__":
    raise SystemExit(main())
