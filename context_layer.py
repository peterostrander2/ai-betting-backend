"""
Context Layer - Pillars 13-17 Services
=======================================

This module provides services for context-based scoring adjustments.

Version: v17.9
- Added StadiumAltitudeService for altitude-based adjustments

Pillars:
- 13: Defensive Rank
- 14: Pace Vector
- 15: Usage Vacuum
- 16: Officials (v17.8)
- 17: Park Factors (MLB only)
"""

import logging
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# Import officials data for Pillar 16
try:
    from officials_data import get_referee_tendency, calculate_officials_adjustment
    OFFICIALS_DATA_AVAILABLE = True
except ImportError:
    OFFICIALS_DATA_AVAILABLE = False
    logger.warning("officials_data module not available")


# =============================================================================
# PILLAR 13: DEFENSIVE RANK
# =============================================================================

class DefensiveRankService:
    """
    Pillar 13: Defensive Rank Analysis

    Adjusts scores based on defensive rankings and matchups.
    """

    @staticmethod
    def get_defensive_adjustment(
        sport: str,
        team: str,
        opponent: str,
        pick_type: str
    ) -> Tuple[float, List[str]]:
        """
        Calculate adjustment based on defensive rankings.

        Returns:
            (adjustment, reasons) tuple
        """
        # Placeholder - actual implementation would query defensive stats
        return (0.0, [])


# =============================================================================
# PILLAR 14: PACE VECTOR
# =============================================================================

class PaceVectorService:
    """
    Pillar 14: Pace Vector Analysis

    Adjusts scores based on team pace and tempo matchups.
    """

    @staticmethod
    def get_pace_adjustment(
        sport: str,
        home_team: str,
        away_team: str,
        pick_type: str
    ) -> Tuple[float, List[str]]:
        """
        Calculate adjustment based on pace matchup.

        Returns:
            (adjustment, reasons) tuple
        """
        # Placeholder - actual implementation would analyze pace data
        return (0.0, [])


# =============================================================================
# PILLAR 15: USAGE VACUUM
# =============================================================================

class UsageVacuumService:
    """
    Pillar 15: Usage Vacuum Analysis

    Adjusts scores when key players are out and usage redistributes.
    """

    @staticmethod
    def get_usage_adjustment(
        sport: str,
        team: str,
        injuries: List[Dict],
        pick_type: str
    ) -> Tuple[float, List[str]]:
        """
        Calculate adjustment based on injury-related usage changes.

        Returns:
            (adjustment, reasons) tuple
        """
        # Placeholder - actual implementation would analyze usage patterns
        return (0.0, [])


# =============================================================================
# PILLAR 16: OFFICIALS (v17.8)
# =============================================================================

class OfficialsService:
    """
    Pillar 16: Officials Analysis

    Adjusts scores based on referee tendencies.
    Data source: ESPN officials API + officials_data.py tendency database.

    v17.8: Now uses real referee tendency data.
    """

    @staticmethod
    def get_officials_adjustment(
        sport: str,
        officials: dict,
        pick_type: str,
        pick_side: str,
        is_home_team: bool = False
    ) -> Tuple[float, List[str]]:
        """
        Calculate scoring adjustment based on referee tendencies.

        Args:
            sport: NBA, NFL, NHL (NCAAB/MLB not supported)
            officials: Dict with lead_official, official_2, etc. from ESPN
            pick_type: TOTAL, SPREAD, MONEYLINE, PROP
            pick_side: Over, Under, or team name
            is_home_team: True if pick is on home team

        Returns:
            (adjustment: float, reasons: List[str])
        """
        adjustment = 0.0
        reasons = []

        # Only NBA, NFL, NHL have referee data
        if sport.upper() not in ("NBA", "NFL", "NHL"):
            return adjustment, reasons

        if not officials:
            return adjustment, reasons

        if not OFFICIALS_DATA_AVAILABLE:
            return adjustment, reasons

        # Get lead official (most influential)
        lead_ref = (
            officials.get("lead_official") or
            officials.get("referee") or
            officials.get("Referee") or
            (officials.get("officials", [{}])[0].get("displayName")
             if isinstance(officials.get("officials"), list) else None)
        )

        if not lead_ref:
            return adjustment, reasons

        # Calculate adjustment using officials_data module
        adj, reason = calculate_officials_adjustment(
            sport=sport,
            referee_name=lead_ref,
            pick_type=pick_type,
            pick_side=pick_side,
            is_home_team=is_home_team
        )

        if adj != 0 and reason:
            adjustment = adj
            reasons.append(reason)

        return adjustment, reasons

    @staticmethod
    def get_referee_info(sport: str, referee_name: str) -> dict:
        """Get detailed info about a specific referee."""
        if not OFFICIALS_DATA_AVAILABLE:
            return {"found": False, "name": referee_name, "sport": sport}

        tendency = get_referee_tendency(sport, referee_name)
        if not tendency:
            return {"found": False, "name": referee_name, "sport": sport}

        return {
            "found": True,
            "name": referee_name,
            "sport": sport,
            "over_tendency": tendency.get("over_tendency"),
            "home_bias": tendency.get("home_bias"),
            "total_games": tendency.get("total_games"),
            "notes": tendency.get("notes"),
        }


