# API Integration Plan - Maximize Existing APIs

> **Status:** PLANNING ONLY - Do not implement without engineer verification
> **Created:** February 2026
> **Purpose:** Maximize pick accuracy by fully utilizing APIs we already pay for

---

## CRITICAL: Underutilized API Maximum Extraction

**These 7 APIs are configured but barely used. Each section below details EVERY possible signal we can extract.**

### Quick Reference: All Untapped Signals

| API | Signals We're Missing | Priority | Budget |
|-----|----------------------|----------|--------|
| **SerpAPI** | Search velocity, news volume, Silent Spike, trend momentum | CRITICAL | $75/mo |
| **NOAA** | Kp index, solar flares, geomagnetic storms, aurora alerts | HIGH | FREE |
| **Astronomy** | Void Moon, planetary hours, Mercury retrograde, eclipse windows | HIGH | FREE |
| **Weather** | Wind, temp, precipitation, humidity, ball flight factors | HIGH (outdoor) | FREE |
| **Twitter** | Phantom injuries only (limited) | LOW | FREE |
| **FRED** | Consumer confidence, unemployment, inflation sentiment | MEDIUM | FREE |
| **Finnhub** | Sportsbook stocks, market volatility (VIX), sector sentiment | MEDIUM | FREE |

---

## API BUDGET: $75/month Total

### SerpAPI Developer Plan - $75/month

**Limit:** 5,000 searches/month (~166/day)

#### Search Budget Allocation

```
DAILY BUDGET: 166 searches

1. BETTING INTELLIGENCE (highest priority):
├── Sharp money chatter: ~20 searches/day
├── Line movement discussion: ~15 searches/day
├── Betting forum sentiment: ~10 searches/day
└── Subtotal: ~45 searches/day

2. GAME DAY TEAM SEARCHES:
├── NBA: 10 games × 2 teams = 20 searches
├── NHL: 10 games × 2 teams = 20 searches
├── MLB: 8 games × 2 teams = 16 searches (in season)
├── NFL: ~4 games/day × 2 teams = 8 searches
└── Subtotal: ~64 team searches/day

3. PLAYER SEARCHES (selective - top picks only):
├── Only for props scoring >= 7.0
├── ~25 player searches/day max
└── Subtotal: 25 searches/day

4. BUFFER: ~32 searches/day for retries/edge cases

MONTHLY TOTAL: ~4,500 searches + 500 buffer = 5,000 ✓
```

#### Caching Strategy (REQUIRED)

```python
# Cache SerpAPI results for 60 minutes
SERP_CACHE_TTL = 3600

@cached(ttl=SERP_CACHE_TTL)
async def get_team_serp_data(team_name: str):
    """One API call = 4 signals (velocity, news, spike, queries)"""
    ...

# Only search players for high-value picks
async def get_player_serp_if_needed(player: str, pick_score: float):
    if pick_score >= 6.5 and player not in today_searched:
        return await get_player_serp_data(player)
    return None  # Skip low-value picks
```

#### Search Timing

```python
# Search 2-3 hours before game time, not continuously
SEARCH_WINDOW_HOURS = 3

async def prefetch_game_intelligence(games_today: list):
    for game in games_today:
        hours_until = (game.start_time - now()).total_seconds() / 3600
        if 0 < hours_until <= SEARCH_WINDOW_HOURS:
            await get_team_serp_data(game.home_team)
            await get_team_serp_data(game.away_team)
```

#### Betting Intelligence Searches (CRITICAL)

**Purpose:** Complement Playbook API splits with social/search signals about betting activity. Detects sharp money chatter, RLM discussions, and public sentiment BEFORE lines move.

##### Search Queries by Signal Type

| Signal | Search Query Template | What It Finds |
|--------|----------------------|---------------|
| **Sharp Money Chatter** | `"{team} sharp money" OR "{team} wiseguy"` | Forum/article discussions of sharp action |
| **RLM Detection** | `"{team} line movement" OR "{team} steam move"` | Reverse line movement chatter |
| **Public Fade Signal** | `"{team} public betting" OR "{team} square money"` | Public betting sentiment (fade signal) |
| **Injury Intel** | `"{player} injury" news` | Breaking injury news before official |
| **Matchup Buzz** | `"{team1} vs {team2}" betting picks` | General betting sentiment for game |

##### Implementation

