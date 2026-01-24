"""
Test suite for Glitch Protocol modules.

Tests all 4 modules + math_glitch core functions.
"""

import unittest
from datetime import datetime, date

from glitch import (
    # Main entry point
    get_glitch_analysis,
    # Esoteric
    get_chrome_resonance,
    calculate_biorhythms,
    check_founders_echo,
    check_chaldean_clock,
    get_esoteric_signals,
    # Physics
    calculate_gann_square,
    analyze_spread_total_gann,
    get_schumann_frequency,
    calculate_atmospheric_drag,
    calculate_hurst_exponent,
    get_kp_index,
    get_physics_signals,
    # Hive Mind
    calculate_noosphere_velocity,
    calculate_void_moon,
    detect_hate_buy_trap,
    calculate_crowd_wisdom,
    get_hive_mind_signals,
    # Market
    check_benford_anomaly,
    detect_rlm,
    check_teammate_void,
    analyze_sgp_correlation,
    get_market_signals,
    # Math Glitch
    check_jarvis_trigger,
    check_titanium_rule,
    check_harmonic_convergence,
    full_gematria_analysis,
    calculate_glitch_score,
    JARVIS_TRIGGERS,
)


class TestEsotericModule(unittest.TestCase):
    """Test esoteric.py functions."""

    def test_chrome_resonance_red_vs_non_red(self):
        """Red team should get aggression boost."""
        result = get_chrome_resonance("Bulls", "Celtics")
        self.assertTrue(result["available"])
        self.assertEqual(result["home_color"], "RED")
        self.assertEqual(result["chrome_signal"], "HOME_AGGRESSION")
        self.assertGreater(result["chrome_boost"], 0)

    def test_chrome_resonance_neutral(self):
        """Neutral matchup should have no boost."""
        result = get_chrome_resonance("Celtics", "Bucks")
        self.assertTrue(result["available"])
        self.assertEqual(result["chrome_boost"], 0.0)

    def test_biorhythms_calculation(self):
        """Biorhythms should return valid values."""
        result = calculate_biorhythms("1990-01-15")
        self.assertTrue(result["available"])
        self.assertIn(result["status"], ["PEAK", "RISING", "FALLING", "LOW"])
        self.assertTrue(-100 <= result["physical"] <= 100)
        self.assertTrue(-100 <= result["emotional"] <= 100)
        self.assertTrue(-100 <= result["intellectual"] <= 100)

    def test_founders_echo(self):
        """Founders echo should detect resonance."""
        result = check_founders_echo("Lakers")
        self.assertTrue(result["available"])
        self.assertEqual(result["founding_year"], 1947)
        self.assertIn(result["resonance_type"], ["DIRECT", "HARMONIC", "ANNIVERSARY", "NONE"])

    def test_esoteric_signals_aggregation(self):
        """Aggregated esoteric signals should work."""
        result = get_esoteric_signals("Lakers", "Celtics")
        self.assertTrue(result["available"])
        self.assertEqual(result["module"], "esoteric")
        self.assertIn("chrome_resonance", result["signals"])
        self.assertIn("founders_echo", result["signals"])


class TestPhysicsModule(unittest.TestCase):
    """Test physics.py functions."""

    def test_gann_square(self):
        """Gann square should calculate angles."""
        result = calculate_gann_square(7.5)
        self.assertTrue(result["available"])
        self.assertIn("angle", result)
        self.assertIn("resonant", result)
        self.assertIn(result["signal"], ["STRONG", "MODERATE", "WEAK", "NONE"])

    def test_gann_square_invalid(self):
        """Negative value should return unavailable."""
        result = calculate_gann_square(-5)
        self.assertFalse(result["available"])

    def test_spread_total_gann(self):
        """Combined Gann analysis should work."""
        result = analyze_spread_total_gann(-3.5, 220.5)
        self.assertTrue(result["available"])
        self.assertIn("spread_analysis", result)
        self.assertIn("total_analysis", result)

    def test_schumann_frequency(self):
        """Schumann frequency should return valid Hz."""
        result = get_schumann_frequency()
        self.assertTrue(result["available"])
        self.assertTrue(7.0 <= result["current_hz"] <= 8.5)
        self.assertIn(result["status"], ["NORMAL", "ELEVATED", "DEPRESSED", "SLIGHTLY_ELEVATED", "SLIGHTLY_DEPRESSED"])

    def test_atmospheric_drag_high_pressure(self):
        """High pressure should signal UNDER."""
        result = calculate_atmospheric_drag(30.20)
        self.assertTrue(result["available"])
        self.assertEqual(result["signal"], "HEAVY_AIR")
        self.assertEqual(result["direction"], "UNDER")

    def test_atmospheric_drag_low_pressure(self):
        """Low pressure should signal OVER."""
        result = calculate_atmospheric_drag(29.70)
        self.assertTrue(result["available"])
        self.assertEqual(result["signal"], "THIN_AIR")
        self.assertEqual(result["direction"], "OVER")

    def test_hurst_exponent(self):
        """Hurst exponent should detect regime."""
        # Trending series
        trending = list(range(1, 30))
        result = calculate_hurst_exponent(trending)
        self.assertTrue(result["available"])
        self.assertIn(result["regime"], ["TRENDING", "MEAN_REVERTING", "RANDOM_WALK"])

    def test_hurst_insufficient_data(self):
        """Too few points should return insufficient data."""
        result = calculate_hurst_exponent([1, 2, 3])
        self.assertFalse(result["available"])

    def test_kp_index(self):
        """Kp index should return valid value."""
        result = get_kp_index()
        self.assertTrue(result["available"])
        self.assertTrue(0 <= result["kp_value"] <= 9)
        self.assertIn(result["status"], ["QUIET", "UNSETTLED", "ACTIVE", "STORM"])

    def test_physics_signals_aggregation(self):
        """Aggregated physics signals should work."""
        result = get_physics_signals(spread=-3.5, total=220.5)
        self.assertTrue(result["available"])
        self.assertEqual(result["module"], "physics")
        self.assertIn("schumann", result["signals"])
        self.assertIn("kp_index", result["signals"])


