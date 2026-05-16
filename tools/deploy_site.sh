#!/usr/bin/env bash
# Sync the LogDx-CI GH Pages site (docs/) to the dedicated
# `logdx-bench/logdx-bench.github.io` repo. The org-root site URL
# requires a separate repo named exactly `<org>.github.io`, so we
# can't just enable Pages on the code repo for a clean URL.
#
# Usage:
#   bash tools/deploy_site.sh          # dry-run: stage + show diff
#   bash tools/deploy_site.sh --push   # stage + commit + push
#
# Prereq: SSH access to git@github.com:logdx-bench/logdx-bench.github.io
# (you should be a member/admin of the logdx-bench org).
set -euo pipefail

SITE_REPO_SSH="git@github.com:logdx-bench/logdx-bench.github.io.git"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGING="$(mktemp -d)/logdx-bench.github.io"
PUSH_MODE="${1:-}"

echo "==> Cloning $SITE_REPO_SSH into $STAGING"
git clone "$SITE_REPO_SSH" "$STAGING" 2>&1 | tail -5

echo "==> Syncing docs/ → site repo root (preserve .git)"
# Use rsync to mirror docs/ at the repo root. Preserve the site
# repo's own .git directory.
rsync -a --delete \
    --exclude '.git' \
    --exclude 'CNAME' \
    "$REPO_ROOT/docs/" "$STAGING/"

# Carry the project README's high-level info into a CNAME-friendly
# /index hint only if no Jekyll-default `index.md` exists yet (ours
# does — already in docs/index.md).

cd "$STAGING"
echo "==> Staging changes"
git add -A

echo ""
echo "==> Diff summary"
git status --short
echo ""
git diff --cached --stat | tail -20 || true

if [ "$PUSH_MODE" != "--push" ]; then
    echo ""
    echo "DRY RUN. Re-run with '--push' to commit and push:"
    echo "    bash tools/deploy_site.sh --push"
    echo ""
    echo "Staging tree left at: $STAGING"
    exit 0
fi

if git diff --cached --quiet; then
    echo "==> No changes to deploy."
    exit 0
fi

CODE_SHA=$(cd "$REPO_ROOT" && git rev-parse --short HEAD)
COMMIT_MSG="Sync site from logdx-bench/LogDx@$CODE_SHA"

echo "==> Committing: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

echo "==> Pushing to origin/main"
git push origin main

echo ""
echo "==> Done. Pages will rebuild in ~1 min."
echo "    Live URL: https://logdx-bench.github.io/"
