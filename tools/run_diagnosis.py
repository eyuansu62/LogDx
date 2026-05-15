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
import os
import re
import shlex
import subprocess
import sys
import urllib.parse
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


def sha256_path(p: Path) -> str | None:
    """Read file bytes and return SHA256. Returns None if unreadable."""
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def diagnoser_config_sha256(
    diagnoser_name: str, explicit_path: Path | None = None
) -> str | None:
    """Per Codex 2026-06-08 F2 [high]: compute the on-disk SHA of the
    loaded diagnoser config so the cache key reflects config identity.

    Resolution mirrors `load_diagnoser_config`: explicit_path wins,
    otherwise fall back to `configs/diagnosers/<name>.json`. Returns
    None when the resolved path doesn't exist (no SHA contribution to
    the cache key)."""
    cfg_path = (
        explicit_path
        if explicit_path is not None
        else ROOT / "configs" / "diagnosers" / f"{diagnoser_name}.json"
    )
    if not cfg_path.exists():
        return None
    return sha256_path(cfg_path)


def shim_path_from_command(command_str: str | None) -> Path | None:
    """Per Codex 2026-06-08 F2 [high]: best-effort parse of a shell
    `command_str` to find the first existing .py file path. Returns
    None when not parseable or no .py file found.

    This lets the runner fold shim-implementation identity into the
    cache key for the canonical repo-local shims (e.g.
    `python3 examples/diagnosis_shim_openai.py`) so editing the shim
    invalidates cached rows that used the old implementation.
    Non-repo-local commands (e.g. an external binary) contribute
    nothing here; the cache key still includes the literal command
    string."""
    if not command_str:
        return None
    try:
        parts = shlex.split(command_str)
    except ValueError:
        return None
    for part in parts:
        if not part.endswith(".py"):
            continue
        p = Path(part)
        if p.is_file():
            return p
    return None


def shim_sha256_for_command(command_str: str | None) -> str | None:
    """SHA256 of the shim script referenced by command_str, if any."""
    p = shim_path_from_command(command_str)
    if p is None:
        return None
    return sha256_path(p)


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


class ProvenanceMismatchError(RuntimeError):
    """Per Codex 2026-05-27 F1 [high]: dedicated exception for fresh-row
    provenance mismatches (requested_model, endpoint, resolved_model,
    or mock-provider-under-real-config). Distinguished from generic
    RuntimeError so the runner can SKIP the output write entirely.

    Pre-fix, the surrounding broad `except Exception` caught these as
    normal provider failures and wrote a provider_error stub row to
    the manifest + per-case JSON. That still polluted the canonical
    `results/<split>/diagnoses/<diagnoser_name>/` location under
    the wrong identity — the exact thing the validators are meant
    to prevent. Now the runner catches ProvenanceMismatchError
    specifically, logs the mismatch, marks the run as failed, and
    skips the case (no row written, no cache update).
    """


class ShimCallError(RuntimeError):
    """Per Codex 2026-05-16 F1: raised when the diagnoser command exits
    non-zero. Carries opt-in metadata (notably `_model_info`) that the
    shim wrote to stdout even on its error path so the runner can
    preserve provenance for failed-but-attempted API calls.

    Without this, the existing exception path discarded stdout entirely
    on non-zero exit, so a row whose API call succeeded but whose
    content was malformed JSON landed in the manifest as
    `provider_error=...` with `metadata.model_info=null` — same as a
    no-call oversized-context skip. That broke the auditability claim
    for post-API failures.
    """

    def __init__(self, message: str, *,
                 model_info: dict | None = None,
                 provider_error_hint: str | None = None):
        super().__init__(message)
        self.model_info = model_info
        self.provider_error_hint = provider_error_hint


def _extract_shim_stdout_metadata(stdout_bytes: bytes) -> dict:
    """Try to parse the shim's stdout as a JSON envelope and pull
    underscore-prefixed opt-in metadata fields (`_model_info`,
    `_provider_error`). Returns {} if stdout isn't JSON or has no
    metadata. Used on the non-zero-exit path so shims that succeeded
    enough to know their model identity can preserve it. Per Codex
    2026-05-16 F1.
    """
    try:
        body = json.loads(stdout_bytes.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, AttributeError):
        return {}
    if not isinstance(body, dict):
        return {}
    out: dict = {}
    if isinstance(body.get("_model_info"), dict):
        out["_model_info"] = body["_model_info"]
    if body.get("_provider_error"):
        out["_provider_error"] = body["_provider_error"]
    return out


