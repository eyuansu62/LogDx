"""Agent-loop cost-quality Pareto plot (companion to make_pareto_plot.py
for v1.0.1 single-shot).

x-axis: agent-loop total_input_tokens_consumed per case (log scale)
y-axis: agent-loop diagnosis_score_v1_1

Reads /tmp/logdx_v1_vs_v1_1_comparison.json.
Writes docs/figures/agent_cost_quality_pareto.png.
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = Path("/tmp/logdx_v1_vs_v1_1_comparison.json")


def color_for(label: str) -> str:
    if label.startswith("hybrid"):
        return "#2A9D8F"
    if label.startswith("rtk"):
        return "#E76F51"
    if "summary" in label:
        return "#9D4EDD"
    if label == "raw":
        return "#888"
    return "#5B8DEF"


def main():
    if not DATA_PATH.exists():
        raise SystemExit(
            f"missing {DATA_PATH}; run tools/compare_single_vs_agent.py first"
        )
    rows = json.load(DATA_PATH.open())

    pts = []
    for r in rows:
        ag = r.get("agent") or {}
        score = ag.get("score")
        cost = ag.get("agent_in")
        if score is None or cost is None or cost <= 0:
            continue
        pts.append({"label": r["method"], "score": score, "cost": cost,
                    "tools": ag.get("agent_tools")})

    if not pts:
        raise SystemExit("no agent-loop points to plot")

    pareto = []
    for p in pts:
        dominated = any(
            (q["cost"] <= p["cost"] and q["score"] > p["score"]) or
            (q["cost"] < p["cost"] and q["score"] >= p["score"])
            for q in pts if q is not p
        )
        if not dominated:
            pareto.append(p)
    pareto.sort(key=lambda p: p["cost"])

    fig, ax = plt.subplots(figsize=(13, 8), dpi=100)
    fig.patch.set_facecolor("white")

    for p in pts:
        c = color_for(p["label"])
        marker = "*" if p["label"].startswith("hybrid") else "o"
        size = 380 if p["label"].startswith("hybrid") else 230
        ax.scatter(p["cost"], p["score"],
                   color=c, edgecolor="white", linewidth=1.6,
                   marker=marker, s=size, zorder=4)

    LABEL = {
        "rtk-log":                    ("right", 0.85, +0.012),
        "llm-summary-v1-mock":        ("left",  1.18, +0.014),
        "tail-200":                   ("right", 0.85, -0.022),
        "hybrid-grep-4k-rtk-err-cat": ("right", 0.85, +0.020),
        "rtk-err-cat":                ("left",  1.18, -0.024),
        "hybrid-grep-120k-rtk-tail":  ("left",  1.18, -0.014),
        "raw":                        ("right", 0.85, +0.022),
        "rtk-read":                   ("left",  1.18, +0.022),
        "grep":                       ("left",  1.18, -0.022),
        "hybrid-grep-120k-tail":      ("left",  1.18, +0.016),
    }
    for p in pts:
        ha, dx, dy = LABEL.get(p["label"], ("left", 1.18, 0.0))
        ax.annotate(
            p["label"], (p["cost"], p["score"]),
            xytext=(p["cost"] * dx, p["score"] + dy),
            ha=ha, va="center",
            fontsize=10.5, family="monospace", color="#222",
        )

    xs = [p["cost"] for p in pareto]
    ys = [p["score"] for p in pareto]
    ax.plot(xs, ys, linestyle="--", color="#2A9D8F",
            linewidth=2.2, alpha=0.7, zorder=1,
            label=f"Agent-loop Pareto frontier ({len(pareto)} methods)")

    ax.set_xscale("log")
    ax.set_xlim(40_000, 200_000)
    ax.set_ylim(0.40, 0.62)
    ax.set_xlabel(
        "Agent-loop  total_input_tokens_consumed  per case  (log scale)",
        fontsize=12, color="#333",
    )
    ax.set_ylabel(
        "Agent-loop  diagnosis_score_v1_1  (Sonnet 4.6)",
        fontsize=12, color="#333",
    )
    ax.grid(True, which="both", linestyle="--", linewidth=0.4,
            color="#ddd", alpha=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#bbb")
    ax.spines["bottom"].set_color("#bbb")
    ax.tick_params(colors="#444")
    ax.legend(loc="lower right", frameon=False, fontsize=11)

    fig.suptitle(
        "LogDx-CI v1.1 — agent-loop cost-quality Pareto frontier",
        fontsize=15, fontweight="bold", color="#222", y=0.965,
    )
    ax.set_title(
        "Compared to single-shot, the quality range collapses and the "
        "Pareto frontier flattens. Cost differences persist.",
        fontsize=11, color="#555", pad=10, loc="left",
    )

    fig.text(
        0.5, 0.018,
        "logdx-bench.github.io  ·  Bowen Qin (NUS, @eyuansu62)  ·  "
        "v1.1 35-case corpus × Sonnet 4.6 agent",
        ha="center", fontsize=10, color="#666",
    )

    out = ROOT / "docs" / "figures" / "agent_cost_quality_pareto.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.subplots_adjust(left=0.08, right=0.97, top=0.92, bottom=0.10)
    fig.savefig(out, dpi=130, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
