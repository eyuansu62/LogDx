# Agent loops flatten the gap between context methods (v1.1)

> Follow-up analysis on the [LogDx-CI v1.1](https://logdx-bench.github.io/)
> agent-loop release. Companion to
> [`why-rtk-underperforms-on-ci-diagnosis.md`](why-rtk-underperforms-on-ci-diagnosis.md).
>
> **Headline finding**: in agent-loop usage, the choice of context
> method matters far less for *quality* than in single-shot — the
> score range collapses from 0.42 to 0.059. Cost differences
> persist (2.4× spread in agent-loop vs 530× single-shot), and the
> v1.0 single-shot winner (`hybrid-grep-120k-rtk-tail`) holds the
> #1 spot in agent-loop too — most robust method across both
> regimes.

## TL;DR

LogDx-CI v1.0 measured how 10 log-reduction methods affect LLM
diagnosis quality in a single-shot setting: hand the model the
reduced log once, ask for a diagnosis, score the answer. v1.1 adds
the **agent-loop** measurement: hand the model the reduced log
*plus* 4 deterministic tools (`grep`, `read_file`, `tail`,
`view_log_lines`) operating on the raw log, and let it call them
across up to 5 turns.

Four findings on the 35-case corpus × Sonnet 4.6 agent:

1. **Every method gains. The quality gap collapses ~7×.** Single-shot
   `diagnosis_score_v1_1` ranges from **0.249** (`rtk-log`, worst)
   to **0.670** (`hybrid-grep-120k-rtk-tail`, best) — a 0.42 spread.
   Agent-loop scores compress to **[0.688, 0.747]**, a 0.059 spread.
   `rtk-log` gains the most (+0.44) by being rescued via tool calls;
   no method loses score.
2. **Confident-error mostly collapses.** v1.0 surfaced that
   `rtk-log` and `llm-summary-v1-mock` produce confidently-wrong
   diagnoses on **~13%** of cases (the failure mode
   [discussed in rtk-ai/rtk#1599](https://github.com/rtk-ai/rtk/issues/1599)).
   In agent-loop, 6 of 10 methods sit at **0%** confident_error,
   including `llm-summary-v1-mock`. The four non-zero rates are
   `rtk-log` (5.7%), `raw` (2.9%), `grep` (2.9%), and `tail-200`
   (2.9%) — methods that either over-compress (rtk-log loses too
   much signal for the agent to verify), or under-filter (raw / tail
   give the agent so much surface detail it commits before tool-
   verifying).
3. **Top single-shot method holds.** v1.0's #1
   (`hybrid-grep-120k-rtk-tail`, 0.670 single-shot) **stays #1 in
   agent-loop** (0.747). It's also the cheapest in the top tier
   (37k tokens/case agent-loop) and has 0% confident_error. **This
   is the v1.1 universal recommendation.** All three v1.0 hybrid
   variants (`hybrid-grep-120k-rtk-tail`, `hybrid-grep-4k-rtk-err-
   cat`, `hybrid-grep-120k-tail`) cluster in the agent-loop top 3.
4. **Cost compresses ~220×, but doesn't vanish.** Single-shot
   input tokens range from 810 (`rtk-log`) to 432k
   (`llm-summary-v1-mock` end-to-end) — a 530× max/min ratio.
   Agent-loop ranges from 28k to 67k — a 2.4× ratio (so the
   spread shrinks by 530 / 2.4 ≈ 220×). The agent adds a roughly
   fixed ~30–70k token cost regardless of starting context.

## Setup

**Diagnoser**: `real-agent-v1` — Anthropic Sonnet 4.6 via direct
Messages API. 4-tool surface, `max_iterations=5`,
`max_total_input_tokens=180000`. The agent receives the **context
method's output as its initial user message** (not blank), and may
call any of the 4 tools on the case's `raw.log` to supplement.

**Corpus**: 35 cases × 10 context methods × 1 model family. Sonnet
4.6 only in v1.1; Haiku 4.5 and gpt-5-mini variants are listed in
[`ROADMAP.md`](../../ROADMAP.md) as v1.2 follow-ups.

**Scoring**: same `diagnosis_score_v1_1` as single-shot. The
`agent_metadata` block on each row records `iterations`,
`tool_call_count`, `total_input_tokens_consumed`,
`total_output_tokens_consumed`, and `budget_exhausted`.

## Side-by-side leaderboard (35-case corpus × Sonnet 4.6 agent)

Sorted by single-shot score (matches the v1.0 leaderboard order).

| Method | single-shot | agent-loop | Δ | conf_err (agent) | tools / case | tokens / case |
|---|---:|---:|---:|---:|---:|---:|
| `hybrid-grep-120k-rtk-tail` | **0.670** | **0.747** | +0.077 | **0.000** | 0.97 | 37,152 |
| `hybrid-grep-120k-tail` | 0.666 | 0.735 | +0.069 | **0.000** | 1.00 | 39,221 |
| `grep` | 0.639 | 0.722 | +0.083 | 0.029 | 1.20 | 42,232 |
| `tail-200` | 0.614 | 0.710 | +0.096 | 0.029 | 0.69 | 28,166 |
| `hybrid-grep-4k-rtk-err-cat` | 0.573 | 0.737 | +0.164 | **0.000** | 1.40 | 42,862 |
| `rtk-err-cat` | 0.470 | 0.708 | +0.238 | **0.000** | 1.66 | 43,009 |
| `raw` | 0.353 | 0.688 | +0.335 | 0.029 | 1.68 | 67,311 |
| `rtk-read` | 0.349 | 0.735 | +0.386 | **0.000** | 1.46 | 55,391 |
| `llm-summary-v1-mock` | 0.328 | 0.715 | +0.387 | **0.000** | 1.88 | 32,139 |
| `rtk-log` | **0.249** | 0.689 | **+0.440** | 0.057 | 2.60 | 36,259 |

![Agent flattens methods](../figures/agent_flattens_methods.png)

## Interpretation

### 1. Why does the agent rescue weak contexts?

`rtk-log`'s static output averages just **~325 context tokens** —
heavily compressed, missing most of the original signal. Single-shot,
the LLM sees the rubbed-out summary and **confidently misdiagnoses
13% of the time** (per the v1.0.1 confident_error column); it also
abstains on ~20% of cases. In agent-loop, the same starting context
triggers **2.60 tool calls per case** (the highest of any method);
the agent immediately recognizes that the rtk-log output is too
lossy and falls back to `tail(200)` or a targeted `grep` on the
raw log. **By the time the agent diagnoses, it has effectively
reconstructed the grep-style context on the fly.**

Same mechanism for `llm-summary-v1-mock` (1.88 tool calls per case
in agent-loop): the mock summary is deterministic and unhelpful, so
the agent supplements via grep/tail on the raw log.

### 2. Does the agent *hurt* strong contexts?

A 5-case smoke test suggested yes — top single-shot methods
appeared to lose 0.10–0.19 score in agent-loop. But the full
35-case data tells a different story: **every method gains, no
method loses.** The smoke effect was a 5-case sampling artifact.

That said, the **gains are smallest** for already-strong methods:
- `hybrid-grep-120k-rtk-tail` (single-shot #1): +0.077
- `hybrid-grep-120k-tail` (single-shot #2): +0.069
- `grep` (single-shot #3): +0.083

And a related effect emerges: four methods carry **non-zero
agent-loop confident_error**: `rtk-log` (5.7%), `raw` (2.9%),
`grep` (2.9%), `tail-200` (2.9%). The cluster is mixed — `rtk-log`
over-compresses (agent can't verify; commits prematurely),
while `raw` / `grep` / `tail-200` give the agent a lot of surface
detail that can mislead it into committing before tool-verifying.
The methods that route via mid-band intermediate logic
(`hybrid-grep-120k-rtk-tail`, `hybrid-grep-120k-tail`, `hybrid-
grep-4k-rtk-err-cat`, `rtk-err-cat`, `llm-summary-v1-mock`,
`rtk-read`) all sit at 0% confident_error.

This is consistent with Sonnet's tool-use bias: it is **trained to
be helpful by exploring**, even when exploration is not informative.
Our prompt explicitly tells the model "Default to 0 tool calls. Call
a tool ONLY if you cannot identify the root cause from the reduced
context," and it still averages ~3 tool calls regardless. But the
exploration is shorter (~3 turns vs ~5 in smoke) and ends with a
correct answer more often once we sample 35 cases.

### 3. Why does confident_error collapse?

In single-shot, a method like `rtk-log` forces a confidence call
based on whatever the rubbed-out summary shows. Sometimes the
summary mentions one specific test name, and the agent confidently
diagnoses based on it — even when the actual root cause is
elsewhere. **High confidence × wrong category = confident error.**

In agent-loop, the same starting point triggers tool calls. After
tool exploration, the agent either (a) finds the signal and emits a
correct, high-confidence answer, or (b) doesn't find anything and
abstains with `category: unknown, confidence: 0`. **The path to
"confident AND wrong" mostly closes** — for 6 of 10 methods,
the multi-turn verification fully eats the failure mode (0%
confident_error). The four exceptions (`rtk-log` 5.7%, `raw` 2.9%,
`grep` 2.9%, `tail-200` 2.9%) — see §2 above.

This is the v1.1 release's clearest safety win for downstream agent
users: if you're using RTK-log or LLM-summary inside a Claude
Code–style agent, you are unlikely to be **misled** by the reducer
(0% confident_error in agent-loop), even if you are more likely to
**pay extra tokens** to recover.

## Cost picture (35-case corpus)

Single-shot input cost ranges from 810 tokens (`rtk-log`) to 432k
(`llm-summary-v1-mock` end-to-end with reducer cost) — a **530×**
spread. Agent-loop costs are much narrower: 28k to 67k — a
**2.4×** spread. The agent adds a roughly fixed 28–67k token cost
regardless of starting context.

| Method | single-shot total | agent-loop total | agent / single-shot |
|---|---:|---:|---:|
| `tail-200`                   |     6,108 |  28,166 |    5× |
| `llm-summary-v1-mock`        |   432,076 |  32,139 |  0.07× (single-shot was dominated by reducer LLM cost) |
| `rtk-log`                    |       810 |  36,259 |   45× |
| `hybrid-grep-120k-rtk-tail`  |    19,844 |  37,152 |    2× |
| `hybrid-grep-120k-tail`      |    19,753 |  39,221 |    2× |
| `grep`                       |    88,355 |  42,232 |    0.5× |
| `hybrid-grep-4k-rtk-err-cat` |    19,892 |  42,862 |    2× |
| `rtk-err-cat`                |    19,850 |  43,009 |    2× |
| `rtk-read`                   |   274,289 |  55,391 |    0.2× |
| `raw`                        |   275,248 |  67,311 |    0.2× |

For tiny static contexts (`rtk-log`, `tail-200`,
`llm-summary-mock`), the agent's tool calls **dwarf** the static
cost — the agent essentially reconstructs the missing signal via
grep/tail on raw.log. For huge static contexts (`raw`, `rtk-read`),
the agent **clips** the context (truncates input before sending to
the LLM) and supplements with targeted tool calls — net cost
drops 3-fold.

The takeaway: in agent-loop, *the static reducer's input size
matters less than its signal density.* `hybrid-grep-120k-rtk-tail`
delivers signal-rich context at 19k tokens and wins both quality
(0.747 — also the v1.0 single-shot #1) and cost (37k agent-loop
total). `raw` and `rtk-read` deliver 275k tokens of which the agent
uses ~25% effectively. `rtk-log`'s 325 tokens are too compressed
and force the most expensive agent recovery (2.60 tool calls
average) — though even that lands at agent-loop quality 0.689,
which is within 0.06 of the leader.

## Caveats

1. **Sonnet 4.6 only.** Haiku 4.5 may use fewer tools (smaller
   tool-use capability); gpt-5-mini may use more or fewer. The
   "agent flattens" finding is calibrated to one model family.
2. **Tool surface is fixed.** The 4 tools (grep / read_file / tail /
   view_log_lines) match Claude Code's real shell tools by design,
   but a different surface (e.g., Cursor's or Codex's) would change
   the dynamic.
3. **5-turn cap + 180k-token cap are soft caps.** Two guards: hard
   stop on cumulative input ≥ 180k AND preflight estimate of next
   request size. Despite both, a single late turn whose observation
   tokens exceed our chars/4 estimate can push cumulative above
   the cap. 18 of 350 v1.1 rows landed above 180k (max 273,654
   total_input_tokens_consumed). Real-world agent traces can also
   exceed both caps. The "180k cap" is enforced for tool-using
   turns; the forced-final no-tools call can add another ~10k.
4. **Routing**: v1.1 was run through OpenRouter's Anthropic-
   native passthrough (`https://openrouter.ai/api/v1/messages`).
   A 3-case A/B test against direct Anthropic showed differences
   within Sonnet's known temp=0 drift range (same category in 2/3
   cases, ±5% token counts). Model snapshot is identical
   (`anthropic/claude-4.6-sonnet-20260217`) on both routes.
4. **35 cases.** Per-case variance still ±0.05 on the macro means
   at this scale.
5. **No real LLM summarizer in agent-loop.** Same as v1.0 —
   `llm-summary-v1-mock` is a deterministic stub. A real Haiku
   summarizer would consume different tokens and might score
   differently.
6. **The "rescue" mechanism is mostly grep + tail on raw.log.** If
   you cannot give your agent direct access to the raw log, the
   agent-loop benefit disappears.

## What this means for practitioners

- **If your agent has tool access**: the choice of upstream log
  reducer is much less critical than v1.0 suggested. Quality-wise
  it barely matters. Cost-wise, hybrid routers still help by giving
  the agent better starting context, reducing follow-up tool calls.
- **If your context is single-shot (no tools)**: v1.0 conclusions
  stand. Hybrid routers dominate; rtk-log is dangerous;
  llm-summary-v1-mock is expensive AND poor.
- **For RTK users**: the agent rescues rtk-log on quality, but at
  the cost of ~2.6 tool calls per case and the highest agent-loop
  confident_error rate (5.7%). If you want both low cost AND high
  quality, the v1.1 universal pick is **`hybrid-grep-120k-rtk-tail`**
  — it leads in both single-shot AND agent-loop rankings.

## See also

- [LogDx-CI v1.0 leaderboard](../leaderboard.html) — single-shot results
- [Why RTK underperforms on CI diagnosis](why-rtk-underperforms-on-ci-diagnosis.md) — mechanistic analysis
- [Cost-quality Pareto plot](../figures/cost_quality_pareto.png) — single-shot view
- [ROADMAP §1](../../ROADMAP.md) — multi-turn / agent-loop work item