def diagnose_command(
    *, context_text: str, safe_metadata: dict, case_id: str,
    context_method: str, command: str, prompt_text: str,
    env: dict[str, str] | None = None,
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
        # Per Codex 2026-05-15 F1: when the caller computes an env
        # mapping (typically to inject the diagnoser-config's
        # requested_alias into the shim env var when the user hasn't),
        # use it. Falls back to inherited parent env otherwise.
        env=env,
    )
    if res.returncode != 0:
        # Per Codex 2026-05-16 F1: read stdout for opt-in metadata
        # before raising. A shim that reached the API and emitted
        # _model_info before failing on (e.g.) JSONDecodeError gets
        # to preserve provenance via this exception's `model_info`.
        partial = _extract_shim_stdout_metadata(res.stdout or b"")
        raise ShimCallError(
            f"diagnosis command exited {res.returncode}: "
            f"{(res.stderr or b'').decode('utf-8', 'replace')[:600]}",
            model_info=partial.get("_model_info"),
            provider_error_hint=partial.get("_provider_error"),
        )
    try:
        out = json.loads(res.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise ShimCallError(
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
    # Per Codex 2026-05-11 F2 [high]: preserve shim-provided opt-in
    # metadata under underscore-prefixed keys. `_model_info` records
    # which exact model/snapshot/base_url produced the row, so the
    # benchmark artifact is auditable (not just "ran some model from
    # env"). `_provider_error` is preserved as defense-in-depth even
    # though the F1 fix now makes shims exit non-zero for hard errors.
    if isinstance(out.get("_model_info"), dict):
        normalized["_model_info"] = out["_model_info"]
    if out.get("_provider_error"):
        normalized["_provider_error"] = out["_provider_error"]
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
    diagnoser_config_name: str | None = None,
    diagnoser_config_sha256_value: str | None = None,
    shim_sha256_value: str | None = None,
) -> dict:
    """Build the per-case diagnosis row. The row captures first-compute
    facts only — there is no `cache_hit` field because reruns that pull
    from cache re-emit the stored row verbatim. Cache activity is
    reported separately in the run summary printed to stdout."""
    proc_tokens = 0  # mock has no processing cost; command may report later
    out_tokens = estimate_tokens(json.dumps(diagnosis_body, ensure_ascii=False))
    try:
        ctx_path_str = str(context_path.relative_to(ROOT))
    except ValueError:
        # context_path outside ROOT (e.g. tests pointing at a tmp dir).
        # Same fallback pattern audit_context_privacy.py uses.
        ctx_path_str = str(context_path)
    # Lift shim-opt-in underscored hints out of diagnosis_body into
    # metadata so the on-disk row carries them in a stable location.
    # Per Codex 2026-05-11 [high]: `_model_info` records the actual
    # model/snapshot/base_url that produced this row (auditability);
    # `_provider_error` is preserved defense-in-depth even though the
    # F1 fix now makes shims exit non-zero for hard errors.
    diagnosis_clean = {k: v for k, v in diagnosis_body.items()
                        if not k.startswith("_")}
    model_info = diagnosis_body.get("_model_info")
    shim_provider_error = diagnosis_body.get("_provider_error")
    row = {
        "case_id": case_id,
        "context_method": context_method,
        "diagnoser": diagnoser,
        "mode": "root_cause_diagnosis",
        **diagnosis_clean,
        "input": {
            "context_path": ctx_path_str,
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
            # Per Codex 2026-05-17 F1 [high]: when the shim emits a
            # structured `_provider_error` taxonomy (e.g. `post_api_error:
            # JSONDecodeError ...` or `unsupported_context_too_large:
            # ...`), that classification is the PRIMARY persisted value.
            # The runner-wrapped subprocess message (e.g.
            # `ShimCallError: diagnosis command exited 1 ...`) goes into
            # `provider_error_detail` so downstream auditing can count
            # error classes by stable prefix without false matches from
            # the generic wrapper string. Previously this preferred the
            # wrapper and only appended the shim taxonomy as a suffix,
            # which made the model card's class counts unreliable.
            "provider_error": (
                shim_provider_error if shim_provider_error else provider_error
            ),
            "provider_error_detail": (
                provider_error if shim_provider_error and provider_error
                else None
            ),
            "command": command_str,
            "model_info": model_info,
            # Per Codex 2026-05-22 F1 [high]: when a reusable_template
            # config is used under a custom --diagnoser-name, record
            # BOTH the runtime output name (in row.diagnoser) and the
            # config's declared name (here) so an auditor can recover
            # the full provenance: "this row ran in directory
            # results/.../stub-debugger-v1/ but used the
            # example-debugger-v1 config".
            "diagnoser_config_name": (
                diagnoser_config_name
                if diagnoser_config_name and diagnoser_config_name != diagnoser
                else None
            ),
            # Per Codex 2026-06-08 F2 [high]: persist the loaded
            # diagnoser-config SHA + shim-implementation SHA so
            # `cache_hit_is_acceptable` can reject cached rows whose
            # config or shim has since changed. Legacy rows without
            # these fields pass back-compat (accepted on cache hit)
            # until canonical state is re-run; future strict-mode
            # validation can drop the back-compat path once all
            # canonical rows carry the fields.
            "diagnoser_config_sha256": diagnoser_config_sha256_value,
            "shim_sha256": shim_sha256_value,
        },
    }
    return row


class DiagnoserConfigError(Exception):
    """Raised when a caller-supplied diagnoser config disagrees with
    --diagnoser-name. Fail fast rather than silently dropping the
    config + degrading to legacy auto-discovery behaviour."""


def load_diagnoser_config(
    diagnoser_name: str, explicit_path: Path | None = None
) -> dict | None:
    """Load the diagnoser config from an explicit path or by auto-discovery.

    Per Codex 2026-05-15 F2: wrappers can load configs from arbitrary paths
    (`run_protocol_diagnosis_eval.py --diagnoser-config <path>`,
    `run_m6_experiment.py --config <path>`, etc.) but historically only
    `--diagnoser-name` was propagated to this runner. The child then
    re-discovered the config by name, which could mean (a) a different
    file altogether, or (b) no file at all when the wrapper's path is
    outside `configs/diagnosers/`. The validated `cache_key_env` /
    `model.requested_alias` / `privacy.requires_explicit_external_llm_opt_in`
    settings could quietly fail to apply to the actual run.

    When `explicit_path` is provided, this function loads from there and
    additionally validates that `config.diagnoser_name` matches
    `diagnoser_name` (otherwise the manifest would claim one config while
    the runner derived behaviour from another); on mismatch it raises
    DiagnoserConfigError. When `explicit_path` is None, this falls back
    to the legacy `configs/diagnosers/<name>.json` auto-discovery for
    back-compat. Returns None when no file exists at the resolved path —
    legacy call sites treat that as "no config available".
    """
    cfg_path = (
        explicit_path
        if explicit_path is not None
        else ROOT / "configs" / "diagnosers" / f"{diagnoser_name}.json"
    )
    if not cfg_path.exists():
        if explicit_path is not None:
            raise DiagnoserConfigError(
                f"--diagnoser-config {cfg_path} does not exist"
            )
        return None
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        if explicit_path is not None:
            raise DiagnoserConfigError(
                f"--diagnoser-config {cfg_path} is unreadable: {exc}"
            ) from exc
        return None
    if explicit_path is not None:
        declared = cfg.get("diagnoser_name")
        if declared and declared != diagnoser_name:
            # Per Codex 2026-05-22 F1 [high]: a config can opt into
            # name-override mode via `reusable_template: true`. The
            # docs document workflows that use the same reusable
            # command template under custom --diagnoser-name values
            # (e.g. example.debugger-v1-command.json with
            # --diagnoser-name=stub-debugger-v1). Without opt-in,
            # the 2026-05-15 strict check rejected those workflows
            # outright. With opt-in, the override is allowed and the
            # config's declared name is recorded in
            # `metadata.diagnoser_config_name` for audit.
            if not cfg.get("reusable_template"):
                raise DiagnoserConfigError(
                    f"--diagnoser-config {cfg_path} declares "
                    f"diagnoser_name={declared!r} but --diagnoser-name "
                    f"is {diagnoser_name!r}. Manifest would claim one "
                    f"config while the runner derived behaviour from "
                    f"another. Pass the correct config, OR override "
                    f"--diagnoser-name, OR mark the config "
                    f"`reusable_template: true` if it's intended to be "
                    f"reused under custom names."
                )
    return cfg


_TRUTHY_OPT_IN_VALUES = {"1", "true", "yes", "on"}


def check_external_llm_opt_in(
    config: dict | None, *, provider: str = "mock"
) -> str | None:
    """Per Codex 2026-05-13 F1 + 2026-05-18 F1: enforce the privacy gate
    for command-provider runs.

    Behaviour:
    - `mock` provider: never gates (no external egress).
    - `command` provider with NO config loaded (auto-discovery missed,
      typo in --diagnoser-name, malformed --diagnoser-config): FAIL
      CLOSED. Pre-2026-05-18 this returned None ("pass"), which let a
      misnamed run send CI logs to whatever DIAGNOSIS_COMMAND points
      at without the runner-level gate firing.
    - `command` provider WITH a config that does not declare
      `privacy.requires_explicit_external_llm_opt_in` at all: FAIL
      CLOSED. Configs MUST be explicit; a missing key is treated as
      "policy not specified", not "policy: false".
    - `command` provider WITH config declaring the gate `false`: pass
      (explicit opt-out, e.g. for a mock-shim command that doesn't
      actually call an external LLM).
    - `command` provider WITH config declaring the gate `true`: pass
      iff the declared env var (default
      `CILOGBENCH_ALLOW_EXTERNAL_LLM`) is set to a truthy value.

    Returns None when the gate passes; returns a human-readable error
    string otherwise so callers print + return 1.

    The same gate is mirrored inside the shim binaries so an off-runner
    invocation (e.g. someone calling DIAGNOSIS_COMMAND directly for a
    smoke-test) cannot send CI log context to an external API without
    the explicit opt-in.
    """
    if provider == "mock":
        return None

    if not isinstance(config, dict):
        return (
            "command-provider runs require a diagnoser config that "
            "declares the external-LLM opt-in gate; none was loaded. "
            "Pass --diagnoser-config <path> or use a --diagnoser-name "
            "that auto-discovers `configs/diagnosers/<name>.json`."
        )

    privacy = config.get("privacy") or {}
    if "requires_explicit_external_llm_opt_in" not in privacy:
        return (
            f"diagnoser {config.get('diagnoser_name', '<unknown>')} "
            f"config does not declare "
            f"`privacy.requires_explicit_external_llm_opt_in`. "
            f"Command-provider runs must declare this explicitly "
            f"(true or false). Missing field is policy-unspecified, "
            f"not policy-false."
        )

    if not privacy["requires_explicit_external_llm_opt_in"]:
        return None  # explicit opt-out

    var = privacy.get("explicit_opt_in_env_var") or "CILOGBENCH_ALLOW_EXTERNAL_LLM"
    val = (os.environ.get(var) or "").strip().lower()
    if val in _TRUTHY_OPT_IN_VALUES:
        return None
    return (
        f"diagnoser {config.get('diagnoser_name', '<unknown>')} requires "
        f"explicit opt-in via env var {var}=1 to invoke an external LLM "
        f"(see privacy.requires_explicit_external_llm_opt_in in the "
        f"diagnoser config). Set {var}=1 to acknowledge the data egress "
        f"and re-run."
    )


def cache_key_env_values(
    config: dict | None,
    env_source: dict[str, str] | None = None,
) -> dict[str, str] | None:
    """Collect env-var values declared in config.cache_key_env.

    Per Codex 2026-05-17 F2: callers pass the SAME env that the shim
    subprocess will see (post-`build_shim_env` injection of config
    defaults). This makes "user did not set X" and "user set X to the
    config default" produce IDENTICAL cache keys; previously the
    pre-injection env left X="" while the shim ran with X=default.

    `env_source` falls back to `os.environ` for legacy call sites
    (mostly unit tests). Returns None when no env vars are declared so
    legacy caches keep matching their old keys for diagnosers that
    don't opt in.
    """
    if not isinstance(config, dict):
        return None
    keys = config.get("cache_key_env")
    if not isinstance(keys, list) or not keys:
        return None
    src = env_source if env_source is not None else os.environ
    return {k: src.get(k, "") for k in sorted(keys)}


def effective_requested_model(config: dict | None) -> str | None:
    """Return the model identifier we expect the current run's shim to emit
    as `metadata.model_info.requested_model`.

    Resolution order:
        1. env_var_name's value in os.environ — ONLY if the config has
           `model.allow_runtime_model_override: true` (Codex 2026-06-05
           F2). Default for canonical real-debugger-* configs is false:
           env overrides do NOT change the expected identity; if the
           shim emits a different requested_model the runner rejects
           it as a provenance mismatch.
        2. config.model.requested_alias (the shim-level alias — e.g. v1
           Claude uses 'haiku' for `claude -p --model haiku`, while
           model.model_name is the canonical dated identity)
        3. config.model.model_name (the canonical / dated identity — what
           the OpenAI shim emits when no env override is in play)

    Codex history:
        - 2026-05-12 F2: introduced env-aware lookup so env overrides
          remain idempotent. (Was permissive by default.)
        - 2026-05-13 F2: explicit env_var_name pointer added to v3 config.
        - 2026-05-14 F2: requested_alias added so v1/v2 (whose shim
          sends short Claude aliases) can validate against what the
          shim actually persists.
        - 2026-06-05 F2 [high]: env override is now an OPT-IN per
          `model.allow_runtime_model_override`. Canonical fixed
          configs lock identity; reusable templates or experiment-
          mode configs can opt into runtime override.
    """
    if not isinstance(config, dict):
        return None
    model_section = config.get("model") or {}
    if model_section.get("allow_runtime_model_override"):
        env_var = model_section.get("env_var_name")
        if env_var:
            val = os.environ.get(env_var)
            if val:
                return val
    alias = model_section.get("requested_alias")
    if alias:
        return alias
    return model_section.get("model_name") or None


def check_locked_env_override(config: dict | None) -> str | None:
    """Per Codex 2026-06-06 F1 [high]: a canonical (locked) config
    that does NOT set `model.allow_runtime_model_override` must
    refuse to invoke the shim when the user has set the
    config-declared env var to a non-canonical value.

    The 2026-06-05 F2 fix made the validator reject post-API rows
    whose `requested_model` disagreed with the locked config — but
    by then the shim had already made the wrong-model API call,
    paying both the $ cost and the privacy cost of shipping CI
    logs to a backend the operator didn't intend. This pre-flight
    check blocks the shim invocation entirely in that case.

    Returns None when the run is safe to proceed; an error string
    otherwise so the runner can print + return 1.
    """
    if not isinstance(config, dict):
        return None
    model = config.get("model") or {}
    if model.get("allow_runtime_model_override"):
        return None  # Experiment-mode configs accept env overrides.
    env_var = model.get("env_var_name")
    if not env_var:
        return None
    user_value = os.environ.get(env_var)
    if user_value is None:
        return None  # Env var unset; canonical alias will be used.
    canonical = model.get("requested_alias") or model.get("model_name")
    if not canonical or user_value == canonical:
        return None
    return (
        f"diagnoser config "
        f"{config.get('diagnoser_name', '<unknown>')!r} locks model "
        f"identity to {canonical!r} but {env_var}={user_value!r} is "
        f"set in the environment. Refusing to invoke the shim — that "
        f"would ship CI log context to a different model than the "
        f"config declares. Either unset {env_var} (or set it to "
        f"{canonical!r}), or use a config that declares "
        f"`model.allow_runtime_model_override: true`."
    )


def build_shim_env(
    config: dict | None, parent_env: dict[str, str] | None = None
) -> dict[str, str]:
    """Per Codex 2026-05-15 F1 [high] + 2026-05-17 F2 [medium]: build the
    env mapping the shim subprocess sees.

    When the diagnoser config declares `model.env_var_name` (e.g.
    CILOGBENCH_CLAUDE_MODEL for v1/v2; CILOGBENCH_OPENAI_MODEL for v3) and
    the user has NOT set that var explicitly, inject the effective model
    into the shim subprocess env. Same for `model.base_url_env_var_name`
    + `model.base_url` (added 2026-05-17). Without these, the shim's
    hardcoded defaults applied invisibly: v2 (config: sonnet) ran against
    a Claude shim with default 'haiku'; v3 cache_key recorded an empty
    base_url while the shim hit the default OpenAI endpoint.

    User-set env values are preserved — this only fills in the gap when
    the user hasn't overridden, so explicit experiments
    (`CILOGBENCH_OPENAI_MODEL=gpt-4o`,
    `CILOGBENCH_OPENAI_BASE_URL=https://proxy/v1`) still work.
    """
    env = dict(parent_env if parent_env is not None else os.environ)
    if not isinstance(config, dict):
        return env
    model = config.get("model") or {}
    # Model alias injection (2026-05-15 F1).
    env_var = model.get("env_var_name")
    alias = model.get("requested_alias") or model.get("model_name")
    if env_var and alias and env.get(env_var) is None:
        env[env_var] = alias
    # Base URL injection (2026-05-17 F2).
    base_url_var = model.get("base_url_env_var_name")
    base_url_default = model.get("base_url")
    if base_url_var and base_url_default and env.get(base_url_var) is None:
        env[base_url_var] = base_url_default
    return env


_API_VERSION_SEGMENT_RE = re.compile(r"^v\d+$")


def _sanitize_base_url_for_compare(url: str) -> str:
    """Per Codex 2026-05-18 F3 + 2026-05-25 F2 + 2026-05-31 F1: the
    OpenAI shim persists a sanitized base_url (userinfo + query +
    deep-path segments stripped) in `metadata.model_info.base_url`.
    The runner's `effective_base_url` returns the env value
    verbatim. Comparing sanitized-vs-raw caused cache_hit_is_acceptable
    to reject the very row it had just written when the user pointed
    CILOGBENCH_OPENAI_BASE_URL at a credentialed-proxy URL.

    Same shape as `examples/diagnosis_shim_openai.py:sanitize_base_url`
    — duplicated here so the runner has no shim-import dependency.
    Codex 2026-05-31 F1 [high]: the 2026-05-25 logic preserved
    arbitrary first segments — proxies shaped like
    `https://proxy/<tenant-key>/v1` would persist the tenant key.
    Now: only first segments matching `^v\\d+$` (canonical API-
    version routes like /v1, /v2, /v10) are preserved. Anything
    else is dropped entirely.
    """
    if not url:
        return url
    parts = urllib.parse.urlsplit(url)
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    path = parts.path or ""
    if path and path != "/":
        segments = [s for s in path.split("/") if s]
        if segments and _API_VERSION_SEGMENT_RE.fullmatch(segments[0]):
            path = "/" + segments[0]
        else:
            path = ""
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, "", ""))


