#!/bin/bash
# Learning sanity check - local/offline validation of storage + JSON readability

set -e

ALLOW_EMPTY="${ALLOW_EMPTY:-0}"

fail() {
  echo "ERROR: $1"
  exit 1
}

# Resolve storage paths
RAILWAY_MOUNT="${RAILWAY_VOLUME_MOUNT_PATH:-}"
GRADER_MOUNT="${GRADER_MOUNT_ROOT:-}"

if [ -n "$RAILWAY_MOUNT" ] || [ -n "$GRADER_MOUNT" ]; then
  PREDICTIONS_FILE=$(python3 - <<'PY'
from storage_paths import get_predictions_file
print(get_predictions_file())
PY
)
  WEIGHTS_FILE=$(python3 - <<'PY'
from storage_paths import get_weights_file
print(get_weights_file())
PY
)
  MOUNT_ROOT=$(python3 - <<'PY'
from storage_paths import get_mount_root
print(get_mount_root())
PY
)
else
  # Local fallback - use data_dir
  PREDICTIONS_FILE=$(python3 - <<'PY'
from data_dir import GRADER_DATA_DIR
import os
print(os.path.join(GRADER_DATA_DIR, "grader", "predictions.jsonl"))
PY
)
  WEIGHTS_FILE=$(python3 - <<'PY'
from data_dir import GRADER_DATA
import os
print(os.path.join(GRADER_DATA, "weights.json"))
PY
)
  MOUNT_ROOT=""
fi

if [ -n "$MOUNT_ROOT" ]; then
  if [[ "$PREDICTIONS_FILE" != "$MOUNT_ROOT"* ]]; then
    fail "Predictions file not under mount root: $PREDICTIONS_FILE"
  fi
  if [[ "$WEIGHTS_FILE" != "$MOUNT_ROOT"* ]]; then
    fail "Weights file not under mount root: $WEIGHTS_FILE"
  fi
fi

# File presence checks
if [ ! -f "$PREDICTIONS_FILE" ]; then
  if [ "$ALLOW_EMPTY" = "1" ]; then
    echo "WARN: predictions file missing: $PREDICTIONS_FILE"
  else
    fail "Predictions file missing: $PREDICTIONS_FILE"
  fi
fi

if [ ! -f "$WEIGHTS_FILE" ]; then
  if [ "$ALLOW_EMPTY" = "1" ]; then
    echo "WARN: weights file missing: $WEIGHTS_FILE"
  else
    fail "Weights file missing: $WEIGHTS_FILE"
  fi
fi

# JSON readability checks
if [ -f "$PREDICTIONS_FILE" ]; then
  python3 - <<PY
import json
path = "$PREDICTIONS_FILE"
with open(path, "r") as f:
    content = f.read().strip()
if content:
    if content.startswith("["):
        json.loads(content)
    else:
        for i, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            json.loads(line)
print("OK: predictions JSON readable")
PY
fi

if [ -f "$WEIGHTS_FILE" ]; then
  python3 - <<PY
import json
path = "$WEIGHTS_FILE"
with open(path, "r") as f:
    json.load(f)
print("OK: weights JSON readable")
PY
fi

echo "Learning sanity check: PASS"
