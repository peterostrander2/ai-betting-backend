"""
Tests for v15.2 Esoteric Engine scoring.
Validates: per-pick variability, bounded output, no runaway inflation.
"""
import hashlib
import pytest


# ---------------------------------------------------------------------------
# Helpers — replicate the esoteric math from live_data_router.py so tests
# stay self-contained (no need to import the full router).
# ---------------------------------------------------------------------------

# v20.28.6: Learning Loop Tuned weights based on Feb 14 grading
# vortex reduced 0.15→0.08 (negative -0.125 correlation, worst performer)
# fib reduced 0.15→0.10 (negative -0.06 correlation)
# Redistributed to numerology and daily_edge (stable performers)
ESOTERIC_WEIGHTS = {
    "numerology": 0.40,
    "astro": 0.27,
    "fib": 0.10,
    "vortex": 0.08,
    "daily_edge": 0.15,
}

# Fibonacci sequence used by Jarvis
FIBONACCI_SEQUENCE = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]
VORTEX_PATTERN = [1, 2, 4, 8, 7, 5]
TESLA_NUMBERS = {3, 6, 9}


def _fib_modifier(magnitude: float) -> float:
    """Replicate fib scoring logic."""
    abs_line = abs(magnitude)
    is_fib = abs_line in FIBONACCI_SEQUENCE
    nearest_fib = min(FIBONACCI_SEQUENCE, key=lambda x: abs(x - abs_line))
    near_fib = abs(abs_line - nearest_fib) <= 0.5
    phi_aligned = False
    for fib in FIBONACCI_SEQUENCE[:10]:
        if fib > 0:
            ratio = abs_line / fib
            if 1.5 <= ratio <= 1.7:
                phi_aligned = True
                break
    if is_fib:
        raw = 0.10
    elif near_fib:
        raw = 0.05
    elif phi_aligned:
        raw = 0.07
    else:
        raw = 0.0
    return min(0.6, raw * 6.0) if raw > 0 else 0.0


def _vortex_modifier(magnitude: float) -> float:
    """Replicate vortex scoring logic."""
    value = int(abs(magnitude * 10)) if magnitude else 0
    reduction = value
    while reduction > 9:
        reduction = sum(int(d) for d in str(reduction))
    if reduction == 0:
        return 0.0
    is_tesla = reduction in TESLA_NUMBERS
    in_vortex = reduction in VORTEX_PATTERN
    if is_tesla:
        raw = 0.15
    elif in_vortex:
        raw = 0.08
    else:
        raw = 0.0
    return min(0.7, raw * 5.0) if raw > 0 else 0.0


