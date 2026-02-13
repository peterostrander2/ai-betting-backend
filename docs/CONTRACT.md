# Scoring Contract - Canonical Reference

**Version:** v20.21
**Status:** FROZEN (No scoring semantics changes allowed)
**Last Updated:** 2026-02-13
**Source of Truth:** `core/scoring_contract.py`

---

## Overview

This document is the canonical reference for the ai-betting-backend scoring system. All values documented here are enforced by the Golden Run regression gate (`tests/test_golden_run.py`).

**Freeze Policy:** The backend scoring semantics are frozen. Any changes to weights, thresholds, or tier logic require explicit approval and must pass all regression gates.

---

## Engine Weights

The scoring system uses 4 weighted engines that sum to 1.00:

| Engine | Weight | Description |
|--------|--------|-------------|
| **AI** | 0.25 (25%) | 8 AI models with dynamic calibration |
| **Research** | 0.35 (35%) | Sharp money, line variance, public fade |
| **Esoteric** | 0.15 (15%) | Numerology, astro, fib, vortex signals |
| **Jarvis** | 0.25 (25%) | Gematria, sacred triggers, hybrid blend |

**Formula:**
```
BASE_4 = (ai_score × 0.25) + (research_score × 0.35) + (esoteric_score × 0.15) + (jarvis_score × 0.25)
```

**Context Modifier:** Applied as a bounded modifier (NOT an engine):
- Range: [-0.35, +0.35]
- Components: Defensive Rank (50%), Pace (30%), Vacuum (20%)

---

## Score Thresholds

| Type | Threshold | Constant | Description |
|------|-----------|----------|-------------|
| **Games** | 7.0 | `MIN_FINAL_SCORE` | Minimum score for game picks to be returned |
| **Props** | 6.5 | `MIN_PROPS_SCORE` | Lower threshold (SERP disabled for props) |
| **Gold Star** | 7.5 | `GOLD_STAR_THRESHOLD` | Minimum for GOLD_STAR tier assignment |

**Why different thresholds?**
Props cannot receive SERP boosts (+4.3 max) that game picks receive. The lower threshold maintains quality while accounting for this structural scoring disadvantage.

---

## Tier Classification

### Valid Output Tiers (Returned to API)

| Tier | Requirements | Description |
|------|--------------|-------------|
| **TITANIUM_SMASH** | ≥3 of 4 engines ≥ 8.0 | Top-tier multi-engine conviction |
| **GOLD_STAR** | score ≥ 7.5 + all gates pass | High conviction with hard gates |
| **EDGE_LEAN** | score ≥ 6.5 (games: 7.0) | Standard actionable pick |

### Hidden Tiers (Internal Only)

| Tier | Score Range | Purpose |
|------|-------------|---------|
| **MONITOR** | 5.5 - 6.5 | Track but don't surface |
| **PASS** | < 5.5 | No action recommended |

**Critical Rule:** Hidden tiers (`MONITOR`, `PASS`) are NEVER returned to API consumers. They are filtered at the output boundary.

---

## Gold Star Hard Gates

A pick must pass ALL gates to achieve GOLD_STAR tier:

| Gate | Threshold | Purpose |
|------|-----------|---------|
| `ai_score` | ≥ 6.8 | AI models must show conviction |
| `research_score` | ≥ 6.5 | Real market signals required |
| `jarvis_score` | ≥ 6.5 | Jarvis triggers must fire |
| `esoteric_score` | ≥ 5.5 | Esoteric components must contribute |

If ANY gate fails, the pick is downgraded to EDGE_LEAN.

---

## Titanium Rule

**Invariant:** `titanium_triggered = true` ONLY when ≥3 of 4 base engines ≥ 8.0

| Condition | Titanium Status |
|-----------|-----------------|
| 0-2 engines ≥ 8.0 | `false` |
| 3-4 engines ≥ 8.0 | `true` |

**Boundary:** Score of exactly 8.0 qualifies. Score of 7.99 does NOT.

---

## Boost Caps

| Boost | Cap | Source |
|-------|-----|--------|
| **Confluence** | 1.5 | Engine alignment |
| **MSRF** | 1.0 | Resonance signals |
| **Jason Sim** | ±1.5 | Post-pick confluence |
| **SERP** | 4.3 | Web search intelligence |
| **Total Boost** | 1.5 | Sum of confluence+msrf+jason+serp |

**Total Boost Cap:** Prevents score inflation from stacking multiple boosts on mediocre base scores.

---

## Confluence Levels

| Level | Boost | Condition |
|-------|-------|-----------|
| **IMMORTAL** | +1.5 | Perfect alignment + Jarvis ≥7.5 |
| **JARVIS_PERFECT** | +1.5 | Jarvis-driven perfect score |
| **PERFECT** | +1.5 | All engines aligned |
| **HARMONIC_CONVERGENCE** | +1.5 | Research + Esoteric both ≥ threshold |
| **STRONG** | +1.0 | Alignment ≥80% + active signal |
| **MODERATE** | +0.3 | Alignment ≥60% |
| **DIVERGENT** | 0.0 | Alignment <60% |