def _base_url_sha256_for_compare(url: str) -> str:
    """sha256 of the FULL effective URL (including any proxy creds).
    Used by cache_hit_is_acceptable to confirm endpoint identity
    without leaking the secret-carrying parts. Matches what the
    OpenAI shim stores as `metadata.model_info.base_url_sha256`."""
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()


def effective_base_url(config: dict | None) -> str | None:
    """Return the endpoint URL we expect the current run's shim to hit,
    used by `cache_hit_is_acceptable` to validate cached rows. Resolution
    mirrors `effective_requested_model`:

        1. env_var_name's value in os.environ (if both declared + non-empty)
        2. config.model.base_url (the canonical default)
    """
    if not isinstance(config, dict):
        return None
    model_section = config.get("model") or {}
    env_var = model_section.get("base_url_env_var_name")
    if env_var:
        val = os.environ.get(env_var)
        if val:
            return val
    return model_section.get("base_url") or None


def _config_requires_model_info(config: dict | None) -> bool:
    """Per Codex 2026-05-18 F2 [high]: a config that declares either
    `cache_key_env` (env vars that affect output) or `model.model_name`
    (a canonical model identity) is saying "this diagnoser is a real
    backend-bound entity"; rows under it MUST carry model_info.

    Codex 2026-05-23 F1 [high]: `reusable_template: true` configs
    (e.g. `example.debugger-v1-command.json`) declare a PLACEHOLDER
    `model_name` so the on-disk file is schema-valid. The actual
    model that the run uses is bound by the caller's shim + env,
    not by the config. Treating those placeholders as canonical
    identity broke documented M6/M7 stub + custom-shim workflows
    (the validator rejected every fresh row because
    requested_model='haiku' or 'gpt-5-mini' or '' didn't match the
    config's 'user-configured-model'). Reusable templates opt out
    of provenance enforcement entirely; the canonical real-debugger
    configs (v1/v2/v3) do NOT set this flag.

    The explicit opt-out is `model.allow_missing_model_info: true`,
    used for legacy mock / stub diagnosers that don't have a shim
    yet. Pre-2026-05-18 the validators accepted missing model_info
    universally as back-compat, which let a stale or custom shim
    write rows under real-debugger-v1/v2/v3 with no provenance.
    """
    if not isinstance(config, dict):
        return False
    if config.get("reusable_template"):
        return False
    model = config.get("model") or {}
    if model.get("allow_missing_model_info"):
        return False
    return bool(config.get("cache_key_env")) or bool(model.get("model_name"))


