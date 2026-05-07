"""
Audit method-context outputs for obvious secret patterns before they are
sent to an external model.

This is a **best-effort** scanner. It cannot guarantee that logs are safe
to share with a third party. If a pattern fires, inspect the hit and
decide whether to stop the M6 run, redact (separate milestone), or
accept the risk with documented justification.

Usage:
    python tools/audit_context_privacy.py --split dev --context-method all
    python tools/audit_context_privacy.py --split dev --context-method grep
    python tools/audit_context_privacy.py --raw-log cases/v2/_incoming/<id>/raw.log

Inputs:
    results/<split>/<method>.jsonl (context manifests from M2–M4)
    results/<split>/<method>/<case>.txt

  …or, in raw-log mode (E10 Phase 2 candidate intake):
    a single raw.log path, scanned directly before import.

Outputs:
    results/<split>/privacy_audit.json
    reports/<split>_privacy_audit.md

  …or, in raw-log mode:
    <raw-log-dir>/privacy_audit.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Same exclusions as the diagnosis runner.
METHOD_EXCLUDE_PREFIXES = ("eval_",)

# (label, regex, note). Each pattern is a compiled RE applied line-by-line
# so pathological single lines do not trigger catastrophic backtracking.
# The note column describes how to interpret a hit.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("github_classic_token",
        re.compile(r"ghp_[A-Za-z0-9]{30,}"),
        "GitHub classic PAT; rotate immediately if leaked."),
    ("github_fine_grained_token",
        re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
        "GitHub fine-grained PAT."),
    ("openai_key",
        re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{30,}"),
        "OpenAI / compatible sk- token (length ≥ 30)."),
    ("aws_access_key",
        re.compile(r"AKIA[A-Z0-9]{16}"),
        "AWS access key ID prefix."),
    # Per Codex adversarial review #2 (2026-05-07): the prior version of
    # this regex matched only `aws_secret_access_key=` (the prefix) and
    # left the actual secret value in the redacted line snippet. Now
    # consume both the key name and the assigned value so _redact() and
    # _redacted_snippet() actually obscure the secret.
    ("aws_secret_key_hint",
        re.compile(r"aws_secret_access_key\s*[=:]\s*[^\s\"'&]+", re.IGNORECASE),
        "Line assigns aws_secret_access_key=<value>; inspect and rotate."),
    ("private_key_block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        "PEM-encoded private key block."),
    ("ssh_private_key_openssh",
        re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
        "OpenSSH private key."),
    ("authorization_header",
        re.compile(r"Authorization:\s+(?!\*\*\*)(Basic|Bearer)\s+[A-Za-z0-9._/+=-]{10,}"),
        "Authorization header with non-masked credential."),
    ("bearer_token",
        re.compile(r"(?<![A-Za-z0-9])Bearer\s+(?!\*\*\*)[A-Za-z0-9._/+=-]{20,}"),
        "Bearer token with non-masked value."),
    ("password_assignment",
        re.compile(r"(?:^|[\s&?])(?:password|passwd|pwd)\s*=\s*(?!\*\*\*)[^\s\"'&]{6,}",
                   re.IGNORECASE),
        "password=<value>; verify whether the value is truly private."),
    ("secret_assignment",
        re.compile(r"(?:^|[\s&?])(?:secret|apikey|api_key)\s*=\s*(?!\*\*\*)[^\s\"'&]{8,}",
                   re.IGNORECASE),
        "secret=<value> / apikey=<value> pattern."),
    ("npm_token",
        re.compile(r"npm_[A-Za-z0-9]{30,}"),
        "npm token prefix."),
    ("slack_token",
        re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
        "Slack API token."),
    ("url_credential",
        re.compile(r"(?:[A-Za-z][A-Za-z0-9+.\-]*)://[^\s/]*:(?!\*\*\*)[^\s@]+@[^\s]+"),
        "URL containing user:password credentials."),
]

MAX_LINE_LEN_FOR_SCAN = 8000   # skip extreme lines (base64 blobs, progress bars)
MAX_LINES_PER_FILE = 50000     # generous cap
MAX_SNIPPET_LEN = 160


def discover_methods(results_dir: Path, split: str) -> list[str]:
    split_dir = results_dir / split
    out: list[str] = []
    for p in sorted(split_dir.glob("*.jsonl")):
        stem = p.stem
        if any(stem.startswith(pfx) for pfx in METHOD_EXCLUDE_PREFIXES):
            continue
        if ".debug." in p.name:
            continue
        # Hybrid baselines also drop a `<method>.routes.jsonl` next to
        # their main manifest. That file has no matching directory and
        # would otherwise be reported as a missing-method dir under the
        # round-3 fail-closed semantics. Skip it explicitly. (The same
        # filter exists in tools/run_diagnosis.py for the same reason.)
        if stem.endswith(".routes"):
            continue
        out.append(stem)
    return out


def _redact(secret: str) -> dict:
    """Replace a real secret with a non-reversible fingerprint.

    The audit must NOT re-write the secret into its own output (per Codex
    adversarial review 2026-05-07): the resulting JSON file would just be
    another copy of the credential. Keep only the length, a sha256 prefix,
    and the first/last 2 chars so a human can still triage uniqueness."""
    sha = hashlib.sha256(secret.encode("utf-8", errors="replace")).hexdigest()
    head = secret[:2] if len(secret) >= 2 else secret
    tail = secret[-2:] if len(secret) >= 4 else ""
    return {
        "length": len(secret),
        "sha256_prefix": sha[:12],
        "head2": head,
        "tail2": tail,
    }


def _redacted_snippet(line: str, spans: list[str]) -> str:
    """Return the line with EVERY matched secret span replaced by
    [REDACTED]. Per Codex adversarial review #3 (2026-05-07):
    multi-secret lines previously leaked the second-and-later secrets
    because only the first matched span was redacted. Always pass the
    full list of spans found anywhere on the line."""
    redacted = line
    # Redact longest spans first so a shorter substring of a longer
    # secret can't survive the replace.
    for span in sorted(set(spans), key=len, reverse=True):
        if span in redacted:
            redacted = redacted.replace(span, "[REDACTED]")
    redacted = redacted.strip()
    if len(redacted) > MAX_SNIPPET_LEN:
        redacted = redacted[: MAX_SNIPPET_LEN] + "…"
    return redacted


def scan_file(path: Path) -> dict:
    """Scan one file. Returns {hits, lines_scanned, lines_skipped_long,
    truncated_after, complete_scan}.

    Per Codex adversarial review 2026-05-07: callers MUST inspect
    `complete_scan`. If it is False, the audit cannot prove the file is
    clean (caps were hit) and downstream gates must fail closed."""
    result = {
        "hits": [],
        "lines_scanned": 0,
        "lines_skipped_long": 0,
        "truncated_after_line": None,
        "complete_scan": True,
    }
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        result["complete_scan"] = False
        result["error"] = "could_not_read"
        return result
    hits: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if lineno > MAX_LINES_PER_FILE:
            result["truncated_after_line"] = MAX_LINES_PER_FILE
            result["complete_scan"] = False
            break
        result["lines_scanned"] = lineno
        if len(line) > MAX_LINE_LEN_FOR_SCAN:
            result["lines_skipped_long"] += 1
            result["complete_scan"] = False
            continue
        # Per Codex adversarial review #3 (2026-05-07): collect EVERY
        # matching span on the line first, then redact all of them
        # before emitting any snippet. The previous code stopped at
        # the first matching pattern and only redacted that span, so
        # a line like `combined AKIA... and ghp_...` would leak the
        # second secret verbatim into `line_snippet_redacted`.
        line_matches: list[tuple[str, str, str]] = []
        for label, pat, note in SECRET_PATTERNS:
            m = pat.search(line)
            if m:
                line_matches.append((label, note, m.group(0)))
        if line_matches:
            all_spans = [span for (_, _, span) in line_matches]
            for label, note, span in line_matches:
                hits.append({
                    "label": label,
                    "note": note,
                    "line_number": lineno,
                    "redacted_match": _redact(span),
                    "line_snippet_redacted": _redacted_snippet(line, all_spans),
                })
    result["hits"] = hits
    return result


def audit(split: str, context_method: str, results_dir: Path,
          reports_dir: Path) -> int:
    if context_method == "all":
        methods = discover_methods(results_dir, split)
    else:
        methods = [context_method]
    if not methods:
        print(f"ERROR: no context methods discovered in {results_dir / split}",
              file=sys.stderr)
        return 1

    total_hits = 0
    # Per Codex adversarial review #3 (2026-05-07): a missing method
    # directory used to be silently noted and the audit would still
    # exit 0, so an explicit `--context-method typo` returned clean
    # despite scanning zero context files. Track missing dirs and
    # missing-but-empty dirs as separate fail-closed signals.
    methods_missing_dir = 0
    methods_with_no_files = 0
    per_method: list[dict] = []
    for m in methods:
        method_dir = results_dir / split / m
        if not method_dir.is_dir():
            methods_missing_dir += 1
            per_method.append({
                "context_method": m,
                "cases_scanned": 0,
                "incomplete_scans": 0,
                "notes": "no context directory found; method may not have been run",
                "findings": [],
            })
            continue
        findings: list[dict] = []
        case_count = 0
        incomplete_count = 0
        for ctx_path in sorted(method_dir.glob("*.txt")):
            case_count += 1
            scan = scan_file(ctx_path)
            hits = scan["hits"]
            if not scan.get("complete_scan", True):
                incomplete_count += 1
            if hits or not scan.get("complete_scan", True):
                try:
                    rel = str(ctx_path.relative_to(ROOT))
                except ValueError:
                    rel = str(ctx_path)
                findings.append({
                    "context_path": rel,
                    "case_id": ctx_path.stem,
                    "hit_count": len(hits),
                    "hits_by_label": _summarize_labels(hits),
                    "hits": hits[:40],  # cap to keep the report readable
                    "complete_scan": scan.get("complete_scan", True),
                    "lines_scanned": scan.get("lines_scanned"),
                    "lines_skipped_long": scan.get("lines_skipped_long", 0),
                    "truncated_after_line": scan.get("truncated_after_line"),
                })
                total_hits += len(hits)
        if case_count == 0:
            methods_with_no_files += 1
        per_method.append({
            "context_method": m,
            "cases_scanned": case_count,
            "incomplete_scans": incomplete_count,
            "notes": ("directory exists but contains no *.txt context "
                      "files") if case_count == 0 else None,
            "findings": findings,
        })

    # Per Codex adversarial review #2 (2026-05-07): track total
    # incomplete scans across all methods so the CLI can fail closed
    # even when no hits are found. Without this, a caller using the
    # split-mode audit as a gate before --allow-external-llm could
    # treat skipped-long-line / truncated-file outputs as a clean pass.
    total_incomplete_scans = sum(m.get("incomplete_scans", 0) for m in per_method)
    summary = {
        "split": split,
        "patterns_checked": [{"label": l, "note": n} for (l, _, n) in SECRET_PATTERNS],
        "context_method_filter": context_method,
        "total_hits": total_hits,
        "total_incomplete_scans": total_incomplete_scans,
        "methods_missing_dir": methods_missing_dir,
        "methods_with_no_files": methods_with_no_files,
        "methods": per_method,
        "disclaimer": (
            "This scanner is best-effort. It only detects patterns listed "
            "in patterns_checked. Absence of hits does NOT prove a context "
            "is safe to share. Review contexts manually before opting in "
            "to an external model provider."
        ),
    }
    out_json = results_dir / split / "privacy_audit.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")

    # Markdown report.
    md: list[str] = []
    md.append(f"# Privacy audit — `{split}`")
    md.append("")
    md.append(
        "This report lists matches of common secret patterns in every "
        "context method output for the split. **This audit is "
        "best-effort.** Absence of hits does not prove that a context is "
        "safe to share with a third-party model. Review manually before "
        "opting in to an external LLM provider."
    )
    md.append("")
    md.append(f"- Methods scanned: **{len(per_method)}**")
    md.append(f"- Total pattern hits across the split: **{total_hits}**")
    md.append(f"- Total incomplete scans across the split: "
              f"**{total_incomplete_scans}** "
              f"({'fail-closed exit 3' if total_incomplete_scans > 0 else 'all complete'})")
    md.append("")
    md.append("## Patterns checked")
    md.append("")
    for label, _, note in SECRET_PATTERNS:
        md.append(f"- `{label}` — {note}")
    md.append("")
    md.append("## Findings per method")
    md.append("")
    md.append("| Context Method | Cases Scanned | Files with Hits | Total Hits |")
    md.append("|---|---:|---:|---:|")
    for mb in per_method:
        files_with = sum(1 for f in mb["findings"] if f["hit_count"] > 0)
        total = sum(f["hit_count"] for f in mb["findings"])
        md.append(f"| {mb['context_method']} | {mb['cases_scanned']} "
                  f"| {files_with} | {total} |")
    md.append("")
    for mb in per_method:
        if not mb["findings"]:
            continue
        md.append(f"### `{mb['context_method']}`")
        md.append("")
        for f in mb["findings"]:
            md.append(f"- **`{f['case_id']}`** ({f['hit_count']} hit(s) "
                      f"in `{f['context_path']}`)")
            for label, count in f["hits_by_label"].items():
                md.append(f"  - `{label}` × {count}")
            for h in f["hits"][:5]:
                md.append(f"    - L{h['line_number']}: "
                          f"`{_escape_backticks(h['line_snippet_redacted'])}`")
            if f["hit_count"] > 5:
                md.append(f"    - … and {f['hit_count']-5} more")
            if not f.get("complete_scan", True):
                md.append(f"    - ⚠ INCOMPLETE SCAN: "
                          f"lines_skipped_long={f.get('lines_skipped_long',0)}, "
                          f"truncated_after_line={f.get('truncated_after_line')}")
        md.append("")
    md.append("## Next steps")
    md.append("")
    md.append(
        "- If the audit is clean, you may opt in to an external model by "
        "setting `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` or passing "
        "`--allow-external-llm` to `tools/run_m6_experiment.py`."
    )
    md.append(
        "- If any hit represents a real secret, either remove the case or "
        "wait for a dedicated redaction milestone. This tool is "
        "audit-only; it does not modify context files."
    )
    md.append(
        "- Even a clean audit is not a guarantee. Treat external-model "
        "runs as a privacy-sensitive action and confirm the scope with "
        "whoever owns the affected logs."
    )

    out_md = reports_dir / f"{split}_privacy_audit.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(ROOT))
        except ValueError:
            return str(p)
    print(f"Wrote {_rel(out_json)}")
    print(f"Wrote {_rel(out_md)}")
    print(f"Hits: {total_hits} across {len(per_method)} method(s); "
          f"incomplete_scans={total_incomplete_scans}; "
          f"missing_dir={methods_missing_dir}; "
          f"empty_dir={methods_with_no_files}")
    if total_hits > 0:
        return 2  # secrets found
    if total_incomplete_scans > 0:
        # Per Codex adversarial review #2 (2026-05-07): the split-mode
        # audit must fail closed too. A skipped long line or truncated
        # context file is exactly the gap that lets an unscanned secret
        # slip through to an external-model run.
        print(f"  ⚠ {total_incomplete_scans} context file(s) had incomplete "
              f"scans (long-line skip or >50k-line truncate). Cannot prove "
              f"clean. Failing closed.", file=sys.stderr)
        return 3  # incomplete — fail closed
    if methods_missing_dir > 0 or methods_with_no_files > 0:
        # Per Codex adversarial review #3 (2026-05-07): a missing or
        # empty method directory used to silently exit 0, so an
        # explicit `--context-method typo-or-missing` returned clean
        # without scanning anything. Treat this as a fail-closed
        # condition equivalent to incomplete scans — the gate cannot
        # prove the requested context is safe if it never read any of
        # its files.
        print(f"  ⚠ {methods_missing_dir} method(s) had no directory and "
              f"{methods_with_no_files} had a directory but zero "
              f"*.txt files. Audit scanned no context for at least "
              f"one requested method. Failing closed.", file=sys.stderr)
        return 3  # nothing-was-scanned — fail closed
    return 0


def _summarize_labels(hits: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for h in hits:
        out[h["label"]] = out.get(h["label"], 0) + 1
    return out


def _escape_backticks(s: str) -> str:
    return s.replace("`", "\\`")


def audit_raw_log(raw_log: Path) -> int:
    """Scan a single raw.log file (pre-import) and write privacy_audit.json
    alongside it. Used by E10 Phase 2 candidate intake before
    `import_case_skeleton.py` is run.

    Per Codex adversarial review 2026-05-07:
      - Output is redacted: matched secret values are hashed, not stored.
      - Failure is closed: if the scanner hit any cap (skipped a line for
        being too long, or stopped after MAX_LINES_PER_FILE), exit code 3
        (\"incomplete\") is returned even when zero hits were found,
        because the audit cannot prove the log is clean.

    Exit codes:
      0  no hits, scan complete (\"clean\")
      2  hits found (must redact and re-run before importing)
      3  scan incomplete (caps hit; cannot prove clean — fail closed)
    """
    if not raw_log.is_file():
        print(f"ERROR: raw log not found: {raw_log}", file=sys.stderr)
        return 1
    scan = scan_file(raw_log)
    hits = scan["hits"]
    complete = scan.get("complete_scan", True)
    summary = {
        "mode": "raw_log",
        "raw_log_path": str(raw_log),
        "raw_log_bytes": raw_log.stat().st_size,
        "patterns_checked": [
            {"label": l, "note": n} for (l, _, n) in SECRET_PATTERNS
        ],
        "total_hits": len(hits),
        "hits_by_label": _summarize_labels(hits),
        "hits": hits[:200],  # cap to keep the file readable
        "complete_scan": complete,
        "lines_scanned": scan.get("lines_scanned"),
        "lines_skipped_long": scan.get("lines_skipped_long", 0),
        "truncated_after_line": scan.get("truncated_after_line"),
        "disclaimer": (
            "This scanner is best-effort. It only detects patterns listed "
            "in patterns_checked. Absence of hits does NOT prove the log "
            "is safe to publish or pass to an external model. Inspect the "
            "log manually before importing as a benchmark case. Matched "
            "secret values are stored only as hashes (sha256_prefix) and "
            "head/tail bytes — the audit file does NOT contain the secret."
        ),
    }
    out = raw_log.parent / "privacy_audit.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Hits: {len(hits)} on {raw_log.name}  "
          f"(complete_scan={complete})")
    if hits:
        for h in hits[:5]:
            r = h["redacted_match"]
            print(f"  L{h['line_number']} {h['label']}: "
                  f"len={r['length']} sha256:{r['sha256_prefix']} "
                  f"{r['head2']}…{r['tail2']}")
        if len(hits) > 5:
            print(f"  … and {len(hits) - 5} more")
        return 2  # secrets found
    if not complete:
        print(f"  ⚠ INCOMPLETE SCAN: "
              f"lines_scanned={scan.get('lines_scanned')}, "
              f"lines_skipped_long={scan.get('lines_skipped_long', 0)}, "
              f"truncated_after_line={scan.get('truncated_after_line')}",
              file=sys.stderr)
        print("  Failing closed: cannot prove the log is clean. Either "
              "raise the scanner caps, scan the file manually, or split it.",
              file=sys.stderr)
        return 3  # scan incomplete — fail closed
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Best-effort secret-pattern scan on method context outputs."
    )
    ap.add_argument("--split", default="dev")
    ap.add_argument("--context-method", default="all",
                    help="One method name or 'all' to scan every manifest.")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--raw-log", type=Path, default=None,
                    help="Scan a single raw.log directly (E10 Phase 2 "
                         "intake). Bypasses --split / --context-method "
                         "and writes privacy_audit.json next to the log. "
                         "Exit 2 if any pattern hits, 0 if clean.")
    args = ap.parse_args(argv)
    if args.raw_log is not None:
        return audit_raw_log(args.raw_log)
    return audit(args.split, args.context_method, args.results_dir,
                  args.reports_dir)


if __name__ == "__main__":
    raise SystemExit(main())
