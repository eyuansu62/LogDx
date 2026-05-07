"""
Benchmark runner.

Usage:
    # 1. Set a GitHub token (public-repo scope is enough):
    export GITHUB_TOKEN=ghp_xxx

    # 2. Run with the default sample set:
    python -m cilog.bench

    # 3. Or point it at specific failed runs:
    python -m cilog.bench --runs owner/repo:run_id owner2/repo2:run_id2

Output: writes results/report.html, results/summary.csv, results/raw/ and results/compressed/.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from .compressor import compress_log
from .signals import measure_preservation, SignalReport
from .tokens import count_tokens, tokenizer_name


# Default list of recent failed CI runs to benchmark. We pick these at runtime
# by querying the GitHub API for recent failed workflow runs on popular repos.
DEFAULT_REPOS = [
    # Python
    "pandas-dev/pandas",
    "scikit-learn/scikit-learn",
    "huggingface/transformers",
    "fastapi/fastapi",
    "django/django",
    "apache/airflow",
    # JavaScript / TypeScript
    "facebook/react",
    "vercel/next.js",
    "microsoft/TypeScript",
    "vitejs/vite",
    "vitest-dev/vitest",
    "sveltejs/svelte",
    # Rust
    "rust-lang/cargo",
    "tokio-rs/tokio",
    "BurntSushi/ripgrep",
    "pola-rs/polars",
    # Go
    "kubernetes/kubernetes",
    "hashicorp/terraform",
    "grafana/grafana",
    "prometheus/prometheus",
]


@dataclasses.dataclass
class BenchResult:
    source: str  # "owner/repo:run_id:job_id"
    repo: str
    job_name: str
    original_bytes: int
    original_lines: int
    original_tokens: int
    compressed_bytes: int
    compressed_lines: int
    compressed_tokens: int
    has_failure: bool
    signal_report: SignalReport | None
    elapsed_ms: float

    @property
    def byte_ratio(self) -> float:
        return self.compressed_bytes / self.original_bytes if self.original_bytes else 0.0

    @property
    def token_ratio(self) -> float:
        return self.compressed_tokens / self.original_tokens if self.original_tokens else 0.0

    @property
    def byte_reduction_pct(self) -> float:
        return 100 * (1 - self.byte_ratio)

    @property
    def token_reduction_pct(self) -> float:
        return 100 * (1 - self.token_ratio)


def gh_api(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "cilog-bench",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def gh_download(url: str, token: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cilog-bench",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def find_failed_runs(repo: str, token: str, max_runs: int = 2) -> list[dict]:
    """Find recent failed workflow runs for a repo, diversified across workflows.

    GitHub's feed often shows several recent failures of the same flaky
    workflow. Without diversification, samples[0] and samples[1] end up
    being the same bug reported twice, which inflates the denominator for
    any compressor flaw that hits that bug. Returns at most one run per
    distinct workflow_id among the most-recent failures.
    """
    per_page = max(20, max_runs * 8)
    try:
        data = gh_api(
            f"/repos/{repo}/actions/runs?status=failure&per_page={per_page}",
            token,
        )
    except urllib.error.HTTPError as e:
        print(f"  ! {repo}: {e}", file=sys.stderr)
        return []
    runs = [r for r in data.get("workflow_runs", []) if r.get("conclusion") == "failure"]
    # Keep the most recent run per workflow_id, in source order.
    seen_workflows: set = set()
    picked: list[dict] = []
    for r in runs:
        wid = r.get("workflow_id")
        if wid in seen_workflows:
            continue
        seen_workflows.add(wid)
        picked.append(r)
        if len(picked) >= max_runs:
            break
    return picked


def find_failed_jobs(repo: str, run_id: int, token: str) -> list[dict]:
    try:
        data = gh_api(f"/repos/{repo}/actions/runs/{run_id}/jobs", token)
    except urllib.error.HTTPError as e:
        print(f"  ! {repo} run {run_id}: {e}", file=sys.stderr)
        return []
    return [j for j in data.get("jobs", []) if j.get("conclusion") == "failure"]


class _NoFollow(urllib.request.HTTPRedirectHandler):
    """Refuse to auto-follow redirects so we can handle them ourselves."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_job_log(repo: str, job_id: int, token: str) -> str:
    """Fetch raw log for a single job.

    The GitHub logs endpoint returns 302 -> a signed URL on Azure Blob
    storage. The signed URL carries its own auth in the query string.
    If we let urllib auto-follow the redirect, it will forward our
    `Authorization: Bearer <gh_token>` header to the blob host, which
    rejects it with 401. So we disable auto-follow, grab the Location,
    and do a second request WITHOUT the Authorization header.
    """
    url = f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cilog-bench",
        },
    )
    opener = urllib.request.build_opener(_NoFollow)
    try:
        with opener.open(req, timeout=30) as resp:
            # No redirect (rare but possible) — body is the log.
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            signed_url = e.headers.get("Location")
            if not signed_url:
                raise
            # Second hop: signed URL is self-authenticating, no headers needed.
            req2 = urllib.request.Request(
                signed_url,
                headers={"User-Agent": "cilog-bench"},
            )
            with urllib.request.urlopen(req2, timeout=60) as resp:
                raw = resp.read()
        else:
            raise
    # Logs can be utf-8, latin-1, or mixed. Be lenient.
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def benchmark_one(raw_log: str, source: str, repo: str, job_name: str) -> tuple[BenchResult, str]:
    original_bytes = len(raw_log.encode("utf-8"))
    original_lines = raw_log.count("\n") + 1
    original_tokens = count_tokens(raw_log)

    t0 = time.perf_counter()
    compressed, sections = compress_log(raw_log)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    compressed_bytes = len(compressed.encode("utf-8"))
    compressed_lines = compressed.count("\n") + 1
    compressed_tokens = count_tokens(compressed)

    has_failure = any(s.has_failure for s in sections)
    report = measure_preservation(raw_log, compressed)

    return BenchResult(
        source=source,
        repo=repo,
        job_name=job_name,
        original_bytes=original_bytes,
        original_lines=original_lines,
        original_tokens=original_tokens,
        compressed_bytes=compressed_bytes,
        compressed_lines=compressed_lines,
        compressed_tokens=compressed_tokens,
        has_failure=has_failure,
        signal_report=report,
        elapsed_ms=elapsed_ms,
    ), compressed


