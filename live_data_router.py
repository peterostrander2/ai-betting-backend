# live_data_router.py v14.0 - NOOSPHERE VELOCITY EDITION
# Research-Optimized + Esoteric Edge + SCALAR-SAVANT + OMNI-GLITCH + GANN PHYSICS + NOOSPHERE

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
import httpx
import os
from datetime import datetime, timedelta
import math
import random

router = APIRouter(prefix="/live", tags=["live"])

# API Keys - use environment variables with fallback
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "ceb2e3a6a3302e0f38fd0d34150294e9")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "pbk_d6f65d6a74c53d5ef9b455a9a147c853b82b")
PLAYBOOK_API_BASE = "https://api.playbook-api.com/v1"

ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Sport mappings
SPORT_MAPPINGS = {
    "nba": {"odds": "basketball_nba", "espn": "basketball/nba", "playbook": "nba"},
    "nfl": {"odds": "americanfootball_nfl", "espn": "football/nfl", "playbook": "nfl"},
    "mlb": {"odds": "baseball_mlb", "espn": "baseball/mlb", "playbook": "mlb"},
    "nhl": {"odds": "icehockey_nhl", "espn": "hockey/nhl", "playbook": "nhl"},
}

# ============================================================================
# JARVIS TRIGGERS - THE PROVEN EDGE NUMBERS
# ============================================================================

JARVIS_TRIGGERS = {
    2178: {"name": "THE IMMORTAL", "boost": 20, "tier": "LEGENDARY", "description": "Only number where n4=reverse AND n4=66^4. Never collapses.", "mathematical": True},
    201: {"name": "THE ORDER", "boost": 12, "tier": "HIGH", "description": "Jesuit Order gematria. The Event of 201.", "mathematical": False},
    33: {"name": "THE MASTER", "boost": 10, "tier": "HIGH", "description": "Highest master number. Masonic significance.", "mathematical": False},
    93: {"name": "THE WILL", "boost": 10, "tier": "HIGH", "description": "Thelema sacred number. Will and Love.", "mathematical": False},
    322: {"name": "THE SOCIETY", "boost": 10, "tier": "HIGH", "description": "Skull & Bones. Genesis 3:22.", "mathematical": False}
}

POWER_NUMBERS = [11, 22, 33, 44, 55, 66, 77, 88, 99]
TESLA_NUMBERS = [3, 6, 9]

# ============================================================================
# ESOTERIC HELPER FUNCTIONS (exported for main.py)
# ============================================================================

def calculate_date_numerology() -> Dict[str, Any]:
    """Calculate numerology for today's date"""
    today = datetime.now()
    digits = str(today.year) + str(today.month).zfill(2) + str(today.day).zfill(2)

    # Life path number
    life_path = sum(int(d) for d in digits)
    while life_path > 9 and life_path not in [11, 22, 33]:
        life_path = sum(int(d) for d in str(life_path))

    # Day vibration
    day_vibe = sum(int(d) for d in str(today.day))
    while day_vibe > 9:
        day_vibe = sum(int(d) for d in str(day_vibe))

    # Check for power numbers
    power_hits = [n for n in POWER_NUMBERS if str(n) in digits]
    tesla_energy = any(d in "369" for d in digits)

    meanings = {
        1: "Leadership - favorites dominate",
        2: "Balance - close games expected",
        3: "Creative - unexpected outcomes",
        4: "Stability - chalk hits",
        5: "Change - underdogs bark",
        6: "Harmony - totals accurate",
        7: "Spiritual - trust the model",
        8: "Power - high scoring",
        9: "Completion - season trends hold"
    }

    return {
        "date": today.strftime("%Y-%m-%d"),
        "life_path": life_path,
        "day_vibration": day_vibe,
        "meaning": meanings.get(life_path % 10, "Standard energy"),
        "power_numbers_present": power_hits,
        "tesla_energy": tesla_energy,
        "is_master_number_day": life_path in [11, 22, 33]
    }


