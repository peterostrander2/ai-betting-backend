"""
Tests for the Unified Player Identity Resolver

Tests cover:
- Name normalizer
- Resolver exact match
- Resolver ambiguous match
- Prop availability guard
- Grading uses canonical ID
"""

import pytest

# Skip if pytest-asyncio isn't available in this environment
pytest.importorskip("pytest_asyncio")
import asyncio
from identity.name_normalizer import (
    normalize_player_name,
    normalize_team_name,
    get_name_variants,
    calculate_name_similarity,
    extract_last_name,
    extract_first_name,
)
from identity.player_index_store import (
    PlayerIndexStore,
    PlayerRecord,
    get_player_index,
)
from identity.player_resolver import (
    PlayerResolver,
    ResolvedPlayer,
    MatchMethod,
    resolve_player,
    get_player_resolver,
)


# =============================================================================
# NAME NORMALIZER TESTS
# =============================================================================

class TestNameNormalizer:
    """Tests for name normalization functions."""

    def test_basic_normalization(self):
        """Test basic name normalization rules."""
        assert normalize_player_name("LeBron James") == "lebron james"
        assert normalize_player_name("LEBRON JAMES") == "lebron james"
        assert normalize_player_name("  LeBron   James  ") == "lebron james"

    def test_suffix_removal(self):
        """Test suffix removal (Jr., Sr., II, III, IV)."""
        assert normalize_player_name("Gary Payton Jr.") == "gary payton"
        assert normalize_player_name("Gary Payton Jr") == "gary payton"
        assert normalize_player_name("Tim Hardaway Jr.") == "tim hardaway"
        assert normalize_player_name("Larry Nance Jr.") == "larry nance"
        assert normalize_player_name("Patrick Ewing III") == "patrick ewing"
        assert normalize_player_name("Player Name II") == "player name"
        assert normalize_player_name("Player Name IV") == "player name"

    def test_punctuation_removal(self):
        """Test punctuation handling."""
        assert normalize_player_name("D'Angelo Russell") == "dangelo russell"
        assert normalize_player_name("O'Neal") == "oneal"
        assert normalize_player_name("De'Aaron Fox") == "deaaron fox"

    def test_accent_removal(self):
        """Test accent/diacritic removal."""
        assert normalize_player_name("Nikola Jokić") == "nikola jokic"
        assert normalize_player_name("Luka Dončić") == "luka doncic"
        assert normalize_player_name("José Calderón") == "jose calderon"

    def test_hyphen_handling(self):
        """Test hyphenated names."""
        assert normalize_player_name("Shai Gilgeous-Alexander") == "shai gilgeous alexander"
        assert normalize_player_name("Karl-Anthony Towns") == "karl anthony towns"

    def test_nickname_expansion(self):
        """Test nickname expansion."""
        assert normalize_player_name("LBJ") == "lebron james"
        assert normalize_player_name("KD") == "kevin durant"
        assert normalize_player_name("Steph") == "stephen curry"
        assert normalize_player_name("Greek Freak") == "giannis antetokounmpo"
        assert normalize_player_name("Wemby") == "victor wembanyama"

    def test_nickname_disabled(self):
        """Test nickname expansion can be disabled."""
        assert normalize_player_name("LBJ", expand_nicknames=False) == "lbj"

    def test_name_variants(self):
        """Test name variant generation."""
        variants = get_name_variants("LeBron James")
        assert "lebron james" in variants
        assert "l james" in variants
        assert "lebron j" in variants
        assert "james" in variants
        assert "lebron" in variants
        assert "james lebron" in variants

    def test_name_similarity(self):
        """Test name similarity calculation."""
        # Exact match
        assert calculate_name_similarity("LeBron James", "lebron james") == 1.0

        # Variant match
        assert calculate_name_similarity("L. James", "LeBron James") >= 0.85

        # High similarity
        assert calculate_name_similarity("Lebron James", "LeBron Jamess") >= 0.8

        # Low similarity
        assert calculate_name_similarity("LeBron James", "Steph Curry") < 0.5

    def test_extract_names(self):
        """Test first/last name extraction."""
        assert extract_last_name("LeBron James") == "james"
        assert extract_first_name("LeBron James") == "lebron"
        assert extract_last_name("Giannis Antetokounmpo") == "antetokounmpo"


