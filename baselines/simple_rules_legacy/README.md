# simple_rules_legacy

A **legacy deterministic-rules baseline** retained for comparison, not the main
product.

This is the Python `cilog` package that used to be the primary CI log compressor
for this project. Under the CILogBench pivot it is kept in place (unchanged) as
one of the baselines the benchmark will eventually compare:

- raw log (no processing)
- tail / head baselines
- grep / error heuristics
- **this: simple rules legacy**
- RTK (external tool)
- LLM summary
- MCP / search-style agent

## Use

From the repo root:

```bash
PYTHONPATH=baselines/simple_rules_legacy python -m cilog.bench --synthetic
PYTHONPATH=baselines/simple_rules_legacy python -m cilog.bench --offline --out /tmp/legacy_out
PYTHONPATH=baselines/simple_rules_legacy python -m cilog.expand <raw.log> <section_id>
```

`cilog/` ships its own `results/raw/` cache of historical GitHub Actions logs
that was used to tune it; those logs have now been promoted into `cases/dev/`
under the new benchmark layout.

## Status

**Frozen.** No new framework compressors or signal rules should be added here.
If a new pattern is needed, the correct home is either a new benchmark method
or a framework-specific annotation in `cases/dev/*/ground_truth.json`. The
legacy code's own CLAUDE.md still applies if you're debugging the legacy
compressor itself.
