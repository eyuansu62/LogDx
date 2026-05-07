# CILogBench diagnosis report — `dev` / `real-debugger-v2`

Prompt SHA256 (first 12): `ecffdf03c99a…`
Cases in split: **5**
Methods evaluated: **8** (`raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`, `hybrid-grep-4k-rtk-err-cat-v1`)

This report scores whether a **fixed diagnoser** can identify the CI failure root cause given each context method's output. It does NOT evaluate the context methods on their own; that lives in the signal-recall report.

## Main metrics (macro-averaged per context method)

| Context Method | Success | Category Acc | Critical Mention | Must Mention | File Recall | Test Recall | Forbidden | Conf Err | Context Tok | Diagnosis Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 20.0% | 35.0% | 35.0% | 40.0% | 33.3% | 0.0% | 20.0% | 130.2k | 241 | 0.251 |
| tail | 100.0% | 60.0% | 45.3% | 70.0% | 73.3% | 33.3% | 0.0% | 40.0% | 5.6k | 559 | 0.465 |
| grep | 100.0% | 80.0% | 72.7% | 85.0% | 80.0% | 100.0% | 0.0% | 20.0% | 42.5k | 936 | 0.717 |
| rtk-read | 100.0% | 20.0% | 25.0% | 35.0% | 40.0% | 33.3% | 0.0% | 20.0% | 130.2k | 246 | 0.223 |
| rtk-log | 100.0% | 60.0% | 22.0% | 50.0% | 16.7% | 16.7% | 20.0% | 40.0% | 385 | 519 | 0.295 |
| rtk-err-cat | 100.0% | 80.0% | 58.7% | 75.0% | 60.0% | 66.7% | 0.0% | 0.0% | 9.4k | 921 | 0.671 |
| llm-summary-v1-mock | 100.0% | 80.0% | 43.3% | 55.0% | 46.7% | 0.0% | 0.0% | 0.0% | 1.5k | 562 | 0.526 |
| hybrid-grep-4k-rtk-err-cat-v1 | 100.0% | 80.0% | 77.7% | 75.0% | 80.0% | 66.7% | 0.0% | 20.0% | 9.0k | 906 | 0.700 |

Columns:

- **Success**: fraction of cases where a non-empty diagnosis was produced (no provider error).
- **Category Acc**: exact match between `diagnosis.root_cause_category` and `ground_truth.root_cause.category`. `unknown` never counts as correct unless ground truth is also `unknown`.
- **Critical Mention**: fraction of ground-truth `required_signals` with `importance=critical` whose value/alias/file appears in the diagnosis text.
- **Must Mention**: fraction of `expected_diagnosis.must_mention` substrings present.
- **Forbidden**: fraction of cases where at least one `expected_diagnosis.must_not_claim` substring leaked into the diagnosis.
- **Conf Err**: cases where `confidence >= 0.70` but category was wrong or a forbidden claim appeared.
- **score_v1**: experimental composite; see `docs/evaluation/diagnosis_eval_v1.md`.

## Per-case category accuracy

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | hybrid-grep-4k-rtk-err-cat-v1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `jest-nextjs-001` | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 100.0% | 100.0% |
| `lint-react-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `mypy-pandas-001` | 0.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `pytest-pandas-001` | 0.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |

## Per-case critical signal mention recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | hybrid-grep-4k-rtk-err-cat-v1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 50.0% | 50.0% | 66.7% | 33.3% | 16.7% | 50.0% | 33.3% | 66.7% |
| `jest-nextjs-001` | 25.0% | 50.0% | 50.0% | 25.0% | 0.0% | 50.0% | 50.0% | 75.0% |
| `lint-react-001` | 100.0% | 66.7% | 66.7% | 66.7% | 33.3% | 33.3% | 33.3% | 66.7% |
| `mypy-pandas-001` | 0.0% | 20.0% | 80.0% | 0.0% | 20.0% | 80.0% | 40.0% | 80.0% |
| `pytest-pandas-001` | 0.0% | 40.0% | 100.0% | 0.0% | 40.0% | 80.0% | 60.0% | 100.0% |

## Per-case forbidden-claim violations

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | hybrid-grep-4k-rtk-err-cat-v1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `jest-nextjs-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `lint-react-001` | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `mypy-pandas-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `pytest-pandas-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-case abstention

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | hybrid-grep-4k-rtk-err-cat-v1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | — | — | — | — | — | — | — | — |
| `jest-nextjs-001` | abst. | — | — | abst. | — | — | — | — |
| `lint-react-001` | — | — | — | — | — | — | — | — |
| `mypy-pandas-001` | abst. | — | — | abst. | — | — | — | — |
| `pytest-pandas-001` | abst. | — | — | abst. | — | — | — | — |

## Per-case confident error

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | hybrid-grep-4k-rtk-err-cat-v1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | — | — | — | — | — | — | — | — |
| `jest-nextjs-001` | — | ERR | — | — | ERR | — | — | — |
| `lint-react-001` | ERR | ERR | ERR | ERR | ERR | — | — | ERR |
| `mypy-pandas-001` | — | — | — | — | — | — | — | — |
| `pytest-pandas-001` | — | — | — | — | — | — | — | — |

