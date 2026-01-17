# Bookie-o-em Backend Complete Handoff Document
**Version:** v14.1 - PRODUCTION_HARDENED
**Repository:** peterostrander2/ai-betting-backend
**Generated:** January 2026

---

## 🎯 Project Overview

**Bookie-o-em** is a production-grade AI-powered sports betting intelligence platform that combines:
- Live odds from 15+ sportsbooks via The Odds API
- Sharp money detection and betting splits from Playbook API
- Advanced machine learning predictions using LSTM neural networks
- 18 esoteric edge detection modules for unconventional betting signals
- Automated grading and weight adjustment systems
- Context-aware feature engineering

**Tech Stack:**
- **Framework:** FastAPI (async)
- **HTTP Client:** httpx (connection pooling)
- **ML/AI:** TensorFlow/Keras (LSTM), scikit-learn
- **Astronomy/Astrology:** ephem, swisseph
- **Database:** PostgreSQL (via psycopg2)
- **Deployment:** Railway, Docker-ready
- **Python:** 3.12.3

---

## 📂 Core Architecture

### Entry Point
```python
main.py (v14.1)
```
- FastAPI application initialization
- Shared httpx.AsyncClient with connection pooling
- Startup/shutdown lifecycle management
- Root health check endpoints
- Includes all active routers

### Active Production Files

| File | Purpose | Key Features |
|------|---------|-------------|
| **main.py** | API entry point | App lifecycle, health checks, router mounting |
| **live_data_router.py** | Live betting endpoints | Sharp money, splits, props, best bets, esoteric edge |
| **context_layer.py** | ML feature engineering | 90+ contextual features for predictions |
| **jarvis_savant_engine.py** | Advanced AI engine | Multi-layer AI predictions with esoteric analysis |
| **lstm_brain.py** | Neural network predictions | LSTM model for time-series betting predictions |
| **lstm_training_pipeline.py** | ML training | Automated LSTM model training pipeline |
| **auto_grader.py** | Prediction grading | Automatic scoring and weight adjustment |
| **esoteric_grader.py** | Esoteric module grading | Grades the 18 esoteric modules |
| **esoteric_engine.py** | Esoteric calculations | Core esoteric edge detection logic |
| **daily_scheduler.py** | Scheduled jobs | Daily audits, grading, cleanup |
| **database.py** | Database layer | PostgreSQL connection and models |
| **advanced_ml_backend.py** | Legacy ML models | 8 traditional ML models (ensemble) |
| **astronomical_api.py** | Celestial data | Moon phases, planetary positions, eclipses |
| **player_birth_data.py** | Player astrology | Birth charts and astrological analysis |
| **playbook_api.py** | Playbook integration | Sharp money and betting splits API |
| **metrics.py** | Performance tracking | System metrics and monitoring |
| **test_api.py** | API testing | Test suite for endpoints |

---

## 🚀 Live API Endpoints

### Base URL (Production)
```
https://your-app.railway.app
```

### Health Checks
- `GET /` - API info + all endpoints list
- `GET /health` - Root health check
- `GET /live/health` - Live router health check

### Live Betting Data
- `GET /live/sharp/{sport}` - Sharp money signals (where pros are betting)
- `GET /live/splits/{sport}` - Public betting splits (% on each side)
- `GET /live/props/{sport}` - Player prop markets
- `GET /live/best-bets/{sport}` - AI-scored best betting opportunities

**Supported Sports:** `nba`, `nfl`, `mlb`, `nhl`

### Esoteric Edge Detection
- `GET /live/esoteric-edge` - Full 18-module esoteric analysis
- `GET /esoteric/today-energy` - Today's energy reading (moon, planets, etc.)
- `GET /live/noosphere/status` - Global consciousness indicators (v14.0)
- `GET /live/gann-physics-status` - GANN physics module status

### Response Format
All endpoints return standardized JSON:
```json
{
  "sport": "NBA",
  "source": "playbook" | "odds_api" | "estimated",
  "count": 5,
  "data": [...]
}
```

---

## 🤖 JARVIS SAVANT ENGINE v7.4 - THE CORE INTELLIGENCE

### Overview

**JARVIS (Just A Rather Very Intelligent System) Savant Engine** is the heart of Bookie-o-em's prediction system. It combines traditional sports analytics (Research Score) with unconventional esoteric signals (Esoteric Score) using a proprietary confluence algorithm.

**File:** `jarvis_savant_engine.py` (1,841 lines)

