# CLAUDE.md - Project Instructions for AI Assistants

## User Environment
- **OS:** Mac
- **Terminal:** Use Mac Terminal commands (no Windows-specific instructions)

---

## Project Overview

**Bookie-o-em** - AI Sports Prop Betting Backend
**Version:** v14.2 PRODUCTION HARDENED
**Stack:** Python 3.11+, FastAPI, Railway deployment
**Frontend:** bookie-member-app (separate repo)
**Production URL:** https://web-production-7b2a.up.railway.app

---

## IMPORTANT: Paid APIs - Always Use These

**We pay for Odds API and Playbook API. Always use these for any data needs:**

| API | Purpose | Key |
|-----|---------|-----|
| **Odds API** | Live odds, lines, betting data, historical props | `ODDS_API_KEY` |
| **Playbook API** | Player stats, game logs, sharp money, splits (all 5 sports) | `PLAYBOOK_API_KEY` |

**Default to our paid APIs first.** These cover all 5 sports: **NBA, NFL, MLB, NHL, NCAAB**

**Exception:** You may suggest alternative APIs if:
1. You explain WHY it's better than our paid APIs (data not available, better quality, etc.)
2. You get approval before implementing
3. There's a clear benefit over what we're already paying for

### Playbook API v1 Endpoints

**Base URL:** `https://api.playbook-api.com/v1`
**Auth:** `api_key` query parameter (NOT Bearer header)
**Leagues:** NBA | NFL | CFB | MLB | NHL (uppercase)

| Endpoint | Purpose | Required Params |
|----------|---------|-----------------|
| `/health` | Health check | none |
| `/me` | Plan + usage info | `api_key` |
| `/teams` | Team metadata + injuries | `league`, `api_key` |
| `/injuries` | Injury report by team | `league`, `api_key` |
| `/splits` | Public betting splits | `league`, `api_key` |
| `/splits-history` | Historical splits | `league`, `date`, `api_key` |
| `/odds-games` | Schedule + gameId list | `league`, `api_key` |
| `/lines` | Current spread/total/ML | `league`, `api_key` |
| `/games` | Game objects from splits | `league`, `date`, `api_key` |

### API Usage Monitoring

**IMPORTANT:** Monitor API usage to avoid hitting limits, especially if community usage grows.

| Endpoint | Purpose |
|----------|---------|
| `GET /live/api-health` | Quick status check (for dashboards) |
| `GET /live/api-usage` | Combined usage with threshold warnings |
| `GET /live/playbook/usage` | Playbook plan + quota info |
| `GET /live/odds-api/usage` | Odds API requests remaining |

**Threshold Warning Levels:**
| Level | % Used | Emoji | Action |
|-------|--------|-------|--------|
| `HEALTHY` | < 25% | ✅ | None needed |
| `CAUTION_25` | 25-49% | 🟢 | Monitor |
| `CAUTION_50` | 50-74% | 🟡 | Watch closely |
| `CAUTION_75` | 75-89% | 🟠 | Consider upgrading |
| `CRITICAL` | 90%+ | 🚨 | UPGRADE NOW |

**Response includes:**
- `overall_status`: Worst status across all APIs
- `action_needed`: true if CRITICAL or CAUTION_75
- `alerts`: List of warning messages
- `summary`: Human-readable status message

**Odds API Info:**
- Resets monthly
- Free tier = 500 requests/month
- Headers: `x-requests-remaining`, `x-requests-used`

**Quick check command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/api-health" -H "X-API-Key: YOUR_KEY"
```

**Full details:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/api-usage" -H "X-API-Key: YOUR_KEY"
```

---

## Authentication

**API Authentication is ENABLED.** Key stored in Railway environment variables (`API_AUTH_KEY`).
- All `/live/*` endpoints require `X-API-Key` header
- `/health` endpoint is public (for Railway health checks)

---

## CRITICAL: Today-Only ET Gate (NEVER skip this)

**Every data path that touches Odds API events MUST filter to today-only in ET before processing.**

### Rules
1. **Props AND game picks** must both pass through `filter_events_today_et()` before iteration
2. The day boundary is **00:00:00 ET to 23:59:59 ET** — never 12:01 AM
3. `filter_events_today_et(events, date_str)` returns `(kept, dropped_window, dropped_missing)` — always log the drop counts
4. `date_str` (YYYY-MM-DD) must be threaded through the full call chain: endpoint → `get_best_bets(date=)` → `_best_bets_inner(date_str=)` → `filter_events_today_et(events, date_str)`
5. Debug output must include `dropped_out_of_window_props`, `dropped_out_of_window_games`, `dropped_missing_time_props`, `dropped_missing_time_games`

### Why
Without the gate, `get_props()` returns ALL upcoming events from Odds API (could be 60+ games across multiple days). This causes:
- Inflated candidate counts
- Ghost picks for games not happening today
- Score distribution skewed by tomorrow's games

### Where it lives
- `time_filters.py`: `et_day_bounds()`, `is_in_et_day()`, `filter_events_today_et()`
- `live_data_router.py` `_best_bets_inner()`: applied to both props loop (~line 2536) and game picks (~line 2790)
- `main.py` `/ops/score-distribution`: passes `date=date` to `get_best_bets()`

### If adding a new data path
If you add ANY new endpoint or function that processes Odds API events, you MUST apply `filter_events_today_et()` before iteration. No exceptions.

---

## Architecture

### Core Files (Active)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI entry point, includes routers |
| `live_data_router.py` | All `/live/*` endpoints, JARVIS triggers, esoteric functions |
| `advanced_ml_backend.py` | 8 AI Models + 8 Pillars of Execution |

### Legacy Files (Reference Only - Do Not Modify)

| File | Status |
|------|--------|
| `new_endpoints.py` | DEPRECATED |
| `services/` | Legacy sync services |
| `prediction_api.py` | Old 8-model API |

---

## Signal Architecture (4-Engine v15.3)

### Scoring Formula
```
FINAL = (AI × 0.25) + (Research × 0.30) + (Esoteric × 0.20) + (Jarvis × 0.15) + confluence_boost
       + jason_sim_boost (post-pick)
```

All engines score 0-10. Min output threshold: **6.5** (picks below this are filtered out).

### Engine 1: AI Score (25%)
- 8 AI Models (0-8 scaled to 0-10) - `advanced_ml_backend.py`
- Dynamic calibration: +0.5 sharp present, +0.25-1.0 signal strength, +0.5 favorable spread, +0.25 player data

