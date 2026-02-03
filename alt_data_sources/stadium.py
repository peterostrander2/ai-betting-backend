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

from typing import Dict, Any, Optional, Tuple, List
import logging
import os

logger = logging.getLogger("stadium")

# Feature flag
STADIUM_ENABLED = os.getenv("STADIUM_ENABLED", "false").lower() == "true"

# Default values
DEFAULT_ALTITUDE = 0  # Sea level
DEFAULT_SURFACE = "UNKNOWN"
DEFAULT_ROOF = "UNKNOWN"

# ============================================================================
# VENUE REGISTRY - Single Source of Truth for all stadium/venue data
# ============================================================================
# Format: team_key -> {stadium_id, name, lat, lon, is_outdoor, league, altitude_ft, roof_type, surface}

VENUE_REGISTRY: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # NFL VENUES (32 teams)
    # -------------------------------------------------------------------------
    # AFC East
    "nfl_buffalo_bills": {
        "stadium_id": "nfl_buf", "name": "Highmark Stadium",
        "lat": 42.7738, "lon": -78.7870, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 600, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_miami_dolphins": {
        "stadium_id": "nfl_mia", "name": "Hard Rock Stadium",
        "lat": 25.9580, "lon": -80.2389, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 5, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_new_england_patriots": {
        "stadium_id": "nfl_ne", "name": "Gillette Stadium",
        "lat": 42.0909, "lon": -71.2643, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 200, "roof_type": "OPEN", "surface": "TURF"
    },
    "nfl_new_york_jets": {
        "stadium_id": "nfl_nyj", "name": "MetLife Stadium",
        "lat": 40.8128, "lon": -74.0742, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 10, "roof_type": "OPEN", "surface": "TURF"
    },
    # AFC North
    "nfl_baltimore_ravens": {
        "stadium_id": "nfl_bal", "name": "M&T Bank Stadium",
        "lat": 39.2780, "lon": -76.6227, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 30, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_cincinnati_bengals": {
        "stadium_id": "nfl_cin", "name": "Paycor Stadium",
        "lat": 39.0955, "lon": -84.5161, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 480, "roof_type": "OPEN", "surface": "TURF"
    },
    "nfl_cleveland_browns": {
        "stadium_id": "nfl_cle", "name": "Cleveland Browns Stadium",
        "lat": 41.5061, "lon": -81.6995, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 580, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_pittsburgh_steelers": {
        "stadium_id": "nfl_pit", "name": "Acrisure Stadium",
        "lat": 40.4468, "lon": -80.0158, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 730, "roof_type": "OPEN", "surface": "GRASS"
    },
    # AFC South
    "nfl_houston_texans": {
        "stadium_id": "nfl_hou", "name": "NRG Stadium",
        "lat": 29.6847, "lon": -95.4107, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 50, "roof_type": "RETRACTABLE", "surface": "TURF"
    },
    "nfl_indianapolis_colts": {
        "stadium_id": "nfl_ind", "name": "Lucas Oil Stadium",
        "lat": 39.7601, "lon": -86.1639, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 715, "roof_type": "RETRACTABLE", "surface": "TURF"
    },
    "nfl_jacksonville_jaguars": {
        "stadium_id": "nfl_jax", "name": "EverBank Stadium",
        "lat": 30.3239, "lon": -81.6373, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 10, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_tennessee_titans": {
        "stadium_id": "nfl_ten", "name": "Nissan Stadium",
        "lat": 36.1665, "lon": -86.7713, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 400, "roof_type": "OPEN", "surface": "TURF"
    },
    # AFC West
    "nfl_denver_broncos": {
        "stadium_id": "nfl_den", "name": "Empower Field at Mile High",
        "lat": 39.7439, "lon": -105.0201, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 5280, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_kansas_city_chiefs": {
        "stadium_id": "nfl_kc", "name": "GEHA Field at Arrowhead Stadium",
        "lat": 39.0489, "lon": -94.4839, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 800, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_las_vegas_raiders": {
        "stadium_id": "nfl_lv", "name": "Allegiant Stadium",
        "lat": 36.0909, "lon": -115.1833, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 2001, "roof_type": "DOME", "surface": "GRASS"
    },
    "nfl_los_angeles_chargers": {
        "stadium_id": "nfl_lac", "name": "SoFi Stadium",
        "lat": 33.9534, "lon": -118.3392, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 100, "roof_type": "DOME", "surface": "TURF"
    },
    # NFC East
    "nfl_dallas_cowboys": {
        "stadium_id": "nfl_dal", "name": "AT&T Stadium",
        "lat": 32.7473, "lon": -97.0945, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 600, "roof_type": "RETRACTABLE", "surface": "TURF"
    },
    "nfl_new_york_giants": {
        "stadium_id": "nfl_nyg", "name": "MetLife Stadium",
        "lat": 40.8128, "lon": -74.0742, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 10, "roof_type": "OPEN", "surface": "TURF"
    },
    "nfl_philadelphia_eagles": {
        "stadium_id": "nfl_phi", "name": "Lincoln Financial Field",
        "lat": 39.9008, "lon": -75.1675, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 40, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_washington_commanders": {
        "stadium_id": "nfl_was", "name": "Northwest Stadium",
        "lat": 38.9076, "lon": -76.8645, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 50, "roof_type": "OPEN", "surface": "GRASS"
    },
    # NFC North
    "nfl_chicago_bears": {
        "stadium_id": "nfl_chi", "name": "Soldier Field",
        "lat": 41.8623, "lon": -87.6167, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 590, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_detroit_lions": {
        "stadium_id": "nfl_det", "name": "Ford Field",
        "lat": 42.3400, "lon": -83.0456, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 600, "roof_type": "DOME", "surface": "TURF"
    },
    "nfl_green_bay_packers": {
        "stadium_id": "nfl_gb", "name": "Lambeau Field",
        "lat": 44.5013, "lon": -88.0622, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 640, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_minnesota_vikings": {
        "stadium_id": "nfl_min", "name": "U.S. Bank Stadium",
        "lat": 44.9736, "lon": -93.2575, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 815, "roof_type": "DOME", "surface": "TURF"
    },
    # NFC South
    "nfl_atlanta_falcons": {
        "stadium_id": "nfl_atl", "name": "Mercedes-Benz Stadium",
        "lat": 33.7554, "lon": -84.4010, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 1050, "roof_type": "RETRACTABLE", "surface": "TURF"
    },
    "nfl_carolina_panthers": {
        "stadium_id": "nfl_car", "name": "Bank of America Stadium",
        "lat": 35.2258, "lon": -80.8528, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 750, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_new_orleans_saints": {
        "stadium_id": "nfl_no", "name": "Caesars Superdome",
        "lat": 29.9511, "lon": -90.0812, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 0, "roof_type": "DOME", "surface": "TURF"
    },
    "nfl_tampa_bay_buccaneers": {
        "stadium_id": "nfl_tb", "name": "Raymond James Stadium",
        "lat": 27.9759, "lon": -82.5033, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 30, "roof_type": "OPEN", "surface": "GRASS"
    },
    # NFC West
    "nfl_arizona_cardinals": {
        "stadium_id": "nfl_ari", "name": "State Farm Stadium",
        "lat": 33.5276, "lon": -112.2626, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 1086, "roof_type": "RETRACTABLE", "surface": "GRASS"
    },
    "nfl_los_angeles_rams": {
        "stadium_id": "nfl_lar", "name": "SoFi Stadium",
        "lat": 33.9534, "lon": -118.3392, "is_outdoor": False,
        "league": "NFL", "altitude_ft": 100, "roof_type": "DOME", "surface": "TURF"
    },
    "nfl_san_francisco_49ers": {
        "stadium_id": "nfl_sf", "name": "Levi's Stadium",
        "lat": 37.4033, "lon": -121.9695, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 10, "roof_type": "OPEN", "surface": "GRASS"
    },
    "nfl_seattle_seahawks": {
        "stadium_id": "nfl_sea", "name": "Lumen Field",
        "lat": 47.5952, "lon": -122.3316, "is_outdoor": True,
        "league": "NFL", "altitude_ft": 10, "roof_type": "OPEN", "surface": "TURF"
    },
    # -------------------------------------------------------------------------
    # MLB VENUES (30 teams)
    # -------------------------------------------------------------------------
    # AL East
    "mlb_baltimore_orioles": {
        "stadium_id": "mlb_bal", "name": "Oriole Park at Camden Yards",
        "lat": 39.2839, "lon": -76.6217, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 25, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_boston_red_sox": {
        "stadium_id": "mlb_bos", "name": "Fenway Park",
        "lat": 42.3467, "lon": -71.0972, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 20, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_new_york_yankees": {
        "stadium_id": "mlb_nyy", "name": "Yankee Stadium",
        "lat": 40.8296, "lon": -73.9262, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 40, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_tampa_bay_rays": {
        "stadium_id": "mlb_tb", "name": "Tropicana Field",
        "lat": 27.7682, "lon": -82.6534, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 40, "roof_type": "DOME", "surface": "TURF"
    },
    "mlb_toronto_blue_jays": {
        "stadium_id": "mlb_tor", "name": "Rogers Centre",
        "lat": 43.6414, "lon": -79.3894, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 250, "roof_type": "RETRACTABLE", "surface": "TURF"
    },
    # AL Central
    "mlb_chicago_white_sox": {
        "stadium_id": "mlb_cws", "name": "Guaranteed Rate Field",
        "lat": 41.8299, "lon": -87.6338, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 590, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_cleveland_guardians": {
        "stadium_id": "mlb_cle", "name": "Progressive Field",
        "lat": 41.4962, "lon": -81.6852, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 660, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_detroit_tigers": {
        "stadium_id": "mlb_det", "name": "Comerica Park",
        "lat": 42.3390, "lon": -83.0485, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 600, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_kansas_city_royals": {
        "stadium_id": "mlb_kc", "name": "Kauffman Stadium",
        "lat": 39.0517, "lon": -94.4803, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 750, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_minnesota_twins": {
        "stadium_id": "mlb_min", "name": "Target Field",
        "lat": 44.9817, "lon": -93.2776, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 830, "roof_type": "OPEN", "surface": "GRASS"
    },
    # AL West
    "mlb_houston_astros": {
        "stadium_id": "mlb_hou", "name": "Minute Maid Park",
        "lat": 29.7573, "lon": -95.3555, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 35, "roof_type": "RETRACTABLE", "surface": "GRASS"
    },
    "mlb_los_angeles_angels": {
        "stadium_id": "mlb_laa", "name": "Angel Stadium",
        "lat": 33.8003, "lon": -117.8827, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 160, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_oakland_athletics": {
        "stadium_id": "mlb_oak", "name": "Oakland Coliseum",
        "lat": 37.7516, "lon": -122.2005, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 25, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_seattle_mariners": {
        "stadium_id": "mlb_sea", "name": "T-Mobile Park",
        "lat": 47.5914, "lon": -122.3325, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 20, "roof_type": "RETRACTABLE", "surface": "GRASS"
    },
    "mlb_texas_rangers": {
        "stadium_id": "mlb_tex", "name": "Globe Life Field",
        "lat": 32.7512, "lon": -97.0832, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 550, "roof_type": "RETRACTABLE", "surface": "TURF"
    },
    # NL East
    "mlb_atlanta_braves": {
        "stadium_id": "mlb_atl", "name": "Truist Park",
        "lat": 33.8908, "lon": -84.4678, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 1050, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_miami_marlins": {
        "stadium_id": "mlb_mia", "name": "LoanDepot Park",
        "lat": 25.7781, "lon": -80.2195, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 10, "roof_type": "RETRACTABLE", "surface": "GRASS"
    },
    "mlb_new_york_mets": {
        "stadium_id": "mlb_nym", "name": "Citi Field",
        "lat": 40.7571, "lon": -73.8458, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 10, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_philadelphia_phillies": {
        "stadium_id": "mlb_phi", "name": "Citizens Bank Park",
        "lat": 39.9061, "lon": -75.1665, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 10, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_washington_nationals": {
        "stadium_id": "mlb_was", "name": "Nationals Park",
        "lat": 38.8730, "lon": -77.0075, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 10, "roof_type": "OPEN", "surface": "GRASS"
    },
    # NL Central
    "mlb_chicago_cubs": {
        "stadium_id": "mlb_chc", "name": "Wrigley Field",
        "lat": 41.9484, "lon": -87.6553, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 595, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_cincinnati_reds": {
        "stadium_id": "mlb_cin", "name": "Great American Ball Park",
        "lat": 39.0979, "lon": -84.5082, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 490, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_milwaukee_brewers": {
        "stadium_id": "mlb_mil", "name": "American Family Field",
        "lat": 43.0280, "lon": -87.9712, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 630, "roof_type": "RETRACTABLE", "surface": "GRASS"
    },
    "mlb_pittsburgh_pirates": {
        "stadium_id": "mlb_pit", "name": "PNC Park",
        "lat": 40.4469, "lon": -80.0057, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 730, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_st_louis_cardinals": {
        "stadium_id": "mlb_stl", "name": "Busch Stadium",
        "lat": 38.6226, "lon": -90.1928, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 450, "roof_type": "OPEN", "surface": "GRASS"
    },
    # NL West
    "mlb_arizona_diamondbacks": {
        "stadium_id": "mlb_ari", "name": "Chase Field",
        "lat": 33.4455, "lon": -112.0667, "is_outdoor": False,
        "league": "MLB", "altitude_ft": 1090, "roof_type": "RETRACTABLE", "surface": "GRASS"
    },
    "mlb_colorado_rockies": {
        "stadium_id": "mlb_col", "name": "Coors Field",
        "lat": 39.7559, "lon": -104.9942, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 5200, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_los_angeles_dodgers": {
        "stadium_id": "mlb_lad", "name": "Dodger Stadium",
        "lat": 34.0739, "lon": -118.2400, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 510, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_san_diego_padres": {
        "stadium_id": "mlb_sd", "name": "Petco Park",
        "lat": 32.7076, "lon": -117.1570, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 20, "roof_type": "OPEN", "surface": "GRASS"
    },
    "mlb_san_francisco_giants": {
        "stadium_id": "mlb_sf", "name": "Oracle Park",
        "lat": 37.7786, "lon": -122.3893, "is_outdoor": True,
        "league": "MLB", "altitude_ft": 0, "roof_type": "OPEN", "surface": "GRASS"
    },
}

