#!/usr/bin/env bash
set -euo pipefail

# Quick checkpoint commit to free up Claude Code context

TIMESTAMP=$(date +"%Y-%m-%d %H:%M")

echo "Creating checkpoint commit..."

# Stage all changes
git add -A

# Check if there are changes
if [ -z "$(git status --porcelain)" ]; then
  echo "No changes to commit"
  exit 0
fi

# Create checkpoint commit
git commit -m "checkpoint: $TIMESTAMP

Auto-checkpoint to free Claude Code context window.
Work in progress - may be rebased/squashed later."

echo "Checkpoint created"
echo ""
echo "To continue in fresh context:"
echo "  1. Tell Claude: 'checkpoint committed, continue from here'"
echo "  2. Or use /compact in Claude Code"
echo ""
echo "To push manually:"
echo "  git push origin main"
