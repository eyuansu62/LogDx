# LogDx-CI v1.1.1 — Release Notes

**Tag**: `v1.1.1`
**Date**: 2026-05-20
**Project homepage**: <https://logdx-bench.github.io/>
**Type**: Patch release (no protocol-lock schema bumps; ranking change is a
data-coverage expansion, not a methodology change)

## TL;DR

v1.1.1 promotes `llm-summary-v1-haiku` — the real Anthropic Haiku 4.5
map-reduce summarizer — to the headline leaderboard. Through v1.1 the
LLM-summary class on the board was represented by `llm-summary-v1-mock`,
a deterministic regex-extract stub that we had been using since v1.0
because the real summarizer had only been prototyped on a 16-case
subset. Community feedback flagged this as unfair to the LLM-summary
class. v1.1.1 backfills the real summarizer
to the full 35-case corpus across all 4 diagnoser families
(Haiku 4.5, Sonnet 4.6, gpt-5-mini single-shot; Sonnet 4.6 agent-loop)
and updates the headline tables accordingly.

## Headline change

| Diagnoser                       | mock score | **haiku score** | Δ |
|---------------------------------|----------:|------------:|----:|
| `real-debugger-v1` (Haiku 4.5)  | 0.343 | **0.583** | +0.240 |
| `real-debugger-v2` (Sonnet 4.6) | 0.348 | **0.704** | +0.356 |
| `real-debugger-v3` (gpt-5-mini) | 0.294 | **0.608** | +0.314 |
| `real-agent-v1` (Sonnet+tools)  | 0.715 | 0.690 | -0.025 |

The real Haiku summarizer **wins by +0.24 to +0.36** in every
single-shot family. In the agent-loop both methods land near 0.70 (the
agent rescues weak contexts via tool calls), but `llm-summary-v1-haiku`
needs only **0.71 tools/case vs the mock's 1.88** — the real summary
genuinely front-loads the failure signal. confident_error drops
from 13% → 3% (single-shot).

## What this means for rankings

**Single-shot leaderboard (overall mean across 3 families):**

| Rank | Method | Overall |
|----:|--------|--------:|
| 1 | `hybrid-grep-120k-rtk-tail` | 0.670 |
| 2 | `hybrid-grep-120k-tail` | 0.666 |
| 3 | `grep` | 0.639 |
| **4** | **`llm-summary-v1-haiku`** | **0.632** |
| 5 | `tail-200` | 0.614 |
| 6–10 | … | … |
| — | `llm-summary-v1-mock` (legacy) | 0.328 |

`llm-summary-v1-haiku` slots in at rank 4 — between `grep` (rank 3) and
`tail-200` (rank 5), ahead of every RTK mode and `raw`. The mock is
relegated to a "—" footer row and labeled as a legacy infrastructure
baseline.

**Agent-loop leaderboard**: `llm-summary-v1-haiku` lands rank 8 (0.690)
but with the lowest tool-call count of any non-`tail-200` method (0.71/
case). The full agent-loop table is in
`docs/leaderboard.md#agent-loop-leaderboard--v11`.

## Cost note

`llm-summary-v1-haiku` is the most expensive method on the board at
**1.68M tokens/case end-to-end** — about 4× more than the mock had
modeled (432k). The gap is Claude-Code-CLI cached-prefix overhead on
nested `claude -p` invocations that the mock didn't simulate. Anyone
optimizing for cost should still pick a 120k-hybrid; the leaderboard's
cost-quality Pareto plot makes the tradeoff explicit.

## Implementation notes

- Map-reduce config: `chunk_lines=500`, `chunk_overlap_lines=25`,
  `temperature=0`, model `haiku` (alias resolves to
  `claude-haiku-4-5`).
- **Three cases** (nodejs-test-debugger-exec-timeout-v2-001,
  pytest-sklearn-stress-001, pytest-sklearn-stress-002) re-chunked at
  `chunk_lines=100` because some 500-line windows exceeded Haiku's
  effective input window after Claude-Code session overhead. Same
  map-reduce algorithm, smaller chunks; the actual config used is
  recorded in per-case `metadata.chunk_lines`.
- All 35 `llm-summary-v1-haiku` rows have `provider_error=None` and
  non-zero output. All 140 diagnosis runs (35 cases × 4 diagnosers)
  succeeded without any allowlist injections.

## Mock status

`llm-summary-v1-mock` is **not removed**. It stays as:
1. A control / smoke-test baseline (`tools/run_llm_summary_baseline.py
   --provider mock` still works — useful for CI without burning paid
   tokens).
2. A lower-bound data point — the +0.30 gap between mock 0.328 and
   haiku 0.632 quantifies what the real LLM contributes vs the
   deterministic structural skeleton.
3. A historical reference — v1.0 published numbers that cite the mock
   remain reproducible.

## CI hygiene fix (pre-release)

This release also fixes a stale protocol lock that was inherited from
v1.1: `protocols/logdx-ci-v2-partial-2026-05-20.lock.json` was pinned
against pre-v1.1 SHAs for `schemas/diagnosis.schema.json` and
`tools/evaluate_diagnosis.py`, and was missing the `prompts/agent_v1.md`
entry that v1.1 introduced. CI tests started failing from `a5a22f6`
because of this drift. The lock has been re-frozen against the current
state; the regeneration is captured in the lock's `regenerated=true`
flag.

## What did NOT change

- **Protocol**: no changes to v1.1's protocol lock
  (`protocols/logdx-ci-v1.1.lock.json`). The map-reduce algorithm,
  scoring formula, evaluator, and corpus are unchanged.
- **Corpus**: same 35 cases across the same 6 splits.
- **Diagnosers**: same 4 (Haiku 4.5, Sonnet 4.6, gpt-5-mini, agent_v1).
- **Schemas / prompts**: unchanged from v1.1.

## Updated documents

Live docs (current state):
- `docs/leaderboard.md` — headline tables, cost breakdown, agent-loop
  table, cross-family agreement, v1.1 promotion note section
- `docs/index.md` — homepage overall table
- `docs/methods/llm_summary.md` — mock relabeled "infrastructure-only /
  legacy"
- `docs/analysis/agent-loop-vs-single-shot.md` — agent-loop table +
  cost-range narrative updated
- `docs/analysis/why-rtk-underperforms-on-ci-diagnosis.md` —
  "mock-summary in the leaderboard" caveat resolved
- `docs/model_cards/llm-summary-v1-haiku.md` — "v1.1 corpus expansion"
  section added

Frozen historical docs (kept as-shipped; forward-pointer footnotes
added):
- `docs/protocol/cilogbench_v1_3.md`
- `docs/reports/cilogbench_v1_3_one_pager.md`
- `docs/reports/cilogbench_v1_3_technical_report.md`

## Reproducibility

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx
git checkout v1.1.1

# Re-run any single eval (deterministic; uses cached diagnoses)
python3 tools/evaluate_diagnosis.py --split v2/dev --diagnoser real-debugger-v2

# Per-method macro scores in
# results/v2/dev/eval_diagnosis_real-debugger-v2.json will match this
# release's published numbers.
```

For a fresh re-run that hits the OpenAI / Anthropic / OpenRouter APIs,
see the reproducibility section in the v1.0 release notes (the workflow
is the same).

## Acknowledgements

Thanks to the reviewer whose three-question critique on v1.1 triggered
this backfill. The relevant question — "is the LLM-summary class fairly
represented?" — turned out to be load-bearing: the answer was no, and
the +0.30 gap between the legacy mock and the real Haiku summarizer
quantifies what was hidden.
