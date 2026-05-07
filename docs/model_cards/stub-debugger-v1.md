# Model card — `stub-debugger-v1`

**Not a real model.** This card documents the CILogBench infrastructure
stub so M10 can run end-to-end without an API key. Real debugger runs
should have their own model card (e.g. `claude-sonnet-debugger-v1.md`)
describing an actual model.

## Identity

- Shim: `examples/diagnosis_shim_stub.py`
- Version: v1
- Determinism: deterministic — a pure keyword-matching Python script
  with no network access and no randomness
- Date: see `results/<split>/m6_real_debugger_stub-debugger-v1.manifest.json`
- Prompt: `prompts/debugger_v1.md` (hash recorded in every diagnosis
  row under `metadata.prompt_sha256`)

## Intended use

Infrastructure verification only:

- Smoke-test `tools/run_protocol_diagnosis_eval.py` on all splits
  without needing `$ANTHROPIC_API_KEY` / `$OPENAI_API_KEY` etc.
- Confirm that the external-LLM opt-in gate, privacy audit, manifest,
  and reports render correctly.
- Verify reproducibility: stub diagnoses should be byte-stable across
  reruns once the cache is populated.

## Decoding / output settings

- temperature = 0, top_p = 1
- max_output_tokens = 1200
- json_mode = true (stub always emits valid diagnosis JSON)
- tool_use = false, web_access = false

## Context-size policy

- `allow_raw_context: true` — stub has no token limit; raw logs up to
  ~50 MB are fine.
- `allow_truncation: false`
- `on_context_too_large: mark_unsupported` — would mark unsupported
  if a real model hit a limit, but the stub never does.

## What stub numbers mean

Metrics from this shim reflect a deterministic keyword heuristic
equivalent to a small rule table. They are not model quality. Do not
cite them.

## Nondeterminism

None. Running the same context through the stub twice produces
identical JSON (byte-equal).

## Privacy

The stub does not call any external service; it reads stdin, runs a
local regex table, and writes to stdout. No CI log ever leaves the
host. This is by design — to give us a working `$DIAGNOSIS_COMMAND`
that the privacy audit and opt-in gate can exercise without network
risk.

## How to swap this for a real model

1. Author a shim that accepts the same stdin JSON and returns the same
   stdout JSON (see `docs/methods/diagnosis.md`).
2. Copy this config to
   `configs/diagnosers/<real-slug>.json`, change `diagnoser_name`,
   update `model.{provider_name,model_name,model_version}`, and set
   `deterministic: false` if the provider does not honor
   `temperature=0`.
3. Write a real model card at
   `docs/model_cards/<real-slug>.md` before running — not after.
4. `export DIAGNOSIS_COMMAND="/path/to/real_shim"`,
   `export CILOGBENCH_ALLOW_EXTERNAL_LLM=1`, then re-run
   `tools/run_protocol_diagnosis_eval.py` with the new config.
