# API Integration Plan - Maximize Existing APIs

> **Status:** PLANNING ONLY - Do not implement without engineer verification
> **Created:** February 2026
> **Purpose:** Maximize pick accuracy by fully utilizing APIs we already pay for

---

## Executive Summary

**Key Insight:** We already have 14 APIs configured but aren't fully utilizing them. This plan focuses on extracting maximum value from existing APIs before considering new ones.

### API Priority Hierarchy

```
TIER 1: PRIMARY PAID APIs (Use First)
├── Odds API        → Odds, props, lines, events
├── BallDontLie     → NBA player data, stats, grading
└── Playbook API    → Sharp money, splits, injuries

TIER 2: ALREADY CONFIGURED (Underutilized)
├── NOAA Space Weather  → Solar storms (Kp index)
├── Astronomy API       → Void Moon, Planetary Hours
├── SerpAPI             → Google Trends, News
├── Twitter API         → Real-time sentiment
├── FRED API            → Economic indicators
├── Finnhub API         → Market sentiment
└── Weather API         → Outdoor game factors

TIER 3: NEW APIs (Only if critical gap)
└── (None recommended until Tier 1-2 fully utilized)
```

---

## Current State: All 14 Configured APIs

```bash
curl "https://web-production-7b2a.up.railway.app/live/debug/integrations?quick=true"
```

```
Configured (14):
✅ odds_api           - Primary odds/props
✅ playbook_api       - Sharp/splits/injuries
✅ balldontlie        - NBA player data
✅ weather_api        - Outdoor factors
✅ astronomy_api      - Moon/planetary ← UNDERUTILIZED
✅ noaa_space_weather - Solar storms   ← UNDERUTILIZED
✅ fred_api           - Economic data  ← UNDERUTILIZED
✅ finnhub_api        - Market data    ← UNDERUTILIZED
✅ serpapi            - Trends/news    ← UNDERUTILIZED
✅ twitter_api        - Sentiment      ← UNDERUTILIZED
✅ whop_api           - Membership
✅ database           - PostgreSQL
✅ redis              - Caching
✅ railway_storage    - Persistence
```

---

## TIER 1: Primary Paid APIs (Maximize First)

### 1. Odds API - Current & Enhanced Usage

**Currently Used For:**
- Live odds, spreads, totals
- Player props
- Line movement detection

**Enhancement Opportunities:**

| Signal | Current | Enhanced | Impact |
|--------|---------|----------|--------|
| Line Edge | Basic comparison | Track opening vs current | +5 pts |
| Steam Moves | Simple detection | Velocity + magnitude | +3 pts |
| Reverse Line Movement | Not tracked | Implement RLM detection | +8 pts |

```python
# Enhanced: Reverse Line Movement Detection
def detect_reverse_line_movement(game_data: dict) -> dict:
    """
    RLM: When line moves OPPOSITE to public betting %.
    Example: 70% on Team A, but line moves from -3 to -2.5

    This is a STRONG sharp money indicator.
    """
    public_pct = game_data["public_pct"]  # From Playbook
    line_open = game_data["spread_open"]
    line_current = game_data["spread_current"]

    public_side = "home" if public_pct > 50 else "away"
    line_moved_toward = "home" if line_current < line_open else "away"

    if public_side != line_moved_toward and abs(public_pct - 50) > 15:
        return {
            "rlm_detected": True,
            "sharp_side": line_moved_toward,
            "confidence_boost": 15,
            "insight": f"RLM: {public_pct}% on {public_side} but line moved toward {line_moved_toward}"
        }

    return {"rlm_detected": False}
```

---

### 2. BallDontLie API - Current & Enhanced Usage

**Currently Used For:**
- NBA grading
- Player lookup

**CONFIRMED: BallDontLie does NOT return player birthdates.**

This means Life Path Sync and Biorhythms remain limited to the static player database (now expanded to 307 players).

**Enhancement Opportunities (What BDL CAN provide):**

| Signal | Current | Enhanced | Impact |
|--------|---------|----------|--------|
| Player Form | Default 50/100 | Real 10-game averages | +8 pts |
| Hurst Exponent | Not implemented | Point differential trends | +5 pts |
| Benford Analysis | Not implemented | Scoring digit patterns | +3 pts |

