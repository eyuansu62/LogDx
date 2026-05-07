# CILogBench diagnosis report — `holdout` / `stub-debugger-v1`

Prompt SHA256 (first 12): `ecffdf03c99a…`
Cases in split: **5**
Methods evaluated: **7** (`raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`)

This report scores whether a **fixed diagnoser** can identify the CI failure root cause given each context method's output. It does NOT evaluate the context methods on their own; that lives in the signal-recall report.

## Main metrics (macro-averaged per context method)

| Context Method | Success | Category Acc | Critical Mention | Must Mention | File Recall | Test Recall | Forbidden | Conf Err | Context Tok | Diagnosis Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 20.0% | 18.0% | 8.0% | 0.0% | 0.0% | 0.0% | 0.0% | 11.1k | 101 | 0.150 |
| tail | 100.0% | 20.0% | 14.0% | 8.0% | 0.0% | 0.0% | 0.0% | 0.0% | 4.6k | 84 | 0.128 |
| grep | 100.0% | 20.0% | 14.0% | 8.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.5k | 92 | 0.128 |
| rtk-read | 100.0% | 20.0% | 18.0% | 8.0% | 0.0% | 0.0% | 0.0% | 0.0% | 11.1k | 101 | 0.150 |
| rtk-log | 100.0% | 20.0% | 5.0% | 8.0% | 0.0% | 0.0% | 0.0% | 0.0% | 260 | 74 | 0.091 |
| rtk-err-cat | 100.0% | 20.0% | 14.0% | 8.0% | 0.0% | 0.0% | 0.0% | 0.0% | 365 | 93 | 0.128 |
| llm-summary-v1-mock | 100.0% | 20.0% | 10.0% | 8.0% | 0.0% | 0.0% | 0.0% | 0.0% | 362 | 78 | 0.106 |

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
| `actions-terraform-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `dependabot-cargo-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `docs-transformers-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `pushpr-nextjs-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `tsc-typescript-001` | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

## Per-case critical signal mention recall

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `dependabot-cargo-001` | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `docs-transformers-001` | 20.0% | 20.0% | 0.0% | 20.0% | 0.0% | 0.0% | 0.0% |
| `pushpr-nextjs-001` | 20.0% | 0.0% | 20.0% | 20.0% | 0.0% | 20.0% | 0.0% |
| `tsc-typescript-001` | 50.0% | 50.0% | 50.0% | 50.0% | 25.0% | 50.0% | 50.0% |

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
| `actions-terraform-001` | abst. | abst. | abst. | abst. | abst. | abst. | abst. |
| `dependabot-cargo-001` | abst. | abst. | abst. | abst. | abst. | abst. | abst. |
| `docs-transformers-001` | — | — | abst. | — | abst. | abst. | abst. |
| `pushpr-nextjs-001` | — | abst. | — | — | abst. | — | abst. |
| `tsc-typescript-001` | — | — | — | — | — | — | — |

## Per-case confident error

| Case | raw | tail | grep | rtk-read | rtk-log | rtk-err-cat | llm-summary-v1-mock |
|---|---:|---:|---:|---:|---:|---:|---:|
| `actions-terraform-001` | — | — | — | — | — | — | — |
| `dependabot-cargo-001` | — | — | — | — | — | — | — |
| `docs-transformers-001` | — | — | — | — | — | — | — |
| `pushpr-nextjs-001` | — | — | — | — | — | — | — |
| `tsc-typescript-001` | — | — | — | — | — | — | — |

## Per-case failure analysis

### `actions-terraform-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] step_name: `Check Changelog Entry`
  - missed [important] command: `core.setFailed(commentDetails);`
  - missed [critical] assertion: `Please add a changelog entry`
  - missed [critical] assertion: `no-changelog-needed`
  - missed [critical] annotation: `##[error]Currently this PR would target a v1.16 release.`

### `dependabot-cargo-001`