def _validate_resolved_model_identity(
    mi: dict, config: dict | None, *, strict: bool = False,
) -> str | None:
    """Shared resolved-model validation used by both fresh-row and
    cache-hit paths.

    Codex 2026-05-25 F1 [high] added the cache-hit check.
    Codex 2026-05-26 F1 [high]: extracted to a shared helper because
    the fresh-row path did NOT perform the same check.
    Codex 2026-05-27 F2 [high]: `strict=True` (fresh-row path) now
    REQUIRES a non-null resolved_model under a config that pins one.
    Pre-fix, the validator returned success when actual_resolved was
    None — so a custom OpenAI-compatible endpoint that omits the
    `model` field in its response could produce a successful row with
    no snapshot evidence and pass the pin check. Cache-hit path keeps
    `strict=False` so legacy backfilled rows with resolved_model=null
    (pre-2026-05-13) and oversized-context rows (no API call ever
    made) continue to pass.

    Returns None when validation passes or doesn't apply; an error
    string otherwise.
    """
    if not isinstance(config, dict):
        return None
    expected_resolved = (config.get("model") or {}).get(
        "expected_resolved_model"
    )
    if not expected_resolved:
        return None
    actual_resolved = mi.get("resolved_model") if isinstance(mi, dict) else None
    if actual_resolved is None:
        if strict:
            return (
                f"shim emitted no `metadata.model_info.resolved_model` "
                f"but diagnoser config pins "
                f"expected_resolved_model={expected_resolved!r}. "
                f"Refusing to accept a fresh success row with no "
                f"snapshot evidence (an OpenAI-compatible endpoint or "
                f"modified response may have omitted the `model` field "
                f"from its JSON envelope, which would silently bypass "
                f"the alias-rotation check)."
            )
        # Legacy back-compat for cache reads: pre-2026-05-13 backfilled
        # rows + rows whose API call never happened (oversized-context
        # skips) have resolved_model=null. We have no evidence to
        # reject these existing on-disk rows.
        return None
    if actual_resolved != expected_resolved:
        return (
            f"resolved_model={actual_resolved!r} != "
            f"config-pinned expected_resolved_model={expected_resolved!r}"
        )
    return None


def _validate_provider_name_identity(
    mi: dict, config: dict | None
) -> str | None:
    """Per Codex 2026-06-02 F1 [high]: validate the cached
    `provider_name` matches `config.model.provider_name`. The
    cache/fresh-row validators historically compared
    `requested_model`, endpoint, and resolved_model, but never the
    provider family — so a miswired command shim could write rows
    with `provider_name: openai` under real-debugger-v1 (Anthropic
    config) and pass every other check, corrupting cross-family
    provenance.

    Returns None when validation passes or doesn't apply; an error
    string on mismatch. Legacy back-compat: rows whose
    `provider_name` is missing pass through ONLY when the config
    doesn't require provenance — for canonical real-debugger configs
    (which declare cache_key_env or model.model_name) missing
    provider_name is rejected.
    """
    if not isinstance(config, dict) or not isinstance(mi, dict):
        return None
    expected = (config.get("model") or {}).get("provider_name")
    if not expected:
        return None
    actual = mi.get("provider_name")
    if actual is None:
        if _config_requires_model_info(config):
            return (
                f"shim emitted no `_model_info.provider_name`, but "
                f"diagnoser {config.get('diagnoser_name', '<unknown>')} "
                f"declares model.provider_name={expected!r}. Required."
            )
        return None
    if actual != expected:
        return (
            f"provider_name={actual!r} != "
            f"config.model.provider_name={expected!r}"
        )
    return None


def _check_base_url_redaction(
    mi: dict, config: dict | None
) -> str | None:
    """Per Codex 2026-06-01 F1 [high]: base_url redaction is a PRIVACY
    invariant, not an identity check. It applies regardless of
    whether the config pins an expected endpoint AND regardless of
    `reusable_template` status (Codex 2026-05-23 made reusable_template
    skip identity checks, but redaction must still fire — templates
    are EXACTLY the case where an externally-supplied shim might
    forget to sanitize, and the runner can't assume it did).

    Returns None when no enforcement applies or the row is already
    sanitized. Returns an error string when the config opts into
    `privacy.allow_secret_values_in_results: false` and the persisted
    `base_url` is NOT already in sanitized form (would leak userinfo,
    query tokens, or non-allowlist path segments).
    """
    if not isinstance(config, dict) or not isinstance(mi, dict):
        return None
    privacy = config.get("privacy") or {}
    # The privacy invariant is "secrets MUST NOT be in results"; enforce
    # only when the field is explicitly set to False. Missing field is
    # policy-unspecified and we don't speculate.
    if privacy.get("allow_secret_values_in_results", True):
        return None
    cached_url = mi.get("base_url")
    if cached_url is None:
        return None
    sanitized_form = _sanitize_base_url_for_compare(cached_url)
    if cached_url != sanitized_form:
        # Per Codex 2026-06-04 F1 [high]: the raw `cached_url` carries
        # the very secrets this guard is meant to block — DO NOT echo
        # it into the rejection reason. The reason is propagated by
        # `cache_reject` / `FAIL_PROVENANCE` log lines and would leak
        # the secret bits into CI logs and stderr. Use the sanitized
        # form + a sha256 prefix of the unsanitized form for identity.
        cached_hash_short = _base_url_sha256_for_compare(cached_url)[:16]
        return (
            f"persisted `base_url` is not in sanitized form; refusing "
            f"to accept a row that would leak userinfo, query tokens, "
            f"or non-allowlist path segments into the canonical "
            f"diagnosis artifact. sanitized={sanitized_form!r}, "
            f"unsanitized_sha={cached_hash_short}…. "
            f"privacy.allow_secret_values_in_results=false."
        )
    return None


def _validate_base_url_identity(
    cached_mi: dict, config: dict | None
) -> str | None:
    """Shared base_url validation logic used by both fresh-row and
    cache-hit validators. Returns None when validation passes or
    doesn't apply; an error string otherwise.

    Codex 2026-05-19 F1 [high]: previously this only ran on cache hits;
    fresh-row writes could pollute the manifest first.
    Codex 2026-05-20 F1 [high]: previously this returned success when
    BOTH `base_url_sha256` and `base_url` were absent from the row.
    A stale shim emitting only `requested_model` could hit the wrong
    backend and still be accepted because the validator had no
    endpoint evidence to compare. Now: if the config requires
    provenance (cache_key_env or model.model_name declared), missing
    endpoint evidence is itself a failure.
    Codex 2026-05-23 F1 [high]: `reusable_template: true` configs
    skip endpoint validation too (no binding endpoint).
    """
    if not isinstance(config, dict):
        return None
    if config.get("reusable_template"):
        return None
    expected_url = effective_base_url(config)
    if not expected_url:
        return None

    # Codex 2026-05-29 F1 redaction check moved out into
    # `_check_base_url_redaction()` (Codex 2026-06-01 F1) so it also
    # applies to reusable_template configs. Both validators call the
    # helper BEFORE delegating here, so this body now only handles
    # identity comparison.
    # Per Codex 2026-06-03 F1 [high]: never include the RAW
    # expected_url in error strings — env values can carry userinfo,
    # query tokens, and tenant-path secrets that would then leak
    # through FAIL_PROVENANCE / cache_reject log lines. Use the
    # sanitized form + short sha256 prefix instead.
    expected_sanitized = _sanitize_base_url_for_compare(expected_url)
    expected_hash_short = _base_url_sha256_for_compare(expected_url)[:16]
    # Per Codex 2026-06-03 F2 [high]: detect when sanitization is
    # lossy (sanitized != raw). For lossy endpoints (proxies/tenant
    # gateways), the sanitized base_url alone can't distinguish
    # `/tenant-a/v1` from `/tenant-b/v1` (both collapse to the
    # bare host under the `^v\d+$`-only allowlist). Fresh rows + the
    # cache-hit path REQUIRE base_url_sha256 in that case.
    sanitization_is_lossy = expected_sanitized != expected_url

    cached_url = cached_mi.get("base_url")
    cached_hash = cached_mi.get("base_url_sha256")
    if cached_hash is not None:
        if cached_hash != _base_url_sha256_for_compare(expected_url):
            return (
                f"shim returned base_url_sha256={cached_hash[:16]}… "
                f"but config expects {expected_hash_short}…"
            )
        return None
    if cached_url is None:
        # No endpoint evidence in the row at all.
        if _config_requires_model_info(config):
            return (
                f"row has no `base_url` or `base_url_sha256` but "
                f"diagnoser config declares an expected endpoint "
                f"(sanitized={expected_sanitized!r}, "
                f"sha256={expected_hash_short}…); provenance required. "
                f"Set `model.allow_missing_model_info: true` in the "
                f"config to opt out (legacy diagnosers only)."
            )
        return None
    # Per Codex 2026-06-03 F2 [high]: lossy sanitization means the
    # sanitized comparison can't distinguish proxy tenants. Require
    # the full-URL hash from the shim.
    if sanitization_is_lossy and _config_requires_model_info(config):
        return (
            f"config endpoint sanitizes lossily (sanitized="
            f"{expected_sanitized!r}, sha256={expected_hash_short}…); "
            f"full `base_url_sha256` required to disambiguate proxy / "
            f"tenant paths but the shim emitted only sanitized "
            f"`base_url`. Re-run with an updated shim that emits "
            f"base_url_sha256 alongside base_url."
        )
    if cached_url != expected_sanitized:
        # Per Codex 2026-06-04 F1 [high]: `cached_url` here passed the
        # redaction guard (it equals its sanitize() form) but a future
        # shim bug could regress that invariant. Defensive: use only
        # the sanitized form + sha for cached side too.
        cached_hash_short = _base_url_sha256_for_compare(cached_url)[:16]
        return (
            f"shim returned base_url (sanitized)={cached_url!r} "
            f"(sha={cached_hash_short}…) but config expects "
            f"(sanitized) {expected_sanitized!r} "
            f"(sha={expected_hash_short}…)"
        )
    return None


