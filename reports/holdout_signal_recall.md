# CILogBench signal-recall report — `holdout`

Context-provider baselines scored against per-case ground truth. `raw` must score 100% on all recall metrics — if it does not, the evaluator or the annotations are wrong. `Mapping` indicates whether a method preserves original raw.log line numbers (`line`) or only transformed text (`text`). Evidence coverage is line-based and shows N/A for text-mapped methods.

## Summary

| Method | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping | Processing Tokens | Final Context Tokens |
|---|---:|---:|---:|---:|---|---:|---:|
| raw | 100.0% | 100.0% | 100.0% | 0.0% | line | 0 | 11.1k |
| tail | 93.1% | 95.0% | 100.0% | 51.3% | line | 0 | 4.6k |
| grep | 89.8% | 95.0% | 73.1% | 87.0% | line | 0 | 1.5k |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | text | 0 | 11.1k |
| rtk-log | 33.1% | 36.0% | N/A | 97.5% | text | 0 | 261 |
| rtk-err-cat | 48.8% | 43.0% | N/A | 97.0% | text | 0 | 367 |
| llm-summary-v1-mock | 60.1% | 58.0% | N/A | 96.6% | text | 13.7k | 362 |
| llm-summary-v1-haiku | 47.6% | 57.0% | N/A | 96.2% | text | 2.8k | 384 |

Token columns are per-case averages. _Processing Tokens_ counts summarization cost (map+reduce input+output tokens) and is 0 for non-LLM baselines. _Final Context Tokens_ estimates the size of the context handed to a downstream reader.

Cases in split: **5**.

## Per-case signal recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | 100.0% | 80.0% | 80.0% | 100.0% | 20.0% | 20.0% | 60.0% | 0.0% |
| `dependabot-cargo-001` | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% | 50.0% | 66.7% | 50.0% |
| `docs-transformers-001` | 100.0% | 100.0% | 100.0% | 100.0% | 33.3% | 66.7% | 66.7% | 66.7% |
| `pushpr-nextjs-001` | 100.0% | 85.7% | 85.7% | 100.0% | 28.6% | 57.1% | 57.1% | 71.4% |
| `tsc-typescript-001` | 100.0% | 100.0% | 83.3% | 100.0% | 33.3% | 50.0% | 50.0% | 50.0% |

## Per-case critical signal recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | 100.0% | 75.0% | 75.0% | 100.0% | 25.0% | 0.0% | 50.0% | 0.0% |
| `dependabot-cargo-001` | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% | 25.0% | 50.0% | 50.0% |
| `docs-transformers-001` | 100.0% | 100.0% | 100.0% | 100.0% | 40.0% | 60.0% | 60.0% | 80.0% |
| `pushpr-nextjs-001` | 100.0% | 100.0% | 100.0% | 100.0% | 40.0% | 80.0% | 80.0% | 80.0% |
| `tsc-typescript-001` | 100.0% | 100.0% | 100.0% | 100.0% | 25.0% | 50.0% | 50.0% | 75.0% |

## Per-case reduction

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock | llm-summary-v1-haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | 0.0% | 41.1% | 93.4% | 0.0% | 98.2% | 98.3% | 97.2% | 96.5% |
| `dependabot-cargo-001` | 0.0% | 24.6% | 79.3% | 0.0% | 96.9% | 98.4% | 95.8% | 95.4% |
| `docs-transformers-001` | 0.0% | 70.2% | 87.7% | 0.0% | 98.0% | 98.5% | 97.0% | 96.9% |
| `pushpr-nextjs-001` | 0.0% | 78.9% | 87.0% | 0.0% | 98.1% | 94.6% | 97.2% | 97.6% |
| `tsc-typescript-001` | 0.0% | 41.8% | 87.5% | 0.0% | 96.3% | 95.1% | 95.9% | 94.4% |

## Notable misses

### `actions-terraform-001`

- **tail** — missed 1 signal(s):
  - type=step_name · importance=critical · value='Check Changelog Entry'
- **grep** — missed 1 signal(s):
  - type=step_name · importance=critical · value='Check Changelog Entry'
- **rtk-log** — missed 4 signal(s):
  - type=step_name · importance=critical · value='Check Changelog Entry'
  - type=command · importance=important · value='core.setFailed(commentDetails);'
  - type=assertion · importance=critical · value='Please add a changelog entry'
  - type=assertion · importance=critical · value='no-changelog-needed'
- **rtk-err-cat** — missed 4 signal(s):
  - type=step_name · importance=critical · value='Check Changelog Entry'
  - type=assertion · importance=critical · value='Please add a changelog entry'
  - type=assertion · importance=critical · value='no-changelog-needed'
  - type=annotation · importance=critical · value='##[error]Currently this PR would target a v1.16 release.'
- **llm-summary-v1-mock** — missed 2 signal(s):
  - type=step_name · importance=critical · value='Check Changelog Entry'
  - type=assertion · importance=critical · value='no-changelog-needed'
- **llm-summary-v1-haiku** — missed 5 signal(s):
  - type=step_name · importance=critical · value='Check Changelog Entry'
  - type=command · importance=important · value='core.setFailed(commentDetails);'
  - type=assertion · importance=critical · value='Please add a changelog entry'
  - type=assertion · importance=critical · value='no-changelog-needed'
  - type=annotation · importance=critical · value='##[error]Currently this PR would target a v1.16 release.'

