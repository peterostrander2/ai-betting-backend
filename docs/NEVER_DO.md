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

