# NEVER DO THESE - Consolidated Rules

Reference this file when making changes in the relevant area.

---

## 🚫 NEVER DO THESE (ML & GLITCH)

1. **NEVER** add a new signal without wiring it into the scoring pipeline
2. **NEVER** add a function parameter without using it in the function body
3. **NEVER** leave API clients as stubs in production (verify `source != "fallback"`)
4. **NEVER** hardcode `base_ai = 5.0` when LSTM models are available
5. **NEVER** skip the ML fallback chain (LSTM → Ensemble → Heuristic)
6. **NEVER** change ENGINE_WEIGHTS without updating `core/scoring_contract.py`
7. **NEVER** add a new pillar without documenting it in the 18-pillar map
8. **NEVER** modify `get_glitch_aggregate()` without updating its docstring weights


---

## 🚫 NEVER DO THESE (MSRF)

16. **NEVER** call MSRF with fewer than 3 significant dates (will return no boost)
17. **NEVER** modify MSRF number lists without understanding sacred geometry theory
18. **NEVER** add MSRF as a 6th engine - use confluence boost pattern instead
19. **NEVER** skip feature flag check (`MSRF_ENABLED`) before MSRF calculations
20. **NEVER** hardcode significant dates - always pull from data sources


---

## 🚫 NEVER DO THESE (SECURITY)

9. **NEVER** log `request.headers` without using `sanitize_headers()`
10. **NEVER** construct URLs with `?apiKey=VALUE` - use `params={}` dict
11. **NEVER** log partial keys like `key[:8]...` (reconnaissance risk)
12. **NEVER** return demo/sample data without `ENABLE_DEMO=true` or `mode=demo`
13. **NEVER** fall back to demo data on API failure (return empty instead)
14. **NEVER** hardcode player names (LeBron, Mahomes) in production responses
15. **NEVER** add new env var secrets without adding to `SENSITIVE_ENV_VARS` in log_sanitizer.py


---

## 🚫 NEVER DO THESE (FastAPI & Function Patterns)

21. **NEVER** return `JSONResponse()` from functions that are called internally - return dicts instead
22. **NEVER** create dual-use functions (endpoint + internal) without verifying return type compatibility
23. **NEVER** use `.get()` on a function return value without verifying it returns a dict (not JSONResponse)
24. **NEVER** leave variables uninitialized before try blocks if they're used after the try block
25. **NEVER** compare numeric variables to thresholds without None checks (use `x is not None and x >= 8.0`)
26. **NEVER** swallow exceptions without logging the traceback
27. **NEVER** return generic error messages in production - include error details in debug mode


---

## 🚫 NEVER DO THESE (Nested Functions & Closures)

28. **NEVER** assume closure variables are defined - verify they're assigned before the nested function
29. **NEVER** use variables from outer scope without checking all code paths initialize them
30. **NEVER** add new variables to nested functions without grepping for all usages
31. **NEVER** modify scoring pipeline without testing all 5 sports (NBA, NHL, NFL, MLB, NCAAB)


---

## 🚫 NEVER DO THESE (API & Data Integration)

32. **NEVER** assume a single API format - check for format variations (Playbook vs ESPN, nested vs flat)
33. **NEVER** put shared context calculations inside pick_type-specific blocks - context runs for ALL types
34. **NEVER** assume injuries/data will match team names exactly - compare actual API responses to game data
35. **NEVER** skip parallel fetching for critical data (props, games, injuries should fetch concurrently)


---

## 🚫 NEVER DO THESE (ESPN Integration)

36. **NEVER** hardcode sport/league mappings inline - use the `SPORT_MAPPING` dict in espn_lineups.py
37. **NEVER** make ESPN calls synchronously in the scoring loop - use batch parallel fetches before scoring
38. **NEVER** assume ESPN has data for all games - officials are assigned closer to game time, gracefully fallback
39. **NEVER** replace primary data with ESPN data - ESPN is for SUPPLEMENT and CROSS-VALIDATION only
40. **NEVER** skip the `league` key in SPORT_MAPPING (the MLB bug: `"mlb": "mlb"` instead of `"league": "mlb"`)
41. **NEVER** forget to handle ESPN $ref links - officials endpoint returns URLs that need separate fetches
42. **NEVER** skip team name normalization when matching ESPN data to Odds API data (case-insensitive + accent handling)
43. **NEVER** assume ESPN venue data exists for indoor sports - only fetch venue/weather for MLB and NFL
44. **NEVER** add ESPN boosts without logging them in research_reasons for debug visibility
45. **NEVER** modify ESPN integration without testing ALL 5 sports (different endpoints, different data availability)


---

## 🚫 NEVER DO THESE (SERP Intelligence)

