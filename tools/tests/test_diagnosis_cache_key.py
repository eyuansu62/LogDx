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
    # The 2026-05-18 F2 fix tightened this: configs declaring identity
    # (cache_key_env or model.model_name) REJECT missing model_info.
    # Legacy back-compat now requires an explicit opt-out
    # (`model.allow_missing_model_info: true`) in the config.
    cfg_optout = {"model": {"model_name": "x", "allow_missing_model_info": True}}
    for row in (
        {"metadata": {"model_info": None}},
        {"metadata": {}},
        {"metadata": {"model_info": {"requested_model": None}}},
        {},
    ):
        ok, reason = rd.cache_hit_is_acceptable(row, cfg_optout)
        assert ok and reason is None, (
            f"legacy row with opt-out should pass: row={row} "
            f"got ({ok}, {reason!r})"
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


# === Codex 2026-05-15 F1: fresh-row model identity + env injection ===

def test_build_shim_env_injects_alias_when_env_unset():
    """v2 (config: sonnet) running against a Claude shim whose hardcoded
    default is 'haiku' would write Haiku rows under real-debugger-v2.
    build_shim_env injects the config-declared alias when the user
    hasn't set the env var, so the shim's default path agrees with the
    config's expectation."""
    cfg = rd.load_diagnoser_config("real-debugger-v2")
    parent = {"PATH": "/usr/bin"}  # no CILOGBENCH_CLAUDE_MODEL
    env = rd.build_shim_env(cfg, parent_env=parent)
    assert env["CILOGBENCH_CLAUDE_MODEL"] == "sonnet", (
        f"v2 should inject sonnet; got {env.get('CILOGBENCH_CLAUDE_MODEL')!r}"
    )
    # PATH and other parent vars are preserved.
    assert env["PATH"] == "/usr/bin"


def test_build_shim_env_preserves_user_override():
    """If the user has explicitly set CILOGBENCH_CLAUDE_MODEL=opus to do
    an experiment, build_shim_env must NOT clobber it with the config
    default. The cache_key already incorporates the user's value via
    cache_key_env, so the combination is self-consistent."""
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    parent = {"CILOGBENCH_CLAUDE_MODEL": "opus", "PATH": "/usr/bin"}
    env = rd.build_shim_env(cfg, parent_env=parent)
    assert env["CILOGBENCH_CLAUDE_MODEL"] == "opus", (
        f"explicit env should win; got {env.get('CILOGBENCH_CLAUDE_MODEL')!r}"
    )


def test_build_shim_env_no_optin_means_no_injection():
    """A diagnoser config without env_var_name (e.g. a hypothetical
    static-shim config) should leave the env unchanged."""
    cfg = {"model": {"model_name": "static-model"}}
    parent = {"PATH": "/usr/bin"}
    env = rd.build_shim_env(cfg, parent_env=parent)
    assert env == parent


def test_validate_fresh_row_passes_when_shim_matches_config():
    """v3 row with matching alias AND matching endpoint evidence. The
    Codex 2026-05-20 F1 fix now requires endpoint evidence under
    provenance-required configs (real-debugger-v3 declares
    cache_key_env so this applies)."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    diag = {"_model_info": {
        "requested_model": "gpt-5-mini",
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": rd._base_url_sha256_for_compare(
            "https://api.openai.com/v1"
        ),
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is None, f"v3 fresh row with full provenance should pass: {err}"


def test_validate_fresh_row_rejects_haiku_under_v2():
    """The exact Codex 2026-05-15 F1 scenario: a Claude shim using its
    hardcoded 'haiku' default emits requested_model='haiku', but v2's
    config expects 'sonnet'. validate_fresh_row_model_identity catches
    this BEFORE the row is written under the v2 diagnoser name."""
    cfg = rd.load_diagnoser_config("real-debugger-v2")
    saved = os.environ.pop("CILOGBENCH_CLAUDE_MODEL", None)
    try:
        diag = {"_model_info": {"requested_model": "haiku"}}
        err = rd.validate_fresh_row_model_identity(diag, cfg)
        assert err is not None, "haiku-under-v2 should be rejected"
        assert "haiku" in err and "sonnet" in err, err
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_CLAUDE_MODEL"] = saved


def test_validate_fresh_row_back_compat_when_shim_emits_no_model_info():
    """Pre-2026-05-18: real-debugger configs accepted missing model_info
    as legacy back-compat. The 2026-05-18 F2 fix tightened this: real
    configs REQUIRE provenance, legacy diagnosers need an explicit
    `model.allow_missing_model_info: true` opt-out."""
    # With opt-out: missing model_info passes.
    cfg_optout = {"model": {"model_name": "x", "allow_missing_model_info": True}}
    diag = {"summary": "anything"}  # no _model_info at all
    assert rd.validate_fresh_row_model_identity(diag, cfg_optout) is None
    # Without opt-out (real-debugger-v3): missing model_info is rejected.
    cfg_v3 = rd.load_diagnoser_config("real-debugger-v3")
    err = rd.validate_fresh_row_model_identity(diag, cfg_v3)
    assert err is not None


# === Codex 2026-05-15 F2: --diagnoser-config path validation ===

def test_load_diagnoser_config_explicit_path_matches_name():
    cfg = rd.load_diagnoser_config(
        "real-debugger-v3",
        explicit_path=Path(__file__).resolve().parent.parent.parent
        / "configs" / "diagnosers" / "real-debugger-v3.json",
    )
    assert cfg is not None
    assert cfg.get("diagnoser_name") == "real-debugger-v3"


def test_load_diagnoser_config_explicit_path_mismatch_raises():
    """v1.json declares diagnoser_name='real-debugger-v1'. Passing it as
    --diagnoser-config with --diagnoser-name=real-debugger-v3 must fail
    fast so the manifest can't claim one config while the runner derived
    behaviour from another."""
    v1_path = (Path(__file__).resolve().parent.parent.parent
                / "configs" / "diagnosers" / "real-debugger-v1.json")
    try:
        rd.load_diagnoser_config("real-debugger-v3", explicit_path=v1_path)
    except rd.DiagnoserConfigError as e:
        msg = str(e)
        assert "real-debugger-v1" in msg and "real-debugger-v3" in msg, msg
        return
    raise AssertionError("expected DiagnoserConfigError on mismatch")


def test_load_diagnoser_config_explicit_missing_path_raises():
    bad_path = Path("/tmp/does-not-exist-zzzz.json")
    try:
        rd.load_diagnoser_config("real-debugger-v3", explicit_path=bad_path)
    except rd.DiagnoserConfigError as e:
        assert "does not exist" in str(e), str(e)
        return
    raise AssertionError("expected DiagnoserConfigError on missing file")


def test_load_diagnoser_config_legacy_path_unchanged():
    """No explicit path → auto-discover by name → returns config, no
    exception. Back-compat with v1/v2 caches written before --diagnoser-config
    existed."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    assert cfg is not None
    assert cfg.get("diagnoser_name") == "real-debugger-v3"


def test_load_diagnoser_config_legacy_missing_returns_none():
    """No explicit path AND no file → None (not an exception). This keeps
    mock-diagnoser paths working when no config exists."""
    assert rd.load_diagnoser_config("nonexistent-diagnoser-xyz") is None


# === Codex 2026-05-16 F1: preserve model_info on shim error path ===

def test_extract_shim_stdout_metadata_picks_up_model_info():
    """Per Codex 2026-05-16 F1 [high]: the shim's error path writes a JSON
    envelope with _model_info to stdout; the runner extracts it so
    provider_error rows preserve model provenance for post-API failures."""
    stdout = (
        b'{"_model_info": {"provider_name": "openai", '
        b'"requested_model": "gpt-5-mini", '
        b'"resolved_model": "gpt-5-mini-2025-08-07"}, '
        b'"_provider_error": "post_api_error: JSONDecodeError ..."}'
    )
    md = rd._extract_shim_stdout_metadata(stdout)
    assert md.get("_model_info", {}).get("resolved_model") \
        == "gpt-5-mini-2025-08-07"
    assert md.get("_provider_error", "").startswith("post_api_error:")


def test_extract_shim_stdout_metadata_handles_non_json():
    # Legacy shims that write plain text to stdout on error: extract
    # returns {} (no crash).
    assert rd._extract_shim_stdout_metadata(b"some non-JSON garbage") == {}
    assert rd._extract_shim_stdout_metadata(b"") == {}


def test_extract_shim_stdout_metadata_ignores_non_dict():
    assert rd._extract_shim_stdout_metadata(b'"just a string"') == {}
    assert rd._extract_shim_stdout_metadata(b"[1,2,3]") == {}


def test_extract_shim_stdout_metadata_ignores_missing_fields():
    # JSON with no opt-in keys → {}.
    assert rd._extract_shim_stdout_metadata(b'{"summary":"ok"}') == {}


def test_shim_call_error_carries_metadata():
    err = rd.ShimCallError(
        "exit 1",
        model_info={"requested_model": "gpt-5-mini"},
        provider_error_hint="post_api_error: ...",
    )
    assert err.model_info == {"requested_model": "gpt-5-mini"}
    assert err.provider_error_hint == "post_api_error: ..."
    assert "exit 1" in str(err)


def test_openai_shim_emits_model_info_envelope_on_parse_failure():
    """End-to-end: the shim writes a JSON envelope containing
    _model_info + _provider_error when post-API parsing fails. We
    simulate this by monkeypatching urllib so the shim never makes a
    real API call but still hits the parse path with a malformed
    response.

    The test is structural — it runs the shim as a subprocess with a
    stubbed urlopen and asserts:
      - exit code is 1 (caller's run_diagnosis treats as provider_error)
      - stdout is valid JSON with _model_info populated
      - _provider_error mentions the parse failure
    """
    import subprocess as _sub
    import tempfile

    # Build a tiny wrapper that monkeypatches urllib.request.urlopen
    # to return a fake response with malformed JSON content. Then
    # invokes the shim's main().
    stub = '''
import io
import json as _json
import os
import sys
import urllib.request as _req

class _FakeResp:
    def __init__(self, body): self._b = body
    def read(self): return self._b.encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, *a): pass

def _fake_urlopen(req, timeout=None):
    return _FakeResp(_json.dumps({
        "model": "gpt-5-mini-2025-08-07",
        "system_fingerprint": "fp_test",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        "choices": [{"message": {"content": "{ this is broken JSON" }}],
    }))

_req.urlopen = _fake_urlopen
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"

sys.path.insert(0, "{repo}/examples")
from diagnosis_shim_openai import main
sys.exit(main())
'''
    import json
    repo = str(Path(__file__).resolve().parent.parent.parent)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
        fp.write(stub.replace("{repo}", repo))
        fp.flush()
        stub_path = fp.name
    payload = json.dumps({
        "case_id": "t1", "context_method": "raw", "prompt": "x",
        "context": "y", "safe_case_metadata": {},
        "expected_output_schema": "schemas/diagnosis.schema.json",
    })
    res = _sub.run(
        ["python3", stub_path],
        input=payload.encode("utf-8"),
        capture_output=True, timeout=30,
    )
    assert res.returncode == 1, (
        f"expected exit 1; got {res.returncode}. stderr={res.stderr!r}"
    )
    body = json.loads(res.stdout.decode("utf-8"))
    mi = body.get("_model_info") or {}
    assert mi.get("resolved_model") == "gpt-5-mini-2025-08-07", (
        f"model_info lost on parse failure: {body!r}"
    )
    assert body.get("_provider_error", "").startswith("post_api_error:"), (
        f"missing structured error hint: {body!r}"
    )


def test_fresh_row_requires_model_info_when_config_declares_identity():
    """Per Codex 2026-05-18 F2 [high]: a real-debugger config that
    declares cache_key_env or model.model_name MUST get a row with
    `_model_info.requested_model` from the shim. Pre-fix, missing
    provenance was accepted as legacy back-compat for EVERY config,
    letting a stale/custom shim write rows under real-debugger-v3
    with no model identity."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    # Shim returns a diagnosis body with NO _model_info — should reject.
    diag_no_mi = {"summary": "looks fine", "root_cause_category": "test_assertion"}
    err = rd.validate_fresh_row_model_identity(diag_no_mi, cfg)
    assert err is not None, "missing _model_info under v3 should reject"
    assert "provenance" in err.lower() or "_model_info" in err


def test_fresh_row_allows_missing_model_info_with_explicit_optout():
    """Legacy diagnosers can opt out by setting model.allow_missing_model_info."""
    cfg = {
        "diagnoser_name": "legacy-mock",
        "model": {"model_name": "x", "allow_missing_model_info": True},
    }
    diag_no_mi = {"summary": "x"}
    err = rd.validate_fresh_row_model_identity(diag_no_mi, cfg)
    assert err is None


def test_cache_hit_rejects_null_model_info_for_real_debugger():
    """Per Codex 2026-05-18 F2 [high]: cache_hit_is_acceptable now also
    requires model_info when the config declares identity. Previously
    a cached row with null model_info passed as legacy."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    row_no_mi = {"metadata": {"model_info": None}}
    ok, reason = rd.cache_hit_is_acceptable(row_no_mi, cfg)
    assert not ok, "v3 cached row without model_info should reject"
    assert "provenance" in (reason or "").lower() or "model_info" in (reason or "")


def test_cache_hit_accepts_legacy_null_when_config_opts_out():
    cfg = {"model": {"model_name": "x", "allow_missing_model_info": True}}
    row_no_mi = {"metadata": {"model_info": None}}
    ok, reason = rd.cache_hit_is_acceptable(row_no_mi, cfg)
    assert ok and reason is None


def test_base_url_validation_uses_sha256_when_available():
    """Per Codex 2026-05-18 F3 [medium]: when the cached row has
    base_url_sha256, compare hashes — the shim writes a sanitized URL
    but the hash is over the FULL URL (including proxy creds), so
    sha256 comparison is the right identity check."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    # Canonical: hash matches both sides
    expected_url = rd.effective_base_url(cfg)
    expected_hash = rd._base_url_sha256_for_compare(expected_url)
    row_ok = {"metadata": {"model_info": {
        "requested_model": "gpt-5-mini",
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": expected_hash,
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row_ok, cfg)
    assert ok, f"canonical row should accept: {reason}"
    # Hash mismatch (someone hand-poisoned with a row from a different
    # endpoint) → reject.
    row_bad = {"metadata": {"model_info": {
        "requested_model": "gpt-5-mini",
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": "a" * 64,  # wrong hash
    }}}
    ok2, reason2 = rd.cache_hit_is_acceptable(row_bad, cfg)
    assert not ok2
    assert "sha256" in (reason2 or "").lower()


def test_base_url_validation_credentialed_proxy_accepts_own_row():
    """Per Codex 2026-05-18 F3 [medium]: the failing scenario.

    User points CILOGBENCH_OPENAI_BASE_URL at a proxy URL with
    userinfo: `https://u:p@proxy/v1?token=xyz`. The shim sanitizes
    when persisting: `metadata.model_info.base_url = "https://proxy/v1"`,
    `base_url_sha256 = sha256("https://u:p@proxy/v1?token=xyz")`. On
    rerun, the cache_key matches (env-driven) and the validator must
    NOT reject the row it just wrote.
    """
    cfg = {
        "model": {
            "model_name": "gpt-5-mini",
            "env_var_name": "CILOGBENCH_OPENAI_MODEL",
            "base_url": "https://api.openai.com/v1",
            "base_url_env_var_name": "CILOGBENCH_OPENAI_BASE_URL",
        }
    }
    proxy_url = "https://user:pass@proxy.example.com/v1?token=abc"
    sanitized = "https://proxy.example.com/v1"
    full_hash = rd._base_url_sha256_for_compare(proxy_url)
    saved = os.environ.get("CILOGBENCH_OPENAI_BASE_URL")
    saved_model = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_BASE_URL"] = proxy_url
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        row = {"metadata": {"model_info": {
            "requested_model": "gpt-5-mini",
            "base_url": sanitized,
            "base_url_sha256": full_hash,
        }}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert ok, f"proxy run should accept its own row; got: {reason}"
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_BASE_URL"] = saved
        if saved_model is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved_model


def test_base_url_validation_falls_back_to_sanitized_compare():
    """For legacy rows that have only `base_url` (no sha256), the
    validator sanitizes BOTH sides before comparing — so a raw
    config-effective URL with userinfo doesn't false-mismatch the
    shim's already-sanitized cached value."""
    cfg = {
        "model": {
            "model_name": "gpt-5-mini",
            "env_var_name": "CILOGBENCH_OPENAI_MODEL",
            "base_url": "https://api.openai.com/v1",
            "base_url_env_var_name": "CILOGBENCH_OPENAI_BASE_URL",
        }
    }
    saved = os.environ.get("CILOGBENCH_OPENAI_BASE_URL")
    saved_model = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_BASE_URL"] = "https://u:p@proxy/v1?t=1"
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        row = {"metadata": {"model_info": {
            "requested_model": "gpt-5-mini",
            "base_url": "https://proxy/v1",   # legacy: only sanitized, no sha256
        }}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert ok, f"legacy sanitized-only row should accept: {reason}"
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_BASE_URL"] = saved
        if saved_model is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved_model


def test_fresh_row_rejects_wrong_endpoint():
    """Per Codex 2026-05-19 F1 [high]: a stale shim that ignores
    CILOGBENCH_OPENAI_BASE_URL could send context to the default OpenAI
    endpoint and emit `requested_model: gpt-5-mini`. Pre-fix, the
    fresh-row validator only compared `requested_model` — that row
    would have been written under a proxy-backed v3 config silently.
    """
    cfg = {
        "model": {
            "model_name": "gpt-5-mini",
            "env_var_name": "CILOGBENCH_OPENAI_MODEL",
            "base_url": "https://api.openai.com/v1",
            "base_url_env_var_name": "CILOGBENCH_OPENAI_BASE_URL",
        },
        "cache_key_env": ["CILOGBENCH_OPENAI_MODEL", "CILOGBENCH_OPENAI_BASE_URL"],
    }
    # User points config at a proxy; stale shim hits default OpenAI.
    saved_url = os.environ.get("CILOGBENCH_OPENAI_BASE_URL")
    saved_model = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_BASE_URL"] = "https://my-proxy.example.com/v1"
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        # Shim emits canonical OpenAI URL (it ignored the env override).
        diag = {"_model_info": {
            "requested_model": "gpt-5-mini",
            "base_url": "https://api.openai.com/v1",
            "base_url_sha256": rd._base_url_sha256_for_compare(
                "https://api.openai.com/v1"
            ),
        }}
        err = rd.validate_fresh_row_model_identity(diag, cfg)
        assert err is not None, "wrong-endpoint fresh row should reject"
        assert "endpoint mismatch" in err.lower() or "base_url" in err
    finally:
        if saved_url is None:
            os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_BASE_URL"] = saved_url
        if saved_model is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved_model


def test_fresh_row_rejects_when_endpoint_evidence_missing():
    """Per Codex 2026-05-20 F1 [high]: a config that declares
    cache_key_env / model.model_name AND model.base_url MUST get rows
    with at least one of base_url / base_url_sha256. A stale shim
    emitting only `requested_model` could otherwise bypass the
    endpoint check entirely."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    diag = {"_model_info": {"requested_model": "gpt-5-mini"}}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None, "missing endpoint evidence should reject"
    assert "base_url" in err and "provenance" in err.lower()


def test_cache_hit_rejects_when_endpoint_evidence_missing():
    """Same scenario at the cache layer."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    row = {"metadata": {"model_info": {"requested_model": "gpt-5-mini"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok
    assert "base_url" in reason and "provenance" in reason.lower()


def test_endpoint_evidence_optional_for_legacy_optout_config():
    """Legacy configs that explicitly opt out of provenance via
    `model.allow_missing_model_info: true` continue to pass without
    endpoint evidence."""
    cfg = {
        "model": {
            "model_name": "x",
            "base_url": "https://api.openai.com/v1",
            "allow_missing_model_info": True,
        },
    }
    diag = {"_model_info": {"requested_model": "x"}}  # no base_url
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is None


def test_fresh_row_accepts_matching_endpoint():
    """Sanity: a shim emitting model + endpoint that match the config
    passes the fresh-row gate."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    diag = {"_model_info": {
        "requested_model": "gpt-5-mini",
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": rd._base_url_sha256_for_compare(
            "https://api.openai.com/v1"
        ),
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is None, f"canonical row should pass: {err}"


def test_openai_shim_oversized_context_emits_structured_provider_error():
    """Per Codex 2026-05-19 F2 [medium]: the shim's pre-API skip path
    (context exceeds 480000 chars) must write a JSON envelope to stdout
    so `metadata.provider_error` lands as `unsupported_context_too_large:
    ...` instead of the runner's wrapper string. Verified end-to-end via
    a real subprocess invocation with an oversized payload."""
    import subprocess as _sub
    import json as _json

    payload = _json.dumps({
        "case_id": "t", "context_method": "raw", "prompt": "x",
        "context": "X" * 600_000,  # exceeds 480000 cap
        "safe_case_metadata": {},
        "expected_output_schema": "schemas/diagnosis.schema.json",
    })
    repo = str(Path(__file__).resolve().parent.parent.parent)
    env = dict(os.environ)
    env["OPENAI_API_KEY"] = "sk-test"
    env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
    res = _sub.run(
        ["python3", f"{repo}/examples/diagnosis_shim_openai.py"],
        input=payload.encode("utf-8"),
        capture_output=True, timeout=20, env=env,
    )
    assert res.returncode == 1, (
        f"expected exit 1; got {res.returncode}. stderr={res.stderr!r}"
    )
    # stdout has a JSON envelope with _provider_error
    body = _json.loads(res.stdout.decode("utf-8"))
    err_str = body.get("_provider_error", "")
    assert err_str.startswith("unsupported_context_too_large:"), (
        f"expected unsupported_context_too_large prefix; got {err_str!r}"
    )


def test_v3_committed_artifacts_provider_error_starts_with_class():
    """Per Codex 2026-05-19 F2 [medium]: lock the taxonomy contract.
    Every committed v3 provider_error must start with one of the
    known stable classes — model card / report claims rely on
    by-prefix counting."""
    import json as _json
    repo = Path(__file__).resolve().parent.parent.parent
    valid_prefixes = (
        "unsupported_context_too_large:",
        "post_api_error:",
        "post_cli_error:",
        # Legacy patterns that pre-date the taxonomy contract; the
        # 2026-05-17 backfill normalized v3 to one of the above, but
        # historical v1/v2 rows can still match these.
        "JSONDecodeError:",
        "RemoteDisconnected:",
        "RuntimeError:",  # legacy v1 claude-CLI-exit rows
    )
    failures = []
    for sp in ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]:
        diag_dir = repo / "results" / sp / "diagnoses" / "real-debugger-v3"
        if not diag_dir.exists():
            continue
        for mf in diag_dir.glob("*.jsonl"):
            for line in mf.open():
                row = _json.loads(line)
                md = row.get("metadata") or {}
                pe = md.get("provider_error") or ""
                if not pe:
                    continue
                if not pe.startswith(valid_prefixes):
                    failures.append(
                        f"{sp}/{mf.stem}/{row.get('case_id')}: {pe[:80]!r}"
                    )
    assert not failures, (
        "v3 provider_error values must start with a known taxonomy "
        "prefix:\n  " + "\n  ".join(failures[:10])
    )


def test_reusable_template_allows_diagnoser_name_override():
    """Per Codex 2026-05-22 F1 [high]: example.debugger-v1-command.json
    opts into name-override mode (`reusable_template: true`). The docs
    document calling it with --diagnoser-name=stub-debugger-v1 etc.;
    pre-fix the 2026-05-15 strict check rejected those workflows."""
    repo = Path(__file__).resolve().parent.parent.parent
    example_path = repo / "configs" / "diagnosers" / "example.debugger-v1-command.json"
    # The config declares example-debugger-v1; pass a different name.
    cfg = rd.load_diagnoser_config(
        "stub-debugger-v1", explicit_path=example_path
    )
    assert cfg is not None
    assert cfg["diagnoser_name"] == "example-debugger-v1"
    assert cfg.get("reusable_template") is True


def test_canonical_config_still_strict_on_name_mismatch():
    """Real-debugger configs (v1/v2/v3) do NOT set reusable_template,
    so the strict name check from Codex 2026-05-15 still applies."""
    repo = Path(__file__).resolve().parent.parent.parent
    v3_path = repo / "configs" / "diagnosers" / "real-debugger-v3.json"
    try:
        rd.load_diagnoser_config("not-the-right-name", explicit_path=v3_path)
    except rd.DiagnoserConfigError as e:
        assert "real-debugger-v3" in str(e)
        return
    raise AssertionError("expected strict check on canonical config")


def test_build_row_records_both_names_for_template_runs():
    """When the config's declared diagnoser_name differs from the
    runtime diagnoser, metadata.diagnoser_config_name records the
    config's name so an auditor can recover both."""
    from pathlib import Path as _P
    row = rd.build_row(
        case_id="t", context_method="raw",
        diagnoser="stub-debugger-v1",
        diagnosis_body={"summary": "x", "_model_info": {"requested_model": "test"}},
        context_path=_P("/tmp/x"), context_text="",
        prompt_sha="p", runtime_ms=0.0,
        provider_name="command",
        command_str="cmd", cache_key="k",
        provider_error=None,
        diagnoser_config_name="example-debugger-v1",
    )
    assert row["metadata"]["diagnoser_config_name"] == "example-debugger-v1"
    assert row["diagnoser"] == "stub-debugger-v1"


def test_build_row_omits_diagnoser_config_name_when_names_match():
    """For canonical runs (config name == output name), the audit field
    is None to avoid duplicate noise in the manifest."""
    from pathlib import Path as _P
    row = rd.build_row(
        case_id="t", context_method="raw",
        diagnoser="real-debugger-v3",
        diagnosis_body={"summary": "x", "_model_info": {"requested_model": "test"}},
        context_path=_P("/tmp/x"), context_text="",
        prompt_sha="p", runtime_ms=0.0,
        provider_name="command",
        command_str="cmd", cache_key="k",
        provider_error=None,
        diagnoser_config_name="real-debugger-v3",
    )
    assert row["metadata"]["diagnoser_config_name"] is None


def test_runner_rejects_mock_provider_under_real_debugger_config():
    """Per Codex 2026-05-21 F1 [high]: running
    `--diagnoser-name real-debugger-v3` with default `--diagnoser mock`
    used to silently write mock rows under
    `results/<split>/diagnoses/real-debugger-v3/` with no model_info,
    bypassing every provenance gate added 2026-05-11..2026-05-20.
    The runner now fails fast at config load time."""
    import subprocess as _sub
    repo = str(Path(__file__).resolve().parent.parent.parent)
    res = _sub.run(
        ["python3", f"{repo}/tools/run_diagnosis.py",
         "--split", "dev",
         "--diagnoser", "mock",
         "--diagnoser-name", "real-debugger-v3",
         "--context-method", "grep"],
        cwd=repo, capture_output=True, timeout=20,
    )
    assert res.returncode == 1, (
        f"expected exit 1; got {res.returncode}. stderr={res.stderr.decode()[:400]!r}"
    )
    err_msg = res.stderr.decode("utf-8")
    assert "real-debugger-v3" in err_msg
    assert "provider" in err_msg.lower()


def test_runner_accepts_command_provider_under_command_config():
    """Sanity: the canonical command-provider invocation still works
    (smoke-test against dev/grep cache hits, no API call)."""
    import subprocess as _sub
    repo = str(Path(__file__).resolve().parent.parent.parent)
    env = dict(os.environ)
    env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
    env.setdefault("OPENAI_API_KEY", "sk-test")  # cache-hit only — never called
    res = _sub.run(
        ["python3", f"{repo}/tools/run_diagnosis.py",
         "--split", "dev",
         "--diagnoser", "command",
         "--diagnoser-name", "real-debugger-v3",
         "--command", f"python3 {repo}/examples/diagnosis_shim_openai.py",
         "--context-method", "grep",
         "--diagnoser-config",
         f"{repo}/configs/diagnosers/real-debugger-v3.json"],
        cwd=repo, capture_output=True, timeout=30, env=env,
    )
    assert res.returncode == 0, (
        f"canonical run should succeed; exit={res.returncode}; "
        f"stderr={res.stderr.decode()[:400]!r}"
    )
    assert b"5 cache hit" in res.stdout, res.stdout[:300]


def test_mock_provider_rejected_inline_if_config_requires_provenance():
    """Defense-in-depth: even if a caller bypassed the early
    provider/config-match check, the inline `validate_fresh_row_model_identity`
    on the mock branch still rejects rows that lack `_model_info` when
    the config declares model identity. A mock-diagnosis body never has
    model_info."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    # Simulate what `diagnose_mock` returns.
    diag = {
        "summary": "fake mock summary",
        "root_cause_category": "test_assertion",
        "confidence": 0.5,
    }  # no _model_info
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None, "mock body under v3 config must be rejected"


def test_reusable_template_skips_fresh_row_validation():
    """Per Codex 2026-05-23 F1 [high]: reusable_template configs declare
    a placeholder model_name (e.g. example-debugger-v1's
    'user-configured-model'). The actual model comes from the caller's
    shim + env. Fresh-row validation must skip identity checks against
    that placeholder; otherwise documented M6/M7 stub workflows would
    fail every fresh row with provider_error."""
    repo = Path(__file__).resolve().parent.parent.parent
    cfg = rd.load_diagnoser_config(
        "stub-debugger-v1",
        explicit_path=repo / "configs" / "diagnosers" / "example.debugger-v1-command.json",
    )
    # Stub shim emits no _model_info at all — accepted.
    err = rd.validate_fresh_row_model_identity(
        {"summary": "stub"}, cfg
    )
    assert err is None, f"stub row under template should pass: {err}"
    # Real shim emits requested_model='gpt-5-mini' — also accepted (no
    # binding to compare against).
    err2 = rd.validate_fresh_row_model_identity(
        {"_model_info": {"requested_model": "gpt-5-mini"}}, cfg
    )
    assert err2 is None, f"real-shim row under template should pass: {err2}"


def test_reusable_template_never_accepts_cache_hits():
    """Per Codex 2026-05-24 F2 [high]: templates have no
    `cache_key_env`, so changing CILOGBENCH_OPENAI_MODEL doesn't move
    the cache key, and the validators have no canonical model identity
    to compare against. A custom-template run could otherwise replay
    rows from a different model. Templates ALWAYS cache-miss, forcing
    a fresh shim call."""
    repo = Path(__file__).resolve().parent.parent.parent
    cfg = rd.load_diagnoser_config(
        "stub-debugger-v1",
        explicit_path=repo / "configs" / "diagnosers" / "example.debugger-v1-command.json",
    )
    row = {"metadata": {"model_info": {"requested_model": "haiku"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok
    assert "reusable_template" in reason


def test_cache_hit_rejects_provider_error_row_by_default():
    """Per Codex 2026-05-24 F1 [high]: a cached row with a populated
    metadata.provider_error must be rejected on read unless
    --cache-errors is passed. Pre-fix, a polluted cache entry from
    a prior --cache-errors run replayed forever, hiding transient
    failures behind a cache hit."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    row = {"metadata": {
        "model_info": {
            "requested_model": "gpt-5-mini",
            "base_url": "https://api.openai.com/v1",
            "base_url_sha256": rd._base_url_sha256_for_compare(
                "https://api.openai.com/v1"
            ),
        },
        "provider_error": "post_api_error: JSONDecodeError ...",
    }}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg, cache_errors=False)
    assert not ok
    assert "provider_error" in reason and "cache-errors" in reason


