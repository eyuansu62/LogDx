---
license: cc-by-4.0
pretty_name: "LogDx-CI: Reproducible Benchmark for CI Log Diagnosis Context Strategies"
language:
  - en
tags:
  - benchmark
  - ci-cd
  - log-analysis
  - root-cause-analysis
  - context-engineering
  - retrieval
  - coding-agents
  - llm-evaluation
task_categories:
  - text-classification
  - question-answering
  - text-generation
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: dev
        path: "cases/dev/**/*.json"
      - split: holdout
        path: "cases/holdout/**/*.json"
      - split: stress
        path: "cases/stress/**/*.json"
      - split: v2_dev
        path: "cases/v2/dev/**/*.json"
      - split: v2_holdout
        path: "cases/v2/holdout/**/*.json"
      - split: v2_stress
        path: "cases/v2/stress/**/*.json"
---

# LogDx-CI

A reproducible benchmark for **failure-context strategies in CI log
diagnosis**. Does an LLM still have enough evidence to identify the
true root cause after a CI log is filtered, summarized, or compressed?

- **Homepage**: <https://logdx-bench.github.io/>
- **Code & evaluator**: <https://github.com/eyuansu62/LogDx>
- **Headline report**: [`reports/e10_v2_generalization_partial.md`](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)
- **Release notes**: [`RELEASE_NOTES.md`](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md)
- **Current release**: `v2-partial-2026-06-22`
- **License**: CC-BY-4.0 (data, this repo); Apache-2.0 (code, GH repo)

## What this dataset contains

**35 real GitHub Actions failure cases** across 6 splits, each with:

| File | Purpose |
|------|---------|
| `raw.log` | The full CI failure log (passed through privacy audit) |
| `case.json` | Safe metadata: repo, framework, workflow/job names, failure_category, line/byte counts |
| `ground_truth.json` | AI-drafted + author-verified root cause, required signals, relevant files/tests, must-mention checklist, forbidden claims |
| `tags.json` | Ecosystem, language, CI provider, signal_position, evidence_formats, multi_failure flag, etc. |
| `privacy_audit.json` | Per-case audit trail of redactions / truncation flags |

## Split sizes

| Split | v1.3 legacy | v2 new | Total |
|-------|------------:|-------:|------:|
| `dev` | 5 | 3 | 8 |
| `holdout` | 5 | 10 | 15 |
| `stress` | 6 | 6 | 12 |
| **Total** | **16** | **19** | **35** |

## Coverage

**8 failure categories**: `test_assertion`, `compile_error`,
`type_error`, `lint_failure`, `dependency_install`, `docker_build`,
`timeout_or_oom`, `multi_failure`, with `scattered` and
`matrix_or_monorepo_failure` as cross-cutting tags.

**7+ ecosystems**: pytest (Python), cargo (Rust), `go test`, Maven
(Java), pnpm + jest + biome (Node), docker buildx, helm/k8s,
terraform, gradle, gh CLI Go-test, hibernate, dubbo-samples,
argocd, prettier, mypy/pandas, tsc/typescript, cpython tcl,
airflow pre-commit, nodejs+pubsub timeouts, biome pnpm-not-found,
moby buildx-bake, pip + GitHub Actions network, go-redis pubsub.

## Headline finding (v2)

> **v2 produces cross-family-stable AND cross-run-stable benchmark
> rankings; v1.3's stability is narrower.**

On the 19-case v2 corpus, Sonnet 4.6 / Haiku 4.5 / gpt-5-mini all
agree on **top-3 ∩ = `{hybrid-v2, hybrid-v3}`** and on the bottom-4
set. On v1.3 the top-3 intersection narrows to `{hybrid-v1}` only.

| Corpus | Top-3 ∩ (all 3 debuggers) | Bottom-4 set | Stability |
|---|---|---|---|
| v1.3 (16) | `{hybrid-v1}` only | raw, rtk-log, llm-summary-mock, rtk-read | narrow |
| **v2 (19)** | **`{hybrid-v2, hybrid-v3}`** | same bottom-4 | cross-family + cross-run |

The v1.3-tuned `hybrid-grep-4k-rtk-err-cat-v1` does NOT generalize to
v2 — its 4k-token threshold is overfit to the v1.3 case distribution.

## How to use

```python
# Download via the unified hf CLI (pip install huggingface_hub; hf auth login)
# (the dataset's primary format is per-case JSON + raw.log files,
# not a single HF Dataset table)
from huggingface_hub import snapshot_download

local_dir = snapshot_download(
    repo_id="eyuansu71/logdx-ci",
    repo_type="dataset",
)

# Each case lives at cases/<split>/<case_id>/
import json
from pathlib import Path

case_dir = Path(local_dir) / "cases" / "v2" / "dev" / "moby-buildx-bake-v2-001"
case = json.loads((case_dir / "case.json").read_text())
truth = json.loads((case_dir / "ground_truth.json").read_text())
tags  = json.loads((case_dir / "tags.json").read_text())
raw_log = (case_dir / "raw.log").read_text()

print(case["repo"], case["framework"], case["line_count"])
print(truth["root_cause"]["category"], truth["root_cause"]["summary"])
```

To run the full benchmark (context providers + diagnosers + evaluator),
clone the **code repository** at <https://github.com/eyuansu62/LogDx>:

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx
# Cases corpus is committed in this repo too; HF is a mirror.

# Run the 165-test suite
python3 tools/tests/test_diagnosis_cache_key.py
python3 tools/tests/test_hybrid_router.py

# Run release-gate validators
python3 tools/validate_committed_diagnosis_provider_errors.py
python3 tools/validate_eval_manifest_consistency.py
python3 tools/validate_diagnosis_vs_context_consistency.py
```

## Privacy

The raw CI logs come from publicly visible GitHub Actions runs.
Each log was passed through `tools/audit_context_privacy.py` (200k-
line cap, fail-closed on truncation or long-line splits) before
commit. Per-case redactions are documented in
`privacy_audit.json` and `tags.json#repo_visibility`. Zero hits
recorded across all 35 cases on the 2026-06-22 release pass.

## Caveats

This is the **v2-partial preprint** release. The cross-family
direction is robust to ship; the per-case magnitudes are preliminary.
Headline limitations:

1. **19 / 34 v2 cases** — Batches 7–8 pending to reach corpus target.
2. **Ground truth is AI-drafted (Claude Opus 4.7) + single-author
   verified** by the project author. Not independent human
   annotation.
3. **Three model families tested.** Adding GPT-4o / Gemini / Llama
   variants is the most-leveraged follow-up.
4. **No human review of v2 diagnoses yet.** v1.1 calibration is
   re-used unchanged from v1.3.
5. **20 historical exclusions** documented in
   `configs/historical_provider_error_exclusions.json` (in the
   code repo); the eval injects zero-score abstentions for those
   tuples so the denominator stays correct.

See [`reports/e10_v2_generalization_partial.md`](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md) §5
for the full list.

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

## Contact

- Author: Bowen Qin (National University of Singapore)
- Email: bowen@lum.id
- Issues: file at <https://github.com/eyuansu62/LogDx/issues>