### Engine 2: Research Score (30%)
- Sharp Money (0-3 pts): STRONG/MODERATE/MILD signal from Playbook splits
- Line Variance (0-3 pts): Cross-book spread variance from Odds API
- Public Fade (0-2 pts): Contrarian signal at ≥65% public + ticket-money divergence ≥5%
- Base (2-3 pts): 2.0 default, 3.0 when real splits data present with money-ticket divergence

### Engine 3: Esoteric Score (20%)
- **See CRITICAL section below for rules**

### Engine 4: Jarvis Score (15%)
- Gematria triggers: 2178, 201, 33, 93, 322
- Mid-spread Goldilocks, trap detection
- `jarvis_savant_engine.py`

### Confluence (v15.3 — with STRONG eligibility gate)
- Alignment = `1 - abs(research - esoteric) / 10`
- **STRONG (+3)**: alignment ≥ 80% **AND** at least one active signal (`jarvis_active`, `research_sharp_present`, or `jason_sim_boost != 0`). If alignment ≥70% but no active signal, downgrades to MODERATE.
- MODERATE (+1): alignment ≥ 60%
- DIVERGENT (+0): below 60%
- PERFECT/IMMORTAL: both ≥7.5 + jarvis ≥7.5 + alignment ≥80%

**Why the gate**: Without it, two engines that are both mediocre (e.g., R=4.0, E=4.0) get 100% alignment and STRONG +3 boost for free, inflating scores without real conviction.

### CRITICAL: GOLD_STAR Hard Gates (v15.3)

**GOLD_STAR tier requires ALL of these engine minimums. If any fails, downgrade to EDGE_LEAN.**

| Gate | Threshold | Why |
|------|-----------|-----|
| `ai_gte_6.8` | AI ≥ 6.8 | AI models must show conviction |
| `research_gte_5.5` | Research ≥ 5.5 | Must have real market signals (sharp/splits/variance) |
| `jarvis_gte_6.5` | Jarvis ≥ 6.5 | Jarvis triggers must fire |
| `esoteric_gte_4.0` | Esoteric ≥ 4.0 | Esoteric components must contribute |

**Output includes**: `scoring_breakdown.gold_star_gates` (dict of gate→bool), `gold_star_eligible` (bool), `gold_star_failed` (list of failed gate names).

**Where it lives**: `live_data_router.py` `calculate_pick_score()`, after `tier_from_score()` call.

### Tier Hierarchy
| Tier | Score Threshold | Additional Requirements |
|------|----------------|------------------------|
| TITANIUM_SMASH | 3/4 engines ≥ 8.0 | Overrides all other tiers |
| GOLD_STAR | ≥ 7.5 | Must pass ALL hard gates |
| EDGE_LEAN | ≥ 6.5 | Default for picks above output filter |
| MONITOR | ≥ 5.5 | Below output filter (hidden) |
| PASS | < 5.5 | Below output filter (hidden) |

### If modifying confluence or tiers
1. Do NOT remove STRONG eligibility gate — it prevents inflation from aligned-but-weak engines
2. Do NOT remove GOLD_STAR hard gates — they ensure only picks with real multi-engine conviction get top tier
3. Run debug mode and verify gates show in `scoring_breakdown`
4. Check that STRONG only fires with alignment ≥80% + active signal

---

## CRITICAL: Esoteric Engine Rules (v15.2)

**Esoteric is a per-pick differentiator, NOT a constant boost. Never modify it to inflate scores uniformly.**

### Components & Weights
| Component | Weight | Max Pts | Input Source |
|-----------|--------|---------|--------------|
| Numerology | 35% | 3.5 | 40% daily (day_of_year) + 60% pick-specific (SHA-256 of game_str\|prop_line\|player_name) |
| Astro | 25% | 2.5 | Vedic astro `overall_score` mapped linearly 0-100 → 0-10 (50 = 5.0) |
| Fibonacci | 15% | 1.5 | Jarvis `calculate_fibonacci_alignment(magnitude)` → scaled 6× in esoteric layer, capped at 0.6 |
| Vortex | 15% | 1.5 | Jarvis `calculate_vortex_pattern(magnitude×10)` → scaled 5× in esoteric layer, capped at 0.7 |
| Daily Edge | 10% | 1.0 | `get_daily_energy()` score: ≥85→1.0, ≥70→0.7, ≥55→0.4, <55→0 |

### Magnitude Fallback (props MUST NOT use spread=0)
```
magnitude = abs(spread) → abs(prop_line) → abs(total/10) → 0
```
Fib and Vortex use `magnitude`, NOT raw `spread`. This ensures props with player lines (2.5, 24.5, etc.) get meaningful fib/vortex input.

### Guardrails
- Numerology uses `hashlib.sha256` for deterministic per-pick seeding (NOT `hash()`)
- Fib+Vortex combined contribution capped at their weight share (3.0 max)
- Fib/Vortex scaling is done in the esoteric layer in `live_data_router.py`, NOT in `jarvis_savant_engine.py`
- Expected range: 2.0-5.5 (median ~3.5). Average must NOT exceed 7.0
- `esoteric_breakdown` in debug output shows all components + `magnitude_input`

### Where it lives
- `live_data_router.py` `calculate_pick_score()`: lines ~2352-2435
- Jarvis provides raw fib/vortex modifiers (unchanged), esoteric layer scales them
- Tests: `tests/test_esoteric.py` (10 tests covering bounds, variability, determinism)

### If modifying Esoteric
1. Do NOT change Jarvis fib/vortex modifiers — scale in the esoteric layer only
2. Run `pytest tests/test_esoteric.py` to verify median ≥2.0, avg ≤7.0, cap ≤10, variability
3. Check confluence still produces DIVERGENT when research >> esoteric by 4+ pts
4. Deploy and verify `esoteric_breakdown` in debug output shows per-pick variation

---

## Pick Deduplication (v15.3)

**Best-bets output is deduplicated to ensure no duplicate picks reach the frontend.**

### How It Works

1. **Stable `pick_id`**: Each pick gets a deterministic 12-char hex ID via SHA-1 hash of canonical bet semantics:
   ```
   SHA1(SPORT|event_id|market|SIDE|line|player)[:12]
   ```
   - `side` is uppercased, `line` is rounded to 2 decimals
   - Field fallbacks: `event_id` OR `game_id` OR `matchup`; `market` OR `prop_type` OR `pick_type`; etc.

2. **Priority rule**: When duplicates share the same `pick_id`, keep the one with:
   - Highest `total_score` (primary)
   - Preferred book (tiebreaker): draftkings > fanduel > betmgm > caesars > pinnacle > others

