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
| v17.7 | 2026-02-02 | - | Hurst & Fib wiring | Pending |
| v17.6 | 2026-01-xx | - | Benford, line_snapshots | Active |
| v17.5 | 2026-01-xx | - | GLITCH foundation | Superseded |

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
