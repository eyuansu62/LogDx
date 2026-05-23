# CILogBench diagnosis report — `dev` / `real-debugger-v1`

Prompt SHA256 (first 12): `ecffdf03c99a…`
Cases in split: **5**
Methods evaluated: **7** (`raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`)

This report scores whether a **fixed diagnoser** can identify the CI failure root cause given each context method's output. It does NOT evaluate the context methods on their own; that lives in the signal-recall report.

## Main metrics (macro-averaged per context method)

| Context Method | Success | Category Acc | Critical Mention | Must Mention | File Recall | Test Recall | Forbidden | Conf Err | Context Tok | Diagnosis Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 80.0% | 0.0% | 25.0% | 20.0% | 20.0% | 0.0% | 0.0% | 20.0% | 130.2k | 115 | 0.092 |
| tail | 100.0% | 40.0% | 56.0% | 60.0% | 53.3% | 33.3% | 0.0% | 60.0% | 5.6k | 505 | 0.355 |
| grep | 100.0% | 40.0% | 63.7% | 70.0% | 70.0% | 66.7% | 0.0% | 60.0% | 42.5k | 545 | 0.429 |
| rtk-read | 80.0% | 0.0% | 25.0% | 20.0% | 20.0% | 0.0% | 0.0% | 20.0% | 130.2k | 111 | 0.090 |
| rtk-log | 100.0% | 40.0% | 23.0% | 40.0% | 16.7% | 16.7% | 20.0% | 60.0% | 385 | 405 | 0.178 |
| rtk-err-cat | 100.0% | 80.0% | 58.7% | 65.0% | 60.0% | 66.7% | 0.0% | 0.0% | 9.4k | 559 | 0.651 |
| llm-summary-v1-mock | 100.0% | 60.0% | 43.3% | 45.0% | 46.7% | 0.0% | 0.0% | 20.0% | 1.5k | 429 | 0.409 |

Columns:

- **Success**: fraction of cases where a non-empty diagnosis was produced (no provider error).
- **Category Acc**: exact match between `diagnosis.root_cause_category` and `ground_truth.root_cause.category`. `unknown` never counts as correct unless ground truth is also `unknown`.
- **Critical Mention**: fraction of ground-truth `required_signals` with `importance=critical` whose value/alias/file appears in the diagnosis text.
- **Must Mention**: fraction of `expected_diagnosis.must_mention` substrings present.
- **Forbidden**: fraction of cases where at least one `expected_diagnosis.must_not_claim` substring leaked into the diagnosis.
- **Conf Err**: cases where `confidence >= 0.70` but category was wrong or a forbidden claim appeared.
- **score_v1**: experimental composite; see `docs/evaluation/diagnosis_eval_v1.md`.

## Per-case category accuracy

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 100.0% | 100.0% |
| `jest-nextjs-001` | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 100.0% |
| `lint-react-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `mypy-pandas-001` | 0.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 100.0% |
| `pytest-pandas-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |

## Per-case critical signal mention recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 0.0% | 50.0% | 66.7% | 0.0% | 16.7% | 50.0% | 33.3% |
| `jest-nextjs-001` | 25.0% | 50.0% | 25.0% | 25.0% | 25.0% | 50.0% | 50.0% |
| `lint-react-001` | 100.0% | 100.0% | 66.7% | 100.0% | 33.3% | 33.3% | 33.3% |
| `mypy-pandas-001` | 0.0% | 20.0% | 60.0% | 0.0% | 20.0% | 60.0% | 40.0% |
| `pytest-pandas-001` | 0.0% | 60.0% | 100.0% | 0.0% | 20.0% | 100.0% | 60.0% |

## Per-case forbidden-claim violations

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `jest-nextjs-001` | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| `lint-react-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `mypy-pandas-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `pytest-pandas-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-case abstention

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | abst. | — | — | abst. | — | — | — |
| `jest-nextjs-001` | abst. | — | — | abst. | — | — | — |
| `lint-react-001` | — | — | — | — | — | abst. | — |
| `mypy-pandas-001` | abst. | — | — | abst. | — | — | — |
| `pytest-pandas-001` | abst. | — | — | abst. | — | — | — |

## Per-case confident error

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | — | — | ERR | — | — | — | — |
| `jest-nextjs-001` | — | ERR | — | — | ERR | — | — |
| `lint-react-001` | ERR | ERR | ERR | ERR | ERR | — | — |
| `mypy-pandas-001` | — | — | — | — | — | — | — |
| `pytest-pandas-001` | — | ERR | ERR | — | ERR | — | ERR |

## Per-case failure analysis

### `cargo-tokio-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `tests-build::macros compile_fail_full`
  - missed [critical] stack_location: `tests/fail/macros_type_mismatch.rs`
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `1 of 10 tests failed`
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - … and 2 more
- **tail** — pred `compile_error` @ 0.85
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`
- **grep** — pred `test_assertion` @ 0.85 [CONFIDENT_ERROR]
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`
  - missed [critical] exit_code: `100`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `tests-build::macros compile_fail_full`
  - missed [critical] stack_location: `tests/fail/macros_type_mismatch.rs`
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `1 of 10 tests failed`
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - … and 2 more
- **rtk-log** — pred `compile_error` @ 0.88
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
- **llm-summary-v1-mock** — pred `compile_error` @ 0.85
  - missed [critical] failed_test: `tests-build::macros compile_fail_full`
  - missed [critical] compile_error: `error[E0308]: mismatched types`
  - missed [critical] assertion: `1 of 10 tests failed`
  - missed [important] panic: `thread 'compile_fail_full' (25975) panicked at`
  - missed [critical] assertion: `396 tests run: 395 passed, 1 failed, 1 skipped`

