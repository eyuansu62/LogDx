# CILogBench v2 — Case Intake Queue

> Companion to [`cilogbench_v2_case_matrix.md`](cilogbench_v2_case_matrix.md),
> [`cilogbench_v2_collection_guidelines.md`](cilogbench_v2_collection_guidelines.md),
> and the E10 Phase 2 plan
> (`/Users/eyuansu62/Downloads/cilogbench_e10_phase2_case_import_annotation_plan.md`).
>
> This is the rolling worklist of v2 candidate logs. One row per
> candidate, with the most recent on top. Update **every time** a
> candidate moves between statuses; the matrix tracker (§12 of the
> case matrix) reads aggregate counts from this queue.

## Status vocabulary

```text
needs_audit         raw log captured; privacy audit not yet run
needs_import        audit clean (or hits redacted); ready for
                    import_case_skeleton.py
needs_annotation    skeleton written; ground_truth.json + tags.json
                    not yet filled
needs_review        annotation drafted; raw sanity not yet run
raw_sanity_failed   raw-method signal recall < 100%; needs annotation
                    fix or rejection
accepted            in cases/v2/<split>/<case_id>/, validators clean,
                    raw sanity = 100%
rejected            see cases/v2/_rejected/<candidate_id>/rejection_reason.md
```

## Intake queue