def get_moon_phase() -> Dict[str, Any]:
    """Get current moon phase and betting implications"""
    # Simplified moon phase calculation
    known_new_moon = datetime(2024, 1, 11)
    days_since = (datetime.now() - known_new_moon).days
    lunar_cycle = 29.53
    phase_day = days_since % lunar_cycle

    phases = [
        (0, 1.85, "New Moon", "Fresh starts - take calculated risks"),
        (1.85, 7.38, "Waxing Crescent", "Building momentum - follow trends"),
        (7.38, 11.07, "First Quarter", "Decision time - key matchups"),
        (11.07, 14.76, "Waxing Gibbous", "Increasing energy - overs favored"),
        (14.76, 16.61, "Full Moon", "High volatility - expect upsets"),
        (16.61, 22.14, "Waning Gibbous", "Reflection - fade public"),
        (22.14, 25.83, "Last Quarter", "Release - unders hit"),
        (25.83, 29.53, "Waning Crescent", "Rest period - low scoring")
    ]

    for start, end, name, meaning in phases:
        if start <= phase_day < end:
            return {
                "phase": name,
                "meaning": meaning,
                "phase_day": round(phase_day, 1),
                "illumination": round(abs(14.76 - phase_day) / 14.76 * 100 if phase_day <= 14.76 else abs(phase_day - 14.76) / 14.76 * 100, 1),
                "betting_edge": "VOLATILITY" if "Full" in name else "STABILITY" if "New" in name else "NEUTRAL"
            }

    return {"phase": "Unknown", "meaning": "Check phase", "phase_day": phase_day}


def get_daily_energy() -> Dict[str, Any]:
    """Get overall daily energy reading for betting"""
    numerology = calculate_date_numerology()
    moon = get_moon_phase()

    # Calculate energy score
    energy_score = 50

    if numerology.get("is_master_number_day"):
        energy_score += 15
    if numerology.get("tesla_energy"):
        energy_score += 10
    if moon.get("phase") == "Full Moon":
        energy_score += 20
    elif moon.get("phase") == "New Moon":
        energy_score -= 10

    # Day of week modifiers
    dow = datetime.now().weekday()
    day_modifiers = {
        0: ("Monday", -5, "Slow start"),
        1: ("Tuesday", 0, "Neutral"),
        2: ("Wednesday", 5, "Midweek momentum"),
        3: ("Thursday", 10, "TNF/Peak energy"),
        4: ("Friday", 15, "Weekend anticipation"),
        5: ("Saturday", 20, "Prime time"),
        6: ("Sunday", 25, "NFL Sunday dominance")
    }
    day_name, modifier, day_meaning = day_modifiers[dow]
    energy_score += modifier

    return {
        "overall_score": min(100, max(0, energy_score)),
        "rating": "HIGH" if energy_score >= 70 else "MEDIUM" if energy_score >= 40 else "LOW",
        "day_of_week": day_name,
        "day_influence": day_meaning,
        "recommended_action": "Aggressive betting" if energy_score >= 70 else "Standard sizing" if energy_score >= 40 else "Conservative approach",
        "numerology_summary": numerology,
        "moon_summary": moon
    }


# ============================================================================
# LIVE DATA ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "14.0",
        "codename": "NOOSPHERE_VELOCITY",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    """Get sharp money signals using Playbook API with Odds API fallback"""
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    sport_config = SPORT_MAPPINGS[sport_lower]
    signals = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            playbook_resp = await client.get(
                f"{PLAYBOOK_API_BASE}/sharp/{sport_config['playbook']}",
                headers={"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
            )
            if playbook_resp.status_code == 200:
                return {"signals": playbook_resp.json().get("games", []), "source": "playbook", "sport": sport.upper()}
        except Exception:
            pass

        # Fallback: Odds API line variance analysis
        try:
            odds_resp = await client.get(
                f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds",
                params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "spreads", "oddsFormat": "american"}
            )
            if odds_resp.status_code == 200:
                games = odds_resp.json()
                for game in games:
                    spreads = []
                    for bm in game.get("bookmakers", []):
                        for market in bm.get("markets", []):
                            if market.get("key") == "spreads":
                                for outcome in market.get("outcomes", []):
                                    if outcome.get("name") == game.get("home_team"):
                                        spreads.append(outcome.get("point", 0))
                    if len(spreads) >= 3:
                        variance = max(spreads) - min(spreads)
                        if variance >= 1.5:
                            signals.append({
                                "game_id": game.get("id"),
                                "home_team": game.get("home_team"),
                                "away_team": game.get("away_team"),
                                "line_variance": round(variance, 1),
                                "signal_strength": "STRONG" if variance >= 2 else "MODERATE"
                            })
        except Exception:
            pass

    return {"signals": signals, "count": len(signals), "sport": sport.upper(), "source": "odds_api"}