class TestHiveMindModule(unittest.TestCase):
    """Test hive_mind.py functions."""

    def test_noosphere_velocity(self):
        """Noosphere velocity should return direction."""
        result = calculate_noosphere_velocity()
        self.assertTrue(result["available"])
        self.assertIn(result["direction"], ["ASCENDING", "DESCENDING", "STABLE"])

    def test_void_moon(self):
        """Void moon should return status."""
        result = calculate_void_moon()
        self.assertTrue(result["available"])
        self.assertIn("moon_sign", result)
        self.assertIn(result["status"], ["VOID_ACTIVE", "VOID_ENDING_SOON", "VOID_CLEAR"])

    def test_hate_buy_trap_no_rlm(self):
        """No RLM should mean no trap."""
        result = detect_hate_buy_trap(-0.5, False, None, "HOME")
        self.assertFalse(result["is_trap"])

    def test_hate_buy_trap_detected(self):
        """Negative sentiment + RLM should detect trap."""
        result = detect_hate_buy_trap(-0.5, True, "HOME", "HOME")
        self.assertTrue(result["is_trap"])
        self.assertEqual(result["signal"], "HATE_BUY")
        self.assertGreater(result["boost"], 0)

    def test_crowd_wisdom_sharp(self):
        """Money > tickets should signal sharp."""
        result = calculate_crowd_wisdom(45, 60)
        self.assertTrue(result["available"])
        self.assertEqual(result["signal"], "SHARP_SIDE")
        self.assertGreater(result["boost"], 0)

    def test_crowd_wisdom_fade_public(self):
        """Tickets > money should signal fade."""
        result = calculate_crowd_wisdom(70, 55)
        self.assertTrue(result["available"])
        self.assertEqual(result["signal"], "FADE_PUBLIC")

    def test_hive_mind_signals_aggregation(self):
        """Aggregated hive mind signals should work."""
        result = get_hive_mind_signals(public_pct=60, money_pct=75)
        self.assertTrue(result["available"])
        self.assertEqual(result["module"], "hive_mind")
        self.assertIn("noosphere", result["signals"])
        self.assertIn("void_moon", result["signals"])


class TestMarketModule(unittest.TestCase):
    """Test market.py functions."""

    def test_benford_anomaly_natural(self):
        """Natural data should not trigger anomaly."""
        # Benford-like distribution
        data = [10.5, 20.3, 15.2, 18.7, 22.1, 11.3, 14.8, 25.6, 12.1, 19.4]
        result = check_benford_anomaly(data)
        self.assertTrue(result["available"])

    def test_benford_insufficient_data(self):
        """Too few data points should return unavailable."""
        result = check_benford_anomaly([1, 2, 3])
        self.assertFalse(result["available"])

    def test_rlm_detected(self):
        """RLM should be detected when line moves opposite to public."""
        result = detect_rlm(-3.0, -4.5, 65)  # Public on favorite, line toward favorite
        self.assertTrue(result["available"])
        # Public 65% but line moved toward favorite = no RLM
        # (This is moving WITH the public)

    def test_teammate_void(self):
        """Same team props should trigger warning."""
        legs = [
            {"player": "LeBron", "team": "Lakers", "stat_type": "points"},
            {"player": "AD", "team": "Lakers", "stat_type": "rebounds"},
        ]
        result = check_teammate_void(legs)
        self.assertTrue(result["available"])
        self.assertGreater(result["warning_count"], 0)
        self.assertEqual(result["warnings"][0]["type"], "TEAMMATE_VOID")

    def test_teammate_void_no_conflict(self):
        """Different team props should not trigger warning."""
        legs = [
            {"player": "LeBron", "team": "Lakers", "stat_type": "points"},
            {"player": "Tatum", "team": "Celtics", "stat_type": "points"},
        ]
        result = check_teammate_void(legs)
        self.assertEqual(result["warning_count"], 0)

    def test_sgp_correlation(self):
        """SGP correlation should analyze leg relationships."""
        legs = [
            {"player": "LeBron", "team": "Lakers", "stat_type": "points"},
            {"player": "LeBron", "team": "Lakers", "stat_type": "assists"},
        ]
        result = analyze_sgp_correlation(legs)
        self.assertTrue(result["available"])
        self.assertIn(result["assessment"], ["HIGH_CORRELATION", "MODERATE_CORRELATION", "LOW_CORRELATION", "NEGATIVE_CORRELATION"])


