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
  Fill matrix gaps from cilogbench_v2_case_matrix.md §3 / §4 / §5.
  Status: 0 / 2 (paused at 8 cases)
    Hunting attempts that didn't yield clean cases:
      - timeout/OOM in pytorch/ray/elastic/cypress repos (failed runs
        were Dependabot/Copilot reviews, not real CI failures)
      - matrix/monorepo failure (would need targeted search)
      - containerd Windows TestRegressionIssue4769: log too messy
        (single FAIL marker buried in 26K lines of debug noise; no
        explicit error to annotate cleanly)
    Next attempt would need either:
      - Targeted search via specific timeout markers (exit 137,
        OOMKilled, "timed out")
      - A repo with explicit timeout-minutes settings hitting limits
      - Or accept Phase 2 partial at 8 cases and pivot to Phase 3+
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
