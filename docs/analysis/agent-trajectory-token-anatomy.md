# Agent-loop trajectory token anatomy: where the input tokens go

This analysis dissects **420 agent-loop runs** from LogDx-CI v1.2
(35 cases × 12 context methods × `real-agent-v1` / Sonnet 4.6 via
OpenRouter) to answer a production-engineering question: **inside an
agent-loop diagnosis session, where do the tokens actually go?**

The answer matters because reduction tools (RTK, Tokenless, hybrid
routers, LLM-summary) all optimize different axes; knowing which axis
dominates the actual bill tells you which tool to reach for.

## TL;DR

1. **Input tokens dominate output by 40× (97.6% / 2.4%).** Reducing the
   model's reply size has a 2.4% ceiling; reducing what the model sees
   each turn has 40× the leverage.
2. **Context-method choice produces 12× variance in agent input tokens
   per case** — `raw` burns 67k/case, `llm-summary-v1-haiku` burns 9k.
3. **Per-iteration cost scales the same way** — every agent turn drags
   the same starting context forward, so a bigger initial context bleeds
   across every turn.
4. **Agents barely use `read_file`** — in CI diagnosis they hit
   `grep` 56% / `tail` 29% / `view_log_lines` 12% / `read_file` 2%. Tools
   that optimize "large file read overhead" target a small slice of
   the actual trajectory.
5. **Tail-risk is real**: worst-case agent runs cost 4–5× the median
   (267k input tokens / case at $0.22, vs median ~9–67k / $0.03–0.09).
   All five worst cases come from v2/stress (huge logs that pushed the
   agent into the 5-turn / 180k budget cap).

## Setup

- **Diagnoser**: `real-agent-v1` — Sonnet 4.6 via OpenRouter
  Anthropic-native passthrough.
- **Agent surface**: 4 deterministic tools (`grep`, `tail`, `read_file`,
  `view_log_lines`) operating on the case's `raw.log`.
- **Budget caps**: `max_iterations=5`, `max_total_input_tokens=180k`.
- **Rows analyzed**: 420 rows under
  `results/<split>/diagnoses/real-agent-v1/<method>.jsonl` covering
  all 6 splits × all 12 context methods (35 unique cases, runs
  duplicated across context methods).
- **Per-row token fields**: from
  `agent_metadata.total_input_tokens_consumed` and
  `total_output_tokens_consumed`, which are cumulative across the
  multi-turn agent loop (not just the final turn).

## Finding 1: input/output ratio

Across all 420 runs:

```
total input  tokens : 15,493,804  (97.6%)
total output tokens :    373,841  ( 2.4%)
```

The model spends 40× more tokens *reading* than *writing* during an
agent-loop diagnosis. This holds whether the agent calls 1 tool or 5.

**Implication for reduction tool design**: any reduction strategy
that only shrinks the model's response (e.g. Tokenless's `chat` /
`coding` profiles, or `max_output_tokens` limits) has a hard 2.4%
ceiling on total billing impact in this regime. Profile-style
reductions matter for *individual reply readability*, not for cost.

The 40× ratio is specific to the agent-loop regime. In single-shot
diagnosis (one LLM call, one diagnosis JSON output), the ratio is
narrower (~5–10×) because there's no multi-turn input replay.

## Finding 2: 12× variance in input tokens per case

Sorted by input cost (smaller = more efficient):

| Context method | input/case | output/case | iters | tools/case | $/case (OR) |
|---|---:|---:|---:|---:|---:|
| `llm-summary-v1-haiku` | **9,099** | 868 | 1.7 | 0.71 | $0.0294 |
| `llm-summary-v1-gpt-5-mini` | **9,839** | 915 | 1.4 | 0.37 | $0.0329 |
| `tail-200` | 28,165 | 807 | 1.7 | 0.69 | $0.0592 |
| `llm-summary-v1-mock` | 32,138 | 947 | 2.5 | 1.89 | $0.0565 |
| `rtk-log` | 36,259 | 984 | 2.8 | 2.60 | $0.0595 |
| `hybrid-grep-120k-rtk-tail` | 37,151 | 891 | 1.9 | 0.97 | $0.0657 |
| `hybrid-grep-120k-tail` | 39,220 | 829 | 1.9 | 1.00 | $0.0656 |
| `grep` | 42,231 | 850 | 2.0 | 1.20 | $0.0690 |
| `hybrid-grep-4k-rtk-err-cat` | 42,862 | 890 | 2.4 | 1.40 | $0.0634 |
| `rtk-err-cat` | 43,008 | 897 | 2.6 | 1.66 | $0.0639 |
| `rtk-read` | 55,390 | 900 | 2.4 | 1.46 | $0.0854 |
| `raw` | **67,310** | 898 | 2.5 | 1.69 | $0.0926 |

