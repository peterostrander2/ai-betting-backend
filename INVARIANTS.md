# Invariants

> Rules that must NEVER be violated. Breaking these causes production issues.

---

## Database Invariants

### INV-001: Context Manager for Database
```
ALWAYS use `with get_db() as db:` - NEVER raw get_db()
```
**Violation**: Connection pool exhaustion, hanging connections
**Test**: Grep for `get_db()` not followed by `as db:`

### INV-002: Check DB_ENABLED First
```
ALWAYS check `if DB_ENABLED:` before any database operation
```
**Violation**: Crashes in environments without database
**Test**: All `get_db()` calls must be inside `if DB_ENABLED:` block

### INV-003: Null Check After Context
```
ALWAYS check `if db:` after `with get_db() as db:`
```
**Violation**: NoneType errors when DB unavailable
**Test**: Every `with get_db() as db:` must have `if db:` inside

---

## Signal Invariants

### INV-004: Signals Must Not Crash Requests
```
ALL esoteric signal calculations MUST be wrapped in try/except
```
**Violation**: 500 errors when signal data missing
**Pattern**:
```python
try:
    signal_result = calculate_signal(...)
except Exception as e:
    logger.debug("Signal skipped: %s", e)
    signal_result = None
```

### INV-005: Signals Must Handle None Inputs
```
ALL signal functions MUST return valid output (or None) when given None inputs
```
**Violation**: TypeError crashes
**Test**: Call every signal function with None parameters

### INV-006: GLITCH Must Always Return Valid Structure
```
get_glitch_aggregate() MUST return dict with 'score', 'signals', 'reasons' keys
even when all inputs are None
```
**Violation**: KeyError in callers
**Test**: `result = get_glitch_aggregate(None, None, None, None, None, None)`

---

## Data Invariants

### INV-007: Hurst Requires Minimum Data Points
```
calculate_hurst_exponent() requires len(data) >= 10
```
**Violation**: Mathematically invalid results
**Check**: Function must validate `if not data or len(data) < 10: return None`

### INV-008: Fibonacci Retracement Requires Range
```
calculate_fibonacci_retracement() requires season_high > season_low
```
**Violation**: Division by zero
**Check**: Function must validate `if season_high <= season_low: return None`

### INV-009: Season Format Must Be Consistent
```
Season strings MUST use format: "YYYY-YY" (e.g., "2025-26")
```
**Violation**: No data found, mismatched queries
**Pattern**:
```python
_now = datetime.now()
_season = f"{_now.year}-{str(_now.year+1)[-2:]}" if _now.month >= 9 else f"{_now.year-1}-{str(_now.year)[-2:]}"
```

---

## API Invariants

### INV-010: Never Expose Internal Errors
```
API responses MUST NOT include stack traces or internal error details
```
**Violation**: Security risk, information disclosure
**Pattern**: Log full error internally, return generic message to client

### INV-011: Esoteric Reasons Must Be Human Readable
```
All entries in esoteric_reasons list MUST be human-readable strings
```
**Violation**: Confusing UI output
**Pattern**: `"Signal Name: value (context)"` format

---

## Deployment Invariants

### INV-012: Syntax Check Before Deploy
```
MUST run `python -m py_compile <file>` before deploying any Python file
```
**Violation**: Deployment crashes immediately
**Gate**: CI/CD should enforce this

### INV-013: New Signals Need Data Accumulation Time
```
New database-dependent signals will show "no data" for 24-48 hours
```
**Violation**: False bug reports, unnecessary rollbacks
**Mitigation**: Document expected delays in release notes

### INV-014: Never Hardcode None for Wired Parameters
```
When a parameter is meant to receive data, NEVER hardcode it as None
```
**Violation**: Feature appears to work but actually does nothing
**Check**: Grep for `parameter=None` and verify it's intentional

---

## Testing Invariants

### INV-015: Test Empty State
```
ALL signal tests MUST include test with empty/None data
```
**Violation**: Crashes on new deployments before data accumulates

### INV-016: Test Boundary Conditions
```
Tests MUST cover: exactly minimum data points, one below minimum, one above
```
**Violation**: Off-by-one errors in data requirements

---

## Invariant Verification Script

```bash
#!/bin/bash
# Run this before every deployment

echo "Checking invariants..."

# INV-001: Context manager usage
echo "INV-001: Checking for raw get_db() calls..."
grep -n "get_db()" *.py | grep -v "with get_db()" | grep -v "def get_db" && echo "FAIL: Raw get_db() found" || echo "PASS"

# INV-002: DB_ENABLED checks
echo "INV-002: Checking DB_ENABLED usage..."
# Manual review required

# INV-004: Try/except around signals
echo "INV-004: Checking signal error handling..."
# Manual review required

# INV-012: Syntax check
echo "INV-012: Syntax check..."
python -m py_compile live_data_router.py && echo "PASS" || echo "FAIL"
python -m py_compile esoteric_engine.py && echo "PASS" || echo "FAIL"
python -m py_compile database.py && echo "PASS" || echo "FAIL"

echo "Done."
```

---

## Adding New Invariants

When adding a new invariant:

1. Assign next INV-XXX number
2. Write the rule in imperative form
3. Document what violation looks like
4. Add test or check method
5. Update verification script if automatable