def compute_esoteric(
    game_str: str,
    prop_line: float = 0,
    player_name: str = "",
    spread: float = 0,
    total: float = 220,
    astro_overall: float = 50,
    daily_energy_score: float = 50,
    day_of_year: int = 27,
    trap_mod: float = 0,
) -> dict:
    """Pure-function replica of the v15.2 esoteric scoring block."""
    # A) Magnitude
    _eso_magnitude = abs(spread) if spread else 0
    if _eso_magnitude == 0 and prop_line:
        _eso_magnitude = abs(prop_line)
    if _eso_magnitude == 0:
        _eso_magnitude = abs(total / 10) if total and total != 220 else 0

    # B) Numerology — pick-specific via SHA-256
    daily_base = (day_of_year % 9 + 1) / 9
    _pick_hash = hashlib.sha256(f"{game_str}|{prop_line}|{player_name}".encode()).hexdigest()
    _pick_seed = int(_pick_hash[:8], 16) % 9 + 1
    pick_factor = _pick_seed / 9
    numerology_raw = (daily_base * 0.4) + (pick_factor * 0.6)
    if "11" in game_str or "22" in game_str or "33" in game_str:
        numerology_raw = min(1.0, numerology_raw * 1.3)
    numerology_score = numerology_raw * 10 * ESOTERIC_WEIGHTS["numerology"]

    # Fib
    fib_scaled = _fib_modifier(_eso_magnitude)
    fib_score = fib_scaled * 10 * ESOTERIC_WEIGHTS["fib"]

    # Vortex
    vortex_scaled = _vortex_modifier(_eso_magnitude)
    vortex_score = vortex_scaled * 10 * ESOTERIC_WEIGHTS["vortex"]

    # Astro — linear 0-100 → 0-10
    astro_score = (astro_overall / 100) * 10 * ESOTERIC_WEIGHTS["astro"]

    # Daily edge
    daily_edge_score = 0.0
    if daily_energy_score >= 85:
        daily_edge_score = 10 * ESOTERIC_WEIGHTS["daily_edge"]
    elif daily_energy_score >= 70:
        daily_edge_score = 7 * ESOTERIC_WEIGHTS["daily_edge"]
    elif daily_energy_score >= 55:
        daily_edge_score = 4 * ESOTERIC_WEIGHTS["daily_edge"]

    esoteric_raw = numerology_score + astro_score + fib_score + vortex_score + daily_edge_score + trap_mod
    esoteric_score = max(0, min(10, esoteric_raw))

    return {
        "score": esoteric_score,
        "magnitude": _eso_magnitude,
        "numerology": numerology_score,
        "astro": astro_score,
        "fib": fib_score,
        "vortex": vortex_score,
        "daily_edge": daily_edge_score,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

SAMPLE_PROPS = [
    {"game_str": "Utah Mammoth@Florida PanthersDylan Guenther", "prop_line": 2.5, "player": "Dylan Guenther", "spread": -1.5, "total": 6.5},
    {"game_str": "Nashville Predators@Boston BruinsJeremy Swayman", "prop_line": 0.5, "player": "Jeremy Swayman", "spread": -2.5, "total": 5.5},
    {"game_str": "Colorado Avalanche@Dallas StarsMikko Rantanen", "prop_line": 24.5, "player": "Mikko Rantanen", "spread": 1.5, "total": 6.0},
    {"game_str": "Minnesota Wild@Seattle KrakenKirill Kaprizov", "prop_line": 3.5, "player": "Kirill Kaprizov", "spread": -3.0, "total": 6.0},
    {"game_str": "Edmonton Oilers@Calgary FlamesConnor McDavid", "prop_line": 1.5, "player": "Connor McDavid", "spread": -1.5, "total": 6.5},
    {"game_str": "Tampa Bay Lightning@Ottawa SenatorsNikita Kucherov", "prop_line": 0.5, "player": "Nikita Kucherov", "spread": 2.0, "total": 6.5},
    {"game_str": "New York Rangers@Buffalo SabresArtemi Panarin", "prop_line": 5.5, "player": "Artemi Panarin", "spread": -3.5, "total": 6.0},
    {"game_str": "Detroit Red Wings@Chicago BlackhawksLucas Raymond", "prop_line": 2.5, "player": "Lucas Raymond", "spread": -1.0, "total": 5.5},
    {"game_str": "Vancouver Canucks@Winnipeg JetsElias Pettersson", "prop_line": 0.5, "player": "Elias Pettersson", "spread": 4.5, "total": 6.5},
    {"game_str": "Los Angeles Kings@Anaheim DucksAdrian Kempe", "prop_line": 3.5, "player": "Adrian Kempe", "spread": -2.0, "total": 5.5},
]


def test_esoteric_not_near_zero():
    """Median esoteric for a sample of 10 varied props should be >= 2.0."""
    scores = []
    for p in SAMPLE_PROPS:
        r = compute_esoteric(p["game_str"], p["prop_line"], p["player"], p["spread"], p["total"])
        scores.append(r["score"])
    scores.sort()
    median = scores[len(scores) // 2]
    assert median >= 2.0, f"Median esoteric {median:.2f} is below 2.0; scores={[round(s,2) for s in scores]}"


def test_pick_variability():
    """Different props on same day must NOT all have identical esoteric scores."""
    scores = set()
    for p in SAMPLE_PROPS:
        r = compute_esoteric(p["game_str"], p["prop_line"], p["player"], p["spread"], p["total"])
        scores.add(round(r["score"], 2))
    # At least 3 distinct scores across 10 picks (was: all identical at ~1.16)
    assert len(scores) >= 3, f"Only {len(scores)} distinct esoteric scores across 10 picks: {sorted(scores)}"
    # Range should be at least 0.3
    score_range = max(scores) - min(scores)
    assert score_range >= 0.3, f"Score range too narrow: {score_range:.2f} across {sorted(scores)}"


def test_no_runaway():
    """Esoteric average across sample props should not exceed 7.0."""
    scores = []
    for p in SAMPLE_PROPS:
        r = compute_esoteric(p["game_str"], p["prop_line"], p["player"], p["spread"], p["total"])
        scores.append(r["score"])
    avg = sum(scores) / len(scores)
    assert avg <= 7.0, f"Average esoteric {avg:.2f} exceeds 7.0 cap"


def test_max_cap():
    """Esoteric score is always <= 10.0 even with best-case inputs."""
    r = compute_esoteric(
        "Master11Number22Game33",
        prop_line=8.0,
        player_name="TestPlayer",
        spread=8.0,
        total=6.5,
        astro_overall=100,
        daily_energy_score=100,
    )
    assert r["score"] <= 10.0, f"Esoteric {r['score']:.2f} exceeds 10.0"


def test_fib_vortex_bounded():
    """Combined fib+vortex never exceeds 3.0 (their weight share = 30%)."""
    # Test with various magnitudes including fibonacci numbers
    for mag in [0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 100, 144, 0.5, 1.5, 2.5, 24.5]:
        r = compute_esoteric("TestGame", prop_line=mag, player_name="P", spread=mag)
        combined = r["fib"] + r["vortex"]
        assert combined <= 3.0, f"fib+vortex={combined:.2f} exceeds 3.0 at magnitude={mag}"


def test_confluence_divergence_still_works():
    """When research >> esoteric by 4+ pts, alignment should be < 60% (DIVERGENT)."""
    # Simulate: research=9.0, esoteric=3.0
    research = 9.0
    esoteric = 3.0
    alignment = 1 - abs(research - esoteric) / 10
    alignment_pct = alignment * 100
    assert alignment_pct < 60, f"Alignment {alignment_pct:.1f}% should be < 60% for DIVERGENT"

    # Even moderate gap: research=7.0, esoteric=2.5
    alignment2 = 1 - abs(7.0 - 2.5) / 10
    assert alignment2 * 100 < 60, f"Alignment {alignment2*100:.1f}% should be < 60%"


def test_deterministic():
    """Same inputs produce same esoteric score across calls."""
    kwargs = {"game_str": "TestGame", "prop_line": 2.5, "player_name": "Player", "spread": 1.5, "total": 6.5}
    r1 = compute_esoteric(**kwargs)
    r2 = compute_esoteric(**kwargs)
    assert r1["score"] == r2["score"], f"Non-deterministic: {r1['score']} != {r2['score']}"
    assert r1["numerology"] == r2["numerology"]


def test_props_no_spread_zero_magnitude():
    """Props with spread=0 should use prop_line as magnitude, not 0."""
    r = compute_esoteric("GameAPlayerX", prop_line=2.5, player_name="X", spread=0, total=220)
    assert r["magnitude"] == 2.5, f"Magnitude should be 2.5 (prop_line), got {r['magnitude']}"


def test_astro_neutral_contributes():
    """Astro at neutral (50) should contribute ~1.25, not 0.0."""
    r = compute_esoteric("Test", prop_line=1.0, player_name="P", astro_overall=50)
    assert r["astro"] >= 1.0, f"Astro at neutral should be ~1.25, got {r['astro']:.2f}"


def test_daily_edge_fires_at_55():
    """Daily edge should fire at score >= 55 (new threshold)."""
    r = compute_esoteric("Test", prop_line=1.0, player_name="P", daily_energy_score=55)
    assert r["daily_edge"] > 0, f"Daily edge should fire at 55, got {r['daily_edge']}"
    r2 = compute_esoteric("Test", prop_line=1.0, player_name="P", daily_energy_score=50)
    assert r2["daily_edge"] == 0, f"Daily edge should NOT fire at 50"
