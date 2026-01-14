# Frontend Website Handoff

**Date:** 2026-01-14
**Backend Version:** v14.7
**Production API:** https://web-production-7b2a.up.railway.app

---

## Overview

This document provides everything needed to build a marketing/landing website for Bookie-o-em. The website should showcase the AI betting platform's capabilities and drive users to the main app.

---

## Brand Identity

### Product Name
**Bookie-o-em** - AI Sports Prop Betting Platform

### Tagline Options
- "Where AI Meets Edge"
- "Smash Picks Powered by 17 Signals"
- "The Confluence Advantage"

### Key Differentiators
1. **17 AI Signals** - 8 AI Models + 4 Esoteric + 5 Live Data
2. **8 Pillars of Execution** - Sharp money, reverse line movement, etc.
3. **JARVIS Engine** - Proprietary gematria-based triggers
4. **Dual-Score Confluence** - Research + Esoteric alignment
5. **5 Sports Coverage** - NBA, NFL, MLB, NHL, NCAAB

---

## Website Pages

### 1. Landing Page (/)

**Hero Section:**
```
Headline: "AI-Powered SMASH Picks"
Subhead: "17 signals. 8 pillars. One confluence score."
CTA: "Get Started" → links to bookie-member-app
```

**Feature Cards:**
| Feature | Description | Icon |
|---------|-------------|------|
| SMASH Picks | High-confidence bets with 9.0+ scores | Fire/Lightning |
| Line Shopping | Best odds across 8 sportsbooks | Chart/Compare |
| Parlay Builder | Combine bets with auto-calculated odds | Stack/Layers |
| AI Scoring | 17 signals analyzed in real-time | Brain/Neural |
| Click-to-Bet | One click to your sportsbook | Pointer/Click |

**Live Stats Section (API-powered):**
```bash
# Fetch today's energy for live display
GET /esoteric/today-energy

# Response includes:
{
  "date": "2026-01-14",
  "day_of_week": "Tuesday",
  "moon_phase": "Waxing Crescent",
  "numerology": {...},
  "overall_energy": 7.2
}
```

### 2. How It Works (/how-it-works)

**The Scoring System:**
```
┌─────────────────────────────────────────────────┐
│           CONFLUENCE SCORING (0-20+)            │
├─────────────────────────────────────────────────┤
│  8 AI MODELS (0-8 pts)                          │
│  ├─ Ensemble Stacking (XGBoost+LightGBM)        │
│  ├─ LSTM Neural Network                         │
│  ├─ Matchup Analysis                            │
│  ├─ Monte Carlo Simulation                      │
│  ├─ Line Movement Detection                     │
│  ├─ Rest/Fatigue Modeling                       │
│  ├─ Injury Impact Analysis                      │
│  └─ Betting Edge Calculator                     │
├─────────────────────────────────────────────────┤
│  8 PILLARS (0-8 pts)                            │
│  ├─ Sharp Money Split                           │
│  ├─ Reverse Line Movement                       │
│  ├─ Hospital Fade Protocol                      │
│  ├─ Situational Spot Analysis                   │
│  ├─ Expert Consensus                            │
│  ├─ Prop Correlation                            │
│  ├─ Hook Discipline                             │
│  └─ Volume Discipline                           │
├─────────────────────────────────────────────────┤
│  JARVIS TRIGGERS (0-4 pts)                      │
│  └─ Gematria-based edge signals                 │
├─────────────────────────────────────────────────┤
│  ESOTERIC EDGE (variable)                       │
│  ├─ Numerology alignment                        │
│  ├─ Moon phase influence                        │
│  └─ Tesla 3-6-9 patterns                        │
└─────────────────────────────────────────────────┘
```

**Bet Tiers Explained:**
| Tier | Score | Units | Description |
|------|-------|-------|-------------|
| GOLD_STAR | 9.0+ | 2u | Maximum conviction - all signals aligned |
| EDGE_LEAN | 7.5+ | 1u | Strong edge - most signals agree |
| ML_DOG_LOTTO | Special | 0.5u | NHL Dog Protocol underdog play |
| MONITOR | 6.0+ | 0u | Track but don't bet |
| PASS | <6.0 | 0u | Skip this game |

