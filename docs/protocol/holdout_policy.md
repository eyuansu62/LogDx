# Holdout policy

The `cases/holdout/` split exists to test whether methods generalize
beyond the cases they were developed on. It is not a second dev set.

## Rules

1. **Do not inspect holdout per-case failures to tune methods.**
   Aggregated numbers are OK to look at; drilling into a specific
   holdout miss and changing a prompt / regex / filter based on it
   breaks the split.
2. **Method development happens on dev.** Add new methods, tune
   parameters, iterate on prompts, debug tooling, then lock the
   protocol. Holdout is what you measure last.
3. **Holdout annotations are created before methods are run on them.**
   This prevents the annotator from subconsciously matching the
   annotation to what a particular method can produce.
4. **If holdout was used to tune a method**, the resulting run MUST be
   labeled `post-holdout-tuned`. These runs are reported separately
   from clean runs and do not enter the aggregate comparison.
5. **If the protocol itself needs to change** (a scoring bug, a schema
   addition), bump the version (`cilogbench-v2`, or `cilogbench-v1.1`
   for minor fixes). Do not silently edit `cilogbench-v1`.

## What IS allowed

- Inspecting aggregate dev-vs-holdout numbers in
  `reports/dev_vs_holdout_<protocol>.md`.
- Noting that a method has a large dev/holdout gap as evidence for
  *future* work, with the change deferred to a new protocol version.
- Running a newly-added method over dev + holdout under the locked
  protocol, provided no dev parameters were touched after seeing the
  holdout result.

## What is NOT allowed

- Reading `cases/holdout/<case_id>/raw.log` while editing a prompt or
  regex that will be re-run on holdout in the same session.
- "Fixing" a method after seeing a holdout miss and then re-running on
  holdout and quoting the improved number as a v1 result.
- Moving a case between dev and holdout after both have been populated.
- Using holdout logs as training data for a model whose outputs are
  evaluated on the same holdout (covert self-tuning).

## Governance checks that catch this

- `tools/check_holdout_contamination.py` flags exact / near / normalized
  duplicates between dev and holdout, and flags holdout case IDs that
  already show up under `results/dev/*.jsonl`.
- `tools/validate_protocol_lock.py` fails when any locked file changes,
  including prompts and evaluators. A silent prompt edit during
  holdout tuning will break the lock.
- Experiment manifests record the prompt SHA and the diagnoser/config
  SHA. If those differ between the "dev run" and the "holdout run" for
  the same claim, the claim is invalid.

## When the policy is violated

If you realize holdout has been used for tuning (even accidentally):

1. Document what was changed and when.
2. Re-run the tuned method on BOTH splits under a new protocol
   version (`cilogbench-v1.1` or `-v2` depending on severity).
3. Do not backport the tuned numbers to `cilogbench-v1` claims.
4. Consider adding new holdout cases so future comparisons are
   meaningful.

The point is not to punish mistakes — it is to keep the benchmark
credible. A v1 claim about a method that was tuned against v1's holdout
is, by definition, not about holdout.