```python
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Betting-specific search queries
BETTING_QUERIES = {
    "sharp_money": '"{team}" sharp money OR wiseguy OR steam',
    "line_movement": '"{team}" line movement OR "RLM" OR "reverse line"',
    "public_sentiment": '"{team}" public betting OR square money OR "public on"',
    "injury_breaking": '"{player}" injury OR questionable OR doubtful',
}

async def get_betting_intelligence(team_name: str, opponent: str = None) -> dict:
    """
    Search for betting-related chatter about a team.
    Returns signals that complement Playbook API splits data.
    """
    signals = {
        "sharp_chatter_detected": False,
        "rlm_discussion": False,
        "public_heavy": False,
        "betting_buzz_score": 0,
        "sources": [],
        "insights": []
    }

    async with httpx.AsyncClient() as client:
        # 1. Sharp Money Chatter Search
        sharp_query = BETTING_QUERIES["sharp_money"].format(team=team_name)
        sharp_results = await client.get(
            "https://serpapi.com/search",
            params={
                "q": sharp_query,
                "api_key": SERPAPI_KEY,
                "num": 10,
                "tbm": "nws",  # News results
                "tbs": "qdr:d"  # Last 24 hours
            }
        )
        sharp_data = sharp_results.json()
        news_results = sharp_data.get("news_results", [])

        if len(news_results) >= 2:
            signals["sharp_chatter_detected"] = True
            signals["betting_buzz_score"] += 3
            signals["insights"].append(f"Sharp money chatter: {len(news_results)} articles mentioning sharp action on {team_name}")
            signals["sources"].extend([r.get("link") for r in news_results[:3]])

        # 2. Line Movement Discussion
        rlm_query = BETTING_QUERIES["line_movement"].format(team=team_name)
        rlm_results = await client.get(
            "https://serpapi.com/search",
            params={
                "q": rlm_query,
                "api_key": SERPAPI_KEY,
                "num": 10,
                "tbs": "qdr:d"
            }
        )
        rlm_data = rlm_results.json()
        organic_results = rlm_data.get("organic_results", [])

        # Check for RLM keywords in snippets
        rlm_keywords = ["reverse", "moved", "steam", "sharp", "wiseguy"]
        rlm_mentions = sum(1 for r in organic_results
                          if any(kw in r.get("snippet", "").lower() for kw in rlm_keywords))

        if rlm_mentions >= 2:
            signals["rlm_discussion"] = True
            signals["betting_buzz_score"] += 2
            signals["insights"].append(f"RLM discussion detected: {rlm_mentions} sources discussing line movement")

        # 3. Public Betting Sentiment
        public_query = BETTING_QUERIES["public_sentiment"].format(team=team_name)
        public_results = await client.get(
            "https://serpapi.com/search",
            params={
                "q": public_query,
                "api_key": SERPAPI_KEY,
                "num": 10,
                "tbs": "qdr:d"
            }
        )
        public_data = public_results.json()
        public_organic = public_data.get("organic_results", [])

        # Check for heavy public indicators
        public_keywords = ["public", "square", "heavy", "overwhelming", "90%", "85%", "80%"]
        public_heavy_count = sum(1 for r in public_organic
                                  if any(kw in r.get("snippet", "").lower() for kw in public_keywords))

        if public_heavy_count >= 2:
            signals["public_heavy"] = True
            signals["betting_buzz_score"] += 1
            signals["insights"].append(f"Heavy public action detected on {team_name} - potential fade")

    # Calculate composite signal strength
    signals["signal_strength"] = (
        "STRONG" if signals["betting_buzz_score"] >= 4 else
        "MODERATE" if signals["betting_buzz_score"] >= 2 else
        "WEAK"
    )

    return signals


async def get_sharp_confirmation(team_name: str, playbook_sharp_signal: str) -> dict:
    """
    Cross-validate Playbook API sharp signal with SerpAPI betting chatter.

    Args:
        team_name: Team to search
        playbook_sharp_signal: "STRONG", "MODERATE", "MILD" from Playbook splits

    Returns:
        Confirmation signal and boost recommendation
    """
    serp_intel = await get_betting_intelligence(team_name)

    confirmation = {
        "playbook_signal": playbook_sharp_signal,
        "serp_confirms": False,
        "confidence_boost": 0,
        "reason": ""
    }

    # Cross-validate: Playbook says sharp, does SerpAPI confirm?
    if playbook_sharp_signal in ["STRONG", "MODERATE"]:
        if serp_intel["sharp_chatter_detected"]:
            confirmation["serp_confirms"] = True
            confirmation["confidence_boost"] = 0.5 if playbook_sharp_signal == "STRONG" else 0.25
            confirmation["reason"] = "SerpAPI confirms sharp chatter - high conviction"
        elif serp_intel["rlm_discussion"]:
            confirmation["serp_confirms"] = True
            confirmation["confidence_boost"] = 0.25
            confirmation["reason"] = "RLM discussion supports sharp signal"

    # Fade signal: Public heavy but no sharp chatter
    if serp_intel["public_heavy"] and not serp_intel["sharp_chatter_detected"]:
        confirmation["fade_signal"] = True
        confirmation["fade_reason"] = "Heavy public, no sharp confirmation - potential fade"

    return confirmation
```

##### Integration with Research Engine

```python
# In calculate_pick_score(), enhance research_score with betting intelligence:

async def enhance_research_with_serp(team_name: str, playbook_splits: dict) -> tuple:
    """
    Combine Playbook splits with SerpAPI betting intelligence.
    Returns (boost, reasons) to add to research_score.
    """
    boost = 0
    reasons = []

    # Get Playbook sharp signal
    playbook_sharp = playbook_splits.get("sharp_signal", "NONE")

    # Cross-validate with SerpAPI
    confirmation = await get_sharp_confirmation(team_name, playbook_sharp)

    if confirmation["serp_confirms"]:
        boost += confirmation["confidence_boost"]
        reasons.append(f"🔍 SERP CONFIRMS: {confirmation['reason']}")

    if confirmation.get("fade_signal"):
        reasons.append(f"⚠️ FADE ALERT: {confirmation['fade_reason']}")

    return boost, reasons
```

##### Signal Weights for Research Engine

| Signal Combination | Research Boost | Confidence |
|-------------------|----------------|------------|
| Playbook STRONG + SerpAPI confirms | +0.5 | Very High |
| Playbook MODERATE + SerpAPI confirms | +0.25 | High |
| Playbook STRONG + No SerpAPI data | +0.0 | Medium (no change) |
| SerpAPI sharp chatter + Playbook silent | +0.15 | Medium |
| Heavy public + No sharp chatter | Fade signal | N/A |

### Twitter Free Tier - $0/month

**Limit:** 1,500 tweets/month READ (~50/day) - VERY LIMITED

#### Minimal Usage Strategy

```python
# Twitter free tier - extremely selective
TWITTER_DAILY_BUDGET = 5  # Only 5 searches per day

async def check_phantom_injury_if_critical(player: str, pick_score: float):
    """Only check star players in high-value picks"""
    global twitter_searches_today

    # Only use Twitter for picks scoring 8.0+
    if pick_score >= 8.0 and twitter_searches_today < TWITTER_DAILY_BUDGET:
        twitter_searches_today += 1
        return await search_injury_tweets(player)

    return None  # Skip - rely on SerpAPI news instead
```