# =============================================================================
# PILLAR 17: PARK FACTORS (MLB only)
# =============================================================================

class ParkFactorsService:
    """
    Pillar 17: Park Factors Analysis (MLB only)

    Adjusts scores based on ballpark characteristics.
    """

    # Park factor data (1.0 = neutral, >1.0 = hitter-friendly)
    PARK_FACTORS = {
        "coors field": 1.38,
        "great american ball park": 1.15,
        "fenway park": 1.12,
        "yankee stadium": 1.10,
        "citizens bank park": 1.08,
        "oracle park": 0.85,
        "petco park": 0.88,
        "tropicana field": 0.90,
        "oakland coliseum": 0.92,
        "t-mobile park": 0.93,
    }

    @classmethod
    def get_park_adjustment(
        cls,
        home_team: str,
        stadium: str,
        pick_type: str,
        pick_side: str
    ) -> Tuple[float, List[str]]:
        """
        Calculate adjustment based on park factors.

        Returns:
            (adjustment, reasons) tuple
        """
        if not stadium:
            return (0.0, [])

        stadium_lower = stadium.lower()
        factor = cls.PARK_FACTORS.get(stadium_lower, 1.0)

        if factor == 1.0:
            return (0.0, [])

        pick_type_upper = pick_type.upper() if pick_type else ""
        pick_side_lower = pick_side.lower() if pick_side else ""

        if pick_type_upper == "TOTAL":
            if factor > 1.1 and "over" in pick_side_lower:
                return (0.3, [f"Hitter-friendly park ({factor:.2f} factor)"])
            elif factor < 0.95 and "under" in pick_side_lower:
                return (0.2, [f"Pitcher-friendly park ({factor:.2f} factor)"])

        return (0.0, [])


# =============================================================================
# STADIUM ALTITUDE SERVICE (v17.9)
# =============================================================================

class StadiumAltitudeService:
    """
    Altitude impact on game scoring (v17.9)

    High-altitude venues affect player performance:
    - Denver (5280ft): Significant impact on all sports
    - Utah (4226ft): Moderate impact
    - Mexico City (7350ft): Major impact for international games

    MLB: Thin air = more home runs, higher scoring
    NFL/NCAAF: Visiting teams fatigue faster at altitude
    NBA/NHL: Less pronounced but still measurable
    """

    HIGH_ALTITUDE = {
        # NFL/MLB/NBA/NHL venues
        "broncos": 5280,
        "nuggets": 5280,
        "rockies": 5200,
        "avalanche": 5280,
        "jazz": 4226,
        "utah": 4226,
        "real salt lake": 4226,
        # College venues
        "colorado": 5430,
        "air force": 6621,
        "wyoming": 7220,
        "new mexico": 5312,
        "byu": 4551,
        "utah state": 4528,
        # International
        "mexico city": 7350,
        "azteca": 7350,
    }

    @classmethod
    def get_altitude_adjustment(
        cls,
        sport: str,
        home_team: str,
        pick_type: str,
        pick_side: str
    ) -> Tuple[float, List[str]]:
        """
        Returns (adjustment, reasons) tuple for altitude impact.

        Args:
            sport: Sport code (NFL, MLB, NBA, etc.)
            home_team: Home team name
            pick_type: TOTAL, SPREAD, MONEYLINE, PROP
            pick_side: Over, Under, or team name

        Returns:
            tuple: (adjustment: float, reasons: list[str])
                   adjustment range: -0.3 to +0.5
        """
        if not home_team:
            return (0.0, [])

        home_lower = home_team.lower().strip()

        # Find altitude for this venue
        altitude = 0
        for venue_key, venue_alt in cls.HIGH_ALTITUDE.items():
            if venue_key in home_lower:
                altitude = venue_alt
                break

        if altitude < 4000:
            return (0.0, [])

        sport_upper = sport.upper() if sport else ""
        pick_type_upper = pick_type.upper() if pick_type else ""
        pick_side_lower = pick_side.lower() if pick_side else ""

        # MLB: Coors Field effect (5000ft+)
        if sport_upper == "MLB" and altitude >= 5000:
            if pick_type_upper == "TOTAL":
                if "over" in pick_side_lower:
                    return (0.5, [f"Coors Field {altitude}ft favors OVER (+0.5)"])
                elif "under" in pick_side_lower:
                    return (-0.3, [f"Coors Field {altitude}ft penalizes UNDER (-0.3)"])
            # Side bets - slight offensive boost
            return (0.2, [f"Altitude {altitude}ft boosts offense (+0.2)"])

        # NFL/NCAAF: Mile High visitor fatigue (5000ft+)
        if sport_upper in ("NFL", "NCAAF") and altitude >= 5000:
            return (0.25, [f"Mile High {altitude}ft visitor fatigue (+0.25)"])

        # NBA/NHL at altitude (4000ft+)
        if sport_upper in ("NBA", "NHL") and altitude >= 4000:
            return (0.15, [f"Altitude {altitude}ft moderate effect (+0.15)"])

        # Generic high altitude (4000ft+)
        if altitude >= 4000:
            return (0.15, [f"Altitude {altitude}ft moderate effect (+0.15)"])

        return (0.0, [])


