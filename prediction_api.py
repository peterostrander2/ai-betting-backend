"""
FastAPI endpoints for AI sports betting predictions
v6.6.0 - Context Layer Integration
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
import sys
sys.path.append('..')
from models.advanced_ml_backend import MasterPredictionSystem
from context_layer import ContextGenerator, DefensiveRankService, PaceVectorService, UsageVacuumService
from loguru import logger
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="AI Sports Betting API",
    description="Advanced ML predictions for sports betting with Context Layer",
    version="6.6.0"
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
# 🔥 CONTEXT LAYER REQUEST MODELS (NEW)
# ============================================

class InjuryInput(BaseModel):
    """Injury data for vacuum calculation"""
    player_name: Optional[str] = Field(None, example="Tyrese Haliburton")
    status: str = Field(..., example="OUT")  # OUT, GTD, Questionable
    usage_pct: float = Field(..., example=26.0)
    minutes_per_game: float = Field(..., example=34.0)

class ContextRequest(BaseModel):
    """Request for context-aware prediction"""
    player_name: str = Field(..., example="Pascal Siakam")
    player_team: str = Field(..., example="Indiana Pacers")
    opponent_team: str = Field(..., example="Washington Wizards")
    position: str = Field(..., example="Wing")  # Guard, Wing, or Big
    player_avg: float = Field(..., example=21.5)
    stat_type: str = Field("points", example="points")
    injuries: List[InjuryInput] = Field(default_factory=list)
    game_total: float = Field(230.0, example=241.0)
    game_spread: float = Field(0.0, example=-5.5)
    line: Optional[float] = Field(None, example=21.5)
    odds: Optional[int] = Field(None, example=-110)

class BatchContextRequest(BaseModel):
    """Request for multiple context predictions"""
    predictions: List[ContextRequest]

class DefenseRankRequest(BaseModel):
    """Request for defense ranking lookup"""
    team: str = Field(..., example="Washington Wizards")
    position: str = Field(..., example="Wing")

class VacuumRequest(BaseModel):
    """Request for usage vacuum calculation"""
    injuries: List[InjuryInput]

class PaceRequest(BaseModel):
    """Request for game pace estimation"""
    team1: str = Field(..., example="Indiana Pacers")
    team2: str = Field(..., example="Oklahoma City Thunder")

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "online",
        "message": "AI Sports Betting API with Context Layer",
        "version": "6.6.0",
        "endpoints": [
            "/predict",
            "/predict-context",
            "/predict-batch",
            "/defense-rank",
            "/defense-rankings/{position}",
            "/usage-vacuum",
            "/game-pace",
            "/pace-rankings",
            "/simulate-game",
            "/analyze-line",
            "/calculate-edge",
            "/health",
            "/docs"
        ]
    }

# ============================================
# 🔥 CONTEXT LAYER ENDPOINTS (NEW)
# ============================================

@app.post("/predict-context")
async def predict_with_context(request: ContextRequest):
    """
    🔥 CONTEXT-AWARE PREDICTION
    
    Uses the 3 context features:
    - Usage Vacuum (injury impact)
    - Defensive Rank (position-specific)
    - Pace Vector (game speed)
    
    Returns prediction with waterfall breakdown and smash spot detection.
    """
    try:
        logger.info(f"Context prediction: {request.player_name} vs {request.opponent_team}")
        
        # Convert injuries to dict format
        injuries = [inj.dict() for inj in request.injuries]
        
        # Generate full context
        context = ContextGenerator.generate_context(
            player_name=request.player_name,
            player_team=request.player_team,
            opponent_team=request.opponent_team,
            position=request.position,
            player_avg=request.player_avg,
            stat_type=request.stat_type,
            injuries=injuries,
            game_total=request.game_total,
            game_spread=request.game_spread
        )
        
        # Extract prediction data
        waterfall = context["waterfall"]
        final_pred = waterfall["finalPrediction"]
        
        # Build response
        response = {
            "status": "success",
            "prediction": {
                "player": request.player_name,
                "team": request.player_team,
                "opponent": request.opponent_team,
                "position": request.position,
                "stat_type": request.stat_type,
                "base": request.player_avg,
                "final": final_pred,
                "line": request.line,
                "recommendation": None,
                "confidence": waterfall["confidence"],
                "is_smash_spot": waterfall["isSmashSpot"]
            },
            "lstm_features": context["lstm_features"],
            "waterfall": waterfall,
            "badges": context["badges"],
            "raw_context": context["raw_context"]
        }
        
        # Add recommendation if line provided
        if request.line:
            edge = final_pred - request.line
            response["prediction"]["recommendation"] = "OVER" if edge > 0 else "UNDER"
            response["edge"] = {
                "raw": round(edge, 1),
                "percent": round((edge / request.line) * 100, 1),
                "direction": "OVER" if edge > 0 else "UNDER"
            }
        
        # Add EV calculation if odds provided
        if request.odds and request.line:
            edge_pct = (final_pred - request.line) / request.line
            # Convert American odds to implied probability
            if request.odds < 0:
                implied_prob = abs(request.odds) / (abs(request.odds) + 100)
            else:
                implied_prob = 100 / (request.odds + 100)
            
            # Our probability based on edge
            our_prob = 0.5 + (edge_pct * 2)  # Simple conversion
            our_prob = max(0.1, min(0.9, our_prob))  # Cap between 10-90%
            
            # EV calculation
            ev = (our_prob * 100) - ((1 - our_prob) * 100)
            
            response["ev"] = {
                "percent": round(ev, 1),
                "per_100": round(ev, 2),
                "implied_prob": round(implied_prob * 100, 1),
                "our_prob": round(our_prob * 100, 1)
            }
        
        logger.success(f"Prediction: {final_pred} | Smash: {waterfall['isSmashSpot']} | Confidence: {waterfall['confidence']}%")
        return response
        
    except Exception as e:
        logger.error(f"Context prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-batch")
async def predict_batch(request: BatchContextRequest):
    """
    Batch context predictions for multiple players
    
    Perfect for analyzing an entire slate at once.
    """
    try:
        logger.info(f"Batch prediction: {len(request.predictions)} players")
        
        results = []
        smash_spots = []
        
        for pred_request in request.predictions:
            # Convert injuries to dict format
            injuries = [inj.dict() for inj in pred_request.injuries]
            
            # Generate context
            context = ContextGenerator.generate_context(
                player_name=pred_request.player_name,
                player_team=pred_request.player_team,
                opponent_team=pred_request.opponent_team,
                position=pred_request.position,
                player_avg=pred_request.player_avg,
                stat_type=pred_request.stat_type,
                injuries=injuries,
                game_total=pred_request.game_total,
                game_spread=pred_request.game_spread
            )
            
            waterfall = context["waterfall"]
            final_pred = waterfall["finalPrediction"]
            
            result = {
                "player": pred_request.player_name,
                "team": pred_request.player_team,
                "opponent": pred_request.opponent_team,
                "position": pred_request.position,
                "base": pred_request.player_avg,
                "final": final_pred,
                "line": pred_request.line,
                "confidence": waterfall["confidence"],
                "is_smash_spot": waterfall["isSmashSpot"],
                "badges": [b["icon"] for b in context["badges"]]
            }
            
            if pred_request.line:
                edge = final_pred - pred_request.line
                result["recommendation"] = "OVER" if edge > 0 else "UNDER"
                result["edge"] = round(edge, 1)
            
            results.append(result)
            
            if waterfall["isSmashSpot"]:
                smash_spots.append(result)
        
        logger.success(f"Batch complete: {len(results)} predictions, {len(smash_spots)} smash spots")
        
        return {
            "status": "success",
            "count": len(results),
            "smash_spot_count": len(smash_spots),
            "predictions": results,
            "smash_spots": smash_spots
        }
        
    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/defense-rank")
async def get_defense_rank(request: DefenseRankRequest):
    """
    Get defensive rank for a team vs position
    
    Returns rank 1-30 (1=best defense, 30=worst/smash spot)
    """
    try:
        rank = DefensiveRankService.get_rank(request.team, request.position)
        context = DefensiveRankService.rank_to_context(request.team, request.position)
        
        # Determine matchup quality
        if rank >= 22:
            quality = "SOFT 🎯"
        elif rank <= 8:
            quality = "TOUGH 🔒"
        else:
            quality = "NEUTRAL"
        
        return {
            "status": "success",
            "team": request.team,
            "position": request.position,
            "rank": rank,
            "context": context,
            "quality": quality
        }
        
    except Exception as e:
        logger.error(f"Defense rank error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/defense-rankings/{position}")
async def get_defense_rankings(position: str):
    """
    Get all teams ranked by defense vs position
    
    Position options: Guard, Wing, Big
    """
    try:
        pos = position.lower()
        if pos in ["guard", "pg", "sg"]:
            rankings = DefensiveRankService.DEFENSE_VS_GUARDS
            pos_label = "Guards"
        elif pos in ["wing", "sf"]:
            rankings = DefensiveRankService.DEFENSE_VS_WINGS
            pos_label = "Wings"
        elif pos in ["big", "pf", "c"]:
            rankings = DefensiveRankService.DEFENSE_VS_BIGS
            pos_label = "Bigs"
        else:
            raise HTTPException(status_code=400, detail="Position must be Guard, Wing, or Big")
        
        # Sort by rank
        sorted_rankings = dict(sorted(rankings.items(), key=lambda x: x[1]))
        
        # Identify smash spots (rank 25+)
        smash_teams = [team for team, rank in rankings.items() if rank >= 25]
        
        return {
            "status": "success",
            "position": pos_label,
            "rankings": sorted_rankings,
            "smash_spots": smash_teams,
            "best_defense": list(sorted_rankings.keys())[0],
            "worst_defense": list(sorted_rankings.keys())[-1]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Defense rankings error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/usage-vacuum")
async def calculate_usage_vacuum(request: VacuumRequest):
    """
    Calculate usage vacuum from injuries
    
    Formula: sum((USG% × MPG) / 48) for all OUT players
    
    Interpretation:
    - 0-10: Minimal impact
    - 10-20: Moderate opportunity
    - 20-35: Significant boost
    - 35+: SMASH SPOT
    """
    try:
        injuries = [inj.dict() for inj in request.injuries]
        vacuum = UsageVacuumService.calculate_vacuum(injuries)
        context = UsageVacuumService.vacuum_to_context(vacuum)
        
        # Determine impact level
        if vacuum >= 35:
            impact = "SMASH SPOT 💎"
        elif vacuum >= 20:
            impact = "SIGNIFICANT 🔥"
        elif vacuum >= 10:
            impact = "MODERATE ⚡"
        else:
            impact = "MINIMAL"
        
        return {
            "status": "success",
            "vacuum": vacuum,
            "context": context,
            "impact": impact,
            "injuries_counted": len([i for i in injuries if i.get('status', '').upper() == 'OUT'])
        }
        
    except Exception as e:
        logger.error(f"Vacuum calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/game-pace")
async def get_game_pace(request: PaceRequest):
    """
    Estimate game pace between two teams
    
    Returns expected possessions per game.
    """
    try:
        pace = PaceVectorService.get_game_pace(request.team1, request.team2)
        context = PaceVectorService.pace_to_context(request.team1, request.team2)
        
        pace1 = PaceVectorService.get_team_pace(request.team1)
        pace2 = PaceVectorService.get_team_pace(request.team2)
        
        # Determine pace category
        if pace >= 101:
            category = "FAST ⚡"
        elif pace <= 96:
            category = "SLOW 🐢"
        else:
            category = "AVERAGE"
        
        return {
            "status": "success",
            "game_pace": pace,
            "context": context,
            "category": category,
            "team1_pace": pace1,
            "team2_pace": pace2,
            "league_avg": PaceVectorService.LEAGUE_AVG_PACE
        }
        
    except Exception as e:
        logger.error(f"Pace calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pace-rankings")
async def get_pace_rankings():
    """
    Get all teams ranked by pace
    
    Pace = possessions per game
    """
    try:
        # Sort by pace (fastest first)
        sorted_pace = dict(sorted(PaceVectorService.TEAM_PACE.items(), key=lambda x: x[1], reverse=True))
        
        # Identify fast teams (pace 100+)
        fast_teams = [team for team, pace in PaceVectorService.TEAM_PACE.items() if pace >= 100]
        
        return {
            "status": "success",
            "rankings": sorted_pace,
            "fast_teams": fast_teams,
            "fastest": list(sorted_pace.keys())[0],
            "slowest": list(sorted_pace.keys())[-1],
            "league_avg": PaceVectorService.LEAGUE_AVG_PACE
        }
        
    except Exception as e:
        logger.error(f"Pace rankings error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ORIGINAL ENDPOINTS
# ============================================

@app.post("/predict", response_model=PredictionResponse)
async def generate_prediction(request: PredictionRequest):
    """
    Generate comprehensive AI prediction for a player prop or game
    
    This endpoint combines all 8 AI models to produce:
    - Predicted value
    - Recommendation (OVER/UNDER)
    - AI confidence score (0-10)
    - Expected value (EV)
    - Probability
    - Kelly criterion bet sizing
    """
    try:
        logger.info(f"Generating prediction for {request.player_id} vs {request.opponent_id}")
        
        # Convert Pydantic models to dicts
        game_data = request.dict()
        
        # Generate prediction
        result = predictor.generate_comprehensive_prediction(game_data)
        
        logger.success(f"Prediction generated: {result['recommendation']} at {result['ai_score']}/10 confidence")
        
        return result
        
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/simulate-game")
async def simulate_game(request: GameSimulationRequest):
    """
    Run Monte Carlo game simulation
    
    Simulates the game thousands of times to get:
    - Win probabilities
    - Score distributions
    - Over/under probabilities
    - Spread cover probabilities
    """
    try:
        logger.info("Running game simulation...")
        
        results = predictor.monte_carlo.simulate_game(
            request.team_a_stats,
            request.team_b_stats,
            request.num_simulations
        )
        
        logger.success("Simulation complete")
        
        return {
            "status": "success",
            "simulations_run": request.num_simulations,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Simulation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

@app.post("/analyze-line")
async def analyze_line_movement(request: LineAnalysisRequest):
    """
    Analyze betting line movement to detect sharp money
    
    Returns:
    - Sharp money indicators
    - Reverse line movement detection
    - Steam move detection
    - Recommended side
    """
    try:
        logger.info(f"Analyzing line movement for {request.game_id}")
        
        analysis = predictor.line_analyzer.analyze_line_movement(
            request.game_id,
            request.current_line,
            request.opening_line,
            request.time_until_game,
            request.betting_percentages.dict()
        )
        
        logger.success("Line analysis complete")
        
        return {
            "status": "success",
            "game_id": request.game_id,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Line analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Line analysis failed: {str(e)}")

@app.post("/calculate-edge")
async def calculate_betting_edge(request: EdgeCalculationRequest):
    """
    Calculate expected value (EV) and optimal bet size
    
    Returns:
    - Expected value per $100 bet
    - Edge percentage
    - Kelly criterion bet size
    - Confidence level
    """
    try:
        logger.info("Calculating betting edge...")
        
        edge = predictor.edge_calculator.calculate_ev(
            request.your_probability,
            request.betting_odds
        )
        
        logger.success(f"Edge calculated: {edge['edge_percent']}%")
        
        return {
            "status": "success",
            "edge_analysis": edge
        }
        
    except Exception as e:
        logger.error(f"Edge calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Edge calculation failed: {str(e)}")

@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "6.6.0",
        "context_layer": "active",
        "models_loaded": True
    }

@app.get("/model-status")
async def model_status():
    """Check status of all AI models"""
    return {
        "version": "6.6.0",
        "context_layer": {
            "usage_vacuum": "ready",
            "defensive_rank": "ready",
            "pace_vector": "ready"
        },
        "ml_models": {
            "ensemble": predictor.ensemble.is_trained,
            "lstm_built": predictor.lstm.model is not None,
            "matchup_models": len(predictor.matchup.matchup_models),
            "monte_carlo": "ready",
            "line_analyzer": "ready",
            "rest_model": "ready",
            "injury_model": "ready",
            "edge_calculator": "ready"
        }
    }

# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    logger.info("Starting AI Sports Betting API v6.6.0 with Context Layer...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
