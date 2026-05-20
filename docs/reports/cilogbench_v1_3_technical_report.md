# CILogBench v1.3: Measuring CI Failure Context Quality for Coding Agents

> **Reviewer disclosure (read first):** sv1.1 was originally calibrated by an
> **LLM-as-judge expert reviewer** (`claude-opus-4-7-expert` in E2/E2b) and
> later spot-checked by **AI-assisted human review** (E9: 1 reviewer, project
> author of the hybrid baseline, working from a ChatGPT-generated draft and
> verifying each of 48 items over the v1.3 hybrid-vs-grep comparison). This is
> *not* independent human review and *not* inter-rater-validated. A second
> independent human reviewer remains the strongest follow-up. Section 8b and
> §14 carry the E9 details; the limitations doc has the full list of caveats.

---

## 1. Executive summary

CILogBench evaluates **CI failure context strategies** by measuring evidence
preservation, downstream diagnosis quality, total token cost, abstention, and
confident-error behavior. The benchmark asks whether an agent can still
diagnose a CI failure after a context strategy has compressed, filtered, or
summarized the raw log.

The current frozen protocol is `cilogbench-v1.3` (16 cases across dev / holdout
/ stress; 8 locked context-provider baselines; calibrated primary score
`diagnosis_score_v1_1`). Two real debugger models — Claude Haiku 4.5 and Claude
Sonnet 4.6 — were run end-to-end on the full protocol.

**Headline result.** A simple deterministic hybrid context strategy,
`hybrid-grep-4k-rtk-err-cat-v1`, **matched `grep` on diagnosis quality** while
using roughly **one third of `grep`'s total token cost** on this 16-case
benchmark, and **ranked #1 by automatic sv1.1 under both debugger models**.
AI-assisted human review preferred grep on direct head-to-head pairwise
judgments (8 wins vs 2 for hybrid out of 16, with 6 ties), while rating both
methods inside a tie band on absolute usefulness (means 3.875 vs 3.938 on a
0–4 scale). The cost gap is unchanged.

| Debugger | hybrid sv1.1 | grep sv1.1 | hybrid total tokens | grep total tokens |
|---|---:|---:|---:|---:|
| Haiku 4.5 (E5) | **0.715** | 0.675 | 4.9k | 15.7k |
| Sonnet 4.6 (E6) | **0.771** | 0.770 | 5.0k | 15.9k |

Top-3 ranks under sv1.1 were identical across debuggers (`hybrid > grep >
tail`). The hybrid baseline is therefore not a single-model artifact, but the
quality
margin over `grep` narrowed from +0.040 sv1.1 (Haiku) to +0.001 (Sonnet) — the
hybrid's main remaining advantage under a stronger debugger is **token cost**.

**The benchmark is small.** 16 cases, two debugger models, one summarizer
model, one summary prompt, and an LLM-as-judge calibration step. Treat all
results as directional, not statistical.

---

## 2. Motivation

Raw CI logs are **large and noisy**: a single failed pytest run for `pandas`
on this corpus produces 80k+ context tokens. Naïve compression (drop
duplicates, keep last 200 lines) routinely **deletes the actual error**. LLM
summaries can be concise but **costly and lossy**. Agentic CI debugging needs
context that is at once compact and diagnostic.

The benchmark asks **not** "how much can we compress?" but "**can the agent
still diagnose the failure?**" — measured downstream of the context method, on
a held-fixed real debugger, against ground-truth root causes.

---

## 3. Why token reduction alone is not enough

Three concrete examples from this corpus:

- **`rtk-log` compresses aggressively** (≥ 99% byte reduction on dev) but
  scored macro sv1.1 = 0.273 vs grep's 0.675 — the compressed output rarely
  carried the failing assertion verbatim.
- **`llm-summary-v1-haiku`** produced final contexts of ~439 tokens (the
  smallest of any method) but spent ~83k summary-processing tokens to do it,
  and lost to grep on diagnosis quality across all three splits.