### `dependabot-cargo-001`

- **rtk-log** — missed 3 signal(s):
  - type=assertion · importance=critical · value='security_update_not_needed'
  - type=package · importance=critical · value='"dependency-name": "rand"'
  - type=exception · importance=important · value='Error: Command failed with exit code 1'
- **rtk-err-cat** — missed 3 signal(s):
  - type=assertion · importance=critical · value="Dependabot encountered '1' error(s) during execution"
  - type=assertion · importance=critical · value='security_update_not_needed'
  - type=package · importance=critical · value='"dependency-name": "rand"'
- **llm-summary-v1-mock** — missed 2 signal(s):
  - type=assertion · importance=critical · value='security_update_not_needed'
  - type=package · importance=critical · value='"dependency-name": "rand"'
- **llm-summary-v1-haiku** — missed 3 signal(s):
  - type=assertion · importance=critical · value='security_update_not_needed'
  - type=package · importance=critical · value='"dependency-name": "rand"'
  - type=exception · importance=important · value='Failure running container'

### `docs-transformers-001`

- **rtk-log** — missed 4 signal(s):
  - type=stack_location · importance=critical · file=transformers/modeling_utils.py:1974
  - type=exception · importance=critical · value='<<<<<<< sonic-moe'
  - type=exception · importance=critical · value='There was an error when converting ../transformers/docs/source/en/model_doc/llama.md to the MDX form…'
  - type=annotation · importance=important · value='::error::Doc build failed because warnings were emitted'
- **rtk-err-cat** — missed 2 signal(s):
  - type=stack_location · importance=critical · file=transformers/modeling_utils.py:1974
  - type=exception · importance=critical · value='<<<<<<< sonic-moe'
- **llm-summary-v1-mock** — missed 2 signal(s):
  - type=stack_location · importance=critical · file=transformers/modeling_utils.py:1974
  - type=exception · importance=critical · value='<<<<<<< sonic-moe'
- **llm-summary-v1-haiku** — missed 2 signal(s):
  - type=exception · importance=critical · value='There was an error when converting ../transformers/docs/source/en/model_doc/llama.md to the MDX form…'
  - type=annotation · importance=important · value='::error::Doc build failed because warnings were emitted'

### `pushpr-nextjs-001`

- **tail** — missed 1 signal(s):
  - type=step_name · importance=important · value='create-pull-request'
- **grep** — missed 1 signal(s):
  - type=step_name · importance=important · value='create-pull-request'
- **rtk-log** — missed 5 signal(s):
  - type=step_name · importance=important · value='create-pull-request'
  - type=command · importance=critical · value='git push origin update/react/19.3.0-canary-142cfde8-20260422'
  - type=exception · importance=critical · value='remote: Permission to vercel/next.js.git denied to nextjs-bot.'
  - type=exception · importance=critical · value="fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL returned error: 403"
  - type=stack_location · importance=important · file=/home/runner/work/next.js/next.js/scripts/sync-react.js:645
- **rtk-err-cat** — missed 3 signal(s):
  - type=step_name · importance=important · value='create-pull-request'
  - type=exception · importance=critical · value='remote: Permission to vercel/next.js.git denied to nextjs-bot.'
  - type=stack_location · importance=important · file=/home/runner/work/next.js/next.js/scripts/sync-react.js:645
- **llm-summary-v1-mock** — missed 3 signal(s):
  - type=step_name · importance=important · value='create-pull-request'
  - type=exception · importance=critical · value='remote: Permission to vercel/next.js.git denied to nextjs-bot.'
  - type=stack_location · importance=important · file=/home/runner/work/next.js/next.js/scripts/sync-react.js:645
- **llm-summary-v1-haiku** — missed 2 signal(s):
  - type=step_name · importance=important · value='create-pull-request'
  - type=exception · importance=critical · value='Error: Command failed with exit code 128'

### `tsc-typescript-001`

- **grep** — missed 1 signal(s):
  - type=assertion · importance=important · value='1 failing'
- **rtk-log** — missed 4 signal(s):
  - type=failed_test · importance=critical · value='codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts'
  - type=assertion · importance=critical · value="AssertionError: expected 'Add return type \\'Foo<string>\\'' to equal 'Add return type \\'Foo<string, s…"
  - type=stack_location · importance=critical · file=src/harness/fourslashImpl.ts:3435
  - type=assertion · importance=important · value='1 failing'
- **rtk-err-cat** — missed 3 signal(s):
  - type=failed_test · importance=critical · value='codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts'
  - type=stack_location · importance=critical · file=src/harness/fourslashImpl.ts:3435
  - type=assertion · importance=important · value='1 failing'
- **llm-summary-v1-mock** — missed 3 signal(s):
  - type=failed_test · importance=critical · value='codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts'
  - type=stack_location · importance=critical · file=src/harness/fourslashImpl.ts:3435
  - type=assertion · importance=important · value='1 failing'
- **llm-summary-v1-haiku** — missed 3 signal(s):
  - type=assertion · importance=critical · value="AssertionError: expected 'Add return type \\'Foo<string>\\'' to equal 'Add return type \\'Foo<string, s…"
  - type=assertion · importance=important · value='1 failing'
  - type=assertion · importance=important · value='Error: Process exited with code: 1'

