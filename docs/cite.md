---
title: "Citation"
description: "How to cite LogDx-CI."
---

# Cite LogDx-CI

[← Home](index.html) · [Leaderboard](leaderboard.html)

If your work uses LogDx-CI's cases corpus, evaluation methodology,
or context-strategy findings, please cite the v2-partial release:

## BibTeX

{% raw %}
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
{% endraw %}

## APA-style

> Qin, B. (2026). *LogDx-CI: A Reproducible Benchmark for
> Failure-Context Strategies in CI Log Diagnosis* (v2-partial)
> [Computer software / dataset]. GitHub.
> <https://github.com/eyuansu62/LogDx>

## IEEE-style

> B. Qin, "LogDx-CI: A Reproducible Benchmark for Failure-Context
> Strategies in CI Log Diagnosis," GitHub repository, v2-partial,
> 2026. [Online]. Available: <https://github.com/eyuansu62/LogDx>

## Plain text

> LogDx-CI v2-partial (2026), Bowen Qin (NUS).
> Code: <https://github.com/eyuansu62/LogDx>.
> Cases corpus: <https://huggingface.co/datasets/eyuansu71/logdx-ci>.
> Licenses: Apache-2.0 (code), CC-BY-4.0 (data + reports).

## CITATION.cff

GitHub's "Cite this repository" button reads
[`CITATION.cff`](https://github.com/eyuansu62/LogDx/blob/main/CITATION.cff)
directly. Click the right-hand panel on the repo page → **Cite this
repository** → APA / BibTeX.

## When you should also cite v1.3

The v1.3 finding (`hybrid-grep-4k-rtk-err-cat-v1` matches grep at
1/3 the cost on the 16-case v1.3 benchmark) stands on the v1.3
corpus. If your work uses v1.3 results specifically (e.g. citing the
hybrid-v1 cost-effectiveness claim), also cite the v1.3 reports
listed at the bottom of the [project README](https://github.com/eyuansu62/LogDx/blob/main/README.md).

## Author

**Bowen Qin** · National University of Singapore

Maintained at <https://github.com/eyuansu62/LogDx>; contact via
[GitHub Issues](https://github.com/eyuansu62/LogDx/issues).
Issues / PRs welcome. New context-provider methods can be benchmarked
by adding a config in `configs/baselines/` and submitting their
output manifests; the three release gates will validate consistency
before merge.

[← Home](index.html) · [Leaderboard](leaderboard.html)
