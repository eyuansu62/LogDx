# CILogBench Pivot Plan

## Purpose

Pivot the project from a CI log compressor into a benchmark for evaluating CI failure context strategies.

The project should answer this question:

> After a CI failure log is compressed, summarized, filtered, or searched, does a coding agent still have enough evidence to identify the true root cause?

This is not a plan to build a new RTK competitor. RTK, raw logs, grep/tail heuristics, LLM summaries, and MCP/search-style agents should become benchmarked methods.

## Current decision

Stop treating `cilog-extract` as the primary product.

The new primary product is:

```text
CILogBench: a benchmark for CI failure context quality and agent debugging reliability.
```

Existing rule-based extraction code may be kept as a legacy baseline, but it should not be expanded as the main objective.

## Non-goals for this first implementation pass

Do not do these yet:

- Do not implement a new Rust CLI.
- Do not expand framework-specific compressors.
- Do not optimize compression ratio.
- Do not integrate RTK yet.
- Do not call LLM APIs yet.
- Do not build an MCP server.
- Do not fetch new GitHub Actions logs.
- Do not create a leaderboard yet.
- Do not delete existing working code unless it is safely moved or clearly obsolete.

This pass is only about establishing benchmark data, schemas, validation, and project direction.

## First milestone

Create a minimal but real benchmark dataset from existing failed CI logs.

Target completion criteria:

- `cases/dev/` contains at least 5 real CI failure cases, if enough existing logs are available.
- Each case has:
  - `raw.log`
  - `case.json`
  - `ground_truth.json`
- JSON schemas exist for cases, ground truth, method outputs, and diagnoses.
- A validator script checks all case files and line references.
- README clearly states that the project is now a benchmark, not a compressor.
- Existing `cilog-extract` code is either moved to a legacy baseline location or explicitly marked as historical/legacy.

If fewer than 5 real logs are present in the repository, create as many valid cases as possible and document the missing dataset requirement in `README.md`.

## Proposed repository structure

Refactor toward this structure:

```text
cilog-bench/
  README.md
  PLAN.md
  cases/
    dev/
      <case_id>/
        raw.log
        case.json
        ground_truth.json
    holdout/
      .gitkeep
  schemas/
    case.schema.json
    ground_truth.schema.json
    method_output.schema.json
    diagnosis.schema.json
  tools/
    validate_cases.py
  baselines/
    simple_rules_legacy/
      # optional: moved old extractor code, if practical
  docs/
    annotation_guide.md
```

Keep the structure simple. Prefer a small correct benchmark over a large incomplete framework.

## Case ID convention

Use stable, descriptive, lowercase IDs:

```text
<framework>-<repo_or_project>-<number>
```

Examples:

```text
pytest-pandas-001
pytest-pandas-002
cargo-tokio-001
jest-example-001
docker-build-example-001
```

The directory name must match `case.json.case_id`.

## Schema requirements

### `case.json`

`case.json` describes the input case. It must not contain the answer.

Example:

```json
{
  "case_id": "pytest-pandas-001",
  "repo": "pandas-dev/pandas",
  "source": "github_actions",
  "framework": "pytest",
  "failure_category": "test_assertion",
  "raw_log_path": "raw.log",
  "line_count": 18432,
  "byte_size": 1260342,
  "workflow_name": "CI",
  "job_name": "linux-py311",
  "notes": "Large pytest failure with traceback and assertion output"
}
```

Required fields:

- `case_id`
- `repo`
- `source`
- `framework`
- `failure_category`
- `raw_log_path`
- `line_count`
- `byte_size`

Recommended enum values:

`source`:

```text
github_actions
local_fixture
unknown
```

`framework`:

```text
pytest
jest
cargo
npm
pnpm
yarn
docker
ruff
eslint
tsc
generic
unknown
```

`failure_category`:

```text
test_assertion
snapshot_diff
compile_error
type_error
lint_error
dependency_install
docker_build
github_actions_config
permission_or_secret
timeout_or_oom
network_or_flaky
generic_error
unknown
```

### `ground_truth.json`

`ground_truth.json` describes the correct answer and the evidence required to reach it.

Line numbers must be 1-indexed and inclusive.

Example:

