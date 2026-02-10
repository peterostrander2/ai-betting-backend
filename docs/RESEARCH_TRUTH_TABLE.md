# Research Engine Truth Table

**Version:** v20.16+
**Last Updated:** 2026-02-10
**Purpose:** Canonical contract for Engine 2 (Research) scoring components

---

## 1. Component Summary

| Component | Source API | Boost Range | Status Values | Anti-Conflation |
|-----------|------------|-------------|---------------|-----------------|
| `sharp_boost` | Playbook API | 0.0 - 3.0 | SUCCESS, NO_DATA, ERROR, DISABLED | ONLY from `playbook_sharp` object |
| `line_boost` | Odds API | 0.0 - 3.0 | SUCCESS, NO_DATA, ERROR, DISABLED | ONLY from `odds_line` object |
| `public_boost` | Playbook API | 0.0 - 2.0 | SUCCESS, NO_DATA, ERROR, DISABLED | From public_pct, ticket/money divergence |
| `espn_odds_boost` | ESPN API | 0.0 - 0.5 | SUCCESS, NO_DATA, ERROR, DISABLED | Cross-validation bonus |
| `liquidity_boost` | Odds API | 0.0 - 0.5 | SUCCESS, NO_DATA | Book coverage count |
| `base_research` | Internal | 2.0 - 3.0 | SUCCESS | Base score when data present |

---

## 2. Component Details

### 2.1 Sharp Boost (Playbook API ONLY)

**Source:** `playbook_api.py` → `/splits` endpoint
**Object:** `playbook_sharp` (NEVER merged with `odds_line`)

| Field | Type | Description |
|-------|------|-------------|
| `status` | enum | SUCCESS, NO_DATA, ERROR, DISABLED |
| `sharp_strength` | enum | STRONG, MODERATE, MILD, NONE |
| `ticket_pct` | int | Ticket percentage (public) |
| `money_pct` | int | Money percentage (sharp) |
| `divergence` | int | `abs(money_pct - ticket_pct)` |
| `sharp_side` | str | "home" or "away" |

**Thresholds:**
| Divergence | Sharp Strength | Boost |
|------------|----------------|-------|
| >= 20% | STRONG | +3.0 |
| >= 10% | MODERATE | +1.5 |
| >= 5% | MILD | +0.5 |
| < 5% | NONE | +0.0 |

**Invariants:**
- `sharp_boost` may ONLY read from `playbook_sharp` object
- If `playbook_sharp.status != SUCCESS` then `sharp_strength` MUST be `NONE`
- If `playbook_sharp.status != SUCCESS` then reasons MUST NOT contain "Sharp"

---

### 2.2 Line Boost (Odds API ONLY)

**Source:** `odds_api.py` → `/odds` endpoint (multi-book spreads)
**Object:** `odds_line` (NEVER merged with `playbook_sharp`)

| Field | Type | Description |
|-------|------|-------------|
| `status` | enum | SUCCESS, NO_DATA, ERROR, DISABLED |
| `line_strength` | enum | STRONG, MODERATE, MILD, NONE |
| `line_open` | float | Opening line |
| `line_current` | float | Current line |
| `line_variance` | float | Cross-book variance (max - min spread) |

**Thresholds:**
| Line Variance | Line Strength | Boost |
|---------------|---------------|-------|
| >= 2.0 pts | STRONG | +3.0 |
| >= 1.5 pts | MODERATE | +1.5 (labeled "moderate") |
| >= 0.5 pts | MILD | +1.5 (labeled "moderate") |
| < 0.5 pts | NONE | +0.0 |

**Invariants:**
- `line_boost` may ONLY read from `odds_line` object
- Line variance can NEVER escalate `sharp_strength`
- `lv_strength` is computed independently from Odds API variance

---

### 2.3 Public Boost (Playbook API)

**Source:** `playbook_api.py` → `/splits` endpoint

| Field | Type | Description |
|-------|------|-------------|
| `public_pct` | int | Public betting percentage |
| `ticket_pct` | int | Ticket count percentage |
| `money_pct` | int | Money percentage |

**Thresholds:**
| Public % | Ticket-Money Divergence | Boost |
|----------|-------------------------|-------|
| >= 75% | >= 5% | +2.0 |
| >= 65% | >= 5% | +1.0 |
| < 65% | any | +0.0 |

---

### 2.4 ESPN Odds Boost (Cross-Validation)

**Source:** ESPN API → `/scoreboard` endpoint

| Validation | Boost |
|------------|-------|
| Spread diff <= 0.5 pts | +0.5 |
| Spread diff <= 1.0 pts | +0.25 |
| Total diff <= 1.0 pts | +0.5 |
| Total diff <= 2.0 pts | +0.25 |

---

### 2.5 Liquidity Boost (Book Coverage)

**Source:** Odds API → book count from response

| Book Count | Boost |
|------------|-------|
| >= 8 books | +0.5 |
| >= 5 books | +0.3 |
| >= 3 books | +0.1 |
| < 3 books | +0.0 |

---

### 2.6 Base Research Score

| Condition | Base Score |
|-----------|------------|
| Real Playbook data with divergence | 3.0 |
| Fallback/no data | 2.0 |

---

## 3. Status Enum Definition

```python
class ComponentStatus(str, Enum):
    SUCCESS = "SUCCESS"      # API call succeeded, data present
    NO_DATA = "NO_DATA"      # API call succeeded but no relevant data
    ERROR = "ERROR"          # API call failed (timeout, 4xx, 5xx)
    DISABLED = "DISABLED"    # Feature flag disabled
```

