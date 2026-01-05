"""
FastAPI - AI Sports Betting API v4.1 with Player Props
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime, date
import requests
import os

try:
    from advanced_ml_backend import MasterPredictionSystem
    predictor = MasterPredictionSystem()
except Exception as e:
    print(f"Warning: Could not load ML system: {e}")
    predictor = None

import uvicorn

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "6e6da61eec951acb5fa9010293b89279")
PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "pbk_095c2ac98199f43d0b409f90031908bb05b8")


class GematriaCalculator:
    SIMPLE = {chr(i+64): i for i in range(1, 27)}
    PYTHAGOREAN = {'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7,'H':8,'I':9,'J':1,'K':2,'L':3,'M':4,'N':5,'O':6,'P':7,'Q':8,'R':9,'S':1,'T':2,'U':3,'V':4,'W':5,'X':6,'Y':7,'Z':8}
    
    def calculate_simple(self, text):
        return sum(self.SIMPLE.get(c, 0) for c in text.upper().replace(" ", ""))
    
    def calculate_pythagorean(self, text):
        total = sum(self.PYTHAGOREAN.get(c, 0) for c in text.upper().replace(" ", ""))
        return self.reduce(total)
    
    def reduce(self, num):
        while num > 9 and num not in [11, 22, 33]:
            num = sum(int(d) for d in str(num))
        return num
    
    def full_analysis(self, text):
        simple = self.calculate_simple(text)
        pyth = self.calculate_pythagorean(text)
        red = self.reduce(simple)
        return {"text": text, "simple": simple, "pythagorean": pyth, "reduced": red}


class NumerologyCalculator:
    MEANINGS = {
        1: {"energy": "Leadership", "sports": "Individual excellence"},
        2: {"energy": "Partnership", "sports": "Team chemistry, close games"},
        3: {"energy": "Creativity", "sports": "High scoring"},
        4: {"energy": "Stability", "sports": "Defense dominates"},
        5: {"energy": "Change", "sports": "Momentum shifts, upsets"},
        6: {"energy": "Harmony", "sports": "Home team advantage"},
        7: {"energy": "Spirituality", "sports": "Underdogs, unexpected"},
        8: {"energy": "Power", "sports": "Favorites cover"},
        9: {"energy": "Completion", "sports": "Blowouts"},
        11: {"energy": "Master Intuition", "sports": "Trust your read"},
        22: {"energy": "Master Builder", "sports": "Dynasty teams"},
        33: {"energy": "Master Teacher", "sports": "Legacy games"}
    }
    
    def reduce(self, num):
        while num > 9 and num not in [11, 22, 33]:
            num = sum(int(d) for d in str(num))
        return num
    
    def date_energy(self, d):
        life_path = self.reduce(d.month + d.day + sum(int(x) for x in str(d.year)))
        meaning = self.MEANINGS.get(life_path, {})
        power_day = life_path in [8, 11, 22]
        upset = life_path in [5, 7]
        return {"date": d.isoformat(), "life_path": life_path, "day_energy": self.reduce(d.day), "meaning": meaning, "power_day": power_day, "upset_potential": upset}


class SacredGeometry:
    FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
    
    def vortex_root(self, num):
        while num > 9:
            num = sum(int(d) for d in str(num))
        return num
    
    def analyze(self, num):
        root = self.vortex_root(int(num))
        near_fib = min(self.FIBONACCI, key=lambda x: abs(x - num))
        is_sacred = root in [3, 6, 9]
        fib_aligned = abs(num - near_fib) < 3
        return {"value": num, "digital_root": root, "is_sacred": is_sacred, "tesla_energy": is_sacred, "nearest_fibonacci": near_fib, "fib_aligned": fib_aligned}


class AstrologyCalculator:
    MOON_CYCLE = 29.53
    
    def moon_phase(self, d):
        known_new = date(2000, 1, 6)
        days = (d - known_new).days
        pos = (days % self.MOON_CYCLE) / self.MOON_CYCLE
        if pos < 0.125:
            phase = "New Moon"
        elif pos < 0.25:
            phase = "Waxing Crescent"
        elif pos < 0.375:
            phase = "First Quarter"
        elif pos < 0.5:
            phase = "Waxing Gibbous"
        elif pos < 0.625:
            phase = "Full Moon"
        elif pos < 0.75:
            phase = "Waning Gibbous"
        elif pos < 0.875:
            phase = "Last Quarter"
        else:
            phase = "Waning Crescent"
        full = 0.45 < pos < 0.55
        new = pos < 0.1 or pos > 0.9
        chaos = "HIGH" if full else "LOW"
        return {"phase": phase, "position": round(pos, 3), "full_moon": full, "new_moon": new, "chaos_factor": chaos}
    
    def zodiac(self, d):
        elements = {"Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire", "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth", "Gemini": "Air", "Libra": "Air", "Aquarius": "Air", "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water"}
        signs = [("Capricorn", 1, 19), ("Aquarius", 2, 18), ("Pisces", 3, 20), ("Aries", 4, 19), ("Taurus", 5, 20), ("Gemini", 6, 20), ("Cancer", 7, 22), ("Leo", 8, 22), ("Virgo", 9, 22), ("Libra", 10, 22), ("Scorpio", 11, 21), ("Sagittarius", 12, 21), ("Capricorn", 12, 31)]
        for sign, month, day in signs:
            if d.month < month or (d.month == month and d.day <= day):
                return {"sign": sign, "element": elements.get(sign, "Unknown")}
        return {"sign": "Capricorn", "element": "Earth"}


class EsotericAnalyzer:
    def __init__(self):
        self.gematria = GematriaCalculator()
        self.numerology = NumerologyCalculator()
        self.sacred = SacredGeometry()
        self.astrology = AstrologyCalculator()
    
    def analyze_matchup(self, home, away, game_date, total=None):
        home_gem = self.gematria.full_analysis(home)
        away_gem = self.gematria.full_analysis(away)
        date_num = self.numerology.date_energy(game_date)
        moon = self.astrology.moon_phase(game_date)
        zodiac = self.astrology.zodiac(game_date)
        sacred = self.sacred.analyze(total) if total else None
        edge_score = 50
        factors = []
        if date_num["power_day"]:
            edge_score += 10
            factors.append("Power day - favorites strengthened")
        if date_num["upset_potential"]:
            edge_score -= 10
            factors.append("Upset energy in numerology")
        if moon["full_moon"]:
            edge_score -= 15
            factors.append("Full Moon CHAOS - expect the unexpected")
        if moon["new_moon"]:
            edge_score -= 5
            factors.append("New Moon - underdog energy")
        if zodiac["element"] == "Fire":
            factors.append("Fire sign - lean OVER")
        elif zodiac["element"] == "Earth":
            factors.append("Earth sign - lean UNDER")
        if sacred and sacred["tesla_energy"]:
            factors.append("Tesla 3-6-9 alignment!")
            edge_score += 5
        gem_diff = home_gem["simple"] - away_gem["simple"]
        if abs(gem_diff) > 20:
            gem_fav = home if gem_diff > 0 else away
            factors.append("Gematria favors " + gem_fav)
        if edge_score > 55:
            lean = "FAVORITE"
        elif edge_score < 45:
            lean = "UNDERDOG"
        else:
            lean = "NEUTRAL"
        edge_score = min(max(edge_score, 0), 100)
        result = {
            "matchup": away + " @ " + home,
            "date": game_date.isoformat(),
            "gematria": {"home": home_gem, "away": away_gem, "difference": gem_diff},
            "numerology": date_num,
            "moon_phase": moon,
            "zodiac": zodiac,
            "sacred_geometry": sacred,
            "esoteric_edge": {"score": edge_score, "factors": factors, "lean": lean}
        }
        return result
    
    def analyze_player_prop(self, player_name, prop_line, prop_type="points"):
        player_gem = self.gematria.full_analysis(player_name)
        line_sacred = self.sacred.analyze(prop_line)
        today = date.today()
        date_num = self.numerology.date_energy(today)
        moon = self.astrology.moon_phase(today)
        factors = []
        edge_score = 50
        if player_gem["reduced"] in [3, 6, 9]:
            factors.append("Player name has Tesla energy - OVER lean")
            edge_score += 8
        if line_sacred["tesla_energy"]:
            factors.append("Prop line has sacred number alignment")
            edge_score += 5
        if line_sacred["fib_aligned"]:
            factors.append("Line near Fibonacci number - expect to hit exact")
        if date_num["life_path"] == 3 and prop_type == "points":
            factors.append("Life Path 3 (creativity) favors high scoring")
            edge_score += 7
        if moon["full_moon"]:
            factors.append("Full Moon - volatile performances expected")
            edge_score -= 5
        if edge_score > 55:
            lean = "OVER"
        elif edge_score < 45:
            lean = "UNDER"
        else:
            lean = "NEUTRAL"
        return {
            "player": player_name,
            "prop_type": prop_type,
            "line": prop_line,
            "gematria": player_gem,
            "line_sacred": line_sacred,
            "date_energy": date_num,
            "moon": moon,
            "esoteric_edge": {"score": edge_score, "factors": factors, "lean": lean}
        }


esoteric = EsotericAnalyzer()


class LiveOddsService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
    
    def get_live_odds(self, sport="basketball_nba", bookmakers="fanduel,draftkings"):
        url = self.base_url + "/sports/" + sport + "/odds"
        params = {"apiKey": self.api_key, "regions": "us", "markets": "h2h,spreads,totals", "bookmakers": bookmakers, "oddsFormat": "american"}
        r = requests.get(url, params=params)
        if r.status_code == 200:
            games = r.json()
            formatted = self._format(games)
            remaining = r.headers.get('x-requests-remaining', 'unknown')
            return {"success": True, "sport": sport, "games_count": len(games), "games": formatted, "api_usage": {"remaining": remaining}}
        return {"success": False, "error": r.status_code}
    
    def get_events(self, sport="basketball_nba"):
        url = self.base_url + "/sports/" + sport + "/events"
        params = {"apiKey": self.api_key}
        r = requests.get(url, params=params)
        if r.status_code == 200:
            return {"success": True, "events": r.json(), "api_usage": {"remaining": r.headers.get('x-requests-remaining', 'unknown')}}
        return {"success": False, "error": r.status_code}
    
    def get_player_props(self, sport="basketball_nba", event_id=None, markets="player_points,player_rebounds,player_assists"):
        if event_id:
            url = self.base_url + "/sports/" + sport + "/events/" + event_id + "/odds"
        else:
            url = self.base_url + "/sports/" + sport + "/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": markets,
            "bookmakers": "fanduel,draftkings",
            "oddsFormat": "american"
        }
        r = requests.get(url, params=params)
        if r.status_code == 200:
            data = r.json()
            props = self._format_props(data)
            return {
                "success": True,
                "sport": sport,
                "event_id": event_id,
                "props_count": len(props),
                "props": props,
                "api_usage": {"remaining": r.headers.get('x-requests-remaining', 'unknown')}
            }
        return {"success": False, "error": r.status_code, "message": r.text}
    
    def _format(self, games):
        result = []
        for g in games:
            fg = {"id": g.get("id"), "commence_time": g.get("commence_time"), "home_team": g.get("home_team"), "away_team": g.get("away_team"), "bookmakers": {}}
            for b in g.get("bookmakers", []):
                fg["bookmakers"][b["key"]] = {"markets": {}}
                for m in b.get("markets", []):
                    outcomes = {}
                    for o in m.get("outcomes", []):
                        outcomes[o["name"]] = {"price": o.get("price"), "point": o.get("point")}
                    fg["bookmakers"][b["key"]]["markets"][m["key"]] = outcomes
            result.append(fg)
        return result
    
    def _format_props(self, data):
        props = []
        games = data if isinstance(data, list) else [data]
        for game in games:
            game_info = {
                "game_id": game.get("id"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "commence_time": game.get("commence_time")
            }
            for bookmaker in game.get("bookmakers", []):
                book_name = bookmaker.get("key")
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "")
                    if "player_" in market_key:
                        for outcome in market.get("outcomes", []):
                            prop = {
                                "game": game_info,
                                "bookmaker": book_name,
                                "market": market_key,
                                "player": outcome.get("description", outcome.get("name", "")),
                                "type": outcome.get("name", ""),
                                "line": outcome.get("point"),
                                "odds": outcome.get("price")
                            }
                            props.append(prop)
        return props


class BettingSplitsService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.playbook-api.com/v1"
    
    def get_splits(self, league="NFL"):
        try:
            url = self.base_url + "/splits"
            params = {"league": league.upper(), "api_key": self.api_key}
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return {"success": True, "league": league, "splits": r.json()}
            return {"success": False, "error": r.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


odds_service = LiveOddsService(ODDS_API_KEY)
splits_service = BettingSplitsService(PLAYBOOK_API_KEY)

app = FastAPI(title="AI Sports Betting API", description="ML + Live Odds + Splits + ESOTERIC + PLAYER PROPS", version="4.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class EdgeRequest(BaseModel):
    your_probability: float = Field(..., ge=0, le=1)
    betting_odds: float


class EsotericRequest(BaseModel):
    home_team: str
    away_team: str
    game_date: str
    predicted_total: Optional[float] = None


class PlayerPropRequest(BaseModel):
    player_name: str
    prop_line: float
    prop_type: Optional[str] = "points"


@app.get("/")
async def root():
    return {"status": "online", "message": "AI Sports Betting API v4.1 with PLAYER PROPS", "version": "4.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "esoteric": "enabled", "player_props": "enabled"}


@app.get("/model-status")
async def model_status():
    models = {
        "ensemble_stacking": "ready",
        "lstm_network": "fallback_mode",
        "matchup_specific": "ready",
        "monte_carlo": "ready",
        "line_analyzer": "ready",
        "rest_fatigue": "ready",
        "injury_impact": "ready",
        "edge_calculator": "ready",
        "gematria": "ready",
        "numerology": "ready",
        "sacred_geometry": "ready",
        "astrology": "ready",
        "player_props": "ready"
    }
    return {"status": "operational", "models": models, "total_models": 13, "version": "4.1.0"}


@app.post("/calculate-edge")
async def calc_edge(req: EdgeRequest):
    odds = req.betting_odds
    prob = req.your_probability
    if odds > 0:
        dec = (odds / 100) + 1
    else:
        dec = (100 / abs(odds)) + 1
    edge = ((prob * dec) - 1) * 100
    kelly = max(0, (prob * (dec - 1) - (1 - prob)) / (dec - 1))
    rec = "BET" if edge > 2 else "NO BET"
    return {"status": "success", "edge_analysis": {"edge_percent": round(edge, 2), "kelly": round(kelly, 4), "recommendation": rec}}


@app.get("/live-odds")
async def live_odds(sport: str = "basketball_nba"):
    return odds_service.get_live_odds(sport)


@app.get("/live-games")
async def live_games(sport: str = "basketball_nba"):
    data = odds_service.get_live_odds(sport)
    if not data.get("success"):
        return data
    simple = []
    for g in data["games"]:
        sg = {"id": g["id"], "home_team": g["home_team"], "away_team": g["away_team"], "start_time": g["commence_time"], "fanduel": None, "draftkings": None}
        if "fanduel" in g.get("bookmakers", {}):
            sg["fanduel"] = g["bookmakers"]["fanduel"]["markets"]
        if "draftkings" in g.get("bookmakers", {}):
            sg["draftkings"] = g["bookmakers"]["draftkings"]["markets"]
        simple.append(sg)
    return {"success": True, "games": simple, "api_usage": data.get("api_usage")}


@app.get("/live-odds/nba")
async def nba():
    return await live_games("basketball_nba")


@app.get("/live-odds/nfl")
async def nfl():
    return await live_games("football_nfl")


@app.get("/live-odds/mlb")
async def mlb():
    return await live_games("baseball_mlb")


@app.get("/splits")
async def splits(league: str = "NFL"):
    return splits_service.get_splits(league)


@app.get("/splits/nfl")
async def splits_nfl():
    return await splits("NFL")


@app.get("/splits/nba")
async def splits_nba():
    return await splits("NBA")


@app.get("/splits/mlb")
async def splits_mlb():
    return await splits("MLB")


@app.get("/splits/nhl")
async def splits_nhl():
    return await splits("NHL")


@app.post("/esoteric/analyze")
async def esoteric_analyze(req: EsotericRequest):
    try:
        game_date = datetime.strptime(req.game_date, "%Y-%m-%d").date()
        result = esoteric.analyze_matchup(req.home_team, req.away_team, game_date, req.predicted_total)
        return {"success": True, "analysis": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/esoteric/gematria/{text}")
async def gematria(text: str):
    result = esoteric.gematria.full_analysis(text)
    return {"success": True, "analysis": result}


@app.get("/esoteric/numerology/{date_str}")
async def numerology(date_str: str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        result = esoteric.numerology.date_energy(d)
        return {"success": True, "analysis": result}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@app.get("/esoteric/moon/{date_str}")
async def moon(date_str: str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        result = esoteric.astrology.moon_phase(d)
        return {"success": True, "analysis": result}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format")


@app.get("/esoteric/sacred/{number}")
async def sacred(number: float):
    result = esoteric.sacred.analyze(number)
    return {"success": True, "analysis": result}


@app.get("/esoteric/today")
async def today_energy():
    d = date.today()
    num = esoteric.numerology.date_energy(d)
    moon = esoteric.astrology.moon_phase(d)
    zod = esoteric.astrology.zodiac(d)
    return {"success": True, "date": d.isoformat(), "numerology": num, "moon": moon, "zodiac": zod}


# ============================================
# PLAYER PROPS ENDPOINTS
# ============================================

@app.get("/props/events")
async def get_events(sport: str = "basketball_nba"):
    """Get list of upcoming events/games"""
    return odds_service.get_events(sport)


@app.get("/props")
async def get_props(sport: str = "basketball_nba", markets: str = "player_points,player_rebounds,player_assists"):
    """Get player props for all games in a sport"""
    return odds_service.get_player_props(sport=sport, markets=markets)


@app.get("/props/nba")
async def get_nba_props():
    """Get NBA player props (points, rebounds, assists)"""
    return odds_service.get_player_props(sport="basketball_nba", markets="player_points,player_rebounds,player_assists")


@app.get("/props/nfl")
async def get_nfl_props():
    """Get NFL player props (passing, rushing, receiving)"""
    return odds_service.get_player_props(sport="football_nfl", markets="player_pass_yds,player_rush_yds,player_reception_yds")


@app.get("/props/nba/points")
async def get_nba_points():
    """Get NBA player points props"""
    return odds_service.get_player_props(sport="basketball_nba", markets="player_points")


@app.get("/props/nba/rebounds")
async def get_nba_rebounds():
    """Get NBA player rebounds props"""
    return odds_service.get_player_props(sport="basketball_nba", markets="player_rebounds")


@app.get("/props/nba/assists")
async def get_nba_assists():
    """Get NBA player assists props"""
    return odds_service.get_player_props(sport="basketball_nba", markets="player_assists")


@app.get("/props/nba/threes")
async def get_nba_threes():
    """Get NBA player 3-pointers props"""
    return odds_service.get_player_props(sport="basketball_nba", markets="player_threes")


@app.get("/props/nhl")
async def get_nhl_props():
    """Get NHL player props (points, goals, assists, shots)"""
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_points,player_goals,player_assists,player_shots_on_goal")


@app.get("/props/nhl/points")
async def get_nhl_points():
    """Get NHL player points props"""
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_points")


@app.get("/props/nhl/goals")
async def get_nhl_goals():
    """Get NHL player goals props"""
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_goals")


@app.get("/props/nhl/assists")
async def get_nhl_assists():
    """Get NHL player assists props"""
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_assists")


@app.get("/props/nhl/shots")
async def get_nhl_shots():
    """Get NHL player shots on goal props"""
    return odds_service.get_player_props(sport="icehockey_nhl", markets="player_shots_on_goal")


@app.get("/props/mlb")
async def get_mlb_props():
    """Get MLB player props (hits, total bases, strikeouts, etc.)"""
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_hits,batter_total_bases,batter_rbis,batter_runs_scored,pitcher_strikeouts")


@app.get("/props/mlb/hits")
async def get_mlb_hits():
    """Get MLB batter hits props"""
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_hits")


@app.get("/props/mlb/bases")
async def get_mlb_bases():
    """Get MLB batter total bases props"""
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_total_bases")


@app.get("/props/mlb/strikeouts")
async def get_mlb_strikeouts():
    """Get MLB pitcher strikeouts props"""
    return odds_service.get_player_props(sport="baseball_mlb", markets="pitcher_strikeouts")


@app.get("/props/mlb/rbis")
async def get_mlb_rbis():
    """Get MLB batter RBIs props"""
    return odds_service.get_player_props(sport="baseball_mlb", markets="batter_rbis")


@app.post("/props/analyze")
async def analyze_prop(req: PlayerPropRequest):
    """Analyze a player prop with esoteric factors"""
    result = esoteric.analyze_player_prop(req.player_name, req.prop_line, req.prop_type)
    return {"success": True, "analysis": result}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
