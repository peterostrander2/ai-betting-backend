# Deployment Guide

> Deployment gates, verification steps, and rollback procedures.

---

## Pre-Deployment Checklist

### Gate 1: Syntax Validation
```bash
# MUST pass before deployment
python -m py_compile live_data_router.py
python -m py_compile esoteric_engine.py
python -m py_compile database.py
python -m py_compile daily_scheduler.py
```
**Failure**: Do not deploy. Fix syntax errors first.

### Gate 2: Import Verification
```bash
# Check for missing imports
python -c "import live_data_router" 2>&1 | grep -i "error"
python -c "import esoteric_engine" 2>&1 | grep -i "error"
```
**Failure**: Missing dependency. Add to requirements.txt or fix import.

### Gate 3: Invariant Check
```bash
# Run invariant verification (see INVARIANTS.md)
./check_invariants.sh
```
**Failure**: Fix invariant violations before deploying.

### Gate 4: Local Smoke Test
```bash
# Start local server
uvicorn live_data_router:app --port 8000 &

# Test endpoints
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/live/best-bets/NBA -H "X-API-Key: test" | jq '.game_picks.picks | length'

# Stop server
kill %1
```
**Failure**: Debug locally before deploying.

---

## Deployment Steps

### Step 1: Commit Changes
```bash
git add -A
git status  # Review changes
git commit -m "v17.7: Wire Hurst & Fibonacci to line history"
```

### Step 2: Push to Deploy
```bash
# Railway auto-deploys from main branch
git push origin main
```

### Step 3: Monitor Deployment
```bash
# Watch Railway logs
railway logs --follow

# Look for:
# - "Application startup complete"
# - No import errors
# - No database connection errors
```

### Step 4: Post-Deploy Verification
```bash
# Run verification script
./v17.7_verify.sh

# Or manual checks:
API_BASE="https://web-production-7b2a.up.railway.app"
API_KEY="your-key"

# Health check
curl -s "${API_BASE}/health" | jq .

# Endpoint test
curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | jq '.game_picks.picks | length'

# Check esoteric reasons populated
curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | unique'
```

---

## Post-Deployment Expectations

### New Signal Timeline

| Signal | When Active | How to Verify |
|--------|-------------|---------------|
| Hurst Exponent | ~5 hours | `jq 'select(contains("HURST"))'` |
| Fibonacci Retracement | ~24 hours | `jq 'select(contains("Fib Retracement"))'` |

**IMPORTANT**: New database-dependent signals will show "no data" initially. This is expected, NOT a bug.

### Data Accumulation Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| Line Snapshot | Every 30 min | Captures current lines for Hurst |
| Season Extremes | Daily 5 AM ET | Updates high/low for Fibonacci |

---

## Rollback Procedure

### Quick Rollback (< 5 minutes)
```bash
# Revert to previous commit
git revert HEAD
git push origin main

# Railway will auto-deploy the revert
```

### Full Rollback (specific version)
```bash
# Find last known good commit
git log --oneline -10

# Reset to that commit
git reset --hard <commit-hash>
git push origin main --force  # Use with caution
```

### Database Rollback
If database schema changes caused issues:
```sql
-- Revert schema changes (example)
-- DROP TABLE IF EXISTS new_table;
-- ALTER TABLE existing_table DROP COLUMN new_column;
```

---

## Monitoring

### Key Metrics to Watch

| Metric | Normal | Alert Threshold |
|--------|--------|-----------------|
| Response time (p95) | < 500ms | > 2000ms |
| Error rate | < 1% | > 5% |
| DB connections | < 10 | > 50 |

### Log Patterns to Watch

```bash
# Errors to investigate
railway logs | grep -i "error\|exception\|failed"

# Database issues
railway logs | grep -i "connection\|timeout\|pool"

# Signal issues
railway logs | grep -i "skipped\|no data"
```

### Health Check Endpoints

| Endpoint | Expected | Failure Action |
|----------|----------|----------------|
| `/health` | `{"status": "ok"}` | Check server startup |
| `/live/best-bets/NBA` | Returns picks array | Check API logic |

---

## Deployment History

| Version | Date | Deployer | Changes | Status |
|---------|------|----------|---------|--------|
| v20.20 | 2026-02-13 | - | Golden Run Gate + Hidden Tier Filter | Active |
| v17.7 | 2026-02-02 | - | Hurst & Fib wiring | Superseded |
| v17.6 | 2026-01-xx | - | Benford, line_snapshots | Superseded |
| v17.5 | 2026-01-xx | - | GLITCH foundation | Superseded |

### v20.20 Deploy Notes (Feb 13, 2026)

