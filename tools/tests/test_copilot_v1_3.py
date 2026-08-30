#!/usr/bin/env python3
"""Regression tests for the LogDx v1.3 Copilot adapter and cache identity."""

from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHIM = load_module("diagnosis_shim_copilot_cli", ROOT / "examples" / "diagnosis_shim_copilot_cli.py")
SDK_SHIM = load_module(
    "diagnosis_shim_copilot_sdk",
    ROOT / "examples" / "diagnosis_shim_copilot_sdk.py",
)
STATS = load_module("analyze_v1_3_transfer", ROOT / "tools" / "analyze_v1_3_transfer.py")
NATIVE_STATS = load_module(
    "analyze_v1_3_native", ROOT / "tools" / "analyze_v1_3_native.py"
)
RUNNER = load_module("run_diagnosis_v1_3", ROOT / "tools" / "run_diagnosis.py")
from logdx_ci import diagnoser as SDK  # noqa: E402


def payload(context: str = "fatal: test failed") -> dict:
    return {
        "case_id": "case-1",
        "context_method": "tail",
        "prompt": "Return diagnosis JSON.",
        "context": context,
        "safe_case_metadata": {"case_id": "case-1"},
    }


class CopilotShimTests(unittest.TestCase):
    def test_success_event_stream_is_parsed(self) -> None:
        events = [
            {
                "type": "model.model_call_started",
                "data": {
                    "model": "gpt-5.6-terra",
                    "modelInfo": {
                        "id": "gpt-5.6-terra",
                        "version": "gpt-5.6-terra",
                        "capabilities": {
                            "tokenizer": "o200k_base",
                            "limits": {
                                "max_context_window_tokens": 400000,
                                "max_prompt_tokens": 272000,
                            },
                        },
                    },
                },
            },
            {
                "type": "assistant.message_delta",
                "data": {"phase": "final_answer", "deltaContent": '{"summary":"ok"}'},
            },
            {
                "type": "model.model_call_success",
                "data": {
                    "reasoningEffort": "low",
                    "maxPromptTokens": 272000,
                    "toolCount": 0,
                    "responseUsage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            },
            {"type": "result", "usage": {"premiumRequests": 1}},
        ]
        reply, info = SHIM._parse_events("\n".join(json.dumps(e) for e in events))
        self.assertEqual(reply, '{"summary":"ok"}')
        self.assertEqual(info["resolved_model"], "gpt-5.6-terra")
        self.assertEqual(info["tool_count"], 0)
        self.assertEqual(info["usage"]["prompt_tokens"], 10)

    def test_non_streaming_final_message_is_parsed(self) -> None:
        event = {
            "type": "assistant.message",
            "data": {"phase": "final_answer", "content": '{"summary":"ok"}'},
        }
        reply, _ = SHIM._parse_events(json.dumps(event))
        self.assertEqual(reply, '{"summary":"ok"}')

    def test_acp_model_update_is_observed(self) -> None:
        update = {
            "sessionUpdate": "config_option_update",
            "configOptions": [
                {"id": "mode", "currentValue": "agent"},
                {"id": "model", "currentValue": "gpt-5.6-sol"},
            ],
        }
        self.assertEqual(SHIM._model_from_config_update(update), "gpt-5.6-sol")

    def test_malformed_model_output_is_rejected_without_echo(self) -> None:
        secret = "tenant-short-secret"
        with self.assertRaisesRegex(ValueError, "reply_sha256") as caught:
            SHIM.parse_diagnosis_json(f"not json {secret}")
        self.assertNotIn(secret, str(caught.exception))

    def test_context_limit_is_fail_closed(self) -> None:
        with self.assertRaises(SHIM.ContextTooLargeError):
            SHIM.build_prompt(payload("12345"), max_context_chars=4)

    def test_safe_error_does_not_persist_provider_text(self) -> None:
        secret = "Bearer abcdefghijklmnopqrstuvwxyz"
        safe = SHIM._safe_error(RuntimeError(secret))
        self.assertIn("message_sha256", safe)
        self.assertNotIn("Bearer", safe)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", safe)

    def test_timeout_is_a_provider_failure(self) -> None:
        with mock.patch.object(
            SHIM.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["copilot"], 1),
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                SHIM.invoke_copilot(
                    prompt="x",
                    model="gpt-5.6-terra",
                    effort="low",
                    context_mode="default",
                    timeout_s=1,
                )

    def test_nonzero_provider_exit_is_hashed(self) -> None:
        completed = subprocess.CompletedProcess(
            ["copilot"], 1, stdout="private output", stderr="private error"
        )
        with mock.patch.object(SHIM.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "stdout_sha256") as caught:
                SHIM.invoke_copilot(
                    prompt="x",
                    model="gpt-5.6-terra",
                    effort="low",
                    context_mode="default",
                    timeout_s=1,
                )
        self.assertNotIn("private output", str(caught.exception))
        self.assertNotIn("private error", str(caught.exception))

    def test_unsupported_model_is_rejected_before_cli_call(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        env = {
            "CILOGBENCH_ALLOW_EXTERNAL_LLM": "1",
            "CILOGBENCH_COPILOT_MODEL": "not a valid/model",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            SHIM.sys, "stdin", io.StringIO(json.dumps(payload()))
        ), redirect_stdout(stdout), redirect_stderr(stderr), mock.patch.object(
            SHIM, "invoke_copilot"
        ) as invoke:
            self.assertEqual(SHIM.main(), 1)
        invoke.assert_not_called()
        self.assertIn("valid CILOGBENCH_COPILOT_MODEL required", stderr.getvalue())


class SdkCacheIdentityTests(unittest.TestCase):
    def identity(self, *, diagnoser: str = "copilot-terra-compat") -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "prompt.md"
            shim = root / "shim.py"
            config = root / "config.json"
            prompt.write_text("prompt", encoding="utf-8")
            shim.write_text("shim", encoding="utf-8")
            config.write_text("{}", encoding="utf-8")
            return SDK._cache_identity(
                diagnoser=diagnoser,
                case_id="case-1",
                reduced_context="context",
                prompt_path=prompt,
                shim_path=shim,
                config_path=config,
            )

    def test_diagnoser_id_changes_identity(self) -> None:
        self.assertNotEqual(
            self.identity(), self.identity(diagnoser="copilot-luna-compat")
        )

    def test_model_change_changes_identity(self) -> None:
        base = self.identity()
        with mock.patch.dict(
            os.environ, {"CILOGBENCH_COPILOT_MODEL": "gpt-5.6-sol"}
        ):
            changed = self.identity()
        self.assertNotEqual(base, changed)

    def test_reasoning_change_changes_identity(self) -> None:
        base = self.identity()
        with mock.patch.dict(
            os.environ, {"CILOGBENCH_COPILOT_REASONING_EFFORT": "high"}
        ):
            changed = self.identity()
        self.assertNotEqual(base, changed)

    def test_context_mode_and_cap_change_identity(self) -> None:
        base = self.identity()
        with mock.patch.dict(
            os.environ,
            {
                "CILOGBENCH_COPILOT_CONTEXT_MODE": "long_context",
                "CILOGBENCH_COPILOT_MAX_CONTEXT_CHARS": "900000",
            },
        ):
            changed = self.identity()
        self.assertNotEqual(base, changed)

    def test_prompt_shim_config_and_context_hashes_are_bound(self) -> None:
        identity = self.identity()
        self.assertEqual(len(identity["prompt_sha256"]), 64)
        self.assertEqual(len(identity["shim_sha256"]), 64)
        self.assertEqual(len(identity["diagnoser_config_sha256"]), 64)
        self.assertEqual(len(identity["reduced_context_sha256"]), 64)


class SdkNativeProvenanceTests(unittest.TestCase):
    @staticmethod
    def event(event_type: str, **data):
        return SimpleNamespace(
            type=SimpleNamespace(value=event_type),
            data=SimpleNamespace(**data),
        )

    def valid_events(self) -> list:
        return [
            self.event(
                "session.start",
                selected_model="gpt-5.6-luna",
                context_tier="long_context",
                copilot_version="1.0.79",
            ),
            self.event("session.usage_info", token_limit=922000),
            self.event("model.call_start", model="gpt-5.6-luna"),
            self.event(
                "assistant.usage",
                model="gpt-5.6-luna",
                _num_tool_calls=0,
                _available_tool_count=0,
            ),
        ]

    def test_long_context_dispatch_proves_requested_model(self) -> None:
        start, usage = SDK_SHIM.validate_event_provenance(
            self.valid_events(), "gpt-5.6-luna"
        )
        self.assertEqual(start["context_tier"], "long_context")
        self.assertEqual(usage["model"], "gpt-5.6-luna")

    def test_prompt_time_model_drift_fails_closed(self) -> None:
        events = self.valid_events()
        events[2] = self.event("model.call_start", model="gpt-5.6-sol")
        with self.assertRaises(SDK_SHIM.ProvenanceError):
            SDK_SHIM.validate_event_provenance(events, "gpt-5.6-luna")

    def test_tool_surface_fails_closed(self) -> None:
        events = self.valid_events()
        events[3] = self.event(
            "assistant.usage",
            model="gpt-5.6-luna",
            _num_tool_calls=0,
            _available_tool_count=1,
        )
        with self.assertRaises(SDK_SHIM.ProvenanceError):
            SDK_SHIM.validate_event_provenance(events, "gpt-5.6-luna")

    def test_unproven_long_context_tier_fails_closed(self) -> None:
        events = self.valid_events()
        events[1] = self.event("session.usage_info", token_limit=272000)
        with self.assertRaises(SDK_SHIM.ProvenanceError):
            SDK_SHIM.validate_event_provenance(events, "gpt-5.6-luna")

    def test_missing_or_invalid_tool_counts_fail_closed(self) -> None:
        for field in ("_num_tool_calls", "_available_tool_count"):
            for value in (None, "0", False, -1, 0.0):
                with self.subTest(field=field, value=value):
                    events = self.valid_events()
                    setattr(events[3].data, field, value)
                    with self.assertRaises(SDK_SHIM.ProvenanceError):
                        SDK_SHIM.validate_event_provenance(events, "gpt-5.6-luna")
            events = self.valid_events()
            delattr(events[3].data, field)
            with self.assertRaises(SDK_SHIM.ProvenanceError):
                SDK_SHIM.validate_event_provenance(events, "gpt-5.6-luna")

    def test_evaluated_sdk_snapshot_keeps_original_hash(self) -> None:
        source = ROOT / "examples/frozen/diagnosis_shim_copilot_sdk_2026_08_30.py"
        self.assertEqual(
            hashlib.sha256(source.read_bytes()).hexdigest(),
            "20143deadb8e3e22cda32c4e86ca19be802af9e8c5b09620953aa597cc834ccc",
        )

    def test_malformed_reply_retains_verified_usage_without_reply(self) -> None:
        info = {"requested_model": "gpt-5.6-luna", "resolved_model": "gpt-5.6-luna",
                "usage": {"prompt_tokens": 123, "completion_tokens": 4}}
        output = io.StringIO()
        with mock.patch.dict(os.environ, {
            "CILOGBENCH_ALLOW_EXTERNAL_LLM": "1",
            "CILOGBENCH_COPILOT_MODEL": "gpt-5.6-luna",
        }), mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload()))), \
                mock.patch.object(SDK_SHIM, "invoke_sdk", new=mock.AsyncMock(
                    return_value=("private malformed response", info))), redirect_stdout(output):
            result = SDK_SHIM.main()
        self.assertEqual(result, 1)
        envelope = json.loads(output.getvalue())
        self.assertEqual(envelope["_model_info"], info)
        self.assertIn("copilot_sdk_error", envelope["_provider_error"])
        self.assertNotIn("private malformed response", output.getvalue())


