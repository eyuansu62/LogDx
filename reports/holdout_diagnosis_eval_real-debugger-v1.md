# CILogBench diagnosis report — `holdout` / `real-debugger-v1`

Prompt SHA256 (first 12): `ecffdf03c99a…`
Cases in split: **5**
Methods evaluated: **7** (`raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`)

This report scores whether a **fixed diagnoser** can identify the CI failure root cause given each context method's output. It does NOT evaluate the context methods on their own; that lives in the signal-recall report.

## Main metrics (macro-averaged per context method)

| Context Method | Success | Category Acc | Critical Mention | Must Mention | File Recall | Test Recall | Forbidden | Conf Err | Context Tok | Diagnosis Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 60.0% | 76.0% | 91.0% | 75.0% | 100.0% | 0.0% | 40.0% | 11.1k | 462 | 0.580 |
| tail | 100.0% | 80.0% | 85.0% | 86.0% | 50.0% | 100.0% | 0.0% | 20.0% | 4.6k | 446 | 0.682 |
| grep | 100.0% | 60.0% | 76.0% | 88.0% | 37.5% | 100.0% | 0.0% | 40.0% | 1.5k | 396 | 0.549 |
| rtk-read | 100.0% | 60.0% | 85.0% | 91.0% | 100.0% | 100.0% | 0.0% | 40.0% | 11.1k | 510 | 0.614 |
| rtk-log | 100.0% | 40.0% | 31.0% | 45.0% | 0.0% | 0.0% | 0.0% | 20.0% | 260 | 335 | 0.273 |
| rtk-err-cat | 100.0% | 60.0% | 35.0% | 52.0% | 12.5% | 0.0% | 0.0% | 0.0% | 365 | 327 | 0.411 |
| llm-summary-v1-mock | 100.0% | 60.0% | 53.0% | 61.0% | 12.5% | 0.0% | 0.0% | 20.0% | 362 | 324 | 0.438 |

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
| `actions-terraform-001` | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `dependabot-cargo-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `docs-transformers-001` | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `pushpr-nextjs-001` | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% |
| `tsc-typescript-001` | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

## Per-case critical signal mention recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | 75.0% | 50.0% | 100.0% | 75.0% | 25.0% | 25.0% | 50.0% |
| `dependabot-cargo-001` | 25.0% | 75.0% | 25.0% | 50.0% | 25.0% | 0.0% | 25.0% |
| `docs-transformers-001` | 100.0% | 100.0% | 80.0% | 100.0% | 40.0% | 20.0% | 60.0% |
| `pushpr-nextjs-001` | 80.0% | 100.0% | 100.0% | 100.0% | 40.0% | 80.0% | 80.0% |
| `tsc-typescript-001` | 100.0% | 100.0% | 75.0% | 100.0% | 25.0% | 50.0% | 50.0% |

## Per-case forbidden-claim violations

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `dependabot-cargo-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs-transformers-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `pushpr-nextjs-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tsc-typescript-001` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Per-case abstention

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | — | — | — | — | — | abst. | — |
| `dependabot-cargo-001` | — | — | — | — | — | — | abst. |
| `docs-transformers-001` | — | — | — | — | — | — | — |
| `pushpr-nextjs-001` | — | — | — | — | — | — | — |
| `tsc-typescript-001` | — | — | — | — | — | — | — |

## Per-case confident error

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | ERR | — | ERR | ERR | ERR | — | ERR |
| `dependabot-cargo-001` | ERR | ERR | ERR | ERR | — | — | — |
| `docs-transformers-001` | — | — | — | — | — | — | — |
| `pushpr-nextjs-001` | — | — | — | — | — | — | — |
| `tsc-typescript-001` | — | — | — | — | — | — | — |

## Per-case failure analysis

### `actions-terraform-001`

- **raw** — pred `test_assertion` @ 0.95 [CONFIDENT_ERROR]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
- **tail** — pred `github_actions_config` @ 0.85
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `no-changelog-needed`
- **grep** — pred `test_assertion` @ 0.85 [CONFIDENT_ERROR]
- **rtk-read** — pred `test_assertion` @ 0.95 [CONFIDENT_ERROR]
  - missed [critical] step_name: `Check Changelog Entry`
- **rtk-log** — pred `test_assertion` @ 0.85 [CONFIDENT_ERROR]
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **rtk-err-cat** — pred `unknown` @ 0.10 [abstained]
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **llm-summary-v1-mock** — pred `other` @ 0.95 [CONFIDENT_ERROR]
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`

### `dependabot-cargo-001`

- **raw** — pred `other` @ 0.85 [CONFIDENT_ERROR]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [critical] annotation: `##[error]Dependabot encountered an error performing the update`
- **tail** — pred `other` @ 0.80 [CONFIDENT_ERROR]
  - missed [critical] annotation: `##[error]Dependabot encountered an error performing the update`