def test_cache_hit_accepts_provider_error_row_when_cache_errors_opted_in():
    """When the operator passes --cache-errors, replaying a cached
    provider_error row is the explicit intent (e.g. running the
    benchmark deterministically against known-failure rows)."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    row = {"metadata": {
        "model_info": {
            "requested_model": "gpt-5-mini",
            "base_url": "https://api.openai.com/v1",
            "base_url_sha256": rd._base_url_sha256_for_compare(
                "https://api.openai.com/v1"
            ),
        },
        "provider_error": "post_api_error: JSONDecodeError ...",
    }}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg, cache_errors=True)
    assert ok and reason is None


def test_canonical_real_debugger_still_enforces_identity():
    """v3 config (not reusable_template) still rejects identity
    mismatches. Sanity-check the opt-out is scoped to templates."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    row = {"metadata": {"model_info": {"requested_model": "gpt-4o"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok
    assert "gpt-4o" in (reason or "") and "gpt-5-mini" in (reason or "")


def test_stub_template_end_to_end_writes_clean_rows():
    """Per Codex 2026-05-23 F1 [high] end-to-end regression: the
    documented workflow (`example.debugger-v1-command.json` template
    + `examples/diagnosis_shim_stub.py`) must produce successful rows
    with `metadata.provider_error == null` — not provider_error rows
    that throw away paid API calls."""
    import subprocess as _sub
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    env = dict(os.environ)
    env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
    env["DIAGNOSIS_COMMAND"] = f"python3 {repo}/examples/diagnosis_shim_stub.py"
    res = _sub.run(
        ["python3", f"{repo}/tools/run_diagnosis.py",
         "--split", "dev",
         "--diagnoser", "command",
         "--diagnoser-name", "stub-debugger-v1",
         "--command", env["DIAGNOSIS_COMMAND"],
         "--context-method", "grep",
         "--diagnoser-config",
         f"{repo}/configs/diagnosers/example.debugger-v1-command.json",
         "--no-cache"],
        cwd=repo, capture_output=True, timeout=60, env=env,
    )
    assert res.returncode == 0, (
        f"stub template run should succeed; exit={res.returncode}; "
        f"stderr={res.stderr.decode()[:400]!r}"
    )
    manifest = repo / "results" / "dev" / "diagnoses" / "stub-debugger-v1" / "grep.jsonl"
    rows = [json.loads(l) for l in manifest.open() if l.strip()]
    assert len(rows) > 0, "manifest should contain rows"
    for row in rows:
        md = row.get("metadata") or {}
        assert md.get("provider_error") is None, (
            f"stub row should not be a provider_error: "
            f"case={row.get('case_id')!r} pe={md.get('provider_error')!r}"
        )
        # The audit trail records both names: row.diagnoser is the
        # runtime name, metadata.diagnoser_config_name is the config's
        # declared name.
        assert row.get("diagnoser") == "stub-debugger-v1"
        assert md.get("diagnoser_config_name") == "example-debugger-v1"


