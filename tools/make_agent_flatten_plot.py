"""Render the headline 'agent flattens method differentiation' plot.

x-axis: single-shot diagnosis_score_v1_1 (averaged across 3 model families)
y-axis: agent-loop diagnosis_score_v1_1 (Sonnet 4.6 only)
Dashed diagonal: y=x (parity line — points above = agent improved,
                 points below = agent hurt the method)

Reads /tmp/logdx_v1_vs_v1_1_comparison.json (produced by
tools/compare_single_vs_agent.py). Writes
docs/figures/agent_flattens_methods.png.
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = Path("/tmp/logdx_v1_vs_v1_1_comparison.json")


COLOR_BY_FAMILY = {
    "hybrid": "#2A9D8F",
    "rtk":    "#E76F51",
    "summary": "#9D4EDD",
    "raw":     "#888",
    "other":   "#5B8DEF",
}


def color_for(label: str) -> str:
    if label.startswith("hybrid"):
        return COLOR_BY_FAMILY["hybrid"]
    if label.startswith("rtk"):
        return COLOR_BY_FAMILY["rtk"]
    if "summary" in label:
        return COLOR_BY_FAMILY["summary"]
    if label == "raw":
        return COLOR_BY_FAMILY["raw"]
    return COLOR_BY_FAMILY["other"]


def main():
    if not DATA_PATH.exists():
        raise SystemExit(
            f"missing {DATA_PATH}; run tools/compare_single_vs_agent.py first"
        )
    rows = json.load(DATA_PATH.open())

    pts = []
    for r in rows:
        ss = (r.get("single_shot") or {}).get("score")
        ag = (r.get("agent") or {}).get("score")
        if ss is None or ag is None:
            continue
        pts.append({"label": r["method"], "ss": ss, "ag": ag})

    fig, ax = plt.subplots(figsize=(12, 9), dpi=100)
    fig.patch.set_facecolor("white")

    # Identity line.
    ax.plot([0.15, 0.75], [0.15, 0.75],
            linestyle="--", color="#bbb", linewidth=1.3,
            label="y = x  (no agent effect)", zorder=1)

    # Plot points.
    for p in pts:
        c = color_for(p["label"])
        marker = "*" if p["label"].startswith("hybrid") else "o"
        size = 380 if p["label"].startswith("hybrid") else 230
        ax.scatter(p["ss"], p["ag"],
                   color=c, edgecolor="white", linewidth=1.8,
                   marker=marker, s=size, zorder=4)

    # Manual label placement — packed tightly because all points
    # sit in the 0.65–0.73 horizontal band.
    LABEL = {
        "hybrid-grep-120k-tail":      ("left",  +0.015, +0.018),
        "hybrid-grep-120k-rtk-tail":  ("right", -0.015, -0.022),
        "hybrid-grep-4k-rtk-err-cat": ("left",  +0.015, +0.018),
        "grep":                       ("right", -0.015, +0.018),
        "tail-200":                   ("left",  +0.015, +0.018),
        "rtk-err-cat":                ("left",  +0.015, -0.020),
        "rtk-read":                   ("left",  +0.015, +0.020),
        "raw":                        ("right", -0.015, +0.024),
        "llm-summary-v1-mock":        ("right", -0.015, -0.024),
        "rtk-log":                    ("left",  +0.015, -0.022),
    }
    for p in pts:
        ha, dx, dy = LABEL.get(p["label"], ("left", 0.015, 0.0))
        ax.annotate(
            p["label"], (p["ss"], p["ag"]),
            xytext=(p["ss"] + dx, p["ag"] + dy),
            ha=ha, va="center",
            fontsize=10.5, family="monospace", color="#222",
        )

    # Annotation: every method gains. No "below the line" cases in v1.1
    # full-corpus data.
    ax.annotate(
        "every method gains in agent-loop\n(weakest methods gain the most)",
        xy=(0.27, 0.55), fontsize=10.5, color="#2A7D67",
        rotation=0, ha="left", style="italic",
    )

    ax.set_xlim(0.18, 0.74)
    ax.set_ylim(0.18, 0.74)
    ax.set_aspect("equal")
    ax.set_xlabel(
        "Single-shot  diagnosis_score_v1_1  (averaged across 3 model families)",
        fontsize=12, color="#333",
    )
    ax.set_ylabel(
        "Agent-loop  diagnosis_score_v1_1  (Sonnet 4.6, max 5 turns × 4 tools)",
        fontsize=12, color="#333",
    )
    ax.grid(True, linestyle="--", linewidth=0.4, color="#ddd", alpha=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#bbb")
    ax.spines["bottom"].set_color("#bbb")
    ax.tick_params(colors="#444")
    ax.legend(loc="upper left", frameon=False, fontsize=10)

    fig.suptitle(
        "LogDx-CI v1.1 — multi-turn agents narrow the gap between context methods",
        fontsize=14, fontweight="bold", color="#222", y=0.965,
    )
    ax.set_title(
        "Score range collapses 6× from single-shot (0.42) to agent-loop (0.069). "
        "All 10 methods improve; rtk-log gains +0.41 by being rescued via tool calls.",
        fontsize=11, color="#555", pad=10, loc="left",
    )

    fig.text(
        0.5, 0.018,
        "logdx-bench.github.io  ·  Bowen Qin (NUS, @eyuansu62)  ·  "
        "v1.1 35-case corpus × Sonnet 4.6 agent",
        ha="center", fontsize=10, color="#666",
    )

    out = ROOT / "docs" / "figures" / "agent_flattens_methods.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.subplots_adjust(left=0.10, right=0.97, top=0.92, bottom=0.10)
    fig.savefig(out, dpi=130, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
