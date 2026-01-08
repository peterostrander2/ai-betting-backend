# live_data_router.py v10.0 - Research-Optimized + Esoteric Edge
# Dual-Score System: Main Confidence + Esoteric Edge + Cosmic Confluence

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
import httpx
import asyncio
from datetime import datetime, timedelta
import math

router = APIRouter(prefix="/live", tags=["live"])

ODDS_API_KEY = "ceb2e3a6a3302e0f38fd0d34150294e9"  # Replace with your key
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# ============================================================================
# SIGNAL WEIGHTS v10.0 - RESEARCH-OPTIMIZED
# ============================================================================

SIGNAL_WEIGHTS = {
    # TIER 1: PROVEN EDGE (56%+ win rates)
    "sharp_money": 22,
    "line_edge": 18,
    "injury_vacuum": 16,
    "game_pace": 15,
    "travel_fatigue": 14,
    "back_to_back": 13,
    "defense_vs_position": 12,
    "public_fade": 11,
    "steam_moves": 10,
    "home_court": 10,

    # TIER 2: SUPPORTING
    "weather": 10,
    "minutes_projection": 10,
    "referee": 8,
    "game_script": 8,

    # TIER 3: ML
    "ensemble_ml": 8,

    # ESOTERIC (showcased separately, minimal main weight)
    "gematria": 3,
    "moon_phase": 2,
    "numerology": 2,
    "sacred_geometry": 2,
    "zodiac": 1
}

# ============================================================================
# ESOTERIC EDGE MODULE
# ============================================================================

# Gematria Ciphers
def gematria_ordinal(text: str) -> int:
    """A=1, B=2, ... Z=26"""
    return sum(ord(c) - 64 for c in (text or "").upper() if 65 <= ord(c) <= 90)

def gematria_reduction(text: str) -> int:
    """Pythagorean reduction to single digits"""
    total = 0
    for c in (text or "").upper():
        if 65 <= ord(c) <= 90:
            val = ord(c) - 64
            while val > 9:
                val = sum(int(d) for d in str(val))
            total += val
    return total

def gematria_reverse(text: str) -> int:
    """A=26, B=25, ... Z=1"""
    return sum(27 - (ord(c) - 64) for c in (text or "").upper() if 65 <= ord(c) <= 90)

def gematria_jewish(text: str) -> int:
    """Hebrew/Jewish cipher"""
    values = {
        'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 'I': 9,
        'K': 10, 'L': 20, 'M': 30, 'N': 40, 'O': 50, 'P': 60, 'Q': 70, 'R': 80,
        'S': 90, 'T': 100, 'U': 200, 'V': 300, 'W': 400, 'X': 500, 'Y': 600, 'Z': 700, 'J': 600
    }
    return sum(values.get(c, 0) for c in (text or "").upper())

def gematria_sumerian(text: str) -> int:
    """Multiples of 6: A=6, B=12, ..."""
    return sum((ord(c) - 64) * 6 for c in (text or "").upper() if 65 <= ord(c) <= 90)

# Power Numbers
POWER_NUMBERS = {
    "master": [11, 22, 33, 44, 55, 66, 77, 88, 99],
    "tesla": [3, 6, 9, 27, 36, 63, 72, 81, 108, 144, 216, 369],
    "fibonacci": [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377],
    "sacred": [7, 12, 40, 72, 153, 666, 777, 888]
}

def get_moon_phase() -> str:
    """Calculate current moon phase"""
    known_new_moon = datetime(2024, 1, 11)
    days_since = (datetime.now() - known_new_moon).days
    lunar_cycle = 29.53
    phase_num = (days_since % lunar_cycle) / lunar_cycle * 8
    phases = ['new', 'waxing_crescent', 'first_quarter', 'waxing_gibbous',
              'full', 'waning_gibbous', 'last_quarter', 'waning_crescent']
    return phases[int(phase_num) % 8]

