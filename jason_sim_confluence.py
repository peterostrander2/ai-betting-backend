# PROTOCOL 33 / SIM J420N — NBA (Ball Don't Lie) — VALUE + PROPS EDITION
# - Pull today's (or specified) NBA slate
# - Pull odds via /nba/v2/odds (with /v2 fallback)
# - Pull player props via /nba/v2/odds/player_props?game_id=... (with /v2 fallback)
# - Rank +EV bets, "sharp-ish" discrepancies, and arb (moneyline) when possible
# - Add per-game high-chance, positive-EV player props (de-cluttered)

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Output controls
VERBOSE = False          # broad diagnostics
DEBUG_PROPS = False      # extra detail for live props requests

import requests


# -----------------------------
# Vendor configuration (global)
# -----------------------------
# Odds feeds can include prediction markets (e.g., polymarket).
# We default to sportsbooks only for Protocol 33 / SIM J420N outputs.
SPORTSBOOK_VENDORS = {
    'bet365','betmgm','ballybet','betrivers','betparx','betway','caesars','draftkings','fanduel','fanatics',
    'pointsbet','unibet','wynnbet','barstool','pinnacle',
}
SPORTSBOOK_VENDORS = {str(v).lower() for v in SPORTSBOOK_VENDORS}

# =========================
# API KEY ()
# =========================
API_KEY = (os.getenv("BDL_API_KEY", "").strip() or os.getenv("API_KEY", "").strip())

# =========================
# Sportsbook/vendor filter
# =========================
# NOTE: The BallDontLie props endpoint is LIVE-only and may return empty pregame or near game end.
# We'll still run, but we will (a) filter odds by allowed books and (b) gracefully handle missing props.

DEFAULT_VENDOR_ALLOW = {"fanduel", "draftkings"}
VENDOR_ALLOW = {
    v.strip().lower()
    for v in os.getenv(
        "VENDOR_ALLOW",
        ",".join(sorted(DEFAULT_VENDOR_ALLOW))
    ).split(",")
    if v.strip()
}

# Back-compat: earlier builds referenced vendor_allow
VENDOR_ALLOW = VENDOR_ALLOW & SPORTSBOOK_VENDORS
if not VENDOR_ALLOW:
    VENDOR_ALLOW = set(DEFAULT_VENDOR_ALLOW)
# Back-compat: earlier builds referenced vendor_allow
vendor_allow = VENDOR_ALLOW


BASE_URL = "https://api.balldontlie.io"
NBA_GAMES_V1 = "/nba/v1/games"
NBA_ODDS_V2 = "/nba/v2/odds"
NBA_PLAYER_PROPS_V2 = "/nba/v2/odds/player_props"
NBA_STATS_V1 = "/nba/v1/stats"  # for recent game logs (batchable)
# NOTE: Season averages endpoints have multiple shapes; this legacy path is kept for back-compat.
NBA_SEASON_AVGS_V1 = "/nba/v1/season_averages"  # fallback if stats missing

# Roster / lineup / injury endpoints
NBA_ACTIVE_PLAYERS_V1 = "/nba/v1/players/active"
NBA_PLAYER_INJURIES_V1 = "/nba/v1/player_injuries"
NBA_LINEUPS_V1 = "/nba/v1/lineups"



# -------------------------
# Helpers
# -------------------------

def hdrs() -> Dict[str, str]:
    # Prefer env var so you never have to hardcode your key into this file.
    api_key = (os.getenv("BDL_API_KEY", "").strip() or API_KEY)
    if not api_key or "PASTE_YOUR" in api_key:
        raise SystemExit("Set BDL_API_KEY environment variable (recommended), or set API_KEY near the top of this file.")
    return {"Authorization": api_key}

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None

def american_to_decimal(odds: Any) -> Optional[float]:
    """
    Converts American odds to decimal.
    Accepts int/float/str. Returns None if not parseable.
    """
    o = safe_float(odds)
    if o is None:
        return None
    # some feeds may already be decimal; heuristically treat 1.01..100 as decimal
    if 1.01 <= o <= 100 and abs(o) < 100:
        # ambiguous; but in our BDL odds/props examples, american is typically >=100 abs.
        # if it's close to common decimal range and not an integer-like american, keep as decimal.
        # If it's exactly 2.0 etc, accept as decimal.
        return float(o)
    if o == 0:
        return None
    if o > 0:
        return 1.0 + (o / 100.0)
    return 1.0 + (100.0 / abs(o))

def decimal_to_american(dec: float) -> Optional[int]:
    if dec <= 1.0:
        return None
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100))
    return int(round(-100.0 / (dec - 1.0)))

def implied_prob_from_decimal(dec: float) -> float:
    return 1.0 / dec if dec and dec > 0 else 0.0

