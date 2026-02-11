# PROJECT MAP

**AUTO-GENERATED** - Run `./scripts/generate_project_map.sh` to regenerate.

## Core Contracts (Single Sources of Truth)

| Contract | What It Defines |
|----------|-----------------|
| `core/scoring_contract.py` | Scoring thresholds, tier rules, engine weights |
| `core/integration_contract.py` | API integrations, env vars, validation rules |
| `core/time_et.py` | ET timezone logic, window bounds |
| `core/research_types.py` | ComponentStatus enum, source API constants |
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
6. **Engine audits:** Read `docs/MASTER_AUDIT_INDEX.md` → single-command verification

## Audit Infrastructure

| File | Purpose |
|------|---------|
| `docs/MASTER_AUDIT_INDEX.md` | Per-engine audit commands, invariants, proof fields |
| `docs/TRAINING_TRUTH_TABLE.md` | Engine 1 training contract |
| `docs/RESEARCH_TRUTH_TABLE.md` | Engine 2 research contract |
| `scripts/audit_training_store.py` | Engine 1 store audit |
| `scripts/engine2_research_audit.py` | Engine 2 anti-conflation audit |
| `scripts/engine2_research_audit.sh` | Engine 2 static + runtime checks |

## Debug Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/live/debug/training-status` | Engine 1 training health + telemetry |
| `/live/best-bets/{sport}?debug=1` | All engine breakdowns |
| `/live/debug/integrations` | Integration health |
| `/live/scheduler/status` | Scheduler jobs |