```json
{
  "root_cause": {
    "summary": "A pytest assertion failed because the actual output differed from the expected output in a pandas test.",
    "category": "test_assertion"
  },
  "required_signals": [
    {
      "type": "failed_test",
      "value": "test_example_name",
      "importance": "critical",
      "evidence_lines": [[1234, 1234]]
    },
    {
      "type": "stack_location",
      "file": "pandas/tests/example/test_file.py",
      "line": 456,
      "importance": "critical",
      "evidence_lines": [[1240, 1245]]
    },
    {
      "type": "assertion",
      "value": "AssertionError",
      "importance": "critical",
      "evidence_lines": [[1250, 1265]]
    }
  ],
  "relevant_files": [
    "pandas/tests/example/test_file.py"
  ],
  "relevant_tests": [
    "test_example_name"
  ],
  "evidence_spans": [
    {
      "start_line": 1234,
      "end_line": 1265,
      "reason": "Primary pytest failure traceback and assertion message"
    }
  ],
  "expected_diagnosis": {
    "must_mention": [
      "failed pytest test",
      "assertion mismatch",
      "relevant test name"
    ],
    "must_not_claim": [
      "dependency installation failed",
      "GitHub Actions permission error",
      "network failure"
    ]
  }
}
```

Required fields:

- `root_cause.summary`
- `root_cause.category`
- `required_signals`
- `evidence_spans`
- `expected_diagnosis.must_mention`
- `expected_diagnosis.must_not_claim`

Signal types should include at least these values:

```text
failed_test
stack_location
assertion
exception
panic
compile_error
exit_code
command
package
version
diff
annotation
step_name
job_name
workflow_name
```

Importance values:

```text
critical
important
optional
```

### `method_output.schema.json`

This schema will be used later by baselines such as raw, tail, grep, RTK, LLM summary, and MCP/search agents.

Create the schema now even if no methods are implemented yet.

Example method output:

```json
{
  "case_id": "pytest-pandas-001",
  "method": "raw",
  "mode": "context_provider",
  "input_bytes": 1260342,
  "output_bytes": 1260342,
  "input_tokens_estimate": 180000,
  "output_tokens_estimate": 180000,
  "context": "...",
  "signals": [],
  "metadata": {
    "runtime_ms": 0,
    "fallback_used": false
  }
}
```

Required fields:

- `case_id`
- `method`
- `mode`
- `input_bytes`
- `output_bytes`
- `context`
- `metadata`

Recommended `mode` values:

```text
context_provider
end_to_end_debugger
```

### `diagnosis.schema.json`

This schema will be used later when a fixed model or agent reads a method output and produces a diagnosis.

Example:

```json
{
  "case_id": "pytest-pandas-001",
  "method": "raw",
  "diagnoser": "fixed-model-placeholder",
  "root_cause_summary": "The pytest test failed due to an assertion mismatch.",
  "relevant_files": ["pandas/tests/example/test_file.py"],
  "relevant_tests": ["test_example_name"],
  "evidence": [
    {
      "line_range": [1234, 1265],
      "quote": "short evidence quote or excerpt"
    }
  ],
  "fix_suggestion": "Inspect the expected output or update the implementation that produced the mismatched result.",
  "confidence": "medium"
}
```

Required fields:

- `case_id`
- `method`
- `diagnoser`
- `root_cause_summary`
- `relevant_files`
- `relevant_tests`
- `evidence`
- `confidence`

## Case annotation rules

When creating or updating `ground_truth.json`:

1. Use only evidence visible in `raw.log`.
2. Do not infer details that are not present in the log.
3. Prefer narrow evidence spans over huge ranges.
4. Mark the minimum set of critical signals needed to diagnose the failure.
5. Use `importance: critical` only for evidence that must be preserved.
6. Use `importance: important` for useful but non-essential evidence.
7. Use `importance: optional` for context that helps readability but is not required.
8. Keep root cause summaries short and concrete.
9. Do not write fix suggestions as ground truth unless the log clearly supports them.
10. Do not tune ground truth based on any method output.

## Security and privacy rules

Before committing or moving any log fixture:

- Search for obvious secrets and redact them.
- Replace tokens, keys, and credentials with `[REDACTED]`.
- Check for patterns such as:
  - `ghp_`
  - `github_pat_`
  - `sk-`
  - `AKIA`
  - `BEGIN PRIVATE KEY`
  - `Authorization:`
  - `Bearer `
  - `password=`
  - `token=`
- Preserve line numbers after redaction when possible.
- If a log contains too much sensitive data, do not include it as a fixture.

## Validator requirements

Create:

```text
tools/validate_cases.py
```

It should accept one or more split directories:

```bash
python tools/validate_cases.py cases/dev
python tools/validate_cases.py cases/dev cases/holdout
```

The validator should check:

