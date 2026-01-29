# ENV_VAR_MAPPING.md - Canonical Environment Variable to Code Mapping

**Last Updated:** 2026-01-29
**Status:** CANONICAL SOURCE OF TRUTH

This document maps EVERY environment variable to its exact usage in code.

---

## 🔑 INTEGRATION API KEYS (14 Total)

### 1. ODDS_API_KEY (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | odds_api |
| **Required** | ✅ Yes |
| **Fallback** | `EXPO_PUBLIC_ODDS_API_KEY` |

| File | Line | Usage |
|------|------|-------|
| `live_data_router.py` | 221 | `ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")` |
| `result_fetcher.py` | 64 | `ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")` |
| `daily_scheduler.py` | 82 | `odds_api_key = os.getenv("ODDS_API_KEY", "")` |
| `playbook_api.py` | - | Referenced for line shop |

| Endpoint | Purpose |
|----------|---------|
| `/live/best-bets/{sport}` | Props and games fetch |
| `/live/props/{sport}` | Player props |
| `/live/lines/{sport}` | Current lines |
| `/live/odds/{sport}` | Current odds |
| `/live/line-shop/{sport}` | Multi-book comparison |

---

### 2. PLAYBOOK_API_KEY (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | playbook_api |
| **Required** | ✅ Yes |
| **Fallback** | `EXPO_PUBLIC_PLAYBOOK_API_KEY` |

| File | Line | Usage |
|------|------|-------|
| `live_data_router.py` | 224 | `PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")` |
| `playbook_api.py` | 12 | `PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")` |
| `result_fetcher.py` | 387 | `PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")` |

| Endpoint | Purpose |
|----------|---------|
| `/live/sharp/{sport}` | Sharp money signals |
| `/live/splits/{sport}` | Public betting splits |
| `/live/injuries/{sport}` | Injury reports |
| `/live/best-bets/{sport}` | Research engine data |

---

### 3. BALLDONTLIE_API_KEY / BDL_API_KEY (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | balldontlie |
| **Required** | ✅ Yes |
| **Fallback** | `BDL_API_KEY` |
| **NOTE** | **NO HARDCODED FALLBACK** - env var REQUIRED |

| File | Line | Usage |
|------|------|-------|
| `alt_data_sources/balldontlie.py` | 37 | `BDL_API_KEY = os.getenv("BALLDONTLIE_API_KEY", os.getenv("BDL_API_KEY", ""))` |
| `result_fetcher.py` | 500 | `BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY", os.getenv("BDL_API_KEY", ""))` |
| `identity/player_resolver.py` | 44 | `BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY", os.getenv("BDL_API_KEY", ""))` |
| `main.py` | 558 | `BDL_KEY = _os.getenv("BALLDONTLIE_API_KEY", _os.getenv("BDL_API_KEY", ""))` |

| Endpoint | Purpose |
|----------|---------|
| `/live/best-bets/NBA` | NBA player props context |
| `/live/grader/run-audit` | NBA prop grading |
| `/live/picks/grading-summary` | Graded picks lookup |

---

### 4. WEATHER_API_KEY / OPENWEATHER_API_KEY (OPTIONAL - DISABLED)

| Attribute | Value |
|-----------|-------|
| **Integration** | weather_api |
| **Required** | ❌ No (feature flagged) |
| **Feature Flag** | `WEATHER_ENABLED=false` (default) |
| **Status** | STUBBED - returns `{"available": false, "reason": "FEATURE_DISABLED"}` |

| File | Line | Usage |
|------|------|-------|
| `alt_data_sources/weather.py` | 30-31 | `WEATHER_ENABLED`, `OPENWEATHER_API_KEY` |

| Endpoint | Purpose |
|----------|---------|
| `/live/best-bets/NFL` | (when enabled) Outdoor weather impact |
| `/live/best-bets/MLB` | (when enabled) Outdoor weather impact |

---

### 5. ASTRONOMY_API_ID / ASTRONOMY_API_SECRET (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | astronomy_api |
| **Required** | ✅ Yes |
| **Fallback** | `EXPO_PUBLIC_ASTRONOMY_API_ID`, `EXPO_PUBLIC_ASTRONOMY_API_SECRET` |

