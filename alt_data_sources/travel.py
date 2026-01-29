"""
TRAVEL/FATIGUE MODULE - Team travel distance and rest analysis

FEATURE FLAG: Travel fatigue and schedule analysis

REQUIREMENTS:
- Must provide travel distance, rest days, timezone changes
- Must return deterministic "data missing" reason when unavailable
- NEVER breaks scoring pipeline

DATA SOURCE:
- Schedule API + team locations (when implemented)
- For now: Stub with explicit "not implemented" status + known distances
"""

from typing import Dict, Any, Optional, Tuple
import logging
import os
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger("travel")

# Feature flag
TRAVEL_ENABLED = os.getenv("TRAVEL_ENABLED", "false").lower() == "true"

# Default values
DEFAULT_DISTANCE = 0  # No travel assumed
DEFAULT_REST_DAYS = 1  # Normal rest


def get_travel_impact(
    sport: str,
    away_team: str,
    home_team: str,
    game_date: str = "",
    last_game_date: str = ""
) -> Dict[str, Any]:
    """
    Get travel impact for away team.

    Args:
        sport: Sport code
        away_team: Away team name
        home_team: Home team name
        game_date: Current game date
        last_game_date: Away team's last game date

    Returns:
        Travel impact dict with status
    """
    if not TRAVEL_ENABLED:
        return {
            "available": False,
            "reason": "FEATURE_DISABLED",
            "message": "Travel analysis feature is disabled",
            "distance_miles": DEFAULT_DISTANCE,
            "rest_days": DEFAULT_REST_DAYS,
            "timezone_change": 0
        }

    # Calculate travel distance using city coordinates
    distance = calculate_distance(away_team, home_team)

    if distance == 0:
        return {
            "available": False,
            "reason": "CITY_DATA_MISSING",
            "message": "City coordinates not available for distance calculation",
            "distance_miles": DEFAULT_DISTANCE,
            "rest_days": DEFAULT_REST_DAYS,
            "timezone_change": 0
        }

    # Calculate timezone change
    tz_change = calculate_timezone_change(away_team, home_team)

    return {
        "available": True,
        "reason": "ESTIMATED",
        "message": "Using estimated distance based on team cities",
        "distance_miles": distance,
        "rest_days": DEFAULT_REST_DAYS,  # Would need schedule API
        "timezone_change": tz_change
    }


def calculate_fatigue_impact(
    sport: str,
    distance_miles: int,
    rest_days: int,
    timezone_change: int
) -> Dict[str, Any]:
    """
    Calculate fatigue impact on away team.

    Args:
        sport: Sport code
        distance_miles: Travel distance
        rest_days: Days since last game
        timezone_change: Hours of timezone change (negative = west to east)

    Returns:
        Impact assessment dict
    """
    impact = {
        "overall_impact": "NONE",
        "away_team_fatigue": 0.0,
        "home_advantage_boost": 0.0,
        "reasons": []
    }

    # Long distance travel
    if distance_miles > 2000:
        impact["overall_impact"] = "MEDIUM"
        impact["away_team_fatigue"] = -0.2
        impact["home_advantage_boost"] = 0.1
        impact["reasons"].append(f"Long distance travel ({distance_miles} miles)")

    # Back-to-back games
    if rest_days == 0:
        impact["overall_impact"] = "HIGH"
        impact["away_team_fatigue"] = -0.4
        impact["home_advantage_boost"] = 0.2
        impact["reasons"].append("Back-to-back games - fatigue factor")

    # Timezone change (especially west to east)
    if abs(timezone_change) >= 3:
        impact["overall_impact"] = "MEDIUM" if impact["overall_impact"] == "NONE" else "HIGH"
        if timezone_change < 0:  # West to east
            impact["away_team_fatigue"] = impact["away_team_fatigue"] - 0.3
            impact["reasons"].append(f"Major timezone change (west to east, {abs(timezone_change)} hours)")
        else:  # East to west
            impact["away_team_fatigue"] = impact["away_team_fatigue"] - 0.1
            impact["reasons"].append(f"Timezone change (east to west, {timezone_change} hours)")

    # Good rest negates some travel
    if rest_days >= 2 and distance_miles > 0:
        impact["away_team_fatigue"] = impact["away_team_fatigue"] * 0.7
        impact["reasons"].append(f"Good rest ({rest_days} days) mitigates travel fatigue")

    return impact


def calculate_distance(team1: str, team2: str) -> int:
    """
    Calculate distance between two teams in miles.

    Args:
        team1: First team name
        team2: Second team name

    Returns:
        Distance in miles
    """
    # Get coordinates for both teams
    coords1 = get_team_coordinates(team1)
    coords2 = get_team_coordinates(team2)

    if not coords1 or not coords2:
        return 0

    # Haversine formula
    lat1, lon1 = coords1
    lat2, lon2 = coords2

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # Radius of earth in miles
    r = 3959

    return int(c * r)


