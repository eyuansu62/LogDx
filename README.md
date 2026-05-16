# LogDx-CI

> A reproducible benchmark for **failure-context strategies in CI log
> diagnosis**. Does an LLM still have enough evidence to identify the
> root cause after a CI log is filtered, summarized, or compressed?

[![CI](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml/badge.svg)](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/eyuansu62/LogDx?include_prereleases&label=release)](https://github.com/eyuansu62/LogDx/releases/latest)
[![License: Apache-2.0 + CC-BY-4.0](https://img.shields.io/badge/license-Apache--2.0%20%2B%20CC--BY--4.0-blue)](LICENSE)
[![Dataset on HF](https://img.shields.io/badge/data-eyuansu71%2Flogdx--ci-yellow)](https://huggingface.co/datasets/eyuansu71/logdx-ci)

LogDx-CI compares 10 context providers (`raw`, `tail`, `grep`, three
`rtk-*` modes, an `llm-summary`, and three hybrid routers) by handing
the same CI failure log to three debugger families
(Claude Haiku 4.5, Claude Sonnet 4.6, OpenAI gpt-5-mini) and scoring
the resulting root-cause diagnoses against AI-drafted +
author-verified ground truths.

It optimizes for **method ranking stability** across model families,
not "which LLM scored highest."

## Headline finding (v2)

> v2 produces cross-family-stable AND cross-run-stable rankings;
> v1.3's stability is narrower.

On the 19-case v2 corpus, Sonnet 4.6 / Haiku 4.5 / gpt-5-mini all
agree on **top-3 ∩ = `{hybrid-v2, hybrid-v3}`** and on the bottom-4.
On v1.3 the top-3 intersection narrows to `{hybrid-v1}` only — its
4k-token threshold is overfit to the v1.3 case distribution and does
**not** generalize.

| Corpus | Top-3 ∩ (all 3 debuggers) | Stability |
|---|---|---|
| v1.3 (16 cases) | `{hybrid-v1}` only | narrow |
| **v2 (19 cases)** | **`{hybrid-v2, hybrid-v3}`** | cross-family + cross-run |

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

This is a `v2-partial` preprint:

- 19 / 34 v2 cases (Batches 7–8 pending)
- Ground truth is AI-drafted + single-author verified (not
  independent human annotation)
- Three model families tested (Haiku / Sonnet / gpt-5-mini)
- 20 documented historical exclusions in
  [`configs/historical_provider_error_exclusions.json`](configs/historical_provider_error_exclusions.json)
  appear as zero-score abstentions in the eval denominator

Full §5 caveats in the
[v2 report](reports/e10_v2_generalization_partial.md#5-caveats).

## Cite

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

## License

- **Code** (`tools/`, `examples/`, `schemas/`, `configs/`,
  `prompts/`, tests, scripts) — Apache-2.0 ([LICENSE](LICENSE))
- **Data + reports + protocol locks** (`cases/`, `results/`,
  `reports/`, `protocols/`, `docs/`) — CC-BY-4.0
  ([LICENSE-DATA](LICENSE-DATA))

## Contributing

New context-provider methods, debugger families, and case
contributions are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the dev environment, repo layout, validator scripts, and the
"add a new method" checklist.

## Contact

Bowen Qin · National University of Singapore · contact via
[GitHub Issues](https://github.com/eyuansu62/LogDx/issues)
