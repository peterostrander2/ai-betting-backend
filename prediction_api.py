"""
FastAPI endpoints for AI sports betting predictions
WITH LIVE ODDS (The Odds API) + BETTING SPLITS (Playbook API)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import requests
import os

# Import ML system
try:
    from advanced_ml_backend import MasterPredictionSystem
    predictor = MasterPredictionSystem()
except Exception as e:
    print(f"Warning: Could not load ML system: {e}")
    predictor = None

import uvicorn

# ============================================
# API KEYS
# ============================================
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "6e6da61eec951acb5fa9010293b89279")
PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "pbk_095c2ac98199f43d0b409f90031908bb05b8")

# ============================================
# LIVE ODDS SERVICE (THE ODDS API)
# ============================================

class LiveOddsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        
    def get_sports(self) -> List[Dict]:
        url = f"{self.base_url}/sports"
        params = {"apiKey": self.api_key}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return []
    
    def get_live_odds(
        self, 
        sport: str = "basketball_nba",
        regions: str = "us",
        markets: str = "h2h,spreads,totals",
        bookmakers: str = "fanduel,draftkings"
    ) -> Dict:
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
            requests_remaining = response.headers.get('x-requests-remaining', 'unknown')
            requests_used = response.headers.get('x-requests-used', 'unknown')
            
            return {
                "success": True,
                "sport": sport,
                "games_count": len(games),
                "games": self._format_games(games),
                "api_usage": {
                    "requests_remaining": requests_remaining,
                    "requests_used": requests_used
                },
                "fetched_at": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code}",
                "message": response.text
            }
    
    def _format_games(self, games: List[Dict]) -> List[Dict]:
        formatted = []
        for game in games:
            formatted_game = {
                "id": game.get("id"),
                "sport": game.get("sport_key"),
                "commence_time": game.get("commence_time"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "bookmakers": {}
            }
            
            for bookmaker in game.get("bookmakers", []):
                book_name = bookmaker.get("key")
                formatted_game["bookmakers"][book_name] = {
                    "last_update": bookmaker.get("last_update"),
                    "markets": {}
                }
                
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key")
                    outcomes = {}
                    for outcome in market.get("outcomes", []):
                        outcomes[outcome.get("name")] = {
                            "price": outcome.get("price"),
                            "point": outcome.get("point")
                        }
                    formatted_game["bookmakers"][book_name]["markets"][market_key] = outcomes
            
            formatted.append(formatted_game)
        return formatted


# ============================================
# BETTING SPLITS SERVICE (PLAYBOOK API)
# ============================================

class BettingSplitsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.playbook-api.com/v1"
    
    def get_splits(self, league: str = "NFL") -> Dict:
        url = f"{self.base_url}/splits"
        params = {
            "league": league.upper(),
            "api_key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "league": league.upper(),
                    "splits": data,
                    "fetched_at": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "message": response.text
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_injuries(self, league: str = "NFL") -> Dict:
        url = f"{self.base_url}/injuries"
        params = {
            "league": league.upper(),
            "api_key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return {
                    "success": True,
                    "league": league.upper(),
                    "injuries": response.json(),
                    "fetched_at": datetime.now().isoformat()
                }
            else:
                return {"success": False, "error": f"API Error: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Initialize services
odds_service = LiveOddsService(api_key=ODDS_API_KEY)
splits_service = BettingSplitsService(api_key=PLAYBOOK_API_KEY)

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="AI Sports Betting API",
    description="Advanced ML predictions + Live Odds + Betting Splits",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

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

# ============================================
# CORE API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "AI Sports Betting API with Live Odds & Betting Splits",
        "version": "3.0.0",
        "endpoints": {
            "predictions": ["/predict", "/calculate-edge"],
            "live_odds": ["/live-odds", "/live-games", "/live-odds/nba", "/live-odds/nfl"],
            "betting_splits": ["/splits", "/splits/nfl", "/splits/nba"],
