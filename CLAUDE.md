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

## Signal Architecture (Dual Engine)

### Scoring Formula
```
SMASH PICK = AI_Models (0-8) + Pillars (0-8) + JARVIS (0-4) + Esoteric_Boost
```

### Components

1. **8 AI Models** (max 8 pts) - `advanced_ml_backend.py`
   - Ensemble, LSTM, Matchup, Monte Carlo, Line Movement, Rest/Fatigue, Injury, Betting Edge

2. **8 Pillars** (max 8 pts) - `advanced_ml_backend.py`
   - Sharp Split, Reverse Line, Hospital Fade, Situational Spot, Expert Consensus, Prop Correlation, Hook Discipline, Volume Discipline

3. **JARVIS Triggers** (max 4 pts) - `live_data_router.py:233-239`
   - Gematria signals: 2178, 201, 33, 93, 322
   - Weight: `boost / 5` (doubled from original /10)

4. **Esoteric Edge** (18 modules) - `live_data_router.py`
   - NOOSPHERE VELOCITY, GANN PHYSICS, SCALAR-SAVANT, OMNI-GLITCH

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

### Code Standards

- Use ES modules with proper import sorting
- Prefer `function` keyword over arrow functions for top-level
- Use explicit return type annotations
- Avoid nested ternary operators - prefer switch/if-else
- Choose clarity over brevity
- Remove unnecessary comments that describe obvious code

### What NOT to Do

- Change functionality or outputs
- Create overly clever solutions
- Combine too many concerns into single functions
- Remove helpful abstractions
- Prioritize "fewer lines" over readability

---

## Vercel Agent Skills (Installed January 16, 2026)

The following skills from `vercel-labs/agent-skills` are available for use in this project.

---

## Skill 1: Vercel Deploy

**Name:** vercel-deploy
**Purpose:** Deploy applications and websites to Vercel instantly. No authentication required.

### When to Use
Use when the user requests deployment actions such as:
- "Deploy my app"
- "Deploy this to production"
- "Create a preview deployment"
- "Deploy and give me the link"
- "Push this live"

### How It Works

1. Packages your project into a tarball (excludes `node_modules` and `.git`)
2. Auto-detects framework from `package.json`
3. Uploads to deployment service
4. Returns **Preview URL** (live site) and **Claim URL** (transfer to your Vercel account)

### Usage

```bash
bash /mnt/skills/user/vercel-deploy/scripts/deploy.sh [path]
```

**Arguments:**
- `path` - Directory to deploy, or a `.tgz` file (defaults to current directory)

### Output

```
Preview URL: https://skill-deploy-abc123.vercel.app
Claim URL:   https://vercel.com/claim-deployment?code=...
```

### Supported Frameworks

- **React**: Next.js, Gatsby, Create React App, Remix, React Router
- **Vue**: Nuxt, Vitepress, Vuepress, Gridsome
- **Svelte**: SvelteKit, Svelte, Sapper
- **Other Frontend**: Astro, Solid Start, Angular, Ember, Preact, Docusaurus
- **Backend**: Express, Hono, Fastify, NestJS, Elysia, h3, Nitro
- **Build Tools**: Vite, Parcel

---

## Skill 2: Web Design Guidelines

**Name:** web-design-guidelines
**Purpose:** Review UI code for Web Interface Guidelines compliance.

### When to Use
Use when asked to:
- "Review my UI"
- "Check accessibility"
- "Audit design"
- "Review UX"
- "Check my site against best practices"

### How It Works

