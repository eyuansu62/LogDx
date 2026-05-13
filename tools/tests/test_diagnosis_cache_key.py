#!/usr/bin/env python3
"""Regression tests for Codex 2026-05-12 F2: command-provider cache keys
must include model identity (so an env-var-driven model/backend switch
does not silently replay a stale row from a different backend), and
cache hits must be revalidated against the diagnoser config.

Run:
    python3 tools/tests/test_diagnosis_cache_key.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent)
)
import run_diagnosis as rd  # noqa: E402


def _cfg(**overrides):
    base = {
        "diagnoser_name": "test-debugger",
        "model": {"model_name": "gpt-5-mini"},
        "cache_key_env": ["CILOGBENCH_OPENAI_MODEL", "CILOGBENCH_OPENAI_BASE_URL"],
    }
    base.update(overrides)
    return base


def _key(env_values):
    return rd.cache_key_for(
        case_id="c1", context_method="raw", context_sha="s1",
        prompt_sha="p1", provider="command", diagnoser="test-debugger",
        command_str="python3 shim.py", env_values=env_values,
    )


def test_legacy_key_back_compat_when_no_env_optin():
    # Diagnoser with NO cache_key_env opt-in (None) yields the same key it
    # always did — pre-existing v1/v2 caches keep matching.
    k_legacy = _key(env_values=None)
    # Stable across runs: recomputing produces the same key.
    assert k_legacy == _key(env_values=None), "legacy key not stable"


def test_optin_changes_key():
    # The moment a diagnoser opts in (env_values is a non-empty dict), the
    # cache key MUST diverge from the legacy key.
    k_legacy = _key(env_values=None)
    k_new = _key(env_values={"CILOGBENCH_OPENAI_MODEL": "gpt-5-mini"})
    assert k_legacy != k_new, "opt-in did not invalidate legacy key"


def test_env_value_swap_changes_key():
    # The Codex F2 attack: same diagnoser + same command_str, but the user
    # flips CILOGBENCH_OPENAI_MODEL=gpt-4o. The key must move so the cache
    # lookup misses.
    k_5mini = _key(env_values={
        "CILOGBENCH_OPENAI_MODEL": "gpt-5-mini",
        "CILOGBENCH_OPENAI_BASE_URL": "https://api.openai.com/v1",
    })
    k_4o = _key(env_values={
        "CILOGBENCH_OPENAI_MODEL": "gpt-4o",
        "CILOGBENCH_OPENAI_BASE_URL": "https://api.openai.com/v1",
    })
    assert k_5mini != k_4o, "model swap did not invalidate cache key"


def test_base_url_swap_changes_key():
    k_official = _key(env_values={
        "CILOGBENCH_OPENAI_MODEL": "gpt-5-mini",
        "CILOGBENCH_OPENAI_BASE_URL": "https://api.openai.com/v1",
    })
    k_proxy = _key(env_values={
        "CILOGBENCH_OPENAI_MODEL": "gpt-5-mini",
        "CILOGBENCH_OPENAI_BASE_URL": "https://my-proxy.example.com/v1",
    })
    assert k_official != k_proxy, "base_url swap did not invalidate cache key"


def test_cache_key_env_values_reads_environ():
    # End-to-end: cache_key_env_values reads from os.environ for declared keys.
    os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
    os.environ["CILOGBENCH_OPENAI_BASE_URL"] = "https://api.openai.com/v1"
    try:
        env = rd.cache_key_env_values(_cfg())
        assert env == {
            "CILOGBENCH_OPENAI_BASE_URL": "https://api.openai.com/v1",
            "CILOGBENCH_OPENAI_MODEL": "gpt-5-mini",
        }, f"unexpected env mapping: {env}"
    finally:
        os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)


def test_cache_key_env_values_returns_none_without_optin():
    # Diagnoser without cache_key_env returns None (back-compat).
    cfg_no_optin = {"diagnoser_name": "v1-style"}
    assert rd.cache_key_env_values(cfg_no_optin) is None
    assert rd.cache_key_env_values(None) is None


def test_cache_hit_acceptable_on_match():
    cfg = _cfg()
    row = {"metadata": {"model_info": {"requested_model": "gpt-5-mini"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert ok and reason is None, f"expected accept, got ({ok}, {reason!r})"


def test_cache_hit_rejected_on_mismatch():
    cfg = _cfg()
    row = {"metadata": {"model_info": {"requested_model": "gpt-4o"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok, "expected reject"
    assert "gpt-4o" in reason and "gpt-5-mini" in reason, reason


def test_cache_hit_accept_legacy_row_without_model_info():
    # Pre-F2 cached rows have model_info=null or no model_info at all.
    # Accept them so we don't trigger a stampede of re-runs on v1/v2.
    cfg = _cfg()
    for row in (
        {"metadata": {"model_info": None}},
        {"metadata": {}},
        {"metadata": {"model_info": {"requested_model": None}}},
        {},
    ):
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert ok and reason is None, (
            f"legacy row should pass: row={row} got ({ok}, {reason!r})"
        )


def test_cache_hit_accept_when_config_lacks_model_name():
    # If the config has no canonical model_name there is nothing to check.
    cfg = {"model": {}}
    row = {"metadata": {"model_info": {"requested_model": "anything"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert ok and reason is None, f"expected accept, got ({ok}, {reason!r})"


def test_v3_config_declares_expected_env_vars():
    # Lock the on-disk v3 config to the env vars the Codex F2 fix relies on.
    # If someone removes one, this test fires before a cache poisoning bug
    # ships.
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    assert cfg is not None, "real-debugger-v3.json missing"
    keys = sorted(cfg.get("cache_key_env") or [])
    assert keys == [
        "CILOGBENCH_OPENAI_BASE_URL",
        "CILOGBENCH_OPENAI_MODEL",
    ], f"v3 cache_key_env drift: {keys}"


def main() -> int:
    tests = [
        test_legacy_key_back_compat_when_no_env_optin,
        test_optin_changes_key,
        test_env_value_swap_changes_key,
        test_base_url_swap_changes_key,
        test_cache_key_env_values_reads_environ,
        test_cache_key_env_values_returns_none_without_optin,
        test_cache_hit_acceptable_on_match,
        test_cache_hit_rejected_on_mismatch,
        test_cache_hit_accept_legacy_row_without_model_info,
        test_cache_hit_accept_when_config_lacks_model_name,
        test_v3_config_declares_expected_env_vars,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    print()
    print(f"{'All ' + str(len(tests)) + ' tests passed.' if failed == 0 else f'{failed} of {len(tests)} tests FAILED.'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
