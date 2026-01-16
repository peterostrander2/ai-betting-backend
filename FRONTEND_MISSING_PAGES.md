# Frontend Missing Pages - Backend Endpoint Mapping

**Status:** Backend endpoints are READY. Frontend pages need to be created.

**Frontend Repo:** `bookie-member-app`
**Backend URL:** `https://web-production-7b2a.up.railway.app`

---

## Quick Summary

| Page | Route | Backend Endpoint | Priority |
|------|-------|------------------|----------|
| Sharp Money | `/sharp` | `/live/sharp/{sport}` | HIGH |
| Best Odds | `/odds` | `/live/line-shop/{sport}` | HIGH |
| Injuries | `/injuries` | `/live/injuries/{sport}` | HIGH |
| Betting Splits | `/splits` | `/live/splits/{sport}` | HIGH |
| Esoteric | `/esoteric` | `/esoteric/today-energy` | MEDIUM |
| Performance | `/performance` | `/live/grader/performance/{sport}` | MEDIUM |
| Grade Picks | `/grading` | `/live/bets/grade/{bet_id}` | MEDIUM |
| Bankroll | `/bankroll` | `/live/bets/history` | LOW |

---

## Page 1: Sharp Money (`/sharp`)

### Backend Endpoint
```
GET /live/sharp/{sport}
```

### Response Format
```json
{
  "sport": "NBA",
  "source": "playbook",
  "count": 5,
  "data": [
    {
      "game_id": "abc123",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "sharp_side": "Lakers -3.5",
      "sharp_percentage": 72,
      "public_percentage": 45,
      "line_movement": "-2.5 → -3.5",
      "steam_move": true,
      "reverse_line_movement": true
    }
  ],
  "timestamp": "2026-01-16T12:00:00"
}
```

### Component Structure
```jsx
// pages/Sharp.jsx
- SportTabs (NBA, NFL, MLB, NHL)
- SharpMoneyTable
  - GameRow
    - Team names
    - Sharp % vs Public % bar
    - Line movement indicator
    - Steam move badge
    - RLM badge (Reverse Line Movement)
```

### Key Features
- Show where sharp money differs from public
- Highlight reverse line movement (sharp money opposite of line move)
- Steam moves (sudden sharp action)

---

## Page 2: Best Odds Finder (`/odds`)

### Backend Endpoint
```
GET /live/line-shop/{sport}
```

### Response Format
```json
{
  "sport": "NBA",
  "games": [
    {
      "game_id": "abc123",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "commence_time": "2026-01-16T19:00:00Z",
      "best_odds": {
        "spread": {
          "home": {"line": -3.5, "odds": -108, "book": "DraftKings"},
          "away": {"line": 3.5, "odds": -105, "book": "FanDuel"}
        },
        "total": {
          "over": {"line": 220.5, "odds": -105, "book": "BetMGM"},
          "under": {"line": 220.5, "odds": -110, "book": "Caesars"}
        },
        "moneyline": {
          "home": {"odds": -150, "book": "PointsBet"},
          "away": {"odds": 135, "book": "BetRivers"}
        }
      },
      "all_books": {
        "draftkings": {...},
        "fanduel": {...},
        "betmgm": {...},
        "caesars": {...},
        "pointsbet": {...},
        "betrivers": {...},
        "espnbet": {...},
        "bet365": {...}
      }
    }
  ],
  "books_checked": 8
}
```

### Component Structure
```jsx
// pages/Odds.jsx
- SportTabs
- GameCard (for each game)
  - BestOddsSection
    - SpreadComparison (8 book logos with odds)
    - TotalComparison
    - MoneylineComparison
  - "Best Value" highlight with savings calculation
  - DeepLink buttons to each sportsbook
```

### Sportsbooks Endpoint
```
GET /live/sportsbooks
```
Returns list of 8 supported books with logos and deep-link URLs.

---

## Page 3: Injuries (`/injuries`)

### Backend Endpoint
```
GET /live/injuries/{sport}
```

