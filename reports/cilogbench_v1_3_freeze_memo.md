# cilogbench-v1.3 freeze memo

## 1. Executive summary

`cilogbench-v1.3` is now frozen at
`protocols/cilogbench-v1.3.lock.json`. It promotes the deterministic
`hybrid-grep-4k-rtk-err-cat-v1` context-provider baseline produced by
E5 from an exploratory result into a locked v1.3 baseline alongside
`raw`, `tail-200`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, and
`llm-summary-v1-mock`. No other component changed from v1.2.

`validate_protocol_lock.py` reports OK on the new lock (17 hashes
match: 10 schemas, 3 prompts, 4 evaluators) across 16 cases / 3 splits.

## 2. What changed from v1.2

| Component | v1.2 | v1.3 |
|---|---|---|
| Cases / splits / ground truth | 16 cases, 3 splits | unchanged |
| Prompts | `debugger_v1`, `llm_summary_v1_*` | unchanged |
| Diagnosis evaluator | `tools/evaluate_diagnosis.py` (sv1 + sv1.1) | unchanged |
| Category compatibility table | `configs/evaluation/category_compatibility_v1_1.json` | unchanged |
| Primary / secondary scores | `sv1.1` / `sv1` | unchanged |
| Locked baselines | 7 | **8** (adds `hybrid-grep-4k-rtk-err-cat-v1`) |

The v1.2 lock file is preserved unchanged on disk. The v1.3 lock adds:
the hybrid baseline entry, the new `hybrid_route` schema, the hybrid
config file hash, and the hybrid router script hash.

## 3. Why hybrid was promoted

E5 evidence (`reports/e5_hybrid_grep_fallback_cilogbench_v1_2.md`):

| Method | macro sv1.1 | macro total tokens | confident_error v1.1 |
|---|---:|---:|---:|
| **hybrid-grep-4k-rtk-err-cat-v1** | **0.715** | **4.9k** | **0.0%** |
| grep | 0.675 | 15.7k | 0.0% |

All four freeze criteria from the freeze plan passed:

| Criterion | Hybrid | Grep | Pass |
|---|---:|---:|:---:|
| macro sv1.1 ≥ grep | 0.715 | 0.675 | ✅ |
| macro total tokens ≤ grep | 4.9k | 15.7k | ✅ |
| macro confErr v1.1 ≤ grep | 0.0% | 0.0% | ✅ |
| provider error rate ≤ 10% | 0.0% | — | ✅ |

E4 offline policy prediction was 0.723 macro sv1.1; E5 first-class
result was 0.715 (Δ = −0.008). The hybrid is therefore stable across
the offline-vs-real-run gap.

## 4. E5 evidence summary

- **Routing decisions** (16 cases): grep selected 10/16, rtk-err-cat
  selected 6/16 (4 dev cases over budget, 2 stress cases over budget),
  zero hybrid provider errors.
- **Per-split sv1.1 vs grep**: dev +0.096, holdout +0.040, stress
  −0.017. The stress slip is one case (`prettier-react-stress-001`);
  hybrid still beats grep at the macro level.
- **Signal recall** (hybrid): dev 76.7%, holdout 89.8%, stress 80.6%.
  All comparable to or better than `grep` on the same splits.
- **Total-pipeline tokens**: hybrid uses ~⅓ of grep's tokens because it
  routes the largest cases to `rtk-err-cat` instead of letting grep
  emit a 40k+-token context.

## 5. Baselines locked in v1.3

```text
raw
tail-200
grep
rtk-read
rtk-log
rtk-err-cat
llm-summary-v1-mock
hybrid-grep-4k-rtk-err-cat-v1   ← NEW
```

**Not locked:** `llm-summary-v1-haiku`. E3 showed real Haiku summary
was useful only under <2k final-context budgets and was not competitive
with grep / hybrid on the calibrated sv1.1 metric. Real summary
remains an experiment artifact, not a v1.3 baseline.

## 6. Anti-leakage verification

The hybrid router uses only context manifests and token-budget
metadata. It does **not** read `ground_truth.json`, signal eval
outputs, diagnosis eval outputs, or review labels.

Source-level guard run on `tools/run_hybrid_baseline.py`:

```text
ground_truth      : 1 match (in docstring on L10, no code reference)
eval_diagnosis    : 0
eval_hybrid       : 0
human_review      : 0
required_signals  : 0
evidence_spans    : 0
failure_category  : 0
```

The single `ground_truth` hit is in the file's top-of-file docstring
that explicitly states the router does not open it. No code path loads
or compares against any forbidden identifier.

The 4k threshold and the choice of `rtk-err-cat` as fallback come from
E4's offline budget-frontier sweep, which used scoring outputs at
*policy selection* time. The v1.3 router itself only consults the
threshold and the raw manifest fields at *per-case decision* time —
the calibration is baked into the policy, not into the router.

