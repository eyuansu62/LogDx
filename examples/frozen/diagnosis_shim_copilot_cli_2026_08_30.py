#!/usr/bin/env python3
"""Single-shot LogDx diagnoser backed by GitHub Copilot CLI.

The shim deliberately exposes no tools to the model. It also uses an isolated
Copilot home so user MCP servers, hooks, memory, and custom instructions do not
enter the benchmark prompt. GitHub CLI authentication remains available to the
Copilot CLI through its normal authentication fallback.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


FORBIDDEN_KEYS = (
    "ground_truth",
    "failure_category",
    "required_signals",
    "evidence_spans",
    "expected_diagnosis",
)
TRUTHY = {"1", "true", "yes", "on"}
CATEGORY_ENUM = {
    "test_assertion",
    "compile_error",
    "type_error",
    "lint_failure",
    "formatting_failure",
    "dependency_install",
    "docker_build",
    "github_actions_config",
    "permission_or_secret",
    "network_or_flaky",
    "timeout_or_oom",
    "unknown",
    "other",
}
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
CONTEXT_MODES = {"default", "long_context"}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ContextTooLargeError(Exception):
    pass


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _safe_error(exc: BaseException) -> str:
    raw = f"{type(exc).__name__}: {exc}"
    return (
        f"{type(exc).__name__} message_sha256={_hash_text(raw)[:16]}… "
        f"message_len={len(raw)}"
    )


def _model_from_config_update(update: dict) -> str | None:
    if update.get("sessionUpdate") != "config_option_update":
        return None
    for option in update.get("configOptions", []):
        if isinstance(option, dict) and option.get("id") == "model":
            value = option.get("currentValue")
            return str(value) if value is not None else None
    return None


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


def build_prompt(payload: dict, *, max_context_chars: int | None) -> str:
    context = str(payload.get("context", ""))
    if max_context_chars is not None and len(context) > max_context_chars:
        raise ContextTooLargeError(
            f"context ({len(context)} chars) exceeds shim cap "
            f"({max_context_chars})"
        )
    metadata = payload.get("safe_case_metadata") or {}
    return "\n".join(
        [
            "# Benchmark instruction",
            "",
            str(payload.get("prompt", "")),
            "",
            "# Safe case metadata",
            "",
            json.dumps(metadata, ensure_ascii=False, indent=2),
            "",
            "# CI log context",
            "",
            context,
            "",
            "Return STRICT JSON matching the benchmark instruction.",
            "Return JSON only. Do not use Markdown fences.",
        ]
    )


def _copilot_version() -> str:
    try:
        result = subprocess.run(
            ["copilot", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        raise RuntimeError(f"copilot version check failed: {_safe_error(exc)}") from exc
    if result.returncode != 0:
        raise RuntimeError(f"copilot version check exited {result.returncode}")
    return (result.stdout or "").splitlines()[0].strip()


def _parse_events(stdout: str) -> tuple[str, dict]:
    response_parts: list[str] = []
    model_info: dict = {}
    call_success: dict | None = None
    result_event: dict | None = None

    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        data = event.get("data") or {}
        if event_type in {"model.turn_started", "model.model_call_started"}:
            info = data.get("modelInfo") or {}
            capabilities = info.get("capabilities") or {}
            limits = capabilities.get("limits") or {}
            model_info.update(
                {
                    "resolved_model": info.get("id") or data.get("model"),
                    "model_version": info.get("version"),
                    "max_context_window_tokens": limits.get("max_context_window_tokens"),
                    "max_prompt_tokens_capability": limits.get("max_prompt_tokens"),
                    "tokenizer": capabilities.get("tokenizer"),
                }
            )
        elif event_type == "assistant.message_delta":
            if data.get("phase") == "final_answer":
                response_parts.append(str(data.get("deltaContent", "")))
        elif event_type == "assistant.message":
            if data.get("phase") == "final_answer":
                response_parts.append(str(data.get("content", "")))
        elif event_type == "model.model_call_success":
            call_success = data
        elif event_type == "result":
            result_event = event

    if call_success is not None:
        response_usage = call_success.get("responseUsage") or {}
        model_info.update(
            {
                "reasoning_effort_resolved": call_success.get("reasoningEffort"),
                "max_prompt_tokens": call_success.get("maxPromptTokens"),
                "tool_count": call_success.get("toolCount"),
                "usage": response_usage,
                "observable_ai_usage": call_success.get("copilotUsage"),
                "model_call_duration_ms": call_success.get("modelCallDurationMs"),
            }
        )
    if result_event is not None:
        model_info["cli_result_usage"] = result_event.get("usage")

    return "".join(response_parts), model_info


def invoke_copilot(
    *, prompt: str, model: str, effort: str, context_mode: str, timeout_s: int
) -> tuple[str, dict]:
    if context_mode == "long_context":
        return _invoke_copilot_acp(
            prompt=prompt,
            model=model,
            effort=effort,
            context_mode=context_mode,
            timeout_s=timeout_s,
        )

    with tempfile.TemporaryDirectory(prefix="logdx-copilot-") as temp_dir:
        temp_path = Path(temp_dir)
        usage_path = temp_path / "usage.json"
        env = os.environ.copy()
        env["COPILOT_HOME"] = str(temp_path / "copilot-home")
        argv = [
            "copilot",
            "-p",
            prompt,
            "--model",
            model,
            "--effort",
            effort,
            "--context",
            context_mode,
            "--output-format",
            "json",
            "--stream",
            "off",
            "--allow-all-tools",
            "--available-tools",
            "__logdx_no_tools__",
            "--no-custom-instructions",
            "--disable-builtin-mcps",
            "--no-remote",
            "--no-auto-update",
            "--max-ai-credits",
            "30",
            "--usage-output-file",
            str(usage_path),
        ]
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"copilot CLI exited {result.returncode}; "
                f"stdout_sha256={_hash_text(result.stdout or '')[:16]}… "
                f"stderr_sha256={_hash_text(result.stderr or '')[:16]}…"
            )
        reply, model_info = _parse_events(result.stdout or "")
        if model_info.get("tool_count") != 0:
            raise RuntimeError(
                "copilot single-shot isolation failed: "
                f"tool_count={model_info.get('tool_count')!r}"
            )
        if not reply:
            raise RuntimeError(
                "copilot CLI returned no final answer; "
                f"stdout_sha256={_hash_text(result.stdout or '')[:16]}…"
            )
        return reply, model_info


def _invoke_copilot_acp(
    *, prompt: str, model: str, effort: str, context_mode: str, timeout_s: int
) -> tuple[str, dict]:
    """Send large prompts over ACP stdio instead of the process argument list."""
    with tempfile.TemporaryDirectory(prefix="logdx-copilot-acp-") as temp_dir:
        env = os.environ.copy()
        env["COPILOT_HOME"] = str(Path(temp_dir) / "copilot-home")
        argv = [
            "copilot",
            "--acp",
            "--stdio",
            "--model",
            model,
            "--effort",
            effort,
            "--context",
            context_mode,
            "--available-tools",
            "__logdx_no_tools__",
            "--no-custom-instructions",
            "--disable-builtin-mcps",
            "--no-remote",
            "--no-auto-update",
            "--max-ai-credits",
            "30",
        ]
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1,
        )
        if process.stdin is None or process.stdout is None or process.stderr is None:
            process.kill()
            raise RuntimeError("copilot ACP stdio pipes unavailable")

        messages: queue.Queue[dict | BaseException | None] = queue.Queue()
        stderr_parts: list[str] = []

        def read_stdout() -> None:
            try:
                for line in process.stdout:
                    if not line.strip():
                        continue
                    messages.put(json.loads(line))
            except BaseException as exc:  # forwarded and redacted by the caller
                messages.put(exc)
            finally:
                messages.put(None)

        def read_stderr() -> None:
            for line in process.stderr:
                stderr_parts.append(line)

        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        deadline = time.monotonic() + timeout_s

        def send(message: dict) -> None:
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            process.stdin.flush()

        def receive() -> dict:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout_s)
            try:
                message = messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise subprocess.TimeoutExpired(argv, timeout_s) from exc
            if message is None:
                raise RuntimeError(
                    "copilot ACP ended before response; "
                    f"stderr_sha256={_hash_text(''.join(stderr_parts))[:16]}…"
                )
            if isinstance(message, BaseException):
                raise RuntimeError(f"copilot ACP decode failed: {_safe_error(message)}")
            return message

        def response_for(
            request_id: int, *, collect_reply: bool = False
        ) -> tuple[dict, str, int, str | None]:
            parts: list[str] = []
            tool_calls = 0
            observed_model: str | None = None
            while True:
                message = receive()
                if message.get("method") == "session/request_permission":
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"outcome": {"outcome": "cancelled"}},
                        }
                    )
                    continue
                if message.get("id") == request_id:
                    if "error" in message:
                        error = json.dumps(message["error"], ensure_ascii=False)
                        raise RuntimeError(
                            "copilot ACP request failed: "
                            f"error_sha256={_hash_text(error)[:16]}… error_len={len(error)}"
                        )
                    return (
                        message.get("result") or {},
                        "".join(parts),
                        tool_calls,
                        observed_model,
                    )
                if not collect_reply or message.get("method") != "session/update":
                    continue
                update = ((message.get("params") or {}).get("update") or {})
                kind = update.get("sessionUpdate")
                changed_model = _model_from_config_update(update)
                if changed_model is not None:
                    observed_model = changed_model
                if kind in {"tool_call", "tool_call_update"}:
                    tool_calls += 1
                if kind != "agent_message_chunk":
                    continue
                content = update.get("content") or {}
                text = str(content.get("text", ""))
                # These two notices describe the deliberate empty tool surface.
                # They are ACP transport messages, not model output.
                if text.startswith("Info: Disabled tools:") or text.startswith(
                    "Info: Unknown tool name in the tool allowlist:"
                ):
                    continue
                parts.append(text)

        try:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": 1, "clientCapabilities": {}},
                }
            )
            initialized, _, _, _ = response_for(1)
            agent_info = initialized.get("agentInfo") or {}
            send(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "session/new",
                    "params": {"cwd": str(Path.cwd()), "mcpServers": []},
                }
            )
            session, _, _, _ = response_for(2)
            session_id = session.get("sessionId")
            models = session.get("models") or {}
            resolved_model = models.get("currentModelId")
            available = {
                item.get("modelId"): item
                for item in models.get("availableModels", [])
                if isinstance(item, dict)
            }
            if model not in available:
                raise RuntimeError(f"requested Copilot model is unavailable: {model}")
            if resolved_model != model:
                raise RuntimeError(
                    "Copilot model identity mismatch before prompt: "
                    f"requested={model!r} resolved={resolved_model!r}"
                )
            send(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "session/prompt",
                    "params": {
                        "sessionId": session_id,
                        "prompt": [{"type": "text", "text": prompt}],
                    },
                }
            )
            started = time.monotonic()
            result, reply, tool_calls, prompt_model = response_for(
                3, collect_reply=True
            )
            resolved_model = prompt_model or resolved_model
            if resolved_model != model:
                raise RuntimeError(
                    "Copilot model identity mismatch during prompt: "
                    f"requested={model!r} resolved={resolved_model!r}"
                )
            if tool_calls:
                raise RuntimeError(
                    f"copilot ACP isolation failed: tool_call_count={tool_calls}"
                )
            if result.get("stopReason") != "end_turn":
                raise RuntimeError(
                    f"copilot ACP stopped with {result.get('stopReason')!r}"
                )
            if not reply:
                raise RuntimeError("copilot ACP returned no final answer")
            selected_meta = available[model].get("_meta") or {}
            return reply, {
                "resolved_model": resolved_model,
                "reasoning_effort_resolved": effort,
                "tool_count": 0,
                "usage": result.get("usage") or {},
                "observable_ai_usage": selected_meta.get("copilotUsage"),
                "copilot_price_category": selected_meta.get("copilotPriceCategory"),
                "model_call_duration_ms": round((time.monotonic() - started) * 1000),
                "cli_version": agent_info.get("version"),
                "transport": "acp-stdio",
            }
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def _max_context_chars(context_mode: str) -> int | None:
    raw = os.environ.get("CILOGBENCH_COPILOT_MAX_CONTEXT_CHARS")
    if raw is not None:
        value = int(raw)
        if value < 1:
            raise ValueError("CILOGBENCH_COPILOT_MAX_CONTEXT_CHARS must be >= 1")
        return value
    if context_mode == "default":
        return 480_000
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    verify_no_leakage(payload)

    if (os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM") or "").lower() not in TRUTHY:
        sys.stderr.write(
            "diagnosis_shim_copilot_cli: CILOGBENCH_ALLOW_EXTERNAL_LLM=1 "
            "is required.\n"
        )
        return 1

    model = (os.environ.get("CILOGBENCH_COPILOT_MODEL") or "").strip()
    effort = (os.environ.get("CILOGBENCH_COPILOT_REASONING_EFFORT") or "low").strip()
    context_mode = (os.environ.get("CILOGBENCH_COPILOT_CONTEXT_MODE") or "default").strip()
    timeout_s = int(os.environ.get("CILOGBENCH_COPILOT_TIMEOUT", "240"))

    if not model or not MODEL_RE.fullmatch(model):
        sys.stderr.write("diagnosis_shim_copilot_cli: valid CILOGBENCH_COPILOT_MODEL required.\n")
        return 1
    if effort not in EFFORTS:
        sys.stderr.write(f"diagnosis_shim_copilot_cli: unsupported reasoning effort {effort!r}.\n")
        return 1
    if context_mode not in CONTEXT_MODES:
        sys.stderr.write(f"diagnosis_shim_copilot_cli: unsupported context mode {context_mode!r}.\n")
        return 1

    try:
        prompt = build_prompt(payload, max_context_chars=_max_context_chars(context_mode))
    except ContextTooLargeError as exc:
        json.dump({"_provider_error": f"unsupported_context_too_large: {exc}"}, sys.stdout)
        sys.stdout.write("\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"diagnosis_shim_copilot_cli: {_safe_error(exc)}\n")
        return 1

    base_model_info = {
        "provider_name": "github-copilot",
        "requested_model": model,
        "resolved_model": None,
        "cli_version": None,
        "reasoning_effort_requested": effort,
        "context_mode": context_mode,
        "max_context_chars": _max_context_chars(context_mode),
        "tools_available": 0,
        "custom_instructions": False,
        "isolated_copilot_home": True,
    }

    try:
        base_model_info["cli_version"] = _copilot_version()
        reply, observed = invoke_copilot(
            prompt=prompt,
            model=model,
            effort=effort,
            context_mode=context_mode,
            timeout_s=timeout_s,
        )
        base_model_info.update(observed)
    except Exception as exc:
        envelope = {
            "_model_info": base_model_info,
            "_provider_error": f"copilot_cli_error: {_safe_error(exc)}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1

    try:
        diagnosis = normalize(parse_diagnosis_json(reply))
        diagnosis["_model_info"] = base_model_info
        json.dump(diagnosis, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        envelope = {
            "_model_info": base_model_info,
            "_provider_error": f"post_cli_error: {_safe_error(exc)}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
