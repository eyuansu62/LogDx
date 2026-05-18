"""Render cost-quality Pareto plot for LogDx-CI v1.0.

x-axis: total tokens per case (reducer_in + reducer_out + context + diagnosis)
        on log scale because the range is 800 -> 432,000
y-axis: diagnosis_score_v1_1 (case-count-weighted macro across the 3
        debugger families, taken from the published leaderboard)

Output: docs/figures/cost_quality_pareto.png
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
COST_PATH = Path("/tmp/logdx_cost_metrics.json")

# Mirrors the published leaderboard so this file is self-contained.
SCORE_BY_METHOD = {
    "hybrid-grep-120k-rtk-tail": 0.670,
    "hybrid-grep-120k-tail":     0.666,
    "grep":                      0.639,
    "tail-200":                  0.614,
    "hybrid-grep-4k-rtk-err-cat":0.573,
    "rtk-err-cat":               0.470,
    "raw":                       0.353,
    "rtk-read":                  0.349,
    "llm-summary-v1-mock":       0.328,
    "rtk-log":                   0.249,
}

CONFIDENT_ERROR = {
    "hybrid-grep-120k-rtk-tail": 0.000,
    "hybrid-grep-120k-tail":     0.010,
    "grep":                      0.000,
    "tail-200":                  0.019,
    "hybrid-grep-4k-rtk-err-cat":0.029,
    "rtk-err-cat":               0.029,
    "raw":                       0.000,
    "rtk-read":                  0.010,
    "llm-summary-v1-mock":       0.133,
    "rtk-log":                   0.133,
}


def main():
    if not COST_PATH.exists():
        raise SystemExit(
            f"missing {COST_PATH}; run tools/aggregate_cost_metrics.py first"
        )
    cost = json.load(COST_PATH.open())

    pts = []
    for label, score in SCORE_BY_METHOD.items():
        c = cost.get(label, {}).get("Overall")
        if not c:
            continue
        pts.append({
            "label": label,
            "tokens": c["total_tokens"],
            "score": score,
            "ce": CONFIDENT_ERROR.get(label, 0.0),
        })

    # Pareto frontier: a point is Pareto-optimal if no other point has
    # both lower tokens AND higher score.
    pareto = []
    for p in pts:
        dominated = any(
            (q["tokens"] <= p["tokens"] and q["score"] > p["score"]) or
            (q["tokens"] < p["tokens"] and q["score"] >= p["score"])
            for q in pts if q is not p
        )
        if not dominated:
            pareto.append(p)
    pareto.sort(key=lambda p: p["tokens"])

    fig, ax = plt.subplots(figsize=(13, 8), dpi=100)
    fig.patch.set_facecolor("white")

    # Color/shape by family.
    def style(label):
        if label.startswith("hybrid"):
            return dict(color="#2A9D8F", marker="*", s=400, zorder=4)
        if label.startswith("rtk"):
            return dict(color="#E76F51", marker="o", s=200, zorder=3)
        if label.startswith("llm-summary"):
            return dict(color="#9D4EDD", marker="s", s=220, zorder=3)
        if label == "raw":
            return dict(color="#888", marker="x", s=180, zorder=2)
        return dict(color="#5B8DEF", marker="D", s=200, zorder=3)

    # Manual label placement keyed by method label.
    LABEL_POS = {
        "rtk-log":                   ("right", 0.85, +0.024),
        "tail-200":                  ("left",  1.20, +0.018),
        "hybrid-grep-120k-tail":     ("right", 0.85, -0.034),
        "hybrid-grep-120k-rtk-tail": ("right", 0.85, +0.030),
        "hybrid-grep-4k-rtk-err-cat":("right", 0.85, -0.026),
        "rtk-err-cat":               ("left",  1.20, -0.014),
        "raw":                       ("left",  1.20, +0.022),
        "rtk-read":                  ("right", 0.85, +0.022),
        "llm-summary-v1-mock":       ("left",  1.10, -0.030),
        "grep":                      ("left",  1.20, +0.016),
    }
    for p in pts:
        ax.scatter(p["tokens"], p["score"],
                   edgecolor="white", linewidth=1.5,
                   **style(p["label"]))
        ha, dx, dy = LABEL_POS.get(p["label"], ("left", 1.18, 0.0))
        ax.annotate(
            p["label"], (p["tokens"], p["score"]),
            xytext=(p["tokens"] * dx, p["score"] + dy),
            fontsize=10.5, ha=ha, va="center",
            family="monospace", color="#222",
        )

    # Pareto frontier line.
    xs = [p["tokens"] for p in pareto]
    ys = [p["score"] for p in pareto]
    ax.plot(xs, ys, linestyle="--", color="#2A9D8F",
            linewidth=2.2, alpha=0.7, zorder=1,
            label=f"Pareto frontier ({len(pareto)} methods)")

    ax.set_xscale("log")
    ax.set_xlim(500, 800_000)
    ax.set_ylim(0.15, 0.75)
    ax.set_xlabel("Total tokens per case  (log scale; reducer LLM + context + diagnosis)",
                  fontsize=12, color="#333")
    ax.set_ylabel("diagnosis_score_v1_1  (case-count-weighted macro, 35 cases × 3 families)",
                  fontsize=12, color="#333")
    ax.grid(True, which="both", linestyle="--", linewidth=0.4,
            color="#ddd", alpha=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#bbb")
    ax.spines["bottom"].set_color("#bbb")
    ax.tick_params(colors="#444")

    ax.legend(loc="lower right", frameon=False, fontsize=11)

    fig.suptitle(
        "LogDx-CI v1.0  —  cost-quality Pareto frontier",
        fontsize=15, fontweight="bold", color="#222", y=0.965,
    )
    ax.set_title(
        "Top-2 hybrids dominate grep on both axes (4.5× cheaper, "
        "+0.03 score). llm-summary-v1-mock pays 432k tokens for "
        "rank-9 quality.",
        fontsize=11, color="#555", pad=10, loc="left",
    )

    fig.text(
        0.5, 0.018,
        "logdx-bench.github.io  ·  Bowen Qin (NUS, @eyuansu62)  ·  "
        "v1.0.1 cost metrics added 2026-05-18",
        ha="center", fontsize=10, color="#666",
    )

    out_dir = ROOT / "docs" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cost_quality_pareto.png"
    plt.subplots_adjust(left=0.08, right=0.97, top=0.92, bottom=0.10)
    fig.savefig(out_path, dpi=130, bbox_inches="tight", facecolor="white")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