---

## 4. Anti-Conflation Requirements

### 4.1 Separate Objects (MANDATORY)

The old `sharp_signal` dict conflated Playbook and Odds API data. The v20.16 fix creates TWO DISTINCT objects:

```python
# CORRECT (v20.16+):
playbook_sharp = {
    "status": "SUCCESS",
    "sharp_strength": "MODERATE",
    "ticket_pct": 45,
    "money_pct": 62,
    "divergence": 17,
    "sharp_side": "away"
}

odds_line = {
    "status": "SUCCESS",
    "line_strength": "MODERATE",
    "line_open": -3.0,
    "line_current": -2.5,
    "line_variance": 0.8
}
```

### 4.2 Exclusive Reading Rules

| Component | Reads From | NEVER Reads From |
|-----------|------------|------------------|
| `sharp_boost` | `playbook_sharp` | `odds_line`, `sharp_signal` |
| `line_boost` | `odds_line` | `playbook_sharp`, `sharp_signal` |
| `sharp_strength` | `playbook_sharp.sharp_strength` | `line_variance`, `lv_strength` |
| `lv_strength` | `odds_line.line_variance` | `sharp_strength`, `divergence` |

### 4.3 Reason String Invariant

**If Playbook API fails (`playbook_sharp.status != SUCCESS`):**
- `sharp_strength` MUST be `"NONE"`
- Reason strings MUST NOT contain "Sharp money"
- `sharp_boost` MUST be `0.0`

**If Odds API fails (`odds_line.status != SUCCESS`):**
- `lv_strength` MUST be `"NONE"`
- Reason strings show "Line variance 0.0pts"
- `line_boost` MUST be `0.0`

---

## 5. Research Breakdown Contract

Every pick's `research_breakdown` MUST include:

```json
{
  "sharp_boost": {
    "value": 1.5,
    "status": "SUCCESS",
    "source_api": "playbook_api",
    "raw_inputs_summary": {
      "ticket_pct": 45,
      "money_pct": 62,
      "divergence": 17,
      "sharp_side": "away"
    },
    "call_proof": {
      "used_live_call": true,
      "usage_counter_delta": 1,
      "http_requests_delta": 1,
      "2xx_delta": 1,
      "cache_hit": false
    }
  },
  "line_boost": {
    "value": 1.5,
    "status": "SUCCESS",
    "source_api": "odds_api",
    "raw_inputs_summary": {
      "line_variance": 0.8,
      "lv_strength": "MILD"
    },
    "call_proof": {
      "used_live_call": true,
      "usage_counter_delta": 1,
      "http_requests_delta": 1,
      "2xx_delta": 1,
      "cache_hit": false
    }
  },
  "public_boost": {
    "value": 0.0,
    "status": "SUCCESS",
    "source_api": "playbook_api"
  },
  "base_research": 2.0,
  "total": 5.0
}
```

---

## 6. Audit Assertions

### 6.1 Per-Request Verification

```python
# If sharp_boost.status == SUCCESS:
assert network_proof.playbook_http_requests_delta >= 1
assert usage_counters_delta.playbook_calls >= 1
assert call_proof.used_live_call == (call_proof["2xx_delta"] >= 1)

# If line_boost.status == SUCCESS:
assert network_proof.odds_http_requests_delta >= 1
assert usage_counters_delta.odds_api_calls >= 1
assert call_proof.used_live_call == (call_proof["2xx_delta"] >= 1)

# If key_present but 2xx_delta == 0:
assert component.status in ("NO_DATA", "ERROR") or component.cache_hit == True
```

### 6.2 Static Code Verification

1. No code path reads `sharp_strength` from `odds_line`
2. No code path reads `line_variance` from `playbook_sharp`
3. No code path merges `playbook_sharp` and `odds_line` objects
4. The legacy upgrade code (lines 2030-2033) is REMOVED

---

## 7. Debug Endpoint Contract

### GET /debug/research-candidates/{sport}

Response includes:
- `candidates_pre_filter[]` with `research_breakdown` per candidate
- `auth_context` with API key presence
- `network_proof` with HTTP request deltas
- `usage_counters_before/after/delta`

See Phase 1 implementation for full response schema.

---

## 8. Test Coverage

Required tests in `tests/test_research_truthfulness.py`:

1. `test_line_variance_cannot_set_sharp_strength`
2. `test_reason_strings_match_component_status`
3. `test_source_api_tags_present`
4. `test_usage_counters_increment_on_real_call_path`
5. `test_sharp_strength_only_from_playbook_sharp`
6. `test_line_boost_only_from_odds_line`
7. `test_call_proof_matches_delta`
8. `test_raw_inputs_summary_present`
9. `test_network_proof_2xx_delta`
10. `test_no_sharp_reason_when_playbook_not_success`
11. `test_used_live_call_requires_2xx`
12. `test_key_present_no_2xx_means_no_data`

---

## Appendix: Historical Bug Reference

### The Conflation Bug (Fixed in v20.16)

**Old code (lines 2030-2033):**
```python
# BUG: Odds API upgrades Playbook field!
if lv >= 2.0 and signal["signal_strength"] in ("NONE", "MILD"):
    signal["signal_strength"] = "STRONG"
```

**Symptom:** "Sharp signal STRONG" appeared when only line variance was strong.

**Root Cause:** Single `sharp_signal` dict held both Playbook (sharp) and Odds API (line variance) data.

**Fix:** Separate `playbook_sharp` and `odds_line` objects with exclusive reading rules.
