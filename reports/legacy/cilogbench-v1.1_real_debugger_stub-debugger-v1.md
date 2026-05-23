# CILogBench M10 — `stub-debugger-v1` on `cilogbench-v1.1`

## 1. Experiment summary

- Protocol: **cilogbench-v1.1**
- Splits: `dev`, `holdout`, `stress`
- Context methods attempted: `grep`, `llm-summary-v1-mock`, `llm-summary-v1-stub`, `raw`, `rtk-err-cat`, `rtk-log`, `rtk-read`, `tail`
- Diagnoser: `stub-debugger-v1`
- Provider: `command`
- Manifest: `results/cilogbench-v1.1_real_debugger_stub-debugger-v1.manifest.json`

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

- Config: `configs/diagnosers/stub-debugger-v1.json` (SHA `74644e93909e…`)
- Model: `stub / examples/diagnosis_shim_stub.py` version `v1`
- temperature=`0`, top_p=`1.0`, max_output_tokens=`1200`, json_mode=`True`, deterministic=`True`, tool_use=`False`, web_access=`False`
- allow_raw_context=`True`, allow_truncation=`False`, on_context_too_large=`mark_unsupported`, max_context_tokens=`None`

## 4. Model card

See `docs/model_cards/stub-debugger-v1.md` for model identity, decoding, determinism, and privacy notes.

## 5. Privacy audit summary

- `dev`: 0 pattern hit(s) across 8 method(s)
- `holdout`: 0 pattern hit(s) across 7 method(s)
- `stress`: 0 pattern hit(s) across 7 method(s)

_Audit is best-effort; see `docs/experiments/m6_real_fixed_debugger.md` for limits._

## 6. Per-split diagnosis metric tables

### dev

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 80.0% | 18.0% | 20.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 20.0% | 0.334 | 42.5k | 124 |
| llm-summary-v1-mock | 100.0% | 60.0% | 21.3% | 20.0% | 20.0% | 0.0% | 100.0% | 0.0% | 0.0% | 40.0% | 0.304 | 1.5k | 116 |
| llm-summary-v1-stub | 100.0% | 60.0% | 21.3% | 20.0% | 20.0% | 0.0% | 100.0% | 0.0% | 0.0% | 40.0% | 0.304 | 1.6k | 116 |
| raw | 100.0% | 80.0% | 18.0% | 35.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.374 | 130.2k | 126 |
| rtk-err-cat | 100.0% | 100.0% | 28.0% | 25.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.434 | 9.4k | 137 |
| rtk-log | 100.0% | 40.0% | 3.3% | 10.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 60.0% | 0.150 | 385 | 87 |
| rtk-read | 100.0% | 80.0% | 18.0% | 35.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.374 | 130.2k | 128 |
| tail | 100.0% | 60.0% | 27.0% | 40.0% | 23.3% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.384 | 5.6k | 137 |

### holdout

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 20.0% | 14.0% | 8.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 60.0% | 0.128 | 1.5k | 92 |
| llm-summary-v1-mock | 100.0% | 20.0% | 10.0% | 8.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 80.0% | 0.106 | 362 | 78 |
| raw | 100.0% | 20.0% | 18.0% | 8.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 40.0% | 0.150 | 11.1k | 101 |
| rtk-err-cat | 100.0% | 20.0% | 14.0% | 8.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 60.0% | 0.128 | 365 | 93 |
| rtk-log | 100.0% | 20.0% | 5.0% | 8.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 80.0% | 0.091 | 260 | 74 |
| rtk-read | 100.0% | 20.0% | 18.0% | 8.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 40.0% | 0.150 | 11.1k | 101 |
| tail | 100.0% | 20.0% | 14.0% | 8.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 60.0% | 0.128 | 4.6k | 84 |

### stress

| Method | Success | Cat Acc | Crit Mention | Must Mention | File Recall | Test Recall | Valid Quote | Forbidden | Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | N/A | 0.0% | 0.0% | 100.0% | 0.007 | 1.9k | 63 |
| llm-summary-v1-mock | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | N/A | 0.0% | 0.0% | 100.0% | 0.007 | 373 | 63 |
| raw | 100.0% | 0.0% | 4.2% | 13.3% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 83.3% | 0.048 | 91.2k | 71 |
| rtk-err-cat | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | N/A | 0.0% | 0.0% | 100.0% | 0.007 | 2.5k | 63 |
| rtk-log | 100.0% | 0.0% | 0.0% | 3.3% | 0.0% | 0.0% | N/A | 0.0% | 0.0% | 100.0% | 0.007 | 165 | 63 |
| rtk-read | 100.0% | 0.0% | 4.2% | 13.3% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 83.3% | 0.048 | 91.2k | 71 |
| tail | 100.0% | 0.0% | 4.2% | 13.3% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 83.3% | 0.048 | 5.0k | 71 |

## 7. Signal-vs-diagnosis comparison

