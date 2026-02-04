#!/bin/bash
# Prod go/no-go gate - run all audits and tests

set -e

SKIP_NETWORK="${SKIP_NETWORK:-0}"
SKIP_PYTEST="${SKIP_PYTEST:-0}"
ALLOW_EMPTY="${ALLOW_EMPTY:-0}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"

ET_DATE=$(python3 - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
print(datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d"))
PY
)

mkdir -p "$ARTIFACTS_DIR"

run() {
  echo "Running: $*"
  "$@"
}

run_and_capture() {
  local name="$1"
  shift
  local out_txt="$ARTIFACTS_DIR/${name}_${ET_DATE}_ET.txt"
  local status="PASS"
  if "$@" >"$out_txt" 2>&1; then
    status="PASS"
  else
    status="FAIL"
  fi
  python3 - <<PY >"$ARTIFACTS_DIR/${name}_${ET_DATE}_ET.json"
import json
from pathlib import Path
data = {
  "name": "$name",
  "date_et": "$ET_DATE",
  "status": "$status",
  "output": Path("$out_txt").read_text(encoding="utf-8", errors="replace"),
}
print(json.dumps(data, indent=2))
PY
  if [ "$status" != "PASS" ]; then
    exit 1
  fi
}

run_and_capture "option_a_drift" bash scripts/option_a_drift_scan.sh
run_and_capture "audit_drift" bash scripts/audit_drift_scan.sh
run_and_capture "env_drift" bash scripts/env_drift_scan.sh
run_and_capture "docs_contract" bash scripts/docs_contract_scan.sh
run_and_capture "learning_sanity" env ALLOW_EMPTY="$ALLOW_EMPTY" bash scripts/learning_sanity_check.sh
run_and_capture "learning_loop" env ALLOW_EMPTY="$ALLOW_EMPTY" bash scripts/learning_loop_sanity.sh

if [ "$SKIP_NETWORK" != "1" ]; then
  run_and_capture "endpoint_matrix" bash scripts/endpoint_matrix_sanity.sh
  run_and_capture "api_proof" bash scripts/api_proof_check.sh
  run_and_capture "live_sanity" bash scripts/live_sanity_check.sh
  run_and_capture "perf_audit_best_bets" bash scripts/perf_audit_best_bets.sh
else
  echo "SKIP_NETWORK=1 set; skipping networked checks."
  python3 - <<PY >"$ARTIFACTS_DIR/endpoint_matrix_${ET_DATE}_ET.json"
import json
print(json.dumps({
  "name": "endpoint_matrix",
  "date_et": "$ET_DATE",
  "status": "SKIPPED",
  "reason": "SKIP_NETWORK=1"
}, indent=2))
PY
fi

if [ "$SKIP_PYTEST" != "1" ]; then
  run_and_capture "pytest" python3 -m pytest -q
else
  echo "SKIP_PYTEST=1 set; skipping pytest."
fi

echo "Prod go/no-go: PASS" | tee "$ARTIFACTS_DIR/prod_go_nogo_${ET_DATE}_ET.txt"
