"""
Run an LLM-generated summary as a context-provider baseline.

This implements a map-reduce pipeline:

    raw.log -> chunk -> MAP prompt -> per-chunk bullet list
                                   \
                                    REDUCE prompt -> final markdown summary

Providers:
    - mock:    deterministic local heuristic (no API, no network). Used for
               CI and acceptance. It is NOT a real benchmark method.
    - command: shell out to a user-supplied command. The command receives
               JSON on stdin and returns JSON on stdout. See docs/methods/
               llm_summary.md for the contract.

Privacy: the default provider is `mock`. `--provider command` is
explicit and the CLI warns that raw CI logs may be sent to an external
model.

Ground truth is NEVER read by this runner. It only touches
cases/<split>/<case_id>/raw.log (and, optionally, case.json for
non-answer metadata).

Outputs:
    results/<split>/<method>/<case_id>.txt                 final context
    results/<split>/<method>/chunks/<case_id>/map_NNN.json per-chunk MAP output
    results/<split>/<method>/chunks/<case_id>/reduce.json  REDUCE output
    results/<split>/<method>.jsonl                         per-case manifest
    results/cache/<method>/<cache_key>.json                one per LLM call

Usage:
    python tools/run_llm_summary_baseline.py --split dev --provider mock \\
        --method llm-summary-v1-mock
    python tools/run_llm_summary_baseline.py --split dev --provider command \\
        --command "$LLM_SUMMARY_COMMAND" --method llm-summary-v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "method_output.schema.json"
PROMPTS_DIR = ROOT / "prompts"

DEFAULT_CHUNK_LINES = 400
DEFAULT_CHUNK_OVERLAP = 20
DEFAULT_MAX_MAP_CHARS = 8000
DEFAULT_MAX_REDUCE_CHARS = 12000
DEFAULT_TEMPERATURE = 0.0

try:
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def prefix_with_line_numbers(lines: list[str]) -> list[str]:
    return [f"L{i:06d}: {line}" for i, line in enumerate(lines, start=1)]


def chunk_lines(
    prefixed: list[str],
    chunk_size: int,
    overlap: int,
) -> list[tuple[int, list[str]]]:
    """Return [(chunk_index, chunk_lines), ...]. Chunks are non-empty."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")
    out: list[tuple[int, list[str]]] = []
    i = 0
    idx = 0
    n = len(prefixed)
    while i < n:
        end = min(n, i + chunk_size)
        out.append((idx, prefixed[i:end]))
        idx += 1
        if end == n:
            break
        i = end - overlap
    return out


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def cache_key(parts: dict[str, Any]) -> str:
    """Deterministic cache key over a dict of scalars/strings."""
    norm = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_text(norm)


