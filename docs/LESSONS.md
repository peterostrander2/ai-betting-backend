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
