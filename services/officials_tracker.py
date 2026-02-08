"""
Officials Tracker Service (v18.0)

Automated tracking of referee assignments and game outcomes to calculate
dynamic tendencies. Replaces static officials_data.py with data-driven adjustments.

Features:
- Record official assignments during best-bets scoring
- Record game outcomes during post-game grading
- Calculate tendencies weekly from game history
- Provide live tendency lookups for OfficialsService

Integration Points:
- live_data_router.py: Record assignments after officials lookup
- auto_grader.py: Record outcomes during grading
- daily_scheduler.py: Weekly tendency recalculation
- context_layer.py: Use DB tendencies first, fall back to static
"""

import logging
from datetime import datetime, date, timezone
from typing import Dict, Any, Optional, List

from database import (
    get_db,
    DB_ENABLED,
    save_official_game_record,
    record_game_outcome,
    get_official_tendency,
    save_official_tendency,
    get_official_game_history,
    OfficialGameRecord,
    OfficialTendency,
)

logger = logging.getLogger("officials_tracker")


class OfficialsTracker:
    """
    Track referee assignments and calculate tendencies.

    Usage:
        # Record assignment during best-bets
        await officials_tracker.record_game_assignment(
            event_id="abc123",
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            officials={"lead_official": "Scott Foster", ...},
            game_date="2026-02-02",
            over_under_line=220.5,
            spread_line=-3.5
        )

        # Record outcome during grading
        await officials_tracker.record_game_outcome(
            event_id="abc123",
            final_total=225,
            home_score=115,
            away_score=110
        )

        # Get live tendency
        tendency = officials_tracker.get_live_tendency("NBA", "Scott Foster")
    """

    def __init__(self):
        self._enabled = DB_ENABLED
        self._assignments_recorded = 0
        self._outcomes_recorded = 0
        self._tendency_lookups = 0

    @property
    def enabled(self) -> bool:
        """Check if tracking is enabled (requires database)."""
        return self._enabled and DB_ENABLED

    def record_game_assignment(
        self,
        event_id: str,
        sport: str,
        home_team: str,
        away_team: str,
        officials: Dict[str, Any],
        game_date: str,
        over_under_line: float = None,
        spread_line: float = None,
        game_start_time: datetime = None,
        season: str = None
    ) -> bool:
        """
        Record official assignment for a game.

        Called from live_data_router.py during best-bets scoring
        after officials lookup succeeds.

        Args:
            event_id: Unique game identifier
            sport: Sport code (NBA, NFL, NHL)
            home_team: Home team name
            away_team: Away team name
            officials: Dict with lead_official, official_2, official_3
            game_date: Game date as YYYY-MM-DD string
            over_under_line: Total line at game time
            spread_line: Spread line at game time (home perspective)
            game_start_time: Game start datetime
            season: Season string (e.g., "2025-26")

        Returns:
            True if recorded successfully, False otherwise
        """
        if not self.enabled:
            return False

        lead_official = officials.get("lead_official") or officials.get("referee")
        if not lead_official:
            return False

        try:
            with get_db() as db:
                if not db:
                    return False

                record = save_official_game_record(
                    db=db,
                    event_id=event_id,
                    sport=sport,
                    home_team=home_team,
                    away_team=away_team,
                    lead_official=lead_official,
                    official_2=officials.get("official_2") or officials.get("umpire_1"),
                    official_3=officials.get("official_3") or officials.get("umpire_2"),
                    game_date=game_date,
                    over_under_line=over_under_line,
                    spread_line=spread_line,
                    game_start_time=game_start_time,
                    season=season
                )

                if record:
                    self._assignments_recorded += 1
                    logger.debug(
                        "Recorded official assignment: %s - %s for %s @ %s",
                        event_id, lead_official, away_team, home_team
                    )
                    return True
                return False

        except Exception as e:
            logger.error("Failed to record official assignment: %s", e)
            return False

    def record_outcome(
        self,
        event_id: str,
        final_total: float,
        home_score: int,
        away_score: int
    ) -> bool:
        """
        Record game outcome for an existing official assignment.

        Called from auto_grader.py during post-game grading
        after determining final scores.

        Args:
            event_id: Unique game identifier
            final_total: Combined final score
            home_score: Home team final score
            away_score: Away team final score

        Returns:
            True if recorded successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            with get_db() as db:
                if not db:
                    return False

                record = record_game_outcome(
                    db=db,
                    event_id=event_id,
                    final_total=final_total,
                    home_score=home_score,
                    away_score=away_score
                )

                if record:
                    self._outcomes_recorded += 1
                    logger.info(
                        "Recorded outcome for %s: total=%s, went_over=%s",
                        event_id, final_total, record.went_over
                    )
                    return True
                return False

        except Exception as e:
            logger.error("Failed to record game outcome: %s", e)
            return False

    def get_live_tendency(
        self,
        sport: str,
        official_name: str,
        season: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get live tendency from database.

        Called from context_layer.py OfficialsService to get
        data-driven tendencies before falling back to static data.

        Args:
            sport: Sport code (NBA, NFL, NHL)
            official_name: Official's name
            season: Optional season filter

        Returns:
            Tendency dict if found and sufficient sample, None otherwise
        """
        if not self.enabled:
            return None

        try:
            with get_db() as db:
                if not db:
                    return None

                tendency = get_official_tendency(
                    db=db,
                    sport=sport,
                    official_name=official_name,
                    season=season
                )

                if tendency:
                    self._tendency_lookups += 1
                    return tendency
                return None

        except Exception as e:
            logger.error("Failed to get live tendency: %s", e)
            return None

    def calculate_tendencies(
        self,
        sport: str,
        min_games: int = 50,
        season: str = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Recalculate all tendencies for a sport from game history.

        Called from daily_scheduler.py weekly (Sunday 3 AM ET).

        Args:
            sport: Sport code (NBA, NFL, NHL)
            min_games: Minimum games for sufficient sample
            season: Optional season filter (defaults to current)

        Returns:
            Dict of official_name -> tendency data
        """
        if not self.enabled:
            return {}

        try:
            with get_db() as db:
                if not db:
                    return {}

                # Get all officials with recorded games
                query = db.query(
                    OfficialGameRecord.lead_official,
                ).filter(
                    OfficialGameRecord.sport == sport.upper(),
                    OfficialGameRecord.outcome_recorded_at.isnot(None)
                )

                if season:
                    query = query.filter(OfficialGameRecord.season == season)

                officials = query.distinct().all()

                tendencies = {}
                for (official_name,) in officials:
                    if not official_name:
                        continue

                    # Get game history for this official
                    history = get_official_game_history(
                        db=db,
                        sport=sport,
                        official_name=official_name,
                        season=season,
                        limit=200
                    )

                    if len(history) < 10:
                        continue

                    # Calculate metrics
                    total_games = len(history)
                    over_games = sum(1 for g in history if g.get("went_over") is True)
                    home_cover_games = sum(1 for g in history if g.get("home_covered") is True)

                    total_points_sum = sum(
                        g.get("final_total", 0) for g in history
                        if g.get("final_total") is not None
                    )
                    avg_total = total_points_sum / total_games if total_games > 0 else None

                    # Determine whistle rate (simplified - based on over tendency)
                    over_pct = over_games / total_games if total_games > 0 else 0.5
                    if over_pct >= 0.55:
                        whistle_rate = "HIGH"
                    elif over_pct <= 0.45:
                        whistle_rate = "LOW"
                    else:
                        whistle_rate = "MEDIUM"

                    # Save tendency
                    tendency_record = save_official_tendency(
                        db=db,
                        sport=sport,
                        official_name=official_name,
                        season=season or self._get_current_season(),
                        total_games=total_games,
                        over_games=over_games,
                        home_cover_games=home_cover_games,
                        avg_total_points=avg_total,
                        whistle_rate=whistle_rate
                    )

                    if tendency_record:
                        tendencies[official_name] = {
                            "total_games": total_games,
                            "over_games": over_games,
                            "over_pct": over_pct,
                            "home_cover_games": home_cover_games,
                            "home_cover_pct": home_cover_games / total_games if total_games > 0 else 0.5,
                            "home_bias": (home_cover_games / total_games - 0.5) if total_games > 0 else 0,
                            "whistle_rate": whistle_rate,
                            "avg_total_points": avg_total,
                            "sample_size_sufficient": total_games >= min_games,
                        }

                logger.info(
                    "Calculated tendencies for %d %s officials",
                    len(tendencies), sport
                )
                return tendencies

        except Exception as e:
            logger.error("Failed to calculate tendencies for %s: %s", sport, e)
            return {}

    def get_status(self) -> Dict[str, Any]:
        """Get tracker status for debugging."""
        return {
            "enabled": self.enabled,
            "database_enabled": DB_ENABLED,
            "assignments_recorded": self._assignments_recorded,
            "outcomes_recorded": self._outcomes_recorded,
            "tendency_lookups": self._tendency_lookups,
        }

    def _get_current_season(self) -> str:
        """Get current season string."""
        now = datetime.now(tz=timezone.utc)
        if now.month >= 10:
            return f"{now.year}-{str(now.year + 1)[-2:]}"
        else:
            return f"{now.year - 1}-{str(now.year)[-2:]}"


# Global singleton instance
officials_tracker = OfficialsTracker()


# Convenience functions for direct import
def record_game_assignment(**kwargs) -> bool:
    """Record official assignment - wrapper for officials_tracker.record_game_assignment()"""
    return officials_tracker.record_game_assignment(**kwargs)


def record_outcome(**kwargs) -> bool:
    """Record game outcome - wrapper for officials_tracker.record_outcome()"""
    return officials_tracker.record_outcome(**kwargs)


def get_live_tendency(sport: str, official_name: str, season: str = None) -> Optional[Dict[str, Any]]:
    """Get live tendency - wrapper for officials_tracker.get_live_tendency()"""
    return officials_tracker.get_live_tendency(sport, official_name, season)


def calculate_tendencies(sport: str, min_games: int = 50, season: str = None) -> Dict[str, Dict[str, Any]]:
    """Calculate tendencies - wrapper for officials_tracker.calculate_tendencies()"""
    return officials_tracker.calculate_tendencies(sport, min_games, season)