# Team name aliases for lookup
TEAM_ALIASES: Dict[str, str] = {
    # NFL
    "bills": "nfl_buffalo_bills", "buffalo": "nfl_buffalo_bills",
    "dolphins": "nfl_miami_dolphins", "miami": "nfl_miami_dolphins",
    "patriots": "nfl_new_england_patriots", "new england": "nfl_new_england_patriots",
    "jets": "nfl_new_york_jets",
    "ravens": "nfl_baltimore_ravens", "baltimore": "nfl_baltimore_ravens",
    "bengals": "nfl_cincinnati_bengals", "cincinnati": "nfl_cincinnati_bengals",
    "browns": "nfl_cleveland_browns", "cleveland": "nfl_cleveland_browns",
    "steelers": "nfl_pittsburgh_steelers", "pittsburgh": "nfl_pittsburgh_steelers",
    "texans": "nfl_houston_texans", "houston": "nfl_houston_texans",
    "colts": "nfl_indianapolis_colts", "indianapolis": "nfl_indianapolis_colts",
    "jaguars": "nfl_jacksonville_jaguars", "jacksonville": "nfl_jacksonville_jaguars",
    "titans": "nfl_tennessee_titans", "tennessee": "nfl_tennessee_titans",
    "broncos": "nfl_denver_broncos", "denver": "nfl_denver_broncos",
    "chiefs": "nfl_kansas_city_chiefs", "kansas city": "nfl_kansas_city_chiefs",
    "raiders": "nfl_las_vegas_raiders", "las vegas": "nfl_las_vegas_raiders",
    "chargers": "nfl_los_angeles_chargers",
    "cowboys": "nfl_dallas_cowboys", "dallas": "nfl_dallas_cowboys",
    "giants": "nfl_new_york_giants",
    "eagles": "nfl_philadelphia_eagles", "philadelphia": "nfl_philadelphia_eagles",
    "commanders": "nfl_washington_commanders", "washington": "nfl_washington_commanders",
    "bears": "nfl_chicago_bears", "chicago": "nfl_chicago_bears",
    "lions": "nfl_detroit_lions", "detroit": "nfl_detroit_lions",
    "packers": "nfl_green_bay_packers", "green bay": "nfl_green_bay_packers",
    "vikings": "nfl_minnesota_vikings", "minnesota": "nfl_minnesota_vikings",
    "falcons": "nfl_atlanta_falcons", "atlanta": "nfl_atlanta_falcons",
    "panthers": "nfl_carolina_panthers", "carolina": "nfl_carolina_panthers",
    "saints": "nfl_new_orleans_saints", "new orleans": "nfl_new_orleans_saints",
    "buccaneers": "nfl_tampa_bay_buccaneers", "tampa bay": "nfl_tampa_bay_buccaneers",
    "cardinals": "nfl_arizona_cardinals", "arizona": "nfl_arizona_cardinals",
    "rams": "nfl_los_angeles_rams",
    "49ers": "nfl_san_francisco_49ers", "san francisco": "nfl_san_francisco_49ers",
    "seahawks": "nfl_seattle_seahawks", "seattle": "nfl_seattle_seahawks",
    # MLB
    "orioles": "mlb_baltimore_orioles",
    "red sox": "mlb_boston_red_sox", "boston": "mlb_boston_red_sox",
    "yankees": "mlb_new_york_yankees",
    "rays": "mlb_tampa_bay_rays",
    "blue jays": "mlb_toronto_blue_jays", "toronto": "mlb_toronto_blue_jays",
    "white sox": "mlb_chicago_white_sox",
    "guardians": "mlb_cleveland_guardians",
    "tigers": "mlb_detroit_tigers",
    "royals": "mlb_kansas_city_royals",
    "twins": "mlb_minnesota_twins",
    "astros": "mlb_houston_astros",
    "angels": "mlb_los_angeles_angels",
    "athletics": "mlb_oakland_athletics", "oakland": "mlb_oakland_athletics",
    "mariners": "mlb_seattle_mariners",
    "rangers": "mlb_texas_rangers", "texas": "mlb_texas_rangers",
    "braves": "mlb_atlanta_braves",
    "marlins": "mlb_miami_marlins",
    "mets": "mlb_new_york_mets",
    "phillies": "mlb_philadelphia_phillies",
    "nationals": "mlb_washington_nationals",
    "cubs": "mlb_chicago_cubs",
    "reds": "mlb_cincinnati_reds",
    "brewers": "mlb_milwaukee_brewers", "milwaukee": "mlb_milwaukee_brewers",
    "pirates": "mlb_pittsburgh_pirates",
    "cardinals_mlb": "mlb_st_louis_cardinals", "st louis": "mlb_st_louis_cardinals",
    "diamondbacks": "mlb_arizona_diamondbacks",
    "rockies": "mlb_colorado_rockies", "colorado": "mlb_colorado_rockies",
    "dodgers": "mlb_los_angeles_dodgers",
    "padres": "mlb_san_diego_padres", "san diego": "mlb_san_diego_padres",
    "giants_mlb": "mlb_san_francisco_giants",
}


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


