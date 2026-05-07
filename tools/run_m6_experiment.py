"""
M6 experiment wrapper: run a real fixed debugger across every context
method, evaluate, and emit a reproducibility manifest + experiment
report.

This does NOT change anything in the pipeline — it is a thin wrapper
around the existing M1–M5 tools, plus:

    - an explicit external-LLM opt-in gate
      (env var CILOGBENCH_ALLOW_EXTERNAL_LLM=1 OR --allow-external-llm)
    - a diagnoser config file with its own SHA-256
    - a privacy audit executed before any external-model call
    - a manifest JSON that captures the run for reproducibility
    - a per-run M6 report with a signal-vs-diagnosis cross-view

Usage:
    export DIAGNOSIS_COMMAND="/path/to/diagnosis_shim"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

    python tools/run_m6_experiment.py \\
        --split dev \\
        --diagnoser-name my-debugger-v1 \\
        --config configs/diagnosers/example.debugger-v1-command.json \\
        --context-method all \\
        --allow-external-llm
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_commit() -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except Exception:
        return "unknown", False
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8")
        dirty = any(line.strip() for line in status.splitlines())
    except Exception:
        dirty = False
    return commit, dirty


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")


def check_external_llm_opt_in(config: dict, cli_flag: bool) -> bool:
    """Returns True when the wrapper is allowed to run the command provider.

    The wrapper defaults to REFUSING. Two independent opt-in paths are
    honored: CILOGBENCH_ALLOW_EXTERNAL_LLM=1 in the environment, OR
    --allow-external-llm on the command line. Both paths exist so users
    can pick whichever is more auditable in their setup (env var leaves
    a process-level footprint; CLI flag shows up in shell history).
    """
    requires_opt_in = bool(
        (config.get("privacy") or {}).get("requires_explicit_external_llm_opt_in", True)
    )
    env_on = os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM", "") == "1"
    if not requires_opt_in:
        return True
    return env_on or cli_flag


def run_step(argv: list[str], *, label: str) -> None:
    print(f"\n$ {' '.join(argv)}")
    res = subprocess.run(argv, cwd=ROOT)
    if res.returncode != 0:
        raise SystemExit(f"step '{label}' failed with exit {res.returncode}")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


# ---------------------------------------------------------------------------
# M6 experiment report
# ---------------------------------------------------------------------------


def pct(x: float | None) -> str:
    if x is None:
        return "N/A"
    return f"{x * 100:.1f}%"


def num(x: float | None, digits: int = 3) -> str:
    if x is None:
        return "N/A"
    return f"{x:.{digits}f}"


def humanize_tokens(n: float | None) -> str:
    if n is None:
        return "N/A"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def build_signal_vs_diagnosis(
    *, split: str, results_dir: Path, diagnoser_name: str,
) -> tuple[list[dict], list[str]]:
    """Join signal-recall evals (per method) with diagnosis evals (per
    context method within this diagnoser). Returns (rows, notes)."""
    diag_eval = load_json(results_dir / split
                           / f"eval_diagnosis_{diagnoser_name}.json")
    rows: list[dict] = []
    notes: list[str] = []
    for mb in diag_eval["methods"]:
        method = mb["context_method"]
        sr_path = results_dir / split / f"eval_{method}.json"
        if sr_path.exists():
            sr = load_json(sr_path)
        else:
            sr = {}
            notes.append(
                f"no signal-recall eval for `{method}` — run "
                f"`tools/evaluate_signal_recall.py --split {split} --method {method}` "
                f"to populate this column"
            )
        rows.append({
            "context_method": method,
            "signal_recall": sr.get("macro_signal_recall"),
            "critical_signal_recall": sr.get("macro_critical_signal_recall"),
            "context_reduction": sr.get("macro_reduction_ratio"),
            "diagnosis_success": mb.get("diagnosis_success_rate"),
            "category_accuracy": mb.get("macro_category_accuracy"),
            "critical_mention": mb.get("macro_critical_signal_mention_recall"),
            "must_mention": mb.get("macro_must_mention_coverage"),
            "forbidden": mb.get("macro_forbidden_claim_violations"),
            "confident_error": mb.get("confident_error_rate"),
            "abstention": mb.get("abstention_rate"),
            "context_tokens": mb.get("macro_context_tokens"),
            "score_v1": mb.get("diagnosis_score_v1"),
        })
    return rows, notes


def write_m6_report(
    *, split: str, diagnoser_name: str,
    config: dict, config_sha: str,
    prompt_path: Path, prompt_sha: str,
    methods_requested: list[str], methods_run: list[str],
    case_count: int,
    manifest_path: Path,
    results_dir: Path, reports_dir: Path,
) -> Path:
    rows, notes = build_signal_vs_diagnosis(
        split=split, results_dir=results_dir, diagnoser_name=diagnoser_name,
    )
    diag_eval = load_json(results_dir / split
                           / f"eval_diagnosis_{diagnoser_name}.json")
    model = config.get("model") or {}

    md: list[str] = []
    md.append(f"# CILogBench M6 experiment — `{diagnoser_name}` on `{split}`")
    md.append("")
    md.append("## Experiment summary")
    md.append("")
    md.append(f"- Split: **{split}**")
    md.append(f"- Cases: **{case_count}**")
    md.append(f"- Diagnoser: `{diagnoser_name}`")
    md.append(f"- Provider: `{config.get('provider', '?')}`")
    md.append(f"- Config: `{config.get('__config_path__', '?')}` "
              f"(SHA256 `{config_sha[:12]}…`)")
    md.append(f"- Prompt: `{prompt_path}` (SHA256 `{prompt_sha[:12]}…`)")
    md.append(f"- Methods requested: {', '.join(f'`{m}`' for m in methods_requested)}")
    md.append(f"- Methods run: {', '.join(f'`{m}`' for m in methods_run)}")
    md.append(f"- Manifest: `{manifest_path.relative_to(ROOT)}`")
    md.append("")
    md.append("## Diagnoser config summary")
    md.append("")
    md.append(f"- Provider name: `{model.get('provider_name','?')}`")
    md.append(f"- Model name: `{model.get('model_name','?')}`")
    md.append(f"- Model version: `{model.get('model_version','unknown')}`")
    md.append(f"- Temperature: `{model.get('temperature','?')}`, "
              f"top_p: `{model.get('top_p','?')}`, "
              f"max_output_tokens: `{model.get('max_output_tokens','?')}`, "
              f"json_mode: `{model.get('json_mode','?')}`, "
              f"deterministic: `{model.get('deterministic','?')}`")
    cp = config.get("context_policy") or {}
    md.append(f"- allow_raw_context: `{cp.get('allow_raw_context')}`, "
              f"max_context_tokens: `{cp.get('max_context_tokens')}`, "
              f"on_context_too_large: `{cp.get('on_context_too_large')}`, "
              f"allow_truncation: `{cp.get('allow_truncation')}`")
    md.append("")
    md.append("## Privacy audit summary")
    md.append("")
    audit_path = results_dir / split / "privacy_audit.json"
    if audit_path.exists():
        audit = load_json(audit_path)
        md.append(f"- Total pattern hits: **{audit.get('total_hits', '?')}**")
        md.append(f"- Methods scanned: **{len(audit.get('methods', []))}**")
        md.append(f"- Disclaimer: {audit.get('disclaimer','')}")
    else:
        md.append("- Privacy audit not available (expected at "
                  "`results/<split>/privacy_audit.json`).")
    md.append("")
    md.append("## Diagnosis metric table (M5)")
    md.append("")
    md.append(
        "| Context Method | Success | Category Acc | Critical Mention "
        "| Must Mention | Forbidden | Conf Err | Abstention "
        "| Context Tok | score_v1 (exp) |"
    )
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        md.append(
            f"| {r['context_method']} "
            f"| {pct(r['diagnosis_success'])} "
            f"| {pct(r['category_accuracy'])} "
            f"| {pct(r['critical_mention'])} "
            f"| {pct(r['must_mention'])} "
            f"| {pct(r['forbidden'])} "
            f"| {pct(r['confident_error'])} "
            f"| {pct(r['abstention'])} "
            f"| {humanize_tokens(r['context_tokens'])} "
            f"| {num(r['score_v1'], 3)} |"
        )
    md.append("")
    md.append("## Signal-vs-diagnosis comparison")
    md.append("")
    md.append(
        "Joins the M2–M4 signal-recall evaluator with this run's "
        "diagnosis evaluator. Use it to check whether higher upstream "
        "signal preservation correlates with higher downstream diagnosis "
        "accuracy for this specific diagnoser and prompt."
    )
    md.append("")
    md.append(
        "| Context Method | Signal Recall | Critical Signal Recall | "
        "Context Reduction | Diagnosis Category Acc | Critical Mention "
        "| Conf Err | Context Tok |"
    )
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        md.append(
            f"| {r['context_method']} "
            f"| {pct(r['signal_recall'])} "
            f"| {pct(r['critical_signal_recall'])} "
            f"| {pct(r['context_reduction'])} "
            f"| {pct(r['category_accuracy'])} "
            f"| {pct(r['critical_mention'])} "
            f"| {pct(r['confident_error'])} "
            f"| {humanize_tokens(r['context_tokens'])} |"
        )
    md.append("")
    if notes:
        md.append("> Notes:")
        for n in notes:
            md.append(f"> - {n}")
        md.append("")

    md.append("## Confident-error analysis")
    md.append("")
    md.append(
        "Confident errors (`confidence ≥ 0.70` AND (wrong category OR "
        "forbidden claim present)) are the key agent-safety failure "
        "mode: the diagnoser sounds sure while being wrong. Rates below "
        "are per context method."
    )
    md.append("")
    any_ce = False
    for mb in diag_eval["methods"]:
        ce_cases = [c for c in mb["cases"] if c.get("confident_error")]
        if not ce_cases:
            continue
        any_ce = True
        md.append(f"### `{mb['context_method']}` — {len(ce_cases)} "
                  f"confident error(s)")
        md.append("")
        for c in ce_cases:
            md.append(f"- `{c['case_id']}` — pred "
                      f"`{c.get('root_cause_category')}` @ "
                      f"{c.get('confidence', 0):.2f}. "
                      f"Forbidden: {c.get('forbidden_claim_violations') or '—'}. "
                      f"Category accuracy: {c.get('category_accuracy')}.")
        md.append("")
    if not any_ce:
        md.append("No confident errors recorded on this run.")
        md.append("")
    md.append("## Abstention analysis")
    md.append("")
    md.append(
        "Abstention (`root_cause_category == \"unknown\"` OR "
        "`confidence < 0.25`) is not automatically bad. It is preferable "
        "to a confident wrong answer when the context is poor."
    )
    md.append("")
    any_ab = False
    for mb in diag_eval["methods"]:
        ab_cases = [c for c in mb["cases"] if c.get("abstained")]
        if not ab_cases:
            continue
        any_ab = True
        md.append(f"- `{mb['context_method']}` — "
                  f"{len(ab_cases)}/{len(mb['cases'])} abstained: "
                  + ", ".join(f"`{c['case_id']}`" for c in ab_cases))
    if not any_ab:
        md.append("- No abstentions across any method.")
    md.append("")

    md.append("## Interpretation guardrails")
    md.append("")
    md.append(
        "- This is a **5-case dev split**. Numbers are not a public "
        "leaderboard and should not be generalized without a holdout "
        "split (planned for a later milestone)."
    )
    md.append(
        "- A single fixed model's behavior may not transfer to other "
        "models. Do not conclude \"method X beats method Y for LLM "
        "debugging in general\" — the supportable statement is about "
        "this diagnoser and this prompt only."
    )
    md.append(
        "- Deterministic text-matching metrics are a proxy. A high "
        "`critical_mention` value does not prove the diagnosis is "
        "actually useful; a low one does not prove it was wrong."
    )
    md.append(
        "- If `deterministic` is false in the config, the numbers in "
        "this report may drift between runs even with temperature 0."
    )
    md.append(
        "- Do not tune prompts, models, or methods after reading this "
        "report and present the new run as a comparison — it invalidates "
        "the experiment."
    )
    md.append("")

    out_path = reports_dir / f"{split}_m6_real_debugger_{diagnoser_name}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "M6 experiment wrapper. Runs validate → privacy audit → "
            "run_diagnosis (command provider) → evaluate_diagnosis → "
            "render_diagnosis_report + writes the M6 experiment manifest "
            "and report. Refuses to invoke the command provider unless "
            "the user explicitly opts in."
        )
    )
    ap.add_argument("--split", default="dev")
    ap.add_argument("--diagnoser-name", required=True)
    ap.add_argument("--config", type=Path, required=True,
                    help="Path to the diagnoser config JSON.")
    ap.add_argument("--context-method", default="all")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--allow-external-llm", action="store_true",
                    help="Explicit opt-in for calling a real external model. "
                         "Can also be enabled via CILOGBENCH_ALLOW_EXTERNAL_LLM=1.")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="Alias for caching on; kept for parity with the plan.")
    ap.add_argument("--strict", action="store_true",
                    help="Pass --strict to run_diagnosis (abort on first error).")
    ap.add_argument("--skip-audit", action="store_true",
                    help="Skip the privacy audit. Only use if a run was "
                         "already audited and contexts have not changed.")
    args = ap.parse_args(argv)

    config_path = args.config.resolve()
    config = load_config(config_path)
    config["__config_path__"] = str(config_path.relative_to(ROOT))
    config_sha = sha256_path(config_path)

    prompt_path = (ROOT / config["prompt_path"]).resolve()
    if not prompt_path.exists():
        print(f"ERROR: prompt not found at {prompt_path}", file=sys.stderr)
        return 1
    prompt_sha = sha256_path(prompt_path)

    if config.get("provider") == "command":
        if not check_external_llm_opt_in(config, args.allow_external_llm):
            print(
                "ERROR: This config targets an external model provider. "
                "Opt in by setting CILOGBENCH_ALLOW_EXTERNAL_LLM=1 OR "
                "passing --allow-external-llm. Refusing to proceed.",
                file=sys.stderr,
            )
            return 2

    started_at = dt.datetime.now(dt.timezone.utc).isoformat()

    # 1. validate
    run_step(
        [sys.executable, "tools/validate_cases.py",
         str(args.cases_dir / args.split)],
        label="validate_cases",
    )

    # 2. privacy audit
    if not args.skip_audit:
        run_step(
            [sys.executable, "tools/audit_context_privacy.py",
             "--split", args.split,
             "--context-method", args.context_method,
             "--results-dir", str(args.results_dir),
             "--reports-dir", str(args.reports_dir)],
            label="audit_context_privacy",
        )

    # 3. run_diagnosis with command provider
    diag_argv = [
        sys.executable, "tools/run_diagnosis.py",
        "--split", args.split,
        "--cases-dir", str(args.cases_dir),
        "--results-dir", str(args.results_dir),
        "--prompt", str(prompt_path),
        "--diagnoser-name", args.diagnoser_name,
        "--context-method", args.context_method,
    ]
    if config.get("provider") == "mock":
        diag_argv += ["--diagnoser", "mock"]
    else:
        diag_argv += ["--diagnoser", "command"]
        cmd = config.get("command_override")
        if not cmd:
            env_var = config.get("command_env_var") or "DIAGNOSIS_COMMAND"
            cmd = os.environ.get(env_var, "")
            if not cmd:
                print(
                    f"ERROR: command provider selected but "
                    f"{env_var} is not set and config has no "
                    f"command_override.", file=sys.stderr,
                )
                return 1
        diag_argv += ["--command", cmd]
    if args.no_cache:
        diag_argv.append("--no-cache")
    if args.strict:
        diag_argv.append("--strict")
    run_step(diag_argv, label="run_diagnosis")

    # 4. evaluate_diagnosis
    run_step(
        [sys.executable, "tools/evaluate_diagnosis.py",
         "--split", args.split,
         "--diagnoser", args.diagnoser_name,
         "--cases-dir", str(args.cases_dir),
         "--results-dir", str(args.results_dir)],
        label="evaluate_diagnosis",
    )

    # 5. render_diagnosis_report
    run_step(
        [sys.executable, "tools/render_diagnosis_report.py",
         "--split", args.split,
         "--diagnoser", args.diagnoser_name,
         "--results-dir", str(args.results_dir),
         "--reports-dir", str(args.reports_dir)],
        label="render_diagnosis_report",
    )

    # 6. experiment manifest + M6 report
    diag_root = args.results_dir / args.split / "diagnoses" / args.diagnoser_name
    methods_run = sorted(p.stem for p in diag_root.glob("*.jsonl"))
    case_count = 0
    if methods_run:
        rows = load_manifest_rows(diag_root / f"{methods_run[0]}.jsonl")
        case_count = len(rows)

    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    commit, dirty = git_commit()

    manifest = {
        "split": args.split,
        "diagnoser_name": args.diagnoser_name,
        "config_path": str(config_path.relative_to(ROOT)),
        "config_sha256": config_sha,
        "prompt_path": str(prompt_path.relative_to(ROOT)),
        "prompt_sha256": prompt_sha,
        "context_methods_requested": [args.context_method],
        "context_methods_run": methods_run,
        "case_count": case_count,
        "privacy_audit_path": str(
            (args.results_dir / args.split / "privacy_audit.json")
            .relative_to(ROOT)
        ) if not args.skip_audit else None,
        "diagnosis_output_dir": str(diag_root.relative_to(ROOT)),
        "eval_path": str(
            (args.results_dir / args.split
             / f"eval_diagnosis_{args.diagnoser_name}.json").relative_to(ROOT)
        ),
        "report_path": str(
            (args.reports_dir / f"{args.split}_diagnosis_eval_"
             f"{args.diagnoser_name}.md").relative_to(ROOT)
        ),
        "started_at": started_at,
        "finished_at": finished_at,
        "git_commit": commit,
        "working_tree_dirty": dirty,
        "opt_in_source": (
            "env" if os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM", "") == "1"
            else "cli" if args.allow_external_llm else "config"
        ),
    }

    manifest_path = (args.results_dir / args.split
                     / f"m6_real_debugger_{args.diagnoser_name}.manifest.json")
    write_manifest(manifest_path, manifest)

    m6_report_path = write_m6_report(
        split=args.split, diagnoser_name=args.diagnoser_name,
        config=config, config_sha=config_sha,
        prompt_path=Path(config["prompt_path"]), prompt_sha=prompt_sha,
        methods_requested=[args.context_method], methods_run=methods_run,
        case_count=case_count,
        manifest_path=manifest_path,
        results_dir=args.results_dir, reports_dir=args.reports_dir,
    )

    print(f"\nM6 manifest → {manifest_path.relative_to(ROOT)}")
    print(f"M6 report   → {m6_report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