class TestTeamNormalizer:
    """Tests for team name normalization."""

    def test_basic_team_normalization(self):
        """Test basic team normalization."""
        assert normalize_team_name("Los Angeles Lakers") == "los angeles lakers"
        assert normalize_team_name("LA Lakers") == "los angeles lakers"
        assert normalize_team_name("Lakers") == "los angeles lakers"
        assert normalize_team_name("LAL") == "los angeles lakers"

    def test_team_aliases(self):
        """Test team alias resolution."""
        assert normalize_team_name("Dubs") == "golden state warriors"
        assert normalize_team_name("GSW") == "golden state warriors"
        assert normalize_team_name("Celtics") == "boston celtics"
        assert normalize_team_name("Heat") == "miami heat"
        assert normalize_team_name("Sixers") == "philadelphia 76ers"


# =============================================================================
# PLAYER INDEX STORE TESTS
# =============================================================================

class TestPlayerIndexStore:
    """Tests for PlayerIndexStore."""

    def setup_method(self):
        """Create fresh index for each test."""
        self.index = PlayerIndexStore()

    def test_add_and_retrieve_player(self):
        """Test adding and retrieving a player."""
        record = PlayerRecord(
            canonical_id="NBA:BDL:123",
            normalized_name="lebron james",
            display_name="LeBron James",
            team="Los Angeles Lakers",
            normalized_team="los angeles lakers",
            sport="NBA",
            balldontlie_id=123,
        )

        self.index.add_player(record)

        # Retrieve by canonical ID
        result = self.index.get_by_canonical_id("NBA:BDL:123")
        assert result is not None
        assert result.display_name == "LeBron James"

        # Retrieve by name
        results = self.index.get_by_name("LeBron James")
        assert len(results) == 1
        assert results[0].canonical_id == "NBA:BDL:123"

        # Retrieve by provider ID
        result = self.index.get_by_provider_id("balldontlie", 123)
        assert result is not None
        assert result.display_name == "LeBron James"

        # Retrieve by team
        results = self.index.get_by_team("Lakers")
        assert len(results) == 1

    def test_name_with_team_hint(self):
        """Test name lookup with team disambiguation."""
        # Add two players with similar names on different teams
        record1 = PlayerRecord(
            canonical_id="NBA:NAME:jalen_williams|okc",
            normalized_name="jalen williams",
            display_name="Jalen Williams",
            team="Oklahoma City Thunder",
            normalized_team="oklahoma city thunder",
            sport="NBA",
        )
        record2 = PlayerRecord(
            canonical_id="NBA:NAME:jalen_williams|mia",
            normalized_name="jalen williams",
            display_name="Jalen Williams",
            team="Miami Heat",
            normalized_team="miami heat",
            sport="NBA",
        )

        self.index.add_player(record1)
        self.index.add_player(record2)

        # Without team hint, get both
        results = self.index.get_by_name("Jalen Williams")
        assert len(results) == 2

        # With team hint, get specific one
        results = self.index.get_by_name("Jalen Williams", team_hint="OKC")
        assert len(results) == 1
        assert "oklahoma" in results[0].normalized_team

    def test_search_players(self):
        """Test fuzzy player search."""
        records = [
            PlayerRecord(
                canonical_id=f"NBA:NAME:player_{i}|team",
                normalized_name=name,
                display_name=name.title(),
                team="Team",
                normalized_team="team",
                sport="NBA",
            )
            for i, name in enumerate([
                "lebron james",
                "kevin durant",
                "stephen curry",
                "giannis antetokounmpo",
            ])
        ]

        for r in records:
            self.index.add_player(r)

        # Search for partial name
        results = self.index.search_players("lebron")
        assert len(results) >= 1
        assert any("lebron" in r.normalized_name for r in results)

        # Search with typo
        results = self.index.search_players("kevin duran")
        assert len(results) >= 1

    def test_props_availability_cache(self):
        """Test props availability caching."""
        event_id = "event_123"
        props = {
            "lebron james": ["points", "rebounds", "assists"],
            "anthony davis": ["points", "rebounds"],
        }

        self.index.set_props_availability(event_id, props)

        # Check availability
        assert self.index.is_prop_available(event_id, "LeBron James", "points") is True
        assert self.index.is_prop_available(event_id, "LeBron James", "steals") is False
        assert self.index.is_prop_available(event_id, "Unknown Player", "points") is False

    def test_injury_cache(self):
        """Test injury caching."""
        injuries = [
            {"player_name": "Anthony Davis", "team": "Lakers", "status": "QUESTIONABLE"},
            {"player_name": "LeBron James", "team": "Lakers", "status": "PROBABLE"},
        ]

        # Add players first
        self.index.add_player(PlayerRecord(
            canonical_id="NBA:BDL:1",
            normalized_name="anthony davis",
            display_name="Anthony Davis",
            team="Lakers",
            normalized_team="los angeles lakers",
            sport="NBA",
        ))

        self.index.set_injuries("NBA", injuries)

        # Check injury status
        status = self.index.get_player_injury_status("Anthony Davis")
        assert status == "QUESTIONABLE"


