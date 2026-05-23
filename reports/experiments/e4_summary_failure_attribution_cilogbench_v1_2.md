# E4 — Summary Failure Attribution & Budgeted Routing

- **Experiment ID:** `E4-summary-failure-attribution-v1`
- **Protocol:** `cilogbench-v1.2` (lock SHA `cc4fdbe62d7793a3…`)
- **Summary method:** `llm-summary-v1-haiku` (vs comparison `grep`)
- **Diagnoser:** `real-debugger-v1` (held fixed)
- **Splits:** dev, holdout, stress (16 cases)
- **Mode:** analysis-only — **no new model runs**.

## 1. Executive summary

Across 16 cases, real LLM summary produced a **method-success** diagnosis on 8/16 cases. The remaining failures split between summary-side (2/16), debugger-side (2/16), provider errors (2/16), and evaluator-undercount / mixed cases (2/16).

**Recommended next experiment: Option `B`.** See section 12 for the matrix.

## 2. E3 recap

From `reports/e3_real_llm_summary_cilogbench_v1_2_haiku.md`: `llm-summary-v1-haiku` was the most stable method across splits (max-gap 0.121) but lost to `grep` on macro sv1.1 (0.490 vs 0.680) and incurred ~6× the total-pipeline tokens after accounting for summary-processing input/output. Final-context size was the smallest of any method (439 tokens average), making it the most useful method only under strict context budgets.

## 3. Inputs and protocol

| Input | Path |
|---|---|
| Protocol lock | `protocols/cilogbench-v1.2.lock.json` |
| Failure analysis | `results/e4_summary_failure_analysis.json` |
| Budget frontier  | `results/e4_budget_frontier.json` |
| E1 diagnosis evals | `results/{dev,holdout,stress}/eval_diagnosis_real-debugger-v1.json` |
| E3 summary outputs | `results/{dev,holdout,stress}/llm-summary-v1-haiku.jsonl` |
| E3 signal recall | `results/{dev,holdout,stress}/eval_llm-summary-v1-haiku.json` |
| Per-case ground truth | `cases/<split>/<case_id>/ground_truth.json` |

## 4. Summary failure attribution

### Table 1 — Failure modes

| Failure Mode | Cases | Splits |
|---|---:|---|
| `omitted_critical_signal` | 16 | dev, holdout, stress |
| `debugger_ignored_present_evidence` | 13 | dev, holdout, stress |
| `omitted_primary_error` | 12 | dev, holdout, stress |
| `omitted_command_or_step` | 9 | dev, holdout, stress |
| `omitted_test_name` | 4 | dev, stress |
| `too_generic` | 4 | dev, holdout, stress |
| `summary_provider_error` | 2 | stress |

### Table 2 — Per-case attribution (sv1.1 summary vs comparison)