### The Complete Formula

```
┌─────────────────────────────────────────────────────────────┐
│                    BOOKIE-O-EM CONFLUENCE                    │
├─────────────────────────────────────────────────────────────┤
│  RESEARCH SCORE (0-10)              ESOTERIC SCORE (0-10)   │
│  ├─ 8 AI Models (0-8)               ├─ JARVIS RS (0-4)      │
│  └─ 8 Pillars (0-8)                 ├─ Gematria (52%)       │
│      scaled to 0-10                 ├─ Public Fade (-13%)   │
│                                     ├─ Mid-Spread (+20%)    │
│                                     └─ Esoteric Edge (0-2)  │
│                                                              │
│  Alignment = 1 - |research - esoteric| / 10                 │
│                                                              │
│  CONFLUENCE LEVELS:                                          │
│  IMMORTAL (+10): 2178 + both ≥7.5 + alignment ≥80%          │
│  JARVIS_PERFECT (+7): Trigger + both ≥7.5 + alignment ≥80%  │
│  PERFECT (+5): both ≥7.5 + alignment ≥80%                   │
│  STRONG (+3): Both high OR aligned ≥70%                     │
│  MODERATE (+1): Aligned ≥60%                                │
│  DIVERGENT (+0): Models disagree                            │
│                                                              │
│  FINAL = (research × 0.67) + (esoteric × 0.33) + boost      │
│                                                              │
│  BET TIERS:                                                  │
│  GOLD_STAR (2u): FINAL ≥ 9.0                                │
│  EDGE_LEAN (1u): FINAL ≥ 7.5                                │
│  ML_DOG_LOTTO (0.5u): NHL Dog Protocol                      │
│  MONITOR: FINAL ≥ 6.0                                        │
│  PASS: FINAL < 6.0                                           │
└─────────────────────────────────────────────────────────────┘
```

### 🔢 THE IMMORTAL: 2178

**Mathematical Proof:**
**2178** is the only number where:
1. **n⁴ contains itself**: 2178⁴ = 22,497,682,**2178**,656
2. **reverse(n)⁴ contains itself**: 8712⁴ = 57,596,201,**8712**,256
3. **Both equal 66⁴ in concatenation**: Mathematical proof of non-collapse

**When 2178 appears in game data (score, spread, player numbers), it triggers IMMORTAL CONFLUENCE (+10 boost)**

### ⚡ JARVIS Triggers (8 Sacred Numbers)

| Number | Name | Boost | Tier | Description |
|--------|------|-------|------|-------------|
| **2178** | THE IMMORTAL | +20 | LEGENDARY | Mathematical non-collapse proof |
| **201** | THE ORDER | +12 | HIGH | "Order out of chaos" |
| **33** | THE MASTER | +10 | HIGH | Master number (Freemasonry) |
| **93** | THE WILL | +10 | HIGH | Thelema ("Do what thou wilt") |
| **322** | THE SOCIETY | +10 | HIGH | Skull & Bones |
| **666** | THE BEAST | +8 | MEDIUM | Number of the Beast |
| **888** | JESUS | +8 | MEDIUM | Greek gematria for Jesus |
| **369** | TESLA KEY | +7 | MEDIUM | Tesla 3-6-9 pattern |

### 🔮 Gematria System

**Three Calculation Types:**

1. **Simple Gematria:** A=1, B=2, C=3... Z=26
2. **Reverse Gematria:** A=26, B=25, C=24... Z=1
3. **Jewish Gematria:** `simple × 6 + length(text)`

**Gematria Signal (52% Weight When Triggered)**

When Gematria Triggers Fire:
- Base weight: 30%
- **Boosted weight: 52%** (in esoteric score calculation)

### 📊 Phase 1: Confluence Core

**1. Public Fade Signal**
- **80%+ on one side:** -0.95 (strong fade)
- **75-79%:** -0.85
- **70-74%:** -0.75
- **65-69%:** -0.65

**2. Mid-Spread Signal (Goldilocks Zone)**
- **4-9 points:** +20% boost (optimal predictability)
- **<4:** Coinflip territory
- **>14:** Blowout variance

**3. Large Spread Trap**
- **Spreads ≥14 points:** -20% penalty (garbage time risk)

### 🎯 Confluence Calculation (THE HEART)

**Alignment Formula:**
```python
alignment = 1 - (|research_score - esoteric_score| / 10)
```

**Confluence Levels:**