| File | Line | Usage |
|------|------|-------|
| `esoteric_engine.py` | - | Moon phase, planetary hours |
| `astronomical_api.py` | - | API client |

| Endpoint | Purpose |
|----------|---------|
| `/live/esoteric-edge` | Esoteric signals |
| `/esoteric/today-energy` | Daily energy reading |
| `/live/best-bets/{sport}` | Esoteric engine (20% weight) |

---

### 6. NOAA_BASE_URL (REQUIRED - FREE API)

| Attribute | Value |
|-----------|-------|
| **Integration** | noaa_space_weather |
| **Required** | ✅ Yes |
| **Default** | `https://services.swpc.noaa.gov` |
| **Auth** | None (free public API) |

| File | Line | Usage |
|------|------|-------|
| `esoteric_engine.py` | - | Kp-index, solar activity |

| Endpoint | Purpose |
|----------|---------|
| `/live/esoteric-edge` | Solar/geomagnetic data |
| `/esoteric/today-energy` | Daily energy |

---

### 7. FRED_API_KEY (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | fred_api |
| **Required** | ✅ Yes |

| File | Line | Usage |
|------|------|-------|
| `esoteric_engine.py` | - | Economic sentiment |

| Endpoint | Purpose |
|----------|---------|
| `/live/esoteric-edge` | Economic indicators |
| `/live/best-bets/{sport}` | Sentiment factor |

---

### 8. FINNHUB_KEY / FINNHUB_API_KEY (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | finnhub_api |
| **Required** | ✅ Yes |
| **Fallback** | `FINNHUB_API_KEY` |

| File | Line | Usage |
|------|------|-------|
| `esoteric_engine.py` | - | Sportsbook stock prices |

| Endpoint | Purpose |
|----------|---------|
| `/live/esoteric-edge` | Market sentiment |

---

### 9. SERPAPI_KEY / SERP_API_KEY (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | serpapi |
| **Required** | ✅ Yes |
| **Fallback** | `SERP_API_KEY` |

| File | Line | Usage |
|------|------|-------|
| `esoteric_engine.py` | - | News sentiment, trending topics |

| Endpoint | Purpose |
|----------|---------|
| `/live/esoteric-edge` | News aggregation |
| `/live/best-bets/{sport}` | Trending analysis |

---

### 10. TWITTER_BEARER / TWITTER_BEARER_TOKEN (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | twitter_api |
| **Required** | ✅ Yes |
| **Fallback** | `TWITTER_BEARER_TOKEN` |

| File | Line | Usage |
|------|------|-------|
| `esoteric_engine.py` | - | Breaking news, injury tweets |

| Endpoint | Purpose |
|----------|---------|
| `/live/esoteric-edge` | Real-time sentiment |
| `/live/best-bets/{sport}` | Injury news |

---

### 11. WHOP_API_KEY (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | whop_api |
| **Required** | ✅ Yes |

| File | Line | Usage |
|------|------|-------|
| `auth.py` | - | Membership verification |

| Endpoint | Purpose |
|----------|---------|
| `/auth/verify` | Premium access check |
| `/auth/webhook` | Membership events |

---

### 12. DATABASE_URL (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | database |
| **Required** | ✅ Yes |
| **Format** | PostgreSQL connection string |

| File | Line | Usage |
|------|------|-------|
| `database.py` | 17 | `DATABASE_URL = os.getenv("DATABASE_URL", "")` |

| Endpoint | Purpose |
|----------|---------|
| All endpoints | Primary data store |

---

### 13. REDIS_URL (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | redis |
| **Required** | ✅ Yes |
| **Format** | Redis connection string |

| File | Line | Usage |
|------|------|-------|
| `live_data_router.py` | 245 | `REDIS_URL = os.getenv("REDIS_URL", "")` |
| `cache.py` | - | Cache operations |

| Endpoint | Purpose |
|----------|---------|
| All endpoints | Response caching |

---

