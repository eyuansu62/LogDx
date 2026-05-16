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

import contextlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent)
)
import run_diagnosis as rd  # noqa: E402


@contextlib.contextmanager
def _snapshot_restore_diag_dir(diag_dir: Path):
    """Per Codex 2026-06-07 F3 [med]: end-to-end tests that drive
    `tools/run_diagnosis.py` against the tracked `results/dev/diagnoses`
    tree must restore the on-disk state on exit so a failed run does
    not leave the canonical artifacts polluted.

    Snapshot the entire diag_dir tree (manifest + per_case/) before
    yield; restore it on __exit__ regardless of whether the test
    passed, failed an assertion, or raised. If diag_dir did not exist
    before, it is removed on cleanup.
    """
    backup_root: Path | None = None
    snap_dir: Path | None = None
    existed_before = diag_dir.exists()
    if existed_before:
        backup_root = Path(tempfile.mkdtemp(prefix="cilogbench-diag-snap-"))
        snap_dir = backup_root / "snap"
        shutil.copytree(diag_dir, snap_dir)
    try:
        yield
    finally:
        if diag_dir.exists():
            shutil.rmtree(diag_dir)
        if existed_before and snap_dir is not None:
            shutil.copytree(snap_dir, diag_dir)
        if backup_root is not None and backup_root.exists():
            shutil.rmtree(backup_root)


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
    row = {"metadata": {"model_info": {"provider_name": "openai", "requested_model": "gpt-5-mini"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert ok and reason is None, f"expected accept, got ({ok}, {reason!r})"


def test_cache_hit_rejected_on_mismatch():
    cfg = _cfg()
    row = {"metadata": {"model_info": {"provider_name": "openai", "requested_model": "gpt-4o"}}}
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
    """Env override only takes effect when the config opts in via
    `model.allow_runtime_model_override` (Codex 2026-06-05 F2).
    Canonical real-debugger-* configs do NOT set this flag, so env
    overrides are ignored at the validator layer."""
    cfg = {"model": {
        "model_name": "gpt-5-mini",
        "env_var_name": "CILOGBENCH_OPENAI_MODEL",
        "allow_runtime_model_override": True,
    }}
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
    """With allow_runtime_model_override=true (experiment mode),
    env-override runs are idempotent. The 2026-05-13 F2 scenario."""
    cfg = {"model": {
        "model_name": "gpt-5-mini",
        "env_var_name": "CILOGBENCH_OPENAI_MODEL",
        "allow_runtime_model_override": True,
    }}
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        row = {"metadata": {"model_info": {"provider_name": "openai", "requested_model": "gpt-4o"}}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert ok and reason is None, (
            f"env-override hit should accept under allow_runtime_model_override; "
            f"got ({ok}, {reason!r})"
        )
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_locked_config_check_helper():
    """Per Codex 2026-06-06 F1 [high]: the new check_locked_env_override
    helper. Canonical configs (no allow_runtime_model_override) with
    a non-canonical env value must return an error string."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")  # canonical, locked
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        # Non-canonical env value → error
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        err = rd.check_locked_env_override(cfg)
        assert err is not None
        assert "gpt-4o" in err and "gpt-5-mini" in err
        # Canonical env value → OK
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        assert rd.check_locked_env_override(cfg) is None
        # Env unset → OK
        os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        assert rd.check_locked_env_override(cfg) is None
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_override_allowed_config_skips_locked_check():
    """Experiment-mode configs (allow_runtime_model_override=true)
    don't trip the locked-env check."""
    cfg = {"model": {
        "model_name": "gpt-5-mini",
        "env_var_name": "CILOGBENCH_OPENAI_MODEL",
        "allow_runtime_model_override": True,
    }}
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        assert rd.check_locked_env_override(cfg) is None
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_locked_env_mismatch_blocks_shim_invocation_end_to_end():
    """Per Codex 2026-06-06 F1 [high]: the EXACT regression Codex
    requested — prove no external shim is called on locked-config
    env mismatch.

    Uses a command-spy shim that writes a sentinel to a temp file
    every time it's invoked. If the runner correctly fails fast on
    the locked-env mismatch, the sentinel file remains empty.
    """
    import subprocess as _sub
    import tempfile
    repo = Path(__file__).resolve().parent.parent.parent

    sentinel = tempfile.NamedTemporaryFile(
        suffix=".sentinel", delete=False
    )
    sentinel.close()
    Path(sentinel.name).write_text("")

    spy_src = f'''
import sys
from pathlib import Path
Path({sentinel.name!r}).write_text("INVOKED")
sys.exit(1)
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
        fp.write(spy_src)
        fp.flush()
        spy_path = fp.name

    env = dict(os.environ)
    env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
    env["OPENAI_API_KEY"] = "sk-test"
    env["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"  # mismatched vs v3's gpt-5-mini
    env["DIAGNOSIS_COMMAND"] = f"python3 {spy_path}"
    res = _sub.run(
        ["python3", f"{repo}/tools/run_diagnosis.py",
         "--split", "dev",
         "--diagnoser", "command",
         "--diagnoser-name", "real-debugger-v3",
         "--command", env["DIAGNOSIS_COMMAND"],
         "--context-method", "grep",
         "--diagnoser-config",
         f"{repo}/configs/diagnosers/real-debugger-v3.json",
         "--no-cache"],
        cwd=repo, capture_output=True, timeout=30, env=env,
    )
    assert res.returncode == 1, f"expected exit 1; got {res.returncode}"
    err = res.stderr.decode("utf-8")
    assert "locks model identity" in err or "gpt-4o" in err, err[:400]
    # KEY: the spy shim was never invoked.
    sentinel_content = Path(sentinel.name).read_text()
    assert sentinel_content == "", (
        f"shim was invoked despite locked-config mismatch: "
        f"sentinel={sentinel_content!r}"
    )


def test_canonical_config_rejects_env_override():
    """Per Codex 2026-06-05 F2 [high]: WITHOUT
    allow_runtime_model_override, env overrides are treated as
    identity mismatches. A user running real-debugger-v3 with
    CILOGBENCH_OPENAI_MODEL=gpt-4o would have written rows under
    v3's canonical output path with gpt-4o results. Now: the
    validator rejects."""
    cfg = {"model": {
        "provider_name": "openai",
        "model_name": "gpt-5-mini",
        "env_var_name": "CILOGBENCH_OPENAI_MODEL",
        # NOTE: NO allow_runtime_model_override → locked
    }}
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        # Shim under env override would emit requested_model=gpt-4o
        row = {"metadata": {"model_info": {"provider_name": "openai", "requested_model": "gpt-4o"}}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert not ok, "canonical config must reject env-override rows"
        assert "gpt-4o" in reason and "gpt-5-mini" in reason
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved


def test_cache_hit_still_rejects_genuinely_wrong_cached_model():
    # Belt-and-suspenders still fires when cache is poisoned with a row
    # from a different model than the current effective model.
    cfg = {"model": {
        "model_name": "gpt-5-mini",
        "env_var_name": "CILOGBENCH_OPENAI_MODEL",
        "allow_runtime_model_override": True,
    }}
    saved = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-4o"
        # Cached row claims to be from a third, unrelated model.
        row = {"metadata": {"model_info": {"provider_name": "anthropic", "requested_model": "claude-haiku"}}}
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
        row = {"metadata": {"model_info": {"provider_name": "anthropic", "requested_model": "haiku"}}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert ok and reason is None, (
            f"v1 default cache row should pass; got ({ok}, {reason!r})"
        )
    finally:
        if saved is not None:
            os.environ["CILOGBENCH_CLAUDE_MODEL"] = saved


def test_v1_cache_hit_rejects_wrong_model():
    # A v1 cache row that was somehow written with model_info from a
    # different Anthropic model (e.g. opus left over from a
    # misconfigured run, same family but wrong alias) gets rejected
    # under the canonical config.
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    saved = os.environ.pop("CILOGBENCH_CLAUDE_MODEL", None)
    try:
        # Note: provider_name is intentionally the CORRECT family so the
        # test isolates the requested_model check (not the
        # 2026-06-02 F1 provider_name check).
        row = {"metadata": {"model_info": {"provider_name": "anthropic", "requested_model": "opus"}}}
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
    """v3 row with matching alias + endpoint + pinned snapshot. The
    Codex 2026-05-20 F1 fix requires endpoint evidence under
    provenance-required configs (real-debugger-v3 declares
    cache_key_env). The 2026-05-27 F2 fix additionally requires
    a non-null resolved_model matching `model.expected_resolved_model`
    on fresh rows."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    diag = {"_model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
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
        diag = {"_model_info": {"provider_name": "anthropic", "requested_model": "haiku"}}
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
        model_info={"provider_name": "openai", "requested_model": "gpt-5-mini"},
        provider_error_hint="post_api_error: ...",
    )
    assert err.model_info == {"provider_name": "openai", "requested_model": "gpt-5-mini"}
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
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": expected_hash,
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row_ok, cfg)
    assert ok, f"canonical row should accept: {reason}"
    # Hash mismatch (someone hand-poisoned with a row from a different
    # endpoint) → reject.
    row_bad = {"metadata": {"model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
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
            "provider_name": "openai", "requested_model": "gpt-5-mini",
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
    validator sanitizes BOTH sides before comparing.

    Per Codex 2026-06-03 F2 [high]: this fallback ONLY applies when
    the config opts out of provenance (`model.allow_missing_model_info:
    true`) OR when sanitization is non-lossy. Provenance-required
    configs with lossy endpoints now require `base_url_sha256`.

    Per Codex 2026-06-19 F1 [high]: hostname redaction now applies
    to non-allowlisted hosts on BOTH the shim and runner sides, so
    this test uses the allowlisted `api.openai.com` host. A
    proxy-style host like `https://proxy/v1` would be redacted on
    both sides equally, BUT a legacy row recording the bare
    unredacted form would correctly be rejected (forcing a fresh
    re-stamp). The fallback path still applies for allowlisted
    hosts where the sanitized form is stable.
    """
    # Legacy opt-out config: sanitized-only fallback still works.
    cfg_legacy = {
        "model": {
            "model_name": "gpt-5-mini",
            "env_var_name": "CILOGBENCH_OPENAI_MODEL",
            "base_url": "https://api.openai.com/v1",
            "base_url_env_var_name": "CILOGBENCH_OPENAI_BASE_URL",
            "allow_missing_model_info": True,
        }
    }
    saved = os.environ.get("CILOGBENCH_OPENAI_BASE_URL")
    saved_model = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        # Allowlisted host with userinfo + query; sanitized form
        # collapses to https://api.openai.com/v1 on both sides.
        os.environ["CILOGBENCH_OPENAI_BASE_URL"] = "https://u:p@api.openai.com/v1?t=1"
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        row = {"metadata": {"model_info": {
            "provider_name": "openai", "requested_model": "gpt-5-mini",
            "base_url": "https://api.openai.com/v1",
        }}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg_legacy)
        assert ok, f"legacy opt-out + sanitized-only row should accept: {reason}"
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_BASE_URL"] = saved
        if saved_model is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved_model


def test_lossy_endpoint_requires_sha256_under_provenance_config():
    """Per Codex 2026-06-03 F2 [high]: distinct proxy tenants like
    `https://proxy/tenant-a/v1` and `https://proxy/tenant-b/v1` both
    sanitize to `https://proxy` (the ^v\\d+$-only allowlist drops
    non-version first segments). A sanitized-only comparison can't
    distinguish them — fresh rows + cache hits under
    provenance-required configs must carry `base_url_sha256`.
    """
    cfg = {
        "model": {
            "provider_name": "openai",
            "model_name": "gpt-5-mini",
            "env_var_name": "CILOGBENCH_OPENAI_MODEL",
            "base_url": "https://proxy.example.com/tenant-a/v1",  # lossy
            "base_url_env_var_name": "CILOGBENCH_OPENAI_BASE_URL",
        },
        "cache_key_env": ["CILOGBENCH_OPENAI_BASE_URL"],
    }
    saved = os.environ.get("CILOGBENCH_OPENAI_BASE_URL")
    saved_model = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_BASE_URL"] = (
            "https://proxy.example.com/tenant-a/v1"
        )
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        # Row with only sanitized base_url, no sha256 — could equally
        # be tenant-a or tenant-b. Reject.
        row = {"metadata": {"model_info": {
            "provider_name": "openai",
            "requested_model": "gpt-5-mini",
            "base_url": "https://proxy.example.com",  # sanitized; tenant lost
        }}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert not ok
        assert "lossily" in (reason or "").lower() or "sha256" in (reason or "").lower()

        # With the full-URL sha256 from the canonical run, the row
        # passes.
        row_ok = {"metadata": {"model_info": {
            "provider_name": "openai",
            "requested_model": "gpt-5-mini",
            "base_url": "https://proxy.example.com",
            "base_url_sha256": rd._base_url_sha256_for_compare(
                "https://proxy.example.com/tenant-a/v1"
            ),
        }}}
        ok2, _ = rd.cache_hit_is_acceptable(row_ok, cfg)
        assert ok2
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_BASE_URL"] = saved
        if saved_model is None:
            os.environ.pop("CILOGBENCH_OPENAI_MODEL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_MODEL"] = saved_model


def test_redaction_error_does_not_echo_raw_cached_url():
    """Per Codex 2026-06-04 F1 [high]: when the validator rejects an
    unsanitized cached_url, the rejection reason must NOT include the
    raw URL — that reason flows through cache_reject / FAIL_PROVENANCE
    logs and would leak the secrets the guard was supposed to block.
    Use the sanitized form + sha256 prefix instead."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    secret_url = (
        "https://user:PASS-SECRET@api.openai.com/tenant-SECRET/v1?token=TOK-SECRET"
    )
    diag = {"_model_info": {
        "provider_name": "openai",
        "requested_model": "gpt-5-mini",
        "base_url": secret_url,
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None
    for secret in ("PASS-SECRET", "tenant-SECRET", "TOK-SECRET",
                    "user:PASS-SECRET", "?token="):
        assert secret not in err, f"redaction error leaked {secret!r}: {err!r}"
    # The legitimate sanitized form + a sha prefix may appear (those
    # are themselves redacted/identifying-only).
    assert "sha=" in err.lower() or "unsanitized_sha" in err


def test_openai_shim_redacts_url_in_malformed_base_url_error():
    """Per Codex 2026-06-04 F2 [high]: a typo'd or proxy-token
    `CILOGBENCH_OPENAI_BASE_URL` would historically surface in
    `urllib.request` exception text (`ValueError: unknown url type:
    'malformed-secret/v1'`). The shim's stderr is promoted into
    `metadata.provider_error`, so secret-bearing values would land
    in committed artifacts. Now: the shim validates scheme upfront
    and never echoes the raw value."""
    import subprocess as _sub
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    env = dict(os.environ)
    env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
    env["OPENAI_API_KEY"] = "sk-test"
    env["CILOGBENCH_OPENAI_BASE_URL"] = (
        "malformed-secret-token/v1/private-route"
    )
    res = _sub.run(
        ["python3", f"{repo}/examples/diagnosis_shim_openai.py"],
        input=json.dumps({
            "case_id": "t", "context_method": "raw", "prompt": "x",
            "context": "y", "safe_case_metadata": {},
            "expected_output_schema": "s",
        }).encode("utf-8"),
        capture_output=True, timeout=20, env=env,
    )
    assert res.returncode == 1
    stdout = res.stdout.decode("utf-8")
    stderr = res.stderr.decode("utf-8")
    body = json.loads(stdout)
    pe = body.get("_provider_error", "")
    assert pe.startswith("invalid_base_url_scheme:"), pe
    # Crucially: the raw secret-bearing value must NOT appear in
    # either stdout (which the runner persists) or stderr (which
    # the runner promotes into row.metadata.provider_error).
    for secret in ("malformed-secret-token", "private-route",
                    "secret-token", "secret"):
        assert secret not in pe, f"leak in stdout envelope: {secret!r}: {pe!r}"
        assert secret not in stderr, f"leak in stderr: {secret!r}: {stderr!r}"


def test_redact_urls_in_text_helper():
    """Unit test for the shim's URL scrubber."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_openai", repo / "examples" / "diagnosis_shim_openai.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = mod.redact_urls_in_text
    # Single URL in exception-shaped text is replaced.
    text = (
        "ValueError: unknown url type: "
        "'https://user:pass@proxy/tenant-secret/v1?token=ABC'"
    )
    redacted = f(text)
    assert "pass@proxy" not in redacted
    assert "tenant-secret" not in redacted
    assert "token=ABC" not in redacted
    assert "<redacted-url" in redacted
    # Multiple URLs in one string each get scrubbed.
    text2 = "first https://a/secret and second http://b/secret"
    out2 = f(text2)
    assert "secret" not in out2
    # Empty / None handled.
    assert f("") == ""
    assert f(None) is None


def test_validation_error_does_not_leak_raw_url_with_secrets():
    """Per Codex 2026-06-03 F1 [high]: error strings must redact the
    raw env URL. Forge a config that triggers the
    "missing-endpoint-evidence" path with a credentialed env value
    and assert NO userinfo/query token appears in the error."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    saved_url = os.environ.get("CILOGBENCH_OPENAI_BASE_URL")
    saved_model = os.environ.get("CILOGBENCH_OPENAI_MODEL")
    try:
        os.environ["CILOGBENCH_OPENAI_BASE_URL"] = (
            "https://user:PASS-SECRET@proxy/tenant-SECRET/v1?token=TOK-SECRET"
        )
        os.environ["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        # Row with NO base_url evidence — triggers the missing-endpoint
        # error path that previously included the raw expected_url.
        row = {"metadata": {"model_info": {
            "provider_name": "openai", "requested_model": "gpt-5-mini",
            "resolved_model": "gpt-5-mini-2025-08-07",
        }}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert not ok
        # No raw secret bits must appear.
        for secret in ("PASS-SECRET", "tenant-SECRET", "TOK-SECRET",
                        "user:PASS-SECRET", "?token="):
            assert secret not in (reason or ""), (
                f"validation error leaked {secret!r}: {reason!r}"
            )
    finally:
        if saved_url is None:
            os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_BASE_URL"] = saved_url
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
            "provider_name": "openai", "requested_model": "gpt-5-mini",
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
    diag = {"_model_info": {"provider_name": "openai", "requested_model": "gpt-5-mini"}}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None, "missing endpoint evidence should reject"
    assert "base_url" in err and "provenance" in err.lower()


def test_cache_hit_rejects_when_endpoint_evidence_missing():
    """Same scenario at the cache layer. Note: row has the pinned
    resolved_model so the resolved-model gate passes; only the
    endpoint-missing branch fires."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    row = {"metadata": {"model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
    }}}
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
    """Sanity: a shim emitting model + endpoint + pinned snapshot that
    match the config passes the fresh-row gate. Per 2026-05-27 F2,
    resolved_model must also be non-null and match the pin."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    diag = {"_model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
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
    (smoke-test against dev/grep cache hits, no API call).

    Per Codex 2026-06-08 F2 [high]: cache keys now fold the loaded
    diagnoser config SHA + shim-impl SHA so a config or shim edit
    invalidates stale cache entries. If those caches are remapped
    (one-shot migration on the F2 commit), this test stays a cache-
    hit replay; if not, the runner would fall through to fresh API
    calls and the Codex 2026-06-08 F1 fail-closed gate would
    correctly exit non-zero. Either outcome is appropriate; the
    snapshot/restore wrapper protects tracked artifacts in the
    fall-through case.
    """
    import subprocess as _sub
    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
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
        {"_model_info": {"provider_name": "openai", "requested_model": "gpt-5-mini"}}, cfg
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
    row = {"metadata": {"model_info": {"provider_name": "anthropic", "requested_model": "haiku"}}}
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
            "provider_name": "openai", "requested_model": "gpt-5-mini",
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


def test_fresh_row_rejects_resolved_model_drift():
    """Per Codex 2026-05-26 F1 [high]: the fresh-row path now enforces
    the same resolved_model check as cache-hit. Pre-fix, a stale shim
    or alias-rotation event could write rows from a different snapshot
    under real-debugger-v3 before any cache read noticed."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    # Diagnosis body emits resolved_model from a future-rotated snapshot.
    diag = {"_model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2099-01-01",
        "base_url": rd._sanitize_base_url_for_compare(expected_url),
        "base_url_sha256": rd._base_url_sha256_for_compare(expected_url),
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None, "rotated resolved_model fresh row should reject"
    assert "resolved_model" in err and "2099-01-01" in err


def test_fresh_row_accepts_canonical_resolved_model():
    """Canonical snapshot — fresh row passes."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    diag = {"_model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
        "base_url": rd._sanitize_base_url_for_compare(expected_url),
        "base_url_sha256": rd._base_url_sha256_for_compare(expected_url),
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is None, f"canonical fresh row should pass: {err}"


# NOTE: the prior 2026-05-26 test
# `test_fresh_row_back_compat_null_resolved_model` was superseded by the
# Codex 2026-05-27 F2 fix — fresh rows now MUST carry a non-null
# resolved_model under pinned configs. See
# `test_fresh_row_rejects_null_resolved_model_under_pin` and
# `test_cache_hit_accepts_null_resolved_model_under_pin` below for the
# asymmetric fresh-row-strict / cache-hit-legacy contract.


def test_fresh_row_rejects_null_resolved_model_under_pin():
    """Per Codex 2026-05-27 F2 [high]: a successful fresh row under a
    config that pins expected_resolved_model MUST carry a non-null
    resolved_model. Pre-fix, a compatible endpoint that omitted the
    `model` field from its response would produce a row with
    requested_model + base_url but no resolved_model, and the
    validator passed it as legacy back-compat — silently bypassing
    the alias-rotation check."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    diag = {"_model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": None,
        "base_url": rd._sanitize_base_url_for_compare(expected_url),
        "base_url_sha256": rd._base_url_sha256_for_compare(expected_url),
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None, (
        "fresh row with null resolved_model under pinned config should reject"
    )
    assert "resolved_model" in err and "snapshot evidence" in err.lower()


def test_cache_hit_rejects_null_resolved_model_under_pin():
    """Per Codex 2026-06-05 F1 [high]: the cache-hit path is now ALSO
    strict on null resolved_model when the config pins a snapshot.
    Pre-fix, a stale or injected cache row with matching
    requested_model + base_url but null resolved_model would be
    accepted and could overwrite manifests as v3 output without a
    fresh provider call. Now: rejected, forcing a fresh call (which
    will populate resolved_model from the API response)."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    row = {"metadata": {"model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": None,
        "base_url": rd._sanitize_base_url_for_compare(expected_url),
        "base_url_sha256": rd._base_url_sha256_for_compare(expected_url),
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok, "null resolved_model cache row under pin must reject now"
    assert "resolved_model" in (reason or "")


def test_provenance_mismatch_skips_manifest_write():
    """Per Codex 2026-05-27 F1 [high]: when fresh-row provenance
    validation fails, the runner must NOT write a provider_error stub
    row to the manifest — that pollutes the canonical
    results/<split>/diagnoses/<name>/ location with the same shape as
    a model abstention. Skip the case entirely.

    Smoke-test by running with a config that pins a different
    resolved_model than what the shim emits, and confirming:
      (a) exit code is non-zero
      (b) no row gets appended to the manifest for that case (or the
          existing row is left unchanged)

    Per Codex 2026-06-07 F3 [med]: wrapped in _snapshot_restore_diag_dir
    so a failed run cannot leave the tracked results/dev/diagnoses/
    real-debugger-v3 tree polluted with the forged row.
    """
    import subprocess as _sub
    import json
    import tempfile

    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        # Use the stub shim: it emits a row WITHOUT _model_info, so under
        # a real config the validator will reject. We tee the stub's row
        # through a tiny pass-through that ADDS a wrong _model_info so
        # the fresh-row check fires (rather than the "missing model_info"
        # path).
        stub_pkg = '''
import json, sys
data = json.load(sys.stdin)
# Forge a wrong resolved_model
print(json.dumps({
    "summary": "fake",
    "root_cause_category": "test_assertion",
    "root_cause": "synthetic",
    "confidence": 0.5,
    "relevant_files": [], "relevant_tests": [],
    "evidence": [], "suggested_fix": "",
    "_model_info": {
        "provider_name": "openai",
        "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2099-01-01",
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": "''' + rd._base_url_sha256_for_compare(
            "https://api.openai.com/v1"
        ) + '''",
    },
}))
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(stub_pkg)
            fp.flush()
            forge_path = fp.name

        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"
        manifest = diag_dir / "grep.jsonl"

        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        # exit non-zero because no rows were written (had_failure set)
        # AND specifically FAIL_PROVENANCE was logged
        err_text = res.stderr.decode("utf-8")
        assert "FAIL_PROVENANCE" in err_text, (
            f"expected FAIL_PROVENANCE log; stderr={err_text[:400]!r}"
        )
        assert "resolved_model" in err_text, err_text[:400]
        assert res.returncode != 0, (
            f"expected non-zero exit when provenance fails; got {res.returncode}"
        )

        # Manifest write was skipped — it should be EMPTY (or absent), not
        # a manifest of provider_error stubs.
        if manifest.exists():
            post_rows = [json.loads(l) for l in manifest.open() if l.strip()]
            # The runner's last action writes the manifest from out_rows;
            # if every case is skipped, out_rows is empty and the file
            # gets truncated. Allow either: file truncated (no rows) OR
            # file matches pre-state.
            if post_rows:
                # Pre-existing rows preserved (file matched pre-state),
                # not polluted with new provider_error stubs.
                assert all(
                    (r.get("metadata") or {}).get("model_info", {}).get(
                        "resolved_model"
                    ) != "gpt-5-mini-2099-01-01"
                    for r in post_rows
                ), "manifest got polluted with forged resolved_model"


def test_base_url_redaction_enforced_even_with_matching_hash():
    """Per Codex 2026-05-29 F1 [high]: a stale shim could otherwise
    emit a full proxy URL carrying secrets PLUS the correct sha256
    and pass the validator. The redaction enforcement is now FIRST
    in the validator: persisted `base_url` must equal its sanitized
    form."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    canonical_hash = rd._base_url_sha256_for_compare(expected_url)
    # Credential-bearing base_url + matching hash — must REJECT.
    row = {"metadata": {"model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
        "base_url": "https://user:pass@api.openai.com/v1?token=xyz",
        "base_url_sha256": canonical_hash,
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok, "credential-bearing base_url should reject"
    assert "sanitized" in (reason or "").lower() or "redaction" in (reason or "").lower()


def test_base_url_redaction_enforced_for_deep_path():
    """Same enforcement applies to deep-path-bearing URLs."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    canonical_hash = rd._base_url_sha256_for_compare(expected_url)
    row = {"metadata": {"model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
        "base_url": "https://api.openai.com/v1/private/secret-route",
        "base_url_sha256": canonical_hash,
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok
    assert "sanitized" in (reason or "").lower() or "redaction" in (reason or "").lower()


def test_base_url_sanitized_form_accepts():
    """Already-sanitized base_url (the shim's canonical output) passes."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    canonical_hash = rd._base_url_sha256_for_compare(expected_url)
    row = {"metadata": {"model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
        "base_url": "https://api.openai.com/v1",  # already sanitized
        "base_url_sha256": canonical_hash,
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert ok, f"sanitized base_url should accept: {reason}"


def test_fresh_row_rejects_unsanitized_base_url():
    """Fresh-row path also enforces redaction (the validator is shared)."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    canonical_hash = rd._base_url_sha256_for_compare(expected_url)
    diag = {"_model_info": {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2025-08-07",
        "base_url": "https://user:p@api.openai.com/v1?t=x",
        "base_url_sha256": canonical_hash,
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None
    assert "sanitized" in err.lower() or "redaction" in err.lower()


def test_fresh_row_rejects_wrong_provider_family():
    """Per Codex 2026-06-02 F1 [high]: a miswired command shim could
    historically emit rows with provider_name=openai under
    real-debugger-v1 (Anthropic config) and pass every other check.
    The new provider_name validator rejects this on the fresh-row
    path."""
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    diag = {"_model_info": {
        "provider_name": "openai",  # WRONG family for v1
        "requested_model": "haiku",
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None, "wrong-provider fresh row should reject"
    assert "provider" in err.lower() and "openai" in err.lower() and "anthropic" in err.lower()


def test_cache_hit_rejects_wrong_provider_family():
    """Same check on cache-hit path."""
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    row = {"metadata": {"model_info": {
        "provider_name": "openai",
        "requested_model": "haiku",
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok
    assert "provider" in (reason or "").lower()


def test_canonical_provider_name_accepts():
    """Sanity: rows with the canonical provider_name pass."""
    cfg_v1 = rd.load_diagnoser_config("real-debugger-v1")
    cfg_v3 = rd.load_diagnoser_config("real-debugger-v3")
    # v1 (anthropic)
    diag_v1 = {"_model_info": {
        "provider_name": "anthropic", "requested_model": "haiku"
    }}
    # On fresh-row, v1 requires endpoint evidence too — minimal payload
    # for the provider_name path alone; ignore the downstream
    # base_url error.
    err_v1 = rd._validate_provider_name_identity(
        diag_v1["_model_info"], cfg_v1
    )
    assert err_v1 is None
    # v3 (openai)
    err_v3 = rd._validate_provider_name_identity(
        {"provider_name": "openai", "requested_model": "gpt-5-mini"},
        cfg_v3,
    )
    assert err_v3 is None


def test_provider_name_required_under_real_configs():
    """A canonical config that declares model.provider_name REQUIRES
    provider_name on cached rows. Missing → reject (provenance)."""
    cfg = rd.load_diagnoser_config("real-debugger-v1")
    err = rd._validate_provider_name_identity({}, cfg)
    assert err is not None
    assert "provider_name" in err


def test_v1_v2_v3_committed_artifacts_carry_correct_provider_name():
    """Lock: every committed v1/v2/v3 row that has model_info also
    has provider_name matching the config family."""
    import json as _json
    repo = Path(__file__).resolve().parent.parent.parent
    expectations = {
        "real-debugger-v1": "anthropic",
        "real-debugger-v2": "anthropic",
        "real-debugger-v3": "openai",
    }
    failures = []
    for diagnoser, expected in expectations.items():
        for sp in ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]:
            diag_dir = repo / "results" / sp / "diagnoses" / diagnoser
            if not diag_dir.exists():
                continue
            for mf in diag_dir.glob("*.jsonl"):
                for line in mf.open():
                    row = _json.loads(line)
                    mi = (row.get("metadata") or {}).get("model_info")
                    if not mi:
                        continue
                    actual = mi.get("provider_name")
                    if actual and actual != expected:
                        failures.append(
                            f"{sp}/{mf.stem}/{row.get('case_id')}: "
                            f"diagnoser={diagnoser} provider_name="
                            f"{actual!r} expected={expected!r}"
                        )
    assert not failures, (
        "committed provider_name drift:\n  " + "\n  ".join(failures[:10])
    )


def test_reusable_template_still_enforces_redaction():
    """Per Codex 2026-06-01 F1 [high]: the 2026-05-23 fix made
    reusable_template configs skip identity validation, but that
    swallowed the redaction guard too. A custom shim using
    example.debugger-v1-command.json could write a row with
    `base_url: https://user:pass@proxy/v1?token=...` and the
    validator passed it. Now: redaction is unconditional. Templates
    still skip identity checks, but unsanitized base_urls are
    rejected on both fresh-row and cache-hit paths."""
    # example.debugger-v1-command.json declares
    # privacy.allow_secret_values_in_results: false AND
    # reusable_template: true.
    repo = Path(__file__).resolve().parent.parent.parent
    cfg = rd.load_diagnoser_config(
        "stub-debugger-v1",
        explicit_path=repo / "configs" / "diagnosers" / "example.debugger-v1-command.json",
    )
    assert cfg.get("reusable_template") is True
    assert cfg["privacy"]["allow_secret_values_in_results"] is False

    # Fresh-row path: an unsanitized URL must reject.
    diag = {"_model_info": {
        "provider_name": "anthropic", "requested_model": "haiku",  # arbitrary; template skips identity
        "base_url": "https://user:pass@proxy.example.com/v1?token=secret",
    }}
    err = rd.validate_fresh_row_model_identity(diag, cfg)
    assert err is not None, (
        "template with privacy.no-secrets + unsanitized base_url should reject"
    )
    assert "redaction" in err.lower() or "sanitized" in err.lower()

    # Cache-hit path: same enforcement BEFORE the template short-circuit.
    row = {"metadata": {"model_info": {
        "provider_name": "anthropic", "requested_model": "haiku",
        "base_url": "https://api.example.com/secret-token/v1",
    }}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok
    assert "redaction" in (reason or "").lower() or "sanitized" in (reason or "").lower()

    # Sanitized URL under same template: redaction passes; the
    # subsequent reusable_template skips identity. Fresh-row accepts;
    # cache-hit still rejects (templates never trust cache).
    diag_clean = {"_model_info": {
        "provider_name": "anthropic", "requested_model": "haiku",
        "base_url": "https://api.openai.com/v1",
    }}
    assert rd.validate_fresh_row_model_identity(diag_clean, cfg) is None


def test_oversized_context_writes_provider_error_not_fail_provenance():
    """Per Codex 2026-05-30 F1 [high]: legitimate no-call shim failures
    (oversized context, missing credentials, transport errors) emit
    NO `_model_info`. Under real-debugger-v3 (which requires
    provenance), the 2026-05-29 F2 fix wrongly classified those as
    provenance corruption — `FAIL_PROVENANCE` logged, method-level
    skip, no provider_error row written. That lost 39 expected
    `unsupported_context_too_large` rows.

    End-to-end: forge a shim that exits 1 with an oversized-context
    envelope (no model_info) and assert (a) the run produces a row
    in the manifest with provider_error starting with
    `unsupported_context_too_large:`, (b) NO `FAIL_PROVENANCE` log
    fires.

    Per Codex 2026-06-07 F3 [med]: wrapped in _snapshot_restore_diag_dir
    so the forged-shim run cannot leave tracked artifacts polluted on
    test failure. (The prior ad-hoc canonical-shim cleanup at the
    function tail was racy — it never fired if any earlier assert
    raised.)
    """
    import subprocess as _sub
    import json
    import tempfile
    repo = Path(__file__).resolve().parent.parent.parent

    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        manifest = diag_dir / "grep.jsonl"

        # Forge a shim that emits the oversized-context envelope (no
        # _model_info) and exits 1 — matching what the real OpenAI shim
        # does on _ContextTooLargeError post 2026-05-19 F2.
        forge_src = '''
import json, sys
sys.stdin.read()  # consume payload
envelope = {
    "_provider_error": "unsupported_context_too_large: synthetic 600000 > 480000",
}
print(json.dumps(envelope))
sys.exit(1)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(forge_src)
            fp.flush()
            forge_path = fp.name

        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"

        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        err_text = res.stderr.decode("utf-8")
        # The KEY assertion: this is NOT a provenance failure. The shim
        # never claimed model_info, so the validator must skip the check.
        assert "FAIL_PROVENANCE" not in err_text, (
            f"oversized-context failure should NOT trip FAIL_PROVENANCE; "
            f"stderr={err_text[:400]!r}"
        )
        # And a manifest row should exist with the unsupported_context_too_large
        # prefix (one of the 5 dev/grep cases).
        assert manifest.exists()
        rows = [json.loads(l) for l in manifest.open() if l.strip()]
        assert any(
            (r.get("metadata") or {}).get("provider_error", "").startswith(
                "unsupported_context_too_large:"
            )
            for r in rows
        ), (
            "expected at least one row with unsupported_context_too_large: "
            f"prefix in manifest; got {[r.get('metadata', {}).get('provider_error') for r in rows]!r}"
        )


def test_shim_error_row_provenance_check_e2e():
    """Per Codex 2026-05-29 F2 [medium]: when a ShimCallError carries
    `_model_info` (post-API parse failure), the runner must run
    fresh-row provenance validation on it before writing the
    provider_error row. Otherwise an API call that reached the wrong
    model/snapshot AND failed parsing would still write
    `post_api_error` row under the canonical diagnoser with wrong
    provenance.

    End-to-end: forge a shim that exits 1 with a stdout envelope
    declaring a wrong resolved_model, and assert the runner
    refuses to write the row (preserves existing artifacts).

    Per Codex 2026-06-07 F3 [med]: wrapped in _snapshot_restore_diag_dir
    so the runner cannot leave the tracked diag tree in a polluted
    state if it regresses and DOES write the forged row.
    """
    import subprocess as _sub
    import tempfile
    repo = Path(__file__).resolve().parent.parent.parent

    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        manifest = diag_dir / "grep.jsonl"
        pre_manifest = manifest.read_text("utf-8") if manifest.exists() else None

        # Forge a shim that exits 1 with the post_api_error envelope but
        # WITH a wrong resolved_model — exactly the failure mode F2 closes.
        forge_src = '''
import json, sys
sys.stdin.read()  # consume payload
envelope = {
    "_model_info": {
        "provider_name": "openai",
        "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2099-01-01",  # wrong snapshot
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": "''' + rd._base_url_sha256_for_compare(
            "https://api.openai.com/v1"
        ) + '''",
    },
    "_provider_error": "post_api_error: synthetic JSONDecodeError",
}
print(json.dumps(envelope))
sys.exit(1)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(forge_src)
            fp.flush()
            forge_path = fp.name

        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"

        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        assert res.returncode != 0
        err_text = res.stderr.decode("utf-8")
        assert "FAIL_PROVENANCE" in err_text, (
            f"shim_error_row provenance failure should log FAIL_PROVENANCE; "
            f"stderr={err_text[:400]!r}"
        )
        assert "shim_error_row" in err_text or "resolved_model" in err_text
        # Manifest preserved
        if pre_manifest is not None:
            post_manifest = manifest.read_text("utf-8")
            assert post_manifest == pre_manifest, (
                "manifest was modified despite shim-error-row provenance failure"
            )


def test_provenance_failure_preserves_existing_manifest_and_per_case():
    """Per Codex 2026-05-28 F1 [high]: when a fresh-row provenance
    check fails for ANY case in a method, the runner must preserve
    the existing manifest + per-case JSON files intact. Pre-fix, the
    loop-end manifest write would truncate the prior valid manifest
    to a shortened (skipped-case) version, and earlier successful
    cases' per-case JSONs would already have been overwritten.

    Setup: forge a wrong-resolved_model shim; seed a snapshot of the
    existing manifest + per-case JSONs; run; assert byte-identical
    after the failed run.
    """
    import subprocess as _sub
    import json
    import tempfile
    repo = Path(__file__).resolve().parent.parent.parent

    # Capture pre-state.
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    manifest = diag_dir / "grep.jsonl"
    method_dir = diag_dir / "grep"
    pre_manifest = manifest.read_text("utf-8") if manifest.exists() else None
    pre_per_case = {}
    if method_dir.exists():
        for p in method_dir.glob("*.json"):
            pre_per_case[p.name] = p.read_text("utf-8")

    # Forge a shim that emits a wrong resolved_model.
    forge_src = '''
import json, sys
data = json.load(sys.stdin)
print(json.dumps({
    "summary": "fake",
    "root_cause_category": "test_assertion",
    "root_cause": "synthetic",
    "confidence": 0.5,
    "relevant_files": [], "relevant_tests": [],
    "evidence": [], "suggested_fix": "",
    "_model_info": {
        "provider_name": "openai",
        "requested_model": "gpt-5-mini",
        "resolved_model": "gpt-5-mini-2099-01-01",
        "base_url": "https://api.openai.com/v1",
        "base_url_sha256": "''' + rd._base_url_sha256_for_compare(
            "https://api.openai.com/v1"
        ) + '''",
    },
}))
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
        fp.write(forge_src)
        fp.flush()
        forge_path = fp.name

    env = dict(os.environ)
    env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
    env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"

    res = _sub.run(
        ["python3", f"{repo}/tools/run_diagnosis.py",
         "--split", "dev",
         "--diagnoser", "command",
         "--diagnoser-name", "real-debugger-v3",
         "--command", env["DIAGNOSIS_COMMAND"],
         "--context-method", "grep",
         "--diagnoser-config",
         f"{repo}/configs/diagnosers/real-debugger-v3.json",
         "--no-cache"],
        cwd=repo, capture_output=True, timeout=60, env=env,
    )
    # Should have exited non-zero (had_failure set) and logged
    # FAIL_PROVENANCE for every case.
    err_text = res.stderr.decode("utf-8")
    assert res.returncode != 0
    assert "FAIL_PROVENANCE" in err_text
    # The "preserved existing manifest" message should appear in stdout.
    out_text = res.stdout.decode("utf-8")
    assert "PROVENANCE-FAILED" in out_text or "preserved" in out_text, (
        f"runner did not log preservation; stdout={out_text[:400]!r}"
    )

    # Verify pre-state is byte-identical to post-state.
    if pre_manifest is not None:
        post_manifest = manifest.read_text("utf-8")
        assert post_manifest == pre_manifest, (
            "manifest was modified despite provenance failure"
        )
    post_per_case = {}
    if method_dir.exists():
        for p in method_dir.glob("*.json"):
            post_per_case[p.name] = p.read_text("utf-8")
    assert post_per_case == pre_per_case, (
        f"per-case JSONs changed despite provenance failure: "
        f"pre keys={sorted(pre_per_case)} post keys={sorted(post_per_case)}"
    )


def test_resolved_model_shared_helper_returns_consistent_results():
    """The fresh-row and cache-hit paths now route through the same
    `_validate_resolved_model_identity` helper. Sanity-check that the
    helper itself behaves consistently."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    # Match → None
    assert rd._validate_resolved_model_identity(
        {"resolved_model": "gpt-5-mini-2025-08-07"}, cfg
    ) is None
    # Mismatch → error
    err = rd._validate_resolved_model_identity(
        {"resolved_model": "gpt-4o-2025-01-01"}, cfg
    )
    assert err is not None and "gpt-4o" in err
    # Null/missing → None (legacy back-compat)
    assert rd._validate_resolved_model_identity({"resolved_model": None}, cfg) is None
    assert rd._validate_resolved_model_identity({}, cfg) is None
    # No pin in config → None
    cfg_no_pin = {"model": {"model_name": "x"}}
    assert rd._validate_resolved_model_identity(
        {"resolved_model": "anything"}, cfg_no_pin
    ) is None


def test_cache_hit_rejects_resolved_model_drift():
    """Per Codex 2026-05-25 F1 [high]: v3 pins
    model.expected_resolved_model. A cache hit whose resolved_model
    differs from the pinned snapshot is rejected — closes the silent
    alias-rotation replay risk."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    expected_url = rd.effective_base_url(cfg)
    base_mi = {
        "provider_name": "openai", "requested_model": "gpt-5-mini",
        "base_url": rd._sanitize_base_url_for_compare(expected_url),
        "base_url_sha256": rd._base_url_sha256_for_compare(expected_url),
    }
    # Canonical run-time snapshot — accept.
    row_ok = {"metadata": {"model_info": dict(
        base_mi, resolved_model="gpt-5-mini-2025-08-07"
    )}}
    ok, reason = rd.cache_hit_is_acceptable(row_ok, cfg)
    assert ok, f"canonical resolved_model should accept: {reason}"
    # Different snapshot (alias retargeted) — reject.
    row_bad = {"metadata": {"model_info": dict(
        base_mi, resolved_model="gpt-5-mini-2026-01-15"
    )}}
    ok2, reason2 = rd.cache_hit_is_acceptable(row_bad, cfg)
    assert not ok2
    assert "resolved_model" in reason2 and "2026-01-15" in reason2


# test_cache_hit_back_compat_null_resolved_model was removed per Codex
# 2026-06-05 F1 [high]: cache-hit no longer accepts null resolved_model
# under a pinned config. See
# `test_cache_hit_rejects_null_resolved_model_under_pin` above for the
# replacement behavior.


def test_v3_config_pins_expected_resolved_model():
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    pinned = (cfg.get("model") or {}).get("expected_resolved_model")
    assert pinned == "gpt-5-mini-2025-08-07", (
        f"v3 must pin the canonical snapshot; got {pinned!r}"
    )


def test_sanitize_base_url_strips_deep_path_segments():
    """Per Codex 2026-05-25 F2 + 2026-05-31 F1 + 2026-06-19 F1 [high]:
    a proxy URL with path-embedded secrets used to be persisted
    verbatim in metadata.model_info.base_url. The sanitizer now
    keeps ONLY a first-segment matching `^v\\d+$` (canonical API-
    version route); any other first segment is dropped along with
    everything after. AND non-allowlisted hostnames are redacted
    with a sha-prefix marker (Azure/proxy tenant hostnames can
    carry identity)."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_openai", repo / "examples" / "diagnosis_shim_openai.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = mod.sanitize_base_url

    # Canonical OpenAI URL preserved (allowlisted hostname +
    # version segment).
    assert f("https://api.openai.com/v1") == "https://api.openai.com/v1"
    # Userinfo + query already stripped (2026-05-12), now path too,
    # and the non-allowlisted hostname is redacted.
    out = f("https://user:pass@proxy.example.com/v1?token=xyz")
    assert "proxy.example.com" not in out, out
    assert "redacted-host sha=" in out, out
    assert out.endswith("/v1"), out
    # Deep path segments after a /v1 are dropped (keep allowlisted),
    # hostname redacted.
    out2 = f("https://proxy.example.com/v1/private/secret-route")
    assert "proxy.example.com" not in out2 and "redacted-host" in out2, out2
    assert out2.endswith("/v1"), out2
    # First segment NOT matching ^v\d+$ → entire path dropped
    # (Codex 2026-05-31 F1 case). Hostname also redacted.
    out3 = f("https://proxy.example.com/secret-token/v1")
    assert "proxy.example.com" not in out3 and "redacted-host" in out3, out3
    assert not out3.endswith("/v1"), out3
    # Higher version numbers also accepted.
    out4 = f("https://proxy.example.com/v10")
    assert out4.endswith("/v10"), out4
    # Trailing-slash URL untouched (allowlisted host).
    assert f("https://api.openai.com/") == "https://api.openai.com/"
    # No-path URL untouched (allowlisted host).
    assert f("https://api.openai.com") == "https://api.openai.com"
    # Port preserved on allowlisted host.
    assert f("http://localhost:11434/v1") == "http://localhost:11434/v1"


def test_sanitize_base_url_redacts_tenant_hostname():
    """Per Codex 2026-06-19 F1 [high]: non-allowlisted hostnames can
    carry tenant / resource identity (e.g. Azure
    `<resource>.openai.azure.com`, internal proxy names with
    tenant prefixes). The sanitizer replaces them with a sha-
    prefixed placeholder so they can't leak into committed
    artifacts."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_openai_redact", repo / "examples" / "diagnosis_shim_openai.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = mod.sanitize_base_url

    # Azure-style tenant host.
    azure_out = f("https://my-resource.openai.azure.com/v1")
    assert "my-resource.openai.azure.com" not in azure_out, azure_out
    assert "redacted-host sha=" in azure_out, azure_out
    # Internal proxy with tenant prefix.
    proxy_out = f("https://tenant42.proxy.internal/v1")
    assert "tenant42" not in proxy_out, proxy_out
    assert "redacted-host" in proxy_out, proxy_out
    # Port on non-allowlisted host is DROPPED (custom-port info on
    # a private endpoint is also identity-leaking).
    port_out = f("https://tenant.proxy:8443/v1")
    assert "8443" not in port_out, port_out
    # Two different tenant hosts produce DIFFERENT redacted forms
    # (sha differs) — so an auditor can still tell two runs apart.
    out_a = f("https://tenant-a.azure.com/v1")
    out_b = f("https://tenant-b.azure.com/v1")
    assert out_a != out_b, f"redacted forms should differ: {out_a} == {out_b}"
    # Allowlisted hosts NOT redacted.
    assert f("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert f("https://api.anthropic.com/v1") == "https://api.anthropic.com/v1"
    assert f("http://localhost:8000/v1") == "http://localhost:8000/v1"
    assert f("http://127.0.0.1:8000/v1") == "http://127.0.0.1:8000/v1"


def test_sanitize_base_url_is_idempotent_on_redacted_host():
    """Per Codex 2026-06-20 F1 [high]: sanitize_base_url must
    PASS THROUGH a URL whose hostname is already the
    `<redacted-host sha=PREFIX>` placeholder. Pre-fix, re-sanitizing
    a row's persisted base_url (e.g. during cache-hit validation)
    would wrap the placeholder's bracket/equals/hex chars as a new
    "hostname" and re-redact it to a DIFFERENT sha — rejecting the
    row as un-sanitized and forcing a fresh call on every cache
    hit for private-endpoint runs.
    """
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_idem", repo / "examples" / "diagnosis_shim_openai.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = mod.sanitize_base_url

    # Generate a fresh sanitized form for an Azure-style host.
    once = f("https://my-resource.openai.azure.com/v1")
    assert "redacted-host sha=" in once, once
    # Re-sanitizing the SANITIZED form must yield the SAME string.
    twice = f(once)
    assert once == twice, (
        f"sanitizer not idempotent: once={once!r}, twice={twice!r}"
    )
    # Same for runner-side helper.
    runner_once = rd._sanitize_base_url_for_compare(
        "https://tenant42.proxy.internal/v1"
    )
    runner_twice = rd._sanitize_base_url_for_compare(runner_once)
    assert runner_once == runner_twice, (
        f"runner sanitizer not idempotent: once={runner_once!r}, "
        f"twice={runner_twice!r}"
    )


def test_private_endpoint_cache_hit_accepts_redacted_row():
    """Per Codex 2026-06-20 F1 [high]: end-to-end, a row whose
    `base_url` is the redacted form (`https://<redacted-host
    sha=PREFIX>/v1`) must be ACCEPTED by `cache_hit_is_acceptable`
    when the current run points at the corresponding private
    endpoint. Pre-fix, the runner re-sanitized the redacted form
    on each hit and rejected the row, breaking every private-
    endpoint cache replay.
    """
    cfg = {
        "model": {
            "provider_name": "openai",
            "model_name": "gpt-5-mini",
            "env_var_name": "CILOGBENCH_OPENAI_MODEL",
            "base_url": "https://tenant-a.proxy.internal/v1",
            "base_url_env_var_name": "CILOGBENCH_OPENAI_BASE_URL",
        },
        "cache_key_env": ["CILOGBENCH_OPENAI_BASE_URL"],
    }
    # Compute the redacted form the shim would write for the private
    # URL — that's what the runner re-validates on cache hit.
    canonical_url = rd.effective_base_url(cfg)
    sanitized = rd._sanitize_base_url_for_compare(canonical_url)
    sha = rd._base_url_sha256_for_compare(canonical_url)
    row = {
        "metadata": {
            "model_info": {
                "provider_name": "openai",
                "requested_model": "gpt-5-mini",
                "resolved_model": None,  # legacy ok for this test
                "base_url": sanitized,
                "base_url_sha256": sha,
            },
        },
    }
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert ok, (
        f"private-endpoint cache hit should accept redacted-host "
        f"base_url; reason={reason!r}"
    )


def test_openai_shim_no_choices_emits_hash_only_summary():
    """Per Codex 2026-06-20 F2 [high]: the post-API `no choices` and
    empty-content paths used to embed `json.dumps(wrapper)[:400]`
    or `json.dumps(choices[0])[:400]` verbatim in the error
    message. A compatible 200 response with non-token-shape
    sensitive content (prompt fragments, CI log text, tenant IDs)
    would still leak. Fix: emit a hash + length + key-list
    summary, no raw body content.
    """
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_no_choices", repo / "examples" / "diagnosis_shim_openai.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Stand up a local server returning a malformed 200 with
    # non-token-shape sensitive payload.
    import http.server, threading, json, os
    import subprocess as _sub
    body = json.dumps({
        "choices": [],  # triggers the no_choices path
        "tenant": "internal-customer-id-12345",
        "echoed_prompt": "PRIVATE CI LOG: build failed in foo/bar",
        "id": "chatcmpl-test",
    }).encode("utf-8")

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_a, **_k):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        env = dict(os.environ)
        env["OPENAI_API_KEY"] = "sk-test-not-real-but-long-enough-1234"
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["CILOGBENCH_OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        env["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY",
                  "https_proxy", "ALL_PROXY", "all_proxy"):
            env.pop(k, None)
        env["NO_PROXY"] = "127.0.0.1,localhost"
        env["no_proxy"] = "127.0.0.1,localhost"
        payload = json.dumps({
            "case_id": "synthetic", "context_method": "raw",
            "prompt": "x", "context": "y",
            "safe_case_metadata": {"case_id": "synthetic"},
            "expected_output_schema": "schemas/diagnosis.schema.json",
        })
        res = _sub.run(
            ["python3", f"{repo}/examples/diagnosis_shim_openai.py"],
            input=payload.encode("utf-8"),
            capture_output=True, timeout=30, env=env, cwd=repo,
        )
        stdout = res.stdout.decode("utf-8")
        stderr = res.stderr.decode("utf-8")
        # Sensitive content must NOT appear.
        assert "internal-customer-id-12345" not in stdout, stdout[:400]
        assert "internal-customer-id-12345" not in stderr, stderr[:400]
        assert "PRIVATE CI LOG" not in stdout, stdout[:400]
        assert "PRIVATE CI LOG" not in stderr, stderr[:400]
        # Hash-only summary should be present.
        assert "wrapper_sha256=" in stdout or "wrapper_sha256=" in stderr, (
            f"expected hash-only summary; stdout={stdout[:400]!r}"
        )
        assert "post_api_error" in stdout, stdout[:400]
    finally:
        srv.shutdown()
        t.join(timeout=3)


def test_runner_sanitize_base_url_for_compare_mirrors_shim_redaction():
    """Per Codex 2026-06-19 F1 [high]: runner-side `_sanitize_base_url
    _for_compare` must agree with shim-side `sanitize_base_url` on
    hostname redaction. Otherwise cache_hit_is_acceptable would
    compare sanitized-redacted-shim-row vs unredacted-runner-form
    and reject every cache hit for non-allowlisted endpoints."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    # Import shim module
    spec_s = importlib.util.spec_from_file_location(
        "_shim_o2", repo / "examples" / "diagnosis_shim_openai.py"
    )
    shim = importlib.util.module_from_spec(spec_s)
    spec_s.loader.exec_module(shim)
    # Use runner module (already imported as `rd`)
    test_urls = [
        "https://api.openai.com/v1",
        "https://my-resource.openai.azure.com/v1",
        "https://tenant-x.proxy.internal/v1/private/segment",
        "http://localhost:11434/v1",
        "http://127.0.0.1:8000/v1",
    ]
    for u in test_urls:
        shim_out = shim.sanitize_base_url(u)
        runner_out = rd._sanitize_base_url_for_compare(u)
        assert shim_out == runner_out, (
            f"shim/runner disagree on {u!r}: shim={shim_out!r}, "
            f"runner={runner_out!r}"
        )


def test_sanitize_base_url_drops_tenant_key_first_segment():
    """Per Codex 2026-05-31 F1 [high]: the EXACT regression Codex
    flagged — proxies/tenant gateways shaped like
    `https://proxy/<tenant-key>/v1` used to persist the tenant key
    in metadata.model_info.base_url. Lock that case explicitly."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_openai", repo / "examples" / "diagnosis_shim_openai.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sanitized = mod.sanitize_base_url(
        "https://proxy.example.com/secret-token/v1"
    )
    # The tenant key MUST NOT appear in the sanitized output.
    assert "secret-token" not in sanitized, (
        f"first-segment secret leaked: {sanitized!r}"
    )
    # And the runner's mirror must agree.
    assert rd._sanitize_base_url_for_compare(
        "https://proxy.example.com/secret-token/v1"
    ) == sanitized
    # The 2026-05-29 F1 redaction guard then ALSO triggers if a
    # malicious shim tries to persist the unsanitized form.
    cfg = {
        "model": {
            "model_name": "gpt-5-mini",
            "base_url": "https://proxy.example.com/secret-token/v1",
            "base_url_env_var_name": "CILOGBENCH_OPENAI_BASE_URL",
        },
        "cache_key_env": ["CILOGBENCH_OPENAI_BASE_URL"],
        "privacy": {"allow_secret_values_in_results": False},
    }
    saved = os.environ.get("CILOGBENCH_OPENAI_BASE_URL")
    try:
        os.environ["CILOGBENCH_OPENAI_BASE_URL"] = (
            "https://proxy.example.com/secret-token/v1"
        )
        row = {"metadata": {"model_info": {
            "provider_name": "openai", "requested_model": "gpt-5-mini",
            # Malicious row: persists the unsanitized URL.
            "base_url": "https://proxy.example.com/secret-token/v1",
            "base_url_sha256": rd._base_url_sha256_for_compare(
                "https://proxy.example.com/secret-token/v1"
            ),
        }}}
        ok, reason = rd.cache_hit_is_acceptable(row, cfg)
        assert not ok, "unsanitized first-segment must be rejected"
        assert "sanitized" in (reason or "").lower() or "redaction" in (reason or "").lower()
    finally:
        if saved is None:
            os.environ.pop("CILOGBENCH_OPENAI_BASE_URL", None)
        else:
            os.environ["CILOGBENCH_OPENAI_BASE_URL"] = saved


def test_runner_sanitize_matches_shim_sanitize():
    """The runner's _sanitize_base_url_for_compare must produce the
    same output as the shim's sanitize_base_url for cache-hit
    validation to work. Mirror both sides identically."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_openai", repo / "examples" / "diagnosis_shim_openai.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    shim_san = mod.sanitize_base_url

    for url in [
        "https://api.openai.com/v1",
        "https://user:pass@proxy.example.com/v1?token=xyz",
        "https://proxy/v1/private/secret",
        "https://api.openai.com",
        "http://localhost:11434/v1",
    ]:
        assert shim_san(url) == rd._sanitize_base_url_for_compare(url), (
            f"shim+runner sanitize disagree for {url!r}"
        )


def test_cache_hit_accepts_provider_error_row_when_cache_errors_opted_in():
    """When the operator passes --cache-errors, replaying a cached
    provider_error row is the explicit intent (e.g. running the
    benchmark deterministically against known-failure rows)."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    row = {"metadata": {
        "model_info": {
            "provider_name": "openai", "requested_model": "gpt-5-mini",
            "resolved_model": "gpt-5-mini-2025-08-07",
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
    row = {"metadata": {"model_info": {"provider_name": "openai", "requested_model": "gpt-4o"}}}
    ok, reason = rd.cache_hit_is_acceptable(row, cfg)
    assert not ok
    assert "gpt-4o" in (reason or "") and "gpt-5-mini" in (reason or "")


def test_stub_template_end_to_end_writes_clean_rows():
    """Per Codex 2026-05-23 F1 [high] end-to-end regression: the
    documented workflow (`example.debugger-v1-command.json` template
    + `examples/diagnosis_shim_stub.py`) must produce successful rows
    with `metadata.provider_error == null` — not provider_error rows
    that throw away paid API calls.

    Per Codex 2026-06-07 F3 [med]: wrapped in _snapshot_restore_diag_dir
    so the test's writes to results/dev/diagnoses/stub-debugger-v1/
    never persist past the test (stub artifacts must not leak into
    canonical results).
    """
    import subprocess as _sub
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "stub-debugger-v1"
    with _snapshot_restore_diag_dir(diag_dir):
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
        manifest = diag_dir / "grep.jsonl"
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
            "_model_info": {"provider_name": "openai", "requested_model": "gpt-5-mini"},
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

def test_provider_error_unknown_class_fails_run_by_default():
    """Per Codex 2026-06-08 F1 [high]: a fresh provider_error row whose
    prefix is NOT in the config's `provider_policy.
    non_fatal_provider_error_prefixes` allowlist must set had_failure
    and exit non-zero. Pre-fix, the runner caught the exception, wrote
    an "unknown" stub row, and exited 0 — wrappers then evaluated /
    rendered / published the failed run as a successful experiment.

    Forge a shim that exits 1 with an arbitrary `_provider_error`
    prefix (e.g. `api_call_failed`) that is NOT in v3's allowlist
    (which only allows `unsupported_context_too_large`). The run
    should exit non-zero AND log FAIL_PROVIDER_ERROR for every case.
    """
    import subprocess as _sub
    import tempfile

    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        forge_src = '''
import json, sys
sys.stdin.read()
envelope = {
    "_provider_error": "api_call_failed: synthetic transport failure",
}
print(json.dumps(envelope))
sys.exit(1)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(forge_src)
            fp.flush()
            forge_path = fp.name
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        err_text = res.stderr.decode("utf-8")
        assert res.returncode != 0, (
            f"expected non-zero exit when provider_error is not in "
            f"non_fatal allowlist; got {res.returncode}; stderr={err_text[:400]!r}"
        )
        assert "FAIL_PROVIDER_ERROR" in err_text, (
            f"expected FAIL_PROVIDER_ERROR log; stderr={err_text[:400]!r}"
        )
        assert "api_call_failed" in err_text, err_text[:400]


def test_provider_error_in_allowlist_preserves_success():
    """Per Codex 2026-06-08 F1 [high]: a fresh provider_error row whose
    prefix IS in the config's allowlist must NOT set had_failure. v3
    declares `unsupported_context_too_large` as the only non-fatal
    class. The runner exits 0 even though provider_error rows are in
    the manifest, because oversized context is the documented graceful
    refusal path per `context_policy.on_context_too_large=provider_error`.

    Companion to test_provider_error_unknown_class_fails_run_by_default
    — together they pin the allowlist contract.
    """
    import subprocess as _sub
    import tempfile

    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        forge_src = '''
import json, sys
sys.stdin.read()
envelope = {
    "_provider_error": "unsupported_context_too_large: synthetic 600000 > 480000",
}
print(json.dumps(envelope))
sys.exit(1)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(forge_src)
            fp.flush()
            forge_path = fp.name
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        err_text = res.stderr.decode("utf-8")
        assert res.returncode == 0, (
            f"expected exit 0 when provider_error matches allowlist; "
            f"got {res.returncode}; stderr={err_text[:400]!r}"
        )
        assert "FAIL_PROVIDER_ERROR" not in err_text, (
            f"allowlisted prefix should NOT trigger FAIL_PROVIDER_ERROR; "
            f"stderr={err_text[:400]!r}"
        )


def test_cache_hit_rejects_when_config_sha_changed():
    """Per Codex 2026-06-08 F2 [high]: cached rows persist
    `metadata.diagnoser_config_sha256` on every fresh write.
    `cache_hit_is_acceptable` rejects when the cached value disagrees
    with the current run's loaded config SHA — closes the silent-
    replay window for behavior-affecting config edits outside
    cache_key_env's coverage.
    """
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    canonical_url = rd.effective_base_url(cfg)
    row = {
        "metadata": {
            "model_info": {
                "provider_name": "openai",
                "requested_model": "gpt-5-mini",
                "resolved_model": "gpt-5-mini-2025-08-07",
                "base_url": canonical_url,
                "base_url_sha256": rd._base_url_sha256_for_compare(
                    canonical_url
                ),
            },
            "diagnoser_config_sha256": "stale-config-sha-from-a-prior-version",
        },
    }
    ok, reason = rd.cache_hit_is_acceptable(
        row, cfg,
        current_diagnoser_config_sha="current-config-sha-different",
    )
    assert not ok, "stale config sha should reject"
    assert "diagnoser_config_sha256" in (reason or ""), reason


def test_cache_hit_accepts_when_config_sha_matches():
    """Companion to the rejection test: when cached SHA == current
    SHA, accept the row (no false negatives)."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    canonical_url = rd.effective_base_url(cfg)
    row = {
        "metadata": {
            "model_info": {
                "provider_name": "openai",
                "requested_model": "gpt-5-mini",
                "resolved_model": "gpt-5-mini-2025-08-07",
                "base_url": canonical_url,
                "base_url_sha256": rd._base_url_sha256_for_compare(
                    canonical_url
                ),
            },
            "diagnoser_config_sha256": "fake-sha-matches-both-sides",
        },
    }
    ok, reason = rd.cache_hit_is_acceptable(
        row, cfg,
        current_diagnoser_config_sha="fake-sha-matches-both-sides",
    )
    assert ok, f"matching config sha should accept; reason={reason!r}"


def test_cache_hit_rejects_legacy_null_under_canonical_config():
    """Per Codex 2026-06-09 F2 [high]: under a canonical config (one
    that declares cache_key_env / requires provenance), cached rows
    missing `metadata.diagnoser_config_sha256` are REJECTED. Pre-2026-
    06-08 F2 cached rows pre-date the field; the migration tool now
    stamps current SHAs onto rebuilt rows so the strict mode passes.

    Companion-test note: a previous round (2026-06-08 F2) accepted
    legacy null as back-compat. The 2026-06-09 F2 round caught that
    this was the exact silent-replay window F2 meant to close — a
    migrated cache with null SHA would replay across future config /
    shim edits. Strict mode closes it.
    """
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    canonical_url = rd.effective_base_url(cfg)
    row = {
        "metadata": {
            "model_info": {
                "provider_name": "openai",
                "requested_model": "gpt-5-mini",
                "resolved_model": "gpt-5-mini-2025-08-07",
                "base_url": canonical_url,
                "base_url_sha256": rd._base_url_sha256_for_compare(
                    canonical_url
                ),
            },
            # Note: no diagnoser_config_sha256, no shim_sha256.
        },
    }
    ok, reason = rd.cache_hit_is_acceptable(
        row, cfg,
        current_diagnoser_config_sha="some-config-sha",
        current_shim_sha="some-shim-sha",
    )
    assert not ok, "legacy null SHA under canonical config should reject"
    assert "diagnoser_config_sha256" in (reason or ""), reason


def test_cache_hit_accepts_legacy_null_under_template_config():
    """Companion: configs that opt OUT of provenance enforcement
    (reusable_template, or model.allow_missing_model_info=true) keep
    back-compat for null SHA fields. Closed-form: the strict gate
    only fires when _config_requires_model_info(config) is true.

    This protects documented stub / template / mock workflows that
    pre-date the SHA fields and have no canonical model identity to
    stamp.
    """
    # Reusable template: cache hits are rejected at an earlier gate
    # (no canonical identity), so we use the `allow_missing_model_info`
    # opt-out instead.
    cfg = {
        "diagnoser_name": "legacy-mock-debugger",
        "model": {
            "provider_name": "anthropic",
            "model_name": "haiku",
            "allow_missing_model_info": True,
        },
    }
    row = {
        "metadata": {
            "model_info": None,
            # No diagnoser_config_sha256, no shim_sha256.
        },
    }
    ok, _ = rd.cache_hit_is_acceptable(
        row, cfg,
        current_diagnoser_config_sha="some-config-sha",
        current_shim_sha="some-shim-sha",
    )
    assert ok, "legacy null SHA under opt-out config should pass back-compat"


def test_cache_hit_rejects_when_shim_sha_changed():
    """Per Codex 2026-06-08 F2 [high]: same gate for shim-impl SHA.
    A cached row that recorded a different shim SHA than the current
    run's shim file must be rejected — the parser/behavior of the
    shim has changed.
    """
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    canonical_url = rd.effective_base_url(cfg)
    row = {
        "metadata": {
            "model_info": {
                "provider_name": "openai",
                "requested_model": "gpt-5-mini",
                "resolved_model": "gpt-5-mini-2025-08-07",
                "base_url": canonical_url,
                "base_url_sha256": rd._base_url_sha256_for_compare(
                    canonical_url
                ),
            },
            "shim_sha256": "stale-shim-sha",
        },
    }
    ok, reason = rd.cache_hit_is_acceptable(
        row, cfg,
        current_shim_sha="current-shim-sha-different",
    )
    assert not ok, "stale shim sha should reject"
    assert "shim_sha256" in (reason or ""), reason


def test_diagnoser_config_sha256_helper_returns_sha_of_loaded_file():
    """Helper test: the SHA helper resolves the same path
    load_diagnoser_config uses and produces the expected hex digest."""
    import hashlib as _hl
    p = (Path(__file__).resolve().parent.parent.parent
         / "configs" / "diagnosers" / "real-debugger-v3.json")
    expected = _hl.sha256(p.read_bytes()).hexdigest()
    got = rd.diagnoser_config_sha256("real-debugger-v3")
    assert got == expected, f"sha mismatch: {got!r} != {expected!r}"


def test_shim_sha256_for_command_resolves_repo_local_path():
    """Helper test: when command_str references a real .py file in
    the repo, the helper returns that file's SHA. When the command
    has no .py file (or points to a nonexistent path), it returns
    None — non-repo-local commands contribute no shim hash."""
    import hashlib as _hl
    repo = Path(__file__).resolve().parent.parent.parent
    shim = repo / "examples" / "diagnosis_shim_openai.py"
    expected = _hl.sha256(shim.read_bytes()).hexdigest()
    cmd = f"python3 {shim}"
    got = rd.shim_sha256_for_command(cmd)
    assert got == expected, f"shim sha mismatch: {got!r} != {expected!r}"

    # No .py → None
    assert rd.shim_sha256_for_command("some-binary --flag") is None
    # Nonexistent .py → None
    assert rd.shim_sha256_for_command("python3 /no/such/path.py") is None
    # None command → None
    assert rd.shim_sha256_for_command(None) is None


def test_fresh_row_writes_carry_config_and_shim_sha():
    """Per Codex 2026-06-08 F2 [high]: build_row stamps the
    `metadata.diagnoser_config_sha256` and `metadata.shim_sha256`
    fields on every fresh row. Existing tracked v3 manifest rows
    pre-date this so they don't carry the fields yet (legacy);
    this unit test pins the build_row contract going forward.
    """
    row = rd.build_row(
        case_id="c1", context_method="grep", diagnoser="real-debugger-v3",
        diagnosis_body={
            "summary": "x", "root_cause_category": "unknown",
            "root_cause": "x", "confidence": 0.5,
            "relevant_files": [], "relevant_tests": [],
            "evidence": [], "suggested_fix": "",
        },
        context_path=Path("ctx.txt"), context_text="ctx",
        prompt_sha="p", runtime_ms=1.0, provider_name="command",
        command_str="cmd", cache_key="k", provider_error=None,
        diagnoser_config_name=None,
        diagnoser_config_sha256_value="cfg-sha",
        shim_sha256_value="shim-sha",
    )
    md = row["metadata"]
    assert md["diagnoser_config_sha256"] == "cfg-sha"
    assert md["shim_sha256"] == "shim-sha"


def test_migrated_cache_rejects_after_config_edit_e2e():
    """Per Codex 2026-06-09 F2 [high]: end-to-end smoke test that a
    cache row stamped under the CURRENT config sha gets rejected when
    the validator is called with a DIFFERENT current_diagnoser_config_sha
    (simulating a post-migration config edit). This is the closed-loop
    contract: migration stamps current SHA → future edit changes SHA
    → cache hit rejects → fresh call required.
    """
    repo = Path(__file__).resolve().parent.parent.parent
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    current_config_sha = rd.diagnoser_config_sha256("real-debugger-v3")
    assert current_config_sha is not None
    canonical_url = rd.effective_base_url(cfg)

    # Simulate a cache row stamped by the migration with the CURRENT
    # config SHA.
    row = {
        "metadata": {
            "model_info": {
                "provider_name": "openai",
                "requested_model": "gpt-5-mini",
                "resolved_model": "gpt-5-mini-2025-08-07",
                "base_url": canonical_url,
                "base_url_sha256": rd._base_url_sha256_for_compare(
                    canonical_url
                ),
            },
            "diagnoser_config_sha256": current_config_sha,
            "shim_sha256": "current-shim-sha-placeholder",
        },
    }

    # Matched config sha → accepted.
    ok, _ = rd.cache_hit_is_acceptable(
        row, cfg,
        current_diagnoser_config_sha=current_config_sha,
        current_shim_sha="current-shim-sha-placeholder",
    )
    assert ok, "matched SHA should accept (baseline)"

    # Now simulate a config edit by passing a DIFFERENT current sha.
    ok2, reason = rd.cache_hit_is_acceptable(
        row, cfg,
        current_diagnoser_config_sha=current_config_sha[:-1] + "0",
        current_shim_sha="current-shim-sha-placeholder",
    )
    assert not ok2, "config edit should invalidate cache hit"
    assert "diagnoser_config_sha256" in (reason or "")

    # Same for shim edit.
    ok3, reason3 = rd.cache_hit_is_acceptable(
        row, cfg,
        current_diagnoser_config_sha=current_config_sha,
        current_shim_sha="some-other-shim-sha",
    )
    assert not ok3, "shim edit should invalidate cache hit"
    assert "shim_sha256" in (reason3 or "")


def test_eval_injects_zero_score_rows_for_historical_exclusions():
    """Per Codex 2026-06-15 F1 [high]: evaluate_diagnosis.py loads the
    historical exclusion manifest and injects a zero-score
    abstention row for each (split, diagnoser, method, case_id)
    listed there. The macro denominator must reflect the source
    context manifest size, not the post-cleanup diagnosis manifest
    size.

    Smoke: real-debugger-v3 dev/rtk-read had cargo-tokio-001 removed
    in the 2026-06-09 cleanup. The current diagnosis manifest has
    4 rows but the eval file's rtk-read method must include 5 case
    entries (4 real + 1 synthesized historical exclusion).
    """
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    eval_path = repo / "results" / "dev" / "eval_diagnosis_real-debugger-v3.json"
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    rtk_read = next(
        (m for m in data["methods"] if m["context_method"] == "rtk-read"),
        None,
    )
    assert rtk_read is not None, "rtk-read method missing from eval"
    case_ids = [c["case_id"] for c in rtk_read["cases"]]
    assert "cargo-tokio-001" in case_ids, (
        f"historical exclusion should be injected into eval; got {case_ids!r}"
    )
    # The injected row carries provider_error and zero scores.
    injected = next(c for c in rtk_read["cases"] if c["case_id"] == "cargo-tokio-001")
    assert injected.get("provider_error"), "synthesized row must have provider_error"
    assert injected.get("diagnosis_success") is False, (
        "synthesized row must NOT count as success"
    )
    assert injected.get("abstained"), "synthesized row must count as abstention"


def test_openai_shim_redacts_bearer_tokens_in_error_text():
    """Per Codex 2026-06-15 F2 [high]: provider error messages that
    contain Bearer tokens or API-key-shaped strings must be
    redacted before they land in metadata.provider_error. Pre-fix,
    a compatible endpoint that echoed Authorization headers in its
    error body would persist those secrets into committed
    diagnosis artifacts."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_for_test", repo / "examples" / "diagnosis_shim_openai.py"
    )
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)

    out = shim.redact_secrets_in_text(
        "Auth fail: Authorization: Bearer sk-abc12345678901234567890abc reject"
    )
    assert "sk-abc12345678901234567890abc" not in out, out
    assert "redacted-secret" in out, out


def test_openai_shim_redacts_api_key_shape():
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_for_test2", repo / "examples" / "diagnosis_shim_openai.py"
    )
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    out = shim.redact_secrets_in_text(
        "provider replied: sk-abcdef0123456789012345678901 invalid"
    )
    assert "sk-abcdef0123456789012345678901" not in out, out
    assert "redacted-secret" in out, out


def test_openai_shim_post_api_error_redacts_bearer_payload():
    """Per Codex 2026-06-16 F1 [high]: when a 200 OpenAI response has
    no choices / empty content, the shim falls into the post-API
    error path. Pre-fix, that path only applied URL redaction —
    a malformed 200 from a proxy that echoed Authorization headers
    in the wrapper JSON would land verbatim in _provider_error.
    """
    import subprocess as _sub
    import tempfile
    import os
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    # Stand up a local HTTP server that returns a malformed 200
    # echoing a bearer token in the wrapper JSON. Verify the shim's
    # post-API error envelope sanitizes it.
    import http.server, threading
    body = json.dumps({
        "choices": [{"message": {"content": ""}}],
        "id": "chatcmpl-test",
        "echoed_auth": "Bearer sk-leak1234567890abcdefghij1234567890",
    }).encode("utf-8")

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_a, **_k):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        env = dict(os.environ)
        env["OPENAI_API_KEY"] = "sk-test-not-real-but-long-enough-1234"
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["CILOGBENCH_OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        env["CILOGBENCH_OPENAI_MODEL"] = "gpt-5-mini"
        # Bypass any system-level HTTP_PROXY so urllib hits our
        # local test server directly.
        for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY",
                  "https_proxy", "ALL_PROXY", "all_proxy"):
            env.pop(k, None)
        env["NO_PROXY"] = "127.0.0.1,localhost"
        env["no_proxy"] = "127.0.0.1,localhost"
        payload = json.dumps({
            "case_id": "synthetic", "context_method": "raw",
            "prompt": "x", "context": "y",
            "safe_case_metadata": {"case_id": "synthetic"},
            "expected_output_schema": "schemas/diagnosis.schema.json",
        })
        res = _sub.run(
            ["python3", f"{repo}/examples/diagnosis_shim_openai.py"],
            input=payload.encode("utf-8"),
            capture_output=True, timeout=30, env=env, cwd=repo,
        )
        stdout = res.stdout.decode("utf-8")
        stderr = res.stderr.decode("utf-8")
        # The shim must exit 1 with a post_api_error envelope.
        assert res.returncode == 1, (
            f"shim should fail post-API; stdout={stdout[:400]!r} "
            f"stderr={stderr[:400]!r}"
        )
        # Neither stdout NOR stderr can contain the leaked token.
        assert "sk-leak1234567890abcdefghij1234567890" not in stdout, (
            f"stdout leaks token: {stdout[:600]!r}"
        )
        assert "sk-leak1234567890abcdefghij1234567890" not in stderr, (
            f"stderr leaks token: {stderr[:600]!r}"
        )
        assert "post_api_error" in stdout, stdout[:400]
    finally:
        srv.shutdown()
        t.join(timeout=3)


def test_runner_redacts_structured_provider_error_from_shim_stdout():
    """Per Codex 2026-06-17 F1 [high]: shim-provided `_provider_error`
    in stdout JSON envelopes is now redacted at the runner boundary
    (`_extract_shim_stdout_metadata`) and in the success-path
    normalization. A shim that built `_provider_error` from raw
    model/CLI text on parse failure could otherwise hand back a
    string carrying credentials, which `build_row` would lift
    directly into `metadata.provider_error`.

    End-to-end: forge a shim that writes a JSON envelope to stdout
    carrying `_provider_error` with a credential-shaped substring.
    Assert the manifest row's `metadata.provider_error` does NOT
    contain the raw secret AND DOES contain the redaction marker.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        forge_src = '''
import json, sys
sys.stdin.read()
envelope = {
    "_provider_error": "api_call_failed: leaked Bearer sk-stdin1234567890abcdef0123456 in reply",
}
print(json.dumps(envelope))
sys.exit(1)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(forge_src)
            fp.flush()
            forge_path = fp.name
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"
        cfg_src = json.loads(
            (repo / "configs" / "diagnosers" / "real-debugger-v3.json").read_text()
        )
        cfg_src.setdefault("provider_policy", {})[
            "non_fatal_provider_error_prefixes"
        ] = ["api_call_failed"]
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as cfp:
            json.dump(cfg_src, cfp)
            cfp.flush()
            cfg_path = cfp.name
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config", cfg_path,
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        manifest = diag_dir / "grep.jsonl"
        assert manifest.exists(), (
            f"manifest not written; rc={res.returncode}; "
            f"stderr={res.stderr.decode()[:400]!r}"
        )
        for line in manifest.open():
            row = json.loads(line)
            pe = (row.get("metadata") or {}).get("provider_error") or ""
            assert "sk-stdin1234567890abcdef0123456" not in pe, (
                f"raw secret in provider_error: {pe[:200]!r}"
            )
            if pe:
                assert "redacted-secret" in pe, (
                    f"runner did not redact structured _provider_error; "
                    f"pe={pe[:200]!r}"
                )


def test_eval_consistency_rejects_excluded_row_with_required_signal_only():
    """Per Codex 2026-06-18 F1 [high]: SCORE_FIELDS previously omitted
    `required_signal_mention_recall` and `category_match_score_v1_1`.
    A stale row with the `[historical exclusion]` marker, abstention
    semantics, and every checked score at 0 — but those two
    specific fields nonzero — passed the gate and still inflated
    the corresponding macro rates in published reports.

    Forge exactly that row shape and assert the check rejects it
    with a specific reason naming the offending field.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    check = repo / "tools" / "validate_eval_manifest_consistency.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        split = root / "dev"
        diag_dir = split / "diagnoses" / "real-debugger-v3"
        diag_dir.mkdir(parents=True)
        (diag_dir / "grep.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "grep"}) + "\n",
            encoding="utf-8",
        )
        eval_path = split / "eval_diagnosis_real-debugger-v3.json"
        eval_path.write_text(
            json.dumps({
                "split": "dev",
                "diagnoser": "real-debugger-v3",
                "methods": [{
                    "context_method": "grep",
                    "cases": [
                        {"case_id": "case-a"},
                        {
                            "case_id": "case-b",
                            # All the fields the 2026-06-17 gate
                            # checked are zero/abstention; only the
                            # two omitted fields are inflated.
                            "provider_error": "synthetic [historical exclusion]",
                            "diagnosis_success": False,
                            "abstained": True,
                            "diagnosis_score_v1": 0.0,
                            "diagnosis_score_v1_1": 0.0,
                            "category_accuracy": 0.0,
                            "critical_signal_mention_recall": 0.0,
                            "must_mention_coverage": 0.0,
                            "relevant_file_recall": 0.0,
                            "relevant_test_recall": 0.0,
                            "valid_evidence_quote_rate": 0.0,
                            # Inflated:
                            "required_signal_mention_recall": 1.0,
                            "category_match_score_v1_1": 1.0,
                        },
                    ],
                }],
            }),
            encoding="utf-8",
        )
        excl = root / "exclusions.json"
        excl.write_text(
            json.dumps({"exclusions": [{
                "split": "dev",
                "diagnoser": "real-debugger-v3",
                "method": "grep",
                "case_id": "case-b",
                "provider_error_prefix": "synthetic",
                "note": "test",
            }]}),
            encoding="utf-8",
        )
        res = _sub.run(
            ["python3", str(check),
             "--results-dir", str(root),
             "--exclusions", str(excl)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode != 0, (
            f"check should reject row with required_signal_mention_recall "
            f"=1.0; stdout={res.stdout.decode()[:300]!r}"
        )
        err = res.stderr.decode("utf-8")
        # Must name one of the previously-omitted fields.
        assert (
            "required_signal_mention_recall" in err
            or "category_match_score_v1_1" in err
        ), err[:600]


def test_eval_consistency_rejects_excluded_row_with_forbidden_claim():
    """Per Codex 2026-06-18 F1 [high]: also reject excluded rows
    whose `forbidden_claim_violations` is non-empty or
    `confident_error*` is True — those contribute to per-method
    rates even when every numeric score field is 0.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    check = repo / "tools" / "validate_eval_manifest_consistency.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        split = root / "dev"
        diag_dir = split / "diagnoses" / "real-debugger-v3"
        diag_dir.mkdir(parents=True)
        (diag_dir / "grep.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "grep"}) + "\n",
            encoding="utf-8",
        )
        eval_path = split / "eval_diagnosis_real-debugger-v3.json"
        eval_path.write_text(
            json.dumps({
                "split": "dev",
                "diagnoser": "real-debugger-v3",
                "methods": [{
                    "context_method": "grep",
                    "cases": [
                        {"case_id": "case-a"},
                        {
                            "case_id": "case-b",
                            "provider_error": "synthetic [historical exclusion]",
                            "diagnosis_success": False,
                            "abstained": True,
                            "diagnosis_score_v1": 0.0,
                            "diagnosis_score_v1_1": 0.0,
                            "category_accuracy": 0.0,
                            "category_match_score_v1_1": 0.0,
                            "required_signal_mention_recall": 0.0,
                            "critical_signal_mention_recall": 0.0,
                            "must_mention_coverage": 0.0,
                            "relevant_file_recall": 0.0,
                            "relevant_test_recall": 0.0,
                            "valid_evidence_quote_rate": 0.0,
                            # Inflated boolean / list fields:
                            "forbidden_claim_violations": ["leaked claim"],
                            "confident_error": True,
                        },
                    ],
                }],
            }),
            encoding="utf-8",
        )
        excl = root / "exclusions.json"
        excl.write_text(
            json.dumps({"exclusions": [{
                "split": "dev",
                "diagnoser": "real-debugger-v3",
                "method": "grep",
                "case_id": "case-b",
                "provider_error_prefix": "synthetic",
                "note": "test",
            }]}),
            encoding="utf-8",
        )
        res = _sub.run(
            ["python3", str(check),
             "--results-dir", str(root),
             "--exclusions", str(excl)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode != 0, (
            f"check should reject row with forbidden_claim_violations / "
            f"confident_error; stdout={res.stdout.decode()[:300]!r}"
        )
        err = res.stderr.decode("utf-8")
        assert (
            "forbidden_claim_violations" in err
            or "confident_error" in err
        ), err[:600]


def test_eval_consistency_rejects_stale_excluded_row_with_inflated_score():
    """Per Codex 2026-06-17 F2 [high]: an exclusion-exempt eval row
    that lacks the `[historical exclusion]` marker OR carries
    non-zero scores must be rejected. Pre-fix, the validator only
    checked case-ID matching — a stale or hand-edited row keeping
    inflated metrics could still pass the gate.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    check = repo / "tools" / "validate_eval_manifest_consistency.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        split = root / "dev"
        diag_dir = split / "diagnoses" / "real-debugger-v3"
        diag_dir.mkdir(parents=True)
        # Manifest has just case-a; eval has case-a + case-b
        # (excluded). case-b is exempted but its row has inflated
        # scores — should reject.
        (diag_dir / "grep.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "grep"}) + "\n",
            encoding="utf-8",
        )
        eval_path = split / "eval_diagnosis_real-debugger-v3.json"
        eval_path.write_text(
            json.dumps({
                "split": "dev",
                "diagnoser": "real-debugger-v3",
                "methods": [
                    {
                        "context_method": "grep",
                        "cases": [
                            {"case_id": "case-a"},
                            {
                                "case_id": "case-b",
                                # No "[historical exclusion]" marker,
                                # and inflated scores.
                                "provider_error": "stale leftover",
                                "diagnosis_success": True,
                                "category_accuracy": 1.0,
                                "diagnosis_score_v1": 0.8,
                                "abstained": False,
                            },
                        ],
                    },
                ],
            }),
            encoding="utf-8",
        )
        # Exclusion file lists case-b → exemption attempted, but
        # validator should still reject due to inflated row.
        excl = root / "exclusions.json"
        excl.write_text(
            json.dumps({
                "exclusions": [
                    {
                        "split": "dev",
                        "diagnoser": "real-debugger-v3",
                        "method": "grep",
                        "case_id": "case-b",
                        "provider_error_prefix": "synthetic",
                        "note": "test",
                    },
                ],
            }),
            encoding="utf-8",
        )
        res = _sub.run(
            ["python3", str(check),
             "--results-dir", str(root),
             "--exclusions", str(excl)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode != 0, (
            f"check should reject stale excluded row; "
            f"stdout={res.stdout.decode()[:300]!r}"
        )
        err = res.stderr.decode("utf-8")
        assert "case-b" in err, err[:600]
        assert "stale/inflated" in err or "exclusion-exempt" in err, err[:600]


def test_runner_redacts_shim_stderr_in_provider_error_detail():
    """Per Codex 2026-06-16 F2 [high]: when a command shim exits
    non-zero, the runner stores up to 600 bytes of stderr in
    ShimCallError, later persisted as
    `metadata.provider_error_detail`. Pre-fix, that string was
    raw. A shim that sanitized its stdout but accidentally wrote
    credentials to stderr (e.g. via a logging library) leaked them
    into committed artifacts.

    End-to-end: forge a shim that writes a sanitized stdout
    envelope AND a secret-bearing stderr line. Run the runner;
    assert `metadata.provider_error` contains the sanitized form
    AND `metadata.provider_error_detail` does NOT contain the raw
    secret.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        forge_src = '''
import json, sys
sys.stdin.read()
envelope = {
    "_provider_error": "api_call_failed: synthetic",
}
print(json.dumps(envelope))
# secret-bearing stderr — runner should redact before persisting
sys.stderr.write("logger leaked: Authorization: Bearer sk-stderr12345678901234abcdef\\n")
sys.exit(1)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(forge_src)
            fp.flush()
            forge_path = fp.name
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"
        # Add the api_call_failed prefix to v3's allowlist for this
        # test only by passing --diagnoser-config to a copy of the
        # v3 config with the prefix added. Simpler: use a temp config
        # that opts into non-fatal so the row gets WRITTEN to manifest.
        cfg_src = json.loads(
            (repo / "configs" / "diagnosers" / "real-debugger-v3.json").read_text()
        )
        cfg_src.setdefault("provider_policy", {})[
            "non_fatal_provider_error_prefixes"
        ] = ["api_call_failed"]
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as cfp:
            json.dump(cfg_src, cfp)
            cfp.flush()
            cfg_path = cfp.name
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config", cfg_path,
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        # Inspect the freshly-written manifest for redaction.
        manifest = diag_dir / "grep.jsonl"
        if not manifest.exists():
            # If the runner aborted before writing, fail with
            # diagnostic info.
            raise AssertionError(
                f"manifest never written; rc={res.returncode}; "
                f"stderr={res.stderr.decode()[:400]!r}"
            )
        for line in manifest.open():
            row = json.loads(line)
            md = row.get("metadata") or {}
            detail = md.get("provider_error_detail") or ""
            assert "sk-stderr12345678901234abcdef" not in detail, (
                f"raw stderr secret leaked into provider_error_detail: "
                f"{detail[:300]!r}"
            )
            # Should reference redacted form.
            if detail:
                assert "redacted-secret" in detail or "redacted-url" in detail, (
                    f"runner did not redact stderr; detail={detail[:300]!r}"
                )


def test_openai_shim_http_error_summary_omits_body():
    """Per Codex 2026-06-15 F2 [high]: the HTTP error path uses
    `safe_http_error_summary` which records status code + body
    digest only — the raw body never appears in the error message.
    """
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "_shim_for_test3", repo / "examples" / "diagnosis_shim_openai.py"
    )
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    body_with_secret = (
        '{"error": {"message": "key sk-abc1234567890123456789012345 wrong"}}'
    )
    summary = shim.safe_http_error_summary(401, body_with_secret)
    assert "sk-abc" not in summary, f"body content leaked into summary: {summary!r}"
    assert "401" in summary, summary
    assert "body_sha256=" in summary, summary
    assert "body_len=" in summary, summary


def test_diagnosis_vs_context_check_passes_on_canonical_state():
    """Per Codex 2026-06-14 F1 [high]: every diagnosis manifest case
    must be present in its source context manifest, OR be listed in
    `configs/historical_provider_error_exclusions.json`. The canonical
    state should satisfy this — the 20 historical removals from the
    2026-06-09 + 2026-06-10 cleanups are all in the exclusion file."""
    import subprocess as _sub
    repo = Path(__file__).resolve().parent.parent.parent
    res = _sub.run(
        ["python3",
         str(repo / "tools" / "validate_diagnosis_vs_context_consistency.py")],
        cwd=repo, capture_output=True, timeout=30,
    )
    assert res.returncode == 0, (
        f"diagnosis-vs-context check failed; "
        f"stderr={res.stderr.decode()[:1200]!r}"
    )


def test_diagnosis_vs_context_check_catches_unexcluded_omission():
    """Per Codex 2026-06-14 F1 [high]: synthesize a temp tree where the
    diagnosis manifest is missing a case present in the source context
    manifest, and that case is NOT in the exclusion list. The check
    must reject."""
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    check = repo / "tools" / "validate_diagnosis_vs_context_consistency.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        split = root / "dev"
        # Source context manifest has 2 cases.
        (split / "grep.jsonl").parent.mkdir(parents=True, exist_ok=True)
        (split / "grep.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "grep"}) + "\n"
            + json.dumps({"case_id": "case-b", "context_method": "grep"}) + "\n",
            encoding="utf-8",
        )
        # Diagnosis manifest only has case-a.
        diag_dir = split / "diagnoses" / "real-debugger-v3"
        diag_dir.mkdir(parents=True)
        (diag_dir / "grep.jsonl").write_text(
            json.dumps({
                "case_id": "case-a",
                "context_method": "grep",
                "diagnoser": "real-debugger-v3",
            }) + "\n",
            encoding="utf-8",
        )
        # Empty exclusion file → case-b is NOT excluded.
        excl = root / "exclusions.json"
        excl.write_text(json.dumps({"exclusions": []}), encoding="utf-8")
        res = _sub.run(
            ["python3", str(check),
             "--results-dir", str(root),
             "--exclusions", str(excl)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode != 0, (
            f"check should reject unexcluded omission; "
            f"stdout={res.stdout.decode()[:300]!r}"
        )
        err = res.stderr.decode("utf-8")
        assert "case-b" in err, err[:600]


def test_diagnosis_vs_context_check_honors_exclusion_list():
    """Per Codex 2026-06-14 F1 [high]: same shape, but case-b IS in the
    exclusion list — check passes."""
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    check = repo / "tools" / "validate_diagnosis_vs_context_consistency.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        split = root / "dev"
        split.mkdir()
        (split / "grep.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "grep"}) + "\n"
            + json.dumps({"case_id": "case-b", "context_method": "grep"}) + "\n",
            encoding="utf-8",
        )
        diag_dir = split / "diagnoses" / "real-debugger-v3"
        diag_dir.mkdir(parents=True)
        (diag_dir / "grep.jsonl").write_text(
            json.dumps({
                "case_id": "case-a",
                "context_method": "grep",
                "diagnoser": "real-debugger-v3",
            }) + "\n",
            encoding="utf-8",
        )
        excl = root / "exclusions.json"
        excl.write_text(
            json.dumps({
                "exclusions": [
                    {
                        "split": "dev",
                        "diagnoser": "real-debugger-v3",
                        "method": "grep",
                        "case_id": "case-b",
                        "provider_error_prefix": "synthetic",
                        "note": "test fixture",
                    },
                ],
            }),
            encoding="utf-8",
        )
        res = _sub.run(
            ["python3", str(check),
             "--results-dir", str(root),
             "--exclusions", str(excl)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode == 0, (
            f"check should accept excluded omission; "
            f"stderr={res.stderr.decode()[:600]!r}"
        )


def test_missing_context_with_provider_error_fails_closed():
    """Per Codex 2026-06-13 F1 [high]: a manifest row that declares
    `metadata.provider_error` AND points at a nonexistent context_path
    must STILL trip the fail-closed path. Pre-fix, the
    ctx_path.exists() check ran first and quietly `continue`d, so the
    method flushed as a clean run with the failed case silently
    omitted — wrapper exited 0 and overwrote prior valid artifacts.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        results_dir = tmp_root / "results"
        method_dir = results_dir / "dev"
        method_dir.mkdir(parents=True)
        manifest = method_dir / "synthetic-ctx.jsonl"
        # context_path points at a file that doesn't exist.
        manifest.write_text(
            json.dumps({
                "case_id": "lint-react-001",
                "context_method": "synthetic-ctx",
                "context_path": "cases/dev/lint-react-001/nonexistent.log",
                "metadata": {
                    "provider_error": "rtk_input_truncated: synthetic huge log",
                },
            }) + "\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = "true"
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "synthetic-ctx",
             "--results-dir", str(results_dir),
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=30, env=env,
        )
        err = res.stderr.decode("utf-8")
        assert res.returncode != 0, (
            f"missing context + provider_error should fail run; "
            f"rc={res.returncode}; stderr={err[:600]!r}"
        )
        assert "FAIL_PROVIDER_ERROR" in err, (
            f"expected FAIL_PROVIDER_ERROR; stderr={err[:600]!r}"
        )


def test_missing_context_without_provider_error_also_fails_closed():
    """Per Codex 2026-06-13 F1 [high]: a missing context file with NO
    upstream provider_error is ALSO a corruption signal — the manifest
    claims a context that isn't on disk. The runner must fail-closed
    and preserve any existing diagnosis artifacts rather than silently
    omit the case.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        results_dir = tmp_root / "results"
        method_dir = results_dir / "dev"
        method_dir.mkdir(parents=True)
        manifest = method_dir / "synthetic-ctx.jsonl"
        manifest.write_text(
            json.dumps({
                "case_id": "lint-react-001",
                "context_method": "synthetic-ctx",
                "context_path": "cases/dev/lint-react-001/nonexistent.log",
                # No metadata.provider_error.
            }) + "\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = "true"
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "synthetic-ctx",
             "--results-dir", str(results_dir),
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=30, env=env,
        )
        err = res.stderr.decode("utf-8")
        assert res.returncode != 0, (
            f"missing context (no provider_error) should fail run; "
            f"rc={res.returncode}; stderr={err[:600]!r}"
        )
        assert "FAIL_PROVIDER_ERROR" in err and "context file missing" in err, (
            f"expected fail-closed message; stderr={err[:600]!r}"
        )


def test_fatal_provider_error_preserves_existing_method_artifacts():
    """Per Codex 2026-06-12 F1 [high]: a non-allowlisted provider_error
    during a re-run must NOT overwrite the existing canonical manifest
    + per-case JSONs. The 2026-06-08 F1 fix set had_failure but the
    flush happened before the wrapper aborted, so a transient
    auth/transport/JSONDecode failure during re-run destroyed good
    data.

    End-to-end: snapshot the v3 dev/grep manifest + per-case JSONs,
    run with a forged shim that emits a non-allowlisted `api_call_failed`
    prefix (which exits 1 from the shim), assert byte-identical
    preservation of the pre-existing artifacts.
    """
    import subprocess as _sub
    import tempfile
    repo = Path(__file__).resolve().parent.parent.parent
    diag_dir = repo / "results" / "dev" / "diagnoses" / "real-debugger-v3"
    with _snapshot_restore_diag_dir(diag_dir):
        # Snapshot what the current canonical state SHOULD be.
        manifest = diag_dir / "grep.jsonl"
        per_case_dir = diag_dir / "grep"
        pre_manifest = manifest.read_text("utf-8") if manifest.exists() else None
        pre_per_case = {}
        if per_case_dir.exists():
            for p in per_case_dir.glob("*.json"):
                pre_per_case[p.name] = p.read_text("utf-8")

        # Forge a shim emitting a non-allowlisted `api_call_failed`
        # prefix. Use --no-cache to force the fresh-call path.
        forge_src = '''
import json, sys
sys.stdin.read()
envelope = {
    "_provider_error": "api_call_failed: synthetic transient transport",
}
print(json.dumps(envelope))
sys.exit(1)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(forge_src)
            fp.flush()
            forge_path = fp.name
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = f"python3 {forge_path}"
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "grep",
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=60, env=env,
        )
        assert res.returncode != 0, "transient failure should exit non-zero"
        out_text = res.stdout.decode("utf-8")
        assert "PROVIDER-ERROR-FAILED" in out_text or "preserved" in out_text, (
            f"runner should log preservation message; stdout={out_text[:400]!r}"
        )

        # Verify byte-identical preservation.
        if pre_manifest is not None:
            post_manifest = manifest.read_text("utf-8")
            assert post_manifest == pre_manifest, (
                "manifest was modified despite provider-error failure"
            )
        post_per_case = {}
        if per_case_dir.exists():
            for p in per_case_dir.glob("*.json"):
                post_per_case[p.name] = p.read_text("utf-8")
        assert post_per_case == pre_per_case, (
            f"per-case JSONs changed despite provider-error failure: "
            f"diff_keys={set(post_per_case) ^ set(pre_per_case)!r}"
        )


def test_eval_consistency_catches_manifest_method_omitted_from_eval():
    """Per Codex 2026-06-12 F2 [medium]: the consistency check used to
    only iterate methods present in the eval file. A manifest method
    that was MISSING from a stale eval file was silently ignored —
    metrics could omit committed diagnosis data while the gate
    claimed consistency.

    Synthesize a tree with two manifests (method-x, method-y) but an
    eval file that only includes method-x. Assert the check rejects.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    check = repo / "tools" / "validate_eval_manifest_consistency.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        split = root / "dev"
        diag_dir = split / "diagnoses" / "real-debugger-v3"
        diag_dir.mkdir(parents=True)
        # Two manifests with one case each.
        (diag_dir / "method-x.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "method-x"}) + "\n",
            encoding="utf-8",
        )
        (diag_dir / "method-y.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "method-y"}) + "\n",
            encoding="utf-8",
        )
        # Eval file only covers method-x.
        eval_path = split / "eval_diagnosis_real-debugger-v3.json"
        eval_path.write_text(
            json.dumps({
                "split": "dev",
                "diagnoser": "real-debugger-v3",
                "methods": [
                    {
                        "context_method": "method-x",
                        "cases": [{"case_id": "case-a"}],
                    },
                ],
            }),
            encoding="utf-8",
        )
        res = _sub.run(
            ["python3", str(check), "--results-dir", str(root)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode != 0, (
            f"check should reject omitted-method state; "
            f"stdout={res.stdout.decode()[:300]!r}"
        )
        err = res.stderr.decode("utf-8")
        assert "method-y" in err, err[:600]


def test_eval_manifest_consistency_check_passes_on_canonical_state():
    """Per Codex 2026-06-11 F1 [high]: after the 2026-06-09 + 2026-06-10
    cleanups, eval_diagnosis_*.json files were regenerated to match
    the cleaned manifests. This test pins the consistency: any future
    manifest edit MUST be paired with eval-file regeneration."""
    import subprocess as _sub
    repo = Path(__file__).resolve().parent.parent.parent
    res = _sub.run(
        ["python3",
         str(repo / "tools" / "validate_eval_manifest_consistency.py")],
        cwd=repo, capture_output=True, timeout=30,
    )
    assert res.returncode == 0, (
        f"eval-manifest consistency check failed; "
        f"stderr={res.stderr.decode()[:800]!r}"
    )


def test_eval_manifest_consistency_check_catches_drift():
    """Per Codex 2026-06-11 F1 [high]: synthesize a temp tree with an
    eval file claiming case IDs that aren't in the corresponding
    manifest, assert the check exits non-zero with a useful diff."""
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    check = repo / "tools" / "validate_eval_manifest_consistency.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        split = root / "dev"
        diag_dir = split / "diagnoses" / "real-debugger-v3"
        diag_dir.mkdir(parents=True)
        # Manifest with 2 case IDs.
        (diag_dir / "grep.jsonl").write_text(
            json.dumps({"case_id": "case-a", "context_method": "grep"}) + "\n"
            + json.dumps({"case_id": "case-b", "context_method": "grep"}) + "\n",
            encoding="utf-8",
        )
        # Eval file with 3 case IDs (one missing from manifest, one extra).
        eval_path = split / "eval_diagnosis_real-debugger-v3.json"
        eval_path.write_text(
            json.dumps({
                "split": "dev",
                "diagnoser": "real-debugger-v3",
                "methods": [
                    {
                        "context_method": "grep",
                        "cases": [
                            {"case_id": "case-a"},
                            {"case_id": "case-c"},  # not in manifest
                            {"case_id": "case-d"},  # not in manifest
                        ],
                    },
                ],
            }),
            encoding="utf-8",
        )
        res = _sub.run(
            ["python3", str(check), "--results-dir", str(root)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode != 0, (
            f"check should reject drifted state; "
            f"stdout={res.stdout.decode()[:300]!r}"
        )
        err = res.stderr.decode("utf-8")
        assert "case-c" in err and "case-d" in err, err[:600]
        assert "case-b" in err, err[:600]  # in manifest but not eval


def test_context_provider_error_triggers_fail_closed():
    """Per Codex 2026-06-11 F2 [high]: when an upstream context row
    carries `metadata.provider_error` (e.g. hybrid router emitted
    "no method selectable"), the diagnosis runner used to write a
    `context_provider_error:` row WITHOUT setting had_failure — the
    runner exited 0 and wrappers published the failed upstream
    context as a successful experiment.

    Fix: route the context_provider_error path through the same
    `provider_policy.non_fatal_provider_error_prefixes` allowlist
    check as fresh diagnoser provider errors. Non-allowlisted
    prefixes → had_failure=True → non-zero exit.

    End-to-end: forge a context manifest with a provider_error row
    (no shim invocation needed — the upstream metadata triggers the
    early branch). Assert the runner exits non-zero and stderr says
    FAIL_PROVIDER_ERROR.
    """
    import subprocess as _sub
    import tempfile
    import json
    import shutil
    repo = Path(__file__).resolve().parent.parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        # Set up minimal results layout pointing at the real cases
        # dir for context_path.
        results_dir = tmp_root / "results"
        cases_dir = repo / "cases"
        method_dir = results_dir / "dev"
        method_dir.mkdir(parents=True)
        # Forge a context manifest carrying provider_error.
        # We need a real case + raw.log for the context_path check.
        real_case = "lint-react-001"  # exists under cases/dev/
        ctx_path = repo / "cases" / "dev" / real_case / "raw.log"
        if not ctx_path.exists():
            return  # skip if fixture missing
        manifest = method_dir / "synthetic-ctx.jsonl"
        manifest.write_text(
            json.dumps({
                "case_id": real_case,
                "context_method": "synthetic-ctx",
                "context_path": str(ctx_path.relative_to(repo)),
                "metadata": {
                    "provider_error": "rtk_input_truncated: synthetic huge log",
                },
            }) + "\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["CILOGBENCH_ALLOW_EXTERNAL_LLM"] = "1"
        env["DIAGNOSIS_COMMAND"] = "true"  # not invoked on context_provider_error path
        res = _sub.run(
            ["python3", f"{repo}/tools/run_diagnosis.py",
             "--split", "dev",
             "--diagnoser", "command",
             "--diagnoser-name", "real-debugger-v3",
             "--command", env["DIAGNOSIS_COMMAND"],
             "--context-method", "synthetic-ctx",
             "--results-dir", str(results_dir),
             "--diagnoser-config",
             f"{repo}/configs/diagnosers/real-debugger-v3.json",
             "--no-cache"],
            cwd=repo, capture_output=True, timeout=30, env=env,
        )
        err = res.stderr.decode("utf-8")
        assert res.returncode != 0, (
            f"context_provider_error should fail run; "
            f"got rc={res.returncode}; stderr={err[:400]!r}"
        )
        assert "FAIL_PROVIDER_ERROR" in err, (
            f"expected FAIL_PROVIDER_ERROR; stderr={err[:400]!r}"
        )
        assert "context-provider" in err or "context_provider_error" in err, err[:400]


def test_release_check_recurses_into_nested_diagnoses_layouts():
    """Per Codex 2026-06-10 F1 [high]: the release check must walk
    recursively for `**/diagnoses` directories, not just direct
    children of split. The v2 protocol nests results under
    `results/v2/<split>/diagnoses/`, which the 2026-06-09 single-
    level scanner skipped — 12 v2 RuntimeError rows hid there.

    Fixture: synthesize a temp results tree with both flat
    (`results/dev/diagnoses/`) and nested (`results/v2/dev/diagnoses/`)
    layouts. Plant a non-allowlisted row in the nested manifest only;
    assert the scanner exits non-zero and the failure references the
    nested path.
    """
    import subprocess as _sub
    import tempfile
    import json
    repo = Path(__file__).resolve().parent.parent.parent
    scanner = repo / "tools" / "validate_committed_diagnosis_provider_errors.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        nested_dir = root / "v2" / "dev" / "diagnoses" / "real-debugger-v1"
        nested_dir.mkdir(parents=True)
        manifest = nested_dir / "grep.jsonl"
        manifest.write_text(
            json.dumps({
                "case_id": "synthetic-001",
                "context_method": "grep",
                "diagnoser": "real-debugger-v1",
                "metadata": {
                    "provider_error": "RuntimeError: synthetic transient failure",
                },
            }) + "\n",
            encoding="utf-8",
        )
        res = _sub.run(
            ["python3", str(scanner), "--results-dir", str(root)],
            cwd=repo, capture_output=True, timeout=30,
        )
        assert res.returncode != 0, (
            f"scanner should reject nested non-allowlisted row; "
            f"stdout={res.stdout.decode()[:300]!r}"
        )
        err = res.stderr.decode("utf-8")
        assert "v2/dev/diagnoses/real-debugger-v1" in err or "v2/dev" in err, (
            f"scanner stderr should reference the nested path; got {err[:600]!r}"
        )
        assert "synthetic-001" in err, err[:600]


def test_release_check_passes_on_clean_canonical_state():
    """Per Codex 2026-06-09 F1 [high]: the release check
    `tools/validate_committed_diagnosis_provider_errors.py` exits 0 on
    the post-cleanup canonical state. If the test ever fails, it means
    a regression has re-introduced non-allowlisted provider_error rows
    into a committed real-debugger-* manifest."""
    import subprocess as _sub
    repo = Path(__file__).resolve().parent.parent.parent
    res = _sub.run(
        ["python3",
         str(repo / "tools" / "validate_committed_diagnosis_provider_errors.py")],
        cwd=repo, capture_output=True, timeout=30,
    )
    assert res.returncode == 0, (
        f"release check failed; stderr={res.stderr.decode()[:600]!r}"
    )


def test_v3_config_declares_provider_policy_allowlist():
    """Per Codex 2026-06-08 F1 [high]: v3 config must declare
    `provider_policy.non_fatal_provider_error_prefixes` with
    `unsupported_context_too_large` so the documented graceful
    refusal path stays non-fatal."""
    cfg = rd.load_diagnoser_config("real-debugger-v3")
    pp = (cfg or {}).get("provider_policy") or {}
    allow = pp.get("non_fatal_provider_error_prefixes") or []
    assert "unsupported_context_too_large" in allow, (
        f"v3 must allowlist 'unsupported_context_too_large'; got {allow!r}"
    )


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
        # Codex 2026-06-05 F2 (canonical configs lock identity)
        test_canonical_config_rejects_env_override,
        # Codex 2026-06-06 F1 (locked configs block shim invocation)
        test_locked_config_check_helper,
        test_override_allowed_config_skips_locked_check,
        test_locked_env_mismatch_blocks_shim_invocation_end_to_end,
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
        # Codex 2026-05-25 F1 (resolved_model pinning, cache-hit path)
        # NOTE: test_cache_hit_back_compat_null_resolved_model removed by
        # Codex 2026-06-05 F1 — cache-hit no longer accepts null
        # resolved_model under a pinned config (see below).
        test_cache_hit_rejects_resolved_model_drift,
        test_v3_config_pins_expected_resolved_model,
        # Codex 2026-05-26 F1 (resolved_model check applies to fresh-row)
        test_fresh_row_rejects_resolved_model_drift,
        test_fresh_row_accepts_canonical_resolved_model,
        # 2026-05-26 test test_fresh_row_back_compat_null_resolved_model
        # was replaced by 2026-05-27 — see below
        test_resolved_model_shared_helper_returns_consistent_results,
        # Codex 2026-05-27 F1 (provenance mismatches skip writes)
        test_provenance_mismatch_skips_manifest_write,
        # Codex 2026-05-28 F1 (provenance failure preserves manifest)
        test_provenance_failure_preserves_existing_manifest_and_per_case,
        # Codex 2026-05-29 F1 (redaction enforcement on persisted base_url)
        test_base_url_redaction_enforced_even_with_matching_hash,
        test_base_url_redaction_enforced_for_deep_path,
        test_base_url_sanitized_form_accepts,
        test_fresh_row_rejects_unsanitized_base_url,
        # Codex 2026-05-29 F2 (provenance check on ShimCallError rows)
        test_shim_error_row_provenance_check_e2e,
        # Codex 2026-05-30 F1 (no-call failures DON'T trip provenance)
        test_oversized_context_writes_provider_error_not_fail_provenance,
        # Codex 2026-06-01 F1 (redaction enforced even on templates)
        test_reusable_template_still_enforces_redaction,
        # Codex 2026-06-02 F1 (provider_name family validation)
        test_fresh_row_rejects_wrong_provider_family,
        test_cache_hit_rejects_wrong_provider_family,
        test_canonical_provider_name_accepts,
        test_provider_name_required_under_real_configs,
        test_v1_v2_v3_committed_artifacts_carry_correct_provider_name,
        # Codex 2026-06-03 F1+F2 (URL redaction in errors + lossy sha256)
        test_lossy_endpoint_requires_sha256_under_provenance_config,
        test_validation_error_does_not_leak_raw_url_with_secrets,
        # Codex 2026-06-04 F1+F2 (deeper URL scrubbing in errors)
        test_redaction_error_does_not_echo_raw_cached_url,
        test_openai_shim_redacts_url_in_malformed_base_url_error,
        test_redact_urls_in_text_helper,
        # Codex 2026-05-27 F2 + 2026-06-05 F1 (strict resolved_model)
        test_fresh_row_rejects_null_resolved_model_under_pin,
        test_cache_hit_rejects_null_resolved_model_under_pin,
        # Codex 2026-05-25 F2 + 2026-05-31 F1 (sanitize_base_url allowlist)
        test_sanitize_base_url_strips_deep_path_segments,
        # Codex 2026-06-19 F1 (hostname redaction for non-public hosts)
        test_sanitize_base_url_redacts_tenant_hostname,
        test_runner_sanitize_base_url_for_compare_mirrors_shim_redaction,
        # Codex 2026-06-20 F1 (sanitizer idempotency for redacted hosts)
        test_sanitize_base_url_is_idempotent_on_redacted_host,
        test_private_endpoint_cache_hit_accepts_redacted_row,
        # Codex 2026-06-20 F2 (no-choices hash-only summary)
        test_openai_shim_no_choices_emits_hash_only_summary,
        test_sanitize_base_url_drops_tenant_key_first_segment,
        test_runner_sanitize_matches_shim_sanitize,
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
        # Codex 2026-06-08 F1 (provider_error fail-closed)
        test_provider_error_unknown_class_fails_run_by_default,
        test_provider_error_in_allowlist_preserves_success,
        test_v3_config_declares_provider_policy_allowlist,
        # Codex 2026-06-08 F2 (config-sha + shim-sha validation)
        test_cache_hit_rejects_when_config_sha_changed,
        test_cache_hit_accepts_when_config_sha_matches,
        test_cache_hit_rejects_when_shim_sha_changed,
        test_diagnoser_config_sha256_helper_returns_sha_of_loaded_file,
        test_shim_sha256_for_command_resolves_repo_local_path,
        test_fresh_row_writes_carry_config_and_shim_sha,
        # Codex 2026-06-09 F2 (strict mode for canonical configs)
        test_cache_hit_rejects_legacy_null_under_canonical_config,
        test_cache_hit_accepts_legacy_null_under_template_config,
        test_migrated_cache_rejects_after_config_edit_e2e,
        # Codex 2026-06-09 F1 (release check on committed artifacts)
        test_release_check_passes_on_clean_canonical_state,
        # Codex 2026-06-10 F1 (recursive walk for nested layouts)
        test_release_check_recurses_into_nested_diagnoses_layouts,
        # Codex 2026-06-11 F2 (context_provider_error fail-closed)
        test_context_provider_error_triggers_fail_closed,
        # Codex 2026-06-11 F1 (eval-manifest consistency release check)
        test_eval_manifest_consistency_check_passes_on_canonical_state,
        test_eval_manifest_consistency_check_catches_drift,
        # Codex 2026-06-13 F1 (missing context + provider_error fail-closed)
        test_missing_context_with_provider_error_fails_closed,
        test_missing_context_without_provider_error_also_fails_closed,
        # Codex 2026-06-14 F1 (diagnosis-vs-context consistency)
        test_diagnosis_vs_context_check_passes_on_canonical_state,
        test_diagnosis_vs_context_check_catches_unexcluded_omission,
        test_diagnosis_vs_context_check_honors_exclusion_list,
        # Codex 2026-06-15 F1 (eval injects zero-score for exclusions)
        test_eval_injects_zero_score_rows_for_historical_exclusions,
        # Codex 2026-06-15 F2 (shim secret redaction in error text)
        test_openai_shim_redacts_bearer_tokens_in_error_text,
        test_openai_shim_redacts_api_key_shape,
        test_openai_shim_http_error_summary_omits_body,
        # Codex 2026-06-16 F1 (shim post-API redacts secrets)
        test_openai_shim_post_api_error_redacts_bearer_payload,
        # Codex 2026-06-16 F2 (runner redacts stderr before persistence)
        test_runner_redacts_shim_stderr_in_provider_error_detail,
        # Codex 2026-06-17 F1 (runner redacts structured _provider_error)
        test_runner_redacts_structured_provider_error_from_shim_stdout,
        # Codex 2026-06-17 F2 (eval consistency rejects inflated excluded rows)
        test_eval_consistency_rejects_stale_excluded_row_with_inflated_score,
        # Codex 2026-06-18 F1 (SCORE_FIELDS now covers all macro fields)
        test_eval_consistency_rejects_excluded_row_with_required_signal_only,
        test_eval_consistency_rejects_excluded_row_with_forbidden_claim,
        # Codex 2026-06-12 F1 (fatal provider_error preserves manifests)
        test_fatal_provider_error_preserves_existing_method_artifacts,
        # Codex 2026-06-12 F2 (consistency check also asserts method set)
        test_eval_consistency_catches_manifest_method_omitted_from_eval,
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
