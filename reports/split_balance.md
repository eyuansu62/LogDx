# Split balance check

| Split | Cases | Frameworks | Categories | Log-size buckets | Positions |
|---|---:|---|---|---|---|
| dev | 5 | cargo, generic, jest, pytest | compile_error, lint_error, permission_or_secret, test_assertion, type_error | large, medium, small | late, scattered |
| holdout | 5 | cargo, generic, tsc | compile_error, dependency_install, github_actions_config, permission_or_secret, test_assertion | medium, small | late |
| stress | 6 | generic, prettier, pytest | formatting_failure, github_actions_config, permission_or_secret, test_assertion | large, small | late, middle |

## Flags

- `failure_category_split_mismatch`: {"value": "compile_error", "present_in": ["dev", "holdout"], "missing_in": ["stress"]}
- `failure_category_split_mismatch`: {"value": "dependency_install", "present_in": ["holdout"], "missing_in": ["dev", "stress"]}
- `failure_category_split_mismatch`: {"value": "formatting_failure", "present_in": ["stress"], "missing_in": ["dev", "holdout"]}
- `failure_category_split_mismatch`: {"value": "github_actions_config", "present_in": ["holdout", "stress"], "missing_in": ["dev"]}
- `failure_category_split_mismatch`: {"value": "lint_error", "present_in": ["dev"], "missing_in": ["holdout", "stress"]}
- `failure_category_split_mismatch`: {"value": "type_error", "present_in": ["dev"], "missing_in": ["holdout", "stress"]}
- `framework_split_mismatch`: {"value": "cargo", "present_in": ["dev", "holdout"], "missing_in": ["stress"]}
- `framework_split_mismatch`: {"value": "jest", "present_in": ["dev"], "missing_in": ["holdout", "stress"]}
- `framework_split_mismatch`: {"value": "prettier", "present_in": ["stress"], "missing_in": ["dev", "holdout"]}
- `framework_split_mismatch`: {"value": "pytest", "present_in": ["dev", "stress"], "missing_in": ["holdout"]}
- `framework_split_mismatch`: {"value": "tsc", "present_in": ["holdout"], "missing_in": ["dev", "stress"]}
- `signal_position_monoculture`: {"split": "holdout", "position": "late"}

## Disclaimer

These flags are diagnostic. A split can be intentionally adversarial (e.g. `stress` may dominate in small logs to test tail-like methods). Use flags to inform future additions, not to gate the protocol.
