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

**Current release**: `v1.2` (adds cross-family LLM-summary; new agent-loop #1) ·
[Leaderboard](leaderboard.html) ·
[Citation](cite.html) ·
[Technical report](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)

> **v1.2 highlight**: `llm-summary-v1-gpt-5-mini` (real OpenAI
> gpt-5-mini map-reduce summarizer) becomes the new
> **agent-loop #1** at 0.749 with only **0.37 tool calls/case** —
> the lowest of any method. Cross-pair (gpt-5-mini-summarizer →
> Haiku-debugger) beats the self-pair (Haiku → Haiku) by +0.071,
> **falsifying the self-call-bias hypothesis** raised by v1.1's
> reviewer. See [v1.2 release notes](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES_v1_2.md)
> and the [v1.2 promotion section](leaderboard.html#v12--cross-family-llm-summary-llm-summary-v1-gpt-5-mini)
> on the leaderboard.
>
> *v1.1 highlight (still load-bearing)*: in multi-turn agent
> usage, the choice of context method matters far less for
> *quality* — the score range collapses 7× (0.42 → 0.06) as the
> agent rescues weak contexts via tool calls. See the
> [agent-loop leaderboard](leaderboard.html#agent-loop-leaderboard--v11).

> *Recent finding (2026-05-21, from the 420-row agent-loop
> trajectory dataset)*: **input tokens dominate output by 40×**
> (97.6% vs 2.4%) in agent-loop diagnosis, and agents barely use
> `read_file` (2.2% of tool calls in CI diagnosis — the rest is
> grep / tail / view_log_lines). Worst-case agent runs cost 4-5×
> the median, all on v2/stress huge logs. Implications for
> reduction-tool design in
> [`docs/analysis/agent-trajectory-token-anatomy.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/analysis/agent-trajectory-token-anatomy.md).

## What it measures

LogDx-CI compares **11 context providers** — `raw`, `tail`, `grep`,
three [RTK](https://github.com/rtk-ai/rtk) modes (`rtk-read`,
`rtk-log`, `rtk-err-cat`), two real LLM summarizers
(`llm-summary-v1-haiku` Anthropic + `llm-summary-v1-gpt-5-mini`
OpenAI), and three hybrid routers — by handing the same CI failure
log to three debugger families (Claude Haiku 4.5, Claude Sonnet
4.6, OpenAI gpt-5-mini) and scoring the resulting root-cause
diagnoses against AI-drafted + author-verified ground truth.

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
    --protocol protocols/logdx-ci-v2-partial-2026-05-20.lock.json
```

## Reproducibility infrastructure

Every release carries:

- **Protocol lock** (`protocols/*.lock.json`) — SHA-pins 10 schemas +
  3 prompts + 4 evaluators + 10 baselines + 35 case files at the
  release commit.<br/>
  <sub>**Note on the 10-lock vs 11-headline split**: the lock pins
  the original v1.0 baseline set (10 providers, including the legacy
  `llm-summary-v1-mock` regex stub). The v1.2 headline leaderboard
  moves `llm-summary-v1-mock` to the appendix and promotes two real
  LLM-summary providers added on top of the lock —
  `llm-summary-v1-haiku` (v1.1.1) and `llm-summary-v1-gpt-5-mini`
  (v1.2) — so the public headline table has **11 methods**. Both real
  summarizers ship their own SHA-pinned shim scripts
  (`examples/summary_shim_claude_cli.py`,
  `examples/summary_shim_openai.py`) and pinned reducer configs; they
  are not yet promoted into the protocol-lock baseline list. A
  follow-up freeze (`logdx-ci-v1.2.lock.json` regenerated to include
  the two real summarizers) is on the v1.3 list.</sub>
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

This is a **v1.2 preprint** release.

1. **35 cases.** Per-case variance can shift macro means by ±0.05
   with future corpus expansion. The direction of the top-3 ∩
   finding is robust; absolute magnitudes are preliminary.
2. **Ground truth is AI-drafted (Claude Opus 4.7) + single-author
   verified** by Bowen Qin (NUS). Not independent human annotation.
3. **Three model families tested** (Anthropic Haiku 4.5 + Sonnet 4.6;
   OpenAI gpt-5-mini; OpenRouter Sonnet for the agent-loop diagnoser).
   Two unique vendors; adding Gemini / Llama / DeepSeek is the
   most-leveraged follow-up.
4. **No independent third-party reproduction** of the 35-case
   diagnoses (an earlier 16-case prototype subset had E2/E2b
   model-as-judge + E9 AI-assisted human review; the full set has
   not been re-scored by an outside party).
5. **gpt-5-mini reproducibility caveat**: reasoning-model variance
   means macro means are stable to ±0.02 across re-runs but per-case
   byte-equality is not guaranteed. Anthropic temp=0 paths
   (haiku-summary reducer, debugger-v1, debugger-v2) are not
   affected.
6. **20 historical exclusions** documented in
   `configs/historical_provider_error_exclusions.json`; the eval
   injects zero-score abstentions for those tuples so the
   denominator stays correct.

See the [full §5 caveats](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md#5-caveats)
for the complete list. Earlier release-by-release history
(v1.0 → v1.1 → v1.1.1 → v1.1.2 → v1.2) lives in
[`ROADMAP.md`](https://github.com/eyuansu62/LogDx/blob/main/ROADMAP.md).

## Roadmap

Next milestones (exploratory; see
[`ROADMAP.md`](https://github.com/eyuansu62/LogDx/blob/main/ROADMAP.md)
for the full schedule):

- **v1.3** — Model-family expansion (Gemini, Llama); cost-integrated
  ranking; agent-loop runs on Haiku 4.5 and gpt-5-mini; configured
  RTK baseline.
- **v2** — Train/holdout split decoupling, `fix_action` evaluation
  dimension, third-party independent reproduction.

## Citation

{% raw %}
```bibtex
@misc{qin2026logdx,
  title  = {{LogDx-CI}: Benchmarking CI Log Reduction Tools
           for LLM Root-Cause Diagnosis},
  author = {Qin, Bowen},
  year   = {2026},
  howpublished = {\url{https://github.com/eyuansu62/LogDx}},
  note   = {v1.2 release; cases corpus at
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
