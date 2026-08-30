#!/usr/bin/env python3
"""Offline regression tests for the public Copilot diagnosis API."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from logdx_ci import diagnoser as API  # noqa: E402


def result(*, native: bool = False) -> dict:
    info = {
        "requested_model": "gpt-5.6-luna",
        "resolved_model": "gpt-5.6-luna",
    }
    if native:
        info.update(tool_count=0, tools_available=0)
    return {"summary": "Test diagnosis", "_model_info": info}


def completed(body: object) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], 0, json.dumps(body).encode(), b"")


class CopilotApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = mock.patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.root = mock.patch.object(API, "find_repo_root", return_value=ROOT)
        self.root.start()
        self.addCleanup(self.root.stop)

    def diagnose(self, *, cache_dir=None, native=False, diagnoser=None):
        name = diagnoser or (
            "copilot-luna-native-long" if native else "copilot-luna-compat"
        )
        return API.diagnose(
            diagnoser=name,
            case_id="test-case",
            reduced_context="test failed",
            case_metadata={},
            cache_dir=cache_dir,
        )

    def test_valid_fresh_result_is_cached_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            API.subprocess, "run", return_value=completed(result())
        ) as run:
            first = self.diagnose(cache_dir=Path(directory))
            self.assertEqual(first, self.diagnose(cache_dir=Path(directory)))
            self.assertEqual(run.call_count, 1)

    def test_fresh_missing_or_wrong_model_is_rejected_before_cache_write(self) -> None:
        bad_results = [{}, [], {"_model_info": None}]
        for field in ("requested_model", "resolved_model"):
            for value in (None, "gpt-5.6-sol"):
                body = result()
                body["_model_info"][field] = value
                bad_results.append(body)
        for body in bad_results:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                with mock.patch.object(API.subprocess, "run", return_value=completed(body)):
                    with self.assertRaises(RuntimeError):
                        self.diagnose(cache_dir=Path(directory))
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_cached_missing_or_wrong_identity_is_rejected_without_new_call(self) -> None:
        for field in ("requested_model", "resolved_model"):
            for value in (None, "gpt-5.6-sol"):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as directory:
                    with mock.patch.object(API.subprocess, "run", return_value=completed(result())) as run:
                        self.diagnose(cache_dir=Path(directory))
                        cache = next(Path(directory).iterdir())
                        body = json.loads(cache.read_text())
                        body["_model_info"][field] = value
                        cache.write_text(json.dumps(body))
                        with self.assertRaisesRegex(RuntimeError, "model identity"):
                            self.diagnose(cache_dir=Path(directory))
                        self.assertEqual(run.call_count, 1)

    def test_model_override_conflicting_with_config_fails_before_provider_call(self) -> None:
        with mock.patch.dict(os.environ, {"CILOGBENCH_COPILOT_MODEL": "gpt-5.6-sol"}):
            with mock.patch.object(API.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "conflicts"):
                    self.diagnose()
                run.assert_not_called()

    def test_zero_exit_provider_error_is_not_cached(self) -> None:
        body = result()
        body["_provider_error"] = "provider failure"
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            API.subprocess, "run", return_value=completed(body)
        ):
            with self.assertRaises(RuntimeError):
                self.diagnose(cache_dir=Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_native_explicit_zero_tool_counts_are_accepted(self) -> None:
        with mock.patch.object(API.subprocess, "run", return_value=completed(result(native=True))):
            self.assertEqual(self.diagnose(native=True)["_model_info"]["tool_count"], 0)

    def test_native_missing_invalid_or_nonzero_tool_counts_are_rejected(self) -> None:
        for field in ("tool_count", "tools_available"):
            for value in (None, 1, -1, "0", False):
                with self.subTest(field=field, value=value):
                    body = result(native=True)
                    body["_model_info"][field] = value
                    with mock.patch.object(API.subprocess, "run", return_value=completed(body)):
                        with self.assertRaisesRegex(RuntimeError, "explicit zero"):
                            self.diagnose(native=True)

    def test_native_cached_missing_tool_count_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            API.subprocess, "run", return_value=completed(result(native=True))
        ) as run:
            self.diagnose(cache_dir=Path(directory), native=True)
            cache = next(Path(directory).iterdir())
            body = json.loads(cache.read_text())
            del body["_model_info"]["tools_available"]
            cache.write_text(json.dumps(body))
            with self.assertRaisesRegex(RuntimeError, "explicit zero"):
                self.diagnose(cache_dir=Path(directory), native=True)
            self.assertEqual(run.call_count, 1)

    def test_legacy_stub_does_not_require_copilot_metadata(self) -> None:
        with mock.patch.object(API.subprocess, "run", return_value=completed({"summary": "stub"})):
            self.assertEqual(self.diagnose(diagnoser="stub-debugger-v1")["summary"], "stub")


class CopilotPreflightTests(unittest.TestCase):
    def test_native_sdk_does_not_require_standalone_cli(self) -> None:
        versions = {"github-copilot-sdk": "1.0.11", "tiktoken": "0.14.0"}
        with mock.patch.object(API.sys, "version_info", (3, 11)), mock.patch.object(
            API.importlib.metadata, "version", side_effect=versions.__getitem__
        ), mock.patch.object(API.shutil, "which", return_value=None) as which:
            API.preflight("copilot-luna-native-long")
            which.assert_not_called()

    def test_native_sdk_reports_missing_packages(self) -> None:
        for missing in ("github-copilot-sdk", "tiktoken"):
            def version(name):
                if name == missing:
                    raise importlib.metadata.PackageNotFoundError(name)
                return "1.0.11"
            with self.subTest(missing=missing), mock.patch.object(API.sys, "version_info", (3, 11)):
                with mock.patch.object(API.importlib.metadata, "version", side_effect=version):
                    with self.assertRaisesRegex(RuntimeError, "install logdx-ci"):
                        API.preflight("copilot-luna-native-long")

    def test_native_sdk_requires_pinned_version(self) -> None:
        with mock.patch.object(API.sys, "version_info", (3, 11)), mock.patch.object(
            API.importlib.metadata, "version", return_value="1.0.12"
        ):
            with self.assertRaisesRegex(RuntimeError, "==1.0.11"):
                API.preflight("copilot-luna-native-long")

    def test_native_sdk_requires_python_311(self) -> None:
        with mock.patch.object(API.sys, "version_info", (3, 10)):
            with self.assertRaisesRegex(RuntimeError, "Python 3.11"):
                API.preflight("copilot-luna-native-long")

    def test_compatibility_mode_still_requires_global_cli(self) -> None:
        with mock.patch.object(API.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "CLI on PATH"):
                API.preflight("copilot-luna-compat")


if __name__ == "__main__":
    unittest.main(verbosity=2)