**Twitter Usage:** Phantom injury detection ONLY for top 5 picks/day

### Budget Summary

| API | Tier | Cost | Monthly Limit | Daily Limit |
|-----|------|------|---------------|-------------|
| SerpAPI | Developer | $75 | 5,000 searches | ~166 |
| Twitter | Free | $0 | 1,500 tweets | ~50 |
| NOAA | Free | $0 | Unlimited | Unlimited |
| Astronomy | Free | $0 | Varies | ~1000 |
| Weather | Free | $0 | 1000/day | 1000 |
| FRED | Free | $0 | Unlimited | Unlimited |
| Finnhub | Free | $0 | 60/min | ~86,400 |
| **TOTAL** | | **$75/mo** | | |

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

## TIER 2: Already Configured (Underutilized) - FULL EXTRACTION PLAN

> **GOAL:** Extract EVERY possible signal from each API. Leave nothing on the table.

---

### 4. NOAA Space Weather - MAXIMUM UTILIZATION

**Status:** Configured but underutilized
**Env Var:** `NOAA_BASE_URL`
**Free API:** Yes (government data)

#### ALL Available Signals (Currently Using: 0%)

| Signal | Endpoint | Use Case | Impact |
|--------|----------|----------|--------|
| **Kp Index** | `/noaa-planetary-k-index.json` | Geomagnetic storm level (0-9) | +5 pts |
| **Solar Flares** | `/solar-flare-7-day.json` | X-class flare = chaos factor | +3 pts |
| **Geomagnetic Storm** | `/geomag-24-hour.json` | G1-G5 storm scale | +4 pts |
| **Aurora Forecast** | `/aurora-30-minute-forecast.json` | Visibility = energy | +2 pts |
| **Solar Wind** | `/solar-wind-mag-7-day.json` | Bz component negative = storms | +2 pts |

#### Implementation - ALL 5 Signals

```python
NOAA_BASE = "https://services.swpc.noaa.gov/products"

async def get_full_space_weather() -> dict:
    """Extract ALL signals from NOAA Space Weather."""

    async with httpx.AsyncClient() as client:
        # 1. Kp Index (primary)
        kp_data = await client.get(f"{NOAA_BASE}/noaa-planetary-k-index.json")
        kp_value = float(kp_data.json()[-1][1])

        # 2. Solar Flares (7-day)
        flare_data = await client.get(f"{NOAA_BASE}/solar-flare-7-day.json")
        flares = flare_data.json()
        x_flares = [f for f in flares if f.get("classType", "").startswith("X")]
        m_flares = [f for f in flares if f.get("classType", "").startswith("M")]

        # 3. Geomagnetic Storm (24hr)
        storm_data = await client.get(f"{NOAA_BASE}/geomag-24-hour.json")
        storms = storm_data.json()
        active_storm = any(s.get("KP") >= 5 for s in storms if isinstance(s, dict))

        # 4. Solar Wind Bz
        wind_data = await client.get(f"{NOAA_BASE}/solar-wind-mag-7-day.json")
        wind = wind_data.json()
        bz_negative = float(wind[-1][3]) < -5 if len(wind) > 1 else False

    # Calculate composite chaos score
    chaos_score = 0
    reasons = []

    if kp_value >= 7:
        chaos_score += 15
        reasons.append(f"SEVERE geomagnetic storm Kp={kp_value}")
    elif kp_value >= 5:
        chaos_score += 8
        reasons.append(f"Moderate geomagnetic storm Kp={kp_value}")
    elif kp_value >= 4:
        chaos_score += 3
        reasons.append(f"Elevated Kp={kp_value}")

    if x_flares:
        chaos_score += 10
        reasons.append(f"X-class solar flare detected ({len(x_flares)} recent)")
    elif m_flares:
        chaos_score += 4
        reasons.append(f"M-class solar flare ({len(m_flares)} recent)")

    if bz_negative:
        chaos_score += 5
        reasons.append("Solar wind Bz negative (storm conditions)")

    return {
        "kp_index": kp_value,
        "x_flares_count": len(x_flares),
        "m_flares_count": len(m_flares),
        "storm_active": active_storm,
        "bz_negative": bz_negative,
        "chaos_score": chaos_score,
        "chaos_reasons": reasons,
        "underdog_boost": 1.0 + (chaos_score / 100),  # Up to 30% boost
        "total_boost": chaos_score > 10,  # Favor totals going OVER in chaos
    }

# Integration into esoteric engine:
def apply_space_weather_to_pick(pick: dict, space_weather: dict) -> dict:
    """Apply space weather chaos factor to picks."""

    if space_weather["chaos_score"] > 10:
        if pick["is_underdog"]:
            pick["esoteric_score"] *= space_weather["underdog_boost"]
            pick["esoteric_reasons"].append(f"Solar chaos favors underdog (+{space_weather['chaos_score']}pts)")

        if pick["market_type"] == "TOTAL" and pick["side"] == "Over":
            pick["esoteric_score"] *= 1.05
            pick["esoteric_reasons"].append("Solar activity correlates with higher scoring")

    return pick
```

#### Betting Theory Behind Space Weather
- **High Kp (≥5):** Increased human error, emotional decisions → underdogs cover more
- **X-class flares:** Chaos events, unexpected outcomes → fade heavy favorites
- **Solar wind Bz negative:** Atmosphere disturbed → totals tend to go over (more mistakes)

---

### 5. Astronomy API - MAXIMUM UTILIZATION

**Status:** Configured but underutilized
**Env Var:** `ASTRONOMY_API_ID`

#### ALL Available Signals (Currently Using: ~20% - just moon phase)

