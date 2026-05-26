---
title: "Citation"
description: "How to cite LogDx-CI."
---

# Cite LogDx-CI

[← Home](index.html) · [Leaderboard](leaderboard.html)

If your work uses LogDx-CI's cases corpus, evaluation methodology,
or log-reduction findings, please cite the v1.2 release:

## BibTeX

{% raw %}
```bibtex
@misc{qin2026logdx,
  title  = {{LogDx-CI}: Benchmarking Log Reduction Tools
           for LLM Root-Cause Diagnosis},
  author = {Qin, Bowen},
  year   = {2026},
  howpublished = {\url{https://github.com/eyuansu62/LogDx}},
  note   = {v1.2 release; cases corpus at
           \url{https://huggingface.co/datasets/eyuansu71/logdx-ci}},
}
```
{% endraw %}

## APA-style

> Qin, B. (2026). *LogDx-CI: Benchmarking Log Reduction Tools
> for LLM Root-Cause Diagnosis* (v1.2)
> [Computer software / dataset]. GitHub.
> <https://github.com/eyuansu62/LogDx>

## IEEE-style

> B. Qin, "LogDx-CI: Benchmarking Log Reduction Tools for
> LLM Root-Cause Diagnosis," GitHub repository, v1.2,
> 2026. [Online]. Available: <https://github.com/eyuansu62/LogDx>

## Plain text

> LogDx-CI v1.2 (2026), Bowen Qin (NUS).
> Code: <https://github.com/eyuansu62/LogDx>.
> Cases corpus: <https://huggingface.co/datasets/eyuansu71/logdx-ci>.
> Licenses: Apache-2.0 (code), CC-BY-4.0 (data + reports).

## CITATION.cff

GitHub's "Cite this repository" button reads
[`CITATION.cff`](https://github.com/eyuansu62/LogDx/blob/main/CITATION.cff)
directly. Click the right-hand panel on the repo page → **Cite this
repository** → APA / BibTeX.

## Author

**Bowen Qin** · National University of Singapore

Maintained at <https://github.com/eyuansu62/LogDx>; contact via
[GitHub Issues](https://github.com/eyuansu62/LogDx/issues).
Issues / PRs welcome. New context-provider methods can be benchmarked
by adding a config in `configs/baselines/` and submitting their
output manifests; the three release gates will validate consistency
before merge.

[← Home](index.html) · [Leaderboard](leaderboard.html)
