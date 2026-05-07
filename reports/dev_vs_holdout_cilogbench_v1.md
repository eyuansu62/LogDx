# Dev vs Holdout — `cilogbench-v1`

Diagnoser: `debugger-v1-mock`

Methods flagged with `*` below have an absolute dev↔holdout gap ≥ 20 pp on at least one metric. The flag is diagnostic, not a failure.

## Signal recall

| Method | Dev Signal | Holdout Signal | Gap | Dev Critical | Holdout Critical | Gap | Dev Reduction | Holdout Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep * | 86.7% | 89.8% | 3.1% | 88.3% | 95.0% | 6.7% | 69.8% | 87.0% |
| llm-summary-v1-mock * | 42.4% | 60.1% | 17.7% | 43.3% | 58.0% | 14.7% | 98.5% | 96.6% |
| raw * | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| rtk-err-cat * | 73.3% | 48.8% | -24.6% | 77.7% | 43.0% | -34.7% | 86.7% | 97.0% |
| rtk-log * | 25.7% | 33.1% | 7.3% | 30.3% | 36.0% | 5.7% | 99.2% | 97.5% |
| rtk-read * | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| tail * | 63.3% | 93.1% | 29.8% | 70.0% | 95.0% | 25.0% | 81.6% | 51.3% |

## Diagnosis — `debugger-v1-mock`

_Mock diagnoser results validate the pipeline only; do not interpret these numbers as real model quality._

| Method | Dev CatAcc | Holdout CatAcc | Gap | Dev CritMention | Holdout CritMention | Gap | Dev ConfErr | Holdout ConfErr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 80.0% | 20.0% | -60.0% | 25.3% | 32.0% | 6.7% | 0.0% | 0.0% |
| llm-summary-v1-mock | 60.0% | 20.0% | -40.0% | 25.3% | 14.0% | -11.3% | 0.0% | 0.0% |
| raw | 80.0% | 20.0% | -60.0% | 24.7% | 23.0% | -1.7% | 20.0% | 20.0% |
| rtk-err-cat | 100.0% | 20.0% | -80.0% | 39.3% | 14.0% | -25.3% | 0.0% | 0.0% |
| rtk-log | 40.0% | 20.0% | -20.0% | 7.3% | 5.0% | -2.3% | 0.0% | 0.0% |
| rtk-read | 80.0% | 20.0% | -60.0% | 24.7% | 23.0% | -1.7% | 20.0% | 20.0% |
| tail | 40.0% | 20.0% | -20.0% | 25.7% | 23.0% | -2.7% | 40.0% | 0.0% |

## Methods with large dev/holdout gaps

- `grep` — gap on: `category_accuracy`
- `llm-summary-v1-mock` — gap on: `category_accuracy`
- `raw` — gap on: `category_accuracy`
- `rtk-err-cat` — gap on: `signal_recall`, `critical_signal_recall`, `category_accuracy`, `critical_mention`
- `rtk-log` — gap on: `category_accuracy`
- `rtk-read` — gap on: `category_accuracy`
- `tail` — gap on: `signal_recall`, `critical_signal_recall`, `reduction`, `category_accuracy`, `confident_error`

## Interpretation guardrails

- This comparison uses only the cases locked in `protocols/cilogbench-v1.lock.json`. Splits are small (5 + 5 = 10 cases), so a 20pp gap on one method may move with one case going the other way. Treat it as a flag, not a verdict.
- Mock diagnosis numbers reflect a deterministic keyword heuristic; they say nothing about real model quality. Do not stop at the mock numbers.
- Holdout cases were annotated before running any method on them. If future method tuning is informed by holdout per-case failures, subsequent runs must be marked `post-holdout-tuned` or a new protocol version must be created.
- `category_accuracy` can jump up or down on holdout simply because the split has different category distributions; look at `critical_signal_recall` first for context-quality signal.