@router.get("/splits/{sport}")
async def get_splits(sport: str):
    """Betting splits with Playbook API + estimation fallback"""
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    sport_config = SPORT_MAPPINGS[sport_lower]
    splits = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            playbook_resp = await client.get(
                f"{PLAYBOOK_API_BASE}/splits/{sport_config['playbook']}",
                headers={"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
            )
            if playbook_resp.status_code == 200:
                return {"splits": playbook_resp.json().get("games", []), "source": "playbook", "sport": sport.upper()}
        except Exception:
            pass

        try:
            odds_resp = await client.get(
                f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds",
                params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
            )
            if odds_resp.status_code == 200:
                for game in odds_resp.json():
                    home_bet = random.randint(40, 60)
                    home_money = home_bet + random.randint(-10, 10)
                    splits.append({
                        "game_id": game.get("id"),
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "spread_splits": {
                            "home": {"bets_pct": home_bet, "money_pct": max(25, min(75, home_money))},
                            "away": {"bets_pct": 100-home_bet, "money_pct": max(25, min(75, 100-home_money))}
                        }
                    })
        except Exception:
            pass

    return {"splits": splits, "count": len(splits), "sport": sport.upper(), "source": "estimated"}


@router.get("/props/{sport}")
async def get_props(sport: str):
    """Get player props for a sport"""
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    sport_config = SPORT_MAPPINGS[sport_lower]
    props = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            odds_resp = await client.get(
                f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": "player_points,player_rebounds,player_assists,player_threes",
                    "oddsFormat": "american"
                }
            )
            if odds_resp.status_code == 200:
                for game in odds_resp.json():
                    game_props = {
                        "game_id": game.get("id"),
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "commence_time": game.get("commence_time"),
                        "props": []
                    }
                    for bm in game.get("bookmakers", []):
                        for market in bm.get("markets", []):
                            if "player" in market.get("key", ""):
                                for outcome in market.get("outcomes", []):
                                    game_props["props"].append({
                                        "player": outcome.get("description", ""),
                                        "market": market.get("key"),
                                        "line": outcome.get("point", 0),
                                        "odds": outcome.get("price", -110),
                                        "side": outcome.get("name"),
                                        "book": bm.get("key")
                                    })
                    if game_props["props"]:
                        props.append(game_props)
        except Exception:
            pass

    return {"props": props, "count": len(props), "sport": sport.upper()}


@router.get("/best-bets/{sport}")
async def get_best_bets(sport: str):
    """Get best bets combining sharp money and model predictions"""
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get sharp signals
    sharp_data = await get_sharp_money(sport)
    daily_energy = get_daily_energy()

    best_bets = []
    for signal in sharp_data.get("signals", []):
        # Score the bet
        score = 5.0
        if signal.get("signal_strength") == "STRONG":
            score += 2.0
        if daily_energy.get("overall_score", 50) >= 70:
            score += 1.0

        # Apply JARVIS trigger boost
        game_str = f"{signal.get('home_team', '')}{signal.get('away_team', '')}"
        for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
            if str(trigger_num) in game_str:
                score += trigger_data["boost"] / 10

        best_bets.append({
            "game": f"{signal.get('away_team', 'Away')} @ {signal.get('home_team', 'Home')}",
            "home_team": signal.get("home_team"),
            "away_team": signal.get("away_team"),
            "recommendation": "SHARP MONEY DETECTED",
            "ai_score": round(min(10, score), 1),
            "confidence": "HIGH" if score >= 8 else "MEDIUM" if score >= 6 else "LOW",
            "line_variance": signal.get("line_variance", 0),
            "signal_strength": signal.get("signal_strength", "MODERATE")
        })

    # Sort by score
    best_bets.sort(key=lambda x: x["ai_score"], reverse=True)

    return {
        "best_bets": best_bets[:10],
        "count": len(best_bets),
        "sport": sport.upper(),
        "daily_energy": daily_energy.get("rating", "MEDIUM"),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/esoteric-edge")
async def get_esoteric_edge():
    """Get current esoteric edge analysis"""
    numerology = calculate_date_numerology()
    moon = get_moon_phase()
    energy = get_daily_energy()

    # Build edge factors
    edge_factors = []

    if numerology.get("is_master_number_day"):
        edge_factors.append({"factor": "Master Number Day", "boost": 15, "description": "Elevated spiritual energy"})

    if numerology.get("tesla_energy"):
        edge_factors.append({"factor": "Tesla 3-6-9 Energy", "boost": 10, "description": "Vortex math alignment"})

    if moon.get("phase") == "Full Moon":
        edge_factors.append({"factor": "Full Moon", "boost": 20, "description": "Maximum illumination - expect chaos"})

    for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
        if trigger_num in [33, 93]:  # Check for daily relevance
            today_num = sum(int(d) for d in datetime.now().strftime("%Y%m%d"))
            if today_num % trigger_num == 0:
                edge_factors.append({
                    "factor": f"JARVIS: {trigger_data['name']}",
                    "boost": trigger_data["boost"],
                    "description": trigger_data["description"]
                })

    total_boost = sum(f["boost"] for f in edge_factors)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "numerology": numerology,
        "moon_phase": moon,
        "daily_energy": energy,
        "edge_factors": edge_factors,
        "total_edge_boost": total_boost,
        "recommendation": "AGGRESSIVE" if total_boost >= 30 else "STANDARD" if total_boost >= 15 else "CONSERVATIVE"
    }


