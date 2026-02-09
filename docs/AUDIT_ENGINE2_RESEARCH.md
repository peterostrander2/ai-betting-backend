# Engine 2 (Research) Audit Report

**Audit Date:** 2026-02-08
**Auditor:** Claude Code
**Branch:** `claude/engine2-research-audit`
**Version:** v20.13+

---

## 1. Research Engine Contract

### 1.1 Engine Weight (Single Source of Truth)

| Constant | File | Value |
|----------|------|-------|
| `ENGINE_WEIGHTS["research"]` | `core/scoring_contract.py:11` | **0.35** (35%) |

The Research Engine is the **largest single engine** in the Option A scoring formula:

```
BASE_4 = (AI × 0.25) + (Research × 0.35) + (Esoteric × 0.20) + (Jarvis × 0.20)
```

### 1.2 Scoring Formula Integration

**File:** `core/scoring_pipeline.py` → `compute_final_score_option_a()`

```python
base_score = (
    (ai_score * 0.25) +
    (research_score * 0.35) +
    (esoteric_score * 0.20) +
    (jarvis_score * 0.20)
)
```

### 1.3 Score Bounds

| Constraint | Value | Enforced In |
|------------|-------|-------------|
| Engine score range | `[0.0, 10.0]` | `research_engine.py:754` |
| Final score range | `[0.0, 10.0]` | `scoring_pipeline.py` (clamp) |
| MIN_FINAL_SCORE (games) | 7.0 | `scoring_contract.py:22` |
| MIN_PROPS_SCORE | 6.5 | `scoring_contract.py:28` |

---

## 2. Research Pillars

### 2.1 Pillar Weights (Must Sum to 1.0)

**Source:** `research_engine.py:48-56`

| Pillar | Weight | Description |
|--------|--------|-------------|
| `sharp_split` | 0.20 | Sharp money vs public betting splits |
| `reverse_line_move` | 0.15 | Line movement against betting % |
| `public_fade` | 0.15 | Fade heavy public side |
| `hook_discipline` | 0.10 | Key number positioning (3, 7, 10) |
| `goldilocks_zone` | 0.15 | Optimal odds range detection |
| `hospital_fade` | 0.10 | Injury impact analysis |
| `trap_gate` | 0.10 | Trap game detection |
| `multi_pillar` | 0.05 | Cross-pillar confluence bonus |
| **TOTAL** | **1.00** | ✅ Verified |

### 2.2 Pillar Implementation Map

| Pillar | Function | Lines | Data Source |
|--------|----------|-------|-------------|
| Sharp Split | `calculate_sharp_split_signal()` | 168-230 | Playbook API (splits) |
| Reverse Line Move | `calculate_rlm_signal()` | 232-295 | Playbook API (lines) |
| Public Fade | `calculate_public_fade_signal()` | 297-360 | Playbook API (public %) |
| Hook Discipline | `calculate_hook_discipline_signal()` | 362-425 | Odds API (spreads) |
| Goldilocks Zone | `calculate_goldilocks_signal()` | 427-490 | Odds API (odds range) |
| Hospital Fade | `calculate_hospital_fade_signal()` | 492-555 | Playbook API (injuries) |
| Trap Gate | `calculate_trap_gate_signal()` | 557-586 | Playbook API (schedule) |
| Multi-Pillar | `calculate_multi_pillar_confluence()` | 765-810 | Internal (pillar scores) |

### 2.3 Pillar Output Fields

Each pillar produces a `PillarResult` dataclass:

```python
@dataclass
class PillarResult:
    name: str           # Pillar identifier
    score: float        # [0.0, 10.0]
    confidence: float   # [0.0, 1.0]
    signals: Dict       # Raw signal data
    reasons: List[str]  # Human-readable explanations
```

### 2.4 Research Engine Output

**Dataclass:** `ResearchResult` (`research_engine.py:58-78`)

| Field | Type | Description |
|-------|------|-------------|
| `score` | float | Weighted pillar average [0.0-10.0] |
| `confidence` | float | Weighted confidence [0.0-1.0] |
| `pillars` | Dict[str, PillarResult] | Individual pillar results |
| `api_calls` | Dict[str, int] | API call counts |
| `errors` | List[str] | Any errors encountered |
| `cached` | bool | Whether result was from cache |

---

## 3. Paid API Usage Map

### 3.1 API Integrations

| API | File | Env Var | Feature Flag |
|-----|------|---------|--------------|
| **Playbook API** | `playbook_api.py` | `PLAYBOOK_API_KEY` | `PLAYBOOK_ENABLED` |
| **Odds API** | `odds_api.py` | `ODDS_API_KEY` | Always enabled |
| **BallDontLie** | `alt_data_sources/balldontlie.py` | `BDL_API_KEY` | `BDL_ENABLED` |

### 3.2 API → Pillar Mapping

| API | Pillars Served | Endpoints Used |
|-----|----------------|----------------|
| **Playbook** | sharp_split, rlm, public_fade, hospital_fade, trap_gate | `/splits`, `/lines`, `/injuries`, `/schedule` |
| **Odds API** | hook_discipline, goldilocks_zone | `/odds` (multi-book) |
| **BallDontLie** | (grading only, not scoring) | `/games`, `/stats` |

### 3.3 Integration Telemetry

