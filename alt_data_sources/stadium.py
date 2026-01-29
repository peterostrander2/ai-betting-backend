"""
STADIUM/VENUE MODULE - Venue characteristics and impact

FEATURE FLAG: Stadium altitude, surface, environment analysis

REQUIREMENTS:
- Must provide venue altitude, surface type, roof status
- Must return deterministic "data missing" reason when unavailable
- NEVER breaks scoring pipeline

DATA SOURCE:
- Venue database (when implemented)
- For now: Stub with explicit "not implemented" status + known venue data
"""

from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger("stadium")

# Feature flag
STADIUM_ENABLED = os.getenv("STADIUM_ENABLED", "false").lower() == "true"

# Default values
DEFAULT_ALTITUDE = 0  # Sea level
DEFAULT_SURFACE = "UNKNOWN"
DEFAULT_ROOF = "UNKNOWN"


def get_stadium_info(
    sport: str,
    team: str,
    venue_name: str = ""
) -> Dict[str, Any]:
    """
    Get stadium characteristics.

    Args:
        sport: Sport code
        team: Team name
        venue_name: Venue name (optional)

    Returns:
        Stadium data dict with status
    """
    if not STADIUM_ENABLED:
        # Check known high-altitude venues even when disabled
        altitude = lookup_altitude(team, venue_name)
        return {
            "available": False if altitude == DEFAULT_ALTITUDE else True,
            "reason": "FEATURE_DISABLED" if altitude == DEFAULT_ALTITUDE else "KNOWN_VENUE",
            "message": "Stadium analysis feature is disabled" if altitude == DEFAULT_ALTITUDE else "Using known venue data",
            "altitude": altitude,
            "surface": DEFAULT_SURFACE,
            "roof": DEFAULT_ROOF,
            "venue_name": venue_name or "Unknown"
        }

    # Lookup known venue data
    venue_data = lookup_venue_characteristics(sport, team, venue_name)

    if venue_data["altitude"] == DEFAULT_ALTITUDE and not venue_data["known"]:
        return {
            "available": False,
            "reason": "NOT_IMPLEMENTED",
            "message": "Stadium API integration pending implementation",
            "altitude": DEFAULT_ALTITUDE,
            "surface": DEFAULT_SURFACE,
            "roof": DEFAULT_ROOF,
            "venue_name": venue_name or "Unknown"
        }

    return {
        "available": True,
        "reason": "KNOWN_VENUE",
        "message": "Using known venue data",
        "altitude": venue_data["altitude"],
        "surface": venue_data["surface"],
        "roof": venue_data["roof"],
        "venue_name": venue_data["name"]
    }


def calculate_altitude_impact(
    sport: str,
    altitude: int
) -> Dict[str, Any]:
    """
    Calculate altitude impact on game.

    Args:
        sport: Sport code
        altitude: Venue altitude in feet

    Returns:
        Impact assessment dict
    """
    impact = {
        "overall_impact": "NONE",
        "scoring_impact": 0.0,
        "distance_impact": 0.0,
        "fatigue_impact": 0.0,
        "reasons": []
    }

    if altitude < 1000:
        # Low altitude - no significant impact
        return impact

    # High altitude effects (Denver, Mexico City, etc.)
    if altitude >= 5000:
        impact["overall_impact"] = "HIGH"
        impact["scoring_impact"] = 0.5
        impact["distance_impact"] = 0.3
        impact["fatigue_impact"] = -0.2
        impact["reasons"].append(f"High altitude ({altitude} ft) - ball travels farther, thinner air")

        if sport.upper() == "MLB":
            impact["scoring_impact"] = 0.8
            impact["reasons"].append("MLB: Balls carry significantly more at altitude")
        elif sport.upper() == "NFL":
            impact["scoring_impact"] = 0.3
            impact["reasons"].append("NFL: Kicking distance increased, visitors may fatigue")

    elif altitude >= 3000:
        impact["overall_impact"] = "MEDIUM"
        impact["scoring_impact"] = 0.2
        impact["distance_impact"] = 0.1
        impact["reasons"].append(f"Moderate altitude ({altitude} ft) - slight scoring boost")

    return impact


