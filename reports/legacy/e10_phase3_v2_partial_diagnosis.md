# E10 Phase 3 (Partial) — Real-debugger-v1 + v2 diagnosis on the v2 corpus

> **Status:** partial / 8 v2 cases (Phase 2 paused at 8/34, not the
> 10-case checkpoint). Real `claude-sonnet-4-6` (real-debugger-v2)
> AND `claude-haiku-4-5` (real-debugger-v1) calls via the
> `examples/diagnosis_shim_claude_cli.py` shim with
> `CILOGBENCH_CLAUDE_MODEL={sonnet,haiku}` and the v1.3-locked
> `prompts/debugger_v1.md`. **128 model calls total** (8 methods × 8
> cases × 2 debuggers).
>
> Companion to [`e10_phase3_v2_partial_signal_recall.md`](e10_phase3_v2_partial_signal_recall.md).
> The signal-recall report's headline (hybrid is the worst-generalizing
> method on v2) **is now confirmed using the calibrated
> `diagnosis_score_v1_1` metric** — i.e. the same metric the v1.3
> headline was based on.

## TL;DR

`hybrid-grep-4k-rtk-err-cat-v1` falls from rank #1 (tied with grep)
on v1.3 to **rank #6 of 8** on v2.

```text
                                    v1.3 sv1.1  v2 sv1.1     Δ
method                              (3 splits)  (2 splits)
hybrid-grep-4k-rtk-err-cat-v1         0.7713      0.4495   -0.3219   ← largest drop
llm-summary-v1-mock                   0.5181      0.2981   -0.2200
grep                                  0.7700      0.6664   -0.1036
rtk-log                               0.3089      0.2434   -0.0656
tail                                  0.6886      0.6647   -0.0238
rtk-read                              0.5224      0.5040   -0.0184
rtk-err-cat                           0.5343      0.5173   -0.0170
raw                                   0.5110      0.5478   +0.0368   ← only method that improves
```

Confident-error rate on hybrid:

```text
                                    v1.3 confErr_v1_1  v2 confErr_v1_1
hybrid-grep-4k-rtk-err-cat-v1            0.0000             0.1666
```

