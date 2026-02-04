# Endpoint Contract Manifest (Backend → Frontend)

Date: 2026-02-03

This manifest is the single reference for member-facing endpoints. It focuses on **best-bets**, **props**, and **live betting** payloads and their required fields.

## Shared Pick Field Contract (Required)

All pick payloads returned by best-bets or live endpoints must include the following fields (even when 0.0):

- `base_4_score`
- `context_modifier`
- `confluence_boost`
- `msrf_boost`
- `jason_sim_boost`
- `serp_boost`
- `final_score`
- `ensemble_adjustment` (0.0 when not applied)
- `context_reasons` (array)
- `confluence_reasons` (array)
- `msrf_status`
- `serp_status`
- `jason_status`

Live-only fields (present on live endpoints, or present with 0.0 on best-bets if available):
- `live_adjustment`
- `live_reasons` (array)

### Scoring Formula (Option A)
```
FINAL = BASE_4
      + context_modifier
      + confluence_boost
      + msrf_boost
      + jason_sim_boost
      + serp_boost
      + ensemble_adjustment (if present)
      + live_adjustment (live-only)
```
- `BASE_4 = ai*0.25 + research*0.35 + esoteric*0.20 + jarvis*0.20`
- `context_modifier` is bounded in ±0.35

## Error Schema (Structured, Fail-Soft)

Endpoints should return HTTP 200 when possible. If errors occur:
```
{
  "detail": {
    "code": "BEST_BETS_FAILED",
    "message": "...",
    "request_id": "...",          // debug only
    "error_type": "...",          // debug only
    "error_message": "...",       // debug only
    "traceback": "..."            // debug only
  }
}
```

## Endpoints

### 1) GET `/live/best-bets/{sport}`
**Query Params**
- `mode`: optional; `live` filters is_live candidates
- `min_score`: optional; default 6.5 (debug allows 5.0)
- `debug`: `1` returns expanded candidates + breakdowns (no cache)
- `date`: optional ET date (YYYY-MM-DD)
- `max_events`: default 12, max 30
- `max_props`: default 10, max 50
- `max_games`: default 10, max 50

**Response (shape)**
```
{
  "sport": "NBA",
  "props": {
    "count": 0,
    "picks": []
  },
  "game_picks": {
    "count": 0,
    "picks": []
  },
  "meta": { ... },
  "date_et": "YYYY-MM-DD",
  "run_timestamp_et": "HH:MM:SS ET"
}
```

### 2) GET `/live/props/{sport}`
**Purpose**: raw prop markets from Odds API/Playbook.

**Response (shape)**
```
{
  "sport": "NBA",
  "source": "odds_api|playbook|generated",
  "count": 0,
  "data": []
}
```

### 3) GET `/live/in-play/{sport}`
**Purpose**: live picks filtered from best-bets (started games).

**Response (shape)**
```
{
  "sport": "NBA",
  "type": "LIVE_BETS",
  "picks": [],
  "live_games_count": 0,
  "community_threshold": 6.5,
  "timestamp": "..."
}
```

### 4) GET `/in-game/{sport}`
**Purpose**: live picks for MISSED_START games + live context.

**Response (shape)**
```
{
  "sport": "NBA",
  "source": "live_in_game_v11.15",
  "live_props": { "count": 0, "picks": [] },
  "live_game_picks": { "count": 0, "picks": [] },
  "trigger_windows": { "games_in_window": 0, "games": [] },
  "bdl_context": { ... },
  "bdl_configured": false,
  "timestamp": "..."
}
```

### 5) GET `/live/debug/integrations`
**Purpose**: fail-loud integration visibility (env + connectivity + usage telemetry).

**Response (shape)**
```
{
  "overall_status": "HEALTHY|DEGRADED|CRITICAL",
  "by_status": {
    "validated": [],
    "configured": [],
    "unreachable": [],
    "disabled": [],
    "not_configured": []
  },
  "integrations": {
    "odds_api": { "status_category": "VALIDATED", "last_used_at": "...", "used_count": 0 },
    "serpapi": { "status_category": "VALIDATED", "last_used_at": "...", "used_count": 0 }
  }
}
```

### 6) GET `/live/debug/pick-breakdown/{sport}`
**Purpose**: debug-only full scoring breakdown for validation (no new scoring).

### 7) GET `/live/grader/status`
**Purpose**: learning loop health (counts, timestamps, storage path status).

### 8) GET `/live/scheduler/status`
**Purpose**: ET schedule visibility + job registration.

## Notes
- For offseason sports (e.g., MLB), endpoints must still return the shape above with empty arrays and `count=0`.
- Debug payloads (`?debug=1`) must include full scoring breakdowns and `used_integrations` where supported.
- Debug payloads also include integration telemetry blocks:
  - `debug.integration_calls`
  - `debug.integration_impact`
  - `debug.integration_totals`
