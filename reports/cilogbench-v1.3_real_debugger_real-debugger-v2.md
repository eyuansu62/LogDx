# CILogBench M10 — `real-debugger-v2` on `cilogbench-v1.3`

## 1. Experiment summary

- Protocol: **cilogbench-v1.3**
- Splits: `dev`, `holdout`, `stress`
- Context methods attempted: `grep`, `hybrid-grep-4k-rtk-err-cat-v1`, `llm-summary-v1-mock`, `raw`, `rtk-err-cat`, `rtk-log`, `rtk-read`, `tail`
- Diagnoser: `real-debugger-v2`
- Provider: `command`
- Manifest: `results/cilogbench-v1.3_real_debugger_real-debugger-v2.manifest.json`

## 2. Protocol lock summary

- Lock path: `protocols/cilogbench-v1.3.lock.json`
- Lock SHA256: `4ef0cf09d830381547df631664a429217dcff1f2a64b02635bbe65320a6e3bde`
- Schemas hashed: **10**
- Prompts hashed: **3**
- Evaluators hashed: **4**
- Baselines in lock: **8**
  - `dev` — 5 cases
  - `holdout` — 5 cases
  - `stress` — 6 cases

## 3. Diagnoser config summary

- Config: `configs/diagnosers/real-debugger-v2.json` (SHA `b26a4637b69f…`)
- Model: `anthropic / claude-sonnet-4-6` version `2026-04-25`
- temperature=`0`, top_p=`1.0`, max_output_tokens=`1200`, json_mode=`True`, deterministic=`False`, tool_use=`False`, web_access=`False`
- allow_raw_context=`True`, allow_truncation=`False`, on_context_too_large=`mark_unsupported`, max_context_tokens=`None`

## 4. Model card

See `docs/model_cards/real-debugger-v2.md` for model identity, decoding, determinism, and privacy notes.

## 5. Privacy audit summary

- `dev`: 0 pattern hit(s) across 11 method(s)
- `holdout`: 0 pattern hit(s) across 10 method(s)
- `stress`: 0 pattern hit(s) across 10 method(s)

_Audit is best-effort; see `docs/experiments/m6_real_fixed_debugger.md` for limits._

## 6. Per-split diagnosis metric tables

### dev

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 80.0% | 72.7% | 85.0% | 80.0% | 100.0% | 78.3% | 0.0% | 20.0% | 0.0% | 0.717 | 42.5k | 936 |
| hybrid-grep-4k-rtk-err-cat-v1 | 100.0% | 80.0% | 77.7% | 75.0% | 80.0% | 66.7% | 93.3% | 0.0% | 20.0% | 0.0% | 0.700 | 9.0k | 906 |
| llm-summary-v1-mock | 100.0% | 80.0% | 43.3% | 55.0% | 46.7% | 0.0% | 79.0% | 0.0% | 0.0% | 0.0% | 0.526 | 1.5k | 562 |
| raw | 100.0% | 20.0% | 35.0% | 35.0% | 40.0% | 33.3% | 77.5% | 0.0% | 20.0% | 60.0% | 0.251 | 130.2k | 241 |
| rtk-err-cat | 100.0% | 80.0% | 58.7% | 75.0% | 60.0% | 66.7% | 89.3% | 0.0% | 0.0% | 0.0% | 0.671 | 9.4k | 921 |
| rtk-log | 100.0% | 60.0% | 22.0% | 50.0% | 16.7% | 16.7% | 78.7% | 20.0% | 40.0% | 0.0% | 0.295 | 385 | 519 |
| rtk-read | 100.0% | 20.0% | 25.0% | 35.0% | 40.0% | 33.3% | 90.0% | 0.0% | 20.0% | 60.0% | 0.223 | 130.2k | 246 |
| tail | 100.0% | 60.0% | 45.3% | 70.0% | 73.3% | 33.3% | 92.0% | 0.0% | 40.0% | 0.0% | 0.465 | 5.6k | 559 |

