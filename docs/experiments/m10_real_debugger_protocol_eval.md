# M10 experiment — Real fixed debugger on a frozen protocol

M10 is the first time CILogBench evaluates a **real** fixed debugger
against every locked context method over every locked split, under a
version-locked protocol.

Prior milestones isolated specific pieces: M5 built the diagnosis
pipeline with a mock debugger, M6 wrapped a real debugger on dev only,
M7 did the same for a real summarizer, M8 froze v1, M9 added a stress
split into v1.1. M10 puts them together and produces the first
publishable (but still internal) cross-split real-model result.

## Protocol lock

M10 uses the latest frozen protocol:

- **Preferred**: `protocols/legacy/cilogbench-v1.1.lock.json` (3 splits: dev,
  holdout, stress; 16 cases).
- **Fallback**: `protocols/legacy/cilogbench-v1.lock.json` (2 splits; 10
  cases) — only if v1.1 is not yet frozen.

The wrapper refuses to run if the lock fails
`tools/validate_protocol_lock.py`.

## Fixed-debugger principle

In one M10 run:

- diagnoser model + prompt + decoding settings are fixed
- safe-metadata policy is the same M5/M6 allowlist
- context-size policy is declared in the diagnoser config and never
  tweaked per-method
- **only** the context method varies

Different models or different prompts require a new `diagnoser_name`
and a new run; do not mix results across configs.

## Privacy gates

Same posture as M6:

1. `tools/audit_context_privacy.py` on **every context method × every
   split** before any external call. Findings dumped to
   `reports/<split>_privacy_audit.md`.
2. `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` or `--allow-external-llm` must be
   set. The wrapper refuses to invoke a `command` provider without
   opt-in.
3. `--allow-privacy-audit-hits` required to continue when the audit
   fires.

The wrapper never prints full suspected secret values.

## Context-size policy

Silent truncation is forbidden. Allowed per-case outcomes:

- `completed` — normal diagnosis row
- `unsupported_context_too_large` — recorded explicitly in metadata;
  diagnosis body is `unknown` with confidence 0
- `provider_error` — recorded in `metadata.provider_error`

If you want a truncated raw variant, add it as a separate method
(e.g. `raw-truncated-100k`) under a new protocol version. Do not
truncate inside the diagnoser.

## Running

```bash
# 0. Author a real shim per docs/methods/diagnosis.md. For infra smoke-
#    testing, use the built-in stub:
export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_stub.py"
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

# 1. Validate the lock before running anything.
python tools/validate_protocol_lock.py \
    --protocol protocols/legacy/cilogbench-v1.1.lock.json

# 2. Smoke-test one method × one split first.
python tools/run_diagnosis.py --split holdout --diagnoser command \
    --diagnoser-name stub-debugger-v1 \
    --command "$DIAGNOSIS_COMMAND" \
    --context-method grep --strict

# 3. Full frozen-protocol run.
python tools/run_protocol_diagnosis_eval.py \
    --protocol protocols/legacy/cilogbench-v1.1.lock.json \
    --diagnoser-config configs/diagnosers/stub-debugger-v1.json \
    --diagnoser-name stub-debugger-v1 \
    --context-methods all \
    --allow-external-llm
```

Outputs:

```
results/<split>/diagnoses/<diagnoser>/<method>.jsonl           per-case diagnosis
results/<split>/diagnoses/<diagnoser>/<method>/<case>.json     per-case json
results/<split>/eval_diagnosis_<diagnoser>.json                per-split eval
reports/<split>_diagnosis_eval_<diagnoser>.md                  per-split M5 report
results/<protocol_id>_real_debugger_<diagnoser>.manifest.json  run manifest
reports/<protocol_id>_real_debugger_<diagnoser>.md             M10 experiment report
```

## M10 report structure

The wrapper renders a 14-section report:

1. Experiment summary
2. Protocol lock summary (SHA, splits, cases)
3. Diagnoser config summary
4. Model card link
5. Privacy audit summary
6. Per-split diagnosis metric tables
7. Signal-vs-diagnosis comparison
8. Cost and token table
9. Confident-error analysis
10. Abstention analysis
11. Unsupported-context analysis
12. Per-case hard failures
13. Dev/holdout/stress gap analysis (reuses `compare_splits.py`)
14. Interpretation guardrails

## Reproducibility manifest

Recorded in
`results/<protocol_id>_real_debugger_<diagnoser>.manifest.json`:

- `protocol_id`, `protocol_lock_path`, `protocol_lock_sha256`
- `diagnoser_name`, `diagnoser_config_path`, `diagnoser_config_sha256`
- `debugger_prompt_path`, `debugger_prompt_sha256`
- `splits`, `context_methods`, `case_count_by_split`
- `diagnosis_output_dirs`, `eval_paths`
- `started_at`, `finished_at`, `git_commit`, `working_tree_dirty`
- `opt_in_source` (env | cli | config)

Reruns with the same inputs must produce byte-identical per-case
diagnosis rows (guaranteed by the M6-era cache-stores-full-row fix).

## Supportable / unsupportable claims

M10 supports claims of the form:

> "Under `cilogbench-v1.1`, with diagnoser `stub-debugger-v1` (prompt
> SHA `abc…`, config SHA `def…`), method X had lower confident-error
> rate on stress than method Y (N cases each)."

M10 does **not** support claims like:

- "Method X is the best CI debugging strategy in general."
- "Model A outperforms model B at CI debugging."
- Cross-model conclusions from a single M10 run.

Real comparative claims need ≥2 diagnoser runs (different models,
same prompt) and the same corpus — that is future work.

## Known limitations

- **Case count is small.** Even at 16 cases, a single case flipping
  can move macro metrics by 6-25 pp. Report patterns, not rankings.
- **Deterministic scoring is a proxy.** Category accuracy +
  critical-signal mention + forbidden-claim detection catch the
  obvious failure modes but can miss valid paraphrases. M11 adds
  human review to calibrate.
- **One prompt version.** All M10 runs use `prompts/debugger_v1.md`.
  Prompt sensitivity is a separate experiment.
- **Stub-only M10 runs are infrastructure validation**, not method
  quality. Mark them as such in any writeup.
