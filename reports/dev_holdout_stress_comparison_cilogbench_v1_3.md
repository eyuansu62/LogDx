# dev vs holdout vs stress — `cilogbench-v1.3`

Diagnoser: `real-debugger-v2`

Methods flagged with `*` have a maximum absolute pairwise gap ≥ 20 pp across the 3 splits on at least one metric.

## Signal recall by split

| Method | dev sig | holdout sig | stress sig | Max gap |
|---|---:|---:|---:|---:|
| grep * | 86.7% | 89.8% | 86.2% | 3.6% |
| hybrid-grep-4k-rtk-err-cat-v1 * | 76.7% | 89.8% | 80.6% | 13.1% |
| llm-summary-v1-haiku | 58.1% | 47.6% | 44.3% | 13.8% |
| llm-summary-v1-mock * | 42.4% | 60.1% | 55.9% | 17.7% |
| raw * | 100.0% | 100.0% | 100.0% | 0.0% |
| rtk-err-cat * | 73.3% | 48.8% | 39.2% | 34.1% |
| rtk-log * | 25.7% | 33.1% | 30.3% | 7.3% |
| rtk-read * | 100.0% | 100.0% | 100.0% | 0.0% |
| tail * | 63.3% | 93.1% | 100.0% | 36.7% |

## Critical signal recall by split

| Method | dev sig | holdout sig | stress sig | Max gap |
|---|---:|---:|---:|---:|
| grep | 88.3% | 95.0% | 87.5% | 7.5% |
| hybrid-grep-4k-rtk-err-cat-v1 | 84.3% | 95.0% | 87.5% | 10.7% |
| llm-summary-v1-haiku | 64.7% | 57.0% | 47.5% | 17.2% |
| llm-summary-v1-mock | 43.3% | 58.0% | 64.2% | 20.8% |
| raw | 100.0% | 100.0% | 100.0% | 0.0% |
| rtk-err-cat | 77.7% | 43.0% | 44.2% | 34.7% |
| rtk-log | 30.3% | 36.0% | 34.2% | 5.7% |
| rtk-read | 100.0% | 100.0% | 100.0% | 0.0% |
| tail | 70.0% | 95.0% | 100.0% | 30.0% |

## Reduction by split

| Method | dev sig | holdout sig | stress sig | Max gap |
|---|---:|---:|---:|---:|
| grep | 69.8% | 87.0% | 89.7% | 19.9% |
| hybrid-grep-4k-rtk-err-cat-v1 | 92.0% | 86.5% | 86.8% | 5.5% |
| llm-summary-v1-haiku | 98.6% | 96.2% | 79.9% | 18.7% |
| llm-summary-v1-mock | 98.5% | 96.6% | 91.9% | 6.6% |
| raw | 0.0% | 0.0% | 0.0% | 0.0% |
| rtk-err-cat | 86.7% | 97.0% | 97.2% | 10.5% |
| rtk-log | 99.2% | 97.5% | 96.9% | 2.3% |
| rtk-read | 0.0% | 0.0% | 0.0% | 0.0% |
| tail | 81.6% | 51.3% | 33.5% | 48.1% |

## Diagnosis category accuracy — `real-debugger-v2`

| Method | dev sig | holdout sig | stress sig | Max gap |
|---|---:|---:|---:|---:|
| grep | 80.0% | 60.0% | 83.3% | 23.3% |
| hybrid-grep-4k-rtk-err-cat-v1 | 80.0% | 60.0% | 0.0% | 80.0% |
| llm-summary-v1-haiku | N/A | N/A | N/A | N/A |
| llm-summary-v1-mock | 80.0% | 60.0% | 0.0% | 80.0% |
| raw | 20.0% | 60.0% | 33.3% | 40.0% |
| rtk-err-cat | 80.0% | 80.0% | 0.0% | 80.0% |
| rtk-log | 60.0% | 40.0% | 0.0% | 60.0% |
| rtk-read | 20.0% | 60.0% | 50.0% | 40.0% |
| tail | 60.0% | 60.0% | 66.7% | 6.7% |