def collect_samples(
    repos: list[str],
    token: str,
    samples_per_repo: int,
    out_dir: Path,
    min_size: int = 0,
) -> list[tuple[str, str, str]]:
    """Return list of (source_tag, repo, job_name, raw_log) — cached on disk.

    Logs shorter than `min_size` bytes are skipped: they're dominated by
    fixed-cost GHA preamble (checkout, artifact cleanup, etc.) and carry
    little information about compression on realistic failure content.
    Skipped logs are still cached so re-runs with a lower threshold don't
    re-hit the API.
    """
    cache_dir = out_dir / "raw"
    cache_dir.mkdir(parents=True, exist_ok=True)
    samples = []

    for repo in repos:
        print(f"[{repo}] finding failed runs...")
        runs = find_failed_runs(repo, token, max_runs=max(samples_per_repo * 2, 3))
        collected = 0
        for run in runs:
            if collected >= samples_per_repo:
                break
            run_id = run["id"]
            jobs = find_failed_jobs(repo, run_id, token)
            for job in jobs:
                if collected >= samples_per_repo:
                    break
                job_id = job["id"]
                job_name = job["name"]
                tag = f"{repo.replace('/', '_')}__{run_id}__{job_id}"
                cache_file = cache_dir / f"{tag}.log"

                if cache_file.exists():
                    raw = cache_file.read_text(encoding="utf-8", errors="replace")
                    print(f"  cached: {tag}")
                else:
                    try:
                        raw = fetch_job_log(repo, job_id, token)
                    except urllib.error.HTTPError as e:
                        print(f"  ! fetch failed {tag}: {e}", file=sys.stderr)
                        continue
                    except Exception as e:  # noqa
                        print(f"  ! fetch failed {tag}: {e}", file=sys.stderr)
                        continue
                    cache_file.write_text(raw, encoding="utf-8")
                    print(f"  fetched: {tag} ({len(raw)} bytes)")

                if min_size and len(raw.encode("utf-8")) < min_size:
                    print(f"    skip (size {len(raw)} < min_size {min_size}): {job_name}")
                    continue

                # Source uses the same `__`-separated form as the cache tag so
                # the derived compressed filename matches between fetch and
                # --offline runs. (Older fetches used `repo:run_id:job_id`,
                # which produced single-underscore compressed filenames and
                # left orphaned files whenever offline overwrote.)
                source = tag
                samples.append((source, repo, job_name, raw))
                collected += 1
                time.sleep(0.3)  # be polite
    return samples


