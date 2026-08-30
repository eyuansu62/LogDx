#!/usr/bin/env python3
"""Compute LogDx v1.3 transfer statistics from canonical eval artifacts."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def ranks(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: item[1], reverse=True)
    out: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        rank = ((index + 1) + end) / 2
        for key, _ in ordered[index:end]:
            out[key] = rank
        index = end
    return out


def spearman(left: dict[str, float], right: dict[str, float]) -> tuple[float | None, int]:
    common = sorted(set(left) & set(right))
    if len(common) < 2:
        return None, len(common)
    left_ranks = ranks({key: left[key] for key in common})
    right_ranks = ranks({key: right[key] for key in common})
    x = [left_ranks[key] for key in common]
    y = [right_ranks[key] for key in common]
    mean_x = statistics.fmean(x)
    mean_y = statistics.fmean(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denominator = math.sqrt(
        sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y)
    )
    return (numerator / denominator if denominator else None), len(common)


def paired_bootstrap(
    deltas: list[float], *, samples: int = 10_000, seed: int = 1300
) -> dict:
    if not deltas:
        return {"paired_cases": 0, "mean_delta": None, "ci95": [None, None]}
    rng = random.Random(seed)
    means = [
        statistics.fmean(rng.choice(deltas) for _ in deltas)
        for _ in range(samples)
    ]
    return {
        "paired_cases": len(deltas),
        "mean_delta": round(statistics.fmean(deltas), 6),
        "ci95": [
            round(percentile(means, 0.025) or 0.0, 6),
            round(percentile(means, 0.975) or 0.0, 6),
        ],
        "samples": samples,
        "seed": seed,
        "sufficient_for_claim": len(deltas) >= 10,
    }


EVAL_METRICS = (
    "diagnosis_score_v1_1",
    "confident_error_v1_1",
    "abstained",
    "critical_signal_mention_recall",
    "valid_evidence_quote_rate",
    "context_tokens",
    "diagnosis_tokens",
)


def validate_panel(rows: dict, label: str) -> dict[str, set]:
    """Require one score for every method on the same split/case population."""
    if not rows:
        raise ValueError(f"empty evaluation panel: {label}")
    cases_by_method: dict[str, set] = {}
    for (split, method, case_id), metrics in rows.items():
        score = metrics.get("diagnosis_score_v1_1")
        if score is None or not math.isfinite(score):
            raise ValueError(
                f"missing or non-finite diagnosis score: {label}: {(split, method, case_id)}"
            )
        cases_by_method.setdefault(method, set()).add((split, case_id))
    reference = next(iter(cases_by_method.values()))
    for method, cases in cases_by_method.items():
        if cases != reference:
            raise ValueError(f"incomplete case/method panel: {label}: {method}")
    return cases_by_method


def paired_deltas(
    left: dict, left_method: str, right: dict, right_method: str
) -> list[float]:
    left_cases = {(s, c) for s, m, c in left if m == left_method}
    right_cases = {(s, c) for s, m, c in right if m == right_method}
    if not left_cases or left_cases != right_cases:
        raise ValueError(f"missing paired comparison rows: {left_method} versus {right_method}")
    return [
        metrics["diagnosis_score_v1_1"]
        - right[(split, right_method, case_id)]["diagnosis_score_v1_1"]
        for (split, method, case_id), metrics in left.items()
        if method == left_method
    ]


def validate_comparison_panels(current: dict, historical: dict) -> None:
    current_cases = validate_panel(current, "current")
    historical_cases = validate_panel(historical, "historical")
    for required in ("raw", "hybrid-grep-120k-rtk-tail-v3"):
        if required not in current_cases:
            raise ValueError(f"missing required comparison method: {required}")
    shared = current_cases.keys() & historical_cases.keys()
    if not shared:
        raise ValueError("current and historical panels have no shared methods")
    for method in shared:
        if current_cases[method] != historical_cases[method]:
            raise ValueError(f"missing paired historical comparison rows: {method}")


def load_eval(diagnoser: str, results_dir: Path) -> tuple[dict, dict]:
    rows: dict[tuple[str, str, str], dict[str, float]] = {}
    aggregate: dict[str, dict[str, list[float]]] = {}
    for path in sorted(results_dir.glob(f"**/eval_diagnosis_{diagnoser}.json")):
        split = str(path.parent.relative_to(results_dir))
        data = json.loads(path.read_text(encoding="utf-8"))
        for method in data.get("methods", []):
            name = method["context_method"]
            if not method.get("cases"):
                raise ValueError(f"empty evaluation method: {path}: {name}")
            for case in method.get("cases", []):
                values = {
                    metric: float(case[metric])
                    for metric in EVAL_METRICS
                    if case.get(metric) is not None
                }
                key = (split, name, case["case_id"])
                if key in rows:
                    raise ValueError(f"duplicate evaluation row: {diagnoser}: {key}")
                rows[key] = values
                bucket = aggregate.setdefault(name, {})
                for metric, value in values.items():
                    bucket.setdefault(metric, []).append(value)
    validate_panel(rows, diagnoser)
    return rows, {
        method: {
            metric: round(statistics.fmean(values), 6)
            for metric, values in metrics.items()
        }
        for method, metrics in aggregate.items()
    }


def historical_panel(
    diagnosers: list[str], results_dir: Path
) -> tuple[dict, dict]:
    if not diagnosers or len(set(diagnosers)) != len(diagnosers):
        raise ValueError("historical diagnosers must be nonempty and unique")
    collected: dict[tuple[str, str, str], dict[str, list[float]]] = {}
    expected_keys = None
    for diagnoser in diagnosers:
        rows, _ = load_eval(diagnoser, results_dir)
        if expected_keys is None:
            expected_keys = set(rows)
        elif set(rows) != expected_keys:
            raise ValueError(f"incomplete historical panel: {diagnoser}")
        for key, metrics in rows.items():
            bucket = collected.setdefault(key, {})
            for metric, value in metrics.items():
                bucket.setdefault(metric, []).append(value)
    rows = {
        key: {
            metric: statistics.fmean(values)
            for metric, values in metrics.items()
        }
        for key, metrics in collected.items()
    }
    aggregate: dict[str, dict[str, list[float]]] = {}
    for (_, method, _), metrics in rows.items():
        bucket = aggregate.setdefault(method, {})
        for metric, value in metrics.items():
            bucket.setdefault(metric, []).append(value)
    means = {
        method: {
            metric: round(statistics.fmean(values), 6)
            for metric, values in metrics.items()
        }
        for method, metrics in aggregate.items()
    }
    return rows, means


def load_runtime(diagnoser: str, results_dir: Path) -> dict[str, dict]:
    collected: dict[str, dict[str, list[float] | int]] = {}
    for path in sorted(results_dir.glob(f"**/diagnoses/{diagnoser}/*.jsonl")):
        method = path.stem
        bucket = collected.setdefault(
            method,
            {"model_latency_ms": [], "success_runtime_ms": [], "error_runtime_ms": [],
             "input_tokens": [], "output_tokens": [],
             "premium_requests": [], "nano_aiu": [], "errors": 0, "rows": 0},
        )
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            bucket["rows"] = int(bucket["rows"]) + 1
            metadata = row.get("metadata") or {}
            failed = bool(metadata.get("provider_error"))
            if failed:
                bucket["errors"] = int(bucket["errors"]) + 1
            info = metadata.get("model_info") or {}
            usage = info.get("usage") or {}
            # Never mix provider model time with local adapter runtime.
            model_latency = info.get("model_call_duration_ms")
            if not failed and model_latency is not None:
                bucket["model_latency_ms"].append(float(model_latency))
            runtime = metadata.get("runtime_ms")
            if runtime is not None:
                key = "error_runtime_ms" if failed else "success_runtime_ms"
                bucket[key].append(float(runtime))
            input_tokens = usage.get("prompt_tokens", usage.get("inputTokens"))
            output_tokens = usage.get("completion_tokens", usage.get("outputTokens"))
            if input_tokens is not None:
                bucket["input_tokens"].append(float(input_tokens))
            if output_tokens is not None:
                bucket["output_tokens"].append(float(output_tokens))
            cli_usage = info.get("cli_result_usage") or {}
            if cli_usage.get("premiumRequests") is not None:
                bucket["premium_requests"].append(float(cli_usage["premiumRequests"]))
            observable = info.get("observable_ai_usage") or {}
            if observable.get("total_nano_aiu") is not None:
                bucket["nano_aiu"].append(float(observable["total_nano_aiu"]))
    out = {}
    for method, bucket in collected.items():
        rows = int(bucket["rows"])
        out[method] = {
            "rows": rows,
            "provider_error_rate": round(int(bucket["errors"]) / rows, 6) if rows else None,
            "mean_input_tokens": round(statistics.fmean(bucket["input_tokens"]), 2) if bucket["input_tokens"] else None,
            "mean_output_tokens": round(statistics.fmean(bucket["output_tokens"]), 2) if bucket["output_tokens"] else None,
            "premium_requests": round(sum(bucket["premium_requests"]), 6) if bucket["premium_requests"] else None,
            "observable_total_nano_aiu": round(sum(bucket["nano_aiu"]), 6),
            "successful_model_call_latency_ms": latency_summary(bucket["model_latency_ms"]),
            "successful_end_to_end_latency_ms": latency_summary(bucket["success_runtime_ms"]),
            "rejected_end_to_end_latency_ms": latency_summary(bucket["error_runtime_ms"]),
            "all_rows_end_to_end_latency_ms": latency_summary(
                bucket["success_runtime_ms"] + bucket["error_runtime_ms"]
            ),
        }
    return out


def latency_summary(values: list[float]) -> dict:
    return {
        "observations": len(values),
        "p50": round(percentile(values, 0.5), 2) if values else None,
        "p95": round(percentile(values, 0.95), 2) if values else None,
    }


def accepted_cases(diagnoser: str, method: str, results_dir: Path) -> set:
    """Cases delivered without a provider/adapter error, including abstentions."""
    accepted = set()
    for path in sorted(results_dir.glob(f"**/eval_diagnosis_{diagnoser}.json")):
        split = str(path.parent.relative_to(results_dir))
        for entry in json.loads(path.read_text())["methods"]:
            if entry["context_method"] == method:
                for case in entry["cases"]:
                    if case["provider_error"] is None:
                        accepted.add((split, case["case_id"]))
    return accepted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnoser", required=True)
    parser.add_argument(
        "--historical-diagnoser",
        action="append",
        dest="historical_diagnosers",
        help="Historical diagnoser to include. Repeat for a panel.",
    )
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    historical_diagnosers = args.historical_diagnosers or [
        "real-debugger-v1", "real-debugger-v2", "real-debugger-v3"
    ]
    current, current_means = load_eval(args.diagnoser, args.results_dir)
    historical, historical_means = historical_panel(
        historical_diagnosers, args.results_dir
    )
    validate_comparison_panels(current, historical)
    current_score_means = {
        method: values["diagnosis_score_v1_1"]
        for method, values in current_means.items()
    }
    historical_score_means = {
        method: values["diagnosis_score_v1_1"]
        for method, values in historical_means.items()
    }
    correlations, common_methods = spearman(
        current_score_means, historical_score_means
    )
    methods = {}
    for method in sorted(current_means):
        # New methods such as Drain3 intentionally have no historical baseline.
        deltas = (
            paired_deltas(current, method, historical, method)
            if method in historical_means else []
        )
        raw_deltas = paired_deltas(current, method, current, "raw")
        hybrid_method = "hybrid-grep-120k-rtk-tail-v3"
        hybrid_deltas = paired_deltas(current, method, current, hybrid_method)
        methods[method] = {
            **{f"{metric}_mean": value for metric, value in current_means[method].items()},
            "paired_delta_vs_historical": paired_bootstrap(deltas),
            "paired_delta_vs_current_raw": paired_bootstrap(raw_deltas),
            "paired_delta_vs_current_hybrid_v3": paired_bootstrap(hybrid_deltas),
        }
    output = {
        "diagnoser": args.diagnoser,
        "historical_diagnosers": historical_diagnosers,
        "method_count": len(current_means),
        "case_method_rows": len(current),
        "spearman_method_ranking": {
            "rho": round(correlations, 6) if correlations is not None else None,
            "common_methods": common_methods,
            "sufficient_for_claim": common_methods >= 5,
        },
        "methods": methods,
        "runtime": load_runtime(args.diagnoser, args.results_dir),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