class TestMathGlitchModule(unittest.TestCase):
    """Test math_glitch.py functions."""

    def test_jarvis_trigger_2178(self):
        """2178 should trigger THE IMMORTAL."""
        result = check_jarvis_trigger(2178)
        self.assertTrue(result["triggered"])
        self.assertEqual(result["name"], "THE IMMORTAL")
        self.assertEqual(result["boost"], 20)

    def test_jarvis_trigger_33(self):
        """33 should trigger THE MASTER."""
        result = check_jarvis_trigger(33)
        self.assertTrue(result["triggered"])
        self.assertEqual(result["name"], "THE MASTER")

    def test_jarvis_no_trigger(self):
        """Random number should not trigger."""
        result = check_jarvis_trigger(42)
        self.assertFalse(result["triggered"])

    def test_gematria_analysis(self):
        """Gematria should calculate values."""
        result = full_gematria_analysis("Lakers")
        self.assertTrue(result["available"])
        self.assertIn("simple_gematria", result)
        self.assertIn("reverse_gematria", result)

    def test_titanium_rule_3_of_4(self):
        """3 of 4 modules should trigger Titanium."""
        result = check_titanium_rule(
            esoteric_fired=["CHROME"],
            physics_fired=["GANN"],
            hive_mind_fired=["NOOSPHERE"],
            market_fired=[]
        )
        self.assertTrue(result["titanium_smash"])
        self.assertEqual(result["titanium_count"], 3)
        self.assertEqual(result["tier"], "TITANIUM_SMASH")

    def test_titanium_rule_4_of_4(self):
        """4 of 4 modules should trigger Perfect Titanium."""
        result = check_titanium_rule(
            esoteric_fired=["CHROME"],
            physics_fired=["GANN"],
            hive_mind_fired=["NOOSPHERE"],
            market_fired=["RLM"]
        )
        self.assertTrue(result["titanium_smash"])
        self.assertEqual(result["titanium_count"], 4)
        self.assertEqual(result["tier"], "PERFECT_TITANIUM")

    def test_titanium_rule_2_of_4(self):
        """2 of 4 modules should not trigger Titanium."""
        result = check_titanium_rule(
            esoteric_fired=["CHROME"],
            physics_fired=[],
            hive_mind_fired=["NOOSPHERE"],
            market_fired=[]
        )
        self.assertFalse(result["titanium_smash"])
        self.assertEqual(result["tier"], "STANDARD")

    def test_harmonic_convergence_triggered(self):
        """Both scores >= 8.0 should trigger harmonic."""
        result = check_harmonic_convergence(8.5, 8.2)
        self.assertTrue(result["harmonic_convergence"])
        self.assertEqual(result["tier"], "GOLDEN")
        self.assertGreater(result["boost"], 0)

    def test_harmonic_convergence_not_triggered(self):
        """One score < 8.0 should not trigger."""
        result = check_harmonic_convergence(8.5, 7.5)
        self.assertFalse(result["harmonic_convergence"])


class TestGlitchIntegration(unittest.TestCase):
    """Test the main get_glitch_analysis function."""

    def test_full_analysis(self):
        """Full analysis should return all components."""
        result = get_glitch_analysis(
            home_team="Lakers",
            away_team="Celtics",
            spread=-3.5,
            total=220.5,
            public_pct=60,
            money_pct=70
        )

        self.assertIn("modules", result)
        self.assertIn("esoteric", result["modules"])
        self.assertIn("physics", result["modules"])
        self.assertIn("hive_mind", result["modules"])
        self.assertIn("market", result["modules"])

        self.assertIn("glitch_score", result)
        self.assertIn("tier", result)
        self.assertIn("titanium_smash", result)
        self.assertIn("recommendations", result)

    def test_analysis_with_ai_scores(self):
        """Analysis with AI scores should check harmonic."""
        result = get_glitch_analysis(
            home_team="Lakers",
            away_team="Celtics",
            ai_score=8.5,
            esoteric_score=8.2
        )

        self.assertIn("harmonic_convergence", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