3. **Applied to both props AND game picks** separately via `_dedupe_picks()`

### Debug Output

```json
{
  "dupe_dropped_props": 3,
  "dupe_dropped_games": 1,
  "dupe_groups_props": [
    {
      "pick_id": "a1b2c3d4e5f6",
      "count": 3,
      "kept_book": "draftkings",
      "dropped_books": ["fanduel", "betmgm"]
    }
  ]
}
```

### Where It Lives
- `live_data_router.py`: `_make_pick_id()`, `_book_priority()`, `_dedupe_picks()` helper functions
- Applied after scoring, before output filter
- Tests: `tests/test_dedupe.py` (12 tests)

### If Modifying Dedupe
1. `pick_id` must remain deterministic — same bet = same ID across requests
2. Never remove the dedupe step — duplicates confuse the frontend and inflate pick counts
3. Run `pytest tests/test_dedupe.py` to verify edge cases (different sides, lines, players not deduped)

---

## Self-Improvement System (Auto-Grader)

The system learns and improves daily through the **Auto-Grader** feedback loop.

### How It Works

1. **Log Predictions** - Each pick is stored with adjustment factors used
2. **Grade Results** - After games, actual stats are compared to predictions
3. **Calculate Bias** - System identifies if it's over/under predicting
4. **Adjust Weights** - Weights are corrected to reduce future errors
5. **Persist Learning** - New weights saved for tomorrow's picks

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/live/grader/status` | GET | Check grader status |
| `/live/grader/weights/{sport}` | GET | Current learned weights |
| `/live/grader/bias/{sport}` | GET | See prediction bias |
| `/live/grader/performance/{sport}` | GET | Hit rate & MAE metrics |
| `/live/grader/run-audit` | POST | Trigger daily audit |
| `/live/grader/adjust-weights/{sport}` | POST | Manual weight adjustment |

### Bias Interpretation

| Bias Range | Status | Action |
|------------|--------|--------|
| -1.0 to +1.0 | ✅ Healthy | None needed |
| -2.0 to -1.0 or +1.0 to +2.0 | 🟡 Monitor | Watch next audit |
| Beyond ±2.0 | 🚨 Critical | Immediate adjustment |

- **Positive bias** = Predicting too HIGH
- **Negative bias** = Predicting too LOW

### Target Metrics

| Sport | Target MAE | Profitable Hit Rate |
|-------|------------|---------------------|
| NBA/NCAAB | < 3.0 pts | > 52% |
| NFL passing | < 15.0 yds | > 52% |
| All props | - | > 55% (🔥 SMASH) |

### Daily Audit

Run this daily after games complete to improve picks:
```bash
curl -X POST "https://web-production-7b2a.up.railway.app/live/grader/run-audit" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"days_back": 1, "apply_changes": true}'
```

### Check Performance

See how picks are doing over the last 7 days:
```bash
curl "https://web-production-7b2a.up.railway.app/live/grader/performance/nba?days_back=7" \
  -H "X-API-Key: YOUR_KEY"
```

### Daily Community Report

Every morning at 6 AM ET, the system grades picks and generates a report for your community.

**Get the daily report:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/grader/daily-report" \
  -H "X-API-Key: YOUR_KEY"
```

**Report includes:**
- Overall performance (wins/losses/hit rate)
- Performance by sport
- What the system learned
- Improvements made to weights
- Ready-to-post community message

**Sample output:**
```
🔥 SMASH SPOT DAILY REPORT 🔥

📅 January 15, 2026 Results:
• Total Picks: 24
• Record: 14-10
• Hit Rate: 58.3%

SMASHING IT!

📚 What We Learned:
• NBA: Model performing well, minor tuning applied.

🔧 Improvements Made:
• Weights optimized for tomorrow.

Your community is in great hands. Keep riding the hot streak!

🎯 We grade EVERY pick at 6 AM and adjust our AI daily.
Whether we win or lose, we're always improving! 💪
```

**Status Levels:**
| Hit Rate | Status | Emoji |
|----------|--------|-------|
| 55%+ | SMASHING IT! | 🔥 |
| 52-54% | PROFITABLE DAY! | 💰 |
| 48-51% | BREAK-EVEN ZONE | 📊 |
| Below 48% | LEARNING DAY | 📈 |

---

## Coding Standards

### Python/FastAPI

```python
# Use async for all endpoint handlers
@router.get("/endpoint")
async def get_endpoint():
    pass

# Use httpx for async HTTP calls (not requests)
async with httpx.AsyncClient() as client:
    resp = await client.get(url)

# Environment variables with fallbacks
API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    logger.warning("API_KEY not set")

# Type hints for function signatures
async def fetch_data(sport: str) -> Dict[str, Any]:
    pass

# Consistent response schema
return {
    "sport": sport.upper(),
    "source": "playbook" | "odds_api" | "estimated",
    "count": len(data),
    "data": data
}
```

### Error Handling

```python
# Prefer explicit status codes over generic exceptions
if resp.status_code == 429:
    raise HTTPException(status_code=503, detail="Rate limited")

if resp.status_code != 200:
    raise HTTPException(status_code=502, detail=f"API error: {resp.status_code}")

# Use logging, not print statements
logger.info("Fetched %d games for %s", len(games), sport)
logger.exception("Failed to fetch: %s", e)
```

### Caching

```python
# Check cache first
cache_key = f"endpoint:{sport}"
cached = api_cache.get(cache_key)
if cached:
    return cached

# ... fetch data ...

# Cache before returning
api_cache.set(cache_key, result, ttl=300)  # 5 min default, 120 for best-bets
return result
```

---

## Environment Variables

### Required
```bash
ODDS_API_KEY=xxx          # The Odds API
PLAYBOOK_API_KEY=xxx      # Playbook Sports API
```

### Optional
```bash
API_AUTH_ENABLED=true     # Enable X-API-Key auth
API_AUTH_KEY=xxx          # Required if auth enabled
ODDS_API_BASE=xxx         # Override API URL
PLAYBOOK_API_BASE=xxx     # Override API URL
```

### Railway Auto-Set
```bash
PORT=8000                 # Read via os.environ.get("PORT", 8000)
```

---

## Deployment

### Railway Configuration

- `railway.toml` - Uses `startCommand = "python main.py"`
- `Procfile` - `web: python main.py`
- `Dockerfile` - `CMD ["python", "main.py"]`

