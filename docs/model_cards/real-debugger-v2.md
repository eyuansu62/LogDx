# Model card — `real-debugger-v2`

## Identity

- **Provider:** Anthropic
- **Model family:** Claude Sonnet 4.6
- **Alias used:** `sonnet`
- **Invoked via:** `claude -p --bare --model sonnet --output-format json`
  (Claude Code CLI, non-interactive print mode)
- **Shim:** `examples/diagnosis_shim_claude_cli.py`
  (same shim as `real-debugger-v1`; `CILOGBENCH_CLAUDE_MODEL=sonnet`)
- **Config:** `configs/diagnosers/real-debugger-v2.json`
- **Prompt:** `prompts/debugger_v1.md` (same prompt as v1; SHA recorded in every diagnosis row)
- **Run date:** 2026-05-03

Sonnet 4.6 was chosen over Haiku 4.5 (`real-debugger-v1`) and Opus 4.7
to test E6's model-stability question at one step up from v1: same
prompt family, same shim, just a stronger model. Opus is the natural
follow-up if E6 is inconclusive.

## Intended use for E6

Replication run under `cilogbench-v1.3` to test whether the locked
`hybrid-grep-4k-rtk-err-cat-v1` baseline retains its E5 advantage
against grep / RTK / raw / tail when the debugger model changes. NOT
a model comparison in any other sense — only one new debugger in this
run, and the prompt + evaluator + scoring are held fixed.

## Decoding / output settings

- `temperature = 0`
- `top_p = 1`
- `max_output_tokens = 1200`
- JSON-only output requested in the prompt; the shim parses and
  validates the JSON, stripping ```` ```json ```` fences if the model
  emits them.
- `tool_use: false`, `web_access: false`, `retrieval: disabled` — the
  shim invokes `claude -p --system-prompt <prompt>` to override Claude
  Code's default agentic system prompt entirely, so the model only sees
  the debugger prompt and the per-case payload.

## Determinism

Marked `deterministic: false` in the config. The Anthropic API is not
guaranteed byte-stable at temperature 0 across runs. The benchmark
caches the first run's diagnosis row keyed on the row hash; rerunning
with the same cache is byte-stable (enforced by the M6-era cache-stores-
full-row fix). Rerunning with `--no-cache` may produce different
outputs and should be reported as a new run with a new timestamp.

## Context-size policy

- `allow_raw_context: true` — Sonnet 4.6 has a 200k-token context
  window. The largest case in v1.3 is `pytest-sklearn-stress-001` at
  ~1.1 MB / ~280k chars ≈ 70k tokens, well within the window.
- `allow_truncation: false`. If a future case exceeds the window, the
  shim records `unsupported_context_too_large` instead of silently
  truncating.

## Cost accounting

The shim captures `total_cost_usd` and per-stage token counts from the
`claude -p --output-format json` envelope when available. Aggregate cost
is reported in the E6 report's "Cost / token" table. Sonnet pricing is
roughly 5–10× Haiku at the time of this run.

## Privacy

- The shim sends context + safe metadata to the Anthropic API via
  `claude -p`. No ground truth, no `failure_category`, no
  `required_signals` are passed — enforced by the M5 safe-metadata
  allowlist and re-checked in the shim itself.
- The shim does not log API responses to disk beyond the per-case
  diagnosis JSON it returns to `run_diagnosis.py`.
- `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` and an explicit
  `--allow-external-llm` flag are both required at the wrapper level.

## Known nondeterminism

- Anthropic API can return slightly different wording for the same
  prompt at temperature 0 across runs.
- `claude -p` includes a small amount of Claude-Code-specific
  bookkeeping in the system context even when `--system-prompt` is
  set; the in-prompt instructions still dominate.

## Limitations

- **Same prompt family.** Replication is "model swap, prompt fixed";
  it does not test alternative debugger prompts.
- **One new model.** Opus 4.7 was not tested in this run.
- **Same evaluator and scoring as v1.** sv1.1 calibration came from E2b
  expert-model labels collected against `real-debugger-v1` outputs;
  the calibration may not transfer perfectly to a stronger debugger.
- **Cost.** Per-token cost is materially higher than Haiku; the cost
  table is informational and may shift.
