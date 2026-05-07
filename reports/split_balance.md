# Split balance check

| Split | Cases | Frameworks | Categories | Log-size buckets | Positions |
|---|---:|---|---|---|---|
| dev | 5 | cargo, generic, jest, pytest | compile_error, lint_error, permission_or_secret, test_assertion, type_error | large, medium, small | late, scattered |
| holdout | 5 | cargo, generic, tsc | compile_error, dependency_install, github_actions_config, permission_or_secret, test_assertion | medium, small | late |
| stress | 6 | generic, prettier, pytest | formatting_failure, github_actions_config, permission_or_secret, test_assertion | large, small | late, middle |
| v2/dev | 3 | docker, jest, pytest | docker_build, network_or_flaky, test_assertion | large, medium | late, middle |
| v2/holdout | 5 | cargo, generic, jest, pnpm | compile_error, dependency_install, github_actions_config, snapshot_or_golden_diff, test_assertion | large, medium, small | late, middle, scattered |
| v2/stress | 2 | pytest | matrix_or_monorepo_failure, test_assertion | large, medium | late |

## Flags

- `failure_category_split_mismatch`: {"value": "compile_error", "present_in": ["dev", "holdout", "v2/holdout"], "missing_in": ["stress", "v2/dev", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "dependency_install", "present_in": ["holdout", "v2/holdout"], "missing_in": ["dev", "stress", "v2/dev", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "docker_build", "present_in": ["v2/dev"], "missing_in": ["dev", "holdout", "stress", "v2/holdout", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "formatting_failure", "present_in": ["stress"], "missing_in": ["dev", "holdout", "v2/dev", "v2/holdout", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "github_actions_config", "present_in": ["holdout", "stress", "v2/holdout"], "missing_in": ["dev", "v2/dev", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "lint_error", "present_in": ["dev"], "missing_in": ["holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "matrix_or_monorepo_failure", "present_in": ["v2/stress"], "missing_in": ["dev", "holdout", "stress", "v2/dev", "v2/holdout"]}
- `failure_category_split_mismatch`: {"value": "network_or_flaky", "present_in": ["v2/dev"], "missing_in": ["dev", "holdout", "stress", "v2/holdout", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "permission_or_secret", "present_in": ["dev", "holdout", "stress"], "missing_in": ["v2/dev", "v2/holdout", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "snapshot_or_golden_diff", "present_in": ["v2/holdout"], "missing_in": ["dev", "holdout", "stress", "v2/dev", "v2/stress"]}
- `failure_category_split_mismatch`: {"value": "type_error", "present_in": ["dev"], "missing_in": ["holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]}
- `framework_split_mismatch`: {"value": "cargo", "present_in": ["dev", "holdout", "v2/holdout"], "missing_in": ["stress", "v2/dev", "v2/stress"]}
- `framework_split_mismatch`: {"value": "docker", "present_in": ["v2/dev"], "missing_in": ["dev", "holdout", "stress", "v2/holdout", "v2/stress"]}
- `framework_split_mismatch`: {"value": "generic", "present_in": ["dev", "holdout", "stress", "v2/holdout"], "missing_in": ["v2/dev", "v2/stress"]}
- `framework_split_mismatch`: {"value": "jest", "present_in": ["dev", "v2/dev", "v2/holdout"], "missing_in": ["holdout", "stress", "v2/stress"]}
- `framework_split_mismatch`: {"value": "pnpm", "present_in": ["v2/holdout"], "missing_in": ["dev", "holdout", "stress", "v2/dev", "v2/stress"]}
- `framework_split_mismatch`: {"value": "prettier", "present_in": ["stress"], "missing_in": ["dev", "holdout", "v2/dev", "v2/holdout", "v2/stress"]}
- `framework_split_mismatch`: {"value": "pytest", "present_in": ["dev", "stress", "v2/dev", "v2/stress"], "missing_in": ["holdout", "v2/holdout"]}
- `framework_split_mismatch`: {"value": "tsc", "present_in": ["holdout"], "missing_in": ["dev", "stress", "v2/dev", "v2/holdout", "v2/stress"]}
- `framework_dominance`: {"split": "v2/stress", "framework": "pytest", "fraction": 1.0}
- `signal_position_monoculture`: {"split": "holdout", "position": "late"}
- `signal_position_monoculture`: {"split": "v2/stress", "position": "late"}

## Disclaimer

These flags are diagnostic. A split can be intentionally adversarial (e.g. `stress` may dominate in small logs to test tail-like methods). Use flags to inform future additions, not to gate the protocol.