**Harmonic Convergence Threshold:** 7.5 (both Research AND Esoteric must be ≥7.5)

---

## Jarvis Hybrid Configuration (v2.2.1)

The Jarvis engine uses a hybrid blend of Jarvis and OPHIS signals:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| **Jarvis Weight** | 0.65 | Weight for Jarvis component |
| **OPHIS Weight** | 0.35 | Weight for OPHIS component |
| **Scale Factor** | 5.0 | OPHIS normalization factor |
| **Saturation Bound** | ±0.75 | Maximum OPHIS adjustment |
| **Baseline** | 4.5 | Score when inputs present but no triggers |

**Blend Formula:**
```
hybrid_score = (jarvis_score × 0.65) + (ophis_normalized × 0.35)
```

---

## Required Integration Health

### Critical Integrations (Block on Failure)

| Integration | Purpose | Env Vars |
|-------------|---------|----------|
| `odds_api` | Live odds and lines | `ODDS_API_KEY` |
| `playbook_api` | Sharp money, splits | `PLAYBOOK_API_KEY` |
| `balldontlie` | NBA stats | `BDL_API_KEY` |
| `railway_storage` | Persistent storage | `RAILWAY_VOLUME_MOUNT_PATH` |

### Degraded-OK Integrations

| Integration | Purpose |
|-------------|---------|
| `redis` | Caching (falls back to in-memory) |
| `whop_api` | Subscription validation |

### Optional Integrations

| Integration | Purpose |
|-------------|---------|
| `serpapi` | Web search intelligence |
| `weather_api` | Outdoor sports weather |
| `astronomy_api` | Celestial calculations |
| `noaa_space_weather` | Kp-index, solar activity |

---

## Required Pick Fields

Every pick returned from `/live/best-bets/{sport}` must include:

### Core Identity
- `pick_id` - Stable 12-char deterministic ID
- `sport` - NBA, NHL, NFL, MLB, NCAAB
- `market` - PROP, TOTAL, SPREAD, MONEYLINE
- `description` - Human-readable pick description
- `matchup` - "Away @ Home" format

### Scoring
- `final_score` - Final computed score (≥ threshold)
- `tier` - TITANIUM_SMASH, GOLD_STAR, or EDGE_LEAN
- `ai_score`, `research_score`, `esoteric_score`, `jarvis_score`
- `context_modifier` - Bounded context adjustment

### Titanium
- `titanium_triggered` - Boolean
- `titanium_count` - 0-4 engines ≥8.0
- `titanium_qualified_engines` - List of qualifying engines

### Bet Details
- `side` - Over, Under, Team name
- `line` - Bet line value
- `odds_american` - American odds format
- `book` - Sportsbook name
- `start_time_et` - Game start in ET

---

## Required Debug Fields

When `?debug=1` is passed, the response includes:

| Field | Type | Description |
|-------|------|-------------|
| `date_window_et` | object | ET filtering info |
| `filtered_below_6_5_total` | int | Picks filtered by threshold |
| `hidden_tier_filtered_total` | int | MONITOR/PASS filtered |
| `contradiction_blocked_total` | int | Opposite sides blocked |
| `pre_threshold_tier_counts` | object | Tier distribution before filter |

---

## Output Boundary Invariants

The output boundary (single choke point) enforces:

1. **Score Thresholds**
   - Props: `final_score >= 6.5`
   - Games: `final_score >= 7.0`

2. **Hidden Tier Filter**
   - MONITOR tier → filtered
   - PASS tier → filtered

3. **Valid Tier Check**
   - Only TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN pass

4. **Telemetry**
   - All violations logged in debug payload

---

## Validation

Run the Golden Gate CI to validate all contracts:

```bash
# Unit tests only
./scripts/ci_golden_gate.sh

# With live API validation
API_KEY=xxx ./scripts/ci_golden_gate.sh
```

### Test Files

| File | Purpose |
|------|---------|
| `tests/test_golden_run.py` | Contract tests (weights, tiers, thresholds) |
| `tests/test_debug_telemetry.py` | Output boundary tests |
| `tests/test_integration_validation.py` | Integration contract tests |

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| v20.21 | 2026-02-13 | Added structured logging, integration state machine |
| v20.20 | 2026-02-13 | Golden run gate, hidden tier filter, freeze baseline |
| v20.19 | 2026-02-12 | Engine weight rebalancing (Esoteric 20%→15%, Jarvis 20%→25%) |
| v20.13 | 2026-02-08 | Added MIN_PROPS_SCORE (6.5) for props threshold |
| v20.12 | 2026-02-07 | Raised MIN_FINAL_SCORE from 6.5 to 7.0 |

---

## References

- **Scoring Contract Source:** `core/scoring_contract.py`
- **Jarvis Hybrid:** `core/jarvis_ophis_hybrid.py`
- **Tier Logic:** `tiering.py`
- **Output Boundary:** `live_data_router.py:_enforce_output_boundary()`
- **Golden Run Tests:** `tests/test_golden_run.py`