**NOT possible via BDL (keep static database):**
- Life Path Sync → Keep player_birth_data.py (307 players)
- Biorhythms → Keep player_birth_data.py (307 players)

```python
# Player Form Signal (Game Logs)
async def calculate_player_form_bdl(player_id: int, stat_type: str = "pts") -> dict:
    """
    Calculate player's recent form from BallDontLie game logs.
    """
    response = await bdl_client.get("/stats", params={
        "player_ids[]": player_id,
        "per_page": 10
    })
    logs = response.json()["data"]

    if not logs:
        return {"score": 50, "trend": "UNKNOWN"}

    values = [log.get(stat_type, 0) for log in logs]
    recent_avg = sum(values) / len(values)

    # Compare last 3 to previous 7
    recent_3 = sum(values[:3]) / 3 if len(values) >= 3 else recent_avg
    previous_7 = sum(values[3:10]) / min(7, len(values)-3) if len(values) > 3 else recent_avg

    trend_pct = ((recent_3 - previous_7) / previous_7 * 100) if previous_7 > 0 else 0

    return {
        "score": min(100, max(0, 50 + trend_pct)),
        "recent_avg": round(recent_avg, 1),
        "trend": "HOT" if trend_pct > 15 else "COLD" if trend_pct < -15 else "STABLE",
        "insight": f"Trending {'+' if trend_pct > 0 else ''}{trend_pct:.0f}% vs recent average"
    }
```

---

### 3. Playbook API - Current & Enhanced Usage

**Currently Used For:**
- Sharp money %
- Public betting %
- Injuries
- Splits

**Enhancement Opportunities:**

| Signal | Current | Enhanced | Impact |
|--------|---------|----------|--------|
| Sharp vs Public | Basic % | Divergence scoring | +5 pts |
| Injury Impact | List injuries | Impact quantification | +5 pts |
| Situational Spots | Basic | Revenge, rest advantage | +8 pts |

```python
def calculate_sharp_public_divergence(playbook_data: dict) -> dict:
    """
    Measure gap between sharp money and public money.
    Large divergence = strong signal.
    """
    sharp_pct = playbook_data["sharp_pct"]
    public_pct = playbook_data["public_pct"]

    divergence = abs(sharp_pct - public_pct)

    # Sharp side
    sharp_side = "home" if sharp_pct > 50 else "away"

    if divergence > 30:
        return {
            "divergence": divergence,
            "sharp_side": sharp_side,
            "signal_strength": "EXTREME",
            "confidence_boost": 15,
            "insight": f"Sharp {sharp_pct}% vs Public {public_pct}% - {divergence}pt divergence"
        }
    elif divergence > 20:
        return {
            "divergence": divergence,
            "sharp_side": sharp_side,
            "signal_strength": "STRONG",
            "confidence_boost": 10,
            "insight": f"Significant sharp/public divergence"
        }

    return {"divergence": divergence, "signal_strength": "NORMAL", "confidence_boost": 0}
```

---

## TIER 2: Already Configured (Underutilized)

### 4. NOAA Space Weather - Kp Index

**Status:** Configured but underutilized
**Env Var:** `NOAA_BASE_URL`

**What It Can Provide:**
- Kp Index (0-9): Geomagnetic activity level
- Solar storm detection
- Chaos factor for underdogs

```python
# You already have this configured!
# Just need to call it and integrate into esoteric scoring

NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

async def fetch_kp_index() -> dict:
    """
    Kp >= 5: Storm conditions - chaos favors underdogs
    Kp >= 7: Severe storm - significant volatility factor
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(NOAA_KP_URL)
        data = response.json()

    latest = data[-1]
    kp_value = float(latest[1])

    return {
        "kp_value": kp_value,
        "storm_active": kp_value >= 5,
        "storm_level": "SEVERE" if kp_value >= 7 else "MODERATE" if kp_value >= 5 else "NONE",
        "underdog_boost": 1.10 if kp_value >= 7 else 1.05 if kp_value >= 5 else 1.0
    }

# Integration into esoteric:
if kp_data["storm_active"] and game_data["is_underdog"]:
    esoteric_score *= kp_data["underdog_boost"]
    insights.append(f"Solar storm Kp={kp_data['kp_value']} - chaos factor active")
```

