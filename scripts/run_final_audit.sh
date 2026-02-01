#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${BACKEND_DIR:-$ROOT_DIR}"
FRONTEND_DIR="${FRONTEND_DIR:-}"

if [ -z "$FRONTEND_DIR" ]; then
  if [ -d "$ROOT_DIR/../bookie-member-app" ]; then
    FRONTEND_DIR="$ROOT_DIR/../bookie-member-app"
  elif [ -d "/Users/apple/bookie-member-app" ]; then
    FRONTEND_DIR="/Users/apple/bookie-member-app"
  elif [ -d "/Users/apple/Desktop/bookie-member-app" ]; then
    FRONTEND_DIR="/Users/apple/Desktop/bookie-member-app"
  fi
fi

if [ -z "$FRONTEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
  echo "Final audit skipped: frontend repo not found. Set FRONTEND_DIR to run."
  exit 0
fi

if [ ! -x "$ROOT_DIR/scripts/final_audit.sh" ]; then
  chmod +x "$ROOT_DIR/scripts/final_audit.sh" || true
fi

"$ROOT_DIR/scripts/final_audit.sh" "$BACKEND_DIR" "$FRONTEND_DIR"