| Case | Split | Sum sv1.1 | Comp sv1.1 | Δ | Sum SigRecall | Sum CritRecall | Top attribution | Failure modes |
|---|---|---:|---:|---:|---:|---:|---|---|
| `cargo-tokio-001` | dev | 0.500 | 0.475 | 0.025 | 57.1% | 66.7% | `mixed` | `omitted_critical_signal`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `jest-nextjs-001` | dev | 0.440 | 0.625 | -0.185 | 50.0% | 50.0% | `summary_failure` | `omitted_critical_signal`, `omitted_test_name`, `omitted_primary_error`, `debugger_ignored_present_evidence`, `too_generic` |
| `lint-react-001` | dev | 0.675 | 0.608 | 0.067 | 66.7% | 66.7% | `method_success` | `omitted_critical_signal`, `omitted_command_or_step`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `mypy-pandas-001` | dev | 0.680 | 0.720 | -0.040 | 50.0% | 60.0% | `method_success` | `omitted_critical_signal`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `pytest-pandas-001` | dev | 0.320 | 0.590 | -0.270 | 66.7% | 80.0% | `debugger_failure` | `omitted_critical_signal`, `omitted_test_name`, `omitted_command_or_step`, `debugger_ignored_present_evidence` |
| `actions-terraform-001` | holdout | 0.175 | 0.675 | -0.500 | 0.0% | 0.0% | `summary_failure` | `omitted_critical_signal`, `omitted_command_or_step`, `omitted_primary_error`, `too_generic` |
| `dependabot-cargo-001` | holdout | 0.225 | 0.315 | -0.090 | 50.0% | 50.0% | `evaluator_possible_undercount` | `omitted_critical_signal`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `docs-transformers-001` | holdout | 0.710 | 0.693 | 0.017 | 66.7% | 80.0% | `method_success` | `omitted_critical_signal`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `pushpr-nextjs-001` | holdout | 0.823 | 0.800 | 0.023 | 71.4% | 80.0% | `method_success` | `omitted_critical_signal`, `omitted_command_or_step`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `tsc-typescript-001` | holdout | 0.770 | 0.885 | -0.115 | 50.0% | 75.0% | `method_success` | `omitted_critical_signal`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `cleanup-k8s-stress-001` | stress | 0.685 | 0.650 | 0.035 | 60.0% | 75.0% | `method_success` | `omitted_critical_signal`, `omitted_command_or_step`, `debugger_ignored_present_evidence` |
| `cleanup-tsc-stress-001` | stress | 0.700 | 0.725 | -0.025 | 60.0% | 75.0% | `method_success` | `omitted_critical_signal`, `omitted_command_or_step`, `debugger_ignored_present_evidence` |
| `docbuild-hf-stress-001` | stress | 0.333 | 0.775 | -0.442 | 60.0% | 60.0% | `debugger_failure` | `omitted_critical_signal`, `omitted_command_or_step`, `debugger_ignored_present_evidence` |
| `prettier-react-stress-001` | stress | 0.700 | 0.667 | 0.033 | 85.7% | 75.0% | `method_success` | `omitted_critical_signal`, `omitted_primary_error`, `debugger_ignored_present_evidence` |
| `pytest-sklearn-stress-001` | stress | 0.050 | 0.850 | -0.800 | 0.0% | 0.0% | `provider_error` | `summary_provider_error`, `omitted_critical_signal`, `omitted_test_name`, `omitted_command_or_step`, `omitted_primary_error`, `too_generic` |
| `pytest-sklearn-stress-002` | stress | 0.050 | 0.828 | -0.777 | 0.0% | 0.0% | `provider_error` | `summary_provider_error`, `omitted_critical_signal`, `omitted_test_name`, `omitted_command_or_step`, `omitted_primary_error`, `too_generic` |

## 5. Missing evidence analysis

Per the E4 plan, every required signal in each case was classified into one of five buckets via literal substring match against the summary text and the diagnosis blob. Paraphrase detection is not implemented; signals matched only in the diagnosis are reported as `unknown_paraphrase_possible` (debugger may have inferred or paraphrased). `not_in_raw_or_annotation_issue` rows indicate the ground-truth signal value did not literal-match the raw log either — either an annotation issue or a different surface form.

