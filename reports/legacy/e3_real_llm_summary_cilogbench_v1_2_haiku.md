# E3 — Real LLM Summary Baseline (haiku) on cilogbench-v1.2

- **Experiment ID:** `E3-real-llm-summary-v1`
- **Protocol:** `cilogbench-v1.2` (SHA `cc4fdbe62d7793a3…`)
- **Summarizer:** `llm-summary-v1-haiku` (config `configs/summarizers/haiku.json`, SHA `26dae6cfc87df601…`)
- **Debugger:** `real-debugger-v1` (held fixed from E1)
- **Splits:** dev, holdout, stress
- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated). `diagnosis_score_v1` reported as secondary.
- **Run started:** 2026-05-02T13:30:24.214575+00:00

## 1. Experiment summary

E3 adds one **real** LLM-generated CI failure summary as a context method (`llm-summary-v1-haiku`) on `cilogbench-v1.2` and runs the same fixed debugger as E1 (`real-debugger-v1`) against it. The intent is to see whether a compact LLM summary improves fixed-debugger diagnosis quality enough to justify its summary-processing cost, vs. raw, tail, grep, the three RTK modes, and the deterministic mock summary.

## 2. Protocol and scoring summary

- Protocol lock: `protocols/cilogbench-v1.2.lock.json` (SHA `cc4fdbe62d7793a34dade2dfeaf1b1fd29261f2b1b3a20602ba465150baffdab`)
- Diagnosis evaluator: `tools/evaluate_diagnosis.py` (v1.2)
- Calibration table: `configs/evaluation/category_compatibility_v1_1.json`
- Primary score: `diagnosis_score_v1_1`
- Secondary score: `diagnosis_score_v1` (preserved alongside sv1.1)
- E2b memo: `reports/e2b_score_calibration_v1_1.md` (why sv1.1 is primary)

## 3. Summarizer config summary

- summarizer_name: `claude-haiku-4-5-summary-v1`
- method_name: `llm-summary-v1-haiku`
- provider: `command`
- model: `claude-haiku-4-5`@`2026-04-25`, temperature=0, max_output_tokens=1800
- chunking: chunk_lines=500, overlap_lines=25, on_oversize=`chunk`
- map prompt SHA: `684c5b978f4aa109f4241d7aa8187f63f9511c4193d6581c1195e15c379922e6`
- reduce prompt SHA: `e3739738b7136af3956f3712e7b76babd9224b6854dcc60ff16546a3fbb16702`

## 4. Debugger config summary

- diagnoser_name: `real-debugger-v1`
- model: `claude-haiku-4-5`@`2026-04-25`, temperature=0, max_output_tokens=1200
- prompt SHA: `ecffdf03c99a91b0f8f75e086720d9fb8db96af0d9dae5285baf679c9c9d28de`
- determinism: `deterministic=False`

## 5. Privacy audit summary

Privacy audits ran on `raw` for all three splits before E3 began (see `reports/<split>_privacy_audit.md`). Re-run on the new summary outputs (`reports/<split>_privacy_audit.md`) before any downstream sharing.

## 6. Splits and methods evaluated

| Split | Cases | Methods |
|---|---:|---|
| dev | 5 | `raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`, `llm-summary-v1-haiku` |
| holdout | 5 | `raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`, `llm-summary-v1-haiku` |
| stress | 6 | `raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`, `llm-summary-v1-haiku` |

## 7. Real summary signal recall

Side-by-side recall of every locked baseline plus the new real summary method `llm-summary-v1-haiku`. `Reduction` = bytes saved vs raw; `Mapping` = chunk count. `Summary Processing Tokens` is 0 for non-summary methods and equals map+reduce input/output token totals for the LLM summary.

