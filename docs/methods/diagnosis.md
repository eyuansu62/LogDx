# Diagnosis runner (M5)

`tools/run_diagnosis.py` turns a context-method output into a structured
root-cause diagnosis, using a **fixed diagnoser**. The same diagnoser
must be used across every context method in a comparison, so any
difference in the diagnosis table is attributable to the context
method, not the model.

## Privacy / anti-leakage

The runner **never reads**:

- `cases/<split>/<case_id>/ground_truth.json`
- `required_signals`, `evidence_spans`, `expected_diagnosis`,
  `failure_category`
- any previous eval output

The runner **reads**:

- `cases/<split>/<case_id>/case.json`, **but only the safe allow-list**:
  `case_id`, `repo`, `source`, `workflow_name`, `job_name`, `framework`
- `results/<split>/<method>.jsonl` (for `context_path`)
- the context text at `context_path`

`failure_category` is explicitly stripped before metadata is forwarded.
The diagnoser sees what a real user/agent would plausibly see *before*
diagnosis: the log (or a derived context) plus basic repo/workflow
metadata. It does not see the answer.

## Providers

### `mock` (default)

Deterministic local pattern scan. Uses the same keyword-oriented logic
as the `grep` baseline, plus a small rules-based category mapper:
dubious-ownership → permission_or_secret, mypy stubtest → type_error,
rustc trybuild → compile_error, etc. Mock is a **pipeline smoke test**,
not a real diagnoser. Its category accuracy is a byproduct of the
heuristic; do not interpret it as a quality signal.

```bash
python tools/run_diagnosis.py --split dev --diagnoser mock --context-method all
```

Output goes to `results/<split>/diagnoses/debugger-v1-mock/`.

### `command`

Shell out to a user-supplied shim that speaks JSON. The runner:

1. For each case, reads `context_path` and safe metadata.
2. Serializes a JSON request and pipes it to the command via stdin.
3. Reads JSON from the command's stdout.
4. Normalizes the response into the CILogBench diagnosis schema
   (filling missing fields with conservative defaults).

**Privacy warning.** The command provider may send context derived from
CI logs to an external model. Run the secret-pattern scan
(`tools/validate_cases.py`) on your cases first and confirm they are
safe to share. CILogBench never modifies user hooks or agent config.

```bash
export DIAGNOSIS_COMMAND="/path/to/diagnosis_shim"
python tools/run_diagnosis.py --split dev --diagnoser command \
    --diagnoser-name my-debugger-v1 \
    --command "$DIAGNOSIS_COMMAND" \
    --context-method all
```

#### Input contract (stdin JSON)

```json
{
  "case_id": "pytest-pandas-001",
  "context_method": "grep",
  "prompt": "... contents of prompts/debugger_v1.md ...",
  "context": "... processed context text ...",
  "safe_case_metadata": {
    "case_id": "pytest-pandas-001",
    "repo": "pandas-dev/pandas",
    "source": "github_actions",
    "workflow_name": "Unit Tests",
    "job_name": "Numpy Nightly",
    "framework": "pytest"
  },
  "expected_output_schema": "schemas/diagnosis.schema.json"
}
```

#### Output contract (stdout JSON)

```json
{
  "summary": "...",
  "root_cause_category": "test_assertion",
  "root_cause": "...",
  "confidence": 0.74,
  "relevant_files": [],
  "relevant_tests": [],
  "evidence": [
    {"quote": "AssertionError: ...", "reason": "shows the failing assertion"}
  ],
  "suggested_fix": "..."
}
```

`root_cause_category` must be one of the enum values from
`schemas/diagnosis.schema.json` (anything else is coerced to `other`).
`confidence` must be a number in `[0,1]` (clamped). Missing fields are
filled with conservative defaults — the runner never discards what the
shim returned.

### Minimal shim example

```python
#!/usr/bin/env python3
"""Minimal diagnosis shim. Replace the placeholder LLM call with whatever
provider you use."""
import json, sys

payload = json.load(sys.stdin)
context = payload["context"]
meta = payload["safe_case_metadata"]

# Replace this block with your real LLM call. Typical flow:
#   resp = llm.complete(system=payload["prompt"], user=context + meta_json)
#   diagnosis = json.loads(resp)
diagnosis = {
    "summary": "unknown",
    "root_cause_category": "unknown",
    "root_cause": "unknown",
    "confidence": 0.0,
    "relevant_files": [],
    "relevant_tests": [],
    "evidence": [],
    "suggested_fix": "Inspect the full CI log.",
}
json.dump(diagnosis, sys.stdout)
```

Never embed API keys in shim files you intend to commit. Use environment
variables and read them inside the shim.

## Caching

Each invocation's response is cached under
`results/<split>/.cache/diagnosis/<cache_key>.json`. Cache key is a
SHA-256 over:

```
case_id, context_method, context SHA-256, prompt SHA-256,
provider, diagnoser name, command string
```

Changing the prompt or the context invalidates the cache automatically.
Provider errors are NOT cached by default; pass `--cache-errors` if you
want them persisted for debugging. Pass `--no-cache` to bypass cache
reads entirely.

## Error handling

Provider failures on a single case do **not** crash the run (unless
`--strict` is passed):

- The runner records `metadata.provider_error` with the exception.
- The diagnosis body is filled with `root_cause_category: unknown`,
  `root_cause: unknown`, `confidence: 0.0`.
- The per-case JSON and JSONL manifest still validate.
- The evaluator counts `diagnosis_success = false` for that case.

## Method discovery

`--context-method all` discovers available manifests from
`results/<split>/*.jsonl`, excluding `eval_*.jsonl` and any `.debug.*`
manifests. Missing manifests (e.g. you haven't run RTK yet) are skipped
with a warning.
