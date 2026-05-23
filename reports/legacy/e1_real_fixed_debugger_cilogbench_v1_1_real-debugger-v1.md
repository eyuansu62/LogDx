# CILogBench E1-real-fixed-debugger-v1 — `real-debugger-v1` on `cilogbench-v1.1`

## 1. Experiment summary

- Protocol: **cilogbench-v1.1**
- Splits: `dev`, `holdout`, `stress`
- Context methods attempted: `grep`, `llm-summary-v1-mock`, `llm-summary-v1-stub`, `raw`, `rtk-err-cat`, `rtk-log`, `rtk-read`, `tail`
- Diagnoser: `real-debugger-v1`
- Provider: `command`
- Manifest: `results/cilogbench-v1.1_real_debugger_real-debugger-v1.manifest.json`

## 2. Protocol lock summary

- Lock path: `protocols/cilogbench-v1.1.lock.json`
- Lock SHA256: `e0cde373dca8d10cfc75d205e7ac72e5cedff3f78a322aedc7d2d67985debad6`
- Schemas hashed: **9**
- Prompts hashed: **3**
- Evaluators hashed: **2**
- Baselines in lock: **7**
  - `dev` — 5 cases
  - `holdout` — 5 cases
  - `stress` — 6 cases

## 3. Diagnoser config summary

- Config: `configs/diagnosers/real-debugger-v1.json` (SHA `c852d7c6a6f8…`)
- Model: `anthropic / claude-haiku-4-5` version `2026-04-25`
- temperature=`0`, top_p=`1.0`, max_output_tokens=`1200`, json_mode=`True`, deterministic=`False`, tool_use=`False`, web_access=`False`
- allow_raw_context=`True`, allow_truncation=`False`, on_context_too_large=`mark_unsupported`, max_context_tokens=`None`

## 4. Model card

See `docs/model_cards/real-debugger-v1.md` for model identity, decoding, determinism, and privacy notes.

## 5. Privacy audit summary

- `dev`: 0 pattern hit(s) across 8 method(s)
- `holdout`: 0 pattern hit(s) across 7 method(s)
- `stress`: 0 pattern hit(s) across 7 method(s)

_Audit is best-effort; see `docs/experiments/m6_real_fixed_debugger.md` for limits._

## 6. Per-split diagnosis metric tables

### dev

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 40.0% | 63.7% | 70.0% | 70.0% | 66.7% | 75.3% | 0.0% | 60.0% | 0.0% | 0.429 | 42.5k | 545 |
| llm-summary-v1-mock | 100.0% | 60.0% | 43.3% | 45.0% | 46.7% | 0.0% | 85.0% | 0.0% | 20.0% | 0.0% | 0.409 | 1.5k | 429 |
| llm-summary-v1-stub | 100.0% | 60.0% | 43.3% | 50.0% | 46.7% | 0.0% | 86.7% | 0.0% | 20.0% | 0.0% | 0.420 | 1.6k | 433 |
| raw | 80.0% | 0.0% | 25.0% | 20.0% | 20.0% | 0.0% | 66.7% | 0.0% | 20.0% | 80.0% | 0.092 | 130.2k | 115 |
| rtk-err-cat | 100.0% | 80.0% | 58.7% | 65.0% | 60.0% | 66.7% | 91.0% | 0.0% | 0.0% | 20.0% | 0.651 | 9.4k | 559 |
| rtk-log | 100.0% | 40.0% | 23.0% | 40.0% | 16.7% | 16.7% | 88.3% | 20.0% | 60.0% | 0.0% | 0.178 | 385 | 405 |
| rtk-read | 80.0% | 0.0% | 25.0% | 20.0% | 20.0% | 0.0% | 50.0% | 0.0% | 20.0% | 80.0% | 0.090 | 130.2k | 111 |
| tail | 100.0% | 40.0% | 56.0% | 60.0% | 53.3% | 33.3% | 67.7% | 0.0% | 60.0% | 0.0% | 0.355 | 5.6k | 505 |

