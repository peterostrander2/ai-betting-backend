"""
FastAPI endpoints for AI sports betting predictions
v6.7.0 - Multi-Sport Context Layer (NBA, NFL, MLB, NHL, NCAAB)
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
    SUPPORTED_SPORTS,
    SPORT_POSITIONS,
    SPORT_STAT_TYPES
)
from loguru import logger
import uvicorn

app = FastAPI(
    title="AI Sports Betting API",
    description="Multi-Sport AI Predictions with Context Layer (NBA, NFL, MLB, NHL, NCAAB)",
    version="6.7.0"
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

# ============================================
# ROOT
# ============================================

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Multi-Sport AI Betting API with Context Layer",
        "version": "6.7.0",
        "supported_sports": SUPPORTED_SPORTS,
        "endpoints": ["/predict-context", "/predict-batch", "/sports", "/defense-rank", 
                      "/defense-rankings/{sport}/{position}", "/usage-vacuum", "/game-pace",
                      "/pace-rankings/{sport}", "/park-factor", "/park-factors", "/calculate-edge", "/health", "/docs"]
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
        
        response = {
            "status": "success", "sport": sport,
            "prediction": {
                "player": request.player_name, "team": request.player_team, "opponent": request.opponent_team,
                "position": request.position, "stat_type": request.stat_type, "base": request.player_avg,
                "final": final_pred, "line": request.line, "recommendation": None,
                "confidence": waterfall["confidence"], "is_smash_spot": waterfall["isSmashSpot"]
            },
            "lstm_features": context["lstm_features"], "waterfall": waterfall,
            "badges": context["badges"], "raw_context": context["raw_context"]
        }
        
        if request.line:
            edge = final_pred - request.line
            response["prediction"]["recommendation"] = "OVER" if edge > 0 else "UNDER"
            response["edge"] = {"raw": round(edge, 1), "percent": round((edge / request.line) * 100, 1) if request.line != 0 else 0, "direction": "OVER" if edge > 0 else "UNDER"}
        
        if request.odds and request.line:
            edge_pct = (final_pred - request.line) / request.line if request.line != 0 else 0
            implied_prob = abs(request.odds) / (abs(request.odds) + 100) if request.odds < 0 else 100 / (request.odds + 100)
            our_prob = max(0.1, min(0.9, 0.5 + (edge_pct * 2)))
            ev = (our_prob * 100) - ((1 - our_prob) * 100)
            response["ev"] = {"percent": round(ev, 1), "per_100": round(ev, 2), "implied_prob": round(implied_prob * 100, 1), "our_prob": round(our_prob * 100, 1)}
        
        logger.success(f"[{sport}] Prediction: {final_pred} | Smash: {waterfall['isSmashSpot']}")
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "version": "6.7.0", "context_layer": "active", "supported_sports": SUPPORTED_SPORTS}

@app.get("/model-status")
async def model_status():
    return {"version": "6.7.0", "supported_sports": SUPPORTED_SPORTS, "context_layer": {"usage_vacuum": "ready", "defensive_rank": "ready", "pace_vector": "ready", "park_factor": "ready (MLB)", "context_generator": "ready"}}

if __name__ == "__main__":
    logger.info("Starting Multi-Sport AI Betting API v6.7.0...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
