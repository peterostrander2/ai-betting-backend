# Lessons Learned

> Mistakes we've made and how to avoid repeating them.
> Update this file whenever a bug or issue teaches us something.

---

## Table of Contents

1. [Database Session Handling](#1-database-session-handling)
2. [Hardcoded None Parameters](#2-hardcoded-none-parameters)
3. [Data Accumulation Delays](#3-data-accumulation-delays)
4. [Function Name Confusion](#4-function-name-confusion)
5. [Import Management](#5-import-management)
6. [Error Handling Patterns](#6-error-handling-patterns)
7. [Testing with No Data](#7-testing-with-no-data)
8. [External Data Without Interpretation Layer](#8-external-data-without-interpretation-layer)
9. [Dual-Use Functions Return Type](#9-dual-use-functions-return-type)
10. [pick_type Value Mismatch](#10-pick_type-value-mismatch)
11. [Multi-Call-Site Parameter Threading](#11-multi-call-site-parameter-threading)
12. [Database Session Context Manager](#12-database-session-context-manager-v177)
13. [Variable Name Typos in Large Dict Returns](#13-variable-name-typos-in-large-dict-returns-v178)
14. [Timezone-Aware vs Naive Datetime Comparisons](#14-timezone-aware-vs-naive-datetime-comparisons-v182)
15. [Environment Variable OR Logic](#15-environment-variable-or-logic-v182)
16. [Variable Initialization Before Conditional Use](#16-variable-initialization-before-conditional-use-v182)

---

## 1. Database Session Handling

### The Mistake
Leaving database connections open, causing connection pool exhaustion.

### The Fix
**ALWAYS** use the context manager pattern:

```python
# CORRECT
from database import get_db, DB_ENABLED

if DB_ENABLED:
    with get_db() as db:
        if db:
            result = get_line_history_values(db, event_id, "spread", 30)

# WRONG - connection never closed
db = get_db()
result = get_line_history_values(db, event_id, "spread", 30)
```

### Rule
> **INVARIANT**: Every `get_db()` call MUST use `with` context manager.

---

## 2. Hardcoded None Parameters

### The Mistake
In v17.6, we added `line_history` parameter to `get_glitch_aggregate()` but hardcoded `line_history=None` in the caller. The function existed but was never actually used.

### The Evidence
```python
# This was the problem - parameter existed but was always None
glitch_result = get_glitch_aggregate(
    ...
    line_history=None,  # <- HARDCODED! Never wired to actual data
    ...
)
```

### The Fix
Always wire new parameters to actual data sources when adding them.

### Rule
> **INVARIANT**: When adding a parameter to a function, grep for all callers and update them. Never leave `parameter=None` hardcoded.

### Checklist for New Parameters
- [ ] Added parameter to function signature
- [ ] Added data fetch logic before function call
- [ ] Updated all callers (grep for function name)
- [ ] Verified data flows end-to-end

---

## 3. Data Accumulation Delays

### The Mistake
Expecting new signals to work immediately after deployment. They won't.

### The Reality
| Signal | Data Source | Time to Activate |
|--------|-------------|------------------|
| Hurst Exponent | line_snapshots | ~5 hours (needs 10+ snapshots) |
| Fibonacci Retracement | season_extremes | ~24 hours (daily 5 AM job) |
| Benford Anomaly | line values | Immediate (uses current lines) |
| Officials Tendency | ESPN + officials_data.py | Immediate (refs assigned 1-3 hrs before game) |

### The Fix
1. Document expected delays in deployment notes
2. Add "no data" handling that fails gracefully
3. Don't panic when new signals show empty results

### Rule
> **INVARIANT**: New database-dependent signals will show "no data" for 24-48 hours. This is expected, not a bug.

---

## 4. Function Name Confusion

### The Mistake
Confusing `calculate_fibonacci_alignment()` (Jarvis) with `calculate_fibonacci_retracement()` (Esoteric).

### The Difference
| Function | What It Does | Example |
|----------|--------------|---------|
| `calculate_fibonacci_alignment()` | Checks if line IS a Fibonacci number | Line 13 -> "Fib number!" |
| `calculate_fibonacci_retracement()` | Checks if line is at Fib % of range | Line at 61.8% of season range |

### The Fix
Use descriptive comments when calling these functions.

### Rule
> **INVARIANT**: When two functions have similar names, add a comment explaining which one you're using and why.

---

## 5. Import Management

### The Mistake
Adding imports in random places, making them hard to find and causing circular import issues.

### The Fix
Group imports by source and add new ones to existing groups:

```python
# Standard library
import os
from datetime import datetime

# Third-party
from fastapi import FastAPI

# Local - Database
from database import get_db, get_line_history_values, get_season_extreme, DB_ENABLED

# Local - Officials (v17.8)
from officials_data import get_referee_tendency, calculate_officials_adjustment
```

### Rule
> **INVARIANT**: When adding imports, first check if there's an existing import from that module and extend it.

---

## 6. Error Handling Patterns

### The Mistake
Letting database or API errors crash the entire request.

### The Fix
**ALWAYS** wrap optional signal calculations in try/except:

```python
# CORRECT
try:
    adj, reasons = OfficialsService.get_officials_adjustment(
        sport=sport_upper,
        officials=officials_data,
        pick_type=officials_pick_type,
        pick_side=officials_pick_side,
        is_home_team=is_home
    )
except Exception as e:
    logger.debug("Officials adjustment skipped: %s", e)
    adj, reasons = 0.0, []

# WRONG - crashes entire request if service fails
adj, reasons = OfficialsService.get_officials_adjustment(...)
```

### Rule
> **INVARIANT**: Pillar signals are OPTIONAL. A failure in one signal must never crash the request. Use try/except with debug logging.

---

## 7. Testing with No Data

### The Mistake
Writing tests that expect signals to return data when the database is empty.

### The Fix
Tests should verify:
1. Function returns valid structure (even if empty)
2. No exceptions thrown with None inputs
3. Graceful handling of missing data

```python
def test_officials_no_data():
    """Officials should return (0.0, []) when no referee data exists."""
    adj, reasons = calculate_officials_adjustment('NBA', 'Unknown Ref', 'TOTAL', 'Over')
    assert adj == 0.0
    assert reasons == []
```

### Rule
> **INVARIANT**: All signal functions must handle None and insufficient data gracefully. Never assume data exists.

---

## 8. External Data Without Interpretation Layer

### The Mistake
Pillar 16 (Officials) had ESPN data source wired (referee names) but returned 0.0 adjustment because there was no interpretation layer - no data about what those referee names MEAN for betting.

### The Evidence
```python
# ESPN provided: {"lead_official": "Scott Foster", ...}
# But OfficialsService just returned: (0.0, [])
# Because it had no data about Scott Foster's tendencies
```

### The Fix (v17.8)
Create an interpretation/tendency database that maps referee names to betting-relevant metrics:

```python
# officials_data.py
NBA_REFEREES = {
    "Scott Foster": {
        "over_tendency": 0.54,  # 54% of games go over
        "foul_rate": "HIGH",
        "home_bias": 0.02,
    },
    # ... 25 NBA refs total
}

# Now the adjustment can be calculated
def calculate_officials_adjustment(sport, ref_name, pick_type, pick_side):
    tendency = get_referee_tendency(sport, ref_name)
    if tendency["over_tendency"] > 0.52 and pick_side == "Over":
        return +0.2, f"Officials: {ref_name} over tendency (54%)"
```

### Rule
> **INVARIANT**: External data (names, IDs) is useless without an interpretation layer that converts it to betting-relevant signals. When adding a new data source, also add the lookup/tendency database.

### Checklist for New Data Sources
- [ ] Data source provides raw identifiers (names, IDs)
- [ ] Interpretation database maps identifiers → betting metrics
- [ ] Adjustment function converts metrics → score changes
- [ ] Output includes human-readable reasons

---

## 9. Dual-Use Functions Return Type

### The Mistake
`get_sharp_money()` was both an endpoint handler AND called internally. It returned `JSONResponse`, which worked for the endpoint but crashed internal callers expecting a dict.

### The Error
```
AttributeError: 'JSONResponse' object has no attribute 'get'
```

### The Fix
Functions used BOTH as endpoints AND internally MUST return dicts:

```python
# WRONG - breaks internal callers
@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    result = {"data": [...]}
    return JSONResponse(result)  # Internal callers can't use .get()

# CORRECT - FastAPI auto-serializes dicts
@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    result = {"data": [...]}
    return result  # Works for both endpoint and internal calls
```

### Rule
> **INVARIANT**: Dual-use functions (endpoint + internal) MUST return dicts, not JSONResponse. FastAPI auto-serializes dicts for HTTP responses.

---

## 10. pick_type Value Mismatch

### The Mistake
Phase 1 dormant signals (Gann Square, Founder's Echo) weren't triggering because the code checked `pick_type == "GAME"`, but game picks use actual market values.

### The Reality
| Market | pick_type Value |
|--------|-----------------|
| Spread bets | `"SPREAD"` |
| Moneyline | `"MONEYLINE"` |
| Totals (O/U) | `"TOTAL"` |
| Props | `"PROP"` |
| Sharp signals | `"SHARP"` |

The value `"GAME"` is only a default/fallback, never used for actual picks.

### The Fix
```python
# WRONG - "GAME" never matches for actual game picks
if pick_type == "GAME" and spread and total:
    # Never triggers

# CORRECT - Check for all game-related pick types
_is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")
if _is_game_pick and spread and total:
    # Works correctly
```

### Rule
> **INVARIANT**: Before using `pick_type` in conditions, trace where it's set. Game picks use "SPREAD", "MONEYLINE", "TOTAL", "SHARP" - NOT "GAME".

---

## 11. Multi-Call-Site Parameter Threading

### The Mistake
When adding `game_bookmakers` parameter to `calculate_pick_score()`, only 1 of 3 call sites was updated. The other 2 passed `None`.

### The Evidence
```python
# calculate_pick_score() called from 3 places:
# 1. Game picks loop (~line 5149) - UPDATED
# 2. Props loop (~line 5290) - MISSED
# 3. Sharp money loop (~line 5472) - MISSED
```

### The Fix
1. **Grep for all call sites FIRST:** `grep -n "calculate_pick_score(" live_data_router.py`
2. **Count call sites:** Expect 3+ (definition + calls)
3. **Update ALL call sites** with the new parameter
4. **Verify no calls are missing:** Re-run grep after changes

### Rule
> **INVARIANT**: When adding parameters to multi-call-site functions, update ALL call sites in the same commit.

---

## Quick Reference: The Golden Rules

1. **Database**: Always use `with get_db() as db:` context manager
2. **Parameters**: When adding params, wire them to real data (never hardcode None)
3. **Timing**: New signals need 24-48 hours to accumulate data
4. **Naming**: Comment which similarly-named function you're using
5. **Imports**: Extend existing import lines, don't scatter new ones
6. **Errors**: Wrap all optional signals in try/except
7. **Testing**: Test with None/empty data, not just happy path
8. **Data Sources**: Always pair raw data with interpretation/tendency database
9. **Return Types**: Dual-use functions must return dicts, not JSONResponse
10. **pick_type**: Game picks use "SPREAD"/"MONEYLINE"/"TOTAL", not "GAME"
11. **Call Sites**: Update ALL call sites when adding function parameters
12. **Database Sessions**: Always use `with get_db() as db:` and check `DATABASE_AVAILABLE and DB_ENABLED`

---

## 12. Database Session Context Manager (v17.7)

### The Mistake
Database connections left open, causing connection pool exhaustion or errors when DB is unavailable.

### The Fix
Always use context manager AND check availability flags BEFORE attempting DB operations:

```python
# CORRECT - Full safety pattern
_line_history = None
try:
    _event_id = candidate.get("id") if isinstance(candidate, dict) else None
    if _event_id and DATABASE_AVAILABLE and DB_ENABLED:
        with get_db() as db:
            if db:
                _line_history = get_line_history_values(
                    db,
                    event_id=_event_id,
                    value_type="spread",
                    limit=30
                )
except Exception as e:
    logger.debug("Database operation skipped: %s", e)

# WRONG - No context manager, no availability check
db = get_db()
result = get_line_history_values(db, event_id, "spread", 30)  # Connection never closed!
```

### Rule
> **INVARIANT**: Always check `DATABASE_AVAILABLE and DB_ENABLED` before any DB operation, use `with get_db() as db:` context manager, and wrap in try/except.

---

## 13. Variable Name Typos in Large Dict Returns (v17.8)

### The Mistake
Production crashed with `NameError: name 'officials_reason' is not defined` because the return dict used `officials_reason` (singular) but the variable was defined as `officials_reasons` (plural).

### The Evidence
```python
# Variable defined (line 4154):
officials_reasons = []

# Later usage (line 4577) - TYPO:
"officials_reason": officials_reason,  # ❌ Should be officials_reasons
```

### The Fix
Always match exact variable names. When adding to large return dicts, copy-paste the variable name.

```python
# CORRECT
officials_reasons = []
# ... logic ...
return {
    "officials_reasons": officials_reasons,  # ✅ Exact match
}
```

### Rule
> **INVARIANT**: When returning variables in dicts, copy-paste variable names. Never type them from memory. Run syntax check (`python -m py_compile`) before every push.

### Checklist for Dict Returns
- [ ] Variable name in dict key matches definition exactly
- [ ] Run `python -m py_compile <file>` before committing
- [ ] Grep for variable name to verify it's defined: `grep -n "variable_name =" file.py`

---

## 12. Daily Sanity Report (Best Bets Health)

### The Mistake
Relying on ad hoc or skipped manual checks after deploys.

### The Fix
Use the daily sanity report to verify production health + best-bets output quickly:

```bash
API_KEY=your_key \
API_BASE=https://web-production-7b2a.up.railway.app \
SPORTS="NBA NFL NHL MLB" \
bash scripts/daily_sanity_report.sh
```

### Rule
> **INVARIANT**: After any deploy that touches scoring, time windows, or contracts, run the daily sanity report at least once.

---

## 13. Daily Lesson Must Be Written

### The Mistake
Autograder ran daily but did not guarantee a human-facing learning summary.

### The Fix
Write a daily lesson at 6 AM ET (after audit):
- `/data/grader_data/audit_logs/lesson_YYYY-MM-DD.json`
- `/data/grader_data/audit_logs/lessons.jsonl`
- Endpoint: `GET /live/grader/daily-lesson`

### Rule
> **INVARIANT**: Every automated learning step must produce a daily lesson artifact and expose it via a member-safe endpoint.

---

## 14. Timezone-Aware vs Naive Datetime Comparisons (v18.2)

### The Mistake
Phase 8 lunar phase calculation crashed with `TypeError: can't subtract offset-naive and offset-aware datetimes` because the reference date was created without a timezone.

### The Evidence
```python
# WRONG - ref_date is naive (no timezone)
ref_date = datetime(2000, 1, 6, 18, 14, 0)  # Reference new moon
days_since = (game_datetime - ref_date).days  # CRASH! Can't mix aware/naive
```

### The Fix
Always use timezone-aware datetimes for astronomical calculations:

```python
# CORRECT - Both datetimes are timezone-aware
from zoneinfo import ZoneInfo

ref_date = datetime(2000, 1, 6, 18, 14, 0, tzinfo=ZoneInfo("UTC"))
game_datetime = datetime.now(ZoneInfo("America/New_York"))
days_since = (game_datetime - ref_date).days  # Works!
```

### Rule
> **INVARIANT**: When doing datetime arithmetic, BOTH datetimes must be timezone-aware. Use `ZoneInfo("UTC")` for reference dates and `ZoneInfo("America/New_York")` for game times.

---

## 15. Environment Variable OR Logic (v18.2)

### The Mistake
SERP API integration failed because the env var check used AND logic when it should have used OR. Both `SERPAPI_KEY` and `SERP_API_KEY` are valid alternatives, but the code required BOTH to be set.

### The Evidence
```python
# WRONG - Requires BOTH keys to be set
if SERPAPI_KEY and SERP_API_KEY:
    # Only runs if both exist

# Also WRONG - all() requires ALL to be truthy
if all([os.getenv("SERPAPI_KEY"), os.getenv("SERP_API_KEY")]):
    # Only runs if both exist
```

### The Fix
Use `any()` for alternative env vars:

```python
# CORRECT - Either key works
if any([os.getenv("SERPAPI_KEY"), os.getenv("SERP_API_KEY")]):
    key = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")
    # Runs if at least one exists
```

### Rule
> **INVARIANT**: When env vars are ALTERNATIVES (either one works), use `any()`. When env vars are ALL REQUIRED, use `all()`. Document which pattern is intended.

---

## 16. Variable Initialization Before Conditional Use (v18.2)

### The Mistake
Production crashed with `NameError: name 'weather_data' is not defined` because the variable was only assigned inside a conditional block but used outside it.

### The Evidence
```python
# WRONG - weather_data only defined if condition is True
if outdoor_sport:
    weather_data = fetch_weather()

# Later in code...
if weather_data:  # NameError if outdoor_sport was False!
    apply_weather_boost()
```

### The Fix
Initialize variables to `None` BEFORE conditional blocks:

```python
# CORRECT - weather_data always defined
weather_data = None  # Initialize first

if outdoor_sport:
    weather_data = fetch_weather()

# Later in code...
if weather_data:  # Safe - weather_data is always defined
    apply_weather_boost()
```

### Rule
> **INVARIANT**: Any variable used after a conditional block MUST be initialized before that block. Initialize to `None`, `[]`, `{}`, or appropriate default.

### Checklist for Conditional Variables
- [ ] Variable initialized before `if` block
- [ ] Initialized value handles the "else" case correctly
- [ ] All code paths after the block can handle the initialized value

---

## Quick Reference: The Golden Rules (Updated v18.2)

1. **Database**: Always use `with get_db() as db:` context manager
2. **Parameters**: When adding params, wire them to real data (never hardcode None)
3. **Timing**: New signals need 24-48 hours to accumulate data
4. **Naming**: Comment which similarly-named function you're using
5. **Imports**: Extend existing import lines, don't scatter new ones
6. **Errors**: Wrap all optional signals in try/except
7. **Testing**: Test with None/empty data, not just happy path
8. **Data Sources**: Always pair raw data with interpretation/tendency database
9. **Return Types**: Dual-use functions must return dicts, not JSONResponse
10. **pick_type**: Game picks use "SPREAD"/"MONEYLINE"/"TOTAL", not "GAME"
11. **Call Sites**: Update ALL call sites when adding function parameters
12. **Database Sessions**: Always use `with get_db() as db:` and check `DATABASE_AVAILABLE and DB_ENABLED`
13. **Variable Names**: Copy-paste variable names in dict returns, run `python -m py_compile`
14. **Timezones**: Both datetimes must be timezone-aware for arithmetic
15. **Env Vars**: Use `any()` for alternatives, `all()` for required
16. **Initialization**: Initialize variables before conditional blocks that might skip assignment

---

## 17. Two Storage Systems Architecture (v20.x)

### The Design (INTENTIONAL)
Two separate storage systems exist by design, NOT by accident:

| System | Module | Path | Purpose |
|--------|--------|------|---------|
| **Picks** | `grader_store.py` | `/data/grader/predictions.jsonl` | All picks (high-frequency writes) |
| **Weights** | `auto_grader.py` | `/data/grader_data/weights.json` | Learned weights only (daily updates) |

### Why Not Merge Them?
1. **Different access patterns**: Picks are written on every best-bets call; weights updated once daily
2. **File locking**: Separate files prevent contention between frequent writes and daily batch processing
3. **Recovery**: Can restore weights without losing picks (and vice versa)
4. **Format**: Picks use append-only JSONL; weights use overwrite JSON

### The Data Flow
```
[Best-bets endpoint]
        ↓
grader_store.persist_pick(pick_data)
        ↓
/data/grader/predictions.jsonl  ←── [WRITE PATH]
        ↓
[Daily 6 AM audit reads picks]
        ↓
auto_grader.grade_prediction()
        ↓
/data/grader_data/weights.json  ←── [WRITE PATH]
```

### What Was Removed (Cleanup)
- `_save_predictions()` method from auto_grader.py
- `predictions.json` saving from `_save_state()`
- `_save_predictions()` calls from `grade_prediction()`

### What Remains
- `auto_grader.py` READS from `grader_store` but only WRITES `weights.json`
- All pick persistence goes through `grader_store.py` exclusively

### Rule
> **INVARIANT**: Two storage systems is CORRECT. Picks flow through `grader_store.py` only. AutoGrader reads picks but only writes weights. Never merge these systems.

### Verification
```bash
# Check both storage paths are healthy
curl /internal/storage/health | jq '{picks: .predictions_line_count, weights_dir: .grader_data_dir}'

# Verify grader reads picks correctly
curl /live/grader/status -H "X-API-Key: KEY" | jq '{predictions_logged, weights_loaded}'
```

---

## 18. Props Pipeline Sanity Check

### The Mistake
Props pipeline could silently fail without blocking deployment. Games would show but props would be missing.

### The Fix
Added `scripts/props_sanity_check.sh` with configurable enforcement:

```bash
# Optional check (warnings only)
./scripts/props_sanity_check.sh

# Strict mode (fails if no props)
REQUIRE_PROPS=1 PROPS_REQUIRED_SPORTS="NBA" ./scripts/props_sanity_check.sh
```

### What It Checks
1. Props endpoint returns 200
2. Props count > 0 for required sports
3. Props have required fields (pick_id, final_score, etc.)

### Rule
> **INVARIANT**: Add sanity checks for each major data pipeline. Make them configurable (strict vs advisory mode).

---

## 19. Integration Usage Tracking Pattern

### The Mistake
NOAA integration worked but `last_used_at` wasn't updating, making it impossible to verify the integration was actually called.

### The Fix
Add tracking helper at the source module:

```python
# alt_data_sources/noaa.py
def _mark_noaa_used() -> None:
    try:
        from integration_registry import mark_integration_used
        mark_integration_used("noaa_space_weather")
    except Exception as e:
        logger.debug("noaa mark_integration_used failed: %s", str(e))

def fetch_kp_index_live():
    # Track on cache hit
    if _kp_cache and (now - _kp_cache_time) < KP_CACHE_TTL:
        _mark_noaa_used()  # ← Important: track even cache hits
        return {**_kp_cache, "source": "cache"}

    # ... API call ...

    _mark_noaa_used()  # ← Track on successful fetch
    return result
```

### Rule
> **INVARIANT**: Integration tracking should happen at the source module level. Track usage on BOTH cache hits AND live API calls.

---

## 20. Boost Field Output Contract

### The Mistake
Frontend expected boost fields but they were inconsistently present in pick payloads.

### The Fix
Documented explicit contract in `SCORING_LOGIC.md`:

```json
{
  "base_4_score": 7.2,
  "context_modifier": 0.15,
  "context_breakdown": {...},
  "context_reasons": [...],
  "confluence_boost": 1.5,
  "confluence_reasons": [...],
  "msrf_boost": 0.25,
  "msrf_status": "MODERATE",
  "msrf_reasons": [...],
  "jason_sim_boost": 0.5,
  "jason_status": "STRONG",
  "jason_reasons": [...],
  "serp_boost": 0.3,
  "serp_status": "LIVE",
  "serp_signals": [...]
}
```

### Rule
> **INVARIANT**: Every boost must expose: value, status/breakdown, and reasons. Frontend should never have to guess field presence.

---

## Quick Reference: The Golden Rules (Updated v20.x)

1. **Database**: Always use `with get_db() as db:` context manager
2. **Parameters**: When adding params, wire them to real data (never hardcode None)
3. **Timing**: New signals need 24-48 hours to accumulate data
4. **Naming**: Comment which similarly-named function you're using
5. **Imports**: Extend existing import lines, don't scatter new ones
6. **Errors**: Wrap all optional signals in try/except
7. **Testing**: Test with None/empty data, not just happy path
8. **Data Sources**: Always pair raw data with interpretation/tendency database
9. **Return Types**: Dual-use functions must return dicts, not JSONResponse
10. **pick_type**: Game picks use "SPREAD"/"MONEYLINE"/"TOTAL", not "GAME"
11. **Call Sites**: Update ALL call sites when adding function parameters
12. **Database Sessions**: Always use `with get_db() as db:` and check `DATABASE_AVAILABLE and DB_ENABLED`
13. **Variable Names**: Copy-paste variable names in dict returns, run `python -m py_compile`
14. **Timezones**: Both datetimes must be timezone-aware for arithmetic
15. **Env Vars**: Use `any()` for alternatives, `all()` for required
16. **Initialization**: Initialize variables before conditional blocks that might skip assignment
17. **Two Storage Systems**: Picks via `grader_store.py`; Weights via `auto_grader.py` - NEVER merge
18. **Pipeline Checks**: Add sanity checks for each major data pipeline
19. **Integration Tracking**: Track usage at source module level, including cache hits
20. **Boost Contract**: Every boost exposes value + status + reasons
21. **SERP Shadow Mode**: Default SERP to LIVE mode, not shadow mode (v17.2)
22. **pick_type Values**: Game picks use "SPREAD"/"MONEYLINE"/"TOTAL", not "GAME" (v17.5)
23. **Dormant Signal Activation**: Use `_is_game_pick` helper for pick_type conditions (v17.5)
24. **Benford Multi-Book**: Aggregate odds across books before anomaly detection (v17.6)
25. **Function Parameter Threading**: Update ALL call sites when adding function parameters (v17.6)
26. **Officials Tendency**: Pair referee names with tendency database for betting signals (v17.8)
27. **Trap Learning Loop**: Detect trap lines via sharp divergence patterns (v19.0)
28. **Complete Learning System**: End-to-end grading → bias → weight updates (v19.1)
29. **Timezone Aware Datetimes**: Both sides must be tz-aware for arithmetic (v18.2)
30. **Env Var OR Logic**: Use `any()` for alternatives, `all()` for required (v18.2)
31. **Variable Init Before Conditionals**: Initialize to None before conditional assignment (v18.2)
32. **Auto Grader Weights**: Include all stat types in weights dict structure (v20.2)
33. **OVER Bet Tracking**: Monitor OVER/UNDER bias for calibration adjustments (v20.2)
34. **Learning Loop Verification**: Check bias trends across sports to verify learning (v20.3)
35. **Grading Pipeline Coverage**: Handle SHARP/MONEYLINE/PROP in grading (v20.3)
36. **Audit Drift Line Filters**: Use precise line ranges in drift scans (v20.4)
37. **Endpoint Matrix Sanity Math**: Verify final_score formula matches production (v20.4)
38. **OVER/UNDER Calibration**: Apply totals_calibration_adj for bias correction (v20.4)
39. **Frontend Tooltip Alignment**: Weights in UI must match scoring_contract.py (v20.4)
40. **Shell Export for Python**: Use `export VAR=value` for Python subprocesses (v20.4)
41. **SHARP Grading**: Grade as moneyline (team won?), not line_variance (v20.5)
42. **PYTZ_AVAILABLE Defined**: Define PYTZ_AVAILABLE before conditional use (v20.5)
43. **Naive vs Aware Datetime**: Use timezone-aware datetimes for all comparisons (v20.5)
44. **Date Window Math**: yesterday = today - 1 day, not today - 2 days (v20.5)
45. **Grader Performance Bug**: Same naive/aware datetime issue in multiple endpoints (v20.5)
46. **Surface All Adjustments**: Every final_score adjustment needs a payload field (v20.5)
47. **Script Env Vars Registry**: Add script-only env vars to RUNTIME_ENV_VARS (v20.5)
48. **Heredoc __file__ Path**: Heredocs run from temp, use explicit paths (v20.5)
49. **Props Timeout Budget**: TIME_BUDGET_S configurable, increase for props (v20.6)
50. **Empty Description Fields**: Auto-generate descriptions in normalize_pick() (v20.6)
51. **Total Boost Cap**: TOTAL_BOOST_CAP = 1.5 prevents score inflation (v20.6)
52. **Jarvis Baseline Design**: 4.5 baseline is intentional (sacred triggers are rare) (v20.6)
53. **SERP Parallel Pre-Fetch**: Pre-fetch SERP data to avoid sequential bottleneck (v20.7)
54. **Props Indentation Bug**: Code placement matters - break AFTER append, not before (v20.8)
55. **Frontend/Backend Contract**: Verify backend endpoint exists before frontend calls it (v20.9)
56. **SHARP Signal Field Name**: Use `sharp_side`, not `side` (signal dictionary field) (v20.10)
57. **NOAA Real API**: Wire existing API implementations, don't leave simulations (v20.11)
58. **Live ESPN Scores**: Extract real scores during fetch, don't hardcode 0-0 (v20.11)
59. **Void Moon Meeus**: Use proper astronomical formulas (synodic month + perturbation) (v20.11)
60. **LSTM Real Data**: Try Playbook API before falling back to synthetic (v20.11)
61. **Comprehensive Rivalry Database**: Cover ALL teams in each sport, not just popular (v20.11)

---

## 21. SERP Shadow Mode Default (v17.2)

### The Mistake
SERP was defaulting to shadow mode (disabled), so the feature was never actually used in production.

### The Fix
Set `SERP_SHADOW_MODE=false` by default to enable SERP intelligence.

### Rule
> **INVARIANT**: Features should default to ENABLED unless there's a specific reason to disable.

---

## 22. pick_type Value Mismatch (v17.5)

### The Mistake
Code checked `pick_type == "GAME"` but actual game picks use `"SPREAD"`, `"MONEYLINE"`, or `"TOTAL"`.

### The Fix
```python
_is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")
if _is_game_pick and spread and total:
    # Now triggers correctly
```

### Rule
> **INVARIANT**: Before using `pick_type` in conditions, trace where it's set. The value `"GAME"` is only a fallback.

---

## 23-31. Phase Lessons (v17.5-v18.2)

See `CLAUDE.md` for detailed coverage of:
- Dormant Signal Activation (23)
- Benford Multi-Book (24)
- Function Parameter Threading (25)
- Officials Tendency (26)
- Trap Learning Loop (27)
- Complete Learning System (28)
- Timezone Aware Datetimes (29)
- Env Var OR Logic (30)
- Variable Init Before Conditionals (31)

---

## 32-45. v20.x Learning Loop & Grading (v20.2-v20.5)

Key lessons from the v20.x learning loop implementation:

- **Auto Grader Weights (32)**: Include ALL stat types in weights structure
- **OVER Tracking (33)**: Monitor bias to enable calibration
- **Learning Verification (34)**: Check trends to confirm learning is working
- **Grading Coverage (35)**: Handle all pick types in grading pipeline
- **SHARP Grading (41)**: Grade as moneyline win/loss, not line variance
- **Datetime Bugs (42-45)**: Always use timezone-aware datetimes

---

## 46-52. v20.5-v20.6 Production Fixes

### 46. Surface All Adjustments
Every adjustment to `final_score` MUST have a corresponding payload field.

### 51. Total Boost Cap (CRITICAL)
**TOTAL_BOOST_CAP = 1.5** prevents score inflation from stacking multiple boosts.

```python
total_boosts = min(TOTAL_BOOST_CAP, confluence + msrf + jason + serp)
```

---

## 53-56. v20.7-v20.10 Performance & Bug Fixes

### 53. SERP Parallel Pre-Fetch
Pre-fetch SERP data before scoring loop to avoid 17s→3s improvement.

### 54. Props Indentation Bug
`break` was placed BETWEEN `calculate_pick_score()` and `props_picks.append()`, making append unreachable.

### 55. Frontend/Backend Contract
NEVER write frontend API method without verifying backend endpoint exists.

### 56. SHARP Signal Field Name
Signal uses `sharp_side`, not `side`. Wrong field = wrong team graded.

---

## 57-61. v20.11 Real Data Sources

### 57. NOAA Real API
If a working API exists (noaa.py), wire it in. Don't leave simulations.

### 58. Live ESPN Scores
Extract real scores from ESPN scoreboard during fetch phase.

### 59. Void Moon Meeus
Use proper astronomical formulas (synodic month 29.53d + perturbation).

### 60. LSTM Real Data
Try Playbook API with `build_training_data_real()` before synthetic fallback.

### 61. Comprehensive Rivalry Database
Cover ALL teams in each sport (204 rivalries across 5 sports).

---

## 62. Post-Base Signals Architecture (v20.11)

### The Mistake
Hook/Expert/Prop signals mutated `research_score` AFTER `base_score` was computed — the mutations had NO EFFECT on `final_score`.

### The Fix
Wire signals as explicit parameters to `compute_final_score_option_a()`, not as engine score mutations. Post-base signals are additive AFTER BASE_4.

### Rule
> **INVARIANT**: Engine scores are LOCKED once BASE_4 is computed. Post-base signals must be explicit parameters, not mutations.

---

## 63. Dormant Features — Stadium Altitude & Travel Fatigue (v20.12)

### The Mistake
Stadium altitude module existed but wasn't called. Travel fatigue had undefined `rest_days` variable.

### The Fix
Wire `alt_data_sources/stadium.py` into scoring. Use `_rest_days_for_team()` closure instead of undefined `rest_days`.

### Rule
> **INVARIANT**: Never use `var if 'var' in dir()` pattern — use the proper function/closure that's already implemented.

---

## 64. CI Partial-Success Error Handling (v20.12)

### The Mistake
Session 8 spot check treated ANY error as fatal. Timeout with valid picks = partial success, not failure.

### The Fix
Check error codes for severity AND count actual picks returned. Timeout codes (`PROPS_TIMED_OUT`, `GAME_PICKS_TIMED_OUT`) are soft errors.

### Rule
> **INVARIANT**: CI scripts must distinguish fatal errors from partial-success. Count picks before deciding error severity.

---

## 65. SERP Quota Cost vs Value (v20.12)

### The Mistake
SERP burned 5000 searches/month. Per-call APIs enabled by default exhausted quota mid-month.

### The Fix
Disabled SERP by default (`SERP_INTEL_ENABLED=false`). Per-call APIs require explicit opt-in.

### Rule
> **INVARIANT**: Never enable expensive per-call APIs by default. Require explicit opt-in and calculate cost/benefit first.

---

## 66-67. Cron Automation Lessons (Feb 2026)

### 66. Cron Path Validation

**The Mistake:** Crontab entries pointed to `~/Desktop/ai-betting-backend-main` but the actual repo was at `~/ai-betting-backend`. All cron jobs silently failed for months.

**The Fix:**
```bash
# Verify cron paths match actual repo locations
crontab -l | grep -E "cd ~/|cd \$HOME"
ls -d ~/ai-betting-backend  # Verify path exists
```

**Rule:**
> **INVARIANT**: After setting up cron jobs, ALWAYS verify paths exist with `ls -d`. Cron failures are silent — jobs won't report errors.

### 67. Automation Script Coverage

**The Mistake:** Manual health checks were forgotten. Scripts existed but weren't scheduled.

**The Fix:** Created 26 automated scripts across both repos with cron scheduling:
- **High frequency** (30min-hourly): Response time, error rates
- **Daily**: Health checks, backups, access logs
- **Weekly**: Vuln scans, dead code, complexity reports

**Rule:**
> **INVARIANT**: Any repeatable check should be automated via cron. Store logs in `~/repo/logs/` and verify cron paths on session start.

**Verification command:**
```bash
crontab -l | wc -l   # Should show 33+ scheduled jobs
```

---

## 68. Robust Shell Script Error Handling (v20.13)

*(Documented in CLAUDE.md lesson table — see CLAUDE.md for details.)*

---

## 69-70. v20.13 Engine 2 (Research) Audit

### 69. Auto-Grader Field Name Mismatch

**The Mistake:**
`auto_grader.py:_convert_pick_to_record()` read `sharp_money`/`public_fade`/`line_variance` from `research_breakdown`, but picks store as `sharp_boost`/`public_boost`/`line_boost`. Daily learning loop always saw 0.0 for research signals.

**The Fix:**
Use fallback pattern: `breakdown.get("sharp_boost", breakdown.get("sharp_money", 0.0))` — reads new name first, old name as fallback.

**Rule:**
> **INVARIANT**: Field names in `_convert_pick_to_record()` MUST match field names in `persist_pick()`. When renaming fields, use fallback pattern for backward compatibility.

### 70. GOLD_STAR Gate Labels

**The Mistake:**
Gate labels said `research_gte_5.5`/`esoteric_gte_4.0` but actual thresholds in `scoring_contract.py` are 6.5/5.5. Labels misled debugging and downgrade messages.

**The Fix:**
Updated labels in `live_data_router.py` to match `scoring_contract.py` values. Fixed docs in `CLAUDE.md` and `docs/MASTER_INDEX.md`.

**Rule:**
> **INVARIANT**: Never hardcode threshold values in label strings. Read from `scoring_contract.py` constants. After any threshold change, grep ALL files for old values.

---

## 71. Session 7 SHARP Fallback Detection Bug (Feb 8, 2026)

### The Mistake
CI spot check Session 7 (`scripts/spot_check_session7.sh`) used `pick_type == "SHARP"` to detect SHARP fallback picks when `events_after_games=0`. The script failed because SHARP fallback picks do NOT have `pick_type: "SHARP"` — they have `pick_type` set to the bet type ("spread", "moneyline", "total").

**The Bug:**
```bash
# WRONG - pick_type is the bet type, not "SHARP"
SHARP_PICKS="$(echo "$RAW" | jq -r '[.game_picks.picks[] | select(.pick_type == "SHARP")] | length')"
# Returns 0 because pick_type is "spread" or "moneyline"

# Error output:
# ❌ FAIL: games returned but no game events analyzed (and not all SHARP)
# events_after_games=0, games_returned=1, sharp_picks=0
```

### The Fix
SHARP fallback picks are identified by `market == "sharp_money"`, NOT by `pick_type`:

```bash
# CORRECT - SHARP fallback picks have market="sharp_money"
SHARP_MARKET_PICKS="$(echo "$RAW" | jq -r '[.game_picks.picks[] | select(.market == "sharp_money")] | length')"

if [ "$GAMES_RETURNED" -gt 0 ] && [ "$GAMES_EVENTS" -eq 0 ]; then
  if [ "$SHARP_MARKET_PICKS" -eq "$GAMES_RETURNED" ]; then
    echo "✅ SHARP fallback: $SHARP_MARKET_PICKS picks from sharp_money market with 0 Odds API events (valid)"
  else
    echo "❌ FAIL: games returned but no game events analyzed (and not all from SHARP fallback)"
    exit 1
  fi
fi
```

**Field Semantics:**
| Field | Value for SHARP Fallback | Value for Regular Picks |
|-------|--------------------------|-------------------------|
| `pick_type` | "spread", "moneyline", "total" (the bet type) | "SPREAD", "MONEYLINE", "TOTAL" |
| `market` | `"sharp_money"` | The specific market key |

### Rule
> **INVARIANT**: SHARP fallback picks are identified by `market == "sharp_money"`, NOT by `pick_type`. The `pick_type` field always contains the bet type (spread/moneyline/total), never "SHARP".

### Related Files
- `scripts/spot_check_session7.sh` — Session 7 Output Filtering Pipeline check
- `live_data_router.py` — Where SHARP fallback picks are created with `market: "sharp_money"`

---

## 81. Training Telemetry Path Is Top-Level (v20.17.3)

### The Mistake
The `/live/debug/training-status` endpoint read `training_telemetry` from the wrong path:

```python
# WRONG (BUG at live_data_router.py:11371 before fix)
training_telemetry = status.get("ensemble", {}).get("training_telemetry", {})

# CORRECT (after fix)
training_telemetry = status.get("training_telemetry", {})
```

### How We Detected It
- `training_health` showed `"NEVER_RAN"` even after successful 7 AM training
- Debug inspection revealed `training_telemetry` was at TOP level of `get_model_status()` return, NOT inside `"ensemble"` dict
- Verified by reading `team_ml_models.py:get_model_status()` (line 605)

### Why It Mattered
- False "NEVER_RAN" status masked successful training
- No visibility into actual training health
- Could lead to unnecessary manual training triggers

### The Fix
Changed path at `live_data_router.py:11371`:
```python
training_telemetry = status.get("training_telemetry", {})
```

### Permanent Guard
- **Test:** `tests/test_training_status.py::test_training_telemetry_path`
- **Audit command:**
```bash
curl -s ".../live/debug/training-status" -H "X-API-Key: KEY" | \
  jq -e '.training_telemetry.last_train_run_at != null or .training_health == "NEVER_RAN"'
```

### Rule
> **INVARIANT**: Always verify the actual return structure of `get_model_status()` before accessing nested keys. The function returns `training_telemetry` at TOP level.

---

## 82. Missing model_preds Attribution Buckets (v20.17.3)

### The Mistake
950 game picks (64% of game market) had `missing_model_preds_attribution.unknown` because the attribution function lacked buckets for:
- `heuristic_fallback` — MPS returned `ai_mode == "HEURISTIC_FALLBACK"`
- `empty_raw_inputs` — game market with `ai_breakdown` but empty `raw_inputs`

### How We Detected It
- Store audit showed `unknown: 950` for game picks
- Manual inspection of records revealed two missing attribution patterns
- Pattern 1: `ai_mode == "HEURISTIC_FALLBACK"` (MPS unavailable)
- Pattern 2: Game picks with `ai_breakdown` present but `raw_inputs == {}`

### Why It Mattered
- Couldn't diagnose why 950 game picks lacked ensemble training data
- No way to distinguish expected missing (old schema) from unexpected missing
- Training pipeline appeared less healthy than it was

### The Fix
Added two new attribution buckets at `scripts/audit_training_store.py:254`:

```python
def _attribute_missing_model_preds(record, date_et, pick_type, market_type):
    # ... existing checks ...

    # Check 4: HEURISTIC_FALLBACK mode (MPS unavailable or failed)
    ai_mode = ai_breakdown.get("ai_mode", record.get("ai_mode", ""))
    if ai_mode == "HEURISTIC_FALLBACK":
        return "heuristic_fallback"

    # Check 5: Empty raw_inputs for game market
    raw_inputs = ai_breakdown.get("raw_inputs", {})
    if market_type == "game" and not raw_inputs:
        return "empty_raw_inputs"

    return "unknown"
```

### Permanent Guard
- **Test:** `tests/test_training_telemetry.py::test_attribution_buckets_complete`
- **Audit command:**
```bash
curl -s ".../live/debug/training-status" -H "X-API-Key: KEY" | \
  jq -e '.store_audit.data_quality.missing_model_preds_attribution.unknown == 0'
```

### Rule
> **INVARIANT**: `missing_model_preds_attribution.unknown` MUST be 0 for game picks. All missing model_preds must have a known attribution bucket.

---

## 83. Empty Dict Conditionals Are False (v20.17.3)

### The Mistake
Training signatures were not stored because of this pattern:

```python
# BUG: Empty dict {} is falsy in Python
if filter_telemetry:
    training_signatures["ensemble"] = {...}

# When filter_telemetry == {}, this block is SKIPPED
```

### How We Detected It
- `ensemble_signature: null` in training-status response after training ran
- Debug showed `filter_telemetry` was `{}` (empty dict), not `None`
- Python truthiness: `bool({}) == False`

### Why It Mattered
- Training ran successfully but signature wasn't recorded
- No proof of training parameters (label_type, schema_match)
- Audit couldn't verify training correctness

### The Fix
Explicit check for the meaningful condition:

```python
# CORRECT: Check for None explicitly, or check specific keys
if filter_telemetry is not None:
    training_signatures["ensemble"] = {...}

# OR: Check for the presence of data you need
if "assertion_passed" in filter_telemetry:
    training_signatures["ensemble"] = {...}
```

### Permanent Guard
- **Code review pattern:** Grep for `if some_dict:` where `{}` is a valid state
- **Test:** `tests/test_training_telemetry.py::test_empty_dict_conditional`
- **Command:**
```bash
grep -n "if filter_telemetry:" team_ml_models.py scripts/train_team_models.py
# Should return 0 matches (explicit None checks instead)
```

### Rule
> **INVARIANT**: Never use `if some_dict:` when `{}` is a meaningful empty state. Use `if some_dict is not None:` or check for specific keys.

---

## Adding New Lessons

When you encounter a bug or issue, add it here:

```markdown
## N. [Short Title]

### The Mistake
What went wrong.

### The Fix
How to do it correctly (with code examples).

### Rule
> **INVARIANT**: The rule to follow going forward.
```
