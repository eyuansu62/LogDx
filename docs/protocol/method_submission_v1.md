# Method submission policy — v1

How to add a new method to CILogBench v1 without corrupting the
benchmark.

## What "method" means

CILogBench recognizes four method kinds:

| kind | what it produces | lives at |
|---|---|---|
| `context_provider` | takes `raw.log` (or another method's output) and emits a compact context | `results/<split>/<method>.jsonl` |
| `summarizer` | takes `raw.log` and produces a compact markdown summary (a specialized context provider) | `results/<split>/<method>.jsonl` |
| `diagnoser` | takes one method's context and produces a structured diagnosis | `results/<split>/diagnoses/<diagnoser>/<method>.jsonl` |
| `end_to_end` | takes `raw.log` and produces a final diagnosis in one step (reserved for future MCP / agent baselines) | TBD |

Each method must declare which kind it is in its submission.

## Required metadata for each method

Submissions must include (via a config under `configs/<kind>/` or a
commit message on the introducing PR):

- `name` (slug form used in paths)
- `kind` (one of the four above)
- `version`
- `command` or `implementation path`
- `parameters` (any tunable knobs, with their frozen values)
- `uses_external_apis` (yes/no)
- `consumes_raw_log` (yes/no)
- `consumes_other_method_output` (yes/no, and which method if so)
- `line_mapping` (yes/no — do outputs carry original line ranges?)
- `privacy_notes` (what the method sees, what it sends externally)
- `runtime_cost_notes` (approx CPU / token / USD per case)

## Hard rules

Every non-evaluator method must NOT read:

- `cases/<split>/<case_id>/ground_truth.json`
- `required_signals`, `evidence_spans`, `expected_diagnosis`
- `failure_category` from `case.json`
- any eval JSON (`eval_*.json`, `eval_diagnosis_*.json`)

Evaluators (`tools/evaluate_*.py`) are the only components allowed to
read ground truth.

## Safe metadata ONLY

Methods may receive — per case — this subset of `case.json`:

```
case_id, repo, source, workflow_name, job_name, framework
```

Nothing more. The M5/M6/M7 runners enforce this by constructing the
safe-metadata blob before handing off to the provider.

## Versioning inside method names

- Context-provider + summarizer method names include a version suffix.
  Example: `llm-summary-v1-<slug>`. The `mock` slug is reserved.
- Diagnoser names also include a version suffix. Example:
  `debugger-v1-<slug>` or `<model-slug>-debugger-v1`. Never include API
  keys, account IDs, or private endpoint names in the slug.
- Protocol versions are independent. A method being added under v1
  does not imply v1 endorsement; see "protocol lock" below.

## Protocol lock interaction

Adding a new method does NOT change the v1 protocol lock unless the
method is added to the lock's `baselines` block. Two valid ways to
ship a new method:

1. **Report-only**: add the method to the repo, run it against
   dev + holdout, include the numbers in a standalone experiment
   report. The v1 lock is untouched. The method is not a v1 baseline.
2. **Baseline addition**: bump the protocol (`cilogbench-v1.1` or
   `cilogbench-v2`) so the lock records the new method's parameters
   too.

Silently editing `protocols/legacy/cilogbench-v1.lock.json` to add a new
baseline is forbidden.

## Method submission checklist

Before merging a PR that introduces a new benchmark method:

- [ ] Method name follows the slug rules above.
- [ ] `line_mapping` is declared honestly. If false, `included_line_ranges`
      must be `[]` and `mapping_type: "text"`.
- [ ] Runner does not touch ground truth (automated AST check).
- [ ] Safe metadata is the only field passed to external calls.
- [ ] Privacy posture documented: does the method send raw CI logs
      to an external service?
- [ ] Cost / runtime recorded in the per-row `metadata`.
- [ ] For command-backed methods: a stub shim exists under `examples/`
      so CI can smoke-test the wrapper without an API key.
- [ ] An entry in `docs/methods/` or `docs/experiments/` explaining
      what the method does and how to interpret its numbers.
- [ ] The method has been run on dev + holdout under the relevant
      protocol lock, with results committed.
- [ ] If the submission also adds the method to the protocol lock, a
      version bump accompanies the PR.

## External LLM submissions (extra bar)

- Privacy audit must run clean (or `--allow-privacy-audit-hits` +
  written justification).
- `requires_explicit_external_llm_opt_in: true` in the config.
- `temperature` and model name/version recorded in the experiment
  manifest. If the provider is non-deterministic despite `temperature=0`,
  the experiment report must say so.