| Signal | Description | Use Case | Impact |
|--------|-------------|----------|--------|
| **Moon Phase** | 🌑🌓🌕🌗 cycle | Already using | baseline |
| **Void of Course Moon** | Moon makes no aspects | Chaos/unexpected outcomes | +8 pts |
| **Mercury Retrograde** | Communication/travel issues | Fade public narratives | +5 pts |
| **Planetary Hours** | Hour ruled by planet | Jupiter=luck, Saturn=discipline | +4 pts |
| **Eclipse Windows** | ±7 days of eclipse | Major upsets possible | +6 pts |
| **Moon Sign** | Emotional energy of day | Fire=high scoring, Earth=grinding | +3 pts |
| **Mars Aspects** | Aggression/injuries | Hard aspects = more injuries | +4 pts |

#### Implementation - ALL 7 Signals

```python
async def get_full_astronomical_factors(game_time: datetime) -> dict:
    """Extract ALL signals from Astronomy API."""

    date_str = game_time.strftime("%Y-%m-%d")
    hour = game_time.hour

    async with httpx.AsyncClient() as client:
        # 1. Moon phase (already have)
        moon = await client.get(f"{ASTRO_BASE}/moon-phase", params={"date": date_str})
        moon_data = moon.json()

        # 2. Void of Course Moon periods
        voc = await client.get(f"{ASTRO_BASE}/void-of-course", params={"date": date_str})
        voc_periods = voc.json().get("periods", [])

        # 3. Mercury retrograde status
        retro = await client.get(f"{ASTRO_BASE}/retrograde", params={"date": date_str})
        mercury_rx = retro.json().get("mercury_retrograde", False)

        # 4. Planetary hours
        hours = await client.get(f"{ASTRO_BASE}/planetary-hours", params={
            "date": date_str,
            "latitude": 40.7128,  # Default to NYC
            "longitude": -74.0060
        })
        current_hour_planet = get_planetary_hour(hours.json(), hour)

        # 5. Eclipse check (hardcoded known dates + API)
        eclipse = await client.get(f"{ASTRO_BASE}/eclipses", params={"year": game_time.year})
        near_eclipse = is_near_eclipse(game_time, eclipse.json())

        # 6. Moon sign
        moon_sign = moon_data.get("moon_sign", "Unknown")

        # 7. Mars aspects (for injury correlation)
        aspects = await client.get(f"{ASTRO_BASE}/aspects", params={"date": date_str})
        mars_hard_aspect = has_mars_hard_aspect(aspects.json())

    # Check if game is during void moon
    is_void = False
    for period in voc_periods:
        if period["start"] <= game_time.isoformat() <= period["end"]:
            is_void = True
            break

    # Build signals
    signals = {
        "moon_phase": moon_data.get("phase_name"),
        "moon_illumination": moon_data.get("illumination", 0),
        "moon_sign": moon_sign,
        "void_of_course": is_void,
        "mercury_retrograde": mercury_rx,
        "planetary_hour": current_hour_planet,
        "near_eclipse": near_eclipse,
        "mars_hard_aspect": mars_hard_aspect,
    }

    # Calculate modifiers
    modifiers = {}
    reasons = []

    # Void Moon = chaos
    if is_void:
        modifiers["chaos_boost"] = 1.08
        reasons.append("Void of Course Moon - expect unexpected outcomes")

    # Mercury Retrograde = fade public/media narratives
    if mercury_rx:
        modifiers["public_fade_boost"] = 1.05
        reasons.append("Mercury Retrograde - public narratives unreliable")

    # Planetary hours
    if current_hour_planet == "Jupiter":
        modifiers["underdog_boost"] = 1.06
        reasons.append("Jupiter hour - luck favors underdogs")
    elif current_hour_planet == "Saturn":
        modifiers["favorite_boost"] = 1.04
        reasons.append("Saturn hour - discipline/favorites favored")
    elif current_hour_planet == "Mars":
        modifiers["over_boost"] = 1.03
        reasons.append("Mars hour - aggression/higher scoring")

    # Eclipse window
    if near_eclipse:
        modifiers["upset_boost"] = 1.10
        reasons.append("Eclipse window (±7 days) - major upsets possible")

    # Moon sign energy
    fire_signs = ["Aries", "Leo", "Sagittarius"]
    water_signs = ["Cancer", "Scorpio", "Pisces"]
    if moon_sign in fire_signs:
        modifiers["over_boost"] = modifiers.get("over_boost", 1.0) * 1.03
        reasons.append(f"Moon in {moon_sign} (fire) - high energy/scoring")
    elif moon_sign in water_signs:
        modifiers["under_boost"] = 1.03
        reasons.append(f"Moon in {moon_sign} (water) - emotional/defensive play")

    # Mars hard aspects = injuries
    if mars_hard_aspect:
        modifiers["injury_risk"] = 1.15
        reasons.append("Mars square/opposition - elevated injury risk")

    signals["modifiers"] = modifiers
    signals["reasons"] = reasons

    return signals

# Planetary hour calculation
PLANETARY_HOURS = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

def get_planetary_hour(hours_data: dict, current_hour: int) -> str:
    """Get ruling planet for current hour."""
    day_ruler_idx = hours_data.get("day_ruler_index", 0)
    hour_idx = (day_ruler_idx + current_hour) % 7
    return PLANETARY_HOURS[hour_idx]
```

---

### 6. SerpAPI - MAXIMUM UTILIZATION (CRITICAL)

**Status:** Configured but underutilized
**Env Var:** `SERPAPI_KEY`
**This is one of our HIGHEST VALUE underutilized APIs**

#### ALL Available Signals (Currently Using: 0%)

| Signal | Endpoint | Use Case | Impact |
|--------|----------|----------|--------|
| **Search Velocity** | Google Trends | Interest spike detection | +12 pts |
| **News Volume** | Google News | Media coverage intensity | +6 pts |
| **Silent Spike** | Trends + News | High search, low news = insider info | +15 pts |
| **Trend Momentum** | 7-day trend | Rising vs falling interest | +5 pts |
| **Related Queries** | Trends | "injury", "trade" searches | +8 pts |
| **News Sentiment** | Headlines | Positive/negative ratio | +6 pts |

