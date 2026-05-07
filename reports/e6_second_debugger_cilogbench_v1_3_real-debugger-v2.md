# E6 — Second-Debugger Replication on cilogbench-v1.3 (real-debugger-v2)

- **Experiment ID:** `E6-second-debugger-replication-v1`
- **Protocol:** `cilogbench-v1.3` (SHA `4ef0cf09d8303815…`)
- **Debugger v1:** `real-debugger-v1` (Claude Haiku 4.5; held fixed for comparison)
- **Debugger v2:** `real-debugger-v2` (Claude Sonnet 4.6; this run)
- **Prompt:** `prompts/debugger_v1.md` (SHA `ecffdf03c99a91b0…`) — same prompt for both debuggers
- **Splits:** dev, holdout, stress
- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated; secondary = `diagnosis_score_v1`)

## 1. Executive summary

On `cilogbench-v1.3` with Sonnet 4.6 as `real-debugger-v2`, the locked `hybrid-grep-4k-rtk-err-cat-v1` baseline scored macro sv1.1 = **0.771** vs `grep` = **0.770**. The v1 (Haiku) numbers were hybrid 0.715 / grep 0.675. Detailed rank-stability table is in section 10.

## 2. Protocol summary

- protocol_id: `cilogbench-v1.3`
- inherits_from: `cilogbench-v1.2`
- splits: `dev` (5 cases), `holdout` (5 cases), `stress` (6 cases)
- locked baselines: 8
- primary score: `diagnosis_score_v1_1`
- secondary score: `diagnosis_score_v1`

## 3. Debugger-v2 config and model card

- diagnoser_name: `real-debugger-v2`
- model: `claude-sonnet-4-6` @ `2026-04-25`
- temperature: 0 · max_output_tokens: 1200
- json_mode: True · tool_use: False · web_access: False
- prompt SHA: `ecffdf03c99a91b0f8f75e086720d9fb8db96af0d9dae5285baf679c9c9d28de`
- config SHA: `b26a4637b69fb110400c0b7cd813234f247c76d7a676774d3325954040f076d4`
- model card: `docs/model_cards/real-debugger-v2.md`

## 4. Privacy audit summary

Privacy audits were run for all 8+ context methods × 3 splits before this experiment. Result: 0 hits (see `reports/{dev,holdout,stress}_privacy_audit.md`). Re-run before any downstream sharing.

## 5. Methods and splits evaluated

| Method | dev | holdout | stress |
|---|:---:|:---:|:---:|
| `raw` | 5 | 5 | 6 |
| `tail` | 5 | 5 | 6 |
| `grep` | 5 | 5 | 6 |
| `rtk-read` | 5 | 5 | 6 |
| `rtk-log` | 5 | 5 | 6 |
| `rtk-err-cat` | 5 | 5 | 6 |
| `llm-summary-v1-mock` | 5 | 5 | 6 |
| `hybrid-grep-4k-rtk-err-cat-v1` | 5 | 5 | 6 |

## 6. Per-split diagnosis metrics (real-debugger-v2)

### Table 1 — Per-split v2 diagnosis

