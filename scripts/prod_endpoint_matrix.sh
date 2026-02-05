#!/bin/bash
set -e

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
SPORTS="${SPORTS:-NBA NFL NHL MLB NCAAB}"
SKIP_NETWORK="${SKIP_NETWORK:-0}"

if [ "$SKIP_NETWORK" = "1" ]; then
  echo "SKIP_NETWORK=1 set; skipping prod endpoint matrix."
  exit 0
fi

if [ -z "$API_KEY" ]; then
  echo "API_KEY is required (or set SKIP_NETWORK=1)."
  exit 1
fi

python3 - <<'PY'
import json
import os
import sys
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

base_url = os.environ.get("BASE_URL", "https://web-production-7b2a.up.railway.app")
api_key = os.environ.get("API_KEY", "")
sports = os.environ.get("SPORTS", "NBA NFL NHL MLB NCAAB").split()

report = {
    "date_et": datetime.now().strftime("%Y-%m-%d"),
    "base_url": base_url,
    "status": "PASS",
    "errors": [],
    "checks": []
}

def fetch_json(path):
    url = f"{base_url}{path}"
    req = Request(url, headers={"X-API-Key": api_key})
    with urlopen(req, timeout=45) as resp:
        return resp.getcode(), json.loads(resp.read().decode("utf-8"))

def check_endpoint(name, path, required_keys=None):
    try:
        status, payload = fetch_json(path)
    except HTTPError as e:
        report["status"] = "FAIL"
        report["errors"].append(f"{name}: HTTP {e.code}")
        report["checks"].append({"name": name, "status": "FAIL", "detail": f"HTTP {e.code}"})
        return
    except URLError as e:
        report["status"] = "FAIL"
        report["errors"].append(f"{name}: {e}")
        report["checks"].append({"name": name, "status": "FAIL", "detail": str(e)})
        return

    missing = []
    if required_keys:
        for k in required_keys:
            if k not in payload:
                missing.append(k)
    if missing:
        report["status"] = "FAIL"
        report["checks"].append({"name": name, "status": "FAIL", "detail": f"missing {missing}"})
    else:
        report["checks"].append({"name": name, "status": "PASS", "detail": "ok"})

check_endpoint("/health", "/health", required_keys=["status", "ok"])
check_endpoint("/live/debug/integrations", "/live/debug/integrations")
check_endpoint("/live/grader/status", "/live/grader/status")

for sport in sports:
    check_endpoint(
        f"/live/grader/performance/{sport}",
        f"/live/grader/performance/{sport}",
    )
    check_endpoint(
        f"/live/best-bets/{sport}",
        f"/live/best-bets/{sport}?debug=1&max_games=1&max_props=1",
        required_keys=["props", "game_picks", "errors", "status"],
    )

# Write report
report_path = os.path.join("docs", "ENDPOINT_MATRIX_REPORT.md")
with open(report_path, "w") as f:
    f.write("# Endpoint Matrix Report\n\n")
    f.write(f"Date ET: {report['date_et']}\n\n")
    f.write(f"Base URL: {report['base_url']}\n\n")
    f.write(f"Status: {report['status']}\n\n")
    if report["errors"]:
        f.write("## Errors\n")
        for err in report["errors"]:
            f.write(f"- {err}\n")
        f.write("\n")
    f.write("## Checks\n")
    for check in report["checks"]:
        f.write(f"- {check['name']}: {check['status']} ({check['detail']})\n")

print(json.dumps(report, indent=2))
if report["status"] != "PASS":
    sys.exit(2)
PY
