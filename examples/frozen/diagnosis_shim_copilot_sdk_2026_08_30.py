#!/usr/bin/env python3
"""Single-shot LogDx diagnoser using the pinned GitHub Copilot Python SDK."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, is_dataclass


FORBIDDEN_KEYS = (
    "ground_truth",
    "failure_category",
    "required_signals",
    "evidence_spans",
    "expected_diagnosis",
)
TRUTHY = {"1", "true", "yes", "on"}
CATEGORY_ENUM = {
    "test_assertion", "compile_error", "type_error", "lint_failure",
    "formatting_failure", "dependency_install", "docker_build",
    "github_actions_config", "permission_or_secret", "network_or_flaky",
    "timeout_or_oom", "unknown", "other",
}
EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EXPECTED_SDK_VERSION = "1.0.11"
TOKENIZER = "o200k_base"
LONG_CONTEXT_TIER = "long_context"
PROMPT_TOKEN_RESERVE = 1_000


class ContextTooLargeError(Exception):
    pass


class ProvenanceError(Exception):
    pass


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _safe_error(exc: BaseException) -> str:
    raw = f"{type(exc).__name__}: {exc}"
    return (
        f"{type(exc).__name__} message_sha256={_hash_text(raw)[:16]}… "
        f"message_len={len(raw)}"
    )


def verify_no_leakage(payload: dict) -> None:
    def walk(obj: object, path: str) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_path = f"{path}.{key}" if path else str(key)
                if any(forbidden in str(key) for forbidden in FORBIDDEN_KEYS):
                    raise ValueError(f"forbidden key in payload at {key_path}")
                walk(value, key_path)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                walk(value, f"{path}[{index}]")

    walk(payload, "")


def normalize(diag_raw: dict) -> dict:
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
    out["evidence"] = [
        {"quote": str(item["quote"]), "reason": str(item["reason"])}
        for item in out["evidence"]
        if isinstance(item, dict) and "quote" in item and "reason" in item
    ]
    return out


def parse_diagnosis_json(text: str) -> dict:
    stripped = text.strip()
    fenced = re.match(r"```(?:json)?\s*(.+?)\s*```$", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(
            "no JSON object in model reply: "
            f"reply_sha256={_hash_text(stripped)[:16]}… reply_len={len(stripped)}"
        )
    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("model JSON root is not an object")
    return parsed


def build_prompt(payload: dict) -> str:
    metadata = payload.get("safe_case_metadata") or {}
    return "\n".join(
        [
            "# Benchmark instruction", "", str(payload.get("prompt", "")), "",
            "# Safe case metadata", "",
            json.dumps(metadata, ensure_ascii=False, indent=2), "",
            "# CI log context", "", str(payload.get("context", "")), "",
            "Return STRICT JSON matching the benchmark instruction.",
            "Return JSON only. Do not use Markdown fences.",
        ]
    )


def _event_type(event: object) -> str:
    value = getattr(event, "type", "")
    return str(getattr(value, "value", value))


def _plain_data(value: object) -> dict:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def validate_event_provenance(events: list[object], model: str) -> tuple[dict, dict]:
    session_starts = [
        _plain_data(event.data)
        for event in events
        if _event_type(event) == "session.start"
    ]
    usage_info = [
        _plain_data(event.data)
        for event in events
        if _event_type(event) == "session.usage_info"
    ]
    starts = [
        _plain_data(event.data)
        for event in events
        if _event_type(event) == "model.call_start"
    ]
    changes = [
        _plain_data(event.data)
        for event in events
        if _event_type(event) == "session.model_change"
    ]
    usages = [
        _plain_data(event.data)
        for event in events
        if _event_type(event) == "assistant.usage"
    ]
    if len(session_starts) != 1:
        raise ProvenanceError(f"expected one session.start, got {len(session_starts)}")
    session_start = session_starts[0]
    if session_start.get("selected_model") != model:
        raise ProvenanceError("session.start selected model mismatch")
    if _enum_value(session_start.get("context_tier")) != LONG_CONTEXT_TIER:
        raise ProvenanceError("session.start did not resolve long_context tier")
    if not usage_info or max(int(item.get("token_limit") or 0) for item in usage_info) < 922_000:
        raise ProvenanceError("session token limit did not prove 922000-token tier")

    starts_models = [item.get("model") for item in starts]
    changed_models = [item.get("new_model") for item in changes]
    if len(starts_models) != 1 or starts_models[0] != model:
        observed = ",".join(str(item) for item in starts_models)
        raise ProvenanceError(
            f"prompt-time model dispatch mismatch: expected={model}, "
            f"observed_sha256={_hash_text(observed)[:16]}… count={len(starts_models)}"
        )
    if any(changed and changed != model for changed in changed_models):
        observed = ",".join(str(item) for item in changed_models)
        raise ProvenanceError(
            f"session model changed away from requested model: "
            f"observed_sha256={_hash_text(observed)[:16]}…"
        )
    if len(usages) != 1:
        raise ProvenanceError(f"expected one assistant usage event, got {len(usages)}")

    usage = usages[0]
    usage_model = usage.get("model")
    tool_count = int(usage.get("_num_tool_calls") or 0)
    available_tool_count = int(usage.get("_available_tool_count") or 0)
    if usage_model != model:
        raise ProvenanceError("assistant.usage model mismatch")
    if tool_count or available_tool_count:
        raise ProvenanceError(
            f"nonzero tool surface: available={available_tool_count}, used={tool_count}"
        )
    return session_start, usage


def _duration_ms(value: object) -> float | None:
    if value is None:
        return None
    if hasattr(value, "total_seconds"):
        return round(float(value.total_seconds()) * 1000, 3)
    return None


async def invoke_sdk(
    *, prompt: str, model: str, effort: str, timeout_s: int
) -> tuple[str, dict]:
    try:
        import tiktoken
        from copilot import CopilotClient
        from copilot.session import PermissionDecisionUserNotAvailable
    except ImportError as exc:  # pragma: no cover - exercised by main envelope
        raise RuntimeError("github-copilot-sdk and tiktoken are required") from exc

    sdk_version = importlib.metadata.version("github-copilot-sdk")
    if sdk_version != EXPECTED_SDK_VERSION:
        raise RuntimeError(
            f"github-copilot-sdk version mismatch: expected "
            f"{EXPECTED_SDK_VERSION}, got {sdk_version}"
        )

    encoding = tiktoken.get_encoding(TOKENIZER)
    counted_prompt_tokens = len(encoding.encode(prompt))
    events: list[object] = []

    def on_event(event: object) -> None:
        events.append(event)

    def deny_permission(*_args: object, **_kwargs: object):
        return PermissionDecisionUserNotAvailable()

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="logdx-copilot-sdk-") as temp_dir:
        async with CopilotClient(
            mode="empty",
            base_directory=temp_dir,
            working_directory=temp_dir,
            log_level="error",
        ) as client:
            models = await client.list_models()
            model_info = next((item for item in models if item.id == model), None)
            if model_info is None:
                raise RuntimeError(f"requested model is unavailable: {model}")
            limits = model_info.capabilities.limits
            token_prices = model_info.billing.token_prices
            long_prices = token_prices.long_context
            max_prompt_tokens = int(long_prices.max_prompt_tokens)
            max_context_tokens = int(limits.max_context_window_tokens)
            if max_prompt_tokens < 900_000 or max_context_tokens < 1_000_000:
                raise RuntimeError(
                    "long-context capability below study requirement: "
                    f"max_prompt_tokens={max_prompt_tokens}, "
                    f"max_context_window_tokens={max_context_tokens}"
                )
            usable_prompt_tokens = max_prompt_tokens - PROMPT_TOKEN_RESERVE
            if counted_prompt_tokens > usable_prompt_tokens:
                raise ContextTooLargeError(
                    f"prompt ({counted_prompt_tokens} tokens via {TOKENIZER}) "
                    f"exceeds safe SDK cap ({usable_prompt_tokens}; provider "
                    f"max {max_prompt_tokens} minus {PROMPT_TOKEN_RESERVE} reserve)"
                )

            session = await client.create_session(
                model=model,
                reasoning_effort=effort,
                context_tier=LONG_CONTEXT_TIER,
                tools=[],
                available_tools=[],
                on_permission_request=deny_permission,
                system_message={
                    "mode": "replace",
                    "content": "Follow the user instruction exactly. Do not use tools.",
                },
                streaming=False,
                infinite_sessions={"enabled": False},
                memory={"enabled": False},
                enable_session_store=False,
                enable_config_discovery=False,
                skip_custom_instructions=True,
                enable_skills=False,
                mcp_servers={},
                skip_embedding_retrieval=True,
                enable_file_change_tracking=False,
                enable_citations=False,
                on_event=on_event,
            )
            try:
                response = await asyncio.wait_for(
                    session.send_and_wait(prompt), timeout=timeout_s
                )
            finally:
                await session.disconnect()

    session_start, usage = validate_event_provenance(events, model)
    tool_count = int(usage.get("_num_tool_calls") or 0)
    available_tool_count = int(usage.get("_available_tool_count") or 0)
    if response is None or _event_type(response) != "assistant.message":
        raise RuntimeError("SDK returned no final assistant message")
    reply = str(getattr(response.data, "content", ""))
    copilot_usage = usage.get("copilot_usage") or {}
    return reply, {
        "provider_name": "github-copilot",
        "requested_model": model,
        "resolved_model": model,
        "model_version": model,
        "sdk_version": sdk_version,
        "cli_version": str(session_start.get("copilot_version")),
        "transport": "copilot-sdk-jsonrpc",
        "reasoning_effort_requested": effort,
        "reasoning_effort_resolved": usage.get("reasoning_effort"),
        "context_mode": LONG_CONTEXT_TIER,
        "context_tier": LONG_CONTEXT_TIER,
        "max_context_window_tokens": max_context_tokens,
        "max_prompt_tokens_capability": max_prompt_tokens,
        "max_prompt_tokens": max_prompt_tokens,
        "safe_prompt_token_cap": usable_prompt_tokens,
        "tokenizer": TOKENIZER,
        "prompt_tokens_counted": counted_prompt_tokens,
        "tools_available": available_tool_count,
        "tool_count": tool_count,
        "custom_instructions": False,
        "memory_enabled": False,
        "infinite_sessions_enabled": False,
        "session_store_enabled": False,
        "isolated_copilot_home": True,
        "usage": {
            "prompt_tokens": usage.get("input_tokens"),
            "completion_tokens": usage.get("output_tokens"),
            "total_tokens": (
                int(usage.get("input_tokens") or 0)
                + int(usage.get("output_tokens") or 0)
            ),
            "cache_read_tokens": usage.get("cache_read_tokens"),
            "cache_write_tokens": usage.get("cache_write_tokens"),
            "reasoning_tokens": usage.get("reasoning_tokens"),
        },
        "observable_ai_usage": {
            "token_details": copilot_usage.get("_token_details"),
            "total_nano_aiu": copilot_usage.get("total_nano_aiu"),
        },
        "model_call_duration_ms": _duration_ms(usage.get("duration")),
        "sdk_session_duration_ms": round((time.monotonic() - started) * 1000, 3),
    }


def main() -> int:
    payload = json.load(sys.stdin)
    verify_no_leakage(payload)
    if (os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM") or "").lower() not in TRUTHY:
        sys.stderr.write(
            "diagnosis_shim_copilot_sdk: CILOGBENCH_ALLOW_EXTERNAL_LLM=1 is required.\n"
        )
        return 1
    model = (os.environ.get("CILOGBENCH_COPILOT_MODEL") or "").strip()
    effort = (os.environ.get("CILOGBENCH_COPILOT_REASONING_EFFORT") or "low").strip()
    timeout_s = int(os.environ.get("CILOGBENCH_COPILOT_TIMEOUT", "600"))
    if not model or not MODEL_RE.fullmatch(model):
        sys.stderr.write("diagnosis_shim_copilot_sdk: valid model required.\n")
        return 1
    if effort not in EFFORTS:
        sys.stderr.write(f"diagnosis_shim_copilot_sdk: unsupported effort {effort!r}.\n")
        return 1
    prompt = build_prompt(payload)
    try:
        reply, model_info = asyncio.run(
            invoke_sdk(prompt=prompt, model=model, effort=effort, timeout_s=timeout_s)
        )
        diagnosis = normalize(parse_diagnosis_json(reply))
        diagnosis["_model_info"] = model_info
        json.dump(diagnosis, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except ContextTooLargeError as exc:
        json.dump({"_provider_error": f"unsupported_context_too_large: {exc}"}, sys.stdout)
        sys.stdout.write("\n")
        return 1
    except Exception as exc:
        envelope = {"_provider_error": f"copilot_sdk_error: {_safe_error(exc)}"}
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
