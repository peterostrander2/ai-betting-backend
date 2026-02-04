#!/bin/bash
# Perf audit for best-bets debug timings

set -e

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
SPORTS="${SPORTS:-NBA NFL NHL MLB NCAAB}"
RUNS="${RUNS:-3}"
SKIP_NETWORK="${SKIP_NETWORK:-0}"

fail() {
  echo "ERROR: $1"
  exit 1
}

if [ "$SKIP_NETWORK" = "1" ]; then
  echo "SKIP_NETWORK=1 set; skipping perf audit."
  exit 0
fi

if [ -z "$API_KEY" ]; then
  fail "API_KEY is required for perf audit."
fi

python3 - <<'PY'
import json
import os
import statistics
import subprocess

base_url = os.environ.get("BASE_URL")
api_key = os.environ.get("API_KEY")
sports = os.environ.get("SPORTS", "NBA NFL NHL MLB NCAAB").split()
runs = int(os.environ.get("RUNS", "3"))

results = {}

for sport in sports:
    timings = []
    for _ in range(runs):
        url = f"{base_url}/live/best-bets/{sport}?debug=1&max_props=3&max_games=3"
        resp = subprocess.run(
            ["curl", "-sS", url, "-H", f"X-API-Key: {api_key}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if resp.returncode != 0:
            timings.append({"error": resp.stderr.strip() or "curl_failed"})
            continue
        try:
            data = json.loads(resp.stdout)
        except Exception:
            timings.append({"error": "invalid_json"})
            continue
        dbg = data.get("debug", {})
        timings.append(dbg.get("debug_timings", {}))

    # Aggregate p50/p95 for each timing key
    agg = {}
    keys = set(k for t in timings if isinstance(t, dict) for k in t.keys())
    for key in keys:
        vals = [t.get(key) for t in timings if isinstance(t, dict) and isinstance(t.get(key), (int, float))]
        if not vals:
            continue
        vals_sorted = sorted(vals)
        p50 = statistics.median(vals_sorted)
        p95 = vals_sorted[int(round(0.95 * (len(vals_sorted) - 1)))]
        agg[key] = {"p50": round(p50, 3), "p95": round(p95, 3), "samples": len(vals_sorted)}

    results[sport] = {
        "runs": runs,
        "timings": timings,
        "aggregate": agg,
    }

print(json.dumps(results, indent=2))
PY