### Response Format
```json
{
  "sport": "NBA",
  "source": "playbook",
  "count": 15,
  "data": [
    {
      "team": "Lakers",
      "player": "LeBron James",
      "position": "SF",
      "status": "Questionable",
      "injury": "Ankle",
      "notes": "Game-time decision",
      "usage_vacuum": 28.5,
      "beneficiaries": [
        {"player": "Rui Hachimura", "boost": "+4.2 pts"},
        {"player": "Austin Reaves", "boost": "+3.1 pts"}
      ]
    }
  ],
  "timestamp": "2026-01-16T12:00:00"
}
```

### Component Structure
```jsx
// pages/Injuries.jsx
- SportTabs
- InjuryTable
  - StatusBadge (Out/Doubtful/Questionable/Probable)
  - PlayerInfo (name, position, team)
  - InjuryDetails
  - UsageVacuumMeter (visual bar showing opportunity)
  - BeneficiaryList (players who benefit)
```

### Key Features
- Color-coded status badges
- Usage vacuum visualization
- "Who benefits?" section for each injury
- Link to player props for beneficiaries

---

## Page 4: Betting Splits (`/splits`)

### Backend Endpoint
```
GET /live/splits/{sport}
```

### Response Format
```json
{
  "sport": "NBA",
  "source": "playbook",
  "count": 8,
  "data": [
    {
      "game_id": "abc123",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "spread": {
        "home_tickets": 45,
        "away_tickets": 55,
        "home_money": 62,
        "away_money": 38
      },
      "total": {
        "over_tickets": 70,
        "under_tickets": 30,
        "over_money": 55,
        "under_money": 45
      },
      "moneyline": {
        "home_tickets": 40,
        "away_tickets": 60,
        "home_money": 58,
        "away_money": 42
      }
    }
  ]
}
```

### Component Structure
```jsx
// pages/Splits.jsx
- SportTabs
- SplitsTable
  - GameRow
    - Teams
    - TicketSplitBar (visual 50/50 bar)
    - MoneySplitBar
    - "Sharp vs Public" indicator
```

### Key Features
- Ticket % vs Money % comparison
- Highlight when money differs from tickets (sharp action)
- Visual split bars

---

## Page 5: Esoteric Edge (`/esoteric`)

### Backend Endpoints
```
GET /esoteric/today-energy           # Daily reading (public)
GET /live/esoteric-edge              # Full analysis (auth required)
GET /live/noosphere/status           # Noosphere velocity
GET /live/gann-physics-status        # GANN physics
GET /live/planetary-hour             # Current planetary hour
```

### Response Format (today-energy)
```json
{
  "date": "2026-01-16",
  "betting_outlook": "FAVORABLE",
  "overall_energy": 7.2,
  "moon_phase": "waxing_gibbous",
  "void_moon_periods": [],
  "schumann_reading": {
    "frequency_hz": 7.91,
    "status": "SLIGHTLY_ELEVATED"
  },
  "planetary_hours": {
    "current_ruler": "Jupiter",
    "favorable_for": "expansion, big bets"
  },
  "noosphere": {
    "sentiment_velocity": 2.3,
    "trending_direction": "BULLISH"
  },
  "recommendation": "Energy aligned. Trust your analysis today."
}
```

### Component Structure
```jsx
// pages/Esoteric.jsx
- DailyEnergyCard
  - OutlookBadge (FAVORABLE/NEUTRAL/UNFAVORABLE)
  - EnergyMeter (0-10 visual)
  - MoonPhaseWidget
  - VoidMoonWarning (if active)
- SchumannFrequency
- NoosphereVelocity
- PlanetaryHoursWheel
- GannPhysicsStatus
- DailyRecommendation
```

### Key Features
- Visual energy meter
- Moon phase display
- Void moon warnings
- "Math + Magic" explanation section

---

## Page 6: Performance (`/performance`)

### Backend Endpoints
```
GET /live/grader/performance/{sport}  # Performance by sport
GET /live/grader/daily-report         # Community report
GET /live/bets/history                # Bet history with stats
```

### Response Format (performance)
```json
{
  "sport": "NBA",
  "days_analyzed": 7,
  "graded_count": 45,
  "overall": {
    "hit_rate": 58.3,
    "mae": 2.4,
    "profitable": true,
    "status": "PROFITABLE"
  },
  "by_stat_type": {
    "points": {"hit_rate": 61.2, "total_picks": 20, "mae": 2.1},
    "rebounds": {"hit_rate": 55.0, "total_picks": 15, "mae": 2.8},
    "assists": {"hit_rate": 56.7, "total_picks": 10, "mae": 2.5}
  }
}
```

