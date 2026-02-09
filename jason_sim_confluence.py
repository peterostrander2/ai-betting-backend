"""
JASON SIM CONFLUENCE - Protocol 33 / SIM J420N Engine
=====================================================
v33.01 - Data-driven confluence layer using BallDontLie Elo model

Replaces v11.08 fake Monte Carlo with real BallDontLie API data:
- Elo ratings built from actual NBA game results
- Real player stats for props evaluation via normal distribution model
- Spread-based fallback for non-NBA sports or API failures

RULES (unchanged from v11.08):
- Spread/ML: Boost if pick-side win% >= 61%, downgrade if <= 55%, block if <= 52% AND base_score < 7.2
- Totals: Reduce confidence if variance HIGH, increase if LOW/MED
- Props: Boost only if base_prop_score >= 6.8 AND environment supports the prop type

OUTPUT (must appear on every pick - unchanged from v11.08):
- jason_ran: bool
- jason_sim_boost: float
- jason_blocked: bool
- jason_win_pct_home: float
- jason_win_pct_away: float
- projected_total: float
- projected_pace: str
- variance_flag: str (LOW/MED/HIGH)
- injury_state: str
- confluence_reasons: array

FINAL SCORE = base_score + jason_sim_boost
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import math
import os
import statistics
import time
from datetime import datetime, timedelta, date

logger = logging.getLogger("jason_sim")

# =============================================================================
# CONFIGURATION (unchanged from v11.08)
# =============================================================================

# Win percentage thresholds for spread/ML picks
WIN_PCT_BOOST_THRESHOLD = 61.0    # >= 61% = boost
WIN_PCT_DOWNGRADE_THRESHOLD = 55.0  # <= 55% = downgrade
WIN_PCT_BLOCK_THRESHOLD = 52.0    # <= 52% AND base < 7.2 = block

# Base score threshold for blocking
BASE_SCORE_BLOCK_THRESHOLD = 7.2

# Boost/downgrade amounts
SPREAD_ML_BOOST = 0.8           # Boost when win% >= 61%
SPREAD_ML_DOWNGRADE = -0.5      # Downgrade when win% <= 55%

# Total variance adjustments
TOTAL_HIGH_VARIANCE_PENALTY = -0.4
TOTAL_LOW_VARIANCE_BOOST = 0.3

# Prop requirements
PROP_MIN_BASE_SCORE = 6.8       # Props need >= 6.8 to get Jason boost
PROP_BOOST = 0.5                # Prop boost amount

# =============================================================================
# PROTOCOL 33 CONFIGURATION
# =============================================================================

BASE_URL = "https://api.balldontlie.io"
BDL_API_KEY = (
    os.getenv("BDL_API_KEY", "").strip()
    or os.getenv("BALLDONTLIE_API_KEY", "").strip()
)

# Elo model constants
ELO_HOME_ADV = 65.0
ELO_K_FACTOR = 20.0
ELO_DEFAULT = 1500.0

# Prop stat mapping from Protocol 33
PROP_TO_STAT = {
    "points": "pts", "rebounds": "reb", "assists": "ast",
    "threes": "fg3m", "steals": "stl", "blocks": "blk",
    "turnovers": "turnover",
    "pts+reb": ["pts", "reb"], "pts+ast": ["pts", "ast"],
    "reb+ast": ["reb", "ast"], "pts+reb+ast": ["pts", "reb", "ast"],
    "pra": ["pts", "reb", "ast"],
}

# CV map for season average fallback (Protocol 33)
_SEASON_AVG_CV = {
    "pts": 0.25, "reb": 0.30, "ast": 0.35, "fg3m": 0.45,
    "stl": 0.50, "blk": 0.55, "turnover": 0.35,
}

# =============================================================================
# PROTOCOL 33 API CLIENT (graceful — never raises SystemExit)
# =============================================================================

def _bdl_headers() -> Dict[str, str]:
    """Get BallDontLie API headers."""
    if not BDL_API_KEY:
        return {}
    return {"Authorization": BDL_API_KEY}


def _bdl_get_json(
    path: str, params: Optional[Dict] = None, timeout: float = 8.0
) -> Optional[Dict]:
    """
    GET request to BallDontLie API with retry/backoff.
    Returns None on any failure — never raises.
    """
    if not BDL_API_KEY:
        return None

    try:
        import requests as _requests
    except ImportError:
        logger.warning("requests library not available for BDL API")
        return None

    headers = _bdl_headers()
    # Try both /nba/ prefixed and direct paths (Protocol 33 pattern)
    candidate_paths = [path]
    if path.startswith("/nba/"):
        candidate_paths.append(path.replace("/nba/", "/", 1))
    elif not path.startswith("/nba/"):
        candidate_paths.append(f"/nba{path}")

    for try_path in candidate_paths:
        url = f"{BASE_URL}{try_path}"
        for attempt in range(3):
            try:
                resp = _requests.get(
                    url, headers=headers, params=params or {}, timeout=timeout
                )
                if resp.status_code in (401, 403):
                    logger.warning("BDL API auth error %d on %s", resp.status_code, try_path)
                    return None
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.debug("BDL rate limited, waiting %ds", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code == 404:
                    break  # Try next candidate path
                if resp.status_code >= 400:
                    if attempt < 2:
                        time.sleep(1)
                        continue
                    return None
                return resp.json()
            except _requests.RequestException as e:
                logger.debug("BDL request failed (attempt %d): %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                continue
            except (SystemExit, KeyboardInterrupt):
                logger.warning("BDL API caught SystemExit/KeyboardInterrupt, returning None")
                return None
            except Exception as e:
                logger.debug("BDL API unexpected error: %s", e)
                return None
    return None


def _bdl_paged_get_all(
    path: str, params: Optional[Dict] = None, max_pages: int = 8
) -> List[Dict]:
    """Paginated GET for BallDontLie. Returns empty list on failure."""
    all_data: List[Dict] = []
    cursor = None
    for _ in range(max_pages):
        p = dict(params or {})
        if cursor:
            p["cursor"] = str(cursor)
        result = _bdl_get_json(path, p)
        if not result:
            break
        data = result.get("data", [])
        if isinstance(data, list):
            all_data.extend(data)
        meta = result.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break
    return all_data


# =============================================================================
# PROTOCOL 33 ELO MODEL
# =============================================================================

def protocol33_team_win_prob(
    home_elo: float, away_elo: float, home_adv: float = ELO_HOME_ADV
) -> float:
    """Calculate home win probability from Elo ratings (Protocol 33)."""
    diff = (home_elo + home_adv) - away_elo
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def margin_from_prob(p_home: float) -> float:
    """Convert win probability to expected point margin (Protocol 33)."""
    return (p_home - 0.5) * 30.0


def build_team_elos_from_history(
    finals: List[Dict], k: float = ELO_K_FACTOR
) -> Dict[int, float]:
    """Build Elo ratings from finished game history (Protocol 33)."""
    elos: Dict[int, float] = {}
    for g in finals:
        h_team = g.get("home_team") or {}
        a_team = g.get("visitor_team") or {}
        h_id = h_team.get("id")
        a_id = a_team.get("id")
        h_score = g.get("home_team_score", 0) or 0
        a_score = g.get("visitor_team_score", 0) or 0
        if not h_id or not a_id or h_score == 0 or a_score == 0:
            continue

        h_elo = elos.get(h_id, ELO_DEFAULT)
        a_elo = elos.get(a_id, ELO_DEFAULT)

        expected_h = protocol33_team_win_prob(h_elo, a_elo, ELO_HOME_ADV)
        actual_h = 1.0 if h_score > a_score else 0.0

        # MOV factor from Protocol 33
        mov = abs(h_score - a_score)
        mov_factor = max(1.0, math.log(mov + 1))

        delta = k * mov_factor * (actual_h - expected_h)
        elos[h_id] = h_elo + delta
        elos[a_id] = a_elo - delta

    return elos


# =============================================================================
# PROTOCOL 33 MATH HELPERS
# =============================================================================

def normal_cdf(x: float) -> float:
    """Standard normal CDF (Protocol 33)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def prob_over_normal(mu: float, sigma: float, line: float) -> float:
    """P(X > line) using normal distribution (Protocol 33)."""
    if sigma <= 0:
        return 1.0 if mu > line else 0.0
    z = (mu - line) / sigma
    return 1.0 - normal_cdf(z)


