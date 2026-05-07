# E5 — Hybrid Grep Fallback Baseline (`hybrid-grep-4k-rtk-err-cat-v1`)

- **Experiment ID:** `E5-hybrid-grep-fallback-v1`
- **Protocol:** `cilogbench-v1.2` (SHA `cc4fdbe62d7793a3…`)
- **Hybrid config:** `configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json` (SHA `c2ffaec3c4a85055…`)
- **Primary:** `grep`  ·  **Fallback:** `rtk-err-cat`  ·  **Budget:** 4000 tokens (chars/4 estimate)
- **Debugger:** `real-debugger-v1` (held fixed from E1/E3)
- **Splits:** dev, holdout, stress
- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated). `diagnosis_score_v1` reported as secondary.

## 1. Executive summary

Per-split macro `diagnosis_score_v1_1` for the hybrid vs. `grep` baseline:

| Split | hybrid sv1.1 | grep sv1.1 | Δ | hybrid macro ctx tok | hybrid confErr v1.1 |
|---|---:|---:|---:|---:|---:|
| dev | 0.699 | 0.604 | +0.096 | 9.0k | 0.0% |
| holdout | 0.714 | 0.674 | +0.040 | 1.5k | 0.0% |
| stress | 0.732 | 0.749 | -0.017 | 2.7k | 0.0% |

## 2. E4 motivation

From `reports/e4_summary_failure_attribution_cilogbench_v1_2.md` section 9: the routing policy `grep-if-fits-else-rtk-err-cat @4k` scored **0.723** macro sv1.1 on the offline E4 simulation versus **0.680** for `grep-default`, while spending ~⅓ the total-pipeline tokens. E5 implements this policy as a first-class deterministic context method (`hybrid-grep-4k-rtk-err-cat-v1`) so it gets the same byte-stable scoring treatment as every other locked baseline, and so we can check whether the offline win survives a real run.

## 3. Hybrid method definition

```text
For each case in {dev, holdout, stress}:
  if grep is available and (output_byte_size / 4) <= 4000:
      select grep
  elif rtk-err-cat is available:
      select rtk-err-cat        # primary_too_large_used_fallback
                                 # OR primary_provider_error_used_fallback
  else:
      record provider_error    # do not silently fall back to raw
```

The token estimate is `output_byte_size // 4` from the existing manifest rows — this matches `tools/run_diagnosis.py`'s `context_tokens` accounting on every locked grep/rtk-err-cat manifest (verified ratio 1.000).

## 4. Anti-leakage statement

The router reads only pre-diagnosis context metadata: per-case `case_id`, `context_path`, `output_byte_size`, `output_line_count`, `included_line_ranges`, and `metadata.provider_error`.

It does **not** read:
- `cases/<split>/<case_id>/ground_truth.json`
- `results/<split>/eval_*.json` (signal recall or diagnosis eval)
- `review/batches/*/labels/*.jsonl` (expert/human review labels)
- any `failure_category` / `required_signals` / `evidence_spans` field

The 4k threshold itself was chosen in E4's offline budget sweep, but the per-case decision in E5 only consults the budget and the raw manifest fields above — no scoring information leaks into the router.

## 5. Routing decisions by split

### Table 1 — Routing summary

| Split | Cases | Selected `grep` | Selected `rtk-err-cat` | Provider errors | Mean selected ctx tok |
|---|---:|---:|---:|---:|---:|
| dev | 5 | 1 | 4 | 0 | 9.0k |
| holdout | 5 | 5 | 0 | 0 | 1.5k |
| stress | 6 | 4 | 2 | 0 | 2.7k |

### Table 2 — Per-case routing

