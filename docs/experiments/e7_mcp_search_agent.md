# E7 — MCP/Search-Agent Baseline (experiment doc)

E7 adds the first **end-to-end search-agent** baseline to CILogBench. It
asks: does an agent that issues bounded log-search tool calls beat the
locked v1.3 hybrid static-context baseline?

## Method

`mcp-search-agent-v1-sonnet` (config:
`configs/search_agents/mcp-search-agent-v1-sonnet.json`) is an end-to-end
agent driven by Claude Sonnet 4.6 via `claude -p`. It receives only safe
case metadata, then uses a small set of deterministic local tools to
inspect the raw log:

- `get_log_metadata` (free)
- `search_log` (regex/substring with line-numbered context)
- `get_lines` (range fetch)
- `get_tail` / `get_head`
- `find_error_blocks` (deterministic helper)
- `list_github_steps` (best-effort)

All tools live in `tools/log_search_tools.py`. None of them reads
`ground_truth.json`, signal eval, diagnosis eval, or review labels.

The agent issues each step as strict JSON (`tool_call` or `final_diagnosis`),
under a fixed budget:

```text
max_tool_calls = 8
max_total_observation_tokens = 16000
max_single_observation_tokens = 4000
```

When the budget is exhausted the runner emits an `unknown` diagnosis
tagged with `budget_exhausted=true`.

## Pipeline

```text
cases/<split>/<case_id>/raw.log
  + cases/<split>/<case_id>/case.json (safe-metadata fields only)
  -> tools/log_search_tools.py        (deterministic local tools)
  -> tools/run_search_agent.py        (per-case agent loop)
  -> examples/search_agent_shim_claude_cli.py  (Sonnet via claude -p)
  -> traces JSON + diagnosis JSONL
  -> tools/evaluate_diagnosis.py      (sv1 + sv1.1)
  -> tools/render_e7_search_agent_report.py
```

## Scope

E7 is a **separately-tabled baseline**, not a context-provider. It is
not included in `protocols/legacy/cilogbench-v1.3.lock.json`. If the verdict
of the rendered report is `ADD_AS_V1_4_BASELINE`, the next step is to
freeze `cilogbench-v1.4` with the search-agent locked in alongside the
v1.3 baselines.

## Outputs

- `results/<split>/search_agents/mcp-search-agent-v1-sonnet/traces/<case>.json` — per-step trace
- `results/<split>/diagnoses/mcp-search-agent-v1-sonnet/<case>.json` — diagnosis row (matches `schemas/diagnosis.schema.json`)
- `results/<split>/diagnoses/mcp-search-agent-v1-sonnet/mcp-search-agent-v1-sonnet.jsonl` — manifest
- `results/<split>/eval_diagnosis_mcp-search-agent-v1-sonnet.json` — eval (same format as `real-debugger-v*`)
- `reports/experiments/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md`
- `results/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.manifest.json`

## Reproducing

```bash
export SEARCH_AGENT_COMMAND="python3 examples/search_agent_shim_claude_cli.py"
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
export CILOGBENCH_CLAUDE_MODEL=sonnet

for split in dev holdout stress; do
  python3 tools/run_search_agent.py \
    --protocol protocols/legacy/cilogbench-v1.3.lock.json \
    --split $split \
    --agent-config configs/search_agents/mcp-search-agent-v1-sonnet.json \
    --allow-external-llm
  python3 tools/evaluate_diagnosis.py \
    --split $split --diagnoser mcp-search-agent-v1-sonnet
done

python3 tools/render_e7_search_agent_report.py
```
