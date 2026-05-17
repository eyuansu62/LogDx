# Contributing to LogDx-CI

Thanks for taking a look. The benchmark is designed to be extended:
new context-provider methods, new debugger families, new cases, and
new evaluation metrics all have well-defined entry points.

## Dev setup

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# Optional but recommended: jsonschema for full schema validation
pip install jsonschema

# Rebuild the diagnosis cache from canonical manifests (one-time;
# cache is gitignored, so fresh clones need this for cache-hit tests
# to pass).
python3 tools/migrate_cache_keys_codex_2026_06_08.py
```

Verify your tree is clean:

```bash
python3 tools/tests/test_diagnosis_cache_key.py    # 155 tests
python3 tools/tests/test_hybrid_router.py          # 10 tests

python3 tools/validate_committed_diagnosis_provider_errors.py
python3 tools/validate_eval_manifest_consistency.py
python3 tools/validate_diagnosis_vs_context_consistency.py

python3 tools/validate_protocol_lock.py \
    --protocol protocols/logdx-ci-v2-partial-2026-06-22.lock.json
```

CI runs all of the above on every push; see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Repo layout (high level)

> **Note on internal naming**: the on-disk split paths
> `cases/dev/`, `cases/holdout/`, `cases/stress/` (16 cases) and
> `cases/v2/dev/`, `cases/v2/holdout/`, `cases/v2/stress/` (19
> cases) reflect two **methodology-development waves** during
> prototyping. Both are merged into the v1.0 corpus (35 cases
> total). Same goes for the `v1.3` and `v2` labels in protocol
> locks and hybrid baseline names. These are preserved for
> reproducibility audit; the public release version is **v1.0**.

```
cases/                  ← case corpus (committed; mirrored on HF)
  dev/, holdout/, stress/    ← initial wave (16 cases)
  v2/                        ← second wave (19 cases)

configs/                ← diagnoser / summarizer / hybrid-router configs
  diagnosers/                ← real-debugger-v{1,2,3} + templates
  baselines/                 ← hybrid routers, llm-summary
  historical_provider_error_exclusions.json

prompts/                ← debugger + llm-summary prompts

schemas/                ← case / ground_truth / diagnosis JSON schemas

tools/                  ← all runnable code
  run_diagnosis.py             ← main runner: context-method × diagnoser → diagnosis row
  run_baseline.py              ← raw/tail/grep context providers
  run_rtk_baseline.py          ← rtk-{read,log,err-cat}
  run_llm_summary_baseline.py  ← llm-summary-v1
  run_hybrid_baseline.py       ← hybrid routers (primary + fallback)
  evaluate_diagnosis.py        ← scoring → eval_diagnosis_*.json
  evaluate_signal_recall.py    ← signal-preservation metric
  audit_context_privacy.py     ← secret-pattern scan + truncation guard
  run_m6_experiment.py         ← M6 wrapper (single diagnoser)
  run_m7_real_summary_experiment.py  ← M7 wrapper (summary + diagnoser)
  freeze_protocol.py           ← write protocols/<id>.lock.json
  validate_protocol_lock.py    ← drift detection
  validate_committed_diagnosis_provider_errors.py
  validate_eval_manifest_consistency.py
  validate_diagnosis_vs_context_consistency.py
  migrate_cache_keys_codex_2026_06_08.py  ← cache rebuild from manifests
  deploy_site.sh                          ← sync docs/ to GH Pages
  tests/                                  ← unit + e2e tests

examples/               ← reference shims (Claude CLI, OpenAI, stub)

results/                ← canonical eval state (committed)
  <split>/<method>.jsonl                   ← context-provider manifests
  <split>/diagnoses/<diagnoser>/<method>.jsonl  ← diagnosis manifests
  <split>/eval_diagnosis_<diagnoser>.json  ← scored aggregates
  <split>/.cache/diagnosis/                ← gitignored cache

protocols/              ← SHA-pinned release locks
  logdx-ci-v2-partial-2026-06-22.lock.json  ← current canonical lock

docs/                   ← GH Pages site + technical sub-docs
  index.md, leaderboard.md, cite.md
  evaluation/, methods/, protocol/, corpus/, …

reports/                ← findings reports
  e10_v2_generalization_partial.md         ← v1.0 technical report
  e1..e9_*.md                              ← v1.3-era reports