### holdout

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 60.0% | 76.0% | 88.0% | 37.5% | 100.0% | 89.3% | 0.0% | 40.0% | 0.0% | 0.549 | 1.5k | 396 |
| llm-summary-v1-mock | 100.0% | 60.0% | 53.0% | 61.0% | 12.5% | 0.0% | 93.3% | 0.0% | 20.0% | 20.0% | 0.438 | 362 | 324 |
| raw | 100.0% | 60.0% | 76.0% | 91.0% | 75.0% | 100.0% | 80.0% | 0.0% | 40.0% | 0.0% | 0.580 | 11.1k | 462 |
| rtk-err-cat | 100.0% | 60.0% | 35.0% | 52.0% | 12.5% | 0.0% | 83.3% | 0.0% | 0.0% | 20.0% | 0.411 | 365 | 327 |
| rtk-log | 80.0% | 20.0% | 26.0% | 33.0% | 0.0% | 0.0% | 83.3% | 0.0% | 20.0% | 20.0% | 0.177 | 260 | 277 |
| rtk-read | 100.0% | 60.0% | 85.0% | 91.0% | 100.0% | 100.0% | 54.7% | 0.0% | 40.0% | 0.0% | 0.614 | 11.1k | 510 |
| tail | 100.0% | 80.0% | 85.0% | 86.0% | 50.0% | 100.0% | 89.3% | 0.0% | 20.0% | 0.0% | 0.682 | 4.6k | 446 |

### stress

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 83.3% | 80.0% | 100.0% | 100.0% | 0.0% | 59.7% | 0.0% | 16.7% | 0.0% | 0.686 | 1.9k | 358 |
| llm-summary-v1-mock | 100.0% | 50.0% | 61.7% | 41.7% | 66.7% | 100.0% | 57.5% | 0.0% | 0.0% | 33.3% | 0.489 | 373 | 289 |
| raw | 100.0% | 50.0% | 57.5% | 66.7% | 33.3% | 0.0% | 68.8% | 0.0% | 16.7% | 33.3% | 0.429 | 91.2k | 290 |
| rtk-err-cat | 100.0% | 50.0% | 34.2% | 41.7% | 66.7% | 100.0% | 86.1% | 0.0% | 0.0% | 50.0% | 0.420 | 2.5k | 214 |
| rtk-log | 100.0% | 0.0% | 34.2% | 16.7% | 0.0% | 0.0% | 87.5% | 0.0% | 33.3% | 50.0% | 0.146 | 165 | 284 |
| rtk-read | 100.0% | 33.3% | 65.8% | 66.7% | 33.3% | 0.0% | 50.0% | 0.0% | 33.3% | 33.3% | 0.364 | 91.2k | 284 |
| tail | 100.0% | 83.3% | 81.7% | 91.7% | 100.0% | 0.0% | 48.3% | 0.0% | 16.7% | 0.0% | 0.669 | 5.0k | 386 |

## 7. Signal-vs-diagnosis comparison

Join of M2/M3/M4 signal-recall and this M10 run's diagnosis metrics.

### dev

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 86.7% | 88.3% | 78.4% | 40.0% | 63.7% | 60.0% | 42.5k | 69.8% |
| llm-summary-v1-mock | 42.4% | 43.3% | N/A | 60.0% | 43.3% | 20.0% | 1.5k | 98.5% |
| llm-summary-v1-stub | 42.4% | 43.3% | N/A | 60.0% | 43.3% | 20.0% | 1.6k | 98.3% |
| raw | 100.0% | 100.0% | 100.0% | 0.0% | 25.0% | 20.0% | 130.2k | 0.0% |
| rtk-err-cat | 73.3% | 77.7% | N/A | 80.0% | 58.7% | 0.0% | 9.4k | 86.7% |
| rtk-log | 25.7% | 30.3% | N/A | 40.0% | 23.0% | 60.0% | 385 | 99.2% |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | 25.0% | 20.0% | 130.2k | 0.0% |
| tail | 63.3% | 70.0% | 30.7% | 40.0% | 56.0% | 60.0% | 5.6k | 81.6% |

### holdout

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 89.8% | 95.0% | 73.1% | 60.0% | 76.0% | 40.0% | 1.5k | 87.0% |
| llm-summary-v1-mock | 60.1% | 58.0% | N/A | 60.0% | 53.0% | 20.0% | 362 | 96.6% |
| raw | 100.0% | 100.0% | 100.0% | 60.0% | 76.0% | 40.0% | 11.1k | 0.0% |
| rtk-err-cat | 48.8% | 43.0% | N/A | 60.0% | 35.0% | 0.0% | 365 | 97.0% |
| rtk-log | 33.1% | 36.0% | N/A | 20.0% | 26.0% | 20.0% | 260 | 97.5% |
| rtk-read | 100.0% | 100.0% | N/A | 60.0% | 85.0% | 40.0% | 11.1k | 0.0% |
| tail | 93.1% | 95.0% | 100.0% | 80.0% | 85.0% | 20.0% | 4.6k | 51.3% |

