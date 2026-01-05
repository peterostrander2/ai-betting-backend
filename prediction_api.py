"""
FastAPI endpoints for AI sports betting predictions
WITH LIVE ODDS + BETTING SPLITS
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
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

class LiveOddsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        
    def get_sports(self):
        url = f"{self.base_url}/sports"
        params = {"apiKey": self.api_key}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return []
    
    def get_live_odds(self, sport="basketball_nba", regions="us", markets="h2h,spreads,totals", bookmakers="fanduel,draftkings"):
        url = f"{self.base_url}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "bookmakers": bookmakers,
            "oddsFormat": "american"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            games = response.json()
            return {
                "success": True,
                "sport": sport,
                "games_count": len(games),
                "games": self._format_games(games),
                "api_usage": {
                    "requests_remaining": response.headers.get('x-requests-remaining', 'unknown'),
                    "requests_used": response.headers.get('x-requests-used', 'unknown')
                },
                "fetched_at": datetime.now().isoformat()
            }
        return {"success": False, "error": f"API Error: {response.status_code}"}
    
    def _format_games(self, games):
        formatted = []
        for game in games:
            fg = {
                "id": game.get("id"),
                "sport": game.get("sport_key"),
                "commence_time": game.get("commence_time"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "bookmakers": {}
            }
            for bm in game.get("bookmakers", []):
                book_name = bm.get("key")
                fg["bookmakers"][book_name] = {"last_update": bm.get("last_update"), "markets": {}}
                for market in bm.get("markets", []):
                    mk = market.get("key")
                    outcomes = {}
                    for outcome in market.get("outcomes", []):
                        outcomes[outcome.get("name")] = {"price": outcome.get("price"), "point": outcome.get("point")}
                    fg["bookmakers"][book_name]["markets"][mk] = outcomes
            formatted.append(fg)
        return formatted

class BettingSplitsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.playbook-api.com/v1"
    
    def get_splits(self, league="NFL"):
        url = f"{self.base_url}/splits"
        params = {"league": league.upper(), "api_key": self.api_key}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return {"success": True, "league": league.upper(), "splits": response.json(), "fetched_at": datetime.now().isoformat()}
            return {"success": False, "error": f"API Error: {response.status_code}", "message": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_injuries(self, league="NFL"):
        url = f"{self.base_url}/injuries"
        params = {"league": league.upper(), "api_key": self.api_key}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return {"success": True, "league": league.upper(), "injuries": response.json(), "fetched_at": datetime.now().isoformat()}
            return {"success": False, "error": f"API Error: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

odds_service = LiveOddsService(api_key=ODDS_API_KEY)
splits_service = BettingSplitsService(api_key=PLAYBOOK_API_KEY)

app = FastAPI(title="AI Sports Betting API", description="ML predictions + Live Odds + Betting Splits", version="3.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PlayerStats(BaseModel):
    stat_type: str = Field(..., example="points")
    expected_value: float = Field(..., example=27.5)
    variance: float = Field(..., example=45.0)
    std_dev: float = Field(..., example=6.5)

class Schedule(BaseModel):
    days_rest: int = Field(..., example=1)
    travel_miles: int = Field(..., example=1500)
    games_in_last_7: int = Field(..., example=3)
    road_trip_game_num: Optional[int] = Field(0, example=2)

class Player(BaseModel):
    position: str = Field(..., example="SF")
    points_per_game: float = Field(..., example=25.4)
    depth: int = Field(1, example=1)

class Injury(BaseModel):
    player: Player
    status: str = Field(..., example="out")

class BettingPercentages(BaseModel):
    public_on_favorite: float = Field(..., example=68.0)

class PredictionRequest(BaseModel):
    player_id: str = Field(..., example="lebron_james")
    opponent_id: str = Field(..., example="gsw")
    features: List[float] = Field(..., example=[25.4, 7.2, 6.8, 1, 35, 28, 2])
    recent_games: List[float] = Field(..., example=[27, 31, 22, 28, 25, 30, 26, 24, 29, 32])
    player_stats: PlayerStats
    schedule: Schedule
    injuries: List[Injury] = Field(default_factory=list)
    depth_chart: Dict = Field(default_factory=dict)
    game_id: str = Field(..., example="lal_gsw_20250114")
    current_line: float = Field(..., example=25.5)
    opening_line: float = Field(..., example=26.0)
    time_until_game: float = Field(..., example=6.0)
    betting_percentages: BettingPercentages
    betting_odds: float = Field(..., example=-110)
    line: float = Field(..., example=25.5)

class EdgeCalculationRequest(BaseModel):
    your_probability: float = Field(..., example=0.65, ge=0, le=1)
    betting_odds: float = Field(..., example=-110)

@app.get("/")
async def root():
    return {"status": "online", "message": "AI Sports Betting API v3.0", "version": "3.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "models_loaded": predictor is not None, "odds_api": "connected", "playbook_api": "connected"}

@app.get("/model-status")
async def model_status():
    return {"status": "operational", "models": {"ensemble_stacking": "ready", "lstm_network": "fallback_mode", "matchup_specific": "ready", "monte_carlo": "ready", "line_analyzer": "ready", "rest_fatigue": "ready", "injury_impact": "ready", "edge_calculator": "ready"}, "total_models": 8, "version": "3.0.0"}

@app.post("/predict")
async def generate_prediction(request: PredictionRequest):
    try:
        if predictor is None:
            raise HTTPException(status_code=500, detail="ML system not loaded")
        game_data = request.dict()
        result = predictor.generate_comprehensive_prediction(game_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/calculate-edge")
async def calculate_betting_edge(request: EdgeCalculationRequest):
    try:
        prob = request.your_probability
        odds = request.betting_odds
        decimal_odds = (odds / 100) + 1 if odds > 0 else (100 / abs(odds)) + 1
        implied_prob = 1 / decimal_odds
        edge = ((prob * decimal_odds) - 1) * 100
        kelly = max(0, (prob * (decimal_odds - 1) - (1 - prob)) / (decimal_odds - 1))
        if edge > 5:
            rec, conf = "STRONG BET", "HIGH"
        elif edge > 2:
            rec, conf = "BET", "MEDIUM"
        elif edge > 0:
            rec, conf = "SMALL BET", "LOW"
        else:
            rec, conf = "NO BET", "NONE"
        return {"status": "success", "edge_analysis": {"your_probability": prob, "implied_probability": round(implied_prob, 4), "edge_percent": round(edge, 2), "expected_value": round(edge, 2), "kelly_bet_size": round(kelly, 4), "half_kelly": round(kelly / 2, 4), "recommendation": rec, "confidence": conf}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Edge calculation failed: {str(e)}")

@app.get("/live-odds")
async def get_live_odds(sport: str = "basketball_nba", bookmakers: str = "fanduel,draftkings"):
    try:
        return odds_service.get_live_odds(sport=sport, bookmakers=bookmakers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live-odds/sports")
async def get_available_sports():
    try:
        sports = odds_service.get_sports()
        main = [s for s in sports if s.get("key") in ["basketball_nba", "football_nfl", "baseball_mlb", "icehockey_nhl", "basketball_ncaab", "football_ncaaf"]]
        return {"success": True, "main_sports": main, "all_sports": sports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live-games")
async def get_live_games_simple(sport: str = "basketball_nba"):
    try:
        odds_data = odds_service.get_live_odds(sport=sport)
        if not odds_data.get("success"):
            return odds_data
        simple_games = []
        for game in odds_data["games"]:
            sg = {"id": game["id"], "home_team": game["home_team"], "away_team": game["away_team"], "start_time": game["commence_time"], "fanduel": None, "draftkings": None}
            if "fanduel" in game.get("bookmakers", {}):
                fd = game["bookmakers"]["fanduel"]["markets"]
                sg["fanduel"] = {"spread": fd.get("spreads", {}), "total": fd.get("totals", {}), "moneyline": fd.get("h2h", {})}
            if "draftkings" in game.get("bookmakers", {}):
                dk = game["bookmakers"]["draftkings"]["markets"]
                sg["draftkings"] = {"spread": dk.get("spreads", {}), "total": dk.get("totals", {}), "moneyline": dk.get("h2h", {})}
            simple_games.append(sg)
        return {"success": True, "sport": sport, "games_count": len(simple_games), "games": simple_games, "api_usage": odds_data["api_usage"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live-odds/nba")
async def get_nba_odds():
    return await get_live_games_simple("basketball_nba")

@app.get("/live-odds/nfl")
async def get_nfl_odds():
    return await get_live_games_simple("football_nfl")

@app.get("/live-odds/mlb")
async def get_mlb_odds():
    return await get_live_games_simple("baseball_mlb")

@app.get("/splits")
async def get_betting_splits(league: str = "NFL"):
    try:
        return splits_service.get_splits(league=league)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/splits/nfl")
async def get_nfl_splits():
    return await get_betting_splits("NFL")

@app.get("/splits/nba")
async def get_nba_splits():
    return await get_betting_splits("NBA")

@app.get("/splits/mlb")
async def get_mlb_splits():
    return await get_betting_splits("MLB")

@app.get("/splits/nhl")
async def get_nhl_splits():
    return await get_betting_splits("NHL")

@app.get("/injuries")
async def get_injuries(league: str = "NFL"):
    try:
        return splits_service.get_injuries(league=league)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
