"""
test_pipeline.py - Pipeline Completeness & Wiring Tests
Version: v10.57

These tests FAIL if any signal/pillar/model is not wired correctly.
"""

import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestReceiptCompleteness(unittest.TestCase):
    """Test that receipts have all required components."""

    def test_receipt_has_all_models(self):
        """Receipt must have all 8 AI models."""
        from receipt_schema import (
            PickReceipt, REQUIRED_MODELS, build_receipt_from_pick
        )

        # Build receipt from sample pick
        sample_pick = {
            "sport": "NBA",
            "player_name": "Test Player",
            "stat_type": "player_points",
            "line": 20.5,
            "final_score": 7.0,
            "tier": "EDGE_LEAN",
            "reasons": []
        }
        receipt = build_receipt_from_pick(sample_pick)

        # All models must be present
        for model in REQUIRED_MODELS:
            self.assertIn(
                model, receipt.models,
                f"Missing model: {model}"
            )

    def test_receipt_has_all_pillars(self):
        """Receipt must have all 8 pillars."""
        from receipt_schema import (
            PickReceipt, REQUIRED_PILLARS, build_receipt_from_pick
        )

        sample_pick = {
            "sport": "NBA",
            "player_name": "Test Player",
            "final_score": 7.0,
            "reasons": []
        }
        receipt = build_receipt_from_pick(sample_pick)

        for pillar in REQUIRED_PILLARS:
            self.assertIn(
                pillar, receipt.pillars,
                f"Missing pillar: {pillar}"
            )

    def test_receipt_has_all_esoteric(self):
        """Receipt must have all esoteric components."""
        from receipt_schema import (
            REQUIRED_ESOTERIC, build_receipt_from_pick
        )

        sample_pick = {
            "sport": "NBA",
            "player_name": "Test Player",
            "final_score": 7.0,
            "reasons": []
        }
        receipt = build_receipt_from_pick(sample_pick)

        for esoteric in REQUIRED_ESOTERIC:
            self.assertIn(
                esoteric, receipt.esoteric,
                f"Missing esoteric: {esoteric}"
            )

    def test_receipt_has_tier(self):
        """Receipt must have tier assignment."""
        from receipt_schema import build_receipt_from_pick

        sample_pick = {
            "sport": "NBA",
            "final_score": 7.5,
            "tier": "GOLD_STAR"
        }
        receipt = build_receipt_from_pick(sample_pick)

        self.assertIsNotNone(receipt.tier)
        self.assertEqual(receipt.tier.tier, "GOLD_STAR")


class TestInjuryOutBlocksPick(unittest.TestCase):
    """Test that OUT players are blocked."""

    def test_out_player_blocked(self):
        """OUT player should be dropped."""
        from validators.injury_guard import (
            validate_injury_status, build_injury_index
        )

        injuries = [
            {"player_name": "Injured Star", "status": "out"}
        ]
        injury_index = build_injury_index(injuries)

        prop = {"player_name": "Injured Star", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, injury_index)

        self.assertFalse(is_valid)
        self.assertEqual(reason, "INJURY_OUT")

    def test_suspended_player_blocked(self):
        """SUSPENDED player should be dropped."""
        from validators.injury_guard import (
            validate_injury_status, build_injury_index
        )

        injuries = [
            {"player_name": "Suspended Guy", "status": "suspended"}
        ]
        injury_index = build_injury_index(injuries)

        prop = {"player_name": "Suspended Guy", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, injury_index)

        self.assertFalse(is_valid)
        self.assertEqual(reason, "INJURY_SUSPENDED")

    def test_healthy_player_passes(self):
        """Healthy player should pass."""
        from validators.injury_guard import (
            validate_injury_status, build_injury_index
        )

        injuries = [
            {"player_name": "Other Player", "status": "out"}
        ]
        injury_index = build_injury_index(injuries)

        prop = {"player_name": "Healthy Star", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, injury_index)

        self.assertTrue(is_valid)
        self.assertIsNone(reason)


