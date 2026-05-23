# E8 — Hybrid-First Search-Fallback Routing Analysis

- **Experiment ID:** `E8-hybrid-first-search-fallback-analysis-v1`
- **Protocol:** `cilogbench-v1.3` (lock SHA `4ef0cf09d8303815…`)
- **Hybrid diagnoser:** `real-debugger-v2` over `hybrid-grep-4k-rtk-err-cat-v1`
- **Search agent:** `mcp-search-agent-v1-sonnet` (E7)
- **Mode:** analysis-only — **no model calls**.
- **Splits:** dev, holdout, stress (16 cases total)

## 1. Executive summary

Across 16 v1.3 cases, the strongest deployable fallback policy was `hybrid-if-evidence-else-search` with macro sv1.1 = **0.776** (Δ vs hybrid-default = +0.002). It invoked search-agent on **12.5%** of cases and spent **14.6k** macro total tokens (vs hybrid's 4.9k). The oracle upper bound is 0.801, so deployable headroom over hybrid is **+0.027 sv1.1**.

**Decision:** `STOP_SEARCH_TRACK` (see §14).

## 2. E7 recap

E7 (`reports/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md`) closed at `KEEP_AS_EXPLORATORY`. Search-agent macro sv1.1 = 0.724 vs hybrid 0.774. Search-agent spent 60.7k average total tokens per case — about 12.4× hybrid's cost. Per-split, search-agent beat hybrid on holdout (+0.027) and stress (+0.028) but lost on dev (−0.223). E8 asks whether a deployable gate can recover those holdout/stress wins without paying search cost on every case.

## 3. Why search fallback instead of search default

If search-agent had outperformed hybrid as a default, E7 would have promoted it to a v1.4 baseline directly. It did not. The remaining question is whether some pre-evaluation feature of the hybrid output reliably *predicts* which cases benefit from a search-agent retry. If yes, that gate becomes a deployable two-stage policy. If no, the search-agent track does not generalize and should be paused.

## 4. Inputs and protocol

| Input | Path |
|---|---|
| Protocol lock | `protocols/cilogbench-v1.3.lock.json` |
| Policy config | `configs/routing/hybrid_search_fallback_policy_v1.json` |
| Hybrid eval (E6) | `results/{dev,holdout,stress}/eval_diagnosis_real-debugger-v2.json` |
| Search-agent eval (E7) | `results/{dev,holdout,stress}/eval_diagnosis_mcp-search-agent-v1-sonnet.json` |
| Hybrid context route records | `results/{dev,holdout,stress}/hybrid-grep-4k-rtk-err-cat-v1.routes.jsonl` |
| Search-agent traces | `results/{dev,holdout,stress}/search_agents/mcp-search-agent-v1-sonnet/traces/*.json` |
| E8 raw output | `results/e8_hybrid_first_search_fallback_cilogbench_v1_3.json` |

## 5. Anti-leakage policy constraints

Each deployable policy in `configs/routing/hybrid_search_fallback_policy_v1.json` may use only:

- `hybrid_confidence`
- `hybrid_category`
- `hybrid_root_cause_text`
- `hybrid_evidence_count`
- `hybrid_evidence_in_context_count`
- `hybrid_relevant_files_count`
- `hybrid_relevant_tests_count`
- `hybrid_selected_method`
- `hybrid_context_token_estimate`
- `hybrid_provider_error`
- `raw_log_line_count`
- `raw_log_byte_size`
- `framework`
- `repo`
- `workflow_name`
- `job_name`

It must **not** consult any of:

- `ground_truth.*`
- `failure_category`
- `required_signals`
- `evidence_spans`
- `diagnosis_score_v1`
- `diagnosis_score_v1_1`
- `category_match_score_v1_1`
- `critical_signal_mention_recall`
- `must_mention_coverage`
- `valid_evidence_quote_rate`
- `forbidden_claim_violations`
- `review/batches/*`

The `oracle-by-case` policy is explicitly labeled **non-deployable** in the config and uses `diagnosis_score_v1_1` to choose; it appears in this report as an **upper bound only**. Every other policy's per-case decision is a function of the deployable feature dict only.

## 6. Candidate routing policies

| # | Policy | Deployable? | Rule |
|---|---|:---:|---|
| 0 | `hybrid-default` | ✅ | `always_choose_hybrid` |
| 1 | `search-default` | ✅ | `always_choose_search_agent` |
| 2 | `hybrid-if-confident-else-search@0.50` | ✅ | `hybrid_if_confidence_geq` |
| 3 | `hybrid-if-confident-else-search@0.60` | ✅ | `hybrid_if_confidence_geq` |
| 4 | `hybrid-if-confident-else-search@0.70` | ✅ | `hybrid_if_confidence_geq` |
| 5 | `hybrid-if-confident-else-search@0.80` | ✅ | `hybrid_if_confidence_geq` |
| 6 | `hybrid-if-known-else-search` | ✅ | `hybrid_if_known` |
| 7 | `hybrid-if-evidence-else-search` | ✅ | `hybrid_if_evidence_in_context` |
| 8 | `rtk-selected-hybrid-then-search` | ✅ | `hybrid_if_grep_selected` |
| 9 | `large-log-avoid-search` | ✅ | `large_log_then_hybrid_else_confidence_gate` |
| 10 | `oracle-by-case` | ❌ ORACLE | `argmax_sv1_1` |

## 7. Policy results

### Table 1 — Policy summary

| Policy | Deployable? | Macro sv1.1 | Δ vs hybrid | Total tokens | Δ cost vs hybrid | Search invocation | Provider err | confErr v1.1 |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| `hybrid-default` | ✅ | 0.774 | +0.000 | 4.9k | +0 | 0.0% | 0.0% | 0.0% |
| `search-default` | ✅ | 0.724 | -0.050 | 60.7k | +55812 | 100.0% | 0.0% | 0.0% |
| `hybrid-if-confident-else-search@0.50` | ✅ | 0.774 | +0.000 | 4.9k | +0 | 0.0% | 0.0% | 0.0% |
| `hybrid-if-confident-else-search@0.60` | ✅ | 0.774 | +0.000 | 4.9k | +0 | 0.0% | 0.0% | 0.0% |
| `hybrid-if-confident-else-search@0.70` | ✅ | 0.738 | -0.036 | 12.6k | +7718 | 6.2% | 0.0% | 0.0% |
| `hybrid-if-confident-else-search@0.80` | ✅ | 0.738 | -0.036 | 12.6k | +7718 | 6.2% | 0.0% | 0.0% |
| `hybrid-if-known-else-search` | ✅ | 0.774 | +0.000 | 4.9k | +0 | 0.0% | 0.0% | 0.0% |
| `hybrid-if-evidence-else-search` | ✅ | 0.776 | +0.002 | 14.6k | +9740 | 12.5% | 0.0% | 0.0% |
| `rtk-selected-hybrid-then-search` | ✅ | 0.701 | -0.073 | 35.3k | +30451 | 37.5% | 0.0% | 0.0% |
| `large-log-avoid-search` | ✅ | 0.774 | +0.000 | 4.9k | +0 | 0.0% | 0.0% | 0.0% |
| `oracle-by-case` | ❌ ORACLE | 0.801 | +0.027 | 28.3k | +23399 | 50.0% | 0.0% | 0.0% |

### Table 2 — Per-split policy result

| Policy | Split | sv1.1 | Hybrid sv1.1 | Search sv1.1 | Total tokens | Search invocations |
|---|---|---:|---:|---:|---:|---:|
| `hybrid-default` | dev | 0.775 | 0.775 | 0.552 | 9.9k | 0 |
| `hybrid-default` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `hybrid-default` | stress | 0.817 | 0.817 | 0.845 | 3.1k | 0 |
| `search-default` | dev | 0.552 | 0.775 | 0.552 | 86.6k | 5 |
| `search-default` | holdout | 0.750 | 0.723 | 0.750 | 42.5k | 5 |
| `search-default` | stress | 0.845 | 0.817 | 0.845 | 54.2k | 6 |
| `hybrid-if-confident-else-search@0.50` | dev | 0.775 | 0.775 | 0.552 | 9.9k | 0 |
| `hybrid-if-confident-else-search@0.50` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `hybrid-if-confident-else-search@0.50` | stress | 0.817 | 0.817 | 0.845 | 3.1k | 0 |
| `hybrid-if-confident-else-search@0.60` | dev | 0.775 | 0.775 | 0.552 | 9.9k | 0 |
| `hybrid-if-confident-else-search@0.60` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `hybrid-if-confident-else-search@0.60` | stress | 0.817 | 0.817 | 0.845 | 3.1k | 0 |
| `hybrid-if-confident-else-search@0.70` | dev | 0.660 | 0.775 | 0.552 | 34.6k | 1 |
| `hybrid-if-confident-else-search@0.70` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `hybrid-if-confident-else-search@0.70` | stress | 0.817 | 0.817 | 0.845 | 3.1k | 0 |
| `hybrid-if-confident-else-search@0.80` | dev | 0.660 | 0.775 | 0.552 | 34.6k | 1 |
| `hybrid-if-confident-else-search@0.80` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `hybrid-if-confident-else-search@0.80` | stress | 0.817 | 0.817 | 0.845 | 3.1k | 0 |
| `hybrid-if-known-else-search` | dev | 0.775 | 0.775 | 0.552 | 9.9k | 0 |
| `hybrid-if-known-else-search` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `hybrid-if-known-else-search` | stress | 0.817 | 0.817 | 0.845 | 3.1k | 0 |
| `hybrid-if-evidence-else-search` | dev | 0.775 | 0.775 | 0.552 | 9.9k | 0 |
| `hybrid-if-evidence-else-search` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `hybrid-if-evidence-else-search` | stress | 0.821 | 0.817 | 0.845 | 29.0k | 2 |
| `rtk-selected-hybrid-then-search` | dev | 0.535 | 0.775 | 0.552 | 76.2k | 4 |
| `rtk-selected-hybrid-then-search` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `rtk-selected-hybrid-then-search` | stress | 0.821 | 0.817 | 0.845 | 29.0k | 2 |
| `large-log-avoid-search` | dev | 0.775 | 0.775 | 0.552 | 9.9k | 0 |
| `large-log-avoid-search` | holdout | 0.723 | 0.723 | 0.750 | 2.0k | 0 |
| `large-log-avoid-search` | stress | 0.817 | 0.817 | 0.845 | 3.1k | 0 |
| `oracle-by-case` | dev | 0.791 | 0.775 | 0.552 | 20.4k | 1 |
| `oracle-by-case` | holdout | 0.760 | 0.723 | 0.750 | 22.8k | 3 |
| `oracle-by-case` | stress | 0.845 | 0.817 | 0.845 | 39.5k | 4 |

## 8. Hybrid vs search case-level analysis

### Table 3 — Case-level routing (best deployable policy)

Best deployable policy by macro sv1.1: **`hybrid-if-evidence-else-search`**

| Case | Split | Chosen | Reason | Hybrid sv1.1 | Search sv1.1 | Chosen sv1.1 | Hybrid conf | Ev. count | Tool calls |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| `cargo-tokio-001` | dev | `hybrid` | hybrid_confident_with_evidence_in_context | 0.750 | 0.562 | **0.750** | 0.820 | 7 | 2 |
| `jest-nextjs-001` | dev | `hybrid` | hybrid_confident_with_evidence_in_context | 0.775 | 0.200 | **0.775** | 0.620 | 5 | 4 |
| `lint-react-001` | dev | `hybrid` | hybrid_confident_with_evidence_in_context | 0.675 | 0.758 | **0.675** | 0.820 | 3 | 2 |
| `mypy-pandas-001` | dev | `hybrid` | hybrid_confident_with_evidence_in_context | 0.773 | 0.577 | **0.773** | 0.920 | 6 | 3 |
| `pytest-pandas-001` | dev | `hybrid` | hybrid_confident_with_evidence_in_context | 0.900 | 0.663 | **0.900** | 0.920 | 5 | 2 |
| `actions-terraform-001` | holdout | `hybrid` | hybrid_confident_with_evidence_in_context | 0.475 | 0.550 | **0.475** | 0.950 | 2 | 1 |
| `dependabot-cargo-001` | holdout | `hybrid` | hybrid_confident_with_evidence_in_context | 0.390 | 0.463 | **0.390** | 0.920 | 5 | 1 |
| `docs-transformers-001` | holdout | `hybrid` | hybrid_confident_with_evidence_in_context | 0.900 | 0.867 | **0.900** | 0.970 | 5 | 1 |
| `pushpr-nextjs-001` | holdout | `hybrid` | hybrid_confident_with_evidence_in_context | 0.900 | 0.883 | **0.900** | 0.950 | 3 | 2 |
| `tsc-typescript-001` | holdout | `hybrid` | hybrid_confident_with_evidence_in_context | 0.948 | 0.988 | **0.948** | 0.920 | 4 | 1 |
| `cleanup-k8s-stress-001` | stress | `hybrid` | hybrid_confident_with_evidence_in_context | 0.725 | 0.800 | **0.725** | 0.920 | 3 | 1 |
| `cleanup-tsc-stress-001` | stress | `hybrid` | hybrid_confident_with_evidence_in_context | 0.800 | 0.800 | **0.800** | 0.920 | 3 | 1 |
| `docbuild-hf-stress-001` | stress | `hybrid` | hybrid_confident_with_evidence_in_context | 0.775 | 0.800 | **0.775** | 0.820 | 3 | 1 |
| `prettier-react-stress-001` | stress | `hybrid` | hybrid_confident_with_evidence_in_context | 0.700 | 0.742 | **0.700** | 0.820 | 4 | 2 |
| `pytest-sklearn-stress-001` | stress | `search_agent` | hybrid_evidence_missing_or_low_confidence | 0.950 | 0.975 | **0.975** | 0.920 | 4 | 4 |
| `pytest-sklearn-stress-002` | stress | `search_agent` | hybrid_evidence_missing_or_low_confidence | 0.950 | 0.950 | **0.950** | 0.880 | 3 | 2 |

## 9. Cost and search-invocation analysis

| Policy | Macro total tokens | Δ cost vs hybrid | Search invocation | When invoked, mean tool calls | When invoked, mean obs tokens |
|---|---:|---:|---:|---:|---:|
| `hybrid-default` | 4.9k | +0 | 0.0% | — | n/a |
| `search-default` | 60.7k | +55812 | 100.0% | 1.9 | 60.7k |
| `hybrid-if-confident-else-search@0.50` | 4.9k | +0 | 0.0% | — | n/a |
| `hybrid-if-confident-else-search@0.60` | 4.9k | +0 | 0.0% | — | n/a |
| `hybrid-if-confident-else-search@0.70` | 12.6k | +7718 | 6.2% | 4.0 | 127.0k |
| `hybrid-if-confident-else-search@0.80` | 12.6k | +7718 | 6.2% | 4.0 | 127.0k |
| `hybrid-if-known-else-search` | 4.9k | +0 | 0.0% | — | n/a |
| `hybrid-if-evidence-else-search` | 14.6k | +9740 | 12.5% | 3.0 | 85.9k |
| `rtk-selected-hybrid-then-search` | 35.3k | +30451 | 37.5% | 2.8 | 92.0k |
| `large-log-avoid-search` | 4.9k | +0 | 0.0% | — | n/a |
| `oracle-by-case` | 28.3k | +23399 | 50.0% | 1.6 | 48.7k |

## 10. Large-log failure analysis

Per-case search-vs-hybrid gap, sorted by raw-log size:

| Case | Split | Raw lines | Hybrid sv1.1 | Search sv1.1 | Δ (search − hybrid) |
|---|---|---:|---:|---:|---:|
| `jest-nextjs-001` | dev | 10992 | 0.775 | 0.200 | -0.575 |
| `pytest-sklearn-stress-001` | stress | 5703 | 0.950 | 0.975 | +0.025 |
| `pytest-sklearn-stress-002` | stress | 5656 | 0.950 | 0.950 | +0.000 |
| `mypy-pandas-001` | dev | 4797 | 0.773 | 0.577 | -0.197 |
| `pytest-pandas-001` | dev | 3788 | 0.900 | 0.663 | -0.237 |
| `cargo-tokio-001` | dev | 3154 | 0.750 | 0.562 | -0.188 |
| `pushpr-nextjs-001` | holdout | 1031 | 0.900 | 0.883 | -0.017 |
| `docs-transformers-001` | holdout | 846 | 0.900 | 0.867 | -0.033 |
| `tsc-typescript-001` | holdout | 358 | 0.948 | 0.988 | +0.040 |
| `actions-terraform-001` | holdout | 334 | 0.475 | 0.550 | +0.075 |
| `lint-react-001` | dev | 292 | 0.675 | 0.758 | +0.083 |
| `dependabot-cargo-001` | holdout | 281 | 0.390 | 0.463 | +0.073 |
| `prettier-react-stress-001` | stress | 228 | 0.700 | 0.742 | +0.042 |
| `cleanup-tsc-stress-001` | stress | 83 | 0.800 | 0.800 | +0.000 |
| `cleanup-k8s-stress-001` | stress | 83 | 0.725 | 0.800 | +0.075 |
| `docbuild-hf-stress-001` | stress | 40 | 0.775 | 0.800 | +0.025 |

## 11. Deployable policy recommendation

The strongest deployable policy by macro sv1.1 is **`hybrid-if-evidence-else-search`** at 0.776 (Δ vs hybrid +0.002).

It invokes search-agent on **12.5%** of cases and costs **14.6k** per-case macro total tokens, a 2.99× multiple of hybrid-default's cost.

## 12. Oracle upper bound

### Table 4 — Oracle gap

| Policy | Macro sv1.1 | Oracle sv1.1 | Gap to oracle | Search invocation |
|---|---:|---:|---:|---:|
| `hybrid-default` | 0.774 | 0.801 | +0.027 | 0.0% |
| `search-default` | 0.724 | 0.801 | +0.078 | 100.0% |
| `hybrid-if-confident-else-search@0.50` | 0.774 | 0.801 | +0.027 | 0.0% |
| `hybrid-if-confident-else-search@0.60` | 0.774 | 0.801 | +0.027 | 0.0% |
| `hybrid-if-confident-else-search@0.70` | 0.738 | 0.801 | +0.063 | 6.2% |
| `hybrid-if-confident-else-search@0.80` | 0.738 | 0.801 | +0.063 | 6.2% |
| `hybrid-if-known-else-search` | 0.774 | 0.801 | +0.027 | 0.0% |
| `hybrid-if-evidence-else-search` | 0.776 | 0.801 | +0.026 | 12.5% |
| `rtk-selected-hybrid-then-search` | 0.701 | 0.801 | +0.101 | 37.5% |
| `large-log-avoid-search` | 0.774 | 0.801 | +0.027 | 0.0% |

### Table 5 — Failure-mode summary (best deployable policy)

| Failure mode | Cases | Example | Policy impacted |
|---|---:|---|---|
| `search_high_cost_low_gain` | 2 | `pytest-sklearn-stress-001` | `hybrid-if-evidence-else-search` |
| `hybrid_low_confidence_but_correct` | 1 | `jest-nextjs-001` | `hybrid-if-evidence-else-search` |
| `hybrid_confident_but_wrong` | 1 | `dependabot-cargo-001` | `hybrid-if-evidence-else-search` |

## 13. Interpretation guardrails

- **Offline routing analysis on existing E6/E7 outputs.** No new model calls; results scoped to the artifacts already generated.
- **One search-agent prompt, one search-agent model, one tool budget.** Conclusions about search-agent cannot generalize to other agent designs.
- **16 cases.** Directional, not statistical. Margins below ~0.05 sv1.1 are noise-level.
- **Automatic scoring proxy.** sv1.1 was calibrated against expert-model labels (E2b), not human review.
- **Search traces not human-reviewed.** A bad-looking large-log search trace is not the same as a confirmed agent failure.
- **Oracle is non-deployable** by construction: it consults `diagnosis_score_v1_1` per case.

## 14. Decision: implement E9 or stop search track

**Decision: `STOP_SEARCH_TRACK`**

Rationale:
- hybrid-default: sv1.1=0.774, total_tokens=4.9k
- best deployable: `hybrid-if-evidence-else-search` sv1.1=0.776 (Δ vs hybrid +0.002), total_tokens=14.6k (Δ vs hybrid +9740), search_invocation_rate=12.5%
- oracle upper bound: sv1.1=0.801 (headroom over hybrid +0.027)

**Stop search-agent track for now.** No deployable gate beat hybrid by a useful margin within an acceptable cost envelope. Re-prioritize human-verified review of E6 diagnoses and larger-corpus replication. Search-agent can be revisited if a different failure profile (e.g. multi-step CI logs or large agent-tool ecosystems) shows up in future cases.

