# Frontend Handoff: Click-to-Bet Feature

**Date:** 2026-01-12
**Backend Version:** v14.3
**For:** bookie-member-app

---

## Feature Overview

Enable users to click on a SMASH bet and immediately see sportsbook options with odds, then click to open that sportsbook with the bet ready to place.

### User Flow
```
1. User sees SMASH BET card (AI Score: 9.2)
2. Clicks "Place Bet" button
3. Modal appears with all sportsbooks + their odds
4. Best odds highlighted at top
5. User clicks preferred sportsbook
6. Opens sportsbook website/app to place bet
```

---

## New Backend Endpoints

### 1. Line Shopping
```
GET /live/line-shop/{sport}
GET /live/line-shop/{sport}?game_id=xyz
```

Returns odds from all sportsbooks with best odds highlighted.

**Response:**
```json
{
  "sport": "NBA",
  "count": 5,
  "sportsbooks": ["draftkings", "fanduel", "betmgm", ...],
  "data": [
    {
      "game_id": "abc123",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "commence_time": "2026-01-12T19:00:00Z",
      "markets": {
        "spreads": {
          "best_odds": {
            "Lakers": {"price": -108, "book": "FanDuel", "book_key": "fanduel"},
            "Celtics": {"price": -110, "book": "DraftKings", "book_key": "draftkings"}
          },
          "all_books": [
            {
              "book_key": "draftkings",
              "book_name": "DraftKings",
              "outcomes": [...],
              "deep_link": {
                "book_key": "draftkings",
                "name": "DraftKings",
                "web_url": "https://sportsbook.draftkings.com/basketball/nba",
                "color": "#53d337",
                "logo": "https://..."
              }
            }
          ]
        },
        "h2h": {...},
        "totals": {...}
      }
    }
  ]
}
```

### 2. Betslip Generator
```
GET /live/betslip/generate?sport=nba&game_id=xyz&bet_type=spread&selection=Lakers
```

Returns all sportsbook options for a specific bet, sorted by best odds.

**Parameters:**
- `sport` - nba, nfl, mlb, nhl
- `game_id` - from best-bets or line-shop response
- `bet_type` - spread, h2h, total
- `selection` - team name or "Over"/"Under"
- `book` (optional) - filter to specific book

**Response:**
```json
{
  "sport": "NBA",
  "game_id": "abc123",
  "game": "Celtics @ Lakers",
  "bet_type": "spread",
  "selection": "Lakers",
  "best_odds": {
    "book_key": "fanduel",
    "book_name": "FanDuel",
    "book_color": "#1493ff",
    "book_logo": "https://...",
    "selection": "Lakers",
    "odds": -108,
    "point": -3.5,
    "deep_link": {
      "web": "https://sportsbook.fanduel.com/",
      "note": "Opens sportsbook - navigate to game to place bet"
    }
  },
  "all_books": [
    // Same structure, sorted by best odds
  ],
  "count": 6
}
```

### 3. Sportsbooks List
```
GET /live/sportsbooks
```

Returns all supported sportsbooks with branding.

**Response:**
```json
{
  "count": 8,
  "sportsbooks": [
    {
      "key": "draftkings",
      "name": "DraftKings",
      "color": "#53d337",
      "logo": "https://...",
      "web_url": "https://sportsbook.draftkings.com"
    },
    {
      "key": "fanduel",
      "name": "FanDuel",
      "color": "#1493ff",
      "logo": "https://...",
      "web_url": "https://sportsbook.fanduel.com"
    }
    // ... betmgm, caesars, pointsbetus, williamhill_us, barstool, betrivers
  ]
}
```

---

## Frontend Implementation Guide

### 1. BetCard Component Enhancement

Add "Place Bet" button to existing bet cards:

```tsx
// BetCard.tsx
interface BetCardProps {
  bet: {
    game_id: string;
    game: string;
    home_team: string;
    away_team: string;
    ai_score: number;
    confidence: string;
    recommendation: string;
  };
  sport: string;
}

function BetCard({ bet, sport }: BetCardProps) {
  const [showBetslip, setShowBetslip] = useState(false);

  return (
    <div className="bet-card">
      {/* Existing bet info */}
      <div className="bet-info">
        <h3>{bet.game}</h3>
        <span className="ai-score">{bet.ai_score}</span>
        <span className="confidence">{bet.confidence}</span>
      </div>

      {/* New: Place Bet button */}
      <button
        onClick={() => setShowBetslip(true)}
        className="place-bet-btn"
      >
        Place Bet
      </button>

      {/* Betslip Modal */}
      {showBetslip && (
        <BetslipModal
          sport={sport}
          gameId={bet.game_id}
          game={bet.game}
          onClose={() => setShowBetslip(false)}
        />
      )}
    </div>
  );
}
```

### 2. Betslip Modal Component

