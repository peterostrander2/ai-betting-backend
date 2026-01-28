# Auto-Grader Fix - Deployment Guide

## Changes Made

### 1. Added `commence_time_iso` Field
**Files modified:** `pick_logger.py`, `live_data_router.py`

- Added `commence_time_iso` field to `PublishedPick` dataclass (ISO timestamp)
- Kept `game_start_time_et` for human-readable display (e.g., "7:30 PM ET")
- Both fields now populated when picks are created in `/live/best-bets/{sport}`

**Why:** Avoids parsing issues when grading picks - ISO timestamps are unambiguous and programmatic.

### 2. Fixed `/live/grader/status` Endpoint
**File modified:** `live_data_router.py`

**Before:** Showed auto_grader predictions (weight learning system, separate from pick grading)
**After:** Shows pick_logger stats with:
- `predictions_logged`: Count of picks logged today
- `pending_to_grade`: Count of ungraded picks
- `graded_today`: Count of graded picks
- `last_run_at`: Last auto-grade run timestamp
- `last_errors`: Recent grading errors
- `weight_learning`: Separate section for auto_grader weight learning stats

**Why:** The user needs to see actual published picks that need grading, not the weight learning system.

### 3. Created `/live/smoke-test/alert-status` Endpoint
**File modified:** `live_data_router.py`

New endpoint for frontend monitors that returns:
- `status`: "healthy", "warning", "degraded", or "critical"
- `pick_logger`: Availability and picks logged today
- `auto_grader`: Availability and last run time
- `api_keys_configured`: Whether ODDS_API_KEY and PLAYBOOK_API_KEY are set
- `alerts`: Array of alert messages (e.g., "Auto-grader hasn't run in 2+ hours")

**Why:** Provides a single endpoint for monitoring system health.

### 4. Added Railway Volume Mount
**Files modified:** `railway.toml`, `pick_logger.py`, `auto_grader.py`

**railway.toml:**
- Added `[[deploy.volumeMounts]]` with mountPath `/data`

**pick_logger.py & auto_grader.py:**
- Added environment variable support: `RAILWAY_VOLUME_MOUNT_PATH`
- If set, uses `/data/pick_logs`, `/data/grader_data`, `/data/graded_picks`
- Otherwise uses local paths `./pick_logs`, `./grader_data`, `./graded_picks` (dev mode)

**Why:** Prevents data loss on Railway deploys and restarts.

---

## Deployment Steps

### Step 1: Create Railway Volume
1. Go to your Railway project dashboard
2. Navigate to Settings → Volumes
3. Click "New Volume"
4. Set mount path: `/data`
5. Set size: 1GB (or as needed)
6. Click "Create Volume"

### Step 2: Set Environment Variable
1. Go to Settings → Environment Variables
2. Add new variable:
   - Name: `RAILWAY_VOLUME_MOUNT_PATH`
   - Value: `/data`
3. Save changes

### Step 3: Deploy the Changes
1. Commit all changes to git:
   ```bash
   git add .
   git commit -m "fix: Auto-grader pick logging and Railway volume persistence"
   git push origin main
   ```
2. Railway will auto-deploy the changes
3. Wait for health check to pass

### Step 4: Verify the Fix
After deployment, test the following endpoints:

**A. Check grader status:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: YOUR_KEY"
```
Expected output:
```json
{
  "available": true,
  "timestamp": "2026-01-28T...",
  "pick_logger": {
    "predictions_logged": 0,
    "pending_to_grade": 0,
    "graded_today": 0,
    "storage_path": "/data/pick_logs",
    "date": "2026-01-28"
  },
  "last_run_at": null,
  "last_errors": [],
  "weight_learning": {
    "available": true,
    "supported_sports": ["NBA", "NFL", "MLB", "NHL", "NCAAB"],
    "predictions_logged": 1,
    "weights_loaded": true,
    "storage_path": "/data/grader_data"
  }
}
```

**B. Check smoke test endpoint:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/smoke-test/alert-status" \
  -H "X-API-Key: YOUR_KEY"
```
Expected output:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-28T...",
  "alerts": [],
  "pick_logger": {
    "available": true,
    "picks_logged_today": 0
  },
  "auto_grader": {
    "available": true,
    "last_run_at": "2026-01-28T..."
  },
  "api_keys_configured": true
}
```

**C. Generate picks and verify logging:**
```bash
# Call best-bets endpoint (generates and logs picks)
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba" \
  -H "X-API-Key: YOUR_KEY" > best_bets_response.json