**Important:** PORT must be read in Python, not shell expansion:
```python
# Correct
port = int(os.environ.get("PORT", 8000))

# Wrong - does not work on Railway
# uvicorn main:app --port ${PORT:-8000}
```

---

## API Endpoints

### Production Endpoints
```
GET /                           # API info
GET /health                     # Health check
GET /live/health                # Router health
GET /live/sharp/{sport}         # Sharp money (derived from splits)
GET /live/splits/{sport}        # Betting splits (cached 5m)
GET /live/injuries/{sport}      # Injury report (Playbook + ESPN)
GET /live/lines/{sport}         # Current lines spread/total/ML
GET /live/props/{sport}         # Player props (cached 5m)
GET /live/best-bets/{sport}     # AI best bets (cached 2m)
GET /live/esoteric-edge         # Esoteric analysis
GET /live/noosphere/status      # Noosphere velocity
GET /live/gann-physics-status   # GANN physics
GET /esoteric/today-energy      # Daily energy
```

### Consolidated Endpoints (Server-Side Fetching)

**Use these endpoints to reduce client-side waterfalls. Each consolidates multiple API calls into one.**

```
GET /live/sport-dashboard/{sport}              # Dashboard: best-bets + splits + lines + injuries + sharp (6→1)
GET /live/game-details/{sport}/{game_id}       # Game view: lines + props + sharp + injuries + AI pick (5→1)
GET /live/parlay-builder-init/{sport}?user_id= # Parlay: recommended props + all props + correlations (3→1)
```

| Endpoint | Replaces | Cache TTL | Use Case |
|----------|----------|-----------|----------|
| `/sport-dashboard/{sport}` | 6 endpoints | 2m | Dashboard page load |
| `/game-details/{sport}/{game_id}` | 5 endpoints | 2m | Game detail modal |
| `/parlay-builder-init/{sport}` | 3 endpoints | 3m | Parlay builder init |

**Response Schema - sport-dashboard:**
```json
{
  "sport": "NBA",
  "best_bets": { "props": [], "game_picks": [] },
  "market_overview": { "lines": [], "splits": [], "sharp_signals": [] },
  "context": { "injuries": [] },
  "daily_energy": {...},
  "timestamp": "ISO",
  "cache_info": { "hit": false, "sources": {...} }
}
```

### Click-to-Bet Endpoints v2.0
```
GET  /live/sportsbooks                    # List 8 supported sportsbooks
GET  /live/line-shop/{sport}              # Line shopping across all books
GET  /live/betslip/generate               # Generate betslip for placing bet
GET  /live/quick-betslip/{sport}/{game}   # Quick betslip with user prefs
GET  /live/user/preferences/{user_id}     # Get user preferences
POST /live/user/preferences/{user_id}     # Save user preferences
POST /live/bets/track                     # Track a placed bet
POST /live/bets/grade/{bet_id}            # Grade bet (WIN/LOSS/PUSH)
GET  /live/bets/history                   # Bet history with stats
```
See `FRONTEND_HANDOFF_CLICK_TO_BET.md` for frontend integration guide.

### Parlay Builder Endpoints
```
GET    /live/parlay/{user_id}                   # Get current parlay slip
POST   /live/parlay/add                         # Add leg to parlay
DELETE /live/parlay/remove/{user_id}/{leg_id}   # Remove leg
DELETE /live/parlay/clear/{user_id}             # Clear parlay slip
POST   /live/parlay/place                       # Track placed parlay
POST   /live/parlay/grade/{parlay_id}           # Grade parlay (WIN/LOSS/PUSH)
GET    /live/parlay/history                     # Parlay history with stats
POST   /live/parlay/calculate                   # Preview odds calculation
```

### Management Endpoints
```
GET /live/cache/stats           # Cache statistics
GET /live/cache/clear           # Clear cache
GET /live/api-health            # Quick API status (for dashboards)
GET /live/api-usage             # Full API usage with warnings
GET /live/playbook/usage        # Playbook plan + quota
GET /live/playbook/health       # Playbook API health check
GET /live/odds-api/usage        # Odds API requests remaining
GET /live/lstm/status           # LSTM status
GET /live/grader/status         # Auto-grader status
GET /live/grader/weights/{sport}# Prediction weights
GET /live/scheduler/status      # Scheduler status
```

### Supported Sports
`nba`, `nfl`, `mlb`, `nhl`

---

## Testing

```bash
# Local
python main.py
curl http://localhost:8000/health

# Production
curl https://web-production-7b2a.up.railway.app/health
curl https://web-production-7b2a.up.railway.app/live/best-bets/nba
```

---

## Git Workflow

- Main production code is on `main` branch
- Feature branches: `claude/feature-name-xxxxx`
- Always commit with descriptive messages
- Push with `git push -u origin branch-name`

### PR Handoffs for External Repos

When providing file updates for PRs (especially for frontend repos), **always provide the complete file content** so the user can:
1. Go to GitHub web editor
2. Select all (Ctrl+A) and delete
3. Paste the complete new file
4. Commit/PR

**Do NOT** give partial instructions like "change X to Y" or "add this after line 5" - this creates guesswork. Always provide the full file ready to copy-paste.

**Always provide direct GitHub links** - don't give step-by-step navigation like "click src, then services, then api.js". Just provide the full URL:
- Edit file: `https://github.com/{owner}/{repo}/edit/{branch}/{path}`
- View file: `https://github.com/{owner}/{repo}/blob/{branch}/{path}`

---

## Key Decisions

1. **In-memory TTL cache** over Redis (single instance for now)
2. **Optional auth** disabled by default (enable in Railway env vars)
3. **JARVIS weight doubled** to 4 max points (was 2)
4. **Async httpx** over sync requests library
5. **Deterministic RNG** for fallback data (stable across requests)

---

## Common Tasks

### Add New Endpoint
1. Add route in `live_data_router.py`
2. Follow async pattern with caching
3. Use standardized response schema
4. Update HANDOFF.md if significant

### Modify Scoring
- AI Models: `advanced_ml_backend.py` → `MasterPredictionSystem`
- JARVIS: `live_data_router.py:233-239` → `JARVIS_TRIGGERS`
- Esoteric: `live_data_router.py` → `get_daily_energy()`

### Debug Deployment
1. Check Railway logs
2. Verify PORT is read via Python `os.environ.get()`
3. Ensure `railway.toml` uses `python main.py`

---

## Session Log: January 16, 2026 - Pre-Launch Audit

### What Was Done

**1. Critical Auto-Grader Bug Fixes**
Fixed 3 bugs that would have broken the self-improvement system in production:

