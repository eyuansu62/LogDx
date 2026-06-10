"""LogDx-CI v1.2 baseline scores, for vs-baseline comparison in Result.summary().

Two flavors:
  * BASELINES         — diagnosis_score_v1_1 (LLM-eval, headline leaderboard)
  * STATIC_BASELINES  — critical_signal_recall (no-LLM, text-only path) for
                        comparing reducers scored under diagnoser=
                        'static-signal-recall'
"""
from __future__ import annotations

import json
from importlib.resources import files


def _load(name: str) -> dict:
    return json.loads((files("logdx_ci.data") / name).read_text())


BASELINES = _load("baseline_scores.json")
STATIC_BASELINES = _load("static_signal_recall_baselines.json")


def _table(static: bool) -> dict:
    return STATIC_BASELINES if static else BASELINES


def _score_key(static: bool) -> str:
    return "critical_signal_recall" if static else "score"


def closest_baseline(score: float, *, static: bool = False) -> str:
    table = _table(static)
    key = _score_key(static)
    ranked = sorted(table.items(), key=lambda kv: abs(kv[1][key] - score))
    name, info = ranked[0]
    delta = score - info[key]
    sign = "+" if delta >= 0 else ""
    return f"{name} ({info[key]:.3f}, {sign}{delta:.3f})"


def render_table(
    my_score: float,
    my_tokens: float | None = None,
    *,
    static: bool = False,
) -> str:
    table = _table(static)
    key = _score_key(static)

    rows = [("**YOU**", my_score, my_tokens, "")]
    for name, info in sorted(table.items(), key=lambda kv: -kv[1][key]):
        delta = info[key] - my_score
        rows.append(
            (name, info[key], info.get("tokens"), f"{delta:+.3f} vs you")
        )

    header_score = "csr" if static else "score"
    lines = [
        f"{'method':<35}  {header_score:>7}  {'tokens':>10}  {'note':<20}",
        "-" * 80,
    ]
    for name, score, tokens, note in rows:
        tok_str = f"{tokens:,.0f}" if tokens else "—"
        lines.append(f"{name:<35}  {score:>7.4f}  {tok_str:>10}  {note}")
    return "\n".join(lines)
