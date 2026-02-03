# Frontend Integration Guide

**Last Updated:** February 2, 2026
**Backend Version:** v17.3
**Frontend Repo:** [bookie-member-app](https://github.com/peterostrander2/bookie-member-app)

---

## Quick Reference

When working on frontend, check:
1. This file for backend → frontend field mapping
2. `/Users/apple/bookie-member-app/CLAUDE.md` for frontend patterns
3. Backend `docs/PICK_CONTRACT_V1.md` for full pick schema

---

## Current Wiring Status

### Fully Wired (Working)

| Backend Field | Frontend Usage | Component |
|--------------|----------------|-----------|
| `pick_id`, `sport`, `matchup` | Pick card identity | PropsSmashList, GameSmashList |
| `home_team`, `away_team` | Game display | GameSmashList |
| `start_time_et`, `has_started`, `is_live` | Time/status display | All pick components |
| `tier`, `final_score`, `units` | Tier badges, unit sizing | SmashSpotsPage |
| `titanium_triggered` | TITANIUM SMASH badge | PropsSmashList, GameSmashList |
| `ai_score`, `research_score`, `esoteric_score`, `jarvis_score` | 4-Engine breakdown | Pick cards |
| `line`, `odds_american`, `book` | Bet details | BetslipModal |
| `bet_string`, `market_label`, `selection` | Bet instruction | Pick cards |
| `book_link`, `sportsbook_event_url` | Click-to-bet | BetslipModal |
| `confidence_label`, `signals_fired` | Signal indicators | Pick cards |

---

## Pending Frontend Work

### Priority 1: Add 5th Engine (Context Score)

**Backend provides:** `context_modifier` (bounded ±0.35) and `context_score` (raw 0-10 for transparency)

**Current state:** Frontend shows 4 engines; context is a modifier, not a weighted engine.

**Files to modify:**
- `PropsSmashList.jsx` - Add context_score to engine breakdown
- `GameSmashList.jsx` - Add context_score to engine breakdown
- `SmashSpotsPage.jsx` - Update any engine legends

**Display suggestion:**
```jsx
// Current (4 engines)
AI: 7.2 | Research: 4.5 | Esoteric: 4.8 | Jarvis: 5.0

// Updated (context as modifier)
AI: 7.2 | Research: 4.5 | Esoteric: 4.8 | Jarvis: 5.0 | Context Mod: +0.18
```

**Engine Weights for reference:**
- AI: 25%
- Research: 35%
- Esoteric: 20%
- Jarvis: 20%
- **Context: modifier only (±0.35 cap)**

---

### Priority 2: Context Layer Details (Tooltip/Expandable)

**Backend provides:**
```json
{
  "context_layer": {
    "def_rank": 4,           // Opponent defensive rank (1-30, lower = better defense)
    "pace": 101.0,           // Expected game pace
    "vacuum": 0.0,           // Injury usage vacuum (0-1)
    "officials_adjustment": 0.0,  // Referee impact
    "park_adjustment": 0.0   // MLB park factors
  },
  "context_breakdown": {
    "def_rank": 4,
    "def_component": 9.03,   // Contribution to context_score
    "pace": 101.0,
    "pace_component": 5.5,
    "vacuum": 0.0,
    "vacuum_component": 5.0,
    "total": 7.17
  }
}
```

**Display suggestion:** Show on hover/tap or in expanded view:
```
Context Score: 7.2
├── vs #4 Defense → +9.0
├── Pace 101 → +5.5
└── Vacuum 0% → +5.0
```

---

### Priority 3: Harmonic Convergence Badge

**Backend provides:** `harmonic_boost` (0 or 1.5)

**When it triggers:** Research >= 7.5 AND Esoteric >= 7.5 (Math + Magic alignment)

**Display suggestion:** Special badge/glow when `harmonic_boost > 0`
```jsx
{pick.harmonic_boost > 0 && (
  <Badge color="purple">HARMONIC</Badge>
)}
```

---

### Priority 4: MSRF Turn Date Resonance

**Backend provides:**
```json
{
  "msrf_boost": 0.5,         // 0, 0.25, 0.5, or 1.0
  "msrf_metadata": {
    "level": "HIGH_RESONANCE",
    "points": 5.5,
    "source": "msrf_live"
  }
}
```

**Display suggestion:** Show when `msrf_boost > 0`:
```jsx
{pick.msrf_boost > 0 && (
  <Badge color="gold">TURN DATE: {pick.msrf_metadata?.level}</Badge>
)}
```

---

### Priority 5: Officials Impact (When Available)

**Backend provides:** `context_layer.officials_adjustment`

**Note:** Officials data comes from ESPN, may not be available for all games (refs assigned close to game time).

**Display suggestion:** Show when non-zero:
```jsx
{pick.context_layer?.officials_adjustment !== 0 && (
  <span>Ref Factor: {pick.context_layer.officials_adjustment > 0 ? '+' : ''}{pick.context_layer.officials_adjustment}</span>
)}
```

---

## API Response Structure

### `/live/best-bets/{sport}` Response

```json
{
  "sport": "NBA",
  "date_et": "2026-02-02",
  "game_picks": {
    "count": 10,
    "picks": [
      {
        // Identity
        "pick_id": "c39fd3f5b3ed",
        "sport": "NBA",
        "matchup": "Houston Rockets @ Indiana Pacers",
        "home_team": "Indiana Pacers",
        "away_team": "Houston Rockets",
        "event_id": "Houston Rockets@Indiana Pacers",

        // Timing
        "start_time_et": "7:10 PM ET",
        "has_started": false,
        "is_live": false,

        // 5 ENGINE SCORES (all 0-10)
        "ai_score": 7.19,
        "research_score": 4.5,
        "esoteric_score": 4.8,
        "jarvis_score": 5.0,
        "context_score": 7.17,        // NEW - 30% weight
        "final_score": 9.65,

        // Tier
        "tier": "EDGE_LEAN",          // TITANIUM_SMASH | GOLD_STAR | EDGE_LEAN
        "titanium_triggered": false,
        "units": 1.0,

        // Bet Details
        "pick_type": "spread",
        "selection": "Indiana Pacers",
        "line": 6.5,
        "line_signed": "+6.5",
        "odds_american": -104,
        "book": "LowVig.ag",
        "book_link": "",
        "bet_string": "Indiana Pacers +6.5 (-104) — 1.0u",

        // Context Layer (Pillars 13-17)
        "context_layer": {
          "def_rank": 4,
          "pace": 101.0,
          "vacuum": 0.0,
          "officials_adjustment": 0.0,
          "park_adjustment": 0.0
        },
        "context_breakdown": {
          "def_rank": 4,
          "def_component": 9.03,
          "pace": 101.0,
          "pace_component": 5.5,
          "vacuum": 0.0,
          "vacuum_component": 5.0,
          "total": 7.17
        },

        // Boosts
        "harmonic_boost": 0.0,        // +1.5 when Math+Magic align
        "msrf_boost": 0.0,            // Turn date resonance
        "msrf_metadata": null,

        // Signals
        "signals_fired": ["Sharp Money Detection", "Public Fade Opportunity"],
        "confluence_reasons": ["Jason BOOST: Pick-side win% 61.9% >= 61.0%"],
        "confidence_label": "HIGH"
      }
    ]
  },
  "props": {
    "count": 0,
    "picks": []
  }
}
```

---

## Tier Display Reference

| Tier | Threshold | Color | Badge |
|------|-----------|-------|-------|
| TITANIUM_SMASH | 3/4 engines >= 8.0 | Cyan #00FFFF | Glow effect |
| GOLD_STAR | final >= 7.5 + gates | Gold #FFD700 | Star icon |
| EDGE_LEAN | final >= 6.5 | Green #10B981 | Checkmark |

---

## Testing Frontend Changes

After any frontend changes, verify with:

```bash
# 1. Check API returns expected structure
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA" \
  -H "X-API-Key: YOUR_KEY" | jq '.game_picks.picks[0] | {
    context_score,
    context_layer,
    harmonic_boost,
    msrf_boost
  }'

# 2. Verify all 5 sports return data
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/$sport" \
    -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | \
    jq '{games: .game_picks.count, props: .props.count}'
done
```

---

## Files to Modify (Frontend Repo)

| File | Changes Needed |
|------|----------------|
| `PropsSmashList.jsx` | Add context_score to engine display |
| `GameSmashList.jsx` | Add context_score to engine display |
| `SmashSpotsPage.jsx` | Update engine legend, add Harmonic badge |
| `signalEngine.js` | Add context layer signal parsing (optional) |

---

## Changelog

### v17.3 (Feb 2026)
- Added `context_score` (5th engine, 30% weight)
- Added `context_layer` with def_rank, pace, vacuum
- Added `harmonic_boost` for Math+Magic alignment
- Added `msrf_boost` and `msrf_metadata` for turn date resonance
- Expanded officials database (+93 officials)
- Lowered HARMONIC_CONVERGENCE threshold from 8.0 to 7.5