## 7. Protocol lock summary

- Path: `protocols/cilogbench-v1.3.lock.json`
- `protocol_id`: `cilogbench-v1.3`
- `inherits_from`: `cilogbench-v1.2`
- Schemas: 10 (`+hybrid_route`)
- Prompts: 3 (unchanged)
- Evaluators: 4 (`+hybrid_router`)
- Baselines: 8 (`+hybrid-grep-4k-rtk-err-cat-v1`)
- Splits: dev (5) + holdout (5) + stress (6) = 16 cases
- Primary score: `diagnosis_score_v1_1` (calibration evidence:
  `reports/e2b_score_calibration_v1_1.md`)
- Secondary score: `diagnosis_score_v1`

The hybrid baseline entry includes:

```json
{
  "enabled": true,
  "type": "hybrid_context_provider",
  "config_path":      "configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json",
  "config_sha256":    "c2ffaec3…",
  "route_schema_path":   "schemas/hybrid_route.schema.json",
  "route_schema_sha256": "6bea0d6b…",
  "router_path":   "tools/run_hybrid_baseline.py",
  "router_sha256": "15091cf0…",
  "primary_method":  "grep",
  "fallback_method": "rtk-err-cat",
  "budget_tokens":   4000,
  "anti_leakage": {
    "uses_ground_truth":   false,
    "uses_signal_eval":    false,
    "uses_diagnosis_eval": false,
    "uses_review_labels":  false
  }
}
```

## 8. Validation results

```text
$ python3 tools/validate_protocol_lock.py \
      --protocol protocols/cilogbench-v1.3.lock.json
Protocol lock OK: cilogbench-v1.3
  17 hashes match (10 schemas, 3 prompts, 4 evaluators)
  16 cases across 3 split(s)
```

Per-split presence checks:

| Artifact | dev | holdout | stress |
|---|---|---|---|
| Hybrid manifest | ✅ 5 rows | ✅ 5 rows | ✅ 6 rows |
| Hybrid routes | ✅ 5 rows | ✅ 5 rows | ✅ 6 rows |
| Hybrid signal eval | ✅ | ✅ | ✅ |
| Hybrid diagnoses | ✅ 5 rows | ✅ 5 rows | ✅ 6 rows |
| Hybrid in `eval_diagnosis_real-debugger-v1.json` | ✅ | ✅ | ✅ |
| `raw` signal recall = 100% | ✅ | ✅ | ✅ |
| Hybrid provider errors | 0 | 0 | 0 |

All v1.3-A through v1.3-D acceptance criteria met.

## 9. Known limitations

- **One debugger model.** All v1.3 sv1.1 numbers come from
  `real-debugger-v1` (Claude Haiku 4.5). The hybrid advantage may be
  model-specific; E6 (planned) will replicate on a second debugger.
- **One threshold (4k tokens).** The hybrid is hardcoded to a single
  budget chosen from E4 analysis. Other thresholds were not implemented.
- **One fallback method (`rtk-err-cat`).** Other fallbacks
  (`tail`, `llm-summary-v1-haiku`, etc.) were tested in E4's offline
  policy sweep and rejected; they are not part of v1.3.
- **16 cases.** Directional, not statistical. Per-split splits stay at
  5 / 5 / 6.
- **Calibration via expert-model review** (E2/E2b used
  `claude-opus-4-7-expert` as reviewer, not unaffiliated humans). The
  sv1.1 → human-usefulness correlation is therefore model-on-model
  until a real human review batch lands.
- **Token estimate** (`output_byte_size // 4`) matches
  `tools/run_diagnosis.py`'s `context_tokens` accounting on every
  locked manifest in the corpus, but Anthropic's tokenizer may diverge
  on Unicode-heavy logs near the 4k boundary.

## 10. Recommended next experiment

**E6 — Second-debugger replication on cilogbench-v1.3.** The plan-
mandated next step after a successful v1.3 freeze is to confirm the
hybrid advantage is not a Haiku-specific artifact. Suggested setup:

- Add `real-debugger-v2` (Sonnet 4.6 or Opus 4.7) as a second locked
  diagnoser config under `configs/diagnosers/`.
- Hold every v1.3 component fixed (cases, splits, prompts, evaluator,
  category compatibility table, baselines, scoring).
- Run the full 8-method × 3-split protocol on `real-debugger-v2`.
- Compare per-method rankings against the `real-debugger-v1` ranking.
  If `hybrid-grep-4k-rtk-err-cat-v1` keeps the top spot (or stays
  within 1 rank of grep) under the second debugger, the hybrid
  advantage is model-stable.

Until E6, all v1.3 claims are scoped to `real-debugger-v1`.