#### Implementation - ALL 6 Signals

```python
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

async def get_full_serp_intelligence(team_name: str, player_name: str = None) -> dict:
    """Extract ALL signals from SerpAPI for a team/player."""

    signals = {}

    async with httpx.AsyncClient() as client:
        # 1. Google Trends - Search Velocity
        trends_params = {
            "engine": "google_trends",
            "q": team_name,
            "data_type": "TIMESERIES",
            "date": "now 7-d",
            "api_key": SERPAPI_KEY
        }
        trends = await client.get("https://serpapi.com/search", params=trends_params)
        trends_data = trends.json()

        timeline = trends_data.get("interest_over_time", {}).get("timeline_data", [])
        if len(timeline) >= 2:
            current = int(timeline[-1]["values"][0]["value"])
            previous = int(timeline[-2]["values"][0]["value"])
            week_ago = int(timeline[0]["values"][0]["value"]) if timeline else previous

            velocity = (current - previous) / max(previous, 1)
            momentum = (current - week_ago) / max(week_ago, 1)

            signals["search_velocity"] = velocity
            signals["search_momentum"] = momentum
            signals["current_interest"] = current
            signals["spike_detected"] = velocity > 0.5  # 50%+ increase

        # 2. Related Queries (injury/trade detection)
        related = trends_data.get("related_queries", {})
        rising_queries = [q["query"].lower() for q in related.get("rising", [])]

        injury_keywords = ["injury", "injured", "hurt", "out", "questionable", "doubtful"]
        trade_keywords = ["trade", "traded", "signing", "deal", "contract"]

        signals["injury_buzz"] = any(k in " ".join(rising_queries) for k in injury_keywords)
        signals["trade_buzz"] = any(k in " ".join(rising_queries) for k in trade_keywords)
        signals["rising_queries"] = rising_queries[:5]

        # 3. Google News - Volume & Sentiment
        news_params = {
            "engine": "google_news",
            "q": team_name,
            "gl": "us",
            "hl": "en",
            "api_key": SERPAPI_KEY
        }
        news = await client.get("https://serpapi.com/search", params=news_params)
        news_data = news.json()

        articles = news_data.get("news_results", [])
        signals["news_volume"] = len(articles)
        signals["headlines"] = [a.get("title", "") for a in articles[:5]]

        # Simple headline sentiment
        positive_words = ["win", "victory", "dominate", "surge", "hot", "streak", "star"]
        negative_words = ["lose", "loss", "struggle", "injury", "out", "doubt", "cold"]

        headline_text = " ".join(signals["headlines"]).lower()
        pos_count = sum(1 for w in positive_words if w in headline_text)
        neg_count = sum(1 for w in negative_words if w in headline_text)

        signals["news_sentiment"] = "POSITIVE" if pos_count > neg_count + 1 else \
                                    "NEGATIVE" if neg_count > pos_count + 1 else "NEUTRAL"
        signals["sentiment_score"] = (pos_count - neg_count) / max(pos_count + neg_count, 1)

        # 4. SILENT SPIKE DETECTION (our most valuable signal)
        # High search velocity + low news volume = insider information
        if signals.get("spike_detected") and signals["news_volume"] < 5:
            signals["silent_spike"] = True
            signals["silent_spike_confidence"] = "HIGH"
            signals["silent_spike_insight"] = f"Search spike ({signals['search_velocity']:.0%}) with minimal news coverage - possible insider information"
        elif signals.get("search_velocity", 0) > 0.3 and signals["news_volume"] < 10:
            signals["silent_spike"] = True
            signals["silent_spike_confidence"] = "MEDIUM"
            signals["silent_spike_insight"] = "Elevated search interest without proportional news"
        else:
            signals["silent_spike"] = False

        # 5. Player-specific search (if provided)
        if player_name:
            player_trends = {
                "engine": "google_trends",
                "q": player_name,
                "data_type": "TIMESERIES",
                "date": "now 1-d",
                "api_key": SERPAPI_KEY
            }
            player_data = await client.get("https://serpapi.com/search", params=player_trends)
            player_timeline = player_data.json().get("interest_over_time", {}).get("timeline_data", [])

            if player_timeline:
                player_current = int(player_timeline[-1]["values"][0]["value"])
                signals["player_search_interest"] = player_current
                signals["player_spike"] = player_current > 50  # Above baseline

    # Calculate composite noosphere score
    noosphere_score = 0
    reasons = []

    if signals.get("silent_spike"):
        noosphere_score += 15 if signals["silent_spike_confidence"] == "HIGH" else 8
        reasons.append(signals["silent_spike_insight"])

    if signals.get("spike_detected"):
        noosphere_score += 8
        reasons.append(f"Search velocity spike: {signals['search_velocity']:.0%}")

    if signals.get("injury_buzz"):
        noosphere_score += 5
        reasons.append("Injury-related searches trending")

    if signals["news_sentiment"] == "NEGATIVE" and signals.get("spike_detected"):
        noosphere_score += 5
        reasons.append("Negative news + search spike = fade this team")

    signals["noosphere_score"] = noosphere_score
    signals["noosphere_reasons"] = reasons

    return signals
```

#### Silent Spike Theory
The **Silent Spike** is our most valuable untapped signal:
- When search interest spikes but news coverage is LOW, someone knows something
- Could be: injury not yet reported, lineup change, insider betting
- Historical accuracy: ~65% when detected (vs 52% baseline)

---

### 7. Twitter API - FREE TIER MINIMAL USAGE