- **raw** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more
- **rtk-read** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] assertion: `Dependabot encountered '1' error(s) during execution`
  - missed [critical] assertion: `security_update_not_needed`
  - missed [critical] package: `"dependency-name": "rand"`
  - missed [important] exception: `Failure running container`
  - missed [important] exception: `Error: Command failed with exit code 1`
  - … and 1 more

### `docs-transformers-001`

- **raw** — pred `lint_failure` @ 0.55
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **tail** — pred `lint_failure` @ 0.55
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **grep** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
  - … and 1 more
- **rtk-read** — pred `lint_failure` @ 0.55
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
  - … and 1 more
- **rtk-err-cat** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
  - … and 1 more
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [critical] stack_location: `transformers/modeling_utils.py`
  - missed [critical] exception: `<<<<<<< sonic-moe`
  - missed [critical] exception: `SyntaxError: invalid syntax`
  - missed [critical] exception: `There was an error when converting ../transformers/docs/source/en/model_doc/llam…`
  - missed [important] annotation: `::error::Doc build failed because warnings were emitted`
  - … and 1 more

### `pushpr-nextjs-001`

- **raw** — pred `lint_failure` @ 0.55
  - missed [important] step_name: `create-pull-request`
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - … and 1 more
- **tail** — pred `unknown` @ 0.00 [abstained]
  - missed [important] step_name: `create-pull-request`
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - … and 2 more
- **grep** — pred `lint_failure` @ 0.55
  - missed [important] step_name: `create-pull-request`
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - … and 1 more
- **rtk-read** — pred `lint_failure` @ 0.55
  - missed [important] step_name: `create-pull-request`
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - … and 1 more
- **rtk-log** — pred `unknown` @ 0.00 [abstained]
  - missed [important] step_name: `create-pull-request`
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - … and 2 more
- **rtk-err-cat** — pred `lint_failure` @ 0.55
  - missed [important] step_name: `create-pull-request`
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - … and 1 more
- **llm-summary-v1-mock** — pred `unknown` @ 0.00 [abstained]
  - missed [important] step_name: `create-pull-request`
  - missed [critical] command: `git push origin update/react/19.3.0-canary-142cfde8-20260422`
  - missed [critical] exception: `Error: Command failed with exit code 128`
  - missed [critical] exception: `remote: Permission to vercel/next.js.git denied to nextjs-bot.`
  - missed [critical] exception: `fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL …`
  - … and 2 more

### `tsc-typescript-001`

- **raw** — pred `test_assertion` @ 0.55
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
- **tail** — pred `test_assertion` @ 0.55
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
- **grep** — pred `test_assertion` @ 0.55
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
- **rtk-read** — pred `test_assertion` @ 0.55
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
- **rtk-log** — pred `test_assertion` @ 0.55
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] assertion: `AssertionError: expected 'Add return type \'Foo<string>\'' to equal 'Add return …`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
- **rtk-err-cat** — pred `test_assertion` @ 0.55
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`
- **llm-summary-v1-mock** — pred `test_assertion` @ 0.55
  - missed [critical] failed_test: `codeFixMissingTypeAnnotationOnExports52-generics-oversimplification.ts`
  - missed [critical] stack_location: `src/harness/fourslashImpl.ts`
  - missed [important] assertion: `1 failing`
  - missed [important] assertion: `Error: Process exited with code: 1`

## Interpretation guardrails

- Mock diagnoser results validate the pipeline, not real LLM quality. If `diagnoser` is `debugger-v1-mock`, the numbers are shaped by simple pattern rules; they should not be read as an endorsement of any context method.
- Deterministic diagnosis scoring is a proxy, not a full semantic judge. A method can lose this proxy while producing a diagnosis a human would accept, and vice versa.
- Raw context is not guaranteed to win with a weak diagnoser: the diagnoser may drown in irrelevant lines.
- High signal recall does not necessarily imply high diagnosis accuracy. The context method may preserve evidence in a form the diagnoser ignores.
- Low context token count is only useful if diagnosis quality remains acceptable. A 99% reduction that forces abstention is not a win.
- `score_v1` is experimental. The individual metrics are what this report is about.

