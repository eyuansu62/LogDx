# Model card — `real-debugger-v3`

## Identity

- **Provider:** OpenAI
- **Model family:** gpt-5-mini (reasoning class)
- **Alias used:** `gpt-5-mini`
- **Resolved snapshot ID:** persisted per-row in
  `metadata.model_info.resolved_model` (read from the API response's
  `model` field at request time; the alias resolves to a dated
  snapshot at OpenAI's side, and the snapshot may rotate without the
  alias name changing)
- **Invoked via:** `POST https://api.openai.com/v1/chat/completions`
  (stdlib `urllib`, no `openai` Python package dependency)
- **Shim:** `examples/diagnosis_shim_openai.py`
- **Config:** `configs/diagnosers/real-debugger-v3.json`
- **Prompt:** `prompts/debugger_v1.md` (same prompt as v1 and v2;
  SHA recorded in every diagnosis row)
- **Original run date:** 2026-05-11
- **Re-run date (Codex 2026-05-12 F1 fix):** 2026-05-13
  — the 2026-05-12 cache-key fix invalidated all v3 cache
  entries by design (see §3i 2026-05-12 disclosure block); the
  v3 sweep was repeated end-to-end so `resolved_model` and the
  full `usage` block are populated from live API responses
  rather than env-time backfill. 285 of 285 successful rows
  carry `metadata.model_info.resolved_model = gpt-5-mini-2025-08-07`
  (zero alias rotation between original run and re-run).
- **Resolved snapshot ID at run time:** `gpt-5-mini-2025-08-07`
- **Provider-error taxonomy (the 65 non-successful rows):**
  | error class | count | API call made? | resolved_model |
  |---|---|---|---|
  | `unsupported_context_too_large` (F1 oversized-context skip) | 39 | NO | absent (legitimate null) |
  | `post_api_error: JSONDecodeError` (model returned malformed JSON) | 24 | YES | preserved via Codex 2026-05-16 F1 fix; backfilled to `gpt-5-mini-2025-08-07` for pre-fix rows |
  | `post_api_error: RemoteDisconnected` (network interrupt after request) | 2 | YES (attempted) | same backfill |

  Earlier versions of this card claimed all 65 were the
  oversized-context F1 path with no API call — this was a Codex
  2026-05-16 [high] finding. The actual breakdown is shown above
  and locked by
  `tools/tests/test_diagnosis_cache_key.py:test_v3_committed_artifacts_have_model_info_on_post_api_failures`.

gpt-5-mini was chosen as the third debugger to test §3i's cross-family
generalization question: do hybrid-v2/v3 rankings on v2 survive a
debugger from a different model family? It was selected over the
larger gpt-5 / gpt-4o family for cost: the full 6-split × 10-baseline
× 35-case pass cost ~$3-5 and ran in ~75 minutes. The 2026-05-13
re-run cost roughly the same (350 cache misses, ~80 min).

## Intended use for §3i

Cross-family validation run under `cilogbench-v2-checkpoint-19`.
Purpose: test whether the v2-vs-v1.3 generalization claims that
§3e–§3h built up on two Anthropic debuggers (Haiku 4.5, Sonnet 4.6)
survive a debugger from a non-Anthropic family. NOT a model
comparison in any other sense — only one new debugger in this run,
prompt + evaluator + scoring held fixed.

## Decoding / output settings

- `temperature` and `top_p`: **not sent** (gpt-5-mini is a
  reasoning-class model; the API ignores these and warns if sent).
- `max_completion_tokens = 4096` (replaces `max_tokens` for
  reasoning models; reasoning tokens do not count against this cap).
- JSON-only output requested via the system prompt + user message
  ("Return STRICT JSON... No prose, no code fences, JSON only").
  The shim's `parse_diagnosis_json` strips ```` ```json ```` fences
  if any leak through.
- `tool_use: false`, `web_access: false`, `retrieval: disabled` — the
  shim only sends the debugger prompt and the per-case payload; no
  custom tools are wired.

## Determinism

Marked `deterministic: false` in the config. Reasoning-class APIs are
typically less deterministic than non-reasoning models at the same
sampling settings, and gpt-5-mini does not document
temperature-controlled determinism. The benchmark caches the first
run's diagnosis row keyed on context_sha + prompt_sha + command_str;
rerunning with the same cache is byte-stable (enforced by the
M6-era cache-stores-full-row fix). Rerunning with `--no-cache` may
produce different outputs and should be reported as a new run with
a new timestamp.

## Privacy posture

- Privacy audit (`tools/audit_context_privacy.py`) must pass with
  `complete_scan=True` and zero hits on the raw log before the case
  is admitted to the corpus. Contexts passed to gpt-5-mini are
  therefore the same as those passed to v1/v2.
- The shim reads `OPENAI_API_KEY` from environment only — never
  logged, never written to any file, never embedded in any row.
