# Lessons Learned - AI Betting Backend

> Self-improvement loop: Document mistakes to prevent repetition

---

## Critical Incidents

### 1. Storage Path Blocker Crash (Jan 28-29, 2026)

**What happened:**
- Added code to block all `/app/*` paths in `data_dir.py`
- Assumed `/data` was ephemeral storage
- Did NOT verify storage health before making changes
- Did NOT read CLAUDE.md Storage Configuration section

**Impact:** Production crashed with 502 errors, 2 minutes downtime

**Root cause:** Misunderstanding that `/data` IS the Railway persistent volume (verified with `os.path.ismount() = True`)

**Fix:** Removed path blocker, unified to `RAILWAY_VOLUME_MOUNT_PATH`

**Lesson:**
- ALWAYS verify production health BEFORE assuming paths are wrong
- `/data` is NOT ephemeral on Railway - it's a mounted 5GB persistent volume
- NEVER add path validation that blocks legitimate storage paths

---

### 2. filter_date Bug (Jan 29, 2026)

**What happened:**
- `filter_date` showing "ERROR" in debug output
- Caused "cannot access local variable" error at line 2149

**Root cause:** Redundant `from core.time_et import et_day_bounds` at lines 3779 and 5029 made Python treat it as local variable

**Fix:** Removed redundant local imports, now uses top-level import consistently

**Lesson:**
- Avoid duplicate imports of the same function at different scopes
- Python's scoping rules can cause subtle bugs with local vs global references
- Check `/live/debug/time` to verify ET timezone consistency

---

## Architectural Rules (Learned the Hard Way)

### Storage Architecture
- ALL storage MUST use `RAILWAY_VOLUME_MOUNT_PATH` environment variable
- Both `storage_paths.py` AND `data_dir.py` must use this
- Picks: `/data/grader/predictions.jsonl` (high-frequency)
- Weights: `/data/grader_data/weights.json` (low-frequency)
- Audits: `/data/audit_logs/audit_{date}.json`

### ET Timezone Filtering
- ALWAYS filter Odds API events to TODAY only in ET timezone
- Single source of truth: `core/time_et.py`
- NEVER use `datetime.now()` or `utcnow()` for slate filtering
- NEVER use pytz - only `zoneinfo` allowed
- Apply filter BEFORE scoring, not after

### Titanium Rule
- `titanium_triggered=true` ONLY when >= 3 of 4 engines >= 8.0
- 1/4 or 2/4 is ALWAYS false, even if scores are high
- Use `core/titanium.py` as single source of truth

### Response Contracts
- `/live/best-bets/{sport}` MUST always return `props`, `game_picks`, `meta` keys
- Empty arrays are valid, missing keys are not
- NHL often has 0 props - frontend must never get KeyError

---

## Pre-Deploy Checklist (From Past Failures)

Before ANY storage/autograder/scheduler change:

1. Read CLAUDE.md Storage Configuration section
2. Verify production health with `/internal/storage/health`
3. Check that `RAILWAY_VOLUME_MOUNT_PATH` is used everywhere
4. Run `scripts/prod_sanity_check.sh`
5. Verify `filter_date` matches `et_date` in debug output

---

## Code Review Red Flags

Watch for these patterns that have caused production issues:

- [ ] Path validation that blocks `/app/*` or `/data/*`
- [ ] Duplicate imports of `time_et` functions
- [ ] Direct use of `datetime.now()` for ET calculations
- [ ] Missing keys in API response structures
- [ ] Titanium logic duplicated instead of using `core/titanium.py`
- [ ] Storage paths hardcoded instead of using env vars

---

### 3. Anti-Drift Architecture (Feb 2026)

**Problem:** Risk of duplicate work, forgotten canonical sources, frontend/backend drift.

**Solution:** Created complete anti-drift system mirroring scoring contract pattern:
- `core/integration_contract.py` - Canonical source for all 14 integrations
- `docs/AUDIT_MAP.md` - Auto-generated (never edit manually)
- `scripts/validate_integration_contract.sh` - Blocks drift before commit
- `docs/MASTER_INDEX.md` - Single routing entry point

**Lesson:** When you build one contract system that works (scoring), immediately apply the same pattern to other sources of truth (integrations). Don't wait for drift to happen.

**Rule:** Any time there's a "where should this live?" question, the answer should be in MASTER_INDEX.md routing. If it's not, add it.

---

## Template: Adding New Lessons

```markdown
### [Title] ([Date])

**What happened:**
- Describe the incident

**Impact:** User-facing impact

**Root cause:** Technical explanation

**Fix:** What was changed

**Lesson:**
- Key takeaway for future development
```
