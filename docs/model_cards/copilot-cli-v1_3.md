# Copilot diagnosers for the v1.3 study

## Purpose

These diagnosers test whether LogDx reducer rankings transfer to current
GitHub Copilot models. They are experimental. They are not part of the frozen
v1.2 results.

## Frozen settings

- Provider: GitHub Copilot
- Observed CLI: `1.0.82`
- Native SDK: `1.0.11`
- Native bundled runtime: `1.0.79`
- Prompt: `prompts/debugger_v1.md`
- Reasoning effort: `low`
- Tools exposed to the model: `0`
- Custom instructions: disabled
- Built-in MCP servers: disabled
- Copilot home: isolated temporary directory per call
- Normal compatibility context cap: `480000` characters
- Native transport: Copilot SDK JSON-RPC with `long_context`
- Native safe prompt cap: `921000` tokens

The requested model comes only from `CILOGBENCH_COPILOT_MODEL`. Each result
records the requested and resolved model. A mismatch fails closed. The cache
identity includes the diagnoser, model, reasoning setting, context mode and
cap, prompt hash, shim hash, config hash, and reduced-context hash.

## Known limits

Compatibility CLI uses its serving system prompt and current date. Native
SDK uses a replacement system message: `Follow the user instruction exactly.
Do not use tools.` The runtime versions also differ. The comparison is not a
controlled test of context size alone, nor identical to the historical panel
using Claude Code CLI (v1/v2) and the OpenAI API (v3).

The compatibility path uses the CLI's structured noninteractive output. The
native path uses the SDK transport because macOS cannot place a million-token
prompt in one process argument. An earlier ACP prototype reported different
models at session creation and prompt execution, so its artifacts were
rejected. The SDK path proves the model at session start, model call, and usage
reporting. It also proves `long_context` and the 922,000-token prompt limit.
Sessions disable tools and the saved metadata reports zero counts. The
evaluated adapter defaulted absent counts to zero, so saved artifacts do not
independently prove explicit zero-tool telemetry. Raw event streams were not
retained. The current adapter rejects absent or invalid counts and retains
verified usage when a response cannot be parsed.

The exact evaluated SDK source is retained under
[`examples/frozen/diagnosis_shim_copilot_sdk_2026_08_30.py`](../../examples/frozen/diagnosis_shim_copilot_sdk_2026_08_30.py)
for audit only. Its SHA is recorded in the report. New calls use the hardened
`examples/diagnosis_shim_copilot_sdk.py`; its different hash invalidates old
cache entries. The native SDK requires Python 3.11+ and its pinned Python
dependencies, not a separate global Copilot CLI installation.

The completed compatibility panel contains 280 rows each for Luna, Terra, and
Sol. Every successful row records a matching requested and resolved model.
GPT-5 Mini is excluded because prompt-mode probes did not expose resolved-model
evidence. The runner rejected those probes and wrote no Mini results.

Oversized contexts were rejected. Two near-limit contexts produced
no usable CLI response after prompt overhead. Their split/method runs used an
effective cap one character below the observed context size so they become
explicit `unsupported_context_too_large` rows. The per-row metadata records
the effective cap. This is a measured transport boundary, not per-case quality
tuning.

The native panel completed 35 raw rows per model. Each model had 31 proven
calls and four explicit `unsupported_context_too_large` rows. The largest
successful counted prompt was 693,398 tokens, so performance at one million
tokens was not measured. The full-corpus raw score improved because 14 extra
cases became accepted. On the same 17 accepted inputs, native raw did not
improve mean scores. System-prompt and runtime differences limit causal claims.
Its full-corpus comparison with hybrid v3 had a 95% interval overlapping zero.
Native recorded downstream cost was about 6.7 times the hybrid cost across
this model mix, excluding local reducer work and frozen-summary preparation.
