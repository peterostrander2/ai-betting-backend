# Commit Checklist - Follow EVERY Time

## Before You Push ANY Fix:

### 1. ✅ Fix the Code
- [ ] Made the code change
- [ ] Tested locally (if possible)

### 2. ✅ Update Documentation (CRITICAL - DON'T SKIP)
- [ ] Does this change an **INVARIANT**? → Update CLAUDE.md
- [ ] Does this change **how scoring works**? → Update SCORING_LOGIC.md
- [ ] Does this add a **new file/module**? → Update PROJECT_MAP.md
- [ ] Does this change **API endpoints**? → Update CLAUDE.md API section

### 3. ✅ Run Hard Invariants Smoke (BEFORE PUSH)

```bash
# Run prod sanity check
./scripts/prod_sanity_check.sh

# Then verify canonical invariants:
# ET Window (must show 00:01:00 start, bounds_valid: true)
curl -s "$BASE_URL/live/debug/time" -H "X-API-Key: $API_KEY" | jq '{start: .et_day_start_iso, valid: .bounds_valid}'

# Integrations (all required keys validated)
curl -s "$BASE_URL/live/debug/integrations?quick=true" -H "X-API-Key: $API_KEY" | jq '.configured_count'

# Grader Status (persistent store + counts)
curl -s "$BASE_URL/live/grader/status" -H "X-API-Key: $API_KEY" | jq '{path: .storage_path, count: .predictions_logged}'
```

**If ANY check fails → DO NOT PUSH. Fix first.**

### 4. ✅ Persistence + Restart Proof (For Storage/Grading/Scheduler Changes)

If you touched `grader_store.py`, `storage_paths.py`, `data_dir.py`, or scheduler:

- [ ] Generate picks → Confirm stored on `RAILWAY_VOLUME_MOUNT_PATH`
- [ ] Restart container (Railway redeploy)
- [ ] Confirm same pick count after restart
- [ ] Verify `is_mountpoint: true` in `/internal/storage/health`

### 5. ✅ Commit BOTH Together
```bash
git add <code_files>
git add <doc_files>
git commit -m "fix: description + docs: update invariants"
git push origin main
```

### 6. ✅ Verify on Railway
- [ ] Check Railway logs (no errors)
- [ ] Run health check: `curl https://web-production-7b2a.up.railway.app/health`
- [ ] Re-run invariants smoke (Step 3) against production

---

## Rollback Rule

**If Railway deploy passes but invariants fail:**
1. **ROLLBACK IMMEDIATELY** - `git revert HEAD && git push`
2. Do NOT "hotfix forward" without updating docs + tests
3. Fix properly, then redeploy

---

## Common Mistakes (DON'T DO THESE):

❌ **Fix code, forget docs** → Next session, bug comes back
❌ **Update docs, forget code** → Docs lie, system broken
❌ **Commit separately** → Code and docs out of sync
❌ **Skip invariants smoke** → Broken code reaches prod

✅ **ALWAYS commit code + docs together**
✅ **ALWAYS run smoke before push**

---

## Quick Reference: What Goes Where

| Change Type | Update These Files |
|-------------|-------------------|
| ET window, storage paths, titanium rule | CLAUDE.md (Master Invariants) |
| Scoring algorithm, engine weights | SCORING_LOGIC.md |
| New file/module added | PROJECT_MAP.md |
| API endpoint added/changed | CLAUDE.md (API section) |
| Bug fix (no invariant change) | Code only (no doc update needed) |

---

## CI/Commit Hook Enforcement (Recommended)

Add a GitHub Action or pre-push hook that enforces:

**If these files change:**
- `core/time_et.py`
- `grader_store.py`
- `storage_paths.py`
- `integration_registry.py`
- `tiering.py`
- `core/titanium.py`

**Then these docs MUST also change:**
- `CLAUDE.md`
- `docs/AUDIT_MAP.md` (if grading-related)

```yaml
# .github/workflows/doc-sync-check.yml
name: Doc Sync Check
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check invariant files have paired doc updates
        run: |
          INVARIANT_FILES="core/time_et.py grader_store.py storage_paths.py integration_registry.py"
          for f in $INVARIANT_FILES; do
            if git diff --name-only origin/main | grep -q "$f"; then
              if ! git diff --name-only origin/main | grep -q "CLAUDE.md"; then
                echo "ERROR: $f changed but CLAUDE.md not updated"
                exit 1
              fi
            fi
          done
```

---

## Example: ET Window Fix

**CANONICAL ET SLATE WINDOW (Single Source of Truth):**
```
Start: 00:01:00 ET (inclusive)
End:   00:00:00 ET next day (exclusive)
Interval: [00:01:00, 00:00:00 next day)
```

**Bad Way:**
```bash
# Fix core/time_et.py
git commit -m "fix: ET window"
git push
# Docs still say 00:00:00 → bug comes back next session
```

**Good Way:**
```bash
# 1. Fix core/time_et.py to use 00:01:00
# 2. Update CLAUDE.md INVARIANT 3 to show [00:01:00, 00:00:00 next day)
# 3. Run smoke test
curl -s "$BASE_URL/live/debug/time" -H "X-API-Key: $API_KEY" | jq '.bounds_valid'
# Must return: true

# 4. Commit together
git add core/time_et.py CLAUDE.md
git commit -m "fix: ET window [00:01:00, 00:00:00) + docs: update INVARIANT 3"
git push origin main

# 5. Verify prod after deploy
curl -s "https://web-production-7b2a.up.railway.app/live/debug/time" \
  -H "X-API-Key: $API_KEY" | jq '{start: .et_day_start_iso, valid: .bounds_valid}'
# Must show: {"start": "2026-01-29T00:01:00-05:00", "valid": true}
```

---

## TL;DR

1. **Code + docs MUST match** - Update both, commit together
2. **Run smoke before push** - Invariants check prevents broken deploys
3. **Restart-proof storage changes** - Verify persistence survives redeploy
4. **Rollback if invariants fail** - Never hotfix forward without docs + tests

**If Railway deploy passes but invariants fail, ROLLBACK IMMEDIATELY.**