### stress

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 86.2% | 87.5% | 86.5% | 83.3% | 80.0% | 16.7% | 1.9k | 89.7% |
| llm-summary-v1-mock | 55.9% | 64.2% | N/A | 50.0% | 61.7% | 0.0% | 373 | 91.9% |
| raw | 100.0% | 100.0% | 100.0% | 50.0% | 57.5% | 16.7% | 91.2k | 0.0% |
| rtk-err-cat | 39.2% | 44.2% | N/A | 50.0% | 34.2% | 0.0% | 2.5k | 97.2% |
| rtk-log | 30.3% | 34.2% | N/A | 0.0% | 34.2% | 33.3% | 165 | 96.9% |
| rtk-read | 100.0% | 100.0% | N/A | 33.3% | 65.8% | 33.3% | 91.2k | 0.0% |
| tail | 100.0% | 100.0% | 100.0% | 83.3% | 81.7% | 16.7% | 5.0k | 33.5% |

## 8. Cost and token table (per split)

_Average per case. Non-LLM methods have 0 summarization tokens._

### dev

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 42.5k | 545 | 0 | 43.0k | — | — |
| llm-summary-v1-mock | 1.5k | 429 | 181.4k | 183.4k | 67 | — |
| llm-summary-v1-stub | 1.6k | 433 | 181.4k | 183.5k | 67 | — |
| raw | 130.2k | 115 | 0 | 130.3k | — | — |
| rtk-err-cat | 9.4k | 559 | 0 | 9.9k | — | — |
| rtk-log | 385 | 405 | 0 | 790 | — | — |
| rtk-read | 130.2k | 111 | 0 | 130.3k | — | — |
| tail | 5.6k | 505 | 0 | 6.1k | — | — |

### holdout

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 1.5k | 396 | 0 | 1.9k | — | — |
| llm-summary-v1-mock | 362 | 324 | 13.7k | 14.4k | 14 | — |
| raw | 11.1k | 462 | 0 | 11.5k | — | — |
| rtk-err-cat | 365 | 327 | 0 | 692 | — | — |
| rtk-log | 260 | 277 | 0 | 537 | — | — |
| rtk-read | 11.1k | 510 | 0 | 11.6k | — | — |
| tail | 4.6k | 446 | 0 | 5.0k | — | — |

### stress

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 1.9k | 358 | 0 | 2.2k | — | — |
| llm-summary-v1-mock | 373 | 289 | 101.2k | 101.9k | 40 | — |
| raw | 91.2k | 290 | 0 | 91.5k | — | — |
| rtk-err-cat | 2.5k | 214 | 0 | 2.8k | — | — |
| rtk-log | 165 | 284 | 0 | 449 | — | — |
| rtk-read | 91.2k | 284 | 0 | 91.5k | — | — |
| tail | 5.0k | 386 | 0 | 5.3k | — | — |

## 9. Confident-error analysis

- `dev` / `grep`: 3 case(s)
  - `cargo-tokio-001` — pred `test_assertion` @ 0.85
  - `lint-react-001` — pred `formatting_failure` @ 0.85
  - `pytest-pandas-001` — pred `other` @ 0.92
- `dev` / `llm-summary-v1-mock`: 1 case(s)
  - `pytest-pandas-001` — pred `other` @ 0.80
- `dev` / `llm-summary-v1-stub`: 1 case(s)
  - `pytest-pandas-001` — pred `other` @ 0.85
- `dev` / `raw`: 1 case(s)
  - `lint-react-001` — pred `formatting_failure` @ 0.95
- `dev` / `rtk-log`: 3 case(s)
  - `jest-nextjs-001` — pred `compile_error` @ 0.72
  - `lint-react-001` — pred `formatting_failure` @ 0.85
  - `pytest-pandas-001` — pred `other` @ 0.82
- `dev` / `rtk-read`: 1 case(s)
  - `lint-react-001` — pred `formatting_failure` @ 0.92
- `dev` / `tail`: 3 case(s)
  - `jest-nextjs-001` — pred `other` @ 0.82
  - `lint-react-001` — pred `formatting_failure` @ 0.95
  - `pytest-pandas-001` — pred `other` @ 0.72
- `holdout` / `grep`: 2 case(s)
  - `actions-terraform-001` — pred `test_assertion` @ 0.85
  - `dependabot-cargo-001` — pred `other` @ 0.87