## Per-case failure analysis

### `cargo-tokio-001`

- **raw** — pred `compile_error` @ 0.97
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`
- **tail** — pred `compile_error` @ 0.82
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`
- **grep** — pred `compile_error` @ 0.92
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`
- **rtk-read** — pred `compile_error` @ 0.97
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `1 of 10 tests failed`
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`
- **rtk-log** — pred `compile_error` @ 0.82
  - missed [critical] failed_test: `tests-build::macros compile_fail_full`
  - missed [critical] stack_location: `tests/fail/macros_type_mismatch.rs`
  - missed [critical] assertion: `1 of 10 tests failed`
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - … and 1 more
- **rtk-err-cat** — pred `compile_error` @ 0.85
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`
- **llm-summary-v1-mock** — pred `compile_error` @ 0.68
  - missed [critical] failed_test: `tests-build::macros compile_fail_full`
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `1 of 10 tests failed`
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
- **hybrid-grep-4k-rtk-err-cat-v1** — pred `compile_error` @ 0.82
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`

### `jest-nextjs-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **tail** — pred `other` @ 0.92 [CONFIDENT_ERROR]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
- **grep** — pred `permission_or_secret` @ 0.72
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **rtk-log** — pred `test_assertion` @ 0.72 [CONFIDENT_ERROR]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
  - … and 1 more
- **rtk-err-cat** — pred `permission_or_secret` @ 0.68
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **llm-summary-v1-mock** — pred `permission_or_secret` @ 0.82
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **hybrid-grep-4k-rtk-err-cat-v1** — pred `permission_or_secret` @ 0.62
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [important] stack_location: `/work/run-tests.js`

### `lint-react-001`

- **raw** — pred `formatting_failure` @ 0.98 [CONFIDENT_ERROR]
- **tail** — pred `formatting_failure` @ 0.97 [CONFIDENT_ERROR]
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
- **grep** — pred `formatting_failure` @ 0.82 [CONFIDENT_ERROR]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
- **rtk-read** — pred `formatting_failure` @ 0.97 [CONFIDENT_ERROR]
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
- **rtk-log** — pred `formatting_failure` @ 0.72 [CONFIDENT_ERROR, forbidden×1]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - forbidden claim present: `compile error`
- **rtk-err-cat** — pred `formatting_failure` @ 0.62
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
- **llm-summary-v1-mock** — pred `formatting_failure` @ 0.62
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
- **hybrid-grep-4k-rtk-err-cat-v1** — pred `formatting_failure` @ 0.82 [CONFIDENT_ERROR]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`

### `mypy-pandas-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
  - … and 1 more
- **tail** — pred `type_error` @ 0.92
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
- **grep** — pred `type_error` @ 0.95
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] step_name: `mypy (stubtest)`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
  - … and 1 more
- **rtk-log** — pred `type_error` @ 0.82
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
- **rtk-err-cat** — pred `type_error` @ 0.92
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
- **llm-summary-v1-mock** — pred `type_error` @ 0.88
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
- **hybrid-grep-4k-rtk-err-cat-v1** — pred `type_error` @ 0.92
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`

### `pytest-pandas-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] stack_location: `pandas/tests/arrays/masked/test_indexing.py`
  - missed [critical] exception: `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
  - … and 1 more
- **tail** — pred `test_assertion` @ 0.82
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] stack_location: `pandas/tests/arrays/masked/test_indexing.py`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
- **grep** — pred `test_assertion` @ 0.95
  - missed [important] step_name: `==================================== ERRORS ====================================`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] stack_location: `pandas/tests/arrays/masked/test_indexing.py`
  - missed [critical] exception: `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
  - … and 1 more
- **rtk-log** — pred `test_assertion` @ 0.82
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] exception: `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
- **rtk-err-cat** — pred `test_assertion` @ 0.92
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
- **llm-summary-v1-mock** — pred `test_assertion` @ 0.82
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
- **hybrid-grep-4k-rtk-err-cat-v1** — pred `test_assertion` @ 0.92
  - missed [important] step_name: `==================================== ERRORS ====================================`

## Interpretation guardrails

- Mock diagnoser results validate the pipeline, not real LLM quality. If `diagnoser` is `debugger-v1-mock`, the numbers are shaped by simple pattern rules; they should not be read as an endorsement of any context method.
- Deterministic diagnosis scoring is a proxy, not a full semantic judge. A method can lose this proxy while producing a diagnosis a human would accept, and vice versa.
- Raw context is not guaranteed to win with a weak diagnoser: the diagnoser may drown in irrelevant lines.
- High signal recall does not necessarily imply high diagnosis accuracy. The context method may preserve evidence in a form the diagnoser ignores.
- Low context token count is only useful if diagnosis quality remains acceptable. A 99% reduction that forces abstention is not a win.
- `score_v1` is experimental. The individual metrics are what this report is about.