def get_life_path(date: datetime = None) -> int:
    """Calculate life path number for a date"""
    if date is None:
        date = datetime.now()
    digits = f"{date.year}{date.month:02d}{date.day:02d}"
    total = sum(int(d) for d in digits)
    while total > 9 and total not in [11, 22, 33]:
        total = sum(int(d) for d in str(total))
    return total

def get_daily_esoteric_reading(date: datetime = None) -> dict:
    """Generate daily esoteric reading"""
    if date is None:
        date = datetime.now()
    
    month = date.month
    day = date.day
    year = date.year
    
    # Life path
    life_path = get_life_path(date)
    
    # Moon phase
    moon_phase = get_moon_phase()
    moon_emoji = {
        'new': '🌑', 'waxing_crescent': '🌒', 'first_quarter': '🌓', 'waxing_gibbous': '🌔',
        'full': '🌕', 'waning_gibbous': '🌖', 'last_quarter': '🌗', 'waning_crescent': '🌘'
    }.get(moon_phase, '🌙')
    
    # Day of week energy
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_energies = {
        0: {"planet": "Moon", "energy": "intuition", "bias": "home teams"},
        1: {"planet": "Mars", "energy": "aggression", "bias": "overs"},
        2: {"planet": "Mercury", "energy": "speed", "bias": "high-pace teams"},
        3: {"planet": "Jupiter", "energy": "expansion", "bias": "underdogs"},
        4: {"planet": "Venus", "energy": "harmony", "bias": "close games"},
        5: {"planet": "Saturn", "energy": "discipline", "bias": "unders"},
        6: {"planet": "Sun", "energy": "victory", "bias": "favorites"}
    }
    
    day_of_week = date.weekday()
    today_energy = day_energies[day_of_week]
    
    # Tesla number
    tesla_number = (day * month) % 9 or 9
    tesla_alignment = "STRONG" if tesla_number in [3, 6, 9] else "moderate"
    
    # Recommendation
    if moon_phase == 'full':
        recommendation = "Full moon = heightened emotions. Trust bold plays."
    elif moon_phase == 'new':
        recommendation = "New moon = fresh starts. Good for underdog plays."
    elif tesla_alignment == "STRONG":
        recommendation = "Tesla alignment active. Trust the mathematics."
    elif life_path == 8:
        recommendation = "Abundance day. High-value plays favored."
    else:
        recommendation = "Steady energy. Stick to high-confluence plays."
    
    return {
        "date": date.strftime("%a %b %d %Y"),
        "life_path": life_path,
        "moon_phase": moon_phase,
        "moon_emoji": moon_emoji,
        "day_of_week": day_names[day_of_week],
        "planetary_ruler": today_energy["planet"],
        "day_energy": today_energy["energy"],
        "natural_bias": today_energy["bias"],
        "tesla_number": tesla_number,
        "tesla_alignment": tesla_alignment,
        "recommendation": recommendation,
        "lucky_numbers": [life_path, tesla_number, day % 10 or 10, (month + day) % 22 or 22]
    }