- `holdout` / `llm-summary-v1-mock`: 1 case(s)
  - `actions-terraform-001` — pred `other` @ 0.95
- `holdout` / `raw`: 2 case(s)
  - `actions-terraform-001` — pred `test_assertion` @ 0.95
  - `dependabot-cargo-001` — pred `other` @ 0.85
- `holdout` / `rtk-log`: 1 case(s)
  - `actions-terraform-001` — pred `test_assertion` @ 0.85
- `holdout` / `rtk-read`: 2 case(s)
  - `actions-terraform-001` — pred `test_assertion` @ 0.95
  - `dependabot-cargo-001` — pred `other` @ 0.82
- `holdout` / `tail`: 1 case(s)
  - `dependabot-cargo-001` — pred `other` @ 0.80
- `stress` / `grep`: 1 case(s)
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.85
- `stress` / `raw`: 1 case(s)
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.95
- `stress` / `rtk-log`: 2 case(s)
  - `pytest-sklearn-stress-001` — pred `compile_error` @ 0.80
  - `pytest-sklearn-stress-002` — pred `compile_error` @ 0.80
- `stress` / `rtk-read`: 2 case(s)
  - `docbuild-hf-stress-001` — pred `other` @ 0.70
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.95
- `stress` / `tail`: 1 case(s)
  - `prettier-react-stress-001` — pred `formatting_failure` @ 0.95

## 10. Abstention analysis

- `dev` / `raw`: 4 case(s)
  - `cargo-tokio-001` — pred `unknown` @ 0.00
  - `jest-nextjs-001` — pred `unknown` @ 0.00
  - `mypy-pandas-001` — pred `unknown` @ 0.00
  - `pytest-pandas-001` — pred `unknown` @ 0.00
- `dev` / `rtk-err-cat`: 1 case(s)
  - `lint-react-001` — pred `unknown` @ 0.20
- `dev` / `rtk-read`: 4 case(s)
  - `cargo-tokio-001` — pred `unknown` @ 0.00
  - `jest-nextjs-001` — pred `unknown` @ 0.00
  - `mypy-pandas-001` — pred `unknown` @ 0.00
  - `pytest-pandas-001` — pred `unknown` @ 0.00
- `holdout` / `llm-summary-v1-mock`: 1 case(s)
  - `dependabot-cargo-001` — pred `unknown` @ 0.15
- `holdout` / `rtk-err-cat`: 1 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.10
- `holdout` / `rtk-log`: 1 case(s)
  - `tsc-typescript-001` — pred `unknown` @ 0.00
- `stress` / `llm-summary-v1-mock`: 2 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.10
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.10
- `stress` / `raw`: 2 case(s)
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-002` — pred `unknown` @ 0.00
- `stress` / `rtk-err-cat`: 3 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.10
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `prettier-react-stress-001` — pred `unknown` @ 0.15
- `stress` / `rtk-log`: 3 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.15
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.10
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.05
- `stress` / `rtk-read`: 2 case(s)
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-002` — pred `unknown` @ 0.00

## 11. Unsupported-context analysis

- None recorded.

## 12. Per-case hard failures (low across every method)

- No case is hard for every method simultaneously.

## 13. Split gap analysis

See [`reports/dev_holdout_stress_comparison_cilogbench_v1_1.md`](../reports/dev_holdout_stress_comparison_cilogbench_v1_1.md) for the cross-split gap table generated by `tools/compare_splits.py`.

## 14. Interpretation guardrails

- This run uses only the cases locked in `protocols/cilogbench-v1.1.lock.json`. Case counts are small (≤ 16 under v1.1). A single case flipping can move macro metrics by 6–25 pp.
- M10 supports statements about **this diagnoser + this prompt** under the frozen protocol. It does not support cross-model or cross-prompt claims.
- Deterministic diagnosis metrics are a proxy. Paraphrases can fail literal signal matching without being wrong; M11 calibrates against human review.
- If `metadata.deterministic=false` in the config, rerun numbers may drift even with temperature=0. The cache stores the first run byte-exactly, so reruns hit cache unless `--no-cache` is passed.


---

## Generalization tables (per metric)

Per the E1 plan, these tables make the dev/holdout/stress gap explicit per metric. `Large Gap?` flags absolute spread ≥ 20 percentage points across the three splits.

### Diagnosis Score v1

