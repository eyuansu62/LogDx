# CILogBench diagnosis report — `stress` / `real-debugger-v1`

Prompt SHA256 (first 12): `ecffdf03c99a…`
Cases in split: **6**
Methods evaluated: **7** (`raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`)

This report scores whether a **fixed diagnoser** can identify the CI failure root cause given each context method's output. It does NOT evaluate the context methods on their own; that lives in the signal-recall report.

## Main metrics (macro-averaged per context method)

| Context Method | Success | Category Acc | Critical Mention | Must Mention | File Recall | Test Recall | Forbidden | Conf Err | Context Tok | Diagnosis Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 50.0% | 57.5% | 66.7% | 33.3% | 0.0% | 0.0% | 16.7% | 91.2k | 290 | 0.429 |
| tail | 100.0% | 83.3% | 81.7% | 91.7% | 100.0% | 0.0% | 0.0% | 16.7% | 5.0k | 386 | 0.669 |
| grep | 100.0% | 83.3% | 80.0% | 100.0% | 100.0% | 0.0% | 0.0% | 16.7% | 1.9k | 358 | 0.686 |
| rtk-read | 100.0% | 33.3% | 65.8% | 66.7% | 33.3% | 0.0% | 0.0% | 33.3% | 91.2k | 284 | 0.364 |
| rtk-log | 100.0% | 0.0% | 34.2% | 16.7% | 0.0% | 0.0% | 0.0% | 33.3% | 165 | 284 | 0.146 |
| rtk-err-cat | 100.0% | 50.0% | 34.2% | 41.7% | 66.7% | 100.0% | 0.0% | 0.0% | 2.5k | 214 | 0.420 |
| llm-summary-v1-mock | 100.0% | 50.0% | 61.7% | 41.7% | 66.7% | 100.0% | 0.0% | 0.0% | 373 | 289 | 0.489 |

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
| `cleanup-k8s-stress-001` | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| `cleanup-tsc-stress-001` | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| `docbuild-hf-stress-001` | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% | 100.0% |
| `prettier-react-stress-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `pytest-sklearn-stress-001` | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% | 100.0% |
| `pytest-sklearn-stress-002` | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% | 100.0% |

## Per-case critical signal mention recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | 75.0% | 75.0% | 50.0% | 100.0% | 25.0% | 0.0% | 75.0% |
| `cleanup-tsc-stress-001` | 50.0% | 75.0% | 75.0% | 75.0% | 75.0% | 0.0% | 50.0% |
| `docbuild-hf-stress-001` | 80.0% | 100.0% | 100.0% | 80.0% | 40.0% | 20.0% | 20.0% |
| `prettier-react-stress-001` | 100.0% | 100.0% | 75.0% | 100.0% | 25.0% | 25.0% | 25.0% |
| `pytest-sklearn-stress-001` | 20.0% | 80.0% | 100.0% | 20.0% | 20.0% | 80.0% | 100.0% |
| `pytest-sklearn-stress-002` | 20.0% | 60.0% | 80.0% | 20.0% | 20.0% | 80.0% | 100.0% |

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
| `cleanup-k8s-stress-001` | — | — | — | — | abst. | abst. | abst. |
| `cleanup-tsc-stress-001` | — | — | — | — | abst. | abst. | abst. |
| `docbuild-hf-stress-001` | — | — | — | — | abst. | — | — |
| `prettier-react-stress-001` | — | — | — | — | — | abst. | — |
| `pytest-sklearn-stress-001` | abst. | — | — | abst. | — | — | — |
| `pytest-sklearn-stress-002` | abst. | — | — | abst. | — | — | — |

## Per-case confident error

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | — | — | — | — | — | — | — |
| `cleanup-tsc-stress-001` | — | — | — | — | — | — | — |
| `docbuild-hf-stress-001` | — | — | — | ERR | — | — | — |
| `prettier-react-stress-001` | ERR | ERR | ERR | ERR | — | — | — |
| `pytest-sklearn-stress-001` | — | — | — | — | ERR | — | — |
| `pytest-sklearn-stress-002` | — | — | — | — | ERR | — | — |

## Per-case failure analysis

### `cleanup-k8s-stress-001`

- **raw** — pred `permission_or_secret` @ 0.82
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
- **tail** — pred `permission_or_secret` @ 0.82
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
- **grep** — pred `permission_or_secret` @ 0.90
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
- **rtk-read** — pred `permission_or_secret` @ 0.85
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
- **rtk-log** — pred `unknown` @ 0.15 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
- **rtk-err-cat** — pred `unknown` @ 0.10 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **llm-summary-v1-mock** — pred `unknown` @ 0.10 [abstained]
  - missed [important] command: `Deleting artifacts for run ID: 23485708914`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`

