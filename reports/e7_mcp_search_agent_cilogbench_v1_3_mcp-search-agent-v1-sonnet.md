# E7 — MCP/Search-Agent Baseline on cilogbench-v1.3 (mcp-search-agent-v1-sonnet)

- **Experiment ID:** `E7-mcp-search-agent-v1`
- **Protocol:** `cilogbench-v1.3` (SHA `4ef0cf09d8303815…`)
- **Agent:** `mcp-search-agent-v1-sonnet` (Sonnet 4.6 via `claude -p`)
- **Mode:** end-to-end search agent (NOT a static context-provider baseline)
- **Tool budget:** max_tool_calls=8, max_total_observation_tokens=16000
- **Allowed tools:** `get_log_metadata`, `search_log`, `get_lines`, `get_tail`, `get_head`, `find_error_blocks`, `list_github_steps`
- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated; secondary = `diagnosis_score_v1`)

## 1. Executive summary

Per-split macro `diagnosis_score_v1_1`, search-agent vs. v1.3 hybrid (under Sonnet 4.6):

| Split | search-agent sv1.1 | hybrid sv1.1 (v2) | Δ |
|---|---:|---:|---:|
| dev | 0.552 | 0.775 | -0.223 |
| holdout | 0.750 | 0.723 | +0.027 |
| stress | 0.845 | 0.817 | +0.028 |

Across all 16 attempted cases, the search agent's trace recorded its tool calls and observations under a fixed budget (8 max tool calls, 16000 max observation tokens).

## 2. Why MCP/search-agent is different from static context

Static context methods (`raw` / `tail` / `grep` / `rtk-*` / `hybrid-grep-4k-rtk-err-cat-v1`) compress the raw log **once**, then a fixed debugger reads that single context. The search agent, by contrast, starts only with safe metadata (no log content), then issues a sequence of bounded tool calls over the raw log and decides what to inspect based on intermediate observations. The cost model is therefore different — `final_context_tokens` for static methods becomes `observation_tokens_estimate + agent_input_tokens_estimate + agent_output_tokens_estimate` for the agent, summed across steps.

## 3. Protocol and model setup

```text
protocol_lock         = protocols/cilogbench-v1.3.lock.json
protocol_lock_sha256  = 4ef0cf09d830381547df631664a429217dcff1f2a64b02635bbe65320a6e3bde
agent_config          = configs/search_agents/mcp-search-agent-v1-sonnet.json
agent_config_sha256   = fe3eb1c2a45c16fe8deb68126e56f4a272bea876af98fcfd7fb4a802866a72db
agent_prompt          = prompts/search_agent_v1.md
agent_prompt_sha256   = ade615ac3768fe29e504357b83bac8bef99cb4c893fe795df167c5051da19d6e
primary_score         = diagnosis_score_v1_1
secondary_score       = diagnosis_score_v1
```

## 4. Tool set and budgets

| Tool | Bounded by |
|---|---|
| `get_log_metadata` | (free) |
| `search_log` | `max_matches_per_search`, `before` ≤ 10, `after` ≤ 30 |
| `get_lines` | `max_ranges_per_get_lines`, `max_lines_per_get_lines` |
| `get_tail` | `max_lines_per_get_tail_or_head` (default 500) |
| `get_head` | `max_lines_per_get_tail_or_head` (default 500) |
| `find_error_blocks` | fixed regex; `max_blocks` ≤ 50 |
| `list_github_steps` | empty list when not detectable |

All observations are also subject to `max_single_observation_tokens = 4000` and the cumulative `max_total_observation_tokens` budget.

## 5. Anti-leakage verification

The agent payload is built from `cases/<split>/<case_id>/raw.log` and the safe-metadata allowlist (`case_id`, `repo`, `source`, `workflow_name`, `job_name`, `framework`). The runner does **not** open `ground_truth.json`, `case.json` fields outside the allowlist, `required_signals`, `evidence_spans`, `expected_diagnosis`, `results/<split>/eval_*.json`, or any `review/batches/*` label.

Source-level guard run on `tools/log_search_tools.py` + `tools/run_search_agent.py`:

```text
ground_truth      : 2 match(es) (only docstring/comment references are allowed)
eval_diagnosis    : 0 match(es) (only docstring/comment references are allowed)
eval_hybrid       : 0 match(es) (only docstring/comment references are allowed)
human_review      : 0 match(es) (only docstring/comment references are allowed)
required_signals  : 2 match(es) (only docstring/comment references are allowed)
evidence_spans    : 2 match(es) (only docstring/comment references are allowed)
failure_category  : 1 match(es) (only docstring/comment references are allowed)
```

