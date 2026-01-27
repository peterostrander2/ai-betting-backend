"""
Event Resolver - Cross-provider event ID mapping
================================================
v14.10 - End-to-end verification support

Canonical Event ID Format:
  {SPORT}:ODDS:{odds_api_event_id}      # Primary (Odds API)
  {SPORT}:TIME:{away}@{home}:{epoch}    # Fallback (time-based)

This resolver maps events across:
- Odds API (primary for all sports)
- BallDontLie (NBA games)
- Playbook API (all sports)

Usage:
    from identity.event_resolver import resolve_event, get_event_resolver

    resolved = resolve_event(
        sport="NBA",
        home_team="Los Angeles Lakers",
        away_team="Boston Celtics",
        commence_time="2026-01-26T19:00:00Z",
        odds_api_id="abc123def456"
    )

    print(resolved.canonical_event_id)  # NBA:ODDS:abc123def456
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from .name_normalizer import normalize_team_name

logger = logging.getLogger(__name__)

# TTL constants (seconds)
TTL_EVENT_MAPPING = 6 * 60 * 60  # 6 hours


class EventMatchMethod(str, Enum):
    """How the event was matched."""
    EXACT_ID = "exact_id"           # Direct Odds API ID lookup
    TEAM_TIME_MATCH = "team_time_match"  # Matched by teams + time
    FUZZY_TEAM = "fuzzy_team"       # Fuzzy team name matching
    NOT_FOUND = "not_found"         # No match found


@dataclass
class ResolvedEvent:
    """Result of event resolution."""
    canonical_event_id: str
    sport: str
    home_team: str
    away_team: str
    commence_time: str  # ISO 8601

    # Provider ID mappings
    provider_ids: Dict[str, str] = field(default_factory=dict)
    # Example: {"odds_api": "abc123", "balldontlie": "12345", "playbook": "PLY-456"}

    # Resolution metadata
    match_method: EventMatchMethod = EventMatchMethod.NOT_FOUND
    confidence: float = 0.0

    # Event status
    status: str = "scheduled"  # scheduled, in_progress, final
    home_score: Optional[int] = None
    away_score: Optional[int] = None

    @property
    def is_resolved(self) -> bool:
        """Check if event was successfully resolved."""
        return self.match_method != EventMatchMethod.NOT_FOUND

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "canonical_event_id": self.canonical_event_id,
            "sport": self.sport,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "commence_time": self.commence_time,
            "provider_ids": self.provider_ids,
            "match_method": self.match_method.value,
            "confidence": self.confidence,
            "status": self.status,
            "home_score": self.home_score,
            "away_score": self.away_score,
        }


class EventResolver:
    """
    Cross-provider event ID resolver.

    Maps events from Odds API to BallDontLie and Playbook.
    Primary source is Odds API for consistent event IDs across sports.
    """

    def __init__(self):
        # Cache of resolved events by canonical ID
        self._cache: Dict[str, ResolvedEvent] = {}
        # Index by team+time for quick lookups
        self._team_time_index: Dict[str, str] = {}  # "away@home:epoch" -> canonical_id
        # Index by provider ID
        self._provider_index: Dict[tuple, str] = {}  # (provider, id) -> canonical_id

    def _generate_canonical_id(
        self,
        sport: str,
        odds_api_id: Optional[str] = None,
        home_team: str = "",
        away_team: str = "",
        commence_time: str = ""
    ) -> str:
        """Generate canonical event ID."""
        sport_upper = sport.upper()

        # Primary: Use Odds API ID if available
        if odds_api_id:
            return f"{sport_upper}:ODDS:{odds_api_id}"

        # Fallback: Time-based ID
        home_norm = normalize_team_name(home_team).replace(" ", "_")
        away_norm = normalize_team_name(away_team).replace(" ", "_")

        try:
            dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
            epoch = int(dt.timestamp())
        except (ValueError, AttributeError):
            epoch = 0

        return f"{sport_upper}:TIME:{away_norm}@{home_norm}:{epoch}"

    def _teams_match(self, team1: str, team2: str) -> bool:
        """Check if two team names refer to the same team."""
        n1 = normalize_team_name(team1)
        n2 = normalize_team_name(team2)
        return n1 == n2 or n1 in n2 or n2 in n1

    def _time_key(self, home_team: str, away_team: str, commence_time: str) -> str:
        """Generate time-based lookup key."""
        home_norm = normalize_team_name(home_team)
        away_norm = normalize_team_name(away_team)

        try:
            dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
            epoch = int(dt.timestamp())
        except (ValueError, AttributeError):
            epoch = 0

        return f"{away_norm}@{home_norm}:{epoch}"

    def resolve_event(
        self,
        sport: str,
        home_team: str,
        away_team: str,
        commence_time: str,
        odds_api_id: Optional[str] = None,
        provider_context: Optional[Dict[str, str]] = None
    ) -> ResolvedEvent:
        """
        Resolve an event to canonical ID.

        Resolution strategy (in order):
        1. Direct Odds API ID lookup
        2. Cached canonical ID lookup
        3. Team + time matching
        4. Create new time-based ID

        Args:
            sport: Sport code (NBA, NFL, etc.)
            home_team: Home team name
            away_team: Away team name
            commence_time: Game start time (ISO 8601)
            odds_api_id: Known Odds API event ID (preferred)
            provider_context: Dict of known provider IDs

        Returns:
            ResolvedEvent with canonical ID and provider mappings
        """
        sport_upper = sport.upper()
        provider_context = provider_context or {}

        # Strategy 1: Direct Odds API ID
        if odds_api_id:
            canonical_id = f"{sport_upper}:ODDS:{odds_api_id}"

            # Check cache first
            if canonical_id in self._cache:
                cached = self._cache[canonical_id]
                # Update provider context if new info provided
                if provider_context:
                    cached.provider_ids.update(provider_context)
                return cached

            # Create new resolved event
            resolved = ResolvedEvent(
                canonical_event_id=canonical_id,
                sport=sport_upper,
                home_team=home_team,
                away_team=away_team,
                commence_time=commence_time,
                provider_ids={"odds_api": odds_api_id, **provider_context},
                match_method=EventMatchMethod.EXACT_ID,
                confidence=1.0,
            )

            # Cache it
            self._cache[canonical_id] = resolved
            self._provider_index[("odds_api", odds_api_id)] = canonical_id
            self._team_time_index[self._time_key(home_team, away_team, commence_time)] = canonical_id

            # Index provider context IDs
            for provider, pid in provider_context.items():
                if pid:
                    self._provider_index[(provider, str(pid))] = canonical_id

            logger.debug("Resolved event via Odds API ID: %s", canonical_id)
            return resolved

        # Strategy 2: Check provider index for known IDs
        for provider, pid in provider_context.items():
            if pid and (provider, str(pid)) in self._provider_index:
                canonical_id = self._provider_index[(provider, str(pid))]
                if canonical_id in self._cache:
                    cached = self._cache[canonical_id]
                    cached.provider_ids.update(provider_context)
                    return cached

        # Strategy 3: Team + time lookup
        time_key = self._time_key(home_team, away_team, commence_time)
        if time_key in self._team_time_index:
            canonical_id = self._team_time_index[time_key]
            if canonical_id in self._cache:
                cached = self._cache[canonical_id]
                cached.provider_ids.update(provider_context)
                return cached

        # Strategy 4: Create new time-based ID
        canonical_id = self._generate_canonical_id(
            sport_upper,
            None,
            home_team,
            away_team,
            commence_time
        )

        resolved = ResolvedEvent(
            canonical_event_id=canonical_id,
            sport=sport_upper,
            home_team=home_team,
            away_team=away_team,
            commence_time=commence_time,
            provider_ids=provider_context.copy(),
            match_method=EventMatchMethod.TEAM_TIME_MATCH,
            confidence=0.85,
        )

        # Cache it
        self._cache[canonical_id] = resolved
        self._team_time_index[time_key] = canonical_id

        # Index provider IDs
        for provider, pid in provider_context.items():
            if pid:
                self._provider_index[(provider, str(pid))] = canonical_id

        logger.debug("Resolved event via team+time: %s", canonical_id)
        return resolved

    def link_provider_id(
        self,
        canonical_id: str,
        provider: str,
        provider_id: str
    ) -> bool:
        """
        Link a provider ID to an existing canonical event.

        Args:
            canonical_id: The canonical event ID
            provider: Provider name (odds_api, balldontlie, playbook)
            provider_id: The provider's event ID

        Returns:
            True if linked successfully, False if canonical ID not found
        """
        if canonical_id in self._cache:
            self._cache[canonical_id].provider_ids[provider] = provider_id
            self._provider_index[(provider, str(provider_id))] = canonical_id
            logger.debug("Linked %s:%s to %s", provider, provider_id, canonical_id)
            return True
        return False

    def get_by_provider_id(
        self,
        provider: str,
        provider_id: str
    ) -> Optional[ResolvedEvent]:
        """
        Look up event by provider-specific ID.

        Args:
            provider: Provider name
            provider_id: Provider's event ID

        Returns:
            ResolvedEvent if found, None otherwise
        """
        key = (provider, str(provider_id))
        if key in self._provider_index:
            canonical_id = self._provider_index[key]
            return self._cache.get(canonical_id)
        return None

    def get_by_canonical_id(self, canonical_id: str) -> Optional[ResolvedEvent]:
        """Get event by canonical ID."""
        return self._cache.get(canonical_id)

    def update_event_status(
        self,
        canonical_id: str,
        status: str,
        home_score: Optional[int] = None,
        away_score: Optional[int] = None
    ) -> bool:
        """
        Update event status and scores.

        Args:
            canonical_id: The canonical event ID
            status: New status (scheduled, in_progress, final)
            home_score: Home team score
            away_score: Away team score

        Returns:
            True if updated, False if not found
        """
        if canonical_id in self._cache:
            event = self._cache[canonical_id]
            event.status = status
            if home_score is not None:
                event.home_score = home_score
            if away_score is not None:
                event.away_score = away_score
            return True
        return False

    def clear(self):
        """Clear all caches."""
        self._cache.clear()
        self._team_time_index.clear()
        self._provider_index.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get resolver statistics."""
        return {
            "cached_events": len(self._cache),
            "time_index_size": len(self._team_time_index),
            "provider_index_size": len(self._provider_index),
        }


# =============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS
# =============================================================================

_event_resolver: Optional[EventResolver] = None


def get_event_resolver() -> EventResolver:
    """Get singleton EventResolver instance."""
    global _event_resolver
    if _event_resolver is None:
        _event_resolver = EventResolver()
    return _event_resolver


def resolve_event(
    sport: str,
    home_team: str,
    away_team: str,
    commence_time: str,
    odds_api_id: Optional[str] = None,
    provider_context: Optional[Dict[str, str]] = None
) -> ResolvedEvent:
    """
    Convenience function to resolve an event.

    Args:
        sport: Sport code
        home_team: Home team name
        away_team: Away team name
        commence_time: Game start time (ISO 8601)
        odds_api_id: Known Odds API event ID
        provider_context: Dict of known provider IDs

    Returns:
        ResolvedEvent with canonical ID and provider mappings
    """
    resolver = get_event_resolver()
    return resolver.resolve_event(
        sport, home_team, away_team, commence_time, odds_api_id, provider_context
    )
