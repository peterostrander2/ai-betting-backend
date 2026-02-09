
## 🔴 LESSONS LEARNED (NEVER REPEAT)

### Lesson 1: Dormant Code Detection
**Problem:** 8 AI models + 14 LSTM weights existed but were never called. Production used `base_ai = 5.0` hardcoded.

**Root Cause:** Code was written but integration points were never added to `live_data_router.py`.

**Prevention:**
- Every new feature MUST have an integration point in the scoring pipeline
- Use `grep -r "function_name" live_data_router.py` to verify integration
- Add to this MASTER FILE INDEX when creating new modules

### Lesson 2: Orphaned Signal Detection
**Problem:** GLITCH Protocol had 19 features designed, but only 10 were active. 9 were "orphaned" (code exists, never called).

**Root Cause:** `get_glitch_aggregate()` was created but individual signals weren't wired in.

**Prevention:**
- Every signal function MUST be called somewhere
- Use grep to verify: `grep -r "function_name" *.py | grep -v "^def\|^#"`
- Document signal weights and integration points

### Lesson 3: API Stubbing vs. Real Implementation
**Problem:** NOAA and SerpAPI were "stubbed" (returning default values) instead of making real API calls.

**Root Cause:** Stub code was written for development but never replaced with real implementation.

**Prevention:**
- Check for `return {"source": "fallback"}` patterns
- Verify env vars are set: `curl /live/debug/integrations`
- Real APIs should show `"source": "xxx_live"` in responses

### Lesson 4: Parameter Passing
**Problem:** `get_glitch_aggregate()` accepted `value_for_benford` parameter but ignored it internally.

**Root Cause:** Function signature was updated but body wasn't.

**Prevention:**
- Search for unused parameters: functions should USE what they accept
- Read function body after changing signature

### Lesson 5: Weight Normalization
**Problem:** GLITCH aggregate weights didn't sum properly, causing score drift.

**Prevention:**
- Always verify: `sum(weights) == 1.0` or use `weighted_score / total_weight`
- Document weights in function docstring

### Lesson 6: Secret Leakage in Logs (SECURITY)
**Problem:** API keys were logged in multiple places:
- `playbook_api.py:211` logged full query params including `api_key`
- `live_data_router.py:6653` constructed URL with bare `?apiKey=VALUE`
- `legacy/services/odds_api_service.py:30` logged `key[:8]...` (reconnaissance risk)

**Root Cause:** No centralized log sanitization. Each developer logged debug info without thinking about secrets.

**Prevention:**
- Use `core/log_sanitizer.py` for ALL logging that might contain sensitive data
- NEVER construct URLs with `?apiKey=` - use `params={}` dict instead
- NEVER log partial keys - even `key[:8]` is a security risk
- Run `grep -rn "apiKey\|api_key\|authorization" *.py` and verify all are sanitized

**Fixed in:** Commit `2e67adc` (Feb 2026)

### Lesson 7: Demo Data Leakage (SECURITY)
**Problem:** Sample/demo data (Lakers/Warriors, LeBron James picks) could leak to production when APIs failed.

**Root Cause:** Fallback code returned demo data without any gate. Any API failure would expose fake picks.

**Prevention:**
- ALL demo data MUST be gated behind `ENABLE_DEMO=true` or `mode=demo`
- When live data unavailable, return EMPTY response, not sample data
- Debug seed endpoints MUST check for demo flag before creating test picks
- Search for hardcoded player names in non-test files: `grep -rn "LeBron\|Lakers" --include="*.py" | grep -v test`

**Fixed in:** Commit `2e67adc` (Feb 2026)

### Lesson 8: New Signal Integration Pattern (MSRF)
**Problem:** How to integrate a new esoteric signal (MSRF) without disrupting existing scoring.

**Solution:** Use CONFLUENCE BOOST pattern instead of creating a 6th engine.

**Integration Pattern (RECOMMENDED for new signals):**
1. Create standalone module in `signals/` directory
2. Export main function as `get_XXX_confluence_boost(context) → (boost, metadata)`
3. Return boost value (0.0, 0.25, 0.5, 1.0) + full metadata dict
4. Integrate in `live_data_router.py` AFTER Harmonic Convergence, BEFORE `confluence_boost =`
5. Add to `confluence["boost"]` (not to engine scores directly)
6. Log boost in `esoteric_reasons` (for debug visibility)
7. Include `XXX_boost` and `XXX_metadata` in pick output

**Why Confluence Boost:**
- Avoids diluting BASE_4 weights (context is modifier-only)
- Easy to enable/disable via feature flag
- Provides additive boost only when signal fires
- Keeps engines clean and focused

**Files Changed for MSRF:**
```
signals/msrf_resonance.py     # NEW - Core module
signals/__init__.py           # MODIFIED - Export functions
live_data_router.py:3567-3591 # MODIFIED - Integration point
```

**Fixed in:** Commit `ce083ef` (Feb 2026)

### Lesson 9: Dual-Use Functions (Endpoint + Internal) - CRITICAL
**Problem:** `get_sharp_money()` was both an endpoint handler (`@router.get("/sharp/{sport}")`) AND called internally by `_best_bets_inner()`. The function returned `JSONResponse` objects, which worked for the endpoint but crashed internal callers expecting a dict.

**Error Message:**
```
AttributeError: 'JSONResponse' object has no attribute 'get'
```

**Root Cause:** Function returned `JSONResponse(_sanitize_public(result))` for all paths. When called internally at line 2580, the code did `sharp_data.get("data", [])` which failed because `JSONResponse` has no `.get()` method.

**The Pattern That Caused This:**
```python
@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    # ... fetch data ...
    result = {"sport": sport, "data": [...]}
    return JSONResponse(_sanitize_public(result))  # ❌ WRONG for dual-use
```

**The Fix:**
```python
@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    # ... fetch data ...
    result = {"sport": sport, "data": [...]}
    return result  # ✅ FastAPI auto-serializes dicts for endpoints
```

**Prevention Rules:**
1. Functions used BOTH as endpoints AND internally MUST return dicts (not JSONResponse)
2. FastAPI automatically serializes dict returns to JSON for endpoint responses
3. Only use `JSONResponse()` when you need custom headers, status codes, or media types
4. Before calling any `async def` function internally, check if it's also an endpoint handler
5. Search for dual-use patterns: `grep -n "@router" *.py` then check if those functions are called elsewhere

**Verification:**
```bash
# Find endpoint handlers
grep -n "@router.get\|@router.post" live_data_router.py | head -20

# Check if any are called internally (not just as endpoints)
# Example: get_sharp_money is defined at line 1758
grep -n "get_sharp_money(" live_data_router.py
# If called anywhere other than the decorator line, it's dual-use
```

**Files Affected:**
- `live_data_router.py:1758-1989` - `get_sharp_money()` fixed to return dict

**Fixed in:** Commit `d7279e9` (Feb 2026)

### Lesson 10: Undefined Variables in Nested Functions
**Problem:** Multiple `NameError` and `TypeError` crashes in `calculate_pick_score()` due to undefined variables or None comparisons.

**Bugs Found (Feb 2026 Debugging Session):**
| Variable | Error | Line | Fix |
|----------|-------|------|-----|
| `_game_date_obj` | NameError | 3571 | Initialize to `None` before try block (line 3440) |
| `jarvis_rs >= 7.5` | TypeError | 3527 | Add `jarvis_rs is not None and` check |
| `esoteric_reasons` | NameError | various | Initialize as `[]` at function start |
| `odds`, `candidate` | NameError | GLITCH section | Removed undefined variable usage |

**Root Cause:** Nested function `calculate_pick_score()` inside `_best_bets_inner()` uses many variables. When code paths skip initialization (e.g., try block fails early), variables remain undefined.

**Prevention Rules:**
1. Initialize ALL variables at the START of the function, before any try blocks
2. Variables used in except/finally blocks MUST be initialized before the try
3. Before comparing numeric variables (e.g., `>= 7.5`), check for None
4. Use `variable is not None and variable >= threshold` pattern
5. When adding new variables to nested functions, grep for all usages and verify initialization

**Pattern:**
```python
# ✅ CORRECT - Initialize before try block
_game_date_obj = None  # Initialize here
glitch_adjustment = 0.0
try:
    _game_date_obj = parse_date(...)  # May fail
    # ... use _game_date_obj ...
except Exception:
    pass  # _game_date_obj is still None, not undefined

# Later code can safely check:
if _game_date_obj:  # Won't raise NameError
    do_something(_game_date_obj)
```

**Fixed in:** Commits `f1b9dae`, `fd4f105`, `559e173`, `4b0a35e`, `0d66095` (Feb 2026)

### Lesson 11: Production Debugging Without Logs Access
**Problem:** `BEST_BETS_FAILED` error gave no details about the actual exception. Had to iterate through multiple deploy cycles to find bugs.

**Solution Implemented:** Added detailed error info to response in debug mode:
```python
except Exception as e:
    import traceback as _tb
    _tb_str = _tb.format_exc()
    logger.error("best-bets CRASH: %s\n%s", e, _tb_str)
    detail = {"code": "BEST_BETS_FAILED", "message": "best-bets failed"}
    if debug_mode:
        detail["error_type"] = type(e).__name__
        detail["error_message"] = str(e)
        detail["traceback"] = _tb_str[-2000:]  # Last 2000 chars
    raise HTTPException(status_code=500, detail=detail)
```

**Usage:**
```bash
# Get detailed error info
curl "/live/best-bets/NBA?debug=1" -H "X-API-Key: KEY"
# Returns: {"detail": {"code": "...", "error_type": "AttributeError", "error_message": "...", "traceback": "..."}}
```

**Prevention:**
- ALL major endpoints should include error details in debug mode
- Never swallow exceptions silently - always log with traceback
- Use `?debug=1` query param to get verbose error info in production

**Fixed in:** Commit `1cf5290` (Feb 2026)

### Lesson 12: API Data Format Mismatches (Playbook vs ESPN)
**Problem:** Injuries data wasn't being parsed correctly. Playbook and ESPN return injuries in different formats:
- **Playbook:** Team objects with nested `players` array (`{"teamName": "...", "players": [...]}`)
- **ESPN:** Flat list with `team` field per injury (`{"team": "...", "player": "..."}`)

**Root Cause:** Code assumed ESPN format (flat list), but production uses Playbook which nests players under team objects.

**Prevention:**
- When integrating API data, check BOTH format variations the API might return
- Add format detection: `if "players" in item and isinstance(item.get("players"), list)`
- Normalize to common format before use
- Test with actual production API responses, not assumptions

**Fixed in:** Commit `01b372c` (Feb 2026)

### Lesson 13: Scope Issues with Context Calculations
**Problem:** Context values (def_rank, pace, vacuum) were only calculated for PROP picks, not GAME picks. GAME picks got default values (def_rank=16, pace=100, vacuum=0).

**Root Cause:** The context lookup code was inside the `if pick_type == "PROP"` block instead of running for ALL pick types.

**Prevention:**
- Context calculations (Pillars 13-15) should run BEFORE the pick_type branch
- Move shared context setup OUTSIDE type-specific blocks
- Verify all pick types show real values in debug output, not just defaults
- Test: `curl /live/best-bets/NBA?debug=1 | jq '.game_picks.picks[0].context_layer'`

**Fixed in:** Commit `6780c93` (Feb 2026)

### Lesson 14: NCAAB Team Name Matching (Mascot Stripping)
**Problem:** NCAAB team names from Odds API include mascots ("North Carolina Tar Heels") but context layer data uses short names ("North Carolina"). This caused all NCAAB picks to get default context values.

**Additional Issue:** Aggressive fuzzy matching caused false positives where "Alabama St Hornets" matched "Alabama" (Crimson Tide) and "North Carolina Central Eagles" matched "North Carolina" (Tar Heels) - completely different schools.

**Root Cause:** The `standardize_team()` function only handled abbreviations, not NCAAB mascot suffixes.

**Solution Implemented:**
1. Added `NCAAB_TEAM_MAPPING` dict with 80+ major program mappings
2. Added `MASCOT_SUFFIXES` whitelist for conservative fuzzy matching
3. Only strip suffixes that are known mascots (not school identifiers like "St" or "Central")

**Key Code (context_layer.py):**
```python
NCAAB_TEAM_MAPPING = {
    "North Carolina Tar Heels": "North Carolina",
    "Duke Blue Devils": "Duke",
    "Syracuse Orange": "Syracuse",
    # ... 80+ mappings
}

MASCOT_SUFFIXES = {
    "Wildcats", "Tigers", "Bulldogs", "Eagles", "Tar Heels",
    "Blue Devils", "Orange", "Crimson Tide", ...
}
```

**Prevention:**
- Always check API team name format vs data format when adding new sports/data
- Use explicit mappings for common cases, conservative fuzzy matching for edge cases
- Test with both major programs AND small schools to catch false positives
- Verify: `curl /live/best-bets/NCAAB?debug=1 | jq '[.game_picks.picks[] | {matchup, pace}] | unique'`

**Known Limitation:** Small schools not in data (SE Louisiana, Gardner-Webb, etc.) will correctly get defaults.

**Fixed in:** Commits `98117dc`, `6518478` (Feb 2026)

### Lesson 15: ESPN Officials Integration (Pillar 16)
**Problem:** Pillar 16 (Officials) code was ready in `OfficialsService` but had no data source - the placeholder code had empty strings for `lead_official`, `official_2`, `official_3`.

**Solution Implemented (v17.2):**
1. Created `alt_data_sources/espn_lineups.py` - ESPN Hidden API integration (FREE, no auth)
2. Added ESPN scoreboard fetch to parallel gather in `_best_bets_inner()`
3. Prefetch officials for all games in batch operation
4. Store in `_officials_by_game[(home_lower, away_lower)]` lookup
5. Scoring function accesses via closure (like `_injuries_by_team`)

**ESPN Hidden API Endpoints:**
- Scoreboard: `https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard`
- Officials: `https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/officials`

