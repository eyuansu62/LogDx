"""Render cost-quality Pareto plot for LogDx-CI v1.2.

x-axis: total tokens per case (reducer_in + reducer_out + context + diagnosis)
        on log scale because the range is 810 → 1,681,520
y-axis: diagnosis_score_v1_1 (case-count-weighted macro across the 3
        debugger families, taken from the published leaderboard)

11 methods on the v1.2 headline. The legacy `llm-summary-v1-mock` was
moved to the leaderboard appendix in v1.1.2 and is excluded here.

Output: docs/figures/cost_quality_pareto.png
"""

from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent

# Mirrors the v1.2 published leaderboard so this file is self-contained.
# Each entry: (total_tokens_per_case, diagnosis_score_v1_1)
DATA = {
    # method                          tokens    score
    "rtk-log":                       (    810, 0.249),
    "tail-200":                      (  6_108, 0.614),
    "hybrid-grep-120k-tail":         ( 19_753, 0.666),
    "hybrid-grep-120k-rtk-tail":     ( 19_844, 0.670),
    "rtk-err-cat":                   ( 19_850, 0.470),
    "hybrid-grep-4k-rtk-err-cat":    ( 19_892, 0.573),
    "grep":                          ( 88_355, 0.639),
    "rtk-read":                      (274_289, 0.349),
    "raw":                           (275_248, 0.353),
    "llm-summary-v1-gpt-5-mini":     (537_638, 0.664),
    "llm-summary-v1-haiku":          (1_681_520, 0.632),
}

# Set of methods on the Pareto frontier — get bigger / brighter markers
PARETO_HIGHLIGHT = {"rtk-log", "tail-200",
                    "hybrid-grep-120k-tail", "hybrid-grep-120k-rtk-tail"}


def style(label: str) -> dict:
    """Color/marker per method family.

    Pareto-frontier methods get larger markers so they pop visually.
    """
    is_pareto = label in PARETO_HIGHLIGHT
    size_boost = 1.4 if is_pareto else 1.0
    edge_width = 2.0 if is_pareto else 1.2
    if label.startswith("hybrid"):
        return dict(color="#2A9D8F", marker="*", s=int(420 * size_boost),
                    zorder=5, linewidth=edge_width)
    if label.startswith("rtk"):
        return dict(color="#E76F51", marker="o", s=int(180 * size_boost),
                    zorder=3, linewidth=edge_width)
    if label == "llm-summary-v1-haiku":
        return dict(color="#9D4EDD", marker="s", s=200,
                    zorder=4, linewidth=edge_width)
    if label == "llm-summary-v1-gpt-5-mini":
        return dict(color="#7B2CBF", marker="s", s=200,
                    zorder=4, linewidth=edge_width)
    if label == "raw":
        return dict(color="#888", marker="X", s=180,
                    zorder=2, linewidth=edge_width)
    return dict(color="#5B8DEF", marker="D", s=int(180 * size_boost),
                zorder=3, linewidth=edge_width)


# Label placement uses (ha, va, dx_points, dy_points) — offsets in DISPLAY
# points (1 pt = 1/72"), so labels sit a fixed visual distance from the
# marker regardless of log-axis scaling. This is the standard matplotlib
# pattern for tight point↔label coupling.
#
# The cluster at x ≈ 19_800 has 4 methods that would overlap if all placed
# on the same side — we push them in 4 different directions (N / W / E / S).
LABEL_PLACEMENT = {
    "rtk-log":                       ("left",   "center", +14,    0),
    "tail-200":                      ("left",   "center", +14,    0),
    "grep":                          ("left",   "center", +14,    0),
    # rtk-read and raw sit at near-identical (x, y); split N / S so labels don't stack
    "rtk-read":                      ("center", "top",      0,  -18),  # S
    "raw":                           ("center", "bottom",   0,  +18),  # N
    "llm-summary-v1-gpt-5-mini":     ("center", "bottom",   0,  +16),
    "llm-summary-v1-haiku":          ("center", "top",      0,  -16),
    # Cluster at x ≈ 19_800
    "hybrid-grep-120k-rtk-tail":     ("center", "bottom",   0,  +18),  # N
    "hybrid-grep-120k-tail":         ("right",  "center", -14,    0),  # W
    "hybrid-grep-4k-rtk-err-cat":    ("left",   "center", +14,    0),  # E
    "rtk-err-cat":                   ("center", "top",      0,  -18),  # S
}


def compute_pareto(points):
    """A point is Pareto-optimal if no other point strictly dominates it
    (≤ tokens AND > score, OR < tokens AND ≥ score)."""
    out = []
    for p in points:
        dominated = any(
            (q["tokens"] <= p["tokens"] and q["score"] > p["score"]) or
            (q["tokens"] <  p["tokens"] and q["score"] >= p["score"])
            for q in points if q is not p
        )
        if not dominated:
            out.append(p)
    return sorted(out, key=lambda p: p["tokens"])


def annotate_point(ax, p):
    ha, va, dx_pts, dy_pts = LABEL_PLACEMENT[p["label"]]
    ax.annotate(
        p["label"], xy=(p["tokens"], p["score"]),
        xytext=(dx_pts, dy_pts), textcoords="offset points",
        fontsize=11, ha=ha, va=va,
        family="monospace", color="#1a1a1a", zorder=6,
    )


def main():
    points = [
        {"label": label, "tokens": tokens, "score": score}
        for label, (tokens, score) in DATA.items()
    ]
    pareto = compute_pareto(points)

    fig, ax = plt.subplots(figsize=(10, 5.8), dpi=120)
    fig.patch.set_facecolor("white")

    # Pareto frontier line — draw first so points sit on top
    xs = [p["tokens"] for p in pareto]
    ys = [p["score"] for p in pareto]
    ax.plot(xs, ys, linestyle="--", color="#2A9D8F",
            linewidth=2.2, alpha=0.55, zorder=1,
            label=f"Pareto frontier  ({len(pareto)} methods)")

    # All points + their labels
    for p in points:
        ax.scatter(p["tokens"], p["score"],
                   edgecolor="white", **style(p["label"]))
        annotate_point(ax, p)

    # Axes & cosmetics
    ax.set_xscale("log")
    ax.set_xlim(550, 2_500_000)
    ax.set_ylim(0.20, 0.75)
    ax.set_xlabel("Total tokens per case (log)",
                  fontsize=11, color="#333", labelpad=6)
    ax.set_ylabel("diagnosis_score_v1_1",
                  fontsize=11, color="#333", labelpad=6)
    ax.grid(True, which="both", linestyle="--", linewidth=0.4,
            color="#ddd", alpha=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#bbb")
    ax.spines["bottom"].set_color("#bbb")
    ax.tick_params(colors="#444", labelsize=9.5)

    ax.legend(loc="lower right", frameon=False, fontsize=10)

    # Single title — no subtitle / no footer (tweet copy does the
    # narrative framing instead).
    fig.suptitle(
        "LogDx-CI v1.2 · cost-quality Pareto frontier",
        fontsize=15, fontweight="bold", color="#1a1a1a",
        x=0.06, y=0.965, ha="left",
    )

    out_dir = ROOT / "docs" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cost_quality_pareto.png"
    plt.subplots_adjust(left=0.08, right=0.98, top=0.91, bottom=0.10)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
