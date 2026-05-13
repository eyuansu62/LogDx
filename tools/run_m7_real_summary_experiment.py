"""
M7 experiment wrapper: run a real LLM summarizer as a new context
method, evaluate its signal recall, run the fixed diagnoser over the
new method, evaluate the diagnosis, and write an M7 experiment manifest
+ report.

This is a thin wrapper around M4's summary runner, M2's signal-recall
evaluator, and M5/M6's diagnosis runner/evaluator. The wrapper adds:

    - method-name guard: must match `llm-summary-v1-<slug>`, and must
      NOT equal `llm-summary-v1-mock` (reserved).
    - external-LLM opt-in gate (same posture as M6).
    - raw-log privacy audit that runs before any external call.
    - full cost accounting (summary processing tokens + final-context
      tokens + diagnosis output tokens).
    - reproducibility manifest + cross-method experiment report.

Usage:
    export LLM_SUMMARY_COMMAND="/path/to/summary_shim"
    export DIAGNOSIS_COMMAND="/path/to/diagnosis_shim"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

    python tools/run_m7_real_summary_experiment.py \\
        --split dev \\
        --summarizer-config configs/summarizers/example.llm-summary-v1-command.json \\
        --diagnoser-config configs/diagnosers/example.debugger-v1-command.json \\
        --diagnoser-name my-debugger-v1 \\
        --allow-external-llm
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

METHOD_NAME_RE = re.compile(r"^llm-summary-v1-(?!mock$)[a-z0-9][a-z0-9-]*$")


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def run_step(argv: list[str], *, label: str) -> None:
    print(f"\n$ {' '.join(argv)}")
    res = subprocess.run(argv, cwd=ROOT)
    if res.returncode != 0:
        raise SystemExit(f"step '{label}' failed with exit {res.returncode}")


def check_external_llm_opt_in(config_privacy: dict, cli_flag: bool) -> bool:
    if not config_privacy.get("requires_explicit_external_llm_opt_in", True):
        return True
    return (
        os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM", "") == "1"
        or cli_flag
    )


def convert_chunking(chunking: dict) -> tuple[int, int]:
    """Honor direct chunk_lines when present; otherwise convert
    chunk_tokens using a ~16 tokens/line approximation."""
    if "chunk_lines" in chunking:
        return (
            int(chunking["chunk_lines"]),
            int(chunking.get("chunk_overlap_lines", 0)),
        )
    tok = int(chunking.get("chunk_tokens", 6000))
    overlap_tok = int(chunking.get("chunk_overlap_tokens", 300))
    return max(1, tok // 16), max(0, overlap_tok // 16)


def humanize_tokens(n: float | None) -> str:
    if n is None:
        return "N/A"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def pct(x: float | None) -> str:
    return "N/A" if x is None else f"{x * 100:.1f}%"


def num(x: float | None, digits: int = 3) -> str:
    return "N/A" if x is None else f"{x:.{digits}f}"


def load_manifest_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def audit_had_hits(audit_path: Path) -> int:
    if not audit_path.exists():
        return 0
    return int(load_json(audit_path).get("total_hits", 0) or 0)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def method_row(method: str, split: str, results_dir: Path) -> dict:
    """Pull together signal-recall + manifest token stats for one context
    method. Missing pieces are returned as None."""
    sr_path = results_dir / split / f"eval_{method}.json"
    sr = load_json(sr_path) if sr_path.exists() else {}
    manifest = load_manifest_rows(results_dir / split / f"{method}.jsonl")
    proc_tokens = 0
    final_tokens = 0
    ext_calls = 0
    for r in manifest:
        meta = r.get("metadata") or {}
        usage = meta.get("usage") or {}
        proc_tokens += int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        ft = int(meta.get("final_context_tokens_estimate", 0))
        if ft == 0:
            ft = max(1, r.get("output_byte_size", 0) // 4)
        final_tokens += ft
        ext_calls += int(meta.get("chunk_count", 0) or 0)
        if meta.get("chunk_count"):
            ext_calls += 1  # reduce call
    n = max(1, len(manifest))
    return {
        "method": method,
        "signal_recall": sr.get("macro_signal_recall"),
        "critical_signal_recall": sr.get("macro_critical_signal_recall"),
        "evidence_coverage": sr.get("macro_evidence_span_coverage"),
        "reduction": sr.get("macro_reduction_ratio"),
        "mapping": "line" if all(
            r.get("line_mapping_available", True) for r in manifest
        ) else "text",
        "summary_processing_tokens_avg": proc_tokens // n if manifest else 0,
        "final_context_tokens_avg": final_tokens // n if manifest else 0,
        "external_calls_estimate": ext_calls,
        "cases": len(manifest),
    }


def diagnosis_block_for(method: str, diag_eval: dict) -> dict | None:
    for mb in diag_eval.get("methods", []):
        if mb["context_method"] == method:
            return mb
    return None


def write_m7_report(
    *,
    split: str,
    summarizer_config: dict,
    summarizer_config_path: Path,
    summarizer_config_sha: str,
    map_prompt_sha: str,
    reduce_prompt_sha: str,
    method_name: str,
    diagnoser_config: dict | None,
    diagnoser_config_path: Path | None,
    diagnoser_config_sha: str | None,
    debugger_prompt_sha: str | None,
    diagnoser_name: str | None,
    compared_methods: list[str],
    results_dir: Path,
    reports_dir: Path,
    manifest_path: Path,
) -> Path:
    rows = [method_row(m, split, results_dir) for m in compared_methods]
    diag_eval_path = (
        results_dir / split / f"eval_diagnosis_{diagnoser_name}.json"
    ) if diagnoser_name else None
    diag_eval = (
        load_json(diag_eval_path)
        if diag_eval_path and diag_eval_path.exists() else None
    )
    audit_path = results_dir / split / "privacy_audit.json"
    audit = load_json(audit_path) if audit_path.exists() else None

    md: list[str] = []
    md.append(f"# CILogBench M7 experiment — `{method_name}` on `{split}`")
    md.append("")
    md.append("## Experiment summary")
    md.append("")
    md.append(f"- Summary method: `{method_name}`")
    md.append(f"- Summarizer: `{summarizer_config['summarizer_name']}`")
    if diagnoser_name:
        md.append(f"- Diagnoser: `{diagnoser_name}`")
    md.append(f"- Split: **{split}**")
    md.append(f"- Compared context methods: "
              + ", ".join(f"`{m}`" for m in compared_methods))
    md.append(f"- Manifest: `{manifest_path.relative_to(ROOT)}`")
    md.append("")

    md.append("## Summarizer config summary")
    md.append("")
    s_model = summarizer_config.get("model") or {}
    md.append(f"- Config: `{summarizer_config_path.relative_to(ROOT)}` "
              f"(SHA256 `{summarizer_config_sha[:12]}…`)")
    md.append(f"- Provider name: `{s_model.get('provider_name', '?')}`")
    md.append(f"- Model name: `{s_model.get('model_name', '?')}` "
              f"(version `{s_model.get('model_version', 'unknown')}`)")
    md.append(f"- temperature=`{s_model.get('temperature')}`, "
              f"top_p=`{s_model.get('top_p')}`, "
              f"max_output_tokens=`{s_model.get('max_output_tokens')}`, "
              f"json_mode=`{s_model.get('json_mode')}`, "
              f"deterministic=`{s_model.get('deterministic')}`")
    md.append("")

    if diagnoser_config is not None:
        md.append("## Diagnoser config summary")
        md.append("")
        d_model = diagnoser_config.get("model") or {}
        md.append(f"- Config: `{diagnoser_config_path.relative_to(ROOT)}` "
                  f"(SHA256 `{diagnoser_config_sha[:12]}…`)")
        md.append(f"- Provider name: `{d_model.get('provider_name', '?')}`")
        md.append(f"- Model name: `{d_model.get('model_name', '?')}` "
                  f"(version `{d_model.get('model_version', 'unknown')}`)")
        md.append(f"- temperature=`{d_model.get('temperature')}`, "
                  f"max_output_tokens=`{d_model.get('max_output_tokens')}`, "
                  f"json_mode=`{d_model.get('json_mode')}`, "
                  f"deterministic=`{d_model.get('deterministic')}`")
        md.append("")

    md.append("## Prompt hashes")
    md.append("")
    md.append(f"- map_prompt_sha256: `{map_prompt_sha}`")
    md.append(f"- reduce_prompt_sha256: `{reduce_prompt_sha}`")
    if debugger_prompt_sha:
        md.append(f"- debugger_prompt_sha256: `{debugger_prompt_sha}`")
    md.append("")

    md.append("## Privacy audit summary")
    md.append("")
    if audit is not None:
        md.append(f"- Total pattern hits: **{audit.get('total_hits', '?')}**")
        md.append(f"- Methods scanned: **{len(audit.get('methods', []))}**")
        md.append(f"- Disclaimer: {audit.get('disclaimer', '')}")
    else:
        md.append("- Privacy audit not present (expected at "
                  "`results/<split>/privacy_audit.json`).")
    md.append("")

    md.append("## Signal recall table")
    md.append("")
    md.append(
        "| Context Method | Signal Recall | Critical Recall "
        "| Evidence Coverage | Reduction | Mapping "
        "| Processing Tokens | Final Context Tokens |"
    )
    md.append("|---|---:|---:|---:|---:|---|---:|---:|")
    for r in rows:
        md.append(
            f"| {r['method']} "
            f"| {pct(r['signal_recall'])} "
            f"| {pct(r['critical_signal_recall'])} "
            f"| {pct(r['evidence_coverage'])} "
            f"| {pct(r['reduction'])} "
            f"| {r['mapping']} "
            f"| {humanize_tokens(r['summary_processing_tokens_avg'])} "
            f"| {humanize_tokens(r['final_context_tokens_avg'])} |"
        )
    md.append("")
    md.append(
        "_Processing Tokens_ averages summarization cost (map+reduce "
        "input+output) per case. 0 for non-summary baselines. "
        "_Final Context Tokens_ estimates the text handed to the downstream "
        "reader (= byte_size/4)."
    )
    md.append("")

    if diag_eval is not None:
        md.append("## Diagnosis metric table")
        md.append("")
        md.append(
            "| Context Method | Success | Category Acc | Critical Mention "
            "| Must Mention | File Recall | Test Recall | Forbidden "
            "| Conf Err | Abstention | Context Tok | score_v1 (exp) |"
        )
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            b = diagnosis_block_for(r["method"], diag_eval)
            if b is None:
                continue
            md.append(
                f"| {r['method']} "
                f"| {pct(b['diagnosis_success_rate'])} "
                f"| {pct(b['macro_category_accuracy'])} "
                f"| {pct(b['macro_critical_signal_mention_recall'])} "
                f"| {pct(b['macro_must_mention_coverage'])} "
                f"| {pct(b['macro_relevant_file_recall'])} "
                f"| {pct(b['macro_relevant_test_recall'])} "
                f"| {pct(b['macro_forbidden_claim_violations'])} "
                f"| {pct(b['confident_error_rate'])} "
                f"| {pct(b['abstention_rate'])} "
                f"| {humanize_tokens(b['macro_context_tokens'])} "
                f"| {num(b['diagnosis_score_v1'], 3)} |"
            )
        md.append("")

    md.append("## Cost table")
    md.append("")
    md.append(
        "Per-case averages. _Total Pipeline_ = summary processing + final "
        "context (sent to diagnoser) + diagnosis output."
    )
    md.append("")
    md.append(
        "| Context Method | Summary Processing | Final Context "
        "| Diagnosis Output | Total Pipeline | Estimated External Calls |"
    )
    md.append("|---|---:|---:|---:|---:|---:|")
    raw_final = next(
        (r["final_context_tokens_avg"] for r in rows if r["method"] == "raw"),
        None,
    )
    for r in rows:
        b = diagnosis_block_for(r["method"], diag_eval) if diag_eval else None
        diag_out = int(b.get("macro_diagnosis_tokens") or 0) if b else 0
        total = r["summary_processing_tokens_avg"] + r["final_context_tokens_avg"] + diag_out
        ext = (r["external_calls_estimate"]
               if r["method"].startswith("llm-summary-v1-") else 0)
        md.append(
            f"| {r['method']} "
            f"| {humanize_tokens(r['summary_processing_tokens_avg'])} "
            f"| {humanize_tokens(r['final_context_tokens_avg'])} "
            f"| {humanize_tokens(diag_out)} "
            f"| {humanize_tokens(total)} "
            f"| {ext if ext else '—'} |"
        )
    md.append("")

    md.append("## Signal-vs-diagnosis comparison")
    md.append("")
    md.append(
        "Joins the signal recall table above with the diagnosis table for "
        "this experiment. Rows with missing signal recall or missing "
        "diagnosis show N/A in the corresponding column."
    )
    md.append("")
    md.append(
        "| Context Method | Signal Recall | Critical Signal Recall "
        "| Reduction | Diagnosis Category Acc | Critical Mention "
        "| Conf Err | Context Tok |"
    )
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        b = diagnosis_block_for(r["method"], diag_eval) if diag_eval else None
        cat = pct(b.get("macro_category_accuracy")) if b else "N/A"
        crit_m = pct(b.get("macro_critical_signal_mention_recall")) if b else "N/A"
        conf_err = pct(b.get("confident_error_rate")) if b else "N/A"
        ctx_tok = humanize_tokens(b.get("macro_context_tokens")) if b else humanize_tokens(r["final_context_tokens_avg"])
        md.append(
            f"| {r['method']} "
            f"| {pct(r['signal_recall'])} "
            f"| {pct(r['critical_signal_recall'])} "
            f"| {pct(r['reduction'])} "
            f"| {cat} "
            f"| {crit_m} "
            f"| {conf_err} "
            f"| {ctx_tok} |"
        )
    md.append("")

    md.append("## Per-case summary audit")
    md.append("")
    summary_manifest = load_manifest_rows(
        results_dir / split / f"{method_name}.jsonl"
    )
    sig_eval = load_json(results_dir / split / f"eval_{method_name}.json") \
        if (results_dir / split / f"eval_{method_name}.json").exists() else {}
    diag_block = (
        diagnosis_block_for(method_name, diag_eval) if diag_eval else None
    )
    md.append(
        "| Case | Ctx Tok | Proc Tok | Signal Recall | Critical Recall "
        "| Category Acc | Critical Mention | Conf Err | Abstained |"
    )
    md.append("|---|---:|---:|---:|---:|---:|---:|---|---|")
    for row in summary_manifest:
        cid = row["case_id"]
        meta = row.get("metadata") or {}
        usage = meta.get("usage") or {}
        proc = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        ctx = int(meta.get("final_context_tokens_estimate", 0))
        sr_case = next(
            (c for c in sig_eval.get("cases", []) if c["case_id"] == cid),
            None,
        )
        d_case = (
            next((c for c in diag_block["cases"] if c["case_id"] == cid), None)
            if diag_block else None
        )
        md.append(
            f"| `{cid}` "
            f"| {humanize_tokens(ctx)} "
            f"| {humanize_tokens(proc)} "
            f"| {pct(sr_case['signal_recall']) if sr_case else 'N/A'} "
            f"| {pct(sr_case['critical_signal_recall']) if sr_case else 'N/A'} "
            f"| {pct(d_case['category_accuracy']) if d_case else 'N/A'} "
            f"| {pct(d_case['critical_signal_mention_recall']) if d_case else 'N/A'} "
            f"| {'YES' if d_case and d_case.get('confident_error') else '—'} "
            f"| {'YES' if d_case and d_case.get('abstained') else '—'} |"
        )
    md.append("")

    md.append("## Summary failure modes (qualitative)")
    md.append("")
    md.append(
        "Inspect `results/<split>/<method_name>/chunks/<case>/` for per-chunk "
        "map outputs and the final reduce output to judge whether the "
        "summarizer paraphrases away evidence, collapses multiple failures, "
        "or invents facts. Classic patterns to watch for:"
    )
    md.append("")
    md.append("- omitting file names or test identifiers that do appear in "
              "the raw log;")
    md.append("- paraphrasing exact error strings so literal signal recall "
              "drops without a real loss of meaning;")
    md.append("- collapsing multiple distinct failures into one;")
    md.append("- overfocusing on the last failure (common with tail-biased "
              "prompts);")
    md.append("- overfocusing on GitHub Actions runner/setup noise;")
    md.append("- inventing a root cause the log does not support;")
    md.append("- quoting lines that do not appear in the context (caught "
              "automatically by `valid_evidence_quote_rate` at diagnosis "
              "time).")
    md.append("")
    md.append(
        "Fill this section with concrete observations after reading the "
        "per-case outputs; do not edit the benchmark code or the prompt to "
        "patch individual cases."
    )
    md.append("")

    md.append("## Interpretation guardrails")
    md.append("")
    md.append(
        "- This is a **5-case dev split**. M7 numbers cannot support "
        "statements of the form \"LLM summaries are better than RTK in "
        "general\"."
    )
    md.append(
        "- M7 CAN support statements of the form \"on these 5 dev cases, "
        "with summarizer S and prompt v1 (SHA `xxx…`), the final summary "
        "preserved Y% of required signals and produced diagnosis category "
        "accuracy Z% under debugger D (prompt SHA `yyy…`).\""
    )
    md.append(
        "- Signal recall is a text-preservation proxy. A summary may "
        "paraphrase correctly and still lose literal matches; cross-check "
        "with the diagnosis category accuracy and critical-signal mention."
    )
    md.append(
        "- Cost matters. Report summary processing tokens alongside final "
        "context size; a 99% final-context reduction that required 50× "
        "more processing tokens than raw may not be cheaper end-to-end."
    )
    md.append(
        "- Do not retune prompts/models/methods after reading this report "
        "and present the new run as a comparison — that invalidates the "
        "experiment."
    )
    md.append("")

    out_path = reports_dir / f"{split}_m7_real_summary_{method_name.removeprefix('llm-summary-v1-')}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "M7 experiment wrapper. Runs validate → privacy audit → "
            "real LLM summary (command provider) → signal recall eval → "
            "optional fixed diagnoser + diagnosis eval → M7 manifest + "
            "report. Refuses to call any external model without explicit "
            "opt-in."
        )
    )
    ap.add_argument("--split", default="dev")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--summarizer-config", type=Path, required=True)
    ap.add_argument("--summarizer-name", default=None,
                    help="Override the summarizer_name from config.")
    ap.add_argument("--method", default=None,
                    help="Override method_name from config.")
    ap.add_argument("--diagnoser-config", type=Path, default=None,
                    help="Optional — when given, the wrapper also runs the "
                         "fixed diagnoser on the new summary method.")
    ap.add_argument("--diagnoser-name", default=None)
    ap.add_argument("--allow-external-llm", action="store_true")
    ap.add_argument("--allow-privacy-audit-hits", action="store_true")
    ap.add_argument("--summary-only", action="store_true",
                    help="Skip the diagnosis step even if a diagnoser config is given.")
    ap.add_argument("--diagnosis-only", action="store_true",
                    help="Skip summary generation; assumes manifest already exists.")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--compared-methods", nargs="*", default=None,
                    help="Methods to include in M7 report tables. Defaults "
                         "to raw, tail, grep, rtk-read, rtk-log, rtk-err-cat, "
                         "llm-summary-v1-mock plus the new method.")
    args = ap.parse_args(argv)

    s_config_path = args.summarizer_config.resolve()
    s_config = load_json(s_config_path)
    s_config_sha = sha256_path(s_config_path)
    summarizer_name = args.summarizer_name or s_config["summarizer_name"]
    method_name = args.method or s_config["method_name"]

    if not METHOD_NAME_RE.match(method_name):
        print(f"ERROR: method name {method_name!r} must match "
              f"'llm-summary-v1-<slug>' (lowercase a–z/0–9/hyphen), and "
              f"must NOT equal 'llm-summary-v1-mock'.", file=sys.stderr)
        return 2

    # Method-name guard: never overwrite the reserved mock manifest.
    target_manifest = args.results_dir / args.split / f"{method_name}.jsonl"
    if method_name == "llm-summary-v1-mock":
        print("ERROR: llm-summary-v1-mock is reserved. Pick a new slug.",
              file=sys.stderr)
        return 2

    # External-LLM opt-in gate.
    s_privacy = s_config.get("privacy") or {}
    if s_config.get("provider") == "command":
        if not check_external_llm_opt_in(s_privacy, args.allow_external_llm):
            print(
                "ERROR: summarizer config targets an external model. "
                "Opt in by setting CILOGBENCH_ALLOW_EXTERNAL_LLM=1 OR "
                "passing --allow-external-llm. Refusing to proceed.",
                file=sys.stderr,
            )
            return 2

    d_config = None
    d_config_sha: str | None = None
    d_config_path = args.diagnoser_config.resolve() if args.diagnoser_config else None
    diagnoser_name = args.diagnoser_name
    if d_config_path and not args.summary_only:
        d_config = load_json(d_config_path)
        d_config_sha = sha256_path(d_config_path)
        diagnoser_name = diagnoser_name or d_config.get("diagnoser_name")
        if d_config.get("provider") == "command":
            if not check_external_llm_opt_in(
                d_config.get("privacy") or {}, args.allow_external_llm,
            ):
                print(
                    "ERROR: diagnoser config targets an external model. "
                    "Opt in by setting CILOGBENCH_ALLOW_EXTERNAL_LLM=1 OR "
                    "passing --allow-external-llm. Refusing to proceed.",
                    file=sys.stderr,
                )
                return 2

    started_at = dt.datetime.now(dt.timezone.utc).isoformat()

    # 1. validate
    if not args.diagnosis_only:
        run_step(
            [sys.executable, "tools/validate_cases.py",
             str(args.cases_dir / args.split)],
            label="validate_cases",
        )

    # 2. privacy audit on raw logs
    if not args.diagnosis_only:
        run_step(
            [sys.executable, "tools/audit_context_privacy.py",
             "--split", args.split, "--context-method", "raw",
             "--results-dir", str(args.results_dir),
             "--reports-dir", str(args.reports_dir)],
            label="audit_context_privacy",
        )
        hits = audit_had_hits(args.results_dir / args.split / "privacy_audit.json")
        if hits > 0 and not args.allow_privacy_audit_hits:
            print(
                f"ERROR: privacy audit found {hits} hit(s). Review "
                f"reports/{args.split}_privacy_audit.md. Override with "
                f"--allow-privacy-audit-hits if you really want to send the "
                f"logs anyway.", file=sys.stderr,
            )
            return 3

    # 3. summary
    map_prompt_path = (ROOT / s_config["prompts"]["map_prompt_path"]).resolve()
    reduce_prompt_path = (ROOT / s_config["prompts"]["reduce_prompt_path"]).resolve()
    map_prompt_sha = sha256_path(map_prompt_path)
    reduce_prompt_sha = sha256_path(reduce_prompt_path)

    if not args.diagnosis_only:
        chunk_lines, overlap_lines = convert_chunking(s_config.get("chunking") or {})
        summary_argv = [
            sys.executable, "tools/run_llm_summary_baseline.py",
            "--split", args.split,
            "--cases-dir", str(args.cases_dir),
            "--results-dir", str(args.results_dir),
            "--method", method_name,
            "--provider", s_config.get("provider", "command"),
            "--chunk-lines", str(chunk_lines),
            "--chunk-overlap-lines", str(overlap_lines),
            "--temperature", str((s_config.get("model") or {}).get("temperature", 0)),
        ]
        if s_config.get("provider") == "command":
            cmd = s_config.get("command_override")
            if not cmd:
                env_var = s_config.get("command_env_var") or "LLM_SUMMARY_COMMAND"
                cmd = os.environ.get(env_var, "")
                if not cmd:
                    print(
                        f"ERROR: command provider requires {env_var} to be "
                        f"set or config.command_override.", file=sys.stderr,
                    )
                    return 1
            summary_argv += ["--command", cmd]
        if args.no_cache:
            summary_argv.append("--force")
        if args.strict:
            summary_argv.append("--fail-fast")
        run_step(summary_argv, label="run_llm_summary_baseline")

    # 4. signal recall for the new method
    run_step(
        [sys.executable, "tools/evaluate_signal_recall.py",
         "--split", args.split, "--method", method_name,
         "--results-dir", str(args.results_dir)],
        label="evaluate_signal_recall",
    )

    # 5 + 6. optional diagnosis pass over the new summary method
    debugger_prompt_sha: str | None = None
    did_diagnosis = False
    if d_config is not None and not args.summary_only:
        dd_prompt_path = (ROOT / d_config["prompt_path"]).resolve()
        debugger_prompt_sha = sha256_path(dd_prompt_path)
        diag_argv = [
            sys.executable, "tools/run_diagnosis.py",
            "--split", args.split,
            "--cases-dir", str(args.cases_dir),
            "--results-dir", str(args.results_dir),
            "--prompt", str(dd_prompt_path),
            "--diagnoser-name", diagnoser_name,
            "--context-method", method_name,
        ]
        if d_config.get("provider") == "mock":
            diag_argv += ["--diagnoser", "mock"]
        else:
            diag_argv += ["--diagnoser", "command"]
            dcmd = d_config.get("command_override")
            if not dcmd:
                env_var = d_config.get("command_env_var") or "DIAGNOSIS_COMMAND"
                dcmd = os.environ.get(env_var, "")
                if not dcmd:
                    print(
                        f"ERROR: diagnoser command provider requires "
                        f"{env_var}.", file=sys.stderr,
                    )
                    return 1
            diag_argv += ["--command", dcmd]
        if args.no_cache:
            diag_argv.append("--no-cache")
        if args.strict:
            diag_argv.append("--strict")
        # Per Codex 2026-05-14 F1: propagate the wrapper-level opt-in
        # so run_diagnosis.py's gate sees the explicit acknowledgement.
        if args.allow_external_llm:
            diag_argv.append("--allow-external-llm")
        # Per Codex 2026-05-15 F2: thread the validated config path so
        # the child uses the same file the wrapper loaded.
        if d_config_path is not None:
            diag_argv += ["--diagnoser-config", str(d_config_path)]
        run_step(diag_argv, label="run_diagnosis")

        run_step(
            [sys.executable, "tools/evaluate_diagnosis.py",
             "--split", args.split, "--diagnoser", diagnoser_name,
             "--cases-dir", str(args.cases_dir),
             "--results-dir", str(args.results_dir)],
            label="evaluate_diagnosis",
        )
        run_step(
            [sys.executable, "tools/render_diagnosis_report.py",
             "--split", args.split, "--diagnoser", diagnoser_name,
             "--results-dir", str(args.results_dir),
             "--reports-dir", str(args.reports_dir)],
            label="render_diagnosis_report",
        )
        did_diagnosis = True

    # 7. Rebuild the signal-recall cross-method report so it includes the
    # new summary method.
    run_step(
        [sys.executable, "tools/render_report.py",
         "--split", args.split,
         "--results-dir", str(args.results_dir),
         "--reports-dir", str(args.reports_dir),
         "--methods", "raw", "tail", "grep",
         "rtk-read", "rtk-log", "rtk-err-cat",
         "llm-summary-v1-mock", method_name],
        label="render_report",
    )

    # 8. manifest
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    commit, dirty = git_commit()

    compared_methods = args.compared_methods or [
        "raw", "tail", "grep",
        "rtk-read", "rtk-log", "rtk-err-cat",
        "llm-summary-v1-mock", method_name,
    ]

    manifest = {
        "split": args.split,
        "summarizer_name": summarizer_name,
        "summary_method": method_name,
        "summarizer_config_path": str(s_config_path.relative_to(ROOT)),
        "summarizer_config_sha256": s_config_sha,
        "map_prompt_path": str(map_prompt_path.relative_to(ROOT)),
        "map_prompt_sha256": map_prompt_sha,
        "reduce_prompt_path": str(reduce_prompt_path.relative_to(ROOT)),
        "reduce_prompt_sha256": reduce_prompt_sha,

        "diagnoser_name": diagnoser_name if did_diagnosis else None,
        "diagnoser_config_path": (
            str(d_config_path.relative_to(ROOT)) if did_diagnosis and d_config_path
            else None
        ),
        "diagnoser_config_sha256": d_config_sha if did_diagnosis else None,
        "debugger_prompt_path": (
            (d_config or {}).get("prompt_path") if did_diagnosis else None
        ),
        "debugger_prompt_sha256": debugger_prompt_sha if did_diagnosis else None,

        "case_count": len(load_manifest_rows(target_manifest)),
        "privacy_audit_path": str(
            (args.results_dir / args.split / "privacy_audit.json").relative_to(ROOT)
        ),
        "summary_manifest_path": str(target_manifest.relative_to(ROOT)),
        "signal_eval_path": str(
            (args.results_dir / args.split / f"eval_{method_name}.json")
            .relative_to(ROOT)
        ),
        "diagnosis_output_dir": (
            str((args.results_dir / args.split / "diagnoses" / diagnoser_name)
                .relative_to(ROOT)) if did_diagnosis else None
        ),
        "diagnosis_eval_path": (
            str((args.results_dir / args.split
                 / f"eval_diagnosis_{diagnoser_name}.json").relative_to(ROOT))
            if did_diagnosis else None
        ),
        "report_path": None,
        "started_at": started_at,
        "finished_at": finished_at,
        "git_commit": commit,
        "working_tree_dirty": dirty,
        "opt_in_source": (
            "env" if os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM", "") == "1"
            else "cli" if args.allow_external_llm else "config"
        ),
    }

    slug = method_name.removeprefix("llm-summary-v1-")
    manifest_path = (
        args.results_dir / args.split
        / f"m7_real_summary_{slug}.manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Report first so we can record its path, then rewrite manifest.
    report_path = write_m7_report(
        split=args.split,
        summarizer_config=s_config,
        summarizer_config_path=s_config_path,
        summarizer_config_sha=s_config_sha,
        map_prompt_sha=map_prompt_sha,
        reduce_prompt_sha=reduce_prompt_sha,
        method_name=method_name,
        diagnoser_config=d_config if did_diagnosis else None,
        diagnoser_config_path=d_config_path if did_diagnosis else None,
        diagnoser_config_sha=d_config_sha if did_diagnosis else None,
        debugger_prompt_sha=debugger_prompt_sha,
        diagnoser_name=diagnoser_name if did_diagnosis else None,
        compared_methods=compared_methods,
        results_dir=args.results_dir,
        reports_dir=args.reports_dir,
        manifest_path=manifest_path,
    )
    manifest["report_path"] = str(report_path.relative_to(ROOT))
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nM7 manifest → {manifest_path.relative_to(ROOT)}")
    print(f"M7 report   → {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