- **grep** — pred `other` @ 0.87 [CONFIDENT_ERROR]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [critical] annotation: `##[error]Dependabot encountered an error performing the update`
- **rtk-read** — pred `other` @ 0.82 [CONFIDENT_ERROR]
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [critical] annotation: `##[error]Dependabot encountered an error performing the update`
- **rtk-log** — pred `network_or_flaky` @ 0.50
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - missed [critical] annotation: `##[error]Dependabot encountered an error performing the update`
- **rtk-err-cat** — pred `permission_or_secret` @ 0.45
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more
- **llm-summary-v1-mock** — pred `unknown` @ 0.15 [abstained]
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [critical] annotation: `##[error]Dependabot encountered an error performing the update`

### `docs-transformers-001`

- **raw** — pred `compile_error` @ 0.96
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **tail** — pred `compile_error` @ 0.92
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **grep** — pred `compile_error` @ 0.95
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **rtk-read** — pred `compile_error` @ 0.95
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **rtk-log** — pred `compile_error` @ 0.82
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **rtk-err-cat** — pred `compile_error` @ 0.85
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exit_code: `1`
- **llm-summary-v1-mock** — pred `compile_error` @ 0.85
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`

### `pushpr-nextjs-001`

- **raw** — pred `permission_or_secret` @ 0.85
  - missed [important] step_name: `create-pull-request`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [important] stack_location: `/home/runner/work/next.js/next.js/scripts/sync-react.js`
- **tail** — pred `permission_or_secret` @ 0.92
  - missed [important] step_name: `create-pull-request`
  - missed [important] stack_location: `/home/runner/work/next.js/next.js/scripts/sync-react.js`
- **grep** — pred `permission_or_secret` @ 0.90
  - missed [important] step_name: `create-pull-request`
  - missed [important] stack_location: `/home/runner/work/next.js/next.js/scripts/sync-react.js`
- **rtk-read** — pred `permission_or_secret` @ 0.95
  - missed [important] step_name: `create-pull-request`
  - missed [important] stack_location: `/home/runner/work/next.js/next.js/scripts/sync-react.js`
- **rtk-log** — pred `network_or_flaky` @ 0.55
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - missed [important] stack_location: `/home/runner/work/next.js/next.js/scripts/sync-react.js`
- **rtk-err-cat** — pred `permission_or_secret` @ 0.85
  - missed [important] step_name: `create-pull-request`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [important] stack_location: `/home/runner/work/next.js/next.js/scripts/sync-react.js`
- **llm-summary-v1-mock** — pred `permission_or_secret` @ 0.85
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [important] stack_location: `/home/runner/work/next.js/next.js/scripts/sync-react.js`

### `tsc-typescript-001`

- **raw** — pred `test_assertion` @ 0.92
  - missed [important] assertion: `Error: Process exited with code: 1`
- **tail** — pred `test_assertion` @ 0.92
  - missed [important] assertion: `Error: Process exited with code: 1`
- **grep** — pred `test_assertion` @ 0.85
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
  - missed [critical] exit_code: `1`
- **rtk-read** — pred `test_assertion` @ 0.95
  - missed [important] assertion: `Error: Process exited with code: 1`
- **rtk-log** — pred `test_assertion` @ 0.82
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] assertion: `AssertionError: expected 'Add return type \'Foo<string>\'' to equal 'Add return …`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
- **rtk-err-cat** — pred `test_assertion` @ 0.85
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
- **llm-summary-v1-mock** — pred `test_assertion` @ 0.78
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`

## Interpretation guardrails

- Mock diagnoser results validate the pipeline, not real LLM quality. If `diagnoser` is `debugger-v1-mock`, the numbers are shaped by simple pattern rules; they should not be read as an endorsement of any context method.
- Deterministic diagnosis scoring is a proxy, not a full semantic judge. A method can lose this proxy while producing a diagnosis a human would accept, and vice versa.
- Raw context is not guaranteed to win with a weak diagnoser: the diagnoser may drown in irrelevant lines.
- High signal recall does not necessarily imply high diagnosis accuracy. The context method may preserve evidence in a form the diagnoser ignores.
- Low context token count is only useful if diagnosis quality remains acceptable. A 99% reduction that forces abstention is not a win.
- `score_v1` is experimental. The individual metrics are what this report is about.

