# Human review — `holdout-stub-001`

- Protocol: **cilogbench-v1.1**
- Split: **holdout**
- Diagnoser: `stub-debugger-v1`
- Reviewers: ['synthetic-infra']
- Items: {'total': 50, 'absolute': 20, 'pairwise': 30}

## Absolute-score means by method

| Method | Cases | Root-cause | Evidence | Localization | Actionable | Hallucination (↓ better) | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 5 | 1.800 | 2.200 | 1.200 | 1.200 | 0.000 | 2.200 |
| grep | 5 | 1.200 | 1.800 | 0.800 | 0.800 | 0.000 | 1.800 |
| rtk-err-cat | 5 | 1.200 | 1.800 | 0.800 | 0.800 | 0.000 | 1.800 |
| rtk-log | 5 | 0.600 | 1.400 | 0.400 | 0.400 | 0.000 | 1.400 |

## Pairwise win / loss / tie by method

| Method | Wins | Losses | Ties |
|---|---:|---:|---:|
| raw | 8 | 7 | 0 |
| grep | 9 | 6 | 0 |
| rtk-err-cat | 8 | 7 | 0 |
| rtk-log | 5 | 10 | 0 |

## Human-vs-deterministic correlation (Spearman)

Correlations over all absolute-mode labels. Small samples: treat as directional only.

| Pair | Spearman |
|---|---:|
| `overall_vs_score_v1` | 0.965 |
| `root_cause_vs_category_accuracy` | 0.612 |
| `evidence_vs_critical_mention` | 0.965 |
| `evidence_vs_valid_quote` | N/A |
| `hallucination_vs_forbidden` | N/A |

## Largest disagreements (human_overall vs diagnosis_score_v1)

| case_id | method | human_overall / 4 | det_score_v1 | gap |
|---|---|---:|---:|---:|
| `docs-transformers-001` | `raw` | 3/4 | 0.110 | 0.640 |
| `pushpr-nextjs-001` | `raw` | 3/4 | 0.110 | 0.640 |
| `pushpr-nextjs-001` | `grep` | 3/4 | 0.110 | 0.640 |
| `pushpr-nextjs-001` | `rtk-err-cat` | 3/4 | 0.110 | 0.640 |
| `tsc-typescript-001` | `rtk-log` | 3/4 | 0.455 | 0.295 |

## Reviewer agreement

- Only 1 reviewer(s); agreement not computed.

## Limitations

- Small batch. A single label flipping can move per-method means by 0.5–1.0 on a 0–4 scale.
- Reviewer blinding is enforced at label-validation time but subtle rubric drift can still leak. Re-randomize the seed when building a new batch.
- Correlation with deterministic metrics is directional only; weak Spearman does not prove the deterministic metric is wrong.
- The `synthetic-reviewer` label file (if present) is for infrastructure validation only. Real human runs must replace it.
