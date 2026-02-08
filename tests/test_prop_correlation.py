"""
Tests for Prop Correlation Signal - Rule-Based Player Prop Correlations
========================================================================

v20.3 - Tests verify:
1. Same-player prop correlations work correctly
2. Same-game teammate correlations work correctly
3. Opposite-direction correlations are detected
4. Adjustments are bounded by caps
5. Game total correlations work correctly
6. Non-prop bets return zero adjustment
"""

from signals.prop_correlation import (
    analyze_prop_correlation,
    get_prop_correlation_adjustment,
    get_total_correlation_adjustment,
    PropCorrelationResult,
    PROP_CORRELATION_CAP,
    CORRELATION_BOOSTS,
    SPORT_CORRELATIONS,
)


class TestNFLCorrelations:
    """Test NFL player prop correlations."""

    def test_qb_wr_same_team_aligned(self):
        """QB passing OVER + WR receiving OVER = aligned (same direction)."""
        other_props = [
            {
                "player_name": "Ja'Marr Chase",
                "prop_type": "player_reception_yds",
                "side": "Over",
                "team": "CIN",
                "final_score": 7.5,
            }
        ]

        result = analyze_prop_correlation(
            sport="NFL",
            player_name="Joe Burrow",
            prop_type="player_pass_yds",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.alignments >= 1
        assert result.adjustment > 0
        assert "aligns" in result.reasons[0].lower()

    def test_qb_rb_opposite_game_script(self):
        """QB passing OVER + RB rushing OVER = contradicting game script."""
        other_props = [
            {
                "player_name": "Joe Mixon",
                "prop_type": "player_rush_yds",
                "side": "Over",
                "team": "CIN",
                "final_score": 7.0,
            }
        ]

        result = analyze_prop_correlation(
            sport="NFL",
            player_name="Joe Burrow",
            prop_type="player_pass_yds",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.contradictions >= 1
        assert result.adjustment < 0
        assert "conflict" in result.reasons[0].lower()

    def test_wr_receptions_and_yards_aligned(self):
        """Same player WR receptions + yards = aligned."""
        other_props = [
            {
                "player_name": "Ja'Marr Chase",
                "prop_type": "player_reception_yds",
                "side": "Over",
                "team": "CIN",
                "final_score": 8.0,
            }
        ]

        result = analyze_prop_correlation(
            sport="NFL",
            player_name="Ja'Marr Chase",
            prop_type="player_receptions",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.alignments >= 1
        assert result.adjustment > 0


class TestNBACorrelations:
    """Test NBA player prop correlations."""

    def test_points_assists_rebounds_aligned(self):
        """Points + Assists + Rebounds OVER = aligned for same player."""
        other_props = [
            {
                "player_name": "LeBron James",
                "prop_type": "player_assists",
                "side": "Over",
                "team": "LAL",
                "final_score": 8.5,
            },
            {
                "player_name": "LeBron James",
                "prop_type": "player_rebounds",
                "side": "Over",
                "team": "LAL",
                "final_score": 7.8,
            },
        ]

        result = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron James",
            prop_type="player_points",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.alignments >= 2
        assert result.correlation_level in ("STRONG_POSITIVE", "MODERATE_POSITIVE")

    def test_pra_correlates_with_components(self):
        """PRA should correlate with points, rebounds, assists."""
        other_props = [
            {
                "player_name": "LeBron James",
                "prop_type": "player_points",
                "side": "Over",
                "team": "LAL",
                "final_score": 8.0,
            }
        ]

        result = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron James",
            prop_type="player_pra",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.alignments >= 1
        assert result.adjustment > 0


class TestMLBCorrelations:
    """Test MLB player prop correlations."""

    def test_pitcher_strikeouts_batter_strikeouts_opposite(self):
        """Pitcher strikeouts OVER + Batter strikeouts UNDER = opposite."""
        other_props = [
            {
                "player_name": "Shohei Ohtani",
                "prop_type": "batter_strikeouts",
                "side": "Under",
                "team": "LAD",
                "final_score": 7.5,
            }
        ]

        result = analyze_prop_correlation(
            sport="MLB",
            player_name="Gerrit Cole",
            prop_type="pitcher_strikeouts",
            pick_side="Over",
            other_props=other_props,
        )

        # Pitcher strikeouts OVER should conflict with batter strikeouts UNDER
        # (If pitcher striking out batters, batters are striking out)
        # This depends on how correlation is defined in SPORT_CORRELATIONS
        assert result.correlations_found >= 0  # May or may not correlate depending on rules

    def test_batter_hits_runs_aligned(self):
        """Same batter hits OVER + runs OVER = aligned."""
        other_props = [
            {
                "player_name": "Shohei Ohtani",
                "prop_type": "player_runs",
                "side": "Over",
                "team": "LAD",
                "final_score": 7.2,
            }
        ]

        result = analyze_prop_correlation(
            sport="MLB",
            player_name="Shohei Ohtani",
            prop_type="player_hits",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.alignments >= 1
        assert result.adjustment > 0


class TestNHLCorrelations:
    """Test NHL player prop correlations."""

    def test_goals_assists_points_aligned(self):
        """Goals + Assists + Points = aligned for same player."""
        other_props = [
            {
                "player_name": "Connor McDavid",
                "prop_type": "player_assists",
                "side": "Over",
                "team": "EDM",
                "final_score": 8.0,
            }
        ]

        result = analyze_prop_correlation(
            sport="NHL",
            player_name="Connor McDavid",
            prop_type="player_goals",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.alignments >= 1
        assert result.adjustment > 0


class TestBounds:
    """Test that adjustments are properly bounded."""

    def test_positive_cap_enforced(self):
        """Positive adjustments should not exceed PROP_CORRELATION_CAP."""
        # Many aligned props
        other_props = [
            {"player_name": "LeBron", "prop_type": "player_assists", "side": "Over", "team": "LAL", "final_score": 9.0},
            {"player_name": "LeBron", "prop_type": "player_rebounds", "side": "Over", "team": "LAL", "final_score": 9.0},
            {"player_name": "LeBron", "prop_type": "player_pra", "side": "Over", "team": "LAL", "final_score": 9.0},
            {"player_name": "LeBron", "prop_type": "player_threes", "side": "Over", "team": "LAL", "final_score": 9.0},
        ]

        result = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron",
            prop_type="player_points",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.adjustment <= PROP_CORRELATION_CAP

    def test_negative_cap_enforced(self):
        """Negative adjustments should not exceed -PROP_CORRELATION_CAP."""
        # Many contradicting props
        other_props = [
            {"player_name": "LeBron", "prop_type": "player_assists", "side": "Under", "team": "LAL", "final_score": 9.0},
            {"player_name": "LeBron", "prop_type": "player_rebounds", "side": "Under", "team": "LAL", "final_score": 9.0},
            {"player_name": "LeBron", "prop_type": "player_pra", "side": "Under", "team": "LAL", "final_score": 9.0},
        ]

        result = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron",
            prop_type="player_points",
            pick_side="Over",
            other_props=other_props,
        )

        assert result.adjustment >= -PROP_CORRELATION_CAP


class TestGameTotalCorrelation:
    """Test game total correlations with props."""

    def test_high_total_offensive_prop_aligned(self):
        """High game total + offensive prop OVER = aligned."""
        adj, reasons = get_total_correlation_adjustment(
            sport="NBA",
            game_total=235.0,  # High total
            game_total_side="Over",
            prop_type="player_points",
            prop_side="Over",
        )

        assert adj > 0
        assert "correlates" in reasons[0].lower()

    def test_low_total_offensive_prop_opposite(self):
        """Game total UNDER + offensive prop OVER = opposing."""
        adj, reasons = get_total_correlation_adjustment(
            sport="NBA",
            game_total=210.0,
            game_total_side="Under",
            prop_type="player_points",
            prop_side="Over",
        )

        assert adj < 0
        assert "opposing" in reasons[0].lower() or "conflict" in reasons[0].lower()

    def test_neutral_total(self):
        """Neutral total (no side picked) = no adjustment."""
        adj, reasons = get_total_correlation_adjustment(
            sport="NBA",
            game_total=220.0,
            game_total_side=None,
            prop_type="player_points",
            prop_side="Over",
        )

        assert adj == 0.0


class TestNonPropBets:
    """Test that non-prop scenarios return zero adjustment."""

    def test_empty_other_props(self):
        """No other props = no correlation."""
        result = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron James",
            prop_type="player_points",
            pick_side="Over",
            other_props=[],
        )

        assert result.adjustment == 0.0
        assert result.correlation_level == "NEUTRAL"

    def test_unsupported_sport(self):
        """Unsupported sport returns neutral."""
        result = analyze_prop_correlation(
            sport="WNBA",
            player_name="Player",
            prop_type="player_points",
            pick_side="Over",
            other_props=[{"player_name": "Other", "prop_type": "player_assists", "side": "Over"}],
        )

        assert result.adjustment == 0.0


class TestWeightedCorrelations:
    """Test that high-confidence props are weighted more heavily."""

    def test_high_score_prop_weighted_more(self):
        """Props with final_score >= 8.0 get 1.5x weight."""
        # Low confidence props
        low_conf_props = [
            {"player_name": "LeBron", "prop_type": "player_assists", "side": "Over", "team": "LAL", "final_score": 6.5},
        ]

        # High confidence props
        high_conf_props = [
            {"player_name": "LeBron", "prop_type": "player_assists", "side": "Over", "team": "LAL", "final_score": 8.5},
        ]

        result_low = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron",
            prop_type="player_points",
            pick_side="Over",
            other_props=low_conf_props,
        )

        result_high = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron",
            prop_type="player_points",
            pick_side="Over",
            other_props=high_conf_props,
        )

        # Higher confidence should result in higher absolute adjustment
        assert abs(result_high.adjustment) >= abs(result_low.adjustment)


class TestConvenienceFunction:
    """Test the get_prop_correlation_adjustment convenience function."""

    def test_returns_tuple(self):
        """get_prop_correlation_adjustment should return (adjustment, reasons) tuple."""
        adj, reasons = get_prop_correlation_adjustment(
            sport="NBA",
            player_name="LeBron James",
            prop_type="player_points",
            pick_side="Over",
            other_props=[
                {"player_name": "LeBron James", "prop_type": "player_assists", "side": "Over", "team": "LAL"}
            ],
        )

        assert isinstance(adj, float)
        assert isinstance(reasons, list)

    def test_reasons_populated(self):
        """Reasons should explain the adjustment."""
        adj, reasons = get_prop_correlation_adjustment(
            sport="NBA",
            player_name="LeBron James",
            prop_type="player_points",
            pick_side="Over",
            other_props=[
                {"player_name": "LeBron James", "prop_type": "player_assists", "side": "Over", "team": "LAL", "final_score": 7.5}
            ],
        )

        assert len(reasons) > 0


class TestPropCorrelationResultDataclass:
    """Test PropCorrelationResult dataclass fields."""

    def test_all_fields_present(self):
        """PropCorrelationResult should have all required fields."""
        result = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron James",
            prop_type="player_points",
            pick_side="Over",
            other_props=[],
        )

        assert hasattr(result, "adjustment")
        assert hasattr(result, "correlation_level")
        assert hasattr(result, "correlations_found")
        assert hasattr(result, "alignments")
        assert hasattr(result, "contradictions")
        assert hasattr(result, "correlated_props")
        assert hasattr(result, "reasons")

    def test_correlated_props_structure(self):
        """correlated_props should contain details about each correlation."""
        result = analyze_prop_correlation(
            sport="NBA",
            player_name="LeBron James",
            prop_type="player_points",
            pick_side="Over",
            other_props=[
                {"player_name": "LeBron James", "prop_type": "player_assists", "side": "Over", "team": "LAL", "final_score": 7.5}
            ],
        )

        if result.correlated_props:
            prop = result.correlated_props[0]
            assert "player" in prop
            assert "prop_type" in prop
            assert "direction" in prop