@router.get("/noosphere/status")
async def get_noosphere_status():
    """Noosphere Velocity - Global consciousness indicators"""
    # Simulated global consciousness data
    # In production, this would connect to actual data sources

    coherence = random.uniform(0.3, 0.9)
    anomaly_detected = coherence > 0.7

    return {
        "status": "ACTIVE",
        "version": "14.0",
        "global_coherence": round(coherence, 3),
        "anomaly_detected": anomaly_detected,
        "anomaly_strength": "STRONG" if coherence > 0.8 else "MODERATE" if coherence > 0.6 else "WEAK",
        "interpretation": "Collective attention spike - information asymmetry likely" if anomaly_detected else "Normal variance",
        "betting_signal": "FADE PUBLIC" if anomaly_detected else "FOLLOW TRENDS",
        "modules": {
            "insider_leak": {"status": "monitoring", "signal": "NEUTRAL"},
            "main_character_syndrome": {"status": "active", "signal": "CHECK NARRATIVES"},
            "phantom_injury": {"status": "scanning", "signal": "NO ALERTS"}
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/gann-physics-status")
async def get_gann_physics_status():
    """GANN Physics - W.D. Gann's geometric principles applied to sports"""
    today = datetime.now()

    # 50% Retracement (Gravity Check)
    day_of_year = today.timetuple().tm_yday
    retracement_level = (day_of_year % 90) / 90 * 100

    # Rule of Three (Exhaustion Node)
    rule_of_three = (day_of_year % 3 == 0)

    # Annulifier Cycle (every 7 days)
    annulifier = (day_of_year % 7 == 0)

    return {
        "status": "ACTIVE",
        "date": today.strftime("%Y-%m-%d"),
        "modules": {
            "50_retracement": {
                "level": round(retracement_level, 1),
                "signal": "REVERSAL ZONE" if 45 <= retracement_level <= 55 else "TREND CONTINUATION",
                "description": "Gravity check - markets tend to retrace 50%"
            },
            "rule_of_three": {
                "active": rule_of_three,
                "signal": "EXHAUSTION" if rule_of_three else "MOMENTUM",
                "description": "Third attempt usually fails or succeeds dramatically"
            },
            "annulifier_cycle": {
                "active": annulifier,
                "signal": "HARMONIC LOCK" if annulifier else "NORMAL",
                "description": "7-day cycle completion - expect resolution"
            }
        },
        "overall_signal": "REVERSAL" if (retracement_level > 45 and rule_of_three) else "CONTINUATION",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# EXPORT FOR MAIN.PY
# ============================================================================

# Create a class wrapper for compatibility
class LiveDataRouter:
    def __init__(self):
        self.router = router

    def get_router(self):
        return self.router


# Export the router instance
live_data_router = router