def devig_two_way(dec_a: Optional[float], dec_b: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    """
    Simple two-way de-vig from two prices.
    Returns probabilities that sum to 1.
    """
    if not dec_a or not dec_b:
        return None, None
    pa = 1.0 / dec_a
    pb = 1.0 / dec_b
    s = pa + pb
    if s <= 0:
        return None, None
    return pa / s, pb / s

def normal_cdf(z: float) -> float:
    # standard normal CDF via erf
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def prob_over_normal(mu: float, sigma: float, line: float) -> float:
    if sigma <= 1e-9:
        return 1.0 if mu > line else 0.0
    z = (line - mu) / sigma
    # P(X > line) = 1 - CDF((line - mu)/sigma)
    return 1.0 - normal_cdf(z)

def pause(msg: str = "\
Press ENTER to close...") -> None:
    try:
        input(msg)
    except Exception:
        pass

def _candidate_paths(path: str) -> List[str]:
    """
    BALLDONTLIE has historically exposed some endpoints both with and without the /nba prefix.
    The NBA docs show core endpoints at /v1/* and betting odds/props at /nba/v2/*.
    To be resilient, we try a small set of compatible path variants.
    """
    cands: List[str] = []
    def add(p: str) -> None:
        if p not in cands:
            cands.append(p)

    add(path)

    # /nba/* -> /* (and vice-versa)
    if path.startswith("/nba/"):
        add(path.replace("/nba/", "/", 1))
    if path.startswith("/v1/") or path.startswith("/v2/"):
        add("/nba" + path)

    # common odds path fix (/nba/v2/odds -> /v2/odds)
    if path.startswith("/nba/v2/"):
        add(path.replace("/nba/v2/", "/v2/", 1))
    if path.startswith("/v2/"):
        add(path.replace("/v2/", "/nba/v2/", 1))

    return cands


def _normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Some BALLDONTLIE docs/examples use array-style keys like team_ids[] / game_ids[] / dates[].
    The OpenAPI spec sometimes uses team_ids / game_ids / dates (no brackets) with an array schema.
    To maximize compatibility, we send BOTH forms when we see a list/tuple OR a bracketed key.
    """
    out: Dict[str, Any] = dict(params)
    for k, v in list(params.items()):
        if k.endswith("[]"):
            base = k[:-2]
            if base not in out:
                out[base] = v
        else:
            if isinstance(v, (list, tuple)) and (k + "[]") not in out:
                out[k + "[]"] = v
    return out


def get_json(path: str, params: Dict[str, Any], timeout: int = 20) -> Dict[str, Any]:
    """
    GET JSON from BallDontLie with:
      - automatic path fallbacks (/nba prefix differences; odds path fix)
      - simple retry/backoff for 429/5xx
    """
    last_err: Optional[str] = None
    for pth in _candidate_paths(path):
        url = BASE_URL + pth
        # retry loop per-path
        backoff = 0.75
        for attempt in range(4):
            headers = hdrs()
            # Encourage fresh data from edge caches / proxies (requests itself does not cache).
            headers.update({
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            })
            r = requests.get(url, headers=headers, params=_normalize_params(params), timeout=timeout)
            if r.status_code < 400:
                return r.json()

            # Tier/auth issues: don't keep retrying
            if r.status_code in (401, 403):
                raise SystemExit(
                    f"HTTP {r.status_code} for {pth}. Check API key and tier access. Response: {r.text}"
                )

            # Not found: try next candidate path
            if r.status_code == 404:
                last_err = f"HTTP 404 for {pth}: {r.text}"
                break

            # Rate limiting / transient server errors
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {r.status_code} for {pth}: {r.text}"
                if attempt < 3:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                break

            # Other errors: surface immediately
            raise SystemExit(f"HTTP {r.status_code} for {pth}: {r.text}")

    raise SystemExit(
        f"All candidate paths failed for request '{path}'. Last error: {last_err}"
    )

def paged_get_all(path: str, params: Dict[str, Any], max_pages: int = 8, timeout: int = 20) -> List[Dict[str, Any]]:
    """
    Cursor-paginated fetch. BDL uses cursor+per_page meta.
    """
    out: List[Dict[str, Any]] = []
    cursor = params.get("cursor", None)
    for _ in range(max_pages):
        p = dict(params)
        if cursor is not None:
            p["cursor"] = cursor
        js = get_json(path, p, timeout=timeout)
        data = js.get("data", []) or []
        out.extend(data)
        meta = js.get("meta", {}) or {}
        next_cursor = meta.get("next_cursor", None)
        if next_cursor is None:
            break
        cursor = next_cursor
    return out

# -------------------------
# Data models
# -------------------------

@dataclass
class Game:
    id: int
    date: str
    season: int
    home_id: int
    away_id: int
    home_name: str
    away_name: str
    status: str = ""
    period: int = 0
    clock: str = ""

    @property
    def label(self) -> str:
        return f"{self.away_name} @ {self.home_name}"

@dataclass
class Pick:
    game: str
    market: str  # MONEYLINE / SPREAD / TOTAL / PROP
    selection: str
    vendor: str
    odds_dec: float
    odds_display: str
    p: float
    hit: float
    edge: float
    ev: float
    notes: str = ""

    def rating33(self) -> int:
        # map Hit (0-10) to 1-33 (cap)
        return int(clamp(round(self.hit * 3.3), 1, 33))

    def tier(self) -> str:
        r = self.rating33()
        if r >= 30:
            return "S"
        if r >= 24:
            return "A"
        if r >= 18:
            return "B"
        if r >= 12:
            return "C"
        return "D"

# -------------------------
# Protocol 33 (team model)
# -------------------------

def protocol33_team_win_prob(home_elo: float, away_elo: float, home_adv: float = 65.0) -> float:
    """
    Elo-style win prob for home team.
    """
    diff = (home_elo + home_adv) - away_elo
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))

def margin_from_prob(p_home: float) -> float:
    """
    Loose mapping from win prob to expected margin (for display + alt-line heuristics).
    """
    # logistic-ish scaling: 50% -> 0, 70% -> ~6, 80% -> ~9
    return (p_home - 0.5) * 30.0

def build_team_elos_from_history(finals: List[Dict[str, Any]], k: float = 20.0) -> Dict[int, float]:
    """
    Build season Elo from finished games list (very light model).
    """
    elos: Dict[int, float] = {}
    def elo_of(tid: int) -> float:
        return elos.get(tid, 1500.0)

    for g in finals:
        ht = (g.get("home_team") or {}).get("id")
        at = (g.get("visitor_team") or {}).get("id")
        hs = g.get("home_team_score")
        as_ = g.get("visitor_team_score")
        if ht is None or at is None or hs is None or as_ is None:
            continue
        home_elo = elo_of(ht)
        away_elo = elo_of(at)
        p_home = protocol33_team_win_prob(home_elo, away_elo)
        # result
        s_home = 1.0 if hs > as_ else 0.0 if hs < as_ else 0.5
        # margin multiplier (cap)
        margin = abs(hs - as_)
        mov = math.log(max(1.0, margin + 1.0))
        # update
        home_elo_new = home_elo + k * mov * (s_home - p_home)
        away_elo_new = away_elo + k * mov * ((1.0 - s_home) - (1.0 - p_home))
        elos[ht] = home_elo_new
        elos[at] = away_elo_new
    return elos

# -------------------------
# Odds parsing (moneyline/spread/total)
# -------------------------

def best_price(rows: List[Dict[str, Any]], field: str) -> Tuple[Optional[str], Optional[float], Optional[Any]]:
    """
    Returns (vendor, best_decimal, raw_american/decimal)
    Picks best for bettor: highest decimal (largest payout).
    """
    best_v = None
    best_dec = None
    best_raw = None
    for r in rows:
        v = str(r.get("vendor", "")).strip().lower()
        o = r.get(field, None)
        dec = american_to_decimal(o)
        if dec is None:
            continue
        if best_dec is None or dec > best_dec:
            best_dec = dec
            best_v = v or "unknown"
            best_raw = o
    return best_v, best_dec, best_raw

def moneyline_fields_present(r: Dict[str, Any]) -> bool:
    return (r.get("moneyline_home_odds") is not None) or (r.get("moneyline_away_odds") is not None)

def sanitize_moneyline_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove obvious feed errors in MONEYLINE rows.

    Handles:
    - rows missing both sides
    - paired-side sanity (implied probs sum not absurd)
    - single-sided outliers (e.g., one book posts a wildly wrong number on only one side)

    Notes:
    - We intentionally allow different vendors for home vs away best prices, but we
      still filter egregious one-sided outliers using per-side medians.
    """
    # First pass: keep rows with at least one side present and apply paired-side sanity when both sides exist.
    stage1: List[Dict[str, Any]] = []
    removed = 0
    for r in rows:
        h = american_to_decimal(r.get("moneyline_home_odds"))
        a = american_to_decimal(r.get("moneyline_away_odds"))
        if not h and not a:
            continue
        if h and a:
            s = implied_prob_from_decimal(h) + implied_prob_from_decimal(a)
            # Markets are usually ~1.02 to 1.12 with vig; we allow a wide band.
            if s < 0.85 or s > 1.35:
                removed += 1
                continue
        stage1.append(r)

    # Second pass: remove one-sided outliers vs per-side median.
    home_decs = [american_to_decimal(r.get("moneyline_home_odds")) for r in stage1]
    away_decs = [american_to_decimal(r.get("moneyline_away_odds")) for r in stage1]
    home_decs = [d for d in home_decs if d and d > 1.01]
    away_decs = [d for d in away_decs if d and d > 1.01]
    med_home = statistics.median(home_decs) if home_decs else None
    med_away = statistics.median(away_decs) if away_decs else None

    def ok(dec: Optional[float], med: Optional[float]) -> bool:
        if dec is None or dec <= 1.01 or med is None:
            return True
        # Very generous bounds; just kill obvious fat-finger/feed glitches.
        low = med / 2.5
        high = med * 2.5
        return (low <= dec <= high)

    clean: List[Dict[str, Any]] = []
    for r in stage1:
        h = american_to_decimal(r.get("moneyline_home_odds"))
        a = american_to_decimal(r.get("moneyline_away_odds"))
        if (h and not ok(h, med_home)) or (a and not ok(a, med_away)):
            removed += 1
            continue
        clean.append(r)

    if removed > 0 and VERBOSE:
        print(f"Data hygiene: removed {removed} MONEYLINE outlier rows (likely vendor/feed errors).")
    return clean

# -------------------------
# Player props modeling
# -------------------------

PROP_TO_STAT = {
    "points": "pts",
    "rebounds": "reb",
    "assists": "ast",
    "threes": "fg3m",
    "steals": "stl",
    "blocks": "blk",
    "turnovers": "turnover",
    # combos:
    "points_rebounds": ("pts", "reb"),
    "points_assists": ("pts", "ast"),
    "rebounds_assists": ("reb", "ast"),
    "points_rebounds_assists": ("pts", "reb", "ast"),
}

def extract_stat_from_game_log(stat_row: Dict[str, Any], prop_type: str) -> Optional[float]:
    s = stat_row
    if prop_type not in PROP_TO_STAT:
        return None
    key = PROP_TO_STAT[prop_type]
    if isinstance(key, tuple):
        vals = []
        for k in key:
            v = safe_float(s.get(k))
            if v is None:
                return None
            vals.append(v)
        return float(sum(vals))
    else:
        v = safe_float(s.get(key))
        return float(v) if v is not None else None

def calc_mu_sigma_from_logs(vals: List[float]) -> Tuple[Optional[float], Optional[float]]:
    vals = [v for v in vals if v is not None]
    if len(vals) < 4:
        return None, None
    mu = statistics.mean(vals)
    sig = statistics.pstdev(vals)  # conservative; avoids overfitting tiny sample
    # floor sigma so we don't get insane probabilities
    sig = max(sig, 1.0)
    return mu, sig

def calc_mu_sigma_from_season_avg(avg: Dict[str, Any], prop_type: str) -> Tuple[Optional[float], Optional[float]]:
    # fallback variance model by prop type
    cv_map = {
        "points": 0.32,
        "rebounds": 0.38,
        "assists": 0.42,
        "threes": 0.55,
        "steals": 0.75,
        "blocks": 0.75,
        "turnovers": 0.55,
        "points_rebounds": 0.28,
        "points_assists": 0.28,
        "rebounds_assists": 0.30,
        "points_rebounds_assists": 0.24,
    }
    if prop_type not in PROP_TO_STAT:
        return None, None
    key = PROP_TO_STAT[prop_type]
    def get_one(k: str) -> Optional[float]:
        return safe_float(avg.get(k))
    if isinstance(key, tuple):
        parts = []
        for k in key:
            v = get_one(k)
            if v is None:
                return None, None
            parts.append(v)
        mu = float(sum(parts))
    else:
        v = get_one(key)
        if v is None:
            return None, None
        mu = float(v)
    cv = cv_map.get(prop_type, 0.40)
    sigma = max(1.0, abs(mu) * cv)
    return mu, sigma

def odds_side_from_prop(prop: Dict[str, Any], side: str) -> Optional[Tuple[float, str]]:
    """
    For over_under: use over_odds/under_odds
    For milestone: use odds
    Returns (decimal, display)
    """
    mkt = (prop.get("market") or {}).get("type")
    if mkt == "over_under":
        if side == "over":
            raw = prop.get("over_odds")
        else:
            raw = prop.get("under_odds")
        dec = american_to_decimal(raw)
        if dec is None:
            return None
        disp = str(raw)
        return dec, disp
    elif mkt == "milestone":
        # milestone is a single 'yes' style market; treat as "over" side.
        raw = prop.get("odds")
        dec = american_to_decimal(raw)
        if dec is None:
            return None
        disp = str(raw)
        return dec, disp
    return None

# -------------------------
# Core workflow
# -------------------------

def resolve_run_date(datestr: Optional[str]) -> str:
    if datestr:
        return datestr
    # local date
    return date.today().isoformat()

def fetch_slate_games(run_date: str, per_page: int = 100) -> List[Game]:
    js = paged_get_all(NBA_GAMES_V1, {"dates[]": run_date, "per_page": per_page}, max_pages=2)
    games: List[Game] = []
    for g in js:
        ht = g.get("home_team") or {}
        at = g.get("visitor_team") or {}
        gid = g.get("id")
        if gid is None or not ht or not at:
            continue
        games.append(Game(
            id=int(gid),
            date=str(g.get("date") or run_date),
            season=int(g.get("season") or 0),
            home_id=int(ht.get("id")),
            away_id=int(at.get("id")),
            home_name=str(ht.get("full_name") or ht.get("name") or ht.get("abbreviation") or "HOME"),
            away_name=str(at.get("full_name") or at.get("name") or at.get("abbreviation") or "AWAY"),
            status=str(g.get("status") or ""),
            period=int(g.get("period") or 0),
            clock=str(g.get("time") or g.get("clock") or ""),
        ))
    return games


# =========================
# Situational: Back-to-Back
# =========================
B2B_PENALTY_PTS_SECOND_NIGHT = float(os.getenv("B2B_PENALTY_PTS_SECOND_NIGHT", "1.75"))
B2B_LOOKAHEAD_PTS_FIRST_NIGHT = float(os.getenv("B2B_LOOKAHEAD_PTS_FIRST_NIGHT", "0.50"))

TEAM_B2B_CONTEXT: dict[int, dict[str, bool]] = {}

def _date_shift(date_str: str, days: int) -> str:
    d = date.fromisoformat(date_str)
    return (d + timedelta(days=days)).isoformat()

def compute_b2b_context(slate_date: str, slate_games: list[Game]) -> dict[int, dict[str, bool]]:
    """Returns {team_id: {'prev': bool, 'next': bool}} for teams on the slate."""
    team_ids = set()
    for gm in slate_games:
        team_ids.add(gm.home_id)
        team_ids.add(gm.away_id)

    prev_date = _date_shift(slate_date, -1)
    next_date = _date_shift(slate_date, +1)

    prev_games = fetch_slate_games(prev_date)
    next_games = fetch_slate_games(next_date)

    prev_ids = set()
    for g in prev_games:
        prev_ids.add(g.home_id); prev_ids.add(g.away_id)

    next_ids = set()
    for g in next_games:
        next_ids.add(g.home_id); next_ids.add(g.away_id)

    ctx = {}
    for tid in team_ids:
        ctx[tid] = {"prev": tid in prev_ids, "next": tid in next_ids}
    return ctx

def apply_b2b_margin_adjustment(gm: Game, base_margin_home: float) -> float:
    """Adjust expected home margin for B2B context (simple fatigue/lookahead heuristic)."""
    if not TEAM_B2B_CONTEXT:
        return base_margin_home

    h = TEAM_B2B_CONTEXT.get(gm.home_id, {"prev": False, "next": False})
    a = TEAM_B2B_CONTEXT.get(gm.away_id, {"prev": False, "next": False})

    # Second night fatigue is the big one (played yesterday)
    adj = 0.0
    if h.get("prev"):
        adj -= B2B_PENALTY_PTS_SECOND_NIGHT
    if a.get("prev"):
        adj += B2B_PENALTY_PTS_SECOND_NIGHT

    # Lookahead: tiny "energy-saving" signal on the first night if they play tomorrow
    if h.get("next"):
        adj -= B2B_LOOKAHEAD_PTS_FIRST_NIGHT
    if a.get("next"):
        adj += B2B_LOOKAHEAD_PTS_FIRST_NIGHT

    return base_margin_home + adj


def fetch_history_finals(season: int, limit_pages: int = 10) -> List[Dict[str, Any]]:
    # Pull a lot of games for the season, then keep finals only.
    # Using dates is hard; just pagination.
    rows = paged_get_all(NBA_GAMES_V1, {"seasons[]": season, "per_page": 100}, max_pages=limit_pages)
    finals = []
    for g in rows:
        # status "Final" or scores present and non-zero
        hs = g.get("home_team_score")
        as_ = g.get("visitor_team_score")
        if hs is None or as_ is None:
            continue
        finals.append(g)
    return finals
def fetch_season_averages(player_ids: List[int], season: int) -> Dict[int, Dict[str, Any]]:
    """Fetch season averages for players.

    Uses /nba/v1/season_averages. This endpoint is sometimes strict about params, so we:
    - query one player at a time with player_id=<int>
    - swallow HTTP errors and return what we can
    """
    out: Dict[int, Dict[str, Any]] = {}
    # de-dupe, keep ints only
    uniq: List[int] = []
    seen = set()
    for pid in player_ids:
        try:
            ip = int(pid)
        except Exception:
            continue
        if ip in seen:
            continue
        seen.add(ip)
        uniq.append(ip)

    for pid in uniq:
        try:
            js = get_json(NBA_SEASON_AVGS_V1, params={"season": int(season), "player_id": int(pid)})
        except SystemExit:
            # Some tiers/edges reject this endpoint or params; skip quietly.
            continue
        except Exception:
            continue

        data = js.get("data")
        if isinstance(data, list) and data:
            row = data[0]
            if isinstance(row, dict):
                # ensure player_id present for downstream joins
                row = dict(row)
                row.setdefault("player_id", pid)
                out[pid] = row
    return out

def fetch_odds_for_date(run_date: str, per_page: int = 100) -> List[Dict[str, Any]]:
    # Odds endpoint requires dates or game_ids. Use dates.
    # NOTE: per_page max 100 per OpenAPI.
    per_page = int(clamp(per_page, 1, 100))
    rows = paged_get_all(NBA_ODDS_V2, {"dates[]": run_date, "per_page": per_page}, max_pages=6)
    return rows
# -------------------------
# Rosters / injuries / lineups (BDL)
# -------------------------

def fetch_active_players(team_ids: Optional[List[int]] = None, per_page: int = 100) -> List[Dict[str, Any]]:
    """
    Current active players (best proxy for each team's current roster).
    Docs: GET /v1/players/active (cursor pagination).
    """
    p: Dict[str, Any] = {"per_page": min(int(per_page or 100), 100)}
    if team_ids:
        p["team_ids[]"] = [int(t) for t in team_ids]
    return paged_get_all(NBA_ACTIVE_PLAYERS_V1, p, max_pages=10)

def fetch_player_injuries(team_ids: Optional[List[int]] = None, per_page: int = 100) -> List[Dict[str, Any]]:
    """
    Player injury list with status (e.g., Out) and a description string.
    Docs: GET /v1/player_injuries (cursor pagination).
    """
    p: Dict[str, Any] = {"per_page": min(int(per_page or 100), 100)}
    if team_ids:
        p["team_ids[]"] = [int(t) for t in team_ids]
    return paged_get_all(NBA_PLAYER_INJURIES_V1, p, max_pages=10)

def fetch_game_lineups(game_ids: List[int], per_page: int = 100) -> List[Dict[str, Any]]:
    """
    Starting lineup data (only available once the game begins; 2025 season+ per docs).
    Docs: GET /v1/lineups?game_ids[]=...
    """
    p: Dict[str, Any] = {"per_page": min(int(per_page or 100), 100)}
    p["game_ids[]"] = [int(g) for g in game_ids]
    return paged_get_all(NBA_LINEUPS_V1, p, max_pages=10)

def _index_players_by_team(active_players: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = {}
    for pl in active_players or []:
        team = pl.get("team") or {}
        tid = team.get("id") or pl.get("team_id")
        if tid is None:
            continue
        out.setdefault(int(tid), []).append(pl)
    return out

def _build_player_team_maps(active_players: List[Dict[str, Any]]) -> Tuple[Dict[int, int], Dict[int, set[int]]]:
    """
    Build:
      - player_id -> team_id
      - team_id -> set(player_id) (roster ids)
    We use this to sanity-filter injuries and lineups so we don't attribute players
    to the wrong team if the upstream payload is missing/incorrectly nested.
    """
    player_team_by_id: Dict[int, int] = {}
    roster_ids_by_team: Dict[int, set[int]] = {}
    for pl in active_players or []:
        pid = pl.get("id")
        team = pl.get("team") or {}
        tid = team.get("id") or pl.get("team_id")
        if pid is None or tid is None:
            continue
        try:
            pid_i = int(pid)
            tid_i = int(tid)
        except Exception:
            continue
        player_team_by_id[pid_i] = tid_i
        roster_ids_by_team.setdefault(tid_i, set()).add(pid_i)
    return player_team_by_id, roster_ids_by_team

def _index_injuries_by_team(
    injuries: List[Dict[str, Any]],
    player_team_by_id: Optional[Dict[int, int]] = None
) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = {}
    for inj in injuries or []:
        pl = inj.get("player") or {}
        pid = pl.get("id") or inj.get("player_id")

        # Prefer explicit team fields on the injury object (least ambiguous).
        tid = (inj.get("team") or {}).get("id") or pl.get("team_id")

        # Fallback to roster-derived mapping if injury rows don't include team.
        if tid is None and pid is not None and player_team_by_id is not None:
            try:
                tid = player_team_by_id.get(int(pid))
            except Exception:
                tid = None

        if tid is None:
            continue

        out.setdefault(int(tid), []).append(inj)
    return out


def _index_lineups(
    lineups: List[Dict[str, Any]],
    player_team_by_id: Optional[Dict[int, int]] = None
) -> Dict[Tuple[int, int], List[Dict[str, Any]]]:
    """
    Returns mapping: (game_id, team_id) -> lineup rows
    """
    out: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    for row in lineups or []:
        gid = row.get("game_id")
        if gid is None:
            continue

        team = row.get("team") or {}
        pl = row.get("player") or {}
        pid = pl.get("id") or row.get("player_id")
        tid = team.get("id") or pl.get("team_id")

        # Prefer roster-derived mapping if team is missing/odd
        if (tid is None) and (pid is not None) and (player_team_by_id is not None):
            try:
                tid = player_team_by_id.get(int(pid))
            except Exception:
                tid = None

        if tid is None:
            continue

        out.setdefault((int(gid), int(tid)), []).append(row)
    return out

def _fmt_player_name(p: Dict[str, Any]) -> str:
    fn = (p.get("first_name") or "").strip()
    ln = (p.get("last_name") or "").strip()
    if fn or ln:
        return (fn + " " + ln).strip()
    return str(p.get("id") or "UNKNOWN")

def _inj_out_list(team_inj: List[Dict[str, Any]], roster_player_ids: Optional[set[int]] = None) -> List[str]:
    """
    Returns short list of OUT-ish players for display.
    If roster_player_ids is provided and non-empty, we only keep injuries for players
    currently on that team's active roster (prevents obvious mis-attribution).
    """
    roster_player_ids = roster_player_ids or set()
    out: List[str] = []
    for inj in team_inj or []:
        status = str(inj.get("status") or "").strip()
        status_l = status.lower()
        if not (status_l == "out" or status_l.startswith("out") or status_l == "doubtful" or status_l.startswith("doubtful")):
            continue

        pl = inj.get("player") or {}
        pid = pl.get("id") or inj.get("player_id")
        if roster_player_ids and pid is not None:
            try:
                if int(pid) not in roster_player_ids:
                    continue
            except Exception:
                pass

        out.append(f"{_fmt_player_name(pl)} ({status})")
    return out

def _starter_list(lineup_rows: List[Dict[str, Any]], roster_player_ids: Optional[set[int]] = None) -> List[str]:
    roster_player_ids = roster_player_ids or set()
    starters: List[str] = []
    for row in lineup_rows or []:
        if row.get("starter") is True:
            pl = row.get("player") or {}
            pid = pl.get("id") or row.get("player_id")
            if roster_player_ids and pid is not None:
                try:
                    if int(pid) not in roster_player_ids:
                        continue
                except Exception:
                    pass
            starters.append(_fmt_player_name(pl))
    # If the API includes non-starters too, cap to 5 names for display
    return starters[:5]


def filter_odds_to_slate(odds_rows: List[Dict[str, Any]], slate_game_ids: set[int], exclude_prediction_markets: bool = True) -> List[Dict[str, Any]]:
    out = []
    for r in odds_rows:
        gid = r.get("game_id")
        if gid is None:
            continue
        try:
            gid_int = int(gid)
        except Exception:
            continue
        if gid_int not in slate_game_ids:
            continue
        vend = str(r.get("vendor", "")).lower()
        if exclude_prediction_markets and vend in {"polymarket", "kalshi"}:
            continue
        out.append(r)
    return out

def group_by_game(rows: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    g: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        gid = r.get("game_id")
        if gid is None:
            continue
        try:
            gid = int(gid)
        except Exception:
            continue
        g.setdefault(gid, []).append(r)
    return g

def protocol33_probs_for_slate(games: List[Game], elos: Dict[int, float]) -> Dict[int, Tuple[float, float, float, str]]:
    """
    returns: game_id -> (p_home, p_away, exp_margin_home, winner_name)
    """
    out = {}
    for gm in games:
        home_elo = elos.get(gm.home_id, 1500.0)
        away_elo = elos.get(gm.away_id, 1500.0)
        p_home = clamp(protocol33_team_win_prob(home_elo, away_elo), 0.01, 0.99)
        p_away = 1.0 - p_home
        m = margin_from_prob(p_home)
        winner = gm.home_name if p_home >= 0.5 else gm.away_name
        out[gm.id] = (p_home, p_away, m, winner)
    return out

def pick_moneyline_value(
    gm: Game,
    odds_rows: List[Dict[str, Any]],
    p_home: float,
    p_away: float,
    min_prob: float,
    min_ev: float
) -> Tuple[Optional[Pick], Optional[Pick], Optional[Pick]]:
    """
    Returns (best_plus_ev_highchance, closest_miss_highchance, best_plus_ev_anychance)
    """
    rows = sanitize_moneyline_rows([r for r in odds_rows if moneyline_fields_present(r)])
    if not rows:
        return None, None, None

    # compute market consensus de-vig from medians (home/away)
    home_decs = [american_to_decimal(r.get("moneyline_home_odds")) for r in rows]
    away_decs = [american_to_decimal(r.get("moneyline_away_odds")) for r in rows]
    home_decs = [d for d in home_decs if d]
    away_decs = [d for d in away_decs if d]
    med_home = statistics.median(home_decs) if home_decs else None
    med_away = statistics.median(away_decs) if away_decs else None
    mkt_home, mkt_away = devig_two_way(med_home, med_away)

    best_high: Optional[Pick] = None
    closest_high: Optional[Pick] = None
    best_any: Optional[Pick] = None

    # Evaluate both sides at best available vendor prices
    # "best" for bettor is max decimal.
    vh, dec_h, raw_h = best_price(rows, "moneyline_home_odds")
    va, dec_a, raw_a = best_price(rows, "moneyline_away_odds")

    candidates = []
    if dec_h:
        candidates.append(("MONEYLINE", gm.home_name, vh or "unknown", dec_h, raw_h, p_home, mkt_home))
    if dec_a:
        candidates.append(("MONEYLINE", gm.away_name, va or "unknown", dec_a, raw_a, p_away, mkt_away))

    for market, sel, vendor, dec, raw, p, mkt_p in candidates:
        implied = implied_prob_from_decimal(dec)
        edge = p - (mkt_p if mkt_p is not None else implied)
        ev = p * dec - 1.0
        hit = p * 10.0
        pk = Pick(
            game=gm.label,
            market=market,
            selection=sel,
            vendor=vendor,
            odds_dec=dec,
            odds_display=str(raw),
            p=p,
            hit=hit,
            edge=edge,
            ev=ev,
            notes=f"implied {implied*100:.1f}%"
        )

        # best any
        if best_any is None or pk.ev > best_any.ev:
            best_any = pk

        # high chance bucket
        if p >= min_prob:
            if pk.ev >= min_ev and (best_high is None or pk.ev > best_high.ev):
                best_high = pk
            # closest miss (high chance but EV <= threshold) -> least negative EV
            if pk.ev < min_ev:
                if (closest_high is None) or (pk.ev > closest_high.ev):
                    closest_high = pk

    return best_high, closest_high, best_any

def moneyline_arb_percent(dec_home: float, dec_away: float) -> float:
    # arb if 1/dec_home + 1/dec_away < 1 ; profit % = 1 - sum
    s = (1.0/dec_home) + (1.0/dec_away)
    return (1.0 - s) * 100.0

def find_moneyline_arb(gm: Game, odds_rows: List[Dict[str, Any]]) -> Optional[str]:
    rows = sanitize_moneyline_rows([r for r in odds_rows if moneyline_fields_present(r)])
    if not rows:
        return None
    vh, dec_h, raw_h = best_price(rows, "moneyline_home_odds")
    va, dec_a, raw_a = best_price(rows, "moneyline_away_odds")
    if not dec_h or not dec_a:
        return None
    s = (1.0/dec_h) + (1.0/dec_a)
    if s >= 1.0:
        return None
    arb = moneyline_arb_percent(dec_h, dec_a)
    return (f"{gm.label} | best_home {vh} {raw_h}  "
            f"+ best_away {va} {raw_a}  | arb ≈ {arb:.2f}%")

def fetch_player_props_for_game(
    game_id: int,
    player_id: Optional[int] = None,
    prop_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch LIVE NBA player props for a game.

    ✅ Correct per BallDontLie OpenAPI:
      GET /nba/v2/odds/player_props?game_id=<id>
      Optional: player_id, prop_type

    ⚠️ IMPORTANT: This endpoint does **NOT** accept `vendors` / `vendors[]`.
    Passing that will typically yield HTTP 400 and an empty result if you swallow the error.

    We fail-soft (return []) so the rest of the slate still prints.
    """
    gid = int(game_id)

    params: Dict[str, Any] = {"game_id": gid}
    if player_id is not None:
        try:
            params["player_id"] = int(player_id)
        except Exception:
            pass
    if prop_type:
        params["prop_type"] = str(prop_type).strip()

    try:
        js = get_json(NBA_PLAYER_PROPS_V2, params, timeout=20)
    except SystemExit as e:
        # Fail soft so odds still run; surface details only in verbose/debug.
        if VERBOSE or DEBUG_PROPS:
            print(f"  WARN: player_props fetch failed for game_id={gid}: {e}")
        return []

    data = (js or {}).get("data") if isinstance(js, dict) else None
    return data if isinstance(data, list) else []


def fetch_recent_stats_for_players(player_ids: List[int], season: int, end_date: str, per_page: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent player game stats (one player at a time).

    Why per-player?
      Some tiers/servers reject array-style inputs with confusing validation errors
      (e.g., 'player_id must be a single integer'). Calling one-at-a-time is slower
      but far more reliable and still fine for the small number of players we evaluate.
    """
    out: List[Dict[str, Any]] = []
    seen: set[int] = set()
    for pid in player_ids:
        if pid is None:
            continue
        try:
            ipid = int(pid)
        except Exception:
            continue
        if ipid in seen:
            continue
        seen.add(ipid)

        params = {
            "player_ids[]": ipid,      # OpenAPI param (preferred)
            "seasons[]": season,
            "end_date": end_date,
            "per_page": min(int(per_page), 100),
        }

        try:
            js = get_json(NBA_STATS_V1, params)
        except SystemExit as e:
            # Fallback: some deployments expect singular player_id
            msg = str(e)
            if "player_id must be a single integer" in msg or "player_id" in msg:
                try:
                    js = get_json(NBA_STATS_V1, {
                        "player_id": ipid,
                        "seasons[]": season,
                        "end_date": end_date,
                        "per_page": min(int(per_page), 100),
                    })
                except SystemExit:
                    continue
            else:
                continue

        data = js.get("data") or []
        if isinstance(data, list):
            out.extend(data)
    return out

# -------------------------
# Lightweight caching (avoid hammering stats endpoints during live props refresh)
# -------------------------

# key: (player_id, season, end_date) -> (fetched_ts, rows)
_PLAYER_STATS_CACHE: Dict[Tuple[int, int, str], Tuple[float, List[Dict[str, Any]]]] = {}

def fetch_recent_stats_for_players_cached(
    player_ids: List[int],
    season: int,
    end_date: str,
    per_page: int = 100,
    ttl_seconds: int = 1800
) -> List[Dict[str, Any]]:
    """Cached wrapper for fetch_recent_stats_for_players.

    In live mode, props refresh can run every ~15s. We do NOT want to refetch
    game logs every cycle. This cache keeps per-player logs hot for `ttl_seconds`.
    """
    now = time.time()
    # dedupe
    uniq: List[int] = []
    seen: set[int] = set()
    for pid in player_ids:
        try:
            ip = int(pid)
        except Exception:
            continue
        if ip in seen:
            continue
        seen.add(ip)
        uniq.append(ip)

    out: List[Dict[str, Any]] = []
    missing: List[int] = []

    for pid in uniq:
        key = (pid, int(season), str(end_date))
        item = _PLAYER_STATS_CACHE.get(key)
        if item and (now - item[0] <= ttl_seconds):
            out.extend(item[1])
        else:
            missing.append(pid)

    if missing:
        fetched = fetch_recent_stats_for_players(missing, season=season, end_date=end_date, per_page=per_page)
        # group by pid
        by_pid: Dict[int, List[Dict[str, Any]]] = {}
        for r in fetched:
            pl = r.get("player") or {}
            rid = pl.get("id")
            if rid is None:
                continue
            try:
                rid = int(rid)
            except Exception:
                continue
            by_pid.setdefault(rid, []).append(r)

        for pid in missing:
            rows = by_pid.get(pid, [])
            _PLAYER_STATS_CACHE[(pid, int(season), str(end_date))] = (now, rows)
            out.extend(rows)

    return out


def pick_best_player_props_for_game(
    gm: Game,
    props: List[Dict[str, Any]],
    season: int,
    end_date: str,
    min_prob: float,
    min_ev: float,
    max_props_per_game: int = 3,
    vendor_allow: Optional[set[str]] = None
) -> List[Pick]:
    """
    For each game, return up to N best player prop picks (over/under),
    using recent game log distribution where available.
    """
    if not props:
        return []

    # Filter vendors if requested
    if vendor_allow is not None:
        def _vn(x: Any) -> str:
            s = str(x or "").strip().lower()
            s = s.replace(" ", "").replace("_", "")
            if s.startswith("draftkings"):
                return "draftkings"
            if s.startswith("fanduel"):
                return "fanduel"
            if s.startswith("bet365"):
                return "bet365"
            if s.startswith("betmgm"):
                return "betmgm"
            return s
        props = [p for p in props if _vn(p.get("vendor")) in vendor_allow]

    # Only consider supported prop types with a numeric line
    usable = []
    for p in props:
        ptype = str(p.get("prop_type", "")).lower()
        if ptype not in PROP_TO_STAT:
            continue
        lv = safe_float(p.get("line_value"))
        if lv is None:
            continue
        usable.append(p)

    if not usable:
        return []

    # Build unique player_ids, cap for rate safety
    pids = sorted({int(p.get("player_id")) for p in usable if p.get("player_id") is not None})
    if not pids:
        return []

    # Pull recent stats in one batch
    # End date should be day before run date (pregame)
    stats_rows = fetch_recent_stats_for_players_cached(pids, season=season, end_date=end_date, per_page=100, ttl_seconds=1800)

    # Group stats by player
    by_player: Dict[int, List[Dict[str, Any]]] = {}
    for r in stats_rows:
        pl = r.get("player") or {}
        pid = pl.get("id")
        if pid is None:
            continue
        try:
            pid = int(pid)
        except Exception:
            continue
        by_player.setdefault(pid, []).append(r)

    # Sort each player's logs by game date (if present)
    def game_dt(row: Dict[str, Any]) -> str:
        g = row.get("game") or {}
        # game datetime can be null; use date string
        return str(g.get("datetime") or g.get("date") or "")

    for pid, rows in by_player.items():
        rows.sort(key=game_dt)

    # Fallback season averages for players with too few logs
    season_avgs = fetch_season_averages(pids, season=season)

    picks: List[Pick] = []

    # De-clutter: group by (player_id, prop_type, line) and keep best vendor price per side
    # For over/under: keep best over and best under separately.
    best_by_key: Dict[Tuple[int, str, float, str], Dict[str, Any]] = {}
    for pr in usable:
        pid = int(pr.get("player_id"))
        ptype = str(pr.get("prop_type")).lower()
        line = float(pr.get("line_value"))
        mkt = (pr.get("market") or {}).get("type")
        if mkt == "over_under":
            for side in ("over", "under"):
                od = odds_side_from_prop(pr, side)
                if not od:
                    continue
                dec, _ = od
                key = (pid, ptype, line, side)
                prev = best_by_key.get(key)
                if prev is None:
                    best_by_key[key] = pr
                else:
                    prev_dec = odds_side_from_prop(prev, side)
                    if prev_dec and dec > prev_dec[0]:
                        best_by_key[key] = pr
        elif mkt == "milestone":
            # single side
            od = odds_side_from_prop(pr, "over")
            if not od:
                continue
            dec, _ = od
            key = (pid, ptype, line, "milestone")
            prev = best_by_key.get(key)
            if prev is None:
                best_by_key[key] = pr
            else:
                prev_dec = odds_side_from_prop(prev, "over")
                if prev_dec and dec > prev_dec[0]:
                    best_by_key[key] = pr

    # Now score each best prop
    for (pid, ptype, line, side), pr in best_by_key.items():
        pl_name = ""
        # try from stats row
        if pid in by_player and by_player[pid]:
            pl = (by_player[pid][-1].get("player") or {})
            pl_name = (str(pl.get("first_name") or "") + " " + str(pl.get("last_name") or "")).strip()
        if not pl_name:
            # no good name; keep id
            pl_name = f"player {pid}"

        # Estimate mu/sigma from last N logs if possible
        logs = by_player.get(pid, [])
        vals = []
        # Use last 12 games if available
        for row in logs[-12:]:
            v = extract_stat_from_game_log(row, ptype)
            if v is not None:
                vals.append(v)
        mu, sigma = calc_mu_sigma_from_logs(vals)

        if mu is None or sigma is None:
            avg = season_avgs.get(pid, {})
            mu, sigma = calc_mu_sigma_from_season_avg(avg, ptype)

        if mu is None or sigma is None:
            continue

        # Compute model probability for this side
        if side == "over":
            p_model = prob_over_normal(mu, sigma, line)
            sel = f"{pl_name} OVER {line:g} {ptype.replace('_', '+').upper()}"
            od = odds_side_from_prop(pr, "over")
        elif side == "under":
            p_over = prob_over_normal(mu, sigma, line)
            p_model = 1.0 - p_over
            sel = f"{pl_name} UNDER {line:g} {ptype.replace('_', '+').upper()}"
            od = odds_side_from_prop(pr, "under")
        else:
            # milestone (treat as "yes/reach")
            # approximate as P(over)
            p_model = prob_over_normal(mu, sigma, line)
            sel = f"{pl_name} REACH {line:g}+ {ptype.replace('_', '+').upper()} (milestone)"
            od = odds_side_from_prop(pr, "over")

        if not od:
            continue
        dec, disp = od

        # Market implied for this side: for over/under, de-vig using both sides when available at same vendor+line
        implied = implied_prob_from_decimal(dec)
        mkt_type = (pr.get("market") or {}).get("type")
        if mkt_type == "over_under":
            # if we can find opposite side at same vendor for same pid/ptype/line (from raw usable list)
            vendor = str(pr.get("vendor", "")).lower()
            opp_side = "under" if side == "over" else "over"
            # find any prop row from that vendor with same player/ptype/line to get odds for both sides
            dec_opp = None
            for pr2 in usable:
                if int(pr2.get("player_id")) != pid:
                    continue
                if str(pr2.get("prop_type","")).lower() != ptype:
                    continue
                if safe_float(pr2.get("line_value")) != line:
                    continue
                if str(pr2.get("vendor","")).lower() != vendor:
                    continue
                if (pr2.get("market") or {}).get("type") != "over_under":
                    continue
                od2 = odds_side_from_prop(pr2, opp_side)
                if od2:
                    dec_opp = od2[0]
                    break
            if dec_opp:
                p_side, p_opp = devig_two_way(dec, dec_opp)
                if p_side is not None:
                    implied = p_side

        edge = p_model - implied
        ev = p_model * dec - 1.0
        hit = p_model * 10.0

        # Filter to "high chance + value"
        # Keep candidates that are either high chance OR very positive EV (to show value even if slightly lower chance),
        # but the final output per game is de-cluttered and sorted by EV then chance.
        if p_model >= min_prob and ev >= min_ev:
            picks.append(Pick(
                game=gm.label,
                market="PROP",
                selection=sel,
                vendor=str(pr.get("vendor","")).lower(),
                odds_dec=dec,
                odds_display=str(disp),
                p=p_model,
                hit=hit,
                edge=edge,
                ev=ev,
                notes=f"mu≈{mu:.1f} σ≈{sigma:.1f} (last{min(12,len(vals))}g)"
            ))

    # Sort and de-clutter to max per game
    picks.sort(key=lambda x: (x.ev, x.p, x.edge, x.odds_dec), reverse=True)
    return picks[:max_props_per_game]

# -------------------------
# Printing
# -------------------------

def fmt_pct(p: float) -> str:
    return f"{p*100:.1f}%"

def fmt_hit(hit: float) -> str:
    return f"{hit:.1f}/10"

def fmt_ev(ev: float) -> str:
    return f"{ev*100:.1f}%"

def print_slate_probs(games: List[Game], probs: Dict[int, Tuple[float, float, float, str]]) -> None:
    print("\
Protocol 33 Win Probabilities (slate)")
    print("------------------------------------")

    def sort_key(g: Game) -> float:
        ph, pa, _, _ = probs.get(g.id, (0.5, 0.5, 0.0, ""))
        return max(ph, pa)

    for gm in sorted(games, key=sort_key, reverse=True):
        p_home, p_away, m, winner = probs.get(gm.id, (0.5, 0.5, 0.0, gm.home_name))
        # Display winner P as max(home, away)
        pwin = max(p_home, p_away)
        print(f"- {gm.label} | model: {gm.away_name} {fmt_pct(p_away)} / {gm.home_name} {fmt_pct(p_home)} | winner: {winner} | P(win) {fmt_pct(pwin)} | expected margin: {winner} by {abs(m):.1f}")

def print_pick(pk: Pick, idx: int) -> None:
    print(f"{idx:>2}. [{pk.tier()} {pk.rating33():>2}/33] {pk.market:<7} | {pk.selection} | @{pk.vendor} | odds {pk.odds_display} "
          f" | model {fmt_pct(pk.p)} | Hit {fmt_hit(pk.hit)} | edge {fmt_pct(pk.edge)} | EV {fmt_ev(pk.ev)}"
          + (f" | {pk.notes}" if pk.notes else ""))


def _norm_vendor_key(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = s.replace(" ", "").replace("_", "")
    # common normalizations
    if s.startswith("draftkings"):
        return "draftkings"
    if s.startswith("fanduel"):
        return "fanduel"
    if s.startswith("bet365"):
        return "bet365"
    if s.startswith("betmgm"):
        return "betmgm"
    return s


def _fmt_prop_snapshot(pr: Dict[str, Any], player_name_by_id: Dict[int, str]) -> str:
    vendor = _norm_vendor_key(pr.get("vendor")) or "?"
    pid = pr.get("player_id")
    try:
        ipid = int(pid)
    except Exception:
        ipid = -1
    pname = player_name_by_id.get(ipid, f"player_id={pid}")
    ptype = str(pr.get("prop_type") or "?")
    lv = pr.get("line_value")
    market = (pr.get("market") or {}).get("type")

    # odds fields vary by market
    if market == "over_under":
        over = pr.get("over_odds")
        under = pr.get("under_odds")
        return f"{pname} — {ptype} {lv} | over {over} / under {under} | @{vendor}"
    if market == "milestone":
        od = pr.get("odds")
        return f"{pname} — {ptype} {lv}+ | odds {od} | @{vendor}"
    # fallback
    od = pr.get("odds") or pr.get("over_odds")
    return f"{pname} — {ptype} {lv} | odds {od} | @{vendor}"

def main() -> int:
    ap = argparse.ArgumentParser(description="PROTOCOL 33 / SIM J420N — NBA odds + props value scanner (live refresh)")
    ap.add_argument("--date", help="Slate date YYYY-MM-DD (default: today)")
    ap.add_argument("--season", type=int, default=2025, help="Season year for history/modeling (default 2025)")
    ap.add_argument("--min_prob", type=float, default=0.70, help="Min model probability for 'high chance' (default 0.70)")
    ap.add_argument("--min_ev", type=float, default=0.00, help="Min EV (decimal) for +EV picks (default 0.00)")
    ap.add_argument("--max_props_per_game", type=int, default=2, help="Max props to show per game (default 2)")
    ap.add_argument("--no_props", action="store_true", help="Skip player props fetch/scoring")
    ap.add_argument("--no_roster", action="store_true", help="Skip roster/injury/lineup snapshot")
    ap.add_argument("--include_prediction_markets", action="store_true", help="Include polymarket/kalshi in odds")
    ap.add_argument("--per_page", type=int, default=100, help="Odds per_page (max 100)")
    ap.add_argument("--slate_refresh", type=int, default=30, help="Seconds between slate/odds refresh (default 30)")
    ap.add_argument("--props_refresh", type=int, default=15, help="Seconds between live props refresh (default 15)")
    ap.add_argument("--once", action="store_true", help="Run once and exit (no live refresh loop)")
    ap.add_argument("--no_pause", action="store_true", help="Do not wait for ENTER at end")
    ap.add_argument("--verbose", action="store_true", help="Print extra diagnostics (less clean output)")
    ap.add_argument("--debug_props", action="store_true", help="Print extra live-props debugging details")
    args = ap.parse_args()

    # wire output controls
    global VERBOSE, DEBUG_PROPS
    VERBOSE = bool(args.verbose)
    DEBUG_PROPS = bool(args.debug_props)

    # Only show these primary books in best-line + value output (as requested).
    primary_books_order = ["draftkings", "fanduel", "bet365", "betmgm"]
    primary_books = set(primary_books_order)

    # Allow prediction markets only if explicitly requested.
    if args.include_prediction_markets:
        primary_books |= {"polymarket", "kalshi"}

    run_date = resolve_run_date(args.date)

    print(f"PROTOCOL 33 / SIM J420N — {run_date} — VALUE + PROPS MODE")
    print(f"High chance threshold: model P >= {args.min_prob:.2f} (Hit >= {args.min_prob*10:.1f}/10)")
    print(f"+EV threshold: EV >= {args.min_ev*100:.1f}%")
    print("Both sides eligible (projected winner NOT required).\
")

    # 1) Fetch slate games once up-front (also used for roster/injury snapshot)
    games = fetch_slate_games(run_date, per_page=100)
    if not games:
        raise SystemExit(f"No games returned for date {run_date}. Try --date YYYY-MM-DD.")
    slate_ids = {g.id for g in games}
    team_ids_on_slate = sorted({int(g.home_id) for g in games} | {int(g.away_id) for g in games})

    # Used for pretty live-props output (best-effort; may be empty if --no_roster).
    player_name_by_id: Dict[int, str] = {}

    # 2) Snapshot roster/injuries/starters ONCE (no refresh each cycle)
    if not args.no_roster:
        print("Roster / Injuries / Starters (BDL) — snapshot (injuries will NOT refresh)")
        print("--------------------------------------------------------------")
        active_players: List[Dict[str, Any]] = []
        injuries: List[Dict[str, Any]] = []
        lineups: List[Dict[str, Any]] = []

        try:
            active_players = fetch_active_players(team_ids_on_slate, per_page=100)
        except SystemExit as e:
            print(f"  WARN: active players unavailable: {e}")
        try:
            injuries = fetch_player_injuries(team_ids_on_slate, per_page=100)
        except SystemExit as e:
            print(f"  WARN: injuries unavailable: {e}")
        try:
            lineups = fetch_game_lineups([g.id for g in games], per_page=100)
        except SystemExit:
            # often pregame
            lineups = []

        rosters_by_team = _index_players_by_team(active_players)
        # Build a quick id->name map for props printing.
        for p in active_players:
            pid = p.get("id")
            try:
                ipid = int(pid)
            except Exception:
                continue
            fn = str(p.get("first_name") or "").strip()
            ln = str(p.get("last_name") or "").strip()
            nm = (fn + " " + ln).strip() or str(p.get("display_name") or "").strip() or f"player_id={ipid}"
            player_name_by_id[ipid] = nm
        player_team_by_id, roster_ids_by_team = _build_player_team_maps(active_players)
        injuries_by_team = _index_injuries_by_team(injuries, player_team_by_id)
        lineups_idx = _index_lineups(lineups, player_team_by_id)

        for gm in games:
            print(f"- {gm.label} | game_id={gm.id} | status={gm.status or 'N/A'}")
            for tid, tname in [(gm.away_id, gm.away_name), (gm.home_id, gm.home_name)]:
                roster_set = roster_ids_by_team.get(int(tid), set())
                roster_n = len(roster_set) if roster_set else len(rosters_by_team.get(int(tid), []))
                out_names = _inj_out_list(injuries_by_team.get(int(tid), []), roster_set)
                starters = _starter_list(lineups_idx.get((int(gm.id), int(tid)), []), roster_set)
                out_txt = (", ".join(out_names) if out_names else "none listed")
                st_txt = (", ".join(starters) if starters else "(not available until tip / lineup feed)")
                print(f"    • {tname}: active_roster={roster_n} | OUT-ish={out_txt} | starters={st_txt}")
        print("")

    # 3) History/elos once (don’t refetch every refresh)
    finals = fetch_history_finals(args.season, limit_pages=10)
    elos = build_team_elos_from_history(finals)

    # Helpers (moneyline best-line + tiered printing)
    def _norm_vendor(v: Any) -> str:
        s = str(v or "").strip().lower()
        s = s.replace(" ", "").replace("_", "")
        if s.startswith("draftkings"):
            return "draftkings"
        if s.startswith("fanduel"):
            return "fanduel"
        if s.startswith("bet365"):
            return "bet365"
        if s.startswith("betmgm"):
            return "betmgm"
        return s

    def _best_ml_for_side(rows: List[Dict[str, Any]], side: str) -> Optional[Tuple[str, str, float]]:
        """Return (vendor, american_str, dec) best price for side in {'home','away'} among primary books.

        Uses sanitize_moneyline_rows to drop obvious vendor/feed errors before selecting best.
        """
        best: Optional[Tuple[str, str, float]] = None
        clean = sanitize_moneyline_rows([r for r in rows if moneyline_fields_present(r)])
        for r in clean:
            vend = _norm_vendor(r.get("vendor"))
            if vend not in primary_books:
                continue
            raw = r.get("moneyline_home_odds") if side == "home" else r.get("moneyline_away_odds")
            dec = american_to_decimal(raw)
            if not dec:
                continue
            if best is None or dec > best[2]:
                best = (vend, str(raw), float(dec))
        return best

    def _is_live(status: Optional[str]) -> bool:
        s = str(status or "").lower()
        if not s:
            return False
        if "final" in s:
            return False
        return ("qtr" in s) or ("half" in s) or ("ot" in s)

    def _is_finalish(status: Optional[str]) -> bool:
        s = str(status or "").lower()
        if not s:
            return False
        return ("final" in s) or ("canceled" in s) or ("cancelled" in s) or ("postpon" in s)

    def _is_actionable(status: Optional[str]) -> bool:
        # Used to hide finished games from odds/value/arb output (prevents stale/settled prices from polluting picks).
        return not _is_finalish(status)

    def _build_ml_picks_for_game(gm: Game, rows: List[Dict[str, Any]], p_home: float, p_away: float) -> List[Pick]:
        picks: List[Pick] = []
        best_home = _best_ml_for_side(rows, "home")
        best_away = _best_ml_for_side(rows, "away")
        if best_home:
            vend, raw, dec = best_home
            implied = 1.0 / dec
            edge = p_home - implied
            ev = p_home * (dec - 1.0) - (1.0 - p_home)
            picks.append(Pick(
                game=gm.label,
                market="MONEYLINE",
                selection=gm.home_name,
                vendor=vend,
                odds_dec=dec,
                odds_display=raw,
                p=p_home,
                hit=p_home * 10.0,
                edge=edge,
                ev=ev,
                notes=f"implied {implied*100:.1f}%"
            ))
        if best_away:
            vend, raw, dec = best_away
            implied = 1.0 / dec
            edge = p_away - implied
            ev = p_away * (dec - 1.0) - (1.0 - p_away)
            picks.append(Pick(
                game=gm.label,
                market="MONEYLINE",
                selection=gm.away_name,
                vendor=vend,
                odds_dec=dec,
                odds_display=raw,
                p=p_away,
                hit=p_away * 10.0,
                edge=edge,
                ev=ev,
                notes=f"implied {implied*100:.1f}%"
            ))
        return picks

    def _print_by_tier(title: str, picks: List[Pick], max_per_tier: int = 10) -> None:
        tiers = ["S", "A", "B"]
        any_printed = False
        for t in tiers:
            grp = [p for p in picks if p.tier() == t]
            if not grp:
                continue
            any_printed = True
            grp.sort(key=lambda x: (x.rating33(), x.ev, x.p), reverse=True)
            print(f"\
{title} — Tier {t}")
            print("-" * (len(title) + 12))
            for i, pk in enumerate(grp[:max_per_tier], start=1):
                print_pick(pk, i)
        if not any_printed:
            print(f"\
{title}")
            print("-" * len(title))
            print("None.")

    # Live refresh loop
    last_slate_refresh = 0.0
    last_props_refresh = 0.0

    # state shared between refreshes
    games_state: List[Game] = games
    probs_state: Dict[int, Tuple[float, float, float, str]] = protocol33_probs_for_slate(games_state, elos)
    odds_by_game_state: Dict[int, List[Dict[str, Any]]] = {}
    live_game_ids_state: List[int] = []

    while True:
        now_ts = time.time()
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # SLATE/ODDS refresh (30s default)
        if last_slate_refresh == 0.0 or (now_ts - last_slate_refresh) >= max(5, int(args.slate_refresh)):
            try:
                games_state = fetch_slate_games(run_date, per_page=100)
                if not games_state:
                    print(f"\
[{now_utc}] WARN: no games returned for {run_date}")
                    games_state = games
                slate_ids = {g.id for g in games_state}

                # probs (cheap; elos cached)
                probs_state = protocol33_probs_for_slate(games_state, elos)

                # odds
                odds_rows = fetch_odds_for_date(run_date, per_page=args.per_page)
                odds_rows = filter_odds_to_slate(
                    odds_rows,
                    slate_ids,
                    exclude_prediction_markets=not args.include_prediction_markets
                )
                odds_by_game_state = group_by_game(odds_rows)

                # live games
                live_game_ids_state = [g.id for g in games_state if _is_live(g.status)]

                print(f"\
=== LIVE | effective_slate_date={run_date} | now_utc={now_utc} | slate_refresh={args.slate_refresh}s | props_refresh={args.props_refresh}s ===")
                print(f"Data pulled: games={len(games_state)} | odds_rows={len(odds_rows)}")
                # Hide finished games from odds/value/arb sections (stale/settled odds can look like huge +EV).
                games_actionable = [g for g in games_state if _is_actionable(g.status)]
                if len(games_actionable) != len(games_state):
                    print(f"Note: hiding {len(games_state)-len(games_actionable)} finished games from odds/value/arb sections.")
                # Predicted win probabilities (Protocol 33 model)
                print_slate_probs(games_actionable, probs_state)

                # Per-game best lines (primary books)
                print("\
Best MONEYLINE (books: DraftKings / FanDuel / bet365 / BetMGM)")
                print("-------------------------------------------------------------")
                for gm in games_actionable:
                    rows = odds_by_game_state.get(gm.id, [])
                    best_away = _best_ml_for_side(rows, "away")
                    best_home = _best_ml_for_side(rows, "home")
                    away_txt = (f"{gm.away_name} {best_away[1]} (imp {fmt_pct(1.0 / best_away[2])}) @{best_away[0]}" if best_away else f"{gm.away_name} (no line)")
                    home_txt = (f"{gm.home_name} {best_home[1]} (imp {fmt_pct(1.0 / best_home[2])}) @{best_home[0]}" if best_home else f"{gm.home_name} (no line)")
                    print(f"- {gm.label} | {away_txt} | {home_txt}")

                # Tiered ML value picks (both teams eligible)
                ml_picks: List[Pick] = []
                for gm in games_actionable:
                    rows = odds_by_game_state.get(gm.id, [])
                    p_home, p_away, _, _ = probs_state.get(gm.id, (0.5, 0.5, 0.0, ""))
                    ml_picks.extend(_build_ml_picks_for_game(gm, rows, p_home=p_home, p_away=p_away))

                # filter to requested tiers, and user EV threshold
                ml_picks = [p for p in ml_picks if p.tier() in {"S", "A", "B"} and p.ev >= args.min_ev]

                _print_by_tier("MONEYLINE value (primary books)", ml_picks, max_per_tier=10)

                # optional arbs (only meaningful if both sides have lines)
                arbs: List[str] = []
                for gm in games_actionable:
                    rows = odds_by_game_state.get(gm.id, [])
                    # arb finder expects rows with moneyline fields present; we feed it raw but it will sanitize
                    arb = find_moneyline_arb(gm, rows)
                    if arb:
                        arbs.append(arb)
                print("\
Current Arbitrage (moneyline)")
                print("----------------------------")
                if not arbs:
                    print("None found.")
                else:
                    for a in arbs:
                        print(a)

            except Exception as e:
                print(f"\
[{now_utc}] WARN: slate refresh failed: {e}")

            last_slate_refresh = now_ts

            # If single-run mode, optionally do one props pass then exit
            if args.once and args.no_props:
                if not args.no_pause:
                    pause()
                return 0

        # PROPS refresh (15s default) — LIVE GAMES ONLY
        if not args.no_props:
            if last_props_refresh == 0.0 or (now_ts - last_props_refresh) >= max(5, int(args.props_refresh)):
                try:
                    if not live_game_ids_state:
                        # don't spam if nothing live
                        last_props_refresh = now_ts
                    else:
                        print(f"\
--- LIVE PROPS REFRESH | now_utc={now_utc} | live_games={len(live_game_ids_state)} ---")
                        any_props_printed = False
                        for gm in games_state:
                            if gm.id not in live_game_ids_state:
                                continue
                            # NOTE: NBA player_props endpoint does NOT accept vendor filtering.
                            # We filter vendors client-side when ranking.
                            props_raw = fetch_player_props_for_game(gm.id)
                            if not props_raw:
                                if DEBUG_PROPS:
                                    print(f"  {gm.label}: 0 props returned")
                                continue

                            # Try scoring within primary books first (DK/FD/...)
                            picks_primary = pick_best_player_props_for_game(
                                gm, props_raw, season=args.season, end_date=run_date,
                                min_prob=0.0, min_ev=-9999.0,
                                max_props_per_game=max(10, args.max_props_per_game * 3),
                                vendor_allow=primary_books
                            )
                            picks_primary = [p for p in picks_primary if p.tier() in {"S", "A", "B"} and p.ev >= args.min_ev]

                            # If nothing qualifies, try any vendor (some slates don't have DK/FD lines).
                            picks_any: List[Pick] = []
                            if not picks_primary:
                                picks_any = pick_best_player_props_for_game(
                                    gm, props_raw, season=args.season, end_date=run_date,
                                    min_prob=0.0, min_ev=-9999.0,
                                    max_props_per_game=max(10, args.max_props_per_game * 3),
                                    vendor_allow=None
                                )
                                picks_any = [p for p in picks_any if p.tier() in {"S", "A", "B"} and p.ev >= args.min_ev]

                            if DEBUG_PROPS:
                                # quick counts to confirm the endpoint is alive
                                primary_n = sum(1 for pr in props_raw if _norm_vendor_key(pr.get("vendor")) in primary_books)
                                print(f"  {gm.label}: props raw={len(props_raw)} | primary_vendor_lines={primary_n} | scored_primary={len(picks_primary)} | scored_any={len(picks_any)}")

                            if picks_primary or picks_any:
                                any_props_printed = True
                                print(f"\
{gm.label}")
                                if picks_primary:
                                    _print_by_tier("Player props", picks_primary, max_per_tier=args.max_props_per_game)
                                else:
                                    _print_by_tier("Player props (non-primary vendors)", picks_any, max_per_tier=args.max_props_per_game)
                            else:
                                # Endpoint is returning lines, but none qualify; show a tiny snapshot so user knows it's working.
                                any_props_printed = True
                                sample_n = 3 if not VERBOSE else 5
                                primary_rows = [pr for pr in props_raw if _norm_vendor_key(pr.get("vendor")) in primary_books]
                                rows_show = primary_rows if primary_rows else props_raw
                                print(f"\
{gm.label} — live props lines={len(props_raw)} (no tier S/A/B +EV picks)\
  sample:")
                                for pr in rows_show[:sample_n]:
                                    print("   • " + _fmt_prop_snapshot(pr, player_name_by_id))

                        if not any_props_printed:
                            print("No live player props returned for the current live games at this refresh.")
                        last_props_refresh = now_ts

                except Exception as e:
                    print(f"\
[{now_utc}] WARN: props refresh failed: {e}")
                    last_props_refresh = now_ts

                if args.once:
                    if not args.no_pause:
                        pause()
                    return 0

        # small sleep so we don't busy-loop
        time.sleep(1.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("\
ERROR:", str(e))
        pause("\
Press ENTER to close (error)...")
        raise
{"parentUuid":"0764238f-16c6-4733-b16c-bd6744b2746c","isSidechain":false,"userType":"external","cwd":"/Users/apple/ai-betting-backend","sessionId":"ae7f3802-fece-4122-bdec-44c87bda3e15","version":"2.1.20","gitBranch":"","slug":"effervescent-questing-catmull","type":"user","message":{"role":"user","content":"This session is being continued from a previous conversation that ran out of context. The summary below covers the earlier portion of the conversation.

Summary:
1. Primary Request and Intent:
   The user wants to replace the existing `jason_sim_confluence.py` file with a new updated version. They stated "lets replace jason sim with the new updated jason sime" (typo for "jason sim"). The user then provided the complete new code - a script called "PROTOCOL 33 / SIM J420N — NBA (Ball Don't Lie) — VALUE + PROPS EDITION" which is substantially different from the original jason_sim_confluence.py module.

2. Key Technical Concepts:
   - **Current jason_sim_confluence.py (v11.08)**: Win probability simulation engine that runs after base score computation, adjusts scores based on win probability alignment, returns jason_* fields for every pick
   - **New PROTOCOL 33 / SIM J420N**: Standalone NBA betting value scanner using BallDontLie API
   - BallDontLie API integration (games, odds, player props, stats, injuries, lineups)
   - Elo-based team win probability modeling
   - Player prop modeling using normal distribution (mu/sigma from game logs)
   - Live refresh functionality for odds and props
   - American-to-decimal odds conversion
   - De-vig probability calculation
   - Back-to-back game fatigue adjustments
   - Vendor filtering (DraftKings, FanDuel, bet365, BetMGM)

3. Files and Code Sections:
   - **`/Users/apple/ai-betting-backend/jason_sim_confluence.py`** (CURRENT - to be replaced)
      - 537 lines, v11.08
      - Internal scoring module for the betting backend
      - Key classes: `JasonSimConfluence`
      - Key functions: `run_confluence()`, `simulate_game()`, `evaluate_spread_ml()`, `evaluate_total()`, `evaluate_prop()`, `run_jason_confluence()`, `get_