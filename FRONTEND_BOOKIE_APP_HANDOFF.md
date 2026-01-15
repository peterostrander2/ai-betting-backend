# Bookie-Member-App Complete Handoff

**Date:** 2026-01-15
**Backend Version:** v14.8
**API Base:** https://web-production-7b2a.up.railway.app
**Repo:** bookie-member-app

**Related Handoffs:**
- [Esoteric Signals Handoff](./FRONTEND_ESOTERIC_HANDOFF.md) - Detailed esoteric UI guide
- [Click-to-Bet Handoff](./FRONTEND_HANDOFF_CLICK_TO_BET.md) - Betslip integration

---

## Quick Start

```javascript
// api.js - Base Configuration
const API_BASE = 'https://web-production-7b2a.up.railway.app';

// All endpoints return JSON with consistent schema:
// { sport, source, count, data, timestamp }
```

---

## Complete API Reference

### Core Betting Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/best-bets/{sport}` | GET | AI-scored picks with confluence |
| `/live/sharp/{sport}` | GET | Sharp money signals |
| `/live/splits/{sport}` | GET | Public vs sharp splits |
| `/live/props/{sport}` | GET | Player prop recommendations |
| `/live/line-shop/{sport}` | GET | Odds comparison across books |
| `/live/sportsbooks` | GET | List of 8 supported books |

### Click-to-Bet Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/betslip/generate` | GET | Generate betslip for specific bet |
| `/live/quick-betslip/{sport}/{game_id}` | GET | Quick betslip with user prefs |
| `/live/user/preferences/{user_id}` | GET | Get user preferences |
| `/live/user/preferences/{user_id}` | POST | Save user preferences |
| `/live/bets/track` | POST | Track a placed bet |
| `/live/bets/grade/{bet_id}` | POST | Grade bet WIN/LOSS/PUSH |
| `/live/bets/history` | GET | Bet history with stats |

### Parlay Builder Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/parlay/{user_id}` | GET | Get current parlay slip |
| `/live/parlay/add` | POST | Add leg to parlay |
| `/live/parlay/remove/{user_id}/{leg_id}` | DELETE | Remove leg |
| `/live/parlay/clear/{user_id}` | DELETE | Clear parlay slip |
| `/live/parlay/place` | POST | Track placed parlay |
| `/live/parlay/grade/{parlay_id}` | POST | Grade parlay |
| `/live/parlay/history` | GET | Parlay history with stats |
| `/live/parlay/calculate` | POST | Preview odds calculation |

### Esoteric & Analysis Endpoints

> **See [FRONTEND_ESOTERIC_HANDOFF.md](./FRONTEND_ESOTERIC_HANDOFF.md) for detailed esoteric UI components**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/esoteric-edge` | GET | Full esoteric analysis |
| `/esoteric/today-energy` | GET | Daily energy score |
| `/live/noosphere/status` | GET | Noosphere velocity |
| `/live/gann-physics-status` | GET | GANN physics signals |
| `/live/astro-status` | GET | Astrological analysis |
| `/live/planetary-hour` | GET | Current planetary hour |
| `/live/nakshatra` | GET | Lunar mansion |
| `/live/retrograde-status` | GET | Retrograde planets |
| `/live/esoteric-analysis` | GET | Complete pick analysis |

### Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/live/cache/stats` | GET | Cache statistics |
| `/live/lstm/status` | GET | LSTM model status |

---

## App Pages & Components

### 1. Dashboard/Home Page

**Data Sources:**
```javascript
// Fetch today's energy
const energy = await fetch(`${API_BASE}/esoteric/today-energy`);

// Fetch best bets for default sport
const bets = await fetch(`${API_BASE}/live/best-bets/nba`);

// Fetch user's bet history stats
const history = await fetch(`${API_BASE}/live/bets/history?user_id=${userId}`);
```

**Display Components:**
- Daily Energy Card (moon phase, numerology, betting outlook)
- Quick Stats (win rate, ROI, pending bets)
- Top SMASH Picks preview
- Active Parlay indicator

### 2. SmashSpots Page (/smash-spots)

**Main Component: SmashSpots.jsx**