# ============================================================================
# VENUE REGISTRY LOOKUP FUNCTIONS
# ============================================================================

def normalize_team_name(team: str) -> str:
    """
    Normalize team name to registry key format.

    Args:
        team: Raw team name (e.g., "Buffalo Bills", "Bills", "buffalo")

    Returns:
        Normalized team key or empty string if not found
    """
    if not team:
        return ""

    team_lower = team.lower().strip()

    # Check direct aliases first
    if team_lower in TEAM_ALIASES:
        return TEAM_ALIASES[team_lower]

    # Check if it's already a registry key
    if team_lower in VENUE_REGISTRY:
        return team_lower

    # Try to match partial name
    for key in VENUE_REGISTRY:
        # Extract team name from key (e.g., "nfl_buffalo_bills" -> "buffalo bills")
        parts = key.split("_", 1)
        if len(parts) == 2:
            team_part = parts[1].replace("_", " ")
            if team_lower in team_part or team_part in team_lower:
                return key

    return ""


def get_venue_by_team(team: str, sport: str = "") -> Dict[str, Any]:
    """
    Get venue information by team name.

    Args:
        team: Team name (flexible format)
        sport: Sport code (optional, helps disambiguate)

    Returns:
        Venue dict with stadium_id, name, lat, lon, is_outdoor, etc.
        Returns empty dict if not found.
    """
    team_key = normalize_team_name(team)

    if team_key and team_key in VENUE_REGISTRY:
        venue = VENUE_REGISTRY[team_key]
        # Verify sport matches if provided
        if sport and venue.get("league", "").upper() != sport.upper():
            # Try to find sport-specific match
            sport_lower = sport.lower()
            sport_prefix = "mlb_" if sport_lower == "mlb" else "nfl_" if sport_lower == "nfl" else ""
            for key, v in VENUE_REGISTRY.items():
                if key.startswith(sport_prefix) and normalize_team_name(team) in key:
                    return v.copy()
        return venue.copy()

    # Try direct lookup with sport prefix
    if sport:
        sport_prefix = sport.lower() + "_"
        team_lower = team.lower().replace(" ", "_")
        direct_key = sport_prefix + team_lower
        if direct_key in VENUE_REGISTRY:
            return VENUE_REGISTRY[direct_key].copy()

    return {}