### Component Structure
```jsx
// pages/Performance.jsx
- OverallStatsCard
  - HitRateMeter (visual gauge)
  - ProfitabilityBadge
  - CLVScore
- SportTabs
- StatBreakdownTable
- PerformanceChart (line chart over time)
- DailyReportSection
```

---

## Page 7: Grade Picks (`/grading`)

### Backend Endpoints
```
POST /live/bets/track                 # Log a new bet
POST /live/bets/grade/{bet_id}        # Grade as WIN/LOSS/PUSH
GET /live/bets/history                # View past bets
GET /live/grader/daily-report         # Auto-graded SMASH picks
```

### Request Format (track)
```json
{
  "user_id": "user123",
  "sport": "NBA",
  "bet_type": "player_prop",
  "player": "LeBron James",
  "market": "points",
  "line": 25.5,
  "selection": "over",
  "odds": -110,
  "stake": 100,
  "sportsbook": "draftkings"
}
```

### Request Format (grade)
```json
{
  "result": "WIN",
  "actual_value": 28,
  "notes": "Easy cover"
}
```

### Component Structure
```jsx
// pages/Grading.jsx
- PendingBetsSection
  - BetCard (with GRADE buttons: WIN/LOSS/PUSH)
- GradedBetsSection
  - FilterTabs (All, Wins, Losses)
  - BetHistoryTable
- QuickStats
  - TodayRecord
  - WeekRecord
  - AllTimeRecord
```

---

## Page 8: Bankroll (`/bankroll`)

### Backend Endpoints
```
GET /live/bets/history?user_id=xxx    # Full bet history
POST /live/bets/track                 # Log new bet with stake
```

### Response Format (history)
```json
{
  "user_id": "user123",
  "bets": [...],
  "stats": {
    "total_bets": 150,
    "wins": 85,
    "losses": 60,
    "pushes": 5,
    "hit_rate": 58.6,
    "total_staked": 15000,
    "total_returned": 16200,
    "profit": 1200,
    "roi": 8.0
  }
}
```

### Component Structure
```jsx
// pages/Bankroll.jsx
- BankrollOverview
  - TotalBankroll
  - TodayPL
  - WeekPL
  - MonthPL
- KellyCriterionCalculator
  - EdgeInput
  - OddsInput
  - BankrollInput
  - RecommendedStake output
- BetSizingChart
- RecentBetsTable
- ProfitChart (cumulative over time)
```

### Key Features
- Kelly Criterion calculator
- Bankroll tracking over time
- Unit-based betting recommendations

---

## Additional Pages to Build

### Parlay Builder (`/parlay-builder`)
```
GET /live/parlay/{user_id}
POST /live/parlay/add
DELETE /live/parlay/remove/{user_id}/{leg_id}
POST /live/parlay/calculate
```

### Bet History (`/bet-history`)
```
GET /live/bets/history
GET /live/parlay/history
```

### CLV Tracker (`/clv`)
Calculate CLV from bet history (closing line value).

### Backtest (`/backtest`)
Historical analysis - may need new backend endpoint.

---

## API Authentication

All `/live/*` endpoints require:
```
Header: X-API-Key: YOUR_KEY
```

The `/esoteric/today-energy` endpoint is public (no auth required).

---

## Quick Start for Frontend Dev

1. Create route in `App.jsx`
2. Create page component in `pages/`
3. Add API call to `services/api.js`
4. Use SportTabs component for multi-sport pages
5. Test with curl first to verify backend response

Example API call:
```javascript
// services/api.js
export const getSharpMoney = async (sport) => {
  const response = await fetch(
    `${API_BASE}/live/sharp/${sport}`,
    { headers: { 'X-API-Key': API_KEY } }
  );
  return response.json();
};
```

---

## Priority Order

1. **HIGH** - Sharp Money, Best Odds, Injuries, Splits (core betting features)
2. **MEDIUM** - Esoteric, Performance, Grading (user engagement)
3. **LOW** - Bankroll, Parlay Builder, CLV Tracker (advanced features)

---

*Last Updated: January 16, 2026*