**Key Files:**
```
alt_data_sources/espn_lineups.py    # NEW - ESPN API client
live_data_router.py:266-277         # NEW - ESPN import
live_data_router.py:4207-4222       # MODIFIED - Parallel fetch includes ESPN
live_data_router.py:4267-4311       # NEW - Officials lookup building
live_data_router.py:3720-3770       # MODIFIED - Officials section uses prefetched data
```

**Verification:**
```bash
# Check if officials data appears in picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {officials_adjustment, research_reasons}'
# Should include "Officials: ..." in research_reasons when refs are assigned
```

**Note:** ESPN may not have officials data for all games (refs assigned closer to game time). The system gracefully falls back when data is unavailable.

**Fixed in:** Commit (Feb 2026)

### Lesson 16: NHL Team Name Accent Normalization
**Problem:** ESPN may return "Montréal Canadiens" (with accent) but context layer data uses "Montreal Canadiens" (without accent), causing lookup misses.

**Solution:** Added `NHL_ACCENT_MAP` to `standardize_team()` in `context_layer.py`:
```python
NHL_ACCENT_MAP = {
    "Montréal Canadiens": "Montreal Canadiens",
    "Montréal": "Montreal",
}
```

**Prevention:** When integrating external APIs, check for Unicode character variants (accents, special characters) that may differ from local data.

**Fixed in:** Commit (Feb 2026)

### Lesson 17: ESPN Data Expansion for Cross-Validation (v17.3)
**Problem:** We had ESPN officials working but weren't using the rich data available in ESPN's summary endpoint (odds, injuries, venue, weather).

**Solution Implemented (v17.3):**
1. Expanded `alt_data_sources/espn_lineups.py` with new extraction functions
2. Batch fetch ESPN enriched data (odds, injuries, venue) for ALL games in parallel
3. Use ESPN odds for cross-validation (+0.25-0.5 research boost when confirmed)
4. Merge ESPN injuries with Playbook injuries
5. Use ESPN venue/weather as fallback for outdoor sports (MLB, NFL)

**New Functions Added:**
```python
get_espn_odds(sport, event_id)        # Spread, ML, O/U extraction
get_espn_injuries(sport, event_id)    # Inline injury data
get_espn_player_stats(sport, event_id) # Box scores for props
get_espn_venue_info(sport, event_id)  # Venue, weather, attendance
get_game_summary_enriched(...)        # All data in one call
get_all_games_enriched(sport)         # Batch for all games
```

**Integration Points in live_data_router.py:**
```
Line 4333-4395: Batch fetch ESPN enriched data
Line 4397-4408: Merge ESPN injuries with Playbook
Line 3281-3312: ESPN odds cross-validation boost
Line 4700-4737: ESPN venue/weather for outdoor sports
```

**Research Boost Logic:**
```python
# ESPN confirms our spread (diff <= 0.5) → +0.5
# ESPN spread close (diff <= 1.0) → +0.25
# ESPN confirms total (diff <= 1.0) → +0.5
# ESPN total close (diff <= 2.0) → +0.25
```

**Prevention:**
- When a free API offers rich data, USE ALL OF IT
- Cross-validate primary data sources with secondary sources
- Batch parallel fetches to avoid N+1 query problems
- Always merge supplementary data, don't replace

**Fixed in:** Commit `f10de5b` (Feb 2026)

### Lesson 18: NCAAB Team Coverage Expansion (50 → 75 Teams)
**Problem:** NCAAB defensive data only covered Top 50 teams, causing mid-major tournament teams (VCU, Dayton, Murray State, etc.) to get default values.

**Solution Implemented:**
1. Expanded `NCAAB_DEFENSE_VS_GUARDS/WINGS/BIGS` from 50 to 75 teams
2. Added 25 mid-major tournament regulars (51-75)
3. Expanded `NCAAB_PACE` with pace values for these teams
4. Updated `DefensiveRankService.get_total_teams()` from 50 to 75

**Teams Added (51-75):**
```python
VCU, Dayton, Saint Mary's, Nevada, New Mexico, UNLV, Drake, Murray State,
Richmond, Davidson, Wichita State, FAU, UAB, Grand Canyon, Akron, Toledo,
Boise State, Utah State, Colorado State, George Mason, Saint Louis,
Loyola Chicago, Princeton, Yale, Liberty
```

**Prevention:**
- When adding team data, include tournament-relevant mid-majors
- Test with actual games to verify coverage
- Update team count constants when expanding data

**Fixed in:** Commit `46f81c6` (Feb 2026)

### Lesson 19: MLB SPORT_MAPPING Bug
**Problem:** MLB ESPN data wasn't being fetched - all MLB games showed empty ESPN enriched data.

**Root Cause:** Typo in `SPORT_MAPPING` - `"mlb": "mlb"` instead of `"league": "mlb"`:
```python
# BUG (wrong key name):
"MLB": {"sport": "baseball", "mlb": "mlb"}

# FIX (correct key name):
"MLB": {"sport": "baseball", "league": "mlb"}
```

**Prevention:**
- Verify all dictionary keys are consistent across the mapping
- Test ALL sports after adding/modifying sport mappings
- Use constants for repeated key names when possible

**Fixed in:** Commit `018d9ef` (Feb 2026)

### Lesson 20: Contradiction Gate Silent Failure
**Problem:** Both Over AND Under were returned for same totals. Contradiction gate wasn't blocking anything.

**Root Cause:** `filter_contradictions()` returned `[], {}` (empty dict) when props list was empty, but `apply_contradiction_gate()` expected dict with `contradictions_detected` key. This caused a silent `KeyError` that was caught by the try/except fallback.

**The Silent Failure Pattern:**
```python
try:
    filtered_props, filtered_games, debug = apply_contradiction_gate(...)
except Exception as e:
    # Fallback silently used - BUG HIDDEN
    filtered_props = filtered_props
    filtered_games = filtered_game_picks
```

**Fix:** Return proper dict structure when empty:
```python
if not picks:
    return [], {"contradictions_detected": 0, "picks_dropped": 0, "contradiction_groups": []}
```

