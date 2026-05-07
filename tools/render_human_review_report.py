"""
Render a markdown report for a human-review batch.

Reads:
    results/human_review_<batch_id>.json
Writes:
    reports/human_review_<batch_id>.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def num(x, digits: int = 3) -> str:
    if x is None:
        return "N/A"
    return f"{x:.{digits}f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    in_p = args.results_dir / f"human_review_{args.batch_id}.json"
    if not in_p.exists():
        print(f"ERROR: {in_p} missing. Run analyze_human_review.py first.",
              file=sys.stderr)
        return 1
    data = json.loads(in_p.read_text(encoding="utf-8"))

    md: list[str] = []
    md.append(f"# Human review — `{data['batch_id']}`")
    md.append("")
    md.append(f"- Protocol: **{data.get('protocol_id')}**")
    md.append(f"- Split: **{data.get('split')}**")
    md.append(f"- Diagnoser: `{data.get('diagnoser')}`")
    md.append(f"- Reviewers: {data['reviewer_ids'] or '(none yet)'}")
    md.append(f"- Items: {data['items']}")
    md.append("")

    md.append("## Absolute-score means by method")
    md.append("")
    md.append("| Method | Cases | Root-cause | Evidence | Localization | "
              "Actionable | Hallucination (↓ better) | Overall |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in data["methods"]:
        md.append(
            f"| {m['context_method']} | {m['case_count']} "
            f"| {num(m['mean_root_cause_correctness'])} "
            f"| {num(m['mean_evidence_support'])} "
            f"| {num(m['mean_localization_quality'])} "
            f"| {num(m['mean_actionability'])} "
            f"| {num(m['mean_hallucination_severity'])} "
            f"| {num(m['mean_overall_usefulness'])} |"
        )
    md.append("")

    md.append("## Pairwise win / loss / tie by method")
    md.append("")
    md.append("| Method | Wins | Losses | Ties |")
    md.append("|---|---:|---:|---:|")
    for m in data["methods"]:
        md.append(f"| {m['context_method']} | {m['pairwise_wins']} "
                  f"| {m['pairwise_losses']} | {m['pairwise_ties']} |")
    md.append("")

    md.append("## Human-vs-deterministic correlation (Spearman)")
    md.append("")
    md.append(
        "Correlations over all absolute-mode labels. Small samples: treat "
        "as directional only."
    )
    md.append("")
    md.append("| Pair | Spearman |")
    md.append("|---|---:|")
    for k, v in (data.get("correlation_with_deterministic") or {}).items():
        md.append(f"| `{k}` | {num(v)} |")
    md.append("")

    md.append("## Largest disagreements (human_overall vs diagnosis_score_v1)")
    md.append("")
    dis = data.get("largest_disagreements") or []
    if dis:
        md.append("| case_id | method | human_overall / 4 | det_score_v1 | gap |")
        md.append("|---|---|---:|---:|---:|")
        for r in dis:
            md.append(
                f"| `{r['case_id']}` | `{r['context_method']}` "
                f"| {r['human_overall']}/4 "
                f"| {num(r['det_score_v1'])} "
                f"| {num(r['disagreement'])} |"
            )
    else:
        md.append("- No absolute labels available.")
    md.append("")

    md.append("## Reviewer agreement")
    md.append("")
    ag = data.get("reviewer_agreement") or {}
    if ag.get("reviewer_count", 0) < 2:
        md.append(f"- Only {ag.get('reviewer_count')} reviewer(s); agreement not computed.")
    else:
        md.append(f"- Reviewer count: {ag.get('reviewer_count')}")
        md.append(f"- Raw pairwise agreement (items both reviewers labeled): "
                  f"{num(ag.get('raw_agreement'))}")
    md.append("")

    md.append("## Limitations")
    md.append("")
    md.append(
        "- Small batch. A single label flipping can move per-method means "
        "by 0.5–1.0 on a 0–4 scale."
    )
    md.append(
        "- Reviewer blinding is enforced at label-validation time but "
        "subtle rubric drift can still leak. Re-randomize the seed when "
        "building a new batch."
    )
    md.append(
        "- Correlation with deterministic metrics is directional only; "
        "weak Spearman does not prove the deterministic metric is wrong."
    )
    md.append(
        "- The `synthetic-reviewer` label file (if present) is for "
        "infrastructure validation only. Real human runs must replace it."
    )

    out_p = args.reports_dir / f"human_review_{args.batch_id}.md"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