- Every case directory contains `raw.log`, `case.json`, and `ground_truth.json`.
- `case.json.case_id` equals the directory name.
- `case.json.raw_log_path` points to an existing file.
- `line_count` equals the actual number of lines in `raw.log`.
- `byte_size` equals the actual byte size of `raw.log`.
- `ground_truth.root_cause.summary` is non-empty.
- `required_signals` is non-empty.
- `evidence_spans` is non-empty.
- All evidence line ranges are valid for the raw log.
- All evidence spans use `start_line <= end_line`.
- All line numbers are 1-indexed, not 0-indexed.
- Required enum values are valid, if enums are implemented.
- No obvious secret patterns are present in `raw.log`.

The validator should print a readable summary:

```text
Validated 5 cases in cases/dev
- 5 passed
- 0 failed
```

On failure, print case ID, field, and reason.

## README rewrite

Rewrite the README around this new positioning:

```text
CILogBench evaluates whether CI failure context strategies preserve enough evidence for coding agents to identify the true root cause.
```

The README should include:

- What the benchmark measures.
- Why this is not another log compressor.
- What methods will eventually be compared:
  - raw log
  - tail/head baselines
  - grep/error heuristics
  - RTK
  - LLM summary
  - MCP/search-style agent
  - simple rules legacy baseline
- Current status:
  - small dev split
  - ground truth annotation in progress
  - no public leaderboard yet
- How to validate cases:

```bash
python tools/validate_cases.py cases/dev
```

- How to add a new case.
- Known limitations.

## Legacy extractor handling

If the repository currently contains the old extractor/compressor implementation, do one of the following:

Preferred option:

```text
baselines/simple_rules_legacy/
```

Alternative option:

```text
legacy/cilog_extract/
```

Update imports, tests, and docs only as much as needed to avoid breakage.

Do not continue optimizing this code in this pass.

The README should describe it as:

```text
A legacy deterministic rules baseline retained for comparison, not the main product.
```

## First 5 cases

Select up to 5 existing real failed CI logs from the current repository or previous benchmark corpus.

Prioritize diversity:

1. A pytest failure, preferably pandas.
2. Another pytest failure with a different error shape.
3. A cargo/Rust failure, preferably tokio.
4. A jest/npm failure, if available.
5. A docker-build, dependency-install, or generic GitHub Actions failure, if available.

If only pytest/cargo cases are available, use those and document the bias.

## What not to over-engineer

Keep this first pass deliberately small.

Avoid:

- complex CLI frameworks
- database storage
- network calls
- API clients
- generated dashboards
- advanced scoring
- model-graded evaluation
- tokenization libraries unless already present

The benchmark should first become correct and auditable.

## Suggested implementation sequence

1. Inspect existing repository layout and identify where logs, benchmark outputs, and extractor code currently live.
2. Create the new directories:
   - `cases/dev/`
   - `cases/holdout/`
   - `schemas/`
   - `tools/`
   - `docs/`
   - `baselines/simple_rules_legacy/` if needed.
3. Move or copy existing real logs into case directories.
4. Create `case.json` for each selected case.
5. Manually write `ground_truth.json` for each selected case.
6. Create JSON schemas.
7. Implement `tools/validate_cases.py`.
8. Add `docs/annotation_guide.md`.
9. Rewrite README around CILogBench.
10. Run validation and fix all case/schema issues.
11. Do not implement new baselines until this milestone is clean.

## Acceptance criteria

This pass is done when these commands work:

```bash
python tools/validate_cases.py cases/dev
```

And the output reports all selected dev cases as valid.

Also verify manually:

- README no longer positions the project as a CI log compressor.
- `cilog-extract` is not presented as the main product.
- Every selected case has human-readable ground truth.
- Evidence spans point to real line ranges in `raw.log`.
- No obvious secrets are present in committed logs.

## Future milestones, not for this pass

After this milestone, implement baselines in this order:

1. Raw log baseline.
2. Tail baseline.
3. Grep/error heuristic baseline.
4. Legacy simple-rules baseline.
5. RTK baseline.
6. LLM summary baseline.
7. Fixed-model diagnosis runner.
8. Signal recall evaluator.
9. Root-cause accuracy evaluator.
10. Context quality leaderboard.
11. End-to-end debugging leaderboard.

The next milestone should not begin until case validation is reliable.

## Final instruction to Codex

Implement only the first milestone unless explicitly asked to continue.

Do not try to solve the whole benchmark in one pass. The goal is to create a trustworthy benchmark foundation: schemas, validated cases, annotation guidance, and README pivot.
