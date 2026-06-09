"""The 11 v1.2 baseline scores, for vs-baseline comparison in Result.summary()."""
from __future__ import annotations

import json
from importlib.resources import files


def _load_baselines() -> dict:
    return json.loads((files("logdx_ci.data") / "baseline_scores.json").read_text())


BASELINES = _load_baselines()


def closest_baseline(score: float) -> str:
    """Return the baseline whose score is closest to `score`."""
    ranked = sorted(
        BASELINES.items(),
        key=lambda kv: abs(kv[1]["score"] - score),
    )
    name, info = ranked[0]
    delta = score - info["score"]
    sign = "+" if delta >= 0 else ""
    return f"{name} ({info['score']:.3f}, {sign}{delta:.3f})"


def render_table(my_score: float, my_tokens: float | None = None) -> str:
    """Render a comparison table: your score vs the 11 baselines."""
    rows = []
    rows.append(("**YOU**", my_score, my_tokens, ""))
    for name, info in sorted(BASELINES.items(), key=lambda kv: -kv[1]["score"]):
        delta = info["score"] - my_score
        rows.append((name, info["score"], info.get("tokens"), f"{delta:+.3f} vs you"))

    lines = []
    lines.append(f"{'method':<35}  {'score':>7}  {'tokens':>10}  {'note':<20}")
    lines.append("-" * 80)
    for name, score, tokens, note in rows:
        tok_str = f"{tokens:,.0f}" if tokens else "—"
        lines.append(f"{name:<35}  {score:>7.4f}  {tok_str:>10}  {note}")
    return "\n".join(lines)