| Case | Split | grep tok | rtk tok | Selected | Reason | Hybrid sv1.1 | Grep sv1.1 | RTK sv1.1 | Δ vs grep |
|---|---|---:|---:|---|---|---:|---:|---:|---:|
| `cargo-tokio-001` | dev | 43496 | 7312 | `rtk-err-cat` | `primary_too_large_used_fallback` | 0.790 | 0.475 | 0.700 | +0.315 |
| `jest-nextjs-001` | dev | 60271 | 2556 | `rtk-err-cat` | `primary_too_large_used_fallback` | 0.700 | 0.625 | 0.700 | +0.075 |
| `lint-react-001` | dev | 317 | 2216 | `grep` | `primary_fits_budget` | 0.608 | 0.608 | 0.250 | +0.000 |
| `mypy-pandas-001` | dev | 27249 | 18892 | `rtk-err-cat` | `primary_too_large_used_fallback` | 0.760 | 0.720 | 0.720 | +0.040 |
| `pytest-pandas-001` | dev | 81104 | 15870 | `rtk-err-cat` | `primary_too_large_used_fallback` | 0.637 | 0.590 | 0.887 | +0.047 |
| `actions-terraform-001` | holdout | 358 | 91 | `grep` | `primary_fits_budget` | 0.600 | 0.675 | 0.200 | -0.075 |
| `dependabot-cargo-001` | holdout | 1956 | 146 | `grep` | `primary_fits_budget` | 0.400 | 0.315 | 0.150 | +0.085 |
| `docs-transformers-001` | holdout | 1751 | 218 | `grep` | `primary_fits_budget` | 0.710 | 0.693 | 0.530 | +0.017 |
| `pushpr-nextjs-001` | holdout | 2489 | 1026 | `grep` | `primary_fits_budget` | 0.900 | 0.800 | 0.660 | +0.100 |
| `tsc-typescript-001` | holdout | 908 | 356 | `grep` | `primary_fits_budget` | 0.960 | 0.885 | 0.513 | +0.075 |
| `cleanup-k8s-stress-001` | stress | 82 | 11 | `grep` | `primary_fits_budget` | 0.725 | 0.650 | 0.050 | +0.075 |
| `cleanup-tsc-stress-001` | stress | 82 | 11 | `grep` | `primary_fits_budget` | 0.650 | 0.725 | 0.050 | -0.075 |
| `docbuild-hf-stress-001` | stress | 229 | 52 | `grep` | `primary_fits_budget` | 0.543 | 0.775 | 0.495 | -0.232 |
| `prettier-react-stress-001` | stress | 339 | 17 | `grep` | `primary_fits_budget` | 0.667 | 0.667 | 0.165 | +0.000 |
| `pytest-sklearn-stress-001` | stress | 5548 | 7780 | `rtk-err-cat` | `primary_too_large_used_fallback` | 0.857 | 0.850 | 0.873 | +0.007 |
| `pytest-sklearn-stress-002` | stress | 4925 | 7658 | `rtk-err-cat` | `primary_too_large_used_fallback` | 0.950 | 0.828 | 0.890 | +0.122 |

## 6. Signal recall comparison

### Table 3 — Signal recall

| Method | Split | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping |
|---|---|---:|---:|---:|---:|---|
| `grep` | dev | 86.7% | 88.3% | 78.4% | 69.8% | text |
| `grep` | holdout | 89.8% | 95.0% | 73.1% | 87.0% | text |
| `grep` | stress | 86.2% | 87.5% | 86.5% | 89.7% | text |
| `rtk-err-cat` | dev | 73.3% | 77.7% | n/a | 86.7% | text |
| `rtk-err-cat` | holdout | 48.8% | 43.0% | n/a | 97.0% | text |
| `rtk-err-cat` | stress | 39.2% | 44.2% | n/a | 97.2% | text |
| `hybrid-grep-4k-rtk-err-cat-v1` | dev | 76.7% | 84.3% | 75.0% | 92.0% | text |
| `hybrid-grep-4k-rtk-err-cat-v1` | holdout | 89.8% | 95.0% | 73.1% | 86.5% | line |
| `hybrid-grep-4k-rtk-err-cat-v1` | stress | 80.6% | 87.5% | 91.7% | 86.8% | line |
| `tail` | dev | 63.3% | 70.0% | 30.7% | 81.6% | text |
| `tail` | holdout | 93.1% | 95.0% | 100.0% | 51.3% | text |
| `tail` | stress | 100.0% | 100.0% | 100.0% | 33.5% | text |
| `raw` | dev | 100.0% | 100.0% | 100.0% | 0.0% | text |
| `raw` | holdout | 100.0% | 100.0% | 100.0% | 0.0% | text |
| `raw` | stress | 100.0% | 100.0% | 100.0% | 0.0% | text |
| `llm-summary-v1-haiku` | dev | 58.1% | 64.7% | n/a | 98.6% | text |
| `llm-summary-v1-haiku` | holdout | 47.6% | 57.0% | n/a | 96.2% | text |
| `llm-summary-v1-haiku` | stress | 44.3% | 47.5% | n/a | 79.9% | text |

## 7. Diagnosis comparison (sv1.1 primary)

### Table 4 — Diagnosis

