---
title: "LogDx-CI"
description: "A benchmark for CI log reduction tools — do they preserve enough evidence for LLM root-cause diagnosis?"
---

# LogDx-CI

> A benchmark for **CI log reduction tools**
> ([RTK](https://github.com/rtk-ai/rtk), grep, tail, hybrid routers,
> LLM-summary) — do they preserve enough evidence for LLM root-cause
> diagnosis?

[![GitHub](https://img.shields.io/badge/code-eyuansu62%2FLogDx-181717?logo=github)](https://github.com/eyuansu62/LogDx)
[![HF](https://img.shields.io/badge/data-eyuansu71%2Flogdx--ci-yellow?logo=huggingface)](https://huggingface.co/datasets/eyuansu71/logdx-ci)
[![Release](https://img.shields.io/github/v/release/eyuansu62/LogDx?include_prereleases&label=release)](https://github.com/eyuansu62/LogDx/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0%20%2B%20CC--BY--4.0-blue)](https://github.com/eyuansu62/LogDx/blob/main/LICENSE)

**Current release**: `v1.1` (adds agent-loop leaderboard) ·
[Leaderboard](leaderboard.html) ·
[Citation](cite.html) ·
[Technical report](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)

> **v1.1 highlight**: in multi-turn agent usage (Claude Code /
> Codex–style tool loops), the choice of context method matters
> far less for *quality* — the score range collapses 7× (0.42 →
> 0.06) as the agent rescues weak contexts via tool calls.
> The v1.0 single-shot #1 (`hybrid-grep-120k-rtk-tail`) is also
> #1 in agent-loop with 0% confident-error — the most robust
> method across both regimes. See the
> [agent-loop leaderboard](leaderboard.html#agent-loop-leaderboard--v11)
> and the
> [agent-loop vs single-shot analysis](https://github.com/eyuansu62/LogDx/blob/main/docs/analysis/agent-loop-vs-single-shot.md).

## What it measures

LogDx-CI compares **10 context providers** — `raw`, `tail`, `grep`,
three [RTK](https://github.com/rtk-ai/rtk) modes (`rtk-read`,
`rtk-log`, `rtk-err-cat`), `llm-summary-*`, and three hybrid
routers — by handing the same CI failure log to three debugger
families (Claude Haiku 4.5, Claude Sonnet 4.6, OpenAI gpt-5-mini)
and scoring the resulting root-cause diagnoses against AI-drafted +
author-verified ground truth.

It optimizes for **method ranking stability** — the question is not
"which LLM is smartest" but "which log reducer gives an LLM the best
chance of finding the true root cause within a fixed token budget,
ACROSS model families."

## Headline finding

> Across **35 real CI failure cases** and **3 model families**
> (Claude Haiku 4.5, Claude Sonnet 4.6, OpenAI gpt-5-mini), the
> per-family top-3 sets agree on
> `{hybrid-grep-120k-rtk-tail, hybrid-grep-120k-tail}`. The
> bottom-4 set is also stable across all three families.

Case-count-weighted macro `diagnosis_score_v1_1` aggregated across
the 35-case corpus:

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Overall | conf_err<br/><sub>(↓)</sub> | tokens<br/><sub>per case (↓)</sub> |
|----:|--------|----------:|----------:|----------:|--------:|--------:|--------:|
| 1 | `hybrid-grep-120k-rtk-tail` | 0.624 | 0.679 | 0.706 | **0.670** | **0.000** | 19,844 |
| 2 | `hybrid-grep-120k-tail`     | 0.610 | 0.730 | 0.658 | **0.666** | 0.010 | 19,753 |
| 3 | `llm-summary-v1-gpt-5-mini` <sub>(*new in v1.2; agent-loop #1 at 0.749*)</sub> | 0.654 | 0.686 | 0.652 | **0.664** | 0.010 | 537,638 |
| 4 | `grep`                      | 0.578 | 0.684 | 0.655 | 0.639 | **0.000** | 88,355 |
| 5 | `llm-summary-v1-haiku` <sub>(*promoted to headline in v1.1*)</sub> | 0.583 | 0.704 | 0.608 | **0.632** | 0.029 | 1,681,520 |
| 6 | `tail-200`                  | 0.595 | 0.624 | 0.623 | 0.614 | 0.019 | **6,108** |
| 7 | `hybrid-grep-4k-rtk-err-cat` <sub>(*replaced; see report*)</sub> | 0.552 | 0.597 | 0.571 | 0.573 | 0.029 | 19,892 |
| 8 | `rtk-err-cat`               | 0.455 | 0.488 | 0.467 | 0.470 | 0.029 | 19,850 |
| 9 | `raw`                       | 0.324 | 0.368 | 0.367 | 0.353 | **0.000** | 275,248 |
| 10 | `rtk-read`                  | 0.329 | 0.369 | 0.349 | 0.349 | 0.010 | 274,289 |
| 11 | `rtk-log`                  | 0.238 | 0.262 | 0.249 | 0.249 | **0.133** | **810** |

<sub>*Footnote on `llm-summary-v1-haiku`*: three of the 35 cases used
`chunk_lines=100` instead of the default 500 because they contained
500-line windows exceeding Haiku's effective input window after
Claude-Code session overhead. Same map-reduce algorithm, same model,
same temperature — only map-stage granularity differs; recorded in
per-case `metadata.chunk_lines`. The legacy `llm-summary-v1-mock`
stub (used as the LLM-summary representative through v1.1) has been
moved to the [appendix](leaderboard.html#appendix-legacy-baselines)
on the leaderboard page.</sub>

Three layers of finding:

1. **Quality**: top-2 are 120k-threshold hybrid routers. Stable
   across all 3 model families. The real Haiku summarizer
   (`llm-summary-v1-haiku`, row 4) lands fourth — a +0.30 jump
   over the legacy mock stub that previously represented the
   LLM-summary class.
2. **Safety** (`conf_err`): top-3 methods produce ~zero confidently-
   wrong diagnoses. `rtk-log` and the legacy `llm-summary-v1-mock`
   mislead a confident LLM on ~13% of cases — the failure mode
   [discussed in rtk-ai/rtk#1599](https://github.com/rtk-ai/rtk/issues/1599).
3. **Cost** (`tokens`): the top-2 hybrids dominate `grep` —
   **same-ballpark score at 4.5× fewer tokens**.
   `llm-summary-v1-haiku` is the most expensive method on the
   board (1.68M tokens/case end-to-end — the real summarizer's
   Claude-Code-nested cached-prefix overhead is ~4× higher than
   the mock had estimated), so it remains a quality-over-cost
   choice. Full Pareto frontier on the
   [leaderboard page](leaderboard.html#cost-quality-pareto-frontier).

The top-2 hybrids replaced an earlier 4k-threshold hybrid that was
overfit during methodology development (see the [technical report
§3](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)
for the prototype-vs-formal corpus analysis).

Full per-split + per-debugger breakdown → **[leaderboard](leaderboard.html)**.

## Corpus

**35 real GitHub Actions failure cases** across `dev` (8), `holdout`
(15), and `stress` (12) splits. Coverage:

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

This is a **v1.0 preprint** release.

1. **35 cases.** Per-case variance can shift macro means by ±0.05
   with future corpus expansion. The direction of the top-3 ∩
   finding is robust; absolute magnitudes are preliminary.
2. **Ground truth is AI-drafted (Claude Opus 4.7) + single-author
   verified** by Bowen Qin (NUS). Not independent human annotation.
3. **Three model families tested.** Adding GPT-4o / Gemini / Llama
   is the most-leveraged follow-up.
4. **No independent human review of v1.0 diagnoses** (an earlier
   16-case prototype subset had E2/E2b model-as-judge + E9
   AI-assisted human review; the full 35-case set has not been
   re-scored).
5. **20 historical exclusions** documented in
   `configs/historical_provider_error_exclusions.json`; the eval
   injects zero-score abstentions for those tuples so the
   denominator stays correct.

See the [full §5 caveats](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md#5-caveats)
for the complete list.

## Roadmap

- **v1.1** — Corpus expansion (target 50+); fill remaining
  `stress` gaps (huge log + non-pytest); spot-checked human
  review of v1.0 diagnoses
- **v2** — Train/holdout split decoupling, GPT-4o + Gemini family
  additions, `matrix_or_monorepo_failure` as a first-class canonical
  category, optional Gradio leaderboard space on HF

## Citation

{% raw %}
```bibtex
@misc{qin2026logdx,
  title  = {{LogDx-CI}: Benchmarking CI Log Reduction Tools
           for LLM Root-Cause Diagnosis},
  author = {Qin, Bowen},
  year   = {2026},
  howpublished = {\url{https://github.com/eyuansu62/LogDx}},
  note   = {v1.0 release; cases corpus at
           \url{https://huggingface.co/datasets/eyuansu71/logdx-ci}},
}
```
{% endraw %}

Plain text → **[cite](cite.html)**.

## Acknowledgements

LogDx-CI benchmarks third-party log-reduction tools alongside its
own baselines. Specifically:

- **[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk)** by
  rtk-ai — the `rtk-read`, `rtk-log`, and `rtk-err-cat` baselines
  are three different invocations of the `rtk` CLI binary. The
  hybrid routers `hybrid-grep-120k-rtk-tail` and
  `hybrid-grep-4k-rtk-err-cat` use rtk's `err-cat` mode as an
  intermediate / fallback context provider. See
  [`docs/methods/rtk.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/methods/rtk.md)
  for setup + invocation details.

CI failure logs are sourced from publicly visible
[GitHub Actions](https://github.com/features/actions) runs.
Diagnoses are produced by [Claude](https://www.anthropic.com)
(Anthropic) and [gpt-5-mini](https://openai.com) (OpenAI).

## Contact

- **Author**: Bowen Qin (National University of Singapore)
- **Issues**: <https://github.com/eyuansu62/LogDx/issues>

---

<sub>Code under Apache-2.0; data, reports, and protocol locks under
CC-BY-4.0. © 2026 Bowen Qin.</sub>
