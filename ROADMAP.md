# LogDx-CI Roadmap

Status as of 2026-05-21.

| Release | Status | Highlights |
|---|---|---|
| **v1.0** | shipped 2026-05-18 | 35-case corpus × 3 model families. [Release notes](RELEASE_NOTES.md) · [Homepage](https://logdx-bench.github.io/) |
| **v1.0.1** | shipped 2026-05-18 | Added `confident_error_rate_v1_1` and `total_tokens` columns to the leaderboard, plus a cost-quality Pareto plot. |
| **v1.1** | shipped 2026-05-18 | Agent-loop leaderboard. Every method gains in agent-loop, the quality range collapses 6× (0.42 → 0.069), confident-error rates drop to 0% on 8 of 10 methods. See [analysis/agent-loop-vs-single-shot.md](docs/analysis/agent-loop-vs-single-shot.md). |
| **v1.1.1** | shipped 2026-05-20 | Promoted real `llm-summary-v1-haiku` to the headline (replaces the `llm-summary-v1-mock` stub); single-shot score +0.24 to +0.36 across diagnoser families. Fixed stale `v2-partial` lock that had been failing CI since `a5a22f6`. |
| **v1.1.2** | shipped 2026-05-20 | Polish release: USD cost column, mock moved to appendix, v1.1.1 protocol lock frozen, `protocols/legacy/` cleanup, HF dataset drift gate, v1.3 historical-doc deprecation banners, chunk_lines=100 caveat. |
| **v1.2** | shipped 2026-05-20 | Cross-family LLM-summary: `llm-summary-v1-gpt-5-mini` (real OpenAI gpt-5-mini map-reduce summarizer) becomes new agent-loop #1 at 0.749 with 0.37 tools/case. Cross-pair beats self-pair → self-call-bias hypothesis falsified. 10× cheaper than haiku-summary. |
| **v1.3** | exploratory | See [`docs/plans/`](docs/plans/) (local, not committed) for current drafts: model-family expansion (Gemini / Llama), cost-integrated ranking + dynamic-mode agent benchmark, hybrid + LLM-summary fallback router. |
| **v2** | exploratory | Train/holdout decoupling, GPT-4o / DeepSeek families, `fix_action` evaluation, third-party independent reproduction. |

This roadmap is informed by the RTK community's
"signal-loss-during-aggressive-compression" issue cluster
(see [the analysis post](docs/analysis/why-rtk-underperforms-on-ci-diagnosis.md)).
Each item below names the community thread or finding that motivates
it, so contributors can trace the design decision.

## Priorities

The six v1.1 items below are ordered by **structural impact on
benchmark credibility**, not by implementation effort.

```
P0 (shipped in v1.0.1)  : #3 confident_error_rate column
                          #2 cost + latency reporting (token columns + Pareto plot)
P0 (shipped in v1.1)    : #1 multi-turn / agent-loop benchmark (Sonnet 4.6, 35 cases)
P0 (deferred to v1.2)   : #2-followup USD pricing snapshot + reducer runtime for grep/tail
P1 (deferred to v1.2)   : #1-followup agent-loop on Haiku 4.5 + gpt-5-mini
                          #4 configured-RTK baseline
                          #5 vitest / dotnet / Playwright corpus expansion
P2 (deferred to v1.2)   : #6 decision-making (fix_action) evaluation dimension
```

P0 items are required for v1.1 release. P1 items ship if time permits.
P2 items are stretch goals; they may slip to v1.2.

## #3 — confident_error_rate as a separate column · DONE in v1.0.1

**Motivation**: [rtk-ai/rtk#1599](https://github.com/rtk-ai/rtk/issues/1599)
("go build reports 'Success' when it failed") and
[rtk-ai/rtk#827](https://github.com/rtk-ai/rtk/issues/827)
("LLM takes decisions on incomplete diffs") name a specific failure
mode that's more dangerous than "missed diagnosis": a method that
produces *confidently wrong* output. v1.0 had the metric in eval
JSON but folded into `diagnosis_score_v1_1`, hiding the safety
distinction.

**Done**: Added `confident_error_rate_v1_1` as a column on
[`docs/index.md`](docs/index.md) and
[`docs/leaderboard.md`](docs/leaderboard.md). Methodology lives in
[`tools/evaluate_diagnosis.py`](tools/evaluate_diagnosis.py) (already)
and aggregation is reproducible via
[`tools/aggregate_confident_error.py`](tools/aggregate_confident_error.py).

**Key finding surfaced**: top-3 methods produce zero or near-zero
confident misdiagnoses; `rtk-log` and `llm-summary-v1-mock` produce
13.3% each. Safety and quality rank together, not in tension.

## #1 — Multi-turn / agent-loop benchmark · P0 for v1.1

**Motivation**: Community evidence that single-shot results don't
predict real-agent results.
- [rtk-ai/rtk#690](https://github.com/rtk-ai/rtk/issues/690): Playwright
  agents need *"3-5x more iterations"* to debug E2E failures with RTK.
- [rtk-ai/rtk#1351](https://github.com/rtk-ai/rtk/issues/1351): public
  terminal-bench 2.0 run shows RTK *increases* codex token usage —
  agent has to retry repeatedly because compressed output lacks
  the signal needed for action.

**Gap in v1.0**: LogDx-CI runs every method as `log → reducer →
single LLM call → score`. Real Claude Code / Codex usage is
`log → reducer → LLM → tool calls (grep/read_file/tail) → LLM →
...`. A method that scores 0.7 single-shot but forces 5 iterations
of follow-up tool calls is **worse** in practice than one scoring
0.6 in a single shot.

**Scope for v1.1**:

1. New diagnoser variant `real-agent-v1` that supports tool calls
   (`grep`, `read_file`, `tail`, `view_log_lines`).
2. Iteration cap: 5 turns. Token budget: same as current.
3. New metrics:
   - `turns_to_diagnosis`: turns used before the agent issues
     a final root-cause answer.
   - `total_input_tokens_consumed`: cumulative LLM input tokens
     across all turns (proxy for cost).
   - `tool_call_count`: number of tool invocations.
4. Re-run all 10 baselines through `real-agent-v1` on Sonnet 4.6
   (Haiku and gpt-5-mini if budget allows).
5. New leaderboard section: **agent-loop leaderboard** alongside
   the single-shot one. Hypothesis: hybrid routers' advantage
   should *increase* in agent-loop because they front-load the
   signal-rich grep output, reducing follow-up grep calls.

**Effort**: medium-large. The harness exists in `tools/run_diagnosis.py`
but needs a tool-call loop; `examples/diagnosis_shim_claude_cli.py`
already supports tool definitions. Mostly evaluator + protocol work,
not new model work.

## #2 — Cost + latency reporting · Mostly DONE in v1.0.1

**Motivation**: The community's central RTK debate is about **cost**,
not about diagnosis quality in isolation. Examples:
- [rtk-ai/rtk#582](https://github.com/rtk-ai/rtk/issues/582):
  "RTK Hook Increases Claude Code Costs by 18%" (disputed; maintainers
  ran rebuttal benchmarks).
- [rtk-ai/rtk#839](https://github.com/rtk-ai/rtk/issues/839):
  "Empirical benchmark: 5 repos, 2,100 measurements — how do actual
  savings compare to claims?"
- [rtk-ai/rtk#1351](https://github.com/rtk-ai/rtk/issues/1351):
  terminal-bench data showing increased token use.

**Done in v1.0.1**:

1. Added `total_tokens` column to the leaderboard on
   [`docs/index.md`](docs/index.md) and
   [`docs/leaderboard.md`](docs/leaderboard.md).
2. Added a [cost-quality Pareto plot](docs/figures/cost_quality_pareto.png)
   to the leaderboard. 4 methods on the Pareto frontier:
   `rtk-log` / `tail-200` / `hybrid-grep-120k-tail` /
   `hybrid-grep-120k-rtk-tail`.
3. Added full cost breakdown table to the leaderboard:
   `reducer_in` + `reducer_out` + `context` + `diag_out` + `total`.
   Surfaces that `llm-summary-v1-mock` consumes 432k tokens/case
   end-to-end (370k input + 60k output to produce a 1.3k summary)
   — the most expensive method on the board.
4. Aggregation lives in
   [`tools/aggregate_cost_metrics.py`](tools/aggregate_cost_metrics.py);
   plot generation in
   [`tools/make_pareto_plot.py`](tools/make_pareto_plot.py).

**Deferred to v1.1**:

- **USD cost per case**. Need a pinned price snapshot
  (Anthropic Haiku 4.5, Sonnet 4.6, OpenAI gpt-5-mini list prices
  with a snapshot date in the protocol lock) before publishing
  USD figures.
- **Reducer runtime for grep / tail / hybrid baselines.** v1.0 only
  records `external_tool.runtime_ms` for RTK methods (via the
  external-tool wrapper). For non-LLM, non-RTK methods, runtime
  needs to be measured by a re-run with timing instrumentation —
  small but requires a baseline re-run.

## #4 — Configured-RTK baseline · P1 for v1.1

**Motivation**: v1.0 uses stock `rtk` invocations
(`rtk read`, `rtk log`, `rtk err cat`). Multiple community threads
imply that power users tune RTK significantly:
- [rtk-ai/rtk#1313](https://github.com/rtk-ai/rtk/issues/1313):
  RKelln audited 47+ `.take(N)` truncation sites; says they're
  controllable.
- The current `docs/methods/rtk.md` already notes "no modification
  of the user's RTK config" as an intentional scope decision.

**Gap in v1.0**: Comparing stock RTK to grep is **structurally
unfair** if a tuned RTK can close the gap. The "RTK loses on CI
diagnosis" claim is only as strong as the configuration we tested.

**Scope for v1.1**:

1. New baseline: `rtk-tuned-for-ci` using a community-recommended
   `.rtkrc` or `--rules` set focused on preserving failure patterns.
2. Reach out to RTK maintainers via [rtk-ai/rtk#1313](https://github.com/rtk-ai/rtk/issues/1313)
   for their recommended CI-diagnosis configuration. Pin and ship
   the exact config under `configs/baselines/rtk-tuned-for-ci.json`.
3. Include `rtk-tuned-for-ci` in the v1.1 leaderboard. If it closes
   the gap to `grep`, the v1.0 framing of "RTK underperforms stand-
   alone" gets a major qualifier added: *"out of the box."*

**Effort**: medium. Mostly waiting on RTK maintainer input + one
new baseline runner. Risk: if maintainers don't engage, we ship
with our best-effort tuning + an open invitation.

## #5 — Test-runner / ecosystem corpus expansion · P1 for v1.1

**Motivation**: Community issues name concrete test runners that RTK
handles poorly:
- [rtk-ai/rtk#1813](https://github.com/rtk-ai/rtk/issues/1813):
  vitest *"shows 5 of 49 failures, hides the rest."*
- [rtk-ai/rtk#1882](https://github.com/rtk-ai/rtk/issues/1882):
  go test failure details hidden.
- [rtk-ai/rtk#1574](https://github.com/rtk-ai/rtk/issues/1574):
  dotnet test summary cut off.
- [rtk-ai/rtk#690](https://github.com/rtk-ai/rtk/issues/690):
  Playwright E2E test agents can't see failure detail.

**Gap in v1.0**: 35-case corpus covers pytest / cargo / `go test` /
mvn / pnpm-jest / gradle / biome, but is light on `vitest` (0 cases),
**`dotnet test`** (0 cases), and **E2E test runners** (0 cases).

**Scope for v1.1**:

1. Add **+5 vitest cases**, **+3 dotnet test cases**, **+2 Playwright
   or Cypress E2E cases**. Total: 35 → 45 cases.
2. Re-evaluate all 10 baselines (single-shot) and all agent-loop
   baselines (from #1).
3. Verify the headline finding (top-3 ∩ stable across families)
   survives the corpus expansion.

**Effort**: medium. Each case is ~2-4 hours wall-clock (find a
public failing CI run + privacy audit + AI-draft ground truth +
single-author verify). 10 cases ≈ 1 person-week.

## #6 — Decision-making (fix_action) evaluation dimension · P2 for v1.1

**Motivation**: [rtk-ai/rtk#827](https://github.com/rtk-ai/rtk/issues/827)
specifically frames this as
*"LLM takes **decisions** on incomplete diffs."* Diagnosing the root
cause and choosing the right next action are different tasks; the
latter is what real agents do.

**Gap in v1.0**: We score "did the LLM identify the right root cause"
but not "did the LLM choose the right fix command."

**Scope for v1.1**:

1. For each ground truth case, add a `fix_action` field documenting
   the canonical next action (e.g., `pip install foo==1.2.3`,
   `gh secret set GITHUB_TOKEN`, `kubectl rollout undo deployment/x`).
2. New eval dimension `fix_action_match_score` — LLM prompted to
   output the next shell command; scored against the canonical
   action via category + argument overlap.
3. Optional: separate `fix_action_leaderboard` if scores differ
   meaningfully from diagnosis scores.

**Effort**: medium-large. Adding `fix_action` to 45 cases is
non-trivial (these are higher-information ground-truth annotations
than category). May ship as P2 deferred to v1.2 if #1, #2, #4, #5
already fill the v1.1 window.

## v1.2 — patches caught by codex review #3

Surfaced during v1.1's third adversarial review. Zero impact on
v1.1 published numbers (audit confirmed 0 affected rows), but
both are real bugs that future v1.1+ runs should not inherit.

### #7 — Bind endpoint into cache identity

Currently `CILOGBENCH_AGENT_V1_BASE_URL` participates in cache_key
only when set; when unset, the shim chooses its default endpoint
from `OPENROUTER_API_KEY` vs `ANTHROPIC_API_KEY` and that choice
is NOT reflected in cache identity. Result: an OpenRouter cache
row could replay when the next invocation routes to Anthropic
direct. Patch: pin `model.base_url` in the diagnoser config and
validate `metadata.model_info.base_url` against it (mirror the
OpenAI shim's `model.base_url_env_var_name` pattern). Effort: ~1
day of code; no API spend.

### #8 — Surface forced-final failure as structured provider_error

The post-loop forced-final no-tools call's `except` block swallows
API errors (network, token-cap from the provider) into an
`unknown_body` row with `budget_exhausted=True` but no
`provider_error`. The runner then accepts it as a normal "unknown"
diagnosis. Patch: route the exception to a `tool_use_budget_
exhausted` provider_error envelope (already in the
non_fatal_provider_error_prefixes allowlist). Add regression test
where the forced-final call raises and assert provider_error
surfaces. Effort: ~½ day; no API spend.

## Out-of-scope for v1.1 (recorded for v1.2+)

- **Other compression tools**: `terminal-output-summarizer`,
  `llm-aware-tee`, custom GPT-4o summarizers running real (not mock).
- **Beyond CI**: git diff compression, JSON output triage, cloud-CLI
  output (`eks describe-cluster` — [rtk-ai/rtk#1466](https://github.com/rtk-ai/rtk/issues/1466)).
  These are RTK's main use cases; LogDx-CI scope explicitly excludes them.
- **Train/holdout decoupling**: v1.0 uses the same 35-case corpus
  for both calibration and reporting. v2 wants a strict held-out
  split that none of the hybrid thresholds were tuned on.
- **Additional model families**: GPT-4o, Gemini 2.5 Pro, Llama 3.3.
  Cost-budget-constrained; consider crowd-sourcing via the
  homepage's "Submit your model" pipeline (not yet built).

## How to contribute

The corpus and protocol are designed for forkability. To add a case
or a baseline:

1. Follow [`docs/corpus/cilogbench_v2_annotation_guide.md`](docs/corpus/cilogbench_v2_annotation_guide.md)
   to import a case.
2. Run [`tools/validate_cases.py`](tools/validate_cases.py) +
   [`tools/validate_case_tags.py`](tools/validate_case_tags.py)
   before opening a PR.
3. New baselines should match the existing baseline shape
   (input `raw.log`, output `<case_id>.txt` + metadata). See
   `tools/run_baseline.py` for the simplest example.

[Issues and PRs welcome](https://github.com/eyuansu62/LogDx/issues).
For changes to the eval methodology, please open an issue first
to discuss whether it's a v1.x calibration tweak or a v2 break.