1. Fetch the latest guidelines from: `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

---

## Skill 3: React Best Practices (Vercel Engineering)

**Name:** vercel-react-best-practices
**Version:** 1.0.0
**Purpose:** React and Next.js performance optimization guidelines from Vercel Engineering.

### When to Apply

Reference these guidelines when:
- Writing new React components or Next.js pages
- Implementing data fetching (client or server-side)
- Reviewing code for performance issues
- Refactoring existing React/Next.js code
- Optimizing bundle size or load times

### Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Eliminating Waterfalls | CRITICAL | `async-` |
| 2 | Bundle Size Optimization | CRITICAL | `bundle-` |
| 3 | Server-Side Performance | HIGH | `server-` |
| 4 | Client-Side Data Fetching | MEDIUM-HIGH | `client-` |
| 5 | Re-render Optimization | MEDIUM | `rerender-` |
| 6 | Rendering Performance | MEDIUM | `rendering-` |
| 7 | JavaScript Performance | LOW-MEDIUM | `js-` |
| 8 | Advanced Patterns | LOW | `advanced-` |

### Quick Reference

#### 1. Eliminating Waterfalls (CRITICAL)
- `async-defer-await` - Move await into branches where actually used
- `async-parallel` - Use Promise.all() for independent operations
- `async-dependencies` - Use better-all for partial dependencies
- `async-api-routes` - Start promises early, await late in API routes
- `async-suspense-boundaries` - Use Suspense to stream content

#### 2. Bundle Size Optimization (CRITICAL)
- `bundle-barrel-imports` - Import directly, avoid barrel files
- `bundle-dynamic-imports` - Use next/dynamic for heavy components
- `bundle-defer-third-party` - Load analytics/logging after hydration
- `bundle-conditional` - Load modules only when feature is activated
- `bundle-preload` - Preload on hover/focus for perceived speed

#### 3. Server-Side Performance (HIGH)
- `server-cache-react` - Use React.cache() for per-request deduplication
- `server-cache-lru` - Use LRU cache for cross-request caching
- `server-serialization` - Minimize data passed to client components
- `server-parallel-fetching` - Restructure components to parallelize fetches
- `server-after-nonblocking` - Use after() for non-blocking operations

#### 4. Client-Side Data Fetching (MEDIUM-HIGH)
- `client-swr-dedup` - Use SWR for automatic request deduplication
- `client-event-listeners` - Deduplicate global event listeners

#### 5. Re-render Optimization (MEDIUM)
- `rerender-defer-reads` - Don't subscribe to state only used in callbacks
- `rerender-memo` - Extract expensive work into memoized components
- `rerender-dependencies` - Use primitive dependencies in effects
- `rerender-derived-state` - Subscribe to derived booleans, not raw values
- `rerender-functional-setstate` - Use functional setState for stable callbacks
- `rerender-lazy-state-init` - Pass function to useState for expensive values
- `rerender-transitions` - Use startTransition for non-urgent updates

#### 6. Rendering Performance (MEDIUM)
- `rendering-animate-svg-wrapper` - Animate div wrapper, not SVG element
- `rendering-content-visibility` - Use content-visibility for long lists
- `rendering-hoist-jsx` - Extract static JSX outside components
- `rendering-svg-precision` - Reduce SVG coordinate precision
- `rendering-hydration-no-flicker` - Use inline script for client-only data
- `rendering-activity` - Use Activity component for show/hide
- `rendering-conditional-render` - Use ternary, not && for conditionals

#### 7. JavaScript Performance (LOW-MEDIUM)
- `js-batch-dom-css` - Group CSS changes via classes or cssText
- `js-index-maps` - Build Map for repeated lookups
- `js-cache-property-access` - Cache object properties in loops
- `js-cache-function-results` - Cache function results in module-level Map
- `js-cache-storage` - Cache localStorage/sessionStorage reads
- `js-combine-iterations` - Combine multiple filter/map into one loop
- `js-length-check-first` - Check array length before expensive comparison
- `js-early-exit` - Return early from functions
- `js-hoist-regexp` - Hoist RegExp creation outside loops
- `js-min-max-loop` - Use loop for min/max instead of sort
- `js-set-map-lookups` - Use Set/Map for O(1) lookups
- `js-tosorted-immutable` - Use toSorted() for immutability

#### 8. Advanced Patterns (LOW)
- `advanced-event-handler-refs` - Store event handlers in refs
- `advanced-use-latest` - useLatest for stable callback refs

### Key React Performance Patterns

#### Parallel Data Fetching
```typescript
// Incorrect: sequential
const user = await fetchUser()
const posts = await fetchPosts()

// Correct: parallel
const [user, posts] = await Promise.all([
  fetchUser(),
  fetchPosts()
])
```

#### Avoid Barrel File Imports
```tsx
// Incorrect: imports entire library
import { Check, X, Menu } from 'lucide-react'

// Correct: imports only what you need
import Check from 'lucide-react/dist/esm/icons/check'
import X from 'lucide-react/dist/esm/icons/x'
```

#### Dynamic Imports for Heavy Components
```tsx
import dynamic from 'next/dynamic'

const MonacoEditor = dynamic(
  () => import('./monaco-editor').then(m => m.MonacoEditor),
  { ssr: false }
)
```

#### Use SWR for Automatic Deduplication
```tsx
import useSWR from 'swr'

function UserList() {
  const { data: users } = useSWR('/api/users', fetcher)
}
```

#### Functional setState Updates
```tsx
// Incorrect: requires state as dependency
const addItems = useCallback((newItems: Item[]) => {
  setItems([...items, ...newItems])
}, [items])

// Correct: stable callbacks, no stale closures
const addItems = useCallback((newItems: Item[]) => {
  setItems(curr => [...curr, ...newItems])
}, [])
```

#### Use toSorted() for Immutability
```typescript
// Incorrect: mutates original array
const sorted = users.sort((a, b) => a.name.localeCompare(b.name))

// Correct: creates new array
const sorted = users.toSorted((a, b) => a.name.localeCompare(b.name))
```

### References

1. https://react.dev
2. https://nextjs.org
3. https://swr.vercel.app
4. https://github.com/shuding/better-all
5. https://vercel.com/blog/how-we-optimized-package-imports-in-next-js
6. https://vercel.com/blog/how-we-made-the-vercel-dashboard-twice-as-fast

---
