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
9. [Alt Data Modules Implemented But Not Wired](#9-alt-data-modules-implemented-but-not-wired)

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
In v17.6, we added `line_history` parameter to `get_glitch_aggregate()` but hardcoded `line_history=None` in the caller at `live_data_router.py:3347`. The function existed but was never actually used.

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
Always wire new parameters to actual data sources when adding them:

```python
# Fetch the data BEFORE the call
_line_history = None
if DB_ENABLED:
    with get_db() as db:
        if db:
            _line_history = get_line_history_values(db, event_id, "spread", 30)

# Pass the actual data
glitch_result = get_glitch_aggregate(
    ...
    line_history=_line_history,  # <- Now wired to real data
    ...
)
```

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
Use descriptive comments when calling these functions:

```python
# Jarvis: Is the line itself a Fibonacci number?
fib_align = jarvis.calculate_fibonacci_alignment(line)

# Esoteric: Is the line at a Fibonacci retracement level?
fib_retrace = calculate_fibonacci_retracement(line, season_high, season_low)
```

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

# Local - Esoteric
from esoteric_engine import get_glitch_aggregate, calculate_fibonacci_retracement
```

### Rule
> **INVARIANT**: When adding imports, first check if there's an existing import from that module and extend it.

---

## 6. Error Handling Patterns

### The Mistake
Letting database errors crash the entire request.

### The Fix
**ALWAYS** wrap optional signal calculations in try/except:

```python
# CORRECT
try:
    if DB_ENABLED:
        with get_db() as db:
            if db:
                result = some_db_operation(db)
except Exception as e:
    logger.debug("Operation skipped: %s", e)  # Debug, not error
    result = None  # Graceful fallback

# WRONG - crashes entire request if DB fails
result = some_db_operation(db)
```

### Rule
> **INVARIANT**: Esoteric signals are OPTIONAL. A failure in one signal must never crash the request. Use try/except with debug logging.

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
def test_hurst_no_data():
    """Hurst should return None when no line history exists."""
    result = calculate_hurst_exponent(None)
    assert result is None  # Not an error, just no data

def test_hurst_insufficient_data():
    """Hurst needs 10+ data points."""
    result = calculate_hurst_exponent([1, 2, 3])  # Only 3 points
    assert result is None  # Not enough data
```

### Rule
> **INVARIANT**: All signal functions must handle None and insufficient data gracefully. Never assume data exists.

---

## Quick Reference: The Golden Rules

1. **Database**: Always use `with get_db() as db:` context manager
2. **Parameters**: When adding params, wire them to real data (never hardcode None)
3. **Timing**: New signals need 24-48 hours to accumulate data
4. **Naming**: Comment which similarly-named function you're using
5. **Imports**: Extend existing import lines, don't scatter new ones
6. **Errors**: Wrap all optional signals in try/except
7. **Testing**: Test with None/empty data, not just happy path

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

### The Fix
Create an interpretation/tendency database that maps referee names to betting-relevant metrics:

```python
# officials_data.py
REFEREE_TENDENCIES = {
    "NBA": {
        "Scott Foster": {
            "over_tendency": 0.54,  # 54% of games go over
            "foul_rate": "HIGH",
            "home_bias": 0.02,
        },
        # ... more refs
    }
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

## Quick Reference: The Golden Rules

1. **Database**: Always use `with get_db() as db:` context manager
2. **Parameters**: When adding params, wire them to real data (never hardcode None)
3. **Timing**: New signals need 24-48 hours to accumulate data
4. **Naming**: Comment which similarly-named function you're using
5. **Imports**: Extend existing import lines, don't scatter new ones
6. **Errors**: Wrap all optional signals in try/except
7. **Testing**: Test with None/empty data, not just happy path
8. **Data Sources**: Always pair raw data with interpretation/tendency database
9. **Alt Data Wiring**: Follow full data flow: fetch → pass → apply → add reasons

---

## 9. Alt Data Modules Implemented But Not Wired

### The Mistake
In v17.8 and earlier, three alt_data modules were fully implemented but their results weren't flowing into the scoring pipeline:
- **Weather**: Fetched but bypassed engines, going directly to final_score
- **Altitude**: 62-venue registry existed but was never called
- **Travel/B2B**: ESPN `rest_days_by_team` computed but never passed to travel module

### The Evidence
```python
# Weather was applied to final_score, bypassing engine weights
if _game_weather and _game_weather.get("available"):
    final_score = final_score + _wmod  # Wrong! Bypasses research weight

# Altitude service existed but was never called
class StadiumAltitudeService:  # Dead code!
    ...

# ESPN computed rest_days but never passed it anywhere
_rest_days_by_team = {...}  # Orphaned data
```

### The Fix (v17.9)
Wire each module to the appropriate engine score:

| Signal | Target Score | Why |
|--------|--------------|-----|
| Weather | research_score | Market doesn't fully price weather |
| Altitude | esoteric_score | Non-traditional factor |
| Travel/B2B | context_score | Game context factor |

```python
# Weather → research_score (scaled and capped)
if _game_weather:
    weather_adj = max(-0.5, _wmod * 0.5)
    research_raw += weather_adj

# Altitude → esoteric_score
altitude_adj, reasons = StadiumAltitudeService.get_altitude_adjustment(...)
esoteric_raw += altitude_adj

# Travel/B2B → context_score (via compute_context_modifiers)
if _ctx_mods.get("travel_fatigue"):
    context_raw += travel_adj
```

### Rule
> **INVARIANT**: When implementing alt_data modules, follow the full data flow: (1) Fetch/compute data, (2) Pass to context/compute function, (3) Apply adjustment to appropriate engine score, (4) Add reason to engine's reasons list. Dead code is worse than no code.

### Checklist for Alt Data Wiring
- [ ] Data is fetched or computed
- [ ] Data is passed to the appropriate service/function
- [ ] Adjustment is applied to correct engine (context/esoteric/research)
- [ ] Reasons are added to the engine's reasons list
- [ ] Old/duplicate applications are removed

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