| Bug | File | Fix |
|-----|------|-----|
| Singleton not used | `live_data_router.py` | Changed all grader endpoints to use `get_grader()` instead of `AutoGrader()` |
| Missing method | `auto_grader.py` | Added `get_audit_summary()` method |
| Scheduler disconnected | `main.py` | Connected scheduler to auto_grader on startup |

**2. Comprehensive System Audit**
Verified all components are integrated:

- **8 AI Models** in `advanced_ml_backend.py` - All present
- **5 Context Features** in `context_layer.py` - All present
- **10+ Esoteric Signals** in `esoteric_engine.py` - All present
- **LSTM Brain** in `lstm_brain.py` - Working with TF fallback
- **67 API Endpoints** in `live_data_router.py` - All verified

**3. Commit Pushed**
```
fix: Critical auto-grader bugs for production launch
```

---

## Launch Day Testing Checklist

Run these tests before going live:

### 1. Health Checks
```bash
# Backend health
curl "https://web-production-7b2a.up.railway.app/health"

# Live router health
curl "https://web-production-7b2a.up.railway.app/live/health" -H "X-API-Key: YOUR_KEY"

# API usage (check quotas)
curl "https://web-production-7b2a.up.railway.app/live/api-health" -H "X-API-Key: YOUR_KEY"
```

### 2. Core Data Endpoints
```bash
# Best bets (SMASH Spots)
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba" -H "X-API-Key: YOUR_KEY"

# Player props
curl "https://web-production-7b2a.up.railway.app/live/props/nba" -H "X-API-Key: YOUR_KEY"

# Splits
curl "https://web-production-7b2a.up.railway.app/live/splits/nba" -H "X-API-Key: YOUR_KEY"

# Lines
curl "https://web-production-7b2a.up.railway.app/live/lines/nba" -H "X-API-Key: YOUR_KEY"
```

### 3. Self-Improvement System
```bash
# Grader status (should show available: true)
curl "https://web-production-7b2a.up.railway.app/live/grader/status" -H "X-API-Key: YOUR_KEY"

# Scheduler status (should show available: true)
curl "https://web-production-7b2a.up.railway.app/live/scheduler/status" -H "X-API-Key: YOUR_KEY"

# Current weights
curl "https://web-production-7b2a.up.railway.app/live/grader/weights/nba" -H "X-API-Key: YOUR_KEY"

# Performance metrics
curl "https://web-production-7b2a.up.railway.app/live/grader/performance/nba" -H "X-API-Key: YOUR_KEY"

# Daily report
curl "https://web-production-7b2a.up.railway.app/live/grader/daily-report" -H "X-API-Key: YOUR_KEY"
```

### 4. Esoteric Features
```bash
# Today's energy
curl "https://web-production-7b2a.up.railway.app/esoteric/today-energy"

# Esoteric edge
curl "https://web-production-7b2a.up.railway.app/live/esoteric-edge" -H "X-API-Key: YOUR_KEY"

# Noosphere
curl "https://web-production-7b2a.up.railway.app/live/noosphere/status" -H "X-API-Key: YOUR_KEY"
```

### 5. Betting Features
```bash
# Line shopping
curl "https://web-production-7b2a.up.railway.app/live/line-shop/nba" -H "X-API-Key: YOUR_KEY"

# Sportsbooks list
curl "https://web-production-7b2a.up.railway.app/live/sportsbooks" -H "X-API-Key: YOUR_KEY"

# Affiliate links
curl "https://web-production-7b2a.up.railway.app/live/affiliate/links" -H "X-API-Key: YOUR_KEY"
```

### 6. Community Features
```bash
# Leaderboard
curl "https://web-production-7b2a.up.railway.app/live/community/leaderboard" -H "X-API-Key: YOUR_KEY"
```

### Expected Results

| Test | Expected |
|------|----------|
| `/health` | `{"status": "healthy"}` |
| `/live/grader/status` | `{"available": true, "predictions_logged": N}` |
| `/live/scheduler/status` | `{"available": true, "apscheduler_available": true}` |
| `/live/best-bets/nba` | Returns `props` and `game_picks` arrays |
| `/esoteric/today-energy` | Returns `betting_outlook` and `overall_energy` |

### If Tests Fail

1. Check Railway logs: `railway logs`
2. Verify environment variables are set
3. Check API quotas aren't exhausted
4. Restart Railway deployment if needed

---

## System Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    BOOKIE-O-EM v14.2                        │
├─────────────────────────────────────────────────────────────┤
│  main.py (FastAPI)                                          │
│    ├── live_data_router.py (67 endpoints)                   │
│    ├── scheduler_router (daily_scheduler.py)                │
│    └── esoteric endpoint (/esoteric/today-energy)           │
├─────────────────────────────────────────────────────────────┤
│  PREDICTION ENGINE                                          │
│    ├── advanced_ml_backend.py (8 AI Models)                 │
│    ├── lstm_brain.py (Neural Network)                       │
│    ├── context_layer.py (5 Context Features)                │
│    └── esoteric_engine.py (10+ Esoteric Signals)            │
├─────────────────────────────────────────────────────────────┤
│  SELF-IMPROVEMENT                                           │
│    ├── auto_grader.py (Feedback Loop)                       │
│    │     └── get_grader() singleton                         │
│    └── daily_scheduler.py (6 AM Audit)                      │
├─────────────────────────────────────────────────────────────┤
│  EXTERNAL APIs                                              │
│    ├── Odds API (odds, lines, props)                        │
│    └── Playbook API (splits, injuries, stats)               │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Simplifier Agent

**Name:** code-simplifier
**Model:** opus
**Purpose:** Simplifies and refines code for clarity, consistency, and maintainability while preserving all functionality.

### When to Use
- After writing or modifying code
- To refine recently touched code sections
- To apply project standards consistently

### Principles

1. **Preserve Functionality**: Never change what code does - only how it does it
2. **Apply Project Standards**: Follow CLAUDE.md coding standards
3. **Enhance Clarity**: Reduce complexity, eliminate redundancy, improve naming
4. **Maintain Balance**: Avoid over-simplification that reduces maintainability
5. **Focus Scope**: Only refine recently modified code unless instructed otherwise

### Code Standards (Python)

- Use async functions with type hints
- Prefer explicit over implicit
- Choose clarity over brevity
- Remove unnecessary comments that describe obvious code

### What NOT to Do

- Change functionality or outputs
- Create overly clever solutions
- Combine too many concerns into single functions
- Remove helpful abstractions
- Prioritize "fewer lines" over readability

---