Join of M2/M3/M4 signal-recall and this M10 run's diagnosis metrics.

### dev

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 86.7% | 88.3% | 78.4% | 80.0% | 18.0% | 0.0% | 42.5k | 69.8% |
| llm-summary-v1-mock | 42.4% | 43.3% | N/A | 60.0% | 21.3% | 0.0% | 1.5k | 98.5% |
| llm-summary-v1-stub | 42.4% | 43.3% | N/A | 60.0% | 21.3% | 0.0% | 1.6k | 98.3% |
| raw | 100.0% | 100.0% | 100.0% | 80.0% | 18.0% | 0.0% | 130.2k | 0.0% |
| rtk-err-cat | 73.3% | 77.7% | N/A | 100.0% | 28.0% | 0.0% | 9.4k | 86.7% |
| rtk-log | 25.7% | 30.3% | N/A | 40.0% | 3.3% | 0.0% | 385 | 99.2% |
| rtk-read | 100.0% | 100.0% | N/A | 80.0% | 18.0% | 0.0% | 130.2k | 0.0% |
| tail | 63.3% | 70.0% | 30.7% | 60.0% | 27.0% | 0.0% | 5.6k | 81.6% |

### holdout

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 89.8% | 95.0% | 73.1% | 20.0% | 14.0% | 0.0% | 1.5k | 87.0% |
| llm-summary-v1-mock | 60.1% | 58.0% | N/A | 20.0% | 10.0% | 0.0% | 362 | 96.6% |
| raw | 100.0% | 100.0% | 100.0% | 20.0% | 18.0% | 0.0% | 11.1k | 0.0% |
| rtk-err-cat | 48.8% | 43.0% | N/A | 20.0% | 14.0% | 0.0% | 365 | 97.0% |
| rtk-log | 33.1% | 36.0% | N/A | 20.0% | 5.0% | 0.0% | 260 | 97.5% |
| rtk-read | 100.0% | 100.0% | N/A | 20.0% | 18.0% | 0.0% | 11.1k | 0.0% |
| tail | 93.1% | 95.0% | 100.0% | 20.0% | 14.0% | 0.0% | 4.6k | 51.3% |

### stress

| Method | Signal Recall | Critical Signal Recall | Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 86.2% | 87.5% | 86.5% | 0.0% | 0.0% | 0.0% | 1.9k | 89.7% |
| llm-summary-v1-mock | 55.9% | 64.2% | N/A | 0.0% | 0.0% | 0.0% | 373 | 91.9% |
| raw | 100.0% | 100.0% | 100.0% | 0.0% | 4.2% | 0.0% | 91.2k | 0.0% |
| rtk-err-cat | 39.2% | 44.2% | N/A | 0.0% | 0.0% | 0.0% | 2.5k | 97.2% |
| rtk-log | 30.3% | 34.2% | N/A | 0.0% | 0.0% | 0.0% | 165 | 96.9% |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | 4.2% | 0.0% | 91.2k | 0.0% |
| tail | 100.0% | 100.0% | 100.0% | 0.0% | 4.2% | 0.0% | 5.0k | 33.5% |

## 8. Cost and token table (per split)

_Average per case. Non-LLM methods have 0 summarization tokens._

### dev

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 42.5k | 124 | 0 | 42.6k | — | — |
| llm-summary-v1-mock | 1.5k | 116 | 181.4k | 183.1k | 67 | — |
| llm-summary-v1-stub | 1.6k | 116 | 181.4k | 183.1k | 67 | — |
| raw | 130.2k | 126 | 0 | 130.3k | — | — |
| rtk-err-cat | 9.4k | 137 | 0 | 9.5k | — | — |
| rtk-log | 385 | 87 | 0 | 472 | — | — |
| rtk-read | 130.2k | 128 | 0 | 130.3k | — | — |
| tail | 5.6k | 137 | 0 | 5.7k | — | — |

### holdout

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 1.5k | 92 | 0 | 1.6k | — | — |
| llm-summary-v1-mock | 362 | 78 | 13.7k | 14.1k | 14 | — |
| raw | 11.1k | 101 | 0 | 11.2k | — | — |
| rtk-err-cat | 365 | 93 | 0 | 458 | — | — |
| rtk-log | 260 | 74 | 0 | 334 | — | — |
| rtk-read | 11.1k | 101 | 0 | 11.2k | — | — |
| tail | 4.6k | 84 | 0 | 4.6k | — | — |

### stress

| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok | Total Pipeline | External Calls | Unsupported Cases |
|---|---:|---:|---:|---:|---:|---:|
| grep | 1.9k | 63 | 0 | 1.9k | — | — |
| llm-summary-v1-mock | 373 | 63 | 101.2k | 101.7k | 40 | — |
| raw | 91.2k | 71 | 0 | 91.3k | — | — |
| rtk-err-cat | 2.5k | 63 | 0 | 2.6k | — | — |
| rtk-log | 165 | 63 | 0 | 228 | — | — |
| rtk-read | 91.2k | 71 | 0 | 91.3k | — | — |
| tail | 5.0k | 71 | 0 | 5.0k | — | — |

