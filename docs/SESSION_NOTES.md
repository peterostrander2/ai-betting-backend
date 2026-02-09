
## Codex DNS / GitHub Push Caveat (Feb 3, 2026)

**Problem observed:**
- Codex runtime reported "No DNS configuration available" (from `scutil --dns`).
- Codex could not resolve `github.com` or `api.github.com`, so `git push`/`git fetch` failed inside Codex.
- Mac Wi-Fi was connected; the issue was isolated to Codex's runtime environment.

**What was true at the time:**
- A real commit existed locally: `d152a96` ("docs: lock Option A + add scoring guard").
- The commit was not pushed due to DNS failure inside Codex.
- Therefore, Option A only "lives in the system" after a successful push from a working terminal.

**Manual steps to finalize when Codex cannot push:**
```bash
cd /Users/apple/ai-betting-backend

# 1) Confirm the commit exists locally
git show -s --oneline d152a96

# 2) Push it
git push origin main

# 3) Verify remote has it
git ls-remote origin refs/heads/main | head -n 1
```

**Interpretation:**
- If `git ls-remote` returns a hash matching `d152a96` (or a newer commit that includes it), the change is pushed.
- If DNS still fails in Codex, use the local terminal to push; no Codex DNS fix is required for this workflow.

**Only meaningful DNS test inside Codex:**
```bash
python3 -c 'import socket; print(socket.gethostbyname("github.com"))'
```

**Next hardening steps (after push confirmed):**
1) Ensure guard tests run in CI (e.g., `tests/test_option_a_scoring_guard.py`).
2) Keep a one-line invariant in this file: Option A is canonical and context is modifier-only.
3) Add a drift-scan to `scripts/ci_sanity_check.sh` to block `BASE_5` / context-weighted strings.
# 1770205770

### Lesson 65: SERP Quota Cost vs Value Analysis (v20.12)
**Problem:** SERP API burned 5000+ searches/month with 1000+ searches in a single day. Quota exhausted mid-month causing 429 rate limits.

**Root Cause:** SERP was enabled by default for both props AND game picks. Each best-bets request triggered ~70+ Google searches for game narratives, team buzz, and news.

**Cost/Benefit Analysis:**
| Signal | Max Boost | Source |
|--------|-----------|--------|
| Sharp Chatter | +1.3 | SERP |
| Narrative Momentum | +0.7 | SERP |
| Noosphere Buzz | +0.6 | SERP |
| **Total SERP Impact** | **+2.6 max** | 5000 searches/month |

**Better Alternatives (No Per-Call Cost):**
- Playbook API: Sharp money splits, line movement (already included)
- ESPN: Live scores, injuries, officials (already included)
- LSTM: Historical player performance (already included)

**Decision:** Disabled SERP by default (`SERP_INTEL_ENABLED=false`).

**To Re-enable (if upgraded plan):**
```bash
# In Railway environment variables:
SERP_INTEL_ENABLED=true
```

**Prevention:**
1. **NEVER enable expensive per-call APIs by default** — require explicit opt-in
2. **Calculate cost/benefit before enabling** — SERP was ~$0.001/search but marginal value
3. **Monitor quota via debug endpoint** — `/live/debug/integrations` shows quota usage

**Fixed in:** v20.12 (Feb 8, 2026)

### Lesson 69: Auto-Grader Field Name Mismatch — Learning Loop Blind to Research Signals (v20.13)
**Problem:** The daily learning loop (auto_grader) always saw 0.0 for all three research engine signals (sharp money, public fade, line variance). The learning loop could never learn from or adjust research signal weights because it was reading the wrong field names.

**Root Cause:** Two different code paths write and read research signal data with **different field names**:

| Path | When | Field Names Used |
|------|------|-----------------|
| **Live path** (`log_prediction()` line 7464-7466) | Every best-bets call | Correctly maps `sharp_boost` → `sharp_money_adjustment` |
| **JSONL read path** (`_convert_pick_to_record()` line 368-370) | Daily 6AM audit | Reads `research_breakdown.sharp_money` — **WRONG** |

The pick payload stores fields as `sharp_boost`, `public_boost`, `line_boost` in `research_breakdown`, but `_convert_pick_to_record()` looked for `sharp_money`, `public_fade`, `line_variance`.