| Method | Split | Success | CMS v1.1 | Crit Mention | Must Mention | confErr v1.1 | Abstention | sv1.1 | sv1 | Ctx Tok | Provider Errs |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw` | dev | 100.0% | 0.300 | 35.0% | 35.0% | 0.0% | 60.0% | **0.326** | 0.251 | 130.2k | 0 |
| `raw` | holdout | 100.0% | 0.600 | 85.0% | 91.0% | 0.0% | 0.0% | **0.728** | 0.627 | 11.1k | 0 |
| `raw` | stress | 100.0% | 0.417 | 69.2% | 63.3% | 0.0% | 33.3% | **0.480** | 0.376 | 91.2k | 0 |
| `tail` | dev | 100.0% | 0.700 | 45.3% | 70.0% | 0.0% | 0.0% | **0.590** | 0.465 | 5.6k | 0 |
| `tail` | holdout | 100.0% | 0.600 | 90.0% | 91.0% | 0.0% | 0.0% | **0.725** | 0.625 | 4.6k | 0 |
| `tail` | stress | 100.0% | 0.750 | 85.0% | 96.7% | 0.0% | 0.0% | **0.750** | 0.646 | 5.0k | 0 |
| `grep` | dev | 100.0% | 0.900 | 72.7% | 85.0% | 0.0% | 0.0% | **0.792** | 0.717 | 42.5k | 0 |
| `grep` | holdout | 100.0% | 0.600 | 76.0% | 100.0% | 0.0% | 0.0% | **0.699** | 0.599 | 1.5k | 0 |
| `grep` | stress | 100.0% | 0.917 | 95.8% | 96.7% | 0.0% | 0.0% | **0.819** | 0.756 | 1.9k | 0 |
| `rtk-read` | dev | 100.0% | 0.300 | 25.0% | 35.0% | 0.0% | 60.0% | **0.298** | 0.223 | 130.2k | 0 |
| `rtk-read` | holdout | 100.0% | 0.600 | 91.0% | 96.0% | 0.0% | 0.0% | **0.755** | 0.655 | 11.1k | 0 |
| `rtk-read` | stress | 100.0% | 0.583 | 65.0% | 66.7% | 0.0% | 33.3% | **0.514** | 0.451 | 91.2k | 0 |
| `rtk-log` | dev | 100.0% | 0.700 | 22.0% | 50.0% | 40.0% | 0.0% | **0.295** | 0.295 | 385 | 0 |
| `rtk-log` | holdout | 100.0% | 0.400 | 41.0% | 49.0% | 20.0% | 0.0% | **0.321** | 0.271 | 260 | 0 |
| `rtk-log` | stress | 100.0% | 0.250 | 45.8% | 31.7% | 0.0% | 50.0% | **0.310** | 0.252 | 165 | 0 |
| `rtk-err-cat` | dev | 100.0% | 0.900 | 58.7% | 75.0% | 0.0% | 0.0% | **0.696** | 0.671 | 9.4k | 0 |
| `rtk-err-cat` | holdout | 100.0% | 0.800 | 39.0% | 56.0% | 0.0% | 0.0% | **0.436** | 0.436 | 365 | 0 |
| `rtk-err-cat` | stress | 100.0% | 0.417 | 49.2% | 51.7% | 0.0% | 50.0% | **0.472** | 0.451 | 2.5k | 0 |
| `llm-summary-v1-mock` | dev | 100.0% | 0.900 | 43.3% | 55.0% | 0.0% | 0.0% | **0.551** | 0.526 | 1.5k | 0 |
| `llm-summary-v1-mock` | holdout | 100.0% | 0.600 | 58.0% | 61.0% | 0.0% | 20.0% | **0.506** | 0.456 | 362 | 0 |
| `llm-summary-v1-mock` | stress | 100.0% | 0.417 | 72.5% | 51.7% | 0.0% | 50.0% | **0.497** | 0.476 | 373 | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | dev | 100.0% | 0.900 | 77.7% | 75.0% | 0.0% | 0.0% | **0.775** | 0.700 | 9.0k | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | holdout | 100.0% | 0.600 | 85.0% | 96.0% | 0.0% | 0.0% | **0.723** | 0.623 | 1.5k | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | stress | 100.0% | 0.917 | 91.7% | 91.7% | 0.0% | 0.0% | **0.817** | 0.754 | 2.7k | 0 |

## 7. Hybrid vs grep (v2)

### Table 2 — Hybrid vs grep

| Split | Hybrid sv1.1 | Grep sv1.1 | Δ | Hybrid total tok | Grep total tok | Token reduction |
|---|---:|---:|---:|---:|---:|---:|
| dev | 0.775 | 0.792 | -0.017 | 9.9k | 43.4k | 77.1% |
| holdout | 0.723 | 0.699 | +0.023 | 2.0k | 2.0k | -2.6% |
| stress | 0.817 | 0.819 | -0.002 | 3.1k | 2.3k | -35.2% |

## 8. Hybrid vs rtk-err-cat (v2)

### Table 3 — Hybrid vs rtk-err-cat

| Split | Hybrid sv1.1 | RTK sv1.1 | Δ | Hybrid total tok | RTK total tok |
|---|---:|---:|---:|---:|---:|
| dev | 0.775 | 0.696 | +0.079 | 9.9k | 10.3k |
| holdout | 0.723 | 0.436 | +0.287 | 2.0k | 765 |
| stress | 0.817 | 0.472 | +0.345 | 3.1k | 2.8k |

## 9. v1 debugger vs v2 debugger comparison

### Table 4 — Replication (macro across 3 splits)

| Method | v1 macro sv1.1 | v2 macro sv1.1 | Δ | v1 rank | v2 rank | Rank change |
|---|---:|---:|---:|---:|---:|---:|
| `raw` | 0.454 | 0.511 | +0.057 | 7 | 7 | — |
| `tail` | 0.661 | 0.689 | +0.027 | 3 | 3 | — |
| `grep` | 0.675 | 0.770 | +0.095 | 2 | 2 | — |
| `rtk-read` | 0.458 | 0.522 | +0.065 | 6 | 5 | +1 |
| `rtk-log` | 0.280 | 0.309 | +0.029 | 8 | 8 | — |
| `rtk-err-cat` | 0.494 | 0.534 | +0.040 | 4 | 4 | — |
| `llm-summary-v1-mock` | 0.494 | 0.518 | +0.024 | 5 | 6 | -1 |
| `hybrid-grep-4k-rtk-err-cat-v1` | 0.715 | 0.771 | +0.056 | 1 | 1 | — |

## 10. Model-stability analysis

### Table 5 — Rank stability

| Method | v1 rank | v2 rank | Stable? | Notes |
|---|---:|---:|:---:|---|
| `raw` | 7 | 7 | ✅ | exact rank match |
| `tail` | 3 | 3 | ✅ | exact rank match |
| `grep` | 2 | 2 | ✅ | exact rank match |
| `rtk-read` | 6 | 5 | ✅ | adjacent ranks (Δ=1) |
| `rtk-log` | 8 | 8 | ✅ | exact rank match |
| `rtk-err-cat` | 4 | 4 | ✅ | exact rank match |
| `llm-summary-v1-mock` | 5 | 6 | ✅ | adjacent ranks (Δ=1) |
| `hybrid-grep-4k-rtk-err-cat-v1` | 1 | 1 | ✅ | exact rank match |

## 11. Cost / token table

Per-method macro tokens for v2 (Sonnet) vs v1 (Haiku). Note: per-token cost differs ~5-10× between Sonnet and Haiku at the time of this run.

| Method | Split | v1 ctx tok | v2 ctx tok | v1 diag tok | v2 diag tok | v1 total | v2 total |
|---|---|---:|---:|---:|---:|---:|---:|
| `raw` | dev | 130.2k | 130.2k | 115 | 241 | 130.3k | 130.4k |
| `raw` | holdout | 11.1k | 11.1k | 462 | 536 | 11.5k | 11.6k |
| `raw` | stress | 91.2k | 91.2k | 290 | 336 | 91.5k | 91.5k |
| `tail` | dev | 5.6k | 5.6k | 505 | 559 | 6.1k | 6.2k |
| `tail` | holdout | 4.6k | 4.6k | 446 | 514 | 5.0k | 5.1k |
| `tail` | stress | 5.0k | 5.0k | 386 | 469 | 5.3k | 5.4k |
| `grep` | dev | 42.5k | 42.5k | 545 | 936 | 43.0k | 43.4k |
| `grep` | holdout | 1.5k | 1.5k | 396 | 460 | 1.9k | 2.0k |
| `grep` | stress | 1.9k | 1.9k | 358 | 408 | 2.2k | 2.3k |
| `rtk-read` | dev | 130.2k | 130.2k | 111 | 246 | 130.3k | 130.5k |
| `rtk-read` | holdout | 11.1k | 11.1k | 510 | 519 | 11.6k | 11.6k |
| `rtk-read` | stress | 91.2k | 91.2k | 284 | 310 | 91.5k | 91.5k |
| `rtk-log` | dev | 385 | 385 | 405 | 519 | 791 | 904 |
| `rtk-log` | holdout | 260 | 260 | 335 | 411 | 595 | 672 |
| `rtk-log` | stress | 165 | 165 | 284 | 349 | 449 | 514 |
| `rtk-err-cat` | dev | 9.4k | 9.4k | 559 | 921 | 9.9k | 10.3k |
| `rtk-err-cat` | holdout | 365 | 365 | 327 | 400 | 693 | 765 |
| `rtk-err-cat` | stress | 2.5k | 2.5k | 214 | 245 | 2.8k | 2.8k |
| `llm-summary-v1-mock` | dev | 1.5k | 1.5k | 429 | 562 | 2.0k | 2.1k |
| `llm-summary-v1-mock` | holdout | 362 | 362 | 324 | 458 | 686 | 820 |
| `llm-summary-v1-mock` | stress | 373 | 373 | 289 | 304 | 662 | 677 |
| `hybrid-grep-4k-rtk-err-cat-v1` | dev | 9.0k | 9.0k | 614 | 906 | 9.6k | 9.9k |
| `hybrid-grep-4k-rtk-err-cat-v1` | holdout | 1.5k | 1.5k | 440 | 465 | 2.0k | 2.0k |
| `hybrid-grep-4k-rtk-err-cat-v1` | stress | 2.7k | 2.7k | 335 | 371 | 3.0k | 3.1k |

## 12. Provider-error and unsupported-context analysis

| Split | Method | v1 errs | v2 errs |
|---|---|---:|---:|
| dev | `raw` | 1 | 0 |
| dev | `rtk-read` | 1 | 0 |

## 13. Confident-error and abstention analysis

| Method | Split | v1 confErr v1.1 | v2 confErr v1.1 | v1 abstain | v2 abstain |
|---|---|---:|---:|---:|---:|
| `raw` | dev | 0.0% | 0.0% | 80.0% | 60.0% |
| `raw` | holdout | 0.0% | 0.0% | 0.0% | 0.0% |
| `raw` | stress | 0.0% | 0.0% | 33.3% | 33.3% |
| `tail` | dev | 0.0% | 0.0% | 0.0% | 0.0% |
| `tail` | holdout | 0.0% | 0.0% | 0.0% | 0.0% |
| `tail` | stress | 0.0% | 0.0% | 0.0% | 0.0% |
| `grep` | dev | 0.0% | 0.0% | 0.0% | 0.0% |
| `grep` | holdout | 0.0% | 0.0% | 0.0% | 0.0% |
| `grep` | stress | 0.0% | 0.0% | 0.0% | 0.0% |
| `rtk-read` | dev | 0.0% | 0.0% | 80.0% | 60.0% |
| `rtk-read` | holdout | 0.0% | 0.0% | 0.0% | 0.0% |
| `rtk-read` | stress | 0.0% | 0.0% | 33.3% | 33.3% |
| `rtk-log` | dev | 20.0% | 40.0% | 0.0% | 0.0% |
| `rtk-log` | holdout | 0.0% | 20.0% | 0.0% | 0.0% |
| `rtk-log` | stress | 33.3% | 0.0% | 50.0% | 50.0% |
| `rtk-err-cat` | dev | 0.0% | 0.0% | 20.0% | 0.0% |
| `rtk-err-cat` | holdout | 0.0% | 0.0% | 20.0% | 0.0% |
| `rtk-err-cat` | stress | 0.0% | 0.0% | 50.0% | 50.0% |
| `llm-summary-v1-mock` | dev | 0.0% | 0.0% | 0.0% | 0.0% |
| `llm-summary-v1-mock` | holdout | 0.0% | 0.0% | 20.0% | 20.0% |
| `llm-summary-v1-mock` | stress | 0.0% | 0.0% | 33.3% | 50.0% |
| `hybrid-grep-4k-rtk-err-cat-v1` | dev | 0.0% | 0.0% | 0.0% | 0.0% |
| `hybrid-grep-4k-rtk-err-cat-v1` | holdout | 0.0% | 0.0% | 0.0% | 0.0% |
| `hybrid-grep-4k-rtk-err-cat-v1` | stress | 0.0% | 0.0% | 0.0% | 0.0% |

## 14. Per-case disagreement analysis

### Table 6 — Top-10 v1 vs v2 disagreements (|Δsv1.1| highest)

| Case | Split | Method | v1 sv1.1 | v2 sv1.1 | Δ | Likely reason |
|---|---|---|---:|---:|---:|---|
| `cargo-tokio-001` | dev | `raw` | 0.000 | 0.790 | +0.790 | v2 fixed wrong category |
| `cargo-tokio-001` | dev | `rtk-read` | 0.000 | 0.740 | +0.740 | v2 fixed wrong category |
| `pytest-sklearn-stress-001` | stress | `rtk-log` | 0.000 | 0.410 | +0.410 | v2 fixed wrong category |
| `lint-react-001` | dev | `rtk-log` | 0.358 | 0.000 | -0.358 | v2 introduced forbidden claim |
| `cargo-tokio-001` | dev | `grep` | 0.475 | 0.830 | +0.355 | v2 fixed wrong category |
| `docbuild-hf-stress-001` | stress | `rtk-read` | 0.457 | 0.800 | +0.343 | v2 fixed wrong category |
| `pytest-pandas-001` | dev | `grep` | 0.590 | 0.930 | +0.340 | v2 fixed wrong category |
| `pytest-pandas-001` | dev | `llm-summary-v1-mock` | 0.367 | 0.680 | +0.313 | v2 fixed wrong category |
| `pytest-pandas-001` | dev | `rtk-log` | 0.264 | 0.567 | +0.302 | v2 fixed wrong category |
| `docbuild-hf-stress-001` | stress | `tail` | 0.775 | 0.510 | -0.265 | larger model overfocused / lost signal |

## 15. Interpretation guardrails

- **Two debugger models, one prompt family.** Conclusions are scoped to Haiku 4.5 + Sonnet 4.6 with `prompts/debugger_v1.md`. Do not generalize to Opus, GPT-class models, or different prompts.
- **16 cases.** Directional, not statistical.
- **Calibration source.** sv1.1 was calibrated in E2/E2b against expert-model labels collected on `real-debugger-v1`. Apply with care to v2.
- **Costs are informational.** Sonnet pricing is roughly 5–10× Haiku at the time of this run; the cost table reflects context+diagnosis tokens only, not external infrastructure.
- **Provider-error carryover.** Cases that hit `unsupported_context_too_large` under v1 may behave differently under v2 because Sonnet has the same 200k-token window but slightly different chunk boundaries.

## 16. Decision: freeze confirmed or needs more replication

**Decision: `CONFIRMED_MODEL_STABLE`**

| Criterion | Hybrid (v2) | Grep (v2) | Pass? |
|---|---:|---:|:---:|
| Macro sv1.1 ≥ grep | 0.771 | 0.770 | ✅ |
| Macro total tokens ≤ grep | 5.0k | 15.9k | ✅ |
| Macro confErr v1.1 ≤ grep | 0.0% | 0.0% | ✅ |
| Hybrid rank near-stable across debuggers (Δ ≤ 1) | v1 rank 1 → v2 rank 1 | — | ✅ |

All four criteria pass. **`cilogbench-v1.3` is model-stable across the two tested debuggers** (Haiku 4.5 and Sonnet 4.6). The hybrid baseline retains its E5 advantage. Recommend moving forward with a public technical report / README narrative for v1.3, then proceeding to E7 (MCP / search-agent baseline) per the post-E6 plan.

