"""
Render the E2 Human Review Calibration Memo (E2.5).

Inputs:
    review/batches/<batch_id>/manifest.json
    results/human_review_<batch_id>.json   (from analyze_human_review.py)
    results/<split>/eval_diagnosis_<diagnoser>.json   for the batch's split
    results/{dev,holdout,stress}/eval_diagnosis_<diagnoser>.json   for E1 cross-split context

Output:
    reports/e2_calibration_memo.md   (drops "human_review" prefix on purpose:
                                       reviewer is currently an LLM-as-judge,
                                       not a human — see disclosure inside)

Decides PASS / PARTIAL / FAIL on whether the deterministic diagnosis evaluator
(`diagnosis_score_v1` and friends) is trustworthy enough to keep using as the
primary signal in subsequent experiments.

Decision logic:

  PASS   - overall_vs_score_v1 Spearman >= 0.6 AND
             pairwise auto/human agreement rate >= 0.6 AND
             method_rank_correlation >= 0.6
  PARTIAL- overall_vs_score_v1 Spearman >= 0.3 (any other guardrail may dip)
  FAIL   - overall_vs_score_v1 Spearman < 0.3
             OR pairwise agreement rate < 0.4 with non-trivial sample
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS_SPEARMAN = 0.6
PARTIAL_SPEARMAN = 0.3
PASS_PAIR_AGREE = 0.6
FAIL_PAIR_AGREE = 0.4
PASS_METHOD_RANK = 0.6


def fmt(v, prec: int = 3) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{prec}f}"
    return str(v)


def decide(report: dict) -> tuple[str, list[str]]:
    """Return (verdict, rationale_bullets)."""
    corr = report.get("correlation_with_deterministic", {}) or {}
    overall_corr = corr.get("overall_vs_score_v1")
    pair_agree = ((report.get("pairwise_vs_auto_consistency", {}) or {})
                  .get("totals", {}) or {}).get("agreement_rate")
    pair_n = (((report.get("pairwise_vs_auto_consistency", {}) or {})
               .get("totals", {}) or {}).get("match", 0)
              + ((report.get("pairwise_vs_auto_consistency", {}) or {})
                 .get("totals", {}) or {}).get("mismatch", 0))
    method_rank = report.get("method_rank_correlation_overall_vs_score_v1")
    rationale: list[str] = []
    rationale.append(
        f"overall_vs_score_v1 Spearman = {fmt(overall_corr)} "
        f"(PASS>=`{PASS_SPEARMAN}`, FAIL<`{PARTIAL_SPEARMAN}`)"
    )
    rationale.append(
        f"pairwise human/auto agreement = {fmt(pair_agree)} "
        f"(over {pair_n} non-tie pairs; PASS>=`{PASS_PAIR_AGREE}`, FAIL<`{FAIL_PAIR_AGREE}`)"
    )
    rationale.append(
        f"method-level Spearman (mean human_overall vs mean det_score_v1) = {fmt(method_rank)}"
    )

    # If we have no correlation data at all (zero labels), produce N/A verdict.
    if overall_corr is None and pair_agree is None and method_rank is None:
        rationale.append(
            "No human labels found yet — verdict is N/A until reviewers submit labels."
        )
        return "N/A_NO_LABELS", rationale

    if overall_corr is None:
        rationale.append("Cannot compute primary correlation — too few absolute labels.")
        return "PARTIAL", rationale

    if overall_corr < PARTIAL_SPEARMAN:
        return "FAIL", rationale
    if pair_agree is not None and pair_n >= 5 and pair_agree < FAIL_PAIR_AGREE:
        return "FAIL", rationale
    if (overall_corr >= PASS_SPEARMAN
            and (pair_agree is None or pair_agree >= PASS_PAIR_AGREE)
            and (method_rank is None or method_rank >= PASS_METHOD_RANK)):
        return "PASS", rationale
    return "PARTIAL", rationale


def render(report: dict, manifest: dict, e1_evals: dict, batch_id: str) -> str:
    methods = manifest.get("methods", [])
    split = manifest.get("split", "?")
    diagnoser = manifest.get("diagnoser", "?")
    items_count = report.get("items", {})
    reviewer_ids = report.get("reviewer_ids", [])
    corr = report.get("correlation_with_deterministic", {}) or {}
    pair_block = report.get("pairwise_vs_auto_consistency", {}) or {}
    pair_totals = pair_block.get("totals", {}) or {}
    pair_by = pair_block.get("by_pair", {}) or {}
    ce = report.get("confident_error_calibration", {}) or {}
    bucket_counts = report.get("disagreement_bucket_counts", {}) or {}
    largest = report.get("largest_disagreements", []) or []
    method_rows = report.get("methods", []) or []
    method_rank = report.get("method_rank_correlation_overall_vs_score_v1")

    verdict, rationale = decide(report)

    lines: list[str] = []
    lines.append("# E2 Calibration Memo (Expert-Model Review)")
    lines.append("")
    lines.append(
        "> **Reviewer disclosure**: the labels backing this memo were "
        "produced by an LLM-as-judge reviewer (`claude-opus-4-7-expert`), "
        "not by an unaffiliated human. Treat these results as **expert-"
        "model review**. Real human review remains the canonical "
        "calibration; until then, every claim here should be read as "
        "model-on-model. See `reports/e2b_score_calibration_v1_1.md` for "
        "the downstream score-rule calibration that depends on these "
        "labels."
    )
    lines.append("")
    lines.append(f"- **Batch:** `{batch_id}`")
    lines.append(f"- **Protocol:** `{report.get('protocol_id') or manifest.get('protocol_id')}`")
    lines.append(f"- **Split:** `{split}`")
    lines.append(f"- **Diagnoser:** `{diagnoser}`")
    lines.append(f"- **Methods reviewed:** {', '.join(f'`{m}`' for m in methods)}")
    lines.append(f"- **Reviewers:** {', '.join(f'`{r}`' for r in reviewer_ids) or '(none yet)'}")
    lines.append(
        f"- **Items:** {items_count.get('absolute', 0)} absolute + "
        f"{items_count.get('pairwise', 0)} pairwise = {items_count.get('total', 0)} total"
    )
    lines.append("")

    # Section 1: Setup
    lines.append("## 1. Review setup")
    lines.append("")
    lines.append("Built from E1 real-debugger-v1 outputs on `cilogbench-v1.1`.")
    lines.append(f"Methods chosen so the calibration can resolve four questions:")
    lines.append("")
    lines.append("- `raw` — full-context baseline")
    lines.append("- `grep` — top sv1 on stress split (E1 winner-side example)")
    lines.append("- `rtk-err-cat` — top sv1 on dev split (alternate winner)")
    lines.append("- `rtk-log` — bottom sv1 on every split (loser-side example)")
    lines.append("")

    # Section 2: Main correlations
    lines.append("## 2. Main correlations")
    lines.append("")
    lines.append("| Metric pair | Spearman | n | Interpretation |")
    lines.append("|---|---:|---:|---|")
    rows_by_kind = report.get("human_vs_det_rows", []) or []
    n_paired = sum(1 for r in rows_by_kind
                   if r.get("human_overall") is not None and r.get("det_score_v1") is not None)
    interp_overall = (
        "passes 0.6 — auto score tracks usefulness" if (corr.get("overall_vs_score_v1") or 0) >= 0.6
        else "0.3-0.6 — partial signal, narrow your claims"
        if (corr.get("overall_vs_score_v1") or 0) >= 0.3
        else "below 0.3 — auto score does not track usefulness"
        if corr.get("overall_vs_score_v1") is not None else "no data"
    )
    lines.append(
        f"| overall_usefulness vs diagnosis_score_v1 | {fmt(corr.get('overall_vs_score_v1'))} "
        f"| {n_paired} | {interp_overall} |"
    )
    lines.append(
        f"| evidence_support vs critical_signal_mention_recall "
        f"| {fmt(corr.get('evidence_vs_critical_mention'))} | {n_paired} "
        f"| does evaluator's literal-mention proxy track human evidence judgment? |"
    )
    lines.append(
        f"| evidence_support vs valid_evidence_quote_rate "
        f"| {fmt(corr.get('evidence_vs_valid_quote'))} | {n_paired} "
        f"| does quote-validity proxy track human evidence judgment? |"
    )
    lines.append(
        f"| root_cause_correctness vs category_accuracy "
        f"| {fmt(corr.get('root_cause_vs_category_accuracy'))} | {n_paired} "
        f"| does taxonomy match track human root-cause judgment? |"
    )
    lines.append(
        f"| hallucination_severity vs forbidden_claim_count "
        f"| {fmt(corr.get('hallucination_vs_forbidden'))} | {n_paired} "
        f"| does forbidden-claim guard catch human-perceived hallucinations? |"
    )
    lines.append("")
    lines.append(
        f"Method-level rank correlation (mean human overall vs mean det_score_v1 across "
        f"{len([m for m in methods if any(mr.get('context_method') == m for mr in method_rows)])} "
        f"methods): **{fmt(method_rank)}**"
    )
    lines.append("")

    # Section 3: Pairwise preference summary
    lines.append("## 3. Pairwise preference summary")
    lines.append("")
    lines.append("| Pair | Human → Auto | Match | Mismatch | Auto-tie |")
    lines.append("|---|---|---:|---:|---:|")
    for pair_key in sorted(pair_by.keys()):
        s = pair_by[pair_key]
        a, b = pair_key.split("|")
        lines.append(f"| `{a}` vs `{b}` |  | {s.get('match', 0)} | {s.get('mismatch', 0)} | {s.get('auto_tie', 0)} |")
    lines.append(
        f"| **TOTAL** |  | **{pair_totals.get('match', 0)}** | "
        f"**{pair_totals.get('mismatch', 0)}** | **{pair_totals.get('auto_tie', 0)}** |"
    )
    lines.append("")
    lines.append(
        f"Aggregate human/auto agreement rate (over non-tie pairs): "
        f"**{fmt(pair_totals.get('agreement_rate'))}**"
    )
    lines.append("")

    # Per-method human means (helpful context).
    if method_rows:
        lines.append("### Per-method human means")
        lines.append("")
        lines.append(
            "| Method | mean overall | mean root cause | mean evidence | "
            "mean halluc severity | W / L / T |"
        )
        lines.append("|---|---:|---:|---:|---:|---|")
        for r in method_rows:
            lines.append(
                f"| `{r.get('context_method')}` | {fmt(r.get('mean_overall_usefulness'))} "
                f"| {fmt(r.get('mean_root_cause_correctness'))} "
                f"| {fmt(r.get('mean_evidence_support'))} "
                f"| {fmt(r.get('mean_hallucination_severity'))} "
                f"| {r.get('pairwise_wins', 0)} / {r.get('pairwise_losses', 0)} / {r.get('pairwise_ties', 0)} |"
            )
        lines.append("")

    # Section 4: Largest disagreements + taxonomy
    lines.append("## 4. Largest disagreements (top 5, classified)")
    lines.append("")
    lines.append("| Case | Method | human_overall | det_score_v1 | gap | bucket |")
    lines.append("|---|---|---:|---:|---:|---|")
    for d in largest:
        lines.append(
            f"| `{d.get('case_id')}` | `{d.get('context_method')}` "
            f"| {d.get('human_overall')} | {fmt(d.get('det_score_v1'))} "
            f"| {fmt(d.get('disagreement'))} | `{d.get('bucket')}` |"
        )
    if not largest:
        lines.append("| (no labels yet) |  |  |  |  |  |")
    lines.append("")
    if bucket_counts:
        lines.append("**Bucket counts in top-5:**")
        for b, c in sorted(bucket_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- `{b}`: {c}")
        lines.append("")

    # Section 5: Evaluator failure modes
    lines.append("## 5. Evaluator failure modes (derived from buckets)")
    lines.append("")
    failure_explainers = {
        "paraphrase_under_counted":
            "Diagnosis is semantically correct (human gives high marks) but does not "
            "literally mention the critical signals — auto evaluator under-counts.",
        "evidence_copied_without_understanding":
            "Diagnosis quotes a lot of valid evidence but human says it's not actually "
            "useful — auto evaluator over-rewards quote density.",
        "wrong_category_but_useful":
            "Diagnosis picks the wrong taxonomy bucket but humans still found it useful — "
            "category match may be too coarse a feature.",
        "correct_category_but_unhelpful":
            "Category matches but humans say the diagnosis is unhelpful — category match "
            "alone is not sufficient.",
        "unsupported_evidence_quote":
            "High auto score driven by quoted evidence but the quote does not support the "
            "stated root cause — auto evaluator can be tricked by quote validity alone.",
        "confident_wrong_unflagged":
            "Diagnoser was confidently wrong by auto rule but humans did not perceive this "
            "as a hallucination — confident-error threshold may be too aggressive.",
        "useful_abstention_under_rewarded":
            "Diagnoser correctly abstained, humans approved, but auto evaluator gave a low "
            "diagnosis_score_v1 — abstention scoring is mis-aligned.",
        "other":
            "Disagreement does not match any pre-defined bucket — inspect the row manually.",
    }
    for b, c in sorted(bucket_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- **{b}** (n={c}) — {failure_explainers.get(b, '')}")
    if not bucket_counts:
        lines.append("- (no labels yet, no bucket distribution to derive)")
    lines.append("")

    # Confident-error calibration block.
    lines.append("## 6. Confident-error calibration")
    lines.append("")
    lines.append(
        f"- Rows where diagnoser was confidently wrong AND a human label exists: "
        f"**{ce.get('n_confident_errors_with_human_label', 0)}**"
    )
    lines.append(
        f"- Of those, humans flagged severe hallucination (human_hallucination >= 3): "
        f"**{ce.get('human_flagged_severe_hallucination', 0)}**"
    )
    lines.append(
        f"- ...flagged unhelpful (human_overall <= 1): "
        f"**{ce.get('human_flagged_unhelpful', 0)}**"
    )
    lines.append(
        f"- ...flagged either: **{ce.get('human_flagged_either', 0)}** "
        f"({fmt(ce.get('human_flag_rate'))} of confident-error rows)"
    )
    lines.append("")
    lines.append(
        "Interpretation: a high human_flag_rate confirms `confident_error` is a useful "
        "safety signal. A low rate suggests the auto rule is over-firing or under-firing."
    )
    lines.append("")

    # Section 7: Decision + recommended next experiment
    lines.append("## 7. Decision and recommended next experiment")
    lines.append("")
    lines.append(f"**Verdict: `{verdict}`**")
    lines.append("")
    lines.append("Rationale:")
    for r in rationale:
        lines.append(f"- {r}")
    lines.append("")

    lines.append("### Recommended next step")
    lines.append("")
    if verdict == "PASS":
        lines.append(
            "Auto evaluator is trustworthy enough to keep using as the primary signal. "
            "Proceed to **E3: real LLM summary baseline** with the same fixed debugger "
            "(`real-debugger-v1`). Do not change the debugger or evaluator yet — only "
            "add `llm-summary-v1-real` as a new context method and re-run the full "
            "protocol. Track summary processing tokens, final context tokens, and "
            "diagnosis tokens to evaluate the cost/quality trade-off."
        )
    elif verdict == "PARTIAL":
        lines.append(
            "Auto evaluator partially tracks human judgment. Two paths are reasonable:"
        )
        lines.append("")
        lines.append(
            "1. Proceed to **E3** but stop using `diagnosis_score_v1` as a single "
            "ranking number; report multi-metric dashboards and explicitly call out "
            "the disagreement buckets."
        )
        lines.append(
            "2. Or build **E2b: diagnosis evaluator v2** first to widen the trust gap."
        )
    elif verdict == "FAIL":
        lines.append(
            "Auto evaluator does not track human judgment enough to keep relying on "
            "`diagnosis_score_v1` as a primary signal. Do **E2b: diagnosis evaluator "
            "v2** before any further method-comparison experiments. Re-score the "
            "existing 109 E1 diagnoses under the new rubric (no model re-runs needed) "
            "and re-check correlation with human labels. Freeze `cilogbench-v2` if "
            "the new rubric materially changes method ranking."
        )
    elif verdict == "N/A_NO_LABELS":
        lines.append(
            "No reviewer labels are present yet. This memo is a skeleton — re-run "
            "`tools/render_e2_calibration_memo.py --batch-id "
            f"{batch_id}` once at least one reviewer file lands under "
            f"`review/batches/{batch_id}/labels/` to get the real verdict."
        )
    lines.append("")

    # Appendix: E1 split summaries for context.
    lines.append("## Appendix A. E1 reference numbers (for context only)")
    lines.append("")
    lines.append("Method-level `diagnosis_score_v1` from the E1 protocol run, all splits:")
    lines.append("")
    lines.append("| Method | dev sv1 | holdout sv1 | stress sv1 |")
    lines.append("|---|---:|---:|---:|")
    e1_methods = sorted({
        m["context_method"]
        for split_data in e1_evals.values()
        for m in (split_data or {}).get("methods", [])
    })
    for m in e1_methods:
        row = [f"`{m}`"]
        for s in ("dev", "holdout", "stress"):
            sd = e1_evals.get(s) or {}
            mb = next((mb for mb in sd.get("methods", []) if mb["context_method"] == m), None)
            row.append(fmt(mb.get("diagnosis_score_v1") if mb else None))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Appendix: how to regenerate.
    lines.append("## Appendix B. Pipeline")
    lines.append("")
    lines.append("```")
    lines.append("# Validate labels first")
    lines.append(f"python3 tools/validate_human_review_labels.py --batch-id {batch_id}")
    lines.append("")
    lines.append("# Aggregate + correlate")
    lines.append(f"python3 tools/analyze_human_review.py --batch-id {batch_id}")
    lines.append("")
    lines.append("# Render this memo")
    lines.append(f"python3 tools/render_e2_calibration_memo.py --batch-id {batch_id}")
    lines.append("```")
    lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--review-root", type=Path, default=ROOT / "review" / "batches")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--out-name", default="e2_calibration_memo.md")
    args = ap.parse_args(argv)

    batch_dir = args.review_root / args.batch_id
    manifest_p = batch_dir / "manifest.json"
    report_p = args.results_dir / f"human_review_{args.batch_id}.json"

    if not manifest_p.exists():
        print(f"ERROR: {manifest_p} missing.", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))

    if not report_p.exists():
        # Allow rendering with empty / TBD content if analyzer hasn't run.
        report = {"items": {"absolute": 0, "pairwise": 0, "total": 0}, "reviewer_ids": []}
        print(
            f"WARN: {report_p} not found - rendering skeleton memo only "
            f"(run analyze_human_review.py first for the real verdict)",
            file=sys.stderr,
        )
    else:
        report = json.loads(report_p.read_text(encoding="utf-8"))

    diagnoser = manifest["diagnoser"]
    e1_evals: dict[str, dict] = {}
    for s in ("dev", "holdout", "stress"):
        ep = args.results_dir / s / f"eval_diagnosis_{diagnoser}.json"
        if ep.exists():
            e1_evals[s] = json.loads(ep.read_text(encoding="utf-8"))

    md = render(report, manifest, e1_evals, args.batch_id)
    out_p = args.reports_dir / args.out_name
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(md, encoding="utf-8")
    print(f"Wrote {out_p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