## Session Log: January 16, 2026 - Backend API Audit

### What Was Done

**1. Backend API Audit (76 Endpoints)**
Audited all FastAPI route handlers:

| File | Routes | Issues Found |
|------|--------|--------------|
| `main.py` | 7 | None |
| `live_data_router.py` | 69 | Missing input validation |

**2. Pydantic Validation Models Added**
Created `models/api_models.py` with request validation:

| Model | Validates |
|-------|-----------|
| `TrackBetRequest` | Sport codes, American odds format, required fields |
| `GradeBetRequest` | WIN/LOSS/PUSH enum |
| `ParlayLegRequest` | Odds format, sport, game_id |
| `PlaceParlayRequest` | Sportsbook required, stake >= 0 |
| `UserPreferencesRequest` | Nested notifications object |

**3. Endpoints Updated with Validation**
- `POST /bets/track` - Now validates odds (-110 valid, -50 invalid)
- `POST /bets/grade/{bet_id}` - Enum validation
- `POST /parlay/add` - Odds + sport validation
- `POST /parlay/place` - Required fields
- `POST /parlay/grade/{parlay_id}` - Enum validation
- `POST /user/preferences/{user_id}` - Nested object handling

### Files Changed

```
models/api_models.py          (NEW - Pydantic models)
models/__init__.py            (NEW - Package init)
live_data_router.py           (MODIFIED - Validation added)
```

---

## Session Log: January 17, 2026 - Server-Side Data Fetching

### What Was Done

**1. Created Consolidated Endpoints**

Added 3 new endpoints to reduce client-side API waterfalls:

| Endpoint | Replaces | Improvement |
|----------|----------|-------------|
| `GET /live/sport-dashboard/{sport}` | 6 calls (best-bets, splits, lines, injuries, sharp, props) | 83% reduction |
| `GET /live/game-details/{sport}/{game_id}` | 5 calls (lines, props, sharp, injuries, best-bets) | 80% reduction |
| `GET /live/parlay-builder-init/{sport}` | 3 calls (best-bets, props, correlations) | 67% reduction |

**Implementation Details:**
- Uses `asyncio.gather()` to fetch all data in parallel server-side
- Graceful error handling - returns partial data if individual fetches fail
- Caches consolidated response (2-3 minute TTL)
- User-specific data (parlay slip) fetched separately to maintain cache efficiency

**2. Marked `/learning/*` Endpoints as Deprecated**

All 6 endpoints marked with `deprecated=True`:
- `/learning/log-pick` → Use `/grader/*`
- `/learning/grade-pick` → Use `/grader/*`
- `/learning/performance` → Use `/grader/performance/{sport}`
- `/learning/weights` → Use `/grader/weights/{sport}`
- `/learning/adjust-weights` → Use `/grader/adjust-weights/{sport}`
- `/learning/recent-picks` → Use `/grader/*`

Will be removed in v15.0.

**3. Added Helper Functions**
- `get_parlay_correlations()` - Static correlation matrix for SGP
- `calculate_parlay_odds_internal()` - Parlay odds calculation helper

### Files Changed

```
live_data_router.py   (MODIFIED - Added 3 consolidated endpoints, deprecated /learning/*)
CLAUDE.md             (MODIFIED - Documented new endpoints + session log)
```

### Testing

```bash
# Test consolidated dashboard endpoint
curl "https://web-production-7b2a.up.railway.app/live/sport-dashboard/nba" -H "X-API-Key: YOUR_KEY"

# Test game details endpoint
curl "https://web-production-7b2a.up.railway.app/live/game-details/nba/GAME_ID" -H "X-API-Key: YOUR_KEY"

# Test parlay builder init
curl "https://web-production-7b2a.up.railway.app/live/parlay-builder-init/nba?user_id=test123" -H "X-API-Key: YOUR_KEY"
```

### Frontend Integration

Update frontend to use consolidated endpoints:

**Before (6 calls):**
```javascript
const bestBets = await fetch('/live/best-bets/nba');
const splits = await fetch('/live/splits/nba');
const lines = await fetch('/live/lines/nba');
const injuries = await fetch('/live/injuries/nba');
const sharp = await fetch('/live/sharp/nba');
```

**After (1 call):**
```javascript
const dashboard = await fetch('/live/sport-dashboard/nba');
// All data in: dashboard.best_bets, dashboard.market_overview, dashboard.context
```

---

## Session Log: January 17, 2026 - CLAUDE.md Cleanup

### What Was Done

**1. Removed Vercel/React Content**

Removed ~200 lines of frontend-focused content that didn't apply to this Python/FastAPI backend:

| Removed Section | Reason |
|-----------------|--------|
| Vercel Agent Skills (5 skills) | React/Next.js only, not Python |
| Agent Rules (Strict) | React-specific rules |
| react-best-practices docs | Frontend skill |
| react-strict-rules docs | Frontend skill |
| web-design-guidelines docs | UI/accessibility for frontend |
| vercel-deploy-claimable docs | Vercel deployment (we use Railway) |
| json-ui-composer docs | JSON UI generation |

**2. Cleaned Up Session Logs**

- Removed Vercel skills installation from Jan 16 log
- Kept Pydantic validation work (still relevant)
- Updated Code Standards to Python-specific

### Why This Change

This is a **Python/FastAPI backend deployed on Railway**, not a React/Next.js app on Vercel. The Vercel skills:
- Were installed but never applicable here
- Added confusion to the project instructions
- Should live in the frontend repo (`bookie-member-app`) if needed

### Backend Best Practices (What We Follow)

| Practice | Implementation |
|----------|----------------|
| Async endpoints | All handlers use `async def` |
| Type hints | Function signatures typed |
| Pydantic validation | Request models in `models/api_models.py` |
| TTL caching | In-memory cache with configurable TTL |
| Error handling | Explicit HTTPException with status codes |
| Logging | Structured logging, no print statements |
| Connection pooling | Shared httpx.AsyncClient |
| Retry with backoff | 2 retries, exponential backoff |
| Auth on mutations | All POST endpoints require X-API-Key |
| Limit validation | History endpoints capped at 500 |
| Parallel fetching | Consolidated endpoints use asyncio.gather() |

---

## Session Log: January 17, 2026 - Backend API Audit

### What Was Done

**1. Complete Endpoint Inventory (83 routes)**

| File | Endpoints | Status |
|------|-----------|--------|
| `main.py` | 6 | Clean |
| `live_data_router.py` | 72 active, 6 deprecated | Fixed |

**2. Security Fixes (P0 Critical)**

