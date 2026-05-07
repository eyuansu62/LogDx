# CILogBench signal-recall report — `dev`

Context-provider baselines scored against per-case ground truth. `raw` must score 100% on all recall metrics — if it does not, the evaluator or the annotations are wrong. `Mapping` indicates whether a method preserves original raw.log line numbers (`line`) or only transformed text (`text`). Evidence coverage is line-based and shows N/A for text-mapped methods.

## Summary

| Method | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping | Processing Tokens | Final Context Tokens |
|---|---:|---:|---:|---:|---|---:|---:|
| raw | 100.0% | 100.0% | 100.0% | 0.0% | line | 0 | 130.3k |
| tail | 63.3% | 70.0% | 30.7% | 81.6% | line | 0 | 5.6k |
| grep | 86.7% | 88.3% | 78.4% | 69.8% | line | 0 | 42.5k |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | text | 0 | 130.3k |
| rtk-log | 25.7% | 30.3% | N/A | 99.2% | text | 0 | 387 |
| rtk-err-cat | 73.3% | 77.7% | N/A | 86.7% | text | 0 | 9.4k |
| llm-summary-v1-mock | 42.4% | 43.3% | N/A | 98.5% | text | 181.4k | 1.5k |
| llm-summary-v1-haiku | 58.1% | 64.7% | N/A | 98.6% | text | 9.4k | 735 |

Token columns are per-case averages. _Processing Tokens_ counts summarization cost (map+reduce input+output tokens) and is 0 for non-LLM baselines. _Final Context Tokens_ estimates the size of the context handed to a downstream reader.

Cases in split: **5**.

## Per-case signal recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 100.0% | 100.0% | 100.0% | 100.0% | 28.6% | 100.0% | 28.6% | 57.1% |
| `jest-nextjs-001` | 100.0% | 50.0% | 83.3% | 100.0% | 16.7% | 66.7% | 50.0% | 50.0% |
| `lint-react-001` | 100.0% | 83.3% | 50.0% | 100.0% | 33.3% | 33.3% | 33.3% | 66.7% |
| `mypy-pandas-001` | 100.0% | 33.3% | 100.0% | 100.0% | 16.7% | 83.3% | 33.3% | 50.0% |
| `pytest-pandas-001` | 100.0% | 50.0% | 100.0% | 100.0% | 33.3% | 83.3% | 66.7% | 66.7% |

## Per-case critical signal recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 100.0% | 100.0% | 100.0% | 100.0% | 33.3% | 100.0% | 33.3% | 66.7% |
| `jest-nextjs-001` | 100.0% | 50.0% | 75.0% | 100.0% | 25.0% | 75.0% | 50.0% | 50.0% |
| `lint-react-001` | 100.0% | 100.0% | 66.7% | 100.0% | 33.3% | 33.3% | 33.3% | 66.7% |
| `mypy-pandas-001` | 100.0% | 40.0% | 100.0% | 100.0% | 20.0% | 80.0% | 40.0% | 60.0% |
| `pytest-pandas-001` | 100.0% | 60.0% | 100.0% | 100.0% | 40.0% | 100.0% | 60.0% | 80.0% |

## Per-case reduction

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 0.0% | 95.6% | 56.2% | 0.0% | 99.6% | 92.6% | 97.7% | 99.5% |
| `jest-nextjs-001` | 0.0% | 98.1% | 78.7% | 0.0% | 99.9% | 99.1% | 99.6% | 99.7% |
| `lint-react-001` | 0.0% | 24.2% | 95.5% | 0.0% | 97.0% | 68.6% | 98.1% | 95.4% |
| `mypy-pandas-001` | 0.0% | 95.4% | 78.5% | 0.0% | 99.6% | 85.1% | 98.4% | 99.5% |
| `pytest-pandas-001` | 0.0% | 94.8% | 40.0% | 0.0% | 99.7% | 88.3% | 98.5% | 99.0% |

## Notable misses

### `cargo-tokio-001`

- **rtk-log** — missed 5 signal(s):
  - type=failed_test · importance=critical · value='tests-build::macros compile_fail_full'
  - type=stack_location · importance=critical · file=tests/fail/macros_type_mismatch.rs:5
  - type=assertion · importance=critical · value='1 of 10 tests failed'
  - type=panic · importance=important · value="thread 'compile_fail_full' (25975) panicked at"
  - type=assertion · importance=critical · value='396 tests run: 395 passed, 1 failed, 1 skipped'
- **llm-summary-v1-mock** — missed 5 signal(s):
  - type=failed_test · importance=critical · value='tests-build::macros compile_fail_full'
  - type=compile_error · importance=critical · value='error[E0308]: mismatched types'
  - type=assertion · importance=critical · value='1 of 10 tests failed'
  - type=panic · importance=important · value="thread 'compile_fail_full' (25975) panicked at"
  - type=assertion · importance=critical · value='396 tests run: 395 passed, 1 failed, 1 skipped'
- **llm-summary-v1-haiku** — missed 3 signal(s):
  - type=compile_error · importance=critical · value='error[E0308]: mismatched types'
  - type=panic · importance=important · value="thread 'compile_fail_full' (25975) panicked at"
  - type=assertion · importance=critical · value='396 tests run: 395 passed, 1 failed, 1 skipped'

### `jest-nextjs-001`