46. **NEVER** set `SERP_SHADOW_MODE=True` in production - user wants LIVE MODE with active boosts
47. **NEVER** skip quota checks before SerpAPI calls - use `check_quota_available()` first
48. **NEVER** exceed boost caps - enforced in `cap_boost()` (per-engine) and `cap_total_boost()` (4.3 total)
49. **NEVER** make SERP calls inside scoring loop without try/except - must fail-soft, never 500
50. **NEVER** add SERP env var aliases without updating BOTH `integration_contract.py` AND `serpapi.py`
51. **NEVER** change SERP_CACHE_TTL or SERP_TIMEOUT in `serpapi.py` - single source of truth is `serp_guardrails.py`
52. **NEVER** forget to call `record_cache_hit()` / `record_cache_miss()` / `record_cache_error()` for tracking
53. **NEVER** skip `apply_shadow_mode()` before returning boosts - even in live mode (it's a no-op but keeps code paths consistent)
54. **NEVER** forget to increment quota after successful API calls - use `increment_quota()` in serpapi.py
55. **NEVER** hardcode sport-specific search queries inline - use `SPORT_QUERIES` template dict in serp_intelligence.py
56. **NEVER** modify signal→engine mapping without updating INVARIANT 23 in CLAUDE.md
57. **NEVER** re-enable SERP for props (`SERP_PROPS_ENABLED=true`) without first increasing `SERP_DAILY_QUOTA` — props consume ~220 calls/day with near-zero cache hit rate


---

## 🚫 NEVER DO THESE (Esoteric/Phase 1 Signals)

**Engine 3 Contract Rules:**
- **NEVER** change esoteric weight from 0.15 without updating `core/scoring_contract.py`
- **NEVER** add new esoteric signals without documenting in `docs/AUDIT_ENGINE3_ESOTERIC.md`
- **NEVER** remove NOAA fallback logic (Kp-Index must work when API is down)
- **NEVER** mutate `esoteric_score` after BASE_4 calculation
- **NEVER** bypass GLITCH aggregate when computing esoteric_score
- **NEVER** enable noosphere without re-enabling SERP (currently cancelled)
- **NEVER** claim 17 signals — actual count is 29 (23 active, 6 dormant, 1 disabled)

**v20.18 Audit-Only Posture (Lesson 84):**
- **NEVER** activate dormant signals during an audit task — audit = observe, not modify
- **NEVER** change GLITCH weights during audit — weights are 0.25/0.20/0.15/0.25/0.25/0.10 (chrome/void/noosphere/hurst/kp/benford)
- **NEVER** conflate old plan files with current task requirements
- **NEVER** use weak guard assertions like `assert total > 0.9` — use exact: `assert abs(total - 1.05) < 0.001`
- **ALWAYS** verify scoring output unchanged before committing audit changes
- **ALWAYS** update docs/ESOTERIC_TRUTH_TABLE.md when changing wired signal count

57. **NEVER** assume `pick_type == "GAME"` for game picks - actual values are "SPREAD", "MONEYLINE", "TOTAL", "SHARP"
58. **NEVER** check `pick_type == "GAME"` directly - use pattern: `_is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")`
59. **NEVER** check `pick_type == "SHARP"` for SHARP fallback detection — SHARP fallback picks have `market == "sharp_money"`, while `pick_type` contains the bet type (spread/moneyline/total). Session 7 CI fix: commit f2dc80b
60. **NEVER** add esoteric signals directly to `esoteric_score` - add to `esoteric_raw` before the clamp
61. **NEVER** wire signals without adding to `esoteric_reasons` for debug visibility
62. **NEVER** add GAME-only signals without the `_is_game_pick` guard
63. **NEVER** add PROP-only signals without checking `pick_type == "PROP"` AND `player_name`
64. **NEVER** assume all teams will trigger Founder's Echo - only ~7/119 teams resonate on any given day
65. **NEVER** activate dormant signals without testing on production data via curl verification commands
66. **NEVER** modify esoteric scoring without running the verification checklist (checks 9-13 in ML & GLITCH section)


---

## 🚫 NEVER DO THESE (v17.6 - Vortex & Benford)

67. **NEVER** add parameters to `calculate_pick_score()` without updating ALL 3 call sites (game_picks, props, sharp_money)
68. **NEVER** assume Benford will run with <10 values - it requires 10+ for statistical significance
69. **NEVER** pass only direct values (prop_line, spread, total) to Benford - use multi-book aggregation
70. **NEVER** forget to extract from `game.bookmakers[]` when multi-book data is needed
71. **NEVER** add Vortex/Tesla signals without checking for 0/None values first (division by zero risk)
72. **NEVER** modify line history tables without considering the scheduler job dependencies
73. **NEVER** run `_run_line_snapshot_capture()` without checking Odds API quota first
74. **NEVER** assume line history exists for new events - check for NULL/empty returns


---

## 🚫 NEVER DO THESE (v19.0 - Trap Learning Loop)

75. **NEVER** exceed `MAX_SINGLE_ADJUSTMENT` (5%) per trap trigger - safety guard is code-enforced
76. **NEVER** bypass the cooldown period (24h default) - prevents runaway adjustments
77. **NEVER** create traps targeting invalid engine/parameter combinations - validate against `SUPPORTED_ENGINES`
78. **NEVER** skip `_validate_adjustment_safety()` before applying adjustments
79. **NEVER** apply adjustments without logging to `adjustments.jsonl` - audit trail is mandatory
80. **NEVER** modify `SUPPORTED_ENGINES` dict without updating trap_router validation logic
81. **NEVER** create traps with `adjustment_cap > 0.05` - exceeds max single adjustment
82. **NEVER** run trap evaluation before grading completes (6:15 AM runs after 6:00 AM grading)
83. **NEVER** skip `enrich_game_result()` before evaluating conditions - numerology/gematria fields required
84. **NEVER** delete trap files manually - use `update_trap_status(trap_id, "RETIRED")` instead
85. **NEVER** allow cumulative adjustments to exceed 15% per trap - `MAX_CUMULATIVE_ADJUSTMENT` enforced
86. **NEVER** create traps without specifying `target_engine` AND `target_parameter` - both required
87. **NEVER** assume game results exist for all sports on all days - handle empty results gracefully
88. **NEVER** modify trap condition evaluation logic without updating dry-run endpoint to match


---

## 🚫 NEVER DO THESE (v18.2 - Phase 8 Esoteric Signals)

89. **NEVER** compare timezone-naive datetime to timezone-aware datetime - causes `TypeError: can't subtract offset-naive and offset-aware datetimes`
90. **NEVER** use `datetime(2000, 1, 1)` without timezone for astronomical calculations - add `tzinfo=ZoneInfo("UTC")`
91. **NEVER** forget to initialize `weather_data = None` before conditional blocks that may reference it
92. **NEVER** skip `get_phase8_esoteric_signals()` in the scoring pipeline - all 5 signals must run
93. **NEVER** hardcode Mercury retrograde dates without updating for the current year
94. **NEVER** assume Phase 8 signals will always trigger - some dates have no lunar/retrograde/rivalry activity
95. **NEVER** add Phase 8 boosts directly to `esoteric_score` - add to `esoteric_raw` before the clamp
96. **NEVER** skip adding Phase 8 reasons to `esoteric_reasons` for debug visibility
97. **NEVER** use AND logic for env var alternatives when OR is needed - check if ANY alternative is set, not ALL
98. **NEVER** forget that everything is in ET only - don't assume UTC for game times


---

## 🚫 NEVER DO THESE (v20.x - Two Storage Systems)

99. **NEVER** write picks from `auto_grader.py` - only `grader_store.py` writes picks
100. **NEVER** write weights from `grader_store.py` - only `auto_grader.py` writes weights
101. **NEVER** merge the two storage systems - they're separate by design for good reasons
102. **NEVER** add a new `_save_predictions()` method to auto_grader - it was removed intentionally
103. **NEVER** assume picks and weights should be in the same file - different access patterns require separation
104. **NEVER** bypass `grader_store.persist_pick()` when saving picks - it's the single source of truth
105. **NEVER** call `auto_grader._save_state()` expecting it to save picks - it only saves weights now


---

## 🚫 NEVER DO THESE (Boost Field Contract)

106. **NEVER** return a pick without all required boost fields (value + status + reasons)
107. **NEVER** omit `msrf_boost`, `jason_sim_boost`, or `serp_boost` from pick payloads - even if 0.0
108. **NEVER** skip tracking integration usage on cache hits - call `mark_integration_used()` for both cache and live


---

## 🚫 NEVER DO THESE (v20.3 - Post-Base Signals / 8 Pillars)

108a. **NEVER** mutate `research_score` (or any engine score) for Hook Discipline, Expert Consensus, or Prop Correlation signals — they are POST-BASE additive, not engine mutations
108b. **NEVER** apply v20.3 post-base adjustments before `base_score` is computed — they must be passed as explicit parameters to `compute_final_score_option_a()`
108c. **NEVER** omit the v20.3 output fields from pick payloads: `hook_penalty`, `hook_flagged`, `hook_reasons`, `expert_consensus_boost`, `expert_status`, `prop_correlation_adjustment`, `prop_corr_status`
108d. **NEVER** apply caps at the call site — caps are enforced inside `compute_final_score_option_a()`: `HOOK_PENALTY_CAP=0.25`, `EXPERT_CONSENSUS_CAP=0.35`, `PROP_CORRELATION_CAP=0.20`
108e. **NEVER** enable Expert Consensus boost in production until validated — currently SHADOW MODE (boost computed but forced to 0.0)


---

## 🚫 NEVER DO THESE (v20.2 - Auto Grader Weights)

109. **NEVER** add a new pick type (market type) without initializing weights for it in `_initialize_weights()`
110. **NEVER** assume `adjust_weights()` fallback to "points" is correct - it masks missing stat_type configurations
111. **NEVER** forget that game picks use `stat_type = pick_type.lower()` (spread, total, moneyline, sharp)
112. **NEVER** skip verifying `calculate_bias()` returns sample_size > 0 for new stat types
113. **NEVER** assume the auto grader "just works" - test with `/live/grader/bias/{sport}?stat_type=X` for all types
114. **NEVER** add new market types to `run_daily_audit()` without adding corresponding weights
115. **NEVER** assume weight adjustments are applied just because sample_size > 0 - check `applied: true` explicitly
116. **NEVER** skip checking `factor_bias` in bias response - it shows what signals are being tracked for learning
117. **NEVER** assume the daily lesson generated correctly - verify with `/live/grader/daily-lesson/latest`
118. **NEVER** forget to verify correlation tracking for all 28 signals (pace, vacuum, officials, glitch, esoteric)


---

## 🚫 NEVER DO THESE (v20.3 - Grading Pipeline)

119. **NEVER** add a new pick_type without adding handling in `grade_game_pick()` - it will grade as PUSH
120. **NEVER** forget to pass `picked_team` to `grade_game_pick()` for spread/moneyline grading accuracy
121. **NEVER** have mismatched stat type lists between `_initialize_weights()` and `run_daily_audit()` - both must match
122. **NEVER** assume STAT_TYPE_MAP covers all formats - check for direct formats ("points") AND Odds API formats ("player_points")
123. **NEVER** forget to strip market suffixes like "_over_under", "_alternate" from stat types before lookup
124. **NEVER** skip testing grading for ALL pick types after changes (SPREAD, TOTAL, MONEYLINE, SHARP, PROP)
125. **NEVER** assume 0% hit rate means bad predictions - it might mean grading is broken (all PUSH)


---

## 🚫 NEVER DO THESE (v20.4 - Go/No-Go & Sanity Scripts)

126. **NEVER** use hardcoded line numbers in sanity script filters without documenting what they filter
127. **NEVER** modify `live_data_router.py` without re-running `audit_drift_scan.sh` locally
128. **NEVER** add a new boost to the scoring formula without updating `endpoint_matrix_sanity.sh` math check
129. **NEVER** assume `ensemble_adjustment` is 0 - it can be `null`, `0.0`, `+0.5`, or `-0.5`
130. **NEVER** skip the go/no-go check after changes to scoring, boosts, or sanity scripts
131. **NEVER** commit code that fails `prod_go_nogo.sh` - all 12 checks must pass
132. **NEVER** forget that `glitch_adjustment` is ALREADY in `esoteric_score` (not a separate additive)


---

## 🚫 NEVER DO THESE (v20.4 - Frontend/Backend Synchronization)

133. **NEVER** change engine weights in `scoring_contract.py` without updating frontend tooltips
134. **NEVER** assume frontend documentation matches backend - verify against `scoring_contract.py`
135. **NEVER** describe context_score as a "weighted engine" - it's a bounded modifier (±0.35)
136. **NEVER** use old weight percentages (AI 15%, Research 20%, Esoteric 15%, Jarvis 10%, Context 30%)
137. **NEVER** skip updating `docs/FRONTEND_INTEGRATION.md` when backend scoring changes
138. **ALWAYS** verify frontend tooltips show: AI 25%, Research 35%, Esoteric 15%, Jarvis 25%, Context ±0.35

**Correct Option A Weights (authoritative source: `core/scoring_contract.py`):**
```python
ENGINE_WEIGHTS = {
    "ai": 0.25,        # 25% - 8 AI models
    "research": 0.35,  # 35% - Sharp money, splits, variance (LARGEST)
    "esoteric": 0.15,  # 15% - Numerology, astro, fib, vortex (v20.19: reduced from 20%)
    "jarvis": 0.25,    # 25% - Gematria, sacred triggers (v20.19: increased from 20%)
}
CONTEXT_MODIFIER_CAP = 0.35  # ±0.35 (NOT a weighted engine!)
```


---

## 🚫 NEVER DO THESE (Shell Scripts with Python Subprocesses)

139. **NEVER** use `VAR=value` when Python subprocesses need the variable - use `export VAR=value`
140. **NEVER** assume shell variables are inherited by child processes - they must be explicitly exported
141. **NEVER** debug "Could not resolve host: None" without checking if env vars are exported
142. **NEVER** write shell scripts that call Python without verifying variable visibility with `os.environ.get()`

**Shell Variable Scope Quick Reference:**
```bash
# ❌ WRONG - Python subprocess can't see this
BASE_URL="https://example.com"
python3 -c "import os; print(os.environ.get('BASE_URL'))"  # None

# ✅ CORRECT - 'export' makes it visible to children
export BASE_URL="https://example.com"
python3 -c "import os; print(os.environ.get('BASE_URL'))"  # https://example.com
```

---


---

## 🚫 NEVER DO THESE (Datetime/Timezone - v20.5)

143. **NEVER** compare `datetime.now()` with `datetime.fromisoformat(timestamp)` - one may be naive, other aware
144. **NEVER** use undefined variables like `PYTZ_AVAILABLE` - use `core.time_et.now_et()` instead
145. **NEVER** use `pytz` for new code - use `core.time_et` (single source of truth) or `zoneinfo`
146. **NEVER** calculate date windows with wrong math like `days_back + 1` for start (creates 2-day window)
147. **NEVER** assume stored timestamps have the same timezone awareness as runtime datetime
148. **NEVER** store `line_variance` in a field named `line` - they have different meanings
149. **NEVER** grade SHARP picks using `line` field - it contains variance, not actual spread
150. **NEVER** add new datetime handling code without testing timezone-aware vs naive comparison
151. **NEVER** use `datetime.now()` in grader code - always use `now_et()` from `core.time_et`


---

## 🚫 NEVER DO THESE (v20.5 - Go/No-Go & Scoring Adjustments)

152. **NEVER** apply a scoring adjustment to `final_score` without surfacing it as its own field in the pick payload - unsurfaced adjustments break sanity math checks
153. **NEVER** use `os.path.dirname(__file__)` inside Python heredocs (`python3 - <<'PY'`) - `__file__` resolves to `<stdin>` and `dirname()` returns empty string; use project-relative paths instead
154. **NEVER** run `prod_go_nogo.sh` locally without `ALLOW_EMPTY=1` - local dev doesn't have production prediction/weight files
155. **NEVER** add script-only env vars (like `MAX_GAMES`, `MAX_PROPS`, `RUNS`) without registering them in `RUNTIME_ENV_VARS` in `integration_registry.py`
156. **NEVER** expect sanity scripts that test production API to pass pre-deploy when the change adds new fields - deploy first, then verify (chicken-and-egg pattern)

**Datetime Comparison Quick Reference:**
```python
# ❌ WRONG - Will crash if timestamp is timezone-aware
cutoff = datetime.now() - timedelta(days=7)
if datetime.fromisoformat(p.timestamp) >= cutoff:  # Error!

# ✅ CORRECT - Use timezone-aware datetime and handle both cases
from core.time_et import now_et
from zoneinfo import ZoneInfo
et_tz = ZoneInfo("America/New_York")
cutoff = now_et() - timedelta(days=7)

ts = datetime.fromisoformat(p.timestamp)
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=et_tz)  # Make aware if naive
if ts >= cutoff:  # Now safe to compare
```

**Date Window Calculation:**
```python
# ❌ WRONG - Creates 2-day window for days_back=1
cutoff = now - timedelta(days=days_back + 1)      # 2 days ago
end_cutoff = now - timedelta(days=days_back - 1)  # today

# ✅ CORRECT - Exact day boundaries
day_start = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
day_end = day_start + timedelta(days=1)
if day_start <= ts < day_end:  # Exclusive end
```


---

## 🚫 NEVER DO THESE (v20.6 - Boost Caps & Production)

157. **NEVER** allow the sum of confluence+msrf+jason_sim+serp boosts to exceed `TOTAL_BOOST_CAP` (1.5) — this causes score inflation and clustering at 10.0
158. **NEVER** add a new additive boost without updating `TOTAL_BOOST_CAP` logic in `compute_final_score_option_a()` — uncapped boosts compound silently
159. **NEVER** hardcode timeout values in API endpoints — always use `os.getenv()` with a sensible default and register in `integration_registry.py`
160. **NEVER** assume `TIME_BUDGET_S` only needs to cover game scoring — props scoring shares the same budget and needs time too
161. **NEVER** set pick contract fields (description, side_label, etc.) outside `normalize_pick()` — it is the single source of truth for the pick payload
162. **NEVER** use `models/pick_converter.py:compute_description()` for dict-based picks — it uses object attributes (`.player_name`) not dict keys (`["player_name"]`)
163. **NEVER** assume a consistently low engine score (like jarvis_rs=4.5) means the engine is dead code — check the production call path and whether triggers are designed to be rare
164. **NEVER** report a function as "dead code" without tracing which modules actually import it — `score_candidate()` in scoring_pipeline.py is dormant but `compute_final_score_option_a()` is active


---

## 🚫 NEVER DO THESE (v20.7 - Parallel Pre-Fetch & Performance)

165. **NEVER** make sequential external API calls inside a scoring loop when the same data can be pre-fetched in parallel — 107 sequential calls at ~157ms each = ~17s wasted; parallel = ~2-3s
166. **NEVER** assume "the cache handles it" for sequential API call performance — `serpapi.py` has a 90-min cache, but all ~107 queries were unique (different teams/targets); cache only helps on repeated calls within TTL
167. **NEVER** use `threading.Thread` directly for parallel API calls in an async context — use `concurrent.futures.ThreadPoolExecutor` + `asyncio.run_in_executor()` to avoid blocking the event loop
168. **NEVER** pre-fetch without a hard timeout — always wrap parallel batches in `asyncio.wait_for(gather(*futs), timeout=N)` to prevent runaway threads from consuming the entire time budget
169. **NEVER** change the SERP pre-fetch cache key format without updating BOTH the pre-fetch block (line ~5893) AND the cache lookup in `calculate_pick_score()` (line ~4434) — mismatched keys = cache misses = fallback to sequential calls
170. **NEVER** assume props can be pre-fetched like game SERP data — prop SERP calls are per-player with unique parameters that can't be batched ahead of time
171. **NEVER** add a new parallel pre-fetch phase without adding it to `_record()` timing AND checking `_past_deadline()` before starting — untracked phases break performance telemetry and can exceed the time budget
172. **NEVER** diagnose "0 props returned" without checking `_timed_out_components` in debug output — timeout starvation from upstream phases (SERP, game scoring) is the most common cause
173. **NEVER** assume a performance fix is working without verifying `debug.serp.prefetch_cached > 0` in production — a prefetch count of 0 means the pre-fetch failed silently and scoring is still sequential

**SERP Pre-Fetch Quick Reference:**
```python
# ❌ WRONG - Sequential API calls in scoring loop
for pick in candidates:
    result = external_api_call(pick.team)  # N calls × latency = slow

# ✅ CORRECT - Parallel pre-fetch before scoring loop
unique_inputs = extract_unique_from_candidates(candidates)
with ThreadPoolExecutor(max_workers=16) as pool:
    cache = dict(pool.map(fetch_one, unique_inputs))
for pick in candidates:
    result = cache.get(pick.key) or external_api_call(pick.team)  # Cache hit: ~0ms
```


---

## 🚫 NEVER DO THESE (v20.8 - Props Indentation & Code Placement)

174. **NEVER** place `if/break/continue/return` between a function call and the code that processes its result — in Python, indentation determines scope, and a misplaced break can make 160+ lines of code unreachable
175. **NEVER** insert loop control flow (`break`, `continue`) without verifying the indentation level matches the intended loop — a 4-space difference can silently change which loop you're breaking from
176. **NEVER** assume "0 props returned" is a timeout or data issue without checking the props scoring loop's control flow first — structural dead code is invisible (no errors, no crashes, no stack traces)
177. **NEVER** edit code near deeply nested loops without reading the surrounding 50+ lines to verify scope isn't broken — Python's indentation scoping means a single edit can silently disable entire code blocks
178. **NEVER** leave `props_picks.append()` unreachable after refactoring the props scoring loop — always verify the append executes by checking `props.count > 0` in production output


---

## 🚫 NEVER DO THESE (v20.9 - Frontend/Backend Endpoint Contract)

179. **NEVER** add an `api.js` method calling a backend endpoint without first verifying that endpoint exists in `live_data_router.py` — a missing endpoint returns 404, and if the frontend has fallback data, the broken connection is completely invisible
180. **NEVER** use realistic mock/fallback data (MOCK_PICKS, sample arrays) that silently activates on API failure — fallbacks must show empty state or error banners so broken connections are immediately visible
181. **NEVER** assume similar endpoint names mean the endpoint exists — `POST /picks/grade` and `GET /picks/graded` are completely different routes; always verify the HTTP method AND path
182. **NEVER** add a frontend page that depends on a backend endpoint without adding the endpoint to the "Key Endpoints" section in CLAUDE.md — undocumented endpoints get lost and forgotten

**Indentation Bug Quick Reference:**
```python
# ❌ CATASTROPHIC — break between calculate_pick_score() and processing code
                score = calculate_pick_score(...)
            if deadline:       # ← Wrong indent level (game loop, not prop loop)
                break          # Skips ALL processing below
                # Everything at 16-space indent is INSIDE the if block → DEAD CODE
                process_result(score)
                picks.append(result)  # NEVER EXECUTES

# ✅ CORRECT — break AFTER processing is complete
                score = calculate_pick_score(...)
                process_result(score)
                picks.append(result)  # Always executes
            if deadline:       # Check AFTER append
                break
```


---

## 🚫 NEVER DO THESE (v20.11 - Real Data Sources)

183. **NEVER** leave working API modules uncalled — if `alt_data_sources/noaa.py` has `fetch_kp_index_live()` working, it must be wired into the scoring pipeline via `signals/physics.py`
184. **NEVER** hardcode live game scores (0-0, period=1) when ESPN scoreboard data is already being fetched — extract and use real scores for in-game adjustments
185. **NEVER** use simplified 27.3-day lunar cycle for void moon — use Meeus-based calculation with synodic month (29.53d) and perturbation terms for accuracy
186. **NEVER** leave `fetch_player_games()` uncalled in LSTM training — if real data fetching is implemented, use it before falling back to synthetic data
187. **NEVER** skip feature flags for new external API integrations — use `USE_REAL_NOAA`, `LSTM_USE_REAL_DATA` etc. for gradual rollout
188. **NEVER** assume API data is always available — always add fallback to simulation/synthetic when external APIs fail or return insufficient data
189. **NEVER** add a new data source without tracking its usage in debug output — `source: "noaa_live"` vs `source: "fallback"` must be visible
190. **NEVER** modify lunar ephemeris calculations without understanding perturbation terms — moon orbit has ~6.3° variation that affects VOC detection
191. **NEVER** use real training data if sample count < `MIN_SAMPLES_PER_SPORT` (500) — insufficient data produces worse models than synthetic
192. **NEVER** hardcode team names for ESPN live score lookups — always normalize (lowercase, strip accents) for reliable matching

**Real Data Fallback Pattern:**
```python
# ✅ CORRECT — Try real API, fallback gracefully
if USE_REAL_API and API_ENABLED:
    try:
        result = fetch_from_real_api()
        if result and len(result) >= MIN_THRESHOLD:
            return {"data": result, "source": "api_live"}
    except Exception as e:
        logger.warning("API failed, using fallback: %s", e)
# Fallback
return {"data": simulation_data(), "source": "fallback"}

# ❌ WRONG — No fallback, crashes on API failure
result = fetch_from_real_api()  # Raises on error
return result  # No source tracking
```


---

## 🚫 NEVER DO THESE (v20.11 - Rivalry Database)

193. **NEVER** add partial rivalry data for a sport — if adding rivalries, cover ALL teams (30 NBA, 32 NFL, 32 NHL, 30 MLB), not just popular matchups
194. **NEVER** use exact string matching for team names in rivalry detection — use keyword sets for flexible matching (`{"celtics", "boston"}` matches "Boston Celtics", "Celtics", etc.)
195. **NEVER** forget to include newest expansion teams in rivalry data — Kraken (2021), Golden Knights (2017), Utah Jazz rename (2024) must have entries
196. **NEVER** organize rivalries randomly — use division/conference structure for maintainability and completeness verification
197. **NEVER** mix up intensity levels — "HIGH" for historic/divisional rivalries, "MEDIUM" for regional/newer rivalries
198. **NEVER** assume a team has no rivalries — every professional team has at least one divisional rival; research before claiming "no rivalry"

**Rivalry Database Quick Reference:**
```python
# ✅ CORRECT — Set-based keywords for flexible matching
({"celtics", "boston"}, {"lakers", "los angeles lakers", "la lakers"}, "HIGH")

# ❌ WRONG — Exact string match will miss variants
("Boston Celtics", "Los Angeles Lakers", "HIGH")

# ✅ CORRECT — Include city, nickname, and common abbreviations
({"yankees", "new york yankees", "nyy"}, {"red sox", "boston", "bos"}, "HIGH")
```

---


---

## 🚫 NEVER DO THESE (v20.11 - Post-Base Signals Architecture)

182. **NEVER** mutate engine scores (ai_score, research_score, esoteric_score, jarvis_score) for post-base signals — engine scores are LOCKED once BASE_4 is computed; any mutation after that point has NO EFFECT on final_score
183. **NEVER** apply post-base adjustments before `base_score` is computed — they must be passed as explicit parameters to `compute_final_score_option_a()`, not baked into engine scores
184. **NEVER** add a new scoring adjustment without surfacing it as its own field in the pick payload — hidden adjustments break reconciliation testing and audit trails
185. **NEVER** enforce caps at the call site — caps for post-base signals (HOOK_PENALTY_CAP, EXPERT_CONSENSUS_CAP, PROP_CORRELATION_CAP) must be enforced INSIDE `compute_final_score_option_a()` for single source of truth
186. **NEVER** skip the reconciliation test when adding new scoring components — `abs(final_score - clamp(sum(all_terms))) <= 0.02` must pass for all test cases

**Post-Base Signal Architecture (v20.11):**
```python
# ❌ WRONG — Mutating engine score after base_score is computed
base_score = (ai * 0.25) + (research * 0.35) + (esoteric * 0.15) + (jarvis * 0.25)
research += hook_penalty  # TOO LATE! base_score already locked, this has NO EFFECT

# ✅ CORRECT — Pass as explicit parameter to scoring function
final_score = compute_final_score_option_a(
    ai_score, research_score, esoteric_score, jarvis_score,
    context_modifier, confluence_boost, msrf_boost, jason_sim_boost, serp_boost,
    ensemble_adjustment, live_adjustment, totals_calibration_adj,
    hook_penalty=hook_penalty,              # Post-base additive
    expert_consensus_boost=expert_boost,    # Post-base additive
    prop_correlation_adjustment=prop_corr,  # Post-base additive
)
```

---


---

## 🚫 NEVER DO THESE (v20.12 - Dormant Features & API Timing Fallbacks)

203. **NEVER** assume external API data is always available at fetch time — ESPN assigns officials 1-2 hours before game, best-bets runs earlier (10 AM, 12 PM, 6 PM)
204. **NEVER** skip fallback logic when external data sources have timing gaps — use existing tendency databases (officials_data.py, stadium.py) with `confidence: "LOW"` markers
205. **NEVER** add dormant features without env var gates — all new features must be gated (STADIUM_ENABLED, TRAVEL_ENABLED, etc.) for instant rollback
206. **NEVER** use undefined variables in fallback logic — `rest_days if 'rest_days' in dir()` pattern fails; use the proper closure function `_rest_days_for_team()`
207. **NEVER** add altitude/stadium impact without using the same integration pattern as surface — check `STADIUM_ENABLED`, import lazily, add to `esoteric_reasons` and `esoteric_raw`

**Officials Fallback Pattern (v20.12 - Lesson 55):**
```python
# ESPN data unavailable (officials not yet assigned)
officials_data = _find_espn_data(_officials_by_game, home_team, away_team)
lead_official = ""

if officials_data and officials_data.get("available"):
    lead_official = officials_data.get("lead_official", "")

# FALLBACK: Use tendency database when ESPN unavailable
if not lead_official and sport_upper in ["NBA", "NFL", "NHL"]:
    fallback_officials = get_likely_officials_for_game(sport_upper, home_team, game_datetime)
    if fallback_officials and fallback_officials.get("lead_official"):
        lead_official = fallback_officials.get("lead_official")
        officials_data = {"available": True, "source": "tendency_database_fallback",
                         "confidence": "LOW", **fallback_officials}
```


---

## 🚫 NEVER DO THESE (v20.12 - CI Spot Checks & Error Handling)

208. **NEVER** fail CI on `has("errors")` alone — check error codes for severity (timeout codes are not fatal)
209. **NEVER** ignore pick counts when evaluating errors — partial success (timeout with valid picks) is valid
210. **NEVER** assume all sports have games — off-season returns 0 picks legitimately
211. **NEVER** skip error code filtering — `PROPS_TIMED_OUT` and `GAME_PICKS_TIMED_OUT` are soft errors, not fatal
212. **NEVER** treat HTTP 502 as permanent failure — transient server restarts are normal; retry with backoff

---


---

## 🚫 NEVER DO THESE (v20.13 - Field Name Mapping & Gate Label Drift)

216. **NEVER** assume field names match between write path and read path — always trace from `persist_pick()` through to `_convert_pick_to_record()` and verify exact key names match
217. **NEVER** read `dict.get("sharp_money")` when the pick payload stores `sharp_boost` — use the fallback pattern: `breakdown.get("sharp_boost", breakdown.get("sharp_money", 0.0))`
218. **NEVER** hardcode threshold values in label strings — always read from `scoring_contract.py` constants (e.g., `GOLD_STAR_GATES["research_score"]` not literal `"5.5"`)
219. **NEVER** update `scoring_contract.py` thresholds without grepping ALL files for the old values — gate labels in `live_data_router.py`, docs in `CLAUDE.md`, and `docs/MASTER_INDEX.md` must all match
220. **NEVER** trust label strings for debugging — if a gate says `research_gte_5.5` but the actual threshold is 6.5, the label misleads debugging and the learning loop
221. **NEVER** add a new field to `research_breakdown` (or any engine breakdown) without updating `_convert_pick_to_record()` in `auto_grader.py` to read it — unread fields are invisible to the learning loop
222. **NEVER** rename a field in the pick payload without adding a fallback read in all consumers — use `dict.get("new_name", dict.get("old_name", default))` pattern for backward compatibility

**Field Name Mapping Quick Reference (v20.13):**
```python
# ❌ WRONG — Reading old field names that don't exist in pick payload
sharp = breakdown.get("sharp_money", 0.0)      # Pick stores "sharp_boost"
public = breakdown.get("public_fade", 0.0)     # Pick stores "public_boost"
line = breakdown.get("line_variance", 0.0)      # Pick stores "line_boost"

# ✅ CORRECT — Fallback pattern reads new name first, old name as fallback
sharp = breakdown.get("sharp_boost", breakdown.get("sharp_money", 0.0))
public = breakdown.get("public_boost", breakdown.get("public_fade", 0.0))
line = breakdown.get("line_boost", breakdown.get("line_variance", 0.0))
```

**Gate Label Drift Quick Reference (v20.13):**
```python
# ❌ WRONG — Hardcoded threshold in label string (drifts from contract)
gate_label = "research_gte_5.5"  # But GOLD_STAR_GATES["research_score"] = 6.5!

# ✅ CORRECT — Read from scoring_contract.py constants
from core.scoring_contract import GOLD_STAR_GATES
threshold = GOLD_STAR_GATES["research_score"]  # 6.5
gate_label = f"research_gte_{threshold}"       # "research_gte_6.5" — always matches
```

**Verification (run after any auto_grader.py or scoring_contract.py change):**
```bash
# 1. Check field names match between write and read paths
grep -n "sharp_boost\|sharp_money" auto_grader.py live_data_router.py
# Both should use consistent names (or fallback pattern)

# 2. Check gate labels match scoring_contract.py
python3 -c "
from core.scoring_contract import GOLD_STAR_GATES
print('Contract thresholds:', GOLD_STAR_GATES)
"
grep -n "gte_5.5\|gte_4.0\|gte_6.5\|gte_5.5" live_data_router.py CLAUDE.md docs/MASTER_INDEX.md
# Labels must match contract values
```

---


---

## 🚫 NEVER DO THESE (v20.0 - Phase 9 Full Spectrum)

98. **NEVER** add weather boost to indoor sports (NBA, NHL, NCAAB) - weather only for NFL, MLB, NCAAF
99. **NEVER** apply live signals to pre-game picks - only when game_status == "LIVE" or "MISSED_START"
100. **NEVER** exceed -0.35 for weather modifier - capped in weather.py module
101. **NEVER** exceed ±0.50 for combined live signals - MAX_COMBINED_LIVE_BOOST enforced
102. **NEVER** make SSE/WebSocket calls synchronous - blocks event loop, use async
103. **NEVER** skip dome detection for NFL weather - indoor stadiums return NOT_RELEVANT
104. **NEVER** apply surface impact to indoor sports - only NFL/MLB outdoor venues
105. **NEVER** break existing altitude integration (live_data_router.py ~line 4026-4037)
106. **NEVER** use SSE polling intervals < 15 seconds - API quota protection
107. **NEVER** stream full pick objects over SSE - bandwidth; use slim_pick format
108. **NEVER** flip TRAVEL_ENABLED without explicit user approval
109. **NEVER** add new pillars without updating CLAUDE.md pillar table and docs/MASTER_INDEX.md

---


---



---

## 🚫 NEVER DO THESE (v20.15 Learning Loop & Prop Detection)

230. **NEVER rely on a single field for prop detection** — check `pick_type`, `market` prefix, AND `player_name` presence
231. **NEVER assume pick_type is set** — props may only have `market` field; fallback detection is required
232. **NEVER hardcode partial prop market lists** — fetch ALL available markets from Odds API
233. **NEVER forget to sync prop configs** — `prop_markets`, `prop_stat_types`, `SPORT_STATS`, `STAT_TYPE_MAP` must ALL match
234. **NEVER add a new prop market without updating all 4 config locations**:
     - `live_data_router.py:2496` (prop_markets fetch list)
     - `auto_grader.py:176` (prop_stat_types for weight init)
     - `auto_grader.py:1109` (prop_stat_types for audit)
     - `daily_scheduler.py:174` (SPORT_STATS)
     - `result_fetcher.py:80` (STAT_TYPE_MAP for grading)
235. **NEVER assume the learning loop sees data** — verify with `/grader/bias/{sport}?stat_type={stat}` showing `sample_size > 0`
236. **NEVER skip testing bias endpoint per stat_type after changes** — silent failures lose learning data

**Testing the learning loop after changes:**
```bash
# Verify all stat types are tracked:
curl /live/grader/weights/NBA -H "X-API-Key: KEY" | jq '.weights | keys'

# Verify data flows through for each stat type:
for stat in points rebounds assists threes steals blocks turnovers; do
  curl -s "/live/grader/bias/NBA?stat_type=$stat&days_back=30" -H "X-API-Key: KEY" | jq "{stat: \"$stat\", samples: .bias.sample_size}"
done
```

## 🚫 NEVER DO THESE (v20.16.5+ - Engine 2 Research Anti-Conflation)

237. **NEVER read sharp_strength from line_variance** — sharp signal comes from Playbook splits ONLY
238. **NEVER read lv_strength from Playbook data** — line variance comes from Odds API ONLY
239. **NEVER let one API's data pollute another API's fields** — keep source attribution clean
240. **NEVER set signal_strength from variance in fallback path** — when Playbook unavailable, sharp_strength MUST be "NONE"
241. **NEVER omit source_api tags in research_breakdown** — must have `sharp_source_api` and `line_source_api`
242. **NEVER skip raw_inputs in research_breakdown** — must show `sharp_raw_inputs` and `line_raw_inputs` for audit
243. **NEVER claim sharp_status=SUCCESS without real Playbook data** — must have non-null money_pct/ticket_pct
244. **NEVER skip usage_counters_snapshot in debug output** — must show before/after/delta for API calls

**Anti-Conflation Invariants (Engine 2):**
```
INVARIANT 1: sharp_source_api == "playbook_api" (always)
INVARIANT 2: line_source_api == "odds_api" (always)
INVARIANT 3: If sharp_status == "NO_DATA" then sharp_strength == "NONE"
INVARIANT 4: lv_strength varies independently of sharp_strength
```

**Verification:**
```bash
# Check source attribution and separation
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.suppressed_candidates[0].research_breakdown | {
  sharp_source_api, line_source_api,
  sharp_strength, lv_strength,
  sharp_status, line_status
}'
```

**Key Files:**
- `docs/RESEARCH_TRUTH_TABLE.md` — Complete Engine 2 contract
- `core/research_types.py` — ComponentStatus enum, source constants
- `tests/test_research_truthfulness.py` — 21 anti-conflation tests
- `scripts/engine2_research_audit.sh` — Static + runtime verification

## 🚫 NEVER DO THESE (v20.16.7 - XGBoost Feature Consistency)

245. **NEVER pass wrong feature count to XGBoost** — validate len(features) == expected before predict()
246. **NEVER mix training features with inference features** — document FEATURE_NAMES explicitly
247. **NEVER rely on exception handling for feature mismatch** — validate upfront, skip gracefully
248. **NEVER train on scoring outputs but predict with context inputs** — feature sets must match

---

## v20.16.8 Hardcoded Sports Lists (Feb 10, 2026)

249. **NEVER hardcode sport lists in multiple places** — use `SUPPORTED_SPORTS` constant from one location
250. **NEVER add a new sport without grepping for sport lists** — `grep -n '"NBA".*"NFL"' *.py` to find all
251. **NEVER assume all sports are in a loop** — verify NCAAB, NCAAF, etc. are included where applicable

## 🚫 NEVER DO THESE (v2.2.1 - Engine 4 Jarvis-Ophis Hybrid Calibration)

245. **NEVER change OPHIS_SCALE_FACTOR without running 200+ pick audit** — small samples (100 picks) don't reveal true distribution
246. **NEVER evaluate saturation rate alone** — must also check side-balance (+/- clamp distribution)
247. **NEVER assume low saturation = good calibration** — 37% saturation with 96% one-sided clamps is worse than 50% with 50/50 balance
248. **NEVER change per-hit scores without recalibrating SF** — per-hit scores affect msrf_mean, which affects optimal SF
249. **NEVER set SF without checking msrf_mean vs jarvis_mean** — optimal SF ≈ jarvis_mean / msrf_mean
250. **NEVER ignore mean(diff) when tuning SF** — mean(diff) should be close to 0 (within ±0.5)
251. **NEVER claim "best centering" for SF that causes high saturation** — balance centering vs saturation
252. **NEVER trust old sweep data after changing MSRF scoring** — distribution changes require new calibration

**ENGINE 4 Calibration Invariants:**
```
INVARIANT 1: mean(diff) = mean(ophis_norm) - mean(jarvis_before) should be in [-0.5, +0.5]
INVARIANT 2: saturation side-balance should be 35-65% each way (not one-sided)
INVARIANT 3: ophis_norm = msrf_component * OPHIS_SCALE_FACTOR
INVARIANT 4: |ophis_delta_applied| <= 0.75 (OPHIS_DELTA_CAP)
INVARIANT 5: ophis_delta_saturated == (|ophis_delta_raw| >= 0.75)
```

**Calibration Checklist:**
```bash
# After changing MSRF per-hit scores or OPHIS_SCALE_FACTOR:
python3 << 'EOF'
import sys; sys.path.insert(0, '.')
from core.jarvis_ophis_hybrid import calculate_hybrid_jarvis_score, OPHIS_SCALE_FACTOR
from datetime import date, timedelta
import random

random.seed(42)
picks = []
teams = ["Lakers", "Celtics", "Warriors", "Heat", "Bucks", "Nuggets"]
for i in range(210):
    home, away = random.sample(teams, 2)
    result = calculate_hybrid_jarvis_score(home, away, "NBA", date.today() + timedelta(days=random.randint(-30, 30)))
    picks.append({
        "diff": result["ophis_score_norm"] - result["jarvis_score_before_ophis"],
        "sat": result["ophis_delta_saturated"],
        "delta": result["ophis_delta_applied"]
    })

sat_picks = [p for p in picks if p["sat"]]
pos = sum(1 for p in sat_picks if p["delta"] > 0)
neg = sum(1 for p in sat_picks if p["delta"] < 0)
mean_diff = sum(p["diff"] for p in picks) / len(picks)

print(f"SF={OPHIS_SCALE_FACTOR}")
print(f"Saturation: {len(sat_picks)}/{len(picks)} = {len(sat_picks)/len(picks)*100:.0f}%")
print(f"Balance: +{pos} / -{neg} = {pos/len(sat_picks)*100:.0f}%/{neg/len(sat_picks)*100:.0f}%")
print(f"Mean(diff): {mean_diff:.2f}")

# Assertions
assert abs(mean_diff) < 1.0, f"mean(diff) too far from 0: {mean_diff}"
assert 0.25 <= pos/len(sat_picks) <= 0.75, f"Side balance off: {pos/len(sat_picks)}"
print("✅ Calibration OK")
EOF
```

---

## 🚫 NEVER DO THESE (v20.19 - Engine Weight Management)

253. **NEVER duplicate ENGINE_WEIGHTS in multiple files** — `core/scoring_contract.py` is the single source of truth
254. **NEVER change weights without updating fallback values** — `core/scoring_pipeline.py:50-51` has ImportError fallbacks that MUST match
255. **NEVER skip the weight grep after changes** — run: `grep -rn "esoteric.*0\." core/ docs/`
256. **NEVER commit weight changes without running TestWeightsFrozen** — `pytest tests/test_reconciliation.py::TestWeightsFrozen`
257. **NEVER disable the scoring consistency pre-commit hook** — it catches doc↔code drift before production
258. **NEVER hardcode weight literals in formulas** — use `ENGINE_WEIGHTS["esoteric"]` not `0.15`

**Engine Weight Single Source of Truth:**
```python
# ✅ CORRECT: Import from canonical source
from core.scoring_contract import ENGINE_WEIGHTS
base_4 = (ai * ENGINE_WEIGHTS["ai"] +
          research * ENGINE_WEIGHTS["research"] +
          esoteric * ENGINE_WEIGHTS["esoteric"] +
          jarvis * ENGINE_WEIGHTS["jarvis"])

# ❌ WRONG: Duplicate definition
ENGINE_WEIGHTS = {"ai": 0.25, "esoteric": 0.15, ...}  # DON'T DO THIS
```

**Weight Change Verification:**
```bash
# After changing weights in scoring_contract.py:
1. grep -rn "esoteric.*0\." core/ docs/ tests/  # Find all refs
2. grep -rn "jarvis.*0\." core/ docs/ tests/    # Find all refs
3. Update: scoring_pipeline.py fallbacks, all docs
4. pytest tests/test_reconciliation.py::TestWeightsFrozen -v
5. git commit  # Pre-commit hook validates docs == code
```

**Current Weights (v20.19):**
| Engine | Weight | Notes |
|--------|--------|-------|
| AI | 0.25 | 8 AI models |
| Research | 0.35 | Sharp money, splits, variance |
| Esoteric | 0.15 | v20.19: reduced from 0.20 |
| Jarvis | 0.25 | v20.19: increased from 0.20 |

---

## 🚫 NEVER DO THESE (v20.19 - Test Field Name Contracts)

259. **NEVER invent field names in test assertions** — copy field names directly from implementation output dict
260. **NEVER assume internal variables are output fields** — `jarvis_boost` is internal, only `jarvis_rs` is output
261. **NEVER write tests for renamed fields without checking implementation** — `ophis_normalized` was renamed to `ophis_score_norm` in v2.2
262. **NEVER assume edge case behavior** — test what `func(empty_inputs)` ACTUALLY returns, not what seems logical
263. **NEVER let tests drift from implementation** — when schema changes, update tests IMMEDIATELY

**Test-Implementation Contract:**
```python
# ✅ CORRECT: Check actual output keys before writing test
>>> from core.jarvis_ophis_hybrid import calculate_hybrid_jarvis_score
>>> r = calculate_hybrid_jarvis_score("Lakers", "Celtics")
>>> sorted(r.keys())  # SEE THE ACTUAL FIELD NAMES

# ✅ CORRECT: Test uses exact field name from implementation
assert "ophis_score_norm" in result  # matches impl output dict

# ❌ WRONG: Test invents field name
assert "ophis_normalized" in result  # DOESN'T EXIST - typo/rename

# ❌ WRONG: Test expects internal variable
assert "jarvis_boost" in result  # Internal var, not in output
```

**Test Verification Before Commit:**
```bash
# After ANY schema change to output dicts:
1. python3 -c "from module import func; print(sorted(func('test').keys()))"  # Check actual output
2. grep -n "required = \[" tests/test_*.py  # Find field assertions
3. Compare actual output vs test expectations
4. pytest -v  # Run ALL tests before commit
```

**Known Field Name Mappings (Jarvis v2.2):**
| Test Used (WRONG) | Implementation Uses (CORRECT) |
|-------------------|------------------------------|
| `ophis_normalized` | `ophis_score_norm` |
| `jarvis_boost` | *(internal variable, not output)* |
| `jarvis_scaled` | *(internal variable, not output)* |
| `msrf_status: "IN_JARVIS"` (empty inputs) | `msrf_status: "INPUTS_MISSING"` |

---

## v20.20 Golden Run Regression Gates (Rules 264-270)

**CRITICAL: Regression gates exist to catch production bugs, not to document them.**

**Rule 264: Never Loosen a Gate to Match Production**
```python
# ❌ WRONG: Gate fails, so add the failing value to valid set
# "Production returns MONITOR, so MONITOR must be valid"
valid_tiers = ["TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN", "MONITOR"]  # NO!

# ✅ CORRECT: Gate fails, so fix production
# "Production returns MONITOR but shouldn't — find and fix the leak"
HIDDEN_TIERS = {"MONITOR", "PASS"}
filtered = [p for p in picks if p.get("tier") not in HIDDEN_TIERS]
```

**Rule 265: Separate Thresholds by Pick Type**
```python
# ❌ WRONG: Single threshold for all picks
min_score = 6.5  # Games should be 7.0!

# ✅ CORRECT: Different thresholds per pick type
MIN_FINAL_SCORE_GAMES = 7.0  # Games
MIN_FINAL_SCORE_PROPS = 6.5  # Props (SERP disabled, lower ceiling)
```

**Rule 266: Internal States Are Not Output Values**
```python
# Tier assignment progression (INTERNAL):
TITANIUM_SMASH → GOLD_STAR → EDGE_LEAN → MONITOR → PASS

# Output contract (EXTERNAL):
VALID_TIERS = {"TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN"}
HIDDEN_TIERS = {"MONITOR", "PASS"}  # Never returned to API

# MONITOR/PASS are internal workflow states, not output tiers
```

**Rule 267: HIDDEN_TIERS Filter Placement**
```python
# Filter MUST be at output stage, AFTER all processing
# In live_data_router.py, near response building:

HIDDEN_TIERS = {"MONITOR", "PASS"}

# Filter props
filtered_props = [p for p in props if p.get("tier") not in HIDDEN_TIERS]

# Filter games (SAME filter, both places)
filtered_games = [p for p in games if p.get("tier") not in HIDDEN_TIERS]
```

**Rule 268: Gate Failures Require Investigation, Not Accommodation**
```bash
# Golden run fails with: "Invalid tier: MONITOR"

# ❌ WRONG response:
#   "MONITOR must be a valid tier now" → add to valid_tiers

# ✅ CORRECT response:
#   "Why is production returning MONITOR?" → investigate
#   "MONITOR should be filtered" → add HIDDEN_TIERS filter
#   "Gate stays strict" → keeps catching future bugs
```

**Rule 269: Document Intended Behavior First**
```python
# Write the contract BEFORE writing the code:
EXPECTED = {
    "valid_tiers": ["TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN"],
    "min_final_score_games": 7.0,
    "min_final_score_props": 6.5,
}

# Then write code to ACHIEVE the contract, not document current bugs
```

**Rule 270: Test Both Contract AND Filter**
```python
# Unit test: Contract is defined correctly
class TestHiddenTierFilter:
    def test_hidden_tiers_defined(self):
        HIDDEN_TIERS = {"MONITOR", "PASS"}
        assert "MONITOR" in HIDDEN_TIERS
        assert "PASS" in HIDDEN_TIERS

    def test_monitor_filtered_from_output(self):
        picks = [
            {"tier": "GOLD_STAR"},
            {"tier": "MONITOR"},  # Should be filtered
        ]
        HIDDEN_TIERS = {"MONITOR", "PASS"}
        filtered = [p for p in picks if p.get("tier") not in HIDDEN_TIERS]
        assert len(filtered) == 1
        assert filtered[0]["tier"] == "GOLD_STAR"
```

**Golden Run Gate Commands:**
```bash
# Unit tests (no network)
pytest tests/test_golden_run.py -v

# Live validation
API_KEY=key python3 scripts/golden_run.py check

# Full regression with live tests
RUN_LIVE_TESTS=1 API_KEY=key pytest tests/test_golden_run.py -v
```

**Rule 271: Distinguish Internal Assignment from Output Thresholds**
```python
# ❌ WRONG: Single threshold documentation
# "EDGE_LEAN (≥ 6.5)" — confuses internal tier with output filter

# ✅ CORRECT: Document BOTH systems separately

# INTERNAL TIER ASSIGNMENT (tiering.py):
# EDGE_LEAN assigned at final_score >= 6.5

# API OUTPUT THRESHOLDS (live_data_router.py):
# Games: final_score >= 7.0 (MIN_FINAL_SCORE)
# Props: final_score >= 6.5 (MIN_PROPS_SCORE)

# A game scored 6.7 is EDGE_LEAN internally but NEVER returned (6.7 < 7.0)
```

**Rule 272: Use Canonical Field Names in Filtering**
```python
# Pick objects have BOTH fields (aliases, same value):
#   "total_score": round(final_score, 2),
#   "final_score": round(final_score, 2),

# ❌ Inconsistent: Filtering uses one, docs use other
filtered = [p for p in picks if p["total_score"] >= MIN_FINAL_SCORE]
# But MIN_FINAL_SCORE refers to "final_score" conceptually

# ✅ CORRECT: Use canonical field name for doc alignment
filtered = [p for p in picks if p["final_score"] >= MIN_FINAL_SCORE]
```

**Rule 273: Specify Scope When Claiming "Clean"**
```python
# ❌ WRONG: Overstated claim
"Engines are clean"  # Ambiguous — clean WHERE?

# ✅ CORRECT: Precise scope
"No MONITOR/PASS above score threshold"  # Specific, verifiable
"No MONITOR/PASS in API output"          # What contract requires

# The distinction matters:
# - hidden_tier_filtered_total=0 proves: none above threshold
# - Pre-threshold tier counts prove: none anywhere in candidate pool
```

**Rule 274: Non-Empty Set Before Claiming "None Exist"**
```python
# ❌ WRONG: Vacuously true if set is empty
if hidden_tier_filtered_total == 0:
    print("No MONITOR/PASS exist")  # False if no picks at all!

# ✅ CORRECT: Check set is non-empty first
if hidden_tier_filtered_total == 0 and num_picks_returned > 0:
    print("Among returned picks, none are MONITOR/PASS")
```

**Rule 275: Unit Tests Must Cover Forced Fixtures**
```python
# ❌ WRONG: Only test with live data (may not exercise edge cases)
def test_titanium_rule():
    response = api.get("/live/best-bets/NBA")
    # If no TITANIUM picks exist today, test proves nothing

# ✅ CORRECT: Forced fixture covers edge case
def test_titanium_requires_3_of_4():
    # 2 of 4 should NOT trigger
    triggered, _ = compute_titanium_flag(8.0, 8.0, 5.0, 5.0)
    assert triggered is False

    # 3 of 4 SHOULD trigger
    triggered, _ = compute_titanium_flag(8.0, 8.0, 8.0, 5.0)
    assert triggered is True
```

---

## v20.20 Verification Commands (Golden Run Gate)

```bash
# 1. Confirm build SHA
curl -s "$BASE/health" | jq '{build_sha, version}'

# 2. Verify hidden_tier debug fields exist
curl -s "$BASE/live/best-bets/NBA?debug=1" -H "X-API-Key: $KEY" | \
  jq '.debug | {hidden_tier_filtered_props, hidden_tier_filtered_games, hidden_tier_filtered_total}'

# 3. Complete verification (both conditions)
curl -s "$BASE/live/best-bets/NBA?debug=1" -H "X-API-Key: $KEY" | jq '{
  filter_removed: .debug.hidden_tier_filtered_total,
  picks_returned: (.game_picks.count + .props.count),
  claim_valid: ((.debug.hidden_tier_filtered_total == 0) and ((.game_picks.count + .props.count) > 0))
}'

# 4. Run unit tests for forced fixtures
pytest tests/test_golden_run.py::TestTitaniumContract -v
pytest tests/test_golden_run.py::TestHiddenTierFilter -v
```

---

## v20.21 CI Golden Gate & Full System Audit (rules 276-290)

**Rule 276: Run CI Golden Gate Before Deploy**
```bash
# ❌ WRONG: Deploy without running CI tests
git push origin main  # Railway auto-deploys without verification

# ✅ CORRECT: Run CI Golden Gate first
./scripts/ci_golden_gate.sh && git push origin main
```

**Rule 277: Full System Audit Before Frontend Integration**
```bash
# ❌ WRONG: Start frontend work without verifying backend
cd ../bookie-member-app  # Jump to frontend without proving backend ready

# ✅ CORRECT: Run full system audit first
API_KEY=your_key ./scripts/full_system_audit.sh
# Must see: "46/46 PASSED - BACKEND READY FOR FRONTEND"
```

**Rule 278: Output Boundary is Single Choke Point**
```python
# ❌ WRONG: Filter picks at multiple locations
if pick["final_score"] < 6.5:
    continue  # Scattered filtering

# ✅ CORRECT: All filtering in _enforce_output_boundary()
picks = _enforce_output_boundary(picks, is_props=False)  # Single location
```

**Rule 279: Free APIs Use Empty env_vars**
```python
# ❌ WRONG: Free API with env_vars requiring key
NOAA_INTEGRATION = Integration(env_vars=["NOAA_API_KEY"])  # NOAA is free!

# ✅ CORRECT: Free APIs have empty env_vars list
NOAA_INTEGRATION = Integration(env_vars=[])  # No key needed
```

**Rule 280: Bash Arithmetic with set -e**
```bash
# ❌ WRONG: ((PASSED++)) when PASSED=0 returns false → script exits
set -e
PASSED=0
((PASSED++))  # Exit code 1, script terminates

# ✅ CORRECT: Use safe arithmetic
PASSED=$((PASSED + 1))  # Always returns 0
```

**Rule 281: Structured Logging is Idempotent**
```python
# ❌ WRONG: Multiple handlers accumulate
configure_structured_logging()  # Handler 1
configure_structured_logging()  # Handler 2 (duplicate)

# ✅ CORRECT: Remove existing handlers first
def configure_structured_logging():
    root = logging.getLogger()
    root.handlers.clear()  # Remove existing
    root.addHandler(new_handler)  # Add fresh
```

**Rule 282: Integration calls_last_15m Uses Rolling Window**
```python
# ❌ WRONG: Store all calls forever
self.all_calls.append(time.time())  # Memory leak

# ✅ CORRECT: Use deque with pruning
self._call_times = deque()  # O(1) operations
def calls_last_15m(self):
    self._prune_old()  # Remove entries > 15 min
    return len(self._call_times)
```

---

## v20.21 Full System Audit — 11 Hard Gates

| Gate | Verifies | Failure Means |
|------|----------|---------------|
| 1. CI Golden Gate | Contract tests pass | Code doesn't match spec |
| 2. Health & Build | `/health` returns healthy | App not running properly |
| 3. Storage | Volume mounted | Data will be lost |
| 4. Integrations | APIs reachable | No data sources |
| 5. Scheduler | Jobs registered | No training/grading |
| 6. Training | HEALTHY status | Models not trained |
| 7. Autograder | Weights loaded | Learning loop broken |
| 8. 4-Engine | All engines fire | Picks won't score correctly |
| 9. Output Boundary | Valid tiers | Invalid tiers returned |
| 10. Pick Contract | All fields present | Frontend will break |
| 11. Headers | Correlation headers | Debugging impossible |

**Exit Codes:**
- `0` = BACKEND READY FOR FRONTEND
- `1` = BLOCK FRONTEND WORK

---

## v20.24 Telemetry Tracking & Version Management (rules 291-300)

**Rule 291: Derive Telemetry Aggregates from Canonical Source**
```python
# ❌ WRONG: Two separate tracking mechanisms
used_integrations: Set = set()  # Manual tracking
integration_calls: Dict = {}    # Detailed tracking

def call_playbook():
    _record_integration_call("playbook_api", ...)  # Updates integration_calls
    # BUG: forgot to call _mark_integration_used("playbook_api")

# ✅ CORRECT: Single canonical source, derive aggregates
def finalize_request():
    # Derive used_integrations from integration_calls (the canonical source)
    used_integrations = {name for name, meta in integration_calls.items() if meta.get("called", 0) > 0}
```

**Rule 292: NEVER Maintain Two Tracking Systems for Same Concept**
```python
# ❌ WRONG: Two methods that should always be called together
_record_integration_call(name, ...)   # Method 1
_mark_integration_used(name)           # Method 2 (easily forgotten)

# ✅ CORRECT: Single method OR derive at read time
_record_integration_call(name, ...)   # Write to canonical source
used_integrations = derive_from(integration_calls)  # Read-time derivation
```

**Rule 293: Verify Telemetry Fields Match After API Calls**
```bash
# After any API call, verify derived fields match source:
curl -s "$BASE/live/best-bets/NBA?debug=1" -H "X-API-Key: KEY" | \
  jq '{used: .debug.used_integrations, calls: [.debug.integration_calls | keys[]]}'
# Both arrays should match
```

**Rule 294: Version Strings Must Update Together**
```bash
# ❌ WRONG: Update one file, forget others
# Updated core/scoring_contract.py:CONTRACT_VERSION
# But forgot: main.py, golden_run.py, golden_snapshot.py, test_golden_run.py

# ✅ CORRECT: Grep and update ALL version locations
grep -rn "20\\.2[0-9]" --include="*.py" --include="*.json" | grep -E "(version|VERSION)"
# Update ALL matches in single commit
```

**Rule 295: Run CI Golden Gate After Version Bump**
```bash
# ❌ WRONG: Bump version and push without testing
sed -i 's/20.23/20.24/' core/scoring_contract.py
git commit -m "bump version" && git push  # May break golden gate!

# ✅ CORRECT: Test locally first
# Update all version locations
./scripts/ci_golden_gate.sh  # Verify tests pass
git commit -m "chore: bump version to 20.24" && git push
```

**Rule 296: Version Bump Checklist (mandatory files)**
```
□ core/scoring_contract.py (CONTRACT_VERSION)
□ main.py (/health response)
□ scripts/golden_run.py
□ scripts/golden_snapshot.py
□ tests/test_golden_run.py (EXPECTED_VERSION)
□ tests/fixtures/golden_baseline_*.json
□ CLAUDE.md (Current Version section)
```

**Rule 297: /health Must Return CONTRACT_VERSION**
```python
# ❌ WRONG: Hardcoded version in health endpoint
@app.get("/health")
async def health():
    return {"version": "20.20", ...}  # Hardcoded, drifts from contract

# ✅ CORRECT: Import from canonical source (or update together)
from core.scoring_contract import CONTRACT_VERSION
# If main.py can't import (circular), ensure version bump updates both
```

**Rule 298: Test Expected Version Must Match Production**
```python
# tests/test_golden_run.py
# ❌ WRONG: Test expects old version after production upgrade
EXPECTED_VERSION = "20.20"  # But production returns "20.24"

# ✅ CORRECT: Test version matches production
EXPECTED_VERSION = "20.24"  # Updated in same commit as production
```

---

## 🚫 NEVER DO THESE (v20.25 ET Canonical Clock)

**Rule 299: Update Import Statements When Adding Exports**
```python
# ❌ WRONG: Add function to __all__ but not to import sites
# core/time_et.py
__all__ = [..., 'format_as_of_et', 'format_et_day']  # Added

# live_data_router.py - FORGOT TO UPDATE
from core.time_et import (now_et, et_day_bounds, ...)  # Missing new functions!
# Runtime: NameError: name 'format_as_of_et' is not defined

# ✅ CORRECT: Grep and update all import sites
grep -rn "from core.time_et import" --include="*.py"
# Update EVERY file that needs the new functions
```

**Rule 300: ISO 8601 Regex Must Handle Microseconds**
```bash
# ❌ WRONG: Regex rejects Python's default isoformat() output
'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}$'
# Fails: 2026-02-14T13:09:33.828134-05:00 (has microseconds)

# ✅ CORRECT: Allow optional fractional seconds
'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?[+-][0-9]{2}:[0-9]{2}$'
```

**Rule 301: ET Canonical Clock Single Source of Truth**
```python
# ❌ WRONG: Multiple ET formatting functions scattered across codebase
def my_format_et():  # In some random file
    return datetime.now(ET).isoformat()

# ✅ CORRECT: Use core/time_et.py functions ONLY
from core.time_et import format_as_of_et, format_et_day
# format_as_of_et() -> "2026-02-14T13:09:33.828134-05:00"
# format_et_day()   -> "2026-02-14"
```

**Rule 302: Response Meta Must Include ET Fields (v20.25+)**
```python
# ❌ WRONG: Meta block missing canonical ET fields
"meta": {
    "sport": "NBA",
    "generated_at": "..."  # NO! This is UTC/internal telemetry
}

# ✅ CORRECT: Include as_of_et and et_day
"meta": {
    "sport": "NBA",
    "as_of_et": "2026-02-14T13:09:33.828134-05:00",  # Canonical ET timestamp
    "et_day": "2026-02-14",                          # Canonical ET date
}
```

**Rule 303: Integration Telemetry Must Use fetched_at_et**
```python
# ❌ WRONG: Integration calls record in UTC
integration_calls[name] = {"fetched_at": datetime.utcnow().isoformat(), ...}

# ✅ CORRECT: Use ET for all timestamps
from core.time_et import format_as_of_et
integration_calls[name] = {"fetched_at_et": format_as_of_et(), ...}
```

**Rule 304: Test Regex Against Real Output Before Deploy**
```bash
# ❌ WRONG: Write regex, deploy, discover failure in production

# ✅ CORRECT: Test against actual output first
ACTUAL=$(curl -s "$URL" | jq -r '.meta.as_of_et')
echo "$ACTUAL" | grep -qE 'YOUR_REGEX' && echo PASS || echo FAIL
# Only deploy after PASS
```

---

## 🚫 NEVER DO THESE (v20.26 Live Audit & Determinism)

**Rule 305: inputs_hash Must Be Deterministic**
```python
# ❌ WRONG: Include time-varying or non-rounded values
_inputs_hash_data = {
    "ai": ai_score,           # Floating point precision issues
    "timestamp": now_et(),    # Changes every call!
    "random": random.random() # Non-deterministic
}

# ✅ CORRECT: Round floats, exclude time-varying values
_inputs_hash_data = {
    "ai": round(ai_scaled, 2),
    "research": round(research_score, 2),
    # ... deterministic inputs only
}
_inputs_hash = hashlib.sha256(json.dumps(_inputs_hash_data, sort_keys=True).encode()).hexdigest()[:16]
```

**Rule 306: JSON Serialization Requires sort_keys=True**
```python
# ❌ WRONG: Dict ordering is non-deterministic in Python < 3.7
json.dumps(data)  # Order may vary between calls

# ✅ CORRECT: Force deterministic ordering
json.dumps(data, sort_keys=True)
```

**Rule 307: market_phase Must Be Present on Every Pick**
```python
# ❌ WRONG: Missing market_phase field
{
    "game_status": "IN_PROGRESS",  # API-specific, inconsistent
    # market_phase missing!
}

# ✅ CORRECT: Include canonical market_phase
{
    "game_status": "IN_PROGRESS",
    "market_phase": "IN_PLAY",  # One of: PRE_GAME, IN_PLAY, HALFTIME, FINAL
}
```

**Rule 308: market_phase Must Be Canonical Value**
```python
# ❌ WRONG: Using API-specific status values
market_phase = game_status  # Could be "INPROGRESS", "live", "1H", etc.

# ✅ CORRECT: Normalize to canonical values
VALID_PHASES = {"PRE_GAME", "IN_PLAY", "HALFTIME", "FINAL"}
# Always map to one of these, default to PRE_GAME if unknown
```

**Rule 309: Integration Timestamps Must Use now_et() Not now**
```python
# ❌ WRONG: Variable 'now' undefined
timestamp = now.isoformat()  # NameError: name 'now' is not defined

# ✅ CORRECT: Use imported now_et() function
from core.time_et import now_et
timestamp = now_et().isoformat()
```

**Rule 310: Integration Health Tracking Must Use ISO Strings**
```python
# ❌ WRONG: Mixing datetime objects and strings in comparisons
cutoff = now_et()
if timestamp >= cutoff:  # TypeError: can't compare str to datetime

# ✅ CORRECT: Convert both to ISO strings for comparison
cutoff_iso = now_et().isoformat()
if timestamp_iso >= cutoff_iso:  # String comparison works
```

**Live Audit Verification Commands (v20.26):**
```bash
# 1. Check inputs_hash determinism (same game, same hash)
curl -s "$URL/live/best-bets/NBA" | jq '.game_picks.picks[0] | {inputs_hash, final_score}'
sleep 3
curl -s "$URL/live/best-bets/NBA" | jq '.game_picks.picks[0] | {inputs_hash, final_score}'
# Hashes should match if final_score unchanged

# 2. Check market_phase present and valid
curl -s "$URL/live/best-bets/NBA" | jq '.game_picks.picks[] | .market_phase' | sort | uniq
# Should only show: "PRE_GAME", "IN_PLAY", "HALFTIME", or "FINAL"

# 3. Check integration call tracking
curl -s "$URL/live/debug/integrations" | jq '.integrations[] | {name, calls_last_15m}'
```

---

## v20.26 Live Betting Correctness (rules 311-318)

**Context:** Live betting requires airtight data staleness tracking and correct game status derivation. These rules ensure users see accurate, timely information.

**Rule 311: NEVER Use MISSED_START Status**
```python
# ❌ WRONG: MISSED_START is deprecated
if is_game_started(commence_time):
    return "MISSED_START"  # Confuses frontend, breaks live betting

# ✅ CORRECT: Use IN_PROGRESS for started games
if is_game_started(commence_time):
    return "IN_PROGRESS"  # Enables live betting
```

**Rule 312: data_age_ms Must Be MAX Across CRITICAL Integrations**
```python
# ❌ WRONG: Using single integration age
data_age_ms = age_ms_from_odds_api  # Ignores stale playbook data

# ✅ CORRECT: Use MAX across ALL critical integrations
max_age_ms = None
for name, entry in integration_calls.items():
    if entry.get("criticality") == "CRITICAL":
        age = data_age_ms(entry.get("fetched_at_et"))
        if max_age_ms is None or age > max_age_ms:
            max_age_ms = age
# data_age_ms = max_age_ms (conservative - worst case)
```

**Rule 313: data_age_ms Must NEVER Be Null When Picks > 0**
```python
# ❌ WRONG: Returning null data_age_ms with picks
{
    "picks": [pick1, pick2],  # picks > 0
    "meta": {"data_age_ms": null}  # VIOLATION
}

# ✅ CORRECT: Always compute data_age_ms when picks present
if len(picks) > 0:
    assert meta["data_age_ms"] is not None, "data_age_ms required when picks > 0"
```

**Rule 314: Every Integration Call Must Record fetched_at_et**
```python
# ❌ WRONG: Recording call without timestamp
_record_integration_call("odds_api", status="SUCCESS")

# ✅ CORRECT: Include fetched_at_et and criticality
_record_integration_call(
    "odds_api",
    status="SUCCESS",
    fetched_at_et=format_as_of_et(),  # When data was fetched
    criticality="CRITICAL"             # Integration tier
)
```

**Rule 315: Game Status Must Use Canonical Values Only**
```python
# ❌ WRONG: Non-canonical status values
game_status = "STARTED"     # Not canonical
game_status = "UPCOMING"    # Deprecated, use PRE_GAME
game_status = "MISSED_START"  # Deprecated, use IN_PROGRESS

# ✅ CORRECT: Only these 4 canonical values
VALID_STATUSES = {"PRE_GAME", "IN_PROGRESS", "FINAL", "NOT_TODAY"}
assert game_status in VALID_STATUSES
```

**Rule 316: get_game_status() Requires completed Parameter**
```python
# ❌ WRONG: Ignoring completion state
status = get_game_status(commence_time)  # Doesn't know if game is final

# ✅ CORRECT: Pass completed flag from API data
status = get_game_status(commence_time, completed=game_data.get("completed", False))
```

**Rule 317: Audit Scripts Must Normalize Date Formats**
```bash
# ❌ WRONG: Direct string comparison of different formats
if [[ "$ET_DAY" == "$DATE_ET" ]]; then  # "2026-02-14" != "February 14, 2026"

# ✅ CORRECT: Normalize before comparing
DATE_ET_NORMALIZED=$(date -j -f "%B %d, %Y" "$DATE_ET" "+%Y-%m-%d" 2>/dev/null || echo "$DATE_ET")
if [[ "$ET_DAY" == "$DATE_ET_NORMALIZED" ]]; then  # Both YYYY-MM-DD now
```

**Rule 318: Live Betting Audit Must Run Post-Deploy**
```bash
# ❌ WRONG: Deploying without live betting audit
git push origin main
# No validation!

# ✅ CORRECT: Run audit after deploy
git push origin main
sleep 120  # Wait for Railway deploy
API_KEY=your_key ./scripts/live_betting_audit.sh
API_KEY=your_key SPORT=NCAAB ./scripts/live_betting_audit.sh
```

**Live Betting Correctness Verification Commands (v20.26):**
```bash
# 1. Run full live betting audit
API_KEY=your_key ./scripts/live_betting_audit.sh

# 2. Verify no MISSED_START status in picks
curl -s "$URL/live/best-bets/NCAAB?debug=1" -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[] | select(.game_status == "MISSED_START")] | length'
# Must be 0

# 3. Verify data_age_ms is conservative (MAX)
curl -s "$URL/live/best-bets/NBA?debug=1" -H "X-API-Key: KEY" | jq '{
  data_age_ms: .meta.data_age_ms,
  odds_api: .meta.integrations_age_ms.odds_api,
  playbook_api: .meta.integrations_age_ms.playbook_api
}'
# data_age_ms should equal max(odds_api, playbook_api)

# 4. Verify IN_PROGRESS games are present during live games
curl -s "$URL/live/best-bets/NCAAB?debug=1" -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[] | .game_status] | group_by(.) | map({status: .[0], count: length})'
# Should show IN_PROGRESS during game hours
```

---

## 🚫 NEVER DO THESE (v20.27 AI Score Variance & Heuristic Fallback)

**Context:** NCAAB best-bets returned constant AI scores (7.8) because context services returned defaults for all teams. These rules prevent future AI score collapse.

**Rule 319: NEVER Assume model_std is Normalized 0-1**
```python
# ❌ WRONG: Assuming MPS model_std is normalized
if model_std < 0.3:  # NEVER triggers — model_std is 31-37 (raw points)
    is_degenerate = True

# ✅ CORRECT: Check INPUT quality, not output metrics
defaults_used = (def_rank == 15 and pace == 100 and vacuum == 0)
if defaults_used:
    is_degenerate = True  # Defaults → identical outputs
```

**Rule 320: NEVER Detect Degenerate Outputs Without Checking Inputs First**
```python
# ❌ WRONG: Only checking model outputs
if unique_scores < 4 or stddev < 0.15:
    is_degenerate = True  # Doesn't explain WHY

# ✅ CORRECT: Check inputs first, then outputs as confirmation
if inputs_are_defaults(game_data):
    return use_heuristic_fallback(game_data)
# MPS with real inputs should produce varied outputs
```

**Rule 321: NEVER Use random() in Scoring — Use Deterministic Hashes**
```python
# ❌ WRONG: Random variance (non-deterministic)
variance = random.random() * 2 - 1  # Different every call!
ai_score = 7.0 + variance

# ✅ CORRECT: Team hash for deterministic variance
team_hash = hash(f"{home}{away}{sport}") % 1000
variance = (team_hash / 1000.0) * 4.0 - 2.0  # Same game → same score
ai_score = 7.0 + variance
```

**Rule 322: NEVER Apply Spread Goldilocks to MONEYLINE Markets**
```python
# ❌ WRONG: Using spread logic for moneyline
if 4 <= spread <= 9:  # spread is 0 for moneylines!
    score += 0.5  # Never triggers

# ✅ CORRECT: Use odds-implied probability for moneylines
if market == "MONEYLINE":
    implied_prob = calculate_implied_probability(odds)
    score = moneyline_value_score(implied_prob)
```

**Rule 323: NEVER Return Picks Without AI Variance Telemetry**
```python
# ❌ WRONG: Debug output lacks variance stats
debug = {"total_candidates": 44}  # No way to diagnose constant scores

# ✅ CORRECT: Include ai_variance_stats in debug
debug = {
    "ai_variance_stats": {
        "games": {
            "count": 44,
            "unique_ai_scores": 24,
            "ai_score_stddev": 0.701,
            "heuristic_fallback_count": 38
        }
    }
}
```

**Rule 324: NEVER Skip Heuristic Fallback for Sports Without Data Coverage**
```python
# ❌ WRONG: Assuming all sports have context data
context = get_context_data(team)  # Returns defaults for NCAAB
ai_score = mps.predict(context)   # Always returns 7.8

# ✅ CORRECT: Detect defaults and fallback
if context_is_default(context):
    return heuristic_ai_score(game_data)  # Varied scores
```

**Rule 325: NEVER Deploy Without Running AI Variance Audit**
```bash
# ❌ WRONG: Deploy without variance check
git push origin main  # May ship constant AI scores

# ✅ CORRECT: Run variance audit for all sports
API_KEY=key SPORT=NBA ./scripts/live_betting_audit.sh
API_KEY=key SPORT=NCAAB ./scripts/live_betting_audit.sh
# Check #6 must pass: unique >= 4, stddev >= 0.15
git push origin main
```

**AI Score Variance Invariants (v20.27):**
```
INVARIANT 1: For >= 5 candidates, unique(ai_score) >= 4
INVARIANT 2: For >= 5 candidates, stddev(ai_score) >= 0.15
INVARIANT 3: Heuristic fallback is deterministic (hash-based)
INVARIANT 4: MONEYLINE scoring uses odds-implied probability, not spread
INVARIANT 5: ai_variance_stats present in debug output when debug=1
```

**AI Score Variance Verification Commands (v20.27):**
```bash
# 1. Check variance stats in debug output
curl -s "$URL/live/best-bets/NCAAB?debug=1" -H "X-API-Key: KEY" | \
  jq '.debug.ai_variance_stats.games | {unique: .unique_ai_scores, stddev: .ai_score_stddev, heuristic: .heuristic_fallback_count}'

# 2. Verify minimum variance thresholds
curl -s "$URL/live/best-bets/NCAAB?debug=1" -H "X-API-Key: KEY" | \
  jq -e '.debug.ai_variance_stats.games | (.unique_ai_scores >= 4) and (.ai_score_stddev >= 0.15)'
# Exit code 0 = pass, non-zero = fail

# 3. Check market type distribution
curl -s "$URL/live/best-bets/NCAAB?debug=1" -H "X-API-Key: KEY" | \
  jq '.debug.market_counts_by_type'
# All market types should have candidates

# 4. Run full audit
API_KEY=your_key SPORT=NCAAB ./scripts/live_betting_audit.sh
# All 6 checks must pass
```

**Key Files (v20.27):**
- `live_data_router.py` — `_resolve_game_ai_score()`, `calculate_pick_score()` with odds parameter
- `tests/test_live_betting_correctness.py` — `TestAIScoreVariance` class (6 tests)
- `scripts/live_betting_audit.sh` — Check #6 AI score variance

---

## v20.28.1 CI Hardening Rules (Lesson 121)

**The Golden Rule: Tests in repo ≠ tests in CI. Wire them or they're useless.**

**Rule 326: NEVER Add Test Files Without Updating GitHub Actions**
```yaml
# ❌ WRONG: Add tests but don't update workflow
# tests/test_new_feature.py created
# .github/workflows/golden-gate.yml NOT updated
# Result: Tests never run, false sense of security

# ✅ CORRECT: Same commit updates both
# tests/test_new_feature.py created
# .github/workflows/golden-gate.yml updated:
- name: New Feature Tests
  run: python -m pytest tests/test_new_feature.py -v
```

**Rule 327: NEVER Use Soft Warnings for Blocking Conditions**
```python
# ❌ WRONG: Warning that doesn't stop deployment
def test_ai_variance():
    if unique_scores < 4:
        warn(f"Low variance: {unique_scores}")  # Deployment continues!

# ✅ CORRECT: Hard assertion that fails CI
def test_ai_variance():
    assert unique_scores >= 4, f"HARD FAIL: {unique_scores} < 4 unique scores"
```

**Rule 328: NEVER Assume CI Runs Your Tests**
```bash
# ❌ WRONG: Push and assume tests run
git push origin main
# Hope tests run...

# ✅ CORRECT: Verify in GitHub Actions output
git push origin main
# Go to GitHub → Actions → Check job output
# Verify your test file appears in the logs
```

**Rule 329: NEVER Add Hard Gates Without CI Integration**
```python
# ❌ WRONG: Hard gate in code but not tested
class TestNewGate:
    def test_invariant(self):
        assert condition, "Gate fails"
# File not in any GitHub Actions job

# ✅ CORRECT: Hard gate + CI job
# 1. Add test class
# 2. Update .github/workflows/golden-gate.yml
# 3. Verify job runs on PR before merging
```

**Rule 330: NEVER Skip Live Audit After Deploy**
```bash
# ❌ WRONG: Unit tests pass, ship it
pytest tests/ && git push

# ✅ CORRECT: Unit tests + live audit after deploy
pytest tests/
git push origin main
# Wait for Railway deploy (3 min)
API_KEY=key ./scripts/live_betting_audit_all_sports.sh
```

**CI Pipeline Checklist (v20.28.1):**
```
Before merging any PR:
[ ] All test files in .github/workflows/golden-gate.yml
[ ] Hard assertions (assert), not soft warnings (warn)
[ ] Cross-sport tests run for all 5 sports
[ ] Live audit runs after Railway deploy on main

After push to main:
[ ] Check GitHub Actions → all jobs green
[ ] Check Railway deploy completed
[ ] Run live audit against production
```

**GitHub Actions Jobs (v20.28.1):**
```yaml
# All 4 jobs must pass for deployment
golden-gate:           # Unit tests + golden run
contract-tests:        # Contract validation
cross-sport-4engine:   # 85 tests (HARD GATE)
live-api-audit:        # Live audit after deploy
```

**Key Files (v20.28.1):**
- `.github/workflows/golden-gate.yml` — CI configuration (4 jobs)
- `tests/test_cross_sport_4engine.py` — 85 tests with hard gate classes
- `tests/test_live_betting_correctness.py` — 25 tests
- `scripts/live_betting_audit_all_sports.sh` — Cross-sport live audit

---

## v20.28.2 Paid APIs First (rules 331-335)

331. **NEVER** use ESPN for data that Odds API provides — live scores, odds, lines are all available from paid API
332. **NEVER** default to free API when paid API has the same feature — check paid APIs first
333. **NEVER** add new ESPN integrations without confirming paid APIs dont have the data
334. **ALWAYS** include `source` field in data to track which API provided it (auditability)
335. **ALWAYS** document API priority in comments when choosing between paid and free sources

---