| Level | Condition | Boost | Action |
|-------|-----------|-------|--------|
| **IMMORTAL** | 2178 + both ≥7.5 + align ≥80% | +10 | MAXIMUM SMASH |
| **JARVIS_PERFECT** | Trigger + both ≥7.5 + align ≥80% | +7 | STRONG SMASH |
| **PERFECT** | Both ≥7.5 + align ≥80% | +5 | PLAY |
| **STRONG** | Both high OR align ≥70% | +3 | LEAN |
| **MODERATE** | Align ≥60% | +1 | MONITOR |
| **DIVERGENT** | Align <60% | +0 | PASS |

### 🧮 Blended Probability (67/33 Formula)

```python
FINAL = (research_score × 0.67) + (esoteric_score × 0.33) + confluence_boost
```

**Why 67/33?**
- **67% = Research** (proven statistical models)
- **33% = Esoteric** (edge detection, contrarian signals)

### 🏆 Bet Tier System

| Tier | Condition | Units | Description |
|------|-----------|-------|-------------|
| **GOLD_STAR** | FINAL ≥ 9.0 | 2u | Maximum confidence |
| **EDGE_LEAN** | FINAL ≥ 7.5 | 1u | Strong edge |
| **ML_DOG_LOTTO** | NHL Dog Protocol | 0.5u | Special NHL underdog bet |
| **MONITOR** | FINAL ≥ 6.0 | 0u | Watch for line movement |
| **PASS** | FINAL < 6.0 | 0u | No bet |

### NHL Dog Protocol

**Conditions:**
1. Team is puck line dog (+1.5)
2. Research score ≥ 9.3
3. Public on favorite ≥ 65%

**Action:** 0.5u ML bet (lottery ticket)

---

## 🔮 18 Esoteric Edge Modules

### NOOSPHERE VELOCITY (v14.0) - 3 modules
1. **Insider Leak Detection** - Social media sentiment spikes
2. **Main Character Syndrome** - Player narrative momentum
3. **Phantom Injury Scanner** - Unreported injury detection

### GANN PHYSICS (v13.0) - 3 modules
4. **50% Retracement** - W.D. Gann gravity check
5. **Rule of Three** - Exhaustion node detection
6. **Annulifier Cycle** - Harmonic lock points

### OMNI-GLITCH (v11.0) - 6 modules
7. **Vortex Math** - Tesla 3-6-9 pattern detection
8. **Shannon Entropy** - Information theory edge
9. **Atmospheric Drag** - Altitude and air pressure impact
10. **Void of Course Moon** - Astrological instability
11. **Gann Spiral** - Geometric price/time relationships
12. **Mars-Uranus Nuclear** - Explosive planetary aspects

### SCALAR-SAVANT (v10.4) - 6 modules
13. **Bio-Sine Wave** - Circadian rhythm optimization
14. **Chrome Resonance** - Team color psychology
15. **Lunacy Factor** - Full moon behavioral impact
16. **Schumann Spike** - Earth resonance frequency
17. **Saturn Block** - Limitation and restriction transit
18. **Zebra Privilege** - Referee bias patterns

---

## 🧠 Machine Learning Architecture

### 1. LSTM Neural Network (`lstm_brain.py`)

**Architecture:**
- **Input:** 90+ contextual features per game
- **Layers:**
  - LSTM Layer 1: 128 units, dropout 0.3
  - LSTM Layer 2: 64 units, dropout 0.3
  - Dense: 32 units, ReLU activation
  - Output: 1 unit, sigmoid activation
- **Loss:** Binary crossentropy
- **Optimizer:** Adam

**Training Pipeline (`lstm_training_pipeline.py`):**
1. Fetch historical game data
2. Generate contextual features via `context_layer.py`
3. Train LSTM model with validation split
4. Save model to `models/lstm_brain.h5`
5. Log performance metrics

### 2. Context Layer (`context_layer.py`)

**90+ Feature Categories:**
- **Team Performance:** Win %, offensive/defensive ratings, pace
- **Rest & Schedule:** Days rest, back-to-backs, travel distance
- **Matchup Dynamics:** Historical H2H, style matchups
- **Momentum:** Recent form, streaks, clutch performance
- **Injury Context:** Key player injuries, impact ratings
- **Market Signals:** Line movement, sharp money indicators
- **Environmental:** Home/away, altitude, weather
- **Advanced Stats:** Four factors, net rating, SRS

### 3. Legacy Ensemble Models (`advanced_ml_backend.py`)

