# M6 experiment — Real fixed debugger

M6 is the first CILogBench milestone that produces meaningful downstream
debugging numbers from a real model. The benchmark loop becomes:

```
CI failure raw.log
  → context provider (raw / tail / grep / rtk-* / llm-summary-*)
  → **fixed** debugger model
  → structured diagnosis JSON
  → deterministic evaluation vs ground truth
  → experiment report
```

## Protocol: one fixed debugger, many contexts

For a single M6 run, **these must stay fixed**:

- diagnoser model name + version
- provider binary / shim (`$DIAGNOSIS_COMMAND`)
- prompt file (`prompts/debugger_v1.md`)
- temperature, top_p, max output tokens, JSON mode
- safe-metadata policy (nothing from ground truth)

**Only `context_method` varies.** Any deviation invalidates the
experiment. If you want to compare prompts or models, start a new run
with a new `diagnoser_name` and a new config — do not mix results.

## Privacy — explicit opt-in

Real contexts may be sent to an external model. The wrapper refuses to
call the command provider unless BOTH:

1. The config has `privacy.requires_explicit_external_llm_opt_in: true`
   (the default for `configs/diagnosers/example.debugger-v1-command.json`).
2. **One of**:
   - `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` in the environment, OR
   - `--allow-external-llm` on the CLI.

`tools/audit_context_privacy.py` runs first and writes
`results/<split>/privacy_audit.json` + `reports/<split>_privacy_audit.md`.
The scan is **best-effort**; a clean audit does not prove a context is
safe to share. Review findings manually.

## Context-size policy

The wrapper never silently truncates. Per the plan, each case × method
has one of these outcomes:

- `completed` — diagnoser returned structured JSON.
- `provider_error` — shim failed; diagnosis body is unknown/unknown/0.
- `unsupported_context_too_large` — context exceeded model limits;
  treat as `provider_error` with an explicit error message; do NOT cut
  the context inside the wrapper.

If you genuinely need a smaller context, ship a new **context method**
(e.g. `raw-truncated-100k`) with its own manifest. Hiding truncation in
the diagnoser breaks the comparison.

## Reproducibility manifest

Every M6 run writes:

```
results/<split>/m6_real_debugger_<diagnoser_name>.manifest.json
```

It captures: config path + SHA-256, prompt path + SHA-256, context
methods requested vs run, case count, privacy audit path, diagnosis
output directory, eval path, report path, `started_at` / `finished_at`,
`git_commit` (or `"unknown"`), and which opt-in channel was used
(`env` / `cli` / `config`).

Changing the config, prompt, or context invalidates the diagnosis cache.

## Running a real model

```bash
# 0. Confirm cases and existing context manifests are clean.
python tools/validate_cases.py cases/dev

# 1. Author a shim that speaks the contract in docs/methods/diagnosis.md.
#    See examples/diagnosis_shim_stub.py for a no-API-key reference.

# 2. Opt in to the external model.
export DIAGNOSIS_COMMAND="/path/to/your_real_shim"
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

# 3. Smoke test one method first.
python tools/run_diagnosis.py --split dev --diagnoser command \
    --diagnoser-name my-debugger-v1 \
    --command "$DIAGNOSIS_COMMAND" \
    --context-method grep --strict

# 4. Full run.
python tools/run_m6_experiment.py \
    --split dev \
    --diagnoser-name my-debugger-v1 \
    --config configs/diagnosers/example.debugger-v1-command.json \
    --context-method all \
    --allow-external-llm
```

Outputs:

```
results/dev/diagnoses/my-debugger-v1/<method>.jsonl
results/dev/diagnoses/my-debugger-v1/<method>/<case>.json
results/dev/eval_diagnosis_my-debugger-v1.json
reports/dev_diagnosis_eval_my-debugger-v1.md           # M5 diagnosis report
reports/dev_m6_real_debugger_my-debugger-v1.md        # M6 experiment report
results/dev/m6_real_debugger_my-debugger-v1.manifest.json
```

## Reading the M6 report

### Signal-vs-diagnosis table

Each row joins an M2–M4 signal-recall eval with an M5–M6 diagnosis
eval for the same context method. Use it to check whether higher
upstream signal preservation correlates with higher downstream
diagnosis accuracy **for this diagnoser and prompt**.

Watch for these patterns:

- High signal recall + low diagnosis category accuracy → the diagnoser
  sees the evidence but mislabels it. Often a prompt / category-enum
  alignment issue, not a context issue.
- Low signal recall + reasonable diagnosis accuracy → the diagnoser
  fills gaps from prior training. Check `valid_evidence_quote_rate` —
  it usually drops when this happens.
- High reduction + high abstention → compression was too aggressive;
  the diagnoser is correctly saying "unknown" rather than guessing.
  Read this as a feature, not a failure.

### Confident-error analysis

Cases where `confidence ≥ 0.70` AND (wrong category OR forbidden
claim). This is the agent-safety failure mode — the diagnoser sounds
sure while being wrong. A non-zero number is worth inspecting before
any user-facing deployment.

### Abstention analysis

Abstention (`unknown` OR `confidence < 0.25`) is not automatically
bad. Pair it with confident-error rate: a healthy debugger uses the
abstention channel when the context is poor.

## Supportable vs unsupportable statements

The 5-case dev split does **not** support claims like:

- "Method X is the best CI log strategy in general."
- "Model A is better than Model B at debugging."
- "RTK is worse than grep" (or vice versa).

It **does** support claims like:

- "On 5 dev cases, with diagnoser `my-debugger-v1` and prompt
  `prompts/debugger_v1.md` (SHA `abcdef…`), method X produced fewer
  confident errors than method Y."
- "On this run, method Z's 99% reduction caused 60% abstention; the
  diagnoser declined to diagnose rather than guessing."

Report differences should always be reported with the prompt SHA, the
config SHA, and the case count.

## When things break

- **Model returns non-JSON**: shim should wrap and re-try once at its
  own layer, OR return an error. The runner records `provider_error`
  and emits an unknown diagnosis. Fix the shim, not the runner.
- **Model hits context length**: mark `unsupported_context_too_large`
  in the shim's returned error. Do not silently truncate.
- **Annotation bug discovered mid-run**: fix the annotation, rerun
  **all** affected methods, and document the fix in
  `docs/annotation_guide.md`. Do not selectively rerun only the
  method that benefits.
- **Non-deterministic provider**: set `model.deterministic: false` in
  config. The M6 report then caveats itself; numbers may drift across
  reruns.

## What M6 does not do

- No MCP / search-agent diagnosis. Planned for M10.
- No LLM judge; evaluation stays deterministic. Semantic grading is a
  later milestone.
- No public leaderboard. Planned after a frozen holdout split (M8).
