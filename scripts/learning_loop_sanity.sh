#!/bin/bash
# Learning loop sanity - validate persistence, thresholds, and counts

set -e

ALLOW_EMPTY="${ALLOW_EMPTY:-0}"

if [ "$ALLOW_EMPTY" = "1" ]; then
  export PYTEST_CURRENT_TEST="${PYTEST_CURRENT_TEST:-1}"
  export PYTEST_MOUNT_ROOT="${PYTEST_MOUNT_ROOT:-/tmp/railway_test}"
fi

fail() {
  echo "ERROR: $1"
  exit 1
}

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

if [ -n "$MOUNT_ROOT" ]; then
  if [[ "$PREDICTIONS_FILE" != "$MOUNT_ROOT"* ]]; then
    fail "Predictions file not under mount root: $PREDICTIONS_FILE"
  fi
  if [[ "$WEIGHTS_FILE" != "$MOUNT_ROOT"* ]]; then
    fail "Weights file not under mount root: $WEIGHTS_FILE"
  fi
fi

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

# Verify predictions >= MIN_FINAL_SCORE and count entries
python3 - <<'PY'
import json
import os
from core.scoring_contract import MIN_FINAL_SCORE
from storage_paths import get_predictions_file

path = get_predictions_file()
if not os.path.exists(path):
    print("WARN: predictions file missing")
    raise SystemExit(0)

bad = 0
count = 0
with open(path, "r") as f:
    content = f.read().strip()
if not content:
    print("WARN: predictions file empty")
    raise SystemExit(0)

if content.lstrip().startswith("["):
    try:
        data = json.loads(content)
    except Exception as exc:
        raise SystemExit(f"predictions JSON invalid: {exc}")
    for item in data:
        count += 1
        score = item.get("final_score")
        if score is not None and score < MIN_FINAL_SCORE:
            bad += 1
else:
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        count += 1
        try:
            item = json.loads(line)
        except Exception as exc:
            raise SystemExit(f"predictions JSONL invalid: {exc}")
        score = item.get("final_score")
        if score is not None and score < MIN_FINAL_SCORE:
            bad += 1

print(f"predictions_count={count}")
if bad:
    raise SystemExit(f"Found {bad} picks with final_score < {MIN_FINAL_SCORE}")
PY

# Print last update times
if [ -f "$PREDICTIONS_FILE" ]; then
  echo "predictions_mtime=$(stat -f %m "$PREDICTIONS_FILE" 2>/dev/null || stat -c %Y "$PREDICTIONS_FILE")"
fi
if [ -f "$WEIGHTS_FILE" ]; then
  echo "weights_mtime=$(stat -f %m "$WEIGHTS_FILE" 2>/dev/null || stat -c %Y "$WEIGHTS_FILE")"
fi

echo "Learning loop sanity: PASS"
