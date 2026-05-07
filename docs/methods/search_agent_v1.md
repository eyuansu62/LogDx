# `search_agent_v1` — method doc

`search_agent_v1` is the prompt + protocol behind CILogBench's first
end-to-end search-agent baseline (`mcp-search-agent-v1-<model_slug>`).

## What it is

An agent that:

1. Starts with only safe case metadata — repo, workflow_name, job_name,
   framework, and the case_id. **No** log content yet.
2. Issues a sequence of strict-JSON `tool_call` actions over a small set
   of bounded local tools that operate on `raw.log`.
3. Stops by emitting a strict-JSON `final_diagnosis` action, normalized
   to `schemas/diagnosis.schema.json`.

Each action must be a single JSON object. Anything else is a runner-side
parse failure and (under `--strict`) aborts the case.

## Tools

See `tools/log_search_tools.py` and the prompt
(`prompts/search_agent_v1.md`). Seven tools, all deterministic, all
bounded by the agent config's `tool_budget`:

```text
get_log_metadata, search_log, get_lines, get_tail, get_head,
find_error_blocks, list_github_steps
```

## Budgets

Hard caps (per `tool_budget` in the agent config):

```text
max_tool_calls                 # of tool steps before final_diagnosis is forced
max_total_observation_tokens   # cumulative tokens of observations shown to the model
max_single_observation_tokens  # any single observation truncated above this
max_matches_per_search         # search_log result cap
max_ranges_per_get_lines       # get_lines argument cap
max_lines_per_get_lines        # get_lines total-line cap
max_lines_per_get_tail_or_head # get_tail / get_head cap (default 500)
```

Budget exhaustion is **not** silent: the runner emits an `unknown`
diagnosis with `metadata.budget_exhausted = true`, and the trace
records `status = "budget_exhausted"`.

## Anti-leakage

The runner builds the agent payload only from `raw.log` + the
safe-metadata allowlist. The shim re-runs an AST-walk and refuses any
payload containing forbidden keys (`ground_truth`, `failure_category`,
`required_signals`, `evidence_spans`, `expected_diagnosis`).

The agent itself is reminded in its prompt that none of these are
available.

## Output

For each case, two artifacts:

- a per-case **trace** under
  `results/<split>/search_agents/<agent>/traces/<case>.json`, with each
  step's agent action, tool observation, and runtime;
- a per-case **diagnosis row** under
  `results/<split>/diagnoses/<agent>/<case>.json`, matching the
  `run_diagnosis.py` row shape so that
  `tools/evaluate_diagnosis.py` can score it without modification.

The diagnosis row's `metadata` block includes:

```text
method_type = "end_to_end_search_agent"
trace_path  = path to the trace JSON
tool_call_count
observed_line_count
observation_tokens_estimate
total_agent_tokens_estimate    # input + output across all steps + observation tokens
budget_exhausted (bool)
provider_error (str|null)
```

## Determinism

Tool outputs are byte-stable. The model loop at `temperature=0` is not
guaranteed byte-stable across reruns of the Anthropic API; per-case
caching is keyed by the row hash so successful cached cases reproduce
verbatim, but `--no-cache` reruns may drift slightly.