**Key Changes:**
1. **MONITOR/PASS filtered at output boundary** — Internal tiers never returned to API
2. **Dual thresholds: games 7.0, props 6.5** — Separate output thresholds by pick type
3. **Golden-run asserts contract, does not normalize known bugs** — Gate tests validate behavior, not mask bugs
4. **Runtime invariant check** — Belt-and-suspenders safety at output boundary
5. **Freeze baseline tagged** — `git tag v20.20-frozen` for rollback

**Validation Completed:**
- ✅ Build SHA `200d189` deployed and verified
- ✅ `/health` returns v20.20
- ✅ `/live/debug/integrations` shows 5 CRITICAL + 2 NOT_CONFIGURED (optional)
- ✅ `pytest tests/test_golden_run.py -v` — 27/27 tests pass
- ✅ Live endpoint spot-check: no MONITOR/PASS tiers, all games ≥7.0, valid tiers only
- ✅ Regression trap test: MONITOR tier picks correctly filtered
- ✅ Freeze verification script passes all hard gates

---

## Freeze Verification (v20.20-frozen)

**Run this after any deploy to verify contract compliance:**

```bash
# Quick version (uses script)
./scripts/freeze_verify.sh

# Or inline:
API_KEY="your-key"
BASE="https://web-production-7b2a.up.railway.app"
EXPECTED_SHA="200d189"  # Update to current deploy SHA

curl -s "$BASE/live/best-bets/NCAAB?debug=1" -H "X-API-Key: $API_KEY" | jq --arg expected_sha "$EXPECTED_SHA" '
  .debug as $d | .build_sha as $build |
  ($d.returned_pick_count_games // 0) as $games |
  ($d.returned_pick_count_props // 0) as $props |
  ($d.min_returned_final_score_games) as $min_games |
  ($d.min_returned_final_score_props) as $min_props |
  ($d.invariant_violations_dropped // 0) as $violations |
  ($d.hidden_tier_filtered_total // 0) as $hidden |
  [.game_picks.picks[].tier, .props.picks[].tier] as $tiers |
  ($violations == 0) as $gate_invariants |
  ($tiers | all(. == "TITANIUM_SMASH" or . == "GOLD_STAR" or . == "EDGE_LEAN")) as $gate_tiers |
  (if $games > 0 then ($min_games != null and $min_games >= 7.0) else true end) as $gate_games_score |
  (if $props > 0 then ($min_props != null and $min_props >= 6.5) else true end) as $gate_props_score |
  ($games + $props >= 1) as $smoke_non_empty |
  (if $expected_sha == "" then true else ($build | startswith($expected_sha)) end) as $gate_build_sha |
  {
    build_sha: $build,
    returned_games: $games, returned_props: $props,
    min_score_games: $min_games, min_score_props: $min_props,
    invariant_violations: $violations, hidden_tier_filtered: $hidden,
    tiers_returned: ($tiers | unique),
    gates: {
      invariants_ok: $gate_invariants, tiers_valid: $gate_tiers,
      games_score_ok: $gate_games_score, props_score_ok: $gate_props_score,
      smoke_valid: $smoke_non_empty, build_sha_ok: $gate_build_sha
    },
    hidden_tier_signal: (if $hidden == 0 then "clean_upstream" else "filter_active_investigate" end),
    PASS: ($gate_invariants and $gate_tiers and $gate_games_score and $gate_props_score and $smoke_non_empty and $gate_build_sha)
  }
'
```

**Hard Gates (all must be true for PASS):**

| Gate | Condition |
|------|-----------|
| `invariants_ok` | `invariant_violations_dropped == 0` |
| `tiers_valid` | every tier ∈ `{TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN}` |
| `games_score_ok` | if games > 0: `min_games != null AND >= 7.0` |
| `props_score_ok` | if props > 0: `min_props != null AND >= 6.5` |
| `smoke_valid` | `games + props >= 1` |
| `build_sha_ok` | if `EXPECTED_SHA` set: build matches |

**Diagnostic Signal (not a gate):**

| Signal | Meaning |
|--------|---------|
| `clean_upstream` | `hidden_tier_filtered_total == 0` — no hidden tiers above threshold |
| `filter_active_investigate` | `hidden_tier_filtered_total > 0` — filter working; investigate upstream |

**Rollback:** `git checkout v20.20-frozen`

---

## Emergency Contacts

| Role | Contact | When to Escalate |
|------|---------|------------------|
| On-call | - | > 5 min downtime |
| DB Admin | - | Connection pool issues |
| Platform | Railway Support | Infrastructure issues |

---

## Deployment Don'ts

1. **DON'T** deploy on Friday afternoon
2. **DON'T** deploy during peak hours (6-10 PM ET)
3. **DON'T** skip syntax validation
4. **DON'T** deploy multiple changes at once
5. **DON'T** ignore "no data" for new signals (it's expected)
6. **DON'T** rollback immediately when new signals show empty (wait 24h)