# =============================================================================
# DATA CACHES (per-day, module-level)
# =============================================================================

_elo_cache: Dict[str, Any] = {"date": None, "elos": {}, "team_map": {}}
_player_id_cache: Dict[str, Optional[int]] = {}
_player_stats_cache: Dict[str, List[Dict]] = {}


def _get_current_season() -> int:
    """Get current NBA season year (season starts in October)."""
    now = datetime.now()
    return now.year if now.month >= 10 else now.year - 1


def _build_elo_ratings() -> Tuple[Dict[int, float], Dict[int, str]]:
    """Build or return cached Elo ratings from season history."""
    today = date.today().isoformat()
    if _elo_cache["date"] == today and _elo_cache["elos"]:
        return _elo_cache["elos"], _elo_cache["team_map"]

    season = _get_current_season()
    all_games = _bdl_paged_get_all(
        "/nba/v1/games",
        params={"seasons[]": str(season), "per_page": "100"},
    )
    if not all_games:
        logger.info("No BDL game history available for Elo — will use spread fallback")
        return {}, {}

    finals = [g for g in all_games if g.get("status") == "Final"]
    if not finals:
        return {}, {}

    elos = build_team_elos_from_history(finals)

    # Build team_id -> team_name map
    team_map: Dict[int, str] = {}
    for g in all_games:
        for key in ("home_team", "visitor_team"):
            t = g.get(key) or {}
            if t.get("id"):
                team_map[t["id"]] = t.get("full_name", t.get("name", ""))

    _elo_cache["date"] = today
    _elo_cache["elos"] = elos
    _elo_cache["team_map"] = team_map
    logger.info(
        "Protocol 33: Built Elo ratings for %d teams from %d finished games",
        len(elos), len(finals),
    )
    return elos, team_map


