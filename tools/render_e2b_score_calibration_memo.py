"""
Render E2b score-calibration memo (sv1 vs sv1.1) against the E2 expert-model
review labels.

This tool does NOT rerun any model. It re-reads:

    review/batches/<batch_id>/items.jsonl
    review/batches/<batch_id>/labels/reviewer_*.jsonl
    results/<batch_split>/eval_diagnosis_<diagnoser>.json   (already contains
                                                             sv1 + sv1.1 fields
                                                             after the v1.1
                                                             rescore)

and computes every E2 calibration block under both score versions, then
diffs them in `reports/e2b_score_calibration_v1_1.md`.

Verdict logic:
    ACCEPT_V1_1   - overall_vs_score Spearman improves AND
                     pairwise human/auto agreement does not regress AND
                     method-rank Spearman does not regress
    KEEP_V1_PRIMARY - sv1.1 ties or only marginally improves
    REJECT_V1_1   - sv1.1 regresses on any of the three primary axes
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def spearman(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3 or len(y) != n:
        return None
    def rank(vals: list[float]) -> list[float]:
        sorted_vals = sorted((v, i) for i, v in enumerate(vals))
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and sorted_vals[j + 1][0] == sorted_vals[i][0]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[sorted_vals[k][1]] = avg
            i = j + 1
        return ranks
    rx, ry = rank(x), rank(y)
    mx = sum(rx) / n; my = sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    vx = sum((rx[i] - mx) ** 2 for i in range(n))
    vy = sum((ry[i] - my) ** 2 for i in range(n))
    if vx == 0 or vy == 0:
        return None
    return round(cov / (vx ** 0.5 * vy ** 0.5), 4)


def fmt(v, prec: int = 3) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{prec}f}"
    return str(v)


def fmt_delta(a, b) -> str:
    if a is None or b is None:
        return "n/a"
    d = b - a
    return f"{'+' if d >= 0 else ''}{d:.3f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--review-root", type=Path, default=ROOT / "review" / "batches")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--out-name", default="e2b_score_calibration_v1_1.md")
    ap.add_argument("--results-out-name",
                    default="e2b_score_calibration_v1_1.json")
    args = ap.parse_args(argv)

    batch_dir = args.review_root / args.batch_id
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    inv_blind = {v: k for k, v in manifest["blind_method_map"].items()}
    split = manifest["split"]
    diagnoser = manifest["diagnoser"]

    items = {it["review_item_id"]: it
             for it in load_jsonl(batch_dir / "items.jsonl")}
    labels_by_item: dict[str, list[dict]] = defaultdict(list)
    reviewer_ids: list[str] = []
    for lp in sorted((batch_dir / "labels").glob("*.jsonl")):
        rid = lp.stem.removeprefix("reviewer_")
        reviewer_ids.append(rid)
        for label in load_jsonl(lp):
            labels_by_item[label["review_item_id"]].append(label)

    diag_eval = json.loads(
        (args.results_dir / split / f"eval_diagnosis_{diagnoser}.json").read_text(encoding="utf-8")
    )
    per_case: dict[tuple[str, str], dict] = {}
    for mb in diag_eval.get("methods", []):
        for c in mb.get("cases", []):
            per_case[(c["case_id"], mb["context_method"])] = c

    # Build (human, deterministic) rows under both score versions.
    abs_rows: list[dict] = []
    for rid, labels in labels_by_item.items():
        it = items.get(rid)
        if it is None or it.get("label_type") != "absolute":
            continue
        method = inv_blind.get(it["blind_method_id"])
        det = per_case.get((it["case_id"], method)) or {}
        for label in labels:
            abs_rows.append({
                "review_item_id": rid,
                "case_id": it["case_id"],
                "context_method": method,
                "human_overall":     label.get("overall_usefulness"),
                "human_root_cause":  label.get("root_cause_correctness"),
                "human_evidence":    label.get("evidence_support"),
                "human_halluc":      label.get("hallucination_severity"),
                "det_cat_v1":        det.get("category_accuracy"),
                "det_cms_v1_1":      det.get("category_match_score_v1_1"),
                "det_crit":          det.get("critical_signal_mention_recall"),
                "det_must":          det.get("must_mention_coverage"),
                "det_valid_quote":   det.get("valid_evidence_quote_rate"),
                "det_forbidden":     len(det.get("forbidden_claim_violations") or []),
                "det_conf_err":      det.get("confident_error"),
                "det_conf_err_v1_1": det.get("confident_error_v1_1"),
                "det_score_v1":      det.get("diagnosis_score_v1"),
                "det_score_v1_1":    det.get("diagnosis_score_v1_1"),
            })

    def pairs(key_h: str, key_d: str) -> tuple[list[float], list[float]]:
        xs: list[float] = []; ys: list[float] = []
        for r in abs_rows:
            h = r.get(key_h); d = r.get(key_d)
            if h is None or d is None:
                continue
            xs.append(float(h)); ys.append(float(d))
        return xs, ys

    # Correlations under both score versions.
    corr_v1 = {
        "overall_vs_score":           spearman(*pairs("human_overall", "det_score_v1")),
        "root_cause_vs_category":     spearman(*pairs("human_root_cause", "det_cat_v1")),
        "evidence_vs_critical":       spearman(*pairs("human_evidence", "det_crit")),
    }
    corr_v1_1 = {
        "overall_vs_score":           spearman(*pairs("human_overall", "det_score_v1_1")),
        "root_cause_vs_category":     spearman(*pairs("human_root_cause", "det_cms_v1_1")),
        "evidence_vs_critical":       spearman(*pairs("human_evidence", "det_crit")),
    }

    # Pairwise agreement under both.
    pair_match_v1 = pair_mismatch_v1 = pair_tie_v1 = 0
    pair_match_v1_1 = pair_mismatch_v1_1 = pair_tie_v1_1 = 0
    pairwise_by_pair_v1: dict[str, dict] = defaultdict(lambda: {"match": 0, "mismatch": 0, "auto_tie": 0})
    pairwise_by_pair_v1_1: dict[str, dict] = defaultdict(lambda: {"match": 0, "mismatch": 0, "auto_tie": 0})
    for rid, labels in labels_by_item.items():
        it = items.get(rid)
        if it is None or it.get("label_type") != "pairwise":
            continue
        ma = inv_blind.get(it["blind_method_id_a"])
        mb = inv_blind.get(it["blind_method_id_b"])
        det_a = per_case.get((it["case_id"], ma)) or {}
        det_b = per_case.get((it["case_id"], mb)) or {}
        det_a_v1 = det_a.get("diagnosis_score_v1")
        det_b_v1 = det_b.get("diagnosis_score_v1")
        det_a_v1_1 = det_a.get("diagnosis_score_v1_1")
        det_b_v1_1 = det_b.get("diagnosis_score_v1_1")
        for label in labels:
            human_winner = None
            if label.get("winner") == "A":
                human_winner = ma
            elif label.get("winner") == "B":
                human_winner = mb
            if human_winner is None:
                continue
            pair_key = "|".join(sorted([ma, mb]))
            for (a_score, b_score, by_pair, totals_inc) in [
                (det_a_v1, det_b_v1, pairwise_by_pair_v1, "v1"),
                (det_a_v1_1, det_b_v1_1, pairwise_by_pair_v1_1, "v1_1"),
            ]:
                if a_score is None or b_score is None:
                    continue
                slot = by_pair[pair_key]
                if a_score > b_score:
                    auto_w = ma
                elif b_score > a_score:
                    auto_w = mb
                else:
                    auto_w = None
                if auto_w is None:
                    slot["auto_tie"] += 1
                    if totals_inc == "v1":     pair_tie_v1 += 1
                    else:                       pair_tie_v1_1 += 1
                elif auto_w == human_winner:
                    slot["match"] += 1
                    if totals_inc == "v1":     pair_match_v1 += 1
                    else:                       pair_match_v1_1 += 1
                else:
                    slot["mismatch"] += 1
                    if totals_inc == "v1":     pair_mismatch_v1 += 1
                    else:                       pair_mismatch_v1_1 += 1

    pair_agree_v1 = (
        round(pair_match_v1 / (pair_match_v1 + pair_mismatch_v1), 3)
        if (pair_match_v1 + pair_mismatch_v1) else None
    )
    pair_agree_v1_1 = (
        round(pair_match_v1_1 / (pair_match_v1_1 + pair_mismatch_v1_1), 3)
        if (pair_match_v1_1 + pair_mismatch_v1_1) else None
    )

    # Method-level rank correlation under both.
    methods = manifest["methods"]
    method_human_overall: dict[str, float] = {}
    for m in methods:
        vals = [r["human_overall"] for r in abs_rows
                if r["context_method"] == m and r.get("human_overall") is not None]
        if vals:
            method_human_overall[m] = statistics.mean(vals)
    method_det_v1: dict[str, float] = {}
    method_det_v1_1: dict[str, float] = {}
    for mb in diag_eval.get("methods", []):
        if mb["context_method"] in methods:
            method_det_v1[mb["context_method"]] = mb.get("diagnosis_score_v1")
            method_det_v1_1[mb["context_method"]] = mb.get("diagnosis_score_v1_1")
    paired = [m for m in methods
              if m in method_human_overall and method_det_v1.get(m) is not None]
    method_rank_v1 = method_rank_v1_1 = None
    if len(paired) >= 3:
        x = [method_human_overall[m] for m in paired]
        y_v1 = [method_det_v1[m] for m in paired]
        y_v1_1 = [method_det_v1_1[m] for m in paired]
        method_rank_v1 = spearman(x, y_v1)
        method_rank_v1_1 = spearman(x, y_v1_1)

    # Confident-error before/after.
    ce_total_v1 = sum(1 for r in abs_rows if r.get("det_conf_err"))
    ce_total_v1_1 = sum(1 for r in abs_rows if r.get("det_conf_err_v1_1"))
    ce_human_flag_v1 = sum(
        1 for r in abs_rows if r.get("det_conf_err")
        and ((r.get("human_halluc") or 0) >= 3 or (r.get("human_overall") or 4) <= 1)
    )
    ce_human_flag_v1_1 = sum(
        1 for r in abs_rows if r.get("det_conf_err_v1_1")
        and ((r.get("human_halluc") or 0) >= 3 or (r.get("human_overall") or 4) <= 1)
    )

    # Top disagreements before/after.
    def top_disagreements(score_key: str) -> list[dict]:
        scored = [r for r in abs_rows
                  if r.get("human_overall") is not None and r.get(score_key) is not None]
        for r in scored:
            r["_gap"] = abs(float(r["human_overall"]) / 4.0 - float(r[score_key]))
        top = sorted(scored, key=lambda r: r["_gap"], reverse=True)[:5]
        out = [{
            "case_id":         t["case_id"],
            "context_method":  t["context_method"],
            "human_overall":   t["human_overall"],
            "score":           round(float(t[score_key]), 3),
            "gap":             round(t["_gap"], 3),
        } for t in top]
        for r in scored:
            r.pop("_gap", None)
        return out

    top_v1 = top_disagreements("det_score_v1")
    top_v1_1 = top_disagreements("det_score_v1_1")

    # Method rankings (per-split) for the 4 reviewed methods.
    split_method_ranks = {}
    for mb in diag_eval.get("methods", []):
        if mb["context_method"] in methods:
            split_method_ranks[mb["context_method"]] = {
                "sv1": mb.get("diagnosis_score_v1"),
                "sv1_1": mb.get("diagnosis_score_v1_1"),
                "category_accuracy": mb.get("macro_category_accuracy"),
                "category_match_score_v1_1": mb.get("macro_category_match_score_v1_1"),
                "confident_error_rate_v1": mb.get("confident_error_rate"),
                "confident_error_rate_v1_1": mb.get("confident_error_rate_v1_1"),
            }

    # Verdict logic.
    overall_v1 = corr_v1["overall_vs_score"]
    overall_v1_1 = corr_v1_1["overall_vs_score"]
    rationale: list[str] = []
    rationale.append(f"overall_vs_score Spearman: v1={fmt(overall_v1)} -> v1.1={fmt(overall_v1_1)}")
    rationale.append(f"pairwise agreement: v1={fmt(pair_agree_v1)} -> v1.1={fmt(pair_agree_v1_1)}")
    rationale.append(f"method-rank Spearman: v1={fmt(method_rank_v1)} -> v1.1={fmt(method_rank_v1_1)}")
    rationale.append(f"confident-error count: v1={ce_total_v1} -> v1.1={ce_total_v1_1}")
    rationale.append(
        f"confident-error confirmed by reviewer (severe halluc OR overall<=1): "
        f"v1={ce_human_flag_v1}/{ce_total_v1} -> v1.1={ce_human_flag_v1_1}/{ce_total_v1_1}"
    )

    def _improves(a, b, eps: float = 0.0) -> bool:
        if a is None or b is None:
            return False
        return b > a + eps

    def _regresses(a, b, eps: float = 0.02) -> bool:
        if a is None or b is None:
            return False
        return a > b + eps

    if overall_v1 is None or overall_v1_1 is None:
        verdict = "INSUFFICIENT_DATA"
    elif _regresses(overall_v1, overall_v1_1):
        verdict = "REJECT_V1_1"
    elif (
        _regresses(pair_agree_v1, pair_agree_v1_1)
        or _regresses(method_rank_v1, method_rank_v1_1)
    ):
        verdict = "REJECT_V1_1"
    elif _improves(overall_v1, overall_v1_1, eps=0.02):
        verdict = "ACCEPT_V1_1"
    else:
        verdict = "KEEP_V1_PRIMARY"

    # ------- Render markdown -------
    lines: list[str] = []
    lines.append("# E2b Score Calibration v1.1")
    lines.append("")
    lines.append(
        "> **Reviewer disclosure**: the 50 review labels backing this memo were "
        "produced by `claude-opus-4-7-expert` acting as an LLM-as-judge expert "
        "reviewer, not by an unaffiliated human. This is **expert-model "
        "review**, not human review. Public summaries should refer to it as "
        "such until human reviewers cross-check the labels."
    )
    lines.append("")
    lines.append(f"- **Batch:** `{args.batch_id}`")
    lines.append(f"- **Protocol:** `{manifest.get('protocol_id')}`")
    lines.append(f"- **Split:** `{split}`")
    lines.append(f"- **Diagnoser:** `{diagnoser}`")
    lines.append(f"- **Methods reviewed:** {', '.join(f'`{m}`' for m in methods)}")
    lines.append(f"- **Reviewer:** `{', '.join(reviewer_ids)}` (expert-model)")
    lines.append("")

    # 1. Motivation
    lines.append("## 1. Motivation")
    lines.append("")
    lines.append(
        "E2 closed with `overall_usefulness vs sv1` Spearman = 0.637 — just over "
        "the PASS threshold. Three of the top-5 disagreements landed in the "
        "`confident_wrong_unflagged` bucket: diagnoses where the reviewer rated "
        "the answer 3 or 4 out of 4, but the auto evaluator marked them as "
        "confident errors purely because `category_accuracy = 0`. That is a "
        "structural scoring bug — semantically correct, operationally useful "
        "diagnoses were being penalized twice (zero category credit + the "
        "confident-error penalty)."
    )
    lines.append("")
    lines.append("E2b is a zero-cost calibration layer that:")
    lines.append("")
    lines.append(
        "1. Replaces binary `category_accuracy` with `category_match_score` "
        "(1.0 / 0.5 / 0.0) using an explicit compatibility table."
    )
    lines.append(
        "2. Rewrites `confident_error` so that wrong category alone no longer "
        "triggers it — the diagnosis must also miss critical evidence or "
        "violate forbidden-claim rules."
    )
    lines.append(
        "3. Adds `diagnosis_score_v1_1` alongside `diagnosis_score_v1`. v1 is "
        "preserved unchanged."
    )
    lines.append("")
    lines.append("It does not change models, prompts, methods, cases, ground truth, or human labels.")
    lines.append("")

    # 2. Changes
    lines.append("## 2. What changed and what did not")
    lines.append("")
    lines.append("| Field | v1 | v1.1 |")
    lines.append("|---|---|---|")
    lines.append("| Category match | `category_accuracy` (binary 0/1) | `category_match_score_v1_1` (0 / 0.5 / 1) using `configs/evaluation/category_compatibility_v1_1.json` |")
    lines.append(
        "| Confident-error trigger | `confidence >= 0.7 AND (category_accuracy=0 OR forbidden>0)` "
        "| `confidence >= 0.7 AND (forbidden>0 OR (category_match=0 AND critical<0.5 AND must_mention<0.5))` |"
    )
    lines.append("| Composite | `diagnosis_score_v1` (preserved) | `diagnosis_score_v1_1` (added) |")
    lines.append("")
    lines.append("Unchanged: diagnosis outputs, model, prompt, cases, methods, ground truth, expert-model labels.")
    lines.append("")

    # 3. Correlation comparison
    lines.append("## 3. Correlation comparison")
    lines.append("")
    lines.append("| Metric | v1 | v1.1 | Δ |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| overall_usefulness Spearman | {fmt(overall_v1)} | {fmt(overall_v1_1)} | {fmt_delta(overall_v1, overall_v1_1)} |"
    )
    lines.append(
        f"| pairwise human/auto agreement | {fmt(pair_agree_v1)} | {fmt(pair_agree_v1_1)} | {fmt_delta(pair_agree_v1, pair_agree_v1_1)} |"
    )
    lines.append(
        f"| method-rank Spearman | {fmt(method_rank_v1)} | {fmt(method_rank_v1_1)} | {fmt_delta(method_rank_v1, method_rank_v1_1)} |"
    )
    lines.append(
        f"| root_cause vs category | {fmt(corr_v1['root_cause_vs_category'])} | {fmt(corr_v1_1['root_cause_vs_category'])} | "
        f"{fmt_delta(corr_v1['root_cause_vs_category'], corr_v1_1['root_cause_vs_category'])} |"
    )
    lines.append(
        f"| evidence vs critical signal | {fmt(corr_v1['evidence_vs_critical'])} | {fmt(corr_v1_1['evidence_vs_critical'])} | "
        f"{fmt_delta(corr_v1['evidence_vs_critical'], corr_v1_1['evidence_vs_critical'])} |"
    )
    lines.append("")

    # 4. Confident-error comparison
    lines.append("## 4. Confident-error comparison")
    lines.append("")
    lines.append("| Stat | v1 | v1.1 |")
    lines.append("|---|---:|---:|")
    lines.append(f"| confident_error rows (in reviewed set) | {ce_total_v1} | {ce_total_v1_1} |")
    lines.append(
        f"| confirmed by reviewer (severe halluc OR overall<=1) | "
        f"{ce_human_flag_v1}/{ce_total_v1} | {ce_human_flag_v1_1}/{ce_total_v1_1} |"
    )
    lines.append(
        f"| false-positive rate | "
        f"{(1 - ce_human_flag_v1/ce_total_v1):.2f}" if ce_total_v1 else "n/a"
    )
    # Replace last line with proper formatting that handles n/a
    lines.pop()
    fp_v1 = f"{(1 - ce_human_flag_v1/ce_total_v1):.2f}" if ce_total_v1 else "n/a"
    fp_v1_1 = f"{(1 - ce_human_flag_v1_1/ce_total_v1_1):.2f}" if ce_total_v1_1 else "n/a"
    lines.append(f"| false-positive rate | {fp_v1} | {fp_v1_1} |")
    lines.append("")
    lines.append("(Lower confident-error count + lower false-positive rate = better calibration.)")
    lines.append("")

    # 5. Method ranking comparison
    lines.append("## 5. Method ranking on the reviewed split")
    lines.append("")
    lines.append("| Method | mean human overall | sv1 | sv1.1 | Δ score | cat_v1 | cms_v1.1 | confErr_v1 | confErr_v1.1 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in methods:
        s = split_method_ranks.get(m, {})
        ho = method_human_overall.get(m)
        sv1 = s.get("sv1"); sv1_1 = s.get("sv1_1")
        lines.append(
            f"| `{m}` | {fmt(ho)} | {fmt(sv1)} | {fmt(sv1_1)} | {fmt_delta(sv1, sv1_1)} "
            f"| {fmt(s.get('category_accuracy'))} | {fmt(s.get('category_match_score_v1_1'))} "
            f"| {fmt(s.get('confident_error_rate_v1'))} | {fmt(s.get('confident_error_rate_v1_1'))} |"
        )
    lines.append("")

    # 6. Top disagreements before/after
    lines.append("## 6. Top disagreements before vs after")
    lines.append("")
    lines.append("### Top-5 under sv1")
    lines.append("")
    lines.append("| Case | Method | human_overall | sv1 | gap |")
    lines.append("|---|---|---:|---:|---:|")
    for d in top_v1:
        lines.append(
            f"| `{d['case_id']}` | `{d['context_method']}` "
            f"| {d['human_overall']} | {fmt(d['score'])} | {fmt(d['gap'])} |"
        )
    lines.append("")
    lines.append("### Top-5 under sv1.1")
    lines.append("")
    lines.append("| Case | Method | human_overall | sv1.1 | gap |")
    lines.append("|---|---|---:|---:|---:|")
    for d in top_v1_1:
        lines.append(
            f"| `{d['case_id']}` | `{d['context_method']}` "
            f"| {d['human_overall']} | {fmt(d['score'])} | {fmt(d['gap'])} |"
        )
    lines.append("")
    avg_gap_v1 = sum(d["gap"] for d in top_v1) / len(top_v1) if top_v1 else None
    avg_gap_v1_1 = sum(d["gap"] for d in top_v1_1) / len(top_v1_1) if top_v1_1 else None
    lines.append(
        f"Average gap among top-5: v1={fmt(avg_gap_v1)} -> v1.1={fmt(avg_gap_v1_1)} "
        f"({fmt_delta(avg_gap_v1, avg_gap_v1_1)})"
    )
    lines.append("")

    # 7. Verdict
    lines.append("## 7. Verdict")
    lines.append("")
    lines.append(f"**`{verdict}`**")
    lines.append("")
    lines.append("Rationale:")
    for r in rationale:
        lines.append(f"- {r}")
    lines.append("")

    if verdict == "ACCEPT_V1_1":
        lines.append(
            "Adopt `diagnosis_score_v1_1` as the primary score for E3 and "
            "downstream experiments. Continue to emit `diagnosis_score_v1` "
            "alongside for historical comparison. Freeze the calibration table "
            "as `cilogbench-v1.2`."
        )
    elif verdict == "KEEP_V1_PRIMARY":
        lines.append(
            "sv1.1 does not materially improve correlation with the expert-"
            "model reviewer. Keep sv1 as the primary score for now, but "
            "continue to emit sv1.1 as a secondary signal so future human-"
            "labeled batches can re-evaluate the calibration."
        )
    elif verdict == "REJECT_V1_1":
        lines.append(
            "sv1.1 regressed against expert-model labels. Revert to sv1 as "
            "primary and revisit the compatibility table or the confident-"
            "error trigger before any further calibration changes."
        )
    elif verdict == "INSUFFICIENT_DATA":
        lines.append(
            "Not enough labeled rows to compute the primary correlation. "
            "Re-run after more reviewers submit labels."
        )
    lines.append("")

    # 8. What this memo does NOT certify
    lines.append("## 8. Caveats")
    lines.append("")
    lines.append(
        "- 50 expert-model labels on 5 holdout cases is a small sample. The "
        "verdict reflects the calibration direction, not statistical certainty."
    )
    lines.append(
        "- The reviewer is `claude-opus-4-7-expert` (LLM-as-judge), not an "
        "unaffiliated human. Real human review remains the canonical "
        "calibration."
    )
    lines.append(
        "- The compatibility table is intentionally narrow. Adding new partial "
        "pairs without justification will erode score discrimination."
    )
    lines.append("")

    # 9. How to regenerate
    lines.append("## 9. Pipeline")
    lines.append("")
    lines.append("```")
    lines.append("# Re-score all splits with v1.1 fields:")
    lines.append("python3 tools/evaluate_diagnosis.py --split dev --diagnoser real-debugger-v1")
    lines.append("python3 tools/evaluate_diagnosis.py --split holdout --diagnoser real-debugger-v1")
    lines.append("python3 tools/evaluate_diagnosis.py --split stress --diagnoser real-debugger-v1")
    lines.append("")
    lines.append("# Render this memo:")
    lines.append(f"python3 tools/render_e2b_score_calibration_memo.py --batch-id {args.batch_id}")
    lines.append("```")
    lines.append("")

    md = "\n".join(lines) + "\n"
    out_md = args.reports_dir / args.out_name
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")

    # Also write the raw calibration JSON for downstream tools.
    summary = {
        "batch_id": args.batch_id,
        "protocol_id": manifest.get("protocol_id"),
        "split": split,
        "diagnoser": diagnoser,
        "reviewer_ids": reviewer_ids,
        "n_absolute_rows": len(abs_rows),
        "correlations_v1": corr_v1,
        "correlations_v1_1": corr_v1_1,
        "pairwise_agreement_v1":   pair_agree_v1,
        "pairwise_agreement_v1_1": pair_agree_v1_1,
        "pairwise_by_pair_v1":     dict(pairwise_by_pair_v1),
        "pairwise_by_pair_v1_1":   dict(pairwise_by_pair_v1_1),
        "method_rank_correlation_v1":   method_rank_v1,
        "method_rank_correlation_v1_1": method_rank_v1_1,
        "confident_error": {
            "v1":   {"total": ce_total_v1,   "human_flag": ce_human_flag_v1},
            "v1_1": {"total": ce_total_v1_1, "human_flag": ce_human_flag_v1_1},
        },
        "method_rankings": split_method_ranks,
        "top_disagreements_v1":   top_v1,
        "top_disagreements_v1_1": top_v1_1,
        "verdict": verdict,
    }
    out_json = args.results_dir / args.results_out_name
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"Wrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
