# CILogBench v1

**Protocol ID:** `cilogbench-v1`
**Lock file:** `protocols/legacy/cilogbench-v1.lock.json`

CILogBench v1 evaluates CI failure context strategies on evidence
preservation and downstream diagnosis proxies. It does not claim to
measure general software-debugging ability.

## 1. Purpose

Answer one question per case:

> After a CI failure log is compressed, summarized, filtered, or
> searched, does a coding agent still have enough evidence to identify
> the true root cause?

The benchmark scores candidate **context methods** two ways:

1. **Signal recall** (intrinsic): does the method's output preserve
   the ground-truth evidence we annotated on the raw log?
2. **Downstream diagnosis** (extrinsic): given the method's output,
   can a fixed diagnoser produce a correct root-cause diagnosis?

## 2. Splits

| split | purpose | size (v1) |
|---|---|---|
| `dev` | develop methods, iterate on prompts, debug tooling | 5 cases |
| `holdout` | final evaluation under the locked protocol | 5 cases |

Both splits live under `cases/<split>/<case_id>/` with
`raw.log`, `case.json`, and `ground_truth.json`. Hashes and tallies
for every case are recorded in `cases/<split>/split_manifest.json`.

Holdout cases are annotated **before** any method is run on them. See
`docs/protocol/holdout_policy.md` for the iteration rules.

## 3. Case schema

Defined by `schemas/case.schema.json`. A case is a single failed CI
job with:

- `case_id` — stable kebab-case identifier; directory name must match.
- `repo`, `source`, `workflow_name`, `job_name`, `framework` — safe
  metadata that may be forwarded to models.
- `failure_category` — the ground-truth category; **never** passed to
  summarizers or diagnosers.
- `raw_log_path`, `line_count`, `byte_size`, `notes`.

## 4. Ground-truth annotation

Defined by `schemas/ground_truth.schema.json`. Each case records:

- `root_cause.summary` + `root_cause.category` (one of 13 values; see
  `schemas/diagnosis.schema.json` for the parallel enum).
- `required_signals` (≥1 critical): failed-test names, stack locations,
  assertion / exception text, compile errors, annotations, exit codes,
  etc. Each signal's `value` must be a literal substring of the raw log
  (after ANSI strip + CRLF→LF normalization) or must declare `aliases`
  that are.
- `relevant_files`, `relevant_tests` (optional).
- `evidence_spans` — narrow line ranges a reviewer would cite.
- `expected_diagnosis.must_mention` + `expected_diagnosis.must_not_claim`
  — concrete substrings the downstream diagnosis must or must not
  contain.

Annotations may change only under `docs/protocol/annotation_freeze_policy.md`.

## 5. Context-provider output schema

Defined by `schemas/method_output.schema.json`. One JSONL row per case
per method. For methods that preserve original line numbers
(`raw`, `tail`, `grep`), `line_mapping_available: true` and
`included_line_ranges` are authoritative. For transformed outputs
(`rtk-*`, `llm-summary-*`), `line_mapping_available: false` +
`mapping_type: "text"`, and scoring uses substring matching.

## 6. Signal-recall scoring

`tools/evaluate_signal_recall.py` (lock key `evaluators.signal_recall`).

A required signal is preserved iff:

- **A. Line coverage** — `line_mapping_available` is true AND every
  line in the signal's `evidence_lines` is inside the method's
  `included_line_ranges`; OR
- **B. Text fallback** — the signal's `value`, one of its `aliases`,
  or its `file` field (for `stack_location` signals) appears as a
  literal substring in the ANSI-stripped context.

`evidence_span_coverage` is reported only when line mapping is
available; otherwise it is N/A.

Macro averages exclude nulls.

## 7. Diagnosis scoring

`tools/evaluate_diagnosis.py` (lock key `evaluators.diagnosis`).

Eleven deterministic metrics, computed per case and macro-averaged
per context method:

1. `diagnosis_success`
2. `category_accuracy`
3. `required_signal_mention_recall`
4. `critical_signal_mention_recall`
5. `relevant_file_recall`
6. `relevant_test_recall`
7. `must_mention_coverage`
8. `forbidden_claim_violations`
9. `valid_evidence_quote_rate`
10. `abstention_rate`
11. `confident_error_rate`

No LLM judge. Metrics that cannot be computed are null (`N/A`), not
zero. See `docs/evaluation/diagnosis_eval_v1.md` for the full spec.

An **experimental** composite `diagnosis_score_v1` is emitted
alongside the individual metrics; it is not a leaderboard metric.

## 8. Allowed metadata for models

Summarizers and diagnosers may receive, per case:

```
case_id, repo, source, workflow_name, job_name, framework
```

Nothing more.

## 9. Disallowed leakage

Never pass to a summarizer, diagnoser, or any benchmark participant:

- `ground_truth.json` (full file)
- `required_signals`, `evidence_spans`, `expected_diagnosis`
- `failure_category`
- previously-computed eval JSON files

Leakage checks are enforced at the AST level in the M5/M6/M7 runners
and re-checked whenever tools change.

## 10. Baselines + parameters

Locked in `protocols/legacy/cilogbench-v1.lock.json` under `baselines`:

| method | params |
|---|---|
| `raw` | (none) |
| `tail-200` | `tail_lines=200` |
| `grep` | default regex, `before=3`, `after=8` |
| `rtk-read` / `rtk-log` / `rtk-err-cat` | external tool `rtk`; version recorded at runtime |
| `llm-summary-v1-mock` | built-in heuristic (not a real LLM) |

Additional methods may be added via `docs/protocol/method_submission_v1.md`
without modifying v1 — they will either participate in future protocol
versions or be reported outside the locked baseline set.

## 11. Prompt versions

Locked under `prompts`:

- `llm_summary_v1_map` (prompts/llm_summary_v1_map.md)
- `llm_summary_v1_reduce` (prompts/llm_summary_v1_reduce.md)
- `debugger_v1` (prompts/debugger_v1.md)

Any change to these files invalidates the v1 lock.

## 12. External tool version recording

RTK runs record the binary path, version string, argv, exit code, and
runtime in the per-row `external_tool` metadata. If RTK is missing,
locked eval records `skipped_missing_external_tool` and continues.

Real LLM summarizer/diagnoser runs record
`summarizer_config_sha256` / `diagnoser_config_sha256` and the prompt
hashes in the per-case manifest + experiment manifest.

## 13. Privacy audit limitations

`tools/audit_context_privacy.py` is best-effort. It detects a fixed set
of secret patterns (GitHub tokens, AWS keys, Authorization headers,
password/secret assignments, etc.) line-by-line over context outputs.
A clean audit does NOT guarantee safety. M6/M7 require explicit
external-LLM opt-in on top of the audit.

## 14. Reproducibility requirements

Every experiment manifest must include:

- config path + SHA-256
- prompt path + SHA-256
- split case count
- git commit (or "unknown")
- `started_at` / `finished_at`
- opt-in channel (`env` / `cli` / `config`)

Successful reruns with the same inputs must produce byte-identical
per-case diagnosis / summary rows (enforced via cache-stored full rows,
not just bodies).

## 15. Supportable and unsupportable claims

v1 supports statements like:

- "Under `cilogbench-v1`, method X preserved Y% of required signals on
  dev and Z% on holdout (10 cases total)."
- "Method A produced Q confident-error cases on holdout under diagnoser
  D (prompt SHA `xxx…`)."

v1 does **not** support:

- "Method X is the best CI log strategy in general."
- "This is a definitive public benchmark of CI debugging tools."
- Rankings based on the 5-case holdout alone.

The dataset grows and the evaluators harden across later milestones.
Publish with care.