| Candidate ID | Source | Repo | Ecosystem | Failure type guess | Log path/URL | Status | Notes |
|---|---|---|---|---|---|---|---|
| pnpm-jest-config-v2-001 | github_actions | pnpm/pnpm | javascript-pnpm-yarn-npm | test_assertion | [run 25437799581 / job 74621031900](https://github.com/pnpm/pnpm/actions/runs/25437799581/job/74621031900) | accepted | `cases/v2/dev/`. Privacy audit clean. Single jest assertion failure in test/config/get.ts:32. Raw sanity 1.0000 / 1.0000 / 1.0000 (signal / critical / evidence span). AI-drafted ground truth, human-verified item-by-item via 17-point checklist. Selected as Batch 1 case 1 — category gap noted (test_assertion vs Batch 1's suggested dependency_install). |
| pip-pytest-network-github-v2-001 | github_actions | pypa/pip | python-pytest | network_or_flaky | [run 25304420764 / job 74177317281](https://github.com/pypa/pip/actions/runs/25304420764/job/74177317281) | accepted | `cases/v2/dev/`. Privacy audit clean. Pytest functional test failed because GitHub returned 502 errors when pip downloaded a test fixture; surface is `AssertionError: Script returned code: 1` but root cause is network. flaky_or_transient = true (3 rerun before final fail). Raw sanity 1.0000 / 1.0000 / 1.0000. AI-drafted, human-verified via 19-point checklist. Selected as Batch 1 case 2 — fills two v1.3 gaps (network_or_flaky and flaky_or_transient were both 0/16 in v1.3). |
| moby-buildx-bake-v2-001 | github_actions | moby/buildkit | docker-buildkit | docker_build | [run 25457465464 / job 74691198803](https://github.com/moby/buildkit/actions/runs/25457465464/job/74691198803) | accepted | `cases/v2/dev/`. Privacy audit found 1 hit at L3814 (AKIA + signature + akamai hmac in a presigned-S3-URL inside a `level=debug fetch failed` line); redacted in place; re-audit clean. `buildx bake` failed at Dockerfile:336 (`RUN wget https://github.com/dragonflyoss/nydus/...` got HTTP 502). flaky_or_transient = true. signal_position = **middle** (failure at L1901 of 3979 ≈ 48%) — exposes tail-200 blind spot. Raw sanity 1.0000 / 1.0000 / 1.0000. Fills v1.3 docker_build gap (was 0/16). First case using v2 schema's `docker_build_output`, `repo_visibility=redacted`, and middle signal_position in v2. |
| gh-cli-go-test-prompter-v2-001 | github_actions | cli/cli | go | test_assertion | [run 25420916282 / job 74562623100](https://github.com/cli/cli/actions/runs/25420916282/job/74562623100) | accepted | `cases/v2/holdout/`. Privacy audit clean. Single Go test failure on macos-latest only: `TestHuhPrompterMultiSelectWithSearchPersistence/selections_persist_after_changing_search_query` with `form.Run() did not complete in time` (huh_prompter_test.go:478). flaky_or_transient = true (macOS timing flake). signal_position = **middle** (FAIL block at L243-247 of 545 ≈ 45%) — primary diagnostic OUTSIDE tail-200's window. Raw sanity 1.0000 / 1.0000 / 1.0000. Fills v1.3 `go` ecosystem gap (was 0/16). Selected as Batch 2 case 1. |
| pnpm-audit-vuln-ip-address-v2-001 | github_actions | pnpm/pnpm | javascript-pnpm-yarn-npm | dependency_install | [run 25434456587 / job 74608664628](https://github.com/pnpm/pnpm/actions/runs/25434456587/job/74608664628) | accepted | `cases/v2/holdout/`. Privacy audit clean. `pnpm audit` reported 1 moderate-severity CVE (XSS in transitive dep `ip-address`, GHSA-v2v4-37r5-5v8g; vulnerable <=10.1.0, patched >=10.1.1). Smallest v2 log so far (158 lines). First v2 case using `ascii_table` evidence format heavily. Raw sanity 1.0000 / 1.0000 / 1.0000. Adds another dependency_install case (v1.3 had 1/16 → v2 has 2). Selected as Batch 2 case 2 (deviation: audit/security gate vs. literal install failure). |
| biome-pnpm-not-found-v2-001 | github_actions | biomejs/biome | rust-cargo | github_actions_config | [run 25469302190 / job 74729494217](https://github.com/biomejs/biome/actions/runs/25469302190/job/74729494217) | accepted | `cases/v2/holdout/`. Privacy audit clean. Workflow runs `just gen-all` → `pnpm format` but `pnpm` is not installed in the runner (`sh: 1: pnpm: not found`, exit 127). 5-line failure block (L15763-15767) at the end of a 15802-line log; bulk is cargo-binstall enumerating 200+ Rust crates. Raw sanity 1.0000 / 1.0000 / 1.0000. Adds github_actions_config case (v1.3 had 1/16 → v2 has 2). Selected as Batch 2 case 3 (deviation: github_actions_config rather than snapshot diff or timeout/OOM — those are harder to surface via run-list browsing without targeted searches). |
| prettier-jest-snapshot-babel-v2-001 | github_actions | prettier/prettier | javascript-jest | snapshot_or_golden_diff | [run 25139423427 / job 73685543084](https://github.com/prettier/prettier/actions/runs/25139423427/job/73685543084) | accepted | `cases/v2/holdout/`. Privacy audit clean. renovate/babel branch broke 13 jest snapshots across 3 test suites because babel changed `import()` parser-error wording. multi_failure=true, signal_position=**scattered** (first FAIL at L399 ≈17%, summary at L2247 ≈98%; span ≈81%). First v2 case with `snapshot_or_golden_diff` category (fills v1.3 gap, was 0/16) and dominant `snapshot_diff` evidence format. Raw sanity 1.0000 / 1.0000 / 1.0000. Selected as Batch 2 case 4. |
| pandas-cpp-xsimd-neon64-v2-001 | github_actions | pandas-dev/pandas | c-cpp-cmake | compile_error | [run 25463397447 / job 74710897960](https://github.com/pandas-dev/pandas/actions/runs/25463397447/job/74710897960) | accepted | `cases/v2/holdout/` (5/4 — slightly over-target; v2/stress reserved for truly difficult cases). Privacy audit clean. C++ template-instantiation compile error: `extern template ... operator()<xsimd::neon64>` at moments_simd.hpp:255 doesn't match the primary template's `xsimd::neon` parameter at line 182. clang++ rejects with `error: explicit instantiation of 'operator()' does not refer to a function template`. Two compile units share one root cause; meson+ninja stops, pip metadata-generation fails. macOS-15 / arm64 / Python 3.12 / clang++ -std=c++20. Adds compile_error case (v1.3: 1/16 → 2 in v2), c-cpp-cmake ecosystem (v1.3: 0/16 → 1), primary_language=cpp (first). Raw sanity 1.0000 / 1.0000 / 1.0000. Selected as Batch 2 case 5 (deviation: compile_error rather than originally-targeted timeout/OOM, which is hard to surface via run-list browsing). |
| numpy-pytest-segfault-argsort-v2-001 | github_actions | numpy/numpy | python-pytest | test_assertion (panic) | [run 25480154290 / job 74762267261](https://github.com/numpy/numpy/actions/runs/25480154290/job/74762267261) | accepted | `cases/v2/stress/` — **first stress case**. Privacy audit clean (complete). Process-crash failure: `Fatal Python error: Segmentation fault` inside `test_datetime_nat_argsort_stability` (test_datetime.py:226 → fromnumeric.py:1231 in argsort) on the `reverse-sorts` perf branch. Pytest faulthandler dumps stack and exits 245. log_size_bucket=large (5553 lines). signal_position=late. requires_repo_context=true (log identifies WHERE the crash is but cannot prove WHY without C source). Different evidence shape from any v1.3 / prior v2 case (no assertion diff, no FAIL marker, no compile error block). Raw sanity 1.0000 / 1.0000 / 1.0000. Selected as Batch 3 case 1 — fills the v2/stress 'unusual evidence format' criterion with process-crash. |
| cpython-tcl-windows-matrix-v2-001 | github_actions | python/cpython | python-pytest | matrix_or_monorepo_failure | [run 25473514383 / job 74742066692](https://github.com/python/cpython/actions/runs/25473514383/job/74742066692) | accepted | `cases/v2/stress/`. Privacy audit clean (complete). Matrix-shaped: ALL 7 Windows configs fail (x64/Win32/arm64 × default/free-threading × switch-case/tail-call); ALL Linux/macOS variants pass. Branch `update_windows_tcltk` updated bundled tcltk to 9.0.3 → broke Unicode surrogate handling. test_tcl has 2 distinct failures (test_eval_surrogates_in_result test_tcl.py:57 + test_evalfile_surrogates_in_result test_tcl.py:292), both with `AssertionError: '<\\ud83d\\udcbb>' != '<ðŸ’»>'`. multi_failure=true. case.json uses test_assertion (case.schema.json doesn't yet support matrix_or_monorepo_failure); tags.json uses matrix_or_monorepo_failure with 'category mismatch justified' note. log_size_bucket=medium (4349 lines). First v2 case in `matrix_or_monorepo_failure` category (was 0/v2). First v2 use of `matrix_summary` evidence_format. Raw sanity 1.0000 / 1.0000 / 1.0000. Selected as Batch 3 case 2 — completes Phase 2 checkpoint (10/34). |
| rust-compiletest-wasm-exceptions-asm-v2-001 | github_actions | rust-lang/rust | rust-cargo | test_assertion | [run 25456140797 / job 74686149799](https://github.com/rust-lang/rust/actions/runs/25456140797/job/74686149799) | accepted | `cases/v2/stress/`. Privacy audit: 49→0 hits (2 ARTIFACTS/CACHES AWS_ACCESS_KEY_ID values redacted via sha256-prefix tokens; 2 GHA-already-masked AWS_*_KEY env lines stripped); re-audit clean. bors-try job for PR #156253 (rollup of 3 PRs, commit `bce7eda69`). compiletest assembly-llvm test `tests/assembly-llvm/wasm_exceptions.rs` failed under target `wasm32-wasip1` because two FileCheck directives (`// CHECK: catch_all` at L38, `// CHECK: catch` at L62) no longer match the actual emitted .s — rustc/LLVM now emits the new exnref-based wasm EH lowering (`try_table (catch_all_ref 0)` + `unreachable` cleanup) where the test still expected legacy `try`/`catch_all` block instructions. multi_failure=true (2 separate CHECK directives, same root cause). requires_repo_context=true (need test source for full CHECK pattern context). log_size_bucket=large (31110 lines / 2.96 MB — largest v2 raw.log so far; previously largest was biome-pnpm-not-found at 15802). signal_position=late (failure block at L30430-30999 of 31110, ~98%). Raw sanity 1.0000 / 1.0000 / 1.0000. Selected as Batch 4 case 1 — fills v2/stress non-pytest framework gap (was 2/2 pytest, breaks check_split_balance.py framework_dominance flag) and adds rust compiler-toolchain ecosystem to v2/stress. New evidence-format gap surfaced: FileCheck `check:N'M ~~~~` annotation pattern has no matching schema enum; closest fits used: `assertion_diff` + `compiler_diagnostic`. Schema-extension target for v3. repo_visibility=redacted. |
| nodejs-test-debugger-exec-timeout-v2-001 | github_actions | nodejs/node | generic-github-actions | timeout_or_oom | [run 25490868700 / job 74798272222](https://github.com/nodejs/node/actions/runs/25490868700/job/74798272222) | accepted | `cases/v2/stress/`. Privacy audit: 0 hits AFTER splitting 3 overlong gyp libtool linker-command lines (>8000 chars each tripped the audit's per-line cap with fail-closed semantics; content was just verbose linker arg lists, no secrets). nodejs/node Test macOS 77min run, parallel test suite (5175 tests). Single test failure (1 of 5175): `parallel/test-debugger-exec` (test/parallel/test-debugger-exec.js) timed out after 15s in `waitForInitialBreak`. Stack: test/common/debugger.js:116 → 67 → throw at debugger.js:92. Captured debugger output proves connect/attach phase succeeded (`Debugger attached.` + `debug>` prompt visible) — only the `break in` initial-break pattern was missing within the 15s window. flaky_or_transient=true (macOS-arm64 timing flake on debugger break-emission). log_size_bucket=large (10773 lines / 5.1 MB; original 10752 lines, +21 from line-splitting redact). signal_position=late (failure block at L10717-10756 of 10773, ~99%). framework=generic (nodejs's tools/test.py runner — case.schema.json enum lacks a `nodejs-tools-test` value). Raw sanity 1.0000 / 1.0000 / 1.0000. Selected as Batch 4 case 2 — **fills the timeout_or_oom failure_category gap (was 0/v2 → 1)** and first v2 case using the `timeout_marker` evidence_format (`Error: Timeout (15000) while waiting for ...`). primary_language=javascript+framework=generic combo also new for v2 (other v2 JS cases use jest/pnpm). multi_failure=false. requires_repo_context=false. |
| airflow-precommit-tsc-middle-v2-001 | github_actions | apache/airflow | typescript-tsc | type_error | [run 25493092125 / job 74810291973](https://github.com/apache/airflow/actions/runs/25493092125/job/74810291973) | accepted | `cases/v2/stress/`. Privacy audit: 0 hits AFTER splitting 8 overlong lines (verbose pre-commit file enumerations). apache/airflow CI image checks / Static checks job (~37min). Pre-commit's `ts-compile-lint-ui` hook fails because `pnpm tsc --p <tmp tsconfig>` reports 3 TypeScript errors: TS6196 'ColorMode' unused at UserSettingsButton.tsx:55, TS6133 'ParamsSpec' value never read at ConnectionForm.tsx:33, TS2739 Type 'SetupServer' missing #private+network props at testsSetup.ts:78. Wrapped in scripts/ci/prek/ts_compile_lint_ui.py:62 → subprocess.CalledProcessError. Pre-commit then continues running ~30 OTHER hooks (all Pass) before ##[error] step exit. **First non-late v2/stress case** (signal_position=**middle**: failure block at L2069-3492 ≈32-54%, ##[error] at L3762 ≈58% of 6496-line log; ~42% post-failure pre-commit chatter). multi_failure=true (3 distinct TS errors). flaky_or_transient=false. requires_repo_context=false. log_size_bucket=large. Raw sanity 1.0000 / 1.0000 / 1.0000. Selected as **Batch 4 case 3 — deliberately added to break the v2/stress 4/4-late signal_position monoculture** flagged by tools/check_split_balance.py at 12-case state (per Codex adversarial review Finding 2). Phase 3 13-case refresh §3d validates the §3c tail-winner caveat: tail's macro lead over grep shrank from +0.087 to +0.023 Sonnet (74% shrink) with this single addition; per-case tail 0.017 vs grep 0.717 on this airflow log confirms the position-dependent trade-off. |
| spring-boot-checkformat-batch5-v2-001 | github_actions | spring-projects/spring-boot | java-gradle | lint_error | [run 25525927228 / job 74921409232](https://github.com/spring-projects/spring-boot/actions/runs/25525927228/job/74921409232) | accepted | `cases/v2/holdout/`. Privacy audit: 0 hits, complete_scan=True. Spring Boot's `:module:spring-boot-actuator:checkFormatMain` Gradle task failed because `src/main/java/org/springframework/boot/actuate/sbom/SbomProperties.java` has formatting violations. Late signal_position (failure at L6188-6195 of 6275, ≈98%). 6275 lines / 569 KB. Easy diagnosis (file path named at line resolution). **Batch 5 hold-out case 1** — fills v2 java-gradle ecosystem gap; NOT in calibration set used to tune hybrid-v2's 120k threshold. |
| gradle-projecthealth-batch5-v2-001 | github_actions | gradle/gradle | java-gradle | lint_error | [run 25520527023 / job 74903876543](https://github.com/gradle/gradle/actions/runs/25520527023/job/74903876543) | accepted | `cases/v2/holdout/`. Privacy audit: 0 hits, complete_scan=True. Gradle's own contributor build (`Sanity Check on Linux`, ~13min): `:platform-base:projectHealth` task failed because `platforms/software/platform-base/build.gradle.kts` declares `domainObjectCollections` as `api` instead of `implementation`. The projectHealth lint plugin gives the proposed fix at line resolution. Late signal_position (≈99%). 12867 lines / 1.0 MB. Easy diagnosis. **Batch 5 hold-out case 2** — second java-gradle case (Kotlin DSL build script). |
| go-redis-pubsub-channel-timeout-batch5-v2-001 | github_actions | go-redis/redis | go | timeout_or_oom | [run 25511454847 / job 74871031554](https://github.com/go-redis/redis/actions/runs/25511454847/job/74871031554) | accepted | `cases/v2/holdout/`. Privacy audit: 0 hits AFTER redacting TestParseURL fixture URLs (placeholder Go test fixtures matched url_credential regex; redacted to `[REDACTED-TEST-FIXTURE-URL]`) and truncating 2 ginkgo bullet-decoration lines (>8000 chars each). Ginkgo test `PubSub [It] should ChannelMessage` at pubsub_test.go:661 timed out 1.001s waiting for a Redis Pub/Sub channel message. flaky_or_transient=true. signal_position=middle (failure at L1102-1172 ≈42%). 2730 lines / 246 KB. Medium difficulty. repo_visibility=redacted. **Batch 5 hold-out case 3** — Go ecosystem timeout_or_oom (calibration set's nodejs case was JS-side; this validates timeout_or_oom generalizes across ecosystems). |
| argocd-race-conditions-batch5-v2-001 | github_actions | argoproj/argo-cd | go | test_assertion | [run 25534571975 / job 74948102287](https://github.com/argoproj/argo-cd/actions/runs/25534571975/job/74948102287) | accepted | `cases/v2/stress/`. Privacy audit: 0 hits, complete_scan=True (raised tools/audit_context_privacy.py MAX_LINES_PER_FILE 50000→200000 to support huge logs). argo-cd's race-test job (~43min): THREE distinct failures across cmd/argocd/commands (timestamp-flake string-eq), server (TestOIDCRefresh data race), util/db (TestClusterRaceConditionClusterSecrets data race). multi_failure=true. signal_position=**scattered** (failures span L54988→88904 ≈62-99% of log). requires_repo_context=true (race traces need source). **First v2 case in `huge` log_size_bucket (>50000 lines, was 0/29 corpus-wide)** — 89188 lines / 12.3 MB. Hard difficulty. **Batch 5 hold-out case 4** — fills the huge-log corpus gap and adds scattered signal to v2/stress. Hybrid-v2 grep produces 1.86M tokens here so it correctly routes to tail. |
| dubbo-samples-test-timeout-batch6-v2-001 | github_actions | apache/dubbo | java-maven | timeout_or_oom | [run 25539178788 / job 74961870539](https://github.com/apache/dubbo/actions/runs/25539178788/job/74961870539) | accepted | `cases/v2/holdout/`. Privacy audit: 0 hits, complete_scan=True. Apache Dubbo PR integration tests (~37min): test `dubbo-samples-test-11137` timed out, orchestrator tore down docker-compose containers (nacos, mysql, test container). Late signal_position (failure block at L4885-4906 ≈80% of 6095 lines / 587 KB). flaky_or_transient=true. **Batch 6 hold-out case 1 — fills java-maven ecosystem gap (was 0/v2 → 1).** failure_category=timeout_or_oom (third v2 timeout case). Easy diagnosis. |
| hibernate-orm-dbversion-test-batch6-v2-001 | github_actions | hibernate/hibernate-orm | java-gradle | test_assertion | [run 25540559564 / job 74965317180](https://github.com/hibernate/hibernate-orm/actions/runs/25540559564/job/74965317180) | accepted | `cases/v2/holdout/`. Privacy audit: 0 hits, complete_scan=True. Hibernate ORM CI on OpenJDK 25 / hsqldb backend (~81min): `DbVersionTest.testCollectionVersion` failed at hibernate-core/.../DbVersionTest.java:60 with `AssertionFailedError: owner version not incremented ==> expected: <false> but was: <true>`. Late signal_position (failure block at L45536-45543 ≈98% of 46198 lines / 4.4 MB). 46198 lines is just under the huge threshold (50000) — sits in `large` bucket. **Batch 6 hold-out case 2 — third v2 java-gradle case** (after spring-boot-checkformat and gradle-projecthealth). Medium difficulty. |

## Per-batch progress

```text
Batch 1 (target: 3 cases)
  Recommended mix:
    1 java-gradle or java-maven compile/test failure
    1 docker/buildkit failure
    1 dependency install failure (Python or Node)
  Status: 3 / 3 accepted ✓ Batch 1 COMPLETE
    accepted:
      pnpm-jest-config-v2-001 (test_assertion, v2/dev) — 100/100/100
        deviation: test_assertion instead of dependency_install
      pip-pytest-network-github-v2-001 (network_or_flaky, v2/dev) — 100/100/100
        bonus: fills v1.3 network_or_flaky + flaky_or_transient gaps
        (both 0/16). Surface AssertionError hides network root cause.
      moby-buildx-bake-v2-001 (docker_build, v2/dev) — 100/100/100
        bonus: fills v1.3 docker_build gap (was 0/16). signal_position=
        middle exposes tail-200 blind spot. First case using v2 schema's
        docker_build_output, repo_visibility=redacted (1 redaction).
    annotation pattern (all 3): AI draft + human verify item-by-item

Batch 2 (target: +5 cases, 8 total)
  Recommended mix:
    1 go test/build failure                    ✓ accepted (case 4)
    1 node pnpm/yarn/npm dependency failure
    1 timeout/OOM
    1 snapshot/golden diff
    1 matrix/monorepo failure
  Status: 5 / 5 ✓ Batch 2 COMPLETE (8 / 8 total cases)
    accepted:
      gh-cli-go-test-prompter-v2-001 (test_assertion, v2/holdout)
        — 100/100/100 — fills go ecosystem gap; signal_position=middle
      pnpm-audit-vuln-ip-address-v2-001 (dependency_install, v2/holdout)
        — 100/100/100 — first heavy ascii_table case
      biome-pnpm-not-found-v2-001 (github_actions_config, v2/holdout)
        — 100/100/100 — pnpm-not-found in runner image, exit 127
      prettier-jest-snapshot-babel-v2-001 (snapshot_or_golden_diff, v2/holdout)
        — 100/100/100 — fills v1.3 snapshot gap; scattered; multi_failure
      pandas-cpp-xsimd-neon64-v2-001 (compile_error, v2/holdout, 5/4 over)
        — 100/100/100 — fills c-cpp-cmake ecosystem gap; cpp language first
    Batch 2 deviations from original mix:
      timeout/OOM (originally requested) — not yet found via run-list
      matrix/monorepo (originally requested) — not yet found via run-list
      Compensated with: github_actions_config, compile_error
    Carried forward to Batch 3+: timeout/OOM, matrix/monorepo
  v2/holdout: 5 / 4 (slight over-target by 1; documented in case notes)

Batch 3 (target: +2 cases, 10 total — Phase 2 checkpoint)
  Status: 2 / 2 ✓ Phase 2 checkpoint COMPLETE (10 / 34 total cases)
    accepted (Batch 3 case 1):
      numpy-pytest-segfault-argsort-v2-001 (test_assertion / panic,
        v2/stress) — 100/100/100 — first v2/stress case;
        process-crash format; requires_repo_context=true
    accepted (Batch 3 case 2):
      cpython-tcl-windows-matrix-v2-001 (matrix_or_monorepo_failure,
        v2/stress) — 100/100/100 — first v2 case in this category;
        first use of `matrix_summary` evidence_format; multi_failure
        (2 distinct test_tcl tests fail with one root cause).

Batch 4 (target: 3-5 cases, 13-15 total)
  Recommended mix (per reports/legacy/v2_split_balance.md flags):
    1 timeout/OOM (still 0/v2)               ✓ Batch 4 case 2
    1 non-pytest v2/stress                   ✓ Batch 4 case 1
    1 huge log_size_bucket (>50k lines)      ✗ blocked by gh CLI
    optional: non-late signal_position       ✓ Batch 4 case 3
  Status: 3 / 3-5 (13 / 34 total cases)
    accepted (Batch 4 case 1):
      rust-compiletest-wasm-exceptions-asm-v2-001 (test_assertion,
        v2/stress) — 100/100/100 — fills non-pytest v2/stress framework
        gap (rust compiler-toolchain). Largest v2 raw.log so far at
        31110 lines / 2.96 MB.
    accepted (Batch 4 case 2):
      nodejs-test-debugger-exec-timeout-v2-001 (timeout_or_oom,
        v2/stress) — 100/100/100 — **fills timeout_or_oom
        failure_category gap (was 0/v2 → 1)**. flaky_or_transient
        =true (timing-sensitive macOS-arm64 runner).
    accepted (Batch 4 case 3):
      airflow-precommit-tsc-middle-v2-001 (type_error, v2/stress)
        — 100/100/100 — **first non-late v2/stress case**
        (signal_position=middle). Closes the v2/stress 4/4-late
        monoculture flagged at 12-case state. Phase 3 13-case
        refresh validated the §3c tail-winner caveat: Sonnet
        tail-vs-grep gap shrank from +0.087 to +0.023 (74% shrink)
        with this single addition. Per-case airflow log: tail 0.017
        (collapsed) vs grep 0.717 (recovered) — confirms no single
        method wins on both signal positions.
    Carry-overs to Batch 5+: huge log (>50k, still 0/29 corpus-wide
        — needs raw-archive download approach), early signal_
        position (still 0/29), permission_or_secret category in v2
        (still 0/v2).

Batch 5 (target: 4-6 hold-out cases for hybrid-v2 generalization test)
  Recommended mix:
    1+ java-gradle/maven (ecosystem gap)
    1+ huge log_size_bucket (>50k lines, was 0/29)
    optional: permission_or_secret, early signal, scattered signal
    Constraint: must NOT retune hybrid-v2's 120k threshold on any of these
  Status: 4 / 4-6 (17 / 34 total cases)
    accepted (Batch 5 case 1):
      spring-boot-checkformat-batch5-v2-001 (lint_error,
        v2/holdout) — 100/100/100 — fills java-gradle ecosystem gap;
        late signal; easy diagnosis
    accepted (Batch 5 case 2):
      gradle-projecthealth-batch5-v2-001 (lint_error, v2/holdout)
        — 100/100/100 — second java-gradle case (Gradle self-build,
        Kotlin DSL); late signal; easy
    accepted (Batch 5 case 3):
      go-redis-pubsub-channel-timeout-batch5-v2-001 (timeout_or_oom,
        v2/holdout) — 100/100/100 — Go ecosystem timeout_or_oom
        (validates timeout pattern generalizes across ecosystems);
        middle signal; flaky_or_transient
    accepted (Batch 5 case 4):
      argocd-race-conditions-batch5-v2-001 (test_assertion,
        v2/stress) — 100/100/100 — **fills huge log_size_bucket gap
        (was 0/29 corpus-wide → 1)**; multi_failure (3 tests, 2
        race conditions + 1 timestamp flake); scattered signal_
        position; requires_repo_context=true; hard difficulty;
        89188 lines / 12.3 MB. Audit cap raised 50k→200k to scan.
    Carry-overs to Batch 6+: permission_or_secret in v2 (still 0/v2),
        early signal_position (still 0/29 corpus-wide), more huge logs
        for variety.

Batch 6 (target: 3-5 cases as second hybrid-v2 hold-out)
  Status: 2 / 3-5 (19 / 34 total cases) — scaled down from 5
    accepted (Batch 6 case 1):
      dubbo-samples-test-timeout-batch6-v2-001 (timeout_or_oom,
        v2/holdout) — 100/100/100 — **fills java-maven ecosystem
        gap (was 0/v2 → 1)**. Apache Dubbo PR integration test
        timeout under docker-compose. flaky_or_transient=true;
        late signal.
    accepted (Batch 6 case 2):
      hibernate-orm-dbversion-test-batch6-v2-001 (test_assertion,
        v2/holdout) — 100/100/100 — third v2 java-gradle case.
        Single test failure (DbVersionTest.testCollectionVersion)
        in a 46198-line log; late signal at ≈98%.
    Hold-out result on Batch 6 (no retuning of hybrid-v2):
      Sonnet hybrid-v2 0.9000 #1 vs grep 0.8875 (+0.012)
      Haiku hybrid-v2 0.7625 #2 behind grep 0.8000
      Combined B5+B6 (6 cases): hybrid-v2 stays #1 on Sonnet
      (0.6838 vs grep 0.6494); on Haiku tied with grep (both 0.6053)
    §3e CLI-flake reproduces a third time on Batch 6 dubbo
      (Haiku hybrid-v2 0.60 vs Haiku grep 0.75).
    Carry-overs to Batch 7+: permission_or_secret (still 0/v2),
        kubernetes-helm/terraform (still 0/v2), OOM-killed (still
        0/v2), early signal (still 0/35 corpus-wide). These were
        the remaining Batch 6 plan targets — punted because
        run-list browsing did not surface them in budget.
```

## Rejection counter

Rolling count of rejections by reason — aggregate signal for
collection bias. Per-candidate rejection memos live at
`cases/v2/_rejected/<candidate_id>/rejection_reason.md`.

```text
duplicate_of_existing_case:        0
insufficient_evidence_in_log:      0
cannot_be_safely_redacted:         0
not_a_real_failure:                0
category_outside_target_matrix:    0
ecosystem_already_at_target:       0
source_unauthorized:               0
flaky_unreproducible_signal:       0
```

## Tooling cheatsheet

```bash
# Pre-import: privacy audit on a raw log captured under _incoming/.
python3 tools/audit_context_privacy.py \
  --raw-log cases/v2/_incoming/<candidate_id>/raw.log
# Exit 0 = clean. Exit 2 = hits found; redact and rerun.

# Import skeleton into the chosen split.
python3 tools/import_case_skeleton.py \
  --split v2/<split> \
  --case-id <case_id> \
  --raw-log cases/v2/_incoming/<candidate_id>/raw.log \
  --repo owner/repo \
  --framework <framework> \
  --workflow-name "<workflow>" \
  --job-name "<job>"

# After hand-editing ground_truth.json + tags.json:
python3 tools/validate_cases.py cases/v2/<split>
python3 tools/validate_case_tags.py --split v2/<split>

# Raw sanity gate.
python3 tools/run_baseline.py --method raw --split v2/<split>
python3 tools/evaluate_signal_recall.py --method raw --split v2/<split>
# Required: raw signal recall = 100%.
```