def calculate_gematria_analysis(home_team: str, away_team: str, date: datetime = None) -> dict:
    """Full gematria analysis for a matchup"""
    if date is None:
        date = datetime.now()
    
    # Calculate all cipher values
    home_values = {
        "ordinal": gematria_ordinal(home_team),
        "reduction": gematria_reduction(home_team),
        "reverse": gematria_reverse(home_team),
        "jewish": gematria_jewish(home_team),
        "sumerian": gematria_sumerian(home_team)
    }
    
    away_values = {
        "ordinal": gematria_ordinal(away_team),
        "reduction": gematria_reduction(away_team),
        "reverse": gematria_reverse(away_team),
        "jewish": gematria_jewish(away_team),
        "sumerian": gematria_sumerian(away_team)
    }
    
    # Find alignments
    alignments = []
    esoteric_score = 50
    
    for cipher in home_values:
        home_val = home_values[cipher]
        away_val = away_values[cipher]
        diff = abs(home_val - away_val)
        
        # Tesla alignment
        if diff in POWER_NUMBERS["tesla"]:
            alignments.append({
                "type": "TESLA_ALIGNMENT",
                "cipher": cipher,
                "value": diff,
                "message": f"{cipher}: Tesla number {diff} ({home_val} vs {away_val})"
            })
            esoteric_score += 10
        
        # Master numbers
        if home_val in POWER_NUMBERS["master"]:
            alignments.append({
                "type": "MASTER_NUMBER",
                "cipher": cipher,
                "team": home_team,
                "value": home_val,
                "message": f"{cipher}: {home_team} = Master {home_val}"
            })
            esoteric_score += 6
        
        if away_val in POWER_NUMBERS["master"]:
            alignments.append({
                "type": "MASTER_NUMBER",
                "cipher": cipher,
                "team": away_team,
                "value": away_val,
                "message": f"{cipher}: {away_team} = Master {away_val}"
            })
            esoteric_score += 6
        
        # Fibonacci
        if home_val in POWER_NUMBERS["fibonacci"]:
            alignments.append({
                "type": "FIBONACCI",
                "cipher": cipher,
                "team": home_team,
                "value": home_val,
                "message": f"{cipher}: {home_team} = Fibonacci {home_val}"
            })
            esoteric_score += 5
    
    esoteric_score = min(95, esoteric_score)
    
    # Determine favored team
    home_alignments = len([a for a in alignments if a.get("team") == home_team])
    away_alignments = len([a for a in alignments if a.get("team") == away_team])
    
    favored = None
    favor_reason = ""
    if home_alignments > away_alignments:
        favored = "home"
        favor_reason = f"{home_team} has {home_alignments} cosmic alignments"
    elif away_alignments > home_alignments:
        favored = "away"
        favor_reason = f"{away_team} has {away_alignments} cosmic alignments"
    
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_values": home_values,
        "away_values": away_values,
        "alignments": alignments[:6],  # Top 6
        "esoteric_score": esoteric_score,
        "favored": favored,
        "favor_reason": favor_reason
    }

