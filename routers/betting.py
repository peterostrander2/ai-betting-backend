"""
BETTING ROUTER - User Betting, Tracking, and Parlay Features

Endpoints for:
- Parlay correlation analysis (/parlay-architect)
- Void player impact checking (/void-check/{player})
- Smash card deep link generation (/smash-card)
- User preferences management (/user/preferences/{user_id})
- Bet tracking and grading (/bets/*)
- Parlay building and management (/parlay/*)
- Quick betslip generation (/quick-betslip/{sport}/{game_id})
- Correlation listing (/correlations)

Extracted from live_data_router.py for maintainability.
"""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_api_key
from core.sportsbooks import SPORTSBOOK_CONFIGS, SMASH_LINK_SCHEMES

logger = logging.getLogger(__name__)

# Try to import Pydantic models
try:
    from models.api_models import (
        UserPreferencesRequest,
        TrackBetRequest,
        GradeBetRequest,
        ParlayLegRequest,
        PlaceParlayRequest,
        GradeParlayRequest,
    )
    PYDANTIC_MODELS_AVAILABLE = True
except ImportError:
    PYDANTIC_MODELS_AVAILABLE = False


router = APIRouter(tags=["betting"])


# ============================================================================
# CORRELATION MATRIX - Parlay correlation data
# ============================================================================

CORRELATION_MATRIX = {
    # NFL Correlations
    "QB_WR": {"correlation": 0.88, "name": "BATTERY STACK", "description": "QB throws 300+ yards -> WR1 must have yards"},
    "QB_TE": {"correlation": 0.72, "name": "REDZONE STACK", "description": "QB TDs correlate with TE targets in redzone"},
    "RB_DST": {"correlation": 0.65, "name": "GRIND STACK", "description": "RB dominance = winning = opponent forced passing = sacks/INTs"},
    "WR1_WR2": {"correlation": -0.35, "name": "CANNIBALIZE", "description": "Negative correlation - targets split"},

    # NBA Correlations
    "PG_C": {"correlation": 0.55, "name": "PNR STACK", "description": "Pick and roll - PG assists correlate with C points"},
    "STAR_OUT_BACKUP": {"correlation": 0.82, "name": "USAGE MONSTER", "description": "Star out = backup usage spike"},
    "BLOWOUT_BENCH": {"correlation": 0.70, "name": "GARBAGE TIME", "description": "Blowout = bench minutes spike"},

    # MLB Correlations
    "LEADOFF_RUNS": {"correlation": 0.68, "name": "TABLE SETTER", "description": "Leadoff OBP correlates with team runs"},
    "ACE_UNDER": {"correlation": 0.75, "name": "ACE EFFECT", "description": "Ace pitching = low scoring game"},
}

# Usage impact multipliers when star players are OUT
VOID_IMPACT_MULTIPLIERS = {
    # NBA - Points boost when star is out
    "Joel Embiid": {"teammate": "Tyrese Maxey", "pts_boost": 1.28, "usage_boost": 1.35},
    "LeBron James": {"teammate": "Anthony Davis", "pts_boost": 1.15, "usage_boost": 1.20},
    "Stephen Curry": {"teammate": "Klay Thompson", "pts_boost": 1.22, "usage_boost": 1.25},
    "Luka Doncic": {"teammate": "Kyrie Irving", "pts_boost": 1.18, "usage_boost": 1.22},
    "Giannis Antetokounmpo": {"teammate": "Damian Lillard", "pts_boost": 1.20, "usage_boost": 1.25},
    "Kevin Durant": {"teammate": "Devin Booker", "pts_boost": 1.12, "usage_boost": 1.18},
    "Jayson Tatum": {"teammate": "Jaylen Brown", "pts_boost": 1.15, "usage_boost": 1.20},
    "Nikola Jokic": {"teammate": "Jamal Murray", "pts_boost": 1.25, "usage_boost": 1.30},

    # NFL - Target/usage boost when WR1 is out
    "Davante Adams": {"teammate": "Jakobi Meyers", "target_boost": 1.35, "usage_boost": 1.40},
    "Tyreek Hill": {"teammate": "Jaylen Waddle", "target_boost": 1.28, "usage_boost": 1.32},
    "CeeDee Lamb": {"teammate": "Brandin Cooks", "target_boost": 1.30, "usage_boost": 1.35},
    "Justin Jefferson": {"teammate": "Jordan Addison", "target_boost": 1.38, "usage_boost": 1.42},
}


# ============================================================================
# IN-MEMORY STATE
# In production, this should use Redis or a database
# ============================================================================

