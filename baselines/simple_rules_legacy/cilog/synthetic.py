"""
Synthetic CI log samples. These mimic real GitHub Actions output closely enough
to validate the compression pipeline end-to-end without hitting the GitHub API.

They're also useful for regression testing (expected behavior documented inline).
"""

from __future__ import annotations


def _gha_prefix(line: str) -> str:
    # Real GHA logs prefix every line with an ISO timestamp
    return f"2024-03-15T10:23:45.1234567Z {line}"


def _wrap_gha(lines: list[str]) -> str:
    return "\n".join(_gha_prefix(l) for l in lines)


# ============================================================================
# Sample 1: pytest with 2 failing tests + 400 passing tests + tons of collected
# ============================================================================

def pytest_sample() -> str:
    lines = []
    lines.append("##[group]Run pytest")
    lines.append("\x1b[1mpytest --verbose\x1b[0m")
    lines.append("============================= test session starts ==============================")
    lines.append("platform linux -- Python 3.11.4, pytest-7.4.0, pluggy-1.3.0")
    lines.append("rootdir: /home/runner/work/myproject/myproject")
    lines.append("plugins: cov-4.1.0, xdist-3.3.1, anyio-3.7.1")
    lines.append("collected 402 items")
    lines.append("")
    # 400 passing lines
    for i in range(400):
        lines.append(f"tests/test_module_{i // 40}.py::test_feature_{i} \x1b[32mPASSED\x1b[0m [{(i+1)*100//402:>3d}%]")
    # Two failures
    lines.append(f"tests/test_auth.py::test_token_expiry \x1b[31mFAILED\x1b[0m [ 99%]")
    lines.append(f"tests/test_billing.py::test_refund_idempotent \x1b[31mFAILED\x1b[0m [100%]")
    lines.append("")
    lines.append("=================================== FAILURES ===================================")
    lines.append("____________________________ test_token_expiry ____________________________")
    lines.append("")
    lines.append("    def test_token_expiry():")
    lines.append("        token = generate_token(ttl=3600)")
    lines.append("        time.sleep(0.1)")
    lines.append(">       assert validate(token).is_valid is True")
    lines.append("E       AssertionError: assert False is True")
    lines.append("E        +  where False = <TokenResult valid=False expired=True>.is_valid")
    lines.append("")
    lines.append("tests/test_auth.py:42: AssertionError")
    lines.append("_______________________ test_refund_idempotent _________________________")
    lines.append("")
    lines.append("    def test_refund_idempotent():")
    lines.append("        charge = create_charge(amount=1000)")
    lines.append("        r1 = refund(charge.id)")
    lines.append(">       r2 = refund(charge.id)")
    lines.append("")
    lines.append("tests/test_billing.py:87: ")
    lines.append("_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _")
    lines.append("")
    lines.append("    def refund(charge_id):")
    lines.append("        if _refunded.get(charge_id):")
    lines.append(">           raise DuplicateRefundError(charge_id)")
    lines.append("E           myapp.errors.DuplicateRefundError: ch_abc123")
    lines.append("")
    lines.append("src/myapp/billing.py:117: DuplicateRefundError")
    lines.append("=========================== short test summary info ============================")
    lines.append("FAILED tests/test_auth.py::test_token_expiry - AssertionError: assert False is True")
    lines.append("FAILED tests/test_billing.py::test_refund_idempotent - myapp.errors.DuplicateRefundError: ch_abc123")
    lines.append("================== 2 failed, 400 passed, 3 warnings in 47.21s ==================")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 1.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 2: jest with progress bars, ANSI, flaky snapshot
# ============================================================================