# =============================================================================
# CONTEXT MODIFIERS CALCULATOR
# =============================================================================

def compute_context_modifiers(
    sport: str,
    home_team: str,
    away_team: str,
    injuries: Optional[List[Dict]] = None,
    rest_days_override: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Compute all context-based modifiers for a game.

    Args:
        sport: Sport code
        home_team: Home team name
        away_team: Away team name
        injuries: List of injury dicts
        rest_days_override: Override for rest days (from ESPN)

    Returns:
        Dict with all computed modifiers
    """
    result = {
        "defensive_rank": {},
        "pace_vector": {},
        "usage_vacuum": {},
        "park_factors": {},
        "travel_fatigue": None,
    }

    # Pillar 13: Defensive Rank
    try:
        adj, reasons = DefensiveRankService.get_defensive_adjustment(
            sport, home_team, away_team, "SPREAD"
        )
        result["defensive_rank"] = {"adjustment": adj, "reasons": reasons}
    except Exception as e:
        logger.debug("Defensive rank calc failed: %s", e)

    # Pillar 14: Pace Vector
    try:
        adj, reasons = PaceVectorService.get_pace_adjustment(
            sport, home_team, away_team, "TOTAL"
        )
        result["pace_vector"] = {"adjustment": adj, "reasons": reasons}
    except Exception as e:
        logger.debug("Pace vector calc failed: %s", e)

    # Pillar 15: Usage Vacuum
    if injuries:
        try:
            adj, reasons = UsageVacuumService.get_usage_adjustment(
                sport, home_team, injuries, "SPREAD"
            )
            result["usage_vacuum"] = {"adjustment": adj, "reasons": reasons}
        except Exception as e:
            logger.debug("Usage vacuum calc failed: %s", e)

    # ===== TRAVEL FATIGUE (v17.9) =====
    # Wire ESPN rest_days to travel module for B2B and fatigue detection
    if rest_days_override is not None:
        try:
            # Import travel module
            try:
                from alt_data_sources.travel import calculate_distance, calculate_fatigue_impact
                TRAVEL_MODULE_AVAILABLE = True
            except ImportError:
                TRAVEL_MODULE_AVAILABLE = False

            if TRAVEL_MODULE_AVAILABLE:
                # Calculate distance between teams
                distance = 0
                if away_team and home_team:
                    distance = calculate_distance(away_team, home_team)

                # Calculate fatigue impact
                fatigue = calculate_fatigue_impact(
                    sport=sport,
                    distance_miles=distance,
                    rest_days_away=int(rest_days_override),
                    rest_days_home=0  # We focus on away team fatigue
                )

                result["travel_fatigue"] = {
                    "rest_days": int(rest_days_override),
                    "distance_miles": distance,
                    "adjustment": fatigue.get("away_team_fatigue", 0.0),
                    "overall_impact": fatigue.get("overall_impact", "NONE"),
                    "reasons": fatigue.get("reasons", [])
                }
                logger.debug(
                    "Travel fatigue calculated: rest=%d, dist=%d, impact=%s",
                    int(rest_days_override), distance, fatigue.get("overall_impact")
                )
        except Exception as e:
            logger.debug("Travel fatigue calc failed: %s", e)

    return result


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DefensiveRankService",
    "PaceVectorService",
    "UsageVacuumService",
    "OfficialsService",
    "ParkFactorsService",
    "StadiumAltitudeService",
    "compute_context_modifiers",
]