- **`raw`** preserves everything but is not always best: on dev the largest
  case (`cargo-tokio-001`, ~400 KB log) hit a context-size error under Haiku;
  on holdout, raw scored only slightly above grep (sv1.1 = 0.580 vs 0.549)
  despite using a much larger context. Preserving more information did not
  produce a decisive diagnosis-quality advantage.

The benchmark therefore reports a basket of metrics rather than a single
compression ratio:

```text
diagnosis_score_v1_1            primary calibrated quality score
critical_signal_mention_recall  did the diagnosis literal-quote the key signal?
must_mention_coverage           must-have phrases that appeared in the diagnosis
confident_error_v1_1            confidently-wrong diagnoses (safety metric)
abstention_rate                 "I don't know" rate
total_pipeline_tokens           context + diagnosis + summary processing
```

---

## 4. Benchmark design

The pipeline is deliberately separated into four layers:

```text
raw CI log
  -> context method     (raw / tail-200 / grep / rtk-* / llm-summary-* / hybrid)
  -> fixed debugger     (real-debugger-v1 = Haiku 4.5; v2 = Sonnet 4.6)
  -> diagnosis JSON     (root_cause, category, evidence quotes, suggested_fix)
  -> deterministic evaluator
```

Each layer is locked separately so that experiments hold one variable fixed at
a time. **No layer reads ground-truth, signal-eval, or diagnosis-eval data**:

- Context methods see only `raw.log` + safe metadata (case_id, repo, framework, …).
- The fixed debugger sees only the context produced by the method, plus the
  same safe metadata; it cannot read `ground_truth.json`,
  `failure_category`, `required_signals`, `evidence_spans`, or
  `expected_diagnosis`.
- The deterministic evaluator reads ground-truth and the diagnosis JSON and
  computes signal recall, category match, must-mention coverage, forbidden-
  claim violations, etc.
- The expert-model review (E2/E2b) was downstream of all of that and was used
  only to calibrate the evaluator.

The hybrid baseline (section 11) follows the same anti-leakage rule — it
routes per case using only manifest token-count metadata, not scoring data.

---

## 5. Dataset and splits

```text
dev:     5 cases   (jest, pytest, cargo, mypy, lint failures)
holdout: 5 cases   (terraform changelog gate, dependabot, transformers docs,
                    next.js sync-react push permission, tsc fourslash)
stress:  6 cases   (k8s cleanup, tsc cleanup, doc-build HuggingFace, prettier
                    react, two pytest-sklearn build-warning cases)
total:  16 cases
```

Stress cases were intentionally chosen to be brittle (very large logs, mixed
failure modes, ambiguous boundaries) so we could observe where existing
methods break. Examples:

- `tail-200` improved on holdout/stress because those splits contained
  shorter logs whose error landed in the last 200 lines.
- `rtk-err-cat` lost ground on holdout/stress where the failure didn't fit
  RTK's category templates (e.g., changelog gate, dependabot security
  advisory).
- The 4k-token hybrid threshold split dev sharply (only 1/5 cases used grep)
  but kept all of holdout (5/5) on grep.

**16 cases is small.** No statistical claims are made on this corpus.

---

## 6. Context methods

Locked v1.3 baselines (`protocols/cilogbench-v1.3.lock.json`):

```text
raw                            full log; if too large for the debugger, the run records
                               provider_error / unsupported_context_too_large rather than
                               silently truncating
tail-200                       last 200 lines
grep                           regex over (error|failed|...|##[error]) +/- 3/8 lines
rtk-read                       RTK context-mode "read"
rtk-log                        RTK context-mode "log"
rtk-err-cat                    RTK context-mode "err-cat"
llm-summary-v1-mock            deterministic infrastructure/control baseline; NOT a real
                               LLM summarizer (mock of the v1 map/reduce pipeline)
hybrid-grep-4k-rtk-err-cat-v1  router (see below)
```

The hybrid router decides per case using only context-manifest metadata:

```text
if grep is available and grep's final_context_tokens_estimate <= 4000:
    select grep
elif rtk-err-cat is available:
    select rtk-err-cat            # primary_too_large_used_fallback
                                  # OR primary_provider_error_used_fallback
else:
    record provider_error          # do not silently fall back to raw
```

Token estimates use the benchmark's existing token-estimation convention.[^1]

[^1]: In the current implementation the estimator is `output_byte_size // 4`,
chosen to match `tools/run_diagnosis.py`'s `context_tokens` field on every
locked grep / rtk-err-cat manifest in this corpus (verified ratio 1.000). The
router is structured around the budget, not the byte heuristic — a future
implementation could swap in a tokenizer-based estimator without changing
the policy.

**`llm-summary-v1-haiku` was tested in E3 but is NOT locked into v1.3.** It
was excluded after the E4 budget-frontier analysis showed that its quality-
cost trade-off was not competitive with grep / hybrid except at very tight
final-context budgets. Real summary remains an experiment artifact.

> **2026-05-20 update (forward-pointer to v1.1)**: a full 35-case × 4-
> diagnoser backfill of `llm-summary-v1-haiku` (Haiku 4.5, Sonnet 4.6, gpt-
> 5-mini single-shot; Sonnet 4.6 agent-loop) showed the real Haiku summary
> scores **0.632** overall (rank 4 across all 10 methods). The v1.3
> exclusion verdict was based on the 16-case prototype subset and a single
> Haiku-only debugger — both of which understated the method. v1.1
> promotes `llm-summary-v1-haiku` to the headline leaderboard. v1.3's lock
> file (`protocols/cilogbench-v1.3.lock.json`) remains frozen as-is for
> reproducibility; a future v1.4 protocol could include the real Haiku
> summarizer if a lock-time re-evaluation is wanted.

---

## 7. Evaluation metrics

| Metric | What it measures |
|---|---|
| `signal_recall` | per-case fraction of ground-truth signals that *appeared* in the context output |
| `critical_signal_recall` | same, restricted to critical signals |
| `evidence_span_coverage` | fraction of ground-truth evidence-line spans present (when line-mapped methods like grep emit ranges) |
| `category_accuracy` (v1) | binary: did the diagnosis name the right `failure_category`? |
| `category_match_score_v1_1` | partial match (1.0/0.5/0.0) using `configs/evaluation/category_compatibility_v1_1.json` |
| `critical_signal_mention_recall` | did the **diagnosis text** quote the critical signal? |
| `must_mention_coverage` | fraction of ground-truth `must_mention` phrases that appeared |
| `forbidden_claim_violations` | count of `must_not_claim` phrases that appeared |
| `valid_evidence_quote_rate` | fraction of evidence quotes that match the context verbatim |
| `confident_error` (v1) | `confidence ≥ 0.7 AND (category=0 OR forbidden>0)` |
| `confident_error_v1_1` | stricter: `confidence ≥ 0.7 AND (forbidden>0 OR (cms=0 AND critical<0.5 AND must<0.5))` |
| `abstention_rate` | rate of `unknown` / low-confidence diagnoses |
| `diagnosis_score_v1_1` | calibrated composite (primary score) |
| `diagnosis_score_v1` | original composite, kept for historical comparison |

`diagnosis_score_v1_1` is the primary calibrated automatic score. `sv1` is
emitted alongside per case for backward comparison.

---

## 8. Expert-model calibration and sv1.1

The original score (`diagnosis_score_v1`) was calibrated against an
LLM-as-judge expert reviewer (`claude-opus-4-7-expert`) on the holdout split,
under E2 (`reports/e2_calibration_memo.md`). The reviewer scored 50 items (20
absolute + 30 pairwise) over 5 holdout cases × 4 methods, with method names
hidden from the reviewer.

E2 found that `sv1` correlated with reviewer **`overall_usefulness`** at
Spearman = 0.637 (just above the 0.6 PASS threshold) but the top-5
disagreements were dominated by a single failure mode:
**`confident_wrong_unflagged`** — diagnoses the reviewer rated 3-or-4 out of
4 were being flagged as confident errors purely because their category label
didn't exact-match the (very coarse) ground-truth category enum.

