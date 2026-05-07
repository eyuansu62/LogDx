"""
Run a root-cause diagnoser over context outputs from previous milestones.

Pipeline:
    method context (raw/tail/grep/rtk-*/llm-summary-*)
      -> safe case metadata (NO failure_category, NO ground truth)
      -> diagnoser (mock or command provider)
      -> diagnosis JSON
      -> per-case JSON + per-method JSONL

Privacy / anti-leakage guarantees enforced here:
    * This module does not read cases/<split>/<case_id>/ground_truth.json.
    * This module does not pass `failure_category` from case.json to the
      diagnoser. Only the safe-allow-listed fields are forwarded.

Usage:
    python tools/run_diagnosis.py --split dev --diagnoser mock \\
        --context-method all
    python tools/run_diagnosis.py --split dev --diagnoser command \\
        --command "$DIAGNOSIS_COMMAND" --context-method grep \\
        --diagnoser-name my-debugger-v1
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
SCHEMA_PATH = ROOT / "schemas" / "diagnosis.schema.json"
DEFAULT_PROMPT_PATH = ROOT / "prompts" / "debugger_v1.md"

# Fields from case.json that are safe to pass to a diagnoser. Anything
# close to the answer (e.g. `failure_category`, `notes`) is omitted.
SAFE_CASE_METADATA_KEYS = (
    "case_id", "repo", "source", "workflow_name", "job_name", "framework",
)

# Manifests that should not be treated as context methods even if they
# happen to live under results/<split>/.
METHOD_EXCLUDE_PREFIXES = ("eval_",)

CATEGORY_ENUM = {
    "test_assertion", "compile_error", "type_error",
    "lint_failure", "formatting_failure",
    "dependency_install", "docker_build",
    "github_actions_config", "permission_or_secret",
    "network_or_flaky", "timeout_or_oom",
    "unknown", "other",
}

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


def load_safe_case_metadata(cases_dir: Path, split: str, case_id: str) -> dict:
    case_json = cases_dir / split / case_id / "case.json"
    if not case_json.exists():
        return {"case_id": case_id}
    full = json.loads(case_json.read_text(encoding="utf-8"))
    safe = {k: full[k] for k in SAFE_CASE_METADATA_KEYS if k in full}
    # Hard guarantee: failure_category never leaves this function.
    safe.pop("failure_category", None)
    return safe


def discover_manifests(results_dir: Path, split: str) -> list[str]:
    split_dir = results_dir / split
    methods: list[str] = []
    for p in sorted(split_dir.glob("*.jsonl")):
        stem = p.stem
        if any(stem.startswith(pfx) for pfx in METHOD_EXCLUDE_PREFIXES):
            continue
        # Skip debug outputs of baselines, keep only canonical manifests.
        if ".debug." in p.name:
            continue
        # Ignore any diagnosis sub-manifests (they live under diagnoses/).
        methods.append(stem)
    return methods


def load_manifest_rows(results_dir: Path, split: str, method: str) -> list[dict]:
    path = results_dir / split / f"{method}.jsonl"
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def validate_diagnosis(row: dict) -> None:
    """Minimal structural validation, always applied. Full jsonschema
    validation is applied when the library is installed."""
    if row.get("mode") != "root_cause_diagnosis":
        raise ValueError(f"[{row.get('case_id')}] mode must be root_cause_diagnosis")
    cat = row.get("root_cause_category")
    if cat not in CATEGORY_ENUM:
        raise ValueError(
            f"[{row.get('case_id')}] root_cause_category {cat!r} "
            f"not in {sorted(CATEGORY_ENUM)}"
        )
    conf = row.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
        raise ValueError(
            f"[{row.get('case_id')}] confidence must be number in [0,1], got {conf!r}"
        )
    for i, ev in enumerate(row.get("evidence", [])):
        if not isinstance(ev, dict) or "quote" not in ev or "reason" not in ev:
            raise ValueError(
                f"[{row.get('case_id')}] evidence[{i}] must have quote+reason"
            )
    if _HAS_JSONSCHEMA and SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(row, schema)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Mock diagnoser
# ---------------------------------------------------------------------------


# Pattern → (category, short hypothesis template). Order matters: pick the
# earliest match so "dubious ownership" beats generic "fatal".
MOCK_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("permission_or_secret",
        re.compile(r"fatal:\s+detected dubious ownership", re.IGNORECASE),
        "Git refused to operate on the workspace due to a dubious-ownership check."),
    ("formatting_failure",
        re.compile(r"prettier|yarn prettier-all|prettier-check", re.IGNORECASE),
        "Prettier reports files that are not formatted according to project configuration."),
    ("type_error",
        re.compile(r"\bmypy\b|stubtest|\[attr-defined\]|\[no-untyped-call\]|: error:.*\[", re.IGNORECASE),
        "Static type checker reported errors."),
    ("compile_error",
        re.compile(r"error\[E\d+\]|trybuild|mismatched types|panicked at", re.IGNORECASE),
        "Compiler or trybuild compile-fail test reports an error."),
    ("test_assertion",
        re.compile(r"^FAILED\s|--- FAIL:|AssertionError|Traceback|E\s+[A-Z]\w*(?:Error|Warning|Exception):", re.MULTILINE),
        "A runtime test failed with an assertion or exception."),
    ("lint_failure",
        re.compile(r"\beslint\b|clippy|ruff\b", re.IGNORECASE),
        "A linter reported failures."),
    ("docker_build",
        re.compile(r"docker buildx|failed to solve|Dockerfile", re.IGNORECASE),
        "Docker build failed."),
    ("dependency_install",
        re.compile(r"npm ERR!|pnpm ERR!|pip (ERROR|error): Could not install|Could not find a version", re.IGNORECASE),
        "Dependency installation failed."),
    ("network_or_flaky",
        re.compile(r"rate limit|connection (refused|reset|timed out)|network error", re.IGNORECASE),
        "Transient network / flaky error."),
    ("timeout_or_oom",
        re.compile(r"\bOut of memory\b|Killed\b|The operation was canceled\.|timeout", re.IGNORECASE),
        "Job was killed, timed out, or ran out of memory."),
    ("github_actions_config",
        re.compile(r"##\[error\]The action .* failed|invalid workflow", re.IGNORECASE),
        "GitHub Actions configuration error."),
]


def _mock_pick_evidence(ctx: str, pattern: re.Pattern[str]) -> tuple[str, str]:
    m = pattern.search(ctx)
    if not m:
        return "", ""
    start = ctx.rfind("\n", 0, m.start()) + 1
    end = ctx.find("\n", m.end())
    line = ctx[start:end if end >= 0 else m.end() + 80]
    line = line.strip()
    if len(line) > 200:
        line = line[:200]
    return line, f"Matches the {pattern.pattern!r} pattern used by the mock diagnoser."


_FILE_RE = re.compile(r"([\w./-]+\.(?:py|rs|ts|tsx|js|jsx|go|java|rb))")
_TEST_RES = (
    re.compile(r"^FAILED\s+([\w./:-]+::[\w./:-]+)"),
    re.compile(r"^--- FAIL:\s+(\S+)"),
    re.compile(r"([\w./-]+::test_\w+)"),
)


_MOCK_MAX_LINE_LEN = 2000  # skip anything longer to avoid regex backtracking
                           # on pathological progress-bar lines (pytest dots etc.)


def _mock_extract_files_and_tests(ctx: str) -> tuple[list[str], list[str]]:
    """Scan at most the first 5000 lines of context. Lines longer than
    _MOCK_MAX_LINE_LEN (2000) are skipped because pytest-style progress
    bars can push a single line past 100k chars and trigger quadratic
    backtracking in the simple regex we use here. Mock is a smoke test,
    not a real diagnoser — missing one test name on such a line is OK."""
    files: list[str] = []
    tests: list[str] = []
    seen_files: set[str] = set()
    seen_tests: set[str] = set()
    for i, line in enumerate(ctx.splitlines()):
        if i >= 5000:
            break
        if len(line) > _MOCK_MAX_LINE_LEN:
            continue
        if len(files) < 6:
            for m in _FILE_RE.finditer(line):
                path = m.group(1)
                if "/" in path and path not in seen_files:
                    seen_files.add(path); files.append(path)
                    if len(files) >= 6:
                        break
        if len(tests) < 4:
            for pat in _TEST_RES:
                m = pat.search(line)
                if m:
                    ident = m.group(1)
                    if ident and ident not in seen_tests:
                        seen_tests.add(ident); tests.append(ident)
                    if len(tests) >= 4:
                        break
        if len(files) >= 6 and len(tests) >= 4:
            break
    return files, tests


def diagnose_mock(
    *, context_text: str, safe_metadata: dict, case_id: str,
    context_method: str,
) -> dict:
    """Deterministic pattern-based diagnoser. Not a real model. The goal is
    to exercise the schema and the evaluator, not to produce accurate
    diagnoses. Real benchmarking goes through the command provider."""
    for category, pat, hypothesis in MOCK_PATTERNS:
        if pat.search(context_text):
            quote, reason = _mock_pick_evidence(context_text, pat)
            files, tests = _mock_extract_files_and_tests(context_text)
            # Confidence scales roughly with how much evidence we saw,
            # capped so we don't walk the full text for large inputs.
            hits = 0
            for _ in pat.finditer(context_text):
                hits += 1
                if hits >= 8:
                    break
            confidence = min(0.80, 0.45 + 0.05 * hits)
            return {
                "summary": (
                    f"{hypothesis} Detected by pattern {pat.pattern!r} "
                    f"in the {context_method} context."
                ),
                "root_cause_category": category,
                "root_cause": hypothesis,
                "confidence": round(confidence, 3),
                "relevant_files": files,
                "relevant_tests": tests,
                "evidence": ([{"quote": quote, "reason": reason}] if quote else []),
                "suggested_fix": "",
            }
    # Nothing matched.
    return {
        "summary": (
            "The provided context does not contain any recognizable failure "
            "signal. The mock diagnoser cannot identify a root cause."
        ),
        "root_cause_category": "unknown",
        "root_cause": "unknown",
        "confidence": 0.0,
        "relevant_files": [],
        "relevant_tests": [],
        "evidence": [],
        "suggested_fix": "Inspect the full CI log.",
    }


# ---------------------------------------------------------------------------
# Command diagnoser
# ---------------------------------------------------------------------------


def diagnose_command(
    *, context_text: str, safe_metadata: dict, case_id: str,
    context_method: str, command: str, prompt_text: str,
) -> dict:
    payload = {
        "case_id": case_id,
        "context_method": context_method,
        "prompt": prompt_text,
        "context": context_text,
        "safe_case_metadata": safe_metadata,
        "expected_output_schema": "schemas/diagnosis.schema.json",
    }
    argv = shlex.split(command)
    res = subprocess.run(
        argv,
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        timeout=180,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"diagnosis command exited {res.returncode}: "
            f"{(res.stderr or b'').decode('utf-8', 'replace')[:600]}"
        )
    try:
        out = json.loads(res.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"diagnosis command returned non-JSON: {e}. "
            f"First 400 chars: {res.stdout[:400]!r}"
        ) from e
    # Best-effort normalization — fill in missing pieces with conservative
    # defaults so the schema is satisfied, but never overwrite what the shim
    # returned.
    normalized = {
        "summary": out.get("summary", ""),
        "root_cause_category": out.get("root_cause_category", "unknown"),
        "root_cause": out.get("root_cause", "unknown"),
        "confidence": float(out.get("confidence", 0.0) or 0.0),
        "relevant_files": list(out.get("relevant_files", []) or []),
        "relevant_tests": list(out.get("relevant_tests", []) or []),
        "evidence": list(out.get("evidence", []) or []),
        "suggested_fix": out.get("suggested_fix", ""),
    }
    if normalized["root_cause_category"] not in CATEGORY_ENUM:
        normalized["root_cause_category"] = "other"
    normalized["confidence"] = max(0.0, min(1.0, normalized["confidence"]))
    return normalized


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def build_row(
    *, case_id: str, context_method: str, diagnoser: str,
    diagnosis_body: dict, context_path: Path, context_text: str,
    prompt_sha: str, runtime_ms: float, provider_name: str,
    command_str: str | None, cache_key: str | None,
    provider_error: str | None,
) -> dict:
    """Build the per-case diagnosis row. The row captures first-compute
    facts only — there is no `cache_hit` field because reruns that pull
    from cache re-emit the stored row verbatim. Cache activity is
    reported separately in the run summary printed to stdout."""
    proc_tokens = 0  # mock has no processing cost; command may report later
    out_tokens = estimate_tokens(json.dumps(diagnosis_body, ensure_ascii=False))
    row = {
        "case_id": case_id,
        "context_method": context_method,
        "diagnoser": diagnoser,
        "mode": "root_cause_diagnosis",
        **diagnosis_body,
        "input": {
            "context_path": str(context_path.relative_to(ROOT)),
            "context_tokens_estimate": estimate_tokens(context_text),
        },
        "usage": {
            "processing_tokens_estimate": proc_tokens,
            "output_tokens_estimate": out_tokens,
        },
        "metadata": {
            "provider": provider_name,
            "prompt_sha256": prompt_sha,
            "runtime_ms": round(runtime_ms, 3),
            "cache_key": cache_key,
            "provider_error": provider_error,
            "command": command_str,
        },
    }
    return row


def cache_key_for(
    *, case_id: str, context_method: str, context_sha: str, prompt_sha: str,
    provider: str, diagnoser: str, command_str: str | None,
) -> str:
    parts = {
        "case_id": case_id,
        "context_method": context_method,
        "context_sha": context_sha,
        "prompt_sha": prompt_sha,
        "provider": provider,
        "diagnoser": diagnoser,
        "command": command_str or "",
    }
    norm = json.dumps(parts, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return sha256_text(norm)


def run(
    *, split: str, diagnoser_provider: str, diagnoser_name: str,
    context_method: str, results_dir: Path, cases_dir: Path,
    prompt_path: Path, command_str: str | None,
    strict: bool, no_cache: bool, cache_errors: bool,
) -> int:
    if not prompt_path.exists():
        print(f"ERROR: prompt not found: {prompt_path}", file=sys.stderr)
        return 1
    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt_sha = sha256_text(prompt_text)

    # Resolve the set of context methods to run against.
    if context_method == "all":
        methods = discover_manifests(results_dir, split)
    else:
        methods = [context_method]
    if not methods:
        print(f"WARNING: no context methods discovered in {results_dir / split}",
              file=sys.stderr)
        return 1

    diag_out_root = results_dir / split / "diagnoses" / diagnoser_name
    cache_dir = results_dir / split / ".cache" / "diagnosis"

    had_failure = False
    for method in methods:
        rows = load_manifest_rows(results_dir, split, method)
        if not rows:
            print(f"  skip {method}: empty or missing manifest", file=sys.stderr)
            continue
        method_dir = diag_out_root / method
        method_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = diag_out_root / f"{method}.jsonl"

        out_rows: list[dict] = []
        method_cache_hits = 0
        method_cache_misses = 0
        for m_row in rows:
            case_id = m_row["case_id"]
            ctx_path = ROOT / m_row["context_path"]
            if not ctx_path.exists():
                print(f"  skip {method}/{case_id}: context file missing "
                      f"({ctx_path})", file=sys.stderr)
                continue
            ctx_text = ctx_path.read_text(encoding="utf-8", errors="replace")
            ctx_sha = sha256_text(ctx_text)
            safe_meta = load_safe_case_metadata(cases_dir, split, case_id)

            key = cache_key_for(
                case_id=case_id, context_method=method,
                context_sha=ctx_sha, prompt_sha=prompt_sha,
                provider=diagnoser_provider, diagnoser=diagnoser_name,
                command_str=command_str,
            )
            cache_path = cache_dir / f"{key}.json"
            cached_row: dict | None = None
            if not no_cache and cache_path.exists():
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                    # Older caches stored {"diagnosis": body}; we now store
                    # the full row under "row". Honor the new layout; treat
                    # the old layout as a miss so the new row gets built and
                    # re-cached.
                    if isinstance(cached, dict) and "row" in cached:
                        cached_row = cached["row"]
                except json.JSONDecodeError:
                    cached_row = None

            if cached_row is not None:
                row = cached_row
                method_cache_hits += 1
            else:
                provider_error: str | None = None
                t0 = time.perf_counter()
                try:
                    if diagnoser_provider == "mock":
                        diag_body = diagnose_mock(
                            context_text=ctx_text, safe_metadata=safe_meta,
                            case_id=case_id, context_method=method,
                        )
                    elif diagnoser_provider == "command":
                        if not command_str:
                            raise ValueError(
                                "--command is required when --diagnoser command"
                            )
                        diag_body = diagnose_command(
                            context_text=ctx_text, safe_metadata=safe_meta,
                            case_id=case_id, context_method=method,
                            command=command_str, prompt_text=prompt_text,
                        )
                    else:
                        raise ValueError(
                            f"unknown diagnoser provider: {diagnoser_provider}"
                        )
                except Exception as e:
                    provider_error = f"{type(e).__name__}: {e}"
                    if strict:
                        print(f"FAIL {method}/{case_id}: {provider_error}",
                              file=sys.stderr)
                        return 1
                    diag_body = {
                        "summary": "Diagnoser failed. See metadata.provider_error.",
                        "root_cause_category": "unknown",
                        "root_cause": "unknown",
                        "confidence": 0.0,
                        "relevant_files": [],
                        "relevant_tests": [],
                        "evidence": [],
                        "suggested_fix": "",
                    }
                runtime_ms = (time.perf_counter() - t0) * 1000

                row = build_row(
                    case_id=case_id, context_method=method,
                    diagnoser=diagnoser_name, diagnosis_body=diag_body,
                    context_path=ctx_path, context_text=ctx_text,
                    prompt_sha=prompt_sha, runtime_ms=runtime_ms,
                    provider_name=diagnoser_provider,
                    command_str=command_str, cache_key=key,
                    provider_error=provider_error,
                )
                method_cache_misses += 1

                if provider_error is None or cache_errors:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(
                        json.dumps({"cache_key": key, "row": row},
                                    ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )

            try:
                validate_diagnosis(row)
            except Exception as e:
                print(f"FAIL validation {method}/{case_id}: {e}", file=sys.stderr)
                had_failure = True
                if strict:
                    return 1
                continue

            # Per-case JSON beside the JSONL manifest.
            per_case_path = method_dir / f"{case_id}.json"
            per_case_path.write_text(
                json.dumps(row, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            out_rows.append(row)

        with manifest_path.open("w", encoding="utf-8") as f:
            for row in out_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  {method}: wrote {len(out_rows)} diagnoses to "
              f"{manifest_path.relative_to(ROOT)} "
              f"({method_cache_hits} cache hit, {method_cache_misses} miss)")

    if not _HAS_JSONSCHEMA:
        print("note: jsonschema not installed — used structural checks only "
              "(pip install jsonschema for full schema validation)",
              file=sys.stderr)
    return 1 if had_failure else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Run a root-cause diagnoser over method contexts. "
            "WARNING: --diagnoser command may send CI log-derived contexts "
            "to an external model depending on the supplied shim; verify "
            "contents are safe to share first."
        )
    )
    ap.add_argument("--split", default="dev")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT_PATH)
    ap.add_argument("--diagnoser", default="mock", choices=["mock", "command"],
                    help="Provider kind.")
    ap.add_argument("--diagnoser-name", default=None,
                    help="Name used in output paths "
                         "(default: debugger-v1-mock / debugger-v1-command).")
    ap.add_argument("--command", default=None,
                    help="Shell command for --diagnoser command.")
    ap.add_argument("--context-method", default="all",
                    help="One method name or 'all' to discover from "
                         "results/<split>/*.jsonl (default: all).")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--cache-errors", action="store_true",
                    help="Also cache provider errors (off by default).")
    ap.add_argument("--strict", action="store_true",
                    help="Abort on first provider or validation error.")
    args = ap.parse_args(argv)

    diagnoser_name = args.diagnoser_name or (
        "debugger-v1-mock" if args.diagnoser == "mock"
        else "debugger-v1-command"
    )
    return run(
        split=args.split, diagnoser_provider=args.diagnoser,
        diagnoser_name=diagnoser_name,
        context_method=args.context_method,
        results_dir=args.results_dir, cases_dir=args.cases_dir,
        prompt_path=args.prompt, command_str=args.command,
        strict=args.strict, no_cache=args.no_cache,
        cache_errors=args.cache_errors,
    )


if __name__ == "__main__":
    raise SystemExit(main())
