# LogDx-CI

> A benchmark for **CI log reduction tools**
> ([RTK](https://github.com/rtk-ai/rtk), grep, tail, hybrid routers,
> LLM-summary) — do they preserve enough evidence for LLM root-cause
> diagnosis?

[![CI](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml/badge.svg)](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/eyuansu62/LogDx?include_prereleases&label=release)](https://github.com/eyuansu62/LogDx/releases/latest)
[![License: Apache-2.0 + CC-BY-4.0](https://img.shields.io/badge/license-Apache--2.0%20%2B%20CC--BY--4.0-blue)](LICENSE)
[![Dataset on HF](https://img.shields.io/badge/data-eyuansu71%2Flogdx--ci-yellow)](https://huggingface.co/datasets/eyuansu71/logdx-ci)

LogDx-CI compares 10 context providers (`raw`, `tail`, `grep`, three
[RTK](https://github.com/rtk-ai/rtk) modes (`rtk-read`, `rtk-log`,
`rtk-err-cat`), an `llm-summary`, and three hybrid routers) by
handing the same CI failure log to three debugger families
(Claude Haiku 4.5, Claude Sonnet 4.6, OpenAI gpt-5-mini) and scoring
the resulting root-cause diagnoses against AI-drafted +
author-verified ground truths.

It optimizes for **method ranking stability** across model families,
not "which LLM scored highest."

## Headline finding

> Across **35 real CI failure cases** and **3 model families**
> (Claude Haiku 4.5, Claude Sonnet 4.6, OpenAI gpt-5-mini),
> the **top-3 ∩** of the per-family rankings is
> `{hybrid-grep-120k-rtk-tail, hybrid-grep-120k-tail}`. Bottom-4
> set is also stable across all three families.

Macro `diagnosis_score_v1_1` aggregated case-count-weighted across
the 35-case corpus:

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Overall |
|----:|--------|----------:|----------:|----------:|--------:|
| 1 | `hybrid-grep-120k-rtk-tail` | 0.624 | 0.679 | 0.706 | **0.670** |
| 2 | `hybrid-grep-120k-tail`     | 0.610 | 0.730 | 0.658 | **0.666** |
| 3 | `grep`                      | 0.578 | 0.684 | 0.655 | 0.639 |
| 4 | `tail-200`                  | 0.595 | 0.624 | 0.623 | 0.614 |
| 5 | `hybrid-grep-4k-rtk-err-cat`<br/><sub>*(earlier 4k-threshold hybrid; replaced)*</sub> | 0.552 | 0.597 | 0.571 | 0.573 |
| 6 | `rtk-err-cat`               | 0.455 | 0.488 | 0.467 | 0.470 |
| 7 | `raw`                       | 0.324 | 0.368 | 0.367 | 0.353 |
| 8 | `rtk-read`                  | 0.329 | 0.369 | 0.349 | 0.349 |
| 9 | `llm-summary-v1-mock`       | 0.343 | 0.348 | 0.294 | 0.328 |
| 10 | `rtk-log`                  | 0.238 | 0.262 | 0.249 | 0.249 |

The top-2 hybrids replaced an earlier 4k-threshold hybrid that was
overfit during methodology development. See [§3 of the technical
report](reports/e10_v2_generalization_partial.md) for the
prototype-vs-formal corpus analysis.

Full leaderboard at <https://logdx-bench.github.io/leaderboard.html>.

## Quick links

| | |
|---|---|
| 🏠 Homepage | <https://logdx-bench.github.io/> |
| 📊 Leaderboard | <https://logdx-bench.github.io/leaderboard.html> |
| 📄 Full report | [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md) |
| 📦 Cases corpus mirror | <https://huggingface.co/datasets/eyuansu71/logdx-ci> |
| 📋 Release notes | [`RELEASE_NOTES.md`](RELEASE_NOTES.md) |
| 📑 Cite | [`CITATION.cff`](CITATION.cff) · [BibTeX](https://logdx-bench.github.io/cite.html) |

## Use the data

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# Each case lives under cases/<split>/<case_id>/{raw.log,case.json,
# ground_truth.json,tags.json,privacy_audit.json}. See the dataset
# card for the schema:
# https://huggingface.co/datasets/eyuansu71/logdx-ci
```

To reproduce a number from the leaderboard:

```bash
python3 tools/evaluate_diagnosis.py \
    --split v2/dev --diagnoser real-debugger-v3
# → results/v2/dev/eval_diagnosis_real-debugger-v3.json
```

For a fresh run that actually hits the OpenAI / Anthropic APIs (vs.
cache replay), see the [reproducibility section in
`RELEASE_NOTES.md`](RELEASE_NOTES.md#reproducibility).

## Caveats

**Current release: `v1.2`** (preprint). We'll add cases + model
families before calling it stable.

- 35 cases (target: 50+ with broader ecosystem coverage)
- Ground truth is AI-drafted + single-author verified (not
  independent human annotation)
- Three model families tested (Haiku / Sonnet / gpt-5-mini); GPT-4o
  / Gemini / Llama are the most-leveraged follow-up
- 20 documented historical exclusions in
  [`configs/historical_provider_error_exclusions.json`](configs/historical_provider_error_exclusions.json)
  appear as zero-score abstentions in the eval denominator

Full caveats in the
[technical report §5](reports/e10_v2_generalization_partial.md#5-caveats).

## Cite

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

## License

- **Code** (`tools/`, `examples/`, `schemas/`, `configs/`,
  `prompts/`, tests, scripts) — Apache-2.0 ([LICENSE](LICENSE))
- **Data + reports + protocol locks** (`cases/`, `results/`,
  `reports/`, `protocols/`, `docs/`) — CC-BY-4.0
  ([LICENSE-DATA](LICENSE-DATA))

## Acknowledgements

LogDx-CI benchmarks third-party log-reduction tools alongside its
own baselines. Specifically:

- **[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk)** by
  rtk-ai — the `rtk-read`, `rtk-log`, and `rtk-err-cat` baselines
  are three different invocations of the `rtk` CLI binary. The
  hybrid routers `hybrid-grep-120k-rtk-tail` and
  `hybrid-grep-4k-rtk-err-cat` use rtk's `err-cat` mode as an
  intermediate / fallback context provider. See
  [`docs/methods/rtk.md`](docs/methods/rtk.md) for setup +
  invocation details.

CI failure logs are sourced from publicly visible
[GitHub Actions](https://github.com/features/actions) runs.
Diagnoses are produced by [Claude](https://www.anthropic.com)
(Anthropic) and [gpt-5-mini](https://openai.com) (OpenAI).

## Contributing

New context-provider methods, debugger families, and case
contributions are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the dev environment, repo layout, validator scripts, and the
"add a new method" checklist.

## Contact

Bowen Qin · National University of Singapore · contact via
[GitHub Issues](https://github.com/eyuansu62/LogDx/issues)
