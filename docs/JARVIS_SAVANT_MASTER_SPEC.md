# JARVIS SAVANT MASTER SPECIFICATION (v1.0–v19.0)

This document is the **single source of truth** for the full system spec and
an **implementation audit** against the current backend. It merges the master
idea set (v7–v19) with the **production invariants** and **integration-backed**
features that exist in code today.

If you change any invariant, scoring rule, or required integration, update:
- `core/scoring_contract.py`
- `core/integration_contract.py`
- `CLAUDE.md`
- `docs/MASTER_INDEX.md`
- `tasks/lessons.md`

---

## 1) System Core Philosophy

- **Identity:** Hybrid‑Savant Architecture (Esoteric + Exoteric).
- **Edge thesis:** Competition + Variance.
- **Primary use:** Straight bets first; parlay only when correlation is real.
- **Learning loop:** “Fused upgrades” from post‑grade analysis.

---

## 2) Production Invariants (Non‑Negotiable)

These are enforced in code and **must never be broken**:

1) **ET day window filter** (America/New_York) before scoring.
2) **Minimum score filter**: never return picks with `final_score < 6.5`.
3) **Contradiction gate**: no opposite sides.
4) **5‑engine architecture** (v17.1): AI + Research + Esoteric + Jarvis + Context.
5) **Gold Star gates** must pass **all** engines, including `context_score >= 4.0`.
6) **Titanium rule**: only triggers when ≥3 of 4 engines ≥8.0 (AI/Research/Esoteric/Jarvis).
7) **Jason Sim Confluence** applied post‑base, pre‑tier.
8) **Fail‑soft endpoints** (no 500s); **debug/health fail‑loud**.
9) **Railway volume persistence** required.
10) **Normalized pick contract** always present in outputs.

---

## 3) Scoring Architecture (Current Production)

### 4‑Engine Base Weights (Option A)
- AI: 0.25
- Research: 0.35
- Esoteric: 0.20
- Jarvis: 0.20

### Context Modifier (bounded, not a weighted engine)
- Derived from Def Rank (50%), Pace (30%), Vacuum (20)
- Bounded cap: ±0.35 (`CONTEXT_MODIFIER_CAP`)

### Hard Gates
- Minimum output: `final_score >= 6.5`
- Gold Star gates:
  - AI >= 6.8
  - Research >= 5.5
  - Esoteric >= 4.0
  - Jarvis >= 6.5
  - Context gate removed (context is a modifier)

### Context Layer (Pillars 13–15)
- Def Rank (50%), Pace (30%), Vacuum (20) → bounded modifier

---

## 4) Master Feature Set — Implementation Audit

Status legend:
- **Implemented**: in code and backed by integrations
- **Partial**: some inputs exist but not full spec
- **Missing**: no API or module support

### Module 1 — Esoteric
1. Gematria Decoder — **Implemented** (esoteric engine)
2. Founder’s Echo — **Missing** (needs franchise founding date DB)
3. Life Path Sync — **Partial** (needs player DOB coverage + integration)
4. Bio‑Sine Biorhythms — **Missing** (requires DOB + biorhythm engine)
5. Chrome Resonance — **Missing** (requires uniform DB)
6. Planetary Hours — **Partial** (astro exists; full planetary‑hour logic not guaranteed)

### Module 2 — Physics
7. Gann Square of Nine — **Partial** (math hook exists, full spec not guaranteed)
8. 50% Retracement Rule — **Partial** (line data exists, specific rule not enforced)
9. Schumann Resonance — **Missing** (no EM frequency feed)
10. Atmospheric Drag — **Partial** (weather exists; rule not enforced)
11. Kp‑Index Protocol — **Partial** (NOAA exists; rule not enforced)

### Module 3 — Hive Mind
12. Noosphere Velocity — **Partial** (SerpAPI news exists; Google Trends missing)
13. Void Moon Filter — **Partial** (astro data exists; gate not explicit)
14. Linguistic Divergence — **Partial** (Twitter + SerpAPI exist; RLM linkage not explicit)

### Module 4 — Math/Market
15. Benford Anomaly — **Missing** (requires player stat history pipeline)
16. Fractal Hurst Exponent — **Missing** (requires long‑window stats)
17. Reverse Line Movement — **Implemented** (Research engine + Playbook/Odds)
18. Teammate Void — **Partial** (requires injury + lineup history)
19. Correlation Matrix (SGP) — **Missing** (requires correlation engine)

### Module 5 — Action Hub
20. Smash Link — **Partial** (UI integration needed)
21. Auto‑Grading (CLV) — **Implemented** (grading pipeline + odds)

---

## 5) Integration Audit (Backed by Current APIs)

This list reflects **`core/integration_contract.py`** (canonical).

**Core Required**
- **Odds API** → lines, props, odds (Research + pricing)
- **Playbook API** → sharp money, splits, injuries (Research)
- **BallDontLie** → NBA stats / grading (Grader)
- **Weather API** → outdoor context (Context modifiers; relevance‑gated)
- **FRED** → economic sentiment (Research/Esoteric)
- **Finnhub** → sportsbook stock sentiment (Research/Esoteric)
- **SerpAPI** → news aggregation (Hive/Research)
- **Twitter/X** → real‑time news sentiment (Hive/Research)
- **Whop** → membership auth
- **Database / Redis / Railway Volume** → persistence + caching

**Optional / Esoteric**
- **Astronomy API** → lunar/astro data (Esoteric)
- **NOAA Space Weather** → geomagnetic data (Esoteric)

---

## 6) Missing Integrations Needed for Full Spec

To fully implement v1.0–v19.0 spec, you still need:

- **Google Trends** (Noosphere Velocity — search volume)
- **Uniform / Branding DB** (Chrome Resonance)
- **Franchise Founding Date DB** (Founder’s Echo)
- **Reliable player DOB coverage** (Life Path + Biorhythms)
- **Schumann Resonance feed** (Physics module)
- **Full Kp‑Index / SpaceWeather feed** (NOAA SWPC with Kp index)
- **Historical stat pipelines** (Benford, Hurst, correlations)

---

## 7) Post‑Change Gates (Run After Any Backend Change)

1) **Auth:** missing → 401 Missing, wrong → 403 Invalid, correct → 200
2) **Shape contract:** engine scores + total/final + bet_tier
3) **Hard gates:** no `final_score < 6.5`, Titanium ≥3/4 engines ≥8.0
4) **Fail‑soft:** 200 with errors; debug integrations loud
5) **Freshness:** date_et + run_timestamp_et; cache TTL expected

---

## 8) Output Contract (Frontend‑Critical)

Each pick must include:
- `bet_string`, `line_signed`, `market_label`, `odds_american`, `recommended_units`
- `pick_type`, `selection`, `matchup`, `start_time`
- `total_score`, `final_score`, `tier`

This is **non‑negotiable** for correct frontend rendering.