---

### 5. Astronomy API - Void Moon & Planetary Hours

**Status:** Configured but underutilized
**Env Var:** `ASTRONOMY_API_ID`

**What It Can Provide:**
- Moon phase (already using)
- Void of Course Moon periods
- Planetary positions
- Planetary hours

```python
# Void of Course Moon
async def get_void_moon_periods(date: date) -> List[dict]:
    """
    Void Moon: Period when Moon makes no major aspects.
    Traditionally inauspicious for new ventures.

    Betting: Avoid NEW bets during VOC, or factor in chaos.
    """
    response = await astronomy_client.get("/void-of-course", params={"date": date.isoformat()})
    return response.json()["periods"]

def is_game_during_void_moon(game_time: datetime, voc_periods: List[dict]) -> dict:
    for period in voc_periods:
        if period["start"] <= game_time <= period["end"]:
            return {
                "is_void": True,
                "warning": "Void Moon active - expect unexpected outcomes",
                "modifier": 0.95  # 5% confidence penalty
            }
    return {"is_void": False, "modifier": 1.0}

# Planetary Hours (already partially implemented?)
# Jupiter hour = underdogs, Saturn hour = favorites
```

---

### 6. SerpAPI - Google Trends & News

**Status:** Configured but underutilized
**Env Var:** `SERPAPI_KEY`

**What It Can Provide:**
- Google Trends (search velocity)
- News aggregation
- Silent spike detection (Noosphere)

```python
# Search Velocity Signal
async def get_search_velocity(team_name: str) -> dict:
    """
    Measure search interest spike for team.
    Silent Spike: High search + low news = insider information
    """
    params = {
        "engine": "google_trends",
        "q": team_name,
        "data_type": "TIMESERIES",
        "api_key": SERPAPI_KEY
    }
    response = await client.get("https://serpapi.com/search", params=params)
    timeline = response.json().get("interest_over_time", {}).get("timeline_data", [])

    if len(timeline) >= 2:
        current = timeline[-1]["values"][0]["value"]
        previous = timeline[-2]["values"][0]["value"]
        velocity = (current - previous) / max(previous, 1)
    else:
        velocity = 0

    return {
        "current_interest": current,
        "velocity": velocity,
        "spike_detected": velocity > 1.0,
        "insight": "Search interest spiking" if velocity > 1.0 else "Normal search volume"
    }

# Silent Spike = High search velocity + Low news volume
async def detect_silent_spike(team_name: str) -> dict:
    search = await get_search_velocity(team_name)
    news = await get_news_volume(team_name)

    if search["spike_detected"] and news["article_count"] < 5:
        return {
            "silent_spike": True,
            "signal": "INSIDER_LEAK",
            "boost": 15,
            "insight": "Search spike without news coverage - information asymmetry detected"
        }
    return {"silent_spike": False, "boost": 0}
```

---

### 7. Twitter API - Real-Time Sentiment

**Status:** Configured but underutilized
**Env Var:** `TWITTER_BEARER`

**What It Can Provide:**
- Real-time sentiment
- Injury chatter detection
- Narrative momentum

```python
# Phantom Injury Detection
async def detect_phantom_injury(player_name: str) -> dict:
    """
    Detect injury chatter without official report.
    """
    query = f"{player_name} injury OR hurt OR questionable -is:retweet"

    response = await twitter_client.get("/tweets/search/recent", params={
        "query": query,
        "max_results": 50
    })

    injury_tweets = len(response.json().get("data", []))

    # Check official injury report (from Playbook)
    official_status = await playbook_client.get_injury_status(player_name)

    if injury_tweets > 10 and not official_status["is_injured"]:
        return {
            "phantom_detected": True,
            "chatter_level": injury_tweets,
            "warning": f"Elevated injury chatter for {player_name} without official report",
            "confidence_modifier": 0.90
        }

    return {"phantom_detected": False}
```

---

### 8. FRED API - Economic Sentiment (Experimental)

