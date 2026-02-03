# PickContract v1 - API Response Contract

**Version:** 1.0
**Implemented:** February 1, 2026
**Commit:** e34dd18

## Overview

PickContract v1 defines the guaranteed fields for every pick returned by `/live/best-bets/{sport}` endpoints. This contract ensures the frontend can render exact bet instructions without guessing or recomputing values.

## Required Fields

Every pick object MUST contain ALL of these fields:

### Core Identity Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | string | Stable unique pick identifier | `"spread123"` |
| `sport` | string | Sport code (uppercase) | `"NBA"`, `"NHL"` |
| `league` | string | League code | `"NBA"`, `"NFL"` |
| `event_id` | string | Event/game identifier | `"game_abc123"` |
| `matchup` | string | Full matchup string | `"Milwaukee Bucks @ Boston Celtics"` |
| `home_team` | string | Home team name | `"Boston Celtics"` |
| `away_team` | string | Away team name | `"Milwaukee Bucks"` |
| `start_time_et` | string\|null | Display time in ET | `"7:30 PM ET"` |
| `start_time_iso` | string\|null | ISO 8601 timestamp | `"2026-02-01T00:30:00Z"` |
| `status` | string | Game status | `"scheduled"`, `"live"`, `"final"` |
| `has_started` | boolean | Whether game has started | `false` |
| `is_live` | boolean | Whether game is currently live | `false` |

### Bet Instruction Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pick_type` | string | Normalized bet type | `"spread"`, `"moneyline"`, `"total"`, `"player_prop"` |
| `market_label` | string | Human-readable market | `"Spread"`, `"Moneyline"`, `"Total"`, `"Points"` |
| `selection` | string | What to bet on | `"Milwaukee Bucks"`, `"LeBron James"` |
| `selection_home_away` | string\|null | HOME, AWAY, or null | `"HOME"`, `"AWAY"`, `null` |
| `side_label` | string | Side for totals/props | `"Over"`, `"Under"` |
| `line` | number\|null | Numeric line value | `1.5`, `220.5`, `null` |
| `line_signed` | string\|null | Formatted line | `"+1.5"`, `"-3.5"`, `"O 220.5"` |
| `odds_american` | number\|null | American odds (NEVER fabricated) | `-110`, `+135`, `null` |
| `units` | number | Recommended bet units | `1.0`, `2.0` |
| `bet_string` | string | Complete bet instruction | `"Milwaukee Bucks +1.5 (-110) — 2.0u"` |
| `book` | string | Sportsbook name | `"draftkings"`, `"Consensus"` |
| `book_link` | string | Deep link to bet | `"https://..."` or `""` |

### Reasoning Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `tier` | string | Bet tier classification | `"TITANIUM_SMASH"`, `"GOLD_STAR"`, `"EDGE_LEAN"` |
| `score` | number | Final pick score (0-10) | `8.5` |
| `confidence_label` | string | Confidence level | `"PLAY"`, `"STRONG"` |
| `signals_fired` | array | List of fired signals | `["sharp_money", "line_variance"]` |
| `confluence_reasons` | array | Reasoning explanations | `["Strong sharp signal on spread"]` |
| `engine_breakdown` | object | 4-engine score breakdown | `{"ai": 8.0, "research": 7.5, ...}` |

## Pick Types

### Spread
```json
{
  "pick_type": "spread",
  "market_label": "Spread",
  "selection": "Milwaukee Bucks",
  "selection_home_away": "AWAY",
  "line": 1.5,
  "line_signed": "+1.5",
  "bet_string": "Milwaukee Bucks +1.5 (-110) — 2.0u"
}
```

### Moneyline
```json
{
  "pick_type": "moneyline",
  "market_label": "Moneyline",
  "selection": "Boston Celtics",
  "selection_home_away": "HOME",
  "line": null,
  "line_signed": null,
  "bet_string": "Boston Celtics ML (-150) — 1.5u"
}
```

### Total
```json
{
  "pick_type": "total",
  "market_label": "Total",
  "selection": "Celtics/Lakers",
  "selection_home_away": null,
  "side_label": "Over",
  "line": 220.5,
  "line_signed": "O 220.5",
  "bet_string": "Celtics/Lakers Over 220.5 (-110) — 1.0u"
}
```

### Player Prop
```json
{
  "pick_type": "player_prop",
  "market_label": "Points",
  "selection": "LeBron James",
  "selection_home_away": null,
  "side_label": "Over",
  "line": 25.5,
  "line_signed": "O 25.5",
  "bet_string": "LeBron James — Points Over 25.5 (-120) — 1.0u"
}
```

## selection_home_away Logic

The `selection_home_away` field is computed by comparing `selection` against `home_team` and `away_team`:

```python
if selection matches home_team:
    selection_home_away = "HOME"
elif selection matches away_team:
    selection_home_away = "AWAY"
else:
    selection_home_away = null  # For totals, props, etc.
```

Matching is case-insensitive and uses substring containment for partial team names.

## SHARP Pick Handling

SHARP picks from Jason Sim are normalized to standard types:
- **With line (line != 0)**: Becomes `pick_type: "spread"`
- **Without line (line == 0 or null)**: Becomes `pick_type: "moneyline"`

The `signal_label` field is set to `"Sharp Signal"` to indicate origin.

## odds_american Policy

**NEVER fabricate odds.** If odds are not available from the source:
- `odds_american` = `null`
- `bet_string` shows `"(N/A)"` for odds portion

Do NOT default to `-110` or any other value.

## Anti-Cache Headers

All `/live/best-bets/*` responses include:
```
Cache-Control: no-store, no-cache, must-revalidate, max-age=0, private
Pragma: no-cache
Expires: 0
Vary: Origin, X-API-Key, Authorization
```

## No Sample Data

When data is unavailable, return empty arrays:
```json
{
  "sport": "NHL",
  "props": {"count": 0, "picks": []},
  "game_picks": {"count": 0, "picks": []}
}
```

NEVER return sample/fallback picks with fake data.

## Implementation Files

| File | Purpose |
|------|---------|
| `utils/pick_normalizer.py` | Single source of truth for normalization |
| `live_data_router.py` | Applies normalization to API responses |
| `jason_sim_confluence.py` | SHARP type mapping |
| `tests/test_pick_contract_v1.py` | Contract verification tests |

## Frontend Usage

Frontend should render directly from API fields:

```typescript
// CORRECT: Use API values directly
<div>{pick.bet_string}</div>
<div>{pick.selection} ({pick.selection_home_away})</div>
<div>Score: {pick.score}</div>

// WRONG: Don't recompute
const betString = `${pick.team} ${pick.line}`; // NO!
```

## Verification

Run contract tests:
```bash
pytest tests/test_pick_contract_v1.py -v
```

All 12 tests must pass for contract compliance.