```

## Adding a new context-provider method

1. **Pick a `method` slug** that matches `^[a-z][a-z0-9_-]*$` and
   doesn't collide with existing manifests
   (`results/<split>/<method>.jsonl`).
2. **Implement the provider** so it emits one JSONL row per case under
   `results/<split>/<method>.jsonl` with the
   [`method_output.schema.json`](schemas/method_output.schema.json)
   shape (case_id, raw_log_path, context_path, output_byte_size,
   reduction_ratio, line_mapping_available, metadata).
3. **Write a config** in `configs/baselines/<method>.json` if your
   method has tunable knobs (token budget, fallback strategy, etc.).
4. **Run the privacy audit** on the generated context files:
   ```bash
   python3 tools/audit_context_privacy.py \
       --split dev --context-method <method>
   ```
   Must end with `Hits: 0`. Any hits fail the gate; fix the redaction
   in your provider, don't add an exception.
5. **Run signal recall** (the cheap, model-free metric):
   ```bash
   python3 tools/evaluate_signal_recall.py \
       --split dev --method <method>
   ```
6. **Run the diagnoser** against your context output (optional but
   recommended for full leaderboard placement):
   ```bash
   export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
   export DIAGNOSIS_COMMAND="python3 examples/diagnosis_shim_<...>.py"
   python3 tools/run_diagnosis.py --split v2/dev \
       --diagnoser command --diagnoser-name real-debugger-v3 \
       --command "$DIAGNOSIS_COMMAND" \
       --context-method <method> \
       --diagnoser-config configs/diagnosers/real-debugger-v3.json
   ```
7. **Evaluate diagnosis** and commit the artifacts:
   ```bash
   python3 tools/evaluate_diagnosis.py \
       --split v2/dev --diagnoser real-debugger-v3
   ```
8. **Verify the three release gates** still pass before opening a PR.

## Adding a new case

1. **Find a real GHA failure run** that fits a documented gap in
   `docs/corpus/cilogbench_v2_case_matrix.md` (failure category /
   signal position / log size / ecosystem).
2. **Privacy audit FIRST**:
   ```bash
   python3 tools/audit_context_privacy.py --raw-log <path>
   ```
   Must end with `complete_scan=True` and zero hits. If long lines
   need splitting or in-place redactions, document under
   `repo_visibility: redacted` in `tags.json` + case notes.
3. **Import skeleton**:
   ```bash
   python3 tools/import_case_skeleton.py \
       --split v2/<dev|holdout|stress> --case-id <id> \
       --raw-log <path> --repo <org/repo> \
       --framework <fw> --workflow-name <wf> --job-name <job>
   ```
4. **Fill in** `ground_truth.json` and `tags.json` (replace `.todo`
   stubs). See [`docs/annotation_guide.md`](docs/annotation_guide.md)
   for the GT contract.
5. **Validate**:
   ```bash
   python3 tools/validate_cases.py cases/v2/<split>
   python3 tools/validate_case_tags.py --split v2/<split>
   ```
6. **Raw sanity**: run `--method raw` and confirm signal recall is
   1.0/1.0/1.0. If not, your ground truth's `required_signals`
   probably don't appear verbatim in the raw log — fix the GT,
   not the recall metric.
7. **Re-freeze the protocol lock** if the case is intended for a
   release:
   ```bash
   python3 tools/freeze_protocol.py \
       --protocol-id logdx-ci-<release-tag> \
       --splits dev,holdout,stress,v2/dev,v2/holdout,v2/stress
   ```

## Adding a new debugger family

1. **Implement a shim** at `examples/diagnosis_shim_<family>.py`
   that reads `{prompt, context, safe_case_metadata}` from stdin
   and writes a diagnosis envelope to stdout. Use
   `diagnosis_shim_openai.py` as the reference; it has the most
   complete privacy redaction + provenance metadata machinery.
2. **Write a diagnoser config** at
   `configs/diagnosers/real-debugger-<family>.json` declaring
   `model.{provider_name,model_name,env_var_name,base_url}`,
   `privacy.requires_explicit_external_llm_opt_in`, and
   `provider_policy.non_fatal_provider_error_prefixes`.
3. **Add a model card** at
   `docs/model_cards/real-debugger-<family>.md` with the snapshot
   ID you ran against, sampling parameters, and any known
   failure modes.
4. **Run on every split** and re-evaluate. The eval will inject
   zero-score abstentions for any cases in
   `historical_provider_error_exclusions.json` that match
   `(split, diagnoser, method, case_id)`.

## Validator contract (release gates)

Three CI-gateable invariant checks enforce reproducibility. If your
PR breaks any of them, the PR fails CI:

| Script | Invariant |
|---|---|
| `validate_committed_diagnosis_provider_errors.py` | No non-allowlisted `provider_error` rows in committed `real-debugger-*` manifests. Allowlist lives in each config's `provider_policy.non_fatal_provider_error_prefixes`. |
| `validate_eval_manifest_consistency.py` | Every `eval_diagnosis_*.json`'s per-method case-ID set matches its manifest. Exclusion-exempt rows must carry the `[historical exclusion]` marker AND zero-score abstention semantics. |
| `validate_diagnosis_vs_context_consistency.py` | Every diagnosis manifest's case set ⊆ source context manifest. Missing cases must be in `configs/historical_provider_error_exclusions.json` with a justification. |

For the cache-identity contract, see `tools/run_diagnosis.py`'s
`cache_hit_is_acceptable` + the `metadata.diagnoser_config_sha256` /
`metadata.shim_sha256` fields stamped on every fresh row.

## Site deployment

The GH Pages site lives in a separate repo
(`logdx-bench/logdx-bench.github.io`) because the org-root URL
needs that name. To sync your local `docs/` changes:

```bash
bash tools/deploy_site.sh           # dry-run
bash tools/deploy_site.sh --push    # commit + push to org repo
```

## Issues and PRs

- File issues at
  <https://github.com/eyuansu62/LogDx/issues>.
- PRs: please ensure `python3 tools/tests/test_diagnosis_cache_key.py`
  + `tools/tests/test_hybrid_router.py` + the three release gates
  all pass locally before opening.

## License

By contributing, you agree your contributions will be licensed under
Apache-2.0 (code) or CC-BY-4.0 (data + reports + protocol locks),
matching the existing repo licensing.
