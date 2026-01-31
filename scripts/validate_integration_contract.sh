#!/bin/bash
# Validate integration contract consistency
set -euo pipefail

echo "Validating integration contract..."

# Check 1: AUDIT_MAP matches contract (regenerate and diff)
echo "Check 1: AUDIT_MAP consistency..."
./scripts/generate_audit_map.sh > /dev/null 2>&1

if ! git diff --quiet docs/AUDIT_MAP.md; then
    echo "❌ FAIL: docs/AUDIT_MAP.md is out of sync with contract"
    echo "Run: ./scripts/generate_audit_map.sh"
    git diff docs/AUDIT_MAP.md
    exit 1
fi
echo "✅ AUDIT_MAP matches contract"

# Check 2: No duplicate integration keys
echo "Check 2: No duplicate integration keys..."
DUPES=$(python3 - << 'PY'
import sys
sys.path.insert(0, '.')
from core.integration_contract import INTEGRATIONS

keys = list(INTEGRATIONS.keys())
if len(keys) != len(set(keys)):
    print("Found duplicates")
    sys.exit(1)
print("No duplicates")
PY
)

if [ "$?" -ne 0 ]; then
    echo "❌ FAIL: Duplicate integration keys found"
    exit 1
fi
echo "✅ No duplicate keys"

# Check 3: Required integrations have env_vars and owner_modules
echo "Check 3: Required integrations complete..."
python3 - << 'PY'
import sys
sys.path.insert(0, '.')
from core.integration_contract import INTEGRATIONS, REQUIRED_INTEGRATIONS

for key in REQUIRED_INTEGRATIONS:
    integration = INTEGRATIONS[key]
    
    if not integration.get("env_vars"):
        print(f"❌ FAIL: Required integration '{key}' missing env_vars")
        sys.exit(1)
    
    if not integration.get("owner_modules"):
        print(f"❌ FAIL: Required integration '{key}' missing owner_modules")
        sys.exit(1)

print("✅ All required integrations complete")
PY

# Check 4: Weather is required and has no feature-flag disable
echo "Check 4: Weather integration rules..."
python3 - << 'PY'
import sys
sys.path.insert(0, '.')
from core.integration_contract import INTEGRATIONS, WEATHER_BANNED_STATUSES

weather = INTEGRATIONS.get("weather_api")
if not weather:
    print("❌ FAIL: weather_api not in contract")
    sys.exit(1)

if not weather.get("required"):
    print("❌ FAIL: weather_api must be required")
    sys.exit(1)

if not weather.get("relevance_gated"):
    print("❌ FAIL: weather_api must be relevance_gated")
    sys.exit(1)

banned = weather.get("banned_status_categories", [])
for status in WEATHER_BANNED_STATUSES:
    if status not in banned:
        print(f"❌ FAIL: weather_api missing banned status: {status}")
        sys.exit(1)

print("✅ Weather integration rules valid")
PY

# Check 5: BallDontLie env var alternates correct
echo "Check 5: BallDontLie env var alternates..."
python3 - << 'PY'
import sys
sys.path.insert(0, '.')
from core.integration_contract import INTEGRATIONS

bdl = INTEGRATIONS.get("balldontlie")
if not bdl:
    print("❌ FAIL: balldontlie not in contract")
    sys.exit(1)

env_vars = set(bdl.get("env_vars", []))
expected = {"BALLDONTLIE_API_KEY", "BDL_API_KEY"}

if env_vars != expected:
    print(f"❌ FAIL: BDL env_vars incorrect: {env_vars} != {expected}")
    sys.exit(1)

print("✅ BallDontLie env vars correct")
PY

echo ""
echo "✅ All integration contract validations passed"