def lookup_altitude(team: str, venue_name: str = "") -> int:
    """
    Lookup venue altitude from known database.

    Args:
        team: Team name
        venue_name: Venue name (optional)

    Returns:
        Altitude in feet
    """
    team_lower = team.lower()
    venue_lower = venue_name.lower()

    # Known high-altitude venues
    if "denver" in team_lower or "rockies" in team_lower or "nuggets" in team_lower or "broncos" in team_lower:
        return 5280  # Denver - Mile High

    if "mexico" in venue_lower or "estadio azteca" in venue_lower:
        return 7380  # Mexico City

    if "salt lake" in team_lower or "jazz" in team_lower:
        return 4226  # Salt Lake City

    if "phoenix" in team_lower or "suns" in team_lower or "cardinals" in team_lower or "diamondbacks" in team_lower:
        return 1086  # Phoenix

    # Default to sea level
    return DEFAULT_ALTITUDE


def lookup_venue_characteristics(
    sport: str,
    team: str,
    venue_name: str = ""
) -> Dict[str, Any]:
    """
    Lookup full venue characteristics.

    Args:
        sport: Sport code
        team: Team name
        venue_name: Venue name

    Returns:
        Venue characteristics dict
    """
    team_lower = team.lower()
    venue_lower = venue_name.lower()

    # Denver venues
    if "denver" in team_lower or "coors field" in venue_lower:
        return {
            "known": True,
            "name": "Coors Field" if sport.upper() == "MLB" else "Mile High",
            "altitude": 5280,
            "surface": "GRASS" if sport.upper() in ["MLB", "NFL"] else "HARDWOOD",
            "roof": "OPEN"
        }

    # Dome stadiums (NFL)
    domes = {
        "cowboys": {"name": "AT&T Stadium", "altitude": 600, "surface": "TURF", "roof": "RETRACTABLE"},
        "saints": {"name": "Superdome", "altitude": 0, "surface": "TURF", "roof": "DOME"},
        "rams": {"name": "SoFi Stadium", "altitude": 100, "surface": "TURF", "roof": "DOME"},
        "colts": {"name": "Lucas Oil Stadium", "altitude": 715, "surface": "TURF", "roof": "RETRACTABLE"},
        "vikings": {"name": "U.S. Bank Stadium", "altitude": 815, "surface": "TURF", "roof": "DOME"},
        "raiders": {"name": "Allegiant Stadium", "altitude": 2001, "surface": "GRASS", "roof": "DOME"},
        "cardinals": {"name": "State Farm Stadium", "altitude": 1086, "surface": "GRASS", "roof": "RETRACTABLE"}
    }

    for team_key, venue_info in domes.items():
        if team_key in team_lower:
            return {
                "known": True,
                **venue_info
            }

    # Default
    return {
        "known": False,
        "name": venue_name or "Unknown",
        "altitude": DEFAULT_ALTITUDE,
        "surface": DEFAULT_SURFACE,
        "roof": DEFAULT_ROOF
    }


def calculate_surface_impact(
    sport: str,
    surface: str
) -> Dict[str, Any]:
    """
    Calculate playing surface impact.

    Args:
        sport: Sport code
        surface: Surface type (GRASS, TURF, etc.)

    Returns:
        Impact assessment dict
    """
    impact = {
        "overall_impact": "NONE",
        "injury_risk": 0.0,
        "speed_impact": 0.0,
        "reasons": []
    }

    if sport.upper() not in ["NFL", "MLB"]:
        return impact

    if surface.upper() == "TURF":
        impact["overall_impact"] = "LOW"
        impact["injury_risk"] = 0.1
        impact["speed_impact"] = 0.05
        impact["reasons"].append("Turf surface - slightly faster play, higher injury risk")
    elif surface.upper() == "GRASS":
        impact["reasons"].append("Natural grass surface - standard play conditions")

    return impact


def calculate_roof_impact(
    sport: str,
    roof: str,
    weather_conditions: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Calculate roof status impact.

    Args:
        sport: Sport code
        roof: Roof type (OPEN, DOME, RETRACTABLE)
        weather_conditions: Weather data (optional)

    Returns:
        Impact assessment dict
    """
    impact = {
        "overall_impact": "NONE",
        "reasons": []
    }

    if roof.upper() == "DOME":
        impact["reasons"].append("Dome stadium - weather neutral, controlled environment")
    elif roof.upper() == "RETRACTABLE":
        if weather_conditions and weather_conditions.get("available"):
            # Could be open or closed depending on weather
            impact["reasons"].append("Retractable roof - status depends on weather")
        else:
            impact["reasons"].append("Retractable roof - status unknown")
    elif roof.upper() == "OPEN":
        impact["reasons"].append("Open stadium - weather conditions apply")

    return impact