| Method | dev | holdout | stress | Max Gap | Large Gap? |
|---|---:|---:|---:|---:|---|
| grep | 42.9% | 54.9% | 68.7% | 25.8% | YES |
| llm-summary-v1-mock | 40.9% | 43.8% | 48.9% | 8.0% | — |
| raw | 9.2% | 58.0% | 42.9% | 48.8% | YES |
| rtk-err-cat | 65.1% | 41.1% | 42.0% | 24.1% | YES |
| rtk-log | 17.8% | 27.3% | 14.6% | 12.7% | — |
| rtk-read | 9.0% | 61.4% | 36.4% | 52.4% | YES |
| tail | 35.5% | 68.2% | 66.9% | 32.6% | YES |

### Category Accuracy

| Method | dev | holdout | stress | Max Gap | Large Gap? |
|---|---:|---:|---:|---:|---|
| grep | 40.0% | 60.0% | 83.3% | 43.3% | YES |
| llm-summary-v1-mock | 60.0% | 60.0% | 50.0% | 10.0% | — |
| raw | 0.0% | 60.0% | 50.0% | 60.0% | YES |
| rtk-err-cat | 80.0% | 60.0% | 50.0% | 30.0% | YES |
| rtk-log | 40.0% | 40.0% | 0.0% | 40.0% | YES |
| rtk-read | 0.0% | 60.0% | 33.3% | 60.0% | YES |
| tail | 40.0% | 80.0% | 83.3% | 43.3% | YES |

### Critical Signal Mention

| Method | dev | holdout | stress | Max Gap | Large Gap? |
|---|---:|---:|---:|---:|---|
| grep | 63.7% | 76.0% | 80.0% | 16.3% | — |
| llm-summary-v1-mock | 43.3% | 53.0% | 61.7% | 18.3% | — |
| raw | 25.0% | 76.0% | 57.5% | 51.0% | YES |
| rtk-err-cat | 58.7% | 35.0% | 34.2% | 24.5% | YES |
| rtk-log | 23.0% | 31.0% | 34.2% | 11.2% | — |
| rtk-read | 25.0% | 85.0% | 65.8% | 60.0% | YES |
| tail | 56.0% | 85.0% | 81.7% | 29.0% | YES |

### Confident Error Rate

| Method | dev | holdout | stress | Max Gap | Large Gap? |
|---|---:|---:|---:|---:|---|
| grep | 60.0% | 40.0% | 16.7% | 43.3% | YES |
| llm-summary-v1-mock | 20.0% | 20.0% | 0.0% | 20.0% | YES |
| raw | 20.0% | 40.0% | 16.7% | 23.3% | YES |
| rtk-err-cat | 0.0% | 0.0% | 0.0% | 0.0% | — |
| rtk-log | 60.0% | 20.0% | 33.3% | 40.0% | YES |
| rtk-read | 20.0% | 40.0% | 33.3% | 20.0% | YES |
| tail | 60.0% | 20.0% | 16.7% | 43.3% | YES |

### Abstention Rate

| Method | dev | holdout | stress | Max Gap | Large Gap? |
|---|---:|---:|---:|---:|---|
| grep | 0.0% | 0.0% | 0.0% | 0.0% | — |
| llm-summary-v1-mock | 0.0% | 20.0% | 33.3% | 33.3% | YES |
| raw | 80.0% | 0.0% | 33.3% | 80.0% | YES |
| rtk-err-cat | 20.0% | 20.0% | 50.0% | 30.0% | YES |
| rtk-log | 0.0% | 0.0% | 50.0% | 50.0% | YES |
| rtk-read | 80.0% | 0.0% | 33.3% | 80.0% | YES |
| tail | 0.0% | 0.0% | 0.0% | 0.0% | — |

## Analysis questions answered

Each answer is grounded in the per-split metrics computed for this run. Statements are descriptive, not prescriptive — see the guardrails section.

**1. Does raw context outperform compressed context?**

- dev: raw `score_v1` = 0.092; top method this split is `rtk-err-cat`.
- holdout: raw `score_v1` = 0.580; top method this split is `tail`.
- stress: raw `score_v1` = 0.429; top method this split is `grep`.

**2. Does raw context ever hurt due to length/noise?**

- dev: raw success=80.0%, abstention=80.0%, confident_error=20.0%.
- holdout: raw success=100.0%, abstention=0.0%, confident_error=40.0%.
- stress: raw success=100.0%, abstention=33.3%, confident_error=16.7%.

