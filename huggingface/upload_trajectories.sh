#!/usr/bin/env bash
# Upload the local agent-loop trajectory dumps to a separate HF dataset.
#
# What this uploads: `results/**/__trajectories/*.json` — full
# conversation messages (assistant text + tool_use + tool_result
# observations) from real-agent-v1 (and any future agent-loop
# diagnoser) runs. These are auto-saved by tools/run_diagnosis.py
# when invoking an agent shim; they are NOT in the main logdx-ci
# corpus dataset (which carries cases only) because:
#   - Bulk: ~50-500 KB per case, ~100 MB per full sweep.
#   - Trust tier: trajectories echo raw.log content via tool_result
#     observations. Same privacy posture as raw.log itself; uploaded
#     under the same data license (CC BY 4.0 per LICENSE-DATA).
#   - Volatility: regenerated every full sweep; corpus dataset is
#     intended to be stable across releases.
#
# Prereq: install the modern unified Hugging Face CLI:
#     pip install -U huggingface_hub
# Then authenticate (once, with a write token from
# https://huggingface.co/settings/tokens):
#     hf auth login
#
# Idempotent: re-running syncs the latest trajectories tree.
set -euo pipefail

DATASET_REPO="eyuansu71/logdx-ci-trajectories"
RELEASE_TAG="agent-trajectories-$(date +%Y-%m-%d)"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGING="$(mktemp -d)/logdx-trajectories-hf"

echo "==> Collecting trajectory dirs under $REPO_ROOT/results"
mapfile -t TRAJ_DIRS < <(
    find "$REPO_ROOT/results" -type d -name "__trajectories" 2>/dev/null
)
if [ ${#TRAJ_DIRS[@]} -eq 0 ]; then
    echo "ERROR: no trajectory dirs found. Run an agent sweep first," >&2
    echo "       e.g. tools/run_diagnosis.py --diagnoser-config ..." >&2
    echo "       which auto-creates results/**/__trajectories/." >&2
    exit 1
fi

echo "==> Staging at $STAGING"
mkdir -p "$STAGING"
TOTAL=0
for src in "${TRAJ_DIRS[@]}"; do
    # Mirror under STAGING with repo-relative path so users can map
    # back to "which split / which diagnoser / which method produced
    # this trajectory" without consulting the file contents.
    rel="${src#$REPO_ROOT/}"
    dst="$STAGING/$rel"
    mkdir -p "$dst"
    cp -p "$src"/*.json "$dst/" 2>/dev/null || true
    n=$(find "$dst" -name '*.json' | wc -l | tr -d ' ')
    TOTAL=$((TOTAL + n))
    echo "    $rel  ($n files)"
done

if [ $TOTAL -eq 0 ]; then
    echo "ERROR: trajectory dirs were present but contained no .json files." >&2
    exit 1
fi

cat > "$STAGING/README.md" <<EOF
---
license: cc-by-4.0
task_categories:
  - text-generation
language:
  - en
tags:
  - ci-failure-diagnosis
  - agent-trajectories
  - llm-tool-use
  - logdx-ci
pretty_name: "LogDx-CI agent-loop trajectories (companion to logdx-ci)"
size_categories:
  - 100K<n<1M
configs: []
---

# LogDx-CI agent-loop trajectories

Companion artifact to the [LogDx-CI benchmark](https://huggingface.co/datasets/eyuansu71/logdx-ci).
Each \`.json\` file is the full conversation transcript of one
agent-loop diagnosis run: the system prompt SHA, the agent config,
the complete \`messages\` list (assistant text, tool_use blocks,
tool_result observations), and the per-run \`agent_metadata\`
(iterations, tool calls, token usage).

## Layout

\`\`\`
results/<split>/diagnoses/<agent-diagnoser>/<method>__trajectories/<case>__<method>.json
\`\`\`

- \`<split>\`: dev / holdout / stress (and \`v2/*\`) — same split
  layout as the parent corpus dataset.
- \`<agent-diagnoser>\`: e.g. \`real-agent-v1\` (Sonnet 4.6 + 4 tools
  via OpenRouter Anthropic-passthrough).
- \`<method>\`: the context-reduction baseline whose context was
  fed to the agent as the first user turn (grep, tail, llm-summary-*,
  hybrid-*, etc.).

## Use

These files let downstream analysis answer questions the headline
diagnosis row can't, such as:

- Which tool calls did the agent issue, in what order, with what args?
- What did the tool_result observation actually contain on each turn?
- Where did the agent's reasoning latch onto the wrong root-cause
  category (visible in the assistant text blocks between tool uses)?

The structural breakdown of these trajectories is documented in
the [agent-trajectory-token-anatomy analysis](https://github.com/eyuansu62/LogDx/blob/main/docs/analysis/agent-trajectory-token-anatomy.md).

## Trust tier and privacy

Trajectories echo raw.log content via the \`tool_result\` blocks
the agent's \`grep\` / \`tail\` / \`view_log_lines\` / \`read_file\`
calls produce. Treat them as the same trust tier as the raw.log
inputs in the parent dataset, which were privacy-audited and
redacted per the LogDx-CI v1 / v2 protocol. The license is
identical to the parent dataset's data license (CC BY 4.0).

## Versioning

Each upload corresponds to one full agent_v1 sweep on this machine.
Filename collisions across uploads overwrite — the dataset reflects
the most recent sweep's view. Use \`git log\` of the
[main repo](https://github.com/eyuansu62/LogDx) to map a release
tag to the commit whose sweep produced the current files.
EOF

cp "$REPO_ROOT/LICENSE-DATA" "$STAGING/LICENSE"

echo "==> Staged total: $TOTAL trajectory files"
echo "==> Total size: $(du -sh "$STAGING" | cut -f1)"

echo "==> Creating HF dataset repo (idempotent via --exist-ok)"
hf repo create "$DATASET_REPO" --repo-type dataset --exist-ok

echo "==> Uploading to $DATASET_REPO ($RELEASE_TAG)"
hf upload \
    "$DATASET_REPO" \
    "$STAGING" . \
    --repo-type dataset \
    --commit-message "$RELEASE_TAG sync ($TOTAL files)"

echo ""
echo "==> Done. View at: https://huggingface.co/datasets/$DATASET_REPO"
echo "==> To verify download:"
echo "    hf download --repo-type dataset \\"
echo "        $DATASET_REPO --local-dir /tmp/logdx-trajectories-verify"
