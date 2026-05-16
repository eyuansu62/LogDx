---
title: "LogDx-CI"
description: "A reproducible benchmark for failure-context strategies in CI log diagnosis."
---

# LogDx-CI

> A reproducible benchmark for **failure-context strategies in CI log
> diagnosis**. Does an LLM still have enough evidence to identify the
> true root cause after a CI log is filtered, summarized, or compressed?

[![GitHub](https://img.shields.io/badge/code-eyuansu62%2FLogDx-181717?logo=github)](https://github.com/eyuansu62/LogDx)
[![HF](https://img.shields.io/badge/data-eyuansu71%2Flogdx--ci-yellow?logo=huggingface)](https://huggingface.co/datasets/eyuansu71/logdx-ci)
[![Release](https://img.shields.io/github/v/release/eyuansu62/LogDx?include_prereleases&label=release)](https://github.com/eyuansu62/LogDx/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0%20%2B%20CC--BY--4.0-blue)](https://github.com/eyuansu62/LogDx/blob/main/LICENSE)

**Current release**: `v2-partial-2026-06-22` ·
[Leaderboard](leaderboard.html) ·
[Citation](cite.html) ·
[Full report](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)

## What it measures

LogDx-CI compares **10 context providers** — `raw`, `tail`, `grep`,
`rtk-*`, `llm-summary-*`, and hybrid routers — by handing the same CI
failure log to three debugger families (Claude Haiku 4.5, Claude
Sonnet 4.6, OpenAI gpt-5-mini) and scoring the resulting root-cause
diagnoses against AI-drafted + author-verified ground truth.

It optimizes for **method ranking stability** — the question is not
"which LLM is smartest" but "what context strategy gives an LLM the
best chance of finding the true root cause within a fixed token budget,
ACROSS model families."

## Headline finding (v2)

> **v2 produces cross-family-stable AND cross-run-stable benchmark
> rankings; v1.3's stability is narrower.**

| Corpus | Top-3 ∩ (all 3 debuggers) | Bottom-4 set | Stability |
|---|---|---|---|
| v1.3 (16 cases) | `{hybrid-v1}` only | raw, rtk-log, llm-summary-mock, rtk-read | narrow |
| **v2 (19 cases)** | **`{hybrid-v2, hybrid-v3}`** | same bottom-4 | cross-family + cross-run |

The v1.3-tuned `hybrid-grep-4k-rtk-err-cat-v1` does **not** generalize
to v2 — its 4k-token threshold is overfit to the v1.3 case
distribution. The replacement hybrids (`hybrid-v2` and `hybrid-v3`)
use a 120k-token primary threshold with explicit `rtk_input_truncated`
gating and recover most of the lost performance.

## Leaderboard (top 6, v2 corpus)

| Rank | Method | Avg score |
|----:|--------|----------:|
| 1 | **`hybrid-grep-120k-rtk-tail-v3`** | **0.646** |
| 2 | `hybrid-grep-120k-tail-v2` | 0.638 |
| 3 | `tail-200` | 0.576 |
| 4 | `grep` | 0.571 |
| 5 | `rtk-err-cat` | 0.474 |
| 6 | `hybrid-grep-4k-rtk-err-cat-v1` (v1.3 winner) | 0.455 |

Full breakdown by debugger family and split → **[leaderboard](leaderboard.html)**.

## Corpus

**35 cases total** — 16 legacy v1.3 + 19 new v2 — across `dev`,
`holdout`, and `stress` splits (each with a parallel `v2/*` split for
the new corpus). Coverage:

- **8 failure categories**: `test_assertion`, `compile_error`,
  `type_error`, `lint_failure`, `dependency_install`, `docker_build`,
  `timeout_or_oom`, `multi_failure`
- **7+ ecosystems**: pytest, cargo, `go test`, Maven, pnpm + jest,
  docker buildx, helm/k8s, terraform, gradle, biome, mypy, tsc, etc.

## Quick start

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# (optional) mirror the cases corpus from HuggingFace
hf download --repo-type dataset \
    eyuansu71/logdx-ci --local-dir cases-from-hf

# 165-test suite
python3 tools/tests/test_diagnosis_cache_key.py
python3 tools/tests/test_hybrid_router.py

# 3 release gates
python3 tools/validate_committed_diagnosis_provider_errors.py
python3 tools/validate_eval_manifest_consistency.py
python3 tools/validate_diagnosis_vs_context_consistency.py

# Validate the canonical protocol lock
python3 tools/validate_protocol_lock.py \
    --protocol protocols/logdx-ci-v2-partial-2026-06-22.lock.json
```

## Reproducibility infrastructure

Every release carries:

- **Protocol lock** (`protocols/*.lock.json`) — SHA-pins 10 schemas +
  3 prompts + 4 evaluators + 10 baselines + 35 case files at the
  release commit
- **3 release gates** — fail CI when any committed artifact drifts:
  - `validate_committed_diagnosis_provider_errors.py` — no non-
    allowlisted provider_error rows in `real-debugger-*` manifests
  - `validate_eval_manifest_consistency.py` — eval files match
    manifests, with strict zero-score verification for excluded rows
  - `validate_diagnosis_vs_context_consistency.py` — diagnosis case
    sets ⊆ source context manifest, with an explicit historical-
    exclusion list for transparent gaps
- **165-test suite** covering unit, integration, and end-to-end paths
- **Cache identity validation** — `metadata.diagnoser_config_sha256`
  + `metadata.shim_sha256` on every fresh row; the runner rejects
  stale cache hits on config/shim edits
- **Secret redaction** — URL / bearer / API-key / long-opaque-token /
  hostname redactors + hash-only summaries for model-controlled
  exception text

## Caveats

This is a **v2-partial preprint** release; do not retire the v1.3
finding yet.

1. **19 / 34 v2 cases** — Batches 7–8 pending. The direction of the
   hybrid-v1 drop is robust; per-case magnitudes are preliminary.
2. **Ground truth is AI-drafted (Claude Opus 4.7) + single-author
   verified** by Bowen Qin (NUS). Plan-compliant with v1.3 but not
   independent human annotation.
3. **Three model families tested.** Adding GPT-4o / Gemini / Llama
   is the most-leveraged follow-up.
4. **No human review of v2 diagnoses yet.** v1.1 calibration is
   re-used unchanged from v1.3.
5. **20 historical exclusions** documented in
   `configs/historical_provider_error_exclusions.json`; the eval
   injects zero-score abstentions for those tuples so the
   denominator stays correct.

See the [full §5 caveats](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md#5-caveats)
for the complete list.

## Roadmap

- **v2-stable** — Batches 7–8 to reach 34/34 cases; v2/stress 3/3;
  spot-checked human review of v2 diagnoses
- **v3** — Train/holdout split decoupling, GPT-4o + Gemini family
  additions, `matrix_or_monorepo_failure` as a first-class canonical
  category, optional Gradio leaderboard space on HF

## Citation

```bibtex
@misc{qin2026logdx,
  title  = {{LogDx-CI}: A Reproducible Benchmark for
           Failure-Context Strategies in CI Log Diagnosis},
  author = {Qin, Bowen},
  year   = {2026},
  howpublished = {\url{https://github.com/eyuansu62/LogDx}},
  note   = {v2-partial release; cases corpus at
           \url{https://huggingface.co/datasets/eyuansu71/logdx-ci}},
}
```

Plain text → **[cite](cite.html)**.

## Contact

- **Author**: Bowen Qin (National University of Singapore)
- **Issues**: <https://github.com/eyuansu62/LogDx/issues>

---

<sub>Code under Apache-2.0; data, reports, and protocol locks under
CC-BY-4.0. © 2026 Bowen Qin.</sub>
