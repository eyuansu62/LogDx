## Tagging guide

Every case carries a `tags.json` alongside `case.json` and
`ground_truth.json`. Tags are **for dataset analysis** (corpus summary,
split balance, stress axes) — **never** for model input. The diagnosis
runner's safe-metadata allowlist does not include any tag field.

### File layout

```
cases/<split>/<case_id>/
  raw.log
  case.json
  ground_truth.json
  tags.json
```

Schema: `schemas/case_tags.schema.json`.

### Required axes

| axis | enum | purpose |
|---|---|---|
| `failure_category` | test_assertion, compile_error, type_error, lint_failure, formatting_failure, dependency_install, docker_build, github_actions_config, permission_or_secret, network_or_flaky, timeout_or_oom, snapshot_or_golden_diff, multi_failure, other, unknown | broad category (richer than `case.json.failure_category`'s v1 enum) |
| `framework` | pytest, jest, cargo, tsc, eslint, prettier, npm, pnpm, pip, docker, terraform, generic, unknown | tool that reports the failure |
| `primary_language` | free string | "python", "javascript", "rust", "go", "shell", "unknown" |
| `log_size_bucket` | small (<500 lines), medium (500–5k), large (5k–50k), huge (>50k) | |
| `signal_position` | early / middle / late / scattered | where the primary evidence sits relative to log length |
| `evidence_formats` | plain_error_line, traceback, compiler_diagnostic, ascii_table, json_block, diff_block, ansi_colored_block, github_annotation, shell_command_output, nested_tool_output | multi-valued |
| `noise_profile` | runner_setup, dependency_install_noise, test_progress_noise, matrix_noise, docker_layer_noise, verbose_build_noise, log_group_noise, low_noise | multi-valued |
| `diagnosis_difficulty` | easy / medium / hard / unclear | honest assessment |

### Optional flags

- `multi_failure`: one log has more than one distinct failure.
- `flaky_or_transient`: the failure depends on network/timing, not code.
- `requires_repo_context`: fixing the failure requires reading files
  outside the log (e.g. a downstream gate that reacts to an upstream
  job).

### Cross-check rules (enforced by `tools/validate_case_tags.py`)

- `log_size_bucket` must match the actual line count of `raw.log`.
  Override with the exact phrase "size mismatch justified" in `notes`.
- `failure_category` should match `ground_truth.root_cause.category`
  modulo the alias table (e.g. `lint_error ↔ lint_failure`). Override
  with "category mismatch justified: <reason>" in `notes`.
- `framework` should match `case.json.framework`. Override with
  "framework mismatch justified: <reason>" in `notes`. This is common
  when the case-schema enum is narrower than the tag enum (e.g.
  `prettier` is not in the case-schema framework enum but is in the
  tag enum).

### How to pick `signal_position`

`tools/tag_cases.py` computes it from `evidence_spans`:

- If the min/max evidence lines span > 30% of the log → `scattered`.
- Else take the midpoint of the span:
  - ratio < 0.25 → `early`
  - ratio > 0.75 → `late`
  - otherwise → `middle`

Override manually when the heuristic is wrong (e.g. the primary
evidence is concentrated in one paragraph but happens to sit at 40%;
human judgment should still call this `middle`, not `scattered`).

### Workflow for a new case

1. `python tools/import_case_skeleton.py --split <split> --case-id <id>
   --raw-log <path> --repo <owner/repo> --framework <...> --workflow-name
   <...> --job-name <...>` — creates `raw.log` + `case.json` +
   `ground_truth.todo.json` + `tags.todo.json`.
2. Annotate `ground_truth.json` manually (see
   `docs/annotation_guide.md`).
3. `python tools/tag_cases.py --split <split>` — writes
   `tags.suggested.json`. Review, edit, and save as `tags.json`.
4. `python tools/validate_cases.py cases/<split>` — confirms schema
   integrity + evidence lines.
5. `python tools/validate_case_tags.py --split <split>` — confirms tag
   cross-references.
6. `python tools/summarize_corpus.py --splits dev,holdout,stress` and
   `python tools/check_split_balance.py --splits dev,holdout,stress` —
   inspect effect on split balance before freezing a protocol version.

### What tags are NOT for

- **Not model input.** Never pass `tags.failure_category`,
  `tags.diagnosis_difficulty`, or any other tag field to a summarizer
  or diagnoser. The safe-metadata allowlist (`case_id`, `repo`,
  `source`, `workflow_name`, `job_name`, `framework` *from case.json*)
  does not include tags.
- **Not override for `case.json`.** If the tag enum is richer than the
  case enum (as with `prettier`/`formatting_failure`), the tag version
  lives in `tags.json` and the case keeps the v1-schema-compliant
  value, with a justified note.
- **Not scoring adjustment.** Tags do not change signal-recall or
  diagnosis-eval metrics. They inform reports and dataset summaries
  only.