def get_venue_coordinates(stadium_id: str) -> Tuple[float, float]:
    """
    Get lat/lon coordinates for a stadium.

    Args:
        stadium_id: Stadium ID (e.g., "nfl_buf")

    Returns:
        (lat, lon) tuple, or (0.0, 0.0) if not found
    """
    # First check by stadium_id field
    for venue in VENUE_REGISTRY.values():
        if venue.get("stadium_id") == stadium_id:
            return (venue.get("lat", 0.0), venue.get("lon", 0.0))

    # Then check by registry key
    if stadium_id in VENUE_REGISTRY:
        venue = VENUE_REGISTRY[stadium_id]
        return (venue.get("lat", 0.0), venue.get("lon", 0.0))

    return (0.0, 0.0)


def is_venue_outdoor(stadium_id: str) -> bool:
    """
    Check if a venue is outdoor (weather affects game).

    Args:
        stadium_id: Stadium ID or registry key

    Returns:
        True if outdoor, False if dome/retractable
    """
    # Check by stadium_id field
    for venue in VENUE_REGISTRY.values():
        if venue.get("stadium_id") == stadium_id:
            return venue.get("is_outdoor", True)

    # Check by registry key
    if stadium_id in VENUE_REGISTRY:
        return VENUE_REGISTRY[stadium_id].get("is_outdoor", True)

    # Default to outdoor (conservative - apply weather)
    return True


