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

echo "==> Syncing homepage files → site repo root (preserve .git)"
# The site is a landing page, NOT a mirror of all technical docs.
# Technical sub-docs live in the code repo at
# github.com/eyuansu62/LogDx/blob/main/docs/... and GitHub renders
# them natively. Only the curated homepage pages are deployed here.
#
# The site ships exactly four files (plus the implicit Jekyll
# theme remote-loaded by _config.yml):
#   _config.yml      ← Jekyll config (theme, baseurl="", SEO)
#   index.md         ← landing page
#   leaderboard.md   ← v2 leaderboard
#   cite.md          ← citation formats
#
# Adding a new homepage page? Add it to SITE_FILES below.
SITE_FILES=( "_config.yml" "index.md" "leaderboard.md" "cite.md" )

# Clean out any prior site content (preserves .git, CNAME, .nojekyll).
find "$STAGING" -mindepth 1 -maxdepth 1 \
    -not -name '.git' \
    -not -name 'CNAME' \
    -not -name '.nojekyll' \
    -exec rm -rf {} +

# Copy the curated set.
for f in "${SITE_FILES[@]}"; do
    cp "$REPO_ROOT/docs/$f" "$STAGING/$f"
done

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
