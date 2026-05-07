# Annotation freeze policy

Ground-truth annotations are part of the protocol. Once a split is
frozen in a protocol lock, changing an annotation silently invalidates
every previous benchmark run on that case.

## Changes permitted without bumping the protocol

Only mechanical fixes, and only when they do not shift scoring
materially:

- Pure typo fixes in `notes` or non-scoring text.
- Correcting an `evidence_lines` range that was wrong (e.g. off-by-one)
  when the corrected range covers the same evidence.
- Adding an `aliases` entry so a literal substring already present in
  the raw log registers against a signal whose canonical `value` does
  not appear verbatim (this can surface during M3-style text scoring).
- Correcting a clearly wrong `root_cause.category`.
- Splitting or merging `evidence_spans` without changing the set of
  covered lines.

Any of these must still trigger the rebuild process below.

## Changes that require a new protocol version

Anything that affects scoring beyond the mechanical fixes above:

- Adding or removing `required_signals`.
- Changing a signal's `importance`.
- Rewriting `root_cause.summary` so `must_mention` / `must_not_claim`
  shift.
- Editing `must_mention` or `must_not_claim` lists.
- Adding aliases solely to make a new method win (this is the
  classic smell; it is forbidden).

Bump as:

- `cilogbench-v1.1` for compatible corrections.
- `cilogbench-v2` for anything that materially changes what a method
  must produce to count as correct.

## Required rebuild process after any annotation change

1. **Document the bug**: add a note in the case's `case.json`
   describing the change and its justification.
2. **Update the annotation**.
3. **Rebuild split manifest**:
   `python tools/build_split_manifest.py --split <affected>`.
4. **Regenerate the protocol lock** at a new protocol ID:
   `python tools/freeze_protocol.py --protocol-id cilogbench-v1.1`
   (or `-v2`). Do not use `--force` on the existing v1 lock.
5. **Rerun all affected methods** on the split, not only the method
   that benefits. Selective rerun is indistinguishable from cheating.
6. **Regenerate dev↔holdout comparison reports**.

## Forbidden patterns

- Tuning an annotation after seeing a specific method's output. The
  signal must be justified by the raw log alone.
- Using `aliases` to cover up a summarizer paraphrase. If a summarizer
  is paraphrasing away evidence, that is a summarizer-quality finding,
  not an annotation fix.
- Removing `must_not_claim` entries because a diagnoser keeps hitting
  them. That is a diagnoser-quality finding — the claim is still
  forbidden.

## Why this is strict

With only 5 dev + 5 holdout cases, one annotation tweak can swing a
macro metric by 10+ percentage points. A loose freeze policy would
make any v1 claim unfalsifiable. The strict policy is how small-split
benchmarks stay honest.