def _find_team_id(team_name: str, team_map: Dict[int, str]) -> Optional[int]:
    """Find team ID from name using fuzzy matching."""
    name_lower = team_name.lower().strip()

    # Exact substring match
    for tid, tname in team_map.items():
        if name_lower in tname.lower() or tname.lower() in name_lower:
            return tid

    # Partial match on last word (e.g., "Lakers" in "Los Angeles Lakers")
    parts = name_lower.split()
    if parts:
        last_word = parts[-1]
        for tid, tname in team_map.items():
            if last_word in tname.lower():
                return tid
    return None


# =============================================================================
# PROTOCOL 33 PLAYER STATS HELPERS
# =============================================================================

def _find_player_id(player_name: str) -> Optional[int]:
    """Find BDL player ID by name. Cached per session."""
    if not player_name or not BDL_API_KEY:
        return None

    cache_key = player_name.lower().strip()
    if cache_key in _player_id_cache:
        return _player_id_cache[cache_key]

    parts = player_name.strip().split()
    search_term = parts[-1] if parts else player_name
    result = _bdl_get_json(
        "/nba/v1/players/active", params={"search": search_term, "per_page": "25"}
    )
    if not result or not result.get("data"):
        _player_id_cache[cache_key] = None
        return None

    name_lower = player_name.lower()
    for p in result["data"]:
        full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower()
        if name_lower in full_name or full_name in name_lower:
            pid = p.get("id")
            _player_id_cache[cache_key] = pid
            return pid

    # First result as fallback
    pid = result["data"][0].get("id")
    _player_id_cache[cache_key] = pid
    return pid


