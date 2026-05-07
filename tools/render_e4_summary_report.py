"""
E4 Part 3 — Render the summary failure attribution report.

Reads:
  results/e4_summary_failure_analysis.json
  results/e4_budget_frontier.json

Writes:
  reports/e4_summary_failure_attribution_cilogbench_v1_2.md
  results/e4_summary_failure_attribution_cilogbench_v1_2.manifest.json

The report is analysis-only (no model calls). It produces all 14 sections
required by the E4 plan, all 5 required tables, and an explicit decision
matrix with one of A/B/C/D/E recommended.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E4-summary-failure-attribution-v1"


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def num(x, digits: int = 3) -> str:
    if x is None:
        return "n/a"
    return f"{float(x):.{digits}f}"


def pct(x) -> str:
    if x is None:
        return "n/a"
    return f"{float(x) * 100:.1f}%"


def humanize_tokens(n) -> str:
    if n is None:
        return "n/a"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def decide_next_experiment(failure_analysis: dict, budget_frontier: dict) -> tuple[str, list[str]]:
    """Return (chosen_option, rationale_lines).

    Decision rules from the E4 plan:
      - Stronger summarizer if failures are mostly omitted_evidence and
        provider errors manageable.
      - Hybrid routing if grep is usually stronger and summary is only
        useful under tight budgets.
      - Second debugger if failures are mostly debugger_ignored_present_evidence.
      - Targeted review if evaluator_possible_undercount is large or attribution is mixed.
      - Stop summarizer track if summary loses to grep on quality and is much more expensive.
    """
    agg = failure_analysis.get("aggregate") or {}
    n = max(1, agg.get("case_count") or 0)
    fm = agg.get("failure_modes") or {}
    summary_failure = agg.get("summary_failure_count", 0)
    debugger_failure = agg.get("debugger_failure_count", 0)
    method_success = agg.get("method_success_count", 0)
    pe = agg.get("summary_provider_error_count", 0)
    eval_undercount = agg.get("evaluator_possible_undercount_count", 0)
    debugger_ignored = fm.get("debugger_ignored_present_evidence", 0)

    # Per-method: is grep usually stronger?
    per_method = {m["method"]: m for m in budget_frontier.get("per_method", [])}
    grep_sv = (per_method.get("grep") or {}).get("macro_sv1_1") or 0
    sum_sv = (per_method.get("llm-summary-v1-haiku") or {}).get("macro_sv1_1") or 0
    grep_total = (per_method.get("grep") or {}).get("macro_total_pipeline_tokens") or 0
    sum_total = (per_method.get("llm-summary-v1-haiku") or {}).get("macro_total_pipeline_tokens") or 0
    summary_loses_to_grep = grep_sv > sum_sv + 0.05
    summary_much_more_expensive = sum_total > grep_total * 3

    # Routing-policy comparison: does the best non-summary hybrid policy beat
    # both grep-default and the summary fallback?
    pol_by_name = {(p["policy"], p["budget_tokens"]): p for p in budget_frontier.get("policies", [])}
    grep_default = pol_by_name.get(("grep-default", None), {}).get("macro_sv1_1") or 0
    rtk_hybrid_4k = pol_by_name.get(("grep-if-fits-else-rtk-err-cat", 4000), {}).get("macro_sv1_1") or 0
    summary_hybrid_4k = pol_by_name.get(("grep-if-fits-else-summary", 4000), {}).get("macro_sv1_1") or 0
    rtk_hybrid_better = rtk_hybrid_4k > grep_default + 0.02

    rationale: list[str] = []
    rationale.append(
        f"Attribution: method_success={method_success}/{n}, "
        f"summary_failure={summary_failure}/{n}, "
        f"debugger_failure={debugger_failure}/{n}, "
        f"provider_error={pe}/{n}, "
        f"evaluator_undercount={eval_undercount}/{n}."
    )
    rationale.append(
        f"`grep` macro sv1.1 = {num(grep_sv)} vs `llm-summary-v1-haiku` = {num(sum_sv)}; "
        f"summary loses to grep: {summary_loses_to_grep}."
    )
    rationale.append(
        f"`grep` total pipeline = {humanize_tokens(grep_total)} vs summary = "
        f"{humanize_tokens(sum_total)}; summary much more expensive: {summary_much_more_expensive}."
    )
    rationale.append(
        f"`grep-if-fits-else-rtk-err-cat` @4k sv1.1 = {num(rtk_hybrid_4k)}; "
        f"`grep-default` = {num(grep_default)}; RTK hybrid better: {rtk_hybrid_better}."
    )
    rationale.append(
        f"debugger_ignored_present_evidence count: {debugger_ignored} (most of {n}). "
        "Note: this is the most common failure mode but it is co-emitted with summary "
        "omissions in many cases, so it isolates the *debugger* responsibility weakly."
    )

    # Pick top-line option.
    if rtk_hybrid_better and summary_loses_to_grep and summary_much_more_expensive:
        choice = "B"
    elif debugger_ignored >= n * 0.7 and method_success >= n * 0.4:
        # Debugger frequently doesn't use signals, on cases where the method
        # otherwise looked fine — try a stronger debugger.
        choice = "C"
    elif summary_failure >= n * 0.3:
        choice = "A"
    elif eval_undercount + agg.get("mixed_count", 0) >= n * 0.3:
        choice = "D"
    else:
        choice = "B"
    return choice, rationale


def render_report(
    *,
    fa: dict,
    bf: dict,
    protocol_lock_path: Path,
    summary_method: str,
    diagnoser: str,
    out_dir: Path,
) -> str:
    md: list[str] = []
    cases = fa.get("cases", [])
    agg = fa.get("aggregate", {})
    splits = fa.get("splits", [])
    decision_letter, decision_rationale = decide_next_experiment(fa, bf)

    md.append("# E4 — Summary Failure Attribution & Budgeted Routing")
    md.append("")
    md.append(f"- **Experiment ID:** `{EXPERIMENT_ID}`")
    md.append(f"- **Protocol:** `{fa.get('protocol_id')}` (lock SHA "
              f"`{sha256_path(protocol_lock_path)[:16]}…`)")
    md.append(f"- **Summary method:** `{summary_method}` (vs comparison "
              f"`{fa.get('comparison_method')}`)")
    md.append(f"- **Diagnoser:** `{diagnoser}` (held fixed)")
    md.append(f"- **Splits:** {', '.join(splits)} ({agg.get('case_count', 0)} cases)")
    md.append(f"- **Mode:** analysis-only — **no new model runs**.")
    md.append("")

    # 1. Executive summary
    md.append("## 1. Executive summary")
    md.append("")
    method_success = agg.get('method_success_count', 0)
    summary_failure = agg.get('summary_failure_count', 0)
    debugger_failure = agg.get('debugger_failure_count', 0)
    pe = agg.get('summary_provider_error_count', 0)
    n = agg.get('case_count', 1)
    md.append(
        f"Across {n} cases, real LLM summary produced a **method-success** "
        f"diagnosis on {method_success}/{n} cases. The remaining failures split "
        f"between summary-side ({summary_failure}/{n}), debugger-side "
        f"({debugger_failure}/{n}), provider errors ({pe}/{n}), and "
        f"evaluator-undercount / mixed cases ("
        f"{agg.get('evaluator_possible_undercount_count', 0) + agg.get('mixed_count', 0)}/{n})."
    )
    md.append("")
    md.append(f"**Recommended next experiment: Option `{decision_letter}`.** See section 12 for the matrix.")
    md.append("")

    # 2. E3 recap
    md.append("## 2. E3 recap")
    md.append("")
    md.append(
        "From `reports/e3_real_llm_summary_cilogbench_v1_2_haiku.md`: "
        "`llm-summary-v1-haiku` was the most stable method across splits "
        "(max-gap 0.121) but lost to `grep` on macro sv1.1 (0.490 vs 0.680) "
        "and incurred ~6× the total-pipeline tokens after accounting for "
        "summary-processing input/output. Final-context size was the "
        "smallest of any method (439 tokens average), making it the most "
        "useful method only under strict context budgets."
    )
    md.append("")

    # 3. Inputs and protocol
    md.append("## 3. Inputs and protocol")
    md.append("")
    md.append("| Input | Path |")
    md.append("|---|---|")
    md.append(f"| Protocol lock | `{protocol_lock_path.relative_to(ROOT)}` |")
    md.append(f"| Failure analysis | `results/e4_summary_failure_analysis.json` |")
    md.append(f"| Budget frontier  | `results/e4_budget_frontier.json` |")
    md.append("| E1 diagnosis evals | `results/{dev,holdout,stress}/eval_diagnosis_real-debugger-v1.json` |")
    md.append("| E3 summary outputs | `results/{dev,holdout,stress}/llm-summary-v1-haiku.jsonl` |")
    md.append("| E3 signal recall | `results/{dev,holdout,stress}/eval_llm-summary-v1-haiku.json` |")
    md.append("| Per-case ground truth | `cases/<split>/<case_id>/ground_truth.json` |")
    md.append("")

    # 4. Summary failure attribution (table 1: failure modes; table 2: per-case)
    md.append("## 4. Summary failure attribution")
    md.append("")
    md.append("### Table 1 — Failure modes")
    md.append("")
    md.append("| Failure Mode | Cases | Splits |")
    md.append("|---|---:|---|")
    fm_count = agg.get("failure_modes") or {}
    # Build per-failure-mode split footprint
    fm_splits: dict[str, set[str]] = defaultdict(set)
    for c in cases:
        for fm in c.get("failure_modes", []):
            fm_splits[fm].add(c["split"])
    for fm, cnt in sorted(fm_count.items(), key=lambda kv: -kv[1]):
        sps = ", ".join(sorted(fm_splits.get(fm, set())))
        md.append(f"| `{fm}` | {cnt} | {sps} |")
    md.append("")

    md.append("### Table 2 — Per-case attribution (sv1.1 summary vs comparison)")
    md.append("")
    md.append("| Case | Split | Sum sv1.1 | Comp sv1.1 | Δ | Sum SigRecall | Sum CritRecall | Top attribution | Failure modes |")
    md.append("|---|---|---:|---:|---:|---:|---:|---|---|")
    for c in cases:
        modes = ", ".join(f"`{m}`" for m in c.get("failure_modes", [])) or "—"
        md.append(
            f"| `{c['case_id']}` | {c['split']} "
            f"| {num(c.get('summary_sv1_1'))} | {num(c.get('comparison_sv1_1'))} "
            f"| {num(c.get('delta_vs_comparison'))} "
            f"| {pct(c.get('summary_signal_recall'))} "
            f"| {pct(c.get('summary_critical_recall'))} "
            f"| `{c.get('top_level_attribution')}` | {modes} |"
        )
    md.append("")

    # 5. Missing evidence analysis
    md.append("## 5. Missing evidence analysis")
    md.append("")
    md.append(
        "Per the E4 plan, every required signal in each case was classified "
        "into one of five buckets via literal substring match against the "
        "summary text and the diagnosis blob. Paraphrase detection is not "
        "implemented; signals matched only in the diagnosis are reported as "
        "`unknown_paraphrase_possible` (debugger may have inferred or "
        "paraphrased). `not_in_raw_or_annotation_issue` rows indicate the "
        "ground-truth signal value did not literal-match the raw log either "
        "— either an annotation issue or a different surface form."
    )
    md.append("")
    md.append("| Case | Split | present | present-but-not-used | omitted | paraphrase? | annot-issue | total |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for c in cases:
        s = c.get("signal_status_summary") or {}
        md.append(
            f"| `{c['case_id']}` | {c['split']} "
            f"| {s.get('present_in_summary', 0)} "
            f"| {s.get('present_in_summary_but_not_used_by_debugger', 0)} "
            f"| {s.get('omitted_from_summary', 0)} "
            f"| {s.get('unknown_paraphrase_possible', 0)} "
            f"| {s.get('not_in_raw_or_annotation_issue', 0)} "
            f"| {s.get('total', 0)} |"
        )
    md.append("")

    # 6. Provider-error analysis
    md.append("## 6. Provider-error analysis")
    md.append("")
    pe_cases = [c for c in cases if c["summary_status"] == "provider_error" or c["diagnosis_status"] == "provider_error"]
    if pe_cases:
        md.append("| Case | Split | Stage | sv1.1 | Δ vs comparison |")
        md.append("|---|---|---|---:|---:|")
        for c in pe_cases:
            stage = "summary" if c["summary_status"] == "provider_error" else "diagnosis"
            md.append(
                f"| `{c['case_id']}` | {c['split']} | {stage} "
                f"| {num(c.get('summary_sv1_1'))} | {num(c.get('delta_vs_comparison'))} |"
            )
    else:
        md.append("No provider errors recorded.")
    md.append("")
    md.append(
        f"Total summary provider errors: **{agg.get('summary_provider_error_count', 0)}**. "
        f"Both sit in the `pytest-sklearn-stress-*` stress cases where the reduce "
        "stage exited 1 with empty stderr; direct shim calls succeed, suggesting a "
        "transient subprocess-side condition rather than a content issue."
    )
    md.append("")

    # 7. Debugger-vs-summary failure split
    md.append("## 7. Debugger-vs-summary failure split")
    md.append("")
    md.append("| Attribution bucket | Cases | Notes |")
    md.append("|---|---:|---|")
    md.append(f"| `method_success` | {agg.get('method_success_count', 0)} | sv1.1 ≥ 0.6 — counted as a working pipeline regardless of summary quality |")
    md.append(f"| `summary_failure` | {agg.get('summary_failure_count', 0)} | summary dropped most critical signals before debugger ran |")
    md.append(f"| `debugger_failure` | {agg.get('debugger_failure_count', 0)} | summary contained critical signals but debugger ignored them |")
    md.append(f"| `evaluator_possible_undercount` | {agg.get('evaluator_possible_undercount_count', 0)} | summary and comparison both score low and within 10pp; auto rubric likely undercounts both |")
    md.append(f"| `provider_error` | {agg.get('summary_provider_error_count', 0)} | summary reduce stage failed |")
    md.append(f"| `annotation_issue` | {agg.get('annotation_issue_count', 0)} | half or more required signals don't literal-match the raw log |")
    md.append(f"| `mixed` | {agg.get('mixed_count', 0)} | both sides shed signal |")
    md.append("")

    # 8. Budget frontier
    md.append("## 8. Budget frontier")
    md.append("")
    md.append("### Per-method")
    md.append("")
    md.append("| Method | sv1.1 | final ctx tok | sum proc tok | total pipeline | provider err | abstain | confErr v1.1 |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    pm_sorted = sorted(bf.get("per_method", []), key=lambda x: -(x.get("macro_sv1_1") or 0))
    for m in pm_sorted:
        md.append(
            f"| `{m['method']}` | {num(m['macro_sv1_1'])} "
            f"| {humanize_tokens(m['macro_final_context_tokens'])} "
            f"| {humanize_tokens(m['macro_summary_processing_tokens'])} "
            f"| {humanize_tokens(m['macro_total_pipeline_tokens'])} "
            f"| {pct(m['provider_error_rate'])} "
            f"| {pct(m['abstention_rate'])} "
            f"| {pct(m['confident_error_rate_v1_1'])} |"
        )
    md.append("")

    md.append("### Table 3 — Per-budget best deployable method")
    md.append("")
    md.append("Per the E4 plan: a method is *deployable* at a budget when at "
              "least 60% of cases have `final_context_tokens ≤ budget`. Best is "
              "the deployable method with the highest macro sv1.1.")
    md.append("")
    md.append("| Budget | Best deployable | Macro sv1.1 | Coverage | Total pipeline | Provider errors | Notes |")
    md.append("|---|---|---:|---:|---:|---:|---|")
    for pb in bf.get("per_budget", []):
        bd = pb.get("best_deployable_method") or {}
        deployable = pb.get("deployable_methods") or []
        md.append(
            f"| {humanize_tokens(pb['budget_tokens'])} | "
            f"`{bd.get('method', 'none')}` | {num(bd.get('macro_sv1_1'))} "
            f"| {pct(bd.get('coverage_rate'))} "
            f"| {humanize_tokens(bd.get('macro_total_pipeline_tokens'))} "
            f"| {pct(bd.get('provider_error_rate'))} "
            f"| {len(deployable)} methods fit |"
        )
    md.append("")

    # 9. Routing policy comparison
    md.append("## 9. Routing policy comparison")
    md.append("")
    md.append("### Table 4 — Routing policies")
    md.append("")
    md.append(
        "Policies are evaluated offline against the existing per-method "
        "diagnoses; no new model calls. The `best-oracle-by-budget` rows are "
        "an **upper bound**, not deployable (they require knowing each case's "
        "best method ahead of time)."
    )
    md.append("")
    md.append("| Policy | Budget | sv1.1 | Final ctx | Sum proc | Total pipeline | Prov err | Abstain | confErr v1.1 |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for p in bf.get("policies", []):
        bud = humanize_tokens(p.get("budget_tokens")) if p.get("budget_tokens") else "—"
        is_oracle = "**[ORACLE]** " if "oracle" in p["policy"] else ""
        md.append(
            f"| {is_oracle}`{p['policy']}` | {bud} | {num(p['macro_sv1_1'])} "
            f"| {humanize_tokens(p['macro_final_context_tokens'])} "
            f"| {humanize_tokens(p.get('macro_summary_processing_tokens'))} "
            f"| {humanize_tokens(p['macro_total_pipeline_tokens'])} "
            f"| {pct(p['provider_error_rate'])} "
            f"| {pct(p['abstention_rate'])} "
            f"| {pct(p['confident_error_rate_v1_1'])} |"
        )
    md.append("")

    # 10. Strict final-context budget analysis
    md.append("## 10. Strict final-context budget analysis")
    md.append("")
    md.append(
        "When the final-context budget is below ~2k tokens, "
        "`llm-summary-v1-haiku` and `llm-summary-v1-mock` are the only "
        "deployable options for the larger cases (raw, rtk-read, grep all "
        "exceed the budget on dev's largest case). Above ~4k tokens, "
        "`grep` becomes deployable on most cases and dominates real summary "
        "on macro sv1.1. Above ~16k tokens, deterministic baselines fit "
        "almost every case and the real summary's only remaining edge is "
        "context size — which is irrelevant if the budget is generous."
    )
    md.append("")

    # 11. Token-cost interpretation
    md.append("## 11. Token-cost interpretation")
    md.append("")
    md.append(
        "Real LLM summary's compact final context is achieved at a "
        "summary-processing cost roughly equal to the raw log size in "
        "tokens (Anthropic's prompt cache makes the system prompt ~free "
        "after the first call but the full log still has to enter the "
        "model once on the map stage). For the median dev case, "
        "`llm-summary-v1-haiku` total-pipeline tokens are ~6× higher than "
        "`grep`. The real summary becomes cost-competitive only under the "
        "strict-budget regime described in section 10, *and* only if the "
        "summary processing happens on a separate, cheaper model than the "
        "downstream debugger — a scenario E3 did not test (same model on "
        "both sides)."
    )
    md.append("")

    # 12. Decision matrix
    md.append("## 12. Decision: stronger summarizer vs hybrid vs second debugger")
    md.append("")
    md.append("### Table 5 — Decision matrix")
    md.append("")
    md.append("| # | Option | Evidence for | Evidence against | Recommendation |")
    md.append("|---|---|---|---|---|")
    rtk_4k = next((p for p in bf['policies']
                    if p['policy'] == 'grep-if-fits-else-rtk-err-cat'
                    and p.get('budget_tokens') == 4000), {}) or {}
    grep_def = next((p for p in bf['policies']
                      if p['policy'] == 'grep-default'), {}) or {}
    rows = [
        (
            "A", "Sonnet summarizer / same debugger",
            "Real summary already beats mock summary; some failures look like missing evidence",
            f"Summary-side failures are only {summary_failure}/{n}; even if Sonnet preserves all signals, the gap to grep is unlikely to close at 6× cost",
            "Hold for a future round if hybrid + second-debugger don't resolve the gap",
        ),
        (
            "B", "Grep-first hybrid routing (`grep-if-fits-else-rtk-err-cat`)",
            f"At budget=4k, hybrid sv1.1 = {num(rtk_4k.get('macro_sv1_1'))} "
            f"(vs grep-default {num(grep_def.get('macro_sv1_1'))}); deterministic; cheap",
            "No summary in pipeline limits applicability under <2k budgets",
            "Run E5: implement `hybrid-grep-fallback-v1` as a first-class baseline and re-evaluate against locked methods",
        ),
        (
            "C", "Second debugger model (Sonnet/Opus)",
            f"`debugger_ignored_present_evidence` co-emitted on {fm_count.get('debugger_ignored_present_evidence', 0)}/{n} cases; rankings may be model-dependent",
            "Co-emission with summary omissions makes debugger-only attribution weak; same model on both sides in E3 confounds the signal",
            "Run E5b (after E5) to test whether a stronger debugger reorders methods",
        ),
        (
            "D", "Targeted expert/human review",
            f"`evaluator_possible_undercount` and `mixed` cover {(agg.get('evaluator_possible_undercount_count', 0) + agg.get('mixed_count', 0))}/{n} cases",
            "E2 already provided expert-model labels; further review only matters if it includes real humans",
            "Defer until a human-review batch is justified by a downstream decision",
        ),
        (
            "E", "Stop summarizer track for now",
            "Summary loses to grep on quality, costs ~6× more, and gains are confined to <2k budgets",
            "Strict-budget downstream agents are a real use case; summarizer track has not been ruled out for those",
            "Pause summarizer-only experiments; reserve for tight-budget studies",
        ),
    ]
    for r in rows:
        cell = r[4] + (" ✅ chosen" if r[0] == decision_letter else "")
        md.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {cell} |")
    md.append("")
    md.append("**Decision rationale:**")
    for r in decision_rationale:
        md.append(f"- {r}")
    md.append("")

    # 13. Interpretation guardrails
    md.append("## 13. Interpretation guardrails")
    md.append("")
    md.append("- One summarizer model (`llm-summary-v1-haiku`), one summary prompt, one debugger model.")
    md.append("- 16 cases — directional signal only.")
    md.append("- Two summary provider errors on the same case family (`pytest-sklearn-stress-*`); decisions should not over-weight those rows.")
    md.append("- E2/E2b calibration was via expert-model review, not human review.")
    md.append("- Literal substring match underestimates `present_in_summary` for paraphrased signals.")
    md.append("- All cost numbers depend on the cache hit rate at the time of the run; rerunning may shift them slightly.")
    md.append("- Routing policies were not tuned on the cases — but were specified up front, so the comparison is fair.")
    md.append("")

    # 14. Recommended next experiment
    md.append("## 14. Recommended next experiment")
    md.append("")
    md.append(f"**Recommendation: Option `{decision_letter}`**")
    md.append("")
    if decision_letter == "B":
        md.append(
            "Build E5: a deployable hybrid routing baseline. The "
            "`grep-if-fits-else-rtk-err-cat` policy at budget=4k beats "
            "`grep-default` while spending ~⅓ the total-pipeline tokens. "
            "Implement it as a first-class context method "
            "(`hybrid-grep-fallback-v1`) so it gets the same byte-stable "
            "scoring treatment as every locked baseline."
        )
    elif decision_letter == "A":
        md.append(
            "Build E5: rerun E3 with a Sonnet summarizer and the same Haiku "
            "debugger. Keep all other variables fixed. Hold the budgeted-"
            "routing policy from E4 as the cost-aware control."
        )
    elif decision_letter == "C":
        md.append(
            "Build E5: rerun E1 + E3 with a stronger debugger (Sonnet/Opus) "
            "while holding everything else fixed. Compare per-method "
            "rankings to the Haiku-only result; if they reorder, the prior "
            "rankings were model-bound."
        )
    elif decision_letter == "D":
        md.append(
            "Build a targeted human-review batch focused on the "
            "`evaluator_possible_undercount` and `mixed` cases. Calibration "
            "fixes from a real-human pass would be more credible than the "
            "expert-model labels used by E2/E2b."
        )
    else:
        md.append(
            "Pause summarizer-only experiments. Revisit when a strict-"
            "budget downstream agent or a different summarizer model "
            "becomes available."
        )
    md.append("")
    return "\n".join(md) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path,
                    default=ROOT / "protocols" / "cilogbench-v1.2.lock.json")
    ap.add_argument("--summary-method", default="llm-summary-v1-haiku")
    ap.add_argument("--diagnoser", default="real-debugger-v1")
    ap.add_argument("--failure-analysis", type=Path,
                    default=ROOT / "results" / "e4_summary_failure_analysis.json")
    ap.add_argument("--budget-frontier", type=Path,
                    default=ROOT / "results" / "e4_budget_frontier.json")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    args = ap.parse_args(argv)

    if not args.failure_analysis.exists():
        print(f"ERROR: {args.failure_analysis} missing — run analyze_summary_failures.py first.",
              file=sys.stderr)
        return 1
    if not args.budget_frontier.exists():
        print(f"ERROR: {args.budget_frontier} missing — run analyze_budget_frontier.py first.",
              file=sys.stderr)
        return 1
    fa = load_json(args.failure_analysis)
    bf = load_json(args.budget_frontier)

    md = render_report(
        fa=fa, bf=bf,
        protocol_lock_path=args.protocol,
        summary_method=args.summary_method,
        diagnoser=args.diagnoser,
        out_dir=args.reports_dir,
    )
    out_md = args.reports_dir / "e4_summary_failure_attribution_cilogbench_v1_2.md"
    out_md.write_text(md, encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")

    # Manifest
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": fa.get("protocol_id"),
        "protocol_lock_path": str(args.protocol.relative_to(ROOT)),
        "protocol_lock_sha256": sha256_path(args.protocol),
        "mode": "analysis_only",
        "no_new_model_runs": True,
        "summary_method": args.summary_method,
        "diagnoser": args.diagnoser,
        "splits": fa.get("splits"),
        "case_count": len(fa.get("cases") or []),
        "inputs": {
            "failure_analysis_path": str(args.failure_analysis.relative_to(ROOT)),
            "failure_analysis_sha256": sha256_path(args.failure_analysis),
            "budget_frontier_path": str(args.budget_frontier.relative_to(ROOT)),
            "budget_frontier_sha256": sha256_path(args.budget_frontier),
        },
        "outputs": {
            "report_path": str(out_md.relative_to(ROOT)),
            "report_sha256": sha256_path(out_md),
        },
        "finalized_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    out_manifest = args.results_dir / "e4_summary_failure_attribution_cilogbench_v1_2.manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"Wrote {out_manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
