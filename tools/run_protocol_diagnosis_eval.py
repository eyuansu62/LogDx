"""
Run a real fixed debugger across every locked split in a frozen protocol,
evaluate + render per-split diagnosis reports, compare splits, and emit
an M10 experiment manifest + report.

This is a thin wrapper around M5/M6/M8/M9 tools. It adds:
    - protocol-lock validation (refuses to run if the lock is stale)
    - per-split privacy audit on context methods
    - external-LLM opt-in gate
    - consolidated M10 manifest with config/prompt hashes
    - 14-section M10 report

Usage:
    export DIAGNOSIS_COMMAND="/path/to/shim"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

    python tools/run_protocol_diagnosis_eval.py \\
        --protocol protocols/legacy/cilogbench-v1.1.lock.json \\
        --diagnoser-config configs/diagnosers/stub-debugger-v1.json \\
        --diagnoser-name stub-debugger-v1 \\
        --context-methods all \\
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


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def run_step(argv: list[str], *, label: str, allow_rc: set[int] | None = None) -> int:
    print(f"\n$ {' '.join(argv)}")
    res = subprocess.run(argv, cwd=ROOT)
    if res.returncode in (allow_rc or {0}):
        return 0
    return res.returncode


def check_opt_in(privacy: dict, cli_flag: bool) -> bool:
    if not privacy.get("requires_explicit_external_llm_opt_in", True):
        return True
    return os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM", "") == "1" or cli_flag


def load_manifest_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def discover_methods_for_split(split: str, results_dir: Path) -> list[str]:
    split_dir = results_dir / split
    if not split_dir.is_dir():
        return []
    out: list[str] = []
    for p in sorted(split_dir.glob("*.jsonl")):
        if p.stem.startswith("eval_") or ".debug." in p.name:
            continue
        out.append(p.stem)
    return out


def pct(x: float | None) -> str:
    return "N/A" if x is None else f"{x * 100:.1f}%"


def num(x: float | None, digits: int = 3) -> str:
    return "N/A" if x is None else f"{x:.{digits}f}"


def humanize_tokens(n: float | None) -> str:
    if n is None:
        return "N/A"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _is_unsupported_context_error(provider_error: str | None) -> bool:
    """Per Codex 2026-05-20 F2 [medium]: the shim's
    `_ContextTooLargeError` path used to set
    `metadata.provider_error = "unsupported_context_too_large"` exactly,
    but the Codex 2026-05-19 F2 fix made it a structured taxonomy
    string `unsupported_context_too_large: context (...) exceeds shim
    cap (...)`. This protocol report's exact-string comparison silently
    started returning zero for the unsupported-context counts. Use a
    prefix-aware predicate so both legacy bare-class rows and post-fix
    detailed-class rows are counted.
    """
    if not provider_error:
        return False
    s = str(provider_error)
    return (
        s == "unsupported_context_too_large"
        or s.startswith("unsupported_context_too_large:")
    )


def collect_per_split(split: str, diagnoser: str, results_dir: Path) -> dict | None:
    p = results_dir / split / f"eval_diagnosis_{diagnoser}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_m10_report(
    *,
    protocol_path: Path,
    protocol_lock: dict,
    diagnoser_name: str,
    diagnoser_config_path: Path,
    diagnoser_config: dict,
    diagnoser_config_sha: str,
    prompt_sha: str,
    results_dir: Path,
    reports_dir: Path,
    manifest_path: Path,
    methods_attempted: list[str],
    splits: list[str],
) -> Path:
    protocol_id = protocol_lock.get("protocol_id", "unknown")

    md: list[str] = []
    md.append(f"# CILogBench M10 — `{diagnoser_name}` on `{protocol_id}`")
    md.append("")

    # 1. Experiment summary
    md.append("## 1. Experiment summary")
    md.append("")
    md.append(f"- Protocol: **{protocol_id}**")
    md.append(f"- Splits: {', '.join(f'`{s}`' for s in splits)}")
    md.append(f"- Context methods attempted: {', '.join(f'`{m}`' for m in methods_attempted)}")
    md.append(f"- Diagnoser: `{diagnoser_name}`")
    md.append(f"- Provider: `{diagnoser_config.get('provider', '?')}`")
    md.append(f"- Manifest: `{manifest_path.relative_to(ROOT)}`")
    md.append("")

    # 2. Protocol lock summary
    md.append("## 2. Protocol lock summary")
    md.append("")
    md.append(f"- Lock path: `{protocol_path.relative_to(ROOT)}`")
    md.append(f"- Lock SHA256: `{sha256_path(protocol_path)}`")
    md.append(f"- Schemas hashed: **{len(protocol_lock.get('schemas') or {})}**")
    md.append(f"- Prompts hashed: **{len(protocol_lock.get('prompts') or {})}**")
    md.append(f"- Evaluators hashed: **{len(protocol_lock.get('evaluators') or {})}**")
    md.append(f"- Baselines in lock: **{len(protocol_lock.get('baselines') or {})}**")
    for s, info in (protocol_lock.get("splits") or {}).items():
        md.append(f"  - `{s}` — {info.get('case_count')} cases")
    md.append("")

    # 3. Diagnoser config summary
    md.append("## 3. Diagnoser config summary")
    md.append("")
    model = diagnoser_config.get("model") or {}
    md.append(f"- Config: `{diagnoser_config_path.relative_to(ROOT)}` (SHA `{diagnoser_config_sha[:12]}…`)")
    md.append(f"- Model: `{model.get('provider_name','?')} / {model.get('model_name','?')}` "
              f"version `{model.get('model_version','unknown')}`")
    md.append(f"- temperature=`{model.get('temperature')}`, "
              f"top_p=`{model.get('top_p')}`, "
              f"max_output_tokens=`{model.get('max_output_tokens')}`, "
              f"json_mode=`{model.get('json_mode')}`, "
              f"deterministic=`{model.get('deterministic')}`, "
              f"tool_use=`{model.get('tool_use', False)}`, "
              f"web_access=`{model.get('web_access', False)}`")
    cp = diagnoser_config.get("context_policy") or {}
    md.append(f"- allow_raw_context=`{cp.get('allow_raw_context')}`, "
              f"allow_truncation=`{cp.get('allow_truncation')}`, "
              f"on_context_too_large=`{cp.get('on_context_too_large')}`, "
              f"max_context_tokens=`{cp.get('max_context_tokens')}`")
    md.append("")

    # 4. Model card link
    md.append("## 4. Model card")
    md.append("")
    md.append(f"See `docs/model_cards/{diagnoser_name}.md` for model identity, "
              f"decoding, determinism, and privacy notes.")
    md.append("")

    # 5. Privacy audit summary (latest raw audit per split)
    md.append("## 5. Privacy audit summary")
    md.append("")
    total_hits = 0
    for s in splits:
        audit_p = results_dir / s / "privacy_audit.json"
        if audit_p.exists():
            audit = json.loads(audit_p.read_text(encoding="utf-8"))
            md.append(f"- `{s}`: {audit.get('total_hits', '?')} pattern hit(s) "
                      f"across {len(audit.get('methods', []))} method(s)")
            total_hits += int(audit.get("total_hits") or 0)
        else:
            md.append(f"- `{s}`: no audit file (expected at "
                      f"`results/{s}/privacy_audit.json`)")
    md.append("")
    md.append("_Audit is best-effort; see `docs/experiments/m6_real_fixed_debugger.md` for limits._")
    md.append("")

    # 6. Per-split diagnosis metric tables
    md.append("## 6. Per-split diagnosis metric tables")
    md.append("")
    for s in splits:
        ev = collect_per_split(s, diagnoser_name, results_dir)
        md.append(f"### {s}")
        md.append("")
        if ev is None:
            md.append("- No evaluation available for this split.")
            md.append("")
            continue
        md.append(
            "| Method | Success | Cat Acc | Crit Mention | Must Mention "
            "| File Recall | Test Recall | Valid Quote | Forbidden "
            "| Conf Err | Abstention | score_v1 | Ctx Tok | Out Tok |"
        )
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for b in ev["methods"]:
            md.append(
                f"| {b['context_method']} "
                f"| {pct(b['diagnosis_success_rate'])} "
                f"| {pct(b['macro_category_accuracy'])} "
                f"| {pct(b['macro_critical_signal_mention_recall'])} "
                f"| {pct(b['macro_must_mention_coverage'])} "
                f"| {pct(b['macro_relevant_file_recall'])} "
                f"| {pct(b['macro_relevant_test_recall'])} "
                f"| {pct(b['macro_valid_evidence_quote_rate'])} "
                f"| {pct(b['macro_forbidden_claim_violations'])} "
                f"| {pct(b['confident_error_rate'])} "
                f"| {pct(b['abstention_rate'])} "
                f"| {num(b['diagnosis_score_v1'], 3)} "
                f"| {humanize_tokens(b['macro_context_tokens'])} "
                f"| {humanize_tokens(b['macro_diagnosis_tokens'])} |"
            )
        md.append("")

    # 7. Signal-vs-diagnosis comparison (per split)
    md.append("## 7. Signal-vs-diagnosis comparison")
    md.append("")
    md.append("Join of M2/M3/M4 signal-recall and this M10 run's diagnosis metrics.")
    md.append("")
    for s in splits:
        ev = collect_per_split(s, diagnoser_name, results_dir)
        if ev is None:
            continue
        md.append(f"### {s}")
        md.append("")
        md.append(
            "| Method | Signal Recall | Critical Signal Recall "
            "| Evidence Coverage | Cat Acc | Crit Mention | Conf Err | Ctx Tok | Reduction |"
        )
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for b in ev["methods"]:
            method = b["context_method"]
            sig_p = results_dir / s / f"eval_{method}.json"
            sr = json.loads(sig_p.read_text(encoding="utf-8")) if sig_p.exists() else {}
            md.append(
                f"| {method} "
                f"| {pct(sr.get('macro_signal_recall'))} "
                f"| {pct(sr.get('macro_critical_signal_recall'))} "
                f"| {pct(sr.get('macro_evidence_span_coverage'))} "
                f"| {pct(b['macro_category_accuracy'])} "
                f"| {pct(b['macro_critical_signal_mention_recall'])} "
                f"| {pct(b['confident_error_rate'])} "
                f"| {humanize_tokens(b['macro_context_tokens'])} "
                f"| {pct(sr.get('macro_reduction_ratio'))} |"
            )
        md.append("")

    # 8. Cost + token table
    md.append("## 8. Cost and token table (per split)")
    md.append("")
    md.append("_Average per case. Non-LLM methods have 0 summarization tokens._")
    md.append("")
    for s in splits:
        ev = collect_per_split(s, diagnoser_name, results_dir)
        if ev is None:
            continue
        md.append(f"### {s}")
        md.append("")
        md.append(
            "| Method | Ctx Tok | Diag Output Tok | Summary Proc Tok "
            "| Total Pipeline | External Calls | Unsupported Cases |"
        )
        md.append("|---|---:|---:|---:|---:|---:|---:|")
        for b in ev["methods"]:
            method = b["context_method"]
            manifest_p = results_dir / s / f"{method}.jsonl"
            rows = load_manifest_rows(manifest_p)
            proc = sum(int((r.get("metadata", {}).get("usage") or {}).get("input_tokens", 0)
                            + (r.get("metadata", {}).get("usage") or {}).get("output_tokens", 0))
                        for r in rows)
            chunk = sum(int((r.get("metadata") or {}).get("chunk_count", 0) or 0) for r in rows)
            if chunk:
                chunk += sum(1 for r in rows)  # +1 reduce call per case
            n = max(1, len(rows))
            ctx_tok = int(b.get("macro_context_tokens") or 0)
            diag_tok = int(b.get("macro_diagnosis_tokens") or 0)
            total = ctx_tok + diag_tok + proc // n
            unsupp = sum(1 for r in rows_for_method(results_dir, s, diagnoser_name, method)
                          if _is_unsupported_context_error(
                              (r.get("metadata") or {}).get("provider_error")
                          ))
            md.append(
                f"| {method} "
                f"| {humanize_tokens(ctx_tok)} "
                f"| {humanize_tokens(diag_tok)} "
                f"| {humanize_tokens(proc // n)} "
                f"| {humanize_tokens(total)} "
                f"| {chunk if chunk else '—'} "
                f"| {unsupp if unsupp else '—'} |"
            )
        md.append("")

    # 9 + 10 + 11. Confident-error / abstention / unsupported-context analysis
    for section, label, key in [
        (9,  "Confident-error analysis",    "confident_error"),
        (10, "Abstention analysis",         "abstained"),
        (11, "Unsupported-context analysis", None),
    ]:
        md.append(f"## {section}. {label}")
        md.append("")
        any_case = False
        for s in splits:
            ev = collect_per_split(s, diagnoser_name, results_dir)
            if ev is None:
                continue
            for b in ev["methods"]:
                hits: list[dict] = []
                if key is None:
                    rows = rows_for_method(results_dir, s, diagnoser_name, b["context_method"])
                    hits = [r for r in rows
                            if _is_unsupported_context_error(
                                (r.get("metadata") or {}).get("provider_error")
                            )]
                else:
                    hits = [c for c in b["cases"] if c.get(key)]
                if not hits:
                    continue
                any_case = True
                md.append(f"- `{s}` / `{b['context_method']}`: "
                          f"{len(hits)} case(s)")
                for h in hits[:5]:
                    cid = h.get("case_id", "?")
                    cat = h.get("root_cause_category", "?")
                    conf = h.get("confidence", 0.0)
                    md.append(f"  - `{cid}` — pred `{cat}` @ {conf:.2f}")
        if not any_case:
            md.append("- None recorded.")
        md.append("")

    # 12. Per-case hard failures — cases with low category + low mention across all methods
    md.append("## 12. Per-case hard failures (low across every method)")
    md.append("")
    hard_cases: list[tuple[str, str]] = []
    for s in splits:
        ev = collect_per_split(s, diagnoser_name, results_dir)
        if ev is None:
            continue
        case_to_methods: dict[str, list[dict]] = {}
        for b in ev["methods"]:
            for c in b["cases"]:
                case_to_methods.setdefault(c["case_id"], []).append(c)
        for cid, rows in case_to_methods.items():
            cat_accs = [c.get("category_accuracy") for c in rows
                         if c.get("category_accuracy") is not None]
            crit = [c.get("critical_signal_mention_recall") for c in rows
                     if c.get("critical_signal_mention_recall") is not None]
            if cat_accs and max(cat_accs) == 0.0 and crit and max(crit) < 0.30:
                hard_cases.append((s, cid))
    if hard_cases:
        for s, cid in hard_cases:
            md.append(f"- `{s}` / `{cid}` — every method's diagnosis missed the "
                      f"category AND had <30% critical-signal mention.")
    else:
        md.append("- No case is hard for every method simultaneously.")
    md.append("")

    # 13. Split gap analysis
    md.append("## 13. Split gap analysis")
    md.append("")
    slug = protocol_id.replace("-", "_").replace(".", "_")
    cmp_report = reports_dir / f"{'_'.join(splits)}_comparison_{slug}.md"
    if cmp_report.exists():
        md.append(f"See [`{cmp_report.relative_to(ROOT)}`](../{cmp_report.relative_to(ROOT)}) "
                  "for the cross-split gap table generated by "
                  "`tools/compare_splits.py`.")
    else:
        md.append(f"- `{cmp_report.relative_to(ROOT)}` not found; run "
                  f"`tools/compare_splits.py --protocol "
                  f"{protocol_path.relative_to(ROOT)} --splits {','.join(splits)} "
                  f"--diagnoser {diagnoser_name}` to populate it.")
    md.append("")

    # 14. Interpretation guardrails
    md.append("## 14. Interpretation guardrails")
    md.append("")
    md.append(
        f"- This run uses only the cases locked in "
        f"`{protocol_path.relative_to(ROOT)}`. Case counts are small "
        f"(≤ 16 under v1.1). A single case flipping can move macro "
        f"metrics by 6–25 pp."
    )
    md.append(
        "- M10 supports statements about **this diagnoser + this "
        "prompt** under the frozen protocol. It does not support "
        "cross-model or cross-prompt claims."
    )
    md.append(
        "- Deterministic diagnosis metrics are a proxy. Paraphrases "
        "can fail literal signal matching without being wrong; M11 "
        "calibrates against human review."
    )
    md.append(
        "- If `metadata.deterministic=false` in the config, rerun "
        "numbers may drift even with temperature=0. The cache stores "
        "the first run byte-exactly, so reruns hit cache unless "
        "`--no-cache` is passed."
    )
    md.append("")

    out_path = reports_dir / f"{protocol_id}_real_debugger_{diagnoser_name}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return out_path


def rows_for_method(results_dir: Path, split: str, diagnoser: str, method: str) -> list[dict]:
    p = results_dir / split / "diagnoses" / diagnoser / f"{method}.jsonl"
    return load_manifest_rows(p)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run a real fixed debugger over a frozen protocol."
    )
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--diagnoser-config", type=Path, required=True)
    ap.add_argument("--diagnoser-name", default=None)
    ap.add_argument("--context-methods", default="all")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--allow-external-llm", action="store_true")
    ap.add_argument("--allow-privacy-audit-hits", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--skip-audit", action="store_true")
    args = ap.parse_args(argv)

    protocol_path = args.protocol if args.protocol.is_absolute() else (ROOT / args.protocol)
    d_config_path = args.diagnoser_config.resolve()

    # 1. Validate protocol lock first.
    rc = run_step(
        [sys.executable, "tools/validate_protocol_lock.py",
         "--protocol", str(protocol_path)],
        label="validate_protocol_lock",
    )
    if rc != 0:
        print("ERROR: protocol lock is drifted; refusing to run.", file=sys.stderr)
        return rc

    lock = load_json(protocol_path)
    splits = sorted((lock.get("splits") or {}).keys())

    d_config = load_json(d_config_path)
    d_config_sha = sha256_path(d_config_path)
    diagnoser_name = args.diagnoser_name or d_config.get("diagnoser_name")
    prompt_path = (ROOT / d_config["prompt_path"]).resolve()
    prompt_sha = sha256_path(prompt_path)

    # 2. Opt-in gate for command provider.
    if d_config.get("provider") == "command":
        if not check_opt_in(d_config.get("privacy") or {}, args.allow_external_llm):
            print("ERROR: diagnoser targets external LLM; set "
                  "CILOGBENCH_ALLOW_EXTERNAL_LLM=1 or --allow-external-llm.",
                  file=sys.stderr)
            return 2

    started_at = dt.datetime.now(dt.timezone.utc).isoformat()

    # 3. Validate cases for every split.
    for s in splits:
        rc = run_step(
            [sys.executable, "tools/validate_cases.py", str(args.cases_dir / s)],
            label=f"validate_cases {s}",
        )
        if rc != 0:
            return rc

    # 4. Privacy audit per split (over all context methods).
    if not args.skip_audit:
        for s in splits:
            rc = run_step(
                [sys.executable, "tools/audit_context_privacy.py",
                 "--split", s, "--context-method", "all",
                 "--results-dir", str(args.results_dir),
                 "--reports-dir", str(args.reports_dir)],
                label=f"audit_context_privacy {s}",
            )
            if rc != 0:
                return rc
            audit_p = args.results_dir / s / "privacy_audit.json"
            if audit_p.exists():
                hits = int(json.loads(audit_p.read_text(encoding="utf-8")).get("total_hits") or 0)
                if hits > 0 and not args.allow_privacy_audit_hits:
                    print(f"ERROR: privacy audit found {hits} hit(s) in {s}. "
                          f"Review reports/{s}_privacy_audit.md. Pass "
                          f"--allow-privacy-audit-hits to override.",
                          file=sys.stderr)
                    return 3

    # 5. Resolve context methods per split.
    if args.context_methods == "all":
        methods_by_split = {s: discover_methods_for_split(s, args.results_dir) for s in splits}
    else:
        fixed = [m.strip() for m in args.context_methods.split(",") if m.strip()]
        methods_by_split = {s: fixed for s in splits}

    all_methods = sorted({m for ms in methods_by_split.values() for m in ms})

    # 6. Run diagnosis per split × method.
    cmd = d_config.get("command_override")
    if not cmd:
        env_var = d_config.get("command_env_var") or "DIAGNOSIS_COMMAND"
        cmd = os.environ.get(env_var, "")
        if d_config.get("provider") == "command" and not cmd:
            print(f"ERROR: {env_var} is not set.", file=sys.stderr)
            return 1

    for s in splits:
        for method in methods_by_split[s]:
            diag_argv = [
                sys.executable, "tools/run_diagnosis.py",
                "--split", s,
                "--cases-dir", str(args.cases_dir),
                "--results-dir", str(args.results_dir),
                "--prompt", str(prompt_path),
                "--diagnoser-name", diagnoser_name,
                "--context-method", method,
            ]
            if d_config.get("provider") == "mock":
                diag_argv += ["--diagnoser", "mock"]
            else:
                diag_argv += ["--diagnoser", "command", "--command", cmd]
            if args.no_cache:
                diag_argv.append("--no-cache")
            if args.strict:
                diag_argv.append("--strict")
            # Per Codex 2026-05-14 F1: propagate the wrapper-level
            # opt-in so the runner's gate + shim defense-in-depth see
            # the explicit acknowledgement. Without this propagation
            # the child run_diagnosis.py would fail closed even though
            # the wrapper already accepted --allow-external-llm at its
            # own gate.
            if args.allow_external_llm:
                diag_argv.append("--allow-external-llm")
            # Per Codex 2026-05-15 F2: thread the exact validated
            # config path so the child doesn't re-discover by name
            # (which could resolve to a different file when the
            # wrapper's --diagnoser-config sits outside configs/diagnosers/
            # or when --diagnoser-name is overridden). run_diagnosis.py
            # fails fast if config.diagnoser_name disagrees.
            diag_argv += ["--diagnoser-config", str(d_config_path)]
            rc = run_step(diag_argv, label=f"run_diagnosis {s}/{method}")
            if rc != 0:
                return rc

    # 7. Evaluate + render per split.
    for s in splits:
        rc = run_step(
            [sys.executable, "tools/evaluate_diagnosis.py",
             "--split", s, "--diagnoser", diagnoser_name,
             "--cases-dir", str(args.cases_dir),
             "--results-dir", str(args.results_dir)],
            label=f"evaluate_diagnosis {s}",
        )
        if rc != 0:
            return rc
        rc = run_step(
            [sys.executable, "tools/render_diagnosis_report.py",
             "--split", s, "--diagnoser", diagnoser_name,
             "--results-dir", str(args.results_dir),
             "--reports-dir", str(args.reports_dir)],
            label=f"render_diagnosis_report {s}",
        )
        if rc != 0:
            return rc

    # 8. Cross-split comparison report.
    rc = run_step(
        [sys.executable, "tools/compare_splits.py",
         "--protocol", str(protocol_path),
         "--splits", ",".join(splits),
         "--diagnoser", diagnoser_name,
         "--results-dir", str(args.results_dir),
         "--reports-dir", str(args.reports_dir)],
        label="compare_splits",
    )
    if rc != 0:
        return rc

    # 9. Manifest.
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    commit, dirty = git_commit()
    manifest = {
        "protocol_id": lock.get("protocol_id"),
        "protocol_lock_path": str(protocol_path.relative_to(ROOT)),
        "protocol_lock_sha256": sha256_path(protocol_path),
        "diagnoser_name": diagnoser_name,
        "diagnoser_config_path": str(d_config_path.relative_to(ROOT)),
        "diagnoser_config_sha256": d_config_sha,
        "debugger_prompt_path": d_config["prompt_path"],
        "debugger_prompt_sha256": prompt_sha,
        "splits": splits,
        "context_methods": all_methods,
        "case_count_by_split": {s: lock["splits"][s]["case_count"] for s in splits},
        "diagnosis_output_dirs": {
            s: str((args.results_dir / s / "diagnoses" / diagnoser_name).relative_to(ROOT))
            for s in splits
        },
        "eval_paths": {
            s: str((args.results_dir / s / f"eval_diagnosis_{diagnoser_name}.json").relative_to(ROOT))
            for s in splits
        },
        "started_at": started_at,
        "finished_at": finished_at,
        "git_commit": commit,
        "working_tree_dirty": dirty,
        "opt_in_source": (
            "env" if os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM", "") == "1"
            else "cli" if args.allow_external_llm else "config"
        ),
    }
    manifest_path = args.results_dir / f"{lock.get('protocol_id','unknown')}_real_debugger_{diagnoser_name}.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    # 10. M10 report.
    report_path = write_m10_report(
        protocol_path=protocol_path, protocol_lock=lock,
        diagnoser_name=diagnoser_name,
        diagnoser_config_path=d_config_path, diagnoser_config=d_config,
        diagnoser_config_sha=d_config_sha, prompt_sha=prompt_sha,
        results_dir=args.results_dir, reports_dir=args.reports_dir,
        manifest_path=manifest_path,
        methods_attempted=all_methods,
        splits=splits,
    )
    manifest["report_path"] = str(report_path.relative_to(ROOT))
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    print(f"\nM10 manifest → {manifest_path.relative_to(ROOT)}")
    print(f"M10 report   → {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