## 9. Confident-error analysis

- None recorded.

## 10. Abstention analysis

- `dev` / `grep`: 1 case(s)
  - `lint-react-001` — pred `unknown` @ 0.00
- `dev` / `llm-summary-v1-mock`: 2 case(s)
  - `lint-react-001` — pred `unknown` @ 0.00
  - `mypy-pandas-001` — pred `unknown` @ 0.00
- `dev` / `llm-summary-v1-stub`: 2 case(s)
  - `lint-react-001` — pred `unknown` @ 0.00
  - `mypy-pandas-001` — pred `unknown` @ 0.00
- `dev` / `rtk-log`: 3 case(s)
  - `jest-nextjs-001` — pred `unknown` @ 0.00
  - `lint-react-001` — pred `unknown` @ 0.00
  - `mypy-pandas-001` — pred `unknown` @ 0.00
- `holdout` / `grep`: 3 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.00
  - `dependabot-cargo-001` — pred `unknown` @ 0.00
  - `docs-transformers-001` — pred `unknown` @ 0.00
- `holdout` / `llm-summary-v1-mock`: 4 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.00
  - `dependabot-cargo-001` — pred `unknown` @ 0.00
  - `docs-transformers-001` — pred `unknown` @ 0.00
  - `pushpr-nextjs-001` — pred `unknown` @ 0.00
- `holdout` / `raw`: 2 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.00
  - `dependabot-cargo-001` — pred `unknown` @ 0.00
- `holdout` / `rtk-err-cat`: 3 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.00
  - `dependabot-cargo-001` — pred `unknown` @ 0.00
  - `docs-transformers-001` — pred `unknown` @ 0.00
- `holdout` / `rtk-log`: 4 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.00
  - `dependabot-cargo-001` — pred `unknown` @ 0.00
  - `docs-transformers-001` — pred `unknown` @ 0.00
  - `pushpr-nextjs-001` — pred `unknown` @ 0.00
- `holdout` / `rtk-read`: 2 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.00
  - `dependabot-cargo-001` — pred `unknown` @ 0.00
- `holdout` / `tail`: 3 case(s)
  - `actions-terraform-001` — pred `unknown` @ 0.00
  - `dependabot-cargo-001` — pred `unknown` @ 0.00
  - `pushpr-nextjs-001` — pred `unknown` @ 0.00
- `stress` / `grep`: 6 case(s)
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
- `stress` / `raw`: 5 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-002` — pred `unknown` @ 0.00
- `stress` / `rtk-err-cat`: 6 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `prettier-react-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
- `stress` / `rtk-log`: 6 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `prettier-react-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
- `stress` / `rtk-read`: 5 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-002` — pred `unknown` @ 0.00
- `stress` / `tail`: 5 case(s)
  - `cleanup-k8s-stress-001` — pred `unknown` @ 0.00
  - `cleanup-tsc-stress-001` — pred `unknown` @ 0.00
  - `docbuild-hf-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-001` — pred `unknown` @ 0.00
  - `pytest-sklearn-stress-002` — pred `unknown` @ 0.00

## 11. Unsupported-context analysis

- None recorded.

## 12. Per-case hard failures (low across every method)

- `holdout` / `actions-terraform-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `holdout` / `dependabot-cargo-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `holdout` / `docs-transformers-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `holdout` / `pushpr-nextjs-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `stress` / `cleanup-k8s-stress-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `stress` / `cleanup-tsc-stress-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `stress` / `docbuild-hf-stress-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `stress` / `prettier-react-stress-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `stress` / `pytest-sklearn-stress-001` — every method's diagnosis missed the category AND had <30% critical-signal mention.
- `stress` / `pytest-sklearn-stress-002` — every method's diagnosis missed the category AND had <30% critical-signal mention.

## 13. Split gap analysis

See [`reports/dev_holdout_stress_comparison_cilogbench_v1_1.md`](dev_holdout_stress_comparison_cilogbench_v1_1.md) for the cross-split gap table generated by `tools/compare_splits.py`.

## 14. Interpretation guardrails

- This run uses only the cases locked in `protocols/cilogbench-v1.1.lock.json`. Case counts are small (≤ 16 under v1.1). A single case flipping can move macro metrics by 6–25 pp.
- M10 supports statements about **this diagnoser + this prompt** under the frozen protocol. It does not support cross-model or cross-prompt claims.
- Deterministic diagnosis metrics are a proxy. Paraphrases can fail literal signal matching without being wrong; M11 calibrates against human review.
- If `metadata.deterministic=false` in the config, rerun numbers may drift even with temperature=0. The cache stores the first run byte-exactly, so reruns hit cache unless `--no-cache` is passed.

