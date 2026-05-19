---
title: "Leaderboard"
description: "Method × debugger leaderboard for LogDx-CI v1.0 (35 cases)."
---

# LogDx-CI Leaderboard

[← Home](index.html) · [Citation](cite.html) ·
[Technical report](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)

All scores are case-count-weighted macro `diagnosis_score_v1_1`
aggregated across the **35-case v1.0 corpus** (3 splits: `dev`,
`holdout`, `stress`). The score formula (a calibrated linear
combination of category accuracy, signal-mention recall, file/test
recall, must-mention coverage, valid-evidence-quote rate, with
forbidden-claim and confident-error penalties) is documented in
[`docs/evaluation/diagnosis_eval_v1.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/evaluation/diagnosis_eval_v1.md).

## Overall (35-case corpus, 3 debugger families)

Sorted by overall mean across the three debugger families.
**`confident_error` is the v1.1-calibrated rate** of confidently-wrong
diagnoses (`confidence ≥ 0.70` AND the diagnosis is demonstrably wrong
on multiple fronts) — lower is better. It is the metric closest to
"how often does this method lead an LLM to confidently misdiagnose a
CI failure," which is the failure mode raised in
[rtk-ai/rtk#1599](https://github.com/rtk-ai/rtk/issues/1599).

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Overall | confident_error<br/><sub>(↓ better)</sub> | total_tokens<br/><sub>per case (↓ better)</sub> |
|----:|--------|----------:|----------:|----------:|--------:|--------:|--------:|
| 1 | `hybrid-grep-120k-rtk-tail` | 0.624 | 0.679 | 0.706 | **0.670** | **0.000** | 19,844 |
| 2 | `hybrid-grep-120k-tail`     | 0.610 | 0.730 | 0.658 | **0.666** | 0.010 | 19,753 |
| 3 | `grep`                      | 0.578 | 0.684 | 0.655 | **0.639** | **0.000** | 88,355 |
| 4 | `tail-200`                  | 0.595 | 0.624 | 0.623 | **0.614** | 0.019 | **6,108** |
| 5 | `hybrid-grep-4k-rtk-err-cat`<br/><sub>*(earlier 4k-threshold hybrid; replaced — see report)*</sub> | 0.552 | 0.597 | 0.571 | **0.573** | 0.029 | 19,892 |
| 6 | `rtk-err-cat`               | 0.455 | 0.488 | 0.467 | **0.470** | 0.029 | 19,850 |
| 7 | `raw`                       | 0.324 | 0.368 | 0.367 | **0.353** | **0.000** | 275,248 |
| 8 | `rtk-read`                  | 0.329 | 0.369 | 0.349 | **0.349** | 0.010 | 274,289 |
| 9 | `llm-summary-v1-mock`       | 0.343 | 0.348 | 0.294 | **0.328** | **0.133** | 432,076 |
| 10 | `rtk-log`                  | 0.238 | 0.262 | 0.249 | **0.249** | **0.133** | **810** |

Two layers of finding:

1. **Safety (confident_error)** — the top-3 methods produce zero or
   near-zero confidently-wrong diagnoses. `rtk-log` and
   `llm-summary-v1-mock` mislead a confident LLM on ~13% of cases
   ([rtk-ai/rtk#1599](https://github.com/rtk-ai/rtk/issues/1599)).

2. **Cost (total_tokens)** — `grep` (rank 3) uses **4.5× more tokens
   per case than the top-2 hybrids** while scoring lower. The hybrids
   dominate grep on both axes. `llm-summary-v1-mock` is the **most
   expensive method on the leaderboard at 432k tokens/case** (because
   the summarizer itself burns 430k tokens generating a 1.3k summary,
   pricing it out of any cost-quality consideration).
   See the [cost-quality Pareto plot](#cost-quality-pareto-frontier)
   below for the full picture.

## Cost-quality Pareto frontier

![Cost-quality Pareto frontier for LogDx-CI v1.0](figures/cost_quality_pareto.png)

x-axis is total LLM tokens consumed per case on a log scale
(reducer-internal LLM calls + context delivered to the diagnoser +
diagnoser output). y-axis is the published `diagnosis_score_v1_1`.

The frontier (4 methods, dashed line) is:

| Pareto-optimal method | total_tokens / case | diagnosis_score_v1_1 |
|---|---:|---:|
| `rtk-log`                   |     810 | 0.249 |
| `tail-200`                  |   6,108 | 0.614 |
| `hybrid-grep-120k-tail`     |  19,753 | 0.666 |
| `hybrid-grep-120k-rtk-tail` |  19,844 | 0.670 |

Every other method is **dominated** — some other method achieves at
least as good a score for fewer tokens, or strictly more score for
the same tokens. Most notable dominations:

- `grep` is **dominated by `hybrid-grep-120k-tail`** — same score
  ballpark (0.639 vs 0.666) at **4.5× fewer tokens** (88,355 vs
  19,753). If you're using `grep` today, the 120k-tail hybrid is a
  pure upgrade on both axes.
- `rtk-err-cat` is **dominated by `hybrid-grep-120k-tail`** —
  similar token cost, but the hybrid scores +0.20 higher.
- `llm-summary-v1-mock` is **dominated by every other method on
  the leaderboard**. At 432k tokens/case it's 22× more expensive
  than the hybrids while scoring rank-9. The hidden cost is the
  summarizer itself: 370k input + 60k output tokens to produce a
  1.3k-token summary fed to the diagnoser. Real LLM summarizers
  inherit this overhead; the v1.0 corpus does not have a real-Haiku
  summary run on the 35-case set (see "A note on llm-summary-v1-haiku"
  below).

### Cost breakdown (case-count-weighted macro)

| Method | reducer_in<br/>(LLM input) | reducer_out<br/>(LLM output) | context<br/>(→ diagnoser) | diag_out<br/>(diagnoser output) | **total** |
|---|--:|--:|--:|--:|--:|
| `rtk-log`                   |       0 |      0 |     325 | 485 |     **810** |
| `tail-200`                  |       0 |      0 |   5,569 | 539 |   **6,108** |
| `hybrid-grep-120k-tail`     |       0 |      0 |  19,219 | 534 |  **19,753** |
| `hybrid-grep-120k-rtk-tail` |       0 |      0 |  19,311 | 533 |  **19,844** |
| `rtk-err-cat`               |       0 |      0 |  19,383 | 467 |  **19,850** |
| `hybrid-grep-4k-rtk-err-cat`|       0 |      0 |  19,388 | 504 |  **19,892** |
| `grep`                      |       0 |      0 |  87,862 | 494 |  **88,355** |
| `rtk-read`                  |       0 |      0 | 273,998 | 291 | **274,289** |
| `raw`                       |       0 |      0 | 274,944 | 304 | **275,248** |
| `llm-summary-v1-mock`       | 369,957 | 60,362 |   1,264 | 492 | **432,076** |

`reducer_in` and `reducer_out` are non-zero only for methods that
internally call an LLM (here, `llm-summary-*`). For `grep`/`tail`/
`rtk-*`/`raw` the reducer is a CPU-bound transform with no LLM cost.

Reducer runtime where measured (only available for RTK methods,
which write `external_tool.runtime_ms` into their manifests):

| Method | reducer_runtime |
|---|---:|
| `rtk-read`    |  9.9 ms |
| `rtk-log`     | 18.7 ms |
| `rtk-err-cat` | 35.4 ms |

`grep`/`tail` runtime is unmeasured in v1.0 but is empirically
sub-100ms for every case in the corpus (CPU-bound, single-pass).

### USD cost

USD cost per case is **not reported** in v1.0.1 because the
relevant provider list prices (Anthropic Haiku 4.5, Sonnet 4.6,
OpenAI gpt-5-mini) need to be pinned to a snapshot date and
versioned in the protocol lock for reproducibility. This will
land in v1.1 alongside the multi-turn / agent-loop benchmark
(see [`ROADMAP.md`](https://github.com/eyuansu62/LogDx/blob/main/ROADMAP.md#2--cost--latency-reporting--p0-for-v11)).

## Agent-loop leaderboard  (v1.1)

The single-shot leaderboard above tests **`log → reducer → single LLM
call → answer`**. Real Claude Code / Codex usage looks different: the
model can call follow-up tools when its initial context is missing
something. v1.1 adds the **agent-loop** measurement using a new
diagnoser `real-agent-v1` (Sonnet 4.6, max 5 turns × 4 deterministic
tools: `grep`, `read_file`, `tail`, `view_log_lines` operating on the
raw log).

![Agent-loop narrows the gap between methods](figures/agent_flattens_methods.png)

**Every context method gains in agent-loop, and the score range
collapses ~7× — from 0.42 (single-shot) to 0.059 (agent-loop).**
Weak single-shot methods are rescued by the agent's tool calls;
`rtk-log` gains a massive **+0.44** and `llm-summary-v1-mock` gains
**+0.39** by being supplemented with on-the-fly grep / tail.
Confident-error rates drop to **0%** on 6 of 10 methods (single-
shot's 13% rate for `rtk-log` and `llm-summary-v1-mock` collapses
to 5.7% and 0% respectively); the four non-zero rates (2.9%–5.7%)
are concentrated on methods where the agent commits before
verifying — see § 2 of the
[analysis doc](analysis/agent-loop-vs-single-shot.md).
**v1.0 single-shot #1 (`hybrid-grep-120k-rtk-tail`) is also #1 in
agent-loop** at 0.747, 0% confident_error, lowest tool usage
(0.97/case among non-tail-200 methods) — the most robust method
across both regimes.

### Agent-loop rankings (Sonnet 4.6, 35-case macro)

Sorted by agent-loop `diagnosis_score_v1_1`.

| Rank | Method | single-shot score | agent score | Δ | conf_err | iters/case | tools/case | tokens/case |
|----:|--------|---:|---:|---:|---:|---:|---:|---:|
| 1 | `hybrid-grep-120k-rtk-tail` | **0.670** (single-shot #1) | **0.747** | +0.077 | **0.000** | 1.94 | 0.97 | 37,152 |
| 2 | `hybrid-grep-4k-rtk-err-cat`| 0.573 | 0.737 | +0.164 | **0.000** | 2.37 | 1.40 | 42,862 |
| 3 | `hybrid-grep-120k-tail`     | 0.666 | 0.735 | +0.069 | **0.000** | 1.94 | 1.00 | 39,221 |
| 4 | `rtk-read`                  | 0.349 | 0.735 | **+0.386** | **0.000** | 2.40 | 1.46 | 55,391 |
| 5 | `grep`                      | 0.639 | 0.722 | +0.083 | 0.029 | 2.00 | 1.20 | 42,232 |
| 6 | `llm-summary-v1-mock`       | 0.328 | 0.715 | **+0.387** | **0.000** | 2.51 | 1.88 | **32,139** |
| 7 | `tail-200`                  | 0.614 | 0.710 | +0.096 | 0.029 | 1.66 | **0.69** | **28,166** |
| 8 | `rtk-err-cat`               | 0.470 | 0.708 | **+0.238** | **0.000** | 2.60 | 1.66 | 43,009 |
| 9 | `rtk-log`                  | **0.249** (single-shot #10) | 0.689 | **+0.440** | 0.057 | 2.77 | 2.60 | 36,259 |
| 10 | `raw`                      | 0.353 | 0.688 | +0.335 | 0.029 | 2.51 | 1.68 | 67,311 |

Five layers of finding:

1. **Quality flattens.** Agent-loop scores cluster in [0.688, 0.747]
   — a 0.059 spread (7× tighter than single-shot's 0.42). The
   agent rescues weak contexts via tool calls.
2. **Safety mostly collapses.** Single-shot's 13% confident_error
   on `rtk-log` and `llm-summary-v1-mock` drops to 5.7% and 0%
   respectively. The agent-loop highest is 5.7% (`rtk-log`); 6 of
   10 methods sit at 0%.
3. **Top single-shot method holds.** v1.0 single-shot #1
   `hybrid-grep-120k-rtk-tail` is also #1 in agent-loop (0.747),
   with 0% confident_error AND lowest non-tail tool usage (0.97
   tools/case). **This method is the v1.1 recommendation for both
   static and agent settings.** All three 120k-threshold and 4k
   hybrid variants land in the agent-loop top 3.
4. **Cost differs by 2.4×.** Cheapest agent-loop method is
   `tail-200` at 28.2k tokens/case; most expensive is `raw` at
   67.3k. The range is 2.4× — far smaller than the 530× single-
   shot range (1k–432k), but still meaningful for a fleet of agents.
5. **Tool calls correlate inversely with single-shot quality.** The
   methods that needed the most rescuing (`rtk-log` 2.60 tools,
   `llm-summary-v1-mock` 1.88, `raw` 1.68) are the ones with the
   worst or most-lossy single-shot starting context. The two
   strongest agent-loop performers (`hybrid-grep-120k-rtk-tail`
   0.97, `hybrid-grep-120k-tail` 1.00) need ~1 tool/case.
   `tail-200` uses the FEWEST tools (0.69/case) but lands rank 7
   on quality.

### Agent-loop cost-quality Pareto frontier

![Agent-loop cost-quality Pareto](figures/agent_cost_quality_pareto.png)

In agent-loop, the Pareto frontier compresses dramatically (the
score range is only 0.059 wide). The frontier is essentially:

- `tail-200` — cheapest (28.2k tokens/case) at score 0.710
- `llm-summary-v1-mock` — 32.1k, score 0.715
- `rtk-log` — 36.3k, score 0.689
- `hybrid-grep-120k-rtk-tail` — top score (0.747) at 37.2k tokens

`hybrid-grep-120k-rtk-tail` dominates: top score, 0% confident_error,
and 37k tokens/case (cheaper than every other method except `tail-
200` / `llm-summary` / `rtk-log` — all of which score worse). It
is the v1.1 recommendation for both single-shot AND agent-loop.

### What this means

- **`hybrid-grep-120k-rtk-tail` is the v1.1 universal pick** —
  ranked #1 in BOTH single-shot (0.670) AND agent-loop (0.747),
  0% confident_error in agent-loop, and only 0.97 tool calls/case
  on average. Use this regardless of whether your downstream is
  single-shot or tool-using.
- **If your downstream is a tool-using agent** (Claude Code, Codex):
  the choice of static reducer matters much less for *quality*
  (range collapses 7×). Cost matters more: `tail-200` is the
  cheapest at 28k tokens/case but ranks 7 on quality. The 120k
  hybrids hit the best cost-quality balance.
- **Don't use `rtk-log` or `llm-summary-v1-mock` standalone** — they
  remain dangerous in single-shot (13% confident misclassification
  rate each). In agent-loop the agent rescues them via tool calls,
  but `rtk-log` still carries the highest agent-loop confident_error
  (5.7%) and needs ~2.6 tool calls/case to recover.

For the full mechanism analysis (why agents rescue weak methods
without hurting strong ones, why confident_error vanishes), see
[`docs/analysis/agent-loop-vs-single-shot.md`](analysis/agent-loop-vs-single-shot.md).

### Agent-loop caveats

- **Sonnet 4.6 only**. Haiku 4.5 and gpt-5-mini agent variants are
  v1.2 follow-ups in [ROADMAP](https://github.com/eyuansu62/LogDx/blob/main/ROADMAP.md).
  The "every method gains" finding may be specific to Sonnet's
  tool-use bias and could narrow for smaller models.
- **5-turn cap, 180k cumulative input cap is a *soft* cap.** Two
  guards: (1) hard stop before issuing any tool-using turn once
  cumulative input ≥ 180k; (2) preflight estimate of the next
  request's input tokens — skip the turn if it would cross the cap.
  Despite both, a single late turn whose observation token count
  exceeds our chars/4 estimate can still push cumulative above the
  cap. 18 of 350 v1.1 rows landed above 180k (max 273,654). Costs
  reported in the leaderboard reflect actual usage, not the nominal
  cap.
- **Routing**: v1.1 ran via OpenRouter's Anthropic-native
  passthrough (`https://openrouter.ai/api/v1/messages`). The
  underlying model is identical to direct Anthropic (`anthropic/
  claude-4.6-sonnet-20260217` resolves on both endpoints).
  A 3-case A/B comparison vs Anthropic direct found no extra
  variance beyond Sonnet's inherent temp=0 drift; differences in
  individual rows are within ±5% on token counts and the same
  category in 2/3 cases.
- **Same 35-case corpus** as single-shot. No corpus expansion in v1.1.
- **Non-determinism**: Sonnet 4.6 at temperature=0 still has small
  variance in tool selection across runs. The macro means above are
  stable to ~±0.02; individual case scores can shift more.

## Headline cross-family agreement

The **top-3** under each debugger family separately:

| Family | Top 3 |
|--------|-------|
| Claude Haiku 4.5 | `hybrid-grep-120k-rtk-tail`, `hybrid-grep-120k-tail`, `tail-200` |
| Claude Sonnet 4.6 | `hybrid-grep-120k-tail`, `grep`, `hybrid-grep-120k-rtk-tail` |
| OpenAI gpt-5-mini | `hybrid-grep-120k-rtk-tail`, `hybrid-grep-120k-tail`, `grep` |

**∩ across all 3 families:**
`{hybrid-grep-120k-rtk-tail, hybrid-grep-120k-tail}` —
**both 120k-threshold hybrid routers**, beating every non-hybrid
single-method baseline on at least one family and on the overall
mean.

The **bottom-4 set** also agrees across all three families:
`{raw, rtk-read, rtk-log, llm-summary-v1-mock}` — context that's
either too large (raw / rtk-read on big logs) or too lossy
(rtk-log / mock summary) for the LLM to identify root causes.

## Methodology evolution

`hybrid-grep-4k-rtk-err-cat` (rank 5 overall) was an earlier hybrid
designed in the prototype phase, tuned at a 4k-token primary
threshold. Its successors `hybrid-grep-120k-tail` and
`hybrid-grep-120k-rtk-tail` use a 120k-token threshold with
explicit `rtk_input_truncated` gating and clear the earlier hybrid
by **~10 percentage points** on the 35-case corpus.

See the [technical report §3](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md#3-headline-result--full-table)
for the prototype-vs-formal corpus analysis that motivated the
threshold change.

## A note on `llm-summary-v1-haiku`

A real Anthropic Haiku summarizer (`llm-summary-v1-haiku`) was run
during prototyping on a 16-case subset but **not** re-run on the
full 35-case corpus, so it's not on the headline leaderboard. Its
subset score is 0.490 on Haiku-as-debugger; Sonnet and gpt-5-mini
aren't scored against it (would have required a paid re-run). See
the report §3 for context.

## How to reproduce a number

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# rebuild the .cache/diagnosis/ tree from canonical manifests (one-time)
python3 tools/migrate_cache_keys_codex_2026_06_08.py

# re-run an eval block (deterministic; uses cached diagnoses)
python3 tools/evaluate_diagnosis.py \
    --split v2/dev --diagnoser real-debugger-v3

# the file lands at results/v2/dev/eval_diagnosis_real-debugger-v3.json
# and the per-method macro scores match the breakdown in §3 of the
# technical report.
```

The on-disk split names (`dev`, `holdout`, `stress`,
`v2/dev`, `v2/holdout`, `v2/stress`) reflect two methodology-
development waves during prototyping; both are merged into the
v1.0 corpus. See [the release notes](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md#a-note-on-internal-naming)
for the mapping.

For a **fresh** re-run that hits the OpenAI / Anthropic APIs (not
just cache replay), see the
[reproducibility section in RELEASE_NOTES.md](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md#reproducibility).

## 20 historical exclusions

The eval injects zero-score abstention rows for 20 (split,
diagnoser, method, case) tuples documented in
[`configs/historical_provider_error_exclusions.json`](https://github.com/eyuansu62/LogDx/blob/main/configs/historical_provider_error_exclusions.json).
These correspond to transient model / CLI / API failures during the
2026-04..05 prototype sweeps that were removed by the 2026-06-09 /
2026-06-10 cleanups. Without injection the eval denominator would
artificially shrink, inflating the macro means. The
`validate_eval_manifest_consistency.py` release gate verifies that
every excluded eval row has `diagnosis_success=False` + zeroed
score fields.

## Method references

Methods in the leaderboard are implemented as follows. Methods with
external dependencies are linked to their upstream projects.

| Method | Implementation |
|--------|----------------|
| `raw` | full log handed to the model |
| `tail-200` | last 200 lines |
| `grep` | regex-filtered failure-pattern lines + 3/8 context, see [`docs/methods/diagnosis.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/methods/diagnosis.md) |
| `rtk-read`, `rtk-log`, `rtk-err-cat` | three modes of **[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk)** by rtk-ai. See [`docs/methods/rtk.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/methods/rtk.md) for setup. |
| `llm-summary-v1-mock` | mock summarizer (deterministic stub; the corresponding real-Haiku run is `llm-summary-v1-haiku`, prototype-only) |
| `hybrid-grep-4k-rtk-err-cat` | earlier 4k-threshold hybrid using grep primary + rtk-err-cat fallback (replaced by the 120k hybrids) |
| `hybrid-grep-120k-tail` | grep ≤ 120k tokens else tail-200 |
| `hybrid-grep-120k-rtk-tail` | grep ≤ 120k tokens else rtk-err-cat (if not truncated and ≤ 120k) else tail-200 |

[← Home](index.html) · [Citation](cite.html)