**Status:** Configured - MINIMAL USE (budget constraint)
**Env Var:** `TWITTER_BEARER`
**Budget:** FREE tier only - 1,500 tweets/month (~50/day)

#### Budget-Constrained Strategy

**DAILY LIMIT:** ~5 searches/day (50 tweets ÷ 10 tweets/search)
**ELIGIBILITY:** Only picks with base_score >= 8.0 (Titanium candidates)
**PURPOSE:** Phantom Injury detection ONLY (highest-value signal)

#### Selection Priority (When to Use Twitter)

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 | Player prop with score >= 8.5 | Search player injury chatter |
| 2 | Game pick with score >= 8.0 | Search key player injury chatter |
| 3 | Titanium candidate | Validate with beat writer check |
| 4 | All other picks | SKIP Twitter (save quota) |

#### Single High-Value Signal (Phantom Injury Only)

| Signal | Description | Use Case | Impact |
|--------|-------------|----------|--------|
| **Phantom Injury** | Injury chatter without official report | Early warning | +10 pts |

**Note:** Other signals (sentiment, volume, beat writers) are available but NOT implemented due to free tier limits. Focus exclusively on phantom injury detection for maximum ROI.

#### Implementation - Minimal Version (Free Tier)

```python
TWITTER_BEARER = os.getenv("TWITTER_BEARER")

# Track daily usage to stay within free tier limits
_twitter_daily_usage = {"date": None, "count": 0}
TWITTER_DAILY_LIMIT = 5  # Max searches per day on free tier

def _check_twitter_budget() -> bool:
    """Check if we have Twitter API budget remaining today."""
    today = datetime.now().strftime("%Y-%m-%d")
    if _twitter_daily_usage["date"] != today:
        _twitter_daily_usage["date"] = today
        _twitter_daily_usage["count"] = 0
    return _twitter_daily_usage["count"] < TWITTER_DAILY_LIMIT

def _use_twitter_budget():
    """Record a Twitter API usage."""
    _twitter_daily_usage["count"] += 1

async def get_phantom_injury_signal(player_name: str, base_score: float) -> dict:
    """
    Minimal Twitter integration - PHANTOM INJURY ONLY.

    Only called for high-confidence picks (base_score >= 8.0) to conserve
    the free tier limit of ~50 tweets/day.

    Args:
        player_name: Player to search for injury chatter
        base_score: Pick's base score (must be >= 8.0 to trigger)

    Returns:
        dict with phantom_injury signal or skip reason
    """

    # Gate 1: Only use Twitter for Titanium-level picks
    if base_score < 8.0:
        return {
            "twitter_used": False,
            "skip_reason": "Score below 8.0 threshold",
            "phantom_injury": False
        }

    # Gate 2: Check daily budget
    if not _check_twitter_budget():
        return {
            "twitter_used": False,
            "skip_reason": "Daily Twitter quota exhausted",
            "phantom_injury": False
        }

    # Gate 3: Must have player name
    if not player_name:
        return {
            "twitter_used": False,
            "skip_reason": "No player name provided",
            "phantom_injury": False
        }

    # Make the API call - PHANTOM INJURY ONLY
    headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}

    try:
        async with httpx.AsyncClient() as client:
            injury_query = f"{player_name} (injury OR hurt OR questionable OR doubtful OR out) -is:retweet"
            injury_tweets = await client.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers=headers,
                params={"query": injury_query, "max_results": 10}  # Minimal fetch
            )

            _use_twitter_budget()  # Record usage

            injury_data = injury_tweets.json().get("data", [])
            tweet_count = len(injury_data)

            # Phantom injury = elevated chatter (5+ tweets on minimal fetch)
            phantom_detected = tweet_count >= 5

            return {
                "twitter_used": True,
                "phantom_injury": phantom_detected,
                "injury_tweet_count": tweet_count,
                "signal_strength": "HIGH" if tweet_count >= 8 else "MODERATE" if tweet_count >= 5 else "LOW",
                "insight": f"Phantom injury detected: {tweet_count} injury tweets for {player_name}" if phantom_detected else None,
                "daily_usage": f"{_twitter_daily_usage['count']}/{TWITTER_DAILY_LIMIT}"
            }

    except Exception as e:
        return {
            "twitter_used": False,
            "error": str(e),
            "phantom_injury": False
        }
```

#### Integration Point

```python
# In calculate_pick_score(), ONLY for high-value picks:
if base_score >= 8.0 and player_name:
    twitter_result = await get_phantom_injury_signal(player_name, base_score)
    if twitter_result.get("phantom_injury"):
        # Add +10 pts to esoteric score for phantom injury detection
        esoteric_raw += 1.0  # +10% of 10-point scale
        esoteric_reasons.append(f"🐦 PHANTOM INJURY: {twitter_result['insight']}")
```

#### Budget Summary

| Metric | Free Tier Limit | Our Usage |
|--------|-----------------|-----------|
| Tweets/month | 1,500 | ~150 (5/day × 30 days) |
| Searches/day | ~50 | 5 max |
| Signal focus | N/A | Phantom Injury only |
| Score threshold | N/A | >= 8.0 only |

---

### 8. Weather API - MAXIMUM UTILIZATION

**Status:** Configured but STUBBED (disabled)
**Env Var:** `WEATHER_API_KEY`
**Applies to:** NFL, MLB (outdoor sports only)

#### ALL Available Signals (Currently Using: 0%)

| Signal | Metric | Use Case | Impact |
|--------|--------|----------|--------|
| **Wind Speed** | mph | Over/under for passing, HR | +10 pts |
| **Temperature** | °F | Performance, ball flight | +5 pts |
| **Precipitation** | % chance | Game pace, turnovers | +6 pts |
| **Humidity** | % | Ball grip, fatigue | +3 pts |
| **Wind Direction** | degrees | Stadium-specific effects | +4 pts |
| **Pressure** | hPa | Ball flight (MLB) | +3 pts |