def _fetch_player_recent_stats(player_id: int) -> List[Dict]:
    """Fetch recent game stats for a player. Cached per session."""
    cache_key = f"{player_id}_{_get_current_season()}"
    if cache_key in _player_stats_cache:
        return _player_stats_cache[cache_key]

    data = _bdl_paged_get_all(
        "/nba/v1/stats",
        params={
            "player_ids[]": str(player_id),
            "seasons[]": str(_get_current_season()),
            "per_page": "25",
        },
        max_pages=2,
    )
    _player_stats_cache[cache_key] = data
    return data


def _extract_stat(game_log: Dict, stat_key) -> Optional[float]:
    """Extract stat value from game log entry (Protocol 33)."""
    if isinstance(stat_key, list):
        total = 0.0
        for k in stat_key:
            v = game_log.get(k)
            if v is None:
                return None
            total += float(v)
        return total
    v = game_log.get(stat_key)
    return float(v) if v is not None else None


def _calc_mu_sigma_from_logs(values: List[float]) -> Optional[Tuple[float, float]]:
    """Calculate mean and std from game logs. Needs >= 4 values (Protocol 33)."""
    if len(values) < 4:
        return None
    mu = statistics.mean(values)
    sigma = max(1.0, statistics.stdev(values))
    return mu, sigma


# =============================================================================
# JASON SIM CLASS (Protocol 33 powered)
# =============================================================================

