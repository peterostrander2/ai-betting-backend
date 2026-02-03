"""
Travel & Fatigue Module
=======================

Calculates travel distance and fatigue impact for away teams.

v17.9: Now wired to ESPN rest_days data via context_layer.py
"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# TEAM LOCATION DATA
# =============================================================================

# Approximate city coordinates (latitude, longitude)
TEAM_LOCATIONS = {
    # NBA
    "atlanta hawks": (33.7490, -84.3880),
    "boston celtics": (42.3601, -71.0589),
    "brooklyn nets": (40.6829, -73.9752),
    "charlotte hornets": (35.2271, -80.8431),
    "chicago bulls": (41.8781, -87.6298),
    "cleveland cavaliers": (41.4993, -81.6944),
    "dallas mavericks": (32.7767, -96.7970),
    "denver nuggets": (39.7392, -104.9903),
    "detroit pistons": (42.3314, -83.0458),
    "golden state warriors": (37.7749, -122.4194),
    "houston rockets": (29.7604, -95.3698),
    "indiana pacers": (39.7684, -86.1581),
    "la clippers": (34.0522, -118.2437),
    "los angeles lakers": (34.0522, -118.2437),
    "memphis grizzlies": (35.1495, -90.0490),
    "miami heat": (25.7617, -80.1918),
    "milwaukee bucks": (43.0389, -87.9065),
    "minnesota timberwolves": (44.9778, -93.2650),
    "new orleans pelicans": (29.9511, -90.0715),
    "new york knicks": (40.7128, -74.0060),
    "oklahoma city thunder": (35.4676, -97.5164),
    "orlando magic": (28.5383, -81.3792),
    "philadelphia 76ers": (39.9526, -75.1652),
    "phoenix suns": (33.4484, -112.0740),
    "portland trail blazers": (45.5152, -122.6784),
    "sacramento kings": (38.5816, -121.4944),
    "san antonio spurs": (29.4241, -98.4936),
    "toronto raptors": (43.6532, -79.3832),
    "utah jazz": (40.7608, -111.8910),
    "washington wizards": (38.9072, -77.0369),

    # NHL
    "anaheim ducks": (33.8076, -117.8764),
    "arizona coyotes": (33.4484, -112.0740),
    "boston bruins": (42.3601, -71.0589),
    "buffalo sabres": (42.8864, -78.8784),
    "calgary flames": (51.0447, -114.0719),
    "carolina hurricanes": (35.7796, -78.6382),
    "chicago blackhawks": (41.8781, -87.6298),
    "colorado avalanche": (39.7392, -104.9903),
    "columbus blue jackets": (39.9612, -82.9988),
    "dallas stars": (32.7767, -96.7970),
    "detroit red wings": (42.3314, -83.0458),
    "edmonton oilers": (53.5461, -113.4938),
    "florida panthers": (26.1224, -80.1373),
    "los angeles kings": (34.0522, -118.2437),
    "minnesota wild": (44.9778, -93.2650),
    "montreal canadiens": (45.5017, -73.5673),
    "nashville predators": (36.1627, -86.7816),
    "new jersey devils": (40.7357, -74.1724),
    "new york islanders": (40.7128, -74.0060),
    "new york rangers": (40.7128, -74.0060),
    "ottawa senators": (45.4215, -75.6972),
    "philadelphia flyers": (39.9526, -75.1652),
    "pittsburgh penguins": (40.4406, -79.9959),
    "san jose sharks": (37.3382, -121.8863),
    "seattle kraken": (47.6062, -122.3321),
    "st. louis blues": (38.6270, -90.1994),
    "tampa bay lightning": (27.9506, -82.4572),
    "toronto maple leafs": (43.6532, -79.3832),
    "vancouver canucks": (49.2827, -123.1207),
    "vegas golden knights": (36.1699, -115.1398),
    "washington capitals": (38.9072, -77.0369),
    "winnipeg jets": (49.8951, -97.1384),

    # NFL (select teams)
    "arizona cardinals": (33.4484, -112.0740),
    "atlanta falcons": (33.7490, -84.3880),
    "baltimore ravens": (39.2904, -76.6122),
    "buffalo bills": (42.8864, -78.8784),
    "carolina panthers": (35.2271, -80.8431),
    "chicago bears": (41.8781, -87.6298),
    "cincinnati bengals": (39.1031, -84.5120),
    "cleveland browns": (41.4993, -81.6944),
    "dallas cowboys": (32.7767, -96.7970),
    "denver broncos": (39.7392, -104.9903),
    "detroit lions": (42.3314, -83.0458),
    "green bay packers": (44.5013, -88.0622),
    "houston texans": (29.7604, -95.3698),
    "indianapolis colts": (39.7684, -86.1581),
    "jacksonville jaguars": (30.3322, -81.6557),
    "kansas city chiefs": (39.0997, -94.5786),
    "las vegas raiders": (36.1699, -115.1398),
    "los angeles chargers": (34.0522, -118.2437),
    "los angeles rams": (34.0522, -118.2437),
    "miami dolphins": (25.7617, -80.1918),
    "minnesota vikings": (44.9778, -93.2650),
    "new england patriots": (42.0909, -71.2643),
    "new orleans saints": (29.9511, -90.0715),
    "new york giants": (40.8136, -74.0743),
    "new york jets": (40.8136, -74.0743),
    "philadelphia eagles": (39.9526, -75.1652),
    "pittsburgh steelers": (40.4406, -79.9959),
    "san francisco 49ers": (37.7749, -122.4194),
    "seattle seahawks": (47.6062, -122.3321),
    "tampa bay buccaneers": (27.9506, -82.4572),
    "tennessee titans": (36.1627, -86.7816),
    "washington commanders": (38.9072, -77.0369),

    # MLB (select teams)
    "arizona diamondbacks": (33.4484, -112.0740),
    "atlanta braves": (33.7490, -84.3880),
    "baltimore orioles": (39.2904, -76.6122),
    "boston red sox": (42.3601, -71.0589),
    "chicago cubs": (41.8781, -87.6298),
    "chicago white sox": (41.8781, -87.6298),
    "cincinnati reds": (39.1031, -84.5120),
    "cleveland guardians": (41.4993, -81.6944),
    "colorado rockies": (39.7392, -104.9903),
    "detroit tigers": (42.3314, -83.0458),
    "houston astros": (29.7604, -95.3698),
    "kansas city royals": (39.0997, -94.5786),
    "los angeles angels": (33.8003, -117.8827),
    "los angeles dodgers": (34.0739, -118.2400),
    "miami marlins": (25.7617, -80.1918),
    "milwaukee brewers": (43.0289, -87.9712),
    "minnesota twins": (44.9778, -93.2650),
    "new york mets": (40.7571, -73.8458),
    "new york yankees": (40.8296, -73.9262),
    "oakland athletics": (37.7516, -122.2005),
    "philadelphia phillies": (39.9061, -75.1665),
    "pittsburgh pirates": (40.4469, -80.0058),
    "san diego padres": (32.7157, -117.1611),
    "san francisco giants": (37.7786, -122.3893),
    "seattle mariners": (47.5914, -122.3325),
    "st. louis cardinals": (38.6226, -90.1928),
    "tampa bay rays": (27.7683, -82.6534),
    "texas rangers": (32.7512, -97.0832),
    "toronto blue jays": (43.6414, -79.3894),
    "washington nationals": (38.8730, -77.0074),
}


# =============================================================================
# DISTANCE CALCULATION
# =============================================================================

def calculate_distance(away_team: str, home_team: str) -> int:
    """
    Calculate approximate distance in miles between two teams.

    Uses Haversine formula for great-circle distance.

    Args:
        away_team: Away team name
        home_team: Home team name

    Returns:
        Distance in miles (0 if teams not found)
    """
    import math

    away_lower = away_team.lower().strip() if away_team else ""
    home_lower = home_team.lower().strip() if home_team else ""

    # Find matching team locations
    away_coords = None
    home_coords = None

    for team_name, coords in TEAM_LOCATIONS.items():
        if team_name in away_lower or away_lower in team_name:
            away_coords = coords
        if team_name in home_lower or home_lower in team_name:
            home_coords = coords

    if not away_coords or not home_coords:
        logger.debug("Could not find coordinates for %s vs %s", away_team, home_team)
        return 0

    # Haversine formula
    lat1, lon1 = math.radians(away_coords[0]), math.radians(away_coords[1])
    lat2, lon2 = math.radians(home_coords[0]), math.radians(home_coords[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Earth's radius in miles
    r = 3956

    distance = int(r * c)
    logger.debug("Distance %s -> %s: %d miles", away_team, home_team, distance)

    return distance


# =============================================================================
# FATIGUE IMPACT CALCULATION
# =============================================================================

def calculate_fatigue_impact(
    sport: str,
    distance_miles: int,
    rest_days_away: int,
    rest_days_home: int = 0
) -> Dict:
    """
    Calculate fatigue impact based on travel and rest.

    Args:
        sport: Sport code (NBA, NHL, NFL, MLB)
        distance_miles: Distance traveled by away team
        rest_days_away: Days since away team's last game
        rest_days_home: Days since home team's last game

    Returns:
        Dict with fatigue analysis:
        - away_team_fatigue: float (-1.0 to 0.0, negative = fatigued)
        - overall_impact: "HIGH", "MEDIUM", "LOW", "NONE"
        - reasons: List of explanation strings
    """
    result = {
        "away_team_fatigue": 0.0,
        "overall_impact": "NONE",
        "reasons": []
    }

    sport_upper = sport.upper() if sport else ""

    # B2B detection (most impactful)
    if rest_days_away == 0:
        result["away_team_fatigue"] = -0.5
        result["overall_impact"] = "HIGH"
        result["reasons"].append("Back-to-back game")

        # B2B with travel is even worse
        if distance_miles > 1000:
            result["away_team_fatigue"] = -0.6
            result["reasons"].append(f"B2B with {distance_miles}mi travel")

        return result

    # Short rest scenarios
    if rest_days_away == 1:
        if distance_miles > 2000:
            result["away_team_fatigue"] = -0.4
            result["overall_impact"] = "HIGH"
            result["reasons"].append(f"1-day rest with {distance_miles}mi travel")
        elif distance_miles > 1500:
            result["away_team_fatigue"] = -0.35
            result["overall_impact"] = "HIGH"
            result["reasons"].append(f"1-day rest with {distance_miles}mi travel")
        elif distance_miles > 1000:
            result["away_team_fatigue"] = -0.25
            result["overall_impact"] = "MEDIUM"
            result["reasons"].append(f"1-day rest with {distance_miles}mi travel")
        elif distance_miles > 500:
            result["away_team_fatigue"] = -0.15
            result["overall_impact"] = "LOW"
            result["reasons"].append(f"1-day rest with {distance_miles}mi travel")

        return result

    # 2-day rest with long travel
    if rest_days_away == 2:
        if distance_miles > 2000:
            result["away_team_fatigue"] = -0.2
            result["overall_impact"] = "MEDIUM"
            result["reasons"].append(f"Cross-country travel ({distance_miles}mi)")
        elif distance_miles > 1500:
            result["away_team_fatigue"] = -0.15
            result["overall_impact"] = "LOW"
            result["reasons"].append(f"Long travel ({distance_miles}mi)")

        return result

    # Long rest but extreme travel
    if distance_miles > 2500:
        result["away_team_fatigue"] = -0.1
        result["overall_impact"] = "LOW"
        result["reasons"].append(f"Extreme distance ({distance_miles}mi)")

    return result


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "calculate_distance",
    "calculate_fatigue_impact",
    "TEAM_LOCATIONS",
]


# =============================================================================
# TEST CODE
# =============================================================================

if __name__ == "__main__":
    # Test distance calculation
    print("Testing distance calculations:")
    print(f"  Lakers -> Celtics: {calculate_distance('Los Angeles Lakers', 'Boston Celtics')} miles")
    print(f"  Heat -> Magic: {calculate_distance('Miami Heat', 'Orlando Magic')} miles")
    print(f"  Nuggets -> Jazz: {calculate_distance('Denver Nuggets', 'Utah Jazz')} miles")

    print("\nTesting fatigue impact:")
    # B2B test
    result = calculate_fatigue_impact("NBA", 2500, 0, 2)
    print(f"  B2B + 2500mi: {result}")

    # Short rest test
    result = calculate_fatigue_impact("NBA", 1800, 1, 2)
    print(f"  1-day rest + 1800mi: {result}")

    # Normal test
    result = calculate_fatigue_impact("NBA", 500, 2, 2)
    print(f"  2-day rest + 500mi: {result}")