def validate_fresh_row_model_identity(
    diag_body: dict, config: dict | None
) -> str | None:
    """Per Codex 2026-05-15 F1 + 2026-05-18 F2 + 2026-05-19 F1 [high]:
    belt-and-suspenders for fresh rows.

    The cache validator only fires on cache hits; fresh rows had no
    such check until 2026-05-15. If the shim returns a row whose
    `_model_info.requested_model` OR `_model_info.base_url` /
    `base_url_sha256` disagrees with the diagnoser config, the row
    should NOT be written under the diagnoser's name. Codex 2026-05-18
    additionally requires that configs declaring a model identity get
    a row WITH `_model_info`; 2026-05-19 closes the corresponding gap
    for endpoint identity (a stale shim that ignored
    CILOGBENCH_OPENAI_BASE_URL could otherwise hit the default OpenAI
    endpoint while the config pointed at a proxy).

    Codex 2026-05-23 F1 [high]: `reusable_template: true` configs
    opt out of identity validation entirely — their `model.model_name`
    is a placeholder, not a binding. The caller's shim + env supply
    the actual model.
    """
    if not isinstance(config, dict):
        return None
    mi = diag_body.get("_model_info") or {}
    # Per Codex 2026-06-01 F1 [high]: redaction is unconditional —
    # applies even to reusable_template configs and to configs with
    # no model identity declared. Runs FIRST so a shim that emits an
    # unsanitized base_url can't write a row even when other
    # provenance checks short-circuit.
    redaction_err = _check_base_url_redaction(mi, config)
    if redaction_err:
        return f"base_url redaction: {redaction_err}"
    if config.get("reusable_template"):
        return None
    # Per Codex 2026-06-02 F1 [high]: validate provider family
    # (anthropic / openai / etc.) BEFORE specific model identity.
    # Catches miswired shims that emit rows with the wrong provider
    # under a canonical diagnoser_name.
    provider_err = _validate_provider_name_identity(mi, config)
    if provider_err:
        return f"provider identity: {provider_err}"
    expected = effective_requested_model(config)
    if not expected:
        # No model identity declared — also skip endpoint checks since
        # the config evidently doesn't ground identity.
        return None
    actual = mi.get("requested_model")
    if actual is None:
        if _config_requires_model_info(config):
            return (
                f"shim emitted no `_model_info.requested_model`, but "
                f"diagnoser {config.get('diagnoser_name', '<unknown>')} "
                f"declares model.model_name / cache_key_env — provenance "
                f"required. Set `model.allow_missing_model_info: true` "
                f"in the config to opt out (legacy diagnosers only)."
            )
        # Pre-2026-05-11 shims don't emit _model_info; back-compat for
        # diagnosers/shims not yet upgraded.
        return None
    if actual != expected:
        return (
            f"shim returned requested_model={actual!r} but diagnoser "
            f"config expects {expected!r}; refusing to write a row "
            f"under the wrong model identity"
        )
    # Endpoint identity (Codex 2026-05-19 F1).
    url_err = _validate_base_url_identity(mi, config)
    if url_err:
        return f"endpoint mismatch under diagnoser config: {url_err}"
    # Resolved-snapshot identity (Codex 2026-05-26 F1 + 2026-05-27 F2):
    # the cache-hit path was already enforcing this; the fresh-row
    # path skipped it. 2026-05-27 additionally requires the fresh-row
    # row to carry a non-null resolved_model under pinned configs —
    # otherwise a compatible endpoint that omits the `model` response
    # field could silently bypass the alias-rotation check.
    resolved_err = _validate_resolved_model_identity(mi, config, strict=True)
    if resolved_err:
        return f"resolved_model mismatch under diagnoser config: {resolved_err}"
    return None