| Case | Split | present | present-but-not-used | omitted | paraphrase? | annot-issue | total |
|---|---|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | dev | 0 | 2 | 2 | 0 | 3 | 7 |
| `jest-nextjs-001` | dev | 0 | 2 | 3 | 0 | 1 | 6 |
| `lint-react-001` | dev | 0 | 3 | 2 | 0 | 1 | 6 |
| `mypy-pandas-001` | dev | 0 | 3 | 2 | 0 | 1 | 6 |
| `pytest-pandas-001` | dev | 0 | 3 | 2 | 0 | 1 | 6 |
| `actions-terraform-001` | holdout | 0 | 0 | 5 | 0 | 0 | 5 |
| `dependabot-cargo-001` | holdout | 0 | 3 | 3 | 0 | 0 | 6 |
| `docs-transformers-001` | holdout | 0 | 3 | 2 | 0 | 1 | 6 |
| `pushpr-nextjs-001` | holdout | 0 | 4 | 2 | 0 | 1 | 7 |
| `tsc-typescript-001` | holdout | 0 | 2 | 3 | 0 | 1 | 6 |
| `cleanup-k8s-stress-001` | stress | 0 | 3 | 2 | 0 | 0 | 5 |
| `cleanup-tsc-stress-001` | stress | 0 | 3 | 2 | 0 | 0 | 5 |
| `docbuild-hf-stress-001` | stress | 0 | 4 | 1 | 0 | 0 | 5 |
| `prettier-react-stress-001` | stress | 0 | 4 | 1 | 0 | 2 | 7 |
| `pytest-sklearn-stress-001` | stress | 0 | 0 | 5 | 0 | 1 | 6 |
| `pytest-sklearn-stress-002` | stress | 0 | 0 | 5 | 0 | 1 | 6 |

## 6. Provider-error analysis

| Case | Split | Stage | sv1.1 | Δ vs comparison |
|---|---|---|---:|---:|
| `pytest-sklearn-stress-001` | stress | summary | 0.050 | -0.800 |
| `pytest-sklearn-stress-002` | stress | summary | 0.050 | -0.777 |

Total summary provider errors: **2**. Both sit in the `pytest-sklearn-stress-*` stress cases where the reduce stage exited 1 with empty stderr; direct shim calls succeed, suggesting a transient subprocess-side condition rather than a content issue.

## 7. Debugger-vs-summary failure split

| Attribution bucket | Cases | Notes |
|---|---:|---|
| `method_success` | 8 | sv1.1 ≥ 0.6 — counted as a working pipeline regardless of summary quality |
| `summary_failure` | 2 | summary dropped most critical signals before debugger ran |
| `debugger_failure` | 2 | summary contained critical signals but debugger ignored them |
| `evaluator_possible_undercount` | 1 | summary and comparison both score low and within 10pp; auto rubric likely undercounts both |
| `provider_error` | 2 | summary reduce stage failed |
| `annotation_issue` | 0 | half or more required signals don't literal-match the raw log |
| `mixed` | 1 | both sides shed signal |

## 8. Budget frontier

### Per-method

| Method | sv1.1 | final ctx tok | sum proc tok | total pipeline | provider err | abstain | confErr v1.1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `grep` | 0.680 | 14.4k | 0 | 14.9k | 0.0% | 0.0% | 0.0% |
| `tail` | 0.666 | 5.0k | 0 | 5.5k | 0.0% | 0.0% | 0.0% |
| `llm-summary-v1-mock` | 0.495 | 733 | 0 | 1.1k | 0.0% | 18.8% | 0.0% |
| `llm-summary-v1-haiku` | 0.490 | 439 | 82.9k | 83.7k | 0.0% | 31.2% | 0.0% |
| `rtk-err-cat` | 0.490 | 4.0k | 0 | 4.4k | 0.0% | 31.2% | 0.0% |
| `rtk-read` | 0.458 | 78.3k | 0 | 78.7k | 6.2% | 37.5% | 0.0% |
| `raw` | 0.457 | 78.3k | 0 | 78.6k | 6.2% | 37.5% | 0.0% |
| `rtk-log` | 0.273 | 263 | 0 | 602 | 0.0% | 18.8% | 18.8% |

### Table 3 — Per-budget best deployable method

Per the E4 plan: a method is *deployable* at a budget when at least 60% of cases have `final_context_tokens ≤ budget`. Best is the deployable method with the highest macro sv1.1.

