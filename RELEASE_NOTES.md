# LogDx-CI v2-partial — Release Notes

**Tag**: `v2-partial-2026-06-22`
**Protocol lock**: [`cilogbench-v2-checkpoint-19.lock.json`](protocols/cilogbench-v2-checkpoint-19.lock.json)
**Headline report**: [`reports/e10_v2_generalization_partial.md`](reports/e10_v2_generalization_partial.md)
**Cases corpus mirror**: [`huggingface.co/datasets/eyuansu71/logdx-ci`](https://huggingface.co/datasets/eyuansu71/logdx-ci)

## TL;DR

LogDx-CI evaluates whether CI failure-context strategies preserve
enough evidence for coding agents to identify the true root cause.
v2-partial extends the v1.3 frozen protocol (16 cases) with 19
new v2 cases (target 34) across three model families and three
splits, and ships three release-gate scripts that pin reproducibility
across config / shim / cache drift and provider-error leakage.

## What's in this release

**Corpus (35 cases total)**

| Split | v1.3 legacy | v2 new | Total |
|-------|------------:|-------:|------:|
| `dev` | 5 | 3 | 8 |
| `holdout` | 5 | 10 | 15 |
| `stress` | 6 | 6 | 12 |
| **All** | **16** | **19** | **35** |

v2 case coverage spans 8 failure categories (test_assertion,
compile_error, type_error, lint_failure, dependency_install,
docker_build, timeout_or_oom, multi_failure, scattered) and 7+
ecosystems (pytest, cargo, go test, Maven, pnpm, docker buildx,
helm/k8s, terraform).

**Context providers evaluated (10)**

- baseline: `raw`, `tail-200`, `grep`
- rtk: `rtk-read`, `rtk-log`, `rtk-err-cat`
- LLM-summary: `llm-summary-v1-mock`, `llm-summary-v1-haiku`
- hybrid routers:
  - `hybrid-grep-4k-rtk-err-cat-v1` (v1.3-tuned)
  - `hybrid-grep-120k-tail-v2` (v2)
  - `hybrid-grep-120k-rtk-tail-v3` (v3, with `metadata.rtk_input_truncated` gating)

**Debuggers tested (3 families)**

- `real-debugger-v1` — Claude Haiku 4.5
- `real-debugger-v2` — Claude Sonnet 4.6
- `real-debugger-v3` — OpenAI gpt-5-mini (canonical resolved_model
  pinned to `gpt-5-mini-2025-08-07`)

**Evaluation**

`tools/evaluate_diagnosis.py` produces per-method macro means of:
- `diagnosis_score_v1_1` (primary; v1.1 calibrated)
- category_accuracy / category_match_score_v1_1
- required + critical signal-mention recall
- relevant-file / relevant-test recall
- must_mention coverage
- forbidden-claim rate
- valid-evidence-quote rate
- abstention + confident-error rates

## Headline finding (§3i)

> **v2 produces cross-family-stable AND cross-run-stable benchmark
> rankings; v1.3's stability is narrower.**

On v2, Sonnet 4.6 / Haiku 4.5 / gpt-5-mini agree on
top-3 ∩ = `{hybrid-v2, hybrid-v3}` and on bottom-4 set. On v1.3 the
top-3 intersection narrows to `{hybrid-v1}` only. v1.3's
`hybrid-grep-4k-rtk-err-cat-v1` does **not** generalize to v2 —
its 4k-token threshold is overfit to the v1.3 case distribution.

## Reproducibility

```bash
# clone
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# (optional) pull the cases corpus from HF
# the same files are also tracked in this repo under cases/
huggingface-cli download --repo-type dataset \
    eyuansu71/logdx-ci --local-dir cases-from-hf

# validate the canonical protocol lock
python3 tools/validate_protocol_lock.py \
    --protocol protocols/cilogbench-v2-checkpoint-19.lock.json

# run the three release-gate scripts
python3 tools/validate_committed_diagnosis_provider_errors.py
python3 tools/validate_eval_manifest_consistency.py
python3 tools/validate_diagnosis_vs_context_consistency.py

# run the 165-test suite
python3 tools/tests/test_diagnosis_cache_key.py
python3 tools/tests/test_hybrid_router.py

# re-run a real debugger (requires API key + opt-in)
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
export OPENAI_API_KEY=...   # only needed for v3
python3 tools/run_diagnosis.py \
    --split dev --diagnoser command \
    --diagnoser-name real-debugger-v3 \
    --command "python3 examples/diagnosis_shim_openai.py" \
    --context-method grep \
    --diagnoser-config configs/diagnosers/real-debugger-v3.json
```

The canonical state has 285 successful v3 rows + 39
`unsupported_context_too_large:` graceful-refusal rows + 20
documented historical exclusions (see
`configs/historical_provider_error_exclusions.json`).

## What's NEW vs the v1.3 release

1. **Three model families** (v1.3 was Anthropic-only). cross-family
   stability is now a first-class finding.
2. **Hybrid-v2 and hybrid-v3 routers** with explicit fail-closed
   semantics for `rtk_input_truncated` (large logs that exceed
   rtk-err-cat's 10MiB internal cap).
3. **19 new v2 cases** (out of 34 target) covering
   `permission_or_secret`, `network_or_flaky`, `timeout_or_oom`,
   `multi_failure`, `scattered`, plus java-maven, pnpm, docker
   buildx, helm/k8s, terraform ecosystems.
4. **Three release-gate scripts** (CI-gateable):
   - `validate_committed_diagnosis_provider_errors.py` — no
     non-allowlisted `provider_error` prefixes ship in
     `results/<split>/diagnoses/real-debugger-*/`
   - `validate_eval_manifest_consistency.py` — every
     `eval_diagnosis_*.json`'s per-method case-ID set matches its
     manifest, with strict zero-score verification for excluded rows
   - `validate_diagnosis_vs_context_consistency.py` — every
     diagnosis manifest's case set ⊆ source context manifest, with
     an explicit `historical_provider_error_exclusions.json` for
     transparently-documented gaps
5. **Cache identity validation** — `metadata.diagnoser_config_sha256`
   + `metadata.shim_sha256` on every fresh row; runner rejects
   stale cache hits on config/shim edits.
6. **Hostname + secret redaction** (28 rounds of hardening) — non-
   public hostnames replaced with `<redacted-host sha=PREFIX>`;
   URL / bearer / API-key / long-opaque-token shapes redacted; raw
   model output and HTTP response bodies replaced with
   hash-only summaries.
7. **165 test cases** in `tools/tests/` covering unit / integration
   / end-to-end paths.

## Caveats (carry over from v2-partial)

This is a **preprint** release; do not retire v1.3 yet. The
v2 finding is robust to ship as preliminary results, but the
following limitations are explicit:

1. **19 / 34 v2 cases** — Batches 7–8 are pending. Per-case
   variance at this scale means macro means can shift by ±0.05
   at 34+ cases. Direction of the hybrid-v1 drop is robust;
   magnitude is preliminary.
2. **Ground truth is AI-drafted (Claude Opus 4.7) + single-author
   verified** by Bowen Qin (NUS). Plan-compliant with v1.3 but
   not independent human annotation. Project-bias caveats apply.
3. **Three model families tested.** Adding GPT-4o / Gemini /
   Llama variants is the most-leveraged follow-up for cross-family
   evidence.
4. **`llm-summary-v1-mock`, not real summarizer** on the diagnosis
   side. Real Haiku summarizer was excluded from the v1.3 lock for
   cost reasons and not re-run on v2.
5. **No human review of v2 diagnoses yet.** v1.3 had E2/E2b
   model-as-judge + E9 AI-assisted human review; v2 has neither
   yet. The `v1_1` calibration is re-used unchanged from v1.3.
6. **v2/stress is partial** (no huge-log + no non-pytest stress
   case at the moment). The full v2 release will fill these.
7. **20 historical exclusions** (documented in
   `configs/historical_provider_error_exclusions.json`) are
   counted as zero-score abstentions in the eval denominator
   via injection; the underlying diagnosis manifest rows were
   removed by the 2026-06-09 / 2026-06-10 cleanups because their
   provider_error prefixes (Claude CLI RuntimeError, JSONDecodeError,
   post_api_error) are not in the canonical allowlist.

See `reports/e10_v2_generalization_partial.md` §5 for the full
list and `docs/limitations/cilogbench_v1_3_limitations.md` for
v1.3 carry-over caveats.

## Roadmap

- **v2-stable** (target: +6 weeks) — Batches 7–8 to reach 34/34;
  v2/stress 3/3; sample human-review of v2 diagnoses
- **v3** — Train/holdout split decoupling, GPT-4o + Gemini family
  additions, `matrix_or_monorepo_failure` as a first-class
  canonical category

## License

- **Code**: Apache-2.0 (`tools/`, `examples/`, `schemas/`,
  `configs/`, `prompts/`, tests, scripts) — see [LICENSE](LICENSE)
- **Data + reports**: CC-BY-4.0 (`cases/`, `results/`, `reports/`,
  `protocols/`, `docs/`) — see [LICENSE-DATA](LICENSE-DATA)

## Citation

See [CITATION.cff](CITATION.cff). BibTeX:

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