def cache_hit_is_acceptable(
    cached_row: dict, config: dict | None,
    *, cache_errors: bool = False,
    current_diagnoser_config_sha: str | None = None,
    current_shim_sha: str | None = None,
) -> tuple[bool, str | None]:
    """Per Codex 2026-05-12 F2 + 2026-05-17 F2 + 2026-05-24: belt-and-
    suspenders. Even if the cache_key matched, validate that the cached
    row's `metadata.model_info` matches the *effective* expected model
    AND endpoint, and reject cached provider_error rows by default.

    Codex 2026-05-24 F2 [high]: `reusable_template: true` configs no
    longer accept cache hits at all. Templates lack `cache_key_env`,
    so changing CILOGBENCH_OPENAI_MODEL / CILOGBENCH_CLAUDE_MODEL
    doesn't move the cache key, and the validators have nothing
    canonical to compare against. A custom-template run could
    otherwise replay rows from a different model/backend under the
    same diagnoser name. Forcing cache miss-through-fresh-call is
    safe because templates are explicitly documented as "you supply
    the model"; the user knows there's no shared canonical state.

    Codex 2026-05-24 F1 [high]: cached rows with non-empty
    `metadata.provider_error` are rejected unless `cache_errors=True`.
    The 2026-05-22 F2 fix prevented WRITING such rows by default, but
    the READ path still accepted any pre-existing polluted entry —
    a transient post_api_error/timeout row could replay forever.

    Returns (True, None) if no validation applies or all checks pass.
    Returns (False, reason) on mismatch.
    """
    if not isinstance(config, dict):
        return True, None
    cached_meta = cached_row.get("metadata") or {}
    cached_mi_for_redaction = cached_meta.get("model_info") or {}
    # Per Codex 2026-06-01 F1 [high]: redaction is unconditional and
    # applies BEFORE the reusable_template short-circuit and the
    # provider_error gate. Even if we're going to reject the cache hit
    # for a different reason, the row's persisted metadata must comply
    # with the privacy policy.
    redaction_err = _check_base_url_redaction(
        cached_mi_for_redaction, config
    )
    if redaction_err:
        return False, f"cache row base_url redaction: {redaction_err}"
    # Reusable templates never trust the cache (no canonical model
    # identity).
    if config.get("reusable_template"):
        return False, (
            "reusable_template config has no canonical model identity; "
            "cache hits cannot be validated and are not trusted"
        )
    # Reject cached provider_error rows unless opted in explicitly.
    cached_pe = cached_meta.get("provider_error")
    if cached_pe and not cache_errors:
        return False, (
            f"cached row has metadata.provider_error="
            f"{str(cached_pe)[:80]!r}; rejecting (default behavior, "
            f"pass --cache-errors to opt in)"
        )
    # cached_meta already bound earlier (with cached_mi_for_redaction).
    cached_mi = cached_mi_for_redaction

    # Per Codex 2026-06-02 F1 [high]: validate provider family. A
    # miswired shim could pass other identity checks but emit
    # provider_name from a different family (e.g. openai rows under
    # real-debugger-v1's Anthropic config).
    provider_err = _validate_provider_name_identity(cached_mi, config)
    if provider_err:
        return False, f"cache row provider identity: {provider_err}"

    expected_model = effective_requested_model(config)
    if expected_model:
        cached_requested = cached_mi.get("requested_model")
        if cached_requested is None:
            # Per Codex 2026-05-18 F2 [high]: legacy back-compat is gated
            # on the diagnoser config opting in. Real-debugger configs
            # that declare model.model_name / cache_key_env REQUIRE
            # provenance — a cached row without model_info under such
            # a config could have come from any stale/custom shim.
            if _config_requires_model_info(config):
                return False, (
                    f"cache row missing metadata.model_info.requested_model "
                    f"but diagnoser config requires provenance "
                    f"(model.model_name or cache_key_env declared)"
                )
        elif cached_requested != expected_model:
            return False, (
                f"cache row requested_model={cached_requested!r} != "
                f"effective model={expected_model!r}"
            )

    # Per Codex 2026-05-25 F1 + 2026-05-26 F1 + 2026-05-27 F2 +
    # 2026-06-05 F1 [high]: snapshot-identity validation via the
    # shared helper. The cache-hit path is now ALSO strict — a pinned
    # config + null resolved_model means the cached row predates the
    # snapshot pin and can't be trusted; force fresh call. Cached
    # provider_error rows are rejected by an earlier gate (Codex
    # 2026-05-24 F1), so this strict check only affects success
    # rows, which are the ones the pin is meant to lock down.
    resolved_err = _validate_resolved_model_identity(
        cached_mi, config, strict=True
    )
    if resolved_err:
        return False, f"cache row {resolved_err}"

    # Per Codex 2026-05-17 F2 + 2026-05-18 F3 + 2026-05-19 F1:
    # delegate endpoint validation to the shared helper so cache-hit
    # and fresh-row paths use identical logic.
    url_err = _validate_base_url_identity(cached_mi, config)
    if url_err:
        return False, f"cache row endpoint mismatch: {url_err}"

    # Per Codex 2026-06-08 F2 + 2026-06-09 F2 [high]: reject cache
    # hits whose persisted diagnoser-config SHA or shim-implementation
    # SHA doesn't match the current run's loaded config + shim. Closes
    # the silent-replay window where editing `configs/diagnosers/*.json`
    # or `examples/diagnosis_shim_*.py` would otherwise reuse stale
    # cache entries (the literal command string + env values stayed
    # the same, so the cache_key didn't move).
    #
    # Codex 2026-06-09 F2: when the config requires provenance
    # (canonical real-debugger-* via `_config_requires_model_info`),
    # the SHA fields are REQUIRED. Missing fields → reject. Pre-fix
    # (2026-06-08 F2 only), the back-compat "accept null" branch let
    # the one-shot migration's null-stamped rows replay across future
    # config / shim edits — exactly the failure 2026-06-08 F2 meant
    # to close. The migration tool now stamps current SHAs onto
    # rebuilt rows so the strict mode passes on the canonical state.
    # Configs without provenance requirements (mock/stub/template)
    # keep back-compat: null SHA → accept (legacy data).
    cached_config_sha = cached_meta.get("diagnoser_config_sha256")
    cached_shim_sha = cached_meta.get("shim_sha256")
    if _config_requires_model_info(config):
        if cached_config_sha is None and current_diagnoser_config_sha is not None:
            return False, (
                "cache row missing metadata.diagnoser_config_sha256 "
                "under a config that requires provenance "
                "(model.model_name / cache_key_env declared). Pre-2026-06-08 "
                "rows pre-date the field; run tools/migrate_cache_keys_"
                "codex_2026_06_08.py to stamp current SHAs."
            )
        if cached_shim_sha is None and current_shim_sha is not None:
            return False, (
                "cache row missing metadata.shim_sha256 under a config "
                "that requires provenance. Run tools/migrate_cache_keys_"
                "codex_2026_06_08.py to stamp current SHAs."
            )
    if (
        cached_config_sha is not None
        and current_diagnoser_config_sha is not None
        and cached_config_sha != current_diagnoser_config_sha
    ):
        return False, (
            f"cache row diagnoser_config_sha256={cached_config_sha[:12]}… "
            f"!= current config sha={current_diagnoser_config_sha[:12]}… "
            f"(config edited since cache write — forcing fresh call)"
        )
    if (
        cached_shim_sha is not None
        and current_shim_sha is not None
        and cached_shim_sha != current_shim_sha
    ):
        return False, (
            f"cache row shim_sha256={cached_shim_sha[:12]}… "
            f"!= current shim sha={current_shim_sha[:12]}… "
            f"(shim edited since cache write — forcing fresh call)"
        )
    return True, None