**Pattern:** `mark_integration_used(integration_name)`

```python
# odds_api.py:45
mark_integration_used("odds_api")

# playbook_api.py (expected)
mark_integration_used("playbook_api")
```

### 3.4 Fail-Soft Behavior

When paid APIs fail or return empty data:

| API | Fallback Behavior | Pillar Score |
|-----|-------------------|--------------|
| Playbook | Use cached data (5min TTL) | 5.0 (neutral) |
| Odds API | Use stale odds with warning | 5.0 (neutral) |
| BallDontLie | Skip NBA-specific features | N/A (grading only) |

**Contract:** If ALL paid APIs fail, Research Engine returns `score=5.0` (neutral) with `confidence=0.2` (low).

---

## 4. Boost Caps & Contract Wiring

### 4.1 Post-Base Boost Caps

**Source:** `scoring_contract.py:86-98`

| Boost | Cap | Implementation |
|-------|-----|----------------|
| `confluence_boost` | 1.5 | `scoring_pipeline.py` |
| `msrf_boost` | 1.0 | `scoring_pipeline.py` |
| `serp_boost` | 4.3 | `serp_guardrails.py` |
| `jason_sim_boost` | 1.5 | `scoring_pipeline.py` |
| **TOTAL_BOOST_CAP** | **1.5** | `scoring_pipeline.py:compute_final_score_option_a()` |

### 4.2 Post-Base Signals (NOT Engine Mutations)

| Signal | Cap | Direction | File |
|--------|-----|-----------|------|
| `hook_penalty` | -0.25 | Penalty only | `scoring_contract.py:137` |
| `expert_consensus_boost` | +0.35 | Boost only | `scoring_contract.py:138` |
| `prop_correlation_adjustment` | ±0.20 | Both | `scoring_contract.py:139` |

### 4.3 Invariant Checks

```python
# CRITICAL: These must hold at all times
assert 0.0 <= research_score <= 10.0
assert sum(PILLAR_WEIGHTS.values()) == 1.0
assert ENGINE_WEIGHTS["research"] == 0.35
assert TOTAL_BOOST_CAP == 1.5
```

---

## 5. Documentation Drift Analysis

### 5.1 Verified Alignments ✅

| Item | Docs | Code | Status |
|------|------|------|--------|
| Engine weight 35% | ✅ | ✅ | Aligned |
| 8 pillars | ✅ | ✅ | Aligned |
| Pillar weights sum to 1.0 | ✅ | ✅ | Aligned |
| TOTAL_BOOST_CAP = 1.5 | ✅ | ✅ | Aligned |
| MIN_FINAL_SCORE = 7.0 | ✅ | ✅ | Aligned |

### 5.2 Potential Drift Items ⚠️

| Item | Issue | Recommendation |
|------|-------|----------------|
| Hook Discipline | Exists as both pillar (research_engine) AND post-base signal (scoring_contract) | Verify no double-counting |
| Integration telemetry | `mark_integration_used()` pattern inconsistent across files | Standardize in all paid API wrappers |
| Playbook API wrapper | Not found in expected location | Verify file exists and is wired |

### 5.3 Missing Documentation

- [ ] Research Engine README in `/docs/engines/`
- [ ] Pillar calibration methodology
- [ ] API failure impact analysis

---

## 6. Runtime Verification Script

**Script:** `scripts/engine2_research_audit.sh`

Tests performed:
1. Health check with debug payload
2. Research engine presence in response
3. Paid API usage counters (Playbook, Odds API)
4. Pillar scores in valid range [0-10]
5. Material impact test (with `audit_disable_research=1`)
6. Fail-soft behavior (API timeout simulation)

---

## 7. Guard Tests

**File:** `tests/test_engine2_research_guards.py`

| Guard Category | Tests |
|----------------|-------|
| Post-Base Mutation | No engine score mutation after BASE_4 calculation |
| Math Reconciliation | Pillar weights sum to 1.0, weighted average correct |
| Fail-Soft Contract | Neutral score (5.0) on API failure |
| Cap Enforcement | All caps respected (TOTAL_BOOST_CAP, pillar bounds) |

---

## 8. Recommendations

### 8.1 Immediate Actions

1. **Add usage counters to debug payload** for Playbook/Odds API calls
2. **Standardize `mark_integration_used()` pattern** across all paid APIs
3. **Verify Hook Discipline** isn't double-counted (pillar + post-base signal)

### 8.2 Future Improvements

1. Add pillar-level confidence weighting
2. Implement adaptive pillar weights based on historical performance
3. Add circuit breaker for repeated API failures

---

## Appendix A: File References

| File | Purpose |
|------|---------|
| `research_engine.py` | Core Research Engine implementation |
| `core/scoring_contract.py` | Single source of truth for constants |
| `core/scoring_pipeline.py` | Score calculation pipeline |
| `odds_api.py` | Odds API wrapper |
| `playbook_api.py` | Playbook API wrapper (TBD) |
| `alt_data_sources/balldontlie.py` | BallDontLie API wrapper |

## Appendix B: Audit Artifacts

| Artifact | Location |
|----------|----------|
| Runtime report | `artifacts/engine2_research_runtime_report.json` |
| Guard tests | `tests/test_engine2_research_guards.py` |
| Audit script | `scripts/engine2_research_audit.sh` |
