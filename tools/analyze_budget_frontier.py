"""
E4 Part 2 — Budget frontier analysis.

For each context method, compute:
  - macro diagnosis_score_v1_1
  - macro final-context tokens
  - macro summary-processing tokens (0 for non-summary methods)
  - macro total pipeline tokens
  - provider error rate
  - abstention rate
  - confident_error_rate_v1_1

Then sweep final-context-token budgets {1k, 2k, 4k, 8k, 16k, 32k}, report:
  - which methods fit (per-case)
  - best deployable method by sv1.1 among methods that fit
  - 5 routing policies (grep-default, tail-if-short-else-grep,
    grep-if-fits-else-summary, grep-if-fits-else-rtk-err-cat,
    best-oracle-by-budget — clearly marked as oracle)

Inputs are existing E1/E3 outputs only. No model calls.

Usage:
    python tools/analyze_budget_frontier.py \
        --protocol protocols/legacy/cilogbench-v1.2.lock.json \
        --diagnoser real-debugger-v1 \
        --splits dev,holdout,stress
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E4-summary-failure-attribution-v1"

DEFAULT_BUDGETS_TOKENS = [1_000, 2_000, 4_000, 8_000, 16_000, 32_000]

DEFAULT_METHODS = [
    "raw", "tail", "grep",
    "rtk-read", "rtk-log", "rtk-err-cat",
    "llm-summary-v1-mock",
    "llm-summary-v1-haiku",
]

ROUTING_POLICIES = [
    "grep-default",
    "tail-if-short-else-grep",
    "grep-if-fits-else-summary",
    "grep-if-fits-else-rtk-err-cat",
    "best-oracle-by-budget",
]


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def estimate_summary_processing_tokens(split: str, summary_method: str,
                                          case_id: str, raw_chars: int,
                                          results_dir: Path) -> int:
    """Reuse the same logic as the E3 renderer: prefer the per-row usage
    metadata, but fall back to chars/4 if the recorded number undercounts
    the system-prompt cache (pre-2026-05-02 shim runs)."""
    p = results_dir / split / f"{summary_method}.jsonl"
    rows = load_jsonl(p)
    row = next((r for r in rows if r["case_id"] == case_id), None)
    if not row:
        return 0
    usage = ((row.get("metadata") or {}).get("usage") or {})
    in_tok = usage.get("input_tokens") or usage.get("input_tokens_total") or 0
    out_tok = usage.get("output_tokens") or usage.get("output_tokens_total") or 0
    raw_chars_row = row.get("input_byte_size") or raw_chars
    chars_estimate = max(0, raw_chars_row // 4)
    if in_tok < chars_estimate * 0.3:
        in_tok_used = chars_estimate
    else:
        in_tok_used = int(in_tok)
    return int(in_tok_used) + int(out_tok)


def per_case_table(diagnoser: str, methods: list[str], splits: list[str],
                    summary_methods: set[str], results_dir: Path) -> list[dict]:
    """Flatten the diagnosis eval into one row per (split, method, case_id),
    enriched with the right summary_processing_tokens and totals."""
    rows: list[dict] = []
    for s in splits:
        ev_p = results_dir / s / f"eval_diagnosis_{diagnoser}.json"
        if not ev_p.exists():
            continue
        ev = load_json(ev_p)
        for mb in ev.get("methods", []):
            method = mb["context_method"]
            if method not in methods:
                continue
            for c in mb.get("cases", []):
                ctx_tok = c.get("context_tokens") or 0
                diag_tok = c.get("diagnosis_tokens") or 0
                proc_tok = 0
                if method in summary_methods:
                    raw_p = ROOT / "cases" / s / c["case_id"] / "raw.log"
                    raw_chars = raw_p.stat().st_size if raw_p.exists() else 0
                    proc_tok = estimate_summary_processing_tokens(
                        s, method, c["case_id"], raw_chars, results_dir
                    )
                rows.append({
                    "split": s,
                    "method": method,
                    "case_id": c["case_id"],
                    "sv1_1": c.get("diagnosis_score_v1_1"),
                    "sv1": c.get("diagnosis_score_v1"),
                    "final_context_tokens": int(ctx_tok),
                    "summary_processing_tokens": int(proc_tok),
                    "total_pipeline_tokens": int(ctx_tok) + int(diag_tok) + int(proc_tok),
                    "diagnosis_tokens": int(diag_tok),
                    "abstained": bool(c.get("abstained")),
                    "confident_error_v1_1": bool(c.get("confident_error_v1_1")),
                    "provider_error": c.get("provider_error"),
                })
    return rows


def macro(values, default=None):
    pool = [v for v in values if v is not None]
    return round(sum(pool) / len(pool), 4) if pool else default


def per_method_summary(rows: list[dict], methods: list[str]) -> list[dict]:
    out = []
    for m in methods:
        rs = [r for r in rows if r["method"] == m]
        n = len(rs) or 1
        out.append({
            "method": m,
            "case_count": len(rs),
            "macro_sv1_1": macro(r["sv1_1"] for r in rs),
            "macro_sv1": macro(r["sv1"] for r in rs),
            "macro_final_context_tokens": int(macro(r["final_context_tokens"] for r in rs) or 0),
            "macro_summary_processing_tokens": int(macro(r["summary_processing_tokens"] for r in rs) or 0),
            "macro_total_pipeline_tokens": int(macro(r["total_pipeline_tokens"] for r in rs) or 0),
            "provider_error_rate": round(
                sum(1 for r in rs if r["provider_error"]) / n, 4
            ),
            "abstention_rate": round(sum(1 for r in rs if r["abstained"]) / n, 4),
            "confident_error_rate_v1_1": round(
                sum(1 for r in rs if r["confident_error_v1_1"]) / n, 4
            ),
        })
    return out


def per_budget_summary(rows: list[dict], methods: list[str],
                        budgets: list[int]) -> list[dict]:
    """For each budget, find the best deployable method by macro sv1.1 over
    the cases where the method's `final_context_tokens` fits the budget."""
    out: list[dict] = []
    for B in budgets:
        method_perf: list[dict] = []
        for m in methods:
            rs = [r for r in rows if r["method"] == m and r["final_context_tokens"] <= B]
            cov = len(rs) / max(1, sum(1 for r in rows if r["method"] == m))
            if not rs:
                continue
            method_perf.append({
                "method": m,
                "covered_cases": len(rs),
                "coverage_rate": round(cov, 4),
                "macro_sv1_1": macro(r["sv1_1"] for r in rs),
                "macro_total_pipeline_tokens": int(macro(r["total_pipeline_tokens"] for r in rs) or 0),
                "provider_error_rate": round(
                    sum(1 for r in rs if r["provider_error"]) / len(rs), 4
                ),
            })
        # Pick best deployable method by sv1.1 with at least 60% coverage.
        # If no method clears 60%, fall back to highest absolute coverage.
        deployable = [mp for mp in method_perf if mp["coverage_rate"] >= 0.6]
        candidates = deployable or method_perf
        candidates.sort(key=lambda mp: (mp.get("macro_sv1_1") or 0), reverse=True)
        best = candidates[0] if candidates else None
        out.append({
            "budget_tokens": B,
            "method_performance": method_perf,
            "best_deployable_method": best,
            "best_deployable_method_name": (best or {}).get("method"),
            "best_deployable_macro_sv1_1": (best or {}).get("macro_sv1_1"),
            "deployable_methods": [mp["method"] for mp in deployable],
        })
    return out