Added `verify_api_key` auth to all mutating endpoints:
- `POST /bets/track`
- `POST /bets/grade/{bet_id}`
- `POST /parlay/add`
- `POST /parlay/place`
- `POST /parlay/grade/{parlay_id}`
- `POST /community/vote`
- `POST /affiliate/configure`

**3. DoS Prevention (P0 Critical)**

Added max limit validation to history endpoints:
- `GET /bets/history` - Max 500 results
- `GET /parlay/history` - Max 500 results

**4. Verified Waterfall Elimination**

Consolidated endpoints correctly use `asyncio.gather()`:
- `/sport-dashboard/{sport}` - 5 parallel fetches
- `/game-details/{sport}/{game_id}` - 5 parallel fetches
- `/parlay-builder-init/{sport}` - 2 parallel fetches

### Issues Identified (Future Work)

| Priority | Issue | Status |
|----------|-------|--------|
| P2 | In-memory storage leak risk | Monitor |
| P2 | No pagination on lists | TODO |
| P3 | Response schema inconsistency | Minor |

### Files Changed

```
live_data_router.py   (MODIFIED - Auth + validation)
CLAUDE.md             (MODIFIED - Session log)
```

---

## Session Log: January 26, 2026 - Unified Player ID Resolver + BallDontLie GOAT

### What Was Done

**1. Unified Player Identity Resolver (CRITICAL FIX)**

Created new `identity/` module with 3 core files:

| File | Purpose |
|------|---------|
| `identity/name_normalizer.py` | Name standardization (lowercase, accents, suffixes, nicknames) |
| `identity/player_index_store.py` | In-memory cache with TTL (roster 6h, injuries 30m, props 5m) |
| `identity/player_resolver.py` | Main resolver with multi-strategy matching |

**Canonical Player ID Format:**
- NBA with BallDontLie: `NBA:BDL:{player_id}`
- Fallback: `{SPORT}:NAME:{normalized_name}|{team_hint}`

**Resolver Strategies (in order):**
1. Provider ID lookup (fastest)
2. Exact name match in cache
3. Fuzzy name search
4. BallDontLie API lookup (NBA only)
5. Fallback name-based ID

**2. BallDontLie GOAT Tier Integration**

Updated `alt_data_sources/balldontlie.py` with GOAT subscription key:
```python
BALLDONTLIE_API_KEY = "1cbb16a0-3060-4caf-ac17-ff11352540bc"
```

Added new GOAT-tier functions:
- `search_player()` - Player lookup by name
- `get_player_season_averages()` - Season stats
- `get_player_game_stats()` - Box score for specific game
- `get_box_score()` - Full game box score
- `grade_nba_prop()` - Direct prop grading function

**3. Live Data Router Integration**

Modified `live_data_router.py`:
- Added identity resolver import
- Props now include `canonical_player_id` and `provider_ids`
- Injury guard uses resolver for blocking OUT/DOUBTFUL players
- Position data included when available

**4. Result Fetcher Updates**

Modified `result_fetcher.py`:
- Uses BallDontLie GOAT key for NBA grading
- Imports identity resolver for player matching
- Fallback normalizers if identity module unavailable

**5. Tests Added**

Created `tests/test_identity.py` with comprehensive tests:
- Name normalizer tests (suffixes, accents, nicknames)
- Team normalizer tests
- Player index store tests
- Player resolver tests (exact, fuzzy, ambiguous)
- Injury guard tests
- Prop availability guard tests

### Files Created

```
identity/__init__.py           (NEW - Module exports)
identity/name_normalizer.py    (NEW - Name standardization)
identity/player_index_store.py (NEW - Caching layer)
identity/player_resolver.py    (NEW - Main resolver)
tests/test_identity.py         (NEW - Unit tests)
```

### Files Modified

```
live_data_router.py            (MODIFIED - Identity resolver integration)
alt_data_sources/balldontlie.py (MODIFIED - GOAT key + grading functions)
result_fetcher.py              (MODIFIED - GOAT key + identity imports)
CLAUDE.md                      (MODIFIED - Session log)
```

### Prop Output Schema (v14.9)

Each prop pick now includes:

```json
{
  "player_name": "LeBron James",
  "canonical_player_id": "NBA:BDL:237",
  "provider_ids": {
    "balldontlie": 237,
    "odds_api": null,
    "playbook": null
  },
  "position": "F",
  "prop_type": "points",
  "line": 25.5,
  "side": "Over",
  "tier": "GOLD_STAR",
  "ai_score": 8.2,
  "research_score": 7.8,
  "esoteric_score": 7.5,
  "jarvis_score": 6.0,
  "final_score": 9.1,
  "jason_ran": true,
  "jason_sim_boost": 0.3,
  ...
}
```

### API Keys Required

| API | Key | Purpose |
|-----|-----|---------|
| BallDontLie GOAT | `BALLDONTLIE_API_KEY` | NBA stats, grading, player lookup |
| Odds API | `ODDS_API_KEY` | Odds, lines, props, game scores |
| Playbook API | `PLAYBOOK_API_KEY` | Splits, injuries, sharp money |

---

## Unified Player ID Resolver (v14.9)

### Overview

The Unified Player ID Resolver prevents:
- Wrong player props
- Ghost props
- Grading mismatches
- "Player not listed" failures
- Name collisions (J. Williams, etc.)

### Usage

```python
from identity import resolve_player, ResolvedPlayer

# Async resolution
resolved = await resolve_player(
    sport="NBA",
    raw_name="LeBron James",
    team_hint="Lakers",
    event_id="game_123"
)

print(resolved.canonical_player_id)  # "NBA:BDL:237"
print(resolved.confidence)           # 1.0
print(resolved.match_method)         # MatchMethod.API_LOOKUP
```

### Injury Guard

```python
resolver = get_player_resolver()

# Check if player is blocked due to injury
resolved = await resolver.check_injury_guard(
    resolved,
    allow_questionable=False  # For TITANIUM tier
)

if resolved.is_blocked:
    print(f"Blocked: {resolved.blocked_reason}")  # "PLAYER_OUT"
```

### Prop Availability Guard

```python
# Check if prop exists at books
resolved = await resolver.check_prop_availability(
    resolved,
    prop_type="points",
    event_id="game_123"
)

if not resolved.prop_available:
    print(f"Blocked: {resolved.blocked_reason}")  # "PROP_NOT_LISTED"
```

### TTL Cache Rules

