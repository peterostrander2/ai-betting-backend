#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$ROOT_DIR/.git/hooks"

if [ ! -d "$HOOK_DIR" ]; then
  echo "❌ .git/hooks not found. Are you in a git repo?"
  exit 1
fi

cp -f "$ROOT_DIR/scripts/pre-commit.template" "$HOOK_DIR/pre-commit"
chmod +x "$HOOK_DIR/pre-commit"

echo "✅ Installed pre-commit hook"