```jsx
// Fetch SMASH picks (high-confidence bets)
const fetchSmashPicks = async (sport) => {
  const res = await fetch(`${API_BASE}/live/best-bets/${sport}`);
  const data = await res.json();

  // Filter for SMASH tier (score >= 9.0)
  return data.data.filter(bet => bet.final_score >= 9.0);
};

// Response structure:
{
  "sport": "NBA",
  "data": [
    {
      "game_id": "abc123",
      "game": "Lakers vs Celtics",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "final_score": 9.5,
      "confidence": "SMASH",
      "bet_tier": "GOLD_STAR",
      "recommended_units": 2.0,
      "recommendation": "Lakers -3.5",
      "ai_models_score": 7.2,
      "pillars_score": 6.8,
      "jarvis_boost": 2.0,
      "esoteric_boost": 0.5,
      "signals": {
        "sharp_money": true,
        "reverse_line": false,
        "injury_edge": true
      }
    }
  ]
}
```

**Bet Card Component:**
```jsx
function SmashBetCard({ bet, sport, userId }) {
  const [showBetslip, setShowBetslip] = useState(false);
  const [showParlay, setShowParlay] = useState(false);

  return (
    <div className={`bet-card tier-${bet.bet_tier.toLowerCase()}`}>
      {/* Score Badge */}
      <div className="score-badge">
        <span className="score">{bet.final_score.toFixed(1)}</span>
        <span className="tier">{bet.bet_tier}</span>
      </div>

      {/* Game Info */}
      <div className="game-info">
        <h3>{bet.game}</h3>
        <p className="recommendation">{bet.recommendation}</p>
        <p className="units">{bet.recommended_units}u recommended</p>
      </div>

      {/* Signal Indicators */}
      <div className="signals">
        {bet.signals.sharp_money && <span className="signal sharp">Sharp $</span>}
        {bet.signals.reverse_line && <span className="signal rlm">RLM</span>}
        {bet.signals.injury_edge && <span className="signal injury">Injury Edge</span>}
      </div>

      {/* Action Buttons */}
      <div className="actions">
        <button onClick={() => setShowBetslip(true)} className="btn-primary">
          Place Bet
        </button>
        <button onClick={() => addToParlay(bet)} className="btn-secondary">
          + Parlay
        </button>
      </div>

      {/* Modals */}
      {showBetslip && (
        <BetslipModal
          sport={sport}
          gameId={bet.game_id}
          game={bet.game}
          userId={userId}
          onClose={() => setShowBetslip(false)}
        />
      )}
    </div>
  );
}
```

### 3. Line Shopping Page (/line-shop)

**Purpose:** Compare odds across all 8 sportsbooks

```javascript
// Fetch line shopping data
const fetchLineShop = async (sport) => {
  const res = await fetch(`${API_BASE}/live/line-shop/${sport}`);
  return res.json();
};

// Response includes best odds highlighted:
{
  "sport": "NBA",
  "data": [
    {
      "game_id": "abc123",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "markets": {
        "spreads": {
          "best_odds": {
            "Lakers": { "price": -108, "book": "FanDuel" },
            "Celtics": { "price": -108, "book": "DraftKings" }
          },
          "all_books": [...]
        },
        "h2h": {...},
        "totals": {...}
      }
    }
  ]
}
```