E2b (`reports/e2b_score_calibration_v1_1.md`) introduced two changes:

1. `category_accuracy` (binary) became `category_match_score_v1_1`
   (1.0 / 0.5 / 0.0) using an explicit compatibility table.
2. `confident_error` was tightened so a wrong category alone no longer
   triggers it — the diagnosis must also miss critical evidence or violate a
   forbidden claim.

Result on the same 50-item batch:

| Metric | sv1 | sv1.1 | Δ |
|---|---:|---:|---:|
| overall_usefulness Spearman | 0.637 | **0.839** | +0.20 |
| pairwise expert-model/auto agreement | 0.760 | **0.880** | +0.12 |
| method-rank Spearman | 0.800 | 0.800 | +0.00 |
| top-5 disagreement avg gap | 0.558 | **0.336** | −0.22 |
| false confident-error count | 5/5 | **0/0** | — |

`diagnosis_score_v1_1` was adopted as the primary score and frozen as
`cilogbench-v1.2`.

**Disclosure.** The reviewer in E2/E2b was an LLM, not an unaffiliated human.
The next subsection (§8b) describes the AI-assisted human review pass that
later spot-checked the v1.3 hybrid-vs-grep comparison.

---

## 8b. AI-assisted human review of the v1.3 hybrid-vs-grep claim

E9 (`reports/e9_human_verified_v1_3_review.md`) ran a 48-item human-review
pass over `cilogbench-v1.3`'s headline comparison: 16 cases × 2 methods
(hybrid vs grep) × (1 absolute + 1 pairwise) under `real-debugger-v2` (Sonnet
4.6, the same debugger as E6). The reviewer is the project author of the
hybrid baseline; they worked from a ChatGPT-generated draft and verified each
of the 48 items, accepting all 48 rows after item-by-item inspection. This is
**AI-assisted human review by a single project-author reviewer**, not
independent human review and not inter-rater-validated.

Findings:

| Metric | hybrid | grep | Δ |
|---|---:|---:|---:|
| mean overall_usefulness (0–4) | 3.875 | 3.938 | -0.063 |
| pairwise wins (out of 16) | **2** | **8** | — |
| pairwise ties | — | — | 6 |

On absolute usefulness the methods are **inside a tie band** (E9 plan
threshold: 0.25). On forced-choice pairwise the reviewer **preferred grep
8-to-2** (10 decisive non-tie pairs). Per-pair detail: most of the human-vs-
sv1.1 mismatches happen on cases where sv1.1 mildly favored hybrid (close
auto-margin) but the reviewer preferred grep's more verbatim quoting of the
failing test name, file:line, or bot account.

`confident_error_v1_1` fired 0 times on the 32 reviewed absolute items,
reproducing the E2b false-positive fix for the third time (originally Opus,
then ChatGPT cross-model, now AI-assisted human).

The Spearman between human `overall_usefulness` and `diagnosis_score_v1_1`
came out **−0.46** on this batch, but with 29 of 32 absolute scores at 4 the
correlation is dominated by tie-breaking noise — a score-compression artifact,
not evidence the evaluator is anti-correlated with usefulness. (E2's Opus
review with much wider variance gave +0.84 on the same metric.)

**Verdict per the E9 plan: `WEAKEN_HEADLINE`.** Hybrid is *cost-efficient and
quality-comparable* to grep, but the headline phrasing in §1 has been changed
from "matched or beat grep" to "matched grep on quality at ~⅓ the token cost,"
with the pairwise-grep-lean noted explicitly.

---

## 9. Real summary experiment (E3)

E3 (`reports/e3_real_llm_summary_cilogbench_v1_2_haiku.md`) added one real
LLM summarizer (`llm-summary-v1-haiku`, Claude Haiku 4.5 with the v1
map/reduce prompts) and reran the full protocol against the same fixed
debugger as v1.