def get_all_outdoor_venues(league: str = "") -> List[Dict[str, Any]]:
    """
    Get all outdoor venues, optionally filtered by league.

    Args:
        league: Optional league filter ("NFL", "MLB")

    Returns:
        List of outdoor venue dicts
    """
    outdoor = []
    for key, venue in VENUE_REGISTRY.items():
        if venue.get("is_outdoor", False):
            if not league or venue.get("league", "").upper() == league.upper():
                outdoor.append({"key": key, **venue})
    return outdoor


def get_venue_for_weather(team: str, sport: str) -> Dict[str, Any]:
    """
    Get venue info needed for weather API call.

    Args:
        team: Team name
        sport: Sport code

    Returns:
        Dict with stadium_id, lat, lon, is_outdoor, name
        or empty dict if not found/not outdoor
    """
    venue = get_venue_by_team(team, sport)

    if not venue:
        return {}

    return {
        "stadium_id": venue.get("stadium_id", ""),
        "name": venue.get("name", "Unknown"),
        "lat": venue.get("lat", 0.0),
        "lon": venue.get("lon", 0.0),
        "is_outdoor": venue.get("is_outdoor", True),
        "altitude_ft": venue.get("altitude_ft", 0),
        "roof_type": venue.get("roof_type", "UNKNOWN"),
    }