### 3. Sportsbooks (/sportsbooks)

**Supported Books:**
| Sportsbook | Color | Description |
|------------|-------|-------------|
| DraftKings | #53d337 | America's #1 sportsbook |
| FanDuel | #1493ff | Fast payouts, great promos |
| BetMGM | #c4a44a | Casino + Sports combo |
| Caesars | #0a2240 | Vegas heritage |
| PointsBet | #ed1c24 | Unique pointsbetting |
| William Hill | #00314d | European reliability |
| Barstool | #c41230 | Sports media integration |
| BetRivers | #1b365d | Rush Street Gaming |

**API for sportsbook data:**
```bash
GET /live/sportsbooks
```

### 4. Pricing (/pricing)

*Define your pricing tiers here*

### 5. About (/about)

**Technology Stack:**
- Python + FastAPI backend
- TensorFlow LSTM models
- Real-time odds via The Odds API
- Player stats via Playbook API
- Railway cloud deployment

---

## API Endpoints for Website

### Public Endpoints (No Auth Required)

```bash
# Health check
GET /health

# Today's esoteric energy (for live display)
GET /esoteric/today-energy

# List of sportsbooks
GET /live/sportsbooks
```

### Sample Responses

**Today's Energy:**
```json
{
  "date": "2026-01-14",
  "day_of_week": "Tuesday",
  "moon_phase": "Waxing Crescent",
  "moon_emoji": "🌒",
  "numerology": {
    "life_path": 5,
    "day_number": 14,
    "power_numbers": [5, 14, 23]
  },
  "fibonacci_day": false,
  "tesla_alignment": "NEUTRAL",
  "overall_energy": 7.2,
  "betting_outlook": "FAVORABLE"
}
```

**Sportsbooks:**
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
    }
  ]
}
```

---

## Design Recommendations

### Color Palette
```css
:root {
  --primary: #6366f1;      /* Indigo - main brand */
  --secondary: #22c55e;    /* Green - positive/wins */
  --accent: #f59e0b;       /* Amber - highlights */
  --danger: #ef4444;       /* Red - losses */
  --dark: #1e1e2e;         /* Dark background */
  --light: #f8fafc;        /* Light text */
}
```

### Typography
- Headlines: Inter Bold or Poppins Bold
- Body: Inter Regular
- Monospace (scores): JetBrains Mono

### UI Elements
- Glass morphism cards for bet displays
- Gradient borders for SMASH picks
- Animated number counters for scores
- Real-time data indicators (pulsing dots)

---

## SEO Keywords

Primary: AI sports betting, sports betting picks, betting signals, sharp money
Secondary: SMASH picks, parlay builder, line shopping, betting AI
Long-tail: best AI sports betting app, how to find sharp money bets

---

## Call-to-Actions

| Location | CTA Text | Link |
|----------|----------|------|
| Hero | "Get Started Free" | bookie-member-app signup |
| Features | "See Today's Picks" | bookie-member-app /smash-spots |
| Pricing | "Start Winning" | bookie-member-app signup |
| Footer | "Join Now" | bookie-member-app signup |

---

## Mobile Responsiveness

- Hamburger menu at 768px breakpoint
- Stack feature cards vertically on mobile
- Full-width CTAs on mobile
- Reduce animation complexity on mobile

---

## Analytics Events to Track

```javascript
// Key conversion events
gtag('event', 'signup_click', { location: 'hero' });
gtag('event', 'pricing_view', { tier: 'pro' });
gtag('event', 'sportsbook_click', { book: 'draftkings' });
gtag('event', 'demo_request', {});
```

---

## Links

- **Main App:** bookie-member-app (separate repo)
- **Backend API:** https://web-production-7b2a.up.railway.app
- **API Docs:** See CLAUDE.md in backend repo

---

*Website Handoff v1.0 - 2026-01-14*