# =============================================================================
# PLAYER RESOLVER TESTS
# =============================================================================

class TestPlayerResolver:
    """Tests for PlayerResolver."""

    def setup_method(self):
        """Create fresh resolver for each test."""
        self.index = PlayerIndexStore()
        self.resolver = PlayerResolver(index=self.index)

    @pytest.mark.asyncio
    async def test_exact_match(self):
        """Test exact name match resolution."""
        # Pre-populate index
        record = PlayerRecord(
            canonical_id="NBA:BDL:123",
            normalized_name="lebron james",
            display_name="LeBron James",
            team="Los Angeles Lakers",
            normalized_team="los angeles lakers",
            sport="NBA",
            balldontlie_id=123,
        )
        self.index.add_player(record)

        result = await self.resolver.resolve_player(
            sport="NBA",
            raw_name="LeBron James"
        )

        assert result.is_resolved
        assert result.canonical_player_id == "NBA:BDL:123"
        assert result.match_method == MatchMethod.EXACT
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_provider_id_match(self):
        """Test resolution by provider ID."""
        record = PlayerRecord(
            canonical_id="NBA:BDL:456",
            normalized_name="kevin durant",
            display_name="Kevin Durant",
            team="Phoenix Suns",
            normalized_team="phoenix suns",
            sport="NBA",
            balldontlie_id=456,
        )
        self.index.add_player(record)

        result = await self.resolver.resolve_player(
            sport="NBA",
            raw_name="KD",  # Nickname
            provider_context={"balldontlie": 456}
        )

        assert result.is_resolved
        assert result.canonical_player_id == "NBA:BDL:456"
        assert result.match_method == MatchMethod.PROVIDER_ID

    @pytest.mark.asyncio
    async def test_ambiguous_match(self):
        """Test ambiguous name resolution with candidates."""
        # Add multiple players with same name
        for i, team in enumerate(["OKC", "Miami"]):
            self.index.add_player(PlayerRecord(
                canonical_id=f"NBA:NAME:jalen_williams|{team.lower()}",
                normalized_name="jalen williams",
                display_name="Jalen Williams",
                team=team,
                normalized_team=team.lower(),
                sport="NBA",
            ))

        result = await self.resolver.resolve_player(
            sport="NBA",
            raw_name="Jalen Williams"
        )

        # Should return with candidates
        assert result.is_resolved
        assert result.match_method == MatchMethod.BEST_GUESS
        assert len(result.candidates) == 2
        assert result.confidence < 1.0

    @pytest.mark.asyncio
    async def test_ambiguous_with_team_hint(self):
        """Test ambiguous resolution with team hint."""
        for i, team in enumerate(["Oklahoma City Thunder", "Miami Heat"]):
            self.index.add_player(PlayerRecord(
                canonical_id=f"NBA:NAME:jalen_williams|{team.split()[0].lower()}",
                normalized_name="jalen williams",
                display_name="Jalen Williams",
                team=team,
                normalized_team=normalize_team_name(team),
                sport="NBA",
            ))

        result = await self.resolver.resolve_player(
            sport="NBA",
            raw_name="Jalen Williams",
            team_hint="OKC"
        )

        assert result.is_resolved
        assert "oklahoma" in result.team.lower()
        assert result.confidence > 0.9

    @pytest.mark.asyncio
    async def test_fuzzy_match(self):
        """Test fuzzy name matching."""
        self.index.add_player(PlayerRecord(
            canonical_id="NBA:BDL:999",
            normalized_name="giannis antetokounmpo",
            display_name="Giannis Antetokounmpo",
            team="Milwaukee Bucks",
            normalized_team="milwaukee bucks",
            sport="NBA",
        ))

        # Search with partial/misspelled name
        result = await self.resolver.resolve_player(
            sport="NBA",
            raw_name="Giannis"
        )

        assert result.is_resolved
        assert "giannis" in result.display_name.lower()

    @pytest.mark.asyncio
    async def test_not_found_creates_fallback(self):
        """Test that unknown players get a fallback canonical ID."""
        result = await self.resolver.resolve_player(
            sport="NFL",
            raw_name="Unknown Player Name",
            team_hint="Chiefs"
        )

        # Should still return a result with fallback ID
        assert result.canonical_player_id.startswith("NFL:NAME:")
        assert "unknown_player_name" in result.canonical_player_id
        assert result.confidence < 0.6

    @pytest.mark.asyncio
    async def test_injury_guard_out(self):
        """Test injury guard blocks OUT players."""
        resolved = ResolvedPlayer(
            canonical_player_id="NBA:BDL:123",
            display_name="Injured Player",
            team="Team",
            sport="NBA",
            injury_status="OUT",
        )

        result = await self.resolver.check_injury_guard(resolved)

        assert result.is_blocked
        assert result.blocked_reason == "PLAYER_OUT"

    @pytest.mark.asyncio
    async def test_injury_guard_questionable(self):
        """Test injury guard handles QUESTIONABLE."""
        resolved = ResolvedPlayer(
            canonical_player_id="NBA:BDL:123",
            display_name="Questionable Player",
            team="Team",
            sport="NBA",
            injury_status="QUESTIONABLE",
        )

        # Allowed by default
        result = await self.resolver.check_injury_guard(resolved, allow_questionable=True)
        assert not result.is_blocked

        # Blocked when not allowed (for TITANIUM)
        result = await self.resolver.check_injury_guard(resolved, allow_questionable=False)
        assert result.is_blocked
        assert result.blocked_reason == "PLAYER_QUESTIONABLE"

    @pytest.mark.asyncio
    async def test_prop_availability_check(self):
        """Test prop availability guard."""
        event_id = "event_abc"

        # Set up availability
        self.index.set_props_availability(event_id, {
            "lebron james": ["points", "rebounds", "assists"],
        })

        resolved = ResolvedPlayer(
            canonical_player_id="NBA:BDL:123",
            display_name="LeBron James",
            team="Lakers",
            sport="NBA",
        )

        # Available prop
        result = await self.resolver.check_prop_availability(
            resolved, "points", event_id
        )
        assert result.prop_available is True
        assert not result.is_blocked

        # Unavailable prop
        result = await self.resolver.check_prop_availability(
            resolved, "steals", event_id
        )
        assert result.prop_available is False
        assert result.is_blocked
        assert result.blocked_reason == "PROP_NOT_LISTED"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the identity system."""

    @pytest.mark.asyncio
    async def test_full_resolution_flow(self):
        """Test complete resolution flow."""
        # Use global resolver
        resolver = get_player_resolver()

        # Clear and set up
        resolver.index.clear()
        resolver.index.add_player(PlayerRecord(
            canonical_id="NBA:BDL:100",
            normalized_name="stephen curry",
            display_name="Stephen Curry",
            team="Golden State Warriors",
            normalized_team="golden state warriors",
            sport="NBA",
            balldontlie_id=100,
            position="G",
        ))

        # Resolve by nickname
        result = await resolver.resolve_player(
            sport="NBA",
            raw_name="Steph Curry"
        )

        assert result.is_resolved
        assert result.canonical_player_id == "NBA:BDL:100"
        assert result.position == "G"

    @pytest.mark.asyncio
    async def test_canonical_id_consistency(self):
        """Test canonical ID is consistent across lookups."""
        resolver = get_player_resolver()
        resolver.index.clear()

        # First lookup creates entry
        result1 = await resolver.resolve_player(
            sport="NBA",
            raw_name="New Player",
            team_hint="Lakers"
        )

        # Second lookup should get same canonical ID
        result2 = await resolver.resolve_player(
            sport="NBA",
            raw_name="New Player",
            team_hint="Lakers"
        )

        assert result1.canonical_player_id == result2.canonical_player_id


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