## Critical mention — `real-debugger-v2`

| Method | dev sig | holdout sig | stress sig | Max gap |
|---|---:|---:|---:|---:|
| grep | 72.7% | 76.0% | 95.8% | 23.2% |
| hybrid-grep-4k-rtk-err-cat-v1 | 77.7% | 85.0% | 0.0% | 85.0% |
| llm-summary-v1-haiku | N/A | N/A | N/A | N/A |
| llm-summary-v1-mock | 43.3% | 58.0% | 0.0% | 58.0% |
| raw | 35.0% | 85.0% | 69.2% | 50.0% |
| rtk-err-cat | 58.7% | 39.0% | 0.0% | 58.7% |
| rtk-log | 22.0% | 41.0% | 35.0% | 19.0% |
| rtk-read | 25.0% | 91.0% | 65.0% | 66.0% |
| tail | 45.3% | 90.0% | 85.0% | 44.7% |

## Confident error rate — `real-debugger-v2`

| Method | dev sig | holdout sig | stress sig | Max gap |
|---|---:|---:|---:|---:|
| grep | 20.0% | 40.0% | 16.7% | 23.3% |
| hybrid-grep-4k-rtk-err-cat-v1 | 20.0% | 40.0% | 0.0% | 40.0% |
| llm-summary-v1-haiku | N/A | N/A | N/A | N/A |
| llm-summary-v1-mock | 0.0% | 20.0% | 0.0% | 20.0% |
| raw | 20.0% | 40.0% | 33.3% | 20.0% |
| rtk-err-cat | 0.0% | 0.0% | 0.0% | 0.0% |
| rtk-log | 40.0% | 40.0% | 0.0% | 40.0% |
| rtk-read | 20.0% | 40.0% | 16.7% | 23.3% |
| tail | 40.0% | 40.0% | 33.3% | 6.7% |

## Methods with large split gaps

- `grep` — gap on: `category_accuracy`, `critical_mention`, `confident_error`
- `hybrid-grep-4k-rtk-err-cat-v1` — gap on: `category_accuracy`, `critical_mention`, `confident_error`
- `llm-summary-v1-mock` — gap on: `critical_signal_recall`, `category_accuracy`, `critical_mention`, `confident_error`
- `raw` — gap on: `category_accuracy`, `critical_mention`, `confident_error`
- `rtk-err-cat` — gap on: `signal_recall`, `critical_signal_recall`, `category_accuracy`, `critical_mention`
- `rtk-log` — gap on: `category_accuracy`, `confident_error`
- `rtk-read` — gap on: `category_accuracy`, `critical_mention`, `confident_error`
- `tail` — gap on: `signal_recall`, `critical_signal_recall`, `reduction`, `critical_mention`

## Split composition (from split manifests)

| Split | Cases | Frameworks | Failure categories |
|---|---:|---|---|
| dev | 5 | cargo×1, generic×2, jest×1, pytest×1 | compile_error×1, lint_error×1, permission_or_secret×1, test_assertion×1, type_error×1 |
| holdout | 5 | cargo×1, generic×3, tsc×1 | compile_error×1, dependency_install×1, github_actions_config×1, permission_or_secret×1, test_assertion×1 |
| stress | 6 | generic×4, pytest×2 | github_actions_config×1, lint_error×1, permission_or_secret×2, test_assertion×2 |

## Interpretation guardrails

- This comparison uses only the cases locked in `protocols/cilogbench-v1.3.lock.json`. The stress split is intentionally adversarial; a 20pp gap vs dev is a signal of brittleness, not automatic method failure.
- Mock diagnosis numbers validate the pipeline only. Real model numbers live under M10.
- Small case counts: a single case flipping can shift a macro metric by 17-25pp. Prefer critical_signal_recall and max-gap patterns over single-number rankings.
- `category_accuracy` depends on the category distribution of each split. If the mock diagnoser scores 0% on stress, that is almost certainly a mock-heuristic gap, not a context-method problem.