### holdout

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 60.0% | 76.0% | 100.0% | 75.0% | 100.0% | 82.7% | 0.0% | 40.0% | 0.0% | 0.599 | 1.5k | 460 |
| hybrid-grep-4k-rtk-err-cat-v1 | 100.0% | 60.0% | 85.0% | 96.0% | 75.0% | 100.0% | 91.0% | 0.0% | 40.0% | 0.0% | 0.623 | 1.5k | 465 |
| llm-summary-v1-mock | 100.0% | 60.0% | 58.0% | 61.0% | 12.5% | 0.0% | 100.0% | 0.0% | 20.0% | 20.0% | 0.456 | 362 | 458 |
| raw | 100.0% | 60.0% | 85.0% | 91.0% | 100.0% | 100.0% | 81.0% | 0.0% | 40.0% | 0.0% | 0.627 | 11.1k | 536 |
| rtk-err-cat | 100.0% | 80.0% | 39.0% | 56.0% | 12.5% | 0.0% | 93.3% | 20.0% | 0.0% | 0.0% | 0.436 | 365 | 400 |
| rtk-log | 100.0% | 40.0% | 41.0% | 49.0% | 0.0% | 0.0% | 100.0% | 0.0% | 40.0% | 0.0% | 0.271 | 260 | 411 |
| rtk-read | 100.0% | 60.0% | 91.0% | 96.0% | 100.0% | 100.0% | 81.0% | 0.0% | 40.0% | 0.0% | 0.655 | 11.1k | 519 |
| tail | 100.0% | 60.0% | 90.0% | 91.0% | 75.0% | 100.0% | 86.0% | 0.0% | 40.0% | 0.0% | 0.625 | 4.6k | 514 |

### stress

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 83.3% | 95.8% | 96.7% | 100.0% | 50.0% | 83.9% | 0.0% | 16.7% | 0.0% | 0.756 | 1.9k | 408 |
| hybrid-grep-4k-rtk-err-cat-v1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | N/A | 0.0% | 0.0% | 100.0% | 0.000 | 2.7k | 55 |
| llm-summary-v1-mock | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | N/A | 0.0% | 0.0% | 100.0% | 0.000 | 373 | 55 |
| raw | 100.0% | 33.3% | 69.2% | 63.3% | 33.3% | 0.0% | 75.4% | 0.0% | 33.3% | 33.3% | 0.376 | 91.2k | 336 |
| rtk-err-cat | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | N/A | 0.0% | 0.0% | 100.0% | 0.000 | 2.5k | 55 |
| rtk-log | 50.0% | 0.0% | 35.0% | 13.3% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.157 | 165 | 123 |
| rtk-read | 100.0% | 50.0% | 65.0% | 66.7% | 33.3% | 0.0% | 68.8% | 0.0% | 16.7% | 33.3% | 0.451 | 91.2k | 310 |
| tail | 100.0% | 66.7% | 85.0% | 96.7% | 100.0% | 100.0% | 62.5% | 0.0% | 33.3% | 0.0% | 0.646 | 5.0k | 469 |

## 7. Signal-vs-diagnosis comparison

Join of M2/M3/M4 signal-recall and this M10 run's diagnosis metrics.

### dev

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 86.7% | 88.3% | 78.4% | 80.0% | 72.7% | 20.0% | 42.5k | 69.8% |
| hybrid-grep-4k-rtk-err-cat-v1 | 76.7% | 84.3% | 75.0% | 80.0% | 77.7% | 20.0% | 9.0k | 92.0% |
| llm-summary-v1-mock | 42.4% | 43.3% | N/A | 80.0% | 43.3% | 0.0% | 1.5k | 98.5% |
| raw | 100.0% | 100.0% | 100.0% | 20.0% | 35.0% | 20.0% | 130.2k | 0.0% |
| rtk-err-cat | 73.3% | 77.7% | N/A | 80.0% | 58.7% | 0.0% | 9.4k | 86.7% |
| rtk-log | 25.7% | 30.3% | N/A | 60.0% | 22.0% | 40.0% | 385 | 99.2% |
| rtk-read | 100.0% | 100.0% | N/A | 20.0% | 25.0% | 20.0% | 130.2k | 0.0% |
| tail | 63.3% | 70.0% | 30.7% | 60.0% | 45.3% | 40.0% | 5.6k | 81.6% |

