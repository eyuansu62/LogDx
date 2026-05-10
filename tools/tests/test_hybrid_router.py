"""Regression tests for tools/run_hybrid_baseline.py routing logic.

Asserts the invariants Codex adversarial reviews surfaced on
2026-05-08-#2 (rtk input-truncation gate) and 2026-05-09 (rtk
output-budget gate) for hybrid-v3's three-way router.

The routing logic in `route_and_emit()` is heavily branched and has
several gates that all must work in concert. This test invokes the
function directly with synthetic manifest rows and verifies each
branch returns the expected `selected_method` + `selected_reason`.

Run as:
    python3 tools/tests/test_hybrid_router.py

Exits 0 on success. On failure prints the broken assertion and exits 1.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import run_hybrid_baseline as rhb  # noqa: E402

V3_CONFIG = {
    "method": "hybrid-grep-120k-rtk-tail-v3",
    "primary_method": "grep",
    "intermediate_method": "rtk-err-cat",
    "fallback_method": "tail",
    "router_version": "v3",
    "routing_rule": {
        "budget_tokens": 120000,
        "intermediate_budget_tokens": 120000,
    },
}


def make_row(method: str, *, ctx_bytes: int, ctx_path: str = "results/x.txt",
              provider_error: str | None = None,
              rtk_input_truncated: bool = False) -> dict:
    """Construct a synthetic method_output manifest row."""
    meta: dict = {}
    if provider_error is not None:
        meta["provider_error"] = provider_error
    if rtk_input_truncated:
        meta["rtk_input_truncated"] = True
    return {
        "case_id": "synthetic",
        "method": method,
        "context_path": ctx_path,
        "output_byte_size": ctx_bytes,
        "metadata": meta,
    }


def route(*, primary_row, intermediate_row, fallback_row, config=V3_CONFIG) -> tuple[str | None, str]:
    """Invoke route_and_emit() and return (selected_method, selected_reason)."""
    out_jsonl: list[str] = []
    out_routes: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        ctx_dir = tmp_root / "ctx"
        ctx_dir.mkdir()
        # Make a minimal context file under the tmp results-dir so the
        # router's existence check + read succeeds without needing real
        # primary/intermediate/fallback files.
        for row in (primary_row, intermediate_row, fallback_row):
            if row is None:
                continue
            path = ctx_dir / Path(row["context_path"]).name
            path.write_text("synthetic context\n", encoding="utf-8")
            row["context_path"] = str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else f"x/{path.name}"
        # The router computes ROOT-relative paths, but we only need it to
        # find the file by absolute path. Patch ROOT temporarily.
        original_root = rhb.ROOT
        rhb.ROOT = tmp_root
        try:
            for row in (primary_row, intermediate_row, fallback_row):
                if row is None:
                    continue
                # Adjust context_path to be tmp-relative so ROOT/<path> resolves.
                p = ctx_dir / Path(row["context_path"]).name
                row["context_path"] = str(p.relative_to(tmp_root))
            raw = tmp_root / "raw.log"
            raw.write_text("synthetic raw log line\n", encoding="utf-8")
            out_dir = tmp_root / "out"
            out_dir.mkdir()
            rhb.route_and_emit(
                split="synthetic",
                case_id="synthetic",
                config=config,
                primary_row=primary_row,
                fallback_row=fallback_row,
                intermediate_row=intermediate_row,
                raw_log_path=raw,
                out_method_dir=out_dir,
                out_jsonl_lines=out_jsonl,
                out_routes_lines=out_routes,
                cases_dir=tmp_root / "cases",
                results_dir=tmp_root / "results",
            )
        finally:
            rhb.ROOT = original_root
    route_record = json.loads(out_routes[0])
    return route_record.get("selected_method"), route_record.get("selected_reason")


def chars(tokens: int) -> int:
    """Convert tokens to bytes the way chars_to_tokens does (×4)."""
    return tokens * 4


# === Test cases ===

def test_primary_fits_budget():
    """grep ≤ 120k → use grep."""
    primary = make_row("grep", ctx_bytes=chars(50000))
    intermediate = make_row("rtk-err-cat", ctx_bytes=chars(60000))
    fallback = make_row("tail", ctx_bytes=chars(1000))
    sel, reason = route(primary_row=primary, intermediate_row=intermediate, fallback_row=fallback)
    assert sel == "grep" and reason == "primary_fits_budget", (sel, reason)
    print("PASS test_primary_fits_budget")


def test_intermediate_fits_when_primary_too_large():
    """grep > 120k AND rtk-err-cat ≤ 120k AND not truncated → use rtk-err-cat.
    This is the §3f-motivated path: rust case had rtk-err-cat at 18k tokens."""
    primary = make_row("grep", ctx_bytes=chars(160000))
    intermediate = make_row("rtk-err-cat", ctx_bytes=chars(18000))
    fallback = make_row("tail", ctx_bytes=chars(1000))
    sel, reason = route(primary_row=primary, intermediate_row=intermediate, fallback_row=fallback)
    assert sel == "rtk-err-cat" and reason == "primary_too_large_used_intermediate", (sel, reason)
    print("PASS test_intermediate_fits_when_primary_too_large")


def test_intermediate_too_large_falls_back_to_tail():
    """grep > 120k AND rtk-err-cat > 120k AND not truncated → use tail.
    This is the Codex-2026-05-09 [high] regression: nodejs case had
    rtk-err-cat at 320k tokens despite rtk_input_truncated=False; the
    pre-fix v3 router incorrectly selected rtk-err-cat there, causing a
    Sonnet abstain at sv1.1 = 0.0. Post-fix: route to tail (3.8k tokens
    on the same case scored 0.75 on Sonnet)."""
    primary = make_row("grep", ctx_bytes=chars(360000))
    intermediate = make_row("rtk-err-cat", ctx_bytes=chars(320000),
                              rtk_input_truncated=False)
    fallback = make_row("tail", ctx_bytes=chars(4000))
    sel, reason = route(primary_row=primary, intermediate_row=intermediate, fallback_row=fallback)
    assert sel == "tail" and reason == "intermediate_too_large_used_fallback", (sel, reason)
    print("PASS test_intermediate_too_large_falls_back_to_tail")


def test_intermediate_truncated_falls_back_to_tail():
    """grep > 120k AND rtk_input_truncated=True → use tail.
    This is the Codex-2026-05-08-#2 [high] regression: argocd case had
    rtk_input_truncated=True; v3 must NOT select the truncated rtk
    output even though its output_byte_size happens to fit a budget."""
    primary = make_row("grep", ctx_bytes=chars(2000000))
    intermediate = make_row("rtk-err-cat", ctx_bytes=chars(80000),
                              rtk_input_truncated=True)
    fallback = make_row("tail", ctx_bytes=chars(1000))
    sel, reason = route(primary_row=primary, intermediate_row=intermediate, fallback_row=fallback)
    assert sel == "tail" and reason == "intermediate_truncated_used_fallback", (sel, reason)
    print("PASS test_intermediate_truncated_falls_back_to_tail")


def test_intermediate_provider_error_falls_back():
    primary = make_row("grep", ctx_bytes=chars(160000))
    intermediate = make_row("rtk-err-cat", ctx_bytes=chars(50000),
                              provider_error="rtk segfaulted")
    fallback = make_row("tail", ctx_bytes=chars(1000))
    sel, reason = route(primary_row=primary, intermediate_row=intermediate, fallback_row=fallback)
    assert sel == "tail" and reason == "intermediate_provider_error_used_fallback", (sel, reason)
    print("PASS test_intermediate_provider_error_falls_back")


def test_intermediate_missing_falls_back():
    primary = make_row("grep", ctx_bytes=chars(160000))
    fallback = make_row("tail", ctx_bytes=chars(1000))
    sel, reason = route(primary_row=primary, intermediate_row=None, fallback_row=fallback,
                         config={**V3_CONFIG, "intermediate_method": "rtk-err-cat"})
    assert sel == "tail" and reason == "intermediate_missing_used_fallback", (sel, reason)
    print("PASS test_intermediate_missing_falls_back")


def test_v2_two_way_routing_unchanged():
    """When intermediate_method is absent (v1, v2 routers), the 2-way
    routing should still work."""
    primary = make_row("grep", ctx_bytes=chars(160000))
    fallback = make_row("tail", ctx_bytes=chars(1000))
    v2_config = {
        "method": "hybrid-grep-120k-tail-v2",
        "primary_method": "grep",
        "fallback_method": "tail",
        "router_version": "v2",
        "routing_rule": {"budget_tokens": 120000},
    }
    sel, reason = route(primary_row=primary, intermediate_row=None, fallback_row=fallback,
                         config=v2_config)
    assert sel == "tail" and reason == "primary_too_large_used_fallback", (sel, reason)
    print("PASS test_v2_two_way_routing_unchanged")


def test_intermediate_missing_output_byte_size_fails_closed():
    """Per Codex 2026-05-09-#2 [high]: when intermediate manifest row
    is missing `output_byte_size`, the previous code coerced None → 0
    tokens and silently routed to the intermediate (passing any budget
    gate trivially). Fix: treat missing size as provider-error so the
    router falls through to fallback.

    Repro from Codex review: a stale rtk-err-cat manifest row with no
    output_byte_size and no provider_error was routing to rtk-err-cat
    with context_tokens=0 even though the underlying file was over
    budget. Post-fix: must route to tail."""
    primary = make_row("grep", ctx_bytes=chars(160000))
    # Synthetic intermediate row with NO output_byte_size — simulates a
    # stale or partially regenerated rtk-err-cat manifest.
    intermediate = {
        "case_id": "synthetic",
        "method": "rtk-err-cat",
        "context_path": "results/x.txt",
        # output_byte_size deliberately absent
        "metadata": {},
    }
    fallback = make_row("tail", ctx_bytes=chars(1000))
    sel, reason = route(primary_row=primary, intermediate_row=intermediate, fallback_row=fallback)
    assert sel == "tail" and reason == "intermediate_provider_error_used_fallback", (sel, reason)
    print("PASS test_intermediate_missing_output_byte_size_fails_closed")


def test_primary_missing_output_byte_size_fails_closed():
    """Same fail-closed semantics on the primary row: if grep manifest
    row is missing output_byte_size, treat as primary provider-error
    rather than 0-token grep that trivially fits the budget."""
    # Synthetic primary row with NO output_byte_size
    primary = {
        "case_id": "synthetic",
        "method": "grep",
        "context_path": "results/x.txt",
        "metadata": {},
    }
    intermediate = make_row("rtk-err-cat", ctx_bytes=chars(50000))
    fallback = make_row("tail", ctx_bytes=chars(1000))
    sel, reason = route(primary_row=primary, intermediate_row=intermediate, fallback_row=fallback)
    # Primary is unavailable (provider-error from missing size), so the
    # router takes the "primary provider error" path → fallback.
    assert sel == "tail" and reason == "primary_provider_error_used_fallback", (sel, reason)
    print("PASS test_primary_missing_output_byte_size_fails_closed")


def test_hybrid_provider_error_propagates_through_run_diagnosis():
    """Per Codex 2026-05-10 [high] end-to-end fix: when the hybrid
    router can't select any context (e.g. primary missing + fallback
    missing), it emits an UNAVAILABLE placeholder + a method_row with
    metadata.provider_error set. Pre-fix, run_diagnosis happily
    evaluated the placeholder and produced a normal low-quality
    diagnosis row with provider_error=null — hiding the data failure
    behind a low sv1.1 score. Post-fix, run_diagnosis MUST detect the
    upstream provider_error and emit a provider-error diagnosis row
    with a context_provider_error message propagated.
    """
    import subprocess, os
    rd_tool = ROOT / "tools" / "run_diagnosis.py"

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        cases_dir = tmp / "cases"
        results_dir = tmp / "results"
        split = "synthetic_split"

        # Build a minimal case (enough for load_safe_case_metadata)
        case_id = "synthetic-provider-error-case"
        case_dir = cases_dir / split / case_id
        case_dir.mkdir(parents=True)
        (case_dir / "raw.log").write_text("synthetic raw log\n")
        (case_dir / "case.json").write_text(json.dumps({
            "case_id": case_id, "repo": "x/y", "framework": "generic",
            "source": "github_actions", "failure_category": "unknown",
            "raw_log_path": "raw.log", "line_count": 1, "byte_size": 20,
            "workflow_name": "x", "job_name": "y", "notes": "synthetic",
        }))
        (case_dir / "ground_truth.json").write_text(json.dumps({
            "root_cause": {"summary": "x", "category": "unknown"},
            "required_signals": [],
            "relevant_files": [], "relevant_tests": [],
            "evidence_spans": [],
            "expected_diagnosis": {"must_mention": [], "must_not_claim": []},
        }))
        (case_dir / "tags.json").write_text(json.dumps({
            "case_id": case_id, "split": split, "origin": "new_v2",
            "ecosystem": "generic-github-actions", "primary_language": "x",
            "ci_provider": "github_actions", "repo_visibility": "public",
            "failure_category": "unknown", "framework": "generic",
            "log_size_bucket": "small", "signal_position": "late",
            "evidence_formats": ["shell_command_output"],
            "noise_profile": ["runner_setup"],
            "multi_failure": False, "flaky_or_transient": False,
            "requires_repo_context": False, "diagnosis_difficulty": "easy",
            "notes": "synthetic test fixture",
        }))

        # Hybrid method_output row with provider_error set + the
        # placeholder context file the router would have written.
        method = "synthetic-hybrid"
        method_dir = results_dir / split / method
        method_dir.mkdir(parents=True)
        ctx_path = method_dir / f"{case_id}.txt"
        ctx_path.write_text(
            "UNAVAILABLE: hybrid router could not select a context.\n"
            "selected_reason: primary_missing_provider_error\n"
        )
        manifest = results_dir / split / f"{method}.jsonl"
        # run_diagnosis resolves context_path against ROOT, so to make
        # the test self-contained without polluting the real repo we
        # write absolute paths and rely on Path's behavior of preserving
        # absolutes when joined.
        method_row = {
            "case_id": case_id,
            "method": method,
            "mode": "context_provider",
            "raw_log_path": str(cases_dir / split / case_id / "raw.log"),
            "context_path": str(ctx_path),
            "input_line_count": 1, "output_line_count": 2,
            "input_byte_size": 20, "output_byte_size": ctx_path.stat().st_size,
            "reduction_ratio": 0.0,
            "included_line_ranges": [], "line_mapping_available": False,
            "metadata": {
                "hybrid": True, "router_version": "synthetic",
                "selected_method": None,
                "selected_reason": "primary_missing_provider_error",
                "provider_error": "hybrid: primary_missing_provider_error; primary=grep fallback=tail",
            },
        }
        manifest.write_text(json.dumps(method_row) + "\n")

        env = {k: v for k, v in os.environ.items()
                if k in ("PATH", "PYTHONPATH", "HOME")}
        r = subprocess.run(
            ["python3", str(rd_tool),
             "--split", split, "--diagnoser", "mock",
             "--cases-dir", str(cases_dir),
             "--results-dir", str(results_dir),
             "--context-method", method],
            capture_output=True, text=True, cwd=ROOT, env=env,
        )
        assert r.returncode == 0, (
            f"run_diagnosis exited {r.returncode}\nstderr: {r.stderr}"
        )

        diag_dir = results_dir / split / "diagnoses"
        diag_files = list(diag_dir.rglob(f"{method}.jsonl"))
        assert diag_files, f"diagnosis manifest not written under {diag_dir}"
        diag_rows = [json.loads(l) for l in diag_files[0].read_text().splitlines() if l.strip()]
        assert len(diag_rows) == 1, f"expected 1 row, got {len(diag_rows)}"
        diag_row = diag_rows[0]
        # Post-fix: provider_error must be propagated.
        pe = diag_row.get("metadata", {}).get("provider_error") or diag_row.get("provider_error")
        assert pe, (f"provider_error not propagated; diag_row metadata="
                    f"{diag_row.get('metadata')}")
        assert "context_provider_error" in pe, (
            f"provider_error doesn't reference upstream cause: {pe!r}"
        )
        ok = (diag_row.get("root_cause_category") == "unknown"
                and (diag_row.get("confidence") or 0.0) == 0.0)
        assert ok, f"expected unknown/0.0 placeholder body, got {diag_row}"
        print("PASS test_hybrid_provider_error_propagates_through_run_diagnosis")


# === Main ===

def main() -> int:
    tests = [
        test_primary_fits_budget,
        test_intermediate_fits_when_primary_too_large,
        test_intermediate_too_large_falls_back_to_tail,
        test_intermediate_truncated_falls_back_to_tail,
        test_intermediate_provider_error_falls_back,
        test_intermediate_missing_falls_back,
        test_v2_two_way_routing_unchanged,
        test_intermediate_missing_output_byte_size_fails_closed,
        test_primary_missing_output_byte_size_fails_closed,
        test_hybrid_provider_error_propagates_through_run_diagnosis,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    if failed:
        print(f"\n{failed} of {len(tests)} tests FAILED")
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
