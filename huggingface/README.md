---
license: cc-by-4.0
pretty_name: "LogDx-CI: Benchmark for Log Reduction Tools"
language:
  - en
tags:
  - benchmark
  - ci-cd
  - log-analysis
  - log-reduction
  - root-cause-analysis
  - rtk
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
        path: "metadata/dev.jsonl"
      - split: holdout
        path: "metadata/holdout.jsonl"
      - split: stress
        path: "metadata/stress.jsonl"
      - split: v2_dev
        path: "metadata/v2_dev.jsonl"
      - split: v2_holdout
        path: "metadata/v2_holdout.jsonl"
      - split: v2_stress
        path: "metadata/v2_stress.jsonl"
---

# LogDx-CI

A benchmark for **log reduction tools**
([RTK](https://github.com/rtk-ai/rtk), grep, tail, hybrid routers,
LLM-summary) — do they preserve enough evidence for LLM root-cause
diagnosis?

- **Homepage**: <https://logdx-bench.github.io/>
- **Code & evaluator**: <https://github.com/eyuansu62/LogDx>
- **Headline report**: [`reports/technical_report.md`](https://github.com/eyuansu62/LogDx/blob/main/reports/technical_report.md)
- **Release notes**: [`RELEASE_NOTES.md`](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md) (latest: [`RELEASE_NOTES_v1_2.md`](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES_v1_2.md))
- **Current release**: `v1.2`
- **License**: CC-BY-4.0 (data, this repo); Apache-2.0 (code, GH repo)

## Two ways to use this dataset

LogDx-CI ships in two formats on this HF repo. They contain the same
underlying 35 cases — pick the one that matches your use case.

| Format | What you get | When to use |
|---|---|---|
| **Dataset Viewer / `load_dataset` (`metadata/<split>.jsonl`)** | Flat 27-column table: per-case metadata + tags + `root_cause.{category,summary}`. 35 rows across 6 splits. No raw logs, no full ground-truth annotations. | Browsing the corpus on the HF viewer, filtering by category / ecosystem / split, building dashboards. |
| **Full per-case bundle (`cases/<split>/<case_id>/`)** | 4 files per case: `raw.log`, `case.json`, `ground_truth.json` (full nested annotations: required_signals, evidence_spans, relevant_files, expected_diagnosis, …), `tags.json`. | Running the benchmark, training, or any work that needs the raw log or full ground truth. Fetch via `huggingface_hub.snapshot_download(repo_id, repo_type="dataset")`. |

The viewer is intentionally schema-flat (the per-case ground-truth files
are deeply nested and aren't a clean table) — see [the
`tools/build_hf_metadata.py` script in the code
repo](https://github.com/eyuansu62/LogDx/blob/main/tools/build_hf_metadata.py)
for the exact field list and how it's derived.

## What's in the full per-case bundle

| File | Purpose |
|------|---------|
| `raw.log` | The full CI failure log (passed through privacy audit) |
| `case.json` | Safe metadata: repo, framework, workflow/job names, failure_category, line/byte counts |
| `ground_truth.json` | AI-drafted + author-verified root cause, required signals, relevant files/tests, must-mention checklist, forbidden claims |
| `tags.json` | Ecosystem, language, CI provider, signal_position, evidence_formats, multi_failure flag, etc. |
| `privacy_audit.json` | Per-case audit trail of redactions / truncation flags |

## Split sizes

| Split | Cases | Notes |
|-------|------:|-------|
| `dev`         |  5 | v1 prototype-wave dev |
| `holdout`     |  5 | v1 prototype-wave holdout |
| `stress`      |  6 | v1 prototype-wave stress |
| `v2_dev`      |  3 | v2 formal-wave dev |
| `v2_holdout`  | 10 | v2 formal-wave holdout |
| `v2_stress`   |  6 | v2 formal-wave stress |
| **Total**     | **35** | |

Both waves are part of the canonical v1.2 corpus. The two-wave split
reflects methodology-development history; see [the release notes
"internal naming" section](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md#a-note-on-internal-naming).

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

## Headline finding

> Across **35 real CI failure cases** and **3 model families**
> (Claude Haiku 4.5, Claude Sonnet 4.6, OpenAI gpt-5-mini),
> top-3 ∩ = `{hybrid-grep-120k-rtk-tail, hybrid-grep-120k-tail}`
> and bottom-4 set are stable across all three families.

| Rank | Method | Overall (case-weighted) |
|----:|--------|------------------------:|
| 1 | `hybrid-grep-120k-rtk-tail` | **0.670** |
| 2 | `hybrid-grep-120k-tail` | **0.666** |
| 3 | `llm-summary-v1-gpt-5-mini` *(new in v1.2; agent-loop #1 at 0.749)* | **0.664** |
| 4 | `grep` | 0.639 |
| 5 | `llm-summary-v1-haiku` *(real Haiku summarizer; promoted to headline in v1.1)* | 0.632 |
| 6 | `tail-200` | 0.614 |
| ... | (see [the full leaderboard](https://logdx-bench.github.io/leaderboard.html)) | |

The top-2 hybrids replaced an earlier 4k-threshold hybrid that was
overfit during methodology development. See the [technical
report §3](https://github.com/eyuansu62/LogDx/blob/main/reports/technical_report.md)
for the prototype-vs-formal corpus analysis.

## How to use

### Option 1 — Browse / filter via `load_dataset` (flat metadata only)

```python
from datasets import load_dataset

ds = load_dataset("eyuansu71/logdx-ci")
print(ds)
# DatasetDict with 6 splits: dev, holdout, stress, v2_dev, v2_holdout, v2_stress

# Filter by failure category
compile_errors = ds["v2_holdout"].filter(
    lambda row: row["failure_category"] == "compile_error"
)
print(compile_errors[0]["repo"], compile_errors[0]["root_cause_summary"])
```

This loads the flat metadata table (27 columns, 35 rows) — the same
view as the HF dataset viewer. No raw logs, no full nested ground
truth.

### Option 2 — Full per-case bundle (raw logs + nested ground truth)

```python
from huggingface_hub import snapshot_download
import json
from pathlib import Path

local_dir = snapshot_download(
    repo_id="eyuansu71/logdx-ci",
    repo_type="dataset",
)

# Each case lives at cases/<split>/<case_id>/
case_dir = Path(local_dir) / "cases" / "v2" / "dev" / "moby-buildx-bake-v2-001"
case = json.loads((case_dir / "case.json").read_text())
truth = json.loads((case_dir / "ground_truth.json").read_text())
tags  = json.loads((case_dir / "tags.json").read_text())
raw_log = (case_dir / "raw.log").read_text()

print(case["repo"], case["framework"], case["line_count"])
print(truth["root_cause"]["category"], truth["root_cause"]["summary"])
# Full nested annotations also available:
for sig in truth["required_signals"]:
    print(sig["type"], sig["value"], sig["importance"])
```

Use this path when you need raw logs or the full nested ground-truth
annotations (required_signals, evidence_spans, relevant_files,
expected_diagnosis, must-mention checklist, forbidden claims).

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
recorded across all 35 cases on the 2026-05-20 v1.2 release pass.

## Caveats

This is the **v1.2 preprint** release. The cross-family direction
is robust to ship; per-case magnitudes are preliminary. Headline
limitations:

1. **35 cases** — corpus target 50+ for v1.3.
2. **Ground truth is AI-drafted (Claude Opus 4.7) + single-author
   verified** by the project author. Not independent human
   annotation.
3. **Three model families tested** (Anthropic Haiku 4.5 + Sonnet
   4.6 via OAuth / API; OpenAI gpt-5-mini via API; OpenRouter
   Sonnet 4.6 for the agent-loop diagnoser). Two unique vendors;
   adding Gemini / Llama / DeepSeek is the most-leveraged follow-up.
4. **No independent third-party reproduction** (an earlier 16-case
   prototype subset had E2/E2b model-as-judge + E9 AI-assisted
   human review; the full 35-case set has not been re-scored by
   an outside party).
5. **gpt-5-mini reproducibility caveat**: reasoning-model variance
   means macro means are stable to ±0.02 across re-runs but
   per-case byte-equality is not guaranteed.
6. **20 historical exclusions** documented in
   `configs/historical_provider_error_exclusions.json` (in the
   code repo); the eval injects zero-score abstentions for those
   tuples so the denominator stays correct.

See [`reports/technical_report.md`](https://github.com/eyuansu62/LogDx/blob/main/reports/technical_report.md) §5
for the full list.

## Citation

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

## Acknowledgements

- **[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk)** by
  rtk-ai — `rtk-read`, `rtk-log`, `rtk-err-cat` baselines + the
  intermediate / fallback step in the `hybrid-grep-120k-rtk-tail`
  and `hybrid-grep-4k-rtk-err-cat` routers all invoke the `rtk` CLI
  binary.
- CI failure logs sourced from publicly visible
  [GitHub Actions](https://github.com/features/actions) runs.
- Diagnoses produced by [Claude](https://www.anthropic.com)
  (Anthropic) and [gpt-5-mini](https://openai.com) (OpenAI).

## Contact

- Author: Bowen Qin (National University of Singapore)
- Issues: file at <https://github.com/eyuansu62/LogDx/issues>