| Method | Split | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping | Sum Proc Tok | Final Ctx Tok |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `raw` | dev | 100.0% | 100.0% | 100.0% | 0.0% | — | — | N/A |
| `raw` | holdout | 100.0% | 100.0% | 100.0% | 0.0% | — | — | N/A |
| `raw` | stress | 100.0% | 100.0% | 100.0% | 0.0% | — | — | N/A |
| `tail` | dev | 63.3% | 70.0% | 30.7% | 81.6% | — | — | N/A |
| `tail` | holdout | 93.1% | 95.0% | 100.0% | 51.3% | — | — | N/A |
| `tail` | stress | 100.0% | 100.0% | 100.0% | 33.5% | — | — | N/A |
| `grep` | dev | 86.7% | 88.3% | 78.4% | 69.8% | — | — | N/A |
| `grep` | holdout | 89.8% | 95.0% | 73.1% | 87.0% | — | — | N/A |
| `grep` | stress | 86.2% | 87.5% | 86.5% | 89.7% | — | — | N/A |
| `rtk-read` | dev | 100.0% | 100.0% | N/A | 0.0% | — | — | N/A |
| `rtk-read` | holdout | 100.0% | 100.0% | N/A | 0.0% | — | — | N/A |
| `rtk-read` | stress | 100.0% | 100.0% | N/A | 0.0% | — | — | N/A |
| `rtk-log` | dev | 25.7% | 30.3% | N/A | 99.2% | — | — | N/A |
| `rtk-log` | holdout | 33.1% | 36.0% | N/A | 97.5% | — | — | N/A |
| `rtk-log` | stress | 30.3% | 34.2% | N/A | 96.9% | — | — | N/A |
| `rtk-err-cat` | dev | 73.3% | 77.7% | N/A | 86.7% | — | — | N/A |
| `rtk-err-cat` | holdout | 48.8% | 43.0% | N/A | 97.0% | — | — | N/A |
| `rtk-err-cat` | stress | 39.2% | 44.2% | N/A | 97.2% | — | — | N/A |
| `llm-summary-v1-mock` | dev | 42.4% | 43.3% | N/A | 98.5% | — | — | N/A |
| `llm-summary-v1-mock` | holdout | 60.1% | 58.0% | N/A | 96.6% | — | — | N/A |
| `llm-summary-v1-mock` | stress | 55.9% | 64.2% | N/A | 91.9% | — | — | N/A |
| `llm-summary-v1-haiku` | dev | 58.1% | 64.7% | N/A | 98.6% | 1–24 | 698.3k | 735 |
| `llm-summary-v1-haiku` | holdout | 47.6% | 57.0% | N/A | 96.2% | 1–3 | 69.2k | 384 |
| `llm-summary-v1-haiku` | stress | 44.3% | 47.5% | N/A | 79.9% | 1–9 | 558.8k | 346 |

## 8. Diagnosis comparison (sv1.1 primary)

