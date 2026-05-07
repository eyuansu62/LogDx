"""
E4 Part 1 — Summary failure attribution.

Reads existing E1/E3 outputs and per-case ground truth; produces
`results/e4_summary_failure_analysis.json`. No model calls. No LLM judge.

For each case in dev/holdout/stress:

  - decide whether the summary stage produced output
  - decide whether the diagnosis stage produced output
  - classify each ground-truth required signal as:
      present_in_summary
      present_in_summary_but_not_used_by_debugger
      omitted_from_summary
      unknown_paraphrase_possible          (literal mismatch but possibly paraphrased)
      not_in_raw_or_annotation_issue       (signal value doesn't appear in raw.log either)
  - assign zero or more failure modes from the plan's taxonomy
  - assign exactly one top-level attribution

Usage:
    python tools/analyze_summary_failures.py \
        --protocol protocols/cilogbench-v1.2.lock.json \
        --summary-method llm-summary-v1-haiku \
        --diagnoser real-debugger-v1 \
        --splits dev,holdout,stress
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E4-summary-failure-attribution-v1"

# Failure modes (from the E4 plan, plus an explicit "no_failure_summary_needed").
FAILURE_MODES = (
    "omitted_primary_error",
    "omitted_critical_signal",
    "omitted_test_name",
    "omitted_file_name",
    "omitted_command_or_step",
    "omitted_fix_relevant_detail",
    "overfocused_on_last_error",
    "overfocused_on_runner_noise",
    "collapsed_multiple_failures",
    "hallucinated_root_cause",
    "unsupported_evidence",
    "too_generic",
    "good_high_level_but_missing_evidence",
    "summary_provider_error",
    "debugger_provider_error",
    "debugger_ignored_present_evidence",
    "no_failure_summary_needed",
)


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def signal_in_text(signal: dict, text: str) -> bool:
    """Conservative literal substring match on the signal value (and its short
    aliases). Returns True if the signal value appears in the text. False
    otherwise. We do NOT attempt paraphrase / semantic matching here — that is
    represented as `unknown_paraphrase_possible` upstream."""
    if not text:
        return False
    val = (signal.get("value") or "").strip()
    if not val:
        return False
    if val in text:
        return True
    # Short aliases for very long quoted strings — first 60 chars often suffice
    short = val[:60].strip()
    if len(short) >= 24 and short in text:
        return True
    return False


def diagnosis_blob(diag_row: dict) -> str:
    """Concatenate the human-visible parts of a diagnosis row into one
    searchable blob, mirroring how `evaluate_diagnosis.py` builds its text
    blob for signal-mention recall."""
    parts: list[str] = []
    for k in ("summary", "root_cause", "suggested_fix"):
        v = diag_row.get(k)
        if isinstance(v, str):
            parts.append(v)
    for f in diag_row.get("relevant_files") or []:
        if isinstance(f, str):
            parts.append(f)
    for t in diag_row.get("relevant_tests") or []:
        if isinstance(t, str):
            parts.append(t)
    for ev in diag_row.get("evidence") or []:
        if isinstance(ev, dict):
            for k in ("quote", "reason"):
                v = ev.get(k)
                if isinstance(v, str):
                    parts.append(v)
    return "\n".join(parts)


def classify_signal_status(
    signal: dict,
    *,
    summary_text: str,
    raw_text: str,
    summary_diag_blob: str,
) -> str:
    """Return one of the five status strings for the given required signal."""
    in_raw = signal_in_text(signal, raw_text)
    if not in_raw:
        return "not_in_raw_or_annotation_issue"
    in_summary = signal_in_text(signal, summary_text)
    in_diag = signal_in_text(signal, summary_diag_blob)
    if in_summary:
        if in_diag:
            return "present_in_summary"
        return "present_in_summary_but_not_used_by_debugger"
    # Not literal in summary; debugger might still have inferred / paraphrased.
    if in_diag:
        return "unknown_paraphrase_possible"
    return "omitted_from_summary"


def classify_failure_modes(
    *,
    case_id: str,
    case: dict,
    ground_truth: dict,
    summary_text: str,
    summary_status: str,
    diag_row: dict,
    diag_status: str,
    summary_signal_status: list[dict],
) -> list[str]:
    modes: list[str] = []
    if summary_status == "provider_error":
        modes.append("summary_provider_error")
    if diag_status == "provider_error":
        modes.append("debugger_provider_error")

    omitted = [s for s in summary_signal_status
               if s["status"] in ("omitted_from_summary",)
               and s["signal"].get("importance") == "critical"]
    if omitted:
        modes.append("omitted_critical_signal")

    # Specific omission types
    types_omitted = {
        s["signal"].get("type")
        for s in summary_signal_status
        if s["status"] == "omitted_from_summary"
    }
    if "failed_test" in types_omitted or "test_name" in types_omitted:
        modes.append("omitted_test_name")
    if "file_path" in types_omitted or "file" in types_omitted or "stack_location" in types_omitted:
        modes.append("omitted_file_name")
    if "command" in types_omitted or "exit_code" in types_omitted or "step_name" in types_omitted:
        modes.append("omitted_command_or_step")
    if "remediation" in types_omitted:
        modes.append("omitted_fix_relevant_detail")
    if "assertion" in types_omitted or "exception" in types_omitted or "compile_error" in types_omitted:
        # These are usually the primary error; mark separately too.
        modes.append("omitted_primary_error")

    # Hallucination / unsupported evidence (from forbidden-claim violations).
    if (diag_row.get("forbidden_claim_violations") or []):
        modes.append("hallucinated_root_cause")

    # Debugger ignored present evidence
    ignored = [s for s in summary_signal_status
               if s["status"] == "present_in_summary_but_not_used_by_debugger"
               and s["signal"].get("importance") == "critical"]
    if ignored:
        modes.append("debugger_ignored_present_evidence")

    # good_high_level_but_missing_evidence: high-quality wording but low
    # critical-mention recall. Use an explicit threshold.
    crit_rec = diag_row.get("critical_signal_mention_recall")
    cms = diag_row.get("category_match_score_v1_1")
    if (cms is not None and cms >= 0.5
            and crit_rec is not None and crit_rec < 0.5
            and (diag_row.get("forbidden_claim_violations") or []) == []):
        modes.append("good_high_level_but_missing_evidence")

    # too_generic: low must_mention coverage, no specific files/tests
    if (diag_row.get("must_mention_coverage") is not None
            and diag_row["must_mention_coverage"] < 0.3
            and not (diag_row.get("relevant_files") or [])
            and not (diag_row.get("relevant_tests") or [])):
        modes.append("too_generic")

    # no_failure_summary_needed: trivial case where raw is already small.
    raw_p = ROOT / "cases" / case.get("split") / case_id / "raw.log"
    if raw_p.exists() and raw_p.stat().st_size < 2_000:
        modes.append("no_failure_summary_needed")

    return modes


def top_level_attribution(
    *,
    summary_status: str,
    diag_status: str,
    diag_row: dict,
    comparison_diag: dict | None,
    summary_signal_status: list[dict],
    sv1_1_summary: float | None,
    sv1_1_comparison: float | None,
) -> str:
    if summary_status == "provider_error" or diag_status == "provider_error":
        return "provider_error"

    # If most required signals don't even appear in raw → annotation issue.
    statuses = [s["status"] for s in summary_signal_status]
    if statuses and sum(1 for s in statuses if s == "not_in_raw_or_annotation_issue") / max(1, len(statuses)) >= 0.5:
        return "annotation_issue"

    if sv1_1_summary is None:
        return "mixed"
    if sv1_1_summary >= 0.6:
        return "method_success"

    # If the summary preserved most critical signals but the diagnosis still
    # missed them, blame the debugger.
    crit_present = sum(
        1 for s in summary_signal_status
        if s["signal"].get("importance") == "critical"
        and s["status"] in ("present_in_summary", "present_in_summary_but_not_used_by_debugger")
    )
    crit_total = sum(
        1 for s in summary_signal_status
        if s["signal"].get("importance") == "critical"
    )
    crit_ignored = sum(
        1 for s in summary_signal_status
        if s["status"] == "present_in_summary_but_not_used_by_debugger"
        and s["signal"].get("importance") == "critical"
    )
    crit_omitted = sum(
        1 for s in summary_signal_status
        if s["status"] == "omitted_from_summary"
        and s["signal"].get("importance") == "critical"
    )

    summary_lost_critical = crit_total >= 1 and crit_omitted >= max(1, crit_total // 2)
    debugger_lost_critical = crit_total >= 1 and crit_ignored >= max(1, crit_total // 2) and not summary_lost_critical

    # Evaluator might be undercounting: comparison is similar but auto sv1.1 differs a lot.
    if (sv1_1_comparison is not None
            and sv1_1_summary < 0.5
            and sv1_1_comparison < 0.5
            and abs(sv1_1_summary - sv1_1_comparison) < 0.10):
        return "evaluator_possible_undercount"

    if summary_lost_critical and debugger_lost_critical:
        return "mixed"
    if summary_lost_critical:
        return "summary_failure"
    if debugger_lost_critical:
        return "debugger_failure"
    return "mixed"


def per_case_analysis(
    *,
    split: str,
    case_id: str,
    summary_method: str,
    comparison_method: str,
    diagnoser: str,
    cases_dir: Path,
    results_dir: Path,
) -> dict:
    case_path = cases_dir / split / case_id
    gt = load_json(case_path / "ground_truth.json") if (case_path / "ground_truth.json").exists() else {}
    raw_text = (case_path / "raw.log").read_text(encoding="utf-8", errors="replace") if (case_path / "raw.log").exists() else ""

    # Summary metadata + context
    sum_manifest = load_jsonl(results_dir / split / f"{summary_method}.jsonl")
    sum_row = next((r for r in sum_manifest if r["case_id"] == case_id), None)
    sum_meta = (sum_row or {}).get("metadata") or {}
    sum_pe = sum_meta.get("provider_error")
    summary_status = "missing" if sum_row is None else (
        "provider_error" if sum_pe else "ok"
    )
    sum_ctx_path = ROOT / ((sum_row or {}).get("context_path") or "")
    summary_text = sum_ctx_path.read_text(encoding="utf-8", errors="replace") if sum_ctx_path.exists() else ""

    # Summary signal recall (per-case stats)
    sig_eval = load_json(results_dir / split / f"eval_{summary_method}.json") if (results_dir / split / f"eval_{summary_method}.json").exists() else {}
    sig_case = next((c for c in sig_eval.get("cases", []) if c["case_id"] == case_id), {})

    # Summary diagnosis row + eval
    diag_man = load_jsonl(results_dir / split / "diagnoses" / diagnoser / f"{summary_method}.jsonl")
    diag_row_raw = next((r for r in diag_man if r["case_id"] == case_id), None)
    diag_pe = ((diag_row_raw or {}).get("metadata") or {}).get("provider_error")
    diag_body = (diag_row_raw or {}).get("diagnosis") or {}
    diag_blob = diagnosis_blob(diag_body)

    # Find per-case diagnosis eval row for sv1.1
    diag_eval = load_json(results_dir / split / f"eval_diagnosis_{diagnoser}.json") if (results_dir / split / f"eval_diagnosis_{diagnoser}.json").exists() else {}
    method_block = next((m for m in diag_eval.get("methods", []) if m["context_method"] == summary_method), {})
    diag_case_row = next((c for c in method_block.get("cases", []) if c["case_id"] == case_id), {})

    sv1_1 = diag_case_row.get("diagnosis_score_v1_1")
    sv1 = diag_case_row.get("diagnosis_score_v1")
    abstained = diag_case_row.get("abstained")
    if diag_row_raw is None:
        diag_status = "missing"
    elif diag_pe:
        diag_status = "provider_error"
    elif abstained:
        diag_status = "abstained"
    else:
        diag_status = "ok"

    # Comparison method (grep) — same case
    comp_block = next((m for m in diag_eval.get("methods", []) if m["context_method"] == comparison_method), {})
    comp_case_row = next((c for c in comp_block.get("cases", []) if c["case_id"] == case_id), {})
    sv1_1_comp = comp_case_row.get("diagnosis_score_v1_1")

    # Classify each required signal
    signal_status: list[dict] = []
    for s in gt.get("required_signals") or []:
        signal_status.append({
            "signal": s,
            "status": classify_signal_status(
                s,
                summary_text=summary_text,
                raw_text=raw_text,
                summary_diag_blob=diag_blob,
            ),
        })

    failure_modes = classify_failure_modes(
        case_id=case_id,
        case={"split": split},
        ground_truth=gt,
        summary_text=summary_text,
        summary_status=summary_status,
        diag_row=diag_case_row,
        diag_status=diag_status,
        summary_signal_status=signal_status,
    )
    attribution = top_level_attribution(
        summary_status=summary_status,
        diag_status=diag_status,
        diag_row=diag_case_row,
        comparison_diag=comp_case_row,
        summary_signal_status=signal_status,
        sv1_1_summary=sv1_1,
        sv1_1_comparison=sv1_1_comp,
    )

    # Build "missing_signals" list — every required signal that did not end up
    # in the summary or in the diagnosis text.
    missing_signals = [
        {
            "type": s["signal"].get("type"),
            "value": s["signal"].get("value"),
            "importance": s["signal"].get("importance"),
            "status": s["status"],
        }
        for s in signal_status
        if s["status"] in ("omitted_from_summary",
                            "unknown_paraphrase_possible",
                            "present_in_summary_but_not_used_by_debugger")
    ]

    return {
        "case_id": case_id,
        "split": split,
        "summary_status": summary_status,
        "diagnosis_status": diag_status,
        "summary_signal_recall": sig_case.get("signal_recall"),
        "summary_critical_recall": sig_case.get("critical_signal_recall"),
        "summary_sv1_1": sv1_1,
        "summary_sv1": sv1,
        "comparison_method": comparison_method,
        "comparison_sv1_1": sv1_1_comp,
        "delta_vs_comparison": (
            None if (sv1_1 is None or sv1_1_comp is None)
            else round(sv1_1 - sv1_1_comp, 4)
        ),
        "missing_signals": missing_signals,
        "signal_status_summary": {
            "present_in_summary": sum(1 for s in signal_status if s["status"] == "present_in_summary"),
            "present_in_summary_but_not_used_by_debugger": sum(1 for s in signal_status if s["status"] == "present_in_summary_but_not_used_by_debugger"),
            "omitted_from_summary": sum(1 for s in signal_status if s["status"] == "omitted_from_summary"),
            "unknown_paraphrase_possible": sum(1 for s in signal_status if s["status"] == "unknown_paraphrase_possible"),
            "not_in_raw_or_annotation_issue": sum(1 for s in signal_status if s["status"] == "not_in_raw_or_annotation_issue"),
            "total": len(signal_status),
        },
        "failure_modes": failure_modes,
        "top_level_attribution": attribution,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--summary-method", default="llm-summary-v1-haiku")
    ap.add_argument("--diagnoser", default="real-debugger-v1")
    ap.add_argument("--comparison-method", default="grep")
    ap.add_argument("--splits", default="dev,holdout,stress")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "results" / "e4_summary_failure_analysis.json")
    args = ap.parse_args(argv)

    if not args.protocol.exists():
        print(f"ERROR: protocol not found: {args.protocol}", file=sys.stderr)
        return 1
    protocol = load_json(args.protocol)
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]

    all_cases: list[dict] = []
    for split in splits:
        case_dirs = sorted(p for p in (args.cases_dir / split).iterdir() if p.is_dir())
        for cd in case_dirs:
            try:
                case_row = per_case_analysis(
                    split=split,
                    case_id=cd.name,
                    summary_method=args.summary_method,
                    comparison_method=args.comparison_method,
                    diagnoser=args.diagnoser,
                    cases_dir=args.cases_dir,
                    results_dir=args.results_dir,
                )
            except Exception as e:
                print(f"WARN {split}/{cd.name}: {type(e).__name__}: {e}", file=sys.stderr)
                continue
            all_cases.append(case_row)

    # Aggregates
    fm_count = Counter()
    for c in all_cases:
        for fm in c["failure_modes"]:
            fm_count[fm] += 1

    attribution_count = Counter(c["top_level_attribution"] for c in all_cases)

    aggregate = {
        "case_count": len(all_cases),
        "summary_provider_error_count": sum(1 for c in all_cases if c["summary_status"] == "provider_error"),
        "diagnosis_provider_error_count": sum(1 for c in all_cases if c["diagnosis_status"] == "provider_error"),
        "abstention_count": sum(1 for c in all_cases if c["diagnosis_status"] == "abstained"),
        "method_success_count": attribution_count.get("method_success", 0),
        "summary_failure_count": attribution_count.get("summary_failure", 0),
        "debugger_failure_count": attribution_count.get("debugger_failure", 0),
        "evaluator_possible_undercount_count": attribution_count.get("evaluator_possible_undercount", 0),
        "annotation_issue_count": attribution_count.get("annotation_issue", 0),
        "mixed_count": attribution_count.get("mixed", 0),
        "failure_modes": dict(fm_count),
    }

    out_obj = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": protocol.get("protocol_id", "unknown"),
        "summary_method": args.summary_method,
        "comparison_method": args.comparison_method,
        "diagnoser": args.diagnoser,
        "splits": splits,
        "cases": all_cases,
        "aggregate": aggregate,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_obj, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"Wrote {args.out.relative_to(ROOT)}")
    print(f"  cases analyzed: {len(all_cases)}")
    print(f"  attribution: {dict(attribution_count)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
