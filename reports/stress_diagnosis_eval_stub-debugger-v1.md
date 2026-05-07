# CILogBench diagnosis report — `stress` / `stub-debugger-v1`

Prompt SHA256 (first 12): `ecffdf03c99a…`
Cases in split: **6**
Methods evaluated: **7** (`raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`)

This report scores whether a **fixed diagnoser** can identify the CI failure root cause given each context method's output. It does NOT evaluate the context methods on their own; that lives in the signal-recall report.

## Main metrics (macro-averaged per context method)

| Context Method | Success | Category Acc | Critical Mention | Must Mention | File Recall | Test Recall | Forbidden | Conf Err | Context Tok | Diagnosis Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 0.0% | 4.2% | 13.3% | 0.0% | 0.0% | 0.0% | 0.0% | 91.2k | 71 | 0.048 |
| tail | 100.0% | 0.0% | 4.2% | 13.3% | 0.0% | 0.0% | 0.0% | 0.0% | 5.0k | 71 | 0.048 |
| grep | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | 0.0% | 0.0% | 1.9k | 63 | 0.007 |
| rtk-read | 100.0% | 0.0% | 4.2% | 13.3% | 0.0% | 0.0% | 0.0% | 0.0% | 91.2k | 71 | 0.048 |
| rtk-log | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | 0.0% | 0.0% | 165 | 63 | 0.007 |
| rtk-err-cat | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | 0.0% | 0.0% | 2.5k | 63 | 0.007 |
| llm-summary-v1-mock | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | 0.0% | 0.0% | 373 | 63 | 0.007 |

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
| `cleanup-k8s-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `cleanup-tsc-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `docbuild-hf-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `prettier-react-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `pytest-sklearn-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `pytest-sklearn-stress-002` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

## Per-case critical signal mention recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `cleanup-tsc-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `docbuild-hf-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `prettier-react-stress-001` | 25.0% | 25.0% | 0.0% | 25.0% | 0.0% | 0.0% | 0.0% |
| `pytest-sklearn-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `pytest-sklearn-stress-002` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

## Per-case forbidden-claim violations

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `cleanup-tsc-stress-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `docbuild-hf-stress-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `prettier-react-stress-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `pytest-sklearn-stress-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `pytest-sklearn-stress-002` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-case abstention

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | abst. | abst. | abst. | abst. | abst. | abst. | abst. |
| `cleanup-tsc-stress-001` | abst. | abst. | abst. | abst. | abst. | abst. | abst. |
| `docbuild-hf-stress-001` | abst. | abst. | abst. | abst. | abst. | abst. | abst. |
| `prettier-react-stress-001` | — | — | abst. | — | abst. | abst. | abst. |
| `pytest-sklearn-stress-001` | abst. | abst. | abst. | abst. | abst. | abst. | abst. |
| `pytest-sklearn-stress-002` | abst. | abst. | abst. | abst. | abst. | abst. | abst. |

## Per-case confident error

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | — | — | — | — | — | — | — |
| `cleanup-tsc-stress-001` | — | — | — | — | — | — | — |
| `docbuild-hf-stress-001` | — | — | — | — | — | — | — |
| `prettier-react-stress-001` | — | — | — | — | — | — | — |
| `pytest-sklearn-stress-001` | — | — | — | — | — | — | — |
| `pytest-sklearn-stress-002` | — | — | — | — | — | — | — |

## Per-case failure analysis

### `cleanup-k8s-stress-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`

### `cleanup-tsc-stress-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`

### `docbuild-hf-stress-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`

### `prettier-react-stress-001`

- **raw** — pred `formatting_failure` @ 0.55
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
  - missed [important] assertion: `error Command failed with exit code 1.`
- **tail** — pred `formatting_failure` @ 0.55
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
  - missed [important] assertion: `error Command failed with exit code 1.`
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
  - … and 2 more
- **rtk-read** — pred `formatting_failure` @ 0.55
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
  - missed [important] assertion: `error Command failed with exit code 1.`
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
  - … and 2 more
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
  - … and 2 more
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
  - … and 2 more

### `pytest-sklearn-stress-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more

### `pytest-sklearn-stress-002`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
  - … and 1 more

## Interpretation guardrails

- Mock diagnoser results validate the pipeline, not real LLM quality. If `diagnoser` is `debugger-v1-mock`, the numbers are shaped by simple pattern rules; they should not be read as an endorsement of any context method.
- Deterministic diagnosis scoring is a proxy, not a full semantic judge. A method can lose this proxy while producing a diagnosis a human would accept, and vice versa.
- Raw context is not guaranteed to win with a weak diagnoser: the diagnoser may drown in irrelevant lines.
- High signal recall does not necessarily imply high diagnosis accuracy. The context method may preserve evidence in a form the diagnoser ignores.
- Low context token count is only useful if diagnosis quality remains acceptable. A 99% reduction that forces abstention is not a win.
- `score_v1` is experimental. The individual metrics are what this report is about.