# ============================================================================
# SURFACE IMPACT FOR SCORING (v20.0 Phase 9)
# ============================================================================

def calculate_surface_impact_for_scoring(
    sport: str,
    home_team: str,
    pick_type: str,
    market: str = ""
) -> Tuple[float, str]:
    """
    Calculate surface impact adjustment for scoring pipeline (v20.0 Phase 9).

    Args:
        sport: Sport code (NFL, MLB)
        home_team: Home team name (for venue lookup)
        pick_type: Pick type (PROP, SPREAD, TOTAL, etc.)
        market: Market type for props (player_passing_yards, etc.)

    Returns:
        Tuple of (adjustment: float, reason: str)

    Surface impacts:
    - NFL TURF: Favors passing (+0.10 for pass props)
    - NFL GRASS: Slightly favors rushing (+0.05 for rush props)
    - MLB TURF: Ball travels faster, favors hits (+0.05)
    - MLB GRASS: Standard conditions (no adjustment)
    """
    sport_upper = sport.upper() if sport else ""

    # Only NFL and MLB have meaningful surface impacts
    if sport_upper not in ("NFL", "MLB"):
        return (0.0, "")

    # Get venue info for home team
    venue = get_venue_by_team(home_team, sport_upper)
    if not venue:
        return (0.0, "")

    surface = venue.get("surface", "UNKNOWN").upper()
    if surface == "UNKNOWN":
        return (0.0, "")

    market_lower = market.lower() if market else ""
    pick_type_upper = pick_type.upper() if pick_type else ""

    # NFL Surface Impact
    if sport_upper == "NFL":
        if surface == "TURF":
            # Turf favors passing - ball travels faster, better footing
            if pick_type_upper == "PROP":
                if any(x in market_lower for x in ["passing", "reception", "receiving", "catch"]):
                    return (0.10, f"Turf surface favors passing (+0.10)")
                elif any(x in market_lower for x in ["rushing", "rush", "carries"]):
                    return (-0.05, f"Turf surface less favorable for rushing (-0.05)")
            # Game picks - turf slightly favors higher scoring
            elif pick_type_upper in ("TOTAL", "SPREAD", "MONEYLINE", "GAME"):
                return (0.05, f"Turf surface tends to increase scoring (+0.05)")
        elif surface == "GRASS":
            # Grass favors rushing slightly
            if pick_type_upper == "PROP":
                if any(x in market_lower for x in ["rushing", "rush", "carries"]):
                    return (0.05, f"Grass surface slightly favors rushing (+0.05)")

    # MLB Surface Impact
    elif sport_upper == "MLB":
        if surface == "TURF":
            # Turf in MLB - ball bounces faster, more hits
            if pick_type_upper == "PROP":
                if any(x in market_lower for x in ["hits", "total_bases", "singles"]):
                    return (0.08, f"Turf surface favors hits (+0.08)")
            # Game totals - turf can increase scoring
            elif pick_type_upper == "TOTAL":
                return (0.05, f"Turf surface may increase scoring (+0.05)")

    return (0.0, "")