| Method | Split | Success | CMS v1.1 | Crit Mention | Must Mention | File Recall | Test Recall | confErr v1.1 | Abstention | sv1.1 | sv1 | Ctx Tok | Diag Tok |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw` | dev | 80.0% | 0.100 | 25.0% | 20.0% | 20.0% | 0.0% | 0.0% | 80.0% | **0.167** | 0.092 | 130.2k | 115 |
| `raw` | holdout | 100.0% | 0.700 | 76.0% | 91.0% | 75.0% | 100.0% | 0.0% | 0.0% | **0.705** | 0.580 | 11.1k | 462 |
| `raw` | stress | 100.0% | 0.583 | 57.5% | 66.7% | 33.3% | 0.0% | 0.0% | 33.3% | **0.491** | 0.429 | 91.2k | 290 |
| `tail` | dev | 100.0% | 0.500 | 56.0% | 60.0% | 53.3% | 33.3% | 0.0% | 0.0% | **0.520** | 0.355 | 5.6k | 505 |
| `tail` | holdout | 100.0% | 0.800 | 85.0% | 86.0% | 50.0% | 100.0% | 0.0% | 0.0% | **0.732** | 0.682 | 4.6k | 446 |
| `tail` | stress | 100.0% | 0.917 | 81.7% | 91.7% | 100.0% | 0.0% | 0.0% | 0.0% | **0.732** | 0.669 | 5.0k | 386 |
| `grep` | dev | 100.0% | 0.500 | 63.7% | 70.0% | 70.0% | 66.7% | 0.0% | 0.0% | **0.604** | 0.429 | 42.5k | 545 |
| `grep` | holdout | 100.0% | 0.700 | 76.0% | 88.0% | 37.5% | 100.0% | 0.0% | 0.0% | **0.674** | 0.549 | 1.5k | 396 |
| `grep` | stress | 100.0% | 0.917 | 80.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | **0.749** | 0.686 | 1.9k | 358 |
| `rtk-read` | dev | 80.0% | 0.100 | 25.0% | 20.0% | 20.0% | 0.0% | 0.0% | 80.0% | **0.165** | 0.090 | 130.2k | 111 |
| `rtk-read` | holdout | 100.0% | 0.700 | 85.0% | 91.0% | 100.0% | 100.0% | 0.0% | 0.0% | **0.739** | 0.614 | 11.1k | 510 |
| `rtk-read` | stress | 100.0% | 0.417 | 65.8% | 66.7% | 33.3% | 0.0% | 0.0% | 33.3% | **0.468** | 0.364 | 91.2k | 284 |
| `rtk-log` | dev | 100.0% | 0.500 | 23.0% | 40.0% | 16.7% | 16.7% | 20.0% | 0.0% | **0.300** | 0.178 | 385 | 405 |
| `rtk-log` | holdout | 100.0% | 0.600 | 31.0% | 45.0% | 0.0% | 0.0% | 0.0% | 0.0% | **0.373** | 0.273 | 260 | 335 |
| `rtk-log` | stress | 100.0% | 0.083 | 34.2% | 16.7% | 0.0% | 0.0% | 33.3% | 50.0% | **0.167** | 0.146 | 165 | 284 |
| `rtk-err-cat` | dev | 100.0% | 0.800 | 58.7% | 65.0% | 60.0% | 66.7% | 0.0% | 20.0% | **0.651** | 0.651 | 9.4k | 559 |
| `rtk-err-cat` | holdout | 100.0% | 0.600 | 35.0% | 52.0% | 12.5% | 0.0% | 0.0% | 20.0% | **0.411** | 0.411 | 365 | 327 |
| `rtk-err-cat` | stress | 100.0% | 0.500 | 34.2% | 41.7% | 66.7% | 100.0% | 0.0% | 50.0% | **0.420** | 0.420 | 2.5k | 214 |
| `llm-summary-v1-mock` | dev | 100.0% | 0.700 | 43.3% | 45.0% | 46.7% | 0.0% | 0.0% | 0.0% | **0.484** | 0.409 | 1.5k | 429 |
| `llm-summary-v1-mock` | holdout | 100.0% | 0.600 | 53.0% | 61.0% | 12.5% | 0.0% | 0.0% | 20.0% | **0.488** | 0.438 | 362 | 324 |
| `llm-summary-v1-mock` | stress | 100.0% | 0.583 | 61.7% | 41.7% | 66.7% | 100.0% | 0.0% | 33.3% | **0.510** | 0.489 | 373 | 289 |
| `llm-summary-v1-haiku` | dev | 100.0% | 0.300 | 54.0% | 70.0% | 60.0% | 66.7% | 0.0% | 0.0% | **0.523** | 0.348 | 735 | 565 |
| `llm-summary-v1-haiku` | holdout | 100.0% | 0.600 | 52.0% | 59.0% | 62.5% | 100.0% | 0.0% | 40.0% | **0.541** | 0.541 | 384 | 347 |
| `llm-summary-v1-haiku` | stress | 100.0% | 0.417 | 47.5% | 56.7% | 33.3% | 0.0% | 0.0% | 50.0% | **0.420** | 0.357 | 237 | 287 |

## 9. sv1 vs sv1.1 comparison

| Method | Split | sv1 | sv1.1 | Δ | confErr v1 | confErr v1.1 |
|---|---|---:|---:|---:|---:|---:|
| `raw` | dev | 0.092 | 0.167 | +0.075 | 20.0% | 0.0% |
| `raw` | holdout | 0.580 | 0.705 | +0.125 | 40.0% | 0.0% |
| `raw` | stress | 0.429 | 0.491 | +0.062 | 16.7% | 0.0% |
| `tail` | dev | 0.355 | 0.520 | +0.165 | 60.0% | 0.0% |
| `tail` | holdout | 0.682 | 0.732 | +0.050 | 20.0% | 0.0% |
| `tail` | stress | 0.669 | 0.732 | +0.062 | 16.7% | 0.0% |
| `grep` | dev | 0.429 | 0.604 | +0.175 | 60.0% | 0.0% |
| `grep` | holdout | 0.549 | 0.674 | +0.125 | 40.0% | 0.0% |
| `grep` | stress | 0.686 | 0.749 | +0.062 | 16.7% | 0.0% |
| `rtk-read` | dev | 0.090 | 0.165 | +0.075 | 20.0% | 0.0% |
| `rtk-read` | holdout | 0.614 | 0.739 | +0.125 | 40.0% | 0.0% |
| `rtk-read` | stress | 0.364 | 0.468 | +0.104 | 33.3% | 0.0% |
| `rtk-log` | dev | 0.178 | 0.300 | +0.122 | 60.0% | 20.0% |
| `rtk-log` | holdout | 0.273 | 0.373 | +0.100 | 20.0% | 0.0% |
| `rtk-log` | stress | 0.146 | 0.167 | +0.021 | 33.3% | 33.3% |
| `rtk-err-cat` | dev | 0.651 | 0.651 | +0.000 | 0.0% | 0.0% |
| `rtk-err-cat` | holdout | 0.411 | 0.411 | +0.000 | 0.0% | 0.0% |
| `rtk-err-cat` | stress | 0.420 | 0.420 | +0.000 | 0.0% | 0.0% |
| `llm-summary-v1-mock` | dev | 0.409 | 0.484 | +0.075 | 20.0% | 0.0% |
| `llm-summary-v1-mock` | holdout | 0.438 | 0.488 | +0.050 | 20.0% | 0.0% |
| `llm-summary-v1-mock` | stress | 0.489 | 0.510 | +0.021 | 0.0% | 0.0% |
| `llm-summary-v1-haiku` | dev | 0.348 | 0.523 | +0.175 | 60.0% | 0.0% |
| `llm-summary-v1-haiku` | holdout | 0.541 | 0.541 | +0.000 | 0.0% | 0.0% |
| `llm-summary-v1-haiku` | stress | 0.357 | 0.420 | +0.062 | 16.7% | 0.0% |

## 10. Full pipeline cost table

Pipeline tokens = `summary_processing_tokens` + `final_context_tokens` + `diagnosis_output_tokens`. summary_processing is non-zero only for the real summary method; for the deterministic baselines it is 0 by definition.

| Method | Split | Sum Proc Tok | Final Ctx Tok | Diag Out Tok | Total Pipeline Tok | Estimated Calls | Unsupported | Provider Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `raw` | dev | 0 | 130.2k | 115 | **130.3k** | — | 0 | 1 |
| `raw` | holdout | 0 | 11.1k | 462 | **11.5k** | — | 0 | 0 |
| `raw` | stress | 0 | 91.2k | 290 | **91.5k** | — | 0 | 0 |
| `tail` | dev | 0 | 5.6k | 505 | **6.1k** | — | 0 | 0 |
| `tail` | holdout | 0 | 4.6k | 446 | **5.0k** | — | 0 | 0 |
| `tail` | stress | 0 | 5.0k | 386 | **5.3k** | — | 0 | 0 |
| `grep` | dev | 0 | 42.5k | 545 | **43.0k** | — | 0 | 0 |
| `grep` | holdout | 0 | 1.5k | 396 | **1.9k** | — | 0 | 0 |
| `grep` | stress | 0 | 1.9k | 358 | **2.2k** | — | 0 | 0 |
| `rtk-read` | dev | 0 | 130.2k | 111 | **130.3k** | — | 0 | 1 |
| `rtk-read` | holdout | 0 | 11.1k | 510 | **11.6k** | — | 0 | 0 |
| `rtk-read` | stress | 0 | 91.2k | 284 | **91.5k** | — | 0 | 0 |
| `rtk-log` | dev | 0 | 385 | 405 | **791** | — | 0 | 0 |
| `rtk-log` | holdout | 0 | 260 | 335 | **595** | — | 0 | 0 |
| `rtk-log` | stress | 0 | 165 | 284 | **449** | — | 0 | 0 |
| `rtk-err-cat` | dev | 0 | 9.4k | 559 | **9.9k** | — | 0 | 0 |
| `rtk-err-cat` | holdout | 0 | 365 | 327 | **693** | — | 0 | 0 |
| `rtk-err-cat` | stress | 0 | 2.5k | 214 | **2.8k** | — | 0 | 0 |
| `llm-summary-v1-mock` | dev | 0 | 1.5k | 429 | **2.0k** | — | 0 | 0 |
| `llm-summary-v1-mock` | holdout | 0 | 362 | 324 | **686** | — | 0 | 0 |
| `llm-summary-v1-mock` | stress | 0 | 373 | 289 | **662** | — | 0 | 0 |
| `llm-summary-v1-haiku` | dev | 139.7k | 735 | 565 | **141.0k** | 56 | 0 | 0 |
| `llm-summary-v1-haiku` | holdout | 13.8k | 384 | 347 | **14.6k** | 13 | 0 | 0 |
| `llm-summary-v1-haiku` | stress | 93.1k | 237 | 287 | **93.7k** | 28 | 0 | 2 |

## 11. Summary failure-mode analysis

Per-case rows for the real summary method only. `expert-reviewed?` is YES on holdout cases that were part of the E2 expert-model review batch.

| Case | Split | Sum Tok | Sum Proc Tok | Sig Recall | Crit Recall | sv1.1 | expert-reviewed? | Failure mode |
|---|---|---:|---:|---:|---:|---:|---|---|
| `cargo-tokio-001` | dev | 519 | 104.7k | 57.1% | 66.7% | 0.500 | no | — |
| `jest-nextjs-001` | dev | 888 | 301.0k | 50.0% | 50.0% | 0.440 | no | good_high_level_but_missing_repair_evidence |
| `lint-react-001` | dev | 326 | 8.7k | 66.7% | 66.7% | 0.675 | no | — |
| `mypy-pandas-001` | dev | 611 | 136.5k | 50.0% | 60.0% | 0.680 | no | omitted_file_name |
| `pytest-pandas-001` | dev | 1.3k | 147.4k | 66.7% | 80.0% | 0.320 | no | omitted_file_name, omitted_test_name, good_high_level_but_missing_repair_evidence |
| `actions-terraform-001` | holdout | 192 | 7.2k | 0.0% | 0.0% | 0.175 | YES | omitted_primary_error, omitted_file_name |
| `dependabot-cargo-001` | holdout | 430 | 12.6k | 50.0% | 50.0% | 0.225 | YES | — |
| `docs-transformers-001` | holdout | 440 | 16.5k | 66.7% | 80.0% | 0.710 | YES | — |
| `pushpr-nextjs-001` | holdout | 455 | 23.4k | 71.4% | 80.0% | 0.823 | YES | — |
| `tsc-typescript-001` | holdout | 404 | 9.5k | 50.0% | 75.0% | 0.770 | YES | — |
| `cleanup-k8s-stress-001` | stress | 302 | 3.8k | 60.0% | 75.0% | 0.685 | no | — |
| `cleanup-tsc-stress-001` | stress | 355 | 3.3k | 60.0% | 75.0% | 0.700 | no | — |
| `docbuild-hf-stress-001` | stress | 373 | 3.5k | 60.0% | 60.0% | 0.333 | no | good_high_level_but_missing_repair_evidence |
| `prettier-react-stress-001` | stress | 355 | 6.2k | 85.7% | 75.0% | 0.700 | no | — |
| `pytest-sklearn-stress-001` | stress | N/A | 284.0k | 0.0% | 0.0% | 0.050 | no | omitted_primary_error, omitted_file_name, omitted_test_name |
| `pytest-sklearn-stress-002` | stress | N/A | 258.1k | 0.0% | 0.0% | 0.050 | no | omitted_primary_error, omitted_file_name, omitted_test_name |

## 12. Confident-error analysis

Confident-error (sv1.1 trigger: `confidence>=0.7 AND (forbidden>0 OR (cms=0 AND critical<0.5 AND must<0.5))`) rate by method × split:

| Method | dev | holdout | stress |
|---|---:|---:|---:|
| `raw` | 0.0% | 0.0% | 0.0% |
| `tail` | 0.0% | 0.0% | 0.0% |
| `grep` | 0.0% | 0.0% | 0.0% |
| `rtk-read` | 0.0% | 0.0% | 0.0% |
| `rtk-log` | 20.0% | 0.0% | 33.3% |
| `rtk-err-cat` | 0.0% | 0.0% | 0.0% |
| `llm-summary-v1-mock` | 0.0% | 0.0% | 0.0% |
| `llm-summary-v1-haiku` | 0.0% | 0.0% | 0.0% |

## 13. Abstention analysis

| Method | dev | holdout | stress |
|---|---:|---:|---:|
| `raw` | 80.0% | 0.0% | 33.3% |
| `tail` | 0.0% | 0.0% | 0.0% |
| `grep` | 0.0% | 0.0% | 0.0% |
| `rtk-read` | 80.0% | 0.0% | 33.3% |
| `rtk-log` | 0.0% | 0.0% | 50.0% |
| `rtk-err-cat` | 20.0% | 20.0% | 50.0% |
| `llm-summary-v1-mock` | 0.0% | 20.0% | 33.3% |
| `llm-summary-v1-haiku` | 0.0% | 40.0% | 50.0% |

## 14. Unsupported-context / provider-error analysis

Per-method counts of `provider_error`/`unsupported_context_too_large` rows.

| Method | Split | Provider errors | Cases |
|---|---|---:|---:|
| `raw` | dev | 1 | 5 |
| `raw` | holdout | 0 | 5 |
| `raw` | stress | 0 | 6 |
| `tail` | dev | 0 | 5 |
| `tail` | holdout | 0 | 5 |
| `tail` | stress | 0 | 6 |
| `grep` | dev | 0 | 5 |
| `grep` | holdout | 0 | 5 |
| `grep` | stress | 0 | 6 |
| `rtk-read` | dev | 1 | 5 |
| `rtk-read` | holdout | 0 | 5 |
| `rtk-read` | stress | 0 | 6 |
| `rtk-log` | dev | 0 | 5 |
| `rtk-log` | holdout | 0 | 5 |
| `rtk-log` | stress | 0 | 6 |
| `rtk-err-cat` | dev | 0 | 5 |
| `rtk-err-cat` | holdout | 0 | 5 |
| `rtk-err-cat` | stress | 0 | 6 |
| `llm-summary-v1-mock` | dev | 0 | 5 |
| `llm-summary-v1-mock` | holdout | 0 | 5 |
| `llm-summary-v1-mock` | stress | 0 | 6 |
| `llm-summary-v1-haiku` | dev | 0 | 5 |
| `llm-summary-v1-haiku` | holdout | 0 | 5 |
| `llm-summary-v1-haiku` | stress | 0 | 6 |

## 15. Generalization table (sv1.1)

Per-method `diagnosis_score_v1_1` across splits. `Max Gap` is the spread between the best and worst split for that method; `Large Gap?` is YES when the gap is ≥ 20 percentage points (0.20).

| Method | dev | holdout | stress | Max Gap | Large Gap? |
|---|---:|---:|---:|---:|---|
| `raw` | 0.167 | 0.705 | 0.491 | 0.538 | YES |
| `tail` | 0.520 | 0.732 | 0.732 | 0.212 | YES |
| `grep` | 0.604 | 0.674 | 0.749 | 0.145 | — |
| `rtk-read` | 0.165 | 0.739 | 0.468 | 0.574 | YES |
| `rtk-log` | 0.300 | 0.373 | 0.167 | 0.206 | YES |
| `rtk-err-cat` | 0.651 | 0.411 | 0.420 | 0.241 | YES |
| `llm-summary-v1-mock` | 0.484 | 0.488 | 0.510 | 0.025 | — |
| `llm-summary-v1-haiku` | 0.523 | 0.541 | 0.420 | 0.121 | — |

## 16. Per-case hard failures (sv1.1 < 0.20)

| Case | Split | Method | sv1.1 | confErr v1.1 | provider_error |
|---|---|---|---:|:---:|---|
| `cargo-tokio-001` | dev | `raw` | 0.000 | — | RuntimeError: diagnosis command exited 1: diagnosis_shim_claude_cli: RuntimeError: claude CLI exited 1: ''
 |
| `jest-nextjs-001` | dev | `raw` | 0.075 | — | — |
| `mypy-pandas-001` | dev | `raw` | 0.000 | — | — |
| `pytest-pandas-001` | dev | `raw` | 0.000 | — | — |
| `jest-nextjs-001` | dev | `rtk-log` | 0.000 | YES | — |
| `cargo-tokio-001` | dev | `rtk-read` | 0.000 | — | RuntimeError: diagnosis command exited 1: diagnosis_shim_claude_cli: RuntimeError: claude CLI exited 1: ''
 |
| `jest-nextjs-001` | dev | `rtk-read` | 0.075 | — | — |
| `mypy-pandas-001` | dev | `rtk-read` | 0.000 | — | — |
| `pytest-pandas-001` | dev | `rtk-read` | 0.000 | — | — |
| `actions-terraform-001` | holdout | `llm-summary-v1-haiku` | 0.175 | — | — |
| `dependabot-cargo-001` | holdout | `rtk-err-cat` | 0.150 | — | — |
| `pytest-sklearn-stress-001` | stress | `llm-summary-v1-haiku` | 0.050 | — | — |
| `pytest-sklearn-stress-002` | stress | `llm-summary-v1-haiku` | 0.050 | — | — |
| `pytest-sklearn-stress-001` | stress | `raw` | 0.060 | — | — |
| `pytest-sklearn-stress-002` | stress | `raw` | 0.060 | — | — |
| `cleanup-k8s-stress-001` | stress | `rtk-err-cat` | 0.050 | — | — |
| `cleanup-tsc-stress-001` | stress | `rtk-err-cat` | 0.050 | — | — |
| `prettier-react-stress-001` | stress | `rtk-err-cat` | 0.165 | — | — |
| `cleanup-k8s-stress-001` | stress | `rtk-log` | 0.165 | — | — |
| `pytest-sklearn-stress-001` | stress | `rtk-log` | 0.000 | YES | — |
| `pytest-sklearn-stress-002` | stress | `rtk-log` | 0.000 | YES | — |
| `pytest-sklearn-stress-001` | stress | `rtk-read` | 0.060 | — | — |
| `pytest-sklearn-stress-002` | stress | `rtk-read` | 0.060 | — | — |

## 17. Interpretation guardrails

- One summarizer (`llm-summary-v1-haiku`), one debugger (`real-debugger-v1`), one summary prompt, 16 cases. Treat all numbers as directional, not statistical.
- Same model on both sides. A Sonnet-summarizer / Haiku-debugger run is the natural follow-up to disentangle self-call effects.
- sv1.1 is the calibrated score from E2b, but the calibration was done with **expert-model** review labels (`claude-opus-4-7-expert`), not human review. Real human review remains the canonical calibration.
- `llm-summary-v1-mock` is a deterministic stub; the gap between mock and real summary is informative but is not a fair LLM-summary baseline.
- Pricing for Haiku changes over time; the cost table is informational.

## 18. Recommended next experiment

Pick one of the four options listed in the E3 plan based on the sv1.1 / cost / signal-recall numbers above:

- **Option A: real summary clearly useful** — freeze `cilogbench-v1.3` with the real summary as a baseline; queue an actual human review of the summary diagnoses.
- **Option B: concise but lossy** — improve the summary prompt on dev only, freeze `llm_summary_v2_*` prompts.
- **Option C: useful but expensive** — explore a hybrid (grep-first, summary-on-fallback).
- **Option D: results mixed** — run a second debugger model or human review before adding more methods.

