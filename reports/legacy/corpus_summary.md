# CILogBench corpus summary

Generated at 2026-04-24T15:31:30.965072+00:00.

## Case counts

| Split | Cases |
|---|---:|
| dev | 5 |
| holdout | 5 |
| stress | 6 |
| **total** | **16** |

## By framework

| Value | dev | holdout | stress | total |
|---|---:|---:|---:|---:|
| cargo | 1 | 1 | 0 | 2 |
| generic | 2 | 3 | 3 | 8 |
| jest | 1 | 0 | 0 | 1 |
| prettier | 0 | 0 | 1 | 1 |
| pytest | 1 | 0 | 2 | 3 |
| tsc | 0 | 1 | 0 | 1 |

## By failure_category

| Value | dev | holdout | stress | total |
|---|---:|---:|---:|---:|
| compile_error | 1 | 1 | 0 | 2 |
| dependency_install | 0 | 1 | 0 | 1 |
| formatting_failure | 0 | 0 | 1 | 1 |
| github_actions_config | 0 | 1 | 1 | 2 |
| lint_error | 1 | 0 | 0 | 1 |
| permission_or_secret | 1 | 1 | 2 | 4 |
| test_assertion | 1 | 1 | 2 | 4 |
| type_error | 1 | 0 | 0 | 1 |

## By log_size_bucket

| Value | dev | holdout | stress | total |
|---|---:|---:|---:|---:|
| large | 1 | 0 | 2 | 3 |
| medium | 3 | 2 | 0 | 5 |
| small | 1 | 3 | 4 | 8 |

## By signal_position

| Value | dev | holdout | stress | total |
|---|---:|---:|---:|---:|
| late | 3 | 5 | 5 | 13 |
| middle | 0 | 0 | 1 | 1 |
| scattered | 2 | 0 | 0 | 2 |

## By diagnosis_difficulty

| Value | dev | holdout | stress | total |
|---|---:|---:|---:|---:|
| easy | 0 | 0 | 3 | 3 |
| hard | 0 | 0 | 1 | 1 |
| medium | 0 | 0 | 2 | 2 |
| unclear | 5 | 5 | 0 | 10 |

## Evidence formats (multi-valued; rows may count multiple tags)

| Value | dev | holdout | stress |
|---|---:|---:|---:|
| ansi_colored_block | 5 | 4 | 2 |
| compiler_diagnostic | 1 | 0 | 0 |
| diff_block | 0 | 0 | 2 |
| github_annotation | 5 | 5 | 0 |
| plain_error_line | 0 | 1 | 4 |
| shell_command_output | 0 | 0 | 4 |
| test_progress_noise | 0 | 0 | 1 |
| traceback | 0 | 1 | 0 |

## Noise profile (multi-valued)

| Value | dev | holdout | stress |
|---|---:|---:|---:|
| dependency_install_noise | 3 | 3 | 2 |
| log_group_noise | 5 | 5 | 4 |
| low_noise | 0 | 0 | 3 |
| runner_setup | 5 | 5 | 6 |
| test_progress_noise | 2 | 1 | 2 |
| verbose_build_noise | 3 | 1 | 0 |

## Flags

| Flag | dev | holdout | stress | total |
|---|---:|---:|---:|---:|
| multi_failure | 5 | 4 | 1 | 10 |
| flaky_or_transient | 0 | 0 | 0 | 0 |