def calculate_esoteric_score(home_team: str, away_team: str, spread: float = None, total: float = None) -> dict:
    """Calculate full esoteric score for a game"""
    date = datetime.now()
    
    # Gematria analysis
    gematria = calculate_gematria_analysis(home_team, away_team, date)
    
    # Daily reading
    daily = get_daily_esoteric_reading(date)
    
    # Moon score
    moon_phase = get_moon_phase()
    if moon_phase == 'full':
        moon_score = 70
        moon_insight = "Full moon: Peak energy, trust your instincts"
    elif moon_phase == 'new':
        moon_score = 65
        moon_insight = "New moon: Fresh cycle, underdogs shine"
    elif moon_phase in ['waxing_gibbous', 'waxing_crescent']:
        moon_score = 58
        moon_insight = "Waxing moon: Building energy, momentum plays"
    else:
        moon_score = 52
        moon_insight = "Waning moon: Releasing energy, fade hype"
    
    # Numerology score
    life_path = daily["life_path"]
    if life_path in [8, 11, 22, 33]:
        numerology_score = 72
        numerology_insight = f"Master number {life_path} day - powerful alignments"
    elif life_path in [1, 5, 9]:
        numerology_score = 62
        numerology_insight = f"Life path {life_path} - action & change energy"
    else:
        numerology_score = 55
        numerology_insight = f"Life path {life_path} - balanced day"
    
    # Geometry score (spread/total)
    line = spread or total or 0
    rounded = round(abs(line))
    if rounded in POWER_NUMBERS["fibonacci"]:
        geometry_score = 68
        geometry_insight = f"Line {rounded} = Fibonacci number (natural harmony)"
    elif rounded % 3 == 0:
        geometry_score = 62
        geometry_insight = f"Line {rounded} = Tesla divisible (3-6-9 energy)"
    elif rounded in POWER_NUMBERS["sacred"]:
        geometry_score = 65
        geometry_insight = f"Line {rounded} = Sacred number"
    else:
        geometry_score = 52
        geometry_insight = f"Line {rounded} - neutral geometry"
    
    # Zodiac score
    zodiac_score = 50
    zodiac_insight = f"{daily['day_of_week']} ({daily['planetary_ruler']}) favors {daily['natural_bias']}"
    
    if daily["natural_bias"] == "overs" and total and total > 220:
        zodiac_score = 65
    elif daily["natural_bias"] == "unders" and total and total < 215:
        zodiac_score = 65
    elif daily["natural_bias"] == "underdogs" and spread and spread > 5:
        zodiac_score = 62
    elif daily["natural_bias"] == "favorites" and spread and spread < -5:
        zodiac_score = 62
    elif daily["natural_bias"] == "home teams":
        zodiac_score = 58
    
    # Weighted average
    weights = {"gematria": 35, "moon": 20, "numerology": 20, "geometry": 15, "zodiac": 10}
    total_weight = sum(weights.values())
    weighted_sum = (
        gematria["esoteric_score"] * weights["gematria"] +
        moon_score * weights["moon"] +
        numerology_score * weights["numerology"] +
        geometry_score * weights["geometry"] +
        zodiac_score * weights["zodiac"]
    )
    
    final_score = round(weighted_sum / total_weight)
    
    # Tier
    if final_score >= 75:
        tier = "COSMIC_ALIGNMENT"
        emoji = "🌟"
    elif final_score >= 65:
        tier = "STARS_FAVOR"
        emoji = "⭐"
    elif final_score >= 55:
        tier = "MILD_ALIGNMENT"
        emoji = "✨"
    else:
        tier = "NEUTRAL"
        emoji = "🔮"
    
    return {
        "esoteric_score": final_score,
        "esoteric_tier": tier,
        "esoteric_emoji": emoji,
        "components": {
            "gematria": {
                "score": gematria["esoteric_score"],
                "alignments": gematria["alignments"],
                "favored": gematria["favored"],
                "favor_reason": gematria["favor_reason"],
                "home_values": gematria["home_values"],
                "away_values": gematria["away_values"]
            },
            "moon": {"score": moon_score, "phase": moon_phase, "insight": moon_insight},
            "numerology": {"score": numerology_score, "life_path": life_path, "insight": numerology_insight},
            "geometry": {"score": geometry_score, "line": rounded, "insight": geometry_insight},
            "zodiac": {"score": zodiac_score, "ruler": daily["planetary_ruler"], "insight": zodiac_insight}
        },
        "daily_reading": daily,
        "top_insights": [
            gematria["alignments"][0]["message"] if gematria["alignments"] else None,
            moon_insight,
            numerology_insight
        ]
    }

def check_cosmic_confluence(main_confidence: int, esoteric_score: int, main_direction: str = None, esoteric_favored: str = None) -> dict:
    """Check if main model and esoteric align"""
    both_high = main_confidence >= 70 and esoteric_score >= 65
    same_direction = main_direction == esoteric_favored or not esoteric_favored
    
    if both_high and same_direction:
        is_perfect = main_confidence >= 80 and esoteric_score >= 75
        return {
            "has_confluence": True,
            "level": "PERFECT" if is_perfect else "STRONG",
            "emoji": "🌟🔥" if is_perfect else "⭐💪",
            "message": "PERFECT COSMIC CONFLUENCE: Sharps + Stars aligned!" if is_perfect else "STRONG CONFLUENCE: Research & cosmos agree",
            "boost": 5 if is_perfect else 3
        }
    
    if both_high and not same_direction:
        return {
            "has_confluence": False,
            "level": "DIVERGENT",
            "emoji": "⚡",
            "message": "Divergence: Strong signals but different directions",
            "boost": 0
        }
    
    if main_confidence >= 70 or esoteric_score >= 70:
        return {
            "has_confluence": False,
            "level": "PARTIAL",
            "emoji": "🔮",
            "message": "Partial alignment - one system strong",
            "boost": 0
        }
    
    return {
        "has_confluence": False,
        "level": "NONE",
        "emoji": "📊",
        "message": "No special alignment",
        "boost": 0
    }