def cache_key_for(
    *, case_id: str, context_method: str, context_sha: str, prompt_sha: str,
    provider: str, diagnoser: str, command_str: str | None,
    env_values: dict[str, str] | None = None,
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
    # Per Codex 2026-05-12 F2: when the diagnoser config opts in via
    # `cache_key_env`, fold those env-var values into the key so changing
    # CILOGBENCH_OPENAI_MODEL (or BASE_URL, etc.) does NOT replay a stale
    # row from a different model/backend. Diagnosers without opt-in retain
    # their legacy key for back-compat.
    if env_values:
        parts["env"] = env_values
    norm = json.dumps(parts, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return sha256_text(norm)
    # Per Codex 2026-06-08 F2 [high]: the diagnoser-config SHA and the
    # shim-impl SHA are NOT folded into the cache key directly. Instead
    # they are persisted into `metadata.diagnoser_config_sha256` /
    # `metadata.shim_sha256` on every fresh write, and
    # `cache_hit_is_acceptable` rejects cache hits when those captured
    # values do not match the current run's loaded config + shim. The
    # validation approach preserves the existing cache filename layout
    # (no migration needed) while closing the silent-replay window
    # Codex flagged: a config or shim edit invalidates affected cache
    # rows by rejection rather than by re-keying.


def run(
    *, split: str, diagnoser_provider: str, diagnoser_name: str,
    context_method: str, results_dir: Path, cases_dir: Path,
    prompt_path: Path, command_str: str | None,
    strict: bool, no_cache: bool, cache_errors: bool,
    diagnoser_config_path: Path | None = None,
) -> int:
    if not prompt_path.exists():
        print(f"ERROR: prompt not found: {prompt_path}", file=sys.stderr)
        return 1
    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt_sha = sha256_text(prompt_text)

    # Per Codex 2026-05-12 F2 + 2026-05-15 F2: load the diagnoser config
    # to discover (a) env-var-driven cache_key contributions, (b) the
    # canonical requested_model / requested_alias for cache-hit
    # validation, and (c) the external-LLM opt-in gate. When the caller
    # supplies an explicit --diagnoser-config path (the wrappers do this
    # now), the loader fails fast on diagnoser_name mismatch so a
    # manifest can never claim one config while the runner derived its
    # behaviour from another.
    try:
        diagnoser_config = load_diagnoser_config(
            diagnoser_name, explicit_path=diagnoser_config_path
        )
    except DiagnoserConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Per Codex 2026-06-08 F2 [high]: SHA the loaded config + the shim
    # script (if command_str references a repo-local .py). These get
    # folded into every cache key so editing either invalidates stale
    # cache entries.
    diagnoser_config_sha = diagnoser_config_sha256(
        diagnoser_name, explicit_path=diagnoser_config_path
    )
    shim_sha = shim_sha256_for_command(command_str)

    # Per Codex 2026-05-22 F1 [high]: capture the config's declared
    # diagnoser_name when it's a reusable_template used under a custom
    # --diagnoser-name. build_row records this in
    # metadata.diagnoser_config_name so the audit trail names BOTH
    # the config (e.g. example-debugger-v1) and the run-time
    # diagnoser (e.g. stub-debugger-v1).
    config_declared_name = (
        (diagnoser_config or {}).get("diagnoser_name")
        if isinstance(diagnoser_config, dict)
        else None
    )

    # Per Codex 2026-05-21 F1 [high]: the CLI takes `--diagnoser`
    # (mock|command) and `--diagnoser-name`, but the gate logic
    # historically trusted the CLI value. A command like
    # `--diagnoser-name real-debugger-v3` with default `--diagnoser mock`
    # kept the default mock provider, skipped the external-LLM gate,
    # AND wrote SUCCESSFUL mock rows under results/<split>/diagnoses/
    # real-debugger-v3 with no `model_info`. Downstream eval keys
    # primarily on `diagnoser_name`, so this silently replaced real
    # debugger artifacts with mock output and defeated the provenance
    # gates added by Codex 2026-05-11..2026-05-20. Fail fast when the
    # loaded config's declared `provider` disagrees with the runtime
    # `--diagnoser` provider.
    if isinstance(diagnoser_config, dict):
        config_provider = diagnoser_config.get("provider")
        if config_provider and config_provider != diagnoser_provider:
            print(
                f"ERROR: diagnoser config "
                f"{diagnoser_config.get('diagnoser_name', diagnoser_name)!r} "
                f"declares provider={config_provider!r} but runtime "
                f"--diagnoser is {diagnoser_provider!r}. Refusing to run: "
                f"running a real-debugger config under the mock provider "
                f"(or vice versa) would write rows under the wrong "
                f"identity. Pass `--diagnoser {config_provider}` to match "
                f"the config, OR use a different --diagnoser-name.",
                file=sys.stderr,
            )
            return 1

    # Per Codex 2026-05-15 F1 [high]: when the diagnoser config declares
    # `model.env_var_name` (e.g. CILOGBENCH_CLAUDE_MODEL) and the user
    # has not set that env var, inject the config's effective requested
    # model into the shim subprocess env. Prevents the failure mode
    # where v2 (config: sonnet) runs against a Claude shim whose
    # hardcoded default is "haiku" and produces rows whose own cache
    # validator later rejects them.
    shim_env = build_shim_env(diagnoser_config)

    # Per Codex 2026-06-06 F1 [high]: BEFORE the shim is invoked,
    # block locked-config runs where the user has set the model env
    # var to a non-canonical value. Without this, the shim would
    # make the wrong-model API call (paying both the $ cost and the
    # privacy cost of shipping CI logs to the wrong backend) and
    # the 2026-06-05 F2 validator would only reject the row after
    # the egress.
    locked_err = check_locked_env_override(diagnoser_config)
    if locked_err is not None:
        print(f"ERROR: {locked_err}", file=sys.stderr)
        return 1

    # Per Codex 2026-05-17 F2 [medium]: collect cache_key env contributions
    # AFTER `build_shim_env` injects config defaults — otherwise the cache
    # key uses the raw (often empty) env while the subprocess runs with
    # the default, so "user did not set X" and "user set X to the config
    # default" produced different keys for identical behaviour.
    key_env_values = cache_key_env_values(diagnoser_config, env_source=shim_env)

    # Per Codex 2026-05-13 F1 [high]: the v3 config declared
    # `privacy.requires_explicit_external_llm_opt_in: true` but the runner
    # never enforced it. The opt-in is the trust-boundary control that
    # prevents accidentally shipping CI log context to an external API on
    # an unrelated diagnoser invocation. Fail closed at the runner BEFORE
    # any provider work happens. The shims also re-check this as
    # belt-and-suspenders so a stale DIAGNOSIS_COMMAND invocation from a
    # different harness cannot bypass the gate.
    gate_err = check_external_llm_opt_in(
        diagnoser_config, provider=diagnoser_provider
    )
    if gate_err is not None:
        print(f"ERROR: {gate_err}", file=sys.stderr)
        return 1

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
        # Per Codex 2026-05-28 F1 [high]: buffer per-case writes in
        # memory; flush only if the method completes without ANY
        # provenance failure. Pre-fix, a provenance failure mid-loop
        # would let earlier successful cases overwrite their per-case
        # JSONs, then the loop-end manifest write would truncate the
        # manifest to the shortened (no-skipped-case) set — leaving
        # stale per-case JSONs for the skipped cases alongside a
        # manifest that doesn't reference them. Buffering preserves
        # the prior method's artifacts intact when any case fails.
        pending_per_case: list[tuple[Path, str]] = []
        method_had_provenance_failure = False
        for m_row in rows:
            case_id = m_row["case_id"]
            ctx_path = ROOT / m_row["context_path"]
            if not ctx_path.exists():
                print(f"  skip {method}/{case_id}: context file missing "
                      f"({ctx_path})", file=sys.stderr)
                continue

            # Per Codex 2026-05-10 [high]: a context-provider (e.g. hybrid
            # router) can emit a method_row whose metadata.provider_error is
            # set when no method could be selected. Previously the diagnoser
            # would happily evaluate the placeholder UNAVAILABLE context and
            # produce a normal low-quality diagnosis row with
            # provider_error=null, hiding the version-skew/data failure
            # behind a benchmark-corrupting low score. Fail closed: if the
            # context-provider already declared a provider_error, propagate
            # it directly into a provider-error diagnosis row WITHOUT
            # invoking the diagnoser.
            ctx_meta = m_row.get("metadata") or {}
            ctx_provider_error = ctx_meta.get("provider_error")
            if ctx_provider_error:
                ctx_text = ""  # not used; we skip the diagnoser
                provider_error_msg = (
                    f"context_provider_error: {ctx_provider_error}"
                )
                diag_body = {
                    "summary": "Context provider failed. See "
                                "metadata.provider_error.",
                    "root_cause_category": "unknown",
                    "root_cause": "unknown",
                    "confidence": 0.0,
                    "relevant_files": [],
                    "relevant_tests": [],
                    "evidence": [],
                    "suggested_fix": "",
                }
                row = build_row(
                    case_id=case_id, context_method=method,
                    diagnoser=diagnoser_name, diagnosis_body=diag_body,
                    context_path=ctx_path, context_text=ctx_text,
                    prompt_sha=prompt_sha, runtime_ms=0.0,
                    provider_name=diagnoser_provider,
                    command_str=command_str, cache_key="",
                    provider_error=provider_error_msg,
                    diagnoser_config_name=config_declared_name,
                    diagnoser_config_sha256_value=diagnoser_config_sha,
                    shim_sha256_value=shim_sha,
                )
                out_rows.append(row)
                method_cache_misses += 1
                continue

            ctx_text = ctx_path.read_text(encoding="utf-8", errors="replace")
            ctx_sha = sha256_text(ctx_text)
            safe_meta = load_safe_case_metadata(cases_dir, split, case_id)

            key = cache_key_for(
                case_id=case_id, context_method=method,
                context_sha=ctx_sha, prompt_sha=prompt_sha,
                provider=diagnoser_provider, diagnoser=diagnoser_name,
                command_str=command_str, env_values=key_env_values,
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
                        candidate = cached["row"]
                        ok, reason = cache_hit_is_acceptable(
                            candidate, diagnoser_config,
                            cache_errors=cache_errors,
                            current_diagnoser_config_sha=diagnoser_config_sha,
                            current_shim_sha=shim_sha,
                        )
                        if ok:
                            cached_row = candidate
                        else:
                            # Per Codex 2026-05-12 F2: log and fall through
                            # to a fresh provider call. The on-disk cache
                            # file is left in place; the fresh row will
                            # overwrite it under the SAME key (the env-var
                            # change should already have produced a
                            # different key — this branch handles the case
                            # where env-driven keying isn't sufficient,
                            # e.g. the config changed but the env did not).
                            print(
                                f"  cache_reject {method}/{case_id}: {reason}",
                                file=sys.stderr,
                            )
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
                        # Per Codex 2026-05-21 F1 [high] (defense-in-
                        # depth): run the same fresh-row provenance gate
                        # on mock rows. The earlier provider/config-match
                        # check should have caught the mismatched case
                        # at config-load time, but apply this here too so
                        # a mock-provider invocation under a real-
                        # debugger config can NEVER emit a successful
                        # row without _model_info — even if someone
                        # bypasses the early check by hand-editing.
                        mock_mismatch = validate_fresh_row_model_identity(
                            diag_body, diagnoser_config
                        )
                        if mock_mismatch:
                            raise ProvenanceMismatchError(
                                f"mock_provider_under_real_config: {mock_mismatch}"
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
                            env=shim_env,
                        )
                        # Per Codex 2026-05-15 F1 [high]: validate the
                        # fresh row's model identity BEFORE writing the
                        # cache entry or per-case JSON. Without this,
                        # a misconfigured shim/config pair could write
                        # a row under the diagnoser's name whose actual
                        # model differs (e.g. v2 expects 'sonnet' but
                        # the Claude shim's default 'haiku' was used).
                        # On mismatch, raise so the normal exception
                        # path turns this into a provider_error row
                        # (no cache write thanks to the `cache_errors`
                        # default being off).
                        mismatch = validate_fresh_row_model_identity(
                            diag_body, diagnoser_config
                        )
                        if mismatch:
                            raise ProvenanceMismatchError(
                                f"fresh_row_model_identity_mismatch: {mismatch}"
                            )
                    else:
                        raise ValueError(
                            f"unknown diagnoser provider: {diagnoser_provider}"
                        )
                except ProvenanceMismatchError as e:
                    # Per Codex 2026-05-27 F1 [high]: provenance
                    # mismatches do NOT produce a stub provider_error
                    # row — writing under the canonical diagnoser_name
                    # IS the violation. Skip the case entirely, mark
                    # the run as failed.
                    # Per Codex 2026-05-28 F1 [high]: also mark the
                    # ENTIRE method as provenance-failed so the
                    # loop-end flush leaves existing manifest +
                    # per-case JSONs intact. Otherwise the buffered
                    # writes from earlier successful cases would
                    # overwrite their per-case files and the
                    # shortened manifest would truncate the prior
                    # canonical state.
                    print(
                        f"FAIL_PROVENANCE {method}/{case_id}: {e}",
                        file=sys.stderr,
                    )
                    had_failure = True
                    method_had_provenance_failure = True
                    if strict:
                        return 1
                    continue
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
                    # Per Codex 2026-05-16 F1 [high]: preserve shim-emitted
                    # model_info on the error path. Without this, post-API
                    # failures (e.g. JSONDecodeError from a malformed
                    # model response) landed in manifests with
                    # metadata.model_info=null — same shape as a no-call
                    # oversized-context skip — which broke auditability
                    # for failed-but-attempted API calls.
                    if isinstance(e, ShimCallError):
                        if e.model_info is not None:
                            diag_body["_model_info"] = e.model_info
                        if e.provider_error_hint:
                            diag_body["_provider_error"] = e.provider_error_hint
                        # Per Codex 2026-05-29 F2 + 2026-05-30 F1 [high]:
                        # ONLY validate provenance when the shim's
                        # error-envelope ACTUALLY carries model_info.
                        # Pre-fix (2026-05-29 F2 alone) ran the check
                        # unconditionally, which misclassified
                        # legitimate no-call failures (oversized
                        # context, missing OPENAI_API_KEY, transport
                        # errors) as provenance corruption under
                        # real-debugger configs that require
                        # provenance — losing 39 expected
                        # `unsupported_context_too_large` rows on v3
                        # to method-level skips. The contract: if the
                        # shim claimed model_info (i.e. reached the
                        # API), validate it; if not, fall through
                        # to write a clean provider_error row with
                        # model_info: null.
                        if e.model_info is not None:
                            prov_err = validate_fresh_row_model_identity(
                                diag_body, diagnoser_config
                            )
                            if prov_err:
                                print(
                                    f"FAIL_PROVENANCE {method}/{case_id}: "
                                    f"shim_error_row {prov_err}",
                                    file=sys.stderr,
                                )
                                had_failure = True
                                method_had_provenance_failure = True
                                if strict:
                                    return 1
                                continue
                runtime_ms = (time.perf_counter() - t0) * 1000

                row = build_row(
                    case_id=case_id, context_method=method,
                    diagnoser=diagnoser_name, diagnosis_body=diag_body,
                    context_path=ctx_path, context_text=ctx_text,
                    prompt_sha=prompt_sha, runtime_ms=runtime_ms,
                    provider_name=diagnoser_provider,
                    command_str=command_str, cache_key=key,
                    provider_error=provider_error,
                    diagnoser_config_name=config_declared_name,
                    diagnoser_config_sha256_value=diagnoser_config_sha,
                    shim_sha256_value=shim_sha,
                )
                method_cache_misses += 1

                # Per Codex 2026-05-22 F2 [medium]: the cache gate
                # historically only checked the exception-local
                # `provider_error` variable, but the shim can exit 0
                # while still emitting `_provider_error` (the JSON
                # envelope path added 2026-05-16 F1). In that case
                # `provider_error` here is None but the ROW carries
                # `metadata.provider_error` (lifted by build_row from
                # `_provider_error`). Pre-fix, that row was cached
                # without --cache-errors and a transient provider
                # failure could replay as a cache hit on every
                # subsequent run. Fix: gate on the row's actual
                # `metadata.provider_error` so any provider-error row
                # — exception-caught OR shim-declared — requires
                # `--cache-errors` to be cached.
                effective_provider_error = (
                    (row.get("metadata") or {}).get("provider_error")
                )
                # Per Codex 2026-06-08 F1 [high]: fresh provider_error
                # rows must default to fail-closed. Pre-fix, the
                # generic `except Exception` path caught auth failures,
                # transport errors, malformed model JSON, etc., wrote
                # an "unknown" diagnosis row, and the runner exited 0
                # — wrappers then evaluated/rendered/published failed
                # runs as a successful experiment. Now: any
                # provider_error sets had_failure UNLESS its prefix is
                # in the config's explicit non-fatal allowlist.
                # Canonical real-debugger configs declare
                # `["unsupported_context_too_large"]` as the only
                # non-fatal class (oversized-context refusal is the
                # documented graceful path on v3); everything else
                # fails the run.
                if effective_provider_error:
                    non_fatal = (
                        ((diagnoser_config or {}).get("provider_policy") or {})
                        .get("non_fatal_provider_error_prefixes") or []
                    )
                    matched = any(
                        isinstance(p, str) and effective_provider_error.startswith(p)
                        for p in non_fatal
                    )
                    if not matched:
                        had_failure = True
                        print(
                            f"FAIL_PROVIDER_ERROR {method}/{case_id}: "
                            f"{effective_provider_error[:160]!r} "
                            f"not in non_fatal_provider_error_prefixes "
                            f"{non_fatal!r}",
                            file=sys.stderr,
                        )
                        if strict:
                            return 1
                if not effective_provider_error or cache_errors:
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

            # Per Codex 2026-05-28 F1 [high]: BUFFER per-case writes
            # instead of flushing immediately. They get flushed at
            # the end of the method ONLY IF no provenance failure
            # occurred. Otherwise the existing on-disk per-case JSON
            # for this case_id stays as the canonical version (since
            # the new row was built from valid identity, that's fine;
            # the corruption Codex flagged was about OTHER cases'
            # writes happening while a different case failed).
            per_case_path = method_dir / f"{case_id}.json"
            pending_per_case.append(
                (per_case_path,
                 json.dumps(row, ensure_ascii=False, indent=2) + "\n")
            )
            out_rows.append(row)

        # Per Codex 2026-05-28 F1 [high]: when ANY case in the method
        # provenance-failed, skip BOTH the per-case writes AND the
        # manifest replacement. The existing on-disk artifacts for
        # this method remain the canonical state. Without this, a
        # rotated alias or stale shim could truncate a prior valid
        # manifest to a shortened (skipped-case) version while
        # leaving stale per-case JSONs alongside it.
        if method_had_provenance_failure:
            try:
                display_path = str(manifest_path.relative_to(ROOT))
            except ValueError:
                display_path = str(manifest_path)
            print(
                f"  {method}: PROVENANCE-FAILED — preserved existing "
                f"manifest + per-case JSONs at "
                f"{display_path} (no writes applied)"
            )
            continue

        # Flush buffered per-case writes.
        for path, content in pending_per_case:
            path.write_text(content, encoding="utf-8")

        with manifest_path.open("w", encoding="utf-8") as f:
            for row in out_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        try:
            display_path = str(manifest_path.relative_to(ROOT))
        except ValueError:
            # results-dir outside ROOT (e.g. tests with tmp dirs). Same
            # fallback pattern audit_context_privacy.py uses.
            display_path = str(manifest_path)
        print(f"  {method}: wrote {len(out_rows)} diagnoses to "
              f"{display_path} "
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
    ap.add_argument(
        "--allow-external-llm", action="store_true",
        help=(
            "Equivalent to setting CILOGBENCH_ALLOW_EXTERNAL_LLM=1 for the "
            "lifetime of this invocation. Wrappers that already accept "
            "--allow-external-llm propagate it here so a wrapper-level "
            "opt-in doesn't get re-prompted at the runner level. "
            "Per Codex 2026-05-14 F1."
        ),
    )
    ap.add_argument(
        "--diagnoser-config", type=Path, default=None,
        help=(
            "Path to the validated diagnoser config (a *.json under "
            "configs/diagnosers/ or a wrapper-resolved location). When "
            "supplied, the runner loads cache_key_env / privacy / model "
            "settings from this exact file and fails fast if its "
            "`diagnoser_name` does not match --diagnoser-name. Falls "
            "back to legacy auto-discovery by name when omitted. Per "
            "Codex 2026-05-15 F2."
        ),
    )
    args = ap.parse_args(argv)

    # Per Codex 2026-05-14 F1: when a wrapper or operator opts in via the
    # CLI flag, hoist that into the env so the gate + shims (which check
    # the env var) see it. This is the documented "wrapper CLI flag"
    # path; the env-var path continues to work unchanged.
    if args.allow_external_llm:
        os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"

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
        diagnoser_config_path=args.diagnoser_config,
    )


if __name__ == "__main__":
    raise SystemExit(main())