class StatisticsTests(unittest.TestCase):
    def test_latency_populations_do_not_mix_model_and_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "dev" / "diagnoses" / "test"
            folder.mkdir(parents=True)
            rows = [
                {"metadata": {"runtime_ms": 100, "model_info": {"model_call_duration_ms": 0}}},
                {"metadata": {"runtime_ms": 200, "model_info": {"model_call_duration_ms": 20}}},
                {"metadata": {"runtime_ms": 300, "model_info": {}}},
                {"metadata": {"runtime_ms": 900, "provider_error": "too_large",
                              "model_info": {"model_call_duration_ms": 800}}},
            ]
            (folder / "raw.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
            runtime = STATS.load_runtime("test", root)["raw"]
            self.assertEqual(runtime["successful_model_call_latency_ms"],
                             {"observations": 2, "p50": 10.0, "p95": 19.0})
            self.assertEqual(runtime["successful_end_to_end_latency_ms"]["p50"], 200)
            self.assertEqual(runtime["rejected_end_to_end_latency_ms"]["p50"], 900)
            self.assertEqual(runtime["all_rows_end_to_end_latency_ms"]["observations"], 4)
            self.assertIsNone(runtime["premium_requests"])

    def test_empty_latency_is_unknown_not_zero(self) -> None:
        self.assertEqual(STATS.latency_summary([]), {"observations": 0, "p50": None, "p95": None})

    def test_coverage_groups_preserve_case_denominators(self) -> None:
        native = {}; compat = {}
        for case, score in (("both", 0.6), ("new", 0.8), ("neither", 0.0)):
            native[("dev", "raw", case)] = {"diagnosis_score_v1_1": score}
            for method in ("raw", "hybrid-grep-120k-rtk-tail-v3", "tail"):
                compat[("dev", method, case)] = {"diagnosis_score_v1_1": 0.7 if case == "both" else 0.0}
        result = NATIVE_STATS.coverage_analysis(
            native, compat, {("dev", "both"), ("dev", "new")}, {("dev", "both")}
        )
        self.assertEqual(result["both_accepted"]["case_count"], 1)
        self.assertEqual(result["native_accepted"]["case_count"], 2)
        self.assertEqual(result["neither_accepted"]["case_count"], 1)
        self.assertEqual(result["compat_only_accepted"]["case_count"], 0)
        self.assertIsNone(result["compat_only_accepted"]["native_raw_mean_score"])
        delta = result["both_accepted"]["comparisons"]["raw"]["paired_delta_native_minus_compat"]
        self.assertAlmostEqual(delta["mean_delta"], -0.1)
        self.assertEqual(result["newly_accepted_native"]["native_raw_mean_score"], 0.8)

    def test_missing_pair_fails_instead_of_silently_shrinking_sample(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing paired"):
            NATIVE_STATS.paired_delta(
                {("dev", "raw", "a"): {"diagnosis_score_v1_1": 0.8}}, "raw", {}, "raw"
            )

    def test_coverage_rejects_different_raw_case_sets(self) -> None:
        row = {"diagnosis_score_v1_1": 0.8}
        with self.assertRaisesRegex(ValueError, "different case sets"):
            NATIVE_STATS.coverage_analysis(
                {("dev", "raw", "a"): row}, {("dev", "raw", "b"): row}, set(), set()
            )

    def test_ranking_sensitivity_uses_only_selected_cases_and_shared_methods(self) -> None:
        left = {}; right = {}
        for method, score in (("raw", 0.1), ("tail", 0.9)):
            left[("dev", method, "selected")] = {"diagnosis_score_v1_1": score}
            right[("dev", method, "selected")] = {"diagnosis_score_v1_1": 1 - score}
            left[("dev", method, "other")] = {"diagnosis_score_v1_1": 1 - score}
            right[("dev", method, "other")] = {"diagnosis_score_v1_1": score}
        left[("dev", "new-method", "selected")] = {"diagnosis_score_v1_1": 0.5}
        result = NATIVE_STATS.ranking_sensitivity(left, right, {("dev", "selected")})
        self.assertEqual(result["case_count"], 1)
        self.assertEqual(result["common_methods"], 2)
        self.assertEqual(result["rho"], -1.0)

    def test_accepted_cases_includes_model_abstentions_but_not_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dev").mkdir()
            data = {"methods": [{"context_method": "raw", "cases": [
                {"case_id": "abstain", "provider_error": None, "abstained": True},
                {"case_id": "error", "provider_error": "too_large", "abstained": True},
            ]}]}
            (root / "dev" / "eval_diagnosis_test.json").write_text(json.dumps(data))
            self.assertEqual(STATS.accepted_cases("test", "raw", root), {("dev", "abstain")})

    def test_spearman_detects_reversed_ranking(self) -> None:
        rho, count = STATS.spearman(
            {"a": 3.0, "b": 2.0, "c": 1.0},
            {"a": 1.0, "b": 2.0, "c": 3.0},
        )
        self.assertEqual(count, 3)
        self.assertEqual(rho, -1.0)

    def test_paired_bootstrap_is_reproducible(self) -> None:
        first = STATS.paired_bootstrap([0.1, 0.2, -0.1], samples=100, seed=7)
        second = STATS.paired_bootstrap([0.1, 0.2, -0.1], samples=100, seed=7)
        self.assertEqual(first, second)
        self.assertFalse(first["sufficient_for_claim"])

    def test_native_pairing_matches_case_across_methods(self) -> None:
        left = {("dev", "raw", "case-1"): {"diagnosis_score_v1_1": 0.8}}
        right = {
            ("dev", "hybrid", "case-1"): {"diagnosis_score_v1_1": 0.5}
        }
        result = NATIVE_STATS.paired_delta(left, "raw", right, "hybrid")
        self.assertEqual(result["paired_cases"], 1)
        self.assertAlmostEqual(result["mean_delta"], 0.3)


class CaseFilterTests(unittest.TestCase):
    def test_selected_rerun_preserves_unselected_manifest_rows(self) -> None:
        source = [{"case_id": "a"}, {"case_id": "b"}, {"case_id": "c"}]
        existing = [
            {"case_id": "a", "value": "old-a"},
            {"case_id": "b", "value": "old-b"},
            {"case_id": "c", "value": "old-c"},
        ]
        selected = [{"case_id": "b", "value": "new-b"}]
        merged = RUNNER.merge_selected_manifest_rows(source, existing, selected)
        self.assertEqual([row["case_id"] for row in merged], ["a", "b", "c"])
        self.assertEqual([row["value"] for row in merged], ["old-a", "new-b", "old-c"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
