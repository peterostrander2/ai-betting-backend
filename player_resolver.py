"""
PLAYER_RESOLVER.PY - Unified Player ID Resolution
==================================================
v1.0 - Production hardened player name matching

Maps player names across:
- BallDontLie API
- Odds API
- Playbook API
- Sportsbooks

This ensures consistent player identification for:
- Grading picks (matching prediction player to actual stats)
- Prop matching (matching player names across different APIs)
- Canonical ID storage in pick_logger

IMPORTANT: This is the single source of truth for player name normalization.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import hashlib

# Configure logging
logger = logging.getLogger("player_resolver")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)


# =============================================================================
# ENGINE VERSION
# =============================================================================
ENGINE_VERSION = "1.0"


# =============================================================================
# KNOWN PLAYER MAPPINGS
# =============================================================================

# Manual mappings for players with inconsistent naming across APIs
# Format: {canonical_name: [alternate_names]}
KNOWN_PLAYER_ALIASES = {
    # NBA
    "LeBron James": ["L. James", "James, LeBron", "Lebron James"],
    "Anthony Davis": ["A. Davis", "Davis, Anthony", "AD"],
    "Stephen Curry": ["S. Curry", "Steph Curry", "Curry, Stephen"],
    "Giannis Antetokounmpo": ["G. Antetokounmpo", "Giannis", "The Greek Freak"],
    "Kevin Durant": ["K. Durant", "KD", "Durant, Kevin"],
    "Luka Doncic": ["L. Doncic", "Luka", "Doncic, Luka"],
    "Ja Morant": ["J. Morant", "Morant, Ja"],
    "Jayson Tatum": ["J. Tatum", "Tatum, Jayson"],
    "Nikola Jokic": ["N. Jokic", "Jokic", "The Joker"],
    "Joel Embiid": ["J. Embiid", "Embiid, Joel"],
    "Devin Booker": ["D. Booker", "Booker, Devin"],
    "Donovan Mitchell": ["D. Mitchell", "Mitchell, Donovan"],
    "Shai Gilgeous-Alexander": ["S. Gilgeous-Alexander", "SGA", "Shai"],
    "Damian Lillard": ["D. Lillard", "Dame", "Lillard, Damian"],
    "Kyrie Irving": ["K. Irving", "Kyrie", "Irving, Kyrie"],
    "Jaylen Brown": ["J. Brown", "Brown, Jaylen"],
    "De'Aaron Fox": ["D. Fox", "DeAaron Fox", "Fox, De'Aaron"],
    "Trae Young": ["T. Young", "Young, Trae"],
    "Zion Williamson": ["Z. Williamson", "Zion", "Williamson, Zion"],
    "Paolo Banchero": ["P. Banchero", "Paolo", "Banchero, Paolo"],
    "Victor Wembanyama": ["V. Wembanyama", "Wemby", "Wembanyama"],

    # NFL
    "Patrick Mahomes": ["P. Mahomes", "Mahomes", "Mahomes II"],
    "Josh Allen": ["J. Allen", "Allen, Josh"],
    "Lamar Jackson": ["L. Jackson", "Jackson, Lamar"],
    "Jalen Hurts": ["J. Hurts", "Hurts, Jalen"],
    "Justin Jefferson": ["J. Jefferson", "Jefferson, Justin"],
    "Tyreek Hill": ["T. Hill", "Hill, Tyreek", "Cheetah"],
    "Travis Kelce": ["T. Kelce", "Kelce, Travis"],
    "Davante Adams": ["D. Adams", "Adams, Davante"],
    "CeeDee Lamb": ["C. Lamb", "Lamb, CeeDee", "CD Lamb"],

    # MLB
    "Shohei Ohtani": ["S. Ohtani", "Ohtani, Shohei", "Ohtani"],
    "Mike Trout": ["M. Trout", "Trout, Mike"],
    "Mookie Betts": ["M. Betts", "Betts, Mookie"],
    "Aaron Judge": ["A. Judge", "Judge, Aaron"],
    "Ronald Acuna Jr.": ["R. Acuna", "Acuna Jr.", "Ronald Acuna"],
    "Juan Soto": ["J. Soto", "Soto, Juan"],
    "Freddie Freeman": ["F. Freeman", "Freeman, Freddie"],

    # NHL
    "Connor McDavid": ["C. McDavid", "McDavid, Connor"],
    "Nathan MacKinnon": ["N. MacKinnon", "MacKinnon, Nathan"],
    "Auston Matthews": ["A. Matthews", "Matthews, Auston"],
    "Leon Draisaitl": ["L. Draisaitl", "Draisaitl, Leon"],
    "Nikita Kucherov": ["N. Kucherov", "Kucherov, Nikita"],
    "David Pastrnak": ["D. Pastrnak", "Pastrnak, David"],
}

# Build reverse lookup
_ALIAS_TO_CANONICAL = {}
for canonical, aliases in KNOWN_PLAYER_ALIASES.items():
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical


# =============================================================================
# KNOWN PLAYER IDS BY PROVIDER
# =============================================================================

# BallDontLie IDs for common NBA players
BALLDONTLIE_IDS = {
    "LeBron James": 237,
    "Anthony Davis": 10,
    "Stephen Curry": 115,
    "Kevin Durant": 140,
    "Giannis Antetokounmpo": 15,
    "Luka Doncic": 132,
    "Nikola Jokic": 246,
    "Joel Embiid": 145,
    "Jayson Tatum": 434,
    "Ja Morant": 246,
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PlayerInfo:
    """Resolved player information."""
    canonical_id: str
    canonical_name: str
    sport: str
    team: Optional[str] = None
    provider_ids: Dict[str, Any] = None

    def __post_init__(self):
        if self.provider_ids is None:
            self.provider_ids = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "canonical_name": self.canonical_name,
            "sport": self.sport,
            "team": self.team,
            "provider_ids": self.provider_ids
        }


# =============================================================================
# NAME NORMALIZATION
# =============================================================================

def normalize_player_name(name: str) -> str:
    """
    Normalize a player name for comparison.

    - Lowercase
    - Remove Jr., Sr., III, II, IV suffixes
    - Remove periods and extra spaces
    - Handle "Last, First" format
    """
    if not name:
        return ""

    # Lowercase and strip
    name = name.lower().strip()

    # Handle "Last, First" format
    if "," in name:
        parts = name.split(",")
        if len(parts) == 2:
            name = f"{parts[1].strip()} {parts[0].strip()}"

    # Remove suffixes
    suffixes = [" jr.", " sr.", " iii", " ii", " iv", " jr", " sr"]
    for suffix in suffixes:
        name = name.replace(suffix, "")

    # Remove periods and normalize spaces
    name = name.replace(".", "").replace("'", "").replace("-", " ")
    name = " ".join(name.split())

    return name


def extract_last_name(name: str) -> str:
    """Extract last name from a player name."""
    normalized = normalize_player_name(name)
    parts = normalized.split()
    return parts[-1] if parts else ""


def extract_first_name(name: str) -> str:
    """Extract first name from a player name."""
    normalized = normalize_player_name(name)
    parts = normalized.split()
    return parts[0] if parts else ""


def extract_initials(name: str) -> str:
    """Extract initials from a player name."""
    normalized = normalize_player_name(name)
    parts = normalized.split()
    return "".join(p[0].upper() for p in parts if p)


# =============================================================================
# CANONICAL ID GENERATION
# =============================================================================

def generate_canonical_id(name: str, sport: str, team: str = None) -> str:
    """
    Generate a canonical ID for a player.

    Format: {sport}_{normalized_name_hash}
    """
    normalized = normalize_player_name(name)
    hash_input = f"{sport.upper()}_{normalized}"
    if team:
        hash_input += f"_{team.lower()}"

    # Create short hash
    hash_val = hashlib.md5(hash_input.encode()).hexdigest()[:8]

    # Create readable prefix
    last_name = extract_last_name(name)
    return f"{sport.upper()}_{last_name}_{hash_val}"


# =============================================================================
# PLAYER RESOLVER CLASS
# =============================================================================

class PlayerResolver:
    """
    Unified player ID resolver.

    Maps player names across: BallDontLie, Odds API, Playbook, Sportsbooks
    """

    VERSION = ENGINE_VERSION

    def __init__(self):
        self._cache: Dict[str, PlayerInfo] = {}
        logger.info("PlayerResolver v%s initialized", self.VERSION)

    def resolve_player(
        self,
        name: str,
        sport: str,
        team: str = None,
        context: Dict[str, Any] = None
    ) -> Optional[PlayerInfo]:
        """
        Resolve a player name to canonical player info.

        Args:
            name: Player name (any format)
            sport: Sport code (NBA, NFL, etc.)
            team: Optional team name for disambiguation
            context: Optional context with provider-specific IDs

        Returns:
            PlayerInfo with canonical_id or None if not resolved
        """
        if not name:
            return None

        context = context or {}
        sport = sport.upper()

        # Check cache first
        cache_key = f"{sport}_{normalize_player_name(name)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try known aliases first
        normalized = normalize_player_name(name)
        canonical_name = _ALIAS_TO_CANONICAL.get(normalized, None)

        if canonical_name:
            # Known player - use canonical name
            player = PlayerInfo(
                canonical_id=generate_canonical_id(canonical_name, sport, team),
                canonical_name=canonical_name,
                sport=sport,
                team=team,
                provider_ids={}
            )

            # Add known provider IDs
            if canonical_name in BALLDONTLIE_IDS:
                player.provider_ids["balldontlie"] = BALLDONTLIE_IDS[canonical_name]

        else:
            # Unknown player - create new canonical entry
            # Use the input name but normalized
            title_name = " ".join(w.capitalize() for w in normalized.split())
            player = PlayerInfo(
                canonical_id=generate_canonical_id(name, sport, team),
                canonical_name=title_name,
                sport=sport,
                team=team,
                provider_ids={}
            )

        # Add any context-provided IDs
        for provider, pid in context.items():
            if pid:
                player.provider_ids[provider] = pid

        # Cache the result
        self._cache[cache_key] = player

        return player

    def resolve_player_id(
        self,
        name: str,
        sport: str,
        team: str = None,
        context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Resolve a player name to canonical ID only.

        Convenience method that returns just the ID string.
        """
        player = self.resolve_player(name, sport, team, context)
        return player.canonical_id if player else None

    def get_player_info(self, canonical_id: str) -> Optional[PlayerInfo]:
        """
        Get player info by canonical ID.

        Returns full player info with all provider mappings.
        """
        # Search cache by canonical_id
        for player in self._cache.values():
            if player.canonical_id == canonical_id:
                return player
        return None

    def match_players(
        self,
        name1: str,
        name2: str,
        threshold: float = 0.85
    ) -> Tuple[bool, float]:
        """
        Check if two player names refer to the same player.

        Args:
            name1: First player name
            name2: Second player name
            threshold: Similarity threshold (0-1)

        Returns:
            Tuple of (is_match: bool, similarity: float)
        """
        norm1 = normalize_player_name(name1)
        norm2 = normalize_player_name(name2)

        # Exact match
        if norm1 == norm2:
            return True, 1.0

        # Check if both resolve to same canonical name
        canonical1 = _ALIAS_TO_CANONICAL.get(norm1)
        canonical2 = _ALIAS_TO_CANONICAL.get(norm2)

        if canonical1 and canonical2 and canonical1 == canonical2:
            return True, 1.0

        # Last name match
        last1 = extract_last_name(name1)
        last2 = extract_last_name(name2)

        if last1 == last2:
            # Same last name - check first name/initial
            first1 = extract_first_name(name1)
            first2 = extract_first_name(name2)

            if first1 == first2:
                return True, 0.95

            # Check if one is initial of the other
            if len(first1) == 1 and first2.startswith(first1):
                return True, 0.90
            if len(first2) == 1 and first1.startswith(first2):
                return True, 0.90

        # Calculate similarity score
        similarity = _calculate_similarity(norm1, norm2)

        return similarity >= threshold, similarity

    def find_best_match(
        self,
        name: str,
        candidates: List[str],
        threshold: float = 0.75
    ) -> Optional[Tuple[str, float]]:
        """
        Find best matching name from a list of candidates.

        Args:
            name: Name to match
            candidates: List of candidate names
            threshold: Minimum similarity threshold

        Returns:
            Tuple of (best_match, similarity) or None if no match above threshold
        """
        if not candidates:
            return None

        best_match = None
        best_similarity = 0

        for candidate in candidates:
            is_match, similarity = self.match_players(name, candidate, threshold)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = candidate

        if best_similarity >= threshold:
            return best_match, best_similarity

        return None


