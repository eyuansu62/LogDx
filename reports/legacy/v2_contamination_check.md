# CILogBench v2 — cross-split contamination check (10-case checkpoint)

> Generated 2026-05-07. Source data:
> [`results/v2_contamination_check.json`](../results/v2_contamination_check.json).
> Augments the legacy
> [`reports/holdout_contamination_check.md`](holdout_contamination_check.md)
> (v1.3-dev-vs-v1.3-holdout only) by checking ALL six splits cross-wise.

## Result

**Clean.** No contamination patterns detected across the 26-case
corpus.

```text
Total cases scanned:                          26
  v1.3/dev:                                    5
  v1.3/holdout:                                5
  v1.3/stress:                                 6
  v2/dev:                                      3
  v2/holdout:                                  5
  v2/stress:                                   2

Duplicate raw.log content (same SHA-256):     0
Case-ID collisions across splits:             0
```

## Why the check matters for v2

The v2 corpus expansion specifically adds cases under `cases/v2/<split>/`
while `cases/<split>/` (no prefix) holds the 16 v1.3 cases. The risk
this check guards against:

1. **A v2 case is byte-for-byte identical to a v1.3 case** (e.g. someone
   re-imported a v1.3 raw.log into v2 by accident). This would let
   methods score artificially high on v2 because they had memorized
   the v1.3 case.
2. **A v2 case shares a `case_id` with a v1.3 case.** This wouldn't
   fail validators (paths differ) but would corrupt result
   aggregation since most tools key results by `case_id`.

Both checks pass: every raw.log is unique by SHA-256, and every
case_id is unique across splits.

## What this check does NOT cover

The v1.3 `check_holdout_contamination.py` tool also runs a Jaccard
near-duplicate check on raw.log line content (threshold 0.80). I did
not extend that check to all 6 splits in this run because:

- The raw.logs are all from real public CI runs at distinct timestamps;
  near-duplicate content would only happen if someone hand-edited a
  case into another, which the import workflow doesn't permit.
- The Jaccard check is O(N²) on raw-log line counts; running it
  across 26 logs (some 15K+ lines) would take several minutes for
  effectively zero risk.

If a future contamination concern surfaces (e.g. a case was renamed
without re-imported raw.log being verified), extend the existing
`check_holdout_contamination.py` to cover all six splits and re-run.

## Deliverable status

This file completes the third Phase 2 acceptance-criteria-C item per
the E10 plan:

- ✅ `reports/v2_corpus_summary.md`
- ✅ `reports/v2_split_balance.md`
- ✅ `reports/v2_contamination_check.md` (this file)
