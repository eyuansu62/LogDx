"""
Run an MCP-style search agent over the v1.3 protocol.

Per case:
  1. Seed the conversation with `get_log_metadata`.
  2. Invoke the agent shim with safe metadata + tool catalog +
     budget_remaining + the conversation so far.
  3. Parse the JSON action: tool_call → execute deterministic tool
     and append the observation; final_diagnosis → break.
  4. Stop when final_diagnosis lands or any budget is exhausted (then
     emit an unknown diagnosis tagged budget_exhausted=true).

Outputs per (split, agent, case):
  results/<split>/search_agents/<agent>/traces/<case_id>.json
  results/<split>/search_agents/<agent>/<agent>.jsonl   ← one trace stub per case

Outputs per (split, agent):
  results/<split>/diagnoses/<agent>/<agent>.jsonl       ← diagnosis-row jsonl,
                                                          format = run_diagnosis.py output

Anti-leakage: the agent payload is built only from raw.log + safe
case-metadata fields. ground_truth.json / failure_category /
required_signals / evidence_spans / expected_diagnosis are NEVER read
by this runner.

Usage:
    export SEARCH_AGENT_COMMAND="python3 examples/search_agent_shim_claude_cli.py"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
    python3 tools/run_search_agent.py \
        --protocol protocols/legacy/cilogbench-v1.3.lock.json \
        --split holdout \
        --agent-config configs/search_agents/mcp-search-agent-v1-sonnet.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from log_search_tools import (  # noqa: E402
    dispatch as tool_dispatch,
    observation_token_estimate,
    cap_observation,
    ALLOWED_META_FIELDS,
)


CATEGORY_ENUM = {
    "test_assertion", "compile_error", "type_error",
    "lint_failure", "formatting_failure",
    "dependency_install", "docker_build",
    "github_actions_config", "permission_or_secret",
    "network_or_flaky", "timeout_or_oom",
    "unknown", "other",
}


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def safe_case_metadata(case_meta: dict) -> dict:
    return {k: case_meta.get(k) for k in ALLOWED_META_FIELDS if k in case_meta}


def tool_catalog(allowed_tools: list[str]) -> list[dict]:
    """The schema documentation handed to the agent (compact form)."""
    schemas = {
        "get_log_metadata": {
            "name": "get_log_metadata",
            "description": "Free; returns line_count, byte_size, repo, workflow_name, job_name, framework. Call once at the start.",
            "arguments": {},
        },
        "search_log": {
            "name": "search_log",
            "description": "Regex / substring search; returns matches with line numbers and ±N lines context.",
            "arguments": {
                "query": "string (regex or substring)",
                "regex": "bool, default true",
                "case_sensitive": "bool, default false",
                "before": "int 0..10, default 3",
                "after": "int 0..30, default 8",
                "max_matches": "int, capped by config",
            },
        },
        "get_lines": {
            "name": "get_lines",
            "description": "Fetch specific [start_line, end_line] ranges (1-indexed).",
            "arguments": {"ranges": "list of [start,end] pairs"},
        },
        "get_tail": {
            "name": "get_tail",
            "description": "Last N lines (capped).",
            "arguments": {"lines": "int"},
        },
        "get_head": {
            "name": "get_head",
            "description": "First N lines (capped).",
            "arguments": {"lines": "int"},
        },
        "find_error_blocks": {
            "name": "find_error_blocks",
            "description": "Deterministic helper using fixed regex (error|failed|...|##[error]). Returns merged candidate blocks.",
            "arguments": {"before": "int", "after": "int", "max_blocks": "int"},
        },
        "list_github_steps": {
            "name": "list_github_steps",
            "description": "Step boundaries via ##[group]/##[endgroup] markers. Empty list if not detectable.",
            "arguments": {},
        },
    }
    return [schemas[t] for t in allowed_tools if t in schemas]


def invoke_shim(
    *, command: str, payload: dict, timeout_s: int = 240,
) -> tuple[dict, dict]:
    """Returns (action, shim_metadata). Raises RuntimeError on shim failure."""
    argv = shlex.split(command)
    res = subprocess.run(
        argv,
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        timeout=timeout_s,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"agent shim exited {res.returncode}: "
            f"{(res.stderr or b'').decode('utf-8', 'replace')[:400]}"
        )
    try:
        wrapper = json.loads(res.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"agent shim returned non-JSON: {e}. First 400 chars: {res.stdout[:400]!r}"
        )
    action = wrapper.get("action")
    if not isinstance(action, dict) or action.get("type") not in ("tool_call", "final_diagnosis"):
        raise RuntimeError(f"agent shim returned invalid action: {action!r}")
    shim_meta = {
        "provider": wrapper.get("provider"),
        "model": wrapper.get("model"),
        "usage": wrapper.get("usage") or {},
    }
    return action, shim_meta


def normalize_diagnosis(diag_raw: dict) -> dict:
    """Same shape as `tools/run_diagnosis.py` row body."""
    out = {
        "summary": str(diag_raw.get("summary", "")),
        "root_cause_category": diag_raw.get("root_cause_category", "unknown"),
        "root_cause": str(diag_raw.get("root_cause", "unknown")),
        "confidence": float(diag_raw.get("confidence", 0.0) or 0.0),
        "relevant_files": list(diag_raw.get("relevant_files", []) or []),
        "relevant_tests": list(diag_raw.get("relevant_tests", []) or []),
        "evidence": list(diag_raw.get("evidence", []) or []),
        "suggested_fix": str(diag_raw.get("suggested_fix", "")),
    }
    if out["root_cause_category"] not in CATEGORY_ENUM:
        out["root_cause_category"] = "other"
    out["confidence"] = max(0.0, min(1.0, out["confidence"]))
    fixed_ev = []
    for ev in out["evidence"]:
        if isinstance(ev, dict) and "quote" in ev and "reason" in ev:
            fixed_ev.append({"quote": str(ev["quote"]), "reason": str(ev["reason"])})
    out["evidence"] = fixed_ev
    return out


def unknown_body(reason: str) -> dict:
    return {
        "summary": reason,
        "root_cause_category": "unknown",
        "root_cause": "unknown",
        "confidence": 0.0,
        "relevant_files": [],
        "relevant_tests": [],
        "evidence": [],
        "suggested_fix": "",
    }


def run_one_case(
    *,
    split: str,
    case_id: str,
    cases_dir: Path,
    results_dir: Path,
    agent_name: str,
    agent_config: dict,
    prompt_text: str,
    prompt_sha: str,
    config_sha: str,
    command: str,
    strict: bool,
) -> dict:
    raw_p = cases_dir / split / case_id / "raw.log"
    case_p = cases_dir / split / case_id / "case.json"
    if not raw_p.exists():
        raise FileNotFoundError(f"missing raw.log for {split}/{case_id}")
    if not case_p.exists():
        raise FileNotFoundError(f"missing case.json for {split}/{case_id}")

    case_meta = load_json(case_p)
    safe_meta = safe_case_metadata(case_meta)
    allowed = list(agent_config.get("allowed_tools") or [])
    catalog = tool_catalog(allowed)
    budget_cfg = agent_config.get("tool_budget") or {}
    max_tool_calls = int(budget_cfg.get("max_tool_calls", 8))
    max_total_obs_tokens = int(budget_cfg.get("max_total_observation_tokens", 16000))
    max_single_obs_tokens = int(budget_cfg.get("max_single_observation_tokens", 4000))

    # ----- Seed conversation with get_log_metadata -----
    conversation: list[dict] = []
    seed_obs = tool_dispatch("get_log_metadata", {}, raw_path=raw_p,
                              case_meta=case_meta, budget=budget_cfg)
    seed_obs_str = json.dumps(seed_obs, ensure_ascii=False)
    seed_obs_tokens = observation_token_estimate(seed_obs)
    conversation.append({
        "role": "tool",
        "name": "get_log_metadata",
        "content": seed_obs_str,
    })

    out_root = results_dir / split / "search_agents" / agent_name
    traces_dir = out_root / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    diag_root = results_dir / split / "diagnoses" / agent_name
    diag_root.mkdir(parents=True, exist_ok=True)
    trace_path = traces_dir / f"{case_id}.json"

    steps: list[dict] = []
    # Seed step (no agent action; pre-seeded observation)
    steps.append({
        "step_index": 0,
        "agent_action": {"type": "seed_observation", "tool": "get_log_metadata"},
        "tool_observation": {
            "tokens_estimate": seed_obs_tokens,
            "preview": seed_obs,
        },
        "runtime_ms": 0,
    })

    tool_calls_used = 0
    obs_tokens_used = seed_obs_tokens
    agent_in_total = 0
    agent_out_total = 0
    final_diag: dict | None = None
    status = "completed"
    provider_error: str | None = None
    case_started = time.perf_counter()
    step_index = 1
    while True:
        if tool_calls_used >= max_tool_calls:
            status = "budget_exhausted"
            break
        if obs_tokens_used >= max_total_obs_tokens:
            status = "budget_exhausted"
            break

        # Build agent payload
        payload = {
            "case_id": case_id,
            "agent_name": agent_name,
            "prompt": prompt_text,
            "safe_case_metadata": safe_meta,
            "available_tools": catalog,
            "conversation": conversation,
            "budget_remaining": {
                "tool_calls": max_tool_calls - tool_calls_used,
                "observation_tokens": max_total_obs_tokens - obs_tokens_used,
            },
        }

        step_start = time.perf_counter()
        try:
            action, shim_meta = invoke_shim(command=command, payload=payload)
        except Exception as e:
            provider_error = f"{type(e).__name__}: {e}"
            status = "provider_error"
            steps.append({
                "step_index": step_index,
                "agent_action": {"type": "provider_error"},
                "tool_observation": None,
                "runtime_ms": (time.perf_counter() - step_start) * 1000,
                "error": provider_error[:400],
            })
            if strict:
                raise
            break

        usage = shim_meta.get("usage") or {}
        in_tok = int(usage.get("input_tokens") or 0)
        out_tok = int(usage.get("output_tokens") or 0)
        agent_in_total += in_tok
        agent_out_total += out_tok

        if action.get("type") == "final_diagnosis":
            final_diag = normalize_diagnosis(action.get("diagnosis") or {})
            steps.append({
                "step_index": step_index,
                "agent_action": {"type": "final_diagnosis"},
                "tool_observation": None,
                "runtime_ms": (time.perf_counter() - step_start) * 1000,
                "agent_input_tokens_estimate": in_tok,
                "agent_output_tokens_estimate": out_tok,
            })
            break

        # tool_call
        tool_name = action.get("tool")
        args = action.get("arguments") or {}
        if tool_name not in allowed:
            status = "invalid_action"
            provider_error = f"agent requested disallowed tool {tool_name!r}"
            steps.append({
                "step_index": step_index,
                "agent_action": action,
                "tool_observation": None,
                "runtime_ms": (time.perf_counter() - step_start) * 1000,
                "error": provider_error,
                "agent_input_tokens_estimate": in_tok,
                "agent_output_tokens_estimate": out_tok,
            })
            break
        try:
            obs = tool_dispatch(tool_name, args, raw_path=raw_p,
                                 case_meta=case_meta, budget=budget_cfg)
        except Exception as e:
            obs = {"_error": f"{type(e).__name__}: {e}"}
        capped = cap_observation(obs, max_tokens=max_single_obs_tokens)
        obs_tokens = observation_token_estimate(capped)
        # If even capped exceeds remaining budget, accept it but mark
        if obs_tokens_used + obs_tokens > max_total_obs_tokens:
            # Still record but mark exhaustion next loop iteration
            pass
        obs_tokens_used += obs_tokens
        tool_calls_used += 1
        conversation.append({
            "role": "assistant",
            "content": json.dumps(action, ensure_ascii=False),
        })
        conversation.append({
            "role": "tool",
            "name": tool_name,
            "content": json.dumps(capped, ensure_ascii=False),
        })
        steps.append({
            "step_index": step_index,
            "agent_action": action,
            "tool_observation": {
                "tokens_estimate": obs_tokens,
                "preview_keys": sorted(capped.keys()) if isinstance(capped, dict) else None,
            },
            "runtime_ms": (time.perf_counter() - step_start) * 1000,
            "agent_input_tokens_estimate": in_tok,
            "agent_output_tokens_estimate": out_tok,
        })
        step_index += 1

    case_runtime_ms = (time.perf_counter() - case_started) * 1000
    if final_diag is None:
        # Emit unknown body tagged with the failure cause
        if status == "budget_exhausted":
            reason = f"budget_exhausted_before_diagnosis tool_calls={tool_calls_used} obs_tokens={obs_tokens_used}"
        elif status == "provider_error":
            reason = f"provider_error: {provider_error or '?'}"
        elif status == "invalid_action":
            reason = f"invalid_action: {provider_error or '?'}"
        else:
            reason = "unknown"
        final_diag = unknown_body(reason)

    # ----- Write trace JSON -----
    trace = {
        "case_id": case_id,
        "split": split,
        "agent_name": agent_name,
        "mode": "end_to_end_search_agent",
        "status": status,
        "safe_case_metadata": safe_meta,
        "tool_budget": budget_cfg,
        "steps": steps,
        "final_diagnosis_path": str((diag_root / f"{case_id}.json").relative_to(ROOT)),
        "usage": {
            "tool_call_count": tool_calls_used,
            "observed_line_count": _approx_lines_from_obs_tokens(obs_tokens_used),
            "observed_byte_size": obs_tokens_used * 4,
            "observation_tokens_estimate": obs_tokens_used,
            "agent_input_tokens_estimate": agent_in_total,
            "agent_output_tokens_estimate": agent_out_total,
            "total_agent_tokens_estimate": agent_in_total + agent_out_total + obs_tokens_used,
        },
        "metadata": {
            "provider": "command",
            "prompt_sha256": prompt_sha,
            "config_sha256": config_sha,
            "runtime_ms": case_runtime_ms,
            "provider_error": provider_error,
            "budget_exhausted": status == "budget_exhausted",
        },
    }
    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    # ----- Write per-case diagnosis row (run_diagnosis.py shape) -----
    diag_row = {
        "case_id": case_id,
        "context_method": agent_name,
        "diagnoser": agent_name,
        "diagnoser_name": agent_name,
        "mode": "root_cause_diagnosis",
        **final_diag,  # summary, root_cause_category, ..., evidence
        "input": {
            "context_path": str((cases_dir / split / case_id / "raw.log").relative_to(ROOT)),
            "context_sha256": "",
            "prompt_sha256": prompt_sha,
            "context_tokens_estimate": obs_tokens_used,
        },
        "usage": {"output_tokens_estimate": agent_out_total},
        "metadata": {
            "method_type": "end_to_end_search_agent",
            "trace_path": str(trace_path.relative_to(ROOT)),
            "tool_call_count": tool_calls_used,
            "observed_line_count": trace["usage"]["observed_line_count"],
            "observation_tokens_estimate": obs_tokens_used,
            "total_agent_tokens_estimate": trace["usage"]["total_agent_tokens_estimate"],
            "budget_exhausted": status == "budget_exhausted",
            "provider_error": provider_error,
            "runtime_ms": case_runtime_ms,
            "config_sha256": config_sha,
            "prompt_sha256": prompt_sha,
            "command": command,
        },
    }
    # also write the per-case json file the trace points at
    (diag_root / f"{case_id}.json").write_text(
        json.dumps(diag_row, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return diag_row


def _approx_lines_from_obs_tokens(tokens: int) -> int:
    # rough heuristic: ~12 tokens/line in CI logs
    return max(0, tokens // 12)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--agent-config", type=Path, required=True)
    ap.add_argument("--agent-name", default=None)
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--case-id", default=None,
                    help="Run only this case (smoke-test mode).")
    ap.add_argument("--allow-external-llm", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="Abort on first provider error.")
    args = ap.parse_args(argv)

    # 1. Validate protocol lock
    rc = subprocess.run(
        [sys.executable, "tools/validate_protocol_lock.py",
         "--protocol", str(args.protocol)],
        cwd=ROOT,
    ).returncode
    if rc != 0:
        return rc

    # 2. Load agent config
    agent_config = load_json(args.agent_config)
    agent_name = args.agent_name or agent_config.get("agent_name")
    if not agent_name:
        print("ERROR: agent name not set", file=sys.stderr)
        return 1

    # 3. Privacy + opt-in gate
    privacy = agent_config.get("privacy") or {}
    if privacy.get("requires_explicit_external_llm_opt_in", True):
        if not (args.allow_external_llm or
                os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM") == "1"):
            print("ERROR: agent requires --allow-external-llm or "
                  "CILOGBENCH_ALLOW_EXTERNAL_LLM=1", file=sys.stderr)
            return 2

    # 4. Resolve command
    command = agent_config.get("command_override")
    if not command:
        env_var = agent_config.get("command_env_var") or "SEARCH_AGENT_COMMAND"
        command = os.environ.get(env_var, "")
        if not command:
            print(f"ERROR: {env_var} not set", file=sys.stderr)
            return 1

    # 5. Load prompt text + hash
    prompt_path = ROOT / agent_config["prompt_path"]
    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt_sha = sha256_path(prompt_path)
    config_sha = sha256_path(args.agent_config)

    split_dir = args.cases_dir / args.split
    case_dirs = sorted(p for p in split_dir.iterdir() if p.is_dir())
    if args.case_id:
        case_dirs = [p for p in case_dirs if p.name == args.case_id]
        if not case_dirs:
            print(f"ERROR: case {args.case_id} not found in {split_dir}", file=sys.stderr)
            return 1

    rows: list[dict] = []
    for case_dir in case_dirs:
        cid = case_dir.name
        try:
            row = run_one_case(
                split=args.split, case_id=cid,
                cases_dir=args.cases_dir, results_dir=args.results_dir,
                agent_name=agent_name, agent_config=agent_config,
                prompt_text=prompt_text, prompt_sha=prompt_sha,
                config_sha=config_sha, command=command, strict=args.strict,
            )
        except Exception as e:
            print(f"FAIL {args.split}/{cid}: {type(e).__name__}: {e}",
                  file=sys.stderr)
            if args.strict:
                return 1
            continue
        rows.append(row)
        meta = row["metadata"]
        print(f"  {cid}: status={'pe' if meta.get('provider_error') else 'be' if meta.get('budget_exhausted') else 'ok'} "
              f"tool_calls={meta['tool_call_count']} "
              f"obs_tokens={meta['observation_tokens_estimate']} "
              f"agent_tokens={meta['total_agent_tokens_estimate']} "
              f"sv1={'?'} runtime={meta['runtime_ms']:.0f}ms")

    # 6. Write the per-method jsonl in run_diagnosis.py format
    diag_root = args.results_dir / args.split / "diagnoses" / agent_name
    diag_root.mkdir(parents=True, exist_ok=True)
    out_jsonl = diag_root / f"{agent_name}.jsonl"
    # Preserve any pre-existing rows for cases we did not just run, but
    # overwrite rows for cases we ran.
    existing: list[dict] = []
    if out_jsonl.exists():
        existing = [json.loads(l) for l in out_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_id: dict[str, dict] = {r["case_id"]: r for r in existing}
    for r in rows:
        by_id[r["case_id"]] = r
    out_jsonl.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                    for r in by_id.values()) + "\n",
                          encoding="utf-8")
    print(f"Wrote {out_jsonl.relative_to(ROOT)}  ({len(by_id)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
