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

### 3. ✅ Run Invariant Smoke Tests (BEFORE COMMIT)
```bash
# Run production sanity check
./scripts/prod_sanity_check.sh

# Verify critical invariants with curls
curl https://web-production-7b2a.up.railway.app/live/debug/time \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.et_window'

curl https://web-production-7b2a.up.railway.app/live/debug/integrations \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.configured | length'

curl https://web-production-7b2a.up.railway.app/live/grader/status \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.storage'
```

**Expected Results:**
- ET window: `[00:01:00 ET, 00:00:00 next day)` (half-open interval)
- Integrations: All required APIs configured
- Storage: `/app/grader_data` with pick counts > 0

### 4. ✅ Persistence + Restart Proof (If Storage/Grading/Scheduler Changed)
```bash
# 1. Generate picks
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.count'

# 2. Check storage count
BEFORE_COUNT=$(curl "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.total_predictions')

# 3. Restart container in Railway dashboard

# 4. Verify same count after restart
AFTER_COUNT=$(curl "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.total_predictions')

# Assert: BEFORE_COUNT == AFTER_COUNT
```

### 5. ✅ Commit BOTH Code + Docs Together
```bash
git add <code_files> <doc_files>
git commit -m "fix: description + docs: update invariants"
git push origin main
```

**UNSKIPPABLE RULE:** If you changed any of these files, you MUST update paired docs:
- `core/time_et.py` → CLAUDE.md INVARIANT 3
- `grader_store.py` / `storage_paths.py` → CLAUDE.md INVARIANT 1
- `core/titanium.py` → CLAUDE.md INVARIANT 2
- `integration_registry.py` → CLAUDE.md Integration section
- Any scoring module → SCORING_LOGIC.md

### 6. ✅ Verify on Railway (AFTER PUSH)
- [ ] Railway deployment succeeded
- [ ] Run health check: `curl https://web-production-7b2a.up.railway.app/health`
- [ ] Re-run invariant smoke tests (from step 3)

### 7. ✅ Rollback Rule (If Invariants Fail After Deploy)
**If Railway deploy passes BUT invariants fail:**
- [ ] **ROLLBACK IMMEDIATELY** (revert commit)
- [ ] Do NOT "hotfix forward" without updating docs + tests
- [ ] Fix locally with docs, test, then redeploy

---

## Common Mistakes (DON'T DO THESE):

❌ **Fix code, forget docs** → Next session, bug comes back
❌ **Update docs, forget code** → Docs lie, system broken
❌ **Commit separately** → Code and docs out of sync
❌ **Skip smoke tests** → Deploy broken changes
❌ **Hotfix without docs** → Perpetuate the cycle

✅ **ALWAYS: Code + Docs + Tests → Commit together**

---

## Quick Reference: What Goes Where

| Change Type | Update These Files |
|-------------|-------------------|
| ET window [00:01:00 ET, 00:00:00 next day) | CLAUDE.md INVARIANT 3 |
| Storage paths `/app/grader_data` | CLAUDE.md INVARIANT 1 |
| Titanium rule (3/4 engines ≥8.0) | CLAUDE.md INVARIANT 2 |
| Scoring algorithm, engine weights | SCORING_LOGIC.md |
| New file/module added | PROJECT_MAP.md |
| API endpoint added/changed | CLAUDE.md API section |
| Bug fix (no invariant change) | Code only (no doc update needed) |

---

## Canonical Invariants (NEVER BREAK THESE)

### INVARIANT 1: Storage Persistence
- **Path:** `/app/grader_data` (Railway volume)
- **Structure:** `/app/grader_data/grader/predictions.jsonl`
- **Test:** Pick count survives container restart

### INVARIANT 2: Titanium 3-of-4 Rule
- **Rule:** ≥3 of 4 engines ≥8.0 (STRICT)
- **File:** `core/titanium.py` (single source of truth)
- **Test:** Verify boundary (3/4 at 8.0 = TRUE, 2/4 = FALSE)

### INVARIANT 3: ET Today-Only Window
- **Window:** `[00:01:00 ET, 00:00:00 next day)` (half-open)
- **File:** `core/time_et.py` (single source of truth)
- **Test:** Games at 00:00:30 EXCLUDED, 00:01:00 INCLUDED

### INVARIANT 4: 4-Engine Scoring (No Double Counting)
- **Rule:** NO double-counting across engines
- **Example:** Sharp money ONLY in Research (not Jarvis)

### INVARIANT 6: Minimum Output Threshold
- **Threshold:** final_score ≥ 6.5
- **Location:** `live_data_router.py` line ~3540

---

## Example: ET Window Fix (CORRECT WAY)
```bash
# 1. Fix core/time_et.py
#    Change: time(0, 0, 0) → time(0, 1, 0)

# 2. Update CLAUDE.md INVARIANT 3
#    Verify: Says [00:01:00 ET, 00:00:00 next day)

# 3. Run smoke test
curl "https://web-production-7b2a.up.railway.app/live/debug/time" \
  -H "X-API-Key: KEY" | jq '.et_window.start'
# Should show: "2026-01-30T00:01:00-05:00" (not 00:00:00)

# 4. Commit together
git add core/time_et.py CLAUDE.md
git commit -m "fix: ET window start 00:01:00 + docs: update INVARIANT 3"
git push origin main

# 5. Verify on Railway
# Wait for deploy, re-run smoke test, confirm 00:01:00
```

---

## TL;DR (Too Long; Didn't Read)

1. **Code + Docs MUST match** - Update both, commit together
2. **Run smoke tests BEFORE commit** - Catch breaks early
3. **Test persistence if storage changed** - Verify restart proof
4. **Rollback if invariants fail** - Don't hotfix forward without docs
5. **Follow this checklist EVERY TIME** - No exceptions

**Print this file. Put it next to your computer. Follow it every single time.**
