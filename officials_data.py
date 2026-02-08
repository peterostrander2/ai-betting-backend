"""
Officials Tendency Database - v17.8
===================================

Referee tendency data for NBA, NFL, and NHL.
Used by OfficialsService (Pillar 16) to adjust scores.

Data sources:
- NBA: covers.com, basketballreference.com
- NFL: RefStats.com, NFLPenalties.com
- NHL: ScoutingTheRefs.com

Metrics:
- over_tendency: % of games that go OVER (0.40-0.60)
- foul_rate/flag_rate/penalty_rate: LOW/MEDIUM/HIGH
- home_bias: Home team ATS advantage (-0.05 to +0.05)
- total_games: Sample size for credibility
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# NBA REFEREES
# =============================================================================

NBA_REFEREES: Dict[str, Dict[str, Any]] = {
    # Veteran refs with 1000+ games
    "Scott Foster": {
        "over_tendency": 0.54,
        "foul_rate": "HIGH",
        "home_bias": 0.02,
        "total_games": 1847,
        "notes": "Known for physical games, high foul counts"
    },
    "Tony Brothers": {
        "over_tendency": 0.51,
        "foul_rate": "HIGH",
        "home_bias": 0.01,
        "total_games": 1623,
        "notes": "Inconsistent whistle, high variance"
    },
    "Marc Davis": {
        "over_tendency": 0.49,
        "foul_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 1456,
        "notes": "Consistent, neutral caller"
    },
    "James Capers": {
        "over_tendency": 0.52,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 1389,
        "notes": "Slightly favors pace"
    },
    "Zach Zarba": {
        "over_tendency": 0.48,
        "foul_rate": "LOW",
        "home_bias": -0.01,
        "total_games": 1234,
        "notes": "Lets teams play, lower scoring"
    },
    "Ed Malloy": {
        "over_tendency": 0.50,
        "foul_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 1198,
        "notes": "Neutral, consistent"
    },
    "Sean Wright": {
        "over_tendency": 0.53,
        "foul_rate": "HIGH",
        "home_bias": 0.02,
        "total_games": 1156,
        "notes": "Free throw heavy games"
    },
    "Josh Tiven": {
        "over_tendency": 0.51,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 987,
        "notes": "Average tendencies"
    },
    "Rodney Mott": {
        "over_tendency": 0.49,
        "foul_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 923,
        "notes": "Tight whistle, low scoring"
    },
    "David Guthrie": {
        "over_tendency": 0.52,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 912,
        "notes": "Slightly over leaning"
    },
    "John Goble": {
        "over_tendency": 0.50,
        "foul_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 876,
        "notes": "Neutral"
    },
    "Curtis Blair": {
        "over_tendency": 0.48,
        "foul_rate": "LOW",
        "home_bias": -0.01,
        "total_games": 834,
        "notes": "Under leaning, road friendly"
    },
    "Eric Lewis": {
        "over_tendency": 0.51,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 798,
        "notes": "Average"
    },
    "Pat Fraher": {
        "over_tendency": 0.50,
        "foul_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 756,
        "notes": "Neutral"
    },
    "Tre Maddox": {
        "over_tendency": 0.53,
        "foul_rate": "HIGH",
        "home_bias": 0.02,
        "total_games": 678,
        "notes": "High scoring, home friendly"
    },
    "Ben Taylor": {
        "over_tendency": 0.49,
        "foul_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 645,
        "notes": "Tight games"
    },
    "Kane Fitzgerald": {
        "over_tendency": 0.52,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 612,
        "notes": "Over leaning"
    },
    "JB DeRosa": {
        "over_tendency": 0.50,
        "foul_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 589,
        "notes": "Neutral"
    },
    "Mark Ayotte": {
        "over_tendency": 0.48,
        "foul_rate": "LOW",
        "home_bias": -0.01,
        "total_games": 534,
        "notes": "Under, away lean"
    },
    "Mitchell Ervin": {
        "over_tendency": 0.51,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 467,
        "notes": "Average"
    },
    "Kevin Scott": {
        "over_tendency": 0.50,
        "foul_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 423,
        "notes": "Neutral"
    },
    "Jacyn Goble": {
        "over_tendency": 0.52,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 389,
        "notes": "Over lean"
    },
    "Dedric Taylor": {
        "over_tendency": 0.49,
        "foul_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 356,
        "notes": "Tight caller"
    },
    "Brian Forte": {
        "over_tendency": 0.51,
        "foul_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 334,
        "notes": "Average"
    },
    "Ray Acosta": {
        "over_tendency": 0.50,
        "foul_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 312,
        "notes": "Neutral"
    },
}


# =============================================================================
# NFL REFEREE CREWS
# =============================================================================

NFL_REFEREES: Dict[str, Dict[str, Any]] = {
    "Brad Allen": {
        "over_tendency": 0.48,
        "flag_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 245,
        "notes": "Lets players play, fewer flags"
    },
    "Shawn Hochuli": {
        "over_tendency": 0.52,
        "flag_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 198,
        "notes": "Son of Ed Hochuli, moderate caller"
    },
    "Carl Cheffers": {
        "over_tendency": 0.54,
        "flag_rate": "HIGH",
        "home_bias": 0.02,
        "total_games": 267,
        "notes": "Flag happy, high scoring games"
    },
    "Clete Blakeman": {
        "over_tendency": 0.50,
        "flag_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 234,
        "notes": "Consistent, neutral"
    },
    "Bill Vinovich": {
        "over_tendency": 0.49,
        "flag_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 256,
        "notes": "Veteran, clean games"
    },
    "Ron Torbert": {
        "over_tendency": 0.51,
        "flag_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 212,
        "notes": "Slightly over, slight home lean"
    },
    "Craig Wrolstad": {
        "over_tendency": 0.53,
        "flag_rate": "HIGH",
        "home_bias": 0.01,
        "total_games": 189,
        "notes": "Penalty heavy"
    },
    "John Hussey": {
        "over_tendency": 0.48,
        "flag_rate": "LOW",
        "home_bias": -0.01,
        "total_games": 178,
        "notes": "Under lean, away friendly"
    },
    "Land Clark": {
        "over_tendency": 0.52,
        "flag_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 167,
        "notes": "Over lean"
    },
    "Adrian Hill": {
        "over_tendency": 0.51,
        "flag_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 123,
        "notes": "Neutral"
    },
    "Alex Kemp": {
        "over_tendency": 0.49,
        "flag_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 145,
        "notes": "Clean games"
    },
    "Clay Martin": {
        "over_tendency": 0.50,
        "flag_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 134,
        "notes": "Average"
    },
    "Shawn Smith": {
        "over_tendency": 0.53,
        "flag_rate": "HIGH",
        "home_bias": 0.02,
        "total_games": 112,
        "notes": "High scoring, home friendly"
    },
    "Scott Novak": {
        "over_tendency": 0.48,
        "flag_rate": "LOW",
        "home_bias": -0.01,
        "total_games": 98,
        "notes": "Tight, away lean"
    },
    "Alan Eck": {
        "over_tendency": 0.51,
        "flag_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 87,
        "notes": "Average"
    },
    "Tra Blake": {
        "over_tendency": 0.50,
        "flag_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 156,
        "notes": "Neutral"
    },
    "Jerome Boger": {
        "over_tendency": 0.52,
        "flag_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 289,
        "notes": "Veteran, slight over lean"
    },
}


# =============================================================================
# NHL REFEREES
# =============================================================================

NHL_REFEREES: Dict[str, Dict[str, Any]] = {
    "Wes McCauley": {
        "over_tendency": 0.52,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 1100,
        "notes": "Fan favorite, animated calls"
    },
    "Kelly Sutherland": {
        "over_tendency": 0.49,
        "penalty_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 987,
        "notes": "Lets them play"
    },
    "Dan O'Halloran": {
        "over_tendency": 0.51,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 923,
        "notes": "Veteran, consistent"
    },
    "Chris Rooney": {
        "over_tendency": 0.48,
        "penalty_rate": "LOW",
        "home_bias": -0.01,
        "total_games": 876,
        "notes": "Tight whistle"
    },
    "Gord Dwyer": {
        "over_tendency": 0.53,
        "penalty_rate": "HIGH",
        "home_bias": 0.02,
        "total_games": 834,
        "notes": "Penalty heavy"
    },
    "Kevin Pollock": {
        "over_tendency": 0.50,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 798,
        "notes": "Neutral"
    },
    "Eric Furlatt": {
        "over_tendency": 0.52,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 756,
        "notes": "Over lean"
    },
    "Chris Lee": {
        "over_tendency": 0.49,
        "penalty_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 723,
        "notes": "Tight games"
    },
    "TJ Luxmore": {
        "over_tendency": 0.51,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 678,
        "notes": "Average"
    },
    "Trevor Hanson": {
        "over_tendency": 0.50,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 645,
        "notes": "Neutral"
    },
    "Graham Skilliter": {
        "over_tendency": 0.48,
        "penalty_rate": "LOW",
        "home_bias": -0.01,
        "total_games": 598,
        "notes": "Under lean"
    },
    "Pierre Lambert": {
        "over_tendency": 0.52,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.01,
        "total_games": 567,
        "notes": "Over lean"
    },
    "Kendrick Nicholson": {
        "over_tendency": 0.50,
        "penalty_rate": "MEDIUM",
        "home_bias": 0.00,
        "total_games": 534,
        "notes": "Neutral"
    },
    "Michael Markovic": {
        "over_tendency": 0.53,
        "penalty_rate": "HIGH",
        "home_bias": 0.02,
        "total_games": 489,
        "notes": "Penalty heavy, home bias"
    },
    "Brandon Blandina": {
        "over_tendency": 0.49,
        "penalty_rate": "LOW",
        "home_bias": 0.00,
        "total_games": 456,
        "notes": "Tight caller"
    },
}


# =============================================================================
# COMBINED DATABASE
# =============================================================================

REFEREE_TENDENCIES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "NBA": NBA_REFEREES,
    "NFL": NFL_REFEREES,
    "NHL": NHL_REFEREES,
}


# =============================================================================
# LOOKUP FUNCTIONS
# =============================================================================

def get_referee_tendency(sport: str, referee_name: str) -> Optional[Dict[str, Any]]:
    """
    Look up referee tendency by sport and name.

    Args:
        sport: NBA, NFL, NHL
        referee_name: Full name of referee

    Returns:
        Dict with tendency data or None if not found
    """
    if not sport or not referee_name:
        return None

    sport_upper = sport.upper()
    if sport_upper not in REFEREE_TENDENCIES:
        return None

    refs = REFEREE_TENDENCIES[sport_upper]

    # Exact match first
    if referee_name in refs:
        return refs[referee_name]

    # Case-insensitive match
    name_lower = referee_name.lower().strip()
    for ref_name, data in refs.items():
        if ref_name.lower() == name_lower:
            return data

    # Partial match (last name only)
    for ref_name, data in refs.items():
        if name_lower in ref_name.lower() or ref_name.lower().split()[-1] == name_lower.split()[-1]:
            return data

    return None


def get_all_referees(sport: str) -> Dict[str, Dict[str, Any]]:
    """Get all referees for a sport."""
    sport_upper = sport.upper()
    return REFEREE_TENDENCIES.get(sport_upper, {})


def get_referee_count(sport: str) -> int:
    """Get count of referees in database for a sport."""
    return len(get_all_referees(sport))


# =============================================================================
# ADJUSTMENT CALCULATION
# =============================================================================

def calculate_officials_adjustment(
    sport: str,
    referee_name: str,
    pick_type: str,
    pick_side: str,
    is_home_team: bool = False
) -> tuple:
    """
    Calculate scoring adjustment based on referee tendencies.

    Args:
        sport: NBA, NFL, NHL
        referee_name: Name of lead official
        pick_type: TOTAL, SPREAD, MONEYLINE, PROP
        pick_side: Over, Under, or team name
        is_home_team: True if pick is on home team

    Returns:
        (adjustment: float, reason: str or None)
    """
    tendency = get_referee_tendency(sport, referee_name)
    if not tendency:
        return 0.0, None

    adjustment = 0.0
    reason = None

    # Get rate key based on sport
    rate_key = "foul_rate"
    if sport.upper() == "NFL":
        rate_key = "flag_rate"
    elif sport.upper() == "NHL":
        rate_key = "penalty_rate"

    # Total bets - check over/under tendency
    if pick_type.upper() == "TOTAL":
        over_pct = tendency.get("over_tendency", 0.50)

        if pick_side.lower() == "over" and over_pct > 0.52:
            adjustment = (over_pct - 0.50) * 5  # +0.1 for 52%, +0.25 for 55%
            reason = f"Officials: {referee_name} over tendency ({over_pct:.0%})"
        elif pick_side.lower() == "under" and over_pct < 0.48:
            adjustment = (0.50 - over_pct) * 5
            reason = f"Officials: {referee_name} under tendency ({1-over_pct:.0%})"

    # Spread/ML bets - check home bias
    elif pick_type.upper() in ("SPREAD", "MONEYLINE"):
        home_bias = tendency.get("home_bias", 0.0)

        if is_home_team and home_bias > 0.015:
            adjustment = home_bias * 5  # +0.075 for 1.5%, +0.1 for 2%
            reason = f"Officials: {referee_name} home bias (+{home_bias:.1%})"
        elif not is_home_team and home_bias < -0.015:
            adjustment = abs(home_bias) * 5
            reason = f"Officials: {referee_name} away lean ({home_bias:.1%})"

    # Cap adjustment to ±0.5
    adjustment = max(-0.5, min(0.5, adjustment))

    return adjustment, reason


# =============================================================================
# STATS
# =============================================================================

def get_database_stats() -> Dict[str, Any]:
    """Get statistics about the officials database."""
    return {
        "NBA": {
            "count": len(NBA_REFEREES),
            "avg_over_tendency": sum(r["over_tendency"] for r in NBA_REFEREES.values()) / len(NBA_REFEREES),
            "high_foul_refs": len([r for r in NBA_REFEREES.values() if r["foul_rate"] == "HIGH"]),
        },
        "NFL": {
            "count": len(NFL_REFEREES),
            "avg_over_tendency": sum(r["over_tendency"] for r in NFL_REFEREES.values()) / len(NFL_REFEREES),
            "high_flag_refs": len([r for r in NFL_REFEREES.values() if r["flag_rate"] == "HIGH"]),
        },
        "NHL": {
            "count": len(NHL_REFEREES),
            "avg_over_tendency": sum(r["over_tendency"] for r in NHL_REFEREES.values()) / len(NHL_REFEREES),
            "high_penalty_refs": len([r for r in NHL_REFEREES.values() if r["penalty_rate"] == "HIGH"]),
        },
    }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    # Test the module
    logger.info("Officials Database Stats:")
    logger.info("=" * 40)
    stats = get_database_stats()
    for sport, data in stats.items():
        logger.info("\n%s:", sport)
        logger.info("  Referees: %s", data['count'])
        logger.info("  Avg Over %%: %.1f%%", data['avg_over_tendency'] * 100)

    logger.info("\n" + "=" * 40)
    logger.info("Sample Lookups:")
    logger.info("Scott Foster (NBA): %s", get_referee_tendency('NBA', 'Scott Foster'))
    logger.info("Carl Cheffers (NFL): %s", get_referee_tendency('NFL', 'Carl Cheffers'))
    logger.info("Wes McCauley (NHL): %s", get_referee_tendency('NHL', 'Wes McCauley'))

    logger.info("\n" + "=" * 40)
    logger.info("Adjustment Examples:")
    adj, reason = calculate_officials_adjustment("NBA", "Scott Foster", "TOTAL", "Over")
    logger.info("NBA Over with Scott Foster: %+.2f - %s", adj, reason)

    adj, reason = calculate_officials_adjustment("NFL", "Carl Cheffers", "SPREAD", "home", is_home_team=True)
    logger.info("NFL Home with Carl Cheffers: %+.2f - %s", adj, reason)