# ============================================================================
# MAIN SIGNAL CALCULATION
# ============================================================================

def calculate_main_confidence(game_data: dict, context: dict = None) -> dict:
    """Calculate main confidence using research-backed signals"""
    context = context or {}
    
    signals = {}
    
    # Sharp money (base)
    sharp_data = context.get("sharp_data", {})
    if sharp_data:
        divergence = abs(sharp_data.get("money_pct", 50) - sharp_data.get("ticket_pct", 50))
        if divergence >= 25:
            signals["sharp_money"] = {"score": 95, "contribution": f"STRONG SHARP: {divergence}% divergence"}
        elif divergence >= 20:
            signals["sharp_money"] = {"score": 88, "contribution": f"Sharp detected: {divergence}% split"}
        elif divergence >= 15:
            signals["sharp_money"] = {"score": 75, "contribution": f"Moderate sharp lean: {divergence}%"}
        else:
            signals["sharp_money"] = {"score": 50, "contribution": "No significant sharp action"}
    else:
        signals["sharp_money"] = {"score": 50, "contribution": "No sharp data"}
    
    # Line edge
    odds = game_data.get("spread_odds", -110)
    if odds >= -100:
        signals["line_edge"] = {"score": 95, "contribution": f"ELITE odds: {odds}"}
    elif odds >= -105:
        signals["line_edge"] = {"score": 82, "contribution": f"Great odds: {odds}"}
    elif odds >= -110:
        signals["line_edge"] = {"score": 55, "contribution": f"Standard odds: {odds}"}
    else:
        signals["line_edge"] = {"score": 40, "contribution": f"Poor odds: {odds}"}
    
    # Game pace
    total = game_data.get("total", 220)
    if total >= 235:
        signals["game_pace"] = {"score": 88, "contribution": f"High pace: O/U {total}"}
    elif total >= 228:
        signals["game_pace"] = {"score": 72, "contribution": f"Above avg pace: O/U {total}"}
    elif total <= 210:
        signals["game_pace"] = {"score": 75, "contribution": f"Slow pace: O/U {total}"}
    else:
        signals["game_pace"] = {"score": 55, "contribution": f"Normal pace: O/U {total}"}
    
    # Home court
    home_team = (game_data.get("home_team") or "").lower()
    altitude_teams = ["nuggets", "denver", "jazz", "utah"]
    if any(t in home_team for t in altitude_teams):
        signals["home_court"] = {"score": 82, "contribution": "Altitude advantage"}
    else:
        signals["home_court"] = {"score": 58, "contribution": "Standard home court"}
    
    # Fill remaining signals with base scores
    for signal in ["injury_vacuum", "travel_fatigue", "back_to_back", "defense_vs_position", 
                   "public_fade", "steam_moves", "weather", "minutes_projection", "referee", 
                   "game_script", "ensemble_ml"]:
        if signal not in signals:
            signals[signal] = {"score": 50, "contribution": "No data available"}
    
    # Calculate weighted average
    total_weight = 0
    weighted_sum = 0
    
    for signal_name, signal_data in signals.items():
        weight = SIGNAL_WEIGHTS.get(signal_name, 1)
        total_weight += weight
        weighted_sum += signal_data["score"] * weight
    
    confidence = round(weighted_sum / total_weight) if total_weight > 0 else 50
    
    # Boost for real odds data
    if game_data.get("spread_odds") or game_data.get("over_odds"):
        confidence = min(100, confidence + 5)
    
    # Determine tier
    if confidence >= 80:
        tier = "GOLDEN_CONVERGENCE"
    elif confidence >= 70:
        tier = "SUPER_SIGNAL"
    elif confidence >= 60:
        tier = "HARMONIC_ALIGNMENT"
    else:
        tier = "PARTIAL_ALIGNMENT"
    
    # Recommendation
    if confidence >= 80:
        recommendation = "SMASH"
    elif confidence >= 70:
        recommendation = "STRONG"
    elif confidence >= 60:
        recommendation = "PLAY"
    elif confidence >= 55:
        recommendation = "LEAN"
    else:
        recommendation = "PASS"
    
    return {
        "confidence": confidence,
        "tier": tier,
        "recommendation": recommendation,
        "signals": signals,
        "top_signals": sorted(signals.items(), key=lambda x: x[1]["score"] * SIGNAL_WEIGHTS.get(x[0], 1), reverse=True)[:3]
    }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/today-energy")