```python
# BUG — auto_grader.py line 368-370
sharp_money_adjustment=pick.get("research_breakdown", {}).get("sharp_money", 0.0),  # Always 0.0!
public_fade_adjustment=pick.get("research_breakdown", {}).get("public_fade", 0.0),  # Always 0.0!
line_variance_adjustment=pick.get("research_breakdown", {}).get("line_variance", 0.0),  # Always 0.0!

# FIX — Try correct field name first, fall back to old name for backward compat
sharp_money_adjustment=pick.get("research_breakdown", {}).get("sharp_boost", pick.get("research_breakdown", {}).get("sharp_money", 0.0)),
public_fade_adjustment=pick.get("research_breakdown", {}).get("public_boost", pick.get("research_breakdown", {}).get("public_fade", 0.0)),
line_variance_adjustment=pick.get("research_breakdown", {}).get("line_boost", pick.get("research_breakdown", {}).get("line_variance", 0.0)),
```

**Impact:** The daily audit's `calculate_bias()` for research signals (sharp_money, public_fade, line_variance) always computed correlations against 0.0, making the learning loop completely blind to research engine performance. Weight adjustments for research signals were always zero.

**Prevention:**
1. **NEVER assume field names match across read/write paths** — trace the full data flow from creation → storage → retrieval
2. **When reading stored data, verify against the WRITE path** — grep for where `research_breakdown` is populated, not just where it's read
3. **Add fallback patterns for field name changes** — `dict.get("new_name", dict.get("old_name", default))` handles both old and new data
4. **Add integration tests for the learning loop** — verify `_convert_pick_to_record()` produces non-zero values for all signal categories

**Files Modified:**
- `auto_grader.py` — Lines 368-370: Updated field name reads with fallback pattern

**Verification:**
```bash
# After next daily audit, verify research signals are non-zero
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '.bias.factor_bias | {sharp_money, public_fade, line_variance}'
# Values should be non-zero when picks have research signals
```

**Fixed in:** v20.13 (Feb 9, 2026) — Commit `33a4a02`

### Lesson 70: GOLD_STAR Gate Labels Drifted from Contract Thresholds (v20.13)
**Problem:** GOLD_STAR downgrade messages showed wrong gate names (`research_gte_5.5`, `esoteric_gte_4.0`) that didn't match the actual thresholds in `scoring_contract.py` (`research_score: 6.5`, `esoteric_score: 5.5`). This made debugging tier downgrades misleading — operators would think a pick failed at 5.5 when the real gate is 6.5.

**Root Cause:** When `scoring_contract.py` was updated with correct thresholds, the gate label strings in `live_data_router.py` were never updated to match. The labels are just cosmetic strings, so no tests caught the drift:

```python
# live_data_router.py line 5433 — BEFORE (WRONG)
"research_gte_5.5": research_score >= GOLD_STAR_GATES["research_score"],  # Label says 5.5, actual gate is 6.5
"esoteric_gte_4.0": esoteric_score >= GOLD_STAR_GATES["esoteric_score"],  # Label says 4.0, actual gate is 5.5

# AFTER (CORRECT)
"research_gte_6.5": research_score >= GOLD_STAR_GATES["research_score"],  # Label matches threshold
"esoteric_gte_5.5": esoteric_score >= GOLD_STAR_GATES["esoteric_score"],  # Label matches threshold
```

**Additional Drift Found:** Documentation in CLAUDE.md and `docs/MASTER_INDEX.md` also showed old values:
- CLAUDE.md GOLD_STAR table: `research ≥ 5.5` → fixed to `≥ 6.5`
- CLAUDE.md GOLD_STAR table: `esoteric ≥ 4.0` → fixed to `≥ 5.5`
- MASTER_INDEX.md: `research>=5.5, esoteric>=4.0` → fixed to match contract

**Impact:** Misleading debug output. When a pick was downgraded from GOLD_STAR to EDGE_LEAN, the `gold_star_failed_gates` field showed labels like `research_gte_5.5` even though the actual threshold is 6.5. Operators debugging score issues would look at the wrong threshold.

**Prevention:**
1. **NEVER hardcode threshold values in label strings** — derive labels from the contract constants or use generic names like `"research_gate"`
2. **When updating `scoring_contract.py`, grep ALL files for old values** — `grep -rn "5\.5\|4\.0" CLAUDE.md docs/ live_data_router.py | grep -i "gate\|gold_star\|esoteric\|research"`
3. **Add a drift scan for gate labels vs contract** — gate label strings should be validated against `GOLD_STAR_GATES` values
4. **Single source of truth** — `core/scoring_contract.py:GOLD_STAR_GATES` is authoritative; everything else must match