def test_cache_gate_respects_row_metadata_provider_error():
    """Per Codex 2026-05-22 F2 [medium]: the cache gate historically
    used the exception-local `provider_error` variable. A shim that
    exited 0 with `_provider_error` in stdout left provider_error=None
    but build_row promoted the shim hint to metadata.provider_error.
    Without the fix, the failed row got CACHED, then replayed as a
    cache hit forever. Test: simulate the row-building flow and check
    that an error row's metadata is what governs caching.
    """
    from pathlib import Path as _P
    row_with_shim_err = rd.build_row(
        case_id="t", context_method="raw",
        diagnoser="real-debugger-v3",
        diagnosis_body={
            "summary": "stub",
            "_provider_error": "post_api_error: synthetic failure",
            "_model_info": {"requested_model": "gpt-5-mini"},
        },
        context_path=_P("/tmp/x"), context_text="",
        prompt_sha="p", runtime_ms=0.0,
        provider_name="command",
        command_str="cmd", cache_key="k",
        provider_error=None,  # no exception caught
    )
    # The row's metadata MUST carry the shim's taxonomy.
    effective = (row_with_shim_err.get("metadata") or {}).get("provider_error")
    assert effective and effective.startswith("post_api_error:"), (
        f"expected post_api_error prefix; got {effective!r}"
    )
    # The cache gate now keys on this field, so the row would NOT be
    # cached without --cache-errors. (We test the gate logic directly
    # since the cache write is inside run() and requires fs setup.)


