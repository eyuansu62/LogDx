# LogDx-CI

> A benchmark for **log reduction tools**
> ([RTK](https://github.com/rtk-ai/rtk), grep, tail, hybrid routers,
> LLM-summary) — do they preserve enough evidence for LLM root-cause
> diagnosis?

[![arXiv](https://img.shields.io/badge/arXiv-2605.28876-b31b1b.svg)](https://arxiv.org/abs/2605.28876)
[![PyPI](https://img.shields.io/pypi/v/logdx-ci.svg?label=pip%20install%20logdx-ci&color=blue)](https://pypi.org/project/logdx-ci/)
[![CI](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml/badge.svg)](https://github.com/eyuansu62/LogDx/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/eyuansu62/LogDx?include_prereleases&label=release)](https://github.com/eyuansu62/LogDx/releases/latest)
[![License: Apache-2.0 + CC-BY-4.0](https://img.shields.io/badge/license-Apache--2.0%20%2B%20CC--BY--4.0-blue)](LICENSE)
[![Dataset on HF](https://img.shields.io/badge/data-eyuansu71%2Flogdx--ci-yellow)](https://huggingface.co/datasets/eyuansu71/logdx-ci)

LogDx-CI compares **12 context providers** (`raw`, `tail`, `grep`,
three [RTK](https://github.com/rtk-ai/rtk) modes, two real LLM
summarizers, three hybrid routers, plus
[Headroom](https://github.com/chopratejas/headroom)) by handing the
same CI failure log to three debugger families (Claude Haiku 4.5,
Claude Sonnet 4.6, OpenAI gpt-5-mini) and scoring the resulting
root-cause diagnoses against AI-drafted + author-verified ground
truths. It optimizes for **method ranking stability** across model
families, not "which LLM scored highest."

## Evaluate your own reducer in 5 minutes

Have a function that takes a CI log and returns a reduced version?
You can rank it against all 12 reference methods with **zero setup —
no clone, no API key, no money:**

```bash
pip install logdx-ci
```

```python
import logdx_ci

def my_reducer(raw_log: str) -> str:
    # your logic here — e.g. keep only the last 200 lines
    return "\n".join(raw_log.split("\n")[-200:])

result = logdx_ci.evaluate(reducer=my_reducer)   # all 35 cases, ~5 sec
print(result.summary())                          # score + table vs 12 baselines
```

The corpus + scoring code is auto-fetched (~20 MB) on first call and
cached. The default `diagnoser="static-signal-recall"` does **not** call
any LLM — it scores whether your reducer preserved the ground-truth
`required_signals`. Deterministic, free, runs in under a second.

For leaderboard-comparable diagnosis-quality scoring, pass
`diagnoser="real-debugger-v2"` (Claude Sonnet 4.6 via the `claude` CLI;
~$0.03 / case) or `"real-debugger-v1"` (Haiku 4.5, ~$0.005 / case) or
`"real-debugger-v3"` (gpt-5-mini, ~$0.006 / case, needs
`OPENAI_API_KEY`). Diagnoses are cached per `(diagnoser, case_id,
reduced_context_hash)`, so reruns are free.

Full SDK tutorial: [`logdx_ci/README.md`](logdx_ci/README.md). External
evaluation example (Headroom): [`docs/external-evaluations/headroom_logcompressor_default.md`](docs/external-evaluations/headroom_logcompressor_default.md).

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
| 3 | `llm-summary-v1-gpt-5-mini`<br/><sub>*(new in v1.2; agent-loop #1 at 0.749)*</sub> | 0.654 | 0.686 | 0.652 | **0.664** |
| 4 | `grep`                      | 0.578 | 0.684 | 0.655 | 0.639 |
| 5 | `llm-summary-v1-haiku`<br/><sub>*(promoted to headline in v1.1)*</sub> | 0.583 | 0.704 | 0.608 | 0.632 |
| 6 | `tail-200`                  | 0.595 | 0.624 | 0.623 | 0.614 |
| 7 | `hybrid-grep-4k-rtk-err-cat`<br/><sub>*(earlier 4k-threshold hybrid; replaced)*</sub> | 0.552 | 0.597 | 0.571 | 0.573 |
| 8 | `headroom-LogCompressor`<br/><sub>*([Headroom](https://github.com/chopratejas/headroom) v0.24.0 defaults; evaluated via the SDK)*</sub> | 0.548 | 0.601 | 0.534 | 0.561 |
| 9 | `rtk-err-cat`               | 0.455 | 0.488 | 0.467 | 0.470 |
| 10 | `raw`                      | 0.324 | 0.368 | 0.367 | 0.353 |
| 11 | `rtk-read`                 | 0.329 | 0.369 | 0.349 | 0.349 |
| 12 | `rtk-log`                  | 0.238 | 0.262 | 0.249 | 0.249 |

The legacy `llm-summary-v1-mock` stub (used as the LLM-summary
representative through v1.1) is retained as an appendix entry on
the leaderboard, not in the headline. The top-2 hybrids replaced an
earlier 4k-threshold hybrid that was overfit during methodology
development. See the [technical
report](reports/technical_report.md) for the v1.2 paper, and
[`reports/legacy/e10_v1_3_to_v2_transition_study.md`](reports/legacy/e10_v1_3_to_v2_transition_study.md)
for the original prototype-vs-formal corpus analysis.

Full leaderboard at <https://logdx-bench.github.io/leaderboard.html>.

## Quick links

| | |
|---|---|
| 🏠 Homepage | <https://logdx-bench.github.io/> |
| 📊 Leaderboard | <https://logdx-bench.github.io/leaderboard.html> |
| 📄 arXiv preprint | <https://arxiv.org/abs/2605.28876> |
| 📄 Full report | [`reports/technical_report.md`](reports/technical_report.md) |
| 🐍 Python SDK | [`logdx_ci/`](logdx_ci/) — `pip install logdx-ci`, evaluate your reducer in 5 min |
| 📦 Cases corpus mirror | <https://huggingface.co/datasets/eyuansu71/logdx-ci> |
| 📋 Release notes | latest: [`RELEASE_NOTES_v1_2.md`](RELEASE_NOTES_v1_2.md) · history: [`RELEASE_NOTES.md`](RELEASE_NOTES.md) (v1.0), [v1.1.1](RELEASE_NOTES_v1_1_1.md), [v1.1.2](RELEASE_NOTES_v1_1_2.md) |
| 📑 Cite | [`CITATION.cff`](CITATION.cff) · [BibTeX](https://logdx-bench.github.io/cite.html) |

## Browse the cases directly

Each case lives under `cases/<split>/<case_id>/{raw.log, case.json,
ground_truth.json, tags.json, privacy_audit.json}`. Schema in the
[dataset card](https://huggingface.co/datasets/eyuansu71/logdx-ci).
The SDK auto-downloads them on first use — the only reason to clone
the repo is if you're reproducing the leaderboard or contributing.

## For benchmark maintainers (reproduce the leaderboard)

The numbers above were generated through the canonical pipeline in
`tools/`, which writes auditable manifest artifacts to `results/`
(committed to git for long-term reproducibility). To regenerate them
from a clean checkout:

```bash
git clone https://github.com/eyuansu62/LogDx.git && cd LogDx
python tools/run_baseline.py     --method tail-200 --split dev
python tools/run_diagnosis.py    --diagnoser real-debugger-v2 \
                                 --split dev --method tail-200
python tools/evaluate_diagnosis.py --split dev --diagnoser real-debugger-v2
```

The SDK (`logdx_ci.evaluate(...)`) re-uses the same scorer + diagnoser
shims, so SDK scores are bit-for-bit comparable to leaderboard numbers
— but the SDK doesn't write the committed-artifact audit trail. Use
the SDK to *try* a new reducer; use `tools/` to *enshrine* a method on
the leaderboard.

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
[technical report §5](reports/technical_report.md#6-caveats-and-limitations).

## Cite

```bibtex
@article{qin2026logdx,
  title         = {{LogDx-CI}: Benchmarking Log Reduction Tools
                  for LLM Root-Cause Diagnosis},
  author        = {Qin, Bowen},
  year          = {2026},
  eprint        = {2605.28876},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE},
  url           = {https://arxiv.org/abs/2605.28876},
  note          = {v1.2 release; cases corpus at
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