**3. Does grep's signal recall translate into better diagnosis?**

- dev: grep signal_recall=86.7% → category_accuracy=40.0%, critical_mention=63.7%.
- holdout: grep signal_recall=89.8% → category_accuracy=60.0%, critical_mention=76.0%.
- stress: grep signal_recall=86.2% → category_accuracy=83.3%, critical_mention=80.0%.

**4. Does rtk-err-cat's lower holdout/stress signal recall reduce diagnosis quality?**

- dev: rtk-err-cat signal_recall=73.3% → cat=80.0%, crit_mention=58.7%, score_v1=0.651.
- holdout: rtk-err-cat signal_recall=48.8% → cat=60.0%, crit_mention=35.0%, score_v1=0.411.
- stress: rtk-err-cat signal_recall=39.2% → cat=50.0%, crit_mention=34.2%, score_v1=0.420.

**5. Does rtk-log cause abstention, wrong answers, or unsupported evidence?**

- dev: cat=40.0% (low → wrong), abstention=0.0%, confident_error=60.0%, valid_evidence_quote_rate=88.3%.
- holdout: cat=40.0% (low → wrong), abstention=0.0%, confident_error=20.0%, valid_evidence_quote_rate=80.0%.
- stress: cat=0.0% (low → wrong), abstention=50.0%, confident_error=33.3%, valid_evidence_quote_rate=87.5%.

**6. Does tail-200's strong holdout/stress signal recall reflect short-log bias?**

- dev: tail signal_recall=63.3%, category_accuracy=40.0%, score_v1=0.355.
- holdout: tail signal_recall=93.1%, category_accuracy=80.0%, score_v1=0.682.
- stress: tail signal_recall=100.0%, category_accuracy=83.3%, score_v1=0.669.

**7. Which method has the lowest confident-error rate?**

- dev: `rtk-err-cat`=0.0%, `llm-summary-v1-mock`=20.0%, `raw`=20.0%
- holdout: `rtk-err-cat`=0.0%, `llm-summary-v1-mock`=20.0%, `rtk-log`=20.0%
- stress: `llm-summary-v1-mock`=0.0%, `rtk-err-cat`=0.0%, `grep`=16.7%

**8. Which method has the highest abstention rate?**

- dev: `raw`=80.0%, `rtk-read`=80.0%, `rtk-err-cat`=20.0%
- holdout: `llm-summary-v1-mock`=20.0%, `rtk-err-cat`=20.0%, `grep`=0.0%
- stress: `rtk-err-cat`=50.0%, `rtk-log`=50.0%, `llm-summary-v1-mock`=33.3%

**9. Which cases are hard for all methods?**

- dev: hard for every method → `lint-react-001`
- holdout: hard for every method → `dependabot-cargo-001`
- stress: hard for every method → `prettier-react-stress-001`

**10. Which required signals are most often missing?**

- dev: top miss types → `assertion`×31, `stack_location`×20, `compile_error`×18, `step_name`×17
- holdout: top miss types → `assertion`×22, `exception`×17, `annotation`×16, `stack_location`×13
- stress: top miss types → `command`×26, `assertion`×25, `exception`×13, `annotation`×12

---

## E1 interpretation guardrails (recap)

- This is one model (Claude Haiku 4.5 via the Claude Code CLI), one prompt (`debugger_v1`, SHA pinned in `cilogbench-v1.1`), and 16 cases. Numbers establish a baseline, not a winner.
- E1 supports statements like "under cilogbench-v1.1, this diagnoser had higher `score_v1` on stress/grep than on stress/rtk-log". It does NOT support "method X is the best CI debugging strategy".
- `diagnosis_success_rate` < 1.0 happens when the CLI itself errors out (e.g. on the largest log). Those rows are labeled `provider_error` in metadata; they are not silent abstentions.
- The deterministic evaluator can undercount valid paraphrases. Cross-check with M11 human review before publishing claims.

## Next recommended experiment

Per the plan, the recommended next step is **E2: human review of E1 diagnoses**. Build a blinded batch from the E1 outputs with `tools/build_human_review_set.py`, score 5 holdout cases × 3-4 context methods, and check whether human `overall_usefulness` correlates with `diagnosis_score_v1` on this real-model run before adding more variables (real summarizer, MCP/agent baselines).

If correlation is strong, E3 (real LLM summary context with the same debugger) becomes a clean follow-up that adds exactly one new variable. If correlation is weak, fix the metric or ground-truth annotations before adding any new variable.