**Files Modified:**
- `live_data_router.py` — Lines 5433, 5435: Fixed gate label strings
- `CLAUDE.md` — GOLD_STAR gate table: Fixed threshold values
- `docs/MASTER_INDEX.md` — Fixed GOLD_STAR gate summary

**Verification:**
```bash
# Verify labels match contract
python3 -c "
from core.scoring_contract import GOLD_STAR_GATES
print('Contract thresholds:')
for k, v in GOLD_STAR_GATES.items():
    print(f'  {k}: {v}')
"
# Should show: research_score: 6.5, esoteric_score: 5.5

# Check live_data_router labels match
grep -n "research_gte\|esoteric_gte" live_data_router.py
# Should show research_gte_6.5 and esoteric_gte_5.5
```

**Fixed in:** v20.13 (Feb 9, 2026) — Commit `33a4a02`

### Active Paid Integrations (v20.12)

| Integration | Purpose | Cost Model | Status |
|-------------|---------|------------|--------|
| **Playbook API** | Sharp money splits, line movement, player game logs | Subscription | ✅ Active |
| **Odds API** | Live odds from 15+ sportsbooks | Subscription | ✅ Active |
| **BallDontLie** | NBA player stats, game data | Subscription | ✅ Active |
| ~~SerpAPI~~ | ~~Google search trends~~ | ~~Per-call~~ | ❌ Canceled |

**Free Integrations (No Cost):**
- ESPN APIs (scores, injuries, officials, schedules)
- NOAA (space weather Kp-index)
- Astronomy calculations (lunar phases, void moon)

**Environment Variables for Paid APIs:**
```bash
PLAYBOOK_API_KEY=xxx      # Required
THE_ODDS_API_KEY=xxx      # Required
BALLDONTLIE_API_KEY=xxx   # Required
SERPAPI_KEY=              # Leave empty (canceled)
```

### Lesson 66: SPORT_STATS Incomplete Coverage (v20.13)
**Problem:** `SchedulerConfig.SPORT_STATS` in `daily_scheduler.py` only defined 3 stat types per sport (e.g., NBA = points, rebounds, assists), but the system supports 7 NBA prop types. The auto grader learning loop was only tracking and adjusting weights for 3 of 7 prop types.

**Root Cause:** When `audit_sport()` iterates over `SchedulerConfig.SPORT_STATS[sport]`, it only audits the stat types listed. Missing stat types (threes, steals, blocks, pra) were never analyzed for bias or weight adjustment.

```python
# BUG — Only 3 stat types audited
SPORT_STATS = {
    "NBA": ["points", "rebounds", "assists"],  # Missing 4 prop types!
    ...
}

# audit_sport() only processes what's listed:
for stat_type in SchedulerConfig.SPORT_STATS.get(sport, ["points"]):
    self._audit_stat_type(sport, stat_type, ...)  # threes, steals, blocks, pra NEVER audited
```

**Impact:**
- Learning loop blind to 4/7 NBA prop types
- No weight adjustments for threes, steals, blocks, pra
- Performance drift on smaller prop markets went undetected

**The Fix (v20.13):**
```python
# FIXED — All 7 NBA prop types now audited
SPORT_STATS = {
    "NBA": ["points", "rebounds", "assists", "threes", "steals", "blocks", "pra"],
    "NFL": ["passing_yards", "rushing_yards", "receiving_yards"],
    "MLB": ["hits", "total_bases", "strikeouts"],
    "NHL": ["points", "shots"],
    "NCAAB": ["points", "rebounds"]
}
```

**Prevention:**
1. **NEVER add prop types to `_initialize_weights()` without adding to `SPORT_STATS`** — they must stay in sync
2. **Verify audit coverage** — run `/live/grader/bias/{sport}?stat_type=X` for ALL prop types after changes
3. **Cross-reference** — `auto_grader.py:prop_stat_types` and `daily_scheduler.py:SPORT_STATS` must match

**Files Modified:**
- `daily_scheduler.py` — Expanded `SPORT_STATS["NBA"]` from 3 to 7 stat types

**Fixed in:** v20.13 (Feb 8, 2026) — Commit `32446c0`

