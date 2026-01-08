# main.py - Complete Bookie-o-em Backend
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, date
import hashlib
import httpx
import os

app = FastAPI(title="Bookie-o-em API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# API KEYS
# ============================================
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "ceb2e3a6a3302e0f38fd0d34150294e9")
PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "pbk_d6f65d6a74c53d5ef9b455a9a147c853b82b")

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
PLAYBOOK_API_BASE = "https://api.playbook-api.com/v1"

SPORT_KEYS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "NCAAB": "basketball_ncaab",
    "NCAAF": "americanfootball_ncaaf"
}

# ============================================
# STORAGE
# ============================================
votes_store = {}
graded_picks_store = []

# ============================================
# MODELS
# ============================================
class VoteRequest(BaseModel):
    side: str

# ============================================
# HELPERS
# ============================================
def get_user_id(request: Request) -> str:
    ip = request.client.host if request.client else "anon"
    return hashlib.md5(ip.encode()).hexdigest()[:12]

async def fetch_json(url: str, headers: dict = None):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.get(url, headers=headers or {})
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"API Error: {url} - {e}")
            return None

# ============================================
# CORE ENDPOINTS
# ============================================
@app.get("/")
def root():
    return {"status": "online", "service": "Bookie-o-em API", "version": "2.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "models_loaded": True, "timestamp": datetime.now().isoformat()}

@app.get("/model-status")
def model_status():
    return {"status": "active", "version": "17-signal", "last_updated": datetime.now().isoformat()}

# ============================================
# LIVE ODDS - The Odds API
# ============================================
@app.get("/live/odds/{sport}")
async def get_live_odds(sport: str):
    sport_key = SPORT_KEYS.get(sport.upper(), "basketball_nba")
    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds?apiKey={ODDS_API_KEY}&regions=us&markets=spreads,totals,h2h&oddsFormat=american"
    
    data = await fetch_json(url)
    if not data:
        return {"games": [], "sport": sport}
    
    games = []
    for game in data:
        book_odds = {}
        best = {"spread_odds": -999, "over_odds": -999, "under_odds": -999, "home_ml": -999, "away_ml": -999}
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")
        
        for bm in game.get("bookmakers", []):
            book = bm.get("key", "unknown").lower()
            bd = {"spread": 0, "spread_odds": -110, "total": 0, "over_odds": -110, "under_odds": -110, "home_ml": 0, "away_ml": 0}
            
            for mkt in bm.get("markets", []):
                if mkt["key"] == "spreads":
                    for o in mkt.get("outcomes", []):
                        if o["name"] == home_team:
                            bd["spread"] = o.get("point", 0)
                            bd["spread_odds"] = o.get("price", -110)
                            if bd["spread_odds"] > best["spread_odds"]:
                                best["spread_odds"], best["spread_book"] = bd["spread_odds"], book
                elif mkt["key"] == "totals":
                    for o in mkt.get("outcomes", []):
                        bd["total"] = o.get("point", 0)
                        if o["name"] == "Over":
                            bd["over_odds"] = o.get("price", -110)
                            if bd["over_odds"] > best["over_odds"]:
                                best["over_odds"], best["over_book"] = bd["over_odds"], book
                        else:
                            bd["under_odds"] = o.get("price", -110)
                            if bd["under_odds"] > best["under_odds"]:
                                best["under_odds"], best["under_book"] = bd["under_odds"], book
                elif mkt["key"] == "h2h":
                    for o in mkt.get("outcomes", []):
                        if o["name"] == home_team:
                            bd["home_ml"] = o.get("price", 0)
                            if bd["home_ml"] > best["home_ml"]:
                                best["home_ml"], best["home_ml_book"] = bd["home_ml"], book
                        else:
                            bd["away_ml"] = o.get("price", 0)
                            if bd["away_ml"] > best["away_ml"]:
                                best["away_ml"], best["away_ml_book"] = bd["away_ml"], book
            book_odds[book] = bd
        
        games.append({
            "home_team": home_team, "away_team": away_team,
            "time": game.get("commence_time", ""),
            "spread": list(book_odds.values())[0]["spread"] if book_odds else 0,
            "total": list(book_odds.values())[0]["total"] if book_odds else 0,
            "books": book_odds, "best": best
        })
    
    return {"games": games, "sport": sport, "updated_at": datetime.now().isoformat()}

# ============================================
# SHARP MONEY - Playbook API
# ============================================
@app.get("/sharp-money/{sport}")
async def get_sharp_money(sport: str):
    headers = {"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
    url = f"{PLAYBOOK_API_BASE}/sharp-action/{sport.lower()}"
    data = await fetch_json(url, headers)
    
    if not data:
        return {"signals": [], "sport": sport}
    
    signals = []
    items = data.get("signals", data if isinstance(data, list) else [])
    for item in items:
        signals.append({
            "game": item.get("game", item.get("matchup", "")),
            "side": item.get("side", ""),
            "divergence": item.get("divergence", 0),
            "strength": "STRONG" if abs(item.get("divergence", 0)) > 15 else "MODERATE",
            "timestamp": datetime.now().isoformat()
        })
    
    return {"signals": signals, "sport": sport, "updated_at": datetime.now().isoformat()}

# ============================================
# BETTING SPLITS - Playbook API
# ============================================
@app.get("/live/splits/{sport}")
async def get_splits(sport: str):
    headers = {"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
    url = f"{PLAYBOOK_API_BASE}/betting-splits/{sport.lower()}"
    data = await fetch_json(url, headers)
    
    if not data:
        return []
    
    return data if isinstance(data, list) else data.get("games", [])

# ============================================
# INJURIES - ESPN (Free)
# ============================================
@app.get("/live/injuries/{sport}")
async def get_injuries(sport: str):
    sport_map = {"NBA": "basketball/nba", "NFL": "football/nfl", "MLB": "baseball/mlb", "NHL": "hockey/nhl"}
    espn_sport = sport_map.get(sport.upper(), "basketball/nba")
    
    data = await fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/injuries")
    if not data:
        return []
    
    injuries = []
    for team in data.get("teams", []):
        team_name = team.get("team", {}).get("displayName", "")
        for inj in team.get("injuries", []):
            injuries.append({
                "team": team_name,
                "player": inj.get("athlete", {}).get("displayName", ""),
                "position": inj.get("athlete", {}).get("position", {}).get("abbreviation", ""),
                "status": inj.get("status", ""),
                "injury": inj.get("type", {}).get("text", "")
            })
    return injuries

# ============================================
# SMASH SPOTS / SLATE
# ============================================
@app.get("/live/slate/{sport}")
async def get_slate(sport: str):
    # Get odds first
    odds_data = await get_live_odds(sport)
    games = odds_data.get("games", [])
    
    slate = []
    for g in games:
        slate.append({
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "time": g.get("time", ""),
            "spread": g.get("spread", 0),
            "total": g.get("total", 0),
            "confidence": 65,  # Default - your signal engine calculates this
            "tier": "PARTIAL_ALIGNMENT"
        })
    
    return {"slate": slate, "sport": sport}

# ============================================
# COMMUNITY VOTING
# ============================================
@app.get("/votes/{game_vote_id}")
async def get_votes(game_vote_id: str, request: Request):
    user_id = get_user_id(request)
    if game_vote_id not in votes_store:
        return {"game_vote_id": game_vote_id, "home": 0, "away": 0, "over": 0, "under": 0, "total": 0, "userVote": None}
    
    data = votes_store[game_vote_id]
    return {
        "game_vote_id": game_vote_id,
        "home": data.get("home", 0), "away": data.get("away", 0),
        "over": data.get("over", 0), "under": data.get("under", 0),
        "total": sum([data.get(k, 0) for k in ["home", "away", "over", "under"]]),
        "userVote": data.get("user_votes", {}).get(user_id)
    }

@app.post("/votes/{game_vote_id}")
async def submit_vote(game_vote_id: str, vote: VoteRequest, request: Request):
    user_id = get_user_id(request)
    if vote.side not in ["home", "away", "over", "under"]:
        raise HTTPException(status_code=400, detail="Invalid side")
    
    if game_vote_id not in votes_store:
        votes_store[game_vote_id] = {"home": 0, "away": 0, "over": 0, "under": 0, "user_votes": {}}
    
    data = votes_store[game_vote_id]
    if user_id in data["user_votes"]:
        data[data["user_votes"][user_id]] -= 1
    
    data[vote.side] += 1
    data["user_votes"][user_id] = vote.side
    
    return await get_votes(game_vote_id, request)

@app.get("/votes/leaderboard")
async def get_leaderboard():
    return {"weekly": [], "ai_record": {"correct": 0, "total": 0}}

# ============================================
# GRADING
# ============================================
@app.get("/grader/picks")
async def get_graded_picks():
    return graded_picks_store

@app.post("/grader/grade")
async def grade_pick(data: dict):
    pick = {"id": data.get("pick_id"), "result": data.get("result"), "graded_at": datetime.now().isoformat()}
    graded_picks_store.append(pick)
    return {"success": True, "pick": pick}

@app.get("/grader/weights")
def get_weights():
    return {"sharp_money": 18, "line_value": 15, "ml_value": 14, "ensemble": 10, "lstm": 10}

# ============================================
# ESOTERIC
# ============================================
@app.get("/esoteric/today-energy")
def get_today_energy():
    phases = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous", "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
    moon = phases[datetime.now().timetuple().tm_yday % 8]
    
    digits = str(datetime.now().year) + str(datetime.now().month).zfill(2) + str(datetime.now().day).zfill(2)
    lp = sum(int(d) for d in digits)
    while lp > 9:
        lp = sum(int(d) for d in str(lp))
    
    return {"moon_phase": moon, "life_path": lp, "date": date.today().isoformat()}

# ============================================
# RUN
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
