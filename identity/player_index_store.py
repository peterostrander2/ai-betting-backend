"""
Player Index Store - In-memory + optional Redis caching for player identity

TTL Rules:
- Roster: 6 hours
- Injuries: 30 minutes
- Odds/Props availability: 5 minutes
- Live state: 1 minute
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

from .name_normalizer import normalize_player_name, normalize_team_name, calculate_name_similarity

logger = logging.getLogger(__name__)

# TTL constants (in seconds)
TTL_ROSTER = 6 * 60 * 60        # 6 hours
TTL_INJURIES = 30 * 60          # 30 minutes
TTL_PROPS_AVAILABILITY = 5 * 60  # 5 minutes
TTL_LIVE_STATE = 60             # 1 minute


@dataclass
class CachedItem:
    """Wrapper for cached items with TTL."""
    value: Any
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class PlayerRecord:
    """Standardized player record for indexing."""
    canonical_id: str  # e.g., "NBA:BDL:123" or "NFL:NAME:patrick_mahomes|kc"
    normalized_name: str
    display_name: str
    team: str
    normalized_team: str
    sport: str
    position: Optional[str] = None

    # Provider IDs
    balldontlie_id: Optional[int] = None
    odds_api_id: Optional[str] = None
    playbook_id: Optional[str] = None
    espn_id: Optional[str] = None

    # Status
    injury_status: Optional[str] = None  # HEALTHY, OUT, QUESTIONABLE, DOUBTFUL, PROBABLE
    injury_note: Optional[str] = None
    is_active: bool = True

    # Metadata
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'canonical_id': self.canonical_id,
            'normalized_name': self.normalized_name,
            'display_name': self.display_name,
            'team': self.team,
            'normalized_team': self.normalized_team,
            'sport': self.sport,
            'position': self.position,
            'provider_ids': {
                'balldontlie': self.balldontlie_id,
                'odds_api': self.odds_api_id,
                'playbook': self.playbook_id,
                'espn': self.espn_id,
            },
            'injury_status': self.injury_status,
            'injury_note': self.injury_note,
            'is_active': self.is_active,
            'last_updated': self.last_updated,
        }


class PlayerIndexStore:
    """
    In-memory player index with TTL-based caching.

    Indexes:
    - by_canonical_id: canonical_id -> PlayerRecord
    - by_normalized_name: normalized_name -> List[PlayerRecord]
    - by_provider_id: (provider, id) -> PlayerRecord
    - by_team: normalized_team -> List[PlayerRecord]
    """

    def __init__(self):
        # Core indexes
        self._by_canonical_id: Dict[str, CachedItem] = {}
        self._by_normalized_name: Dict[str, CachedItem] = {}  # name -> list of records
        self._by_provider_id: Dict[tuple, CachedItem] = {}     # (provider, id) -> record
        self._by_team: Dict[str, CachedItem] = {}              # team -> list of records

        # Props availability cache (event_id -> set of available props)
        self._props_availability: Dict[str, CachedItem] = {}

        # Injury cache (sport -> list of injury records)
        self._injuries: Dict[str, CachedItem] = {}

        # Live game state cache
        self._live_state: Dict[str, CachedItem] = {}

        logger.info("PlayerIndexStore initialized")

    def _cleanup_expired(self):
        """Remove expired entries from all caches."""
        now = time.time()

        for cache in [
            self._by_canonical_id,
            self._by_normalized_name,
            self._by_provider_id,
            self._by_team,
            self._props_availability,
            self._injuries,
            self._live_state,
        ]:
            expired_keys = [k for k, v in cache.items() if v.expires_at < now]
            for k in expired_keys:
                del cache[k]

    def add_player(self, record: PlayerRecord, ttl: int = TTL_ROSTER) -> None:
        """Add or update a player record in all indexes."""
        expires_at = time.time() + ttl
        cached = CachedItem(value=record, expires_at=expires_at)

        # Index by canonical ID
        self._by_canonical_id[record.canonical_id] = cached

        # Index by normalized name (multiple players can have same name)
        name_key = record.normalized_name
        if name_key in self._by_normalized_name and not self._by_normalized_name[name_key].is_expired:
            existing = self._by_normalized_name[name_key].value
            # Update existing or add
            updated = [r for r in existing if r.canonical_id != record.canonical_id]
            updated.append(record)
            self._by_normalized_name[name_key] = CachedItem(value=updated, expires_at=expires_at)
        else:
            self._by_normalized_name[name_key] = CachedItem(value=[record], expires_at=expires_at)

        # Index by provider IDs
        if record.balldontlie_id:
            self._by_provider_id[('balldontlie', record.balldontlie_id)] = cached
        if record.odds_api_id:
            self._by_provider_id[('odds_api', record.odds_api_id)] = cached
        if record.playbook_id:
            self._by_provider_id[('playbook', record.playbook_id)] = cached
        if record.espn_id:
            self._by_provider_id[('espn', record.espn_id)] = cached

        # Index by team
        team_key = record.normalized_team
        if team_key in self._by_team and not self._by_team[team_key].is_expired:
            existing = self._by_team[team_key].value
            updated = [r for r in existing if r.canonical_id != record.canonical_id]
            updated.append(record)
            self._by_team[team_key] = CachedItem(value=updated, expires_at=expires_at)
        else:
            self._by_team[team_key] = CachedItem(value=[record], expires_at=expires_at)

    def get_by_canonical_id(self, canonical_id: str) -> Optional[PlayerRecord]:
        """Look up player by canonical ID."""
        cached = self._by_canonical_id.get(canonical_id)
        if cached and not cached.is_expired:
            return cached.value
        return None

    def get_by_name(self, name: str, team_hint: Optional[str] = None) -> List[PlayerRecord]:
        """
        Look up players by normalized name.

        Args:
            name: Player name (will be normalized)
            team_hint: Optional team to filter results

        Returns:
            List of matching PlayerRecord objects
        """
        normalized = normalize_player_name(name)
        cached = self._by_normalized_name.get(normalized)

        if not cached or cached.is_expired:
            return []

        results = cached.value

        # Filter by team if hint provided
        if team_hint:
            norm_team = normalize_team_name(team_hint)
            results = [r for r in results if r.normalized_team == norm_team or norm_team in r.normalized_team]

        return results

    def get_by_provider_id(self, provider: str, player_id: Any) -> Optional[PlayerRecord]:
        """Look up player by provider-specific ID."""
        key = (provider, player_id)
        cached = self._by_provider_id.get(key)
        if cached and not cached.is_expired:
            return cached.value
        return None

    def get_by_team(self, team: str) -> List[PlayerRecord]:
        """Get all players on a team."""
        normalized = normalize_team_name(team)
        cached = self._by_team.get(normalized)
        if cached and not cached.is_expired:
            return cached.value
        return []

    def search_players(
        self,
        query: str,
        sport: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 10
    ) -> List[PlayerRecord]:
        """
        Search for players by partial name match.

        Returns matches sorted by relevance.
        """
        from .name_normalizer import calculate_name_similarity

        normalized_query = normalize_player_name(query)
        results = []

        for name_key, cached in self._by_normalized_name.items():
            if cached.is_expired:
                continue

            similarity = calculate_name_similarity(normalized_query, name_key)
            if similarity > 0.5:  # Threshold for inclusion
                for record in cached.value:
                    # Apply filters
                    if sport and record.sport.upper() != sport.upper():
                        continue
                    if team:
                        norm_team = normalize_team_name(team)
                        if norm_team not in record.normalized_team:
                            continue

                    results.append((similarity, record))

        # Sort by similarity descending
        results.sort(key=lambda x: x[0], reverse=True)

        return [r[1] for r in results[:limit]]

    # Props availability methods
    def set_props_availability(
        self,
        event_id: str,
        available_props: Dict[str, List[str]]  # player_name -> [prop_types]
    ) -> None:
        """Cache which props are available for an event."""
        self._props_availability[event_id] = CachedItem(
            value=available_props,
            expires_at=time.time() + TTL_PROPS_AVAILABILITY
        )

    def get_props_availability(self, event_id: str) -> Optional[Dict[str, List[str]]]:
        """Get cached props availability for an event."""
        cached = self._props_availability.get(event_id)
        if cached and not cached.is_expired:
            return cached.value
        return None

    def is_prop_available(
        self,
        event_id: str,
        player_name: str,
        prop_type: str
    ) -> Optional[bool]:
        """
        Check if a specific prop is available.

        Returns:
            True if available, False if not, None if unknown (not cached)
        """
        availability = self.get_props_availability(event_id)
        if availability is None:
            return None

        normalized = normalize_player_name(player_name)

        # Check exact match
        if normalized in availability:
            return prop_type.lower() in [p.lower() for p in availability[normalized]]

        # Check partial matches
        for cached_name, props in availability.items():
            if calculate_name_similarity(normalized, cached_name) > 0.85:
                return prop_type.lower() in [p.lower() for p in props]

        return False

    # Injury methods
    def set_injuries(self, sport: str, injuries: List[Dict[str, Any]]) -> None:
        """Cache injury list for a sport."""
        self._injuries[sport.upper()] = CachedItem(
            value=injuries,
            expires_at=time.time() + TTL_INJURIES
        )

        # Also update individual player injury status
        for injury in injuries:
            player_name = injury.get('player_name', '')
            if not player_name:
                continue

            records = self.get_by_name(player_name, team_hint=injury.get('team'))
            for record in records:
                record.injury_status = injury.get('status', 'UNKNOWN')
                record.injury_note = injury.get('description', '')
                # Re-add with shorter TTL for injury data
                self.add_player(record, ttl=TTL_INJURIES)

    def get_injuries(self, sport: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached injuries for a sport."""
        cached = self._injuries.get(sport.upper())
        if cached and not cached.is_expired:
            return cached.value
        return None

    def get_player_injury_status(self, player_name: str, team_hint: Optional[str] = None) -> Optional[str]:
        """Get injury status for a specific player."""
        records = self.get_by_name(player_name, team_hint)
        if records:
            # Return most severe status if multiple matches
            statuses = [r.injury_status for r in records if r.injury_status]
            if statuses:
                severity = {'OUT': 4, 'DOUBTFUL': 3, 'QUESTIONABLE': 2, 'PROBABLE': 1, 'HEALTHY': 0}
                return max(statuses, key=lambda s: severity.get(s, 0))
        return None

    # Live state methods
    def set_live_state(self, event_id: str, state: Dict[str, Any]) -> None:
        """Cache live game state."""
        self._live_state[event_id] = CachedItem(
            value=state,
            expires_at=time.time() + TTL_LIVE_STATE
        )

    def get_live_state(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get cached live game state."""
        cached = self._live_state.get(event_id)
        if cached and not cached.is_expired:
            return cached.value
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        self._cleanup_expired()

        return {
            'players_by_id': len(self._by_canonical_id),
            'players_by_name': len(self._by_normalized_name),
            'players_by_provider': len(self._by_provider_id),
            'teams_indexed': len(self._by_team),
            'events_with_props': len(self._props_availability),
            'sports_with_injuries': len(self._injuries),
            'live_states_cached': len(self._live_state),
        }

    def clear(self) -> None:
        """Clear all caches."""
        self._by_canonical_id.clear()
        self._by_normalized_name.clear()
        self._by_provider_id.clear()
        self._by_team.clear()
        self._props_availability.clear()
        self._injuries.clear()
        self._live_state.clear()
        logger.info("PlayerIndexStore cleared")


# Singleton instance
_player_index: Optional[PlayerIndexStore] = None


def get_player_index() -> PlayerIndexStore:
    """Get the singleton PlayerIndexStore instance."""
    global _player_index
    if _player_index is None:
        _player_index = PlayerIndexStore()
    return _player_index