| Budget | Best deployable | Macro sv1.1 | Coverage | Total pipeline | Provider errors | Notes |
|---|---|---:|---:|---:|---:|---|
| 1.0k | `llm-summary-v1-haiku` | 0.501 | 93.8% | 79.3k | 0.0% | 3 methods fit |
| 2.0k | `llm-summary-v1-mock` | 0.500 | 87.5% | 851 | 0.0% | 3 methods fit |
| 4.0k | `grep` | 0.679 | 62.5% | 1.2k | 0.0% | 5 methods fit |
| 8.0k | `grep` | 0.706 | 75.0% | 1.9k | 0.0% | 6 methods fit |
| 16.0k | `grep` | 0.706 | 75.0% | 1.9k | 0.0% | 6 methods fit |
| 32.0k | `rtk-read` | 0.714 | 62.5% | 7.4k | 0.0% | 8 methods fit |

## 9. Routing policy comparison

### Table 4 — Routing policies

Policies are evaluated offline against the existing per-method diagnoses; no new model calls. The `best-oracle-by-budget` rows are an **upper bound**, not deployable (they require knowing each case's best method ahead of time).

| Policy | Budget | sv1.1 | Final ctx | Sum proc | Total pipeline | Prov err | Abstain | confErr v1.1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `grep-default` | — | 0.680 | 14.4k | 0 | 14.9k | 0.0% | 0.0% | 0.0% |
| `tail-if-short-else-grep` | — | 0.680 | 15.0k | 0 | 15.5k | 0.0% | 0.0% | 0.0% |
| `grep-if-fits-else-summary` | 2.0k | 0.553 | 617 | 78.4k | 79.5k | 0.0% | 12.5% | 0.0% |
| `grep-if-fits-else-summary` | 4.0k | 0.552 | 744 | 77.0k | 78.1k | 0.0% | 12.5% | 0.0% |
| `grep-if-fits-else-summary` | 8.0k | 0.651 | 1.4k | 43.1k | 44.9k | 0.0% | 0.0% | 0.0% |
| `grep-if-fits-else-summary` | 16.0k | 0.651 | 1.4k | 43.1k | 44.9k | 0.0% | 0.0% | 0.0% |
| `grep-if-fits-else-rtk-err-cat` | 2.0k | 0.714 | 4.2k | 0 | 4.6k | 0.0% | 0.0% | 0.0% |
| `grep-if-fits-else-rtk-err-cat` | 4.0k | 0.723 | 4.3k | 0 | 4.7k | 0.0% | 0.0% | 0.0% |
| `grep-if-fits-else-rtk-err-cat` | 8.0k | 0.717 | 4.0k | 0 | 4.4k | 0.0% | 0.0% | 0.0% |
| `grep-if-fits-else-rtk-err-cat` | 16.0k | 0.717 | 4.0k | 0 | 4.4k | 0.0% | 0.0% | 0.0% |
| **[ORACLE]** `best-oracle-by-budget` | 2.0k | 0.685 | 634 | 27.7k | 28.7k | 0.0% | 0.0% | 0.0% |
| **[ORACLE]** `best-oracle-by-budget` | 4.0k | 0.700 | 868 | 12.0k | 13.2k | 0.0% | 0.0% | 0.0% |
| **[ORACLE]** `best-oracle-by-budget` | 8.0k | 0.747 | 2.7k | 10.0k | 13.2k | 0.0% | 0.0% | 0.0% |
| **[ORACLE]** `best-oracle-by-budget` | 16.0k | 0.779 | 3.6k | 10.0k | 14.0k | 0.0% | 0.0% | 0.0% |
| **[ORACLE]** `best-oracle-by-budget` | — | 0.784 | 6.4k | 0 | 6.9k | 0.0% | 0.0% | 0.0% |

## 10. Strict final-context budget analysis

When the final-context budget is below ~2k tokens, `llm-summary-v1-haiku` and `llm-summary-v1-mock` are the only deployable options for the larger cases (raw, rtk-read, grep all exceed the budget on dev's largest case). Above ~4k tokens, `grep` becomes deployable on most cases and dominates real summary on macro sv1.1. Above ~16k tokens, deterministic baselines fit almost every case and the real summary's only remaining edge is context size — which is irrelevant if the budget is generous.

## 11. Token-cost interpretation

Real LLM summary's compact final context is achieved at a summary-processing cost roughly equal to the raw log size in tokens (Anthropic's prompt cache makes the system prompt ~free after the first call but the full log still has to enter the model once on the map stage). For the median dev case, `llm-summary-v1-haiku` total-pipeline tokens are ~6× higher than `grep`. The real summary becomes cost-competitive only under the strict-budget regime described in section 10, *and* only if the summary processing happens on a separate, cheaper model than the downstream debugger — a scenario E3 did not test (same model on both sides).

## 12. Decision: stronger summarizer vs hybrid vs second debugger

### Table 5 — Decision matrix

| # | Option | Evidence for | Evidence against | Recommendation |
|---|---|---|---|---|
| A | Sonnet summarizer / same debugger | Real summary already beats mock summary; some failures look like missing evidence | Summary-side failures are only 2/16; even if Sonnet preserves all signals, the gap to grep is unlikely to close at 6× cost | Hold for a future round if hybrid + second-debugger don't resolve the gap |
| B | Grep-first hybrid routing (`grep-if-fits-else-rtk-err-cat`) | At budget=4k, hybrid sv1.1 = 0.723 (vs grep-default 0.680); deterministic; cheap | No summary in pipeline limits applicability under <2k budgets | Run E5: implement `hybrid-grep-fallback-v1` as a first-class baseline and re-evaluate against locked methods ✅ chosen |
| C | Second debugger model (Sonnet/Opus) | `debugger_ignored_present_evidence` co-emitted on 13/16 cases; rankings may be model-dependent | Co-emission with summary omissions makes debugger-only attribution weak; same model on both sides in E3 confounds the signal | Run E5b (after E5) to test whether a stronger debugger reorders methods |
| D | Targeted expert/human review | `evaluator_possible_undercount` and `mixed` cover 2/16 cases | E2 already provided expert-model labels; further review only matters if it includes real humans | Defer until a human-review batch is justified by a downstream decision |
| E | Stop summarizer track for now | Summary loses to grep on quality, costs ~6× more, and gains are confined to <2k budgets | Strict-budget downstream agents are a real use case; summarizer track has not been ruled out for those | Pause summarizer-only experiments; reserve for tight-budget studies |

**Decision rationale:**
- Attribution: method_success=8/16, summary_failure=2/16, debugger_failure=2/16, provider_error=2/16, evaluator_undercount=1/16.
- `grep` macro sv1.1 = 0.680 vs `llm-summary-v1-haiku` = 0.490; summary loses to grep: True.
- `grep` total pipeline = 14.9k vs summary = 83.7k; summary much more expensive: True.
- `grep-if-fits-else-rtk-err-cat` @4k sv1.1 = 0.723; `grep-default` = 0.680; RTK hybrid better: True.
- debugger_ignored_present_evidence count: 13 (most of 16). Note: this is the most common failure mode but it is co-emitted with summary omissions in many cases, so it isolates the *debugger* responsibility weakly.

## 13. Interpretation guardrails

- One summarizer model (`llm-summary-v1-haiku`), one summary prompt, one debugger model.
- 16 cases — directional signal only.
- Two summary provider errors on the same case family (`pytest-sklearn-stress-*`); decisions should not over-weight those rows.
- E2/E2b calibration was via expert-model review, not human review.
- Literal substring match underestimates `present_in_summary` for paraphrased signals.
- All cost numbers depend on the cache hit rate at the time of the run; rerunning may shift them slightly.
- Routing policies were not tuned on the cases — but were specified up front, so the comparison is fair.

## 14. Recommended next experiment

**Recommendation: Option `B`**

Build E5: a deployable hybrid routing baseline. The `grep-if-fits-else-rtk-err-cat` policy at budget=4k beats `grep-default` while spending ~⅓ the total-pipeline tokens. Implement it as a first-class context method (`hybrid-grep-fallback-v1`) so it gets the same byte-stable scoring treatment as every locked baseline.

