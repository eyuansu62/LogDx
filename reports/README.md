# LogDx-CI Reports

The canonical technical artifact for LogDx-CI is **one report**.
Everything else in this directory is an audit trail.

## The technical report

- [`e10_v2_generalization_partial.md`](e10_v2_generalization_partial.md)
  — headline finding, methodology, full per-method per-debugger
  breakdown, caveats. This is what to cite.

## Audit trail

[`legacy/`](legacy/) holds 48 working-notes / per-experiment writeups
from the v1.0 → v1.2 development phases (calibration memos, per-split
diagnosis evals, signal-recall analyses, contamination checks,
prototype-debugger writeups, freeze memos, and the e2–e9 series of
per-experiment writeups that fed into the technical report above).

These are preserved for provenance and audit purposes; they are
**not** part of the citable public artifact. The published v1.2
numbers can be reproduced end-to-end from the technical report alone
(see [`../RELEASE_NOTES_v1_2.md`](../RELEASE_NOTES_v1_2.md)).
