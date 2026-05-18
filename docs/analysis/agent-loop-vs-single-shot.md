# Agent loops flatten the gap between context methods (v1.1)

> Follow-up analysis on the [LogDx-CI v1.1](https://logdx-bench.github.io/)
> agent-loop release. Companion to
> [`why-rtk-underperforms-on-ci-diagnosis.md`](why-rtk-underperforms-on-ci-diagnosis.md).
>
> **Headline finding**: in agent-loop usage, the choice of context
> method matters far less for *quality* than in single-shot — the
> score range collapses from 0.42 to 0.074. Cost differences
> persist (1.5× spread in agent-loop vs 530× single-shot), and the
> v1.0 single-shot winner (`hybrid-grep-120k-rtk-tail`) drops to
> agent-loop rank 8 with a non-zero confident_error rate (2.9%).

## TL;DR

LogDx-CI v1.0 measured how 10 log-reduction methods affect LLM
diagnosis quality in a single-shot setting: hand the model the
reduced log once, ask for a diagnosis, score the answer. v1.1 adds
the **agent-loop** measurement: hand the model the reduced log
*plus* 4 deterministic tools (`grep`, `read_file`, `tail`,
`view_log_lines`) operating on the raw log, and let it call them
across up to 5 turns.

Four findings on the 35-case corpus × Sonnet 4.6 agent:

1. **Every method gains. The quality gap collapses ~6×.** Single-shot
   `diagnosis_score_v1_1` ranges from **0.249** (`rtk-log`, worst)
   to **0.670** (`hybrid-grep-120k-rtk-tail`, best) — a 0.42 spread.
   Agent-loop scores compress to **[0.666, 0.740]**, a 0.074 spread.
   `rtk-log` gains the most (+0.42) by being rescued via tool calls;
   no method loses score.
2. **Confident-error mostly collapses.** v1.0 surfaced that
   `rtk-log` and `llm-summary-v1-mock` produce confidently-wrong
   diagnoses on **~13%** of cases (the failure mode
   [discussed in rtk-ai/rtk#1599](https://github.com/rtk-ai/rtk/issues/1599)).
   In agent-loop, 7 of 10 methods sit at **0%** confident_error,
   including `rtk-log` itself. The three exceptions are
   `raw` (5.7%), `llm-summary-v1-mock` (2.9%), and
   `hybrid-grep-120k-rtk-tail` (2.9%) — methods that deliver
   either over-comprehensive content (`raw`'s 275k tokens of full
   log) or pre-structured output that encourages premature
   confidence.
3. **Rankings reshuffle.** v1.0's #1 (`hybrid-grep-120k-rtk-tail`)
   drops to rank 8 in agent-loop. The new winner is
   `hybrid-grep-120k-tail` (single-shot rank 2, agent rank 1, agent
   confident_error 0%); `grep` jumps from single-shot rank 3 to
   agent rank 2 (0.738, 0% confident_error). `tail-200` settles at
   agent rank 4, narrowly trailing.
4. **Cost compresses ~350×, but doesn't vanish.** Single-shot
   input tokens range from 810 (`rtk-log`) to 432k
   (`llm-summary-v1-mock` end-to-end) — a 530× max/min ratio.
   Agent-loop ranges from 48.3k to 71.5k — a 1.5× ratio (so the
   spread shrinks by 530 / 1.5 ≈ 350×). The agent adds a roughly
   fixed ~48–72k token cost regardless of starting context.

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
| `hybrid-grep-120k-rtk-tail` | **0.670** | 0.702 | +0.033 | 0.029 | 2.86 |  60,530 |
| `hybrid-grep-120k-tail` | 0.666 | **0.740** | +0.074 | **0.000** | 2.71 |  56,777 |
| `grep` | 0.639 | 0.738 | +0.099 | **0.000** | 2.80 |  61,394 |
| `tail-200` | 0.614 | 0.722 | +0.108 | **0.000** | 2.80 |  59,047 |
| `hybrid-grep-4k-rtk-err-cat` | 0.573 | 0.720 | +0.147 | **0.000** | 3.20 |  55,287 |
| `rtk-err-cat` | 0.470 | 0.708 | +0.238 | **0.000** | 3.28 |  57,552 |
| `raw` | 0.353 | 0.700 | +0.347 | 0.057 | 2.94 |  71,411 |
| `rtk-read` | 0.349 | 0.726 | +0.377 | **0.000** | 2.89 |  71,450 |
| `llm-summary-v1-mock` | 0.328 | 0.703 | +0.375 | 0.029 | 3.40 |  48,826 |
| `rtk-log` | **0.249** | 0.666 | **+0.417** | **0.000** | 3.97 |  48,334 |

![Agent flattens methods](../figures/agent_flattens_methods.png)

## Interpretation

### 1. Why does the agent rescue weak contexts?

`rtk-log`'s static output averages just **~325 context tokens** —
heavily compressed, missing most of the original signal. Single-shot,
the LLM sees the rubbed-out summary and **confidently misdiagnoses
13% of the time** (per the v1.0.1 confident_error column); it also
abstains on ~20% of cases. In agent-loop, the same starting context
triggers **3.97 tool calls per case** (the highest of any method);
the agent immediately recognizes that the rtk-log output is too
lossy and falls back to `tail(200)` or a targeted `grep` on the
raw log. **By the time the agent diagnoses, it has effectively
reconstructed the grep-style context on the fly.**

Same mechanism for `llm-summary-v1-mock` (3.40 tool calls per case
in agent-loop): the mock summary is deterministic and unhelpful, so
the agent supplements via grep/tail on the raw log.

### 2. Does the agent *hurt* strong contexts?

A 5-case smoke test suggested yes — top single-shot methods
appeared to lose 0.10–0.19 score in agent-loop. But the full
35-case data tells a different story: **every method gains, no
method loses.** The smoke effect was a 5-case sampling artifact.

That said, the **gains are smallest** for already-strong methods:
- `hybrid-grep-120k-rtk-tail` (single-shot #1): +0.033
- `hybrid-grep-120k-tail` (single-shot #2): +0.074
- `grep` (single-shot #3): +0.099

And a related effect emerges: three methods that deliver
comprehensive or pre-structured starting contexts
(`raw`, `hybrid-grep-120k-rtk-tail`, `llm-summary-v1-mock`) are the
**only methods with non-zero agent-loop confident_error rates**
(5.7%, 2.9%, 2.9% respectively); the other seven methods sit at
0%. The mechanism: when the front-loaded context already looks
comprehensive (275k tokens of raw log, a 3-layer hybrid output, or
a pre-digested LLM summary), the agent sometimes reads it
confidently, skips tool verification, and commits to a wrong
category. Front-loading **too much** structure appears to be
slightly counter-productive in agent-loop, where the agent's own
tool surface already provides the fallback.

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
"confident AND wrong" mostly closes** — for 7 of 10 methods,
the multi-turn verification fully eats the failure mode (0%
confident_error). The three exceptions (`raw` 5.7%,
`llm-summary-v1-mock` 2.9%, `hybrid-grep-120k-rtk-tail` 2.9%) are
the methods that deliver enough surface detail to encourage
premature confidence — see §2 above.

This is the v1.1 release's clearest safety win for downstream agent
users: if you're using RTK-log or LLM-summary inside a Claude
Code–style agent, you are unlikely to be **misled** by the reducer
(0% confident_error in agent-loop), even if you are more likely to
**pay extra tokens** to recover.

## Cost picture (35-case corpus)

Single-shot input cost ranges from 810 tokens (`rtk-log`) to 432k
(`llm-summary-v1-mock` end-to-end with reducer cost) — a **530×**
spread. Agent-loop costs are much narrower: 48.3k to 71.5k — a
**1.5×** spread. The agent adds a roughly fixed 48–72k token cost
regardless of starting context.

| Method | single-shot total | agent-loop total | agent / single-shot |
|---|---:|---:|---:|
| `rtk-log`                    |       810 |  48,334 |   60× |
| `llm-summary-v1-mock`        |   432,076 |  48,826 |  0.11× (single-shot was dominated by reducer LLM cost) |
| `tail-200`                   |     6,108 |  59,047 |   10× |
| `rtk-err-cat`                |    19,850 |  57,552 |    3× |
| `hybrid-grep-4k-rtk-err-cat` |    19,892 |  55,287 |    3× |
| `hybrid-grep-120k-tail`      |    19,753 |  56,777 |    3× |
| `grep`                       |    88,355 |  61,394 |    0.7× |
| `hybrid-grep-120k-rtk-tail`  |    19,844 |  60,530 |    3× |
| `raw`                        |   275,248 |  71,411 |    0.3× |
| `rtk-read`                   |   274,289 |  71,450 |    0.3× |

For tiny static contexts (`rtk-log`, `tail-200`,
`llm-summary-mock`), the agent's tool calls **dwarf** the static
cost — the agent essentially reconstructs the missing signal via
grep/tail on raw.log. For huge static contexts (`raw`, `rtk-read`),
the agent **clips** the context (truncates input before sending to
the LLM) and supplements with targeted tool calls — net cost
drops 3-fold.

The takeaway: in agent-loop, *the static reducer's input size
matters less than its signal density.* `hybrid-grep-120k-tail`
delivers signal-rich context at 19k tokens and wins both quality
(0.740) and cost (56.8k agent-loop total). `raw` and `rtk-read`
deliver 275k tokens of which the agent uses ~25% effectively.
`rtk-log`'s 325 tokens are too compressed and force the most
expensive agent recovery (4.0 tool calls average).

## Caveats

1. **Sonnet 4.6 only.** Haiku 4.5 may use fewer tools (smaller
   tool-use capability); gpt-5-mini may use more or fewer. The
   "agent flattens" finding is calibrated to one model family.
2. **Tool surface is fixed.** The 4 tools (grep / read_file / tail /
   view_log_lines) match Claude Code's real shell tools by design,
   but a different surface (e.g., Cursor's or Codex's) would change
   the dynamic.
3. **5-turn cap + 180k-token cap are soft caps.** The token cap is
   checked at the start of each tool-using turn; a single high-cost
   turn (typical for huge-log cases like the v2/stress argocd race-
   conditions case) can push cumulative input above 180k by up to
   ~75k tokens before the loop exits to the forced-final no-tools
   call. 6 of 350 v1.1 rows landed above 180k (max 254,688
   total_input_tokens_consumed). Real-world agent traces can also
   exceed both caps.
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
  the cost of ~4 tool calls per case. If you want both low cost
  AND high quality, route to grep/tail first; use rtk modes only
  in the >120k-token bucket where grep doesn't fit (per the v1.0
  Pareto frontier).

## See also

- [LogDx-CI v1.0 leaderboard](../leaderboard.html) — single-shot results
- [Why RTK underperforms on CI diagnosis](why-rtk-underperforms-on-ci-diagnosis.md) — mechanistic analysis
- [Cost-quality Pareto plot](../figures/cost_quality_pareto.png) — single-shot view
- [ROADMAP §1](../../ROADMAP.md) — multi-turn / agent-loop work item