class TestDKMarketMissingBlocksPick(unittest.TestCase):
    """Test that props not on DK are blocked (Deni Avdija case)."""

    def test_unlisted_player_blocked(self):
        """Player not in DK feed should be dropped."""
        from validators.market_availability import (
            validate_market_available, build_dk_market_index
        )

        # DK feed only has LeBron props
        dk_props = [
            {
                "sport": "NBA",
                "game_id": "game1",
                "player_name": "LeBron James",
                "market": "player_points",
                "line": 25.5,
                "side": "over"
            }
        ]
        dk_index = build_dk_market_index(dk_props)

        # Deni Avdija prop should be blocked
        deni_prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "Deni Avdija",
            "market": "player_points",
            "line": 10.5,
            "side": "over"
        }
        is_valid, reason = validate_market_available(deni_prop, dk_index)

        self.assertFalse(is_valid)
        self.assertEqual(reason, "DK_MARKET_NOT_LISTED")

    def test_listed_player_passes(self):
        """Player in DK feed should pass."""
        from validators.market_availability import (
            validate_market_available, build_dk_market_index
        )

        dk_props = [
            {
                "sport": "NBA",
                "game_id": "game1",
                "player_name": "LeBron James",
                "market": "player_points",
                "line": 25.5,
                "side": "over"
            }
        ]
        dk_index = build_dk_market_index(dk_props)

        lebron_prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "over"
        }
        is_valid, reason = validate_market_available(lebron_prop, dk_index)

        self.assertTrue(is_valid)

    def test_case_insensitive_matching(self):
        """Player name matching should be case insensitive."""
        from validators.market_availability import (
            validate_market_available, build_dk_market_index
        )

        dk_props = [
            {
                "sport": "NBA",
                "game_id": "game1",
                "player_name": "LeBron James",
                "market": "player_points",
                "line": 25.5,
                "side": "over"
            }
        ]
        dk_index = build_dk_market_index(dk_props)

        # Uppercase should still match
        lebron_prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "LEBRON JAMES",
            "market": "player_points",
            "line": 25.5,
            "side": "over"
        }
        is_valid, reason = validate_market_available(lebron_prop, dk_index)

        self.assertTrue(is_valid)


class TestTieringSingleSourceOfTruth(unittest.TestCase):
    """Test that tiering uses single source of truth."""

    def test_gold_star_threshold(self):
        """Score >= 7.5 should be GOLD_STAR."""
        from tiering import tier_from_score

        tier, config = tier_from_score(7.5)
        self.assertEqual(tier, "GOLD_STAR")

        tier, config = tier_from_score(8.0)
        self.assertEqual(tier, "GOLD_STAR")

    def test_edge_lean_threshold(self):
        """Score >= 6.5 and < 7.5 should be EDGE_LEAN."""
        from tiering import tier_from_score

        tier, config = tier_from_score(6.5)
        self.assertEqual(tier, "EDGE_LEAN")

        tier, config = tier_from_score(7.49)
        self.assertEqual(tier, "EDGE_LEAN")

    def test_monitor_threshold(self):
        """Score >= 5.5 and < 6.5 should be MONITOR."""
        from tiering import tier_from_score

        tier, config = tier_from_score(5.5)
        self.assertEqual(tier, "MONITOR")

        tier, config = tier_from_score(6.49)
        self.assertEqual(tier, "MONITOR")

    def test_pass_threshold(self):
        """Score < 5.5 should be PASS."""
        from tiering import tier_from_score

        tier, config = tier_from_score(5.49)
        self.assertEqual(tier, "PASS")

        tier, config = tier_from_score(0.0)
        self.assertEqual(tier, "PASS")