def write_csv(results: list[BenchResult], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "source", "repo", "job_name",
            "original_bytes", "original_lines", "original_tokens",
            "compressed_bytes", "compressed_lines", "compressed_tokens",
            "byte_reduction_pct", "token_reduction_pct",
            "has_failure",
            "signals_total", "signals_preserved", "preservation_rate",
            "elapsed_ms",
        ])
        for r in results:
            sr = r.signal_report
            w.writerow([
                r.source, r.repo, r.job_name,
                r.original_bytes, r.original_lines, r.original_tokens,
                r.compressed_bytes, r.compressed_lines, r.compressed_tokens,
                f"{r.byte_reduction_pct:.1f}", f"{r.token_reduction_pct:.1f}",
                r.has_failure,
                sr.total_signals if sr else 0,
                sr.preserved_signals if sr else 0,
                f"{sr.preservation_rate * 100:.1f}" if sr else "100.0",
                f"{r.elapsed_ms:.1f}",
            ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", nargs="*", default=DEFAULT_REPOS)
    parser.add_argument("--samples-per-repo", type=int, default=2)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--offline", action="store_true",
                        help="Skip fetching; use cached samples in --out/raw/")
    parser.add_argument("--synthetic", action="store_true",
                        help="Skip GitHub entirely; use built-in synthetic samples for smoke test")
    parser.add_argument("--min-size", type=int, default=5000, metavar="BYTES",
                        help="Drop samples smaller than BYTES (default 5000). "
                             "Applies to fetch and --offline. Use 0 to disable.")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "compressed").mkdir(exist_ok=True)

    print(f"Tokenizer: {tokenizer_name()}")

    samples: list[tuple[str, str, str, str]] = []

    if args.synthetic:
        from . import synthetic
        print("Using synthetic samples.")
        samples = synthetic.all_samples()
    elif args.offline:
        raw_dir = args.out / "raw"
        skipped_small = 0
        for cache_file in sorted(raw_dir.glob("*.log")):
            tag = cache_file.stem
            repo_parts = tag.split("__")
            repo = repo_parts[0].replace("_", "/", 1) if len(repo_parts) > 0 else "unknown"
            raw = cache_file.read_text(encoding="utf-8", errors="replace")
            if args.min_size and len(raw.encode("utf-8")) < args.min_size:
                skipped_small += 1
                continue
            samples.append((tag, repo, tag, raw))
        if skipped_small:
            print(f"Skipped {skipped_small} cached samples below --min-size {args.min_size}.")
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("ERROR: GITHUB_TOKEN env var required (or use --synthetic / --offline).", file=sys.stderr)
            return 1
        samples = collect_samples(
            args.repos, token, args.samples_per_repo, args.out,
            min_size=args.min_size,
        )

    if not samples:
        print("No samples collected.", file=sys.stderr)
        return 1

    print(f"\nBenchmarking {len(samples)} samples...")
    results: list[BenchResult] = []
    compressed_outputs: dict[str, str] = {}
    raw_outputs: dict[str, str] = {}
    for source, repo, job_name, raw in samples:
        r, compressed = benchmark_one(raw, source, repo, job_name)
        results.append(r)
        compressed_outputs[source] = compressed
        raw_outputs[source] = raw
        print(f"  {source}: {r.original_tokens:>7d} → {r.compressed_tokens:>6d} tokens "
              f"({r.token_reduction_pct:5.1f}% off)  signals kept: "
              f"{r.signal_report.preserved_signals}/{r.signal_report.total_signals}")

        # Save compressed to disk for inspection
        safe = source.replace("/", "_").replace(":", "_")
        (args.out / "compressed" / f"{safe}.md").write_text(compressed, encoding="utf-8")

    # Write CSV
    csv_path = args.out / "summary.csv"
    write_csv(results, csv_path)
    print(f"\nCSV summary: {csv_path}")

    # Write HTML report
    from . import report as report_mod
    html_path = args.out / "report.html"
    html = report_mod.build_report(results, compressed_outputs, raw_outputs, tokenizer_name())
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML report: {html_path}")

    # Aggregate stats
    total_orig = sum(r.original_tokens for r in results)
    total_comp = sum(r.compressed_tokens for r in results)
    avg_reduction = 100 * (1 - total_comp / total_orig) if total_orig else 0
    preservation_rates = [
        r.signal_report.preservation_rate for r in results
        if r.signal_report and r.signal_report.total_signals > 0
    ]
    avg_preservation = 100 * sum(preservation_rates) / len(preservation_rates) if preservation_rates else 100.0

    print("\n" + "=" * 60)
    print(f"Aggregate:  {total_orig:,} tokens → {total_comp:,} tokens ({avg_reduction:.1f}% reduction)")
    print(f"Avg signal preservation: {avg_preservation:.1f}%")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