def jest_sample() -> str:
    lines = []
    lines.append("##[group]Run npm test")
    lines.append("npm test")
    lines.append("")
    lines.append("> myapp@1.0.0 test")
    lines.append("> jest --ci --coverage --maxWorkers=4")
    lines.append("")
    # Fake progress noise
    for i in range(50):
        lines.append(f"\r\x1b[0KDetermining test suites to run... [{i*2}%]")
    lines.append("")
    # Lots of passing files
    for path in [
        "src/utils/format.test.ts", "src/utils/parse.test.ts",
        "src/components/Button.test.tsx", "src/components/Modal.test.tsx",
        "src/api/client.test.ts", "src/api/retry.test.ts",
        "src/hooks/useAuth.test.ts", "src/hooks/useDebounce.test.ts",
        "src/pages/home.test.tsx", "src/pages/settings.test.tsx",
    ] * 4:
        lines.append(f"\x1b[32mPASS\x1b[0m  {path} (2.341 s)")
    # One failing file
    lines.append("\x1b[31mFAIL\x1b[0m  src/api/webhook.test.ts (8.721 s)")
    lines.append("  Webhook delivery")
    lines.append("    ✓ retries on 500 (12 ms)")
    lines.append("    ✓ respects retry-after header (8 ms)")
    lines.append("    ✗ deduplicates by idempotency key (2043 ms)")
    lines.append("")
    lines.append("  ● Webhook delivery › deduplicates by idempotency key")
    lines.append("")
    lines.append("    expect(received).toBe(expected) // Object.is equality")
    lines.append("")
    lines.append("    Expected: 1")
    lines.append("    Received: 2")
    lines.append("")
    lines.append("      47 |   const key = crypto.randomUUID();")
    lines.append("      48 |   await deliver(event, { idempotencyKey: key });")
    lines.append("    > 49 |   expect(mockServer.calls.length).toBe(1);")
    lines.append("         |                                   ^")
    lines.append("      50 | });")
    lines.append("")
    lines.append("      at src/api/webhook.test.ts:49:39")
    lines.append("      at node_modules/@jest/expect/build/index.js:133:12")
    lines.append("      at node_modules/jest-jasmine2/build/queueRunner.js:45:7")
    lines.append("")
    lines.append("Test Suites: 1 failed, 40 passed, 41 total")
    lines.append("Tests:       1 failed, 203 passed, 204 total")
    lines.append("Snapshots:   0 total")
    lines.append("Time:        52.114 s")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 1.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 3: cargo build + test, compile error at the end
# ============================================================================

def cargo_sample() -> str:
    lines = []
    lines.append("##[group]cargo build")
    lines.append("cargo build --release --all-features")
    lines.append("    Updating crates.io index")
    for crate in [
        "syn", "quote", "proc-macro2", "serde", "serde_json", "tokio",
        "hyper", "reqwest", "clap", "anyhow", "thiserror", "regex",
        "tracing", "tracing-subscriber", "futures", "async-trait",
    ]:
        lines.append(f"    Compiling {crate} v1.2.3")
    for _ in range(80):
        lines.append("    Compiling myapp v0.1.0 (/home/runner/work/myapp/myapp)")
    lines.append("error[E0308]: mismatched types")
    lines.append("   --> src/pipeline/executor.rs:142:28")
    lines.append("    |")
    lines.append("140 |       async fn run(&self, cfg: Config) -> Result<Report, ExecError> {")
    lines.append("141 |           let handle = self.spawn(cfg.clone()).await?;")
    lines.append("142 |           let report = handle.collect().await;")
    lines.append("    |                        ^^^^^^^^^^^^^^^^^^^^^^ expected `Result<Report, ExecError>`, found `Report`")
    lines.append("    |")
    lines.append("    = note: consider wrapping with `Ok(...)`")
    lines.append("")
    lines.append("error: could not compile `myapp` (bin \"myapp\") due to 1 previous error")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 101.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 4: npm install noise dominates, build passes, flaky E2E fails
# ============================================================================

