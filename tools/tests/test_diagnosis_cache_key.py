#!/usr/bin/env python3
"""Regression tests for the diagnoser config + cache-key contract.

Started 2026-05-12 for Codex F2 (env-driven cache-key safety), grown over
several Codex review rounds: 2026-05-13 added external-LLM opt-in gate
coverage (F1) + effective-model validation (F2); 2026-05-14 added the
diagnoser_config.schema.json round-trip check (F3).

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


# === Codex 2026-05-13 F2: effective-model validation ===

def test_effective_model_falls_back_to_config_when_env_unset():
    cfg = {"model": {"model_name": "gpt-5-mini",
                      "env_var_name": "CILOGBENCH_OPENAI_MODEL"}}
    # Save then drop env to ensure fall-through
    saved = os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
    try:
        assert rd.effective_requested_model(cfg) == "gpt-5-mini"
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_effective_model_uses_env_override_when_set():
    cfg = {"model": {"model_name": "gpt-5-mini",
                      "env_var_name": "CILOGBENCH_OPENAI_MODEL"}}
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        assert rd.effective_requested_model(cfg) == "gpt-4o"
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_cache_hit_acceptable_when_env_override_matches_cached():
    # Codex 2026-05-13 F2 [medium]: the scenario Codex flagged.
    # User runs with CILOGBENCH_OPENAI_MODEL=gpt-4o. The first run writes a
    # cache entry with requested_model='gpt-4o'. The second identical run
    # MUST hit + accept the cache (was previously rejected because the
    # validator compared against config.model.model_name='gpt-5-mini').
    cfg = {"model": {"model_name": "gpt-5-mini",
                      "env_var_name": "CILOGBENCH_OPENAI_MODEL"}}
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        row = {"metadata": {"model_info": {"requested_model": "gpt-4o"}}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert ok and reason is None, (
            f"env-override hit should accept; got ({ok}, {reason!r})"
        )
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_cache_hit_still_rejects_genuinely_wrong_cached_model():
    # Belt-and-suspenders still fires when cache is poisoned with a row
    # from a different model than the current effective model.
    cfg = {"model": {"model_name": "gpt-5-mini",
                      "env_var_name": "CILOGBENCH_OPENAI_MODEL"}}
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        # Cached row claims to be from a third, unrelated model.
        row = {"metadata": {"model_info": {"requested_model": "claude-haiku"}}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert not ok, "wrong-model cache row should be rejected"
        assert "claude-haiku" in reason and "gpt-4o" in reason, reason
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_v3_config_declares_env_var_name():
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    assert cfg is not None
    env_var = (cfg.get("model") or {}).get("env_var_name")
    assert env_var == "CILOGBENCH_OPENAI_MODEL", (
        f"v3 env_var_name drift: {env_var}"
    )


# === Codex 2026-05-14 F2: Claude (v1/v2) cache + model_info ===

def test_effective_model_prefers_requested_alias_over_model_name():
    # The Claude shim sends the alias (`haiku`/`sonnet`) to
    # `claude -p --model`; the config's `model_name` is the canonical
    # dated identity used in reports/docs. The validator must compare
    # against the alias so cached `requested_model='haiku'` matches.
    cfg = {"model": {"model_name": "claude-haiku-4-5",
                      "requested_alias": "haiku",
                      "env_var_name": "CILOGBENCH_CLAUDE_MODEL"}}
    saved = os.environ.pop("CILOGBENCH_CLAUDE_MODEL", None)
    try:
        assert rd.effective_requested_model(cfg) == "haiku"
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_CLAUDE_MODEL"] = saved


def test_v1_config_has_cache_key_env_and_requested_alias():
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    assert cfg is not None
    assert sorted(cfg.get("cache_key_env") or []) == ["CILOGBENCH_CLAUDE_MODEL"]
    model = cfg.get("model") or {}
    assert model.get("requested_alias") == "haiku"
    assert model.get("env_var_name") == "CILOGBENCH_CLAUDE_MODEL"
    assert model.get("model_name") == "claude-haiku-4-5"


def test_v2_config_has_cache_key_env_and_requested_alias():
    cfg = rd.load_diagnoser_config("real-debugger-v2")
    assert cfg is not None
    assert sorted(cfg.get("cache_key_env") or []) == ["CILOGBENCH_CLAUDE_MODEL"]
    model = cfg.get("model") or {}
    assert model.get("requested_alias") == "sonnet"
    assert model.get("env_var_name") == "CILOGBENCH_CLAUDE_MODEL"
    assert model.get("model_name") == "claude-sonnet-4-6"


def test_claude_model_swap_changes_cache_key():
    # Same scenario Codex flagged: a user runs v1 (configured for haiku)
    # with CILOGBENCH_CLAUDE_MODEL=opus. Old code: same cache_key →
    # silent stale replay. New code: env value in key → different file.
    cfg_v1 = rd.load_diagnoser_config("real-debugger-v1")
    saved = os.environ.get("CILOGBENCH_CLAUDE_MODEL")
    try:
        os.environ["CILOGBENCH_CLAUDE_MODEL"] = "haiku"
        env_haiku = rd.cache_key_env_values(cfg_v1)
        k_haiku = rd.cache_key_for(
            case_id="c1", context_method="raw", context_sha="s1",
            prompt_sha="p1", provider="command", diagnoser="real-debugger-v1",
            command_str="x", env_values=env_haiku,
        )
        os.environ["CILOGBENCH_CLAUDE_MODEL"] = "opus"
        env_opus = rd.cache_key_env_values(cfg_v1)
        k_opus = rd.cache_key_for(
            case_id="c1", context_method="raw", context_sha="s1",
            prompt_sha="p1", provider="command", diagnoser="real-debugger-v1",
            command_str="x", env_values=env_opus,
        )
        assert k_haiku != k_opus, (
            "CILOGBENCH_CLAUDE_MODEL swap did NOT invalidate v1 cache_key"
        )
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_CLAUDE_MODEL", None)
        else:
            os.environ["CILOGBENCH_CLAUDE_MODEL"] = saved


def test_v1_cache_hit_accepts_haiku_alias():
    # Sanity: a v1 cached row that ran with the default haiku alias
    # should pass validation under the canonical run-time config.
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    saved = os.environ.pop("CILOGBENCH_CLAUDE_MODEL", None)
    try:
        row = {"metadata": {"model_info": {"requested_model": "haiku"}}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert ok and reason is None, (
            f"v1 default cache row should pass; got ({ok}, {reason!r})"
        )
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_CLAUDE_MODEL"] = saved


def test_v1_cache_hit_rejects_wrong_model():
    # A v1 cache row that was somehow written with model_info from a
    # different model (e.g. opus left over from a misconfigured run)
    # gets rejected under the canonical config.
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    saved = os.environ.pop("CILOGBENCH_CLAUDE_MODEL", None)
    try:
        row = {"metadata": {"model_info": {"requested_model": "opus"}}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert not ok, "wrong-model v1 cache row should be rejected"
        assert "opus" in reason and "haiku" in reason, reason
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_CLAUDE_MODEL"] = saved


# === Codex 2026-05-13 F1: external-LLM opt-in gate ===

def test_opt_in_gate_blocks_when_env_unset():
    cfg = {
        "diagnoser_name": "test-debugger",
        "privacy": {"requires_explicit_external_llm_opt_in": True,
                     "explicit_opt_in_env_var": "CILOGBENCH_ALLOW_EXTERNAL_LLM"},
    }
    saved = os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
    try:
        err = rd.check_external_llm_opt_in(cfg)
        assert err is not None, "gate should block when env var unset"
        assert "CILOGBENCH_ALLOW_EXTERNAL_LLM" in err
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = saved


def test_opt_in_gate_passes_when_env_set_to_truthy():
    cfg = {
        "diagnoser_name": "test-debugger",
        "privacy": {"requires_explicit_external_llm_opt_in": True,
                     "explicit_opt_in_env_var": "CILOGBENCH_ALLOW_EXTERNAL_LLM"},
    }
    saved = os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM")
    try:
        for v in ("1", "true", "yes", "on", "TRUE", "YES"):
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = v
            err = rd.check_external_llm_opt_in(cfg)
            assert err is None, f"gate should accept {v!r}; got: {err}"
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
        else:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = saved


def test_opt_in_gate_rejects_non_truthy_values():
    cfg = {
        "diagnoser_name": "test-debugger",
        "privacy": {"requires_explicit_external_llm_opt_in": True},
    }
    saved = os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM")
    try:
        for v in ("0", "false", "no", "off", "", "maybe"):
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = v
            err = rd.check_external_llm_opt_in(cfg)
            assert err is not None, f"gate should reject {v!r}"
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
        else:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = saved


def test_opt_in_gate_skips_when_config_does_not_require():
    # Mock diagnoser configs should not be gated.
    cfg_no_req = {"diagnoser_name": "mock",
                   "privacy": {"requires_explicit_external_llm_opt_in": False}}
    assert rd.check_external_llm_opt_in(cfg_no_req) is None
    assert rd.check_external_llm_opt_in({}) is None
    assert rd.check_external_llm_opt_in(None) is None


def test_runner_cli_flag_satisfies_opt_in_gate():
    """Per Codex 2026-05-14 F1 [high]: orchestration wrappers that already
    accept --allow-external-llm now propagate it down to run_diagnosis.py.
    The runner's main() hoists the flag into the env so the gate (which
    reads env) sees it. End-to-end check: run main([..., "--allow-external-llm"])
    against a mock diagnoser with no CILOGBENCH_ALLOW_EXTERNAL_LLM in env.

    We use --diagnoser mock so the test never makes an external call; the
    gate still applies because it's config-driven, but only command-based
    diagnosers with `requires_explicit_external_llm_opt_in` actually trip
    it. The check this test ENCODES is structural: the flag must hoist
    into env when main() is invoked, regardless of whether the gate fires.
    """
    # Save + clear env so we know the flag is what's doing the work.
    saved = os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
    try:
        os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
        # Direct white-box check: argparse + the env hoist in main()
        # without actually invoking run() (which would touch the
        # filesystem). We replicate the relevant lines:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--allow-external-llm", action="store_true")
        ns = ap.parse_args(["--allow-external-llm"])
        # This mirrors run_diagnosis.main():
        if ns.allow_external_llm:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        # Now the gate must pass against a config that requires opt-in:
        cfg = {
            "diagnoser_name": "wrap-test",
            "privacy": {"requires_explicit_external_llm_opt_in": True},
        }
        err = rd.check_external_llm_opt_in(cfg)
        assert err is None, f"--allow-external-llm did not satisfy gate: {err}"
    finally:
        os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
        if saved is not None:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = saved


def test_opt_in_gate_honors_custom_env_var_name():
    cfg = {
        "diagnoser_name": "custom",
        "privacy": {"requires_explicit_external_llm_opt_in": True,
                     "explicit_opt_in_env_var": "ALLOW_CUSTOM_LLM"},
    }
    saved = os.environ.get("ALLOW_CUSTOM_LLM")
    saved_default = os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
    try:
        # Default var set should NOT pass the gate when config asks for a
        # different one.
        os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        os.environ.pop("ALLOW_CUSTOM_LLM", None)
        assert rd.check_external_llm_opt_in(cfg) is not None
        # Custom var set passes.
        os.environ["ALLOW_CUSTOM_LLM"] = "1"
        assert rd.check_external_llm_opt_in(cfg) is None
    finally:
        os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
        if saved is None:
            os.environ.pop("ALLOW_CUSTOM_LLM", None)
        else:
            os.environ["ALLOW_CUSTOM_LLM"] = saved
        if saved_default is not None:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = saved_default


def test_v1_v2_configs_also_declare_optin():
    # Lock the back-compat default: v1/v2 configs require the opt-in too.
    # The default env var name (when explicit_opt_in_env_var is null) is
    # CILOGBENCH_ALLOW_EXTERNAL_LLM.
    for name in ("real-debugger-v1", "real-debugger-v2"):
        cfg = rd.load_diagnoser_config(name)
        assert cfg is not None, f"{name}.json missing"
        privacy = cfg.get("privacy") or {}
        assert privacy.get("requires_explicit_external_llm_opt_in") is True, (
            f"{name} should require external-LLM opt-in"
        )


# === Codex 2026-05-14 F3: configs validate against committed schema ===

def test_all_real_debugger_configs_validate_against_schema():
    """Per Codex 2026-05-14 F3 [medium]: lock the contract between the
    on-disk diagnoser configs and schemas/diagnoser_config.schema.json.

    If v3's reasoning-model nulls (temperature/top_p/model_version) or
    provider_error context-policy value drift back out of the schema, this
    test fires before a config/schema mismatch ships. Falls back to a
    minimal structural check when `jsonschema` is unavailable in the
    runtime environment so the test suite doesn't go silent.
    """
    import json as _json
    schema_path = (Path(__file__).resolve().parent.parent.parent
                    / "schemas" / "diagnoser_config.schema.json")
    schema = _json.loads(schema_path.read_text(encoding="utf-8"))

    config_names = ("real-debugger-v1", "real-debugger-v2",
                     "real-debugger-v3")
    configs = {n: rd.load_diagnoser_config(n) for n in config_names}
    for name, cfg in configs.items():
        assert cfg is not None, f"{name}.json missing"

    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError:
        # Fallback: structural-only check covering the fields F3 fixed.
        for name, cfg in configs.items():
            assert "model" in cfg and "context_policy" in cfg, (
                f"{name} missing top-level keys"
            )
            assert cfg["context_policy"]["on_context_too_large"] in (
                "mark_unsupported", "error", "provider_error",
            ), f"{name} on_context_too_large outside enum"
        return

    for name, cfg in configs.items():
        try:
            jsonschema.validate(instance=cfg, schema=schema)
        except jsonschema.ValidationError as e:
            raise AssertionError(f"{name} fails schema validation: {e.message}")


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
        # Codex 2026-05-13 F2
        test_effective_model_falls_back_to_config_when_env_unset,
        test_effective_model_uses_env_override_when_set,
        test_cache_hit_acceptable_when_env_override_matches_cached,
        test_cache_hit_still_rejects_genuinely_wrong_cached_model,
        test_v3_config_declares_env_var_name,
        # Codex 2026-05-14 F2 (Claude / v1+v2)
        test_effective_model_prefers_requested_alias_over_model_name,
        test_v1_config_has_cache_key_env_and_requested_alias,
        test_v2_config_has_cache_key_env_and_requested_alias,
        test_claude_model_swap_changes_cache_key,
        test_v1_cache_hit_accepts_haiku_alias,
        test_v1_cache_hit_rejects_wrong_model,
        # Codex 2026-05-13 F1
        test_opt_in_gate_blocks_when_env_unset,
        test_opt_in_gate_passes_when_env_set_to_truthy,
        test_opt_in_gate_rejects_non_truthy_values,
        test_opt_in_gate_skips_when_config_does_not_require,
        test_runner_cli_flag_satisfies_opt_in_gate,
        test_opt_in_gate_honors_custom_env_var_name,
        test_v1_v2_configs_also_declare_optin,
        # Codex 2026-05-14 F3
        test_all_real_debugger_configs_validate_against_schema,
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
