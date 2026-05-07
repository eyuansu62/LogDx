# CILogBench signal-recall report — `stress`

Context-provider baselines scored against per-case ground truth. `raw` must score 100% on all recall metrics — if it does not, the evaluator or the annotations are wrong. `Mapping` indicates whether a method preserves original raw.log line numbers (`line`) or only transformed text (`text`). Evidence coverage is line-based and shows N/A for text-mapped methods.

## Summary

| Method | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping | Processing Tokens | Final Context Tokens |
|---|---:|---:|---:|---:|---|---:|---:|
| raw | 100.0% | 100.0% | 100.0% | 0.0% | line | 0 | 91.6k |
| tail | 100.0% | 100.0% | 100.0% | 33.5% | line | 0 | 5.0k |
| grep | 86.2% | 87.5% | 86.5% | 89.7% | line | 0 | 1.9k |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | text | 0 | 91.6k |
| rtk-log | 30.3% | 34.2% | N/A | 96.9% | text | 0 | 164 |
| rtk-err-cat | 39.2% | 44.2% | N/A | 97.2% | text | 0 | 2.6k |
| llm-summary-v1-mock | 55.9% | 64.2% | N/A | 91.9% | text | 101.2k | 373 |
| llm-summary-v1-haiku | 66.4% | 71.2% | N/A | 69.9% | text | 2.3k | 346 |

Token columns are per-case averages. _Processing Tokens_ counts summarization cost (map+reduce input+output tokens) and is 0 for non-LLM baselines. _Final Context Tokens_ estimates the size of the context handed to a downstream reader.

Cases in split: **6**.

## Per-case signal recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | 100.0% | 100.0% | 80.0% | 100.0% | 40.0% | 0.0% | 40.0% | 60.0% |
| `cleanup-tsc-stress-001` | 100.0% | 100.0% | 80.0% | 100.0% | 40.0% | 0.0% | 40.0% | 60.0% |
| `docbuild-hf-stress-001` | 100.0% | 100.0% | 100.0% | 100.0% | 40.0% | 40.0% | 60.0% | 60.0% |
| `prettier-react-stress-001` | 100.0% | 100.0% | 57.1% | 100.0% | 28.6% | 28.6% | 28.6% | 85.7% |
| `pytest-sklearn-stress-001` | 100.0% | 100.0% | 100.0% | 100.0% | 16.7% | 83.3% | 83.3% | — |
| `pytest-sklearn-stress-002` | 100.0% | 100.0% | 100.0% | 100.0% | 16.7% | 83.3% | 83.3% | — |

## Per-case critical signal recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | 100.0% | 100.0% | 75.0% | 100.0% | 50.0% | 0.0% | 50.0% | 75.0% |
| `cleanup-tsc-stress-001` | 100.0% | 100.0% | 75.0% | 100.0% | 50.0% | 0.0% | 50.0% | 75.0% |
| `docbuild-hf-stress-001` | 100.0% | 100.0% | 100.0% | 100.0% | 40.0% | 40.0% | 60.0% | 60.0% |
| `prettier-react-stress-001` | 100.0% | 100.0% | 75.0% | 100.0% | 25.0% | 25.0% | 25.0% | 75.0% |
| `pytest-sklearn-stress-001` | 100.0% | 100.0% | 100.0% | 100.0% | 20.0% | 100.0% | 100.0% | — |
| `pytest-sklearn-stress-002` | 100.0% | 100.0% | 100.0% | 100.0% | 20.0% | 100.0% | 100.0% | — |