**Status:** Configured but underutilized
**Env Var:** `FRED_API_KEY`

**Potential Use:** Consumer confidence correlates with public betting patterns

```python
async def get_economic_sentiment() -> dict:
    """
    Consumer confidence index affects public betting behavior.
    High confidence = more public action on favorites
    Low confidence = more conservative betting
    """
    # UMCSENT = University of Michigan Consumer Sentiment
    response = await fred_client.get("/series/observations", params={
        "series_id": "UMCSENT",
        "limit": 2,
        "sort_order": "desc"
    })

    observations = response.json()["observations"]
    current = float(observations[0]["value"])
    previous = float(observations[1]["value"])

    return {
        "consumer_sentiment": current,
        "trend": "BULLISH" if current > previous else "BEARISH",
        "public_bias": "favorites" if current > 100 else "underdogs"
    }
```

---

### 9. Finnhub API - Market Sentiment (Experimental)

**Status:** Configured but underutilized
**Env Var:** `FINNHUB_KEY`

**Potential Use:** Sportsbook stock performance as market sentiment proxy

```python
async def get_sportsbook_market_sentiment() -> dict:
    """
    Track sportsbook stocks (DKNG, PENN, etc.)
    If sportsbooks are up = they expect public to lose
    If sportsbooks are down = sharps may be winning
    """
    symbols = ["DKNG", "PENN", "MGM", "CZR"]  # Major sportsbook stocks

    sentiments = []
    for symbol in symbols:
        response = await finnhub_client.get("/quote", params={"symbol": symbol})
        quote = response.json()
        change_pct = (quote["c"] - quote["pc"]) / quote["pc"] * 100
        sentiments.append(change_pct)

    avg_change = sum(sentiments) / len(sentiments)

    return {
        "sportsbook_stocks": avg_change,
        "trend": "UP" if avg_change > 1 else "DOWN" if avg_change < -1 else "FLAT",
        "insight": "Books confident (fade public)" if avg_change > 2 else "Books hurting (sharps winning)" if avg_change < -2 else "Normal"
    }
```

---

### 10. Weather API - Outdoor Game Factors

**Status:** Configured (currently stubbed/disabled)
**Env Var:** `WEATHER_API_KEY`

**What It Can Provide:**
- Temperature, wind, precipitation
- Ball travel factors (MLB, NFL)
- Playing conditions

```python
async def get_weather_impact(venue: str, game_time: datetime) -> dict:
    """
    Weather affects:
    - NFL: Wind impacts passing, cold impacts kicking
    - MLB: Temperature affects ball travel, wind affects HR
    """
    coords = VENUE_COORDINATES.get(venue, {"lat": 0, "lon": 0})

    response = await weather_client.get("/forecast", params={
        "lat": coords["lat"],
        "lon": coords["lon"],
        "dt": int(game_time.timestamp())
    })

    weather = response.json()
    temp = weather["main"]["temp"]
    wind = weather["wind"]["speed"]

    impact = {
        "temperature": temp,
        "wind_speed": wind,
        "conditions": weather["weather"][0]["main"],
        "factors": []
    }

    if wind > 15:
        impact["factors"].append({"type": "HIGH_WIND", "effect": "Under bias, fade passing props"})
    if temp < 32:
        impact["factors"].append({"type": "COLD", "effect": "Under bias, kicking affected"})
    if temp > 90:
        impact["factors"].append({"type": "HEAT", "effect": "Fatigue factor, pace slower"})

    return impact
```

---

## Implementation Priority

### Phase 1: Maximize Tier 1 APIs (Week 1)

```
Day 1-2: BallDontLie Enhancement
├── Implement player form from game logs (BDL has this)
├── Implement Hurst exponent from game logs
├── Keep static player_birth_data.py for Life Path (BDL lacks DOB)
└── Test with NBA props

Day 3: Playbook Enhancement
├── Sharp/public divergence scoring
├── RLM detection using Odds API + Playbook
└── Situational spots enhancement

Day 4-5: Integration Testing
├── Test enhanced signals on historical picks
├── Validate weight assignments
└── Measure accuracy impact
```

### Phase 2: Activate Tier 2 APIs (Week 2)