### 14. RAILWAY_VOLUME_MOUNT_PATH (REQUIRED)

| Attribute | Value |
|-----------|-------|
| **Integration** | railway_storage |
| **Required** | ✅ Yes |
| **Fallback** | `GRADER_MOUNT_ROOT` |
| **Production Value** | `/app/grader_data` |

| File | Line | Usage |
|------|------|-------|
| `storage_paths.py` | 32-36 | Mount path resolution |
| `data_dir.py` | 21 | `_railway_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")` |
| `main.py` | 401 | Status display |

| Endpoint | Purpose |
|----------|---------|
| `/live/best-bets/{sport}` | Pick persistence |
| `/live/grader/status` | Storage health |
| `/internal/storage/health` | Volume health check |

---

## 🎛️ FEATURE FLAGS

| Env Var | Default | File | Purpose |
|---------|---------|------|---------|
| `WEATHER_ENABLED` | `false` | `alt_data_sources/weather.py` | Enable weather analysis |
| `REFS_ENABLED` | `false` | `alt_data_sources/refs.py` | Enable referee analysis |
| `STADIUM_ENABLED` | `false` | `alt_data_sources/stadium.py` | Enable stadium analysis |
| `TRAVEL_ENABLED` | `false` | `alt_data_sources/travel.py` | Enable travel fatigue |
| `PHYSICS_ENABLED` | `true` | `signals/physics.py` | Physics signals |
| `HIVE_MIND_ENABLED` | `true` | `signals/hive_mind.py` | Hive mind signals |
| `MARKET_SIGNALS_ENABLED` | `true` | `signals/market.py` | Market signals |
| `MATH_GLITCH_ENABLED` | `true` | `signals/math_glitch.py` | Math glitch detection |

---

## 🔐 AUTH & CONFIG

| Env Var | File | Purpose |
|---------|------|---------|
| `API_AUTH_KEY` | `live_data_router.py:236` | API authentication key |
| `API_AUTH_ENABLED` | `live_data_router.py:237` | Enable auth (default: false) |
| `DEBUG_MODE` | `main.py:56` | Debug logging |
| `ADMIN_TOKEN` | `main.py:57` | Admin operations |

---

## 📍 BASE URLs (Override Defaults)

| Env Var | Default | File |
|---------|---------|------|
| `ODDS_API_BASE` | `https://api.the-odds-api.com/v4` | `live_data_router.py:222` |
| `PLAYBOOK_API_BASE` | `https://api.playbook-api.com/v1` | `live_data_router.py:225` |
| `NOAA_BASE_URL` | `https://services.swpc.noaa.gov` | `esoteric_engine.py` |

---

## ⚠️ UNUSED / DEPRECATED ENV VARS

These env vars may be set in Railway but are NOT used in current code:

| Env Var | Status | Notes |
|---------|--------|-------|
| `EXPO_PUBLIC_*` | FALLBACK | Only used if primary key not set |

---

## 📋 QUICK REFERENCE: Railway Required Vars

**Set these in Railway environment variables:**

```bash
# Core APIs (REQUIRED)
ODDS_API_KEY=xxx
PLAYBOOK_API_KEY=xxx
BALLDONTLIE_API_KEY=xxx  # or BDL_API_KEY

# Esoteric APIs (REQUIRED)
ASTRONOMY_API_ID=xxx
ASTRONOMY_API_SECRET=xxx
FRED_API_KEY=xxx
FINNHUB_KEY=xxx
SERPAPI_KEY=xxx
TWITTER_BEARER=xxx

# Platform (REQUIRED)
WHOP_API_KEY=xxx
DATABASE_URL=postgres://...
REDIS_URL=redis://...

# Storage (AUTO-SET by Railway)
RAILWAY_VOLUME_MOUNT_PATH=/app/grader_data

# Auth
API_AUTH_KEY=xxx
API_AUTH_ENABLED=true
```

---

## 🔍 Verification Command

Check all integrations status:
```bash
curl "https://web-production-7b2a.up.railway.app/live/debug/integrations" \
  -H "X-API-Key: YOUR_KEY"
```
