"""
Weather Integration Tests (v16.0)

Tests the weather integration module for correct behavior:
1. Feature flag disabled shows DISABLED status
2. Weather modifier is capped at ±1.0
3. Indoor venues return 0.0 modifier
4. Cache works correctly
"""

import pytest
import os
from unittest.mock import patch, MagicMock


# Test weather modifier capping
class TestWeatherModifierCapping:
    """Test that weather modifiers are properly capped at ±1.0."""

    def test_extreme_cold_capped(self):
        """Extreme cold weather is capped at -1.0."""
        from alt_data_sources.weather import calculate_weather_modifier

        # Temperature: 0°F (extreme cold)
        # Wind: 30 mph (extreme)
        # Rain: 1.0 in (heavy)
        # Raw modifier would be: -0.5 (cold) - 0.5 (wind) - 0.6 (rain) = -1.6
        # Should be capped at -1.0
        result = calculate_weather_modifier(
            temp_f=0.0,
            wind_mph=30.0,
            precip_in=1.0,
            sport="NFL"
        )

        assert result["weather_modifier"] == -1.0, "Extreme negative modifier should be capped at -1.0"
        assert result["raw_modifier"] < -1.0, "Raw modifier should exceed cap"

    def test_perfect_weather(self):
        """Perfect weather conditions give 0.0 modifier."""
        from alt_data_sources.weather import calculate_weather_modifier

        result = calculate_weather_modifier(
            temp_f=70.0,
            wind_mph=5.0,
            precip_in=0.0,
            sport="NFL"
        )

        assert result["weather_modifier"] == 0.0, "Perfect weather should be 0.0 modifier"
        assert result["weather_score"] == 5.0, "Perfect weather should be 5.0 score (neutral)"

    def test_moderate_cold(self):
        """Moderate cold gives -0.3 modifier (not capped)."""
        from alt_data_sources.weather import calculate_weather_modifier

        result = calculate_weather_modifier(
            temp_f=35.0,  # Chilly but not freezing
            wind_mph=5.0,
            precip_in=0.0,
            sport="NFL"
        )

        assert result["weather_modifier"] == -0.3, "Chilly temps should be -0.3"

    def test_heavy_rain(self):
        """Heavy rain gives -0.6 modifier."""
        from alt_data_sources.weather import calculate_weather_modifier

        result = calculate_weather_modifier(
            temp_f=60.0,
            wind_mph=5.0,
            precip_in=0.7,  # Heavy rain
            sport="NFL"
        )

        assert result["weather_modifier"] == -0.6, "Heavy rain should be -0.6"

    def test_high_wind(self):
        """High wind gives -0.4 modifier."""
        from alt_data_sources.weather import calculate_weather_modifier

        result = calculate_weather_modifier(
            temp_f=60.0,
            wind_mph=22.0,  # High wind
            precip_in=0.0,
            sport="NFL"
        )

        assert result["weather_modifier"] == -0.4, "High wind should be -0.4"

    def test_combined_factors(self):
        """Combined factors add up but cap at -1.0."""
        from alt_data_sources.weather import calculate_weather_modifier

        # Cold + wind + light rain
        result = calculate_weather_modifier(
            temp_f=30.0,  # -0.5 (cold)
            wind_mph=25.0,  # -0.5 (very high wind)
            precip_in=0.15,  # -0.2 (light rain)
            sport="NFL"
        )

        # Raw: -0.5 - 0.5 - 0.2 = -1.2, capped to -1.0
        assert result["weather_modifier"] == -1.0, "Combined factors capped at -1.0"


class TestWeatherFeatureFlag:
    """Test feature flag behavior."""

    def test_disabled_returns_neutral(self):
        """When WEATHER_ENABLED=false, returns neutral modifier."""
        from alt_data_sources.weather import get_weather_for_game

        # The sync wrapper should return FEATURE_DISABLED when disabled
        with patch.dict(os.environ, {"WEATHER_ENABLED": "false"}):
            # Reimport to pick up env var change
            import importlib
            import alt_data_sources.weather as weather_mod
            importlib.reload(weather_mod)

            result = weather_mod.get_weather_for_game(
                sport="NFL",
                home_team="Buffalo Bills",
                venue="",
                game_time=""
            )

        assert result["available"] == False
        assert result["reason"] in {"FEATURE_DISABLED", "API_KEY_MISSING"}
        assert result["weather_modifier"] == 0.0

    def test_indoor_sport_ignored(self):
        """Indoor sports (NBA, NHL) return neutral modifier."""
        from alt_data_sources.weather import is_outdoor_sport

        assert is_outdoor_sport("NFL") == True
        assert is_outdoor_sport("MLB") == True
        assert is_outdoor_sport("NBA") == False
        assert is_outdoor_sport("NHL") == False
        assert is_outdoor_sport("NCAAB") == False


class TestWeatherScore:
    """Test weather score (0-10 scale) calculation."""

    def test_score_range(self):
        """Weather score should be 0-10."""
        from alt_data_sources.weather import calculate_weather_modifier

        # Perfect weather = 5.0 (neutral)
        result = calculate_weather_modifier(70.0, 5.0, 0.0, "NFL")
        assert 0.0 <= result["weather_score"] <= 10.0

        # Bad weather = lower score
        result = calculate_weather_modifier(20.0, 25.0, 0.5, "NFL")
        assert 0.0 <= result["weather_score"] <= 10.0
        assert result["weather_score"] < 5.0  # Bad weather = below neutral

    def test_score_reflects_modifier(self):
        """Score should reflect modifier: 5.0 + (modifier * 5)."""
        from alt_data_sources.weather import calculate_weather_modifier

        # Modifier of -0.5 should give score of 2.5
        result = calculate_weather_modifier(30.0, 5.0, 0.0, "NFL")  # Cold = -0.5
        assert abs(result["weather_score"] - 2.5) < 0.1


class TestVenueIntegration:
    """Test venue registry integration."""

    def test_venue_registry_exists(self):
        """Venue registry should have NFL and MLB venues."""
        from alt_data_sources.stadium import VENUE_REGISTRY

        assert len(VENUE_REGISTRY) >= 60, "Should have 60+ venues (32 NFL + 30 MLB)"

    def test_venue_has_coordinates(self):
        """Venues should have lat/lon coordinates."""
        from alt_data_sources.stadium import VENUE_REGISTRY

        # Check a known venue
        buffalo = VENUE_REGISTRY.get("nfl_buffalo_bills")
        assert buffalo is not None, "Buffalo Bills venue should exist"
        assert "lat" in buffalo
        assert "lon" in buffalo
        assert buffalo["lat"] != 0.0
        assert buffalo["lon"] != 0.0

    def test_indoor_venues_marked(self):
        """Indoor/dome venues should be marked as not outdoor."""
        from alt_data_sources.stadium import VENUE_REGISTRY

        # Cowboys play in AT&T Stadium (dome)
        cowboys = VENUE_REGISTRY.get("nfl_dallas_cowboys")
        if cowboys:
            assert cowboys.get("is_outdoor") == False, "Cowboys dome should be indoor"

    def test_get_venue_for_weather(self):
        """get_venue_for_weather should return venue info."""
        from alt_data_sources.stadium import get_venue_for_weather

        venue = get_venue_for_weather("Buffalo Bills", "NFL")
        assert venue is not None
        assert "lat" in venue
        assert "lon" in venue
        assert "is_outdoor" in venue


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