```
Day 1: NOAA Kp Index
├── Call existing endpoint
├── Integrate into esoteric scoring
└── Test solar storm signal

Day 2: Astronomy API Enhancement
├── Void Moon detection
├── Planetary hours calculation
└── Integrate into esoteric

Day 3-4: SerpAPI Noosphere
├── Search velocity signal
├── News volume tracking
├── Silent spike detection

Day 5: Twitter Sentiment
├── Team sentiment scoring
├── Phantom injury detection
└── Linguistic divergence
```

### Phase 3: Experimental Signals (Week 3)

```
Day 1-2: FRED + Finnhub
├── Economic sentiment correlation
├── Sportsbook stock tracking
└── Validate if signals are useful

Day 3-4: Weather API
├── Re-enable for outdoor sports
├── NFL/MLB specific factors
└── Test impact

Day 5: Full System Testing
├── All signals active
├── Weight calibration
├── Production deployment
```

---

## Engineer Verification Checklist

Before implementation:

- [x] ~~Verify BallDontLie API returns player birthdates~~ **CONFIRMED: NO** (keep static DB)
- [ ] Check NOAA endpoint is being called (or just configured)
- [ ] Check Astronomy API endpoint capabilities (void moon?)
- [ ] Verify SerpAPI Google Trends access
- [ ] Check Twitter API rate limits and access level
- [ ] Test each Tier 2 API endpoint manually
- [ ] Confirm all env vars are actually set in Railway
- [ ] Decide: Expand player_birth_data.py further if needed?

---

## Signal Weights (After Full Utilization)

```python
SIGNAL_WEIGHTS = {
    # TIER 1: Primary Paid APIs
    "line_edge": 18,
    "steam_moves": 10,
    "reverse_line_movement": 12,  # NEW
    "sharp_money": 22,
    "public_fade": 11,
    "injury_vacuum": 16,
    "sharp_public_divergence": 10,  # NEW
    "player_form": 10,  # NEW - from BDL game logs
    "hurst_trend": 5,  # NEW - from BDL game logs
    "life_path_sync": 5,  # Keep static 307 players
    "biorhythm": 4,  # Keep static 307 players

    # TIER 2: Underutilized APIs
    "solar_storm": 3,  # NEW - NOAA
    "void_moon": 3,  # NEW - Astronomy
    "planetary_hours": 2,  # NEW - Astronomy
    "search_velocity": 8,  # NEW - SerpAPI
    "silent_spike": 12,  # NEW - SerpAPI
    "sentiment_divergence": 8,  # NEW - Twitter
    "phantom_injury": 6,  # NEW - Twitter

    # Existing Esoteric (Keep as-is)
    "noosphere_velocity": 17,
    "jarvis_trigger": 5,
    "crush_zone": 4,
    "goldilocks": 3,
    "nhl_protocol": 4,
    "gematria": 3,
    "moon_phase": 2,
    "numerology": 2,
    "sacred_geometry": 2,
    "zodiac": 1,
}
```

---

## Success Metrics

Track after implementation:

1. **Signal Contribution:** Which newly-activated signals correlate with wins?
2. **API Utilization:** Are we now calling all configured APIs?
3. **NBA Enhancement:** Did BallDontLie full roster improve NBA picks?
4. **Noosphere Accuracy:** Do Silent Spike picks outperform?
5. **Cost Efficiency:** Same API spend, more signals extracted

---

## Summary

**Focus: Use what we have before buying more.**

| Priority | API | Enhancement | Estimated Impact |
|----------|-----|-------------|------------------|
| 1 | BallDontLie | Player form from game logs | +8 pts |
| 2 | Playbook | Sharp/public divergence | +5 pts |
| 3 | Odds API | RLM detection | +8 pts |
| 4 | SerpAPI | Silent Spike detection | +12 pts |
| 5 | Twitter | Phantom injury detection | +8 pts |
| 6 | NOAA | Kp index (solar storms) | +3 pts |
| 7 | Astronomy | Void Moon | +3 pts |
| 8 | Weather | Outdoor game factors | +10 pts |

**Total potential improvement: +57 points across all signals**