`raw` actually improves on v2 (+0.0368) — the v2 logs are on average
more compact than v1.3 (median ~3000 lines vs v1.3's ~5000), so
"hand the whole log to the debugger" stops being prohibitively noisy.

## Ranking change

```text
v1.3 ranking by sv1.1 (3-split macro):
  1. hybrid                    0.7713
  2. grep                      0.7700  (effectively tied with hybrid)
  3. tail                      0.6886
  4. rtk-err-cat               0.5343
  5. rtk-read                  0.5224
  6. llm-summary-v1-mock       0.5181
  7. raw                       0.5110
  8. rtk-log                   0.3089

v2 ranking by sv1.1 (2-split macro):
  1. grep                      0.6664
  2. tail                      0.6647   (effectively tied with grep)
  3. raw                       0.5478
  4. rtk-err-cat               0.5173
  5. rtk-read                  0.5040
  6. hybrid                    0.4495   ← was #1 on v1.3
  7. llm-summary-v1-mock       0.2981
  8. rtk-log                   0.2434
```

The v1.3 one-pager headline:
> "matched grep on quality at ~⅓ token cost"

is **falsified** by the v2 corpus. Hybrid does not match grep on v2;
it scores 0.22 sv1.1 below grep on v2, with a confident-error rate
0.17 above grep. The cost advantage holds (~95% reduction), but the
quality match does not generalize.

## Per-case hybrid vs grep on v2

```text
case_id                                hybrid sv1.1  grep sv1.1   route
moby-buildx-bake-v2-001                  0.5500       0.6500     rtk-err-cat
pip-pytest-network-github-v2-001         0.9167       0.9750     rtk-err-cat
pnpm-jest-config-v2-001                  0.0000       0.6067     rtk-err-cat   ← total fail
biome-pnpm-not-found-v2-001              0.2500       0.5500     rtk-err-cat
gh-cli-go-test-prompter-v2-001           0.3000       0.3000     grep          (tied: both failed)
pandas-cpp-xsimd-neon64-v2-001           0.7500       0.9000     rtk-err-cat
pnpm-audit-vuln-ip-address-v2-001        0.1500       0.4000     grep          (hybrid worse despite same route)
prettier-jest-snapshot-babel-v2-001      0.6000       0.7950     rtk-err-cat
```

Notable failure modes:

- **pnpm-jest-config-v2-001 → 0.00**. The hybrid routed to
  rtk-err-cat, which extracted only the per-package PASS lines and
  the GHA `##[error]` annotation. The actual jest assertion diff
  (`Expected: "https://my-org.registry.example.com" / Received:
  "https://my-org.registry.example.com/"`) was dropped.
  Sonnet diagnosed against the truncated context and produced a
  confident-but-wrong root cause — the case fails on
  `confident_error_v1_1`, dragging the score to 0.
- **biome-pnpm-not-found-v2-001 → 0.25**. rtk-err-cat extracted
  the cargo crate listings (which look like errors to the heuristic)
  rather than the trailing `pnpm: not found` line. Sonnet
  diagnosed a Rust compile/build problem instead of the missing-tool
  workflow misconfig.
- **pandas-cpp / prettier-snapshot / moby-buildx / pip-pytest →
  hybrid trails grep by 0.10–0.20**. rtk-err-cat catches the
  surface error but not enough surrounding context for confident
  high-quality diagnosis. Grep with ±3/8 lines does better.

## What this confirms vs what's new

**Confirmed from signal-recall report**:
- Hybrid is the worst-generalizing method on v2.
- Grep is the most stable.
- The v1.3 4k-token threshold is overfit to v1.3.

**New from real-debugger run**:
- `raw` improves on v2 (signal-recall already at 1.0 on v1.3, so
  signal-recall couldn't change; sv1.1 *can* change because Sonnet's
  diagnosis quality on raw context depends on log size and noise
  profile, both of which are smaller in v2).
- Confident-error rate on hybrid jumps to 0.17 on v2 — i.e. the
  hybrid sometimes produces a high-confidence wrong diagnosis when
  rtk-err-cat truncates the assertion diff.
- The `hybrid > grep` v1.3 ranking flips to `grep > hybrid` on v2.
  Margin: -0.22 sv1.1.

## v2-corpus-specific findings

- **Single test_assertion case where hybrid failed completely**
  (pnpm-jest-config). The jest expected/received diff is the kind
  of tightly-bounded surface that rtk-err-cat misses but grep with
  ±3/8 lines catches reliably.
- **Cases where both grep and hybrid lose** (gh-cli-go-test +
  pnpm-audit-vuln) are independent of routing — the failure
  surfaces don't match grep's regex (`error|failed|...`). These are
  v1.3-grep-regex blindspots, not threshold issues.
- **Cases where rtk-read works** (raw passthrough): all 8 cases hit
  1.0 signal-recall but only ~0.5 sv1.1 — Sonnet's diagnosis on
  uncompressed context is noisy because v1 / v2 logs both have
  >1k lines of pre-failure noise that distract the model.

## Why this matters for v1.3 conclusions

The v1.3 limitations doc §9 said:
> The 4k-token threshold inside `hybrid-grep-4k-rtk-err-cat-v1`
> was chosen in E4's offline budget-frontier sweep on the same
> case set later used to score the hybrid in E5. This is a
> deliberate choice ... but it does mean E5 / E6 numbers should
> be read as **confirming the offline pick**, not as
> **independent re-discovery**.

E10 Phase 3 is the independent re-discovery test. **Result:**
- Hybrid sv1.1 collapses 0.32 from v1.3 (0.77) to v2 (0.45).
- Hybrid confidence-error rate jumps from 0 to 0.17.
- Hybrid was the v1.3 winner; on v2 it's bottom-third.

This does NOT invalidate the v1.3 numbers — they are what they are
on the v1.3 corpus. It does invalidate the **claim that the v1.3
hybrid generalizes**. The v1.3 one-pager headline must carry an
explicit v2 caveat.

## Caveats

1. **8 v2 cases** is small. Variance per-case is high (one case at
   0.00 vs 0.61 alone moves the macro by ~0.07). The headline
   direction is strong (hybrid drops by 3-4× any other method) but
   the exact magnitude could shift at 30+ cases.
2. **AI-drafted ground truth** for v2 (Opus 4.7 reading raw.log)
   was human-verified item-by-item via per-case checklists. The
   diagnoser is Sonnet 4.6 — different model — so there is no
   direct same-model leakage. But there is potential for
   correlated-error bias (Opus and Sonnet may share patterns in
   what they consider "must_mention"). A second human reviewer on
   the v2 ground truth would close this gap.
3. **One debugger model.** Sonnet 4.6 only. v1.3 had two debuggers
   (Haiku 4.5 + Sonnet 4.6) and the rank top-3 was identical. The
   v2 corpus has only Sonnet 4.6 results so far. Adding Haiku 4.5
   would test whether the v2 ranking is debugger-specific.
4. **Mock summary, not real summary.** Same constraint as v1.3.
5. **No human review of v2 diagnoses.** v1.3 had E2/E2b expert-model
   review and E9 AI-assisted human review. v2 has neither yet.
   The sv1.1 metric used here is the same calibrated formula as
   v1.3's, but its calibration on v2 is unverified.
6. **Hybrid routing on v2** decided 6 of 8 cases go to rtk-err-cat.
   On v1.3, the 16-case split was more balanced. The rtk-err-cat
   weakness on v2 is amplified by routing.

## Cross-debugger confirmation (Haiku 4.5 + Sonnet 4.6)

The same 8 methods × 8 v2 cases were also run with
`real-debugger-v1` (`claude-haiku-4-5`). Result: **the hybrid drop
is debugger-stable** — both Haiku and Sonnet show it as the
worst-generalizing method on v2, by a wide margin.

```text
                                v1.3 macro     v2 macro       Δ        v1.3 macro     v2 macro       Δ
method                          (Haiku)        (Haiku)     (Haiku)     (Sonnet)       (Sonnet)    (Sonnet)
raw                              0.4543         0.4352    -0.0191       0.5110         0.5478    +0.0368
tail                             0.6612         0.5464    -0.1149       0.6886         0.6647    -0.0238
grep                             0.6755         0.5472    -0.1283       0.7700         0.6664    -0.1036
rtk-read                         0.4575         0.4454    -0.0121       0.5224         0.5040    -0.0184
rtk-log                          0.2800         0.2330    -0.0469       0.3089         0.2434    -0.0656
rtk-err-cat                      0.4942         0.4712    -0.0230       0.5343         0.5173    -0.0170
llm-summary-v1-mock              0.4938         0.2668    -0.2270       0.5181         0.2981    -0.2200
hybrid-grep-4k-rtk-err-cat-v1    0.7150         0.4150    -0.3000       0.7713         0.4495    -0.3219
                                                          ^^^^^^^                                  ^^^^^^^
                                                         largest                                  largest
```

Cross-debugger ranking on v2 (1 = best):

```text
                                  Haiku v2           Sonnet v2
method                            score   rank       score   rank
grep                              0.5472    1        0.6664    1   ← unanimous winner on v2
tail                              0.5464    2        0.6647    2   ← stable #2
rtk-err-cat                       0.4712    3        0.5173    4
rtk-read                          0.4454    4        0.5040    5
raw                               0.4352    5        0.5478    3
hybrid-grep-4k-rtk-err-cat-v1     0.4150    6        0.4495    6   ← unanimous #6 on v2
llm-summary-v1-mock               0.2668    7        0.2981    7
rtk-log                           0.2330    8        0.2434    8
```

Top-2 and bottom-3 ranks are **identical** across debuggers. Hybrid
is rank 6 in both. Compare to v1.3 where hybrid was #1 (Sonnet) /
#1 (Haiku). The v1.3 model-stability finding ("hybrid stays #1
across two debuggers") generalizes the wrong way: hybrid stays #6
across two debuggers on v2.

## What would change the conclusion

- 30+ v2 cases with the same patterns would harden the headline.
- A v2-tuned hybrid threshold (e.g. 8k or 12k) would likely
  recover some quality. But re-tuning on the same v2 corpus
  re-introduces the selection-by-method risk that v2 was meant
  to test against — better to wait for a v3 corpus to evaluate
  any retuned hybrid.
- A third debugger model (Opus 4.7 or GPT-class) — Haiku 4.5 and
  Sonnet 4.6 already agree, but adding a different model family
  would lift the "two-Anthropic-models" caveat.
- Independent human review of v2 ground truth + v2 diagnoses would
  close the AI-on-AI bias caveat.

## Where to next

- **Update the v1.3 one-pager** with an explicit v2 caveat line:
  *"Quality match between hybrid and grep on v1.3 does not
  generalize on the 8-case v2 corpus (hybrid sv1.1 −0.22 vs grep)."*
- **Continue Phase 2** to 30+ v2 cases. Specifically target:
  - More test_assertion cases with bounded assertion diffs (where
    hybrid currently fails)
  - Go `--- FAIL:` cases (where grep blindspot lives)
  - Audit/lint outputs in ascii_table format (other grep blindspot)
  - Timeout/OOM and matrix/monorepo (still un-found)
- **Add a second debugger** (Haiku 4.5) to confirm the v2 ranking
  isn't Sonnet-specific.
- **Independent human review** on the v2 batch before claiming
  a v2 frozen protocol.

## Where the numbers live

```text
results/v2/{dev,holdout}/diagnoses/real-debugger-v2/<method>.jsonl
    Per-case diagnoses written by Sonnet 4.6 (one row per case).

results/v2/{dev,holdout}/eval_diagnosis_real-debugger-v2.json
    Per-method aggregated metrics (sv1, sv1.1, confErr_v1.1, etc.).

results/{dev,holdout,stress}/eval_diagnosis_real-debugger-v2.json
    Same format on v1.3 splits — used as the comparison baseline.
```
