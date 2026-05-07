"""
CILogBench E7 — deterministic local search tools over raw CI logs.

All tools operate on:
  cases/<split>/<case_id>/raw.log
  the safe-metadata derived from cases/<split>/<case_id>/case.json

Tools must NOT read:
  ground_truth.json
  case.json fields beyond the safe-metadata allowlist
  required_signals
  evidence_spans
  evaluation outputs
  diagnosis outputs
  review labels

Each tool enforces hard caps from the agent config's `tool_budget`.

Usage as a library: see `dispatch(tool_name, arguments, *, raw_path,
case_meta, budget)`.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

# Approximate "token" estimator used everywhere in the benchmark for char-based
# accounting (chars / 4). Keep consistent with run_diagnosis.py / hybrid router.
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


# ----- Tool 1: get_log_metadata -----

ALLOWED_META_FIELDS = (
    "case_id", "repo", "source", "workflow_name", "job_name", "framework",
)


def get_log_metadata(*, raw_path: Path, case_meta: dict) -> dict:
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    line_count = text.count("\n") + (0 if text.endswith("\n") else 1)
    safe_meta = {k: case_meta.get(k) for k in ALLOWED_META_FIELDS if k in case_meta}
    return {
        "case_id": safe_meta.get("case_id"),
        "line_count": line_count,
        "byte_size": len(text.encode("utf-8")),
        "framework": safe_meta.get("framework"),
        "repo": safe_meta.get("repo"),
        "workflow_name": safe_meta.get("workflow_name"),
        "job_name": safe_meta.get("job_name"),
        "source": safe_meta.get("source"),
    }


# ----- Tool 2: search_log -----

def search_log(
    *,
    raw_path: Path,
    arguments: dict,
    budget: dict,
) -> dict:
    query = arguments.get("query")
    if not isinstance(query, str) or not query:
        raise ValueError("search_log: 'query' must be a non-empty string")
    is_regex = bool(arguments.get("regex", True))
    case_sensitive = bool(arguments.get("case_sensitive", False))
    before = max(0, min(int(arguments.get("before", 3)), 10))
    after = max(0, min(int(arguments.get("after", 8)), 30))
    cap = int(budget.get("max_matches_per_search", 30))
    max_matches = max(1, min(int(arguments.get("max_matches", cap)), cap))

    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    n = len(lines)

    if is_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error as e:
            raise ValueError(f"search_log: invalid regex {query!r}: {e}")
        def match_test(s: str) -> bool:
            return bool(pattern.search(s))
    else:
        needle = query if case_sensitive else query.lower()
        def match_test(s: str) -> bool:
            return needle in (s if case_sensitive else s.lower())

    matches: list[dict] = []
    total_match_count = 0
    for i, line in enumerate(lines):
        # Avoid pathological-length lines blowing up regex
        if len(line) > 4000:
            line_for_match = line[:4000]
        else:
            line_for_match = line
        if not match_test(line_for_match):
            continue
        total_match_count += 1
        if len(matches) >= max_matches:
            continue
        ctx_start = max(0, i - before)
        ctx_end = min(n, i + after + 1)
        ctx = []
        for j in range(ctx_start, ctx_end):
            ctx.append({"line": j + 1, "text": lines[j][:1500]})
        matches.append({
            "line": i + 1,
            "text": lines[i][:1500],
            "context": ctx,
        })

    truncated = total_match_count > len(matches)
    return {
        "query": query,
        "regex": is_regex,
        "case_sensitive": case_sensitive,
        "before": before,
        "after": after,
        "max_matches": max_matches,
        "matches": matches,
        "match_count": total_match_count,
        "truncated": truncated,
    }


# ----- Tool 3: get_lines -----

def get_lines(*, raw_path: Path, arguments: dict, budget: dict) -> dict:
    ranges = arguments.get("ranges") or []
    if not isinstance(ranges, list) or not ranges:
        raise ValueError("get_lines: 'ranges' must be a non-empty list of [start,end] pairs")
    max_ranges = int(budget.get("max_ranges_per_get_lines", 5))
    max_total_lines = int(budget.get("max_lines_per_get_lines", 200))
    if len(ranges) > max_ranges:
        ranges = ranges[:max_ranges]

    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    n = len(lines)

    out_ranges: list[dict] = []
    total_lines = 0
    for r in ranges:
        try:
            start, end = int(r[0]), int(r[1])
        except (TypeError, ValueError, IndexError):
            raise ValueError(f"get_lines: invalid range {r!r}")
        if start < 1 or end < start:
            continue
        s = max(1, start)
        e = min(n, end)
        rng_lines: list[dict] = []
        for j in range(s - 1, e):
            if total_lines >= max_total_lines:
                break
            rng_lines.append({"line": j + 1, "text": lines[j][:1500]})
            total_lines += 1
        out_ranges.append({"start": s, "end": e, "lines": rng_lines})
        if total_lines >= max_total_lines:
            break

    return {
        "ranges": out_ranges,
        "total_lines_returned": total_lines,
        "truncated": total_lines >= max_total_lines,
    }


# ----- Tool 4: get_tail -----

def get_tail(*, raw_path: Path, arguments: dict, budget: dict) -> dict:
    asked = int(arguments.get("lines", 200))
    cap = int(budget.get("max_lines_per_get_tail_or_head", 500))
    n_req = max(1, min(asked, cap))
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    total = len(lines)
    start_idx = max(0, total - n_req)
    out = [{"line": i + 1, "text": lines[i][:1500]} for i in range(start_idx, total)]
    return {
        "asked_lines": asked,
        "returned_lines": len(out),
        "first_line": out[0]["line"] if out else None,
        "last_line": out[-1]["line"] if out else None,
        "lines": out,
    }


# ----- Tool 5: get_head -----

def get_head(*, raw_path: Path, arguments: dict, budget: dict) -> dict:
    asked = int(arguments.get("lines", 200))
    cap = int(budget.get("max_lines_per_get_tail_or_head", 500))
    n_req = max(1, min(asked, cap))
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    out = [{"line": i + 1, "text": lines[i][:1500]} for i in range(min(n_req, len(lines)))]
    return {
        "asked_lines": asked,
        "returned_lines": len(out),
        "first_line": 1 if out else None,
        "last_line": out[-1]["line"] if out else None,
        "lines": out,
    }


# ----- Tool 6: find_error_blocks -----

# Same fixed regex as the locked grep baseline.
_ERROR_REGEX = re.compile(
    r"error|failed|failure|traceback|exception|assert|panic|exit code|##\[error\]",
    re.IGNORECASE,
)


def find_error_blocks(*, raw_path: Path, arguments: dict, budget: dict) -> dict:
    before = max(0, min(int(arguments.get("before", 3)), 10))
    after = max(0, min(int(arguments.get("after", 8)), 30))
    max_blocks = max(1, min(int(arguments.get("max_blocks", 20)), 50))
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    n = len(lines)

    matched_indices: list[int] = []
    for i, line in enumerate(lines):
        line_for_match = line[:4000]
        if _ERROR_REGEX.search(line_for_match):
            matched_indices.append(i)
        if len(matched_indices) > 5000:
            break

    # Merge overlapping windows
    blocks: list[tuple[int, int]] = []
    for idx in matched_indices:
        s = max(0, idx - before)
        e = min(n - 1, idx + after)
        if blocks and s <= blocks[-1][1] + 1:
            blocks[-1] = (blocks[-1][0], max(blocks[-1][1], e))
        else:
            blocks.append((s, e))

    truncated = len(blocks) > max_blocks
    blocks = blocks[:max_blocks]

    out_blocks: list[dict] = []
    for s, e in blocks:
        block_lines = [{"line": j + 1, "text": lines[j][:1500]} for j in range(s, e + 1)]
        out_blocks.append({
            "start_line": s + 1,
            "end_line": e + 1,
            "lines": block_lines,
        })

    return {
        "regex": _ERROR_REGEX.pattern,
        "before": before,
        "after": after,
        "max_blocks": max_blocks,
        "block_count": len(out_blocks),
        "blocks": out_blocks,
        "truncated": truncated,
        "total_match_count": len(matched_indices),
    }


# ----- Tool 7: list_github_steps -----

# Best-effort detection of GitHub Actions step boundaries via the
# `##[group]Step Name ... ##[endgroup]` markers that the runner emits.
_GROUP_START_RE = re.compile(r"##\[group\](.+?)\s*$")
_GROUP_END_RE = re.compile(r"^\s*##\[endgroup\]")


def list_github_steps(*, raw_path: Path, arguments: dict, budget: dict) -> dict:
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    steps: list[dict] = []
    open_step: dict | None = None
    for i, line in enumerate(lines):
        m = _GROUP_START_RE.search(line)
        if m:
            if open_step is not None:
                # implicit close on next start
                open_step["end_line"] = i
                steps.append(open_step)
            open_step = {
                "name": m.group(1).strip()[:200],
                "start_line": i + 1,
                "end_line": None,
            }
            continue
        if _GROUP_END_RE.search(line) and open_step is not None:
            open_step["end_line"] = i + 1
            steps.append(open_step)
            open_step = None
    if open_step is not None:
        open_step["end_line"] = len(lines)
        steps.append(open_step)
    return {"steps": steps, "step_count": len(steps)}


# ----- Dispatcher + obs-token check -----

_TOOLS = {
    "get_log_metadata": "metadata",
    "search_log": "search",
    "get_lines": "lines",
    "get_tail": "tail",
    "get_head": "head",
    "find_error_blocks": "find",
    "list_github_steps": "steps",
}


def dispatch(
    tool_name: str,
    arguments: dict,
    *,
    raw_path: Path,
    case_meta: dict,
    budget: dict,
) -> dict:
    if tool_name not in _TOOLS:
        raise ValueError(f"unknown tool: {tool_name}")
    if tool_name == "get_log_metadata":
        return get_log_metadata(raw_path=raw_path, case_meta=case_meta)
    if tool_name == "search_log":
        return search_log(raw_path=raw_path, arguments=arguments, budget=budget)
    if tool_name == "get_lines":
        return get_lines(raw_path=raw_path, arguments=arguments, budget=budget)
    if tool_name == "get_tail":
        return get_tail(raw_path=raw_path, arguments=arguments, budget=budget)
    if tool_name == "get_head":
        return get_head(raw_path=raw_path, arguments=arguments, budget=budget)
    if tool_name == "find_error_blocks":
        return find_error_blocks(raw_path=raw_path, arguments=arguments, budget=budget)
    if tool_name == "list_github_steps":
        return list_github_steps(raw_path=raw_path, arguments=arguments, budget=budget)
    raise AssertionError("unreachable")


def observation_token_estimate(observation: dict) -> int:
    """Token-cost estimate for an observation, used to enforce
    `max_total_observation_tokens` and `max_single_observation_tokens`."""
    return estimate_tokens(json.dumps(observation, ensure_ascii=False))


def cap_observation(observation: dict, *, max_tokens: int) -> dict:
    """If an observation exceeds max_tokens, return a truncated wrapper
    rather than truncating arbitrary text. Caller can decide what to do."""
    if observation_token_estimate(observation) <= max_tokens:
        return observation
    # Return a truncated stub the agent can recognize.
    return {
        "_truncated": True,
        "reason": f"observation_tokens > max_single_observation_tokens ({max_tokens})",
        "tool_keys_present": sorted(observation.keys())
                              if isinstance(observation, dict) else None,
    }