**Line Shopping Component:**
```jsx
function LineShopTable({ game }) {
  return (
    <table className="line-shop-table">
      <thead>
        <tr>
          <th>Sportsbook</th>
          <th>{game.away_team}</th>
          <th>{game.home_team}</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        {game.markets.spreads.all_books.map(book => (
          <tr key={book.book_key}>
            <td>
              <img src={book.logo} alt={book.name} />
              {book.name}
            </td>
            <td className={book.is_best_away ? 'best-odds' : ''}>
              {formatOdds(book.away_odds)}
            </td>
            <td className={book.is_best_home ? 'best-odds' : ''}>
              {formatOdds(book.home_odds)}
            </td>
            <td>{book.total}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### 4. Parlay Builder Page (/parlay)

**Parlay Slip Component:**
```jsx
function ParlaySlip({ userId }) {
  const [slip, setSlip] = useState({ legs: [], combined_odds: null });
  const [stake, setStake] = useState(25);

  // Fetch current slip
  useEffect(() => {
    fetchSlip();
  }, [userId]);

  const fetchSlip = async () => {
    const res = await fetch(`${API_BASE}/live/parlay/${userId}`);
    setSlip(await res.json());
  };

  const addLeg = async (legData) => {
    await fetch(`${API_BASE}/live/parlay/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, ...legData })
    });
    fetchSlip();
  };

  const removeLeg = async (legId) => {
    await fetch(`${API_BASE}/live/parlay/remove/${userId}/${legId}`, {
      method: 'DELETE'
    });
    fetchSlip();
  };

  const clearSlip = async () => {
    await fetch(`${API_BASE}/live/parlay/clear/${userId}`, {
      method: 'DELETE'
    });
    fetchSlip();
  };

  const placeParlay = async (sportsbook) => {
    await fetch(`${API_BASE}/live/parlay/place`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        sportsbook: sportsbook,
        stake: stake,
        use_current_slip: true
      })
    });
    // Open sportsbook
    window.open(getSportsbookUrl(sportsbook), '_blank');
  };

  const potentialPayout = stake * (slip.combined_odds?.decimal || 1);

  return (
    <div className="parlay-slip">
      <h2>Parlay Slip ({slip.leg_count} legs)</h2>

      {/* Legs List */}
      <div className="legs">
        {slip.legs.map(leg => (
          <div key={leg.leg_id} className="leg">
            <span className="sport">{leg.sport}</span>
            <span className="game">{leg.game}</span>
            <span className="selection">{leg.selection}</span>
            <span className="odds">{formatOdds(leg.odds)}</span>
            <button onClick={() => removeLeg(leg.leg_id)}>✕</button>
          </div>
        ))}
      </div>

      {/* Odds & Payout */}
      {slip.combined_odds && (
        <div className="odds-display">
          <div className="combined-odds">
            <span>Combined Odds:</span>
            <strong>{formatOdds(slip.combined_odds.american)}</strong>
            <span className="decimal">({slip.combined_odds.decimal.toFixed(2)}x)</span>
          </div>
          <div className="implied-prob">
            Implied: {slip.combined_odds.implied_probability.toFixed(1)}%
          </div>
        </div>
      )}

      {/* Stake Input */}
      <div className="stake-input">
        <label>Stake:</label>
        <input
          type="number"
          value={stake}
          onChange={e => setStake(Number(e.target.value))}
        />
        <span className="payout">
          To Win: ${(potentialPayout - stake).toFixed(2)}
        </span>
      </div>

      {/* Action Buttons */}
      <div className="actions">
        <button onClick={clearSlip} className="btn-secondary">Clear</button>
        <button
          onClick={() => setShowSportsbooks(true)}
          className="btn-primary"
          disabled={slip.leg_count < 2}
        >
          Place Parlay
        </button>
      </div>
    </div>
  );
}
```

**Quick Parlay Calculator:**
```javascript
// Preview parlay odds without saving
const calculateParlay = async (legs, stake) => {
  const res = await fetch(`${API_BASE}/live/parlay/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ legs, stake })
  });
  return res.json();
};

// Response:
{
  "leg_count": 3,
  "combined_odds": {
    "decimal": 5.958,
    "american": 496,
    "implied_probability": 16.78
  },
  "stake": 25,
  "potential_payout": 148.95,
  "profit_if_win": 123.95,
  "example_payouts": {
    "$10": 59.58,
    "$25": 148.95,
    "$50": 297.90,
    "$100": 595.80
  }
}
```

### 5. Bet History Page (/history)

**Bet History Component:**
```jsx
function BetHistory({ userId }) {
  const [bets, setBets] = useState([]);
  const [parlays, setParlays] = useState([]);
  const [stats, setStats] = useState({});

  useEffect(() => {
    fetchHistory();
  }, [userId]);

  const fetchHistory = async () => {
    const [betsRes, parlaysRes] = await Promise.all([
      fetch(`${API_BASE}/live/bets/history?user_id=${userId}`),
      fetch(`${API_BASE}/live/parlay/history?user_id=${userId}`)
    ]);

    const betsData = await betsRes.json();
    const parlaysData = await parlaysRes.json();

    setBets(betsData.bets);
    setParlays(parlaysData.parlays);
    setStats({
      straight: betsData.stats,
      parlay: parlaysData.stats
    });
  };

  return (
    <div className="bet-history">
      {/* Stats Cards */}
      <div className="stats-grid">
        <StatCard title="Win Rate" value={`${stats.straight?.win_rate}%`} />
        <StatCard title="ROI" value={`${stats.straight?.roi}%`} />
        <StatCard title="Total Profit" value={`$${stats.straight?.total_profit}`} />
        <StatCard title="Parlay Wins" value={stats.parlay?.wins} />
      </div>

      {/* Tabs */}
      <Tabs>
        <Tab label="Straight Bets">
          <BetList bets={bets} onGrade={gradeBet} />
        </Tab>
        <Tab label="Parlays">
          <ParlayList parlays={parlays} onGrade={gradeParlay} />
        </Tab>
      </Tabs>
    </div>
  );
}
```

### 6. User Settings Page (/settings)

**User Preferences:**
```javascript
// Get preferences
const getPrefs = async (userId) => {
  const res = await fetch(`${API_BASE}/live/user/preferences/${userId}`);
  return res.json();
};