**Prevention:**
- Always return consistent dict structure, not empty `{}`
- Log exceptions in fallback blocks (don't just swallow)
- Add assertions for expected dict keys in tests
- Test contradiction gate with empty props + non-empty games (the failure case)

**Fixed in:** Commit `b5ffc3c` (Feb 2026)

### Lesson 21: SERP Shadow Mode Default (Live Mode Required)
**Problem:** SERP intelligence was configured with `SERP_SHADOW_MODE=True` by default, which zeroed all boosts. User explicitly wanted LIVE MODE where boosts are actively applied to scoring.

**Root Cause:** The default was set to True (shadow/observation mode) as a safety measure during initial implementation, but it was never flipped to False for production use.

**The Shadow Mode Pattern:**
```python
# WRONG - All boosts zeroed, signals logged but never applied
SERP_SHADOW_MODE = _env_bool("SERP_SHADOW_MODE", True)  # ❌

# CORRECT - Boosts applied to scoring (LIVE MODE)
SERP_SHADOW_MODE = _env_bool("SERP_SHADOW_MODE", False)  # ✅
```

**What Shadow Mode Does:**
- When `True`: All SERP boosts are logged but set to 0.0 before applying
- When `False`: Boosts from Silent Spike, Sharp Chatter, Narrative, etc. actively modify scores

**Prevention:**
- Always verify `SERP_SHADOW_MODE` default in `core/serp_guardrails.py`
- Check debug output shows `shadow_mode: false` and `mode: "live"`
- Test that picks have non-zero `serp_boost` when signals fire
- User confirmed preference: "i dont want anything in shadowmode. I want everything active"

**Verification:**
```bash
# Must show shadow_mode: false, mode: "live"
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.serp'
```

**Fixed in:** Commit enabling SERP live mode by default (Feb 2026)

### Lesson 22: pick_type Value Mismatch (v17.5)
**Problem:** Phase 1 dormant signals (Gann Square, Founder's Echo) weren't triggering because the code checked `pick_type == "GAME"`, but game picks use `pick_type` values of "SPREAD", "MONEYLINE", or "TOTAL".

**Root Cause:** The `pick_type` parameter passed to `calculate_pick_score()` varies by market:
- Spread bets: `pick_type = "SPREAD"`
- Moneyline bets: `pick_type = "MONEYLINE"`
- Total (O/U) bets: `pick_type = "TOTAL"`
- Props: `pick_type = "PROP"`
- Sharp signals: `pick_type = "SHARP"`

The code assumed game picks would have `pick_type = "GAME"`, which is only used as a default/fallback.

**The Bug Pattern:**
```python
# WRONG - "GAME" never matches for actual game picks
if pick_type == "GAME" and spread and total:  # ❌ Never triggers

# CORRECT - Check for all game-related pick types
_is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")
if _is_game_pick and spread and total:  # ✅ Works correctly
```

**Prevention:**
- Before using `pick_type` in conditions, trace where it's set (search for `pick_type=`)
- Game picks: "SPREAD", "MONEYLINE", "TOTAL", "SHARP"
- Prop picks: "PROP"
- Test with real production data, not assumptions
- Check actual API response `pick_type` values: `jq '[.game_picks.picks[].pick_type] | unique'`

**Verification:**
```bash
# Check actual pick_type values in production
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].pick_type] | unique'
# Returns: ["moneyline", "spread", "total"] - NOT "GAME"
```

**Fixed in:** Commit `9e01390` (Feb 2026)

### Lesson 23: Dormant Signal Activation Pattern (v17.5)
**Problem:** esoteric_engine.py contained fully implemented signals (Biorhythms, Gann Square, Founder's Echo) that were never called from the scoring pipeline.

**Root Cause:** Functions were written during initial development but integration points were never added to `calculate_pick_score()` in live_data_router.py.

**Solution Pattern (Phase 1 Activation):**
1. Identify dormant functions: `grep -r "def function_name" esoteric_engine.py`
2. Verify function is NOT called: `grep -r "function_name(" live_data_router.py`
3. Find correct integration point (after GLITCH, before esoteric_score clamp)
4. Add signal with proper pick_type guard (use `_is_game_pick` pattern)
5. Add to `esoteric_reasons` for debug visibility
6. Add boost to `esoteric_raw` (NOT to esoteric_score directly)
7. Test with production curl commands

**Phase 1 Signals Activated:**
| Signal | Pick Type | Boost Range | Function |
|--------|-----------|-------------|----------|
| Biorhythms | PROP only | +0.3 (PEAK), +0.15 (RISING), -0.2 (LOW) | `calculate_biorhythms()` |
| Gann Square | GAME only | +0.25 (STRONG), +0.15 (MODERATE), +0.1 (Combined) | `analyze_spread_gann()` |
| Founder's Echo | GAME only | +0.2 (single), +0.35 (both) | `check_founders_echo()` |

**Integration Point:** `live_data_router.py:3605-3710` (after GLITCH, before esoteric_score clamp)

**Esoteric Engine Status:** Was 8/10 signals active after Phase 1 (now 10/10 after v17.6)

**Verification:**
```bash
# Check esoteric_reasons for new signals
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | unique'
# Should show: "Gann: 45° (MODERATE)", "Biorhythm: PEAK (85)", etc.
```

**Fixed in:** Commits `2bfa25e`, `9e01390` (Feb 2026)

### Lesson 24: Benford Multi-Book Aggregation Fix (v17.6)
**Problem:** Benford's Law anomaly detection NEVER triggered because it requires 10+ values for statistical significance, but only 3 values were passed (prop_line, spread, total).

**Root Cause:** Original implementation only collected the primary line values:
```python
# BAD - Only 3 values, Benford always skips
_line_values = []
if prop_line: _line_values.append(prop_line)      # 1 value
if spread: _line_values.append(abs(spread))       # 2 values
if total: _line_values.append(total)              # 3 values
# len(_line_values) < 10, so Benford NEVER runs
```

**Solution:** Extract multi-book lines from `game.bookmakers[]` array (Odds API returns 5-10 sportsbooks):
```python
# GOOD - 10-25 values from multiple books
def _extract_benford_values_from_game(game: dict, prop_line, spread, total) -> list:
    values = []
    if prop_line: values.append(prop_line)
    if spread: values.append(abs(spread))
    if total: values.append(total)

    for bm in game.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market.get("key") == "spreads":
                for outcome in market.get("outcomes", []):
                    point = outcome.get("point")
                    if point is not None:
                        values.append(abs(point))
            elif market.get("key") == "totals":
                for outcome in market.get("outcomes", []):
                    point = outcome.get("point")
                    if point is not None and point > 0:
                        values.append(point)
    return list(dict.fromkeys(values))  # Deduplicate
```

**Key Insight:** The Odds API data was already available but not being utilized. Multi-book data provides 10-25 unique line values across sportsbooks.

**Integration Pattern:**
1. Add `game_bookmakers=None` parameter to `calculate_pick_score()` function signature
2. Pass `game_bookmakers=candidate.get("bookmakers", [])` from all 3 call sites
3. Use helper to extract values: `_extract_benford_values_from_game({"bookmakers": game_bookmakers}, ...)`
4. Pass to GLITCH: `value_for_benford=_line_values if len(_line_values) >= 10 else None`

**Files Modified:**
- `live_data_router.py:3150-3165` - Added `_extract_benford_values_from_game()` helper
- `live_data_router.py:3210` - Updated function signature with `game_bookmakers` param
- `live_data_router.py:3590-3610` - Updated Benford value collection
- `live_data_router.py:5149, 5290, 5472` - Updated all 3 call sites

**Verification:**
```bash
# Check Benford now receives 10+ values
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '.game_picks.picks[0].glitch_breakdown.benford | {values_count, triggered, distribution}'
# values_count should be 10-25
```

**Fixed in:** v17.6 (Feb 2026)

### Lesson 25: Function Parameter Threading Pattern (v17.6)
**Problem:** When adding new data to a scoring function called from multiple locations, ALL call sites must be updated or the data will be `None`.

**Root Cause:** `calculate_pick_score()` is called from 3 different places:
1. Game picks loop (~line 5149)
2. Props loop (~line 5290)
3. Sharp money loop (~line 5472)

Adding `game_bookmakers=None` to the function signature without updating all call sites means 2 out of 3 calls would pass `None`.

**Solution Pattern:**
1. **Grep for all call sites FIRST:** `grep -n "calculate_pick_score(" live_data_router.py`
2. **Count call sites:** Expect 3+ (definition + calls)
3. **Update ALL call sites** with the new parameter
4. **Verify no calls are missing:** Re-run grep after changes

**Example Fix:**
```python
# Call site 1 (game picks) - line 5149
pick_score_result = calculate_pick_score(
    ...,
    game_bookmakers=candidate.get("bookmakers", [])  # NEW
)

# Call site 2 (props) - line 5290
pick_score_result = calculate_pick_score(
    ...,
    game_bookmakers=candidate.get("bookmakers", [])  # NEW
)

# Call site 3 (sharp money) - line 5472
pick_score_result = calculate_pick_score(
    ...,
    game_bookmakers=candidate.get("bookmakers", [])  # NEW
)
```

**Invariant:** When adding parameters to multi-call-site functions, update ALL call sites in the same commit.

**Verification:**
```bash
# Verify all call sites pass the parameter
grep -n "calculate_pick_score(" live_data_router.py | wc -l
# Should be 4 (1 definition + 3 calls)

grep -n "game_bookmakers=" live_data_router.py | wc -l
# Should be 4 (matching all call sites)
```

**Fixed in:** v17.6 (Feb 2026)

### Lesson 26: Officials Tendency Integration Pattern (v17.8)
**Problem:** Pillar 16 (Officials) had ESPN data source wired but always returned 0.0 adjustment because there was no interpretation layer - no data about what referee names MEAN for betting.

**Root Cause:** ESPN provides referee names, but without tendency data, we couldn't calculate adjustments:
```python
# ESPN provided: {"lead_official": "Scott Foster", ...}
# But OfficialsService returned: (0.0, [])
# Because there was no tendency database
```

**Solution (v17.8):**
1. Create `officials_data.py` with referee tendency database
2. Add `get_officials_adjustment()` method to `OfficialsService`
3. Wire tendency-based adjustments in `live_data_router.py`

**Key Files:**
```
officials_data.py                   # Referee tendency database
├── NBA_REFEREES (25 refs)          # Scott Foster, Tony Brothers, etc.
├── NFL_REFEREES (17 crews)         # Carl Cheffers, Brad Allen, etc.
├── NHL_REFEREES (15 refs)          # Wes McCauley, Chris Rooney, etc.
├── get_referee_tendency()          # Lookup function
└── calculate_officials_adjustment()# Adjustment calculation

context_layer.py
└── OfficialsService.get_officials_adjustment()  # Uses officials_data module

live_data_router.py (lines 4055-4106)
└── Pillar 16 section                # Wires tendency-based adjustments
```

**Adjustment Logic:**
| Condition | Boost | Example |
|-----------|-------|---------|
| Over tendency > 52% + Over pick | +0.1 to +0.3 | Scott Foster (54%) |
| Over tendency < 48% + Under pick | +0.1 to +0.3 | Marc Davis (47%) |
| Home bias > 1.5% + Home pick | +0.1 to +0.2 | Kane Fitzgerald (+2%) |
| Home bias < -1.5% + Away pick | +0.1 to +0.2 | Bill Kennedy (-2%) |

**Invariant:** External data (names, IDs) is useless without an interpretation layer that converts it to betting-relevant signals. When adding a new data source, also add the lookup/tendency database.

**Verification:**
```bash
# Check officials adjustments in picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].research_reasons] | flatten | map(select(startswith("Officials")))'

# Test officials_data module
python3 -c "
from officials_data import get_referee_tendency, calculate_officials_adjustment
print('Scott Foster:', get_referee_tendency('NBA', 'Scott Foster'))
adj, reason = calculate_officials_adjustment('NBA', 'Scott Foster', 'TOTAL', 'Over')
print(f'Adjustment: {adj:+.2f} ({reason})')
"
```

**Fixed in:** v17.8 (Feb 2026)

### Lesson 27: Trap Learning Loop Architecture (v19.0)
**Problem:** Manual weight adjustments based on observed patterns (e.g., "Dallas always covers by 20+ when favored") required human intervention and weren't systematically tracked.

**Solution Implemented (v19.0):**
1. Create `trap_learning_loop.py` - Core hypothesis-driven learning system
2. Create `trap_router.py` - RESTful API for trap CRUD operations
3. Add scheduler job at 6:15 AM ET for post-game trap evaluation
4. JSONL storage for traps, evaluations, and adjustment audit trail

**Architecture Pattern - Hypothesis-Driven Learning:**
```
PRE-GAME: User creates trap with condition + action
          "If Dallas wins by 20+, reduce public_fade by 1%"
                    ↓
POST-GAME: System evaluates condition against results
          Yesterday's games → enrich_game_result() → check conditions
                    ↓
ADJUSTMENT: If condition met AND safety checks pass
          Apply delta to target_engine.target_parameter
                    ↓
AUDIT: Log to adjustments.jsonl with full context
```

**Key Design Decisions:**
| Decision | Why |
|----------|-----|
| JSONL storage (not DB) | Matches existing grader pattern, portable, human-readable |
| 5% single / 15% cumulative caps | Prevents runaway adjustments from bad traps |
| 24h cooldown default | Allows observation before next trigger |
| Decay factor (0.7x) | Reduces impact of repeatedly-firing traps |
| Separate evaluation time (6:15 AM) | Runs after grading (6:00 AM) has results |
| Dry-run endpoint | Test traps before committing to production |

**Condition Language Design:**
- JSON-based for API compatibility
- Operator support: AND, OR
- Comparators: ==, !=, >, <, >=, <=, IN, BETWEEN
- Extensible fields: outcome, date, gematria, prior scores

**Safety Guards (Defense in Depth):**
1. **Validation on create**: Engine/parameter must exist in SUPPORTED_ENGINES
2. **Cooldown check**: Skip if triggered within cooldown_hours
3. **Weekly limit**: Skip if max_triggers_per_week exceeded
4. **Single cap**: Clamp adjustment to MAX_SINGLE_ADJUSTMENT (5%)
5. **Cumulative cap**: Clamp total adjustments to MAX_CUMULATIVE_ADJUSTMENT (15%)
6. **Parameter bounds**: New value clamped to engine's valid range
7. **Audit trail**: Every adjustment logged with before/after values

**Integration Points:**
```python
# main.py - Register router
from trap_router import trap_router
app.include_router(trap_router)

# daily_scheduler.py - Add evaluation job
self.scheduler.add_job(
    self._run_trap_evaluation,
    CronTrigger(hour=6, minute=15, timezone="America/New_York"),
    id="trap_evaluation"
)
```

**Invariant:** Learning systems must have safety bounds. Unbounded automated adjustments can destabilize scoring. Always cap single and cumulative changes, enforce cooldowns, and maintain audit trails.

**Fixed in:** v19.0 (Feb 2026)

### Lesson 28: Complete Learning System Pattern (v19.1)
**Problem:** After implementing AutoGrader (statistical) and Trap Learning Loop (hypothesis-driven), we discovered 15 gaps where learning should happen but doesn't:
- GAP 1: Research Engine signals (sharp_money, public_fade, line_variance) not tracked for learning
- GAP 2: GLITCH/Esoteric signals not tracked for learning
- GAP 3: Props vs Games treated identically (no pick_type differentiation)
- GAP 4: AutoGrader and Trap Learning Loop could conflict on same parameter
- GAP 5: No confidence decay (old picks weighted same as recent)

**Solution Implemented (v19.1):**
1. Expanded `PredictionRecord` with ALL 28 signal tracking fields
2. Updated `calculate_bias()` to analyze ALL signals with 70% confidence decay
3. Added `pick_type_breakdown` for differentiated learning (PROP vs SPREAD vs TOTAL)
4. Added Trap-AutoGrader reconciliation (24h lookback prevents conflicts)
5. Updated `live_data_router.py` to extract and persist all signal contributions

**Key Design Decisions:**
| Decision | Why |
|----------|-----|
| Track ALL 28 signals | Complete learning coverage - no blind spots |
| 70% confidence decay | Recent picks more relevant than older picks |
| pick_type differentiation | Props behave differently than game picks |
| 24h reconciliation window | Prevents conflicting adjustments |
| Dict fields for GLITCH/Esoteric | Flexible signal structure, easy to extend |

**Signal Coverage (28 total):**
| Category | Count | Signals |
|----------|-------|---------|
| Context Layer | 5 | defense, pace, vacuum, lstm, officials |
| Research Engine | 3 | sharp_money, public_fade, line_variance |
| GLITCH Protocol | 6 | chrome_resonance, void_moon, noosphere, hurst, kp_index, benford |
| Esoteric Engine | 14 | numerology, astro, fib_alignment, fib_retracement, vortex, daily_edge, biorhythms, gann, founders_echo, lunar, mercury, rivalry, streak, solar |

**Reconciliation Pattern:**
```python
# In AutoGrader.adjust_weights_with_reconciliation()
for param in parameters_to_adjust:
    if has_recent_trap_adjustment(engine, param, lookback_hours=24):
        logger.info("SKIP %s.%s - trap adjusted in last 24h", engine, param)
        continue
    # Apply statistical adjustment
```

**Verification Commands:**
```bash
# Check all signal fields in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  glitch_signals: .glitch_signals,
  esoteric_contributions: .esoteric_contributions,
  research_breakdown: .research_breakdown
}'

# Check bias calculation includes all signals
curl /live/grader/bias/NBA?days_back=1 -H "X-API-Key: KEY" | jq '.factor_bias | keys'

# Check pick_type breakdown
curl /live/grader/bias/NBA?days_back=7 -H "X-API-Key: KEY" | jq '.pick_type_breakdown'
```

**Invariant:** Every signal contribution MUST be tracked for learning. Two learning systems MUST NOT conflict. Philosophy: "Competition + variance. Learning loop baked in via fused upgrades."

**Fixed in:** v19.1 (Feb 2026)

### Lesson 29: Timezone-Aware vs Naive Datetime Comparisons (v18.2)
**Problem:** Phase 8 lunar phase calculation crashed with `TypeError: can't subtract offset-naive and offset-aware datetimes` because the reference date was created without a timezone.

**Root Cause:**
```python
# WRONG - ref_date is naive (no timezone)
ref_date = datetime(2000, 1, 6, 18, 14, 0)  # Reference new moon
days_since = (game_datetime - ref_date).days  # CRASH! Can't mix aware/naive
```

**Solution:**
```python
# CORRECT - Both datetimes are timezone-aware
from zoneinfo import ZoneInfo

ref_date = datetime(2000, 1, 6, 18, 14, 0, tzinfo=ZoneInfo("UTC"))
game_datetime = datetime.now(ZoneInfo("America/New_York"))
days_since = (game_datetime - ref_date).days  # Works!
```

**Prevention:**
- When doing datetime arithmetic, BOTH datetimes must be timezone-aware
- Use `ZoneInfo("UTC")` for reference dates
- Use `ZoneInfo("America/New_York")` for game times
- The NEVER DO rule 88 enforces this

**Fixed in:** v18.2 (Feb 2026) - `calculate_lunar_phase_intensity()` line 1422-1426

### Lesson 30: Environment Variable OR Logic (v18.2)
**Problem:** SERP API integration failed because the env var check used AND logic when it should have used OR. Both `SERPAPI_KEY` and `SERP_API_KEY` are valid alternatives, but the code required BOTH to be set.

**Root Cause:**
```python
# WRONG - Requires BOTH keys to be set
if SERPAPI_KEY and SERP_API_KEY:
    # Only runs if both exist

# Also WRONG - all() requires ALL to be truthy
if all([os.getenv("SERPAPI_KEY"), os.getenv("SERP_API_KEY")]):
    # Only runs if both exist
```

**Solution:**
```python
# CORRECT - Either key works
if any([os.getenv("SERPAPI_KEY"), os.getenv("SERP_API_KEY")]):
    key = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")
    # Runs if at least one exists
```

**Prevention:**
- Use `any()` for ALTERNATIVE env vars (either one works)
- Use `all()` for REQUIRED env vars (all must be set)
- Document which pattern is intended
- The NEVER DO rule 96 enforces this

**Fixed in:** v18.2 (Feb 2026)

### Lesson 31: Variable Initialization Before Conditional Use (v18.2)
**Problem:** Production crashed with `NameError: name 'weather_data' is not defined` because the variable was only assigned inside a conditional block but used outside it.

**Root Cause:**
```python
# WRONG - weather_data only defined if condition is True
if outdoor_sport:
    weather_data = fetch_weather()

# Later in code...
if weather_data:  # NameError if outdoor_sport was False!
    apply_weather_boost()
```

**Solution:**
```python
# CORRECT - weather_data always defined
weather_data = None  # Initialize first

if outdoor_sport:
    weather_data = fetch_weather()

# Later in code...
if weather_data:  # Safe - weather_data is always defined
    apply_weather_boost()
```

**Prevention:**
- Any variable used after a conditional block MUST be initialized before that block
- Initialize to `None`, `[]`, `{}`, or appropriate default
- The NEVER DO rule 90 enforces this

**Fixed in:** v18.2 (Feb 2026) - `weather_data = None` initialization at line 3345

### Lesson 32: Auto Grader Weights Must Include All Stat Types (v20.2)
**Problem:** Auto grader returned "No graded predictions found" for ALL game picks (spread, total, moneyline, sharp) even though 242 graded picks existed.

**Root Cause:** The `_initialize_weights()` method only created `WeightConfig` entries for PROP stat types (points, rebounds, assists, etc.) but NOT for GAME stat types (spread, total, moneyline, sharp).

```python
# BUG - Only PROP stat types initialized
stat_types = {
    "NBA": ["points", "rebounds", "assists", "threes", ...],  # PROP only
    ...
}
for stat in stat_types.get(sport, ["points"]):
    self.weights[sport][stat] = WeightConfig()
# Missing: spread, total, moneyline, sharp
```

**The Bug Flow:**
1. `run_daily_audit()` called `adjust_weights(sport, "spread")`
2. `adjust_weights()` checked if "spread" was in `weights[sport]` → **NO**
3. Line 802-803 defaulted to `stat_type = "points"` as fallback
4. `calculate_bias()` filtered for records where `record.stat_type == "points"`
5. Game picks have `stat_type` like "spread", "total" → **NO MATCH**
6. → "No graded predictions found" for ALL game picks

**Solution (v20.2):**
```python
# FIXED - Both PROP and GAME stat types initialized
prop_stat_types = {
    "NBA": ["points", "rebounds", "assists", ...],
    ...
}
game_stat_types = ["spread", "total", "moneyline", "sharp"]

for sport in self.SUPPORTED_SPORTS:
    self.weights[sport] = {}
    # Initialize PROP stat types
    for stat in prop_stat_types.get(sport, ["points"]):
        self.weights[sport][stat] = WeightConfig()
    # Initialize GAME stat types
    for stat in game_stat_types:
        self.weights[sport][stat] = WeightConfig()
```

**Prevention:**
- When adding new pick types (market types), ensure weights are initialized for them
- The `stat_type` field in `PredictionRecord` comes from `pick_type.lower()` for game picks
- Verify with: `curl /live/grader/bias/NBA?stat_type=spread` - should return sample_size > 0
- The NEVER DO rules 108-111 enforce this

**Verification Commands:**
```bash
# Check all game stat types have weights
for stat in spread total moneyline sharp; do
  echo "=== $stat ==="
  curl -s "/live/grader/bias/NBA?stat_type=$stat&days_back=1" -H "X-API-Key: KEY" | \
    jq '{stat_type: .stat_type, sample_size: .bias.sample_size, hit_rate: .bias.overall.hit_rate}'
done
# All should show sample_size > 0 (if graded picks exist)
```

**Fixed in:** v20.2 (Feb 2026) - Commit `ac25a59`

### Lesson 33: OVER Bet Performance Tracking (v20.2 Analysis)
**Problem:** Feb 3, 2026 analysis revealed severe OVER bias - 19.1% win rate on OVER bets vs 81.6% on UNDER bets.

**Performance Data (Feb 3, 2026):**
| Market | Record | Win Rate | Assessment |
|--------|--------|----------|------------|
| SPREAD | 96-21-40 | 82.1% | Excellent |
| UNDER | 31-7 | 81.6% | Excellent |
| OVER | 9-38 | 19.1% | **Critical Problem** |

**Root Cause:** The system was overvaluing OVER bets. 38 of 66 total losses (57.6%) came from OVER picks.

**Learning Loop Impact:**
- With v20.2 fix, the auto grader can now properly analyze this data
- `calculate_bias()` for "total" stat_type will detect the OVER bias
- Weights will be adjusted to reduce OVER confidence
- The esoteric/context signals that pushed OVER need recalibration

**Prevention:**
- Monitor OVER/UNDER split in daily grading reports
- Auto grader bias analysis now properly includes totals picks
- Consider market-type-specific confidence adjustments

**Action:** The v20.2 fix enables the learning loop to automatically adjust based on this performance data.

### Lesson 34: Verifying the Learning Loop is Working (v20.3)
**Problem:** After fixing the auto grader weights (v20.2), needed to verify the entire learning loop was functioning end-to-end.

**Verification Steps Performed (Feb 4, 2026):**
1. **Grader Status Check**: `available: true` ✅
2. **Grading Summary**: 242 graded picks, 136 wins, 66 losses (67.3% hit rate) ✅
3. **Bias Calculation for Game Types**: Working for all stat types ✅
4. **Weight Adjustments Applied**: `applied: true` with actual deltas ✅

**Key Verification Results:**

| Component | Endpoint | Expected | Actual |
|-----------|----------|----------|--------|
| Grader Status | `/live/grader/status` | `available: true` | ✅ Working |
| Weights Initialized | `/live/grader/weights/NBA` | All 11 stat types | ✅ spread, total, moneyline, sharp + props |
| Spread Bias | `/live/grader/bias/NBA?stat_type=spread` | sample_size > 0 | ✅ 53 samples, 84.9% hit rate |
| Total Bias | `/live/grader/bias/NBA?stat_type=total` | sample_size > 0 | ✅ 32 samples, 56.2% hit rate |
| Weight Adjustments | Run audit | `applied: true` | ✅ pace, vacuum, officials adjusted |
| Factor Correlations | Bias response | Non-null values | ✅ 28 signals tracked |

**What "Learning Loop Working" Means:**
1. Picks are being persisted to `/data/grader/predictions.jsonl`
2. Grading summary shows wins/losses/pushes
3. `calculate_bias()` returns sample_size > 0 for active stat types
4. `factor_bias` shows correlations for all tracked signals (pace, vacuum, officials, glitch, esoteric)
5. `weight_adjustments` shows `applied: true` with actual delta values
6. Confidence decay (70% per day) is being applied

**Factor Bias Signals Tracked (28 total):**
```python
factor_bias = {
    "pace": {"correlation": 0.088, "suggested_adjustment": -0.0088},
    "vacuum": {"correlation": 0.032, "suggested_adjustment": -0.0032},
    "officials": {"correlation": 0.313, "suggested_adjustment": -0.0313},
    "glitch": {
        "void_moon": {"correlation": 0.155},
        "kp_index": {"correlation": 0.0}
    },
    "esoteric": {
        "numerology": {"correlation": 0.114},
        "astro": {"correlation": 0.003},
        "fib_alignment": {"correlation": 0.146},
        "vortex": {"correlation": 0.058},
        "daily_edge": {"correlation": -0.313}
    }
}
```

**Prevention:**
- Run the full learning loop verification after any auto_grader.py changes
- Check both bias AND weight_adjustments sections of audit response
- Verify `applied: true` not just sample_size > 0
- Monitor factor correlations for outliers (e.g., officials at 0.313)

**Verification Command (Full Check):**
```bash
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '{
    stat_type,
    sample_size: .bias.sample_size,
    hit_rate: .bias.overall.hit_rate,
    weight_adjustments_applied: (.weight_adjustments != null),
    factors_tracked: (.bias.factor_bias | keys)
  }'
```

### Lesson 35: Grading Pipeline Missing SHARP/MONEYLINE/PROP Handling (v20.3)
**Problem:** Investigation revealed:
- **SHARP**: 18 picks, 0% hit rate (all graded as PUSH)
- **MONEYLINE**: 1 sample in 7 days
- **PROPS**: 0 samples in learning loop

**Root Causes Found:**

1. **SHARP picks graded as PUSH** (`result_fetcher.py:842-884`)
   - `grade_game_pick()` checked for "total", "spread", "moneyline" in pick_type
   - SHARP picks have `pick_type="SHARP"` which matched NONE of these
   - Fell through to `return "PUSH", 0.0` - never WIN or LOSS

2. **`picked_team` not passed** (`result_fetcher.py:1067-1075`)
   - Call to `grade_game_pick()` didn't include `picked_team` parameter
   - For spreads/moneylines, couldn't determine which team was picked

3. **`run_daily_audit()` prop_stat_types incomplete** (`auto_grader.py:1071-1077`)
   - Only audited: points, rebounds, assists
   - Missing: threes, steals, blocks, pra (4 prop types not analyzed)

4. **Prop stat lookup failures** (`result_fetcher.py:770-798`)
   - STAT_TYPE_MAP didn't include direct formats like "threes"
   - Market keys like "player_points_over_under" not cleaned

**Fixes Applied (v20.3):**

| Bug | Fix | File:Lines |
|-----|-----|------------|
| SHARP grading | Added `elif "sharp" in pick_type_lower` handling | `result_fetcher.py:893-916` |
| picked_team | Extract from selection/picked_team/team/side fields | `result_fetcher.py:1066-1074` |
| prop_stat_types | Synced with `_initialize_weights()` (7 NBA, 5 NFL, etc.) | `auto_grader.py:1071-1077` |
| STAT_TYPE_MAP | Added direct formats + market suffix stripping | `result_fetcher.py:80-125` |

**Verification Commands:**
```bash
# After next grading cycle, verify SHARP picks have WIN/LOSS (not all PUSH)
curl -s "/live/picks/grading-summary?date=$(date +%Y-%m-%d)" -H "X-API-Key: KEY" | \
  jq '[.graded_picks[] | select(.pick_type == "SHARP")] | group_by(.result) | map({result: .[0].result, count: length})'

# Verify prop stat types being audited
curl -s -X POST "/live/grader/run-audit" -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" -d '{"days_back": 1}' | \
  jq '.results.results.NBA | keys'
# Should include: points, rebounds, assists, threes, steals, blocks, pra, spread, total, moneyline, sharp
```

**Fixed in:** v20.3 (Feb 4, 2026)

### Lesson 36: Audit Drift Scan Line Number Filters (v20.4)
**Problem:** Go/no-go check failed with `audit_drift` error because the line number filter in `audit_drift_scan.sh` didn't match actual code locations.

**Root Cause:** The ensemble adjustment fallback code shifted from lines 4753-4757 to lines 4757-4763. The filter pattern `live_data_router.py:475[67]` allowed line 4757 but NOT line 4761 (the penalty code).

**The Failure:**
```
Found additive final_score +/-0.5 outside allowed ensemble adjustment:
live_data_router.py:4761:                            final_score = max(0.0, final_score - 0.5)
ERROR: Unexpected literal +/-0.5 applied to final_score
```

**The Fix:**
```bash
# OLD filter (incomplete)
rg -v "live_data_router.py:475[34]" | \
rg -v "live_data_router.py:475[67]" || true

# NEW filter (includes lines 4760-4762)
rg -v "live_data_router.py:475[34]" | \
rg -v "live_data_router.py:475[67]" | \
rg -v "live_data_router.py:476[012]" || true
```

**Prevention:**
- When code shifts (refactoring, additions), line-based filters in sanity scripts break
- After ANY change to `live_data_router.py`, re-run `audit_drift_scan.sh` locally
- Use broader patterns when possible, or document exact line purposes
- The filter comment now explains: "Lines 4757 (boost) and 4761 (penalty) are the fallback ensemble adjustments"

**Verification:**
```bash
# Check current ensemble adjustment line numbers
grep -n "final_score.*0\.5" live_data_router.py | grep -E "(min|max)"
# Should show lines ~4757 and ~4761

# Run audit_drift scan
bash scripts/audit_drift_scan.sh
# Should pass

# Full go/no-go
API_KEY="KEY" SKIP_NETWORK=0 SKIP_PYTEST=1 bash scripts/prod_go_nogo.sh
```

**Files Modified:**
- `scripts/audit_drift_scan.sh:43-48` - Updated filter pattern with comment

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 37: Endpoint Matrix Sanity Math Formula (v20.4)
**Problem:** `endpoint_matrix_sanity.sh` final_score math check failed because the formula was missing `ensemble_adjustment`.

**Root Cause:** The production API was returning `ensemble_adjustment: null` instead of `0.0` or an actual value, causing:
- Computed sum: 9.443
- Actual final_score: 9.94
- Difference: 0.497 (exceeds 0.02 tolerance)

**The Formula (must match scoring pipeline):**
```jq
($p.base_4_score + $p.context_modifier + $p.confluence_boost + $p.msrf_boost +
 $p.jason_sim_boost + $p.serp_boost + ($p.ensemble_adjustment // 0) +
 ($p.live_adjustment // 0) + ($p.totals_calibration_adj // 0)) as $raw |
($raw | if . > 10 then 10 else . end) as $capped |
($p.final_score - $capped) | abs
```

**Key Points:**
- `ensemble_adjustment` is exposed at `live_data_router.py:4939,4952`
- Default is `0.0` (line 4720), but can be `±0.5` based on ensemble model
- `totals_calibration_adj` is ±0.75 from `TOTALS_SIDE_CALIBRATION` (v20.4) - surfaced in v20.5
- `glitch_adjustment` is NOT added separately (already folded into `esoteric_score`)
- The `// 0` jq syntax handles null values
- **EVERY adjustment to final_score MUST be surfaced as a field** (Lesson 46)

**Prevention:**
- When adding new boosts/adjustments to scoring, update ALL THREE:
  1. `live_data_router.py` pick payload (surface as a named field)
  2. `scripts/endpoint_matrix_sanity.sh` math formula (add to jq sum)
  3. `CLAUDE.md` Boost Inventory + canonical formula
- Document formula in CLAUDE.md INVARIANT 4 (already done)

**Verification:**
```bash
# Check a pick's math manually
curl -s "/live/best-bets/NBA?debug=1&max_games=1" -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {
    base_4: .base_4_score,
    context: .context_modifier,
    confluence: .confluence_boost,
    msrf: .msrf_boost,
    jason_sim: .jason_sim_boost,
    serp: .serp_boost,
    ensemble: .ensemble_adjustment,
    live: .live_adjustment,
    totals_cal: .totals_calibration_adj,
    computed: (.base_4_score + .context_modifier + .confluence_boost +
               .msrf_boost + .jason_sim_boost + .serp_boost +
               (.ensemble_adjustment // 0) + (.live_adjustment // 0) +
               (.totals_calibration_adj // 0)),
    actual: .final_score,
    diff: ((.base_4_score + .context_modifier + .confluence_boost +
            .msrf_boost + .jason_sim_boost + .serp_boost +
            (.ensemble_adjustment // 0) + (.live_adjustment // 0) +
            (.totals_calibration_adj // 0)) - .final_score) | fabs
  }'
# diff should be < 0.02
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 38: OVER/UNDER Totals Bias Calibration (v20.4)
**Problem:** Learning loop revealed massive OVER vs UNDER imbalance:
- **OVER**: 9W / 38L = 19.1% hit rate (terrible)
- **UNDER**: 31W / 7L = 81.6% hit rate (excellent)

The contradiction gate was keeping whichever side scored higher. OVER picks consistently scored higher but lost more often.

**Root Cause:** No mechanism to apply learned bias corrections to totals scoring. Both Over and Under were scored identically with no calibration based on historical performance.

**The Fix (v20.4):**

1. Added `TOTALS_SIDE_CALIBRATION` to `core/scoring_contract.py`:
```python
TOTALS_SIDE_CALIBRATION = {
    "enabled": True,
    "over_penalty": -0.75,   # Penalty applied to OVER picks
    "under_boost": 0.75,     # Boost applied to UNDER picks
    "min_samples_required": 50,
    "last_updated": "2026-02-04",
}
```

2. Applied calibration in `live_data_router.py:4577-4592`:
   - When `pick_type == "TOTAL"`, check side
   - Apply over_penalty (-0.75) to Over picks
   - Apply under_boost (+0.75) to Under picks
   - Log adjustment for tracking

**Expected Outcome:**
- UNDER picks gain +0.75, more likely to win contradiction gate
- OVER picks penalized -0.75, less likely to be selected
- Learning loop should show improved total hit rates

**Verification:**
```bash
# Check OVER/UNDER split after next grading cycle
curl -s "/live/picks/grading-summary?date=$(date +%Y-%m-%d)" -H "X-API-Key: KEY" | jq '{
  over: {wins: [.graded_picks[] | select(.side == "Over" and .result == "WIN")] | length,
         losses: [.graded_picks[] | select(.side == "Over" and .result == "LOSS")] | length},
  under: {wins: [.graded_picks[] | select(.side == "Under" and .result == "WIN")] | length,
          losses: [.graded_picks[] | select(.side == "Under" and .result == "LOSS")] | length}
}'
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 39: Frontend Tooltip Alignment with Option A Weights (v20.4)

**Problem:** Frontend tooltips in `PropsSmashList.jsx` and `GameSmashList.jsx` showed incorrect engine weights that didn't match the backend `scoring_contract.py`:

| Engine | Frontend (Wrong) | Backend (Correct) |
|--------|------------------|-------------------|
| AI | 15% | **25%** |
| Research | 20% | **35%** |
| Esoteric | 15% | **20%** |
| Jarvis | 10% | **20%** |
| Context | 30% weighted | **±0.35 modifier** |

**Root Cause:** Frontend documentation and tooltips were written for an outdated scoring architecture. When Option A (4-engine base + context modifier) was implemented, the frontend wasn't updated to reflect that:
1. Context is NOT a weighted engine - it's a bounded modifier (±0.35 cap)
2. The 4 engine weights sum to 100% (25+35+20+20)
3. Context modifier is applied AFTER the weighted base score

**The Fix (v20.4):**

1. Updated `bookie-member-app/PropsSmashList.jsx` tooltips:
```jsx
// Option A: 4 weighted engines + context modifier
<ScoreBadge label="AI" tooltip="8 AI models (25% weight)" />
<ScoreBadge label="Research" tooltip="Sharp money, line variance (35% weight)" />
<ScoreBadge label="Esoteric" tooltip="Numerology, astro, fibonacci (20% weight)" />
<ScoreBadge label="Jarvis" tooltip="Gematria triggers (20% weight)" />
<ScoreBadge label="Context" tooltip="Defense rank, pace, vacuum (modifier ±0.35)" />
```

2. Updated `bookie-member-app/GameSmashList.jsx` with same corrections

3. Updated `bookie-member-app/CLAUDE.md` documentation in 3 sections

4. Updated `ai-betting-backend/docs/FRONTEND_INTEGRATION.md`:
   - Marked Priority 1-3 as COMPLETE
   - Fixed weight comments in API response structure

**Prevention:**
- ALWAYS check `core/scoring_contract.py` for authoritative weights
- When changing backend scoring, IMMEDIATELY update frontend tooltips
- Add drift scan for frontend/backend weight synchronization

**Files Modified:**
- `bookie-member-app/PropsSmashList.jsx`
- `bookie-member-app/GameSmashList.jsx`
- `bookie-member-app/CLAUDE.md`
- `ai-betting-backend/docs/FRONTEND_INTEGRATION.md`

**Verification:**
```bash
# Check frontend tooltips match backend weights
grep -n "25% weight\|35% weight\|20% weight\|modifier.*0.35" \
  /Users/apple/bookie-member-app/PropsSmashList.jsx \
  /Users/apple/bookie-member-app/GameSmashList.jsx

# Check backend scoring_contract.py for truth
grep -A5 "ENGINE_WEIGHTS" core/scoring_contract.py
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 40: Shell Variable Export for Python Subprocesses (v20.4)
**Problem:** `perf_audit_best_bets.sh` was trying to connect to `None` as a hostname:
```
curl: (6) Could not resolve host: None
```

**Root Cause:** Shell variables are NOT automatically inherited by Python subprocesses. The script set `BASE_URL` as a shell variable, but Python's `os.environ.get("BASE_URL")` returned `None`:

```bash
# BUG - Python subprocess doesn't see this variable
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"

# Inside Python heredoc:
base_url = os.environ.get("BASE_URL")  # Returns None!
```

**The Fix:**
```bash
# CORRECT - 'export' makes variable available to subprocesses
export BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
export API_KEY="${API_KEY:-}"
```

**Prevention:**
- When shell scripts call Python (via heredoc, subprocess, or exec), variables MUST be exported
- Use `export VAR=value` not just `VAR=value`
- Test scripts by checking what Python actually sees: `python3 -c "import os; print(os.environ.get('VAR'))"`

**Shell Variable Scope Rules:**
| Pattern | Scope | Python sees it? |
|---------|-------|-----------------|
| `VAR=value` | Current shell only | ❌ No |
| `export VAR=value` | Current shell + children | ✅ Yes |
| `VAR=value command` | Command only | ✅ Yes (for that command) |

**Files Modified:**
- `scripts/perf_audit_best_bets.sh` - Added `export` to BASE_URL and API_KEY

**Verification:**
```bash
# Test that Python inherits the variable
export TEST_VAR="hello"
python3 -c "import os; print(os.environ.get('TEST_VAR'))"
# Should print: hello
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 41: SHARP Pick Grading - line_variance vs Actual Spread (v20.5)
**Problem:** SHARP picks showing 0% hit rate across all sports (NBA 0/14, NHL 0/8, NCAAB 0/7).

**Root Cause:** SHARP picks were being graded incorrectly because the `line` field contained `line_variance` (the movement amount) instead of the actual spread:

```python
# In live_data_router.py - SHARP pick creation
"line": signal.get("line_variance", 0),  # BUG: This is 0.5, 1.5, etc.

# In result_fetcher.py - Grading logic treated it as spread
if line and line != 0:
    adjusted = home_score + line  # WRONG: using line_variance as spread
```

**Example of the bug:**
- Sharp signal: "sharps on Lakers" for Lakers (-5.5) vs Celtics
- `line_variance` = 1.5 (line moved 1.5 points)
- Pick logged with `"line": 1.5`
- Grading treated as "Lakers +1.5 spread"
- Lakers win by 4 → graded as WIN (should be LOSS, didn't cover -5.5)

**The Fix:** Grade SHARP picks as moneyline only (who won), ignoring the `line` field:

```python
# v20.5 fix in result_fetcher.py
elif "sharp" in pick_type_lower:
    # ALWAYS grade as moneyline - line field is line_variance, not actual spread
    if home_score == away_score:
        return "PUSH", 0.0
    if picked_home:
        return ("WIN" if home_score > away_score else "LOSS"), 0.0
    else:
        return ("WIN" if away_score > home_score else "LOSS"), 0.0
```

**Why moneyline is correct:**
- Sharp signals indicate "sharps are betting HOME/AWAY"
- Without the actual spread line, we can only grade on straight-up winner
- This is semantically accurate: "sharp side won" = their team won

**Prevention:**
- Never assume a field contains what its name suggests - trace data flow
- `line_variance` ≠ `line` (spread)
- Always verify grading logic with actual data examples

**Files Modified:**
- `result_fetcher.py` - Fixed `grade_game_pick()` SHARP case (lines 930-943)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 42: Undefined PYTZ_AVAILABLE Variable (v20.5)
**Problem:** `/grader/queue` endpoint returning `{"detail":"name 'PYTZ_AVAILABLE' is not defined"}`

**Root Cause:** Code referenced `PYTZ_AVAILABLE` variable that was never defined:
```python
if PYTZ_AVAILABLE:  # NameError - never defined!
    ET_TZ = pytz.timezone("America/New_York")
```

**The Fix:** Use `core.time_et.now_et()` - the single source of truth for ET timezone:
```python
from core.time_et import now_et
date = now_et().strftime("%Y-%m-%d")
```

**Prevention:**
- NEVER use `pytz` in new code - use `core.time_et` or `zoneinfo`
- NEVER reference variables without importing/defining them
- All ET timezone logic MUST go through `core.time_et`

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 43: Naive vs Aware Datetime Comparison (v20.5)
**Problem:** `/grader/daily-report` returning `{"detail":"can't compare offset-naive and offset-aware datetimes"}`

**Root Cause:** Comparing `datetime.now()` (naive) with stored timestamps that may be timezone-aware:
```python
cutoff = datetime.now() - timedelta(days=1)  # Naive
ts = datetime.fromisoformat(p.timestamp)      # May be aware
if ts >= cutoff:  # TypeError!
```

**The Fix:** Use timezone-aware datetime and handle both naive/aware timestamps:
```python
from core.time_et import now_et
from zoneinfo import ZoneInfo
et_tz = ZoneInfo("America/New_York")

cutoff = now_et() - timedelta(days=1)  # Aware

ts = datetime.fromisoformat(p.timestamp)
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=et_tz)  # Make aware if naive
if ts >= cutoff:  # Safe comparison
```

**Prevention:**
- NEVER use `datetime.now()` in grader code - use `now_et()`
- ALWAYS handle both naive and aware timestamps when parsing stored data
- Test with both timezone-aware and naive timestamp data

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 44: Date Window Math Error (v20.5)
**Problem:** Daily report showing ~290 picks for "yesterday" when actual count was ~150

**Root Cause:** Wrong date window calculation created 2-day window instead of 1:
```python
# For days_back=1 (yesterday), this creates a 2-day window:
cutoff = now - timedelta(days=days_back + 1)      # 2 days ago (WRONG)
end_cutoff = now - timedelta(days=days_back - 1)  # today
```

**The Fix:** Use exact day boundaries:
```python
# Correct: exactly one day
day_start = (now - timedelta(days=days_back)).replace(
    hour=0, minute=0, second=0, microsecond=0
)
day_end = day_start + timedelta(days=1)

if day_start <= ts < day_end:  # Exclusive end bound
```

**Prevention:**
- NEVER use `days_back + 1` / `days_back - 1` math for date windows
- ALWAYS use `.replace(hour=0, ...)` for day boundaries
- Use exclusive end bounds (`<` not `<=`) to avoid overlap
- Test date window logic with specific date examples

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 45: Grader Performance Endpoint Same Bug (v20.5)
**Problem:** `/grader/performance/{sport}` returning `Internal Server Error`

**Root Cause:** Same naive vs aware datetime bug as Lesson 43 - copy-paste pattern:
```python
cutoff = datetime.now() - timedelta(days=days_back)
datetime.fromisoformat(p.timestamp) >= cutoff  # Same error
```

**The Fix:** Apply same fix as Lesson 43 - use `now_et()` and handle mixed timestamps.

**Prevention:**
- When fixing a bug, grep the entire codebase for the same pattern
- `/grader/daily-report` and `/grader/performance` had identical bugs
- Run `grep -n "datetime.now()" *.py | grep fromisoformat` after datetime fixes

**Files Modified (v20.5 datetime fixes):**
- `live_data_router.py` lines 8933-8944 (performance endpoint)
- `live_data_router.py` lines 9016-9058 (daily-report endpoint)
- `live_data_router.py` lines 9210-9215 (queue endpoint)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 46: Unsurfaced Scoring Adjustments Break Sanity Math (v20.5)
**Problem:** `endpoint_matrix_sanity.sh` math check showed diff=0.748 because `totals_calibration_adj` (±0.75) was applied to `final_score` but NOT surfaced as a field in the pick payload.

**Root Cause:** `TOTALS_SIDE_CALIBRATION` (v20.4) adjusted `final_score` directly via a local variable `totals_calibration_adj`, but this value was never included in the pick output dict. The sanity script recomputes `final_score` from surfaced fields, so the hidden adjustment caused a mismatch.

**The Fix:**
1. Added `"totals_calibration_adj": round(totals_calibration_adj, 3)` to pick output dict in `live_data_router.py`
2. Updated jq formula in `endpoint_matrix_sanity.sh` to include `+ ($p.totals_calibration_adj // 0)`

**Prevention:**
- **INVARIANT:** Every adjustment to `final_score` MUST be surfaced as its own field in the pick payload
- When adding a new scoring adjustment: (1) add to pick dict, (2) add to sanity formula, (3) add to CLAUDE.md Boost Inventory, (4) add to canonical formula
- The endpoint matrix math check exists precisely to catch this class of bug

**Files Modified:**
- `live_data_router.py` (pick output dict)
- `scripts/endpoint_matrix_sanity.sh` (jq formula)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 47: Script-Only Env Vars Must Be in RUNTIME_ENV_VARS (v20.5)
**Problem:** `env_drift_scan.sh` failed because `MAX_GAMES`, `MAX_PROPS`, and `RUNS` were used in scripts but not registered in `RUNTIME_ENV_VARS` in `integration_registry.py`.

**Root Cause:** The env drift scan greps all `.sh` and `.py` files for `os.environ` / `${}` references, then checks them against the `RUNTIME_ENV_VARS` list. Script-only variables were not registered because they seemed "not important enough."

**The Fix:** Added `MAX_GAMES`, `MAX_PROPS`, and `RUNS` to `RUNTIME_ENV_VARS` in `integration_registry.py` in alphabetical position.

**Prevention:**
- ANY env var referenced in ANY script or Python file must be in either `INTEGRATION_CONTRACTS` or `RUNTIME_ENV_VARS`
- Run `bash scripts/env_drift_scan.sh` after adding new env vars to scripts
- The scan is intentionally aggressive - false positives are better than missed drift

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 48: Python Heredoc `__file__` Path Resolution Bug (v20.5)
**Problem:** `prod_endpoint_matrix.sh` failed with `FileNotFoundError: [Errno 2] No such file or directory: '../docs/ENDPOINT_MATRIX_REPORT.md'`

**Root Cause:** The script uses `python3 - <<'PY'` (Python heredoc). Inside a heredoc, `__file__` resolves to `"<stdin>"`, so `os.path.dirname(__file__)` returns an empty string. The path `os.path.join("", "..", "docs", "ENDPOINT_MATRIX_REPORT.md")` resolved to `../docs/ENDPOINT_MATRIX_REPORT.md` which doesn't exist.

**The Fix:** Changed to project-relative path: `os.path.join("docs", "ENDPOINT_MATRIX_REPORT.md")` - works because the shell script runs from the project root.

**Prevention:**
- NEVER use `__file__`, `__dir__`, or `os.path.dirname(__file__)` inside Python heredocs
- In heredocs, use project-relative paths (scripts always run from project root)
- Test heredoc scripts directly: `bash scripts/script_name.sh`

**Files Modified:**
- `scripts/prod_endpoint_matrix.sh` (line 86)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 49: Props Timeout — Shared Time Budget Starvation (v20.6)
**Problem:** `/live/best-bets/NBA` returned 0 props despite game picks working. Props section showed `"picks": []`.

**Root Cause:** `TIME_BUDGET_S = 40.0` was hardcoded in `live_data_router.py:2741`. Game scoring consumed the full budget, leaving 0 seconds for props scoring. The timeout wasn't configurable.

**The Fix:**
1. Changed `TIME_BUDGET_S` from hardcoded `40.0` to `float(os.getenv("BEST_BETS_TIME_BUDGET_S", "55"))` — configurable with higher default
2. Registered `BEST_BETS_TIME_BUDGET_S` in `integration_registry.py` `RUNTIME_ENV_VARS`

**Prevention:**
- Any shared time budget must leave enough headroom for ALL consumers (games + props)
- All timeout/budget values should be env-configurable, not hardcoded
- Always register new env vars in `integration_registry.py` (see Lesson 47)

**Files Modified:**
- `live_data_router.py` (line 2741)
- `integration_registry.py` (RUNTIME_ENV_VARS)

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 50: Empty Description Fields in Pick Payload (v20.6)
**Problem:** All picks returned `"description": ""` in the best-bets response. Frontend had no human-readable summary of each pick.

**Root Cause:** `compute_description()` existed in `models/pick_converter.py` but it used object attribute access (`.player_name`, `.matchup`) — only works for database model objects. The live scoring path uses plain dicts through `normalize_pick()`, so `compute_description()` was never called.

**The Fix:** Added dict-based description generation directly in `utils/pick_normalizer.py` `normalize_pick()`, covering:
- Player props: `"LeBron James Points Over 25.5"`
- Moneyline: `"LAL @ BOS — Lakers ML +150"`
- Spreads/totals: `"LAL @ BOS — Spread Away -3.5"`
- Fallback: matchup string

**Prevention:**
- When adding a new field to the pick contract, verify it's populated in ALL paths (normalize_pick is the single source)
- `normalize_pick()` is the ONLY place to set pick fields — never set them in individual scoring functions

**Files Modified:**
- `utils/pick_normalizer.py` (added ~15 lines in normalize_pick)

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 51: Score Inflation from Unbounded Boost Stacking (v20.6)
**Problem:** Multiple picks had `final_score = 10.0` despite mediocre base scores (~6.5). Picks clustered at the max, eliminating score differentiation.

**Root Cause:** Individual boost caps existed (confluence 10.0, msrf 1.0, jason_sim 1.5, serp 4.3) but NO cap on their SUM. Theoretical max boost was 16.8 points. In practice, confluence 3.0 + msrf 1.0 + serp 2.0 + jason 0.5 = 6.5 boosts on a 6.5 base = 13.0 → clamped to 10.0.

**The Fix:**
1. Added `TOTAL_BOOST_CAP = 1.5` in `core/scoring_contract.py`
2. In `compute_final_score_option_a()`: sum of confluence+msrf+jason_sim+serp capped to `TOTAL_BOOST_CAP` before adding to base_score
3. Context modifier is excluded from the cap (it's a bounded modifier, not a boost)
4. Updated `test_option_a_scoring_guard.py` to test new cap behavior

**Prevention:**
- Every additive boost system needs BOTH individual caps AND a total cap
- Monitor production score distributions — clustering at boundaries is a red flag
- Added Invariant 26 to prevent regression

**Files Modified:**
- `core/scoring_contract.py` (TOTAL_BOOST_CAP constant)
- `core/scoring_pipeline.py` (cap enforcement in compute_final_score_option_a)
- `tests/test_option_a_scoring_guard.py` (updated tests for new cap)

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 52: Jarvis Baseline Is Not a Bug — Sacred Triggers Are Rare By Design (v20.6)
**Problem:** Report claimed `jarvis_score = 5.0` hardcoded at `core/scoring_pipeline.py:280` made Jarvis "dead code."

**Investigation Found:** The hardcoded 5.0 is in `score_candidate()` which is dormant demo code — NOT the production path. Production Jarvis scoring is in `live_data_router.py:calculate_jarvis_engine_score()` (lines 2819-3037), fully wired with real triggers.

**Why Jarvis Stays at 4.5 Baseline:**
- Sacred number triggers (2178, 201, 33, 93, 322, 666, 888, 369) fire on gematria sums of player+team names
- Simple gematria (a=1..z=26) produces sums typically in the 100-400 range
- Sacred numbers are statistically rare — most matchups don't trigger ANY
- This is intentional: Jarvis should ONLY boost when genuine sacred number alignment exists
- GOLD_STAR gate requires `jarvis_rs >= 6.5` — needs at minimum a +2.0 trigger (33, 93, or 322)

**Prevention:**
- Before reporting "dead code," trace the actual production call path (imports, function calls)
- `core/scoring_pipeline.py:score_candidate()` is NOT used in production — only `compute_final_score_option_a()` and `compute_harmonic_boost()` are imported
- A low/constant score from an engine is not necessarily a bug — check if triggers are designed to be rare

**Production Jarvis flow:**
```
get_jarvis_savant() → JarvisSavantEngine singleton
  → calculate_jarvis_engine_score()
    ├── check_jarvis_trigger() for sacred numbers
    ├── calculate_gematria_signal() for name sums
    └── mid-spread goldilocks for spreads 4.0-9.0
  → jarvis_rs = 4.5 + triggers + gematria + goldilocks
```

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 53: SERP Sequential Bottleneck — Parallel Pre-Fetch Pattern (v20.7)
**Problem:** Props scoring returned 0 picks despite v20.6 timeout fix. Deep dive revealed 107 sequential SerpAPI calls at ~157ms each = ~17s, consuming half the game scoring budget and leaving no time for props.

**Root Cause:** `get_serp_betting_intelligence()` makes 9 API calls per game pick (silent_spike×1, sharp_chatter×2, narrative×2, situational×2, noosphere×2). For 8 games with both home and away targets, that's ~14 unique queries per game × 8 games = ~107 calls. Each call goes through `serpapi.py` with ~157ms average latency. All sequential.

**The Sequential Bottleneck Pattern:**
```python
# ❌ BAD - Sequential SERP calls inside scoring loop (~17s total)
for pick in game_picks:
    serp_intel = get_serp_betting_intelligence(sport, home, away, pick_side)
    # Each call: 9 sequential API requests × ~157ms = ~1.4s per pick
    # 12 picks × 1.4s = ~17s total
```

**Solution (v20.7 — Parallel Pre-Fetch Pattern):**
```python
# ✅ GOOD - Pre-fetch all SERP data in parallel before scoring loop (~2-3s)
# Step 1: Extract unique (home, away) pairs from all games
_unique_serp_games = {(g["home_team"], g["away_team"]) for g in raw_games + prop_games}

# Step 2: Pre-fetch both targets (home, away) per game in parallel
with ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(_prefetch_serp_game, h, a, target)
               for h, a in _unique_serp_games
               for target in [h, a]]  # Both home and away as target
    results = wait_for(gather(*futures), timeout=12.0)

# Step 3: Store in cache dict, accessed by scoring function via closure
_serp_game_cache[(home_lower, away_lower, target_lower)] = result

# Step 4: In calculate_pick_score(), check cache before live call
if _serp_cache_key in _serp_game_cache:
    serp_intel = _serp_game_cache[_serp_cache_key]  # Cache hit: ~0ms
else:
    serp_intel = get_serp_betting_intelligence(...)  # Fallback: ~1.4s
```

**Key Design Decisions:**
| Decision | Why |
|----------|-----|
| `ThreadPoolExecutor` + `run_in_executor` | SERP calls are synchronous (requests lib); threads avoid blocking async loop |
| 16 workers max | ~16 unique game-target pairs for 8 games; 1 thread per task |
| 12s timeout on entire batch | Hard ceiling prevents runaway parallel calls |
| Cache key = `(home_lower, away_lower, target_lower)` | Mirrors `serp_intelligence.py:602` target_team selection logic |
| Props NOT pre-fetched | Per-player data too many unique combinations; benefit from warm serpapi cache |
| Closure-scoped `_serp_game_cache` | Available to nested `calculate_pick_score()` without parameter threading |

**Performance Impact:**
| Metric | Before (v20.6) | After (v20.7) | Improvement |
|--------|----------------|---------------|-------------|
| SERP total time | ~17s sequential | ~2-3s parallel | **~6x faster** |
| Game scoring | ~35-46s | ~20-30s (expected) | Time freed for props |
| Props scoring | 0 picks (timeout) | Should complete | **Props restored** |

**Debug Telemetry Added:**
```json
{
  "debug": {
    "serp": {
      "prefetch_cached": 16,   // Results successfully pre-fetched
      "prefetch_games": 8      // Unique game pairs cached
    },
    "timings": {
      "serp_prefetch": 2.3     // Seconds for parallel pre-fetch
    }
  }
}
```

**Files Modified:**
- `live_data_router.py:5851-5927` — SERP pre-fetch block (after player resolution, before scoring loop)
- `live_data_router.py:4431-4442` — Cache lookup in `calculate_pick_score()` for game bets
- `live_data_router.py:7229-7230` — Debug telemetry (`prefetch_cached`, `prefetch_games`)

**Prevention:**
- When an external API is called N times sequentially in a loop, consider parallel pre-fetching
- Always measure actual API call counts and latencies before assuming "it's fast enough"
- The 90-minute `serpapi.py` cache helps for repeated queries but doesn't help when ALL queries are unique
- Pre-fetch tasks should have a hard timeout to prevent blocking the main budget
- Always add debug telemetry for pre-fetch results so performance can be monitored

**The General Pre-Fetch Pattern (for future similar bottlenecks):**
1. **Identify** the sequential bottleneck: grep for API calls inside scoring loops
2. **Extract** unique inputs from all candidates before the loop starts
3. **Parallelize** using `ThreadPoolExecutor` + `asyncio.run_in_executor()`
4. **Cache** results in a closure-scoped dict with deterministic keys
5. **Fallback** gracefully to live calls on cache miss or timeout
6. **Telemetry** via `_record()` and debug output fields

**Fixed in:** v20.7 (Feb 5, 2026)

### Lesson 54: Props Indentation Bug — Dead Code from Misplaced Break (v20.8)
**Problem:** ALL sports (NBA, NHL, NFL, MLB, NCAAB) returned 0 props despite game picks working correctly. Props were scored but never collected into the output.

**Root Cause:** `if _props_deadline_hit: break` was positioned at game-loop indentation level (12 spaces) BETWEEN `calculate_pick_score()` and all prop processing code (16 spaces). Due to Python's indentation-sensitive scoping:

```python
# BUG — Lines 6499-6506 (before fix):
                    game_status=_prop_game_status
                )
            if _props_deadline_hit:       # ← 12-space indent (game loop level)
                break

                # Lineup confirmation guard (props only)   # ← 16-space indent
                lineup_guard = _lineup_risk_guard(...)      #    INSIDE the if block
                ...
                props_picks.append({...})                   #    ALSO INSIDE — UNREACHABLE
```

**How Python interpreted this:**
- When `_props_deadline_hit = True`: `break` executes, everything after is unreachable
- When `_props_deadline_hit = False`: the entire `if` block is skipped — BUT all code at 16-space indent was INSIDE the `if` block, so it was ALSO skipped
- Result: `props_picks.append(...)` at line 6596 NEVER executes regardless of the flag's value

**The Fix:**
1. Removed `if _props_deadline_hit: break` from between `calculate_pick_score()` and prop processing (line 6502)
2. Added `if _props_deadline_hit: break` AFTER `props_picks.append({...})` completes (line 6662)

```python
# FIXED — Each prop is fully processed before deadline check:
                    game_status=_prop_game_status
                )

                # Lineup confirmation guard (props only)
                lineup_guard = _lineup_risk_guard(...)
                ...
                props_picks.append({...})
            if _props_deadline_hit:
                break
```

**Why This Was Hard to Find:**
- No errors, no crashes, no stack traces — the code simply never reached `append()`
- Props status showed "OK" (scoring succeeded), but count was always 0
- The bug was invisible in normal test output because Python's indentation scoping made the dead code syntactically valid
- A 4-character indentation difference (12 vs 16 spaces) determined whether 160+ lines of code executed

**Prevention:**
1. **NEVER place control flow (`if/break/continue/return`) between a function call and the code that uses its result** — especially in deeply nested loops
2. **When moving `break` statements, verify the indentation level matches the loop you intend to break from** — Python treats indentation as scope
3. **After any edit near loop control flow, read the surrounding 50+ lines** to verify the intended scope isn't broken
4. **If props return 0 picks but game picks work**, the first thing to check is the prop scoring loop's control flow — not timeouts, not data sources
5. **Add integration tests that verify `props.count > 0`** when test data is available — a structural invariant test would have caught this immediately

**Files Modified:**
- `live_data_router.py` — 2 edits: remove misplaced break (line 6502), add break after append (line 6662)

**Verification:**
```bash
# 1. Syntax check
python3 -m py_compile live_data_router.py

# 2. Scoring guard tests
python3 -m pytest tests/test_option_a_scoring_guard.py -q

# 3. Option A drift scan
bash scripts/option_a_drift_scan.sh

# 4. Verify props return picks in production
curl /live/best-bets/NBA -H "X-API-Key: KEY" | jq '.props.count'
# Should be > 0 when today's games exist

# 5. Check all sports
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, props: .props.count, games: .game_picks.count}'
done
```

**Impact:** This was the root cause of the "props not pulling across sports" issue. Every sport (NBA, NHL, NFL, MLB, NCAAB) was affected since the bug was in the shared props scoring loop in `_best_bets_inner()`.

**Fixed in:** v20.8 (Feb 5, 2026)

### SERP Props Quota Optimization Note (v20.9 Addendum to Lesson 53)
**Problem:** SERP daily quota (166/day) exhausted by a single best-bets request (~291 calls). Props alone consume ~220 calls (60% of budget) with near-zero cache hit rate because each player query is unique. When quota exhausts, SERP pre-fetch for game picks is disabled, causing game scoring to revert to sequential SERP (51s of 55s budget), and props time out entirely.

**Production Data (Feb 5, 2026):**
- NBA: 3/55 props analyzed (TIMED_OUT)
- NHL: 0/59 props analyzed (TIMED_OUT)
- SERP: daily_used=176, daily_limit=166, daily_remaining=-10
- Pre-fetch skipped (quota exhausted)

**Root Cause:** Per-prop SERP calls are unique per player (cache miss rate ~100%), while game SERP queries repeat across picks for the same game (high cache hit rate). Props get moderate boost impact (research cap 0.5, esoteric cap 0.6) vs game signals (sharp chatter 1.3, narrative 0.7).

**Solution (v20.9):**
1. Added `SERP_PROPS_ENABLED` env var in `core/serp_guardrails.py` (default: `False`)
2. When disabled, props skip SERP entirely with `serp_status = "SKIPPED_PROPS"`
3. Props still benefit from LSTM, context layer, GLITCH, Phase 8, and all other signals
4. Game SERP signals remain active (high cache hit rate, higher impact)
5. Re-enable with `SERP_PROPS_ENABLED=true` without code changes

**Expected Impact:**
| Metric | Before | After |
|--------|--------|-------|
| SERP daily calls | ~291 (exceeds 166 quota) | ~72 (within quota) |
| Props completed | 3/55 NBA, 0/59 NHL | Full completion within budget |
| Game pre-fetch | Disabled (quota exhausted) | Active (quota available) |

**Prevention:**
- Monitor SERP quota via `debug.serp.status.quota.daily_remaining`
- Check `get_serp_status()["props_enabled"]` in debug output
- If re-enabling props SERP, ensure daily quota is increased first

**Files Modified:**
- `core/serp_guardrails.py` - Added `SERP_PROPS_ENABLED` config + status reporting
- `live_data_router.py` - Skip SERP for props when disabled
- `integration_registry.py` - Documented `SERP_PROPS_ENABLED` in serpapi notes

**Fixed in:** v20.9 (Feb 2026)

### Lesson 55: Missing GET Endpoint — Frontend Calling Non-Existent Backend Route (v20.9)
**Problem:** Frontend `Grading.jsx` called `GET /live/picks/graded` but the backend had no such endpoint. The backend only had `POST /live/picks/grade` (grade a pick) and `GET /live/picks/grading-summary` (stats). The missing GET endpoint caused the frontend to fall back to hardcoded MOCK_PICKS, making the Grading page show fake data instead of real picks.

**Root Cause:** The frontend `api.js` was written with `getGradedPicks()` calling `GET /live/picks/graded`, but the backend endpoint was never implemented. The frontend silently fell back to MOCK_PICKS on the 404 error, masking the problem completely — no error shown to users, no console warnings, just fake data displayed as if it were real.

**The Fix:**
1. Added `GET /picks/graded` endpoint to `live_data_router.py` using `grader_store.load_predictions()` with grade records merged
2. Maps internal pick fields to frontend format: `id`, `pick_id`, `player`, `team`, `opponent`, `stat`, `line`, `recommendation`, `graded` (boolean), `result`, `actual`
3. Supports `?date=` and `?sport=` query params, defaults to today ET
4. Updated `Grading.jsx`: removed MOCK_PICKS fallback, fixed `pick_id` usage for grade calls, handled game picks alongside props
5. Added try-catch to `api.getGradedPicks()` (Invariant 11)

**Why This Was Hard to Find:**
- No errors, no crashes — frontend had a MOCK_PICKS fallback that silently activated
- The page looked functional with mock data, so the broken backend connection was invisible
- The similar endpoint names (`/picks/grade` POST vs `/picks/graded` GET) made it easy to assume the GET existed

**Prevention:**
1. **NEVER add a frontend API method without verifying the backend endpoint exists** — check `live_data_router.py` for the route before writing `api.js` methods
2. **NEVER use mock/fallback data that looks like real data** — fallbacks should show an empty state or error banner, not realistic fake picks that mask broken connections
3. **When adding a new GET endpoint, add it to the same section as related POST endpoints** — keeps the contract discoverable
4. **Add backend endpoint existence checks to the frontend CI** — the `verify-backend.sh` pre-commit hook should validate all `api.js` endpoints exist

**Files Modified:**
- `live_data_router.py` — Added `GET /picks/graded` endpoint (grader_store integration)
- `bookie-member-app/Grading.jsx` — Removed MOCK_PICKS, fixed pick_id, improved pick rendering
- `bookie-member-app/api.js` — Added try-catch to `getGradedPicks()`

**Fixed in:** v20.9 (Feb 5, 2026)

### Lesson 56: SHARP Signal Field Name Mismatch — Wrong Team Graded (v20.10)
**Problem:** SHARP picks showed 18% hit rate (2W-9L) with all picks showing `actual: 0.0`. Sharp money signals were always being graded as HOME team wins regardless of the actual sharp side.

**Root Cause:** The SHARP signal dictionary uses `sharp_side` field with lowercase values ("home" or "away"), but the pick creation code used `signal.get("side", "HOME")` which always returned the default "HOME" since the `side` field doesn't exist in the signal.

```python
# BUG — signal has "sharp_side", not "side"
sharp_side = "home" if money_pct > ticket_pct else "away"  # Line 1924
data.append({
    "sharp_side": sharp_side,  # The actual field name
    ...
})

# Pick creation used wrong field name
"side": home_team if signal.get("side") == "HOME" else away_team  # Line 6326
# signal.get("side") returns None, defaults to "HOME"
# So ALL picks get side=home_team regardless of actual sharp_side
```

**The Fix:** Changed all `signal.get("side", "HOME")` to `signal.get("sharp_side", "home")` and updated comparisons from uppercase "HOME" to lowercase "home":
- Lines 6286, 6314: `pick_side=signal.get("sharp_side", "home")`
- Lines 6324-6327: Use `signal.get("sharp_side")` with lowercase comparison
- Line 6347: `signal.get('sharp_side', 'home').upper()`

**Impact:** Before fix, ~50% of SHARP picks were graded against the wrong team (when sharps actually bet AWAY, pick was graded as if they bet HOME).

**Prevention:**
1. **NEVER assume field names** — always trace back to where the data dictionary is created
2. **Field name consistency** — if data source uses `sharp_side`, consuming code must also use `sharp_side`
3. **Beware of silent defaults** — `signal.get("side", "HOME")` returning "HOME" masked the bug because HOME is a valid value
4. **Unit test SHARP grading** with both HOME and AWAY scenarios

**Files Modified:**
- `live_data_router.py` — Fixed 7 occurrences of `signal.get("side")` to `signal.get("sharp_side")`

**Fixed in:** v20.10 (Feb 8, 2026)

### Lesson 57: NOAA Space Weather — Replace Simulation with Real API (v20.11)
**Problem:** `signals/physics.py:get_kp_index()` used time-based simulation instead of real Kp-Index data from NOAA Space Weather API.

**Root Cause:** The function was a placeholder simulation (time-modulated fake values 0-9) even though `alt_data_sources/noaa.py` had a fully working `fetch_kp_index_live()` implementation that was never called.

**The Fix:**
```python
# signals/physics.py - Now calls real NOAA API
from alt_data_sources.noaa import get_kp_betting_signal, NOAA_ENABLED

def get_kp_index(game_time: datetime = None) -> Dict[str, Any]:
    if USE_REAL_NOAA and NOAA_ENABLED:
        try:
            return get_kp_betting_signal(game_time)  # Real NOAA data
        except Exception as e:
            logger.warning("NOAA API call failed, using simulation: %s", e)
    # Fallback to simulation if disabled or API fails
```

**Key Design Decisions:**
- `USE_REAL_NOAA` env var (default: true) for gradual rollout
- Graceful fallback to simulation on API error
- 3-hour cache in `noaa.py` (Kp updates every 3 hours)

**Prevention:**
1. **NEVER leave working API integrations uncalled** — if the module exists and works, wire it in
2. **Always add feature flags** for new external API calls (gradual rollout)
3. **Always add fallback** for external APIs that may fail

**Files Modified:**
- `signals/physics.py` — Updated `get_kp_index()` to call NOAA API

**Verification:**
```bash
# Check NOAA Kp-Index source in debug output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.glitch_breakdown.kp_index.source'
# Should show "noaa_live" when API working, "fallback" on error, "disabled" if NOAA_ENABLED=false
```

**Fixed in:** v20.11 (Feb 8, 2026)

### Lesson 58: Live Game Signals — ESPN Scoreboard Integration (v20.11)
**Problem:** `live_data_router.py` hardcoded `home_score=0, away_score=0, period=1` for in-game adjustments instead of using actual live scores from ESPN.

**Root Cause:** The ESPN scoreboard was being fetched but never parsed to extract live game data. The live signals section used placeholder values.

**The Fix:**
```python
# live_data_router.py - Build live scores lookup from ESPN scoreboard
_live_scores_by_teams = {}
if espn_scoreboard and isinstance(espn_scoreboard, dict):
    for event in espn_scoreboard.get("events", []):
        # Extract competitors, scores, period, status
        key = (_normalize_team_name(home_team), _normalize_team_name(away_team))
        _live_scores_by_teams[key] = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "status": game_status,
        }

# In calculate_pick_score() - Use real scores instead of hardcoded values
_live_data = _find_espn_data(_live_scores_by_teams, home_team, away_team)
if _live_data:
    _home_score = _live_data.get("home_score", 0)
    _away_score = _live_data.get("away_score", 0)
    _period = _live_data.get("period", 1)
```

**Key Design Decisions:**
- Scores extracted during parallel fetch phase (no additional API calls in scoring loop)
- Team name normalization for matching (handles case and accent differences)
- Graceful fallback to 0-0 if ESPN data unavailable

**Prevention:**
1. **NEVER hardcode live data values** when the data source is already being fetched
2. **Extract data during fetch phase**, not inside scoring loop
3. **Normalize team names** for reliable lookups

**Files Modified:**
- `live_data_router.py` — Added `_live_scores_by_teams` lookup and score extraction

**Verification:**
```bash
# Check live adjustment in debug output (during live games)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[] | select(.game_status == "LIVE") | {live_adjustment, live_score_diff}]'
# live_adjustment should be non-zero when score differential is significant
```

**Fixed in:** v20.11 (Feb 8, 2026)

### Lesson 59: Void Moon — Improved Lunar Calculation (v20.11)
**Problem:** `signals/hive_mind.py:get_void_moon()` used a simplified 27.3-day cycle approximation that was inaccurate for precise void-of-course detection.

**Root Cause:** The original calculation used a simple linear formula based on sidereal month (27.3 days), ignoring synodic month (29.53 days) and lunar orbit perturbations (~6.3° variation).

**The Fix:**
```python
# signals/hive_mind.py - Meeus-based lunar ephemeris
SYNODIC_MONTH = 29.53059  # More accurate than 27.3 sidereal
MEEUS_EPOCH = datetime(2000, 1, 6, 18, 14, 0, tzinfo=timezone.utc)
PERTURBATION_AMPLITUDE = 6.289  # Main lunar perturbation (degrees)

def _calculate_moon_longitude(dt: datetime) -> float:
    """Calculate ecliptic longitude using Meeus method with perturbation."""
    days_since_epoch = (dt - MEEUS_EPOCH).total_seconds() / 86400.0
    # Mean longitude + main perturbation term
    mean_longitude = (218.3165 + 13.176396 * days_since_epoch) % 360
    # Add perturbation correction (simplified Meeus)
    M = (134.963 + 13.064993 * days_since_epoch) % 360
    correction = PERTURBATION_AMPLITUDE * math.sin(math.radians(M))
    return (mean_longitude + correction) % 360

def _is_void_of_course(longitude: float) -> Tuple[bool, float]:
    """VOC when moon in last 3 degrees of sign (more conservative)."""
    sign_position = longitude % 30
    if sign_position >= 27:  # Last 3 degrees = VOC
        return True, (30 - sign_position) / 30  # Confidence 0-1
    return False, 0.0
```

**Key Design Decisions:**
- Synodic month (29.53d) more accurate for phase calculations than sidereal (27.3d)
- Main perturbation term improves accuracy by ~6 degrees
- Last 3 degrees of sign for VOC (more conservative than last 1 degree)
- Optional `ASTRONOMY_API_ID` env var for future paid API integration

**Prevention:**
1. **Use proper astronomical formulas** for celestial calculations (Meeus algorithm)
2. **Include perturbation terms** for lunar calculations (moon orbit is complex)
3. **Be conservative** with esoteric signals (better to miss than false trigger)

**Files Modified:**
- `signals/hive_mind.py` — Improved `get_void_moon()` with Meeus calculation

**Verification:**
```bash
# Check void moon calculation in debug output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.esoteric.void_moon | {is_void, confidence, method}'
# method should show "meeus_local" (improved calculation)
```

**Fixed in:** v20.11 (Feb 8, 2026)

### Lesson 60: LSTM Real Training Data — Playbook API Integration (v20.11)
**Problem:** `lstm_training_pipeline.py` had a TODO at line 478 and always used synthetic data, even though `fetch_player_games()` was fully implemented at lines 141-179.

**Root Cause:** The `build_training_data_real()` method that should call `fetch_player_games()` was never implemented. The training pipeline always fell through to `SyntheticDataGenerator.generate_training_data()`.

**The Fix:**
```python
# lstm_training_pipeline.py - New build_training_data_real() method
@classmethod
def build_training_data_real(
    cls,
    sport: str,
    stat_type: str,
    max_players: int = 100,
    min_games: int = 20
) -> Tuple[np.ndarray, np.ndarray]:
    """Build training data from real Playbook API game logs."""
    STAT_FIELD_MAP = {
        "points": "points", "rebounds": "rebounds", "assists": "assists",
        "threes": "threePointersMade", "passing_yards": "passingYards", ...
    }
    # Fetch players, get game logs, build 15-game sequences
    X_sequences, y_targets = [], []
    for player in fetch_players(sport, limit=max_players):
        games = fetch_player_games(player_id, sport, limit=50)
        # Build sliding window sequences...
    return np.array(X_sequences), np.array(y_targets)

# train_sport() - Try real data first, fallback to synthetic
if not use_synthetic:
    X, y = HistoricalDataFetcher.build_training_data_real(sport, stat_type, ...)
    if len(X) >= TrainingConfig.MIN_SAMPLES_PER_SPORT:  # 500
        data_source = "real_playbook"
if len(X) < TrainingConfig.MIN_SAMPLES_PER_SPORT:
    data_source = "synthetic"
    X, y = SyntheticDataGenerator.generate_training_data(sport, stat_type)
```

**Key Design Decisions:**
- `MIN_SAMPLES_PER_SPORT = 500` threshold for using real data
- Graceful fallback to synthetic if real data insufficient
- `data_source` field in training results for tracking
- 15-game sequence windows with 6 features per game

**Prevention:**
1. **NEVER leave working fetch methods uncalled** — if data fetching is implemented, wire it into the pipeline
2. **Always add fallback** for external data sources (API may return insufficient data)
3. **Track data source** in results for debugging and quality monitoring

**Files Modified:**
- `lstm_training_pipeline.py` — Added `build_training_data_real()`, updated `train_sport()` to try real data first

**Verification:**
```bash
# Check LSTM training data source in logs
# After retrain (Sundays 4AM ET), check:
curl /live/ml/status -H "X-API-Key: KEY" | jq '.lstm.training_info'
# data_source should show "real_playbook" when API data available
```

**Fixed in:** v20.11 (Feb 8, 2026)

### Lesson 61: Comprehensive Rivalry Database Expansion (v20.11)
**Problem:** `MAJOR_RIVALRIES` in `esoteric_engine.py` only covered ~50 popular matchups. User requirement: "Every team has a rivalry in each sport — grab them all."

**Root Cause:** Original database was written for "popular" rivalries only (Lakers-Celtics, Yankees-Red Sox), leaving most teams without rivalry detection. Mid-market and newer teams (Kraken, Golden Knights, Utah Jazz) had no entries.

**The Fix:**
```python
# esoteric_engine.py lines 1583-1653 — Comprehensive coverage
MAJOR_RIVALRIES = {
    "NBA": [  # 35 rivalries covering all 30 teams
        ({"celtics", "boston"}, {"lakers", "los angeles lakers"}, "HIGH"),
        ({"celtics", "boston"}, {"sixers", "76ers", "philadelphia"}, "HIGH"),
        # ... divisional + historic rivalries
    ],
    "NFL": [  # 46 rivalries covering all 32 teams
        ({"bills", "buffalo"}, {"dolphins", "miami"}, "HIGH"),
        ({"packers", "green bay"}, {"bears", "chicago"}, "HIGH"),
        # ... all divisional matchups
    ],
    "NHL": [  # 36 rivalries including newest teams
        ({"bruins", "boston"}, {"canadiens", "montreal"}, "HIGH"),
        ({"kraken", "seattle"}, {"canucks", "vancouver"}, "MEDIUM"),
        ({"golden knights", "vegas"}, {"sharks", "san jose"}, "HIGH"),
        # ... Original Six + expansion teams
    ],
    "MLB": [  # 36 rivalries + interleague
        ({"yankees", "new york yankees"}, {"red sox", "boston"}, "HIGH"),
        ({"cubs", "chicago cubs"}, {"cardinals", "st louis"}, "HIGH"),
        # ... divisional + crosstown
    ],
    "NCAAB": [  # 51 rivalries for major programs
        ({"duke", "blue devils"}, {"north carolina", "tar heels", "unc"}, "HIGH"),
        ({"kentucky", "wildcats"}, {"louisville", "cardinals"}, "HIGH"),
        # ... conference + regional rivalries
    ],
}
# Total: 204 rivalries across 5 sports
```

**Key Design Decisions:**
- Tuples use sets for case-insensitive keyword matching: `({"celtics", "boston"}, {"lakers"}, "HIGH")`
- Intensity levels: "HIGH" (historic/divisional) and "MEDIUM" (regional/newer)
- Every NBA (30), NFL (32), NHL (32), MLB (30) team has at least one rivalry
- NCAAB covers all major conference programs + historic independents

**Coverage by Sport:**
| Sport | Rivalries | Teams Covered | Coverage |
|-------|-----------|---------------|----------|
| NBA | 35 | 30/30 | 100% |
| NFL | 46 | 32/32 | 100% |
| NHL | 36 | 32/32 | 100% (incl. Kraken, Vegas, Utah) |
| MLB | 36 | 30/30 | 100% (incl. interleague) |
| NCAAB | 51 | 75+ programs | Major conferences |
| **Total** | **204** | All teams | Comprehensive |

**Prevention:**
1. **NEVER add partial data for a sport** — cover ALL teams, not just "popular" ones
2. **Always organize by division/conference** for maintainability
3. **Use keyword sets** for flexible matching (city names, nicknames, abbreviations)
4. **Include newest teams** (Kraken 2021, Golden Knights 2017, Utah 2024)

**Files Modified:**
- `esoteric_engine.py` — Expanded `MAJOR_RIVALRIES` from ~50 to 204 entries (lines 1583-1653)

**Verification:**
```bash
# Test rivalry detection for all sports
python3 -c "
from esoteric_engine import calculate_rivalry_intensity
tests = [
    ('NBA', 'Celtics', 'Lakers', True),      # Historic
    ('NBA', 'Kings', 'Warriors', True),      # California
    ('NFL', 'Bills', 'Dolphins', True),      # AFC East
    ('NFL', 'Jaguars', 'Titans', True),      # AFC South
    ('NHL', 'Kraken', 'Canucks', True),      # Pacific
    ('NHL', 'Golden Knights', 'Sharks', True), # Expansion
    ('MLB', 'Mets', 'Yankees', True),        # Subway Series
    ('NCAAB', 'Duke', 'UNC', True),          # Tobacco Road
]
for sport, t1, t2, expected in tests:
    result = calculate_rivalry_intensity(sport, t1, t2)
    status = '✅' if result.get('is_rivalry') == expected else '❌'
    print(f'{status} {sport}: {t1} vs {t2} = {result}')"
```

**Fixed in:** v20.11 (Feb 8, 2026) — Commit `5e51fa1`

---


### Lesson 72: Auto-Grader Prop Detection via pick_type Pattern (v20.15)
**Problem:** Learning loop showed 0 samples for prop stats (points, rebounds, assists) even though 63+ prop picks existed. Props stored as `player_points` but learning loop looked for `points`.

**Root Cause:** Props are stored with `market="player_points"` but NO explicit `pick_type` field. The auto_grader at line 308 fell back to `market.upper()` → `"PLAYER_POINTS"`. The check `if pick_type in ("PROP", "PLAYER_PROP")` didn't match, so props were treated as game picks and `stat_type` kept the `player_` prefix instead of being stripped.

**The Data Flow Bug:**
```python
# How props were stored (live_data_router.py line 7218-7220):
{
    "market": "player_points",  # From Odds API
    "stat_type": "player_points",  # Same as market
    "prop_type": "player_points",  # Same as market
    # NO "pick_type" field!
}

# Auto-grader detection logic (auto_grader.py line 308-310):
pick_type = pick.get("pick_type", pick.get("market", "")).upper()
# → pick_type = "PLAYER_POINTS" (not "PROP" or "PLAYER_PROP")

if pick_type in ("PROP", "PLAYER_PROP"):  # FALSE!
    stat_type = raw_stat.replace("player_", "")  # Never executed
else:
    stat_type = pick_type.lower()  # → "player_points" (with prefix!)
```

**The Fix:**
```python
# auto_grader.py lines 310-316 — Expanded prop detection
is_prop = (
    pick_type in ("PROP", "PLAYER_PROP") or
    pick_type.startswith("PLAYER_") or  # NEW: catches PLAYER_POINTS
    pick.get("player_name") or           # NEW: has player = is prop
    pick.get("player")
)

if is_prop:
    stat_type = raw_stat.replace("player_", "")  # "points"
```

**Prevention:**
1. **NEVER rely on a single field for type detection** — check multiple signals (pick_type, market prefix, player_name presence)
2. **Always trace data from storage → read** — verify field values match at both ends
3. **Test with real stored data** — bias endpoint with specific stat_type reveals mismatches

**Files Modified:**
- `auto_grader.py` — Expanded `_convert_pick_to_record()` prop detection (lines 310-321)

**Verification:**
```bash
# Before fix: 0 samples for "points"
curl /live/grader/bias/NBA?stat_type=points&days_back=30 -H "X-API-Key: KEY" | jq '.bias.sample_size'
# 0

# After fix: 63+ samples
curl /live/grader/bias/NBA?stat_type=points&days_back=30 -H "X-API-Key: KEY" | jq '.bias.sample_size'
# 63

# Stat types now stripped correctly:
curl /live/grader/performance/NBA -H "X-API-Key: KEY" | jq '.by_stat_type | keys'
# ["assists", "moneyline", "points", "rebounds", "sharp", "spread", "threes", "total"]
```

**Fixed in:** v20.15 (Feb 9, 2026) — Commit `f56b1ce`

---

### Lesson 73: Incomplete Prop Market Coverage (v20.15)
**Problem:** Only 4 NBA prop markets were being fetched (points, rebounds, assists, threes). Missing: steals, blocks, turnovers. "If we bet on them, everything should be tracked and learning loop. It's common sense."

**Root Cause:** `live_data_router.py` line 2496 hardcoded a limited prop market list:
```python
prop_markets = "player_points,player_rebounds,player_assists,player_threes"
# Missing: player_blocks, player_steals, player_turnovers
```

**The Fix — Expanded All Sports:**
```python
# live_data_router.py line 2496 — v20.15: All available prop markets
prop_markets = "player_points,player_rebounds,player_assists,player_threes,player_blocks,player_steals,player_turnovers"
if sport_lower == "nfl":
    prop_markets = "player_pass_tds,player_pass_yds,player_rush_yds,player_reception_yds,player_receptions,player_anytime_td"
elif sport_lower == "mlb":
    prop_markets = "batter_total_bases,batter_hits,batter_rbis,batter_runs,batter_home_runs,pitcher_strikeouts,pitcher_outs"
elif sport_lower == "nhl":
    prop_markets = "player_points,player_shots_on_goal,player_assists,player_goals,player_saves"
```

**Also Updated Learning Loop Configs:**
- `auto_grader.py` — `prop_stat_types` expanded for all sports (2 locations)
- `daily_scheduler.py` — `SchedulerConfig.SPORT_STATS` expanded
- `result_fetcher.py` — `STAT_TYPE_MAP` expanded with all mappings

**Coverage After Fix:**
| Sport | Prop Stats Tracked |
|-------|-------------------|
| NBA | points, rebounds, assists, threes, steals, blocks, turnovers, pra |
| NFL | pass_tds, pass_yds, rush_yds, reception_yds, receptions, anytime_td |
| MLB | hits, runs, rbis, home_runs, total_bases, strikeouts, outs |
| NHL | goals, assists, points, shots, saves |
| NCAAB | points, rebounds, assists, threes, steals, blocks, turnovers |

**Prevention:**
1. **NEVER hardcode partial market lists** — fetch ALL available markets from the API
2. **Keep configs in sync** — prop_markets, prop_stat_types, SPORT_STATS, STAT_TYPE_MAP must all match
3. **Common sense rule: If we bet on it, we track it** — no exceptions

**Files Modified:**
- `live_data_router.py` — Expanded `prop_markets` for all sports (line 2496)
- `auto_grader.py` — Expanded `prop_stat_types` (2 locations: line 176, line 1109)
- `daily_scheduler.py` — Expanded `SchedulerConfig.SPORT_STATS` (line 174)
- `result_fetcher.py` — Expanded `STAT_TYPE_MAP` with all mappings (line 80)

**Verification:**
```bash
# Weights now include all stat types:
curl /live/grader/weights/NBA -H "X-API-Key: KEY" | jq '.weights | keys'
# ["assists", "blocks", "moneyline", "points", "pra", "rebounds", "sharp", "spread", "steals", "threes", "total", "turnovers"]
```

**Fixed in:** v20.15 (Feb 9, 2026) — Commit `e8f0954`

---
