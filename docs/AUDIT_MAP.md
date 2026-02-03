# Integration Audit Map

**AUTO-GENERATED from `core/integration_contract.py` - DO NOT EDIT MANUALLY**

Run `./scripts/generate_audit_map.sh` to regenerate.

## Summary

- **Total Integrations:** 14
- **Required:** 14
- **Optional:** 0

## Integration Details

| Integration | Env Vars | Required | Owner Modules | Feeds Engine | Description |
|-------------|----------|----------|---------------|--------------|-------------|
| **Astronomy API** | `ASTRONOMY_API_ID`, `ASTRONOMY_API_SECRET` | ✅ Yes | `astronomy_api.py` | esoteric | Lunar phases and celestial data |
| **BallDontLie API** | `BALLDONTLIE_API_KEY`, `BDL_API_KEY` | ✅ Yes | `balldontlie.py`, `auto_grader.py` | grader | NBA stats and player data for grading |
| **Supabase Database** | `DATABASE_URL` | ✅ Yes | `database.py` | persistence | Primary database for application data |
| **Finnhub Market Data** | `FINNHUB_KEY` | ✅ Yes | `finnhub_api.py` | research | Financial market sentiment |
| **FRED Economic Data** | `FRED_API_KEY` | ✅ Yes | `fred_api.py` | research | Federal Reserve economic indicators |
| **NOAA Space Weather** | `NOAA_BASE_URL` | ✅ Yes | `noaa_api.py` | esoteric | Space weather and geomagnetic data |
| **The Odds API** | `ODDS_API_KEY` | ✅ Yes | `odds_api.py`, `live_data_router.py` | research | Sports betting odds data provider |
| **Playbook API** | `PLAYBOOK_API_KEY` | ✅ Yes | `playbook_api.py`, `live_data_router.py` | research | Advanced sports analytics and insights |
| **Railway Volume Storage** | `RAILWAY_VOLUME_MOUNT_PATH` | ✅ Yes | `storage_paths.py`, `data_dir.py`, `grader_store.py` | persistence | Persistent storage for picks and predictions |
| **Redis Cache** | `REDIS_URL` | ✅ Yes | `cache.py` | performance | In-memory cache for performance |
| **SerpAPI** | `SERPAPI_KEY` | ✅ Yes | `serpapi.py` | research | Search engine results for research |
| **Twitter/X API** | `TWITTER_BEARER` | ✅ Yes | `twitter_api.py` | research | Social sentiment analysis |
| **Weather API** | `WEATHER_API_KEY` | ✅ Yes | `weather_api.py`, `live_data_router.py` | context_modifiers | Weather data for outdoor sports context |
| **Whop Payments** | `WHOP_API_KEY` | ✅ Yes | `whop_integration.py` | none | Payment and membership management |

## Special Rules

### Weather Integration

- **Status:** Required but relevance-gated
- **Allowed Statuses:** `VALIDATED`, `CONFIGURED`, `NOT_RELEVANT`, `UNAVAILABLE`, `ERROR`, `MISSING`
- **Banned Statuses:** `FEATURE_DISABLED`, `DISABLED` (hard ban)
- **Behavior:** Returns `NOT_RELEVANT` for indoor sports, never feature-disabled

### BallDontLie Integration

- **Env Var Aliases:** Accepts both `BALLDONTLIE_API_KEY` and `BDL_API_KEY`

## Runtime Status

For current integration status, query:
```bash
curl "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" | jq .
```

## Validation

This document is validated by:
- `scripts/validate_integration_contract.sh` (pre-commit hook)
- Session 4 in CI (`scripts/ci_sanity_check.sh`)