def policy_choose(case_idx: dict, *, policy: str, budget: int | None) -> str | None:
    """Given a per-case method index `(split, case_id) -> {method -> row}`,
    return the policy's chosen method for that case, or None to skip."""
    methods = case_idx
    raw = methods.get("raw")
    grep = methods.get("grep")
    tail = methods.get("tail")
    summ = methods.get("llm-summary-v1-haiku")
    rtk_err = methods.get("rtk-err-cat")

    if policy == "grep-default":
        return "grep" if grep else None
    if policy == "tail-if-short-else-grep":
        # Use raw input line count as proxy for "short". Fall back to tail's
        # final_context_tokens which closely tracks tail output size.
        if not raw or not tail or not grep:
            return "grep" if grep else None
        if (raw.get("final_context_tokens") or 0) <= 6_000:
            # ~ 400-500 lines * 16 chars-per-token mid-bound
            return "tail"
        return "grep"
    if policy == "grep-if-fits-else-summary":
        if grep is None or budget is None:
            return None
        if (grep.get("final_context_tokens") or 0) <= budget:
            return "grep"
        return "llm-summary-v1-haiku" if summ else None
    if policy == "grep-if-fits-else-rtk-err-cat":
        if grep is None or budget is None:
            return None
        if (grep.get("final_context_tokens") or 0) <= budget:
            return "grep"
        return "rtk-err-cat" if rtk_err else None
    if policy == "best-oracle-by-budget":
        if budget is None:
            # pick the highest sv1.1 method that exists
            choices = [(m, r["sv1_1"]) for m, r in methods.items()
                       if r.get("sv1_1") is not None]
        else:
            choices = [(m, r["sv1_1"]) for m, r in methods.items()
                       if r.get("sv1_1") is not None
                       and (r.get("final_context_tokens") or 0) <= budget]
        if not choices:
            return None
        choices.sort(key=lambda kv: kv[1], reverse=True)
        return choices[0][0]
    return None


