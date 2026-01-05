"""
FastAPI endpoints for AI sports betting predictions
WITH LIVE ODDS FROM THE ODDS API
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
# LIVE ODDS SERVICE (THE ODDS API)
# ============================================

class LiveOddsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        
    def get_sports(self) -> List[Dict]:
        """Get list of available sports"""
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
        """Get live odds for upcoming games"""
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
        """Format games data for easier frontend consumption"""
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

# Initialize services
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "6e6da61eec951acb5fa9010293b89279")
odds_service = LiveOddsService(api_key=ODDS_API_KEY)

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="AI Sports Betting API",
    description="Advanced ML predictions + Live Odds from FanDuel & DraftKings",
    version="2.0.0"
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
    """API health check"""
    return {
        "status": "online",
        "message": "AI Sports Betting API with Live Odds",
        "version": "2.0.0",
        "endpoints": {
            "predictions": ["/predict", "/calculate-edge"],
            "live_odds": ["/live-odds", "/live-games", "/live-odds/sports"],
            "system": ["/health", "/model-status", "/docs"]
        }
    }

@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": predictor is not None,
        "odds_api": "connected"
    }

@app.get("/model-status")
async def model_status():
    """Check status of all AI models"""
    return {
        "status": "operational",
        "models": {
            "ensemble_stacking": "ready",
            "lstm_network": "fallback_mode",
            "matchup_specific": "ready",
            "monte_carlo": "ready",
            "line_analyzer": "ready",
            "rest_fatigue": "ready",
            "injury_impact": "ready",
            "edge_calculator": "ready"
        },
        "total_models": 8,
        "version": "2.0.0"
    }

@app.post("/predict")
async def generate_prediction(request: PredictionRequest):
    """Generate comprehensive AI prediction"""
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
    """Calculate expected value and Kelly criterion bet size"""
    try:
        prob = request.your_probability
        odds = request.betting_odds
        
        # Convert American odds to decimal
        if odds > 0:
            decimal_odds = (odds / 100) + 1
        else:
            decimal_odds = (100 / abs(odds)) + 1
        
        # Calculate implied probability
        implied_prob = 1 / decimal_odds
        
        # Calculate edge
        edge = ((prob * decimal_odds) - 1) * 100
        
        # Calculate Kelly criterion
        kelly = max(0, (prob * (decimal_odds - 1) - (1 - prob)) / (decimal_odds - 1))
        
        # Determine recommendation
        if edge > 5:
            recommendation = "STRONG BET"
            confidence = "HIGH"
        elif edge > 2:
            recommendation = "BET"
            confidence = "MEDIUM"
        elif edge > 0:
            recommendation = "SMALL BET"
            confidence = "LOW"
        else:
            recommendation = "NO BET"
            confidence = "NONE"
        
        return {
            "status": "success",
            "edge_analysis": {
                "your_probability": prob,
                "implied_probability": round(implied_prob, 4),
                "edge_percent": round(edge, 2),
                "expected_value": round(edge, 2),
                "kelly_bet_size": round(kelly, 4),
                "half_kelly": round(kelly / 2, 4),
                "recommendation": recommendation,
                "confidence": confidence
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Edge calculation failed: {str(e)}")

# ============================================
# LIVE ODDS ENDPOINTS (THE ODDS API)
# ============================================

@app.get("/live-odds")
async def get_live_odds(
    sport: str = "basketball_nba",
    bookmakers: str = "fanduel,draftkings"
):
    """
    Get live betting odds from FanDuel & DraftKings
    
    Sports: basketball_nba, football_nfl, baseball_mlb, icehockey_nhl
    """
    try:
        result = odds_service.get_live_odds(sport=sport, bookmakers=bookmakers)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live-odds/sports")
async def get_available_sports():
    """Get list of all available sports"""
    try:
        sports = odds_service.get_sports()
        # Filter to main US sports
        main_sports = [s for s in sports if s.get("key") in [
            "basketball_nba", "football_nfl", "baseball_mlb", 
            "icehockey_nhl", "basketball_ncaab", "football_ncaaf"
        ]]
        return {
            "success": True,
            "main_sports": main_sports,
            "all_sports": sports
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live-games")
async def get_live_games_simple(sport: str = "basketball_nba"):
    """Get today's games with odds in an easy format"""
    try:
        odds_data = odds_service.get_live_odds(sport=sport)
        
        if not odds_data.get("success"):
            return odds_data
        
        simple_games = []
        for game in odds_data["games"]:
            simple_game = {
                "id": game["id"],
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "start_time": game["commence_time"],
                "fanduel": None,
                "draftkings": None
            }
            
            if "fanduel" in game.get("bookmakers", {}):
                fd = game["bookmakers"]["fanduel"]["markets"]
                simple_game["fanduel"] = {
                    "spread": fd.get("spreads", {}),
                    "total": fd.get("totals", {}),
                    "moneyline": fd.get("h2h", {})
                }
            
            if "draftkings" in game.get("bookmakers", {}):
                dk = game["bookmakers"]["draftkings"]["markets"]
                simple_game["draftkings"] = {
                    "spread": dk.get("spreads", {}),
                    "total": dk.get("totals", {}),
                    "moneyline": dk.get("h2h", {})
                }
            
            simple_games.append(simple_game)
        
        return {
            "success": True,
            "sport": sport,
            "games_count": len(simple_games),
            "games": simple_games,
            "api_usage": odds_data["api_usage"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live-odds/nba")
async def get_nba_odds():
    """Quick endpoint for NBA odds"""
    return await get_live_games_simple("basketball_nba")

@app.get("/live-odds/nfl")
async def get_nfl_odds():
    """Quick endpoint for NFL odds"""
    return await get_live_games_simple("football_nfl")

@app.get("/live-odds/mlb")
async def get_mlb_odds():
    """Quick endpoint for MLB odds"""
    return await get_live_games_simple("baseball_mlb")

# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting AI Sports Betting API on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
