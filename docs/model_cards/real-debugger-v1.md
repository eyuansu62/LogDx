# Model card — `real-debugger-v1`

## Identity

- **Provider:** Anthropic
- **Model family:** Claude Haiku 4.5
- **Alias used:** `haiku`
- **Invoked via:** `claude -p --bare --model haiku --output-format json`
  (Claude Code CLI, non-interactive print mode)
- **Shim:** `examples/diagnosis_shim_claude_cli.py`
- **Config:** `configs/diagnosers/real-debugger-v1.json`
- **Prompt:** `prompts/debugger_v1.md` (SHA recorded in every diagnosis row)
- **Run date:** 2026-04-25

Haiku 4.5 was chosen over Sonnet / Opus to keep the 112-diagnosis run
cheap (Opus 4.7 was tested for one ping and cost $0.095 — scaling to
the full protocol would be >$10).

## Intended use for E1

First real downstream diagnosis run under `cilogbench-v1.1`. Purpose:
compare context methods with the debugger held fixed. NOT a model
comparison — only one debugger in this run.

## Decoding / output settings

- `temperature = 0`
- `top_p = 1`
- `max_output_tokens = 1200`
- JSON-only output requested in the prompt; the shim parses and
  validates the JSON, stripping ` ```json ` fences if the model emits
  them.
- `tool_use: false`, `web_access: false`, `retrieval: disabled` — the
  `--bare` flag skips Claude Code hooks, plugins, and auto-loaded
  context, so the model only sees what the shim passes.

## Determinism

Marked `deterministic: false` in the config. The underlying Anthropic
API is not guaranteed byte-stable at temperature 0 across runs. The
benchmark caches the first run's diagnosis row; rerunning with the
same cache is byte-stable (enforced by the M6-era cache-stores-full-row
fix). Rerunning with `--no-cache` may produce different outputs and
should be reported as a new run with a new timestamp.

## Context-size policy

- `allow_raw_context: true` — Haiku 4.5 has a 200k-token context
  window. The largest case in v1.1 is `pytest-sklearn-stress-001` at
  ~1.1 MB / ~280k chars ≈ 70k tokens, well within the window.
- `allow_truncation: false`. If a future case exceeds the window, the
  shim records `unsupported_context_too_large` instead of silently
  truncating.

## Cost accounting (recorded by `claude -p --output-format json`)

The shim captures `total_cost_usd` and per-model token counts in
`metadata.cost` of each diagnosis row. Aggregate cost reported in the
E1 report's Cost Table.

## Privacy

- The shim sends context + safe metadata to the Anthropic API via
  `claude -p`. No ground truth, no `failure_category`, no
  `required_signals` are passed — this is enforced by the M5 safe-
  metadata allowlist and re-checked in the shim itself.
- The shim does not log the API response body to any file beyond the
  per-case diagnosis JSON it returns to `run_diagnosis.py`.
- `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` and an explicit
  `--allow-external-llm` flag are both required at the wrapper level.

## Known nondeterminism

- Anthropic API can return slightly different wording for the same
  prompt at temperature 0 across runs.
- `claude -p` prepends a Claude-Code-specific system context (the
  `--bare` flag minimizes this but does not eliminate it).

## Limitations

- **One model, one prompt, 16 cases.** Do not quote per-method
  numbers from this card as model quality. See the E1 report
  guardrails.
- **Haiku is smaller than Sonnet or Opus.** Results here are not
  expected to upper-bound what a larger model could achieve; they
  establish the feasibility of the protocol and a baseline to
  compare future runs against.
- The cost table is informational. Haiku 4.5 pricing changes over
  time and the `--bare` flag still includes some non-zero Claude-Code
  overhead in each call.