- `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` opt-in required (same posture
  as v1 and v2's Claude shim).
- The shim's `verify_no_leakage` rejects payloads that contain
  `ground_truth`, `failure_category`, `required_signals`,
  `evidence_spans`, or `expected_diagnosis` — belt-and-suspenders
  with the runner's stripping logic.

## Known issues at run time

- **Reasoning latency.** gpt-5-mini reasoning tokens add wall-clock
  per call. Full v2 run was ~75 min for 350 calls (~13s/call median).
- **Output token cap occasionally hit on huge logs.** Some
  v2/stress cases (notably argocd) had `usage.completion_tokens`
  near the 4096 cap. No abstain attributable to truncated output
  was observed in §3i, but a future run could see one — a v4
  raise to 8192 is the obvious mitigation.
- **None of the 350 diagnoses exhibited the wrapper-flake issue
  documented for `real-debugger-v1` (Haiku) in §3e caveat 2.**
  The flake appears to be Claude-CLI-specific, not a property of
  wrapped contexts in general.
- **Run-to-run variance.** Reasoning-class APIs are non-
  deterministic at the sampling settings the shim uses
  (temperature not sent). The 2026-05-13 re-run produced
  per-method score deltas of up to ±0.13 on v1.3 (max on
  rtk-read/raw — large logs where the model has many places to
  pick differently each run) and up to ±0.057 on v2. v1.3
  rankings moved (hybrid-v1 #5 → #2 on gpt-5-mini); v2 rankings
  did NOT move. This is itself a §3i finding: v2 produces more
  run-stable rankings than v1.3. Single-run v3 numbers should
  be treated as worst-case ranking instability; future v3
  protocols should consider N=3-5 re-runs + median aggregation.

## Reproducing the §3i run

```bash
# 1. Set env (don't commit the key to git)
export OPENAI_API_KEY='sk-...'
export CILOGBENCH_OPENAI_MODEL='gpt-5-mini'
export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_openai.py"
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

# 2. Run all 6 splits × 10 baselines
for split in dev holdout stress v2/dev v2/holdout v2/stress; do
  for m in raw tail grep rtk-read rtk-log rtk-err-cat llm-summary-v1-mock \
           hybrid-grep-4k-rtk-err-cat-v1 hybrid-grep-120k-tail-v2 \
           hybrid-grep-120k-rtk-tail-v3; do
    python3 tools/run_diagnosis.py --split "$split" \
      --diagnoser command --diagnoser-name real-debugger-v3 \
      --command "$DIAGNOSIS_COMMAND" --context-method "$m"
  done
done

# 3. Evaluate (same evaluator as v1, v2; same ground truth files)
for split in dev holdout stress v2/dev v2/holdout v2/stress; do
  python3 tools/evaluate_diagnosis.py --split "$split" \
    --diagnoser real-debugger-v3
done
```

Cost estimate: ~$3-5 if all rows are cache misses. Cache hits cost $0.

## Auditability

Each diagnosis row contains `metadata.model_info.resolved_model` —
the exact snapshot ID OpenAI returned. After the Codex 2026-05-12 F1
re-run, **all 285 successful v3 rows carry
`resolved_model: gpt-5-mini-2025-08-07`** populated from live API
responses. After the Codex 2026-05-16 F1 fix + backfill, the 26
post-API failure rows (24 `JSONDecodeError` + 2 `RemoteDisconnected`)
also carry `model_info`; the remaining 39 rows are pre-API
oversized-context skips that legitimately never reached the API
(model_info absent). If a future re-run produces a different
`resolved_model` value despite the same `requested_model`, that's
the audit signal that OpenAI rotated the alias underneath us.

The row also carries `metadata.model_info.base_url` (sanitized —
userinfo and query string stripped) and `metadata.model_info.base_url_sha256`
(sha256 of the FULL env-provided URL, including any proxy
credentials). The sanitized URL is what readers see; the hash lets
an auditor confirm that a re-run hit the same endpoint as the
canonical run without storing the secret. See Codex 2026-05-12 F3
in §3i for context.

## Cache-key safety (Codex 2026-05-12 F2)

This config opts into `cache_key_env`, listing
`CILOGBENCH_OPENAI_MODEL` and `CILOGBENCH_OPENAI_BASE_URL`.
`tools/run_diagnosis.py` folds these env values into the diagnosis
cache key, so a re-run with a different alias or proxy will MISS
the cache instead of silently replaying a row from a different
backend. The runner additionally validates each cache hit's
`metadata.model_info.requested_model` against `config.model.model_name`
as belt-and-suspenders. See
`tools/tests/test_diagnosis_cache_key.py` for the regression
suite.

## Limitations carried over to §3i

1. **Sample size 1 family + 1 model.** "Cross-family stable" with
   N=1 is weak. The natural follow-ups are GPT-4o, Gemini, Llama
   variants. See §3i caveat 2.
2. **sv1.1 calibration was done against an Anthropic expert model**
   (E2/E2b on Opus 4.7-class). The v3 numbers are computed with the
   same evaluator on the same ground truths, but absolute scores
   may have a small systematic shift relative to a hypothetical
   "calibrated against gpt-5-mini" version. The rank-correlation
   findings in §3i hold independently of this potential shift.
3. **gpt-5-mini is not in any locked-protocol baseline set.** The
   real-debugger-v1 and v2 baselines are SHA-pinned in
   `cilogbench-v1.3.lock.json` / `cilogbench-v2-checkpoint-*.lock.json`
   via the prompt + evaluator hashes. v3's diagnosis_shim_openai.py
   SHA is committed but not yet pinned in any protocol lock. A v4
   protocol could add it.