def get_team_coordinates(team: str) -> Optional[Tuple[float, float]]:
    """
    Get team city coordinates.

    Args:
        team: Team name

    Returns:
        (latitude, longitude) tuple or None
    """
    team_lower = team.lower()

    # Major city coordinates (lat, lon)
    CITY_COORDS = {
        "atlanta": (33.7490, -84.3880),
        "boston": (42.3601, -71.0589),
        "brooklyn": (40.6782, -73.9442),
        "charlotte": (35.2271, -80.8431),
        "chicago": (41.8781, -87.6298),
        "cleveland": (41.4993, -81.6944),
        "dallas": (32.7767, -96.7970),
        "denver": (39.7392, -104.9903),
        "detroit": (42.3314, -83.0458),
        "golden state": (37.7749, -122.4194),  # San Francisco
        "houston": (29.7604, -95.3698),
        "indiana": (39.7684, -86.1581),  # Indianapolis
        "los angeles": (34.0522, -118.2437),
        "memphis": (35.1495, -90.0490),
        "miami": (25.7617, -80.1918),
        "milwaukee": (43.0389, -87.9065),
        "minnesota": (44.9778, -93.2650),  # Minneapolis
        "new orleans": (29.9511, -90.0715),
        "new york": (40.7128, -74.0060),
        "oklahoma city": (35.4676, -97.5164),
        "orlando": (28.5383, -81.3792),
        "philadelphia": (39.9526, -75.1652),
        "phoenix": (33.4484, -112.0740),
        "portland": (45.5152, -122.6784),
        "sacramento": (38.5816, -121.4944),
        "san antonio": (29.4241, -98.4936),
        "toronto": (43.6532, -79.3832),
        "utah": (40.7608, -111.8910),  # Salt Lake City
        "washington": (38.9072, -77.0369),
        # NFL cities
        "arizona": (33.4484, -112.0740),  # Phoenix
        "baltimore": (39.2904, -76.6122),
        "buffalo": (42.8864, -78.8784),
        "carolina": (35.2271, -80.8431),  # Charlotte
        "cincinnati": (39.1031, -84.5120),
        "green bay": (44.5133, -88.0133),
        "indianapolis": (39.7684, -86.1581),
        "jacksonville": (30.3322, -81.6557),
        "kansas city": (39.0997, -94.5786),
        "las vegas": (36.1699, -115.1398),
        "pittsburgh": (40.4406, -79.9959),
        "san francisco": (37.7749, -122.4194),
        "seattle": (47.6062, -122.3321),
        "tampa": (27.9506, -82.4572),
        "tennessee": (36.1627, -86.7816),  # Nashville
    }

    for city, coords in CITY_COORDS.items():
        if city in team_lower:
            return coords

    return None


def calculate_timezone_change(team1: str, team2: str) -> int:
    """
    Calculate timezone change between two teams.

    Args:
        team1: First team name
        team2: Second team name

    Returns:
        Hours of timezone change (negative = west to east)
    """
    tz1 = get_team_timezone(team1)
    tz2 = get_team_timezone(team2)

    if not tz1 or not tz2:
        return 0

    # Calculate difference (negative = traveling east)
    return tz2 - tz1


def get_team_timezone(team: str) -> Optional[int]:
    """
    Get team timezone offset from ET.

    Args:
        team: Team name

    Returns:
        Hours offset from ET (0 = ET, -1 = CT, -2 = MT, -3 = PT)
    """
    team_lower = team.lower()

    # Eastern Time (ET) teams
    et_teams = ["atlanta", "boston", "brooklyn", "charlotte", "cleveland", "detroit", "indiana", "miami",
                "new york", "orlando", "philadelphia", "toronto", "washington", "baltimore", "buffalo",
                "carolina", "jacksonville", "pittsburgh", "tampa", "tennessee"]

    # Central Time (CT) teams
    ct_teams = ["chicago", "dallas", "houston", "memphis", "milwaukee", "minnesota", "new orleans",
                "san antonio", "green bay", "indianapolis", "kansas city"]

    # Mountain Time (MT) teams
    mt_teams = ["denver", "utah", "arizona"]

    # Pacific Time (PT) teams
    pt_teams = ["golden state", "los angeles", "portland", "phoenix", "sacramento",
                "las vegas", "san francisco", "seattle"]

    for team_name in et_teams:
        if team_name in team_lower:
            return 0

    for team_name in ct_teams:
        if team_name in team_lower:
            return -1

    for team_name in mt_teams:
        if team_name in team_lower:
            return -2

    for team_name in pt_teams:
        if team_name in team_lower:
            return -3

    return None