### holdout

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 89.8% | 95.0% | 73.1% | 60.0% | 76.0% | 40.0% | 1.5k | 87.0% |
| hybrid-grep-4k-rtk-err-cat-v1 | 89.8% | 95.0% | 73.1% | 60.0% | 85.0% | 40.0% | 1.5k | 86.5% |
| llm-summary-v1-mock | 60.1% | 58.0% | N/A | 60.0% | 58.0% | 20.0% | 362 | 96.6% |
| raw | 100.0% | 100.0% | 100.0% | 60.0% | 85.0% | 40.0% | 11.1k | 0.0% |
| rtk-err-cat | 48.8% | 43.0% | N/A | 80.0% | 39.0% | 0.0% | 365 | 97.0% |
| rtk-log | 33.1% | 36.0% | N/A | 40.0% | 41.0% | 40.0% | 260 | 97.5% |
| rtk-read | 100.0% | 100.0% | N/A | 60.0% | 91.0% | 40.0% | 11.1k | 0.0% |
| tail | 93.1% | 95.0% | 100.0% | 60.0% | 90.0% | 40.0% | 4.6k | 51.3% |

### stress

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 86.2% | 87.5% | 86.5% | 83.3% | 95.8% | 16.7% | 1.9k | 89.7% |
| hybrid-grep-4k-rtk-err-cat-v1 | 80.6% | 87.5% | 91.7% | 0.0% | 0.0% | 0.0% | 2.7k | 86.8% |
| llm-summary-v1-mock | 55.9% | 64.2% | N/A | 0.0% | 0.0% | 0.0% | 373 | 91.9% |
| raw | 100.0% | 100.0% | 100.0% | 33.3% | 69.2% | 33.3% | 91.2k | 0.0% |
| rtk-err-cat | 39.2% | 44.2% | N/A | 0.0% | 0.0% | 0.0% | 2.5k | 97.2% |
| rtk-log | 30.3% | 34.2% | N/A | 0.0% | 35.0% | 0.0% | 165 | 96.9% |
| rtk-read | 100.0% | 100.0% | N/A | 50.0% | 65.0% | 16.7% | 91.2k | 0.0% |
| tail | 100.0% | 100.0% | 100.0% | 66.7% | 85.0% | 33.3% | 5.0k | 33.5% |

## 8. Cost and token table (per split)

_Average per case. Non-LLM methods have 0 summarization tokens._

### dev

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 42.5k | 936 | 0 | 43.4k | — | — |
| hybrid-grep-4k-rtk-err-cat-v1 | 9.0k | 906 | 0 | 9.9k | — | — |
| llm-summary-v1-mock | 1.5k | 562 | 181.4k | 183.5k | 67 | — |
| raw | 130.2k | 241 | 0 | 130.4k | — | — |
| rtk-err-cat | 9.4k | 921 | 0 | 10.3k | — | — |
| rtk-log | 385 | 519 | 0 | 904 | — | — |
| rtk-read | 130.2k | 246 | 0 | 130.5k | — | — |
| tail | 5.6k | 559 | 0 | 6.2k | — | — |

### holdout

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 1.5k | 460 | 0 | 2.0k | — | — |
| hybrid-grep-4k-rtk-err-cat-v1 | 1.5k | 465 | 0 | 2.0k | — | — |
| llm-summary-v1-mock | 362 | 458 | 13.7k | 14.5k | 14 | — |
| raw | 11.1k | 536 | 0 | 11.6k | — | — |
| rtk-err-cat | 365 | 400 | 0 | 765 | — | — |
| rtk-log | 260 | 411 | 0 | 671 | — | — |
| rtk-read | 11.1k | 519 | 0 | 11.6k | — | — |
| tail | 4.6k | 514 | 0 | 5.1k | — | — |

### stress

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 1.9k | 408 | 0 | 2.3k | — | — |
| hybrid-grep-4k-rtk-err-cat-v1 | 2.7k | 55 | 0 | 2.8k | — | — |
| llm-summary-v1-mock | 373 | 55 | 101.2k | 101.7k | 40 | — |
| raw | 91.2k | 336 | 0 | 91.5k | — | — |
| rtk-err-cat | 2.5k | 55 | 0 | 2.6k | — | — |
| rtk-log | 165 | 123 | 0 | 288 | — | — |
| rtk-read | 91.2k | 310 | 0 | 91.5k | — | — |
| tail | 5.0k | 469 | 0 | 5.4k | — | — |

## 9. Confident-error analysis

- `dev` / `grep`: 1 case(s)
  - `lint-react-001` — pred `formatting_failure` @ 0.82
- `dev` / `hybrid-grep-4k-rtk-err-cat-v1`: 1 case(s)
  - `lint-react-001` — pred `formatting_failure` @ 0.82
- `dev` / `raw`: 1 case(s)
  - `lint-react-001` — pred `formatting_failure` @ 0.98
- `dev` / `rtk-log`: 2 case(s)
  - `jest-nextjs-001` — pred `test_assertion` @ 0.72
  - `lint-react-001` — pred `formatting_failure` @ 0.72