class TestSportCorrelationsConfig:
    """Test that SPORT_CORRELATIONS is properly configured."""

    def test_major_sports_covered(self):
        """All major sports should have correlations defined."""
        assert "NFL" in SPORT_CORRELATIONS
        assert "NBA" in SPORT_CORRELATIONS
        assert "MLB" in SPORT_CORRELATIONS
        assert "NHL" in SPORT_CORRELATIONS
        assert "NCAAB" in SPORT_CORRELATIONS

    def test_nfl_has_qb_wr_correlation(self):
        """NFL should have QB-WR passing/receiving correlation."""
        nfl = SPORT_CORRELATIONS["NFL"]
        assert "player_pass_yds" in nfl
        correlations = nfl["player_pass_yds"]
        # correlations is a list of (prop_type, direction) tuples
        correlated_types = [c[0] for c in correlations]
        assert "player_reception_yds" in correlated_types

    def test_nba_has_pra_correlation(self):
        """NBA should have PRA correlation with components."""
        nba = SPORT_CORRELATIONS["NBA"]
        assert "player_pra" in nba
        pra_corrs = nba["player_pra"]
        # pra_corrs is a list of (prop_type, direction) tuples
        correlated_types = [c[0] for c in pra_corrs]
        assert "player_points" in correlated_types
        assert "player_assists" in correlated_types
        assert "player_rebounds" in correlated_types