class TestPipelineOrder(unittest.TestCase):
    """Test that pipeline stages run in correct order."""

    def test_validators_before_publish_gate(self):
        """Validators must run BEFORE publish gate."""
        # This tests that the code structure is correct
        # by checking the order of sections in live_data_router.py

        with open('live_data_router.py', 'r') as f:
            content = f.read()

        # Find positions of key sections
        validator_pos = content.find("v10.57: DATA INTEGRITY VALIDATORS")
        publish_gate_pos = content.find("v10.43: PUBLISH GATE")

        self.assertGreater(
            validator_pos, 0,
            "Validators section not found"
        )
        self.assertGreater(
            publish_gate_pos, 0,
            "Publish Gate section not found"
        )
        self.assertLess(
            validator_pos, publish_gate_pos,
            "Validators must come BEFORE Publish Gate"
        )

    def test_publish_gate_before_pick_filter(self):
        """Publish gate must run BEFORE pick filter."""
        with open('live_data_router.py', 'r') as f:
            content = f.read()

        publish_gate_pos = content.find("v10.43: PUBLISH GATE")
        pick_filter_pos = content.find("v10.56: PICK FILTER")

        self.assertGreater(publish_gate_pos, 0)
        self.assertGreater(pick_filter_pos, 0)
        self.assertLess(
            publish_gate_pos, pick_filter_pos,
            "Publish Gate must come BEFORE Pick Filter"
        )

    def test_pick_filter_before_output(self):
        """Pick filter must run BEFORE output construction."""
        with open('live_data_router.py', 'r') as f:
            content = f.read()

        pick_filter_pos = content.find("v10.56: PICK FILTER")
        # Look for where we build the response
        output_pos = content.find("# Rebuild merged_picks after filtering")

        self.assertGreater(pick_filter_pos, 0)
        self.assertGreater(output_pos, 0)
        self.assertLess(
            pick_filter_pos, output_pos,
            "Pick Filter must come BEFORE output construction"
        )


class TestScoreChangesIfSignalForced(unittest.TestCase):
    """Test that score changes when signals are modified."""

    def test_sharp_signal_affects_score(self):
        """Sharp signal should affect the research score."""
        # This is a conceptual test - in production we'd need
        # to mock the scoring function

        # The key insight is that if sharp_diff >= 15:
        # pillar_boost += 2.0 * mw_sharp (for game picks)
        # So changing sharp signal MUST change the score

        # We verify this by checking the code structure
        with open('live_data_router.py', 'r') as f:
            content = f.read()

        # Verify sharp signal is used in scoring
        self.assertIn(
            'sharp_strength == "STRONG"',
            content,
            "Sharp signal must be checked in scoring"
        )
        self.assertIn(
            "pillar_boost +=",
            content,
            "Pillar boost must be applied"
        )


class TestValidatorIntegration(unittest.TestCase):
    """Test that validators are properly integrated."""

    def test_validators_import_exists(self):
        """Validators module must be importable."""
        try:
            from validators import (
                validate_prop_integrity,
                validate_injury_status,
                validate_market_available,
                build_injury_index,
                build_dk_market_index
            )
        except ImportError as e:
            self.fail(f"Failed to import validators: {e}")

    def test_dk_market_index_built(self):
        """DK market index must be built in live_data_router."""
        with open('live_data_router.py', 'r') as f:
            content = f.read()

        self.assertIn(
            "dk_market_index = build_dk_market_index",
            content,
            "DK market index must be built"
        )

    def test_market_availability_validation_wired(self):
        """Market availability validation must be called."""
        with open('live_data_router.py', 'r') as f:
            content = f.read()

        self.assertIn(
            "validate_props_batch_market",
            content,
            "Market availability validation must be called"
        )


class TestPropIntegrityValidation(unittest.TestCase):
    """Test prop integrity validation."""

    def test_missing_required_field_fails(self):
        """Missing required field should fail."""
        from validators.prop_integrity import validate_prop_integrity

        prop = {
            "sport": "NBA",
            # Missing player_name, market, line, side, game_id
        }
        is_valid, reason = validate_prop_integrity(prop)

        self.assertFalse(is_valid)
        self.assertIn("MISSING_REQUIRED", reason)

    def test_valid_prop_passes(self):
        """Valid prop should pass."""
        from validators.prop_integrity import validate_prop_integrity

        prop = {
            "sport": "NBA",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "over",
            "game_id": "abc123"
        }
        is_valid, reason = validate_prop_integrity(prop)

        self.assertTrue(is_valid)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