```tsx
// BetslipModal.tsx
interface BetslipModalProps {
  sport: string;
  gameId: string;
  game: string;
  onClose: () => void;
}

function BetslipModal({ sport, gameId, game, onClose }: BetslipModalProps) {
  const [betType, setBetType] = useState<'spread' | 'h2h' | 'total'>('spread');
  const [selection, setSelection] = useState('');
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchBetslip = async () => {
    if (!selection) return;
    setLoading(true);

    const res = await fetch(
      `${API_URL}/live/betslip/generate?sport=${sport}&game_id=${gameId}&bet_type=${betType}&selection=${selection}`
    );
    const data = await res.json();
    setBooks(data.all_books);
    setLoading(false);
  };

  useEffect(() => {
    fetchBetslip();
  }, [betType, selection]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Place This Bet</h2>
        <p className="game-name">{game}</p>

        {/* Bet Type Selector */}
        <div className="bet-type-tabs">
          <button onClick={() => setBetType('spread')}>Spread</button>
          <button onClick={() => setBetType('h2h')}>Moneyline</button>
          <button onClick={() => setBetType('total')}>Total</button>
        </div>

        {/* Selection (would need game data for team names) */}
        <div className="selection">
          <input
            placeholder="Enter team name or Over/Under"
            value={selection}
            onChange={e => setSelection(e.target.value)}
          />
        </div>

        {/* Sportsbook Options */}
        {loading ? (
          <div className="loading">Loading odds...</div>
        ) : (
          <div className="sportsbook-grid">
            {books.map(book => (
              <a
                key={book.book_key}
                href={book.deep_link.web}
                target="_blank"
                rel="noopener noreferrer"
                className="sportsbook-card"
                style={{ borderColor: book.book_color }}
              >
                <img src={book.book_logo} alt={book.book_name} />
                <span className="book-name">{book.book_name}</span>
                <span className="odds">{book.odds > 0 ? '+' : ''}{book.odds}</span>
                {book.point && <span className="line">{book.point}</span>}
              </a>
            ))}
          </div>
        )}

        <button className="close-btn" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
```

### 3. Styling (Tailwind example)

```css
/* Sportsbook grid */
.sportsbook-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.sportsbook-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  border: 2px solid;
  border-radius: 8px;
  text-decoration: none;
  transition: transform 0.2s;
}

.sportsbook-card:hover {
  transform: scale(1.05);
}

.sportsbook-card img {
  height: 32px;
  margin-bottom: 8px;
}

.odds {
  font-size: 24px;
  font-weight: bold;
}

/* Best odds badge */
.sportsbook-card.best::after {
  content: 'BEST ODDS';
  position: absolute;
  top: -8px;
  background: #22c55e;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}
```

---

## Integration with Best Bets

The `/live/best-bets/{sport}` response already includes `game_id`. Use this to fetch betslip:

```tsx
// When user clicks bet from best-bets list
const handlePlaceBet = (bet) => {
  // bet.game_id is available
  // bet.home_team and bet.away_team for selection options
  openBetslipModal({
    sport: currentSport,
    gameId: bet.game_id,
    homeTeam: bet.home_team,
    awayTeam: bet.away_team
  });
};
```

---

## Supported Sportsbooks

| Book | Key | Color | Status |
|------|-----|-------|--------|
| DraftKings | draftkings | #53d337 | Active |
| FanDuel | fanduel | #1493ff | Active |
| BetMGM | betmgm | #c4a44a | Active |
| Caesars | caesars | #0a2240 | Active |
| PointsBet | pointsbetus | #ed1c24 | Active |
| William Hill | williamhill_us | #00314d | Active |
| Barstool | barstool | #c41230 | Active |
| BetRivers | betrivers | #1b365d | Active |

---

## v2.0 Enhancements (NOW IMPLEMENTED)

### 1. User Preferences (DONE)
```bash
# Get user preferences
curl https://web-production-7b2a.up.railway.app/live/user/preferences/user123

# Save user preferences
curl -X POST https://web-production-7b2a.up.railway.app/live/user/preferences/user123 \
  -H "Content-Type: application/json" \
  -d '{"favorite_books": ["fanduel", "draftkings"], "default_bet_amount": 50}'
```

### 2. Bet Tracking (DONE)
```bash
# Track a bet
curl -X POST https://web-production-7b2a.up.railway.app/live/bets/track \
  -H "Content-Type: application/json" \
  -d '{"sport": "NBA", "game_id": "xyz", "bet_type": "spread", "selection": "Lakers", "odds": -110, "sportsbook": "draftkings", "stake": 25}'

# Grade a bet
curl -X POST https://web-production-7b2a.up.railway.app/live/bets/grade/BET_NBA_xyz_123 \
  -H "Content-Type: application/json" \
  -d '{"result": "WIN"}'

# Get bet history
curl https://web-production-7b2a.up.railway.app/live/bets/history
```

### 3. Quick Betslip with User Prefs (DONE)
```bash
# Quick betslip (prioritizes user's favorite books)
curl "https://web-production-7b2a.up.railway.app/live/quick-betslip/nba/game123?user_id=user123"
```

### 4. Enhanced Deep Links (DONE)
- Sport-specific URLs for all 8 sportsbooks
- Example: DraftKings NBA → `sportsbook.draftkings.com/basketball/nba`

---

## Future Enhancements (TODO)

1. **True Deep Links** - Partner with OpticOdds for direct bet placement URLs
2. **Parlay Builder** - Combine multiple bets into parlays

---

## Testing

Backend endpoints to test:
```bash
# List sportsbooks
curl https://web-production-7b2a.up.railway.app/live/sportsbooks

# Line shopping
curl https://web-production-7b2a.up.railway.app/live/line-shop/nba

# Generate betslip
curl "https://web-production-7b2a.up.railway.app/live/betslip/generate?sport=nba&game_id=TEST&bet_type=spread&selection=Lakers"

# User preferences
curl https://web-production-7b2a.up.railway.app/live/user/preferences/user123

# Bet tracking
curl https://web-production-7b2a.up.railway.app/live/bets/history

# Quick betslip
curl "https://web-production-7b2a.up.railway.app/live/quick-betslip/nba/game123"
```

---

*Backend: v14.5 DEPLOYED*
*Frontend: api.js updated, BetslipModal ready*
