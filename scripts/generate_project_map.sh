#!/usr/bin/env bash
set -euo pipefail

OUTPUT="docs/PROJECT_MAP.md"
mkdir -p docs

cat > "$OUTPUT" << 'HEADER'
# PROJECT MAP

**AUTO-GENERATED** - Run `./scripts/generate_project_map.sh` to regenerate.

## Core Contracts (Single Sources of Truth)

| Contract | What It Defines |
|----------|-----------------|
| `core/scoring_contract.py` | Scoring thresholds, tier rules, engine weights |
| `core/integration_contract.py` | API integrations, env vars, validation rules |
| `core/time_et.py` | ET timezone logic, window bounds |
| `storage_paths.py` + `data_dir.py` | Persistence paths under RAILWAY_VOLUME_MOUNT_PATH |

## Key Directories

- `core/` - Canonical contracts (single sources of truth)
- `docs/` - Documentation (MASTER_INDEX, AUDIT_MAP, etc.)
- `scripts/` - Validators, CI checks, generators
- `tasks/` - lessons.md (self-improvement), todo.md (planning)

## Entry Points

1. **New sessions:** Read `SESSION_START.md`
2. **Making changes:** Read `docs/MASTER_INDEX.md` → route to canonical file
3. **When things break:** Read `docs/RECOVERY.md`
4. **Before committing:** Follow `COMMIT_CHECKLIST.md`
5. **After user corrections:** Update `tasks/lessons.md`
HEADER

echo "✅ Generated $OUTPUT"