def load_cached(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


FAILURE_KEYWORDS = re.compile(
    r"error|failed|failure|traceback|exception|assert|panic|exit code|"
    r"##\[error\]|fatal:|^FAIL\b|--- FAIL|✘|✖|✗",
    re.IGNORECASE | re.MULTILINE,
)


def provider_mock(messages: list[dict], stage: str, **_: object) -> dict:
    """Deterministic local heuristic: scan user content for failure-keyword
    lines (chunks already carry L000123 prefixes) and emit category bullets.

    This is NOT a real LLM. It exists so the end-to-end code path can run
    without API keys. Mock output intentionally keeps exact strings so that
    the schema/evaluator/reporting pipeline can be verified.
    """
    user = next((m for m in messages if m.get("role") == "user"), {})
    content = user.get("content") or ""

    if stage == "map":
        bullets: list[str] = []
        for raw_line in content.splitlines():
            m = re.match(r"^L(\d+):\s?(.*)$", raw_line)
            if not m:
                continue
            line_no = m.group(1)
            body = m.group(2)
            if not FAILURE_KEYWORDS.search(body):
                continue
            category = _mock_category(body)
            body_short = body.strip()
            if len(body_short) > 200:
                body_short = body_short[:200] + "…"
            bullets.append(f"- [{category}] `{body_short}`  (lines: L{line_no})")
        text = "\n".join(bullets) if bullets else "NO_RELEVANT_FAILURE_SIGNAL"
        return {
            "content": text,
            "provider": "mock",
            "model": None,
            "usage": {
                "input_tokens": estimate_tokens(content),
                "output_tokens": estimate_tokens(text),
            },
        }

    # reduce stage: collapse to final markdown structure
    sections = {
        "Primary Failure": [],
        "Critical Evidence": [],
        "Failed Tests / Checks": [],
        "Relevant Files and Locations": [],
        "Commands and Exit Codes": [],
        "Possible Root Cause": [],
        "Uncertainties / Missing Context": [],
    }
    for ln in content.splitlines():
        if not ln.strip().startswith("- ["):
            continue
        m = re.match(r"- \[([A-Z_]+)\]\s+(.*)", ln)
        if not m:
            continue
        cat, rest = m.group(1), m.group(2)
        sec = _mock_section_for_category(cat)
        sections[sec].append(f"- {rest}")
    # De-duplicate within each section
    for k, vals in list(sections.items()):
        seen = set(); unique = []
        for v in vals:
            if v in seen:
                continue
            seen.add(v); unique.append(v)
        sections[k] = unique
    body = ["# CI Failure Summary", ""]
    for header, items in sections.items():
        body.append(f"## {header}")
        body.append("")
        if items:
            body.extend(items[:40])
        else:
            body.append("- _(none identified)_")
        body.append("")
    text = "\n".join(body)
    return {
        "content": text,
        "provider": "mock",
        "model": None,
        "usage": {
            "input_tokens": estimate_tokens(content),
            "output_tokens": estimate_tokens(text),
        },
    }


def _mock_category(body: str) -> str:
    low = body.lower()
    if "##[error]" in low or "process completed with exit code" in low:
        return "GHA_ERROR"
    if re.search(r"^FAILED\b|--- FAIL:|^FAIL\s", body):
        return "FAILED_TEST"
    if "panicked at" in low:
        return "EXCEPTION"
    if "traceback" in low or "assertionerror" in low or body.strip().startswith("E "):
        return "ASSERTION"
    if re.search(r"^\s*error(\[E\d+\])?:", body) or re.search(r":\d+:\s*error:", body):
        return "COMPILE_ERROR"
    if body.strip().startswith("fatal:"):
        return "EXCEPTION"
    if "exit code" in low:
        return "EXIT_CODE"
    if re.search(r"\.(py|js|ts|rs|go|java):\d+", body):
        return "STACK_LOCATION"
    return "ASSERTION"


def _mock_section_for_category(cat: str) -> str:
    return {
        "FAILED_TEST":    "Failed Tests / Checks",
        "STACK_LOCATION": "Relevant Files and Locations",
        "EXIT_CODE":      "Commands and Exit Codes",
        "GHA_ERROR":      "Commands and Exit Codes",
        "COMMAND":        "Commands and Exit Codes",
        "REMEDIATION":    "Possible Root Cause",
        "UNCERTAINTY":    "Uncertainties / Missing Context",
    }.get(cat, "Critical Evidence")


def provider_command(messages: list[dict], stage: str, *,
                     command: str, temperature: float,
                     max_output_chars: int, case_id: str,
                     prompt_version: str) -> dict:
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_output_chars": max_output_chars,
        "metadata": {
            "case_id": case_id,
            "prompt_version": prompt_version,
            "stage": stage,
        },
    }
    argv = shlex.split(command)
    try:
        res = subprocess.run(
            argv,
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"LLM command timed out after 180s: {command}") from e
    if res.returncode != 0:
        raise RuntimeError(
            f"LLM command exited {res.returncode}: "
            f"{(res.stderr or b'').decode('utf-8', 'replace')[:600]}"
        )
    try:
        out = json.loads(res.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"LLM command returned non-JSON stdout: {e}. "
            f"First 400 chars: {res.stdout[:400]!r}"
        ) from e
    if "content" not in out:
        raise RuntimeError(f"LLM command response missing 'content' field: {out}")
    return out


ProviderFn = Callable[..., dict]


