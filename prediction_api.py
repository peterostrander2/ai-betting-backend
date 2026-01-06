"""
FastAPI endpoints for AI sports betting predictions
v7.0.0 - Multi-Sport Context Layer + Officials + LSTM Brain + Auto-Grader (NBA, NFL, MLB, NHL, NCAAB)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from context_layer import (
    ContextGenerator, 
    DefensiveRankService, 
    PaceVectorService, 
    UsageVacuumService,
    ParkFactorService,
    OfficialsService,
    SUPPORTED_SPORTS,
    SPORT_POSITIONS,
    SPORT_STAT_TYPES,
    LEAGUE_AVERAGES
)
from lstm_brain import LSTMBrain, MultiSportLSTMBrain, integrate_lstm_prediction
from auto_grader import AutoGrader, ContextFeatureCalculator, get_grader
from loguru import logger
import uvicorn

# Initialize LSTM Brain (sport-specific models)
lstm_brain_manager = MultiSportLSTMBrain()

# Initialize Auto-Grader (feedback loop)
auto_grader = get_grader()

app = FastAPI(
    title="AI Sports Betting API",
    description="Multi-Sport AI Predictions with Context Layer + Officials + LSTM Brain + Auto-Grader (NBA, NFL, MLB, NHL, NCAAB)",
    version="7.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# REQUEST MODELS
# ============================================

class InjuryInput(BaseModel):
    player_name: Optional[str] = None
    status: str = "OUT"
    usage_pct: Optional[float] = None
    minutes_per_game: Optional[float] = None
    target_share: Optional[float] = None
    snaps_per_game: Optional[float] = None
    time_on_ice: Optional[float] = None
    plate_appearances: Optional[float] = None

class LSTMHistoryInput(BaseModel):
    """Historical game features for LSTM sequence (single game)."""
    defense_rank: float = Field(16, description="Opponent defense rank (1-32)")
    defense_context: float = Field(0.0, description="Defense context adjustment (-1 to 1)")
    pace: float = Field(100.0, description="Game pace factor")
    pace_context: float = Field(0.0, description="Pace context adjustment (-1 to 1)")
    vacuum: float = Field(0.0, description="Usage vacuum factor (0 to 1)")
    vacuum_context: float = Field(0.0, description="Vacuum context adjustment (-1 to 1)")

class ContextRequest(BaseModel):
    sport: str
    player_name: str
    player_team: str
    opponent_team: str
    position: str
    player_avg: float
    stat_type: Optional[str] = "points"
    injuries: List[InjuryInput] = Field(default_factory=list)
    game_total: Optional[float] = 0.0
    game_spread: Optional[float] = 0.0
    home_team: Optional[str] = None
    line: Optional[float] = None
    odds: Optional[int] = None
    # Officials
    lead_official: Optional[str] = None
    official_2: Optional[str] = None
    official_3: Optional[str] = None
    # LSTM Brain historical context (up to 14 past games)
    historical_features: Optional[List[LSTMHistoryInput]] = Field(
        default=None,
        description="Historical game features for LSTM sequence (max 14 games)"
    )
    use_lstm_brain: Optional[bool] = Field(
        default=True,
        description="Enable LSTM neural prediction adjustment"
    )

class BatchContextRequest(BaseModel):
    predictions: List[ContextRequest]

class DefenseRankRequest(BaseModel):
    sport: str
    team: str
    position: str

class VacuumRequest(BaseModel):
    sport: str
    injuries: List[InjuryInput]

class PaceRequest(BaseModel):
    sport: str
    team1: str
    team2: str

class ParkFactorRequest(BaseModel):
    team: str

class EdgeCalculationRequest(BaseModel):
    your_probability: float = Field(..., ge=0, le=1)
    betting_odds: int

class OfficialsRequest(BaseModel):
    sport: str
    lead_official: str
    official_2: Optional[str] = ""
    official_3: Optional[str] = ""
    bet_type: Optional[str] = "total"  # total, spread, props
    is_home: Optional[bool] = False
    is_star: Optional[bool] = False

# ============================================
# ROOT
# ============================================

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Multi-Sport AI Betting API with Context Layer + Officials + LSTM Brain + Auto-Grader",
        "version": "7.0.0",
        "supported_sports": SUPPORTED_SPORTS,
        "endpoints": {
            "predictions": ["/predict-context", "/predict-batch"],
            "brain": ["/brain/predict", "/brain/status"],
            "grader": ["/grader/weights", "/grader/grade", "/grader/audit", "/grader/bias"],
            "sports_info": ["/sports", "/sports/{sport}/positions", "/sports/{sport}/stat-types"],
            "defense": ["/defense-rank", "/defense-rankings/{sport}/{position}"],
            "pace": ["/game-pace", "/pace-rankings/{sport}"],
            "vacuum": ["/usage-vacuum"],
            "officials": ["/officials-analysis", "/officials/{sport}", "/official/{sport}/{name}"],
            "mlb": ["/park-factor", "/park-factors"],
            "edge": ["/calculate-edge"],
            "system": ["/health", "/model-status", "/docs"]
        }
    }

@app.get("/sports")
async def get_supported_sports():
    return {
        "status": "success",
        "sports": SUPPORTED_SPORTS,
        "details": {sport: {"positions": SPORT_POSITIONS.get(sport, []), "stat_types": SPORT_STAT_TYPES.get(sport, [])} for sport in SUPPORTED_SPORTS}
    }

@app.get("/sports/{sport}/positions")
async def get_sport_positions(sport: str):
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    return {"status": "success", "sport": sport, "positions": SPORT_POSITIONS.get(sport, [])}

@app.get("/sports/{sport}/stat-types")
async def get_sport_stat_types(sport: str):
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    return {"status": "success", "sport": sport, "stat_types": SPORT_STAT_TYPES.get(sport, [])}

# ============================================
# CONTEXT PREDICTIONS
# ============================================

@app.post("/predict-context")
async def predict_with_context(request: ContextRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        logger.info(f"[{sport}] Context prediction: {request.player_name} vs {request.opponent_team}")
        injuries = [inj.dict() for inj in request.injuries]
        
        context = ContextGenerator.generate_context(
            sport=sport, player_name=request.player_name, player_team=request.player_team,
            opponent_team=request.opponent_team, position=request.position, player_avg=request.player_avg,
            stat_type=request.stat_type or "points", injuries=injuries, game_total=request.game_total or 0.0,
            game_spread=request.game_spread or 0.0, home_team=request.home_team
        )
        
        waterfall = context["waterfall"]
        final_pred = waterfall["finalPrediction"]
        
        # =====================
        # LSTM BRAIN PREDICTION
        # =====================
        lstm_prediction = None
        if request.use_lstm_brain:
            try:
                # Convert historical features if provided
                historical_features = None
                if request.historical_features:
                    historical_features = [h.dict() for h in request.historical_features]
                
                # Get LSTM prediction from sport-specific brain
                lstm_prediction = lstm_brain_manager.predict(
                    sport=sport,
                    current_features=context["lstm_features"],
                    historical_features=historical_features,
                    scale_factor=5.0  # Adjust prediction by up to ±5 points
                )
                
                # Apply LSTM adjustment to waterfall
                lstm_adjustment = lstm_prediction.get("adjustment", 0)
                if abs(lstm_adjustment) > 0.1:  # Only apply significant adjustments
                    waterfall["adjustments"].append({
                        "factor": "lstm_brain",
                        "value": round(lstm_adjustment, 2),
                        "reason": f"Neural pattern analysis ({lstm_prediction.get('method', 'unknown')})"
                    })
                    final_pred += lstm_adjustment
                    waterfall["finalPrediction"] = round(final_pred, 1)
                    
                    # Add brain badge if high confidence
                    if lstm_prediction.get("confidence", 0) >= 50:
                        context["badges"].append({
                            "icon": "🧠", 
                            "label": "brain", 
                            "active": True,
                            "confidence": lstm_prediction.get("confidence")
                        })
                
                logger.info(f"[{sport}] LSTM Brain: adjustment={lstm_adjustment:.2f}, confidence={lstm_prediction.get('confidence', 0):.1f}%")
                
            except Exception as lstm_error:
                logger.warning(f"LSTM Brain error (non-critical): {str(lstm_error)}")
                lstm_prediction = {"error": str(lstm_error), "method": "skipped"}
        
        # Add officials adjustment if provided
        officials_analysis = None
        if request.lead_official:
            officials_analysis = OfficialsService.analyze_crew(
                sport, request.lead_official, 
                request.official_2 or "", 
                request.official_3 or ""
            )
            
            if officials_analysis.get("has_data"):
                # Get props adjustment for star players
                is_star = request.player_avg > 20 if sport in ["NBA", "NCAAB"] else request.player_avg > 80
                officials_adj = OfficialsService.get_adjustment(
                    sport, request.lead_official,
                    request.official_2 or "", request.official_3 or "",
                    bet_type="props", is_star=is_star
                )
                
                if officials_adj:
                    waterfall["adjustments"].append(officials_adj)
                    final_pred += officials_adj["value"]
                    waterfall["finalPrediction"] = round(final_pred, 1)
                    context["badges"].append({"icon": "🦓", "label": "officials", "active": True})
        
        response = {
            "status": "success", "sport": sport,
            "prediction": {
                "player": request.player_name, "team": request.player_team, "opponent": request.opponent_team,
                "position": request.position, "stat_type": request.stat_type, "base": request.player_avg,
                "final": waterfall["finalPrediction"], "line": request.line, "recommendation": None,
                "confidence": waterfall["confidence"], "is_smash_spot": waterfall["isSmashSpot"]
            },
            "lstm_features": context["lstm_features"], 
            "lstm_brain": lstm_prediction,  # NEW: Include LSTM brain output
            "waterfall": waterfall,
            "badges": context["badges"], "raw_context": context["raw_context"],
            "dynamic_weights": auto_grader.get_weights(sport, request.stat_type or "points")  # Dynamic weights from grader
        }
        
        # Log prediction for grading (feedback loop)
        adjustments_for_log = {}
        for adj in waterfall.get("adjustments", []):
            factor = adj.get("factor", "unknown")
            adjustments_for_log[factor] = adj.get("value", 0)
        
        prediction_id = auto_grader.log_prediction(
            sport=sport,
            player_name=request.player_name,
            stat_type=request.stat_type or "points",
            predicted_value=waterfall["finalPrediction"],
            line=request.line,
            adjustments=adjustments_for_log
        )
        response["prediction_id"] = prediction_id  # Return for grading later
        
        # Add officials analysis if available
        if officials_analysis and officials_analysis.get("has_data"):
            response["officials"] = {
                "crew": officials_analysis.get("officials_found", []),
                "total_recommendation": officials_analysis.get("total_recommendation"),
                "props_lean": officials_analysis.get("props_lean"),
                "over_pct": officials_analysis.get("over_pct"),
                "confidence": officials_analysis.get("confidence")
            }
        
        if request.line:
            edge = waterfall["finalPrediction"] - request.line
            response["prediction"]["recommendation"] = "OVER" if edge > 0 else "UNDER"
            response["edge"] = {"raw": round(edge, 1), "percent": round((edge / request.line) * 100, 1) if request.line != 0 else 0, "direction": "OVER" if edge > 0 else "UNDER"}
        
        if request.odds and request.line:
            edge_pct = (waterfall["finalPrediction"] - request.line) / request.line if request.line != 0 else 0
            implied_prob = abs(request.odds) / (abs(request.odds) + 100) if request.odds < 0 else 100 / (request.odds + 100)
            our_prob = max(0.1, min(0.9, 0.5 + (edge_pct * 2)))
            ev = (our_prob * 100) - ((1 - our_prob) * 100)
            response["ev"] = {"percent": round(ev, 1), "per_100": round(ev, 2), "implied_prob": round(implied_prob * 100, 1), "our_prob": round(our_prob * 100, 1)}
        
        logger.success(f"[{sport}] Prediction: {waterfall['finalPrediction']} | Smash: {waterfall['isSmashSpot']}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Context prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict-batch")
async def predict_batch(request: BatchContextRequest):
    try:
        results, smash_spots, by_sport = [], [], {}
        for pred_request in request.predictions:
            sport = pred_request.sport.upper()
            injuries = [inj.dict() for inj in pred_request.injuries]
            context = ContextGenerator.generate_context(
                sport=sport, player_name=pred_request.player_name, player_team=pred_request.player_team,
                opponent_team=pred_request.opponent_team, position=pred_request.position, player_avg=pred_request.player_avg,
                stat_type=pred_request.stat_type or "points", injuries=injuries, game_total=pred_request.game_total or 0.0,
                game_spread=pred_request.game_spread or 0.0, home_team=pred_request.home_team
            )
            waterfall = context["waterfall"]
            final_pred = waterfall["finalPrediction"]
            result = {"sport": sport, "player": pred_request.player_name, "team": pred_request.player_team,
                      "opponent": pred_request.opponent_team, "position": pred_request.position, "stat_type": pred_request.stat_type,
                      "base": pred_request.player_avg, "final": final_pred, "line": pred_request.line,
                      "confidence": waterfall["confidence"], "is_smash_spot": waterfall["isSmashSpot"],
                      "badges": [b["icon"] for b in context["badges"]]}
            if pred_request.line:
                edge = final_pred - pred_request.line
                result["recommendation"] = "OVER" if edge > 0 else "UNDER"
                result["edge"] = round(edge, 1)
            results.append(result)
            if sport not in by_sport:
                by_sport[sport] = []
            by_sport[sport].append(result)
            if waterfall["isSmashSpot"]:
                smash_spots.append(result)
        return {"status": "success", "count": len(results), "smash_spot_count": len(smash_spots), "predictions": results, "smash_spots": smash_spots, "by_sport": by_sport}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# OFFICIALS ENDPOINTS (ALL SPORTS)
# ============================================

@app.post("/officials-analysis")
async def analyze_officials(request: OfficialsRequest):
    """
    Analyze officiating crew for ANY sport
    
    Supports: NBA, NFL, MLB, NHL, NCAAB
    
    Returns tendencies for:
    - Totals (over/under)
    - Spreads (home advantage)
    - Props (foul/penalty rates)
    """
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        analysis = OfficialsService.analyze_crew(
            sport, request.lead_official,
            request.official_2 or "",
            request.official_3 or ""
        )
        
        if not analysis.get("has_data"):
            return {"status": "no_data", "message": "Official(s) not found in database", "sport": sport}
        
        adjustment = None
        if request.bet_type:
            adjustment = OfficialsService.get_adjustment(
                sport, request.lead_official,
                request.official_2 or "", request.official_3 or "",
                bet_type=request.bet_type,
                is_home=request.is_home or False,
                is_star=request.is_star or False
            )
        
        return {
            "status": "success",
            "sport": sport,
            "analysis": analysis,
            "adjustment": adjustment,
            "league_avg": LEAGUE_AVERAGES.get(sport, {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Officials analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/officials/{sport}")
async def get_all_officials(sport: str):
    """Get all officials for a sport grouped by tendency"""
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        grouped = OfficialsService.get_all_officials_by_tendency(sport)
        
        # Count by tendency
        summary = {tendency: len(officials) for tendency, officials in grouped.items()}
        
        return {
            "status": "success",
            "sport": sport,
            "officials": grouped,
            "summary": summary,
            "league_avg": LEAGUE_AVERAGES.get(sport, {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Officials fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/official/{sport}/{name}")
async def get_official_profile(sport: str, name: str):
    """Get profile for a single official in any sport"""
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        profile = OfficialsService.get_official_profile(sport, name)
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"Official '{name}' not found in {sport}")
        
        league_avg = LEAGUE_AVERAGES.get(sport, {})
        
        # Calculate edges vs league average
        edges = {}
        for key, value in profile.items():
            if key != "tendency" and isinstance(value, (int, float)) and key in league_avg:
                edges[key] = round(value - league_avg[key], 1)
        
        return {
            "status": "success",
            "sport": sport,
            "name": name.title(),
            "profile": profile,
            "edges_vs_avg": edges,
            "league_avg": league_avg
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Official profile error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# DEFENSE RANKINGS
# ============================================

@app.post("/defense-rank")
async def get_defense_rank(request: DefenseRankRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        rank = DefensiveRankService.get_rank(sport, request.team, request.position)
        context = DefensiveRankService.rank_to_context(sport, request.team, request.position)
        total = DefensiveRankService.get_total_teams(sport)
        soft_threshold, tough_threshold = int(total * 0.75), int(total * 0.25)
        quality = "SOFT 🎯" if rank >= soft_threshold else "TOUGH 🔒" if rank <= tough_threshold else "NEUTRAL"
        return {"status": "success", "sport": sport, "team": request.team, "position": request.position, "rank": rank, "total_teams": total, "context": context, "quality": quality}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/defense-rankings/{sport}/{position}")
async def get_defense_rankings(sport: str, position: str):
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        rankings = DefensiveRankService.get_rankings_for_position(sport, position)
        if not rankings:
            raise HTTPException(status_code=400, detail=f"Invalid position for {sport}. Valid: {SPORT_POSITIONS.get(sport, [])}")
        sorted_rankings = dict(sorted(rankings.items(), key=lambda x: x[1]))
        total = len(rankings)
        smash_teams = [team for team, rank in rankings.items() if rank >= int(total * 0.8)]
        return {"status": "success", "sport": sport, "position": position, "total_teams": total, "rankings": sorted_rankings, "smash_spots": smash_teams, "best_defense": list(sorted_rankings.keys())[0], "worst_defense": list(sorted_rankings.keys())[-1]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# VACUUM & PACE
# ============================================

@app.post("/usage-vacuum")
async def calculate_usage_vacuum(request: VacuumRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        injuries = [inj.dict() for inj in request.injuries]
        vacuum = UsageVacuumService.calculate_vacuum(sport, injuries)
        context = UsageVacuumService.vacuum_to_context(vacuum)
        impact = "SMASH SPOT 💎" if vacuum >= 35 else "SIGNIFICANT 🔥" if vacuum >= 20 else "MODERATE ⚡" if vacuum >= 10 else "MINIMAL"
        return {"status": "success", "sport": sport, "vacuum": vacuum, "context": context, "impact": impact, "injuries_counted": len([i for i in injuries if i.get('status', '').upper() == 'OUT'])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/game-pace")
async def get_game_pace(request: PaceRequest):
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        pace = PaceVectorService.get_game_pace(sport, request.team1, request.team2)
        context = PaceVectorService.pace_to_context(sport, request.team1, request.team2)
        pace1, pace2 = PaceVectorService.get_team_pace(sport, request.team1), PaceVectorService.get_team_pace(sport, request.team2)
        league_avg = PaceVectorService.LEAGUE_AVG.get(sport, 0)
        category = "FAST ⚡" if context >= 0.7 else "SLOW 🐢" if context <= 0.3 else "AVERAGE"
        return {"status": "success", "sport": sport, "game_pace": pace, "context": context, "category": category, "team1_pace": pace1, "team2_pace": pace2, "league_avg": league_avg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pace-rankings/{sport}")
async def get_pace_rankings(sport: str):
    try:
        sport = sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        rankings = PaceVectorService.get_all_rankings(sport)
        sorted_pace = dict(sorted(rankings.items(), key=lambda x: x[1], reverse=True))
        league_avg = PaceVectorService.LEAGUE_AVG.get(sport, 0)
        fast_teams = [team for team, pace in rankings.items() if pace > league_avg * 1.03]
        return {"status": "success", "sport": sport, "rankings": sorted_pace, "fast_teams": fast_teams, "fastest": list(sorted_pace.keys())[0] if sorted_pace else None, "slowest": list(sorted_pace.keys())[-1] if sorted_pace else None, "league_avg": league_avg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# MLB PARK FACTORS
# ============================================

@app.post("/park-factor")
async def get_park_factor(request: ParkFactorRequest):
    try:
        factor = ParkFactorService.get_park_factor(request.team)
        env = ParkFactorService.get_game_environment(request.team, "")
        return {"status": "success", "team": request.team, "park_factor": factor, "environment": env["environment"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/park-factors")
async def get_all_park_factors():
    try:
        from context_layer import MLB_PARK_FACTORS, MLB_TEAM_TO_PARK
        sorted_parks = dict(sorted(MLB_PARK_FACTORS.items(), key=lambda x: x[1], reverse=True))
        hitter_parks = [park for park, factor in MLB_PARK_FACTORS.items() if factor >= 1.05]
        pitcher_parks = [park for park, factor in MLB_PARK_FACTORS.items() if factor <= 0.92]
        return {"status": "success", "park_factors": sorted_parks, "team_to_park": MLB_TEAM_TO_PARK, "hitter_friendly": hitter_parks, "pitcher_friendly": pitcher_parks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# EDGE & HEALTH
# ============================================

@app.post("/calculate-edge")
async def calculate_betting_edge(request: EdgeCalculationRequest):
    try:
        if request.betting_odds < 0:
            decimal_odds = 1 + (100 / abs(request.betting_odds))
            implied_prob = abs(request.betting_odds) / (abs(request.betting_odds) + 100)
        else:
            decimal_odds = 1 + (request.betting_odds / 100)
            implied_prob = 100 / (request.betting_odds + 100)
        edge = request.your_probability - implied_prob
        edge_percent = edge * 100
        ev = (request.your_probability * (decimal_odds - 1) * 100) - ((1 - request.your_probability) * 100)
        kelly = max(0, edge / (decimal_odds - 1)) if decimal_odds > 1 else 0
        confidence = "HIGH" if edge_percent >= 10 else "MEDIUM" if edge_percent >= 5 else "LOW" if edge_percent > 0 else "NO EDGE"
        return {"status": "success", "edge_analysis": {"your_probability": round(request.your_probability * 100, 1), "implied_probability": round(implied_prob * 100, 1), "edge_percent": round(edge_percent, 2), "ev_per_100": round(ev, 2), "kelly_bet_size": round(kelly * 100, 1), "decimal_odds": round(decimal_odds, 3), "confidence": confidence}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# LSTM BRAIN ENDPOINTS
# ============================================

class LSTMPredictRequest(BaseModel):
    """Direct LSTM Brain prediction request."""
    sport: str
    current_features: LSTMHistoryInput
    historical_features: Optional[List[LSTMHistoryInput]] = None
    scale_factor: Optional[float] = 5.0

@app.post("/brain/predict")
async def lstm_brain_predict(request: LSTMPredictRequest):
    """
    Direct LSTM Brain prediction.
    
    Runs the (15, 6) LSTM neural network on provided features.
    """
    try:
        sport = request.sport.upper()
        if sport not in SUPPORTED_SPORTS:
            raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
        
        historical = None
        if request.historical_features:
            historical = [h.dict() for h in request.historical_features]
        
        result = lstm_brain_manager.predict(
            sport=sport,
            current_features=request.current_features.dict(),
            historical_features=historical,
            scale_factor=request.scale_factor or 5.0
        )
        
        return {
            "status": "success",
            "sport": sport,
            "brain_output": result
        }
    except Exception as e:
        logger.error(f"LSTM Brain error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/brain/status")
async def lstm_brain_status():
    """Get LSTM Brain status for all sports."""
    return {
        "status": "success",
        "brain_type": "Multi-Sport LSTM",
        "input_shape": "(15, 6)",
        "architecture": "Bidirectional LSTM (64) -> LSTM (32) -> Dense (32) -> Dense (16) -> Output",
        "sports": lstm_brain_manager.get_status()
    }

# ============================================
# AUTO-GRADER ENDPOINTS (FEEDBACK LOOP)
# ============================================

class GradeRequest(BaseModel):
    """Grade a prediction with actual result."""
    prediction_id: str
    actual_value: float

class BulkGradeRequest(BaseModel):
    """Bulk grade predictions."""
    sport: str
    results: List[Dict]  # [{"player_name": str, "stat_type": str, "actual": float}]

class BiasRequest(BaseModel):
    """Request bias analysis."""
    sport: str
    stat_type: Optional[str] = "all"
    days_back: Optional[int] = 1

class AuditRequest(BaseModel):
    """Request daily audit."""
    days_back: Optional[int] = 1

@app.get("/grader/weights")
async def get_grader_weights():
    """
    Get current dynamic weights for all sports.
    
    These weights are adjusted automatically by the feedback loop.
    """
    return {
        "status": "success",
        "weights": auto_grader.get_all_weights(),
        "description": "Weights are dynamically adjusted based on prediction accuracy"
    }

@app.get("/grader/weights/{sport}")
async def get_sport_weights(sport: str, stat_type: str = "points"):
    """Get weights for a specific sport and stat type."""
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    return {
        "status": "success",
        "sport": sport,
        "stat_type": stat_type,
        "weights": auto_grader.get_weights(sport, stat_type)
    }

@app.post("/grader/grade")
async def grade_prediction(request: GradeRequest):
    """
    Grade a single prediction with actual result.
    
    Call this after game completes with actual player stats.
    """
    result = auto_grader.grade_prediction(request.prediction_id, request.actual_value)
    
    if result is None:
        raise HTTPException(status_code=404, detail=f"Prediction not found: {request.prediction_id}")
    
    return {
        "status": "success",
        "grading": result
    }

@app.post("/grader/grade-bulk")
async def grade_bulk_predictions(request: BulkGradeRequest):
    """
    Grade multiple predictions at once.
    
    Useful for end-of-day grading of all predictions.
    """
    sport = request.sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    result = auto_grader.bulk_grade(sport, request.results)
    
    return {
        "status": "success",
        "sport": sport,
        "grading": result
    }

@app.post("/grader/bias")
async def get_bias_analysis(request: BiasRequest):
    """
    Get bias analysis for predictions.
    
    Shows which factors are over/under-predicting.
    """
    sport = request.sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    result = auto_grader.calculate_bias(sport, request.stat_type or "all", request.days_back or 1)
    
    return {
        "status": "success",
        "bias_analysis": result
    }

@app.post("/grader/audit")
async def run_daily_audit(request: AuditRequest):
    """
    Run daily audit to adjust weights.
    
    This is the core feedback loop - call daily after grading predictions.
    It analyzes yesterday's bias and adjusts weights to improve accuracy.
    """
    result = auto_grader.run_daily_audit(request.days_back or 1)
    
    return {
        "status": "success",
        "audit": result
    }

@app.post("/grader/adjust-weights")
async def adjust_weights(sport: str, stat_type: str = "points", days_back: int = 1, apply: bool = True):
    """
    Manually trigger weight adjustment for specific sport/stat.
    """
    sport = sport.upper()
    if sport not in SUPPORTED_SPORTS:
        raise HTTPException(status_code=400, detail=f"Sport must be one of: {SUPPORTED_SPORTS}")
    
    result = auto_grader.adjust_weights(sport, stat_type, days_back, apply_changes=apply)
    
    return {
        "status": "success",
        "adjustment": result
    }

# ============================================
# SYSTEM STATUS
# ============================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(), 
        "version": "7.0.0", 
        "context_layer": "active", 
        "officials_layer": "active",
        "lstm_brain": "active",
        "auto_grader": "active",
        "supported_sports": SUPPORTED_SPORTS
    }

@app.get("/model-status")
async def model_status():
    return {
        "version": "7.0.0",
        "supported_sports": SUPPORTED_SPORTS,
        "context_layer": {
            "usage_vacuum": "ready",
            "defensive_rank": "ready",
            "pace_vector": "ready",
            "park_factor": "ready (MLB)",
            "context_generator": "ready"
        },
        "officials_layer": {
            "nba_officials": "35+ refs",
            "nfl_officials": "20+ refs",
            "mlb_officials": "20+ umps",
            "nhl_officials": "20+ refs",
            "ncaab_officials": "20+ refs"
        },
        "lstm_brain": lstm_brain_manager.get_status(),
        "auto_grader": {
            "status": "active",
            "weights_per_sport": len(auto_grader.weights),
            "predictions_logged": sum(len(p) for p in auto_grader.predictions.values())
        }
    }

if __name__ == "__main__":
    logger.info("Starting Multi-Sport AI Betting API v7.0.0...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