def mixed_playwright_sample() -> str:
    lines = []
    # --- npm install: lots of noise ---
    lines.append("##[group]Install dependencies")
    lines.append("npm ci")
    for _ in range(200):
        lines.append("npm warn deprecated inflight@1.0.6: This module is not supported and leaks memory.")
    for _ in range(150):
        lines.append("npm warn deprecated glob@7.2.3: Glob versions prior to v9 are no longer supported")
    lines.append("")
    lines.append("added 1847 packages, and audited 1848 packages in 47s")
    lines.append("298 packages are looking for funding")
    lines.append("  run `npm fund` for details")
    lines.append("found 0 vulnerabilities")
    lines.append("##[endgroup]")

    # --- build: passes ---
    lines.append("##[group]Build")
    lines.append("npm run build")
    for i in range(60):
        lines.append(f"\r\x1b[0K[{i*2:>3d}%] webpack compiling... {i*12} modules")
    lines.append("")
    lines.append("webpack 5.89.0 compiled successfully in 47832 ms")
    lines.append("##[endgroup]")

    # --- playwright: one test fails, lots of base64 screenshots ---
    lines.append("##[group]Run playwright test")
    lines.append("npx playwright test")
    lines.append("")
    lines.append("Running 34 tests using 4 workers")
    for i in range(30):
        lines.append(f"  \x1b[32m✓\x1b[0m  [chromium] › e2e/smoke.spec.ts:{i+1}:1 › loads homepage ({300 + i*10}ms)")
    lines.append("  \x1b[31m✘\x1b[0m  [chromium] › e2e/checkout.spec.ts:82:1 › completes payment flow (45s)")
    lines.append("")
    lines.append("  1) [chromium] › e2e/checkout.spec.ts:82:1 › completes payment flow")
    lines.append("")
    lines.append("    TimeoutError: locator.click: Timeout 30000ms exceeded.")
    lines.append("    Call log:")
    lines.append("      - waiting for locator('button[data-testid=\"submit-order\"]')")
    lines.append("      - locator resolved to <button disabled data-testid=\"submit-order\">Place order</button>")
    lines.append("      - attempting click action")
    lines.append("      - waiting for element to be visible, enabled and stable")
    lines.append("      - element is not enabled")
    lines.append("")
    lines.append("      at e2e/checkout.spec.ts:101:32")
    # Fake giant screenshot base64 blob
    lines.append("    attachment #1: screenshot.png (image/png) ────────────────────")
    huge_blob = "iVBORw0KGgoAAAANSUhEUgAAB4AAAASwCAYAAABOk" * 200
    lines.append("    " + huge_blob)
    lines.append("    ─────────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("  33 passed (58s)")
    lines.append("  1 failed")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 1.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 5: docker build with lots of cached layers
# ============================================================================

def docker_sample() -> str:
    lines = []
    lines.append("##[group]Docker build")
    lines.append("docker buildx build --platform linux/amd64,linux/arm64 -t myapp:ci .")
    lines.append("#1 [internal] load build definition from Dockerfile")
    lines.append("#1 DONE 0.0s")
    lines.append("#2 [internal] load .dockerignore")
    lines.append("#2 DONE 0.0s")
    for i in range(3, 22):
        lines.append(f"#{i} [build {i-2}/19] RUN --mount=type=cache,target=/root/.cache/go-build go build ./...")
        lines.append(f"#{i} CACHED")
        lines.append(f"#{i} DONE 0.1s")
    lines.append("#23 [runtime 5/6] COPY --from=build /app/bin /usr/local/bin/")
    lines.append("#23 ERROR: failed to calculate checksum of ref: \"/app/bin\": not found")
    lines.append("")
    lines.append("------")
    lines.append(" > [runtime 5/6] COPY --from=build /app/bin /usr/local/bin/:")
    lines.append("------")
    lines.append("Dockerfile:47")
    lines.append("--------------------")
    lines.append("  45 | ")
    lines.append("  46 |     FROM alpine:3.19 AS runtime")
    lines.append("  47 | >>> COPY --from=build /app/bin /usr/local/bin/")
    lines.append("  48 |     EXPOSE 8080")
    lines.append("  49 |     ENTRYPOINT [\"myapp\"]")
    lines.append("--------------------")
    lines.append("ERROR: failed to solve: failed to compute cache key: \"/app/bin\" not found")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 1.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 6: go test with lots of successful packages + race detector failure
# ============================================================================

def go_test_sample() -> str:
    lines = []
    lines.append("##[group]go test -race ./...")
    lines.append("go test -race -coverprofile=coverage.out ./...")
    for pkg in [
        "github.com/acme/service/internal/auth",
        "github.com/acme/service/internal/config",
        "github.com/acme/service/internal/db",
        "github.com/acme/service/internal/handlers",
        "github.com/acme/service/internal/middleware",
        "github.com/acme/service/pkg/logger",
        "github.com/acme/service/pkg/metrics",
    ]:
        lines.append(f"ok  \t{pkg}\t1.234s\tcoverage: 87.3% of statements")
    lines.append("==================")
    lines.append("WARNING: DATA RACE")
    lines.append("Read at 0x00c00012c050 by goroutine 13:")
    lines.append("  github.com/acme/service/internal/cache.(*Cache).Get()")
    lines.append("      /home/runner/work/service/service/internal/cache/cache.go:87 +0x4a")
    lines.append("  github.com/acme/service/internal/cache_test.TestConcurrentGet.func1()")
    lines.append("      /home/runner/work/service/service/internal/cache/cache_test.go:142 +0x5b")
    lines.append("")
    lines.append("Previous write at 0x00c00012c050 by goroutine 12:")
    lines.append("  github.com/acme/service/internal/cache.(*Cache).Set()")
    lines.append("      /home/runner/work/service/service/internal/cache/cache.go:103 +0x8c")
    lines.append("==================")
    lines.append("--- FAIL: TestConcurrentGet (0.42s)")
    lines.append("    testing.go:1446: race detected during execution of test")
    lines.append("FAIL")
    lines.append("FAIL\tgithub.com/acme/service/internal/cache\t0.527s")
    lines.append("FAIL")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 1.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 7: mypy pre-commit hook with a wall of type errors (pandas-style)
# ============================================================================
# Captures the pattern that broke real-world pandas runs: a single GHA section
# containing 80+ "path/file.py:N: error: ... [tag]" lines from mypy/stubtest.
# The "error:" token appears in the middle of the line, not at start — so
# the original compressor's failure-signal regexes did not fire on these lines,
# and compress_generic dropped most of them into a `[... N lines elided ...]`.

def mypy_stubtest_sample() -> str:
    lines = []
    lines.append("##[group]Run pre-commit")
    lines.append("pre-commit run --all-files --hook-stage manual")
    lines.append("")
    # Some passing hooks first
    for hook in ["black", "isort", "pyupgrade", "flake8", "ruff"]:
        lines.append(f"{hook}" + "." * (72 - len(hook)) + "Passed")
    lines.append("")
    lines.append("mypy (stubtest)" + "." * 57 + "Failed")
    lines.append("- hook id: stubtest")
    lines.append("- duration: 72.61s")
    lines.append("- exit code: 1")
    lines.append("error: not checking stubs due to mypy build errors:")
    # A wall of mypy errors — the exact pattern that broke pandas.
    files_and_attrs = [
        ("myproj/compat/backend.py", [
            (69, "Call to untyped function \"fill_null\" in typed context", "no-untyped-call"),
            (76, "Module has no attribute \"is_null\"", "attr-defined"),
            (78, "Module has no attribute \"if_else\"", "attr-defined"),
            (79, "Module has no attribute \"if_else\"", "attr-defined"),
            (89, "Module has no attribute \"if_else\"", "attr-defined"),
            (91, "Module has no attribute \"is_null\"", "attr-defined"),
        ]),
        ("myproj/arrays/string_backend.py", [
            (110, "Module has no attribute \"utf8_length\"", "attr-defined"),
            (114, "Module has no attribute \"utf8_lower\"", "attr-defined"),
            (117, "Module has no attribute \"utf8_upper\"", "attr-defined"),
            (121, "Module has no attribute \"utf8_trim\"", "attr-defined"),
            (128, "Module has no attribute \"utf8_ltrim\"", "attr-defined"),
            (130, "Module has no attribute \"utf8_rtrim\"", "attr-defined"),
            (134, "Module has no attribute \"match_substring\"", "attr-defined"),
            (140, "Module has no attribute \"starts_with\"", "attr-defined"),
            (145, "Module has no attribute \"ends_with\"", "attr-defined"),
            (150, "Module has no attribute \"find_substring\"", "attr-defined"),
        ]),
        ("myproj/arrays/string_arrow.py", [
            (271, "Module has no attribute \"utf8_capitalize\"", "attr-defined"),
            (352, "Module has no attribute \"is_in\"", "attr-defined"),
            (536, "Module has no attribute \"count_substring_regex\"", "attr-defined"),
            (582, "Module has no attribute \"is_null\"", "attr-defined"),
            (583, "Module has no attribute \"or_kleene\"", "attr-defined"),
            (585, "Module has no attribute \"not_equal\"", "attr-defined"),
        ]),
        ("myproj/strings/accessor.py", [
            (296, "Module has no attribute \"list_value_length\"", "attr-defined"),
            (297, "Module has no attribute \"max\"", "attr-defined"),
            (298, "Module has no attribute \"min\"", "attr-defined"),
            (307, "Module has no attribute \"list_slice\"", "attr-defined"),
            (317, "Module has no attribute \"list_flatten\"", "attr-defined"),
        ]),
        ("myproj/io/feather_format.py", [
            (70,  "Call to untyped function \"write_feather\" in typed context", "no-untyped-call"),
            (160, "Call to untyped function \"read_table\" in typed context", "no-untyped-call"),
        ]),
        ("myproj/tests/reshape/test_get_dummies.py", [
            (30, "Incompatible types in assignment (expression has type \"None\", variable has type Module)", "assignment"),
        ]),
    ]
    total_errors = 0
    for fpath, errs in files_and_attrs:
        for lineno, msg, tag in errs:
            lines.append(f"{fpath}:{lineno}: error: {msg}  [{tag}]")
            total_errors += 1
    lines.append(f"Found {total_errors} errors in {len(files_and_attrs)} files (checked 1458 source files)")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 1.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 8: cargo trybuild-style compile-fail test output (tokio-style)
# ============================================================================
# The failing tokio sample that broke the cargo compressor. trybuild runs
# tests declared as "should fail to compile" and prints the expected vs
# actual rustc diagnostics inside its own framing — every rustc line gets
# a 4-space indent. The original `^error(?:\[E\d+\])?:` anchor missed these
# entirely and the generic fallback kept only the framing, not the
# diagnostics themselves.

def cargo_trybuild_sample() -> str:
    lines = []
    lines.append("##[group]cargo test --workspace --all-features")
    lines.append("cargo test --workspace --all-features")
    # Plenty of passing output
    for i in range(40):
        lines.append(f"    Compiling myasync v0.1.{i}")
    lines.append("running 6 tests")
    lines.append("    test tests/fail/macros_join.rs [should fail to compile] ... ok")
    lines.append("    test tests/fail/macros_try_join.rs [should fail to compile] ... ok")
    lines.append("    test tests/fail/macros_type_mismatch.rs [should fail to compile] ... mismatch")
    lines.append("")
    lines.append("    EXPECTED:")
    lines.append("    " + "┈" * 60)
    # Indented rustc diagnostics — the pattern we need to catch.
    lines.append("    error[E0308]: mismatched types")
    lines.append("     --> tests/fail/macros_type_mismatch.rs:5:5")
    lines.append("      |")
    lines.append("    5 |     Ok(())")
    lines.append("      |     ^^^^^^ expected `()`, found `Result<(), _>`")
    lines.append("      |")
    lines.append("      = note: expected unit type `()`")
    lines.append("                      found enum `Result<(), _>`")
    lines.append("")
    lines.append("    error[E0271]: expected `{async block@$DIR/tests/fail/macros_type_mismatch.rs:3:1: 3:15}` to be a future that resolves to `()`, but it resolves to `Result<(), _>`")
    lines.append("     --> tests/fail/macros_type_mismatch.rs:3:1")
    lines.append("      |")
    lines.append("    3 | async fn wrong_ok() {")
    lines.append("      | ^^^^^^^^^^^^^^^^^^^^")
    lines.append("      = note: required for the cast from `&{async block@$DIR/tests/fail/macros_type_mismatch.rs:3:1: 3:15}` to `&dyn Future<Output = ()>`")
    lines.append("")
    lines.append("    error[E0271]: expected `{async block@$DIR/tests/fail/macros_type_mismatch.rs:8:1: 8:15}` to be a future that resolves to `Result<(), ()>`, but it resolves to `()`")
    lines.append("     --> tests/fail/macros_type_mismatch.rs:8:1")
    lines.append("")
    lines.append("    error[E0277]: the `?` operator can only be used in an async block that returns `Result` or `Option` (or another type that implements `FromResidual`)")
    lines.append("     --> tests/fail/macros_type_mismatch.rs:13:5")
    lines.append("")
    lines.append("    ACTUAL:")
    lines.append("    " + "┈" * 60)
    lines.append("    (actual output differed from expected)")
    lines.append("")
    lines.append("test result: FAILED. 5 passed; 1 failed; 0 ignored")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 101.")
    return _wrap_gha(lines)


# ============================================================================
# Sample 9: tool-level fatals (git/docker/mount) that aren't "error:" prefixed
# ============================================================================
# The next.js Test Examples sample had `fatal: detected dubious ownership`
# as the root cause. Current failure signals only matched the downstream
# `Git error: fatal: ...` wrapper, not `fatal:` itself, so generic fallback
# kept the wrapper-warning but dropped the actual fatal line.

def tool_fatal_sample() -> str:
    lines = []
    lines.append("##[group]Run setup")
    for i in range(15):
        lines.append(f"  + git config --global --add safe.directory step-{i}")
    lines.append("##[endgroup]")
    lines.append("##[group]Check git status")
    lines.append("+ git status --porcelain")
    lines.append("fatal: detected dubious ownership in repository at '/work'")
    lines.append("To add an exception for this directory, call:")
    lines.append("    git config --global --add safe.directory /work")
    lines.append(" WARNING  failed to get git status for dirty hash: Git error: fatal: detected dubious ownership in repository at '/work'")
    for i in range(40):
        lines.append(f"  resolving dependency tree for example-{i}")
    lines.append("##[endgroup]")
    lines.append("##[error]Process completed with exit code 128.")
    return _wrap_gha(lines)


# ============================================================================
# Registry
# ============================================================================

SAMPLES = {
    "pytest_2fail_400pass": pytest_sample,
    "jest_1fail_40pass":    jest_sample,
    "cargo_type_error":     cargo_sample,
    "playwright_with_install_noise": mixed_playwright_sample,
    "docker_missing_file":  docker_sample,
    "go_test_race":         go_test_sample,
    "mypy_stubtest_wall":   mypy_stubtest_sample,
    "cargo_trybuild_fail":  cargo_trybuild_sample,
    "tool_fatal_noise":     tool_fatal_sample,
}


def all_samples() -> list[tuple[str, str, str, str]]:
    """Returns list of (source, repo, job_name, raw_log) matching collect_samples."""
    out = []
    for name, fn in SAMPLES.items():
        raw = fn()
        out.append((f"synthetic:{name}", "synthetic/fixtures", name, raw))
    return out
