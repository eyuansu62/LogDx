"""Render a Twitter-friendly LogDx-CI leaderboard image.

Output: /tmp/logdx-leaderboard.png (1600x900, 16:9 — X-optimal aspect).
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

DATA = [
    ("hybrid-grep-120k-rtk-tail", 0.624, 0.679, 0.706, 0.670, "top"),
    ("hybrid-grep-120k-tail",     0.610, 0.730, 0.658, 0.666, "top"),
    ("grep",                      0.578, 0.684, 0.655, 0.639, "mid"),
    ("tail-200",                  0.595, 0.624, 0.623, 0.614, "mid"),
    ("hybrid-grep-4k-rtk-err-cat",0.552, 0.597, 0.571, 0.573, "mid"),
    ("rtk-err-cat",               0.455, 0.488, 0.467, 0.470, "mid"),
    ("raw",                       0.324, 0.368, 0.367, 0.353, "bottom"),
    ("rtk-read",                  0.329, 0.369, 0.349, 0.349, "bottom"),
    ("llm-summary-v1-mock",       0.343, 0.348, 0.294, 0.328, "bottom"),
    ("rtk-log",                   0.238, 0.262, 0.249, 0.249, "bottom"),
]

C_HAIKU = "#5B8DEF"
C_SONNET = "#F4A261"
C_GPT5 = "#2A9D8F"
C_TOP_TINT = "#E8F5E9"
C_BOTTOM_TINT = "#FFEBEE"

fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
fig.patch.set_facecolor("white")

methods = [d[0] for d in DATA][::-1]
haiku = [d[1] for d in DATA][::-1]
sonnet = [d[2] for d in DATA][::-1]
gpt5 = [d[3] for d in DATA][::-1]
overall = [d[4] for d in DATA][::-1]
zones = [d[5] for d in DATA][::-1]

y = np.arange(len(methods))
height = 0.26

ax.barh(y + height, haiku, height, label="Claude Haiku 4.5",
        color=C_HAIKU, edgecolor="white", linewidth=0.8)
ax.barh(y,          sonnet, height, label="Claude Sonnet 4.6",
        color=C_SONNET, edgecolor="white", linewidth=0.8)
ax.barh(y - height, gpt5, height, label="OpenAI gpt-5-mini",
        color=C_GPT5, edgecolor="white", linewidth=0.8)

for i, zone in enumerate(zones):
    if zone == "top":
        ax.axhspan(i - 0.45, i + 0.45, color=C_TOP_TINT, zorder=0)
    elif zone == "bottom":
        ax.axhspan(i - 0.45, i + 0.45, color=C_BOTTOM_TINT, zorder=0)

for i, ov in enumerate(overall):
    ax.text(0.78, i, f"overall  {ov:.3f}",
            va="center", ha="left",
            fontsize=11, family="monospace",
            color="#222",
            fontweight=("bold" if zones[i] == "top" else "normal"))

ax.set_yticks(y)
ax.set_yticklabels(methods, family="monospace", fontsize=11)
ax.set_xlabel("diagnosis_score_v1_1  (case-count-weighted macro)",
              fontsize=12, color="#444")
ax.set_xlim(0, 0.95)
ax.set_xticks(np.arange(0, 0.81, 0.1))
ax.set_axisbelow(True)
ax.grid(axis="x", linestyle="--", linewidth=0.5, color="#ccc", alpha=0.6)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
ax.spines["left"].set_color("#bbb")
ax.spines["bottom"].set_color("#bbb")
ax.tick_params(axis="both", colors="#444")

legend_handles = [
    mpatches.Patch(color=C_HAIKU,  label="Claude Haiku 4.5"),
    mpatches.Patch(color=C_SONNET, label="Claude Sonnet 4.6"),
    mpatches.Patch(color=C_GPT5,   label="OpenAI gpt-5-mini"),
    mpatches.Patch(color=C_TOP_TINT, label="cross-family top-3 ∩"),
    mpatches.Patch(color=C_BOTTOM_TINT, label="cross-family bottom-4"),
]
ax.legend(
    handles=legend_handles,
    loc="upper center",
    bbox_to_anchor=(0.5, -0.08),
    frameon=False,
    fontsize=10,
    ncol=5,
)

fig.suptitle(
    "LogDx-CI v1.0  —  do CI log reduction tools preserve enough "
    "evidence for LLM root-cause diagnosis?",
    fontsize=15, fontweight="bold", color="#222", y=0.965,
)
ax.set_title(
    "10 reducers × 3 model families × 35 real GitHub Actions "
    "failures   ·   top-2 = 120k-threshold hybrids "
    "(stable across families)",
    fontsize=11.5, color="#555", pad=10, loc="left",
)

fig.text(
    0.5, 0.018,
    "logdx-bench.github.io  ·  Bowen Qin (NUS, @eyuansu62)  "
    "·  Apache-2.0 code / CC-BY-4.0 data",
    ha="center", fontsize=10, color="#666",
)

plt.subplots_adjust(left=0.20, right=0.97, top=0.90, bottom=0.16)
out_path = "/tmp/logdx-leaderboard.png"
fig.savefig(out_path, dpi=130, bbox_inches="tight", facecolor="white")
print(f"wrote {out_path}")