The shim itself (`examples/search_agent_shim_claude_cli.py`) re-runs an AST-walk that fails any payload containing forbidden keys at any depth — this is a belt-and-suspenders check on the runner-built payload.

## 6. Per-split diagnosis metrics

### Table 1 — Static vs search-agent quality

| Method | Type | Split | Success | sv1.1 | CMS v1.1 | Crit Mention | Must Mention | confErr v1.1 | Abstention | Provider Errors |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mcp-search-agent-v1-sonnet` | search | dev | 100.0% | **0.552** | 0.500 | 59.3% | 70.0% | 0.0% | 0.0% | 0 |
| `mcp-search-agent-v1-sonnet` | search | holdout | 100.0% | **0.750** | 0.600 | 95.0% | 100.0% | 0.0% | 0.0% | 0 |
| `mcp-search-agent-v1-sonnet` | search | stress | 100.0% | **0.845** | 0.917 | 100.0% | 95.8% | 0.0% | 0.0% | 0 |
| `raw` | static | dev | 100.0% | 0.326 | 0.300 | 35.0% | 35.0% | 0.0% | 60.0% | 0 |
| `raw` | static | holdout | 100.0% | 0.728 | 0.600 | 85.0% | 91.0% | 0.0% | 0.0% | 0 |
| `raw` | static | stress | 100.0% | 0.480 | 0.417 | 69.2% | 63.3% | 0.0% | 33.3% | 0 |
| `tail` | static | dev | 100.0% | 0.590 | 0.700 | 45.3% | 70.0% | 0.0% | 0.0% | 0 |
| `tail` | static | holdout | 100.0% | 0.725 | 0.600 | 90.0% | 91.0% | 0.0% | 0.0% | 0 |
| `tail` | static | stress | 100.0% | 0.750 | 0.750 | 85.0% | 96.7% | 0.0% | 0.0% | 0 |
| `grep` | static | dev | 100.0% | 0.792 | 0.900 | 72.7% | 85.0% | 0.0% | 0.0% | 0 |
| `grep` | static | holdout | 100.0% | 0.699 | 0.600 | 76.0% | 100.0% | 0.0% | 0.0% | 0 |
| `grep` | static | stress | 100.0% | 0.819 | 0.917 | 95.8% | 96.7% | 0.0% | 0.0% | 0 |
| `rtk-err-cat` | static | dev | 100.0% | 0.696 | 0.900 | 58.7% | 75.0% | 0.0% | 0.0% | 0 |
| `rtk-err-cat` | static | holdout | 100.0% | 0.436 | 0.800 | 39.0% | 56.0% | 0.0% | 0.0% | 0 |
| `rtk-err-cat` | static | stress | 100.0% | 0.472 | 0.417 | 49.2% | 51.7% | 0.0% | 50.0% | 0 |
| `rtk-log` | static | dev | 100.0% | 0.295 | 0.700 | 22.0% | 50.0% | 40.0% | 0.0% | 0 |
| `rtk-log` | static | holdout | 100.0% | 0.321 | 0.400 | 41.0% | 49.0% | 20.0% | 0.0% | 0 |
| `rtk-log` | static | stress | 100.0% | 0.310 | 0.250 | 45.8% | 31.7% | 0.0% | 50.0% | 0 |
| `llm-summary-v1-mock` | static | dev | 100.0% | 0.551 | 0.900 | 43.3% | 55.0% | 0.0% | 0.0% | 0 |
| `llm-summary-v1-mock` | static | holdout | 100.0% | 0.506 | 0.600 | 58.0% | 61.0% | 0.0% | 20.0% | 0 |
| `llm-summary-v1-mock` | static | stress | 100.0% | 0.497 | 0.417 | 72.5% | 51.7% | 0.0% | 50.0% | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | static | dev | 100.0% | 0.775 | 0.900 | 77.7% | 75.0% | 0.0% | 0.0% | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | static | holdout | 100.0% | 0.723 | 0.600 | 85.0% | 96.0% | 0.0% | 0.0% | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | static | stress | 100.0% | 0.817 | 0.917 | 91.7% | 91.7% | 0.0% | 0.0% | 0 |

## 7. Search-agent vs hybrid

| Split | Agent sv1.1 | Hybrid sv1.1 | Δ | Agent total tok | Hybrid total tok |
|---|---:|---:|---:|---:|---:|
| dev | 0.552 | 0.775 | -0.223 | 7.6k | 9.9k |
| holdout | 0.750 | 0.723 | +0.027 | 2.9k | 2.0k |
| stress | 0.845 | 0.817 | +0.028 | 2.6k | 3.1k |

## 8. Search-agent vs grep

| Split | Agent sv1.1 | Grep sv1.1 (v2) | Δ |
|---|---:|---:|---:|
| dev | 0.552 | 0.792 | -0.240 |
| holdout | 0.750 | 0.699 | +0.051 |
| stress | 0.845 | 0.819 | +0.026 |

## 9. Search-agent vs raw

| Split | Agent sv1.1 | Raw sv1.1 (v2) | Δ |
|---|---:|---:|---:|
| dev | 0.552 | 0.326 | +0.227 |
| holdout | 0.750 | 0.728 | +0.022 |
| stress | 0.845 | 0.480 | +0.364 |

## 10. Token / tool-call cost analysis

### Table 2 — Cost

| Method | Type | Split | Total Pipeline Tok | Final/Observed Ctx Tok | Tool Calls | Observed Lines | Provider Errors | Budget Exhausted |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `mcp-search-agent-v1-sonnet` | search | dev | 86.6k | 6.5k | 2.6 | 541 | 0 | 0 |
| `mcp-search-agent-v1-sonnet` | search | holdout | 42.5k | 2.3k | 1.2 | 187 | 0 | 0 |
| `mcp-search-agent-v1-sonnet` | search | stress | 54.2k | 1.9k | 1.8 | 161 | 0 | 0 |
| `raw` | static | dev | 130.4k | 130.2k | 0 | n/a | 0 | 0 |
| `raw` | static | holdout | 11.6k | 11.1k | 0 | n/a | 0 | 0 |
| `raw` | static | stress | 91.5k | 91.2k | 0 | n/a | 0 | 0 |
| `tail` | static | dev | 6.2k | 5.6k | 0 | n/a | 0 | 0 |
| `tail` | static | holdout | 5.1k | 4.6k | 0 | n/a | 0 | 0 |
| `tail` | static | stress | 5.4k | 5.0k | 0 | n/a | 0 | 0 |
| `grep` | static | dev | 43.4k | 42.5k | 0 | n/a | 0 | 0 |
| `grep` | static | holdout | 2.0k | 1.5k | 0 | n/a | 0 | 0 |
| `grep` | static | stress | 2.3k | 1.9k | 0 | n/a | 0 | 0 |
| `rtk-err-cat` | static | dev | 10.3k | 9.4k | 0 | n/a | 0 | 0 |
| `rtk-err-cat` | static | holdout | 765 | 365 | 0 | n/a | 0 | 0 |
| `rtk-err-cat` | static | stress | 2.8k | 2.5k | 0 | n/a | 0 | 0 |
| `rtk-log` | static | dev | 904 | 385 | 0 | n/a | 0 | 0 |
| `rtk-log` | static | holdout | 672 | 260 | 0 | n/a | 0 | 0 |
| `rtk-log` | static | stress | 514 | 165 | 0 | n/a | 0 | 0 |
| `llm-summary-v1-mock` | static | dev | 2.1k | 1.5k | 0 | n/a | 0 | 0 |
| `llm-summary-v1-mock` | static | holdout | 820 | 362 | 0 | n/a | 0 | 0 |
| `llm-summary-v1-mock` | static | stress | 677 | 373 | 0 | n/a | 0 | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | static | dev | 9.9k | 9.0k | 0 | n/a | 0 | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | static | holdout | 2.0k | 1.5k | 0 | n/a | 0 | 0 |
| `hybrid-grep-4k-rtk-err-cat-v1` | static | stress | 3.1k | 2.7k | 0 | n/a | 0 | 0 |

## 11. Budget exhaustion and provider-error analysis

| Split | Cases | Provider errors | Budget exhausted | Completed |
|---|---:|---:|---:|---:|
| dev | 5 | 0 | 0 | 5 |
| holdout | 5 | 0 | 0 | 5 |
| stress | 6 | 0 | 0 | 6 |

## 12. Query / tool behavior analysis

### Table 3 — Search-agent behavior

| Split | Mean Tool Calls | Median Tool Calls | Mean Observation Tokens | Mean Observed Lines | Most Used Tool | Budget Exhaustion Rate |
|---|---:|---:|---:|---:|---|---:|
| dev | 2.6 | 2 | 6.5k | 541.8 | `find_error_blocks` | 0.0% |
| holdout | 1.2 | 1 | 2.3k | 187.8 | `find_error_blocks` | 0.0% |
| stress | 1.83 | 1.5 | 1.9k | 161.5 | `find_error_blocks` | 0.0% |

### Table 5 — Tool usage

| Tool | Call Count | Cases Used | Mean Observation Tokens | Typical Purpose |
|---|---:|---:|---:|---|
| `find_error_blocks` | 15 | 15 | 1.8k | deterministic candidate errors |
| `get_tail` | 6 | 6 | 2.1k | look at the end of the log |
| `search_log` | 6 | 5 | 2.0k | targeted regex / substring search |
| `get_lines` | 3 | 3 | 1.0k | zoom into specific line ranges |

## 13. Per-case wins and losses

### Table 4 — Per-case comparison

| Case | Split | Search sv1.1 | Hybrid sv1.1 | Grep sv1.1 | Search Tokens | Hybrid Tokens | Tool Calls | Winner |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `cargo-tokio-001` | dev | 0.562 | 0.750 | 0.830 | 75.8k | 8.0k | 2 | `grep` |
| `jest-nextjs-001` | dev | 0.200 | 0.775 | 0.700 | 127.0k | 3.5k | 4 | `hybrid` |
| `lint-react-001` | dev | 0.758 | 0.675 | 0.675 | 52.8k | 699 | 2 | `search` |
| `mypy-pandas-001` | dev | 0.577 | 0.773 | 0.826 | 99.1k | 19.7k | 3 | `grep` |
| `pytest-pandas-001` | dev | 0.663 | 0.900 | 0.930 | 78.5k | 17.7k | 2 | `grep` |
| `actions-terraform-001` | holdout | 0.550 | 0.475 | 0.475 | 34.2k | 735 | 1 | `search` |
| `dependabot-cargo-001` | holdout | 0.463 | 0.390 | 0.390 | 38.1k | 2.6k | 1 | `search` |
| `docs-transformers-001` | holdout | 0.867 | 0.900 | 0.867 | 40.2k | 2.3k | 1 | `hybrid` |
| `pushpr-nextjs-001` | holdout | 0.883 | 0.900 | 0.840 | 63.6k | 2.9k | 2 | `hybrid` |
| `tsc-typescript-001` | holdout | 0.988 | 0.948 | 0.925 | 36.5k | 1.5k | 1 | `search` |
| `cleanup-k8s-stress-001` | stress | 0.800 | 0.725 | 0.800 | 32.8k | 452 | 1 | `search` |
| `cleanup-tsc-stress-001` | stress | 0.800 | 0.800 | 0.800 | 32.8k | 446 | 1 | `search` |
| `docbuild-hf-stress-001` | stress | 0.800 | 0.775 | 0.760 | 35.1k | 698 | 1 | `search` |
| `prettier-react-stress-001` | stress | 0.742 | 0.700 | 0.700 | 52.7k | 848 | 2 | `search` |
| `pytest-sklearn-stress-001` | stress | 0.975 | 0.950 | 0.992 | 107.7k | 8.1k | 4 | `grep` |
| `pytest-sklearn-stress-002` | stress | 0.950 | 0.950 | 0.860 | 64.1k | 7.9k | 2 | `search` |

## 14. Failure-mode analysis

### Table 6 — Search-agent failure modes

| Failure Mode | Cases | Example | Notes |
|---|---:|---|---|
| `method_success` | 11 | `lint-react-001` | — |
| `missed_primary_error` | 4 | `cargo-tokio-001` | — |
| `tool_observation_too_noisy` | 1 | `mypy-pandas-001` | — |

## 15. Interpretation guardrails

- **One agent prompt, one tool budget, one model.** The agent ran with `prompts/search_agent_v1.md`, the budget in this config, and Claude Sonnet 4.6 only.
- **Local MCP-style tools** (Mode A in the E7 plan). A real MCP server adapter is a future extension.
- **16 cases.** Directional, not statistical.
- **Calibration is expert-model, not human.** sv1.1 was calibrated on E2/E2b expert-model labels collected against Haiku diagnoses, not Sonnet diagnoses. Apply with care to v2 / search-agent.
- **Cost accounting differs from static methods.** The search-agent total includes input/output across all steps plus tool observations actually shown to the model. Static methods include the single context sent once + diagnosis output.
- **The 4 schemas / 7 tools / agent shim are deterministic side-by-side with the model loop**, but the model's actions at temperature=0 still drift slightly across runs.

## 16. Decision and next experiment

**Decision: `KEEP_AS_EXPLORATORY`**

| Criterion | Value | Pass? |
|---|---:|:---:|
| search-agent macro sv1.1 ≥ hybrid macro - 0.02 | 0.716 vs 0.771 | ❌ |
| provider error rate ≤ 10% | 0.0% | ✅ |
| budget exhaustion rate ≤ 20% | 0.0% | ✅ |
| mean total agent tokens per case | 61.1k | (informational) |

Search-agent is competitive with hybrid but does not clearly win. Keep `mcp-search-agent-v1-sonnet` as an **exploratory** method — report it alongside v1.3 baselines but do not freeze a v1.4 baseline yet. Investigate the dominant failure mode in §14 before committing to a search-agent track.

