"""
Player Resolver - Main entry point for Unified Player Identity Resolution

Canonical Player ID Rule:
- NBA with BallDontLie: NBA:BDL:{bdl_player_id}
- Otherwise: {SPORT}:NAME:{normalized_name}|{team_hint}

This resolver must be used in:
- Prop generation
- Injury validation
- Grading/auto-grader
- Logging + learning loop
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .name_normalizer import (
    normalize_player_name,
    normalize_team_name,
    calculate_name_similarity,
    get_name_variants,
)
from .player_index_store import (
    PlayerIndexStore,
    PlayerRecord,
    get_player_index,
    TTL_ROSTER,
    TTL_INJURIES,
)

logger = logging.getLogger(__name__)

# BallDontLie GOAT API Key
BALLDONTLIE_API_KEY = os.getenv(
    "BALLDONTLIE_API_KEY",
    "1cbb16a0-3060-4caf-ac17-ff11352540bc"  # GOAT tier key
)
BALLDONTLIE_BASE_URL = "https://api.balldontlie.io/v1"


class MatchMethod(str, Enum):
    """How the player was matched."""
    EXACT = "exact"
    CANONICAL_ID = "canonical_id"
    PROVIDER_ID = "provider_id"
    NORMALIZED_NAME = "normalized_name"
    FUZZY_NAME = "fuzzy_name"
    VARIANT_MATCH = "variant_match"
    API_LOOKUP = "api_lookup"
    BEST_GUESS = "best_guess"
    NOT_FOUND = "not_found"


@dataclass
class ResolvedPlayer:
    """Result of player resolution."""
    canonical_player_id: str
    display_name: str
    team: str
    sport: str

    # Provider ID mappings
    provider_ids: Dict[str, Any] = field(default_factory=dict)

    # Resolution metadata
    confidence: float = 0.0  # 0.0 to 1.0
    match_method: MatchMethod = MatchMethod.NOT_FOUND
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    # Player status
    position: Optional[str] = None
    injury_status: Optional[str] = None  # HEALTHY, OUT, QUESTIONABLE, DOUBTFUL, PROBABLE
    injury_note: Optional[str] = None
    is_active: bool = True

    # Prop availability (set after checking)
    prop_available: Optional[bool] = None
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'canonical_player_id': self.canonical_player_id,
            'display_name': self.display_name,
            'team': self.team,
            'sport': self.sport,
            'provider_ids': self.provider_ids,
            'confidence': self.confidence,
            'match_method': self.match_method.value,
            'candidates': self.candidates,
            'position': self.position,
            'injury_status': self.injury_status,
            'injury_note': self.injury_note,
            'is_active': self.is_active,
            'prop_available': self.prop_available,
            'blocked_reason': self.blocked_reason,
        }

    @property
    def is_resolved(self) -> bool:
        return self.match_method != MatchMethod.NOT_FOUND and self.confidence > 0.5

    @property
    def is_blocked(self) -> bool:
        return self.blocked_reason is not None


class PlayerResolver:
    """
    Unified Player Identity Resolver.

    Uses multiple strategies to match player names to canonical IDs:
    1. Cache lookup (fastest)
    2. Provider ID lookup
    3. Normalized name match
    4. Fuzzy name match
    5. API lookup (BallDontLie for NBA)
    """

    def __init__(self, index: Optional[PlayerIndexStore] = None):
        self.index = index or get_player_index()
        self._http_client = None

    async def _get_client(self):
        """Get or create HTTP client."""
        if not HTTPX_AVAILABLE:
            return None
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client and HTTPX_AVAILABLE:
            await self._http_client.aclose()
            self._http_client = None

    def _generate_canonical_id(
        self,
        sport: str,
        normalized_name: str,
        team_hint: Optional[str],
        bdl_id: Optional[int] = None
    ) -> str:
        """Generate canonical player ID."""
        sport_upper = sport.upper()

        # NBA with BallDontLie ID
        if sport_upper == "NBA" and bdl_id:
            return f"NBA:BDL:{bdl_id}"

        # Fallback: name-based ID
        team_part = normalize_team_name(team_hint) if team_hint else "unknown"
        team_part = team_part.replace(" ", "_")
        name_part = normalized_name.replace(" ", "_")
        return f"{sport_upper}:NAME:{name_part}|{team_part}"

    async def resolve_player(
        self,
        sport: str,
        raw_name: str,
        team_hint: Optional[str] = None,
        event_id: Optional[str] = None,
        provider_context: Optional[Dict[str, Any]] = None
    ) -> ResolvedPlayer:
        """
        Resolve a player name to a canonical identity.

        Args:
            sport: Sport code (NBA, NFL, MLB, NHL)
            raw_name: Raw player name from source
            team_hint: Optional team to disambiguate (e.g., "Lakers")
            event_id: Optional event ID for prop availability check
            provider_context: Optional dict with provider-specific IDs

        Returns:
            ResolvedPlayer with canonical ID and metadata
        """
        sport_upper = sport.upper()
        normalized_name = normalize_player_name(raw_name)
        normalized_team = normalize_team_name(team_hint) if team_hint else None
        candidates = []

        provider_context = provider_context or {}

        # Strategy 1: Check provider ID if provided
        if provider_context:
            for provider, pid in provider_context.items():
                if pid:
                    record = self.index.get_by_provider_id(provider, pid)
                    if record and record.sport.upper() == sport_upper:
                        return self._record_to_resolved(
                            record,
                            MatchMethod.PROVIDER_ID,
                            confidence=1.0,
                            candidates=[]
                        )

        # Strategy 2: Exact name match in cache
        exact_matches = self.index.get_by_name(normalized_name, team_hint=team_hint)
        if exact_matches:
            # Filter by sport
            sport_matches = [r for r in exact_matches if r.sport.upper() == sport_upper]
            if len(sport_matches) == 1:
                return self._record_to_resolved(
                    sport_matches[0],
                    MatchMethod.EXACT,
                    confidence=1.0,
                    candidates=[r.to_dict() for r in sport_matches]
                )
            elif len(sport_matches) > 1:
                # Multiple matches - try to disambiguate by team
                if normalized_team:
                    team_filtered = [
                        r for r in sport_matches
                        if normalized_team in r.normalized_team
                    ]
                    if len(team_filtered) == 1:
                        return self._record_to_resolved(
                            team_filtered[0],
                            MatchMethod.NORMALIZED_NAME,
                            confidence=0.95,
                            candidates=[r.to_dict() for r in sport_matches]
                        )
                    sport_matches = team_filtered or sport_matches

                # Still ambiguous - return best guess with candidates
                candidates = [r.to_dict() for r in sport_matches]
                return self._record_to_resolved(
                    sport_matches[0],
                    MatchMethod.BEST_GUESS,
                    confidence=0.7,
                    candidates=candidates
                )

        # Strategy 3: Fuzzy name search in cache
        fuzzy_results = self.index.search_players(
            normalized_name,
            sport=sport_upper,
            team=team_hint,
            limit=5
        )
        if fuzzy_results:
            best = fuzzy_results[0]
            similarity = calculate_name_similarity(normalized_name, best.normalized_name)
            candidates = [r.to_dict() for r in fuzzy_results]

            if similarity >= 0.9:
                return self._record_to_resolved(
                    best,
                    MatchMethod.FUZZY_NAME,
                    confidence=similarity,
                    candidates=candidates
                )
            elif similarity >= 0.7:
                return self._record_to_resolved(
                    best,
                    MatchMethod.BEST_GUESS,
                    confidence=similarity,
                    candidates=candidates
                )

        # Strategy 4: API lookup (NBA -> BallDontLie)
        # For NBA, ALWAYS try to get BallDontLie player ID for accurate grading
        if sport_upper == "NBA":
            bdl_result = await self._lookup_balldontlie(normalized_name, team_hint)
            if bdl_result:
                # Cache the result
                self.index.add_player(bdl_result, ttl=TTL_ROSTER)
                return self._record_to_resolved(
                    bdl_result,
                    MatchMethod.API_LOOKUP,
                    confidence=0.95,
                    candidates=[]
                )
            else:
                logger.info("BallDontLie lookup returned no results for: %s", normalized_name)

        # Strategy 5: Create new record with name-based canonical ID
        canonical_id = self._generate_canonical_id(
            sport_upper,
            normalized_name,
            team_hint
        )

        new_record = PlayerRecord(
            canonical_id=canonical_id,
            normalized_name=normalized_name,
            display_name=raw_name,
            team=team_hint or "Unknown",
            normalized_team=normalized_team or "unknown",
            sport=sport_upper,
        )
        self.index.add_player(new_record, ttl=TTL_ROSTER // 2)  # Shorter TTL for unverified

        return self._record_to_resolved(
            new_record,
            MatchMethod.BEST_GUESS if candidates else MatchMethod.NOT_FOUND,
            confidence=0.5 if candidates else 0.3,
            candidates=candidates
        )

    async def _lookup_balldontlie(
        self,
        normalized_name: str,
        team_hint: Optional[str] = None
    ) -> Optional[PlayerRecord]:
        """
        Look up player in BallDontLie API.

        Uses the GOAT tier subscription key for premium access.
        """
        if not BALLDONTLIE_API_KEY:
            logger.warning("BallDontLie API key not configured")
            return None

        if not HTTPX_AVAILABLE:
            logger.warning("httpx not available for BallDontLie lookup")
            return None

        try:
            client = await self._get_client()
            if not client:
                return None

            # Search by name
            search_term = normalized_name.replace(" ", "%20")
            url = f"{BALLDONTLIE_BASE_URL}/players?search={search_term}"

            response = await client.get(
                url,
                headers={"Authorization": BALLDONTLIE_API_KEY}
            )

            if response.status_code != 200:
                logger.warning(f"BallDontLie API error: {response.status_code}")
                return None

            data = response.json()
            players = data.get("data", [])

            if not players:
                return None

            # Filter by team if hint provided
            if team_hint:
                normalized_team = normalize_team_name(team_hint)
                for player in players:
                    team_data = player.get("team", {})
                    player_team = team_data.get("full_name", "") or team_data.get("name", "")
                    if normalized_team in normalize_team_name(player_team):
                        return self._bdl_to_record(player)

            # Return first result if no team filter or no team match
            return self._bdl_to_record(players[0])

        except Exception as e:
            logger.exception(f"BallDontLie lookup failed: {e}")
            return None

    def _bdl_to_record(self, bdl_player: Dict[str, Any]) -> PlayerRecord:
        """Convert BallDontLie player data to PlayerRecord."""
        player_id = bdl_player.get("id")
        first_name = bdl_player.get("first_name", "")
        last_name = bdl_player.get("last_name", "")
        display_name = f"{first_name} {last_name}".strip()

        team_data = bdl_player.get("team", {})
        team_name = team_data.get("full_name", "") or team_data.get("name", "Unknown")

        position = bdl_player.get("position", "")

        canonical_id = f"NBA:BDL:{player_id}"
        normalized_name = normalize_player_name(display_name)
        normalized_team = normalize_team_name(team_name)

        return PlayerRecord(
            canonical_id=canonical_id,
            normalized_name=normalized_name,
            display_name=display_name,
            team=team_name,
            normalized_team=normalized_team,
            sport="NBA",
            position=position,
            balldontlie_id=player_id,
            is_active=True,
        )

    def _record_to_resolved(
        self,
        record: PlayerRecord,
        match_method: MatchMethod,
        confidence: float,
        candidates: List[Dict[str, Any]]
    ) -> ResolvedPlayer:
        """Convert PlayerRecord to ResolvedPlayer."""
        return ResolvedPlayer(
            canonical_player_id=record.canonical_id,
            display_name=record.display_name,
            team=record.team,
            sport=record.sport,
            provider_ids={
                'balldontlie': record.balldontlie_id,
                'odds_api': record.odds_api_id,
                'playbook': record.playbook_id,
                'espn': record.espn_id,
            },
            confidence=confidence,
            match_method=match_method,
            candidates=candidates,
            position=record.position,
            injury_status=record.injury_status,
            injury_note=record.injury_note,
            is_active=record.is_active,
        )

    async def check_prop_availability(
        self,
        resolved: ResolvedPlayer,
        prop_type: str,
        event_id: str
    ) -> ResolvedPlayer:
        """
        Check if a prop is available for the resolved player.

        Updates the resolved player with availability info.
        """
        # Check cache first
        is_available = self.index.is_prop_available(
            event_id,
            resolved.display_name,
            prop_type
        )

        if is_available is False:
            resolved.prop_available = False
            resolved.blocked_reason = "PROP_NOT_LISTED"
            return resolved

        if is_available is True:
            resolved.prop_available = True
            return resolved

        # Unknown - leave as None (will need API check)
        resolved.prop_available = None
        return resolved

    async def check_injury_guard(
        self,
        resolved: ResolvedPlayer,
        allow_questionable: bool = True
    ) -> ResolvedPlayer:
        """
        Apply injury guard rules.

        Rules:
        - OUT: block pick
        - DOUBTFUL: block pick
        - QUESTIONABLE: block for TITANIUM tier (unless allow_questionable)
        - PROBABLE/HEALTHY: allow
        """
        status = resolved.injury_status

        if not status or status.upper() in ["HEALTHY", "ACTIVE", ""]:
            return resolved

        status_upper = status.upper()

        if status_upper == "OUT":
            resolved.blocked_reason = "PLAYER_OUT"
        elif status_upper == "DOUBTFUL":
            resolved.blocked_reason = "PLAYER_DOUBTFUL"
        elif status_upper == "QUESTIONABLE" and not allow_questionable:
            resolved.blocked_reason = "PLAYER_QUESTIONABLE"
        # PROBABLE is allowed

        return resolved


# Singleton instance
_player_resolver: Optional[PlayerResolver] = None


def get_player_resolver() -> PlayerResolver:
    """Get the singleton PlayerResolver instance."""
    global _player_resolver
    if _player_resolver is None:
        _player_resolver = PlayerResolver()
    return _player_resolver


async def resolve_player(
    sport: str,
    raw_name: str,
    team_hint: Optional[str] = None,
    event_id: Optional[str] = None,
    provider_context: Optional[Dict[str, Any]] = None
) -> ResolvedPlayer:
    """
    Convenience function to resolve a player.

    This is the main entry point for player resolution.
    """
    resolver = get_player_resolver()
    return await resolver.resolve_player(
        sport=sport,
        raw_name=raw_name,
        team_hint=team_hint,
        event_id=event_id,
        provider_context=provider_context
    )


# Synchronous wrapper for non-async contexts
def resolve_player_sync(
    sport: str,
    raw_name: str,
    team_hint: Optional[str] = None,
    event_id: Optional[str] = None,
    provider_context: Optional[Dict[str, Any]] = None
) -> ResolvedPlayer:
    """
    Synchronous wrapper for resolve_player.

    Note: This creates a new event loop if needed, so prefer the async version.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're in an async context but called synchronously
        # Create a new thread to run the coroutine
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                resolve_player(sport, raw_name, team_hint, event_id, provider_context)
            )
            return future.result()
    else:
        return asyncio.run(
            resolve_player(sport, raw_name, team_hint, event_id, provider_context)
        )