- **tail** — missed 3 signal(s):
  - type=exception · importance=critical · value="fatal: detected dubious ownership in repository at '/work'"
  - type=exception · importance=important · value="Git error: fatal: detected dubious ownership in repository at '/work'"
  - type=failed_test · importance=critical · value='examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries'
- **grep** — missed 1 signal(s):
  - type=assertion · importance=critical · value='No tests found, exiting with code 1'
- **rtk-log** — missed 5 signal(s):
  - type=exception · importance=critical · value="fatal: detected dubious ownership in repository at '/work'"
  - type=exception · importance=important · value="Git error: fatal: detected dubious ownership in repository at '/work'"
  - type=assertion · importance=critical · value='No tests found, exiting with code 1'
  - type=failed_test · importance=critical · value='examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries'
  - type=stack_location · importance=important · file=/work/run-tests.js:927
- **rtk-err-cat** — missed 2 signal(s):
  - type=assertion · importance=critical · value='No tests found, exiting with code 1'
  - type=stack_location · importance=important · file=/work/run-tests.js:927
- **llm-summary-v1-mock** — missed 3 signal(s):
  - type=assertion · importance=critical · value='No tests found, exiting with code 1'
  - type=failed_test · importance=critical · value='examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries'
  - type=stack_location · importance=important · file=/work/run-tests.js:927
- **llm-summary-v1-haiku** — missed 3 signal(s):
  - type=exception · importance=critical · value="fatal: detected dubious ownership in repository at '/work'"
  - type=exception · importance=important · value="Git error: fatal: detected dubious ownership in repository at '/work'"
  - type=failed_test · importance=critical · value='examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries'

### `lint-react-001`

- **tail** — missed 1 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
- **grep** — missed 3 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
- **rtk-log** — missed 4 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
  - type=stack_location · importance=critical · file=packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js:1
- **rtk-err-cat** — missed 4 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
  - type=stack_location · importance=critical · file=packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js:1
- **llm-summary-v1-mock** — missed 4 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
  - type=stack_location · importance=critical · file=packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js:1
- **llm-summary-v1-haiku** — missed 2 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'

### `mypy-pandas-001`

- **tail** — missed 4 signal(s):
  - type=stack_location · importance=critical · file=pandas/compat/pyarrow.py:69
  - type=compile_error · importance=important · value='error: Call to untyped function "fill_null" in typed context  [no-untyped-call]'
  - type=assertion · importance=critical · value='Found 279 errors in 9 files (checked 1458 source files)'
  - type=step_name · importance=critical · value='mypy (stubtest)'
- **rtk-log** — missed 5 signal(s):
  - type=stack_location · importance=critical · file=pandas/compat/pyarrow.py:69
  - type=compile_error · importance=critical · value='error: Module has no attribute "is_null"  [attr-defined]'
  - type=compile_error · importance=important · value='error: Call to untyped function "fill_null" in typed context  [no-untyped-call]'
  - type=assertion · importance=critical · value='Found 279 errors in 9 files (checked 1458 source files)'
  - type=step_name · importance=critical · value='mypy (stubtest)'
- **rtk-err-cat** — missed 1 signal(s):
  - type=assertion · importance=critical · value='Found 279 errors in 9 files (checked 1458 source files)'
- **llm-summary-v1-mock** — missed 4 signal(s):
  - type=compile_error · importance=critical · value='error: Module has no attribute "is_null"  [attr-defined]'
  - type=compile_error · importance=important · value='error: Call to untyped function "fill_null" in typed context  [no-untyped-call]'
  - type=assertion · importance=critical · value='Found 279 errors in 9 files (checked 1458 source files)'
  - type=step_name · importance=critical · value='mypy (stubtest)'
- **llm-summary-v1-haiku** — missed 3 signal(s):
  - type=stack_location · importance=critical · file=pandas/compat/pyarrow.py:69
  - type=compile_error · importance=critical · value='error: Module has no attribute "is_null"  [attr-defined]'
  - type=compile_error · importance=important · value='error: Call to untyped function "fill_null" in typed context  [no-untyped-call]'

### `pytest-pandas-001`

- **tail** — missed 3 signal(s):
  - type=step_name · importance=important · value='==================================== ERRORS ===================================='
  - type=stack_location · importance=critical · file=pandas/tests/arrays/masked/test_indexing.py:43
  - type=failed_test · importance=critical · value='pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_dti_cmp_nat_behaves_l…'
- **rtk-log** — missed 4 signal(s):
  - type=step_name · importance=important · value='==================================== ERRORS ===================================='
  - type=exception · importance=critical · value="DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated"
  - type=failed_test · importance=critical · value='pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_dti_cmp_nat_behaves_l…'
  - type=assertion · importance=critical · value='= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s'
- **rtk-err-cat** — missed 1 signal(s):
  - type=step_name · importance=important · value='==================================== ERRORS ===================================='
- **llm-summary-v1-mock** — missed 2 signal(s):
  - type=failed_test · importance=critical · value='pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_dti_cmp_nat_behaves_l…'
  - type=assertion · importance=critical · value='= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s'
- **llm-summary-v1-haiku** — missed 2 signal(s):
  - type=step_name · importance=important · value='==================================== ERRORS ===================================='
  - type=failed_test · importance=critical · value='pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_dti_cmp_nat_behaves_l…'