def make_provider(name: str, command: str | None) -> ProviderFn:
    if name == "mock":
        return provider_mock
    if name == "command":
        if not command:
            raise ValueError("--command is required when --provider=command")
        def _wrap(messages, stage, **kw):
            return provider_command(messages, stage, command=command, **kw)
        return _wrap
    raise ValueError(f"unknown provider: {name}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def read_prompts() -> tuple[str, str]:
    map_p = (PROMPTS_DIR / "llm_summary_v1_map.md").read_text(encoding="utf-8")
    red_p = (PROMPTS_DIR / "llm_summary_v1_reduce.md").read_text(encoding="utf-8")
    return map_p, red_p


def validate_row(row: dict) -> None:
    if row["mode"] != "context_provider":
        raise ValueError(f"[{row['case_id']}] mode must be context_provider")
    if not (0.0 <= row["reduction_ratio"] <= 1.0):
        raise ValueError(
            f"[{row['case_id']}] reduction_ratio out of [0,1]: {row['reduction_ratio']}"
        )
    if _HAS_JSONSCHEMA and SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(row, schema)  # type: ignore[arg-type]


def run_one_case(
    *,
    case_dir: Path,
    method: str,
    provider_name: str,
    provider_fn: ProviderFn,
    map_prompt: str,
    reduce_prompt: str,
    map_prompt_sha: str,
    reduce_prompt_sha: str,
    chunk_size: int,
    overlap: int,
    max_map_chars: int,
    max_reduce_chars: int,
    temperature: float,
    results_dir: Path,
    split: str,
    force: bool,
    command_str: str | None,
) -> dict:
    case_id = case_dir.name
    raw_path = case_dir / "raw.log"
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    raw_sha = sha256_text(raw_text)
    raw_lines = raw_text.splitlines()
    input_line_count = raw_text.count("\n")
    input_byte_size = len(raw_text.encode("utf-8"))

    prefixed = prefix_with_line_numbers(raw_lines)
    chunks = chunk_lines(prefixed, chunk_size, overlap)

    method_results_dir = results_dir / split / method
    chunks_dir = method_results_dir / "chunks" / case_id
    chunks_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = results_dir / "cache" / method

    map_outputs: list[str] = []
    non_empty = 0
    total_input_tokens = 0
    total_output_tokens = 0
    usage_reported = False
    usage_estimated = False
    cache_hits = 0
    cache_misses = 0

    for idx, chunk in chunks:
        chunk_text = "\n".join(chunk)
        chunk_sha = sha256_text(chunk_text)
        key_parts = {
            "case_id": case_id, "raw_sha": raw_sha,
            "prompt_version": "llm_summary_v1",
            "prompt_sha": map_prompt_sha,
            "provider": provider_name,
            "method": method, "chunk_index": idx,
            "chunk_sha": chunk_sha,
            "temperature": temperature,
            "max_output_chars": max_map_chars,
            "stage": "map",
        }
        key = cache_key(key_parts)
        cache_path = cache_dir / f"{key}.json"
        cached = None if force else load_cached(cache_path)
        if cached is not None:
            resp = cached["response"]
            cache_hits += 1
        else:
            messages = [
                {"role": "system", "content": map_prompt},
                {"role": "user",   "content": chunk_text},
            ]
            resp = provider_fn(
                messages, "map",
                temperature=temperature,
                max_output_chars=max_map_chars,
                case_id=case_id,
                prompt_version="llm_summary_v1",
            )
            write_cache(cache_path, {"key_parts": key_parts, "response": resp})
            cache_misses += 1

        chunk_out_path = chunks_dir / f"map_{idx:03d}.json"
        chunk_out_path.write_text(
            json.dumps({"chunk_index": idx, **resp}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        content = (resp.get("content") or "").strip()
        if content and content != "NO_RELEVANT_FAILURE_SIGNAL":
            map_outputs.append(f"### chunk {idx}\n{content}")
            non_empty += 1

        usage = resp.get("usage") or {}
        if "input_tokens" in usage and "output_tokens" in usage:
            total_input_tokens += int(usage["input_tokens"])
            total_output_tokens += int(usage["output_tokens"])
            if provider_name == "mock":
                usage_estimated = True
            else:
                usage_reported = True
        else:
            total_input_tokens += estimate_tokens(chunk_text)
            total_output_tokens += estimate_tokens(content)
            usage_estimated = True

    # Reduce
    if not map_outputs:
        final_context = (
            "# CI Failure Summary\n\n"
            "## Primary Failure\n\n- _(none identified)_\n"
            "## Critical Evidence\n\n- _(none identified)_\n"
            "## Failed Tests / Checks\n\n- _(none identified)_\n"
            "## Relevant Files and Locations\n\n- _(none identified)_\n"
            "## Commands and Exit Codes\n\n- _(none identified)_\n"
            "## Possible Root Cause\n\n- _(none identified)_\n"
            "## Uncertainties / Missing Context\n\n"
            "- No relevant failure signal was extracted from any chunk.\n"
        )
        reduce_response = {
            "content": final_context,
            "provider": provider_name,
            "model": None,
            "usage": {
                "input_tokens": 0,
                "output_tokens": estimate_tokens(final_context),
            },
        }
        (chunks_dir / "reduce.json").write_text(
            json.dumps({"synthetic_reduce": True, **reduce_response},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        usage_estimated = True
        total_input_tokens += reduce_response["usage"]["input_tokens"]
        total_output_tokens += reduce_response["usage"]["output_tokens"]
    else:
        reduce_input = "\n\n".join(map_outputs)
        key_parts = {
            "case_id": case_id, "raw_sha": raw_sha,
            "prompt_version": "llm_summary_v1",
            "prompt_sha": reduce_prompt_sha,
            "provider": provider_name,
            "method": method,
            "chunk_index": -1,
            "chunk_sha": sha256_text(reduce_input),
            "temperature": temperature,
            "max_output_chars": max_reduce_chars,
            "stage": "reduce",
        }
        key = cache_key(key_parts)
        cache_path = cache_dir / f"{key}.json"
        cached = None if force else load_cached(cache_path)
        if cached is not None:
            reduce_response = cached["response"]
            cache_hits += 1
        else:
            messages = [
                {"role": "system", "content": reduce_prompt},
                {"role": "user",   "content": reduce_input},
            ]
            reduce_response = provider_fn(
                messages, "reduce",
                temperature=temperature,
                max_output_chars=max_reduce_chars,
                case_id=case_id,
                prompt_version="llm_summary_v1",
            )
            write_cache(cache_path, {"key_parts": key_parts, "response": reduce_response})
            cache_misses += 1
        (chunks_dir / "reduce.json").write_text(
            json.dumps(reduce_response, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        final_context = (reduce_response.get("content") or "").rstrip() + "\n"

        usage = reduce_response.get("usage") or {}
        if "input_tokens" in usage and "output_tokens" in usage:
            total_input_tokens += int(usage["input_tokens"])
            total_output_tokens += int(usage["output_tokens"])
            if provider_name == "mock":
                usage_estimated = True
            else:
                usage_reported = True
        else:
            total_input_tokens += estimate_tokens(reduce_input)
            total_output_tokens += estimate_tokens(final_context)
            usage_estimated = True

    ctx_path = method_results_dir / f"{case_id}.txt"
    ctx_path.write_text(final_context, encoding="utf-8")
    output_byte_size = len(final_context.encode("utf-8"))
    output_line_count = final_context.count("\n")

    reduction_ratio = (
        0.0 if input_byte_size == 0
        else round(1 - output_byte_size / input_byte_size, 6)
    )
    reduction_ratio = max(0.0, min(1.0, reduction_ratio))

    usage_source = (
        "provider_reported" if usage_reported and not usage_estimated
        else ("estimated" if usage_estimated and not usage_reported else "mixed")
    )

    model = None
    for resp_like in (reduce_response,):
        if isinstance(resp_like, dict) and resp_like.get("model"):
            model = resp_like["model"]
            break

    row = {
        "case_id": case_id,
        "method": method,
        "mode": "context_provider",
        "raw_log_path": str(raw_path.relative_to(ROOT)),
        "context_path": str(ctx_path.relative_to(ROOT)),
        "input_line_count": input_line_count,
        "output_line_count": output_line_count,
        "input_byte_size": input_byte_size,
        "output_byte_size": output_byte_size,
        "reduction_ratio": reduction_ratio,
        "included_line_ranges": [],
        "line_mapping_available": False,
        "mapping_type": "text",
        "metadata": {
            "provider": provider_name,
            "model": model,
            "prompt_version": "llm_summary_v1",
            "map_prompt_sha256": map_prompt_sha,
            "reduce_prompt_sha256": reduce_prompt_sha,
            "temperature": temperature,
            "chunk_lines": chunk_size,
            "chunk_overlap_lines": overlap,
            "chunk_count": len(chunks),
            "non_empty_chunk_count": non_empty,
            # cache_hit_count / cache_miss_count deliberately OMITTED from
            # the row — they flip between runs and break byte-level
            # reproducibility (M7-D). Cache activity is logged to stdout
            # instead by the caller.
            "usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "usage_source": usage_source,
            },
            "final_context_tokens_estimate": estimate_tokens(final_context),
        },
    }
    if command_str:
        row["metadata"]["command"] = command_str
    validate_row(row)
    # cache_hits / cache_misses are run-level facts, kept out of the row
    # so reruns are byte-stable (M7-D acceptance).
    return row, cache_hits, cache_misses


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Run the llm-summary-v1 context-provider baseline. "
            "WARNING: --provider command may send raw CI logs to an external "
            "model depending on the supplied command. Ensure logs are safe to "
            "share before running."
        )
    )
    ap.add_argument("--split", default="dev")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--method", default="llm-summary-v1")
    ap.add_argument("--provider", default="mock", choices=["mock", "command"])
    ap.add_argument("--command", default=None,
                    help="Shell command invoked per LLM request "
                         "(required for --provider command).")
    ap.add_argument("--chunk-lines", type=int, default=DEFAULT_CHUNK_LINES)
    ap.add_argument("--chunk-overlap-lines", type=int, default=DEFAULT_CHUNK_OVERLAP)
    ap.add_argument("--max-map-output-chars", type=int, default=DEFAULT_MAX_MAP_CHARS)
    ap.add_argument("--max-reduce-output-chars", type=int, default=DEFAULT_MAX_REDUCE_CHARS)
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument("--force", action="store_true",
                    help="Ignore cache and re-call the provider.")
    ap.add_argument("--case-id", default=None,
                    help="Run only this case; manifest is written to "
                         "<method>.debug.<case_id>.jsonl.")
    ap.add_argument("--fail-fast", action="store_true")
    args = ap.parse_args(argv)

    provider_fn = make_provider(args.provider, args.command)
    map_prompt, reduce_prompt = read_prompts()
    map_sha = sha256_text(map_prompt)
    reduce_sha = sha256_text(reduce_prompt)

    cases_dir = args.cases_dir / args.split
    if not cases_dir.is_dir():
        print(f"ERROR: split dir not found: {cases_dir}", file=sys.stderr)
        return 1
    case_dirs = sorted(
        p for p in cases_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    if args.case_id:
        case_dirs = [p for p in case_dirs if p.name == args.case_id]
        if not case_dirs:
            print(f"ERROR: case_id {args.case_id!r} not found under {cases_dir}",
                  file=sys.stderr)
            return 1

    if args.provider == "command" and not args.command:
        print("ERROR: --command is required when --provider command", file=sys.stderr)
        return 1

    rows: list[dict] = []
    started = time.perf_counter()
    for case_dir in case_dirs:
        if not (case_dir / "raw.log").exists():
            print(f"  skip {case_dir.name}: no raw.log", file=sys.stderr)
            continue
        t0 = time.perf_counter()
        try:
            row, cache_hits, cache_misses = run_one_case(
                case_dir=case_dir,
                method=args.method,
                provider_name=args.provider,
                provider_fn=provider_fn,
                map_prompt=map_prompt,
                reduce_prompt=reduce_prompt,
                map_prompt_sha=map_sha,
                reduce_prompt_sha=reduce_sha,
                chunk_size=args.chunk_lines,
                overlap=args.chunk_overlap_lines,
                max_map_chars=args.max_map_output_chars,
                max_reduce_chars=args.max_reduce_output_chars,
                temperature=args.temperature,
                results_dir=args.results_dir,
                split=args.split,
                force=args.force,
                command_str=args.command,
            )
        except Exception as e:
            msg = f"FAIL {case_dir.name}: {e}"
            print(msg, file=sys.stderr)
            if args.fail_fast:
                return 1
            continue
        rows.append(row)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  {case_dir.name}: "
              f"{row['input_byte_size']:>7d} -> {row['output_byte_size']:>6d} bytes "
              f"(reduction {row['reduction_ratio']:.2%})  "
              f"chunks={row['metadata']['chunk_count']} "
              f"non_empty={row['metadata']['non_empty_chunk_count']}  "
              f"cache={cache_hits}hit/{cache_misses}miss  "
              f"[{elapsed:.0f}ms]")

    manifest_path = args.results_dir / args.split / f"{args.method}.jsonl"
    if args.case_id:
        manifest_path = manifest_path.with_suffix(f".debug.{args.case_id}.jsonl")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows to {manifest_path.relative_to(ROOT)}  "
          f"(provider={args.provider}, elapsed={(time.perf_counter()-started):.1f}s)")
    if not _HAS_JSONSCHEMA:
        print("note: jsonschema not installed — used structural checks only "
              "(pip install jsonschema for full schema validation)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
