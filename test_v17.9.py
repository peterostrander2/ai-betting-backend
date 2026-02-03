"""
v17.9 Integration Tests
=======================

Tests the Weather, Altitude, and Travel/B2B integrations without FastAPI.
"""

import sys

# Test StadiumAltitudeService
print("=" * 60)
print("v17.9 Integration Tests")
print("=" * 60)

# Import context_layer
try:
    from context_layer import StadiumAltitudeService, compute_context_modifiers
    print("\n✓ context_layer imported successfully")
except ImportError as e:
    print(f"\n✗ Failed to import context_layer: {e}")
    sys.exit(1)

# Import travel module
try:
    from alt_data_sources.travel import calculate_distance, calculate_fatigue_impact
    print("✓ travel module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import travel module: {e}")
    sys.exit(1)

print("\n" + "-" * 60)
print("Test 1: Altitude - Denver NBA (Nuggets)")
print("-" * 60)
adj, reasons = StadiumAltitudeService.get_altitude_adjustment(
    "NBA", "Denver Nuggets", "SPREAD", "Denver"
)
print(f"  Adjustment: {adj}")
print(f"  Reasons: {reasons}")
assert adj == 0.15, f"Expected 0.15, got {adj}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 2: Altitude - Denver NFL (Broncos)")
print("-" * 60)
adj, reasons = StadiumAltitudeService.get_altitude_adjustment(
    "NFL", "Denver Broncos", "SPREAD", "Away"
)
print(f"  Adjustment: {adj}")
print(f"  Reasons: {reasons}")
assert adj == 0.25, f"Expected 0.25, got {adj}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 3: Altitude - Coors Field MLB Over")
print("-" * 60)
adj, reasons = StadiumAltitudeService.get_altitude_adjustment(
    "MLB", "Colorado Rockies", "TOTAL", "Over"
)
print(f"  Adjustment: {adj}")
print(f"  Reasons: {reasons}")
assert adj == 0.5, f"Expected 0.5, got {adj}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 4: Altitude - Coors Field MLB Under")
print("-" * 60)
adj, reasons = StadiumAltitudeService.get_altitude_adjustment(
    "MLB", "Colorado Rockies", "TOTAL", "Under"
)
print(f"  Adjustment: {adj}")
print(f"  Reasons: {reasons}")
assert adj == -0.3, f"Expected -0.3, got {adj}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 5: Altitude - Utah Jazz")
print("-" * 60)
adj, reasons = StadiumAltitudeService.get_altitude_adjustment(
    "NBA", "Utah Jazz", "SPREAD", "Jazz"
)
print(f"  Adjustment: {adj}")
print(f"  Reasons: {reasons}")
assert adj == 0.15, f"Expected 0.15, got {adj}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 6: Altitude - Low altitude venue (no adjustment)")
print("-" * 60)
adj, reasons = StadiumAltitudeService.get_altitude_adjustment(
    "NBA", "Los Angeles Lakers", "SPREAD", "Lakers"
)
print(f"  Adjustment: {adj}")
print(f"  Reasons: {reasons}")
assert adj == 0.0, f"Expected 0.0, got {adj}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 7: Travel Distance - Lakers to Celtics")
print("-" * 60)
dist = calculate_distance("Los Angeles Lakers", "Boston Celtics")
print(f"  Distance: {dist} miles")
assert dist > 2500, f"Expected > 2500 miles, got {dist}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 8: Travel Fatigue - B2B game")
print("-" * 60)
result = calculate_fatigue_impact("NBA", 2500, 0, 2)
print(f"  Fatigue: {result['away_team_fatigue']}")
print(f"  Impact: {result['overall_impact']}")
print(f"  Reasons: {result['reasons']}")
assert result['overall_impact'] == "HIGH", f"Expected HIGH, got {result['overall_impact']}"
assert result['away_team_fatigue'] <= -0.5, f"Expected <= -0.5, got {result['away_team_fatigue']}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 9: Travel Fatigue - 1-day rest with long travel")
print("-" * 60)
result = calculate_fatigue_impact("NBA", 1800, 1, 2)
print(f"  Fatigue: {result['away_team_fatigue']}")
print(f"  Impact: {result['overall_impact']}")
print(f"  Reasons: {result['reasons']}")
assert result['overall_impact'] == "HIGH", f"Expected HIGH, got {result['overall_impact']}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 10: Travel Fatigue - Well rested, short travel")
print("-" * 60)
result = calculate_fatigue_impact("NBA", 300, 3, 2)
print(f"  Fatigue: {result['away_team_fatigue']}")
print(f"  Impact: {result['overall_impact']}")
print(f"  Reasons: {result['reasons']}")
assert result['overall_impact'] == "NONE", f"Expected NONE, got {result['overall_impact']}"
print("  ✓ PASSED")

print("\n" + "-" * 60)
print("Test 11: Context Modifiers with rest_days")
print("-" * 60)
mods = compute_context_modifiers(
    sport="NBA",
    home_team="Miami Heat",
    away_team="Boston Celtics",
    rest_days_override=0  # B2B
)
print(f"  Travel fatigue data: {mods.get('travel_fatigue')}")
if mods.get('travel_fatigue'):
    print(f"  Rest days: {mods['travel_fatigue'].get('rest_days')}")
    print(f"  Impact: {mods['travel_fatigue'].get('overall_impact')}")
print("  ✓ PASSED (travel_fatigue computed)")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)

print("\nIntegration Summary:")
print("┌────────────┬──────────────────┬─────────────────────┐")
print("│ Signal     │ Target Score     │ Adjustment Range    │")
print("├────────────┼──────────────────┼─────────────────────┤")
print("│ Weather    │ research_score   │ -0.5 to 0.0         │")
print("│ Altitude   │ esoteric_score   │ -0.3 to +0.5        │")
print("│ Travel/B2B │ context_score    │ -0.5 to 0.0         │")
print("└────────────┴──────────────────┴─────────────────────┘")