def _calculate_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaro-Winkler similarity between two strings.

    Returns value between 0 and 1.
    """
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)

    if len1 == 0 or len2 == 0:
        return 0.0

    # Match window
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    # Find matches
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)

        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    # Count transpositions
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3

    # Jaro-Winkler prefix bonus
    prefix = 0
    for i in range(min(4, min(len1, len2))):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break

    return jaro + prefix * 0.1 * (1 - jaro)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_player_resolver_instance = None


def get_player_resolver() -> PlayerResolver:
    """Get or create singleton PlayerResolver instance."""
    global _player_resolver_instance
    if _player_resolver_instance is None:
        _player_resolver_instance = PlayerResolver()
    return _player_resolver_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def resolve_player_name(
    name: str,
    sport: str,
    team: str = None
) -> Optional[str]:
    """
    Convenience function to resolve a player name to canonical ID.

    Args:
        name: Player name in any format
        sport: Sport code
        team: Optional team for disambiguation

    Returns:
        Canonical player ID or None
    """
    resolver = get_player_resolver()
    return resolver.resolve_player_id(name, sport, team)


def match_player_stats(
    player_name: str,
    stat_type: str,
    all_stats: List[Dict[str, Any]]
) -> Optional[float]:
    """
    Find a player's actual stat value from statlines using fuzzy matching.

    Args:
        player_name: Player name to match
        stat_type: Stat type (points, rebounds, etc.)
        all_stats: List of stat dictionaries with 'player_name' and stat values

    Returns:
        Actual stat value or None if not found
    """
    resolver = get_player_resolver()

    # Build candidate list
    candidates = [s.get("player_name", "") for s in all_stats if s.get("player_name")]

    # Find best match
    result = resolver.find_best_match(player_name, candidates, threshold=0.75)

    if result:
        matched_name, similarity = result

        # Find the stat record
        for stat in all_stats:
            if stat.get("player_name") == matched_name:
                # Try to get the stat value
                stat_key = stat_type.replace("player_", "")

                if stat_key in stat:
                    return stat[stat_key]
                elif stat_key in stat.get("stats", {}):
                    return stat["stats"][stat_key]

                # Try common mappings
                stat_mappings = {
                    "points": ["pts", "points", "PTS"],
                    "rebounds": ["reb", "rebounds", "REB", "total_rebounds"],
                    "assists": ["ast", "assists", "AST"],
                    "threes": ["fg3m", "three_pointers_made", "3PM"],
                    "steals": ["stl", "steals", "STL"],
                    "blocks": ["blk", "blocks", "BLK"],
                }

                for key in stat_mappings.get(stat_key, []):
                    if key in stat:
                        return stat[key]
                    if key in stat.get("stats", {}):
                        return stat["stats"][key]

    return None


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PLAYER RESOLVER v1.0 - TEST")
    print("=" * 60)

    resolver = get_player_resolver()

    # Test 1: Known player with alias
    print("\nTest 1: Known player - 'L. James'")
    player = resolver.resolve_player("L. James", "NBA", "Lakers")
    if player:
        print(f"  Canonical ID: {player.canonical_id}")
        print(f"  Canonical Name: {player.canonical_name}")
        print(f"  Provider IDs: {player.provider_ids}")

    # Test 2: Player matching
    print("\nTest 2: Matching 'LeBron James' vs 'L. James'")
    is_match, similarity = resolver.match_players("LeBron James", "L. James")
    print(f"  Match: {is_match}, Similarity: {similarity:.2f}")

    # Test 3: Unknown player
    print("\nTest 3: Unknown player - 'John Smith'")
    player = resolver.resolve_player("John Smith", "NBA", "Lakers")
    if player:
        print(f"  Canonical ID: {player.canonical_id}")
        print(f"  Canonical Name: {player.canonical_name}")

    # Test 4: Find best match from list
    print("\nTest 4: Find best match")
    candidates = ["LeBron James", "Kevin Durant", "Stephen Curry"]
    result = resolver.find_best_match("L. James", candidates)
    if result:
        print(f"  Best match: {result[0]} (similarity: {result[1]:.2f})")

    # Test 5: Name normalization
    print("\nTest 5: Name normalization")
    test_names = ["LeBron James Jr.", "CURRY, STEPHEN", "Giannis Antetokounmpo"]
    for name in test_names:
        normalized = normalize_player_name(name)
        print(f"  '{name}' -> '{normalized}'")

    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)