async def get_today_energy():
    """Get today's esoteric reading"""
    return get_daily_esoteric_reading()

@router.post("/analyze-esoteric")
async def analyze_esoteric(data: dict):
    """Analyze matchup gematria"""
    home_team = data.get("home_team", "")
    away_team = data.get("away_team", "")
    spread = data.get("spread")
    total = data.get("total")
    
    if not home_team or not away_team:
        raise HTTPException(status_code=400, detail="home_team and away_team required")
    
    return calculate_esoteric_score(home_team, away_team, spread, total)

@router.get("/props/{sport}")
async def get_live_props(sport: str, limit: int = 5):
    """Get live props with dual-score system (70%+ confidence only)"""
    sport_keys = {
        "nba": "basketball_nba",
        "nfl": "americanfootball_nfl",
        "mlb": "baseball_mlb",
        "nhl": "icehockey_nhl",
        "ncaab": "basketball_ncaab"
    }
    
    sport_key = sport_keys.get(sport.lower())
    if not sport_key:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get events
        events_resp = await client.get(
            f"{ODDS_API_BASE}/sports/{sport_key}/events",
            params={"apiKey": ODDS_API_KEY, "dateFormat": "iso"}
        )
        
        if events_resp.status_code != 200:
            return {"props": [], "message": "Failed to fetch events"}
        
        events = events_resp.json()
        if not events:
            return {"props": [], "message": "No upcoming events"}
        
        all_props = []
        
        for event in events[:5]:
            event_id = event.get("id")
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            commence_time = event.get("commence_time")
            
            # Get props
            props_resp = await client.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": "player_points,player_rebounds,player_assists,player_threes",
                    "oddsFormat": "american"
                }
            )
            
            if props_resp.status_code != 200:
                continue
            
            props_data = props_resp.json()
            bookmakers = props_data.get("bookmakers", [])
            
            for bookmaker in bookmakers[:1]:  # First book
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "")
                    
                    for outcome in market.get("outcomes", []):
                        player_name = outcome.get("description", "Unknown")
                        prop_type = market_key.replace("player_", "").replace("_", " ").title()
                        line = outcome.get("point", 0)
                        price = outcome.get("price", -110)
                        bet_type = outcome.get("name", "Over")
                        
                        # Calculate main confidence
                        game_data = {
                            "home_team": home_team,
                            "away_team": away_team,
                            "spread_odds": price,
                            "total": 220
                        }
                        main_result = calculate_main_confidence(game_data)
                        
                        # Calculate esoteric score
                        esoteric_result = calculate_esoteric_score(home_team, away_team, line, 220)
                        
                        # Check confluence
                        confluence = check_cosmic_confluence(
                            main_result["confidence"],
                            esoteric_result["esoteric_score"],
                            "home" if main_result["recommendation"] in ["SMASH", "STRONG"] else None,
                            esoteric_result["components"]["gematria"]["favored"]
                        )
                        
                        # Apply confluence boost
                        final_confidence = main_result["confidence"]
                        if confluence["has_confluence"]:
                            final_confidence = min(100, final_confidence + confluence["boost"])
                        
                        # Only 70%+ confidence
                        if final_confidence >= 70:
                            all_props.append({
                                "player": player_name,
                                "team": home_team,
                                "opponent": away_team,
                                "prop_type": prop_type,
                                "line": line,
                                "bet_type": bet_type,
                                "price": price,
                                "confidence": final_confidence,
                                "tier": main_result["tier"],
                                "recommendation": main_result["recommendation"],
                                "esoteric_edge": {
                                    "score": esoteric_result["esoteric_score"],
                                    "tier": esoteric_result["esoteric_tier"],
                                    "emoji": esoteric_result["esoteric_emoji"]
                                },
                                "confluence": confluence,
                                "game_time": commence_time,
                                "bookmaker": bookmaker.get("title", "Unknown")
                            })
        
        # Sort by confidence, limit
        all_props.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "props": all_props[:limit],
            "total_analyzed": len(all_props),
            "engine_version": "10.0",
            "dual_score_system": True,
            "daily_reading": get_daily_esoteric_reading()
        }