| Method | Split | Success | CMS v1.1 | Crit Mention | Must Mention | confErr v1.1 | Abstention | sv1.1 | sv1 | Ctx Tok |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw` | dev | 80.0% | 0.100 | 25.0% | 20.0% | 0.0% | 80.0% | **0.167** | 0.092 | 130.2k |
| `raw` | holdout | 100.0% | 0.700 | 76.0% | 91.0% | 0.0% | 0.0% | **0.705** | 0.580 | 11.1k |
| `raw` | stress | 100.0% | 0.583 | 57.5% | 66.7% | 0.0% | 33.3% | **0.491** | 0.429 | 91.2k |
| `tail` | dev | 100.0% | 0.500 | 56.0% | 60.0% | 0.0% | 0.0% | **0.520** | 0.355 | 5.6k |
| `tail` | holdout | 100.0% | 0.800 | 85.0% | 86.0% | 0.0% | 0.0% | **0.732** | 0.682 | 4.6k |
| `tail` | stress | 100.0% | 0.917 | 81.7% | 91.7% | 0.0% | 0.0% | **0.732** | 0.669 | 5.0k |
| `grep` | dev | 100.0% | 0.500 | 63.7% | 70.0% | 0.0% | 0.0% | **0.604** | 0.429 | 42.5k |
| `grep` | holdout | 100.0% | 0.700 | 76.0% | 88.0% | 0.0% | 0.0% | **0.674** | 0.549 | 1.5k |
| `grep` | stress | 100.0% | 0.917 | 80.0% | 100.0% | 0.0% | 0.0% | **0.749** | 0.686 | 1.9k |
| `rtk-err-cat` | dev | 100.0% | 0.800 | 58.7% | 65.0% | 0.0% | 20.0% | **0.651** | 0.651 | 9.4k |
| `rtk-err-cat` | holdout | 100.0% | 0.600 | 35.0% | 52.0% | 0.0% | 20.0% | **0.411** | 0.411 | 365 |
| `rtk-err-cat` | stress | 100.0% | 0.500 | 34.2% | 41.7% | 0.0% | 50.0% | **0.420** | 0.420 | 2.5k |
| `rtk-read` | dev | 80.0% | 0.100 | 25.0% | 20.0% | 0.0% | 80.0% | **0.165** | 0.090 | 130.2k |
| `rtk-read` | holdout | 100.0% | 0.700 | 85.0% | 91.0% | 0.0% | 0.0% | **0.739** | 0.614 | 11.1k |
| `rtk-read` | stress | 100.0% | 0.417 | 65.8% | 66.7% | 0.0% | 33.3% | **0.468** | 0.364 | 91.2k |
| `rtk-log` | dev | 100.0% | 0.500 | 23.0% | 40.0% | 20.0% | 0.0% | **0.300** | 0.178 | 385 |
| `rtk-log` | holdout | 100.0% | 0.600 | 31.0% | 45.0% | 0.0% | 0.0% | **0.373** | 0.273 | 260 |
| `rtk-log` | stress | 100.0% | 0.083 | 34.2% | 16.7% | 33.3% | 50.0% | **0.167** | 0.146 | 165 |
| `llm-summary-v1-mock` | dev | 100.0% | 0.700 | 43.3% | 45.0% | 0.0% | 0.0% | **0.484** | 0.409 | 1.5k |
| `llm-summary-v1-mock` | holdout | 100.0% | 0.600 | 53.0% | 61.0% | 0.0% | 20.0% | **0.488** | 0.438 | 362 |
| `llm-summary-v1-mock` | stress | 100.0% | 0.583 | 61.7% | 41.7% | 0.0% | 33.3% | **0.510** | 0.489 | 373 |
| `llm-summary-v1-haiku` | dev | 100.0% | 0.300 | 54.0% | 70.0% | 0.0% | 0.0% | **0.523** | 0.348 | 735 |
| `llm-summary-v1-haiku` | holdout | 100.0% | 0.600 | 52.0% | 59.0% | 0.0% | 40.0% | **0.541** | 0.541 | 384 |
| `llm-summary-v1-haiku` | stress | 100.0% | 0.417 | 47.5% | 56.7% | 0.0% | 50.0% | **0.420** | 0.357 | 237 |
| `hybrid-grep-4k-rtk-err-cat-v1` | dev | 100.0% | 0.700 | 68.7% | 80.0% | 0.0% | 0.0% | **0.699** | 0.574 | 9.0k |
| `hybrid-grep-4k-rtk-err-cat-v1` | holdout | 100.0% | 0.700 | 81.0% | 88.0% | 0.0% | 0.0% | **0.714** | 0.589 | 1.5k |
| `hybrid-grep-4k-rtk-err-cat-v1` | stress | 100.0% | 0.917 | 73.3% | 81.7% | 0.0% | 0.0% | **0.732** | 0.669 | 2.7k |

## 8. Cost / token comparison

### Table 5 — Cost

| Method | Split | Final Ctx Tok | Sum Proc Tok | Diag Out Tok | Total Pipeline Tok | Provider Errors |
|---|---|---:|---:|---:|---:|---:|
| `raw` | dev | 130.2k | — | 115 | **130.3k** | 1 |
| `raw` | holdout | 11.1k | — | 462 | **11.5k** | 0 |
| `raw` | stress | 91.2k | — | 290 | **91.5k** | 0 |
| `tail` | dev | 5.6k | — | 505 | **6.1k** | 0 |
| `tail` | holdout | 4.6k | — | 446 | **5.0k** | 0 |
| `tail` | stress | 5.0k | — | 386 | **5.3k** | 0 |
| `grep` | dev | 42.5k | — | 545 | **43.0k** | 0 |
| `grep` | holdout | 1.5k | — | 396 | **1.9k** | 0 |
| `grep` | stress | 1.9k | — | 358 | **2.2k** | 0 |
| `rtk-err-cat` | dev | 9.4k | — | 559 | **9.9k** | 0 |
| `rtk-err-cat` | holdout | 365 | — | 327 | **693** | 0 |
| `rtk-err-cat` | stress | 2.5k | — | 214 | **2.8k** | 0 |
| `rtk-read` | dev | 130.2k | — | 111 | **130.3k** | 1 |
| `rtk-read` | holdout | 11.1k | — | 510 | **11.6k** | 0 |
| `rtk-read` | stress | 91.2k | — | 284 | **91.5k** | 0 |
| `rtk-log` | dev | 385 | — | 405 | **791** | 0 |
| `rtk-log` | holdout | 260 | — | 335 | **595** | 0 |
| `rtk-log` | stress | 165 | — | 284 | **449** | 0 |
| `llm-summary-v1-mock` | dev | 1.5k | — | 429 | **2.0k** | 0 |
| `llm-summary-v1-mock` | holdout | 362 | — | 324 | **686** | 0 |
| `llm-summary-v1-mock` | stress | 373 | — | 289 | **662** | 0 |
| `llm-summary-v1-haiku` | dev | 735 | — | 565 | **1.3k** | 0 |
| `llm-summary-v1-haiku` | holdout | 384 | — | 347 | **731** | 0 |
| `llm-summary-v1-haiku` | stress | 237 | — | 287 | **525** | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | dev | 9.0k | — | 614 | **9.6k** | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | holdout | 1.5k | — | 440 | **2.0k** | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | stress | 2.7k | — | 335 | **3.0k** | 0 |

Note: the table above shows summary-processing as `—` for non-summary methods. The hybrid baseline does not call any LLM during context construction (it copies an already-built grep or rtk-err-cat context); summary-processing for hybrid is therefore 0.

## 9. Provider-error analysis

| Split | Method | Case | Error |
|---|---|---|---|
| dev | `raw` | `cargo-tokio-001` | `RuntimeError: diagnosis command exited 1: diagnosis_shim_claude_cli: RuntimeError: claude CLI exited 1: ''
` |
| dev | `rtk-read` | `cargo-tokio-001` | `RuntimeError: diagnosis command exited 1: diagnosis_shim_claude_cli: RuntimeError: claude CLI exited 1: ''
` |

## 10. Confident-error and abstention analysis

| Method | Split | confErr v1 | confErr v1.1 | Abstention |
|---|---|---:|---:|---:|
| `grep` | dev | 60.0% | 0.0% | 0.0% |
| `grep` | holdout | 40.0% | 0.0% | 0.0% |
| `grep` | stress | 16.7% | 0.0% | 0.0% |
| `rtk-err-cat` | dev | 0.0% | 0.0% | 20.0% |
| `rtk-err-cat` | holdout | 0.0% | 0.0% | 20.0% |
| `rtk-err-cat` | stress | 0.0% | 0.0% | 50.0% |
| `hybrid-grep-4k-rtk-err-cat-v1` | dev | 40.0% | 0.0% | 0.0% |
| `hybrid-grep-4k-rtk-err-cat-v1` | holdout | 40.0% | 0.0% | 0.0% |
| `hybrid-grep-4k-rtk-err-cat-v1` | stress | 16.7% | 0.0% | 0.0% |
| `tail` | dev | 60.0% | 0.0% | 0.0% |
| `tail` | holdout | 20.0% | 0.0% | 0.0% |
| `tail` | stress | 16.7% | 0.0% | 0.0% |
| `llm-summary-v1-haiku` | dev | 60.0% | 0.0% | 0.0% |
| `llm-summary-v1-haiku` | holdout | 0.0% | 0.0% | 40.0% |
| `llm-summary-v1-haiku` | stress | 16.7% | 0.0% | 50.0% |

## 11. Dev/holdout/stress generalization

| Method | dev sv1.1 | holdout sv1.1 | stress sv1.1 | Max Gap | Large Gap? |
|---|---:|---:|---:|---:|---|
| `raw` | 0.167 | 0.705 | 0.491 | 0.538 | YES |
| `tail` | 0.520 | 0.732 | 0.732 | 0.212 | YES |
| `grep` | 0.604 | 0.674 | 0.749 | 0.145 | — |
| `rtk-err-cat` | 0.651 | 0.411 | 0.420 | 0.241 | YES |
| `rtk-read` | 0.165 | 0.739 | 0.468 | 0.574 | YES |
| `rtk-log` | 0.300 | 0.373 | 0.167 | 0.206 | YES |
| `llm-summary-v1-mock` | 0.484 | 0.488 | 0.510 | 0.025 | — |
| `llm-summary-v1-haiku` | 0.523 | 0.541 | 0.420 | 0.121 | — |
| `hybrid-grep-4k-rtk-err-cat-v1` | 0.699 | 0.714 | 0.732 | 0.033 | — |

## 12. Comparison to E4 offline prediction

### Table 6 — E4 prediction vs E5 actual

| Metric | E4 offline policy estimate | E5 first-class baseline | Δ |
|---|---:|---:|---:|
| Macro sv1.1 | 0.723 | 0.715 | -0.008 |
| Macro final ctx tok | 4.3k | 4.4k | 154 |
| Macro total pipeline tok | 4.7k | 4.9k | 198 |
| Provider error rate | 0.0% | 0.0% | 0.0% |

## 13. Decision: freeze v1.3 or keep exploratory

**Decision: `FREEZE_V1_3`**

| Criterion | Hybrid | Grep | Pass? |
|---|---:|---:|:---:|
| Macro sv1.1 | 0.715 | 0.675 | ✅ |
| Macro total pipeline tokens | 4.9k | 15.7k | ✅ |
| Macro confErr v1.1 | 0.0% | 0.0% | ✅ |
| Provider error rate ≤ 10% | 0.0% | — | ✅ |

All four freeze criteria met. **Recommend freezing `cilogbench-v1.3` with `hybrid-grep-4k-rtk-err-cat-v1` as a new first-class baseline** alongside the existing locked methods. Then run a second debugger model on v1.3 to check whether the hybrid advantage is model-stable.

## 14. Interpretation guardrails

- One debugger model. The hybrid's advantage may be model-bound — same `real-debugger-v1` (Haiku 4.5) used in E1/E3.
- One threshold (4k tokens) and one fallback method (`rtk-err-cat`). Other thresholds / fallbacks were not implemented in E5.
- 16 cases total — directional, not statistical.
- The 4k threshold was picked from E4's offline analysis on the **same case set**. The hybrid-vs-grep delta therefore should not be re-tuned on holdout/stress without freezing a new protocol.
- The `output_byte_size // 4` token estimate matches `run_diagnosis.py` exactly on chars, but Anthropic's tokenizer may diverge on Unicode-heavy logs; large chars-vs-tokens drift would only matter near the 4k boundary.
- Provider errors on dev `cargo-tokio-001` (raw/rtk-read context-too-large) carry over from E1; the hybrid does not surface them because grep / rtk-err-cat both fit.

## 15. Recommended next experiment

**Freeze `cilogbench-v1.3` with the hybrid baseline included, then run a second debugger model.** The plan-mandated next step after a successful E5 is to confirm the hybrid advantage is not a Haiku-specific artifact. Suggested experiment: **E6 — second-debugger replication on v1.3** (Sonnet 4.6 or Opus 4.7 as `real-debugger-v2`, all other variables fixed).

