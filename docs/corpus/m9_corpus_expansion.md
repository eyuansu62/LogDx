## M9: corpus expansion overview

M9 expands CILogBench from a 5+5 dev/holdout split into a three-way
corpus with a stratified **stress** split, and freezes the result as
`cilogbench-v1.1`.

### What changed

| | v1 | v1.1 |
|---|---|---|
| splits | `dev`, `holdout` | `dev`, `holdout`, `stress` |
| dev cases | 5 | 5 (unchanged) |
| holdout cases | 5 | 5 (unchanged) |
| stress cases | — | 6 |
| protocol lock | `protocols/cilogbench-v1.lock.json` | `protocols/cilogbench-v1.1.lock.json` (new file; v1 is never modified) |
| tag schema | — | `schemas/case_tags.schema.json` |
| corpus tools | — | `tools/{import_case_skeleton, tag_cases, validate_case_tags, summarize_corpus, check_split_balance}.py` |

`protocols/cilogbench-v1.lock.json` is **unchanged**. Any benchmark
result produced against v1 continues to be reproducible with
`tools/validate_protocol_lock.py --protocol protocols/cilogbench-v1.lock.json`.

### What did NOT change

- `cases/dev/` — same 5 cases.
- `cases/holdout/` — same 5 cases.
- All schemas that are part of v1: `case.schema.json`,
  `ground_truth.schema.json`, `method_output.schema.json`,
  `diagnosis.schema.json`, `diagnosis_eval.schema.json`. A hash change
  there would silently invalidate every v1 result.
- All v1 prompts (`llm_summary_v1_{map,reduce}.md`, `debugger_v1.md`).
- All v1 evaluators (`evaluate_signal_recall.py`, `evaluate_diagnosis.py`).
- Baseline parameters (tail=200, grep regex/before/after, RTK methods,
  `llm-summary-v1-mock`).

### Stress split composition

6 real GHA cases covering 4 failure categories, 2 frameworks, 2 size
buckets, and 3 signal positions. See
`docs/corpus/stress_case_selection.md` for per-case rationale and
known gaps.

### How v1.1 freezes

```bash
python tools/build_split_manifest.py --split all
python tools/freeze_protocol.py --protocol-id cilogbench-v1.1 \
    --splits dev,holdout,stress
python tools/validate_protocol_lock.py --protocol protocols/cilogbench-v1.1.lock.json
```

The v1.1 lock inherits every schema/prompt/evaluator hash from v1
(they are unchanged) and adds the stress split manifest. If any of the
v1-locked files drifts, `validate_protocol_lock.py` fails on both
locks.

### Running the benchmark under v1.1

```bash
# 1. Corpus sanity.
python tools/validate_cases.py cases/dev
python tools/validate_cases.py cases/holdout
python tools/validate_cases.py cases/stress
python tools/validate_case_tags.py --split all

# 2. Locked baselines on stress.
python tools/run_locked_eval.py \
    --protocol protocols/cilogbench-v1.1.lock.json \
    --split stress \
    --methods raw,tail-200,grep,rtk-read,rtk-log,rtk-err-cat,llm-summary-v1-mock

# 3. Mock diagnosis on stress.
python tools/run_diagnosis.py --split stress --diagnoser mock --context-method all
python tools/evaluate_diagnosis.py --split stress --diagnoser debugger-v1-mock
python tools/render_diagnosis_report.py --split stress --diagnoser debugger-v1-mock

# 4. 3-way comparison.
python tools/compare_splits.py \
    --protocol protocols/cilogbench-v1.1.lock.json \
    --splits dev,holdout,stress \
    --diagnoser debugger-v1-mock
```

### Interpretation guardrails

M9 can support statements like:

> "Under `cilogbench-v1.1`, method X has a 30-percentage-point signal-recall
> gap between dev and stress, concentrated in the `large/late` bucket."

M9 cannot support statements like:

> "Method X is the best CI debugging method."

Reasons:

- stress is *intentionally* adversarial — scoring high on dev does
  not imply scoring high on stress, but scoring low on stress does not
  prove the method is bad either.
- 16 cases total is still small.
- mock diagnoser numbers validate the pipeline, not real model quality.
- evidence-based scoring is a proxy for semantic correctness, nothing
  more.

Real-model downstream comparison lives in M10, which uses the v1.1
lock as input.