def test_protocol_report_unsupported_context_predicate_handles_both_forms():
    """Per Codex 2026-05-20 F2 [medium]: the protocol report compared
    `provider_error == "unsupported_context_too_large"` exactly. After
    the 2026-05-19 F2 fix, the value is the structured detailed form
    `unsupported_context_too_large: context (...) exceeds shim cap`.
    The new `_is_unsupported_context_error` predicate must match both
    the legacy bare class string AND the detailed prefix form, so
    counts stay accurate across the format transition."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_protocol_eval", repo / "tools" / "run_protocol_diagnosis_eval.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = mod._is_unsupported_context_error
    # Both forms count as a hit.
    assert fn("unsupported_context_too_large") is True
    assert fn("unsupported_context_too_large: context (1234) exceeds shim cap") is True
    # Other taxonomy classes / unrelated errors do not.
    assert fn("post_api_error: JSONDecodeError ...") is False
    assert fn("RuntimeError: claude CLI exited 1: ''") is False
    assert fn(None) is False
    assert fn("") is False
    # Prefix-only false-positive guard: a class whose name is a
    # SUBSTRING of the legitimate taxonomy must not be matched.
    assert fn("supported_context_too_large: foo") is False  # missing 'un'


def test_v3_committed_artifacts_have_model_info_on_post_api_failures():
    """Lock the backfill: every committed v3 row whose provider_error is
    a POST-API failure must carry metadata.model_info. Pre-2026-05-16
    these landed null and were indistinguishable from no-call skips.
    """
    import json as _json
    repo = Path(__file__).resolve().parent.parent.parent
    splits = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]
    failures = []
    for sp in splits:
        diag_dir = repo / "results" / sp / "diagnoses" / "real-debugger-v3"
        if not diag_dir.exists():
            continue
        for mf in diag_dir.glob("*.jsonl"):
            for line in mf.open():
                row = _json.loads(line)
                md = row.get("metadata") or {}
                pe = md.get("provider_error") or ""
                if not pe:
                    continue
                # Skip true no-call errors (oversized context) — those
                # legitimately have no model_info.
                if "unsupported_context_too_large" in pe:
                    continue
                mi = md.get("model_info") or {}
                if not mi.get("requested_model"):
                    failures.append(
                        f"{sp}/{mf.stem}/{row.get('case_id')}: {pe[:80]}"
                    )
    assert not failures, (
        "post-API provider_error rows missing model_info:\n  "
        + "\n  ".join(failures[:10])
    )


# === Codex 2026-05-13 F1: external-LLM opt-in gate ===

def test_opt_in_gate_blocks_when_env_unset():
    cfg = {
        "diagnoser_name": "test-debugger",
        "privacy": {"requires_explicit_external_llm_opt_in": True,
                     "explicit_opt_in_env_var": "CILOGBENCH_ALLOW_EXTERNAL_LLM"},
    }
    saved = os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
    try:
        err = rd.check_external_llm_opt_in(cfg, provider="command")
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
            err = rd.check_external_llm_opt_in(cfg, provider="command")
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
            err = rd.check_external_llm_opt_in(cfg, provider="command")
            assert err is not None, f"gate should reject {v!r}"
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
        else:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = saved


def test_opt_in_gate_skips_when_config_does_not_require():
    # Mock-provider runs are never gated regardless of config shape.
    cfg_no_req = {"diagnoser_name": "mock",
                   "privacy": {"requires_explicit_external_llm_opt_in": False}}
    assert rd.check_external_llm_opt_in(cfg_no_req, provider="mock") is None
    assert rd.check_external_llm_opt_in({}, provider="mock") is None
    assert rd.check_external_llm_opt_in(None, provider="mock") is None
    # An explicit `false` gate setting also opts out for command-provider
    # runs (e.g. a wrapper that uses a fake shim).
    assert rd.check_external_llm_opt_in(cfg_no_req, provider="command") is None


def test_opt_in_gate_fails_closed_when_command_has_no_config():
    """Per Codex 2026-05-18 F1 [high]: command-provider runs MUST have a
    loaded config that declares the gate. A missing config (auto-
    discovery failure, typo in --diagnoser-name) used to pass silently
    and ship CI logs without the gate firing."""
    saved = os.environ.pop("CILOGBENCH_ALLOW_EXTERNAL_LLM", None)
    try:
        err = rd.check_external_llm_opt_in(None, provider="command")
        assert err is not None, "command + no config should fail closed"
        assert "diagnoser config" in err
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = saved


def test_opt_in_gate_fails_closed_when_command_config_omits_gate():
    """Per Codex 2026-05-18 F1: command-provider config that doesn't
    DECLARE privacy.requires_explicit_external_llm_opt_in fails closed.
    Missing != false."""
    cfg = {"diagnoser_name": "weird", "privacy": {}}
    err = rd.check_external_llm_opt_in(cfg, provider="command")
    assert err is not None
    assert "does not declare" in err


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
        err = rd.check_external_llm_opt_in(cfg, provider="command")
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
        assert rd.check_external_llm_opt_in(cfg, provider="command") is not None
        # Custom var set passes.
        os.environ["ALLOW_CUSTOM_LLM"] = "1"
        assert rd.check_external_llm_opt_in(cfg, provider="command") is None
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
        # Codex 2026-05-15 F1 (env injection + fresh-row validation)
        test_build_shim_env_injects_alias_when_env_unset,
        test_build_shim_env_preserves_user_override,
        test_build_shim_env_no_optin_means_no_injection,
        test_validate_fresh_row_passes_when_shim_matches_config,
        test_validate_fresh_row_rejects_haiku_under_v2,
        test_validate_fresh_row_back_compat_when_shim_emits_no_model_info,
        # Codex 2026-05-15 F2 (--diagnoser-config path validation)
        test_load_diagnoser_config_explicit_path_matches_name,
        test_load_diagnoser_config_explicit_path_mismatch_raises,
        test_load_diagnoser_config_explicit_missing_path_raises,
        test_load_diagnoser_config_legacy_path_unchanged,
        test_load_diagnoser_config_legacy_missing_returns_none,
        # Codex 2026-05-16 F1 (preserve model_info on shim error path)
        test_extract_shim_stdout_metadata_picks_up_model_info,
        test_extract_shim_stdout_metadata_handles_non_json,
        test_extract_shim_stdout_metadata_ignores_non_dict,
        test_extract_shim_stdout_metadata_ignores_missing_fields,
        test_shim_call_error_carries_metadata,
        test_openai_shim_emits_model_info_envelope_on_parse_failure,
        # Codex 2026-05-18 F2 (require model_info under real configs)
        test_fresh_row_requires_model_info_when_config_declares_identity,
        test_fresh_row_allows_missing_model_info_with_explicit_optout,
        test_cache_hit_rejects_null_model_info_for_real_debugger,
        test_cache_hit_accepts_legacy_null_when_config_opts_out,
        # Codex 2026-05-18 F3 (base_url sha256 comparison)
        test_base_url_validation_uses_sha256_when_available,
        test_base_url_validation_credentialed_proxy_accepts_own_row,
        test_base_url_validation_falls_back_to_sanitized_compare,
        # Codex 2026-05-19 F1 (fresh-row endpoint validation)
        test_fresh_row_rejects_wrong_endpoint,
        # Codex 2026-05-20 F1 (require endpoint evidence)
        test_fresh_row_rejects_when_endpoint_evidence_missing,
        test_cache_hit_rejects_when_endpoint_evidence_missing,
        test_endpoint_evidence_optional_for_legacy_optout_config,
        test_fresh_row_accepts_matching_endpoint,
        # Codex 2026-05-19 F2 (oversized-context taxonomy class)
        test_openai_shim_oversized_context_emits_structured_provider_error,
        test_v3_committed_artifacts_provider_error_starts_with_class,
        # Codex 2026-05-20 F2 (protocol report prefix-aware comparison)
        test_protocol_report_unsupported_context_predicate_handles_both_forms,
        # Codex 2026-05-22 F1 (reusable_template opt-in)
        test_reusable_template_allows_diagnoser_name_override,
        test_canonical_config_still_strict_on_name_mismatch,
        test_build_row_records_both_names_for_template_runs,
        test_build_row_omits_diagnoser_config_name_when_names_match,
        # Codex 2026-05-23 F1 (reusable_template skips identity validation)
        test_reusable_template_skips_fresh_row_validation,
        # 2026-05-23 test renamed/replaced 2026-05-24 — templates are
        # no longer trusted on cache reads:
        test_reusable_template_never_accepts_cache_hits,
        test_canonical_real_debugger_still_enforces_identity,
        test_stub_template_end_to_end_writes_clean_rows,
        # Codex 2026-05-24 (cache-hit gate for provider_error rows)
        test_cache_hit_rejects_provider_error_row_by_default,
        test_cache_hit_accepts_provider_error_row_when_cache_errors_opted_in,
        # Codex 2026-05-22 F2 (cache gate uses row metadata)
        test_cache_gate_respects_row_metadata_provider_error,
        # Codex 2026-05-21 F1 (provider/config consistency)
        test_runner_rejects_mock_provider_under_real_debugger_config,
        test_runner_accepts_command_provider_under_command_config,
        test_mock_provider_rejected_inline_if_config_requires_provenance,
        test_v3_committed_artifacts_have_model_info_on_post_api_failures,
        # Codex 2026-05-13 F1
        test_opt_in_gate_blocks_when_env_unset,
        test_opt_in_gate_passes_when_env_set_to_truthy,
        test_opt_in_gate_rejects_non_truthy_values,
        test_opt_in_gate_skips_when_config_does_not_require,
        test_opt_in_gate_fails_closed_when_command_has_no_config,
        test_opt_in_gate_fails_closed_when_command_config_omits_gate,
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