8 traditional ML models:
1. Logistic Regression
2. Random Forest
3. Gradient Boosting
4. XGBoost
5. LightGBM
6. Support Vector Machine
7. Neural Network (Dense)
8. Naive Bayes

**Ensemble Method:** Weighted average based on historical accuracy

---

## 🎯 Click-to-Bet Implementation

### User Flow
```
1. User sees SMASH BET card in app
   ↓
2. User clicks "Place Bet" button
   ↓
3. Modal displays all 8 sportsbooks with current odds
   ↓
4. Best odds highlighted (green border/badge)
   ↓
5. User clicks their preferred sportsbook
   ↓
6. Deep link opens sportsbook app/website
   ↓
7. Bet pre-populated on betslip (DraftKings, FanDuel, BetMGM)
   ↓
8. User enters stake amount
   ↓
9. User confirms bet in sportsbook
   ↓
10. Bet placed ✓
```

### 2-Click Handoff (Industry Standard)

**Click 1:** In Bookie-o-em app → Opens sportsbook
**Click 2:** In sportsbook → Confirm bet

### Deep Link Technology

**Supported Sportsbooks (Bet Pre-Population):**
- ✅ DraftKings
- ✅ FanDuel
- ✅ BetMGM
- ✅ Caesars
- ⚠️ BetRivers (partial)
- ⚠️ PointsBet (partial)

### What We CAN'T Do

**True 1-Click Betting (Not Possible):**
- No public APIs for bet placement
- Would require OAuth partnerships with each sportsbook
- Regulatory restrictions prohibit automated bet placement

### Backend API

**Endpoint:**
```
GET /live/best-bets/{sport}?includeLinks=true&includeSids=true
```

**Response:**
```json
{
  "sport": "NBA",
  "data": [{
    "game": "Lakers @ Celtics",
    "pick": "Lakers -6.5",
    "tier": "GOLD_STAR",
    "confidence": 9.2,
    "sportsbooks": [
      {
        "name": "DraftKings",
        "odds": -108,
        "link": "https://sportsbook.draftkings.com/...",
        "is_best_odds": true
      }
    ]
  }
]}
```

---

## 🗄️ Database Schema (PostgreSQL)

### Core Tables

**games**
- id, sport, home_team, away_team
- game_date, game_time
- home_score, away_score
- status (scheduled, in_progress, completed)

**predictions**
- id, game_id, model_name
- predicted_winner, confidence
- predicted_spread, predicted_total
- created_at

**esoteric_signals**
- id, game_id, module_name
- signal_value, interpretation
- created_at

**grading_results**
- id, prediction_id
- actual_winner, correct (boolean)
- roi, graded_at

**model_weights**
- id, model_name, weight
- accuracy, updated_at

**player_birth_charts**
- id, player_name
- birth_date, birth_time, birth_location
- sun_sign, moon_sign, ascendant
- chart_data (JSON)

---

## 🌐 External API Integrations

### 1. The Odds API
**URL:** https://the-odds-api.com/
**Purpose:** Live odds from 15+ sportsbooks
**Rate Limits:** 500 requests/month (free tier)
**Environment Variable:** `ODDS_API_KEY`

### 2. Playbook Sports API
**URL:** https://playbook-api.com/
**Purpose:** Sharp money, betting splits, player props
**Environment Variable:** `PLAYBOOK_API_KEY`

### 3. NOAA Space Weather API
**URL:** https://services.swpc.noaa.gov/
**Purpose:** Solar activity and geomagnetic data
**No API Key Required**

---

## 🐳 Deployment (Railway)

**Configuration Files:**
- `Procfile` - `web: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`
- `runtime.txt` - `python-3.12.3`
- `railway.toml` - Health checks and restart policy

**Environment Variables:**
```bash
ODDS_API_KEY=your_key_here
PLAYBOOK_API_KEY=your_key_here
DATABASE_URL=postgresql://... (auto-provided by Railway)
PORT=8000 (auto-set by Railway)
```

**Deploy Steps:**
1. Connect GitHub repo to Railway
2. Set environment variables
3. Deploy from `main` branch
4. Test: `curl https://your-app.railway.app/health`

---

## 📦 Dependencies

### requirements.txt (Production)
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
httpx==0.26.0
pydantic==2.5.3
python-dotenv==1.0.0
psycopg2-binary==2.9.9
tensorflow==2.15.0
scikit-learn==1.4.0
pandas==2.2.0
numpy==1.26.3
eph...