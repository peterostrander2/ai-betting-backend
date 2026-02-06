"""
Tests for diversity filter - prevents props concentration on single players or games.

Tests ensure:
1. get_player_key() handles all canonical_player_id formats
2. get_game_key() handles event_id and matchup fallbacks
3. apply_diversity_limits() correctly filters by player and game limits
4. apply_diversity_gate() filters BOTH props AND game picks (v20.12)

v20.12: Updated to use CONCENTRATION_LIMITS from scoring_contract.py:
- max_props_per_player: 1 (only best line per player)
- max_per_matchup: 2 (applies to ALL pick types now, not just props)
"""
import pytest
from utils.diversity_filter import (
    get_player_key,
    get_game_key,
    apply_diversity_limits,
    apply_diversity_gate,
    MAX_PROPS_PER_PLAYER,
    MAX_PICKS_PER_MATCHUP,
)


# =============================================================================
# get_player_key() tests - CRITICAL for deduplication
# =============================================================================

class TestGetPlayerKey:
    """Tests for player key extraction from various input formats."""

    def test_canonical_id_with_pipe(self):
        """Standard format: NBA:NAME:player_name|team extracts player portion."""
        pick = {"canonical_player_id": "NBA:NAME:lebron_james|lakers"}
        assert get_player_key(pick) == "nba:name:lebron_james"

    def test_canonical_id_with_multiple_pipes(self):
        """Multiple pipes: take only first segment."""
        pick = {"canonical_player_id": "NBA:NAME:stephen_curry|warriors|2024"}
        assert get_player_key(pick) == "nba:name:stephen_curry"

    def test_canonical_id_without_pipe(self):
        """No pipe in canonical_id: uses the canonical_id directly."""
        pick = {
            "canonical_player_id": "lebron_james",  # No pipe
            "player_name": "LeBron James"
        }
        # Uses canonical_id directly (split on | returns same string if no |)
        assert get_player_key(pick) == "lebron_james"

    def test_empty_canonical_id_uses_player_name(self):
        """Empty canonical_player_id uses player_name field."""
        pick = {
            "canonical_player_id": "",
            "player_name": "Kevin Durant"
        }
        assert get_player_key(pick) == "kevin durant"

    def test_none_canonical_id_uses_player_name(self):
        """None canonical_player_id uses player_name field."""
        pick = {
            "canonical_player_id": None,
            "player_name": "Kevin Durant"
        }
        assert get_player_key(pick) == "kevin durant"

    def test_missing_canonical_id_uses_player_name(self):
        """Missing canonical_player_id uses player_name field."""
        pick = {"player_name": "Giannis Antetokounmpo"}
        assert get_player_key(pick) == "giannis antetokounmpo"

    def test_player_field_fallback(self):
        """Falls back to 'player' field when player_name missing."""
        pick = {"player": "Jayson Tatum"}
        assert get_player_key(pick) == "jayson tatum"

    def test_both_player_fields_prefers_player_name(self):
        """player_name takes precedence over player."""
        pick = {
            "player_name": "Luka Doncic",
            "player": "Wrong Name"
        }
        assert get_player_key(pick) == "luka doncic"

    def test_empty_pick_returns_empty_string(self):
        """Empty pick returns empty string."""
        pick = {}
        assert get_player_key(pick) == ""

    def test_all_fields_empty(self):
        """All fields empty/None returns empty string."""
        pick = {
            "canonical_player_id": "",
            "player_name": "",
            "player": ""
        }
        assert get_player_key(pick) == ""

    def test_whitespace_handling(self):
        """Whitespace is stripped from result."""
        pick = {"player_name": "  Nikola Jokic  "}
        assert get_player_key(pick) == "nikola jokic"

    def test_case_normalization(self):
        """Result is always lowercase."""
        pick = {"player_name": "LEBRON JAMES"}
        assert get_player_key(pick) == "lebron james"

    def test_canonical_id_format_variations(self):
        """Various canonical ID formats."""
        # Format with league prefix
        assert get_player_key({"canonical_player_id": "NFL:NAME:patrick_mahomes|chiefs"}) == "nfl:name:patrick_mahomes"

        # Format without league prefix
        assert get_player_key({"canonical_player_id": "connor_mcdavid|oilers"}) == "connor_mcdavid"

        # Format with only pipe at end
        assert get_player_key({"canonical_player_id": "mike_trout|"}) == "mike_trout"