// Save preferences
const savePrefs = async (userId, prefs) => {
  await fetch(`${API_BASE}/live/user/preferences/${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs)
  });
};

// Preference schema:
{
  "favorite_books": ["draftkings", "fanduel", "betmgm"],
  "default_bet_amount": 25,
  "notifications": {
    "smash_picks": true,
    "line_movements": true
  }
}
```

---

## Shared Components

### BetslipModal.jsx

```jsx
function BetslipModal({ sport, gameId, game, userId, onClose }) {
  const [books, setBooks] = useState([]);
  const [userPrefs, setUserPrefs] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    // Use quick-betslip which applies user preferences
    const url = userId
      ? `${API_BASE}/live/quick-betslip/${sport}/${gameId}?user_id=${userId}`
      : `${API_BASE}/live/betslip/generate?sport=${sport}&game_id=${gameId}`;

    const res = await fetch(url);
    const data = await res.json();
    setBooks(data.sportsbooks);
  };

  const trackBet = async (book) => {
    await fetch(`${API_BASE}/live/bets/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        sport: sport,
        game_id: gameId,
        game: game,
        sportsbook: book.book_key,
        // Add other bet details
      })
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal betslip-modal" onClick={e => e.stopPropagation()}>
        <h2>Place Bet</h2>
        <p className="game-name">{game}</p>

        <div className="sportsbook-grid">
          {books.map(book => (
            <a
              key={book.book_key}
              href={book.deep_link.web}
              target="_blank"
              rel="noopener noreferrer"
              className={`sportsbook-card ${book.is_favorite ? 'favorite' : ''}`}
              style={{ borderColor: book.book_color }}
              onClick={() => trackBet(book)}
            >
              {book.is_favorite && <span className="fav-badge">★</span>}
              <span className="book-name">{book.book_name}</span>
              <span className="open-text">Open →</span>
            </a>
          ))}
        </div>

        <button className="btn-close" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
```

### PlaceBetButton.jsx

```jsx
function PlaceBetButton({ bet, sport, userId }) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="place-bet-btn"
      >
        Place Bet
      </button>

      {showModal && (
        <BetslipModal
          sport={sport}
          gameId={bet.game_id}
          game={bet.game}
          userId={userId}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
```

### AddToParlayButton.jsx

```jsx
function AddToParlayButton({ bet, sport, userId, onAdd }) {
  const [loading, setLoading] = useState(false);
  const [added, setAdded] = useState(false);

  const handleAdd = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/live/parlay/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          sport: sport,
          game_id: bet.game_id,
          game: bet.game,
          bet_type: bet.bet_type || 'spread',
          selection: bet.selection || bet.recommendation,
          odds: bet.odds || -110,
          ai_score: bet.final_score
        })
      });
      setAdded(true);
      onAdd?.();
    } catch (err) {
      console.error('Failed to add to parlay:', err);
    }
    setLoading(false);
  };

  return (
    <button
      onClick={handleAdd}
      disabled={loading || added}
      className={`add-parlay-btn ${added ? 'added' : ''}`}
    >
      {loading ? '...' : added ? '✓ Added' : '+ Parlay'}
    </button>
  );
}
```

---

## API Helper Functions (api.js)

```javascript
const API_BASE = 'https://web-production-7b2a.up.railway.app';

