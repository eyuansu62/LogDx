# Model card — `llm-summary-v1-haiku`

## Identity

- **Provider:** Anthropic
- **Model family:** Claude Haiku 4.5
- **Alias used:** `haiku`
- **Invoked via:** `claude -p --model haiku --output-format json --system-prompt <map|reduce prompt>`
  (Claude Code CLI, non-interactive print mode)
- **Shim:** `examples/summary_shim_claude_cli.py`
- **Config:** `configs/summarizers/haiku.json`
- **Map prompt:** `prompts/llm_summary_v1_map.md`
- **Reduce prompt:** `prompts/llm_summary_v1_reduce.md`
- **Run date:** 2026-05-02

## Why Haiku

Haiku 4.5 was used as both summarizer and debugger in E3. Reasons:

- Cheapest deterministic option in the Claude family. The full E3 pipeline
  requires summarization on every case before the debugger ever runs;
  using Sonnet/Opus for either side would multiply the cost.
- Same model used in E1 for the debugger, so E3 isolates one variable
  (the new `llm-summary-v1-haiku` context method) without introducing a
  second model.
- Same model on both sides creates a "self-call" pipeline where the
  summarizer and debugger share priors. This is the simplest baseline
  and is meant to anchor future Sonnet-/Opus-summarizer experiments.

## Intended use for E3

First **real** LLM-summary context method on `cilogbench-v1.2`. Purpose
is to compare a real LLM-generated CI failure summary against the locked
deterministic baselines (`raw`, `tail-200`, `grep`, `rtk-read`,
`rtk-log`, `rtk-err-cat`) and the deterministic mock summarizer
(`llm-summary-v1-mock`).

Not a model comparison.

## Decoding / output settings

- `temperature = 0`
- `top_p = 1`
- `max_output_tokens = 1800` (per-stage; map and reduce each cap at this)
- Plain text / Markdown output (the prompt asks for a structured
  Markdown summary; the shim does not enforce JSON).
- `tool_use = false`, `web_access = false`.

## Determinism

Marked `deterministic: false` in the config. The Anthropic API is not
guaranteed byte-stable at temperature 0 across runs. As with the E1
debugger:
- The pipeline caches the first run's summary row by `case_id +
  prompt_version + provider + model + stage` (per
  `tools/run_llm_summary_baseline.py`); rerunning with the same cache is
  byte-stable.
- Rerunning with `--no-cache` may produce different summaries and should
  be reported as a new run with a new timestamp.

## Chunking

- `chunk_lines = 500`, `chunk_overlap_lines = 25` (~6-8k tokens per
  chunk after Markdown noise).
- `on_context_too_large = "chunk"`: oversize logs are chunked and the
  reduce stage merges per-chunk maps.
- `max_chunks = null`: no hard ceiling; the wrapper records
  `chunk_count` per case in metadata.

## Privacy

- The shim sends raw log chunks to the Anthropic API via `claude -p`.
  No ground truth, no failure_category, no required_signals are passed
  — enforced by `tools/run_llm_summary_baseline.py`'s safe-metadata
  allowlist and re-checked in the shim itself.
- The shim does not log API responses to disk beyond the per-case
  summary content the wrapper persists.
- `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` and an explicit
  `--allow-external-llm` flag are both required at the wrapper level.

## Cost accounting

The shim captures `total_cost_usd` and per-stage token counts when the
CLI envelope provides them. Aggregate cost reported in the E3 report's
"Full pipeline cost table".

## Known nondeterminism

- Anthropic API can return slightly different wording for the same
  prompt at temperature 0 across runs.
- `claude -p` includes a small amount of Claude-Code-specific bookkeeping
  in the system context even when `--system-prompt` is set; the
  in-prompt instructions still dominate.
- Map-stage outputs feed the reduce stage; map nondeterminism can
  amplify into reduce-stage variance.

## v1.1 corpus expansion (2026-05-20)

The original E3 run was on a 16-case prototype subset (`dev`,
`holdout`, `stress` v1 splits) with only Haiku 4.5 as the debugger.
v1.1 expanded coverage to:

- **35 cases** (full v1.0 corpus = 16 v1 + 19 v2 cases)
- **4 diagnoser families** (Haiku 4.5, Sonnet 4.6, gpt-5-mini single-
  shot; Sonnet 4.6 agent-loop)
- Same map-reduce config (`chunk_lines=500`, `chunk_overlap_lines=25`,
  `temperature=0`)
- Three cases (one nodejs, two pytest-sklearn) re-chunked at
  `chunk_lines=100` because some 500-line windows exceeded Haiku's
  effective input window after Claude-Code session overhead. Same
  algorithm, smaller chunks; recorded in per-case
  `metadata.chunk_lines`.

Headline result of the v1.1 backfill (`diagnosis_score_v1_1`,
case-weighted macro across 6 splits):

| Diagnoser | mock | haiku | Δ |
|---|---:|---:|---:|
| real-debugger-v1 (Haiku 4.5) | 0.343 | 0.583 | **+0.240** |
| real-debugger-v2 (Sonnet 4.6) | 0.348 | 0.704 | **+0.356** |
| real-debugger-v3 (gpt-5-mini) | 0.294 | 0.608 | **+0.314** |
| real-agent-v1 (Sonnet+tools) | 0.715 | 0.690 | -0.025 |

`llm-summary-v1-haiku` is now the LLM-summary class representative
on the v1.1 headline leaderboard at rank 4 overall (0.632).

## Limitations

- **One summarizer model.** v1.1 fixed the cross-diagnoser gap (the
  real summary is evaluated against 4 different debuggers now), but
  the summarizer itself is still single-model (Haiku 4.5). A
  Sonnet-summarizer / Opus-summarizer comparison would isolate
  "summarizer model" as a separate variable.
- **Same model on both sides for v1-debugger.** Self-call has known
  shared priors when the debugger is also Haiku.
- **High end-to-end cost.** ~1.68M tokens/case (~4× the v1.0 mock
  estimate). Most of the gap is Claude-Code cached-prefix overhead
  the mock didn't simulate.
- **Pricing changes over time.** The cost numbers above are
  informational and not a leaderboard.
