"""
Aggregate reviewer labels for a batch and correlate with deterministic metrics.

Outputs:
    results/human_review_<batch_id>.json
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
    """Compute Spearman rank correlation. Returns None when not computable."""
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
            avg = (i + j) / 2 + 1  # ranks are 1-indexed
            for k in range(i, j + 1):
                ranks[sorted_vals[k][1]] = avg
            i = j + 1
        return ranks
    rx, ry = rank(x), rank(y)
    mean_x = sum(rx) / n; mean_y = sum(ry) / n
    cov = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    var_x = sum((rx[i] - mean_x) ** 2 for i in range(n))
    var_y = sum((ry[i] - mean_y) ** 2 for i in range(n))
    if var_x == 0 or var_y == 0:
        return None
    return round(cov / (var_x ** 0.5 * var_y ** 0.5), 4)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--review-root", type=Path, default=ROOT / "review" / "batches")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--split", default=None,
                    help="Override split (default: taken from batch manifest).")
    args = ap.parse_args(argv)

    batch_dir = args.review_root / args.batch_id
    manifest_p = batch_dir / "manifest.json"
    if not manifest_p.exists():
        print(f"ERROR: {manifest_p} missing.", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    inverse_blind = {v: k for k, v in manifest["blind_method_map"].items()}
    split = args.split or manifest["split"]
    diagnoser = manifest["diagnoser"]

    items = {it["review_item_id"]: it
             for it in load_jsonl(batch_dir / "items.jsonl")}
    if not items:
        print("ERROR: items.jsonl empty.", file=sys.stderr)
        return 1

    reviewer_ids: list[str] = []
    labels_by_item: dict[str, list[dict]] = defaultdict(list)
    for lp in sorted((batch_dir / "labels").glob("*.jsonl")):
        rid = lp.stem.removeprefix("reviewer_")
        reviewer_ids.append(rid)
        for label in load_jsonl(lp):
            labels_by_item[label["review_item_id"]].append(label)

    # Deterministic diagnosis eval for correlation. When the batch's split is
    # "all" (multi-split E9-style batches), pull eval data from every split
    # the manifest declares as merged.
    if split == "all":
        eval_splits = manifest.get("splits_merged") or ["dev", "holdout", "stress"]
    else:
        eval_splits = [split]
    per_case: dict[tuple[str, str], dict] = {}
    for s in eval_splits:
        diag_eval_p = args.results_dir / s / f"eval_diagnosis_{diagnoser}.json"
        if not diag_eval_p.exists():
            continue
        diag_eval = json.loads(diag_eval_p.read_text(encoding="utf-8"))
        # Flatten: (case_id, context_method) -> per-case scores
        for mb in diag_eval.get("methods", []):
            for c in mb.get("cases", []):
                per_case[(c["case_id"], mb["context_method"])] = c

    # Per-method aggregation.
    method_absolute: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    method_pairwise: Counter[str] = Counter()
    method_pair_wins: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    human_vs_det: list[dict] = []

    for rid, labels in labels_by_item.items():
        it = items.get(rid)
        if it is None:
            continue
        for label in labels:
            lt = label["label_type"]
            if lt == "absolute":
                blind = it["blind_method_id"]
                method = inverse_blind.get(blind, blind)
                for axis in ("root_cause_correctness", "evidence_support",
                              "localization_quality", "actionability",
                              "hallucination_severity", "overall_usefulness"):
                    if axis in label:
                        method_absolute[method][axis].append(int(label[axis]))
                # Collect (human, deterministic) pairs for correlation.
                det = per_case.get((it["case_id"], method)) or {}
                human_vs_det.append({
                    "review_item_id": rid,
                    "case_id": it["case_id"],
                    "context_method": method,
                    "reviewer_id": label.get("reviewer_id"),
                    "human_overall":          label.get("overall_usefulness"),
                    "human_root_cause":       label.get("root_cause_correctness"),
                    "human_evidence":         label.get("evidence_support"),
                    "human_localization":     label.get("localization_quality"),
                    "human_actionability":    label.get("actionability"),
                    "human_hallucination":    label.get("hallucination_severity"),
                    "human_abstention_apt":   label.get("abstention_appropriateness"),
                    "det_category_accuracy":  det.get("category_accuracy"),
                    "det_critical_mention":   det.get("critical_signal_mention_recall"),
                    "det_valid_quote":        det.get("valid_evidence_quote_rate"),
                    "det_forbidden_count":    len(det.get("forbidden_claim_violations") or []),
                    "det_score_v1":           det.get("diagnosis_score_v1"),
                    "det_confident_error":    det.get("confident_error"),
                    "det_abstained":          det.get("abstained"),
                    "det_provider_error":     det.get("provider_error"),
                    "det_diagnosis_success":  det.get("diagnosis_success"),
                    "det_root_cause_category": det.get("root_cause_category"),
                })
            elif lt == "pairwise":
                blind_a = it["blind_method_id_a"]
                blind_b = it["blind_method_id_b"]
                method_a = inverse_blind.get(blind_a, blind_a)
                method_b = inverse_blind.get(blind_b, blind_b)
                if label.get("tie") or label.get("both_bad") or label.get("insufficient_information"):
                    method_pair_wins[(method_a, method_b)]["tie"] += 1
                    method_pair_wins[(method_b, method_a)]["tie"] += 1
                    method_pairwise[f"{method_a}|tie"] += 1
                    method_pairwise[f"{method_b}|tie"] += 1
                elif label.get("winner") == "A":
                    method_pair_wins[(method_a, method_b)]["win"] += 1
                    method_pair_wins[(method_b, method_a)]["loss"] += 1
                    method_pairwise[f"{method_a}|win"] += 1
                    method_pairwise[f"{method_b}|loss"] += 1
                elif label.get("winner") == "B":
                    method_pair_wins[(method_b, method_a)]["win"] += 1
                    method_pair_wins[(method_a, method_b)]["loss"] += 1
                    method_pairwise[f"{method_b}|win"] += 1
                    method_pairwise[f"{method_a}|loss"] += 1

    # Per-method summary.
    methods_out: list[dict] = []
    for m in manifest["methods"]:
        axes = method_absolute.get(m, {})
        case_count = len({it["case_id"] for it in items.values()
                           if it.get("label_type") == "absolute"
                           and inverse_blind.get(it.get("blind_method_id")) == m})
        methods_out.append({
            "context_method": m,
            "case_count": case_count,
            "mean_root_cause_correctness":
                round(statistics.mean(axes["root_cause_correctness"]), 3)
                if axes.get("root_cause_correctness") else None,
            "mean_evidence_support":
                round(statistics.mean(axes["evidence_support"]), 3)
                if axes.get("evidence_support") else None,
            "mean_localization_quality":
                round(statistics.mean(axes["localization_quality"]), 3)
                if axes.get("localization_quality") else None,
            "mean_actionability":
                round(statistics.mean(axes["actionability"]), 3)
                if axes.get("actionability") else None,
            "mean_hallucination_severity":
                round(statistics.mean(axes["hallucination_severity"]), 3)
                if axes.get("hallucination_severity") else None,
            "mean_overall_usefulness":
                round(statistics.mean(axes["overall_usefulness"]), 3)
                if axes.get("overall_usefulness") else None,
            "pairwise_wins":   method_pairwise.get(f"{m}|win", 0),
            "pairwise_losses": method_pairwise.get(f"{m}|loss", 0),
            "pairwise_ties":   method_pairwise.get(f"{m}|tie", 0),
        })

    # Correlations with deterministic metrics.
    def pairs(key_h: str, key_d: str) -> tuple[list[float], list[float]]:
        xs: list[float] = []; ys: list[float] = []
        for r in human_vs_det:
            h = r.get(key_h); d = r.get(key_d)
            if h is None or d is None:
                continue
            xs.append(float(h)); ys.append(float(d))
        return xs, ys

    correlations: dict[str, float | None] = {}
    for label, (kh, kd) in {
        "overall_vs_score_v1":             ("human_overall",        "det_score_v1"),
        "root_cause_vs_category_accuracy": ("human_root_cause",     "det_category_accuracy"),
        "evidence_vs_critical_mention":    ("human_evidence",       "det_critical_mention"),
        "evidence_vs_valid_quote":         ("human_evidence",       "det_valid_quote"),
        "hallucination_vs_forbidden":      ("human_hallucination",  "det_forbidden_count"),
    }.items():
        x, y = pairs(kh, kd)
        correlations[label] = spearman(x, y)

    # Largest disagreements: human_overall vs det_score_v1, Top 5.
    scored = [r for r in human_vs_det
               if r.get("human_overall") is not None and r.get("det_score_v1") is not None]
    for r in scored:
        r["disagreement"] = round(
            abs(float(r["human_overall"]) / 4.0 - float(r["det_score_v1"])), 3)
    top = sorted(scored, key=lambda r: r["disagreement"], reverse=True)[:5]
    top_out = [{
        "review_item_id":   t["review_item_id"],
        "case_id":          t["case_id"],
        "context_method":   t["context_method"],
        "human_overall":    t["human_overall"],
        "det_score_v1":     t["det_score_v1"],
        "disagreement":     t["disagreement"],
    } for t in top]

    # ---- E2.5 calibration blocks ----

    # Confident-error calibration: among rows the diagnoser was confidently wrong,
    # do humans flag hallucination / mark unhelpful?
    ce_total = ce_human_halluc_severe = ce_human_overall_low = ce_either = 0
    ce_rows = []
    for r in human_vs_det:
        if r.get("det_confident_error") is True:
            ce_total += 1
            halluc_severe = (r.get("human_hallucination") or 0) >= 3
            overall_low   = (r.get("human_overall") if r.get("human_overall") is not None else 4) <= 1
            ce_human_halluc_severe += int(halluc_severe)
            ce_human_overall_low   += int(overall_low)
            ce_either += int(halluc_severe or overall_low)
            ce_rows.append({
                "review_item_id":      r["review_item_id"],
                "case_id":             r["case_id"],
                "context_method":      r["context_method"],
                "human_hallucination": r.get("human_hallucination"),
                "human_overall":       r.get("human_overall"),
                "human_flagged":       (halluc_severe or overall_low),
            })
    confident_error_calibration = {
        "n_confident_errors_with_human_label": ce_total,
        "human_flagged_severe_hallucination":  ce_human_halluc_severe,
        "human_flagged_unhelpful":             ce_human_overall_low,
        "human_flagged_either":                ce_either,
        "human_flag_rate":                     round(ce_either / ce_total, 3) if ce_total else None,
        "rows": ce_rows,
    }

    # Pairwise vs. auto-score consistency.
    # For each pairwise label with a clear winner, check whether auto-score agrees.
    pair_consistency: dict[str, dict] = {}
    pair_total_match = pair_total_mismatch = pair_total_auto_tie = 0
    for rid, labels in labels_by_item.items():
        it = items.get(rid)
        if it is None or it.get("label_type") != "pairwise":
            continue
        method_a = inverse_blind.get(it["blind_method_id_a"])
        method_b = inverse_blind.get(it["blind_method_id_b"])
        det_a = (per_case.get((it["case_id"], method_a)) or {}).get("diagnosis_score_v1")
        det_b = (per_case.get((it["case_id"], method_b)) or {}).get("diagnosis_score_v1")
        for label in labels:
            human_winner = None
            if label.get("winner") == "A":
                human_winner = method_a
            elif label.get("winner") == "B":
                human_winner = method_b
            if human_winner is None or det_a is None or det_b is None:
                continue
            auto_winner = method_a if det_a > det_b else (method_b if det_b > det_a else None)
            pair_key = "|".join(sorted([method_a, method_b]))
            slot = pair_consistency.setdefault(pair_key, {"match": 0, "mismatch": 0, "auto_tie": 0})
            if auto_winner is None:
                slot["auto_tie"] += 1
                pair_total_auto_tie += 1
            elif auto_winner == human_winner:
                slot["match"] += 1
                pair_total_match += 1
            else:
                slot["mismatch"] += 1
                pair_total_mismatch += 1
    pairwise_vs_auto = {
        "by_pair": pair_consistency,
        "totals": {
            "match":    pair_total_match,
            "mismatch": pair_total_mismatch,
            "auto_tie": pair_total_auto_tie,
            "agreement_rate": (
                round(pair_total_match / (pair_total_match + pair_total_mismatch), 3)
                if (pair_total_match + pair_total_mismatch) else None
            ),
        },
    }

    # Method-level Spearman: mean(human_overall) vs mean(det_score_v1) across methods.
    method_human_means: dict[str, float] = {}
    method_det_means: dict[str, list[float]] = defaultdict(list)
    for r in human_vs_det:
        m = r.get("context_method")
        if r.get("det_score_v1") is not None:
            method_det_means[m].append(float(r["det_score_v1"]))
    for m in manifest["methods"]:
        axes = method_absolute.get(m, {})
        if axes.get("overall_usefulness"):
            method_human_means[m] = statistics.mean(axes["overall_usefulness"])
    paired_methods = [m for m in manifest["methods"]
                      if m in method_human_means and method_det_means.get(m)]
    method_rank_correlation = None
    if len(paired_methods) >= 3:
        x = [method_human_means[m] for m in paired_methods]
        y = [statistics.mean(method_det_means[m]) for m in paired_methods]
        method_rank_correlation = spearman(x, y)

    # Disagreement taxonomy: bucket each top-N disagreement.
    def _bucket(r: dict) -> str:
        ho = r.get("human_overall")
        sv1 = r.get("det_score_v1")
        cat = r.get("det_category_accuracy")
        crit = r.get("det_critical_mention") or 0.0
        vq = r.get("det_valid_quote") or 0.0
        ce = r.get("det_confident_error")
        ab = r.get("det_abstained")
        hh = r.get("human_hallucination") or 0
        haa = r.get("human_abstention_apt")
        # Precedence: most specific buckets first.
        if ab is True and haa == "correct_abstention" and (sv1 or 0) < 0.4:
            return "useful_abstention_under_rewarded"
        if ce is True and hh <= 1:
            return "confident_wrong_unflagged"
        if ho is not None and ho >= 3 and (cat == 0):
            return "wrong_category_but_useful"
        if ho is not None and ho <= 1 and (cat == 1):
            return "correct_category_but_unhelpful"
        if ho is not None and ho >= 3 and crit < 0.5 and (sv1 or 0) < 0.4:
            return "paraphrase_under_counted"
        if ho is not None and ho <= 1 and vq >= 0.8 and crit >= 0.5:
            return "evidence_copied_without_understanding"
        if ho is not None and ho <= 2 and vq < 0.5 and (sv1 or 0) >= 0.5:
            return "unsupported_evidence_quote"
        return "other"
    # Re-find original disagreement rows so we can run _bucket on full row data.
    full_rows_by_rid = {r["review_item_id"]: r for r in human_vs_det}
    disagreement_taxonomy = []
    for t in top_out:
        full = full_rows_by_rid.get(t["review_item_id"], {})
        disagreement_taxonomy.append({
            **t,
            "bucket": _bucket(full),
        })
    bucket_counts: Counter = Counter(d["bucket"] for d in disagreement_taxonomy)

    # Reviewer agreement if ≥2 reviewers.
    reviewer_agreement: dict = {"reviewer_count": len(reviewer_ids), "raw_agreement": None}
    if len(reviewer_ids) >= 2:
        # For pairwise items where both reviewers labeled the same item, record
        # raw agreement on `winner`/`tie`/etc.
        agree = total = 0
        for rid, labels in labels_by_item.items():
            if len(labels) < 2: continue
            if labels[0]["label_type"] != "pairwise": continue
            total += 1
            v1 = (labels[0].get("winner"), labels[0].get("tie"), labels[0].get("both_bad"))
            v2 = (labels[1].get("winner"), labels[1].get("tie"), labels[1].get("both_bad"))
            if v1 == v2:
                agree += 1
        if total:
            reviewer_agreement["raw_agreement"] = round(agree / total, 3)

    summary = {
        "batch_id":     args.batch_id,
        "protocol_id":  manifest.get("protocol_id"),
        "split":        split,
        "diagnoser":    diagnoser,
        "reviewer_ids": reviewer_ids,
        "items": {
            "total":    len(items),
            "absolute": sum(1 for it in items.values() if it["label_type"] == "absolute"),
            "pairwise": sum(1 for it in items.values() if it["label_type"] == "pairwise"),
        },
        "methods": methods_out,
        "correlation_with_deterministic": correlations,
        "method_rank_correlation_overall_vs_score_v1": method_rank_correlation,
        "confident_error_calibration": confident_error_calibration,
        "pairwise_vs_auto_consistency": pairwise_vs_auto,
        "largest_disagreements": disagreement_taxonomy,
        "disagreement_bucket_counts": dict(bucket_counts),
        "reviewer_agreement": reviewer_agreement,
        "human_vs_det_rows": human_vs_det,
    }
    out_p = args.results_dir / f"human_review_{args.batch_id}.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"Wrote {out_p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