export const api = {
  // Best Bets
  getBestBets: (sport) =>
    fetch(`${API_BASE}/live/best-bets/${sport}`).then(r => r.json()),

  // Line Shopping
  getLineShop: (sport) =>
    fetch(`${API_BASE}/live/line-shop/${sport}`).then(r => r.json()),

  // Sportsbooks
  getSportsbooks: () =>
    fetch(`${API_BASE}/live/sportsbooks`).then(r => r.json()),

  // Betslip
  generateBetslip: (params) =>
    fetch(`${API_BASE}/live/betslip/generate?${new URLSearchParams(params)}`).then(r => r.json()),

  getQuickBetslip: (sport, gameId, userId) =>
    fetch(`${API_BASE}/live/quick-betslip/${sport}/${gameId}?user_id=${userId}`).then(r => r.json()),

  // User Preferences
  getUserPrefs: (userId) =>
    fetch(`${API_BASE}/live/user/preferences/${userId}`).then(r => r.json()),

  saveUserPrefs: (userId, prefs) =>
    fetch(`${API_BASE}/live/user/preferences/${userId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(prefs)
    }).then(r => r.json()),

  // Bet Tracking
  trackBet: (betData) =>
    fetch(`${API_BASE}/live/bets/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(betData)
    }).then(r => r.json()),

  gradeBet: (betId, result) =>
    fetch(`${API_BASE}/live/bets/grade/${betId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result })
    }).then(r => r.json()),

  getBetHistory: (userId, filters = {}) =>
    fetch(`${API_BASE}/live/bets/history?${new URLSearchParams({ user_id: userId, ...filters })}`).then(r => r.json()),

  // Parlay Builder
  getParlaySlip: (userId) =>
    fetch(`${API_BASE}/live/parlay/${userId}`).then(r => r.json()),

  addParlayLeg: (legData) =>
    fetch(`${API_BASE}/live/parlay/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(legData)
    }).then(r => r.json()),

  removeParlayLeg: (userId, legId) =>
    fetch(`${API_BASE}/live/parlay/remove/${userId}/${legId}`, { method: 'DELETE' }).then(r => r.json()),

  clearParlay: (userId) =>
    fetch(`${API_BASE}/live/parlay/clear/${userId}`, { method: 'DELETE' }).then(r => r.json()),

  placeParlay: (parlayData) =>
    fetch(`${API_BASE}/live/parlay/place`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parlayData)
    }).then(r => r.json()),

  gradeParlay: (parlayId, result) =>
    fetch(`${API_BASE}/live/parlay/grade/${parlayId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result })
    }).then(r => r.json()),

  getParlayHistory: (userId, filters = {}) =>
    fetch(`${API_BASE}/live/parlay/history?${new URLSearchParams({ user_id: userId, ...filters })}`).then(r => r.json()),

  calculateParlay: (legs, stake) =>
    fetch(`${API_BASE}/live/parlay/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ legs, stake })
    }).then(r => r.json()),

  // Esoteric
  getTodayEnergy: () =>
    fetch(`${API_BASE}/esoteric/today-energy`).then(r => r.json()),

  getEsotericEdge: () =>
    fetch(`${API_BASE}/live/esoteric-edge`).then(r => r.json()),
};
```

---

## Sportsbooks Reference

| Book | Key | Color | Web URL |
|------|-----|-------|---------|
| DraftKings | `draftkings` | #53d337 | sportsbook.draftkings.com |
| FanDuel | `fanduel` | #1493ff | sportsbook.fanduel.com |
| BetMGM | `betmgm` | #c4a44a | sports.betmgm.com |
| Caesars | `caesars` | #0a2240 | sportsbook.caesars.com |
| PointsBet | `pointsbetus` | #ed1c24 | pointsbet.com |
| William Hill | `williamhill_us` | #00314d | williamhill.com |
| Barstool | `barstool` | #c41230 | barstoolsportsbook.com |
| BetRivers | `betrivers` | #1b365d | betrivers.com |

---

## Bet Tiers & Styling

```css
/* Bet tier colors */
.tier-gold_star {
  border-color: #fbbf24;
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
}

.tier-edge_lean {
  border-color: #22c55e;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.tier-ml_dog_lotto {
  border-color: #8b5cf6;
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
}

.tier-monitor {
  border-color: #6b7280;
  background: #374151;
}

/* Score badge */
.score-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.score-badge .score {
  font-size: 2rem;
  font-weight: bold;
}

.score-badge .tier {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
```

---

## Testing Endpoints

```bash
# Health
curl https://web-production-7b2a.up.railway.app/health

# Best Bets
curl https://web-production-7b2a.up.railway.app/live/best-bets/nba

# Line Shop
curl https://web-production-7b2a.up.railway.app/live/line-shop/nba

# Sportsbooks
curl https://web-production-7b2a.up.railway.app/live/sportsbooks

# Today's Energy
curl https://web-production-7b2a.up.railway.app/esoteric/today-energy

# User Preferences
curl https://web-production-7b2a.up.railway.app/live/user/preferences/test_user

# Parlay Slip
curl https://web-production-7b2a.up.railway.app/live/parlay/test_user

# Parlay Calculate
curl -X POST https://web-production-7b2a.up.railway.app/live/parlay/calculate \
  -H "Content-Type: application/json" \
  -d '{"legs": [{"odds": -110}, {"odds": +150}], "stake": 25}'
```

---

## Supported Sports

- `nba` - NBA Basketball
- `nfl` - NFL Football
- `mlb` - MLB Baseball
- `nhl` - NHL Hockey
- `ncaab` - College Basketball (LSTM models only)

---

*Handoff Version: 2.1*
*Backend: v14.8*
*Date: 2026-01-15*