### Lesson 67: Learning Loop Stat Type Sync Invariant (v20.13)
**Problem:** Three separate locations define prop stat types, and they can drift out of sync:
1. `auto_grader.py:_initialize_weights()` — Creates weight entries
2. `auto_grader.py:run_daily_audit()` — Which types get audited (prop_stat_types)
3. `daily_scheduler.py:SchedulerConfig.SPORT_STATS` — Which types the scheduler audits

**Root Cause:** No single source of truth for "which prop stat types exist per sport." Each location was updated independently, leading to gaps.

**The Sync Invariant:**
```
For each sport, these three lists MUST be identical:

1. auto_grader._initialize_weights() prop_stat_types[sport]
2. auto_grader.run_daily_audit() prop_stat_types[sport]
3. daily_scheduler.SchedulerConfig.SPORT_STATS[sport]

If ANY differ, some prop types won't have weights OR won't be audited.
```

**Complete Prop Stat Types (Authoritative):**
| Sport | Stat Types | Count |
|-------|-----------|-------|
| NBA | points, rebounds, assists, threes, steals, blocks, pra | 7 |
| NFL | passing_yards, rushing_yards, receiving_yards, receptions, touchdowns | 5 |
| MLB | hits, runs, rbis, strikeouts, total_bases, walks | 6 |
| NHL | goals, assists, points, shots, saves, blocks | 6 |
| NCAAB | points, rebounds, assists, threes | 4 |

**Verification Command:**
```bash
# Check all three locations are in sync
python3 -c "
from auto_grader import AutoGrader
from daily_scheduler import SchedulerConfig

grader = AutoGrader()
for sport in ['NBA', 'NFL', 'MLB', 'NHL', 'NCAAB']:
    scheduler_stats = set(SchedulerConfig.SPORT_STATS.get(sport, []))
    weight_stats = set(grader.weights.get(sport, {}).keys()) - {'spread', 'total', 'moneyline', 'sharp'}
    if scheduler_stats != weight_stats:
        print(f'MISMATCH {sport}: scheduler={scheduler_stats}, weights={weight_stats}')
    else:
        print(f'OK {sport}: {len(scheduler_stats)} prop types')
"
```

**Prevention:**
1. **ALWAYS update all 3 locations** when adding a new prop stat type
2. **Add sync check to CI** — verify all three lists match before deploy
3. **Consider refactoring** — extract to single `PROP_STAT_TYPES` constant imported by both modules

**NEVER DO (Learning Loop Coverage - rules 213-215):**
- 213: NEVER add a prop type to `_initialize_weights()` without adding to `SPORT_STATS` — creates weights that are never audited
- 214: NEVER add a prop type to `SPORT_STATS` without adding to `_initialize_weights()` — audit fails with missing weights
- 215: NEVER assume "big 3" props (points, rebounds, assists) are sufficient — smaller prop markets (threes, steals, blocks) need learning too

**Fixed in:** v20.13 (Feb 8, 2026)

### Lesson 68: Robust Shell Script Error Handling for Sanity Reports (v20.13)
**Problem:** The daily sanity report script (`scripts/daily_sanity_report.sh`) would fail silently or with cryptic jq parsing errors when an API endpoint returned null, empty, or non-JSON responses. This made it impossible to distinguish between:
1. **Transient API errors** (network issues, backend timeouts, empty data)
2. **Code parsing bugs** (jq syntax errors, missing fields)
3. **Actual data problems** (malformed JSON from backend)

**Root Cause:** The original curl pattern piped output directly to jq without:
- Capturing the HTTP status code
- Capturing the curl exit code
- Validating JSON before parsing
- Preserving raw response for debugging

**The Fix (v20.13):**
```bash
# ROBUST PATTERN — Use temp file to capture response + codes
resp_file=$(mktemp)
http_code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
  "$API_BASE/live/best-bets/$sport?debug=1" \
  -H "X-API-Key: $API_KEY" 2>&1)
curl_rc=$?

resp=$(cat "$resp_file" 2>/dev/null || true)
rm -f "$resp_file"

# Check curl exit code and empty response
if [ $curl_rc -ne 0 ] || [ -z "$resp" ]; then
  echo "$sport: ERROR curl_rc=$curl_rc http_code=$http_code"
  echo "resp_head: $(echo "$resp" | head -c 200)"
  printf "\n"
  continue
fi

# Validate JSON before parsing
if ! echo "$resp" | jq -e . >/dev/null 2>&1; then
  echo "$sport: ERROR non_json http_code=$http_code"
  echo "resp_head: $(echo "$resp" | head -c 200)"
  printf "\n"
  continue
fi

# Now safe to parse with jq
echo "$resp" | jq -r '{ ... }'
```