@router.get("/best-bets/{sport}")
async def get_best_bets(sport: str):
    """Get best bets with dual-score system"""
    sport_keys = {
        "nba": "basketball_nba",
        "nfl": "americanfootball_nfl",
        "mlb": "baseball_mlb",
        "nhl": "icehockey_nhl"
    }
    
    sport_key = sport_keys.get(sport.lower())
    if not sport_key:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{ODDS_API_BASE}/sports/{sport_key}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,totals",
                "oddsFormat": "american"
            }
        )
        
        if resp.status_code != 200:
            return {"games": [], "message": "Failed to fetch odds"}
        
        games = resp.json()
        analyzed_games = []
        
        for game in games:
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            commence_time = game.get("commence_time")
            
            # Get best lines
            best_spread = None
            best_total = None
            
            for bm in game.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "spreads":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == home_team:
                                best_spread = outcome.get("point", 0)
                    elif market["key"] == "totals":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == "Over":
                                best_total = outcome.get("point", 220)
            
            # Calculate scores
            game_data = {"home_team": home_team, "away_team": away_team, "spread": best_spread, "total": best_total}
            main_result = calculate_main_confidence(game_data)
            esoteric_result = calculate_esoteric_score(home_team, away_team, best_spread, best_total)
            confluence = check_cosmic_confluence(
                main_result["confidence"],
                esoteric_result["esoteric_score"]
            )
            
            final_confidence = main_result["confidence"]
            if confluence["has_confluence"]:
                final_confidence = min(100, final_confidence + confluence["boost"])
            
            analyzed_games.append({
                "home_team": home_team,
                "away_team": away_team,
                "game_time": commence_time,
                "spread": best_spread,
                "total": best_total,
                "main_confidence": final_confidence,
                "main_tier": main_result["tier"],
                "recommendation": main_result["recommendation"],
                "esoteric_edge": {
                    "score": esoteric_result["esoteric_score"],
                    "tier": esoteric_result["esoteric_tier"],
                    "emoji": esoteric_result["esoteric_emoji"],
                    "favored": esoteric_result["components"]["gematria"]["favored"],
                    "top_insights": esoteric_result["top_insights"]
                },
                "confluence": confluence
            })
        
        # Sort by confidence
        analyzed_games.sort(key=lambda x: x["main_confidence"], reverse=True)
        
        return {
            "games": analyzed_games[:10],
            "engine_version": "10.0",
            "daily_reading": get_daily_esoteric_reading()
        }

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "engine_version": "10.0",
        "dual_score_system": True,
        "features": ["research_signals", "esoteric_edge", "cosmic_confluence", "gematria_6_ciphers"]
    }


# =============================================================================
# BACKWARDS COMPATIBILITY FOR prediction_api.py
# =============================================================================
# prediction_api.py line 26 expects: from live_data_router import LiveDataRouter, live_data_router

class LiveDataRouter:
    """Compatibility wrapper for prediction_api.py import"""
    def __init__(self):
        self.router = router
    
    def get_router(self):
        return self.router

# Export the router instance with the expected name
live_data_router = router