class JasonSimConfluence:
    """
    Jason Simulation Confluence Engine.
    v33.01 - Powered by Protocol 33 / SIM J420N Elo model.

    Uses real BallDontLie API data for NBA games.
    Falls back to spread-based estimation for non-NBA or when API unavailable.
    """

    def __init__(self):
        self.VERSION = "33.01"
        logger.info("JasonSimConfluence v%s (Protocol 33) initialized", self.VERSION)

    def _get_elo_win_prob(
        self, home_team: str, away_team: str
    ) -> Optional[Dict[str, Any]]:
        """Get Elo-based win probability for a matchup. Returns None on failure."""
        try:
            elos, team_map = _build_elo_ratings()
            if not elos:
                return None

            home_id = _find_team_id(home_team, team_map)
            away_id = _find_team_id(away_team, team_map)
            if not home_id or not away_id:
                logger.debug(
                    "Team ID lookup failed: %s=%s, %s=%s",
                    home_team, home_id, away_team, away_id,
                )
                return None

            home_elo = elos.get(home_id, ELO_DEFAULT)
            away_elo = elos.get(away_id, ELO_DEFAULT)
            p_home = protocol33_team_win_prob(home_elo, away_elo)
            margin = margin_from_prob(p_home)

            return {
                "home_win_pct": round(p_home * 100, 1),
                "away_win_pct": round((1.0 - p_home) * 100, 1),
                "home_elo": round(home_elo, 1),
                "away_elo": round(away_elo, 1),
                "expected_margin": round(margin, 1),
                "source": "protocol33_elo",
            }
        except Exception as e:
            logger.debug("Elo win prob failed: %s", e)
            return None

    def _estimate_from_spread(
        self, spread: float, total: float
    ) -> Dict[str, Any]:
        """Fallback: estimate win probability from spread (non-NBA or API failure)."""
        spread_prob = 0.5 + (spread / -20.0)
        spread_prob = max(0.25, min(0.75, spread_prob))

        home_win_pct = round(spread_prob * 100, 1)
        away_win_pct = round((1.0 - spread_prob) * 100, 1)
        home_cover_pct = round(home_win_pct * 0.9, 1)
        away_cover_pct = round(away_win_pct * 0.9, 1)

        return {
            "home_win_pct": home_win_pct,
            "away_win_pct": away_win_pct,
            "home_cover_pct": home_cover_pct,
            "away_cover_pct": away_cover_pct,
            "projected_total": round(total, 1),
            "projected_pace": "NEUTRAL",
            "variance_flag": "MED",
            "total_std": 15.0,
            "num_sims": 0,
            "source": "spread_estimate",
        }

    def simulate_game(
        self,
        home_team: str,
        away_team: str,
        spread: float = 0,
        total: float = 220,
        home_implied_prob: float = 0.5,
        injury_impact: float = 0,
        num_sims: int = 0,
    ) -> Dict[str, Any]:
        """
        Get game probabilities using Protocol 33 Elo model.
        Falls back to spread-based estimation if API unavailable.
        """
        # Try Protocol 33 Elo model first
        elo_result = self._get_elo_win_prob(home_team, away_team)

        if elo_result:
            home_win_pct = elo_result["home_win_pct"]
            away_win_pct = elo_result["away_win_pct"]
            margin = elo_result["expected_margin"]

            # Derive cover percentages from margin vs spread
            cover_edge = (margin - (-spread)) / 20.0
            home_cover_pct = max(20.0, min(80.0, 50.0 + cover_edge * 100))
            away_cover_pct = 100.0 - home_cover_pct

            # Projected total from Elo margin (small adjustment)
            projected_total = total + (margin * 0.1)

            # Determine variance from margin magnitude
            abs_margin = abs(margin)
            if abs_margin > 10:
                variance_flag = "LOW"
                total_std = 10.0
            elif abs_margin < 3:
                variance_flag = "HIGH"
                total_std = 19.5
            else:
                variance_flag = "MED"
                total_std = 15.0

            # Determine pace
            if projected_total > total + 5:
                projected_pace = "FAST"
            elif projected_total < total - 5:
                projected_pace = "SLOW"
            else:
                projected_pace = "NEUTRAL"

            return {
                "home_win_pct": home_win_pct,
                "away_win_pct": away_win_pct,
                "home_cover_pct": round(home_cover_pct, 1),
                "away_cover_pct": round(away_cover_pct, 1),
                "projected_total": round(projected_total, 1),
                "projected_pace": projected_pace,
                "variance_flag": variance_flag,
                "total_std": round(total_std, 2),
                "num_sims": 0,
                "source": "protocol33_elo",
            }

        # Fallback to spread-based estimation
        return self._estimate_from_spread(spread, total)

    def evaluate_spread_ml(
        self,
        base_score: float,
        pick_side: str,
        home_team: str,
        away_team: str,
        sim_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate spread/ML picks using Elo-derived probabilities.
        Same threshold logic as v11.08.
        """
        reasons: List[str] = []
        boost = 0.0
        blocked = False

        pick_is_home = (
            pick_side.lower() in home_team.lower()
            or "home" in pick_side.lower()
        )

        if pick_is_home:
            pick_win_pct = sim_results["home_win_pct"]
            pick_cover_pct = sim_results.get("home_cover_pct", 50.0)
        else:
            pick_win_pct = sim_results["away_win_pct"]
            pick_cover_pct = sim_results.get("away_cover_pct", 50.0)

        source = sim_results.get("source", "unknown")

        if pick_win_pct >= WIN_PCT_BOOST_THRESHOLD:
            boost = SPREAD_ML_BOOST
            reasons.append(
                f"Jason BOOST: Pick-side win% {pick_win_pct}% >= "
                f"{WIN_PCT_BOOST_THRESHOLD}% ({source})"
            )
        elif (
            pick_win_pct <= WIN_PCT_BLOCK_THRESHOLD
            and base_score < BASE_SCORE_BLOCK_THRESHOLD
        ):
            blocked = True
            boost = -1.5
            reasons.append(
                f"Jason BLOCK: Win% {pick_win_pct}% <= {WIN_PCT_BLOCK_THRESHOLD}% "
                f"AND base {base_score} < {BASE_SCORE_BLOCK_THRESHOLD} ({source})"
            )
        elif pick_win_pct <= WIN_PCT_DOWNGRADE_THRESHOLD:
            boost = SPREAD_ML_DOWNGRADE
            reasons.append(
                f"Jason DOWNGRADE: Pick-side win% {pick_win_pct}% <= "
                f"{WIN_PCT_DOWNGRADE_THRESHOLD}% ({source})"
            )
        else:
            reasons.append(
                f"Jason NEUTRAL: Pick-side win% {pick_win_pct}% in normal range ({source})"
            )

        return {
            "boost": boost,
            "blocked": blocked,
            "pick_win_pct": pick_win_pct,
            "pick_cover_pct": pick_cover_pct,
            "reasons": reasons,
        }

    def evaluate_total(
        self,
        base_score: float,
        pick_side: str,
        total_line: float,
        sim_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate total picks using Elo-derived projections.
        Same threshold logic as v11.08.
        """
        reasons: List[str] = []
        boost = 0.0
        blocked = False

        variance = sim_results["variance_flag"]
        projected = sim_results["projected_total"]

        pick_is_over = pick_side.lower() == "over"
        projection_agrees = (pick_is_over and projected > total_line) or (
            not pick_is_over and projected < total_line
        )

        if variance == "HIGH":
            boost = TOTAL_HIGH_VARIANCE_PENALTY
            reasons.append(
                f"Jason PENALTY: High variance "
                f"({sim_results.get('total_std', 0)} std) on total"
            )
        elif variance in ["LOW", "MED"] and projection_agrees:
            boost = TOTAL_LOW_VARIANCE_BOOST
            diff = abs(projected - total_line)
            reasons.append(
                f"Jason BOOST: {variance} variance, projection {projected} "
                f"{'>' if pick_is_over else '<'} line {total_line} (diff: {diff:.1f})"
            )
        else:
            reasons.append(
                f"Jason NEUTRAL: Variance {variance}, "
                f"projection {projected} vs line {total_line}"
            )

        return {
            "boost": boost,
            "blocked": blocked,
            "projection_agrees": projection_agrees,
            "reasons": reasons,
        }

    def evaluate_prop(
        self,
        base_score: float,
        player_name: str,
        prop_type: str,
        prop_line: float,
        sim_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate prop picks.
        Enhanced with Protocol 33 player stats model when BDL data available.
        Falls back to v11.08 pace-based evaluation.
        """
        reasons: List[str] = []
        boost = 0.0
        blocked = False

        pace = sim_results["projected_pace"]
        variance = sim_results["variance_flag"]

        if base_score < PROP_MIN_BASE_SCORE:
            reasons.append(
                f"Jason SKIP: Prop base score {base_score} < "
                f"{PROP_MIN_BASE_SCORE} threshold"
            )
            return {"boost": 0.0, "blocked": False, "reasons": reasons}

        # Try Protocol 33 player stats model for NBA props
        p33_result = self._evaluate_prop_with_stats(
            player_name, prop_type, prop_line
        )
        if p33_result is not None:
            return p33_result

        # Fallback to pace-based evaluation (same as v11.08)
        scoring_props = [
            "points", "pts", "yards", "passing", "rushing",
            "receiving", "goals", "shots",
        ]
        is_scoring_prop = any(sp in prop_type.lower() for sp in scoring_props)

        volume_props = ["rebounds", "assists", "rebs", "asts", "saves"]
        is_volume_prop = any(vp in prop_type.lower() for vp in volume_props)

        if is_scoring_prop and pace == "FAST":
            boost = PROP_BOOST
            reasons.append(
                f"Jason BOOST: {prop_type} prop + FAST pace environment"
            )
        elif is_volume_prop and pace in ["SLOW", "NEUTRAL"]:
            boost = PROP_BOOST * 0.75
            reasons.append(
                f"Jason BOOST: {prop_type} prop + {pace} pace favors volume"
            )
        elif variance == "LOW":
            boost = PROP_BOOST * 0.5
            reasons.append("Jason BOOST: LOW variance game favors prop consistency")
        else:
            reasons.append(
                f"Jason NEUTRAL: {prop_type} prop, {pace} pace, {variance} variance"
            )

        return {"boost": boost, "blocked": blocked, "reasons": reasons}

    def _evaluate_prop_with_stats(
        self, player_name: str, prop_type: str, prop_line: float
    ) -> Optional[Dict[str, Any]]:
        """
        Use Protocol 33 normal-distribution model for prop evaluation.
        Returns None if data unavailable (triggers pace-based fallback).
        """
        if not BDL_API_KEY or not player_name or prop_line <= 0:
            return None

        try:
            player_id = _find_player_id(player_name)
            if not player_id:
                return None

            # Resolve stat key from prop type
            prop_lower = prop_type.lower().strip()
            stat_key = PROP_TO_STAT.get(prop_lower)
            if not stat_key:
                for pname, skey in PROP_TO_STAT.items():
                    if pname in prop_lower or prop_lower in pname:
                        stat_key = skey
                        break
            if not stat_key:
                return None

            # Fetch recent game logs
            game_logs = _fetch_player_recent_stats(player_id)
            if not game_logs:
                return None

            # Extract stat values from game logs
            values: List[float] = []
            for log in game_logs:
                v = _extract_stat(log, stat_key)
                if v is not None:
                    values.append(v)

            result = _calc_mu_sigma_from_logs(values)
            if not result:
                return None

            mu, sigma = result
            p_over = prob_over_normal(mu, sigma, prop_line)

            reasons: List[str] = []
            boost = 0.0

            if p_over >= 0.60:
                boost = PROP_BOOST
                reasons.append(
                    f"Jason P33 BOOST: {player_name} {prop_type} "
                    f"\u03bc={mu:.1f} \u03c3={sigma:.1f} "
                    f"P(>{prop_line})={p_over:.0%}"
                )
            elif p_over <= 0.35:
                boost = -0.3
                reasons.append(
                    f"Jason P33 FADE: {player_name} {prop_type} "
                    f"\u03bc={mu:.1f} \u03c3={sigma:.1f} "
                    f"P(>{prop_line})={p_over:.0%}"
                )
            else:
                reasons.append(
                    f"Jason P33 NEUTRAL: {player_name} {prop_type} "
                    f"\u03bc={mu:.1f} \u03c3={sigma:.1f} "
                    f"P(>{prop_line})={p_over:.0%}"
                )

            return {"boost": boost, "blocked": False, "reasons": reasons}

        except Exception as e:
            logger.debug("P33 prop stats failed for %s: %s", player_name, e)
            return None

    def run_confluence(
        self,
        base_score: float,
        pick_type: str,
        pick_side: str,
        home_team: str,
        away_team: str,
        spread: float = 0,
        total: float = 220,
        prop_line: float = 0,
        player_name: str = "",
        injury_state: str = "CONFIRMED_ONLY",
    ) -> Dict[str, Any]:
        """
        Run full Jason Sim Confluence for a pick.
        Same signature and output contract as v11.08.
        """
        # Get game probabilities (Elo model or spread fallback)
        sim_results = self.simulate_game(
            home_team=home_team,
            away_team=away_team,
            spread=spread,
            total=total,
        )

        # Normalize pick_type (unchanged from v11.08)
        normalized_type = pick_type.upper()
        type_mapping = {
            "SPREAD": "SPREAD",
            "SPREADS": "SPREAD",
            "ML": "SPREAD_ML",
            "MONEYLINE": "SPREAD_ML",
            "H2H": "SPREAD_ML",
            "TOTAL": "TOTAL",
            "TOTALS": "TOTAL",
            "PROP": "PROP",
            "PLAYER_PROP": "PROP",
            "SHARP": "SPREAD" if spread != 0 else "SPREAD_ML",
            "SHARP_MONEY": "SPREAD" if spread != 0 else "SPREAD_ML",
        }
        canonical_type = type_mapping.get(normalized_type, "SPREAD_ML")

        # Evaluate based on canonical pick type
        if canonical_type in ["SPREAD", "SPREAD_ML"]:
            eval_result = self.evaluate_spread_ml(
                base_score=base_score,
                pick_side=pick_side,
                home_team=home_team,
                away_team=away_team,
                sim_results=sim_results,
            )
        elif canonical_type == "TOTAL":
            eval_result = self.evaluate_total(
                base_score=base_score,
                pick_side=pick_side,
                total_line=total,
                sim_results=sim_results,
            )
        elif canonical_type == "PROP":
            eval_result = self.evaluate_prop(
                base_score=base_score,
                player_name=player_name,
                prop_type=pick_side,
                prop_line=prop_line,
                sim_results=sim_results,
            )
        else:
            eval_result = self.evaluate_spread_ml(
                base_score=base_score,
                pick_side=pick_side,
                home_team=home_team,
                away_team=away_team,
                sim_results=sim_results,
            )

        # Build final output (same contract as v11.08)
        jason_sim_boost = eval_result["boost"]
        final_score = base_score + jason_sim_boost

        return {
            # Required fields (output contract — unchanged from v11.08)
            "jason_ran": True,
            "jason_sim_available": True,
            "jason_sim_boost": round(jason_sim_boost, 2),
            "jason_blocked": eval_result.get("blocked", False),
            "jason_win_pct_home": sim_results["home_win_pct"],
            "jason_win_pct_away": sim_results["away_win_pct"],
            "projected_total": sim_results["projected_total"],
            "projected_pace": sim_results["projected_pace"],
            "variance_flag": sim_results["variance_flag"],
            "injury_state": injury_state,
            "sim_count": sim_results.get("num_sims", 0),
            "confluence_reasons": eval_result["reasons"],
            # Additional fields
            "home_cover_pct": sim_results.get("home_cover_pct", 50.0),
            "away_cover_pct": sim_results.get("away_cover_pct", 50.0),
            "total_std": sim_results.get("total_std", 15.0),
            "num_sims": sim_results.get("num_sims", 0),
            # Computed final
            "base_score": round(base_score, 2),
            "final_score_with_jason": round(final_score, 2),
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_jason_instance: Optional[JasonSimConfluence] = None


def get_jason_sim() -> JasonSimConfluence:
    """Get singleton Jason Sim instance."""
    global _jason_instance
    if _jason_instance is None:
        _jason_instance = JasonSimConfluence()
    return _jason_instance


# =============================================================================
# PUBLIC API (unchanged signatures from v11.08)
# =============================================================================


def run_jason_confluence(
    base_score: float,
    pick_type: str,
    pick_side: str,
    home_team: str,
    away_team: str,
    spread: float = 0,
    total: float = 220,
    prop_line: float = 0,
    player_name: str = "",
    injury_state: str = "CONFIRMED_ONLY",
) -> Dict[str, Any]:
    """
    Convenience function to run Jason confluence.
    Same signature as v11.08 for backward compatibility.

    Usage:
        jason_result = run_jason_confluence(
            base_score=7.5,
            pick_type="SPREAD",
            pick_side="Lakers -4.5",
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            spread=-4.5
        )
        final_score = base_score + jason_result["jason_sim_boost"]
    """
    try:
        jason = get_jason_sim()
        return jason.run_confluence(
            base_score=base_score,
            pick_type=pick_type,
            pick_side=pick_side,
            home_team=home_team,
            away_team=away_team,
            spread=spread,
            total=total,
            prop_line=prop_line,
            player_name=player_name,
            injury_state=injury_state,
        )
    except SystemExit:
        # Protocol 33 API patterns may raise SystemExit — catch and degrade
        logger.warning("Jason Sim caught SystemExit from API client, returning default")
        result = get_default_jason_output()
        result["confluence_reasons"] = ["Jason API error (SystemExit caught)"]
        return result
    except Exception as e:
        logger.warning("Jason Sim failed: %s", e)
        result = get_default_jason_output()
        result["confluence_reasons"] = [f"Jason error: {type(e).__name__}"]
        return result


def get_default_jason_output() -> Dict[str, Any]:
    """
    Get default Jason output when Jason doesn't run.
    Ensures jason_* fields always exist even on error.
    Same output as v11.08.
    """
    return {
        "jason_ran": False,
        "jason_sim_available": False,
        "jason_sim_boost": 0.0,
        "jason_blocked": False,
        "jason_win_pct_home": 50.0,
        "jason_win_pct_away": 50.0,
        "projected_total": 220.0,
        "projected_pace": "NEUTRAL",
        "variance_flag": "MED",
        "injury_state": "CONFIRMED_ONLY",
        "sim_count": 0,
        "confluence_reasons": ["Jason did not run"],
        "base_score": 0.0,
        "final_score_with_jason": 0.0,
    }