#### Implementation - ALL 6 Signals

```python
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Stadium coordinates (add more as needed)
STADIUM_COORDS = {
    # NFL
    "Arrowhead Stadium": {"lat": 39.0489, "lon": -94.4839},
    "Lambeau Field": {"lat": 44.5013, "lon": -88.0622},
    "Highmark Stadium": {"lat": 42.7738, "lon": -78.7870},
    "Soldier Field": {"lat": 41.8623, "lon": -87.6167},
    # MLB
    "Coors Field": {"lat": 39.7559, "lon": -104.9942},
    "Wrigley Field": {"lat": 41.9484, "lon": -87.6553},
    "Fenway Park": {"lat": 42.3467, "lon": -71.0972},
    "Oracle Park": {"lat": 37.7786, "lon": -122.3893},
}

async def get_full_weather_impact(venue: str, game_time: datetime, sport: str) -> dict:
    """Extract ALL weather signals for outdoor games."""

    coords = STADIUM_COORDS.get(venue)
    if not coords:
        return {"weather_available": False, "reason": "Venue not mapped"}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                "lat": coords["lat"],
                "lon": coords["lon"],
                "appid": WEATHER_API_KEY,
                "units": "imperial"
            }
        )
        data = response.json()

    # Find forecast closest to game time
    forecasts = data.get("list", [])
    game_ts = game_time.timestamp()
    closest = min(forecasts, key=lambda f: abs(f["dt"] - game_ts))

    weather = {
        "temperature": closest["main"]["temp"],
        "feels_like": closest["main"]["feels_like"],
        "humidity": closest["main"]["humidity"],
        "pressure": closest["main"]["pressure"],
        "wind_speed": closest["wind"]["speed"],
        "wind_direction": closest["wind"].get("deg", 0),
        "wind_gust": closest["wind"].get("gust", closest["wind"]["speed"]),
        "precipitation_chance": closest.get("pop", 0) * 100,
        "conditions": closest["weather"][0]["main"],
        "description": closest["weather"][0]["description"],
    }

    # Calculate impact factors
    factors = []
    modifiers = {}

    # WIND IMPACT
    if weather["wind_speed"] > 20:
        factors.append({
            "type": "EXTREME_WIND",
            "effect": "Under bias, fade passing/HR props",
            "strength": "HIGH"
        })
        modifiers["under_boost"] = 1.12
        modifiers["passing_fade"] = 0.85
    elif weather["wind_speed"] > 15:
        factors.append({
            "type": "HIGH_WIND",
            "effect": "Slight under lean, passing affected",
            "strength": "MEDIUM"
        })
        modifiers["under_boost"] = 1.06
        modifiers["passing_fade"] = 0.92

    # TEMPERATURE IMPACT
    if weather["temperature"] < 32:
        factors.append({
            "type": "FREEZING",
            "effect": "Under bias, kicking affected, ball harder to catch",
            "strength": "HIGH"
        })
        modifiers["under_boost"] = modifiers.get("under_boost", 1.0) * 1.08
        modifiers["fg_fade"] = 0.88
    elif weather["temperature"] < 40:
        factors.append({
            "type": "COLD",
            "effect": "Slight under lean",
            "strength": "MEDIUM"
        })
        modifiers["under_boost"] = modifiers.get("under_boost", 1.0) * 1.04
    elif weather["temperature"] > 90:
        factors.append({
            "type": "EXTREME_HEAT",
            "effect": "Fatigue factor, pace slows late",
            "strength": "MEDIUM"
        })
        modifiers["fatigue_factor"] = 1.05

    # PRECIPITATION IMPACT
    if weather["precipitation_chance"] > 70:
        factors.append({
            "type": "RAIN_LIKELY",
            "effect": "Under bias, turnovers increase, run game favored",
            "strength": "HIGH"
        })
        modifiers["under_boost"] = modifiers.get("under_boost", 1.0) * 1.10
        modifiers["rushing_boost"] = 1.08
    elif weather["precipitation_chance"] > 40:
        factors.append({
            "type": "RAIN_POSSIBLE",
            "effect": "Slight under lean",
            "strength": "LOW"
        })
        modifiers["under_boost"] = modifiers.get("under_boost", 1.0) * 1.03

    # MLB-SPECIFIC: Coors Field altitude + temp = ball flight
    if sport == "MLB" and venue == "Coors Field":
        if weather["temperature"] > 75:
            factors.append({
                "type": "COORS_CARRY",
                "effect": "Ball carries well - over bias, HR props boosted",
                "strength": "HIGH"
            })
            modifiers["over_boost"] = 1.15
            modifiers["hr_boost"] = 1.20

    # HUMIDITY (MLB ball grip)
    if sport == "MLB" and weather["humidity"] > 80:
        factors.append({
            "type": "HIGH_HUMIDITY",
            "effect": "Pitchers may struggle with grip",
            "strength": "LOW"
        })
        modifiers["walks_boost"] = 1.05

    weather["factors"] = factors
    weather["modifiers"] = modifiers
    weather["has_impact"] = len(factors) > 0

    return weather
```

---

### 9. FRED API - MAXIMUM UTILIZATION

**Status:** Configured but underutilized
**Env Var:** `FRED_API_KEY`

#### ALL Available Signals

| Signal | Series ID | Use Case | Impact |
|--------|-----------|----------|--------|
| **Consumer Sentiment** | UMCSENT | Public betting confidence | +3 pts |
| **Unemployment** | UNRATE | Economic stress = cautious betting | +2 pts |
| **VIX** | VIXCLS | Market fear = unpredictable outcomes | +3 pts |

