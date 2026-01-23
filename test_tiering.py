"""
test_tiering.py - Unit tests for tiering module

Verifies tier boundary behavior using DEFAULT_TIERS:
- GOLD_STAR: score >= 7.5
- EDGE_LEAN: 6.5 <= score < 7.5
- MONITOR: 5.5 <= score < 6.5
- PASS: score < 5.5
"""

import unittest
from tiering import tier_from_score, DEFAULT_TIERS, clamp_score


class TestTierFromScore(unittest.TestCase):
    """Test tier_from_score with canonical thresholds."""

    def test_gold_star_boundary(self):
        """7.51 should be GOLD_STAR."""
        tier, badge = tier_from_score(7.51)
        self.assertEqual(tier, "GOLD_STAR")

    def test_gold_star_exact(self):
        """7.5 exactly should be GOLD_STAR."""
        tier, _ = tier_from_score(7.5)
        self.assertEqual(tier, "GOLD_STAR")

    def test_edge_lean_boundary(self):
        """6.51 should be EDGE_LEAN."""
        tier, badge = tier_from_score(6.51)
        self.assertEqual(tier, "EDGE_LEAN")

    def test_edge_lean_exact(self):
        """6.5 exactly should be EDGE_LEAN."""
        tier, _ = tier_from_score(6.5)
        self.assertEqual(tier, "EDGE_LEAN")

    def test_monitor_boundary(self):
        """5.51 should be MONITOR."""
        tier, badge = tier_from_score(5.51)
        self.assertEqual(tier, "MONITOR")

    def test_monitor_exact(self):
        """5.5 exactly should be MONITOR."""
        tier, _ = tier_from_score(5.5)
        self.assertEqual(tier, "MONITOR")

    def test_pass_boundary(self):
        """5.49 should be PASS."""
        tier, badge = tier_from_score(5.49)
        self.assertEqual(tier, "PASS")

    def test_real_world_case_6_89(self):
        """6.89 should be EDGE_LEAN (the bug case)."""
        tier, _ = tier_from_score(6.89)
        self.assertEqual(tier, "EDGE_LEAN")

    def test_real_world_case_6_72(self):
        """6.72 should be EDGE_LEAN."""
        tier, _ = tier_from_score(6.72)
        self.assertEqual(tier, "EDGE_LEAN")

    def test_custom_tiers_not_mutated(self):
        """Custom tiers dict should not be mutated."""
        custom = {"GOLD_STAR": 8.0}
        original = custom.copy()
        tier_from_score(7.6, custom)
        self.assertEqual(custom, original)


class TestClampScore(unittest.TestCase):
    """Test score clamping."""

    def test_clamp_high(self):
        self.assertEqual(clamp_score(15.0), 10.0)

    def test_clamp_low(self):
        self.assertEqual(clamp_score(-5.0), 0.0)

    def test_clamp_none(self):
        self.assertEqual(clamp_score(None), 0.0)

    def test_clamp_string(self):
        self.assertEqual(clamp_score("invalid"), 0.0)


class TestDefaultTiers(unittest.TestCase):
    """Test DEFAULT_TIERS structure."""

    def test_expected_values(self):
        self.assertEqual(DEFAULT_TIERS["GOLD_STAR"], 7.5)
        self.assertEqual(DEFAULT_TIERS["EDGE_LEAN"], 6.5)
        self.assertEqual(DEFAULT_TIERS["MONITOR"], 5.5)
        self.assertEqual(DEFAULT_TIERS["PASS"], 0.0)


if __name__ == "__main__":
    unittest.main()
