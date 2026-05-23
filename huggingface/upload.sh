#!/usr/bin/env bash
# Upload the LogDx-CI cases corpus to HuggingFace as a dataset.
#
# Prereq: install the modern unified Hugging Face CLI:
#     pip install -U huggingface_hub
# Then authenticate (once, with a write token from
# https://huggingface.co/settings/tokens):
#     hf auth login
#
# Idempotent: re-running will sync the latest cases/ tree to the
# dataset repo. To bump release tag, change v2-partial-2026-05-20
# below.
set -euo pipefail

DATASET_REPO="eyuansu71/logdx-ci"
RELEASE_TAG="v2-partial-2026-05-20"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGING="$(mktemp -d)/logdx-hf"

echo "==> Staging dataset content at $STAGING"
mkdir -p "$STAGING"
# Per-case files: raw.log + case.json + ground_truth.json + tags.json
# + privacy_audit.json under cases/<split>/<case_id>/
cp -r "$REPO_ROOT/cases" "$STAGING/"
# Dataset card (HF reads README.md with YAML frontmatter)
cp "$REPO_ROOT/huggingface/README.md" "$STAGING/README.md"
# Per-data license + citation
cp "$REPO_ROOT/LICENSE-DATA" "$STAGING/LICENSE"
cp "$REPO_ROOT/CITATION.cff" "$STAGING/"

echo "==> Verifying staging tree"
echo "Case count: $(find "$STAGING/cases" -name case.json | wc -l | tr -d ' ')"
echo "Total size: $(du -sh "$STAGING" | cut -f1)"

echo "==> Creating HF dataset repo (idempotent via --exist-ok)"
hf repo create "$DATASET_REPO" --repo-type dataset --exist-ok

echo "==> Uploading to $DATASET_REPO"
hf upload \
    "$DATASET_REPO" \
    "$STAGING" . \
    --repo-type dataset \
    --commit-message "$RELEASE_TAG initial release"

echo ""
echo "==> Done. View at: https://huggingface.co/datasets/$DATASET_REPO"
echo "==> To verify download:"
echo "    hf download --repo-type dataset \\"
echo "        $DATASET_REPO --local-dir /tmp/logdx-hf-verify"