# Check predictions_logged increased
curl "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: YOUR_KEY"
```
Expected: `predictions_logged` should be > 0 (e.g., 10-20 picks logged)

**D. Trigger manual grade run:**
```bash
# Wait for games to complete, then trigger grading
curl -X POST "https://web-production-7b2a.up.railway.app/live/grader/manual-grade" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json"
```

Or use the scheduled auto-grade that runs every 30 minutes. Check logs:
```bash
railway logs
```
Look for:
- `"Running scheduled auto-grade..."`
- `"Found X pending picks to grade"`
- `"Graded X picks"`

---

## Architecture Changes Summary

### Two Separate Systems (Now Properly Separated)

**1. Pick Logger (`pick_logs/`):**
- Stores published picks that go to the community
- Used by auto-grader to grade picks after games complete
- Storage: `/data/pick_logs/picks_YYYY-MM-DD.jsonl`
- Fields: Full PublishedPick with all engine scores, tier, canonical IDs, etc.

**2. Auto-Grader Weight Learning (`grader_data/`):**
- Learns and adjusts prediction weights based on accuracy
- Storage: `/data/grader_data/predictions.json`, `/data/grader_data/weights.json`
- Fields: Simple PredictionRecord with predicted_value, actual_value, adjustments
- Runs daily audit at 6 AM ET to adjust weights

### Auto-Grade Flow

1. **Pick Creation** (`/live/best-bets/{sport}`):
   - Generates picks with scores >= 6.5
   - Logs to pick_logger → `/data/pick_logs/picks_YYYY-MM-DD.jsonl`
   - Each pick has `commence_time_iso` for programmatic use
   - Each pick has canonical IDs for grading

2. **Scheduled Auto-Grade** (every 30 minutes):
   - `result_fetcher.scheduled_auto_grade()` runs
   - Loads pending picks from pick_logger via `get_picks_for_date()`
   - Fetches game results from Odds API
   - Fetches player stats from BallDontLie (NBA) / Playbook
   - Grades each pick: WIN / LOSS / PUSH
   - Updates pick_logger with results

3. **Status Monitoring**:
   - `/live/grader/status` shows pick_logger stats + last run info
   - `/live/smoke-test/alert-status` shows overall system health
   - Both endpoints accessible via X-API-Key header

---

## Troubleshooting

### Issue: `predictions_logged` still shows 0 after calling `/best-bets`

**Check:**
1. Are picks actually being generated? Check response has `props` and `game_picks` arrays
2. Is PICK_LOGGER_AVAILABLE = true? Check logs for import errors
3. Are picks being filtered out? Check logs for "PICK_LOGGER: Logged X picks"

**Debug:**
```bash
# SSH into Railway container
railway run bash

# Check if pick files exist
ls -la /data/pick_logs/
cat /data/pick_logs/picks_$(date +%Y-%m-%d).jsonl | wc -l
```

### Issue: Auto-grader runs but grades 0 picks

**Check:**
1. Are there any picks logged for today? Check `/live/grader/status`
2. Are games completed? Check game_status on picks
3. Are canonical IDs populated? Check pick JSON for `canonical_event_id` and `canonical_player_id`

**Debug:**
```bash
# Check scheduler logs
railway logs --filter "scheduled auto-grade"
railway logs --filter "Found X pending picks"
```

### Issue: Data lost after deploy

**Check:**
1. Is Railway volume created? Check project Settings → Volumes
2. Is `RAILWAY_VOLUME_MOUNT_PATH=/data` set? Check Environment Variables
3. Are storage paths using volume? Check logs for "storage_path": "/data/..."

---

## Next Steps

After verifying the fix works:

1. **Monitor for 24 hours** - Ensure picks are logged and graded consistently
2. **Check daily audit** - Runs at 6 AM ET, adjusts weights based on yesterday's results
3. **Review daily report** - Call `/live/grader/daily-report` each morning for community post
4. **Set up alerting** - Use `/live/smoke-test/alert-status` in monitoring dashboard

---

## Files Changed

| File | Change |
|------|--------|
| `pick_logger.py` | Added `commence_time_iso` field, Railway volume support |
| `live_data_router.py` | Fixed `/grader/status`, added `/smoke-test/alert-status`, populate `commence_time_iso` |
| `auto_grader.py` | Railway volume support |
| `railway.toml` | Added volume mount configuration |

---

## Environment Variables Required

| Variable | Value | Purpose |
|----------|-------|---------|
| `RAILWAY_VOLUME_MOUNT_PATH` | `/data` | Points storage to persistent volume |
| `ODDS_API_KEY` | Your key | Game results and odds |
| `PLAYBOOK_API_KEY` | Your key | Player stats and splits |
| `API_AUTH_KEY` | Your key | API authentication |

---

## Contact

For issues or questions about this deployment, check:
- Railway logs: `railway logs`
- Health check: `/health`
- Grader status: `/live/grader/status`
- Alert status: `/live/smoke-test/alert-status`
