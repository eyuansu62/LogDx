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

## Limitations

- **One model on both sides.** Do not quote E3 numbers as "LLM summary
  beats grep" in general — it is one summarizer + one debugger + one
  prompt + 16 cases.
- **Same model on both sides.** Self-call has known shared priors. A
  Sonnet-summarizer/Haiku-debugger experiment is a natural follow-up to
  separate signal from artifact.
- **Pricing changes over time.** The cost numbers in the E3 report are
  informational and not a leaderboard.
