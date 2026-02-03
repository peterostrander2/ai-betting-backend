#!/bin/bash
# Env drift scan - ensure env var usage matches docs/registry

set -e

ROOT_DIR="${ROOT_DIR:-.}"

fail() {
  echo "ERROR: $1"
  exit 1
}

python3 - <<'PY'
import os
import re
from pathlib import Path

root = Path(".")

# 1) Collect env vars used in Python via os.getenv / os.environ.get / os.environ["VAR"]
env_vars = set()
pattern_getenv = re.compile(r"os\.getenv\(\s*[\"']([A-Z0-9_]+)[\"']")
pattern_environ_get = re.compile(r"os\.environ\.get\(\s*[\"']([A-Z0-9_]+)[\"']")
pattern_environ_idx = re.compile(r"os\.environ\[\s*[\"']([A-Z0-9_]+)[\"']\s*\]")

for path in root.rglob("*.py"):
    # Skip large history/backup docs that may contain references
    if "SESSION_HISTORY" in path.name or "CLAUDE_FULL_BACKUP" in path.name:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue
    env_vars.update(pattern_getenv.findall(text))
    env_vars.update(pattern_environ_get.findall(text))
    env_vars.update(pattern_environ_idx.findall(text))

# 2) Collect env vars used in shell scripts via default expansion ${VAR:-...}
pattern_shell_default = re.compile(r"\$\{\s*([A-Z][A-Z0-9_]+)\s*:-")
for path in root.rglob("*.sh"):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue
    env_vars.update(pattern_shell_default.findall(text))

# 3) Collect env vars from docs/AUDIT_MAP.md

audit_map_path = root / "docs" / "AUDIT_MAP.md"
audit_envs = set()
if audit_map_path.exists():
    lines = audit_map_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        # Env Vars column is index 2 in the table: | Integration | Env Vars | Required | ...
        env_col = parts[2]
        audit_envs.update(re.findall(r"`([A-Z0-9_]{3,})`", env_col))

# 4) Collect env vars from integration_registry.py (includes RUNTIME_ENV_VARS list)
registry_path = root / "integration_registry.py"
registry_envs = set()
if registry_path.exists():
    text = registry_path.read_text(encoding="utf-8")
    registry_envs.update(re.findall(r"['\"]([A-Z][A-Z0-9_]{2,})['\"]", text))

# 5) Deprecated env vars allowed in docs (lines containing 'deprecated')
deprecated_envs = set()
if audit_map_path.exists():
    for line in audit_map_path.read_text(encoding="utf-8").splitlines():
        if "deprecated" in line.lower():
            deprecated_envs.update(re.findall(r"`([A-Z0-9_]{3,})`", line))

# 6) Compute drift
allowed_envs = audit_envs | registry_envs
missing_in_docs_or_registry = sorted(e for e in env_vars if e not in allowed_envs)
unused_in_docs = sorted(e for e in audit_envs if e not in env_vars and e not in deprecated_envs)

print("Env usage count:", len(env_vars))
print("Docs/registry env count:", len(allowed_envs))

if missing_in_docs_or_registry:
    print("\nMissing from docs/AUDIT_MAP.md or integration_registry.py:")
    for e in missing_in_docs_or_registry:
        print("-", e)

if unused_in_docs:
    print("\nEnv vars in docs/AUDIT_MAP.md but not used in code (no deprecated tag):")
    for e in unused_in_docs:
        print("-", e)

if missing_in_docs_or_registry or unused_in_docs:
    raise SystemExit(2)

print("Env drift scan: PASS")
PY