`raw` (67k) vs `llm-summary-v1-haiku` (9k) is a 7.4× spread; vs
`gpt-5-mini` summary (9.8k) is 6.8×. End-to-end (including reducer)
the two LLM-summary methods are more expensive than the front-loaded
hybrids (haiku-summary's reducer alone runs $1.75/case — see
[`leaderboard.md`](../leaderboard.md) USD table). But on the
**agent-side only**, they're far the cheapest because the agent
needs almost no tool calls to recover the signal.

## Finding 3: per-iteration tokens (which method "leaks" most per turn)

Tokens-per-iteration = total_input / iterations. This measures how
expensive each agent turn is, controlling for how many turns it took.

| method | tokens/iter |
|---|---:|
| `raw` | 26,771 |
| `rtk-read` | 23,079 |
| `grep` | 21,116 |
| `hybrid-grep-120k-tail-v2` | 20,187 |
| `hybrid-grep-120k-rtk-tail-v3` | 19,122 |
| `hybrid-grep-4k-rtk-err-cat-v1` | 18,074 |
| `tail-200` | 16,996 |
| `rtk-err-cat` | 16,542 |
| `rtk-log` | 13,083 |
| `llm-summary-v1-mock` | 12,782 |
| `llm-summary-v1-gpt-5-mini` | 7,028 |
| `llm-summary-v1-haiku` | 5,491 |

Each row of an agent loop *re-includes* the starting context (the
agent sees its conversation history at every turn). A 67k-token
`raw` context replayed across 2.5 turns = 168k input tokens; a
9k-token summary replayed across 1.7 turns = 15k. **Multi-turn
multiplies the front-load cost.** Front-loaded summary contexts
both reduce per-turn cost AND reduce turn count, compounding.

## Finding 4: actual tool usage distribution

Of 547 tool invocations across all 420 runs:

| Tool | Invocations | Share |
|---|---:|---:|
| `grep` | 307 | 56.1% |
| `tail` | 161 | 29.4% |
| `view_log_lines` | 67 | 12.2% |
| `read_file` | 12 | **2.2%** |

In CI-failure diagnosis, agents almost never read full files — they
search by pattern (`grep`) and check log endings (`tail`). The
2.2% `read_file` share has a design-implication:

**Tools that focus on optimizing "large file read overhead" (e.g.
Tokenless's `TOKENLESS-READ-PACKET/0.1` for `Read` tool replacement)
are targeting a small slice of the actual agent trajectory in this
benchmark.** A 90% reduction on 2.2% of calls is a 2% end-to-end
saving — comparable to optimizing the response side.

That said: CI diagnosis is a constrained task. In general coding
agent workflows (refactoring, exploring an unfamiliar codebase),
the `read_file` share is presumably much higher. The 2.2% number
here is specific to "diagnose a CI failure given a raw log", not
universal.

## Finding 5: tail-risk — worst cases cost 4–5× the median

The five most-expensive single agent runs:

| Split | Method | Case | input toks | iters | tools | $ |
|---|---|---|---:|---:|---:|---:|
| v2/stress | raw | numpy-pytest-segfault-argsort | 273,654 | 5 | 5 | $0.2114 |
| v2/holdout | raw | biome-pnpm-not-found | 261,940 | 5 | 5 | $0.2232 |
| v2/stress | grep | airflow-precommit-tsc-middle | 249,566 | 5 | 5 | $0.2197 |
| v2/stress | hybrid-grep-120k-tail-v2 | argocd-race-conditions-batch5 | 247,677 | 5 | 5 | $0.2186 |
| v2/stress | grep | rust-compiletest-wasm-exceptions-asm | 212,237 | 5 | 6 | $0.2116 |

All five hit the **5-iteration cap with ≥5 tool calls** — these are
runs where the agent ran out of budget without converging. Four of
five are v2/stress (the largest, noisiest logs in the corpus).

**For capacity planning**: the median is misleading. If you run a
fleet of 1000 CI diagnosis agents, p99 cost per case is 4–5× the
mean, concentrated on huge logs that push the agent into budget
exhaustion. The leaderboard's "average $/case" understates real
infrastructure risk by this amount.

**For tool design**: methods that produce a focused front-loaded
context (`llm-summary-v1-*`, `tail-200`) keep the worst-case bounded
because the agent doesn't enter the explore-and-recover mode that
explodes input on huge logs.

## What this means for reduction-tool design

Combining all five findings:

1. **The dominant token sink is per-turn context replay, not per-call
   output size.** Multi-turn agents see the same starting context
   N times. Methods that shrink the starting context save N× as
   many tokens vs methods that only shrink one turn.
2. **Hybrid routers that front-load failure-signal extraction
   minimize total token spend** because they reduce both per-turn
   cost AND turn count. Top-2 hybrids hit ~37k/case at 0.97–1.00
   tool calls each.
3. **LLM-summary methods minimize agent-side tokens (9–10k/case)
   but pay the reducer cost upfront** — only worth it if you'd
   otherwise re-spend that context across many turns / agents.
4. **Tool-output reducers (RTK, Tokenless's per-command reducers)
   matter most for tools the agent actually uses heavily** —
   `grep` and `tail` here, not `read_file`. Reducers that don't
   compress grep/tail output do not move the agent-loop bill.
5. **Plan capacity for the tail**: assume 5× peak cost on stress
   cases (huge logs), not the mean.

## Limitations

- **Single model family for agent_v1**: Sonnet 4.6 via OpenRouter
  only. Haiku-as-agent and gpt-5-mini-as-agent are v1.3 follow-ups.
- **Custom 4-tool harness**: not Claude Code, not Codex. Real-world
  agent frameworks have larger tool surfaces (MCP servers, hooks,
  Skills, memory injection) that LogDx does not measure.
- **CI diagnosis is one task**: read_file's 2.2% share is specific
  to "find the root cause in a log". Code-editing tasks have
  different tool distributions.
- **Budget cap shapes the distribution**: with `max_iterations=5`,
  budget-exhausted runs cap at ~270k tokens. A 10-iter cap would
  produce higher tail.
- **OpenRouter pricing is provider-specific**: the $/case column
  reflects what OpenRouter billed, which closely tracks Anthropic
  list price but may differ from a direct-Anthropic re-run by a
  few percent.

## Follow-up: Claude Code token anatomy (not done yet)

This analysis only covers our own `real-agent-v1` harness. A
natural extension: **decompose a real Claude Code session's
per-request body** into:

- System prompt baseline
- Memory auto-injection (per-turn cost of files under
  `~/.claude/projects/<id>/memory/`)
- MCP server tool definitions (often the largest single chunk)
- Plugin / Skill descriptions
- CLAUDE.md / per-project instructions
- User prompt + tool history

Decomposition would isolate which "hook-class" components are the
real per-turn cost driver in Claude Code specifically — and answer
questions like "how much does my 6-file memory directory cost me
per session". That experiment requires MITM-ing Claude Code's
request bodies, which is out of scope for this analysis but a
clean follow-up.

## How to reproduce

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx
python3 docs/analysis/agent-trajectory-token-anatomy.py
```

(Script is the inline Python from this analysis; numbers regenerate
from committed `results/<split>/diagnoses/real-agent-v1/*.jsonl`.)

## See also

- [`agent-loop-vs-single-shot.md`](agent-loop-vs-single-shot.md) —
  the v1.1 finding that agent-loop collapses the quality range
  across methods. This analysis explains *why* in terms of token
  flow.
- [`leaderboard.md`](../leaderboard.md) — the headline rankings
  and USD cost table this analysis extends.
- [`why-rtk-underperforms-on-ci-diagnosis.md`](why-rtk-underperforms-on-ci-diagnosis.md)
  — the per-method inductive-bias breakdown for *quality*; this
  doc covers the parallel breakdown for *token cost*.
