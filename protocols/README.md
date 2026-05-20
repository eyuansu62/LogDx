# Protocol locks

## Current (v1.1.x family — `logdx-ci-*`)

```
logdx-ci-v1.1.lock.json                # v1.1 release (2026-05-18)
logdx-ci-v1.1.1.lock.json              # v1.1.1 release (2026-05-20)
logdx-ci-v2-partial-2026-06-22.lock.json   # rolling "live" lock validated by CI
```

These are the actively maintained locks. `tools/validate_protocol_lock.py`
points at `logdx-ci-v2-partial-2026-06-22.lock.json` in the CI workflow;
the per-release locks (`v1.1`, `v1.1.1`) are point-in-time snapshots for
reproducibility of published numbers.

## Legacy (`cilogbench-*` namespace)

Moved to [`legacy/`](legacy/). These predate the v1.0 rebrand from
"CILogBench" to "LogDx-CI" (commit `0ce65e9`, 2026-05-15). They are
referenced by historical analysis tools under `tools/render_e*.py` and
`tools/analyze_*.py` and by the v1.3 frozen reports under
`docs/reports/cilogbench_v1_3_*` and `docs/protocol/cilogbench_v1*.md`.

The lock files themselves remain valid — none of the SHA-pinned schemas /
prompts / evaluators have been deleted, just renamed in some cases. The
`cilogbench-v1.3.lock.json` is in particular still the canonical
reproducibility anchor for the v1.3 technical report's 16-case numbers.

Don't add new lock files under `legacy/`. New releases go in the parent
`protocols/` directory with the `logdx-ci-*` prefix.

## How to add a new release lock

```bash
python3 tools/freeze_protocol.py \
  --protocol-id logdx-ci-vX.Y[.Z] \
  --splits dev,holdout,stress,v2/dev,v2/holdout,v2/stress
```

The frozen lock pins SHA256 of every schema, prompt, evaluator,
hybrid-baseline config, and per-case ground-truth bundle. `tools/
validate_protocol_lock.py --protocol <lock>` checks for drift.
