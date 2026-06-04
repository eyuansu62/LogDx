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
{% endraw %}

## APA-style

> Qin, B. (2026). *LogDx-CI: Benchmarking Log Reduction Tools
> for LLM Root-Cause Diagnosis*. arXiv preprint arXiv:2605.28876.
> <https://arxiv.org/abs/2605.28876>

## IEEE-style

> B. Qin, "LogDx-CI: Benchmarking Log Reduction Tools for
> LLM Root-Cause Diagnosis," 2026, *arXiv:2605.28876*.
> [Online]. Available: <https://arxiv.org/abs/2605.28876>

## Plain text

> LogDx-CI v1.2 (2026), Bowen Qin (NUS).
> arXiv: <https://arxiv.org/abs/2605.28876>.
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