### `jest-nextjs-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **tail** — pred `other` @ 0.82 [CONFIDENT_ERROR]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **grep** — pred `permission_or_secret` @ 0.75
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
  - missed [critical] exit_code: `1`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **rtk-log** — pred `compile_error` @ 0.72 [CONFIDENT_ERROR, forbidden×1]
  - missed [critical] exception: `fatal: detected dubious ownership in repository at '/work'`
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
  - forbidden claim present: `compilation error`
- **rtk-err-cat** — pred `permission_or_secret` @ 0.60
  - missed [important] exception: `Git error: fatal: detected dubious ownership in repository at '/work'`
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`
- **llm-summary-v1-mock** — pred `permission_or_secret` @ 0.82
  - missed [critical] assertion: `No tests found, exiting with code 1`
  - missed [critical] failed_test: `examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries`
  - missed [important] stack_location: `/work/run-tests.js`

### `lint-react-001`

- **raw** — pred `formatting_failure` @ 0.95 [CONFIDENT_ERROR]
  - missed [optional] step_name: `Run prettier`
- **tail** — pred `formatting_failure` @ 0.95 [CONFIDENT_ERROR]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
- **grep** — pred `formatting_failure` @ 0.85 [CONFIDENT_ERROR]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
- **rtk-read** — pred `formatting_failure` @ 0.92 [CONFIDENT_ERROR]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
- **rtk-log** — pred `formatting_failure` @ 0.85 [CONFIDENT_ERROR]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
- **rtk-err-cat** — pred `unknown` @ 0.20 [abstained]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
- **llm-summary-v1-mock** — pred `formatting_failure` @ 0.35
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`

### `mypy-pandas-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
  - … and 1 more
- **tail** — pred `type_error` @ 0.80
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
- **grep** — pred `type_error` @ 0.82
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] step_name: `mypy (stubtest)`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
  - … and 1 more
- **rtk-log** — pred `type_error` @ 0.72
  - missed [critical] stack_location: `pandas/compat/pyarrow.py`
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
- **rtk-err-cat** — pred `type_error` @ 0.78
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`
- **llm-summary-v1-mock** — pred `type_error` @ 0.88
  - missed [critical] compile_error: `error: Module has no attribute "is_null"  [attr-defined]`
  - missed [important] compile_error: `error: Call to untyped function "fill_null" in typed context  [no-untyped-call]`
  - missed [critical] assertion: `Found 279 errors in 9 files (checked 1458 source files)`
  - missed [critical] step_name: `mypy (stubtest)`

### `pytest-pandas-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] stack_location: `pandas/tests/arrays/masked/test_indexing.py`
  - missed [critical] exception: `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
  - … and 1 more
- **tail** — pred `other` @ 0.72 [CONFIDENT_ERROR]
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] stack_location: `pandas/tests/arrays/masked/test_indexing.py`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
- **grep** — pred `other` @ 0.92 [CONFIDENT_ERROR]
  - missed [important] step_name: `==================================== ERRORS ====================================`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] stack_location: `pandas/tests/arrays/masked/test_indexing.py`
  - missed [critical] exception: `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
  - … and 1 more
- **rtk-log** — pred `other` @ 0.82 [CONFIDENT_ERROR]
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] exception: `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`
  - missed [critical] exit_code: `1`
- **rtk-err-cat** — pred `test_assertion` @ 0.85
  - missed [important] step_name: `==================================== ERRORS ====================================`
- **llm-summary-v1-mock** — pred `other` @ 0.80 [CONFIDENT_ERROR]
  - missed [important] step_name: `==================================== ERRORS ====================================`
  - missed [critical] failed_test: `pandas/tests/arithmetic/test_datetime64.py::TestDatetimeIndexComparisons::test_d…`
  - missed [critical] assertion: `= 45 failed, 162298 passed, 25570 skipped, 701 xfailed, 52 errors in 759.43s`

## Interpretation guardrails

- Mock diagnoser results validate the pipeline, not real LLM quality. If `diagnoser` is `debugger-v1-mock`, the numbers are shaped by simple pattern rules; they should not be read as an endorsement of any context method.
- Deterministic diagnosis scoring is a proxy, not a full semantic judge. A method can lose this proxy while producing a diagnosis a human would accept, and vice versa.
- Raw context is not guaranteed to win with a weak diagnoser: the diagnoser may drown in irrelevant lines.
- High signal recall does not necessarily imply high diagnosis accuracy. The context method may preserve evidence in a form the diagnoser ignores.
- Low context token count is only useful if diagnosis quality remains acceptable. A 99% reduction that forces abstention is not a win.
- `score_v1` is experimental. The individual metrics are what this report is about.