_user_preferences: Dict[str, Dict[str, Any]] = {}
_tracked_bets: List[Dict[str, Any]] = []
_parlay_slips: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> list of parlay legs
_placed_parlays: List[Dict[str, Any]] = []  # Tracked parlays


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def deterministic_rng_for_player(player_name: str) -> random.Random:
    """Create a deterministic RNG based on player name for consistent results."""
    import hashlib
    seed = int(hashlib.sha256(str(player_name).encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return 1 + (american_odds / 100)
    else:
        return 1 + (100 / abs(american_odds))


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds."""
    if decimal_odds >= 2.0:
        return int(round((decimal_odds - 1) * 100))
    else:
        return int(round(-100 / (decimal_odds - 1)))


def calculate_parlay_odds(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate combined parlay odds from individual legs.
    Returns decimal odds, American odds, and implied probability.
    """
    if not legs:
        return {"decimal": 1.0, "american": -10000, "implied_probability": 100.0}

    combined_decimal = 1.0
    for leg in legs:
        leg_odds = leg.get("odds", -110)
        combined_decimal *= american_to_decimal(leg_odds)

    combined_american = decimal_to_american(combined_decimal)
    implied_prob = (1 / combined_decimal) * 100

    return {
        "decimal": round(combined_decimal, 3),
        "american": combined_american,
        "implied_probability": round(implied_prob, 2)
    }


def calculate_payout(stake: float, odds: int) -> float:
    """Calculate potential payout from American odds."""
    if stake <= 0:
        return 0
    if odds > 0:
        return stake + (stake * odds / 100)
    else:
        return stake + (stake * 100 / abs(odds))


def generate_enhanced_deep_link(book_key: str, sport: str, game_id: str, game_data: Dict) -> Dict[str, str]:
    """Generate enhanced deep links with sport-specific URLs."""
    config = SPORTSBOOK_CONFIGS.get(book_key)
    if not config:
        return {"web": "#", "note": "Unknown sportsbook"}

    sport_paths = {
        "nba": {
            "draftkings": "basketball/nba",
            "fanduel": "navigation/nba",
            "betmgm": "sports/basketball/104/nba",
            "caesars": "us/nba",
            "pointsbetus": "sports/basketball/nba",
            "williamhill_us": "sports/basketball/nba",
            "barstool": "sports/basketball/nba",
            "betrivers": "sports/basketball/nba"
        },
        "nfl": {
            "draftkings": "football/nfl",
            "fanduel": "navigation/nfl",
            "betmgm": "sports/football/100/nfl",
            "caesars": "us/nfl",
            "pointsbetus": "sports/football/nfl",
            "williamhill_us": "sports/football/nfl",
            "barstool": "sports/football/nfl",
            "betrivers": "sports/football/nfl"
        },
        "mlb": {
            "draftkings": "baseball/mlb",
            "fanduel": "navigation/mlb",
            "betmgm": "sports/baseball/103/mlb",
            "caesars": "us/mlb",
            "pointsbetus": "sports/baseball/mlb",
            "williamhill_us": "sports/baseball/mlb",
            "barstool": "sports/baseball/mlb",
            "betrivers": "sports/baseball/mlb"
        },
        "nhl": {
            "draftkings": "hockey/nhl",
            "fanduel": "navigation/nhl",
            "betmgm": "sports/hockey/102/nhl",
            "caesars": "us/nhl",
            "pointsbetus": "sports/hockey/nhl",
            "williamhill_us": "sports/hockey/nhl",
            "barstool": "sports/hockey/nhl",
            "betrivers": "sports/hockey/nhl"
        }
    }

    sport_path = sport_paths.get(sport, {}).get(book_key, sport)

    # Build URL with game context when possible
    base_url = config["web_base"]
    full_url = f"{base_url}/{sport_path}"

    return {
        "web": full_url,
        "app_scheme": config.get("app_scheme", ""),
        "sport_path": sport_path,
        "note": f"Opens {config['name']} {sport.upper()} page"
    }


# ============================================================================
# PARLAY ARCHITECT - Correlation Engine
# ============================================================================

@router.post("/parlay-architect")
async def parlay_architect(leg1: Dict[str, Any], leg2: Dict[str, Any]):
    """
    Calculates 'Correlation Alpha' for Same Game Parlays (SGP).
    Finds correlated props that books misprice as independent events.

    Request Body:
    {
        "leg1": {"player": "Patrick Mahomes", "position": "QB", "team": "KC", "prop": "passing_yards", "line": 275.5},
        "leg2": {"player": "Travis Kelce", "position": "TE", "team": "KC", "prop": "receiving_yards", "line": 65.5}
    }

    Response:
    {
        "stack_type": "BATTERY STACK",
        "correlation": 0.88,
        "glitch_score": 9.0,
        "recommendation": "CORRELATION GLITCH - Book Misprice Detected",
        "edge_explanation": "If Mahomes hits 275+ yards, Kelce MUST have yards. Books price independently."
    }
    """
    pos1 = leg1.get("position", "").upper()
    pos2 = leg2.get("position", "").upper()
    team1 = leg1.get("team", "").upper()
    team2 = leg2.get("team", "").upper()

    correlation = 0.0
    stack_type = "INDEPENDENT"
    description = "No significant correlation detected"

    # Same team correlations
    if team1 == team2:
        # QB + WR/TE Stack
        if pos1 == "QB" and pos2 in ["WR", "TE"]:
            corr_key = f"QB_{pos2}"
            if corr_key in CORRELATION_MATRIX:
                data = CORRELATION_MATRIX[corr_key]
                correlation = data["correlation"]
                stack_type = data["name"]
                description = data["description"]
        elif pos2 == "QB" and pos1 in ["WR", "TE"]:
            corr_key = f"QB_{pos1}"
            if corr_key in CORRELATION_MATRIX:
                data = CORRELATION_MATRIX[corr_key]
                correlation = data["correlation"]
                stack_type = data["name"]
                description = data["description"]

        # RB + DST Stack
        elif (pos1 == "RB" and pos2 == "DST") or (pos1 == "DST" and pos2 == "RB"):
            data = CORRELATION_MATRIX["RB_DST"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

        # WR1 + WR2 (negative correlation)
        elif pos1 == "WR" and pos2 == "WR":
            data = CORRELATION_MATRIX["WR1_WR2"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

        # PG + C (NBA)
        elif (pos1 == "PG" and pos2 == "C") or (pos1 == "C" and pos2 == "PG"):
            data = CORRELATION_MATRIX["PG_C"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

    # Calculate glitch score
    base_score = 5.0
    if correlation > 0.80:
        base_score += 4.0
        recommendation = "CORRELATION GLITCH - Book Misprice Detected"
    elif correlation > 0.60:
        base_score += 2.5
        recommendation = "MODERATE CORRELATION - Slight Edge"
    elif correlation > 0.40:
        base_score += 1.0
        recommendation = "WEAK CORRELATION - Standard Parlay"
    elif correlation < 0:
        base_score -= 2.0
        recommendation = "NEGATIVE CORRELATION - Avoid This Parlay"
    else:
        recommendation = "INDEPENDENT - No Correlation Edge"

    return {
        "stack_type": stack_type,
        "correlation": round(correlation, 2),
        "glitch_score": round(min(10, max(0, base_score)), 1),
        "recommendation": recommendation,
        "edge_explanation": description,
        "leg1": leg1,
        "leg2": leg2,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/void-check/{player}")
async def void_check(player: str, target_player: Optional[str] = None, baseline_avg: Optional[float] = None):
    """
    The HOF Feature: Recalculates hit rate when a star player is OUT.
    Finds the 'Usage Monster' - the teammate who benefits most.

    Example: /live/void-check/Joel%20Embiid
    Example: /live/void-check/Joel%20Embiid?target_player=Tyrese%20Maxey&baseline_avg=24.0

    Response:
    {
        "missing_star": "Joel Embiid",
        "usage_beneficiary": "Tyrese Maxey",
        "baseline_avg": 24.0,
        "void_avg": 30.7,
        "boost_pct": 28,
        "hit_rate_with_star": "5/10 (50%)",
        "hit_rate_without_star": "8/10 (80%)",
        "signal": "USAGE MONSTER (+6.7 pts without Joel Embiid)",
        "recommendation": "SMASH THE OVER"
    }
    """
    # Normalize player name
    player_normalized = player.title()

    # Check if we have data for this player
    impact_data = VOID_IMPACT_MULTIPLIERS.get(player_normalized)

    if not impact_data:
        # Generate reasonable fallback based on player name hash
        rng = deterministic_rng_for_player(player_normalized)
        pts_boost = 1.15 + (rng.random() * 0.20)  # 15-35% boost
        usage_boost = pts_boost + 0.05

        # Find a generic teammate name
        teammate = target_player or "Teammate"
        base_avg = baseline_avg or rng.randint(18, 28)
    else:
        teammate = target_player or impact_data["teammate"]
        pts_boost = impact_data.get("pts_boost", impact_data.get("target_boost", 1.20))
        usage_boost = impact_data["usage_boost"]
        base_avg = baseline_avg or 24.0  # Default baseline

    void_avg = base_avg * pts_boost
    boost_pct = int((pts_boost - 1) * 100)

    # Calculate hit rates (simulated based on boost)
    base_hit_rate = 50
    void_hit_rate = min(90, base_hit_rate + (boost_pct * 1.2))

    # Generate signal
    diff = void_avg - base_avg
    if diff > 5.0:
        signal = f"USAGE MONSTER (+{diff:.1f} pts without {player_normalized})"
        recommendation = "SMASH THE OVER"
    elif diff > 3.0:
        signal = f"USAGE SPIKE (+{diff:.1f} pts without {player_normalized})"
        recommendation = "LEAN OVER"
    else:
        signal = f"MINOR BUMP (+{diff:.1f} pts without {player_normalized})"
        recommendation = "MONITOR"

    return {
        "missing_star": player_normalized,
        "usage_beneficiary": teammate,
        "baseline_avg": round(base_avg, 1),
        "void_avg": round(void_avg, 1),
        "boost_pct": boost_pct,
        "usage_boost_pct": int((usage_boost - 1) * 100),
        "hit_rate_with_star": f"{base_hit_rate // 10}/10 ({base_hit_rate}%)",
        "hit_rate_without_star": f"{int(void_hit_rate) // 10}/10 ({int(void_hit_rate)}%)",
        "signal": signal,
        "recommendation": recommendation,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/smash-card")
async def generate_smash_card(bet_data: Dict[str, Any], book: Optional[str] = "draftkings"):
    """
    Generates a 'Smash Card' with deep links for one-tap betting.
    Bypasses sportsbook lobby and drops user directly into bet slip.

    Request Body:
    {
        "bet_data": {
            "player": "Tyrese Maxey",
            "prop": "points",
            "line": 28.5,
            "pick": "over",
            "odds": -110,
            "hit_rate": "8/10",
            "reasoning": "Embiid OUT - Usage Spike",
            "event_id": "nba_phi_vs_sac_123",
            "market_id": "player_points_maxey"
        },
        "book": "draftkings"
    }
    """
    book_key = book.lower() if book else "draftkings"
    book_config = SPORTSBOOK_CONFIGS.get(book_key, SPORTSBOOK_CONFIGS["draftkings"])
    link_schemes = SMASH_LINK_SCHEMES.get(book_key, SMASH_LINK_SCHEMES["draftkings"])

    player = bet_data.get("player", "Player")
    prop = bet_data.get("prop", "points")
    line = bet_data.get("line", 0)
    pick = bet_data.get("pick", "over").upper()
    odds = bet_data.get("odds", -110)
    hit_rate = bet_data.get("hit_rate", "7/10")
    reasoning = bet_data.get("reasoning", "AI Analysis")
    event_id = bet_data.get("event_id", "event_123")
    market_id = bet_data.get("market_id", "market_456")

    # Parse hit rate for visual
    try:
        hits, total = hit_rate.split("/")
        hit_pct = int(int(hits) / int(total) * 100)
    except Exception:
        hit_pct = 70

    # Generate hit rate bar
    filled = hit_pct // 10
    empty = 10 - filled
    hit_rate_bar = f"[{'█' * filled}{'░' * empty}] {hit_pct}%"

    # Determine confidence
    if hit_pct >= 80:
        confidence = "HIGH"
    elif hit_pct >= 60:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Generate deep links
    sport = bet_data.get("sport", "nba").upper()
    sport_path = {"NBA": "basketball/nba", "NFL": "football/nfl", "MLB": "baseball/mlb", "NHL": "hockey/nhl"}.get(sport, "basketball/nba")

    deep_links = {
        "app": link_schemes["app"].format(sport=sport, event_id=event_id, market_id=market_id),
        "web": link_schemes["web"].format(sport_path=sport_path, event_id=event_id),
        "universal": link_schemes["universal"].format(sport=sport.lower(), event_id=event_id, market_id=market_id)
    }

    return {
        "smash_card": {
            "title": f"SMASH: {player} {pick} {line} {prop.upper()}",
            "subtitle": reasoning,
            "odds_display": f"{'+' if odds > 0 else ''}{odds}",
            "hit_rate_display": hit_rate_bar,
            "hit_rate_raw": hit_rate,
            "confidence": confidence,
            "button": {
                "text": f"Place on {book_config['name']}",
                "color": book_config["color"],
                "logo": book_config.get("logo", "")
            },
            "deep_links": deep_links,
            "all_books": [
                {
                    "key": key,
                    "name": cfg["name"],
                    "color": cfg["color"],
                    "logo": cfg.get("logo", ""),
                    "deep_link": SMASH_LINK_SCHEMES.get(key, {}).get("universal", "").format(
                        sport=sport.lower(), event_id=event_id, market_id=market_id
                    )
                }
                for key, cfg in SPORTSBOOK_CONFIGS.items()
            ]
        },
        "bet_data": bet_data,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/correlations")
async def list_correlations():
    """List all known correlation patterns for parlay building."""
    return {
        "count": len(CORRELATION_MATRIX),
        "correlations": [
            {
                "key": key,
                "name": data["name"],
                "correlation": data["correlation"],
                "description": data["description"],
                "edge": "HIGH" if data["correlation"] > 0.75 else "MEDIUM" if data["correlation"] > 0.5 else "LOW"
            }
            for key, data in CORRELATION_MATRIX.items()
        ],
        "void_players": list(VOID_IMPACT_MULTIPLIERS.keys()),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# USER PREFERENCES
# ============================================================================

@router.get("/user/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """
    Get user's sportsbook preferences.

    Returns:
    - favorite_books: List of preferred sportsbooks (in order)
    - default_bet_amount: Default stake amount
    - notifications: Notification preferences
    """
    prefs = _user_preferences.get(user_id, {
        "user_id": user_id,
        "favorite_books": ["draftkings", "fanduel", "betmgm"],
        "default_bet_amount": 25,
        "auto_best_odds": True,
        "notifications": {
            "smash_alerts": True,
            "odds_movement": True,
            "bet_results": True
        },
        "created_at": datetime.now().isoformat()
    })

    return prefs


@router.post("/user/preferences/{user_id}")
async def save_user_preferences(user_id: str, prefs: UserPreferencesRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any]):
    """
    Save user's sportsbook preferences.

    Request Body (validated with Pydantic):
    - favorite_books: array of strings (validated against supported books)
    - default_bet_amount: float (default: 25, must be >= 0)
    - auto_best_odds: bool (default: true)
    - notifications: object with smash_alerts, odds_movement, bet_results booleans
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(prefs, 'dict'):
        data = prefs.dict()
    else:
        data = prefs if isinstance(prefs, dict) else dict(prefs)

    # Validate favorite_books
    valid_books = list(SPORTSBOOK_CONFIGS.keys())
    favorite_books = data.get("favorite_books", [])
    validated_books = [b for b in favorite_books if b in valid_books]

    # Get notifications, handling nested object
    notifications_data = data.get("notifications", {})
    if hasattr(notifications_data, 'dict'):
        notifications_data = notifications_data.dict()

    _user_preferences[user_id] = {
        "user_id": user_id,
        "favorite_books": validated_books if validated_books else ["draftkings", "fanduel", "betmgm"],
        "default_bet_amount": data.get("default_bet_amount", 25),
        "auto_best_odds": data.get("auto_best_odds", True),
        "notifications": notifications_data if notifications_data else {
            "smash_alerts": True,
            "odds_movement": True,
            "bet_results": True
        },
        "updated_at": datetime.now().isoformat()
    }

    return {"status": "saved", "preferences": _user_preferences[user_id]}


# ============================================================================
# BET TRACKING
# ============================================================================

@router.post("/bets/track")
async def track_bet(
    bet_data: TrackBetRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Track a bet that was placed through the click-to-bet flow.

    Request Body (validated with Pydantic):
    - user_id: str (default: "anonymous")
    - sport: str (required, validated: NBA/NFL/MLB/NHL)
    - game_id: str (required)
    - game: str (default: "Unknown Game")
    - bet_type: str (required)
    - selection: str (required)
    - line: float (optional)
    - odds: int (required, validated: American odds format)
    - sportsbook: str (required)
    - stake: float (default: 0, must be >= 0)
    - ai_score: float (optional, 0-20)
    - confluence_level: str (optional)

    Returns bet_id for later grading.
    """
    # Handle both Pydantic model and dict input for backwards compatibility
    if PYDANTIC_MODELS_AVAILABLE and hasattr(bet_data, 'dict'):
        data = bet_data.dict()
    else:
        # Fallback validation for dict input
        data = bet_data if isinstance(bet_data, dict) else dict(bet_data)
        required_fields = ["sport", "game_id", "bet_type", "selection", "odds", "sportsbook"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        # Validate odds format
        if data.get("odds") and (data["odds"] == 0 or (-100 < data["odds"] < 100)):
            raise HTTPException(status_code=400, detail="Invalid odds. American odds must be <= -100 or >= 100")
        data["sport"] = data.get("sport", "").upper()

    bet_id = f"BET_{data['sport']}_{data['game_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tracked_bet = {
        "bet_id": bet_id,
        "user_id": data.get("user_id", "anonymous"),
        "sport": data["sport"],
        "game_id": data["game_id"],
        "game": data.get("game", "Unknown Game"),
        "bet_type": data["bet_type"],
        "selection": data["selection"],
        "line": data.get("line"),
        "odds": data["odds"],
        "sportsbook": data["sportsbook"],
        "stake": data.get("stake", 0),
        "potential_payout": calculate_payout(data.get("stake", 0), data["odds"]),
        "ai_score": data.get("ai_score"),
        "confluence_level": data.get("confluence_level"),
        "status": "PENDING",
        "result": None,
        "placed_at": datetime.now().isoformat()
    }

    _tracked_bets.append(tracked_bet)

    return {
        "status": "tracked",
        "bet_id": bet_id,
        "bet": tracked_bet,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/bets/grade/{bet_id}")
async def grade_bet(
    bet_id: str,
    result_data: GradeBetRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Grade a tracked bet with actual result.

    Request Body (validated with Pydantic):
    - result: str (required, must be WIN, LOSS, or PUSH)
    - actual_score: str (optional)
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(result_data, 'result'):
        result = result_data.result.value if hasattr(result_data.result, 'value') else str(result_data.result)
        actual_score = result_data.actual_score
    else:
        result = result_data.get("result", "").upper()
        actual_score = result_data.get("actual_score")
        if result not in ["WIN", "LOSS", "PUSH"]:
            raise HTTPException(status_code=400, detail="Result must be WIN, LOSS, or PUSH")

    for bet in _tracked_bets:
        if bet["bet_id"] == bet_id:
            bet["status"] = "GRADED"
            bet["result"] = result
            bet["actual_score"] = actual_score
            bet["graded_at"] = datetime.now().isoformat()

            # Calculate actual profit/loss
            if result == "WIN":
                bet["profit"] = bet["potential_payout"] - bet["stake"]
            elif result == "LOSS":
                bet["profit"] = -bet["stake"]
            else:  # PUSH
                bet["profit"] = 0

            return {"status": "graded", "bet": bet}

    raise HTTPException(status_code=404, detail=f"Bet not found: {bet_id}")


@router.get("/bets/history")
async def get_bet_history(
    user_id: Optional[str] = None,
    sport: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    auth: bool = Depends(verify_api_key)
):
    """
    Get bet history with optional filters.

    Supports filtering by:
    - user_id: Filter by user
    - sport: Filter by sport (NBA, NFL, etc.)
    - status: Filter by status (PENDING, GRADED)
    - limit: Max 500 results (default 50)
    """
    # Validate and cap limit to prevent DoS
    limit = min(max(1, limit), 500)
    filtered_bets = _tracked_bets.copy()

    if user_id:
        filtered_bets = [b for b in filtered_bets if b.get("user_id") == user_id]
    if sport:
        filtered_bets = [b for b in filtered_bets if b.get("sport") == sport.upper()]
    if status:
        filtered_bets = [b for b in filtered_bets if b.get("status") == status.upper()]

    # Sort by placed_at descending
    filtered_bets.sort(key=lambda x: x.get("placed_at", ""), reverse=True)

    # Calculate stats
    graded_bets = [b for b in filtered_bets if b.get("status") == "GRADED"]
    wins = len([b for b in graded_bets if b.get("result") == "WIN"])
    losses = len([b for b in graded_bets if b.get("result") == "LOSS"])
    pushes = len([b for b in graded_bets if b.get("result") == "PUSH"])
    total_profit = sum(b.get("profit", 0) for b in graded_bets)

    return {
        "bets": filtered_bets[:limit],
        "count": len(filtered_bets[:limit]),
        "total_tracked": len(filtered_bets),
        "stats": {
            "graded": len(graded_bets),
            "pending": len(filtered_bets) - len(graded_bets),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / len(graded_bets) * 100, 1) if graded_bets else 0,
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / sum(b.get("stake", 1) for b in graded_bets) * 100, 1) if graded_bets else 0
        },
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PARLAY BUILDER
# ============================================================================

@router.get("/parlay/{user_id}")
async def get_parlay_slip(user_id: str):
    """
    Get current parlay slip for a user.

    Returns all legs in the parlay with calculated combined odds.
    """
    legs = _parlay_slips.get(user_id, [])
    combined = calculate_parlay_odds(legs)

    return {
        "user_id": user_id,
        "legs": legs,
        "leg_count": len(legs),
        "combined_odds": combined,
        "max_legs": 12,
        "can_add_more": len(legs) < 12,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/add")
async def add_parlay_leg(
    leg_data: ParlayLegRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Add a leg to a user's parlay slip.

    Request Body (validated with Pydantic):
    - user_id: str (required)
    - sport: str (required, auto-uppercased)
    - game_id: str (required)
    - game: str (default: "Unknown Game")
    - bet_type: str (required)
    - selection: str (required)
    - line: float (optional)
    - odds: int (required, validated American format)
    - ai_score: float (optional)

    Returns updated parlay slip with combined odds.
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(leg_data, 'dict'):
        data = leg_data.dict()
    else:
        data = leg_data if isinstance(leg_data, dict) else dict(leg_data)
        required_fields = ["user_id", "sport", "game_id", "bet_type", "selection", "odds"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        # Validate odds
        if data.get("odds") and (data["odds"] == 0 or (-100 < data["odds"] < 100)):
            raise HTTPException(status_code=400, detail="Invalid odds format")
        data["sport"] = data.get("sport", "").upper()

    user_id = data["user_id"]

    # Initialize slip if needed
    if user_id not in _parlay_slips:
        _parlay_slips[user_id] = []

    # Check max legs
    if len(_parlay_slips[user_id]) >= 12:
        raise HTTPException(status_code=400, detail="Maximum 12 legs per parlay")

    # Check for duplicate game/bet_type
    for existing in _parlay_slips[user_id]:
        if existing["game_id"] == data["game_id"] and existing["bet_type"] == data["bet_type"]:
            raise HTTPException(
                status_code=400,
                detail=f"Already have a {data['bet_type']} bet for this game"
            )

    leg_id = f"LEG_{user_id}_{len(_parlay_slips[user_id])}_{datetime.now().strftime('%H%M%S')}"

    new_leg = {
        "leg_id": leg_id,
        "sport": data["sport"],
        "game_id": data["game_id"],
        "game": data.get("game", "Unknown Game"),
        "bet_type": data["bet_type"],
        "selection": data["selection"],
        "line": data.get("line"),
        "odds": data["odds"],
        "ai_score": data.get("ai_score"),
        "added_at": datetime.now().isoformat()
    }

    _parlay_slips[user_id].append(new_leg)
    combined = calculate_parlay_odds(_parlay_slips[user_id])

    return {
        "status": "added",
        "leg": new_leg,
        "parlay": {
            "legs": _parlay_slips[user_id],
            "leg_count": len(_parlay_slips[user_id]),
            "combined_odds": combined
        },
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/parlay/remove/{user_id}/{leg_id}")
async def remove_parlay_leg(user_id: str, leg_id: str):
    """
    Remove a specific leg from a user's parlay slip.
    """
    if user_id not in _parlay_slips:
        raise HTTPException(status_code=404, detail="No parlay slip found for user")

    original_len = len(_parlay_slips[user_id])
    _parlay_slips[user_id] = [leg for leg in _parlay_slips[user_id] if leg["leg_id"] != leg_id]

    if len(_parlay_slips[user_id]) == original_len:
        raise HTTPException(status_code=404, detail=f"Leg {leg_id} not found")

    combined = calculate_parlay_odds(_parlay_slips[user_id])

    return {
        "status": "removed",
        "removed_leg_id": leg_id,
        "parlay": {
            "legs": _parlay_slips[user_id],
            "leg_count": len(_parlay_slips[user_id]),
            "combined_odds": combined
        },
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/parlay/clear/{user_id}")
async def clear_parlay_slip(user_id: str):
    """
    Clear all legs from a user's parlay slip.
    """
    removed_count = len(_parlay_slips.get(user_id, []))
    _parlay_slips[user_id] = []

    return {
        "status": "cleared",
        "removed_count": removed_count,
        "parlay": {
            "legs": [],
            "leg_count": 0,
            "combined_odds": {"decimal": 1.0, "american": -10000, "implied_probability": 100.0}
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/place")
async def place_parlay(
    parlay_data: PlaceParlayRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Track a parlay bet that was placed.

    Request Body (validated with Pydantic):
    - user_id: str (default: "anonymous")
    - sportsbook: str (required)
    - stake: float (default: 0, must be >= 0)
    - use_current_slip: bool (default: true)
    - legs: array (optional, used if use_current_slip is false)

    If use_current_slip is true, uses the user's current parlay slip.
    Otherwise, provide a "legs" array directly.
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(parlay_data, 'dict'):
        data = parlay_data.dict()
    else:
        data = parlay_data if isinstance(parlay_data, dict) else dict(parlay_data)

    user_id = data.get("user_id", "anonymous")
    sportsbook = data.get("sportsbook")
    stake = data.get("stake", 0)

    if not sportsbook:
        raise HTTPException(status_code=400, detail="sportsbook is required")

    # Get legs from current slip or from request
    if data.get("use_current_slip", True):
        legs = _parlay_slips.get(user_id, [])
    else:
        legs = data.get("legs", [])

    if len(legs) < 2:
        raise HTTPException(status_code=400, detail="Parlay requires at least 2 legs")

    combined = calculate_parlay_odds(legs)

    # Calculate potential payout
    if stake > 0:
        potential_payout = round(stake * combined["decimal"], 2)
    else:
        potential_payout = 0

    parlay_id = f"PARLAY_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tracked_parlay = {
        "parlay_id": parlay_id,
        "user_id": user_id,
        "legs": legs,
        "leg_count": len(legs),
        "combined_odds": combined,
        "sportsbook": sportsbook,
        "stake": stake,
        "potential_payout": potential_payout,
        "status": "PENDING",
        "result": None,
        "placed_at": datetime.now().isoformat()
    }

    _placed_parlays.append(tracked_parlay)

    # Clear the slip after placing
    if data.get("use_current_slip", True):
        _parlay_slips[user_id] = []

    return {
        "status": "placed",
        "parlay": tracked_parlay,
        "message": f"Parlay with {len(legs)} legs tracked. Open {sportsbook} to place bet.",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/grade/{parlay_id}")
async def grade_parlay(
    parlay_id: str,
    grade_data: GradeParlayRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Grade a placed parlay with WIN, LOSS, or PUSH.

    Request Body (validated with Pydantic):
    - result: str (required, must be WIN, LOSS, or PUSH)
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(grade_data, 'result'):
        result = grade_data.result.value if hasattr(grade_data.result, 'value') else str(grade_data.result)
    else:
        result = grade_data.get("result", "").upper()
        if result not in ["WIN", "LOSS", "PUSH"]:
            raise HTTPException(status_code=400, detail="Result must be WIN, LOSS, or PUSH")

    for parlay in _placed_parlays:
        if parlay["parlay_id"] == parlay_id:
            parlay["status"] = "GRADED"
            parlay["result"] = result
            parlay["graded_at"] = datetime.now().isoformat()

            # Calculate profit/loss
            if result == "WIN":
                parlay["profit"] = parlay["potential_payout"] - parlay["stake"]
            elif result == "LOSS":
                parlay["profit"] = -parlay["stake"]
            else:  # PUSH
                parlay["profit"] = 0

            return {
                "status": "graded",
                "parlay": parlay,
                "timestamp": datetime.now().isoformat()
            }

    raise HTTPException(status_code=404, detail=f"Parlay {parlay_id} not found")


@router.get("/parlay/history")
async def get_parlay_history(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    auth: bool = Depends(verify_api_key)
):
    """
    Get parlay history with stats.

    Supports filtering by:
    - user_id: Filter by user
    - status: Filter by status (PENDING, GRADED)
    - limit: Max 500 results (default 50)
    """
    # Validate and cap limit to prevent DoS
    limit = min(max(1, limit), 500)
    filtered = _placed_parlays.copy()

    if user_id:
        filtered = [p for p in filtered if p.get("user_id") == user_id]
    if status:
        filtered = [p for p in filtered if p.get("status") == status.upper()]

    # Sort by placed_at descending
    filtered.sort(key=lambda x: x.get("placed_at", ""), reverse=True)

    # Calculate stats
    graded = [p for p in filtered if p.get("status") == "GRADED"]
    wins = len([p for p in graded if p.get("result") == "WIN"])
    losses = len([p for p in graded if p.get("result") == "LOSS"])
    pushes = len([p for p in graded if p.get("result") == "PUSH"])
    total_profit = sum(p.get("profit", 0) for p in graded)
    total_staked = sum(p.get("stake", 0) for p in graded)

    return {
        "parlays": filtered[:limit],
        "count": len(filtered[:limit]),
        "total_tracked": len(filtered),
        "stats": {
            "graded": len(graded),
            "pending": len(filtered) - len(graded),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / len(graded) * 100, 1) if graded else 0,
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / total_staked * 100, 1) if total_staked > 0 else 0
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/calculate")
async def calculate_parlay(calc_data: Dict[str, Any]):
    """
    Calculate parlay odds and payout without saving.

    Request Body:
    {
        "legs": [
            {"odds": -110},
            {"odds": +150},
            {"odds": -105}
        ],
        "stake": 25
    }

    Useful for preview/what-if calculations.
    """
    legs = calc_data.get("legs", [])
    stake = calc_data.get("stake", 0)

    if not legs:
        raise HTTPException(status_code=400, detail="At least one leg required")

    combined = calculate_parlay_odds(legs)

    if stake > 0:
        potential_payout = round(stake * combined["decimal"], 2)
        profit = round(potential_payout - stake, 2)
    else:
        potential_payout = 0
        profit = 0

    return {
        "leg_count": len(legs),
        "combined_odds": combined,
        "stake": stake,
        "potential_payout": potential_payout,
        "profit_if_win": profit,
        "example_payouts": {
            "$10": round(10 * combined["decimal"], 2),
            "$25": round(25 * combined["decimal"], 2),
            "$50": round(50 * combined["decimal"], 2),
            "$100": round(100 * combined["decimal"], 2)
        },
        "timestamp": datetime.now().isoformat()
    }


__all__ = [
    'router',
    'CORRELATION_MATRIX',
    'VOID_IMPACT_MULTIPLIERS',
]