| Result | Number |
|---|---:|
| Beat `llm-summary-v1-mock` (control baseline) on macro sv1.1 | **+0.04 to +0.05** across splits (v1.3 16-case subset; in v1.1's 35-case backfill the same comparison widens to **+0.24 to +0.36** across diagnosers — see forward-pointer above) |
| Cross-split max-gap (stability) | **0.121** (2nd-most stable method) |
| Confident-error v1.1 across all 3 splits | **0.0%** |
| Lost to `grep` on macro sv1.1 | **−0.13** |
| Total-pipeline-token ratio vs `grep` (median) | **~6×** |

(`llm-summary-v1-mock` is an infrastructure/control baseline — a deterministic stand-in for the v1 map/reduce summarizer pipeline, not a real LLM. The +0.04 to +0.05 lift is therefore over a control, not over a representative LLM-summary baseline.)

The interpretation: real LLM summary may be useful at extremely tight final-
context budgets, but **summary-only is not a good default** on this
benchmark. It is more stable than aggressive deterministic compressors but
its summary-processing cost is not justified by the diagnosis-quality result.

E3 closed with the question that motivated E4: *"Did real summary fail
because the summarizer was too weak, because summaries are structurally
lossy, or because they are only useful under strict final-context budgets?"*

---

## 10. Budget frontier and hybrid routing (E4)

E4 (`reports/e4_summary_failure_attribution_cilogbench_v1_2.md`) was an
analysis-only experiment (no model runs). For each final-context-token
budget in {1k, 2k, 4k, 8k, 16k, 32k} it asked: which method is the best
deployable choice?

| Budget | Best deployable method | sv1.1 |
|---:|---|---:|
| 1k | `llm-summary-v1-haiku` | 0.501 |
| 2k | `llm-summary-v1-mock` *(control)* | 0.500 |
| **4k** | **`grep`** | **0.679** |
| 8k | `grep` | 0.706 |
| 16k | `grep` | 0.706 |
| 32k | `rtk-read` | 0.714 |

Real LLM summary was only the best deployable choice at the **1k** budget.
At 4k+ budgets, `grep` dominated, and the best routing policy was:

```text
if grep fits the budget:
    use grep
else:
    use rtk-err-cat   # cheap deterministic fallback for over-budget cases
```

E4's offline simulation of this policy at 4k:

```text
grep-default              sv1.1 = 0.680, total tokens = 14.9k
grep-if-fits-else-summary sv1.1 = 0.552, total tokens = 78.1k    # summary fallback expensive
grep-if-fits-else-rtk     sv1.1 = 0.723, total tokens = 4.7k     # ⬅ winner
```

This is the policy E5 promoted to a first-class baseline.

---

## 11. Hybrid baseline result (E5)

E5 (`reports/e5_hybrid_grep_fallback_cilogbench_v1_2.md`) implemented
`hybrid-grep-4k-rtk-err-cat-v1` as a first-class deterministic context
provider — same scoring treatment as every other locked baseline.

Per-split results under Haiku 4.5:

| Split | hybrid sv1.1 | grep sv1.1 | Δ |
|---|---:|---:|---:|
| dev | **0.699** | 0.604 | +0.096 |
| holdout | **0.714** | 0.674 | +0.040 |
| stress | 0.732 | **0.749** | −0.017 |
| **macro** | **0.715** | 0.675 | **+0.040** |

Cost (macro across splits):

| Method | macro total pipeline tokens |
|---|---:|
| **hybrid** | **4.9k** |
| grep | 15.7k |
| llm-summary-v1-haiku | 83.7k |

E4 offline predicted macro sv1.1 = 0.723; E5 actual was 0.715 — a delta of
−0.008. **The budget-frontier analysis was a strong predictor of the real
result.**

All four freeze criteria from the v1.3 plan passed (`reports/cilogbench_v1_3_freeze_memo.md`):
sv1.1 ≥ grep, total tokens ≤ grep, confErr v1.1 ≤ grep, provider error rate
≤ 10%. The hybrid was promoted into `protocols/cilogbench-v1.3.lock.json`.

---

## 12. Second-debugger replication (E6)

E6 (`reports/e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md`) reran
the full v1.3 protocol with **Sonnet 4.6** as `real-debugger-v2`, holding
every other component fixed.

Method ranks (macro sv1.1 across 3 splits):

| Rank | v1 (Haiku) | sv1.1 | v2 (Sonnet) | sv1.1 |
|---|---|---:|---|---:|
| 1 | **hybrid** | 0.715 | **hybrid** | **0.771** |
| 2 | grep | 0.675 | grep | 0.770 |
| 3 | tail | 0.661 | tail | 0.689 |
| 4 | rtk-err-cat | 0.494 | rtk-err-cat | 0.534 |
| 5 | llm-summary-v1-mock *(control)* | 0.494 | rtk-read | 0.522 |
| 6 | rtk-read | 0.458 | llm-summary-v1-mock *(control)* | 0.518 |
| 7 | raw | 0.454 | raw | 0.511 |
| 8 | rtk-log | 0.280 | rtk-log | 0.309 |

**Top-3 ranks identical.** The only swap is `rtk-read` ↔ `llm-summary-v1-
mock` at adjacent ranks (Δ = 1).

Other observations:

- All methods improved under Sonnet (uniform +0.02 to +0.10).
- Hybrid's sv1.1 lead over grep narrowed to **+0.001**, but it kept its **3×
  cost advantage** (5.0k vs 15.9k macro total tokens).
- Confident-error v1.1 was 0.0% across every (method, split) for Sonnet.
- `rtk-log` remained worst across both debuggers.

E6 verdict: `CONFIRMED_MODEL_STABLE`. The hybrid advantage is **not a Haiku
artifact**. Under a stronger debugger, the **quality margin shrinks but the
cost advantage persists**.

---

## 13. What we learned

1. **Context strategy materially changes diagnosis quality** — `rtk-log` and
   `grep` differ by ~0.4 sv1.1 with the same debugger and prompt.
2. **Token reduction alone is insufficient.** The two most aggressive
   compressors on this corpus (`rtk-log` and the real LLM summary) were the
   two least diagnostic.
3. **Aggressive compression can destroy diagnosability.** `rtk-log` removed
   the failing assertion text on most cases.
4. **Simple deterministic filters are strong baselines.** `grep` with a
   trivial regex beats every LLM summary variant tested here.
5. **Real LLM summaries can be stable but costly and lossy.** Real summary
   was the second-most cross-split-stable method on this corpus, but spent
   ~83k summary-processing tokens to produce a 439-token context that scored
   below `grep`.
6. **Budget-aware routing can beat single-method baselines.** A two-method
   router with one threshold matched or beat every single-method baseline
   under both debuggers.
7. **Stronger debuggers narrow quality gaps but do not eliminate token-cost
   differences.** Sonnet closed hybrid's quality lead over grep to ~0pp but
   the 3× cost ratio held.
8. **Confident-error and abstention are important safety metrics.**
   Calibrated confident-error v1.1 dropped to 0% under Sonnet; Haiku
   exhibited 0–60% confident-error rates depending on context method. Auto
   metrics that ignore confidence behavior would mis-rank methods.
9. **Forced-choice human pairwise can disagree with sv1.1 even when both
   sit inside the absolute-usefulness tie band.** AI-assisted human review
   in E9 rated hybrid and grep as ≈ tied on absolute usefulness (means
   3.875 vs 3.938) but preferred grep 8-to-2 in head-to-head pairs (out of
   10 decisive). The pattern: hybrid's compactness sometimes loses specific
   quotable details (test names, file:line, bot account) that the reviewer
   values, even when sv1.1 awards full literal-mention credit for semantic
   paraphrases.

---

## 14. Limitations

- **16 cases.** Directional, not statistical.
- **Expert-model calibration + AI-assisted human review of the headline.**
  sv1.1 was calibrated against an LLM-as-judge reviewer in E2/E2b. E9 added a
  48-item AI-assisted human review pass on the v1.3 hybrid-vs-grep comparison
  (1 reviewer, project author, verified a ChatGPT draft). This is not
  independent human review and not inter-rater-validated. A second
  independent human reviewer remains the strongest follow-up.
- **Two debugger models only.** Haiku 4.5 and Sonnet 4.6, both via Anthropic
  API. Opus 4.7, OpenAI / GPT-class models, and open models were not tested.
- **One real summarizer model and one summary prompt.** All LLM-summary
  numbers come from `llm_summary_v1_*` prompts on Haiku 4.5.
- **Small and hand-annotated corpus.** Cases were curated by hand from
  GitHub Actions logs the project's authors had access to.
- **Deterministic scoring is a proxy.** sv1.1 is calibrated against expert-
  model labels; it is not a guarantee of agent usefulness.
- **No MCP / search-agent baseline yet.** The benchmark currently only
  measures static-context strategies.
- **RTK version-specific results.** RTK output formats can shift between
  versions. The protocol records the RTK version and command metadata used
  here (rather than a vendored binary SHA), so results may change across RTK
  versions.
- **Hybrid threshold selected from prior analysis.** The 4k threshold came
  out of E4's offline budget sweep on the same case set; downstream E5/E6
  results should be read as confirming the offline pick, not independent
  re-discovery.

---

> ## What not to conclude
>
> This report does **not** show that:
>
> - hybrid routing is generally best for CI debugging
> - RTK is worse than grep in general (the locked v1.3 RTK output is one version's behavior on a 16-case corpus)
> - LLM summaries are bad in general (one summarizer model, one prompt, one corpus)
> - sv1.1 is a human-validated measure (calibration is via expert-model review, not human review)
> - CILogBench fully measures agentic debugging ability (no MCP / search-agent baseline yet)
> - the benchmark is definitive (16 cases; treat results as directional)

---

## 15. Recommended future work

In rough priority order:

1. **A second independent human reviewer on the E9 batch.** E9 closed the
   "expert-model only" gap with one AI-assisted human reviewer (project
   author). A truly independent reviewer is the only way to compute real
   inter-rater agreement and to lift the project-bias caveat.
2. **MCP / search-agent baseline.** E7 implemented one (`mcp-search-agent-
   v1-sonnet`); E8 found no deployable search-fallback policy beat hybrid.
   Both verdicts were `KEEP_AS_EXPLORATORY` / `STOP_SEARCH_TRACK` — leave
   exploratory unless a different model family or different agent prompt
   shows a different failure profile.
3. **Larger corpus with more ecosystems.** Java/Maven, Python/poetry, Go,
   different CI providers (CircleCI / Buildkite). Current corpus is heavy
   on JavaScript / Python / Rust. **This is the biggest constraint on
   every claim** — wider corpus would also widen score variance and let
   the human-vs-sv1.1 correlation be computed cleanly (the E9 batch was
   score-compressed to 4/4 for 29 of 32 items).
4. **More debuggers** — Opus 4.7, GPT-class, an open model. E6 confirmed
   one cross-model replication; a third would harden the model-stability
   claim.
5. **More hybrid policies.** `hybrid-grep-8k-rtk`, `hybrid-grep-4k-tail`,
   `hybrid-grep-4k-summary` — each was rejected by E4's offline sweep on
   this corpus, but a larger corpus might re-rank them.
6. **Real summarizer v2** — only worth running if strict final-context
   budgets are a target deployment scenario. Otherwise, the E3/E4 finding
   that summary loses on quality/cost stands.

---

## 16. Reproducing the v1.3 headline result

The full E6 replication run can be reproduced from the locked protocol with:

```bash
# 1. Validate the lock (recomputes every recorded SHA, confirms 16 cases × 3 splits)
python3 tools/validate_protocol_lock.py \
  --protocol protocols/cilogbench-v1.3.lock.json

# 2. (one-time) Build the hybrid baseline outputs from the locked grep + rtk-err-cat
#     manifests. Anti-leakage: router reads only context manifests + token estimates.
for split in dev holdout stress; do
  python3 tools/run_hybrid_baseline.py \
    --split $split \
    --config configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json
  python3 tools/evaluate_signal_recall.py \
    --split $split --method hybrid-grep-4k-rtk-err-cat-v1
done

# 3. Run the fixed second debugger over every locked v1.3 baseline.
#     Set DIAGNOSIS_COMMAND to the shim of your choice; for the Sonnet run we used:
#       export DIAGNOSIS_COMMAND="python3 examples/diagnosis_shim_claude_cli.py"
#       export CILOGBENCH_CLAUDE_MODEL=sonnet
#     and the same shim with CILOGBENCH_CLAUDE_MODEL=haiku for the v1 run.
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
python3 tools/run_protocol_diagnosis_eval.py \
  --protocol protocols/cilogbench-v1.3.lock.json \
  --diagnoser-name real-debugger-v2 \
  --diagnoser-config configs/diagnosers/real-debugger-v2.json \
  --context-methods raw,tail,grep,rtk-read,rtk-log,rtk-err-cat,llm-summary-v1-mock,hybrid-grep-4k-rtk-err-cat-v1 \
  --allow-external-llm

# 4. Render the comparison report (reads both v1 and v2 eval JSONs)
python3 tools/render_e6_replication_report.py
```

This produces `reports/e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md`,
the source of every E6 number quoted in this report. Per-case manifests under
`results/<split>/diagnoses/real-debugger-v{1,2}/<method>.jsonl` are byte-stable
when rerun against the per-row cache; non-deterministic API output is the only
known source of drift.

---

## 17. Appendix: protocol and artifact links

```text
protocols/cilogbench-v1.3.lock.json                     frozen v1.3 protocol
configs/evaluation/category_compatibility_v1_1.json     sv1.1 calibration table
configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json      hybrid router config
schemas/hybrid_route.schema.json                        per-case route record schema
docs/protocol/cilogbench_v1_3.md                        v1.3 protocol doc

reports/e2_calibration_memo.md                          E2 expert-model review
reports/e2b_score_calibration_v1_1.md                   E2b sv1 → sv1.1 calibration
reports/e3_real_llm_summary_cilogbench_v1_2_haiku.md    E3 real summary
reports/e4_summary_failure_attribution_cilogbench_v1_2.md  E4 budget frontier
reports/e5_hybrid_grep_fallback_cilogbench_v1_2.md      E5 hybrid first-class
reports/cilogbench_v1_3_freeze_memo.md                  v1.3 freeze
reports/e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md  E6 replication
reports/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md  E7 search-agent
reports/e8_hybrid_first_search_fallback_cilogbench_v1_3.md  E8 search-fallback routing
reports/e9_cross_model_expert_style_review.md           E9 cross-model spot-check (ChatGPT)
reports/e9_human_verified_v1_3_review.md                E9 AI-assisted human review (this run)

results/e2b_score_calibration_v1_1.json                 calibration raw data
results/e3_real_llm_summary_cilogbench_v1_2_haiku.manifest.json
results/e4_budget_frontier.json                         budget sweep raw data
results/e4_summary_failure_analysis.json                per-case failure attribution
results/e5_hybrid_grep_fallback_cilogbench_v1_2.manifest.json
results/e6_second_debugger_cilogbench_v1_3_real-debugger-v2.manifest.json
results/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.manifest.json
results/e8_hybrid_first_search_fallback_cilogbench_v1_3.json
results/e9_human_verified_v1_3_review.manifest.json
results/human_review_e9_v1_3_hybrid_vs_grep_human_001.json   E9 analyzer output

review/batches/e2-real-debugger-v1-holdout-001/         E2 expert-model review batch
review/batches/e9_v1_3_hybrid_vs_grep_human_001/        E9 human-review batch + UI
docs/model_cards/real-debugger-v1.md                    Haiku 4.5 debugger card
docs/model_cards/real-debugger-v2.md                    Sonnet 4.6 debugger card
docs/model_cards/llm-summary-v1-haiku.md                Haiku summarizer card
```