### `cleanup-tsc-stress-001`

- **raw** — pred `permission_or_secret` @ 0.78
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **tail** — pred `permission_or_secret` @ 0.85
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
- **grep** — pred `permission_or_secret` @ 0.85
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
- **rtk-read** — pred `permission_or_secret` @ 0.85
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
- **rtk-log** — pred `unknown` @ 0.10 [abstained]
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Cleanup artifacts`
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **llm-summary-v1-mock** — pred `unknown` @ 0.10 [abstained]
  - missed [important] command: `Deleting artifacts for run ID: 24823635328`
  - missed [critical] exception: `gh: Resource not accessible by integration (HTTP 403)`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`

### `docbuild-hf-stress-001`

- **raw** — pred `github_actions_config` @ 0.65
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
- **tail** — pred `github_actions_config` @ 0.85
- **grep** — pred `github_actions_config` @ 0.75
- **rtk-read** — pred `other` @ 0.70 [CONFIDENT_ERROR]
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
- **rtk-log** — pred `unknown` @ 0.05 [abstained]
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
- **rtk-err-cat** — pred `github_actions_config` @ 0.40
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`
  - missed [critical] exit_code: `1`
- **llm-summary-v1-mock** — pred `github_actions_config` @ 0.70
  - missed [critical] step_name: `doc_build_status_check`
  - missed [critical] command: `if [[ "failure" == "success" || "failure" == "skipped" ]] && \`
  - missed [critical] command: `exit 1`
  - missed [critical] annotation: `##[error]Process completed with exit code 1.`

### `prettier-react-stress-001`

- **raw** — pred `formatting_failure` @ 0.95 [CONFIDENT_ERROR]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
- **tail** — pred `formatting_failure` @ 0.95 [CONFIDENT_ERROR]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
- **grep** — pred `formatting_failure` @ 0.85 [CONFIDENT_ERROR]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
- **rtk-read** — pred `formatting_failure` @ 0.95 [CONFIDENT_ERROR]
  - missed [optional] step_name: `Run prettier`
  - missed [important] command: `yarn prettier-check`
- **rtk-log** — pred `formatting_failure` @ 0.65
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
- **rtk-err-cat** — pred `unknown` @ 0.15 [abstained]
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`
- **llm-summary-v1-mock** — pred `formatting_failure` @ 0.55
  - missed [important] command: `yarn prettier-check`
  - missed [critical] assertion: `This project uses prettier to format all JavaScript code.`
  - missed [critical] stack_location: `packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js`
  - missed [critical] stack_location: `compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactive…`

### `pytest-sklearn-stress-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **tail** — pred `test_assertion` @ 0.85
  - missed [critical] assertion: `1 failed`
- **grep** — pred `test_assertion` @ 0.85
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **rtk-log** — pred `compile_error` @ 0.80 [CONFIDENT_ERROR]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **rtk-err-cat** — pred `test_assertion` @ 0.85
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **llm-summary-v1-mock** — pred `test_assertion` @ 0.85
  - missed [important] assertion: `LogisticRegression()`

### `pytest-sklearn-stress-002`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **tail** — pred `test_assertion` @ 0.95
  - missed [critical] exception: `DocTestFailure`
  - missed [critical] assertion: `1 failed`
- **grep** — pred `test_assertion` @ 0.85
  - missed [critical] assertion: `1 failed`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **rtk-log** — pred `compile_error` @ 0.80 [CONFIDENT_ERROR]
  - missed [critical] failed_test: `FAILED`
  - missed [critical] stack_location: `doc/callbacks.rst`
  - missed [critical] exception: `DocTestFailure`
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **rtk-err-cat** — pred `test_assertion` @ 0.85
  - missed [important] assertion: `LogisticRegression()`
  - missed [critical] assertion: `1 failed`
- **llm-summary-v1-mock** — pred `test_assertion` @ 0.85
  - missed [important] assertion: `LogisticRegression()`

## Interpretation guardrails

- Mock diagnoser results validate the pipeline, not real LLM quality. If `diagnoser` is `debugger-v1-mock`, the numbers are shaped by simple pattern rules; they should not be read as an endorsement of any context method.
- Deterministic diagnosis scoring is a proxy, not a full semantic judge. A method can lose this proxy while producing a diagnosis a human would accept, and vice versa.
- Raw context is not guaranteed to win with a weak diagnoser: the diagnoser may drown in irrelevant lines.
- High signal recall does not necessarily imply high diagnosis accuracy. The context method may preserve evidence in a form the diagnoser ignores.
- Low context token count is only useful if diagnosis quality remains acceptable. A 99% reduction that forces abstention is not a win.
- `score_v1` is experimental. The individual metrics are what this report is about.