**Why This Pattern Works:**
1. **Temp file** — Separates response capture from status code extraction (can't do both with pipes)
2. **`-w "%{http_code}"`** — Captures HTTP status even on non-2xx responses
3. **`$?` capture** — Detects network failures, DNS errors, connection refused
4. **`jq -e .`** — Validates JSON without producing output (exit 1 if invalid)
5. **`head -c 200`** — Shows response prefix for debugging without flooding logs

**Diagnosis Flowchart:**
```
curl_rc != 0  → Network/connection error (check DNS, firewall, SSL)
http_code 4xx → Auth failure (check API_KEY) or endpoint not found
http_code 5xx → Backend error (check Railway logs)
non_json      → Backend returned HTML error page or partial response
Empty resp    → Backend returned 204/empty body or connection dropped
```

**Prevention:**
1. **NEVER pipe curl directly to jq** without validating JSON first — `curl ... | jq` hides the real error
2. **ALWAYS capture HTTP code** — A 200 with empty body is different from a 500 with error JSON
3. **ALWAYS capture curl exit code** — Network errors return exit code != 0 but no HTTP code
4. **ALWAYS show response head on error** — First 200 chars reveal HTML error pages, auth failures, etc.

**NEVER DO (Shell Script Error Handling - rules 216-219):**
- 216: NEVER use `curl ... | jq` without JSON validation — jq parse errors hide the real problem
- 217: NEVER assume HTTP 200 means valid data — backend might return `null` or `{}` with 200
- 218: NEVER discard curl exit code — network failures need different diagnosis than API errors
- 219: NEVER log full response on error — use `head -c 200` to avoid flooding logs with huge HTML pages

**Files Modified:**
- `scripts/daily_sanity_report.sh` — Added robust error handling pattern

**Fixed in:** v20.13 (Feb 8, 2026)

### Lesson 69: Grader Routes Require /live Prefix and API Key (v20.14)

**Date:** Feb 8, 2026

**What Happened:**
All 5 grader endpoints returned 404 errors when accessed at paths like `/grader/status`, `/grader/weights/NBA`, etc. After fixing paths, public URL access returned 401 Unauthorized.

**Root Causes:**
1. **Router prefix forgotten**: `live_data_router.py` is mounted with prefix `/live` in `main.py`, so all routes defined as `/grader/...` are actually served at `/live/grader/...`
2. **Auth requirement not documented**: All `/live/*` endpoints require `X-API-Key` header for authentication

**The Fix:**
1. Changed all grader endpoint paths from `/grader/...` to `/live/grader/...`
2. Added `-H "X-API-Key: $API_KEY"` to all curl commands for public URL tests
3. Created comprehensive verification script: `scripts/verify_grader_routes.sh`

**NEVER DO (Grader Routes & Authentication - rules 220-222):**
- 220: NEVER test grader routes without `/live` prefix — routes in `live_data_router.py` are mounted at `/live/*`
- 221: NEVER hit public `/live/*` URLs without `X-API-Key` header — all live endpoints require authentication
- 222: NEVER assume endpoint path matches route decorator — always check how router is mounted in `main.py`

**Correct Grader Endpoints (all require `/live` prefix):**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/live/grader/status` | GET | Grader health check |
| `/live/grader/weights/{sport}` | GET | Current learned weights |
| `/live/grader/bias/{sport}` | GET | Model bias analysis |
| `/live/grader/run-audit` | POST | Trigger learning audit |
| `/live/grader/performance/{sport}` | GET | Historical performance |

**Verification Commands:**
```bash
# Localhost (inside container):
curl http://localhost:8000/live/grader/status

# Public URL (with auth):
curl -H "X-API-Key: $API_KEY" https://web-production-7b2a.up.railway.app/live/grader/status

# Full verification:
./scripts/verify_grader_routes.sh
```

**Files Modified:**
- `scripts/verify_grader_routes.sh` — Comprehensive 6-test verification suite
- `CLAUDE.md` — Added grader endpoints documentation with correct paths

**Fixed in:** v20.14 (Feb 8, 2026)