def evaluate_policy(rows: list[dict], policy: str,
                     budget: int | None) -> dict:
    by_case: dict[tuple, dict] = defaultdict(dict)
    for r in rows:
        by_case[(r["split"], r["case_id"])][r["method"]] = r
    case_decisions: list[dict] = []
    used_rows: list[dict] = []
    skipped = 0
    for key, methods in by_case.items():
        chosen = policy_choose(methods, policy=policy, budget=budget)
        if not chosen or chosen not in methods:
            skipped += 1
            case_decisions.append({"split": key[0], "case_id": key[1],
                                   "chosen": None, "reason": "no_policy_match"})
            continue
        used_rows.append(methods[chosen])
        case_decisions.append({"split": key[0], "case_id": key[1],
                               "chosen": chosen})
    n = max(1, len(used_rows))
    return {
        "policy": policy,
        "budget_tokens": budget,
        "case_count_covered": len(used_rows),
        "case_count_skipped": skipped,
        "macro_sv1_1": macro(r["sv1_1"] for r in used_rows),
        "macro_final_context_tokens": int(macro(r["final_context_tokens"] for r in used_rows) or 0),
        "macro_summary_processing_tokens": int(macro(r["summary_processing_tokens"] for r in used_rows) or 0),
        "macro_total_pipeline_tokens": int(macro(r["total_pipeline_tokens"] for r in used_rows) or 0),
        "provider_error_rate": round(sum(1 for r in used_rows if r["provider_error"]) / n, 4),
        "abstention_rate": round(sum(1 for r in used_rows if r["abstained"]) / n, 4),
        "confident_error_rate_v1_1": round(sum(1 for r in used_rows if r["confident_error_v1_1"]) / n, 4),
        "case_decisions": case_decisions,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--diagnoser", default="real-debugger-v1")
    ap.add_argument("--splits", default="dev,holdout,stress")
    ap.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    ap.add_argument("--budgets", default=",".join(str(b) for b in DEFAULT_BUDGETS_TOKENS))
    ap.add_argument("--summary-method", default="llm-summary-v1-haiku")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "results" / "e4_budget_frontier.json")
    args = ap.parse_args(argv)

    if not args.protocol.exists():
        print(f"ERROR: protocol not found: {args.protocol}", file=sys.stderr)
        return 1
    protocol = load_json(args.protocol)

    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    budgets = [int(b) for b in args.budgets.split(",") if b.strip()]

    summary_methods = {m for m in methods if m.startswith("llm-summary-v1-") and m != "llm-summary-v1-mock"}

    rows = per_case_table(args.diagnoser, methods, splits, summary_methods, args.results_dir)

    per_method = per_method_summary(rows, methods)
    per_budget = per_budget_summary(rows, methods, budgets)

    # Routing policies (one row per policy + budget combo where applicable).
    policy_results: list[dict] = []
    # Policies that don't depend on budget
    for pol in ("grep-default", "tail-if-short-else-grep"):
        policy_results.append(evaluate_policy(rows, pol, budget=None))
    # Budget-dependent policies
    for pol in ("grep-if-fits-else-summary",
                "grep-if-fits-else-rtk-err-cat",
                "best-oracle-by-budget"):
        for B in (2_000, 4_000, 8_000, 16_000):
            policy_results.append(evaluate_policy(rows, pol, budget=B))
    # Oracle without budget — true upper bound, deployable nowhere
    policy_results.append(evaluate_policy(rows, "best-oracle-by-budget", budget=None))

    out_obj = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": protocol.get("protocol_id", "unknown"),
        "diagnoser": args.diagnoser,
        "splits": splits,
        "methods": methods,
        "budgets": budgets,
        "per_method": per_method,
        "per_budget": per_budget,
        "policies": policy_results,
        "case_count": len({(r["split"], r["case_id"]) for r in rows}),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_obj, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"Wrote {args.out.relative_to(ROOT)}")
    print(f"  methods analyzed: {len(per_method)}")
    print(f"  budgets analyzed: {len(per_budget)}")
    print(f"  policies analyzed: {len(policy_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
