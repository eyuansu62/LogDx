# LogDx-CI

> A reproducible benchmark for **failure-context strategies in CI log
> diagnosis**. Does an LLM still have enough evidence to identify the
> root cause after a CI log is filtered, summarized, or compressed?

[![CI](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml/badge.svg)](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/eyuansu62/LogDx?include_prereleases&label=release)](https://github.com/eyuansu62/LogDx/releases/latest)
[![License: Apache-2.0 + CC-BY-4.0](https://img.shields.io/badge/license-Apache--2.0%20%2B%20CC--BY--4.0-blue)](LICENSE)
[![Dataset on HF](https://img.shields.io/badge/data-eyuansu71%2Flogdx--ci-yellow)](https://huggingface.co/datasets/eyuansu71/logdx-ci)
[![Tests](https://img.shields.io/badge/tests-165%20passing-brightgreen)](tools/tests/)

**Current release**: `v2-partial-2026-06-22` — see
[`RELEASE_NOTES.md`](RELEASE_NOTES.md).

LogDx-CI compares 10 context providers — raw, tail, grep, `rtk-*`,
`llm-summary-*`, and hybrid routers — by handing the same CI failure
log to three debuggers (Claude Haiku 4.5, Claude Sonnet 4.6, OpenAI
gpt-5-mini) and scoring the resulting root-cause diagnoses against
AI-drafted + author-verified ground truths.

It measures:

- signal preservation (raw-log evidence reaching the model)
- downstream diagnosis quality (`diagnosis_score_v1_1` calibrated)
- total token cost
- abstention + confident-error rates
- dev / holdout / stress generalization
- **cross-family stability** (Haiku / Sonnet / gpt-5-mini)

## Headline finding (v2)

> **v2 produces cross-family-stable AND cross-run-stable benchmark
> rankings; v1.3's stability is narrower.**

On the 19-case v2 corpus, Sonnet 4.6 / Haiku 4.5 / gpt-5-mini all
agree on **top-3 ∩ = `{hybrid-v2, hybrid-v3}`** and on the bottom-4
set. On v1.3 the top-3 intersection narrows to `{hybrid-v1}` only —
its 4k-token threshold is overfit to the v1.3 case distribution and
does **not** generalize.

| Corpus | Top-3 ∩ (all 3 debuggers) | Bottom-4 set | Stability |
|---|---|---|---|
| v1.3 (16 cases) | `{hybrid-v1}` only | raw, rtk-log, llm-summary-mock, rtk-read | narrow |
| **v2 (19 cases)** | **`{hybrid-v2, hybrid-v3}`** | same bottom-4 | cross-family + cross-run |

This is `v2-partial`: the cross-family direction is robust, but the
corpus target is 34 cases and full release awaits Batches 7–8.
Full caveats in [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md) §5.

## Quick start

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# (optional) pull cases corpus from the HF mirror
huggingface-cli download --repo-type dataset \
    eyuansu71/logdx-ci --local-dir cases-from-hf

# run the 165-test suite
python3 tools/tests/test_diagnosis_cache_key.py
python3 tools/tests/test_hybrid_router.py

# run the 3 release gates on canonical state
python3 tools/validate_committed_diagnosis_provider_errors.py
python3 tools/validate_eval_manifest_consistency.py
python3 tools/validate_diagnosis_vs_context_consistency.py

# validate the protocol lock
python3 tools/validate_protocol_lock.py \
    --protocol protocols/cilogbench-v2-checkpoint-19.lock.json
```

## What ships

- **35 cases** total — 16 legacy v1.3 + 19 new v2 — under
  [`cases/`](cases/) (also mirrored at
  [`huggingface.co/datasets/eyuansu71/logdx-ci`](https://huggingface.co/datasets/eyuansu71/logdx-ci))
- **10 context-provider baselines** with method-by-case manifests
  under [`results/`](results/)
- **3 diagnosers** (Anthropic ×2 + OpenAI ×1) with per-case JSONs
- **Eval files** with macro-averaged metrics +
  zero-score-abstention injection for documented historical
  exclusions
- **Protocol locks** SHA-pinning 14 schema / prompt / evaluator
  hashes per release (see [`protocols/`](protocols/))
- **Release gate scripts** for CI gating (see below)

## Release gates

Three CI-gateable invariant checks ensure reproducibility:

| Script | Invariant |
|---|---|
| `validate_committed_diagnosis_provider_errors.py` | No non-allowlisted `provider_error` rows in committed `real-debugger-*` manifests |
| `validate_eval_manifest_consistency.py` | Every `eval_diagnosis_*.json`'s per-method case-ID set matches its manifest, with strict zero-score verification for excluded rows |
| `validate_diagnosis_vs_context_consistency.py` | Every diagnosis manifest's case set ⊆ source context manifest, with a documented exclusion list for transparent gaps |

## Read more

- **v2 headline report**:
  [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md)
- **Release notes**: [`RELEASE_NOTES.md`](RELEASE_NOTES.md)
- **v1.3 carry-over**:
  - One-pager: [`docs/reports/cilogbench_v1_3_one_pager.md`](docs/reports/cilogbench_v1_3_one_pager.md)
  - Full technical report: [`docs/reports/cilogbench_v1_3_technical_report.md`](docs/reports/cilogbench_v1_3_technical_report.md)
  - Limitations: [`docs/reports/cilogbench_v1_3_limitations.md`](docs/reports/cilogbench_v1_3_limitations.md)
  - v1.3 protocol doc: [`docs/protocol/cilogbench_v1_3.md`](docs/protocol/cilogbench_v1_3.md)
- **Citation**: [`CITATION.cff`](CITATION.cff)
- **License**: code under [`LICENSE`](LICENSE) (Apache-2.0); cases /
  reports / protocols / docs under [`LICENSE-DATA`](LICENSE-DATA)
  (CC-BY-4.0)

## v1.3 historical finding (carry-over)

The original `hybrid-grep-4k-rtk-err-cat-v1` strategy
**matched `grep` on diagnosis quality** at about **one third of `grep`'s
token cost** on the 16-case v1.3 benchmark:

| Debugger | hybrid sv1.1 | grep sv1.1 | hybrid total tok | grep total tok |
|---|---:|---:|---:|---:|
| Haiku 4.5 (E5) | **0.715** | 0.675 | 4.9k | 15.7k |
| Sonnet 4.6 (E6) | **0.771** | 0.770 | 5.0k | 15.9k |

Top-3 ranks under sv1.1 were identical across debuggers on v1.3
(`hybrid > grep > tail`). AI-assisted human review (E9) preferred grep
**8-to-2 in head-to-head pairwise judgments** (with 6 ties) while rating
both methods as essentially tied on absolute usefulness (means 3.875 vs
3.938 on a 0–4 scale). v2 reveals the 4k-threshold doesn't generalize
— see §3 of the v2 report.

---

## Project arc (longer narrative)

After a CI failure log is compressed, summarized, filtered, or searched,
**does a coding agent still have enough evidence to identify the true
root cause?** This repository exists to answer that question honestly.

## What this is

- A **benchmark**, not a product.
- A small curated set of real GitHub Actions failure logs with
  human-written ground truth.
- A validator that keeps the benchmark data internally consistent.
- A place where multiple *methods* of handing CI context to an agent —
  raw logs, tail/head, grep heuristics, RTK, LLM summaries, MCP search,
  our legacy rule-based compressor — can be compared apples-to-apples.

## What this is NOT

- Not a new CI log compressor. The legacy rule-based compressor that
  used to be the "product" of this repo lives on under
  [`baselines/simple_rules_legacy/`](baselines/simple_rules_legacy/) and
  is kept as **one** of the methods to benchmark, not the main output.
- Not a wrapper around RTK. [RTK](https://github.com/rtk-ai/rtk) is a
  separate production tool; it will be included as a benchmarked
  method alongside everything else.
- Not a leaderboard yet. The first milestone is to get the cases and
  schemas right; scoring comes later.

## Methods that will be compared

The eventual benchmark will score each of these as a way of giving a
coding agent CI failure context:

| method | what it does |
|---|---|
| `raw` | hand the entire log to the agent |
| `tail-N` / `head-N` | keep only last / first N lines |
| `grep-heuristic` | filter to lines matching common failure patterns |
| `simple_rules_legacy` | the rule-based compressor preserved from the previous phase of this repo |
| `rtk` | run output through [RTK](https://github.com/rtk-ai/rtk) |
| `llm-summary` | have a fixed model summarize the log before handing it over |
| `mcp-search` | expose the log to the agent via an MCP-style search tool |

None of these is the "right" answer a priori. The benchmark is designed
to let the numbers pick.

## Current status

- ✅ Small dev split: 5 real cases under `cases/dev/`.
- ✅ JSON schemas for `case`, `ground_truth`, `method_output`, and
  `diagnosis`.
- ✅ Validator that keeps the data internally consistent
  (`tools/validate_cases.py`).
- ✅ **M2 benchmark loop** for three context-provider baselines (`raw`,
  `tail`, `grep`) with a signal-recall evaluator and a markdown report.
- ✅ **M3 RTK baseline** — three external-tool methods (`rtk-read`,
  `rtk-log`, `rtk-err-cat`) scored via text-based preservation
  (`line_mapping_available: false`).
- ✅ **M4 LLM-summary baseline infrastructure** — map-reduce pipeline
  with `--provider mock|command`, per-call caching, prompt hashing,
  chunk + usage metadata.
- ✅ **M5 root-cause diagnosis evaluation** — a fixed diagnoser
  (`--diagnoser mock|command`) runs over every context method's
  output, producing a structured diagnosis. 11 deterministic metrics
  (category accuracy, critical-signal mention, must-mention, forbidden
  claims, valid evidence quotes, abstention, confident-error rate …)
  computed against ground truth, plus an experimental composite
  `diagnosis_score_v1`. No LLM judge. See
  `docs/methods/diagnosis.md` and
  `docs/evaluation/diagnosis_eval_v1.md`.
- ✅ **M6 experiment wrapper for a real fixed debugger** —
  diagnoser config schema, privacy audit, explicit external-LLM
  opt-in gate, reproducibility manifest (config SHA + prompt SHA +
  git commit + timestamps), joint signal-vs-diagnosis report,
  byte-stable reruns from cache. A working stub shim lives at
  `examples/diagnosis_shim_stub.py` for infrastructure tests
  without an API key.
- ✅ **M7 experiment wrapper for a real LLM summary** —
  summarizer config schema + method-name guard
  (`llm-summary-v1-<slug>`, `mock` reserved), two privacy gates
  (raw-log audit + external-LLM opt-in), full cost accounting
  (summary processing + final context + diagnosis output), signal
  and diagnosis evaluation, byte-stable reruns, 12-section M7
  experiment report.
- ✅ **M8 `cilogbench-v1` protocol + holdout split** — 5 real
  holdout cases, 4 protocol docs, SHA-256-locked protocol file
  (9 schemas + 3 prompts + 2 evaluators + 7 baselines + 2 splits),
  `validate_protocol_lock` catches drift, dev-vs-holdout comparator
  flags ≥20pp gaps. See `docs/protocol/cilogbench_v1.md`.
- ✅ **M9 stress split + `cilogbench-v1.1` protocol** — 6 new
  stress cases (4 categories), 5 corpus tools
  (`build_split_manifest` / `import_case_skeleton` / `tag_cases` /
  `validate_case_tags` / `summarize_corpus` / `check_split_balance`),
  tag schema separate from model input, v1.1 lock covers dev +
  holdout + stress (16 cases total). v1 lock untouched. 3-way
  comparison report flagged tail climbing to 100% recall on small
  logs and rtk-err-cat dropping to 39%.
- ✅ **M10 real-debugger wrapper on frozen protocol** —
  `run_protocol_diagnosis_eval.py` validates lock, audits every
  split, runs diagnosis per split × method, writes a 14-section
  experiment report + reproducibility manifest (lock / config /
  prompt / git SHAs). Stub-shim end-to-end run completes for v1.1
  (16 cases × 7 methods = 112 diagnoses). Real `$DIAGNOSIS_COMMAND`
  is a drop-in swap.
- ✅ **M11 blinded human-review infrastructure** — three schemas
  (item, label, report), three review docs (protocol, instructions,
  label schema), four tools (`build_human_review_set` /
  `validate_human_review_labels` / `analyze_human_review` /
  `render_human_review_report`). Batch builder sanitizes method
  names out of diagnosis text, label validator rejects
  out-of-range scores and unblinding leaks in reviewer notes,
  analyzer computes per-method means, pairwise W/L/T, and Spearman
  correlation with deterministic metrics.
- ✅ **E1 first real fixed-debugger run** — Claude Haiku 4.5 via
  `claude -p`, 112/112 v1.1 method × case diagnoses (109 real + 3
  legitimate `provider_error`).
- ✅ **E2 expert-model review** — 50 review labels (20 absolute + 30
  pairwise) by `claude-opus-4-7-expert` over 5 holdout cases × 4
  methods. PASS at marginal Spearman 0.637.
- ✅ **E2b score-rule calibration** — `category_match_score_v1_1`
  (0/0.5/1) + stricter `confident_error_v1_1`. Spearman 0.637 →
  0.839; pairwise agreement 0.760 → 0.880. Frozen as
  `cilogbench-v1.2`.
- ✅ **E3 real LLM-summary baseline** — `llm-summary-v1-haiku`
  (Haiku 4.5 with `llm_summary_v1_*` prompts). Stable across splits
  but lost to `grep` on quality and ~6× cost.
- ✅ **E4 budget-frontier analysis** — analysis-only sweep over 1k–32k
  budgets; offline-best policy: `grep-if-fits-else-rtk-err-cat @4k`,
  predicted macro sv1.1 = 0.723 vs grep-default 0.680.
- ✅ **E5 hybrid first-class baseline** — `hybrid-grep-4k-rtk-err-cat-
  v1` implemented as a deterministic context provider; macro sv1.1 =
  0.715 vs grep 0.675; total tokens 4.9k vs 15.7k. All four freeze
  criteria passed.
- ✅ **`cilogbench-v1.3` protocol freeze** — v1.2 + hybrid baseline
  locked. v1.2 unchanged on disk. `validate_protocol_lock` passes
  (17 hashes; 10 schemas, 3 prompts, 4 evaluators).
- ✅ **E6 second-debugger replication** — Sonnet 4.6 as
  `real-debugger-v2`. Hybrid stayed rank #1 under both debuggers;
  top-3 ranks identical. Verdict: `CONFIRMED_MODEL_STABLE`.
- ✅ **E7 MCP/search-agent baseline** — `mcp-search-agent-v1-sonnet`
  (Sonnet 4.6 via `claude -p` with 7 deterministic local tools, 8-call
  budget). 16/16 cases completed; macro sv1.1 = 0.716 vs hybrid 0.771
  at ~12× the agent-token cost. Verdict: `KEEP_AS_EXPLORATORY` (not
  locked into v1.3).
- ✅ **E8 hybrid-first search-fallback analysis** — offline routing
  sweep over 11 policies (incl. oracle). No deployable gate beat
  hybrid-default by a useful margin within an acceptable cost
  envelope. Verdict: `STOP_SEARCH_TRACK`.
- ✅ **E9 AI-assisted human review of v1.3 hybrid-vs-grep** — 1
  reviewer (project author), verified all 48 items of a ChatGPT
  draft. Pairwise: grep wins 8 / hybrid wins 2 / 6 ties. Absolute
  means tied within 0.063 on 0–4. Verdict: `WEAKEN_HEADLINE` —
  v1.3 headline updated to "matched grep on quality at ~⅓ token cost".
- ⏳ A second independent human reviewer on the E9 batch is the
  strongest remaining follow-up (canonical IRR; lifts the
  project-author bias caveat).
- ❌ Larger corpus across more ecosystems remains the biggest
  constraint on every claim. No public leaderboard.
- 🚧 **E10 corpus-expansion + v2 generalization** — in progress. Goal:
  grow the corpus from 16 → 50 cases (10 dev / 20 holdout / 20 stress)
  with explicit ecosystem, log-size, signal-position, and
  evidence-format coverage targets, then re-run the v1.3 locked
  methods + `real-debugger-v2` against the larger corpus to test
  whether the hybrid-vs-grep cost/quality tradeoff generalizes.
  v1.3 results are **not** retroactively rewritten by v2;
  `cilogbench-v1.3` stays frozen and `cilogbench-v2` will be a
  separate locked protocol. Phase 1 deliverables landed
  2026-05-06:
  - Plan: [`cilogbench_e10_corpus_expansion_v2_generalization_plan.md`](cilogbench_e10_corpus_expansion_v2_generalization_plan.md) (external)
  - Target matrix: [`docs/corpus/cilogbench_v2_case_matrix.md`](docs/corpus/cilogbench_v2_case_matrix.md)
  - Collection rules: [`docs/corpus/cilogbench_v2_collection_guidelines.md`](docs/corpus/cilogbench_v2_collection_guidelines.md)
  - Annotation overlay: [`docs/corpus/cilogbench_v2_annotation_guide.md`](docs/corpus/cilogbench_v2_annotation_guide.md)
  - Schema bump: `schemas/case_tags.schema.json` (additive: `origin`,
    `ecosystem`, `ci_provider`, `repo_visibility`,
    `matrix_or_monorepo_failure`, 7 new evidence formats; v1.3 tags
    remain valid).
  - Tooling: `tools/validate_case_tags.py` accepts `v2/dev`,
    `v2/holdout`, `v2/stress`, `v1.3`, `v2`, `all`; case importer
    already handled nested splits.
  - Cases collected so far: **19 / 34** new (16 / 16 legacy tagged
    `origin=legacy_v1_3`). Batch 1 (3/3) ✓, Batch 2 (5/5) ✓,
    Batch 3 (2/2) ✓ Phase 2 10-case checkpoint, Batch 4 (3/3) ✓,
    Batch 5 (4/4-6) ✓ — first hybrid-v2 hold-out, Batch 6 (2/3-5)
    ✓ — second hybrid-v2 hold-out (java-maven dubbo + java-gradle
    hibernate). v2/dev 3/3 ✓, v2/holdout 10/4 (over-target by 6),
    v2/stress 6/3 (over-target by 3).
  - v2/stress cases (5 — process-crash + matrix + non-pytest framework + timeout + middle-signal):
    1. `cases/v2/stress/numpy-pytest-segfault-argsort-v2-001/`
       — `Fatal Python error: Segmentation fault` inside
       `test_datetime_nat_argsort_stability` on numpy's
       `reverse-sorts` perf branch. Process-crash format, exit 245.
       `requires_repo_context = true`.
    2. `cases/v2/stress/cpython-tcl-windows-matrix-v2-001/`
       — first v2 `matrix_or_monorepo_failure` (tags.json label
       only — case.json + ground_truth.root_cause.category are
       both still `test_assertion` for evaluator and manifest
       purposes; schema/prompt extension deferred to v3 to avoid
       a re-run of the full v2 diagnoser pipeline; see
       `reports/e10_v2_generalization_partial.md` §5.8). cpython's
       `update_windows_tcltk` broke Unicode surrogate handling
       in the bundled tcltk: ALL 7 Windows configs fail with the
       same `AssertionError: '<💻>' != '<ðŸ’»>'` while
       ALL Linux/macOS variants pass. `multi_failure = true`.
    3. `cases/v2/stress/rust-compiletest-wasm-exceptions-asm-v2-001/`
       — Batch 4 case 1; first non-pytest v2/stress framework (rust
       compiletest), closes the v2/stress framework_dominance
       split-balance flag (was 2/2 pytest). Largest v2 raw.log
       so far at 31110 lines.
    4. `cases/v2/stress/nodejs-test-debugger-exec-timeout-v2-001/`
       — Batch 4 case 2; first v2 case with `timeout_or_oom`
       failure_category (was 0/v2 → 1) and first use of the
       `timeout_marker` evidence_format. nodejs/node `parallel/
       test-debugger-exec` timed out 15s waiting for the inspector
       break-in pattern.
    5. `cases/v2/stress/airflow-precommit-tsc-middle-v2-001/`
       — Batch 4 case 3; **first non-late v2/stress case**
       (signal_position=middle). apache/airflow pre-commit
       `ts-compile-lint-ui` hook fails with 3 TypeScript errors
       (TS6196, TS6133, TS2739) at L3391-3479 of a 6496-line log;
       ##[error] step exit at L3762 (≈58%); ~42% of the log AFTER
       the failure is non-failure pre-commit hook chatter from
       the ~30 OTHER hooks pre-commit keeps running. Selected
       deliberately to test the §3c tail-winner sampling caveat.
  - **Six protocol locks exist for v2; two validate today.** The
    full reference is in
    [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md)
    header. Quick summary:
    [`cilogbench-v2-partial`](protocols/cilogbench-v2-partial.lock.json)
    (8 v2 cases — frozen pre-v2/stress; validates today since v2/stress
    is absent from its splits dict),
    [`cilogbench-v2-checkpoint`](protocols/cilogbench-v2-checkpoint.lock.json)
    + [`cilogbench-v2-checkpoint-12`](protocols/cilogbench-v2-checkpoint-12.lock.json)
    (both historical 12-case snapshots with v2/stress=4 — fail
    validation now because the on-disk v2/stress manifest moved
    past them at commit 64c7340; check out 530d5fd / 7036fdb to
    reproduce historical eval),
    [`cilogbench-v2-checkpoint-13`](protocols/cilogbench-v2-checkpoint-13.lock.json)
    (13 v2 cases / v2/stress=5 — also historical now; fails
    validation because Batch 5 grew v2/holdout 5→8 and
    v2/stress 5→6),
    [`cilogbench-v2-checkpoint-17`](protocols/cilogbench-v2-checkpoint-17.lock.json)
    (17 v2 cases — also historical now; fails validation because
    Batch 6 grew v2/holdout 8→10),
    and [`cilogbench-v2-checkpoint-19`](protocols/cilogbench-v2-checkpoint-19.lock.json)
    (19 v2 cases / v2/holdout=10 / v2/stress=6 — **current canonical,
    35 cases total**). The 19-case lock includes THREE hybrid
    baselines (v1 `hybrid-grep-4k-rtk-err-cat-v1`, the
    evaluation-tuned v2 `hybrid-grep-120k-tail-v2`, and the
    §3h-tested v3 prototype `hybrid-grep-120k-rtk-tail-v3`).
    `validate_protocol_lock.py` fail-closes on hybrid drift across
    all `type: hybrid_context_provider` baselines (9 file hashes
    total: 3 hybrids × {config, route_schema, router}).
  - **12-case refresh surfaced two findings.** Phase 3 was re-run
    with Sonnet + Haiku on the 2 new v2/stress cases (16 calls each
    debugger). Hybrid sv1.1 stayed flat (0.4427 → 0.4353 Sonnet,
    0.4683 → 0.4302 Haiku — both still ≥0.27 below v1.3), rank
    stable at **#4 unanimous**.
    1. **Method-level (robust):** rust + nodejs both reveal a
       previously-unseen grep blindspot. When the regex matches
       too widely (rust 31k-line log → 161k tokens, nodejs
       10k-line log → 359k tokens), Sonnet/Haiku abstain on the
       inflated context (sv1.1 = 0.0). `tail`'s bounded 200-line
       window survives all 4 v2/stress cases.  `rtk-err-cat` also
       collapses on nodejs (~320k tokens). Hybrid's 4k threshold
       avoids grep's blowup but inherits rtk-err-cat's nodejs
       collapse.
    2. **Macro-level (resolved at 13-case):** at 12-case the v2
       macro showed tail #1 (Sonnet 0.68) over grep (0.59) — but
       the +0.09 gap was a v2/stress 4/4-late sampling bias.
       Adding airflow's middle-signal case at 13-case shrank the
       Sonnet gap to **+0.02** (74% shrink), well within
       case-to-case variance. Per-case on the new airflow log
       (Sonnet): tail 0.017 (collapsed — failure block >2900
       lines from the bottom), grep 0.717 (recovered — structured
       tsc errors). The robust 13-case takeaway: **no single
       context-provider wins on both signal positions** — tail
       beats grep on late, grep beats tail on middle, hybrid's
       threshold-on-tokens routing doesn't capture the position
       trade-off. Full 13-case detail with per-case
       decomposition in
       [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md)
       §3d, narrative in
       [`reports/v2_split_balance.md`](reports/v2_split_balance.md).
    3. **§3e — v2 router prototype (evaluation-tuned).** Built
       `hybrid-grep-120k-tail-v2` (budget 4k → 120k, fallback
       rtk-err-cat → tail) to test §3d's hypothesis. The
       hybrid-v2 config declares `uses_diagnosis_eval: true` —
       the threshold was calibrated against eval data per Codex
       review 2026-05-08. On the 13-case calibration data:
       Sonnet v2 macro 0.6801 (#1), Haiku 0.5311 (#2).
    4. **§3f — Hold-out validation (Batch 5, 4 new cases).**
       Collected spring-boot-checkformat (java-gradle), gradle-
       projecthealth (java-gradle), go-redis timeout, and
       argocd-race-conditions (**first huge log >50k lines —
       89188 lines, fills the corpus-wide gap**) WITHOUT
       retuning hybrid-v2. Hold-out result: Sonnet hybrid-v2
       0.5757 #1 (drop −0.10), Haiku 0.3521 #2 (drop −0.15;
       grep wins). **Sonnet generalization confirmed; Haiku
       partial.** The §3e direction (v2 > v1) holds across
       both debuggers (+0.21 / +0.02 hold-out). The §3c
       "tail unseats grep" macro claim is fully retracted —
       tail drops −0.21 / −0.18 on hold-out. Argocd exposes
       a hybrid-v2 weakness on huge multi-failure logs: tail-
       fallback (0.12) loses to hybrid-v1's rtk-err-cat fallback
       (0.56) on Sonnet there. Full §3f detail at
       [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md).
    5. **§3g — Second hold-out (Batch 6, 2 cases).** dubbo
       (java-maven timeout) + hibernate (java-gradle test).
       Confirms direction: hybrid-v2 stays #1 on Sonnet
       (0.6838 vs grep 0.6494 on combined B5+B6, +0.034); on
       Haiku tied with grep. **§3e Haiku CLI-flake reproduces
       a third time** on dubbo (hybrid-v2 0.60 vs grep 0.75).
    6. **§3h — Hybrid-v3 prototype (negative result).** Built
       3-way router `hybrid-grep-120k-rtk-tail-v3` to test §3f's
       rtk-err-cat-fallback hypothesis. Result: **v3 LOSES to v2
       on Sonnet** (−0.055 v2 macro) — the killer is nodejs
       where rtk-err-cat output is too-big-but-not-truncated
       (320k tokens, Sonnet abstains). The §3f hypothesis
       splits 1-1-1: wins rust (+0.05), catastrophic loss on
       nodejs (−0.75), wrapper-variance loss on argocd (−0.12).
       Sub-finding: v3 BEATS v2 on Haiku Batch 6 hold-out
       (+0.15) because the §3e Haiku CLI-flake is empirically
       wrapper-content-specific — v3's different wrapper
       sidesteps it (artifact-driven gain, not method-driven).
       **No v3 promotion**; hybrid-v2 stays canonical. v3 is in
       the lock as a documented prototype.
    7. **§3i — Third debugger (gpt-5-mini, cross-family
       validation).** Added `examples/diagnosis_shim_openai.py`
       and ran full Phase 3 with gpt-5-mini as `real-debugger-v3`.
       Result: **v2 produces cross-family-stable benchmark
       rankings; v1.3 does not.** v1.3 top-3 ∩ across the 3
       debuggers is ∅ (Sonnet's #1 hybrid-v1 is gpt's #5; gpt's
       #1 grep is Sonnet's #3). v2 top-3 ∩ = {hybrid-v2,
       hybrid-v3}; Sonnet and gpt-5-mini produce IDENTICAL #1-#3
       rankings on v2 (hybrid-v2 → hybrid-v3 → grep). All three
       debuggers also rank positions 7-10 in unanimous identical
       order on v2. The hybrid-v2 #1 finding from §3e-§3h now
       survives a debugger from a different model family.
  - Phase 2 acceptance-criteria-C deliverables landed:
    [`reports/v2_corpus_summary.md`](reports/v2_corpus_summary.md),
    [`reports/v2_split_balance.md`](reports/v2_split_balance.md),
    [`reports/v2_contamination_check.md`](reports/v2_contamination_check.md).
  - 🚨 **Phase 3 (partial) finding** — v1.3 methods do NOT generalize
    to v2. Confirmed using BOTH the deterministic `signal-recall`
    proxy AND the calibrated `diagnosis_score_v1_1` metric (with
    real Sonnet 4.6 calls via `real-debugger-v2`).
    - `hybrid-grep-4k-rtk-err-cat-v1` drops from **0.7713 → 0.4495**
      sv1.1 (Δ = **−0.32**) — falls from rank #1 (tied with grep) on
      v1.3 to **rank #6 of 8** on v2. Confident-error rate spikes
      from 0.00 → 0.17. By signal-recall: 0.82 → 0.48 (Δ = **−0.34**).
    - `grep` is the most stable: −0.10 sv1.1, smallest signal-recall
      drop too. Now de facto winner on v2 (0.6664).
    - `raw` actually IMPROVES on v2 (+0.0368) — v2 logs are smaller
      median size, so handing the whole log to Sonnet stops being
      noisy enough to hurt.
    - Per-case: hybrid routes 6/8 v2 cases to rtk-err-cat; grep
      would have done strictly better on 5 of those 6. One case
      (pnpm-jest-config) fails at 0.00 sv1.1 because rtk-err-cat
      drops the assertion diff and Sonnet diagnoses confidently-wrong.
    - This **confirms `cilogbench_v1_3_limitations.md` §9** — the
      4k-token threshold was tuned on v1.3 and is overfit. The v1.3
      one-pager headline ("matched grep on quality at ~⅓ token
      cost") is **falsified on v2**: cost match is real; quality
      match does not generalize.
    - **Cross-debugger confirmation:** rerun with Haiku 4.5
      (`real-debugger-v1`) on v2 — Haiku also shows hybrid drop
      −0.30 (rank #1 → #6); top-2 and bottom-3 ranks **identical**
      across Haiku + Sonnet. The v1.3 model-stability finding
      ("hybrid stays #1 across two debuggers") generalizes the
      wrong way on v2: hybrid stays #6 across two debuggers.
    - Frozen as
      [`protocols/cilogbench-v2-partial.lock.json`](protocols/cilogbench-v2-partial.lock.json)
      (5 splits, 24 cases, 14 SHA-pinned schema/prompt/evaluator
      hashes). Validate with
      `python3 tools/validate_protocol_lock.py --protocol protocols/cilogbench-v2-partial.lock.json`.
    - **Canonical narrative:**
      [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md)
      — the single document aggregating signal-recall + diagnosis
      (Haiku + Sonnet) + cross-debugger + per-case detail + caveats
      + reproducibility instructions. Companion deep-dives:
      [`reports/e10_phase3_v2_partial_signal_recall.md`](reports/e10_phase3_v2_partial_signal_recall.md)
      and
      [`reports/e10_phase3_v2_partial_diagnosis.md`](reports/e10_phase3_v2_partial_diagnosis.md).
  - Phase 2 (case import + annotation) infrastructure ready:
    `cases/v2/{dev,holdout,stress,_incoming,_rejected}/` exist;
    [`docs/corpus/v2_case_intake_queue.md`](docs/corpus/v2_case_intake_queue.md)
    is the rolling worklist; `tools/audit_context_privacy.py
    --raw-log <path>` runs a pre-import secret-pattern scan; the
    raw / signal-recall / case validators all accept `v2/<split>`
    paths. Annotation pattern is AI-draft + human-verify (item-by-
    item per case).
  - Accepted cases (raw sanity 100/100/100 each):
    1. `cases/v2/dev/pnpm-jest-config-v2-001/` — single-test jest
       assertion failure (trailing-slash drift) from pnpm/pnpm run
       25437799581. category=`test_assertion`.
    2. `cases/v2/dev/pip-pytest-network-github-v2-001/` — pytest
       functional test that failed because GitHub returned 502s
       while pip downloaded a test fixture. Surface
       `AssertionError: Script returned code: 1` hides a network
       root cause; pytest-rerunfailures retried 3× before final
       fail. category=`network_or_flaky`, `flaky_or_transient=true`.
       Fills two v1.3 gaps (both categories were 0/16 in v1.3).
    3. `cases/v2/dev/moby-buildx-bake-v2-001/` — `docker buildx bake`
       failed at Dockerfile:336 because `RUN wget https://github.com/
       dragonflyoss/nydus/...` hit HTTP 502 from github.com.
       category=`docker_build`, `flaky_or_transient=true`,
       `repo_visibility=redacted` (1 redaction stripping an AWS access
       key + signature + akamai HMAC from a presigned-S3-URL in a
       debug-level `fetch failed` line). signal_position=`middle`
       (failure at L1901 of 3979) — exposes tail-200 blind spot.
       Fills v1.3 docker_build gap (was 0/16); first v2 case using
       new schema fields `docker_build_output` and
       `repo_visibility=redacted`.

## Repository layout

```
cilog-bench/
├── README.md                      ← you are here
├── PLAN.md                        ← the pivot plan driving this milestone
├── cases/
│   ├── dev/                       ← 5 real GHA failure cases
│   │   └── <case_id>/
│   │       ├── raw.log
│   │       ├── case.json          ← inputs; does NOT contain the answer
│   │       └── ground_truth.json  ← the answer + required evidence
│   └── holdout/                   ← reserved; intentionally empty
├── schemas/
│   ├── case.schema.json
│   ├── ground_truth.schema.json
│   ├── method_output.schema.json
│   └── diagnosis.schema.json
├── tools/
│   ├── validate_cases.py
│   ├── run_baseline.py              ← raw / tail / grep context providers
│   ├── run_rtk_baseline.py          ← rtk-read / rtk-log / rtk-err-cat (external)
│   ├── run_llm_summary_baseline.py  ← llm-summary-v1 via mock or command provider
│   ├── run_diagnosis.py             ← fixed diagnoser over each method's context
│   ├── run_m6_experiment.py         ← M6 wrapper (audit → diagnose → eval → report)
│   ├── run_m7_real_summary_experiment.py ← M7 wrapper (audit → summarize → signal + diagnosis)
│   ├── audit_context_privacy.py     ← best-effort secret-pattern scan on contexts
│   ├── build_split_manifest.py      ← per-case SHAs + tallies for a split
│   ├── check_holdout_contamination.py ← dev/holdout dedup + leak checks
│   ├── freeze_protocol.py           ← write protocols/<id>.lock.json
│   ├── validate_protocol_lock.py    ← recompute hashes; fail on drift
│   ├── run_locked_eval.py           ← run baselines with locked parameters
│   ├── compare_splits.py            ← dev vs holdout comparison report
│   ├── evaluate_signal_recall.py    ← signal-preservation metric
│   ├── evaluate_diagnosis.py        ← 11 deterministic diagnosis metrics
│   ├── render_report.py             ← reports/<split>_signal_recall.md
│   └── render_diagnosis_report.py   ← reports/<split>_diagnosis_eval_<diagnoser>.md
├── prompts/
│   ├── llm_summary_v1_map.md     ← per-chunk evidence-extraction prompt
│   ├── llm_summary_v1_reduce.md  ← cross-chunk reduce prompt
│   └── debugger_v1.md            ← root-cause diagnosis prompt
├── configs/
│   ├── diagnosers/example.debugger-v1-command.json      ← M6 reference config
│   └── summarizers/example.llm-summary-v1-command.json  ← M7 reference config
├── examples/
│   ├── diagnosis_shim_stub.py    ← drop-in shim for M6 pipeline smoke tests
│   └── summary_shim_stub.py      ← drop-in shim for M7 pipeline smoke tests
├── docs/
│   ├── annotation_guide.md                    ← how to write correct ground truth
│   ├── methods/rtk.md                         ← RTK baselines setup
│   ├── methods/llm_summary.md                ← llm-summary-v1: map-reduce, providers, cache, privacy
│   ├── methods/diagnosis.md                   ← debugger-v1 providers + privacy guarantees
│   ├── evaluation/diagnosis_eval_v1.md        ← the 11 deterministic diagnosis metrics
│   ├── experiments/m6_real_fixed_debugger.md  ← M6 experiment protocol + guardrails
│   ├── experiments/m7_real_llm_summary.md     ← M7 experiment protocol + cost accounting
│   ├── protocol/cilogbench_v1.md              ← v1 protocol definition
│   ├── protocol/holdout_policy.md             ← holdout-is-not-dev governance
│   ├── protocol/annotation_freeze_policy.md   ← when/how annotations may change
│   └── protocol/method_submission_v1.md       ← how to add a new method
└── baselines/
    └── simple_rules_legacy/       ← legacy rule-based compressor, kept as a baseline
```

## Run the loop

```bash
# 1. Validate cases
python tools/validate_cases.py cases/dev

# 2. Run the context-provider baselines
python tools/run_baseline.py     --method raw         --split dev
python tools/run_baseline.py     --method tail        --split dev  # --tail-lines 200
python tools/run_baseline.py     --method grep        --split dev  # --before 3 --after 8
python tools/run_rtk_baseline.py --method rtk-read    --split dev
python tools/run_rtk_baseline.py --method rtk-log     --split dev
python tools/run_rtk_baseline.py --method rtk-err-cat --split dev  # needs `rtk` on PATH

# LLM summary (mock, no API key — useful for CI and acceptance)
python tools/run_llm_summary_baseline.py --split dev \
    --provider mock --method llm-summary-v1-mock

# LLM summary (real) — explicit opt-in; may send logs to an external model
# export LLM_SUMMARY_COMMAND="/path/to/your_shim"
# python tools/run_llm_summary_baseline.py --split dev \
#     --provider command --command "$LLM_SUMMARY_COMMAND" \
#     --method llm-summary-v1

# 3. Score each method against per-case ground truth
for m in raw tail grep rtk-read rtk-log rtk-err-cat llm-summary-v1-mock; do
  python tools/evaluate_signal_recall.py --method "$m" --split dev
done

# 4. Render the signal-recall comparison report
python tools/render_report.py --split dev \
    --methods raw tail grep rtk-read rtk-log rtk-err-cat llm-summary-v1-mock
# -> reports/dev_signal_recall.md

# 5. Diagnosis layer (mock; swap to --diagnoser command for a real LLM)
python tools/run_diagnosis.py --split dev --diagnoser mock --context-method all
python tools/evaluate_diagnosis.py --split dev --diagnoser debugger-v1-mock
python tools/render_diagnosis_report.py --split dev --diagnoser debugger-v1-mock
# -> reports/dev_diagnosis_eval_debugger-v1-mock.md

# 6. M6 real-debugger experiment (stub shim smoke test; use your own shim for a real model)
export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_stub.py"
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
python tools/run_m6_experiment.py --split dev \
    --diagnoser-name stub-debugger-v1 \
    --config configs/diagnosers/example.debugger-v1-command.json \
    --context-method all
# -> reports/dev_m6_real_debugger_stub-debugger-v1.md
# -> results/dev/m6_real_debugger_stub-debugger-v1.manifest.json

# 7. M7 real-LLM-summary experiment (stub shims; swap for real LLM shims to run for real)
export LLM_SUMMARY_COMMAND="python3 $(pwd)/examples/summary_shim_stub.py"
python tools/run_m7_real_summary_experiment.py \
    --summarizer-config configs/summarizers/example.llm-summary-v1-command.json \
    --summarizer-name stub-summarizer-v1 \
    --method llm-summary-v1-stub \
    --diagnoser-config configs/diagnosers/example.debugger-v1-command.json \
    --diagnoser-name stub-debugger-v1
# -> reports/dev_m7_real_summary_stub.md
# -> results/dev/m7_real_summary_stub.manifest.json

# 8. M8: freeze cilogbench-v1 protocol + locked holdout eval
python tools/build_split_manifest.py --split all
python tools/check_holdout_contamination.py
python tools/freeze_protocol.py --protocol-id cilogbench-v1
python tools/validate_protocol_lock.py --protocol protocols/cilogbench-v1.lock.json
python tools/run_locked_eval.py --protocol protocols/cilogbench-v1.lock.json --split dev \
    --methods raw,tail-200,grep,rtk-read,rtk-log,rtk-err-cat,llm-summary-v1-mock
python tools/run_locked_eval.py --protocol protocols/cilogbench-v1.lock.json --split holdout \
    --methods raw,tail-200,grep,rtk-read,rtk-log,rtk-err-cat,llm-summary-v1-mock
python tools/run_diagnosis.py --split holdout --diagnoser mock --context-method all
python tools/evaluate_diagnosis.py --split holdout --diagnoser debugger-v1-mock
python tools/render_diagnosis_report.py --split holdout --diagnoser debugger-v1-mock
python tools/compare_splits.py --protocol protocols/cilogbench-v1.lock.json --diagnoser debugger-v1-mock
# -> reports/dev_vs_holdout_cilogbench_v1.md
```

## Validate the cases

```bash
python tools/validate_cases.py cases/dev
```

The validator checks that every case directory has a `raw.log`,
`case.json`, and `ground_truth.json`; that line counts and byte sizes
match; that every cited evidence line range is valid and 1-indexed; and
that `raw.log` does not contain obvious unmasked secret patterns.

Install `jsonschema` (`pip install jsonschema`) for strict schema
validation; the validator also has a dependency-free fallback path for
the core checks.

## Add a new case

1. Pick a short, stable `case_id`: `<framework>-<repo_or_project>-<NNN>`
   (lowercase, hyphen-separated). The directory name must match.
2. Drop the raw GHA log at
   `cases/dev/<case_id>/raw.log`.
3. Redact any non-GHA-masked secrets by hand (see
   `docs/annotation_guide.md` and the secret patterns enforced by the
   validator).
4. Write `case.json` (repo, framework, failure category, line count,
   byte size, etc.). Do **not** include the answer here.
5. Write `ground_truth.json` per `docs/annotation_guide.md`. Cite
   narrow, 1-indexed line ranges. Only claim what the log says.
6. Run `python tools/validate_cases.py cases/dev` and fix every error it
   reports before committing.

## Known limitations

- **5-case dev split** is tiny. It is enough to force schema + tooling
  decisions, but not enough for statistically defensible comparisons
  between methods.
- **Annotation bias.** Ground truths were written by whoever wrote the
  case. They have not yet been reviewed by an independent second pair
  of eyes.
- **GitHub-Actions-only.** No GitLab CI / CircleCI / Buildkite fixtures
  yet. The rules and signal vocabulary assume GHA conventions
  (`##[group]`, `##[error]`, etc.).
- **Python-biased.** 2/5 dev cases are pandas. A genuine comparison
  needs broader framework coverage.
- **No scoring yet.** The benchmark currently answers "do the cases
  type-check?" It does not yet answer "which method wins?"

## Future milestones (not for this pass)

Roughly in order, once the dev split is trusted:

1. Raw log baseline
2. Tail baseline
3. Grep / error-heuristic baseline
4. Legacy `simple_rules_legacy` baseline
5. RTK baseline
6. LLM summary baseline
7. Fixed-model diagnosis runner
8. Signal-recall evaluator
9. Root-cause accuracy evaluator
10. Context-quality leaderboard
11. End-to-end debugging leaderboard

See `PLAN.md` for the full pivot rationale and constraints.