- `dev` / `rtk-read`: 1 case(s)
  - `lint-react-001` — pred `formatting_failure` @ 0.97
- `dev` / `tail`: 2 case(s)
  - `jest-nextjs-001` — pred `other` @ 0.92
  - `lint-react-001` — pred `formatting_failure` @ 0.97
- `holdout` / `grep`: 2 case(s)
  - `actions-terraform-001` — pred `other` @ 0.95
  - `dependabot-cargo-001` — pred `other` @ 0.92
- `holdout` / `hybrid-grep-4k-rtk-err-cat-v1`: 2 case(s)
  - `actions-terraform-001` — pred `other` @ 0.95
  - `dependabot-cargo-001` — pred `other` @ 0.92
- `holdout` / `llm-summary-v1-mock`: 1 case(s)
  - `actions-terraform-001` — pred `other` @ 0.88
- `holdout` / `raw`: 2 case(s)
  - `actions-terraform-001` — pred `other` @ 0.97
  - `dependabot-cargo-001` — pred `other` @ 0.95
- `holdout` / `rtk-log`: 2 case(s)
  - `actions-terraform-001` — pred `other` @ 0.82
  - `pushpr-nextjs-001` — pred `network_or_flaky` @ 0.78
- `holdout` / `rtk-read`: 2 case(s)
  - `actions-terraform-001` — pred `other` @ 0.95
  - `dependabot-cargo-001` — pred `other` @ 0.95
- `holdout` / `tail`: 2 case(s)
  - `actions-terraform-001` — pred `other` @ 0.95
  - `dependabot-cargo-001` — pred `other` @ 0.95
- `stress` / `grep`: 1 case(s)
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.85
- `stress` / `raw`: 2 case(s)
  - `docbuild-hf-stress-001` — pred `other` @ 0.92
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.97
- `stress` / `rtk-read`: 1 case(s)
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.97
- `stress` / `tail`: 2 case(s)
  - `docbuild-hf-stress-001` — pred `other` @ 0.88
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.97

## 10. Abstention analysis

- `dev` / `raw`: 3 case(s)
  - `jest-nextjs-001` — pred `unknown` @ 0.00
  - `mypy-pandas-001` — pred `unknown` @ 0.00
  - `pytest-pandas-001` — pred `unknown` @ 0.00
- `dev` / `rtk-read`: 3 case(s)
  - `jest-nextjs-001` — pred `unknown` @ 0.00
  - `mypy-pandas-001` — pred `unknown` @ 0.00
  - `pytest-pandas-001` — pred `unknown` @ 0.00
- `holdout` / `llm-summary-v1-mock`: 1 case(s)
  - `dependabot-cargo-001` — pred `unknown` @ 0.20
- `stress` / `hybrid-grep-4k-rtk-err-cat-v1`: 6 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `prettier-react-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
- `stress` / `llm-summary-v1-mock`: 6 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `prettier-react-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
- `stress` / `raw`: 2 case(s)
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-002` — pred `unknown` @ 0.00
- `stress` / `rtk-err-cat`: 6 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `prettier-react-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
- `stress` / `rtk-log`: 6 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.10
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.10
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.10
  - `prettier-react-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
- `stress` / `rtk-read`: 2 case(s)
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-002` — pred `unknown` @ 0.00

## 11. Unsupported-context analysis

- None recorded.

## 12. Per-case hard failures (low across every method)

- No case is hard for every method simultaneously.

## 13. Split gap analysis

See [`reports/dev_holdout_stress_comparison_cilogbench_v1_3.md`](../reports/dev_holdout_stress_comparison_cilogbench_v1_3.md) for the cross-split gap table generated by `tools/compare_splits.py`.

## 14. Interpretation guardrails

- This run uses only the cases locked in `protocols/cilogbench-v1.3.lock.json`. Case counts are small (≤ 16 under v1.1). A single case flipping can move macro metrics by 6–25 pp.
- M10 supports statements about **this diagnoser + this prompt** under the frozen protocol. It does not support cross-model or cross-prompt claims.
- Deterministic diagnosis metrics are a proxy. Paraphrases can fail literal signal matching without being wrong; M11 calibrates against human review.
- If `metadata.deterministic=false` in the config, rerun numbers may drift even with temperature=0. The cache stores the first run byte-exactly, so reruns hit cache unless `--no-cache` is passed.