# =============================================================================
# get_game_key() tests
# =============================================================================

class TestGetGameKey:
    """Tests for game key extraction."""

    def test_event_id_primary(self):
        """event_id is preferred when available."""
        pick = {
            "event_id": "abc123",
            "matchup": "Lakers @ Celtics"
        }
        assert get_game_key(pick) == "abc123"

    def test_canonical_event_id_fallback(self):
        """canonical_event_id used when event_id missing."""
        pick = {
            "canonical_event_id": "xyz789",
            "matchup": "Lakers @ Celtics"
        }
        assert get_game_key(pick) == "xyz789"

    def test_matchup_fallback(self):
        """matchup used when no event_id. Special chars are normalized."""
        pick = {"matchup": "Lakers @ Celtics"}
        # _normalize_name removes special chars like @
        assert get_game_key(pick) == "lakers celtics"

    def test_game_field_fallback(self):
        """'game' field used as last resort. Special chars normalized."""
        pick = {"game": "Warriors vs Suns"}
        assert get_game_key(pick) == "warriors vs suns"

    def test_empty_pick_returns_empty(self):
        """Empty pick returns empty string."""
        assert get_game_key({}) == ""


# =============================================================================
# apply_diversity_limits() tests
# =============================================================================

class TestApplyDiversityLimits:
    """Tests for the main diversity filtering logic."""

    def test_single_player_multiple_lines_keeps_highest(self):
        """Same player with different lines: keep highest score only."""
        picks = [
            {"player_name": "Svi Mykhailiuk", "line": 7.5, "total_score": 8.0, "pick_type": "PROP"},
            {"player_name": "Svi Mykhailiuk", "line": 8.5, "total_score": 7.5, "pick_type": "PROP"},
            {"player_name": "Svi Mykhailiuk", "line": 9.5, "total_score": 7.0, "pick_type": "PROP"},
            {"player_name": "Svi Mykhailiuk", "line": 10.5, "total_score": 6.5, "pick_type": "PROP"},
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 1
        assert kept[0]["line"] == 7.5  # Highest score
        assert debug["player_limited"] == 3
        assert debug["total_dropped"] == 3

    def test_different_players_all_kept(self):
        """Different players from DIFFERENT games are all kept."""
        # v20.12: max_per_matchup is now 2, so same-game picks are limited
        # Use different games to test player-only filtering
        picks = [
            {"player_name": "Player A", "line": 20.5, "total_score": 8.0, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player B", "line": 15.5, "total_score": 7.5, "event_id": "game2", "pick_type": "PROP"},
            {"player_name": "Player C", "line": 10.5, "total_score": 7.0, "event_id": "game3", "pick_type": "PROP"},
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 3
        assert debug["total_dropped"] == 0

    def test_game_limit_enforced(self):
        """Max 2 props per game (v20.12 max_per_matchup)."""
        picks = [
            {"player_name": "Player A", "total_score": 8.0, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player B", "total_score": 7.5, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player C", "total_score": 7.0, "event_id": "game1", "pick_type": "PROP"},  # 3rd - dropped
            {"player_name": "Player D", "total_score": 6.5, "event_id": "game1", "pick_type": "PROP"},  # 4th - dropped
            {"player_name": "Player E", "total_score": 6.0, "event_id": "game1", "pick_type": "PROP"},  # 5th - dropped
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 2
        assert debug["game_limited"] == 3

    def test_spreads_across_games(self):
        """Picks spread across games are not game-limited."""
        picks = [
            {"player_name": "Player A", "total_score": 8.0, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player B", "total_score": 7.5, "event_id": "game2", "pick_type": "PROP"},
            {"player_name": "Player C", "total_score": 7.0, "event_id": "game3", "pick_type": "PROP"},
            {"player_name": "Player D", "total_score": 6.5, "event_id": "game4", "pick_type": "PROP"},
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 4
        assert debug["game_limited"] == 0

    def test_empty_input(self):
        """Empty input returns empty output."""
        kept, debug = apply_diversity_limits([])

        assert kept == []
        assert debug["total_dropped"] == 0

    def test_custom_limits(self):
        """Custom limits are respected."""
        picks = [
            {"player_name": "Player A", "total_score": 8.0, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player A", "total_score": 7.5, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player A", "total_score": 7.0, "event_id": "game1", "pick_type": "PROP"},
        ]
        # Allow 2 per player
        kept, debug = apply_diversity_limits(picks, max_per_player=2)

        assert len(kept) == 2
        assert debug["player_limited"] == 1

    def test_game_picks_also_game_limited(self):
        """v20.12: Spread/total/ML picks ARE now game limited (max_per_matchup applies to ALL)."""
        picks = [
            {"player_name": "", "total_score": 8.0, "event_id": "game1", "pick_type": "SPREAD"},
            {"player_name": "", "total_score": 7.5, "event_id": "game1", "pick_type": "TOTAL"},
            {"player_name": "", "total_score": 7.0, "event_id": "game1", "pick_type": "MONEYLINE"},  # 3rd - dropped
            {"player_name": "", "total_score": 6.5, "event_id": "game1", "pick_type": "SPREAD"},    # 4th - dropped
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 2  # Only top 2 kept per max_per_matchup
        assert debug["game_limited"] == 2

    def test_sorting_by_score(self):
        """Picks are sorted by score before filtering."""
        picks = [
            {"player_name": "Player A", "total_score": 6.0, "pick_type": "PROP"},  # Lowest
            {"player_name": "Player A", "total_score": 8.0, "pick_type": "PROP"},  # Highest
            {"player_name": "Player A", "total_score": 7.0, "pick_type": "PROP"},  # Middle
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 1
        assert kept[0]["total_score"] == 8.0  # Highest kept

    def test_final_score_fallback(self):
        """Uses final_score if total_score missing."""
        picks = [
            {"player_name": "Player A", "final_score": 6.0, "pick_type": "PROP"},
            {"player_name": "Player A", "final_score": 8.0, "pick_type": "PROP"},
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 1
        assert kept[0]["final_score"] == 8.0

    def test_debug_mode(self):
        """Debug mode includes detailed info."""
        picks = [
            {"player_name": "Player A", "total_score": 8.0, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player A", "total_score": 7.0, "event_id": "game1", "pick_type": "PROP"},
        ]
        kept, debug = apply_diversity_limits(picks, debug=True)

        assert "dropped_by_player" in debug
        assert "player_counts" in debug
        assert debug["player_counts"]["player a"] == 1

    def test_player_prop_market_types(self):
        """v20.12: Various player prop market types are recognized, max 2 per game."""
        picks = [
            {"player_name": "Player A", "total_score": 8.0, "event_id": "game1", "market": "PLAYER_POINTS"},
            {"player_name": "Player B", "total_score": 7.5, "event_id": "game1", "market": "PLAYER_ASSISTS"},
            {"player_name": "Player C", "total_score": 7.0, "event_id": "game1", "market": "PLAYER_REBOUNDS"},  # 3rd - dropped
            {"player_name": "Player D", "total_score": 6.5, "event_id": "game1", "market": "PLAYER_THREES"},    # 4th - dropped
        ]
        kept, debug = apply_diversity_limits(picks)

        assert len(kept) == 2  # v20.12: max_per_matchup = 2
        assert debug["game_limited"] == 2


# =============================================================================
# apply_diversity_gate() tests
# =============================================================================

class TestApplyDiversityGate:
    """Tests for the combined props + games gate."""

    def test_props_filtered_games_passed_through(self):
        """Props get diversity filter, game picks pass through unchanged."""
        props = [
            {"player_name": "Player A", "total_score": 8.0, "pick_type": "PROP"},
            {"player_name": "Player A", "total_score": 7.0, "pick_type": "PROP"},
        ]
        games = [
            {"matchup": "Team A @ Team B", "total_score": 7.5, "pick_type": "SPREAD"},
            {"matchup": "Team C @ Team D", "total_score": 7.0, "pick_type": "TOTAL"},
        ]

        filtered_props, filtered_games, debug = apply_diversity_gate(props, games)

        assert len(filtered_props) == 1  # Player limit applied
        assert len(filtered_games) == 2  # Games unchanged
        assert debug["props_player_limited"] == 1
        assert debug["games_total_dropped"] == 0

    def test_empty_inputs(self):
        """Empty inputs return empty outputs."""
        filtered_props, filtered_games, debug = apply_diversity_gate([], [])

        assert filtered_props == []
        assert filtered_games == []
        assert debug["total_dropped"] == 0


# =============================================================================
# Integration tests
# =============================================================================

class TestDiversityFilterIntegration:
    """Integration tests simulating real-world scenarios."""

    def test_svi_mykhailiuk_scenario(self):
        """The original bug: Svi Mykhailiuk appearing 4 times."""
        picks = [
            {
                "player_name": "Svi Mykhailiuk",
                "canonical_player_id": "NBA:NAME:svi_mykhailiuk|hawks",
                "line": 7.5,
                "total_score": 7.8,
                "event_id": "hawks_celtics_20260201",
                "pick_type": "PLAYER_POINTS",
            },
            {
                "player_name": "Svi Mykhailiuk",
                "canonical_player_id": "NBA:NAME:svi_mykhailiuk|hawks",
                "line": 8.5,
                "total_score": 7.5,
                "event_id": "hawks_celtics_20260201",
                "pick_type": "PLAYER_POINTS",
            },
            {
                "player_name": "Svi Mykhailiuk",
                "canonical_player_id": "NBA:NAME:svi_mykhailiuk|hawks",
                "line": 9.5,
                "total_score": 7.2,
                "event_id": "hawks_celtics_20260201",
                "pick_type": "PLAYER_POINTS",
            },
            {
                "player_name": "Svi Mykhailiuk",
                "canonical_player_id": "NBA:NAME:svi_mykhailiuk|hawks",
                "line": 10.5,
                "total_score": 6.8,
                "event_id": "hawks_celtics_20260201",
                "pick_type": "PLAYER_POINTS",
            },
        ]

        kept, debug = apply_diversity_limits(picks)

        # Only 1 Svi pick kept (highest score)
        assert len(kept) == 1
        assert kept[0]["line"] == 7.5
        assert kept[0]["total_score"] == 7.8
        assert debug["player_limited"] == 3

    def test_mixed_players_and_games(self):
        """Real scenario with multiple players across multiple games (v20.12)."""
        props = [
            # Game 1: 4 different players
            {"player_name": "Player A", "total_score": 8.5, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player B", "total_score": 8.0, "event_id": "game1", "pick_type": "PROP"},
            {"player_name": "Player C", "total_score": 7.5, "event_id": "game1", "pick_type": "PROP"},  # 3rd from game1 - dropped
            {"player_name": "Player D", "total_score": 7.0, "event_id": "game1", "pick_type": "PROP"},  # 4th from game1 - dropped

            # Game 2: 2 players
            {"player_name": "Player E", "total_score": 7.8, "event_id": "game2", "pick_type": "PROP"},
            {"player_name": "Player F", "total_score": 7.2, "event_id": "game2", "pick_type": "PROP"},

            # Player A again with different line
            {"player_name": "Player A", "total_score": 7.6, "event_id": "game1", "pick_type": "PROP"},  # Dup - player limited
        ]

        games = [
            {"matchup": "Team A @ Team B", "total_score": 8.2, "pick_type": "SPREAD"},
            {"matchup": "Team C @ Team D", "total_score": 7.9, "pick_type": "TOTAL"},
        ]

        filtered_props, filtered_games, debug = apply_diversity_gate(props, games)

        # v20.12: max_per_matchup = 2
        # Player A duplicate dropped (player limit = 1)
        # Player C, D dropped (game1 already has 2 after A, B)
        assert len(filtered_props) == 4  # A, B from game1 + E, F from game2
        assert debug["props_player_limited"] == 1  # Player A duplicate
        assert debug["props_game_limited"] == 2  # Player C, D (3rd, 4th from game1)

        # Games also game-limited now (v20.12)
        assert len(filtered_games) == 2  # Both kept (different matchups)


# =============================================================================
# Default configuration tests
# =============================================================================

class TestDefaultConfiguration:
    """Tests for default configuration values."""

    def test_max_per_player_default(self):
        """Default max per player is 1."""
        assert MAX_PROPS_PER_PLAYER == 1

    def test_max_per_game_default(self):
        """v20.12: Default max per matchup is 2."""
        assert MAX_PICKS_PER_MATCHUP == 2