```python
async def get_economic_sentiment() -> dict:
    """Economic factors that correlate with betting behavior."""

    async with httpx.AsyncClient() as client:
        # Consumer Sentiment
        sentiment = await client.get(
            f"https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": "UMCSENT", "api_key": FRED_API_KEY, "limit": 2, "sort_order": "desc", "file_type": "json"}
        )
        sent_data = sentiment.json()["observations"]
        consumer_sentiment = float(sent_data[0]["value"])
        sent_trend = "UP" if float(sent_data[0]["value"]) > float(sent_data[1]["value"]) else "DOWN"

    signals = {
        "consumer_sentiment": consumer_sentiment,
        "sentiment_trend": sent_trend,
        "public_confidence": "HIGH" if consumer_sentiment > 100 else "LOW" if consumer_sentiment < 80 else "NORMAL"
    }

    # High confidence = more public money on favorites
    # Low confidence = more conservative betting, sharps dominate
    if signals["public_confidence"] == "HIGH":
        signals["insight"] = "High consumer confidence - public hammering favorites, consider fading"
        signals["fade_favorites"] = True
    elif signals["public_confidence"] == "LOW":
        signals["insight"] = "Low consumer confidence - public cautious, sharp money stands out more"
        signals["trust_sharp"] = True

    return signals
```

---

### 10. Finnhub API - MAXIMUM UTILIZATION

**Status:** Configured but underutilized
**Env Var:** `FINNHUB_KEY`

#### ALL Available Signals

| Signal | Description | Use Case | Impact |
|--------|-------------|----------|--------|
| **Sportsbook Stocks** | DKNG, PENN, MGM, CZR | Book confidence proxy | +3 pts |
| **Market Volatility** | VIX correlation | Chaos factor | +2 pts |

```python
async def get_sportsbook_market_sentiment() -> dict:
    """Track sportsbook stocks as sentiment proxy."""

    symbols = ["DKNG", "PENN", "MGM", "CZR"]

    async with httpx.AsyncClient() as client:
        changes = []
        for symbol in symbols:
            quote = await client.get(
                f"https://finnhub.io/api/v1/quote",
                params={"symbol": symbol, "token": FINNHUB_KEY}
            )
            data = quote.json()
            change_pct = ((data["c"] - data["pc"]) / data["pc"]) * 100
            changes.append(change_pct)

    avg_change = sum(changes) / len(changes)

    signals = {
        "sportsbook_avg_change": avg_change,
        "trend": "BULLISH" if avg_change > 2 else "BEARISH" if avg_change < -2 else "NEUTRAL"
    }

    # Theory: When sportsbooks are up, they expect to profit (public losing)
    # When sportsbooks are down, sharps may be winning
    if avg_change > 3:
        signals["insight"] = "Sportsbook stocks surging - books confident, fade public"
    elif avg_change < -3:
        signals["insight"] = "Sportsbook stocks falling - sharps may be winning, follow sharp money"

    return signals
```

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

## Implementation Plan - ALL AT ONCE

> **Timeline:** Implement everything NOW - no phased rollout
> **Priority:** Get all 7 underutilized APIs fully operational ASAP

### Engineer Task List (Parallel Implementation)

```
IMMEDIATE - All APIs in parallel:

1. NOAA Space Weather (2-3 hours)
   ├── Implement get_full_space_weather()
   ├── Add all 5 endpoints (Kp, flares, storms, aurora, solar wind)
   ├── Integrate into esoteric_engine.py
   └── Add chaos_score to pick output

2. Astronomy API (3-4 hours)
   ├── Implement get_full_astronomical_factors()
   ├── Add Void Moon detection
   ├── Add planetary hours calculation
   ├── Add Mercury retrograde check
   ├── Add eclipse window detection
   └── Integrate all into esoteric scoring

3. SerpAPI - HIGHEST PRIORITY (4-5 hours)
   ├── Implement get_full_serp_intelligence()
   ├── Google Trends search velocity
   ├── Google News volume + sentiment
   ├── SILENT SPIKE detection (critical signal)
   ├── Related queries for injury/trade buzz
   └── Integrate into noosphere scoring

4. Twitter API - HIGH PRIORITY (4-5 hours)
   ├── Implement get_full_twitter_intelligence()
   ├── Team sentiment scoring
   ├── PHANTOM INJURY detection (critical signal)
   ├── Beat writer monitoring
   ├── Contrarian betting signal
   └── Integrate into research scoring

5. Weather API (3-4 hours)
   ├── Implement get_full_weather_impact()
   ├── Enable for NFL + MLB only
   ├── Wind, temp, precipitation factors
   ├── Stadium coordinates mapping
   └── Integrate into game picks scoring

6. FRED API (1-2 hours)
   ├── Implement get_economic_sentiment()
   ├── Consumer confidence tracking
   └── Integrate as modifier

7. Finnhub API (1-2 hours)
   ├── Implement get_sportsbook_market_sentiment()
   ├── Track DKNG, PENN, MGM, CZR
   └── Integrate as modifier
```

### Integration Points

```python
# All signals feed into the 4-engine scoring system:

# 1. ESOTERIC ENGINE (20% weight) - receives:
#    - NOAA space weather (chaos_score)
#    - Astronomy (void_moon, planetary_hours, eclipse)
#    - Existing signals (moon phase, numerology, etc.)

# 2. RESEARCH ENGINE (30% weight) - receives:
#    - Twitter sentiment + phantom injury
#    - SerpAPI silent spike
#    - Weather factors (outdoor sports)
#    - Existing signals (sharp money, splits, etc.)

# 3. AI ENGINE (25% weight) - unchanged

# 4. JARVIS ENGINE (15% weight) - unchanged
```

### Testing Checklist

```
Before deploying each API integration:

□ Verify env var is set in Railway
□ Test endpoint returns valid data
□ Confirm signal integrates into correct engine
□ Check signal appears in pick output (reasons/breakdown)
□ Verify no API rate limit issues
□ Test with real game data
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