## Per-case reduction

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cleanup-k8s-stress-001` | 0.0% | 0.0% | 93.6% | 0.0% | 96.3% | 99.1% | 91.4% | 76.7% |
| `cleanup-tsc-stress-001` | 0.0% | 0.0% | 93.6% | 0.0% | 96.3% | 99.1% | 91.4% | 72.4% |
| `docbuild-hf-stress-001` | 0.0% | 0.0% | 62.2% | 0.0% | 92.2% | 91.4% | 72.1% | 38.3% |
| `prettier-react-stress-001` | 0.0% | 9.6% | 92.4% | 0.0% | 96.7% | 99.6% | 97.0% | 92.1% |
| `pytest-sklearn-stress-001` | 0.0% | 96.0% | 98.0% | 0.0% | 99.9% | 97.3% | 99.7% | — |
| `pytest-sklearn-stress-002` | 0.0% | 95.6% | 98.1% | 0.0% | 99.9% | 97.0% | 99.6% | — |

## Notable misses

### `cleanup-k8s-stress-001`

- **grep** — missed 1 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
- **rtk-log** — missed 3 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
  - type=command · importance=important · value='Deleting artifacts for run ID: 23485708914'
  - type=exception · importance=critical · value='gh: Resource not accessible by integration (HTTP 403)'
- **rtk-err-cat** — missed 5 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
  - type=command · importance=important · value='Deleting artifacts for run ID: 23485708914'
  - type=exception · importance=critical · value='gh: Resource not accessible by integration (HTTP 403)'
  - type=annotation · importance=critical · value='##[error]Process completed with exit code 1.'
  - type=exit_code · importance=critical · value='1'
- **llm-summary-v1-mock** — missed 3 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
  - type=command · importance=important · value='Deleting artifacts for run ID: 23485708914'
  - type=exception · importance=critical · value='gh: Resource not accessible by integration (HTTP 403)'
- **llm-summary-v1-haiku** — missed 2 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
  - type=command · importance=important · value='Deleting artifacts for run ID: 23485708914'

### `cleanup-tsc-stress-001`

- **grep** — missed 1 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
- **rtk-log** — missed 3 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
  - type=command · importance=important · value='Deleting artifacts for run ID: 24823635328'
  - type=exception · importance=critical · value='gh: Resource not accessible by integration (HTTP 403)'
- **rtk-err-cat** — missed 5 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
  - type=command · importance=important · value='Deleting artifacts for run ID: 24823635328'
  - type=exception · importance=critical · value='gh: Resource not accessible by integration (HTTP 403)'
  - type=annotation · importance=critical · value='##[error]Process completed with exit code 1.'
  - type=exit_code · importance=critical · value='1'
- **llm-summary-v1-mock** — missed 3 signal(s):
  - type=step_name · importance=critical · value='Cleanup artifacts'
  - type=command · importance=important · value='Deleting artifacts for run ID: 24823635328'
  - type=exception · importance=critical · value='gh: Resource not accessible by integration (HTTP 403)'
- **llm-summary-v1-haiku** — missed 2 signal(s):
  - type=command · importance=important · value='Deleting artifacts for run ID: 24823635328'
  - type=annotation · importance=critical · value='##[error]Process completed with exit code 1.'

### `docbuild-hf-stress-001`

- **rtk-log** — missed 3 signal(s):
  - type=step_name · importance=critical · value='doc_build_status_check'
  - type=command · importance=critical · value='if [[ "failure" == "success" || "failure" == "skipped" ]] && \\'
  - type=command · importance=critical · value='exit 1'
- **rtk-err-cat** — missed 3 signal(s):
  - type=step_name · importance=critical · value='doc_build_status_check'
  - type=command · importance=critical · value='exit 1'
  - type=annotation · importance=critical · value='##[error]Process completed with exit code 1.'
- **llm-summary-v1-mock** — missed 2 signal(s):
  - type=step_name · importance=critical · value='doc_build_status_check'
  - type=command · importance=critical · value='exit 1'
- **llm-summary-v1-haiku** — missed 2 signal(s):
  - type=command · importance=critical · value='if [[ "failure" == "success" || "failure" == "skipped" ]] && \\'
  - type=command · importance=critical · value='exit 1'

### `prettier-react-stress-001`

- **grep** — missed 3 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
- **rtk-log** — missed 5 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
  - type=stack_location · importance=critical · file=packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js:1
  - type=stack_location · importance=critical · file=compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactiveFunction.ts:1
- **rtk-err-cat** — missed 5 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
  - type=stack_location · importance=critical · file=packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js:1
  - type=stack_location · importance=critical · file=compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactiveFunction.ts:1
- **llm-summary-v1-mock** — missed 5 signal(s):
  - type=step_name · importance=optional · value='Run prettier'
  - type=command · importance=important · value='yarn prettier-check'
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'
  - type=stack_location · importance=critical · file=packages/react-dom/src/__tests__/ReactDOMFragmentRefs-test.js:1
  - type=stack_location · importance=critical · file=compiler/packages/babel-plugin-react-compiler/src/ReactiveScopes/CodegenReactiveFunction.ts:1
- **llm-summary-v1-haiku** — missed 1 signal(s):
  - type=assertion · importance=critical · value='This project uses prettier to format all JavaScript code.'

### `pytest-sklearn-stress-001`

- **rtk-log** — missed 5 signal(s):
  - type=failed_test · importance=critical · value='FAILED'
  - type=stack_location · importance=critical · file=doc/callbacks.rst:48
  - type=exception · importance=critical · value='DocTestFailure'
  - type=assertion · importance=important · value='LogisticRegression()'
  - type=assertion · importance=critical · value='1 failed'
- **rtk-err-cat** — missed 1 signal(s):
  - type=assertion · importance=important · value='LogisticRegression()'
- **llm-summary-v1-mock** — missed 1 signal(s):
  - type=assertion · importance=important · value='LogisticRegression()'

### `pytest-sklearn-stress-002`

- **rtk-log** — missed 5 signal(s):
  - type=failed_test · importance=critical · value='FAILED'
  - type=stack_location · importance=critical · file=doc/callbacks.rst:48
  - type=exception · importance=critical · value='DocTestFailure'
  - type=assertion · importance=important · value='LogisticRegression()'
  - type=assertion · importance=critical · value='1 failed'
- **rtk-err-cat** — missed 1 signal(s):
  - type=assertion · importance=important · value='LogisticRegression()'
- **llm-summary-v1-mock** — missed 1 signal(s):
  - type=assertion · importance=important · value='LogisticRegression()'