| Data Type | TTL | Reason |
|-----------|-----|--------|
| Roster | 6 hours | Players don't change often |
| Injuries | 30 minutes | Status can change pre-game |
| Props availability | 5 minutes | Books update frequently |
| Live state | 1 minute | Real-time data |

---

## Session Log: January 27-28, 2026 - Best-Bets Performance Fix + Pick Logger Pipeline

### What Was Done

**1. Best-Bets Performance Overhaul (v16.1)**

Reduced `/live/best-bets/{sport}` response time from **18.28s → 5.5s** (70% improvement).

| Change | Before | After |
|--------|--------|-------|
| Data fetch | Sequential (props then games) | Parallel via `asyncio.gather()` |
| Player resolution | Sequential per-prop (~1.5s each) | Parallel batch with 0.8s per-call timeout, 3s batch timeout |
| Stage order | Props → Game picks | Game picks first (fast, no resolver), then props |
| Time budget | None | 15s hard deadline with `_timed_out_components` |

**2. Debug Instrumentation**

Added `debug=1` query param output:

| Field | Purpose |
|-------|---------|
| `debug_timings` | Per-stage timing (props_fetch, game_fetch, player_resolution, props_scoring, game_picks, pick_logging) |
| `total_elapsed_s` | Wall clock time |
| `timed_out_components` | List of stages that hit deadline |
| `date_window_et` | ET day bounds with events_before/after counts |
| `picks_logged` | Picks successfully written to pick_logger |
| `picks_skipped_dupes` | Picks skipped due to deduplication |
| `pick_log_errors` | Any silent pick_logger exceptions |
| `player_resolution` | attempted/succeeded/timed_out counts |
| `dropped_out_of_window_props/games` | ET filter drop counts |

**3. ET Day-Window Filter Verified**

- Both props AND game picks pass through `filter_events_today_et()` before scoring
- `date_window_et` debug block shows `start_et: "00:00:00"`, `end_et: "23:59:59"`, before/after counts
- `date_str` threaded through full call chain: endpoint → `get_best_bets(date=)` → `_best_bets_inner(date_str=)`

**4. Pick Logger Pipeline Fixed (CRITICAL)**

Three bugs found and fixed in the pick logging path:

| Bug | Root Cause | Fix |
|-----|------------|-----|
| `pytz` not defined | `pytz` used in `_enrich_pick_for_logging` but never imported in that scope | Added `import pytz as _pytz` inside the try block |
| `float(None)` crash | `pick_data.get("field", 0)` returns `None` when key exists with `None` value | Added `_f()`/`_i()` None-safe helpers in `pick_logger.py` |
| No logging visibility | `logged_count` never included in debug output | Added `picks_logged`, `picks_skipped_dupes`, `pick_log_errors` to debug block |

**5. Autograder Dry-Run Cleanup**

- Dry-run now skips picks with `grade_status="FAILED"` and empty `canonical_player_id` (old test seeds)
- Reports `skipped_stale_seeds` and `skipped_already_graded` counts
- 4 old test seeds (LeBron, Brandon Miller, Test Player Seed x2) no longer pollute dry-run

**6. Query Parameters Added**

| Param | Default | Purpose |
|-------|---------|---------|
| `max_events` | 12 | Cap events before props fetch |
| `max_props` | 10 | Cap prop picks in output |
| `max_games` | 10 | Cap game picks in output |
| `debug` | 0 | Enable debug output |
| `date` | today ET | Override date for testing |

### Verification Results (Production)

```
picks_attempted: 20
picks_logged: 12        ✅
picks_skipped_dupes: 8  ✅ (correctly deduped from earlier call)
pick_log_errors: []     ✅
total_elapsed_s: 5.57   ✅ (under 15s budget)
timed_out_components: [] ✅

Dry-run:
  total: 34, pending: 30, failed: 0, unresolved: 0
  overall_status: PENDING  ✅
  skipped_stale_seeds: 4   ✅
```

### Key Design Decisions

1. **Pick dedupe is DATE-BOUND (ET)**: `pick_hashes` keyed by `get_today_date_et()`. Tomorrow's picks won't be blocked by today's hashes.
2. **Grader scans ET date window**: `get_picks_for_grading()` defaults to today ET, allows yesterday for morning grading.
3. **Player resolution graceful degradation**: If BallDontLie times out, falls back to `{SPORT}:NAME:{name}|{team}` canonical ID. Props are never blocked by resolver failures.
4. **Game picks run before props**: Game picks are fast (no player resolution), so they complete first and aren't at risk of being skipped by the time budget.

### Files Changed

```
live_data_router.py   (MODIFIED - Performance overhaul, debug instrumentation, pick logging fixes, smoke test endpoint)
pick_logger.py        (MODIFIED - None-safe float/int conversions)
time_filters.py       (UNCHANGED - ET bounds already correct)
```

**7. Smoke Test Endpoint**

Added `GET` and `HEAD` `/live/smoke-test/alert-status` — returns `{"ok": true}`. Uptime monitors were hitting this path and logging 404s.

**8. Grade-Ready: Allow line=0 for Game Picks**

Game picks can have `line=0` (pick-em spread). `check_grade_ready()` no longer flags `line_at_bet` as missing for game picks (only for prop picks with `player_name`).

---

## Production Readiness Smoke Checks (Backend)

### 0) Required env
- Base URL (Railway): `https://web-production-7b2a.up.railway.app`
- API key header: `X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4`

### 1) Uptime monitor endpoint
Must return **200 for both HEAD and GET**.

```bash
echo "=== HEAD ===" && \
curl -I "https://web-production-7b2a.up.railway.app/live/smoke-test/alert-status" && \
echo && echo "=== GET ===" && \
curl -s "https://web-production-7b2a.up.railway.app/live/smoke-test/alert-status" && echo
```

### 2) Best-bets pick logging
Must show `pick_log_errors: []` and either `picks_logged > 0` (first call) or `picks_skipped_dupes > 0` (repeat).

```bash
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['debug']; \
    [print(f'{k}: {d[k]}') for k in ['picks_attempted','picks_logged','picks_skipped_dupes','pick_log_errors','total_elapsed_s']]"
```

### 3) Grader dry-run
Must show `pre_mode_pass: true`, `failed: 0`, `unresolved: 0`.

```bash
curl -s -X POST "https://web-production-7b2a.up.railway.app/live/grader/dry-run" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-01-27","mode":"pre"}' | python3 -m json.tool
```

### 4) Grader status
Must show `available: true`, `weights_loaded: true`, `predictions_logged > 0`.

```bash
curl -s "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | python3 -m json.tool
```

---
