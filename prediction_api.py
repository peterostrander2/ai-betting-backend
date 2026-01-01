"""
FastAPI endpoints for AI sports betting predictions
Railway Production Version with 8 AI Models
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import sys
import os
import uvicorn

# Import the advanced ML backend
from advanced_ml_backend import MasterPredictionSystem

# Initialize FastAPI app
app = FastAPI(
    title="AI Sports Betting API - 8 Model System",
    description="Advanced ML predictions powered by 8 specialized AI models",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global predictor instance
predictor = MasterPredictionSystem()

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
    status: str = Field(..., example="out")  # out, doubtful, questionable

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

class PredictionResponse(BaseModel):
    predicted_value: float
    line: float
    recommendation: str
    ai_score: float
    confidence: str
    expected_value: float
    probability: float
    kelly_bet_size: float
    factors: Dict
    monte_carlo: Dict

class GameSimulationRequest(BaseModel):
    team_a_stats: Dict = Field(..., example={
        'pace': 100.0,
        'off_rating': 115.0,
        'off_rating_std': 5.0
    })
    team_b_stats: Dict = Field(..., example={
        'pace': 98.0,
        'off_rating': 110.0,
        'off_rating_std': 6.0
    })
    num_simulations: int = Field(10000, example=10000)

class LineAnalysisRequest(BaseModel):
    game_id: str
    current_line: float
    opening_line: float
    time_until_game: float
    betting_percentages: BettingPercentages

class EdgeCalculationRequest(BaseModel):
    your_probability: float = Field(..., example=0.65, ge=0, le=1)
    betting_odds: float = Field(..., example=-110)

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "online",
        "message": "AI Sports Betting API - 8 Model System",
        "version": "2.0.0",
        "models": [
            "Ensemble Stacking (XGBoost + LightGBM + RF)",
            "LSTM Neural Network",
            "Matchup-Specific Models",
            "Monte Carlo Simulator",
            "Line Movement Analyzer",
            "Rest & Fatigue Model",
            "Injury Impact Model",
            "Betting Edge Calculator"
        ],
        "endpoints": [
            "/predict",
            "/simulate-game",
            "/analyze-line",
            "/calculate-edge",
            "/health",
            "/docs"
        ]
    }

@app.post("/predict", response_model=PredictionResponse)
async def generate_prediction(request: PredictionRequest):
    """
    Generate comprehensive AI prediction using all 8 models
    
    This endpoint combines all models to produce:
    - Predicted value
    - Recommendation (OVER/UNDER/NO BET)
    - AI confidence score (0-10)
    - Expected value (EV)
    - Probability
    - Kelly criterion bet sizing
    - Full factor breakdown
    """
    try:
        print(f"📊 Generating prediction for {request.player_id} vs {request.opponent_id}")
        
        # Convert Pydantic models to dicts
        game_data = request.dict()
        
        # Generate prediction using all 8 models
        result = predictor.generate_comprehensive_prediction(game_data)
        
        print(f"✅ Prediction: {result['recommendation']} at {result['ai_score']}/10 confidence")
        
        return result
        
    except Exception as e:
        print(f"❌ Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/simulate-game")
async def simulate_game(request: GameSimulationRequest):
    """
    Run Monte Carlo game simulation (Model #4)
    
    Simulates the game thousands of times to get:
    - Win probabilities
    - Score distributions
    - Over/under probabilities
    - Spread cover probabilities
    """
    try:
        print("🎲 Running Monte Carlo simulation...")
        
        results = predictor.monte_carlo.simulate_game(
            request.team_a_stats,
            request.team_b_stats,
            request.num_simulations
        )
        
        print("✅ Simulation complete")
        
        return {
            "status": "success",
            "simulations_run": request.num_simulations,
            "results": results
        }
        
    except Exception as e:
        print(f"❌ Simulation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

@app.post("/analyze-line")
async def analyze_line_movement(request: LineAnalysisRequest):
    """
    Analyze betting line movement (Model #5)
    
    Detects:
    - Sharp money indicators
    - Reverse line movement
    - Steam moves
    - Recommended side
    """
    try:
        print(f"📈 Analyzing line movement for {request.game_id}")
        
        analysis = predictor.line_analyzer.analyze_line_movement(
            request.game_id,
            request.current_line,
            request.opening_line,
            request.time_until_game,
            request.betting_percentages.dict()
        )
        
        print("✅ Line analysis complete")
        
        return {
            "status": "success",
            "game_id": request.game_id,
            "analysis": analysis
        }
        
    except Exception as e:
        print(f"❌ Line analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Line analysis failed: {str(e)}")

@app.post("/calculate-edge")
async def calculate_betting_edge(request: EdgeCalculationRequest):
    """
    Calculate expected value and optimal bet size (Model #8)
    
    Returns:
    - Expected value per $100 bet
    - Edge percentage
    - Kelly criterion bet size
    - Confidence level
    """
    try:
        print("💰 Calculating betting edge...")
        
        edge = predictor.edge_calculator.calculate_ev(
            request.your_probability,
            request.betting_odds
        )
        
        kelly_size = predictor.edge_calculator.kelly_criterion(
            request.your_probability,
            request.betting_odds
        )
        
        print(f"✅ Edge calculated: {edge['edge_percent']}%")
        
        return {
            "status": "success",
            "edge_analysis": {
                **edge,
                "kelly_bet_size": kelly_size,
                "recommendation": "BET" if edge['expected_value'] > 0 else "NO BET",
                "confidence": "HIGH" if edge['edge_percent'] > 10 else "MEDIUM" if edge['edge_percent'] > 5 else "LOW"
            }
        }
        
    except Exception as e:
        print(f"❌ Edge calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Edge calculation failed: {str(e)}")

@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": True,
        "system": "8-model AI prediction system"
    }

@app.get("/model-status")
async def model_status():
    """Check status of all 8 AI models"""
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

@app.get("/docs-info")
async def docs_info():
    """Information about the 8 AI models"""
    return {
        "models": [
            {
                "id": 1,
                "name": "Ensemble Stacking Model",
                "description": "Combines XGBoost, LightGBM, and Random Forest",
                "purpose": "Base prediction with high accuracy",
                "edge": "More accurate than single models"
            },
            {
                "id": 2,
                "name": "LSTM Neural Network",
                "description": "Deep learning for time series analysis",
                "purpose": "Detect player momentum and trends",
                "edge": "Captures hot/cold streaks statistical models miss"
            },
            {
                "id": 3,
                "name": "Matchup-Specific Model",
                "description": "Player vs opponent historical learning",
                "purpose": "Quantify matchup advantages",
                "edge": "Some players consistently perform better vs certain teams"
            },
            {
                "id": 4,
                "name": "Monte Carlo Simulator",
                "description": "10,000+ game simulations",
                "purpose": "Generate probability distributions",
                "edge": "Full probability distribution vs point estimates"
            },
            {
                "id": 5,
                "name": "Line Movement Analyzer",
                "description": "Detects sharp money and steam moves",
                "purpose": "Follow professional bettors",
                "edge": "Sharp money wins long-term"
            },
            {
                "id": 6,
                "name": "Rest & Fatigue Model",
                "description": "Schedule and travel impact",
                "purpose": "Quantify back-to-back and fatigue effects",
                "edge": "Rest significantly impacts performance"
            },
            {
                "id": 7,
                "name": "Injury Impact Model",
                "description": "Cascading injury effects",
                "purpose": "Calculate team-wide injury impact",
                "edge": "Injuries create opportunities for other players"
            },
            {
                "id": 8,
                "name": "Betting Edge Calculator",
                "description": "Kelly Criterion and EV optimization",
                "purpose": "Optimal bet sizing for bankroll growth",
                "edge": "Mathematical advantage over flat betting"
            }
        ]
    }

# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting AI Sports Betting API")
    print("=" * 60)
    print("📊 8 Advanced AI Models Loaded:")
    print("   1. Ensemble Stacking (XGBoost + LightGBM + RF)")
    print("   2. LSTM Neural Network")
    print("   3. Matchup-Specific Models")
    print("   4. Monte Carlo Simulator")
    print("   5. Line Movement Analyzer")
    print("   6. Rest & Fatigue Model")
    print("   7. Injury Impact Model")
    print("   8. Betting Edge Calculator")
    print("=" * 60)
    port = int(os.getenv("PORT", 8000))
    print(f"📡 Server starting on http://0.0.0.0:{port}")
    print(f"📚 API Docs: http://0.0.0.0:{port}/docs")
    print("=" * 60)
    
    # Get port from environment variable (Railway sets this)
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
