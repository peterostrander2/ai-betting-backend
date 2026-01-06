"""
FastAPI endpoints for AI sports betting predictions
UPDATED: Integrates live data from Odds API and Playbook API
17 Signals: 8 AI Models + 4 Esoteric + 5 External Data
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append('..')

# Import AI models (your existing 8)
from models.advanced_ml_backend import MasterPredictionSystem

# Import live data services (NEW)
from services.odds_api_service import odds_service
from services.playbook_api_service import playbook_service

# Import esoteric calculators (your existing 4)
from models.esoteric import (
    GematriaCalculator,
    NumerologyEngine,
    SacredGeometryAnalyzer,
    MoonZodiacTracker
)

from loguru import logger
import uvicorn

# ============================================
# Initialize FastAPI
# ============================================

app = FastAPI(
    title="Bookie-o-em AI Sports Betting API",
    description="17 Signals: 8 AI Models + 4 Esoteric + 5 External Data",
    version="6.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Initialize All Systems
# ============================================

# 8 AI Models (existing)
predictor = MasterPredictionSystem()

# 4 Esoteric Engines (existing)
gematria = GematriaCalculator()
numerology = NumerologyEngine()
sacred_geometry = SacredGeometryAnalyzer()
moon_zodiac = MoonZodiacTracker()

# 5 External Data (NEW - powered by live APIs)
# Sharp Money, Public Fade, Line Value, Key Numbers, Splits
# These are now methods on odds_service and playbook_service

logger.info("🚀 Bookie-o-em v6.3.0 initialized with 17 signals")

# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class PlayerStats(BaseModel):
    stat_type: str = Field(..., example="points")
    expected_value: float = Field(..., example=27.5)
    variance: float = Field(default=45.0)
    std_dev: float = Field(default=6.5)

class Schedule(BaseModel):
    days_rest: int = Field(..., example=1)
    travel_miles: int = Field(default=0)
    games_in_last_7: int = Field(default=3)
    is_home: bool = Field(default=True)

class BettingPercentages(BaseModel):
    public_on_favorite: float = Field(default=50.0)

class PredictionRequest(BaseModel):
    player_id: str = Field(..., example="lebron_james")
    player_name: str = Field(default="")
    opponent_id: str = Field(..., example="gsw")
    opponent_name: str = Field(default="Golden State Warriors")
    features: List[float] = Field(default_factory=list)
    recent_games: List[float] = Field(default_factory=list)
    player_stats: PlayerStats
    schedule: Schedule
    game_id: str = Field(default="")
    current_line: float = Field(..., example=25.5)
    opening_line: float = Field(default=0)
    time_until_game: float = Field(default=6.0)
    betting_percentages: Optional[BettingPercentages] = None
    betting_odds: float = Field(default=-110)
    # NEW: Enable/disable signal groups
    use_esoteric: bool = Field(default=True)
    use_external_data: bool = Field(default=True)

class ComprehensiveResponse(BaseModel):
    """Full 17-signal prediction response"""
    player_id: str
    line: float
    predicted_value: float
    recommendation: str
    ai_score: float  # 0-10 composite score
    confidence: str
    
    # Core prediction
    expected_value: float
    probability: float
    kelly_bet_size: float
    
    # Signal breakdown
    signals: Dict
    signal_count: int
    signals_agreeing: int
    
    # Individual model outputs
    ai_models: Dict
    esoteric_signals: Dict
    external_data: Dict
    
    # Factors and reasoning
    factors: Dict
    reasoning: List[str]

# ============================================
# MAIN PREDICTION ENDPOINT
# ============================================

@app.post("/predict", response_model=ComprehensiveResponse)
async def generate_comprehensive_prediction(request: PredictionRequest):
    """
    Generate full 17-signal prediction
    
    8 AI Models:
    1. Ensemble Stacking
    2. LSTM Neural Network
    3. Monte Carlo KDE
    4. Matchup Model
    5. Line Analyzer
    6. Rest/Fatigue
    7. Injury Impact
    8. Edge Calculator (Kelly)
    
    4 Esoteric:
    9. Gematria
    10. Numerology
    11. Sacred Geometry
    12. Moon/Zodiac
    
    5 External Data:
    13. Sharp Money
    14. Public Fade
    15. Line Value
    16. Key Numbers
    17. Splits
    """
    try:
        logger.info(f"🎯 Generating 17-signal prediction for {request.player_id}")
        
        game_data = request.dict()
        signals = {}
        reasoning = []
        
        # ==========================================
        # SECTION 1: 8 AI MODELS
        # ==========================================
        
        ai_result = predictor.generate_comprehensive_prediction(game_data)
        
        ai_models = {
            "ensemble": {
                "prediction": ai_result.get("predicted_value", 0),
                "confidence": ai_result.get("ensemble_confidence", 0.5),
                "signal": "OVER" if ai_result.get("predicted_value", 0) > request.current_line else "UNDER"
            },
            "lstm": {
                "prediction": ai_result.get("lstm_prediction", ai_result.get("predicted_value", 0)),
                "trend": ai_result.get("lstm_trend", "stable"),
                "signal": "OVER" if ai_result.get("lstm_prediction", 0) > request.current_line else "UNDER"
            },
            "monte_carlo": ai_result.get("monte_carlo", {}),
            "matchup": {
                "adjustment": ai_result.get("matchup_adjustment", 0),
                "signal": "OVER" if ai_result.get("matchup_adjustment", 0) > 0 else "UNDER"
            },
            "line_analyzer": {
                "movement": ai_result.get("line_movement", 0),
                "sharp_indicator": ai_result.get("sharp_indicator", False),
                "signal": ai_result.get("line_signal", "HOLD")
            },
            "rest_fatigue": {
                "adjustment": ai_result.get("rest_adjustment", 0),
                "fatigue_level": ai_result.get("fatigue_level", "normal"),
                "signal": "UNDER" if ai_result.get("rest_adjustment", 0) < -1 else "NEUTRAL"
            },
            "injury_impact": {
                "team_adjustment": ai_result.get("injury_adjustment", 0),
                "signal": "OVER" if ai_result.get("injury_adjustment", 0) > 0 else "NEUTRAL"
            },
            "edge_calculator": {
                "ev_percent": ai_result.get("expected_value", 0),
                "kelly_fraction": ai_result.get("kelly_bet_size", 0),
                "signal": "BET" if ai_result.get("expected_value", 0) > 3 else "PASS"
            }
        }
        
        # Count AI signals
        ai_signals = [m.get("signal") for m in ai_models.values() if isinstance(m, dict) and "signal" in m]
        signals["ai_models"] = ai_signals
        
        reasoning.append(f"AI Models: {ai_result.get('predicted_value', 0):.1f} predicted vs {request.current_line} line")
        
        # ==========================================
        # SECTION 2: 4 ESOTERIC SIGNALS
        # ==========================================
        
        esoteric_signals = {}
        
        if request.use_esoteric:
            try:
                # Gematria analysis
                player_name = request.player_name or request.player_id.replace("_", " ").title()
                gematria_result = gematria.analyze(
                    player_name,
                    request.opponent_name,
                    request.current_line
                )
                esoteric_signals["gematria"] = gematria_result
                
                # Numerology
                game_date = datetime.now()
                numerology_result = numerology.calculate(
                    player_name,
                    game_date,
                    request.current_line
                )
                esoteric_signals["numerology"] = numerology_result
                
                # Sacred Geometry
                geometry_result = sacred_geometry.analyze(
                    request.current_line,
                    ai_result.get("predicted_value", 0),
                    request.recent_games[-5:] if request.recent_games else []
                )
                esoteric_signals["sacred_geometry"] = geometry_result
                
                # Moon/Zodiac
                moon_result = moon_zodiac.get_influence(game_date)
                esoteric_signals["moon_zodiac"] = moon_result
                
                # Count esoteric signals
                esoteric_over = sum(1 for e in esoteric_signals.values() 
                                   if e.get("signal") == "OVER" or e.get("energy") == "positive")
                esoteric_under = sum(1 for e in esoteric_signals.values() 
                                    if e.get("signal") == "UNDER" or e.get("energy") == "negative")
                
                signals["esoteric"] = {
                    "over": esoteric_over,
                    "under": esoteric_under,
                    "dominant": "OVER" if esoteric_over > esoteric_under else "UNDER"
                }
                
                reasoning.append(f"Esoteric: {esoteric_over} OVER vs {esoteric_under} UNDER signals")
                
            except Exception as e:
                logger.warning(f"Esoteric calculation error: {e}")
                esoteric_signals = {"error": str(e)}
        
        # ==========================================
        # SECTION 3: 5 EXTERNAL DATA SIGNALS
        # ==========================================
        
        external_data = {}
        
        if request.use_external_data:
            try:
                # Get live odds data
                odds_data = odds_service.get_odds(sport="basketball_nba")
                
                # Signal 13: Sharp Money
                betting_pcts = playbook_service.get_betting_percentages(request.game_id)
                sharp_analysis = playbook_service.detect_sharp_money(betting_pcts)
                external_data["sharp_money"] = {
                    "side": sharp_analysis.get("sharp_side"),
                    "confidence": sharp_analysis.get("confidence", 0),
                    "indicators": sharp_analysis.get("indicators", []),
                    "signal": sharp_analysis.get("sharp_side", "NEUTRAL").upper()
                }
                
                # Signal 14: Public Fade
                fade_analysis = playbook_service.detect_public_fade(betting_pcts)
                external_data["public_fade"] = {
                    "fade_side": fade_analysis.get("fade_side"),
                    "public_percent": betting_pcts.get("home", {}).get("ticket_percent", 50),
                    "signal": f"FADE_{fade_analysis.get('public_side', 'NONE').upper()}" if fade_analysis.get("fade_side") else "NEUTRAL"
                }
                
                # Signal 15: Line Value
                line_value = odds_service.analyze_line_value(odds_data)
                external_data["line_value"] = {
                    "best_odds": line_value[0].get("best_odds", {}) if line_value else {},
                    "edges": line_value[0].get("line_value_edges", []) if line_value else [],
                    "signal": "VALUE" if line_value and line_value[0].get("line_value_edges") else "NEUTRAL"
                }
                
                # Signal 16: Key Numbers
                key_numbers = odds_service.detect_key_numbers(odds_data)
                external_data["key_numbers"] = {
                    "near_key": len(key_numbers) > 0,
                    "key_number_games": key_numbers[:3],
                    "signal": "KEY_NUMBER" if key_numbers else "NEUTRAL"
                }
                
                # Signal 17: Splits
                splits_analysis = playbook_service.analyze_splits_for_prop(
                    player_id=request.player_id,
                    stat_type=request.player_stats.stat_type,
                    line=request.current_line,
                    opponent_id=request.opponent_id,
                    is_home=request.schedule.is_home,
                    days_rest=request.schedule.days_rest
                )
                external_data["splits"] = {
                    "weighted_prediction": splits_analysis.get("weighted_prediction", 0),
                    "over_probability": splits_analysis.get("over_probability", 0.5),
                    "factors": splits_analysis.get("factors", []),
                    "signal": splits_analysis.get("recommendation", "NEUTRAL")
                }
                
                # Count external signals
                ext_signals = [
                    external_data.get("sharp_money", {}).get("signal", "NEUTRAL"),
                    external_data.get("splits", {}).get("signal", "NEUTRAL")
                ]
                signals["external"] = ext_signals
                
                reasoning.append(f"External Data: Sharp={sharp_analysis.get('sharp_side', 'N/A')}, Splits={splits_analysis.get('recommendation', 'N/A')}")
                
            except Exception as e:
                logger.warning(f"External data error: {e}")
                external_data = {"error": str(e)}
        
        # ==========================================
        # SECTION 4: COMPOSITE SCORING
        # ==========================================
        
        # Count all signals
        all_over_signals = 0
        all_under_signals = 0
        total_signals = 0
        
        # AI model signals
        for model in ai_models.values():
            if isinstance(model, dict) and "signal" in model:
                total_signals += 1
                if model["signal"] == "OVER":
                    all_over_signals += 1
                elif model["signal"] == "UNDER":
                    all_under_signals += 1
        
        # Esoteric signals
        if esoteric_signals and "error" not in esoteric_signals:
            for signal in esoteric_signals.values():
                if isinstance(signal, dict):
                    total_signals += 1
                    if signal.get("signal") == "OVER" or signal.get("energy") == "positive":
                        all_over_signals += 1
                    elif signal.get("signal") == "UNDER" or signal.get("energy") == "negative":
                        all_under_signals += 1
        
        # External data signals
        if external_data and "error" not in external_data:
            for signal in external_data.values():
                if isinstance(signal, dict) and "signal" in signal:
                    total_signals += 1
                    sig = signal["signal"]
                    if "OVER" in sig or sig in ["HOME", "VALUE", "KEY_NUMBER"]:
                        all_over_signals += 1
                    elif "UNDER" in sig or sig == "AWAY":
                        all_under_signals += 1
        
        # Final recommendation
        final_recommendation = "OVER" if all_over_signals > all_under_signals else "UNDER"
        signals_agreeing = max(all_over_signals, all_under_signals)
        
        # Calculate AI Score (0-10)
        agreement_ratio = signals_agreeing / total_signals if total_signals > 0 else 0.5
        ev_boost = min(ai_result.get("expected_value", 0) / 10, 1)  # Cap at +1
        
        ai_score = round(
            (agreement_ratio * 7) +  # Up to 7 points for signal agreement
            (ev_boost * 2) +          # Up to 2 points for +EV
            (1 if signals_agreeing >= 12 else 0),  # +1 bonus for 12+ signals agreeing
            1
        )
        ai_score = min(ai_score, 10)
        
        # Confidence level
        if ai_score >= 8:
            confidence = "SMASH"
        elif ai_score >= 6.5:
            confidence = "HIGH"
        elif ai_score >= 5:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        reasoning.append(f"Final: {signals_agreeing}/{total_signals} signals agree on {final_recommendation}")
        
        # ==========================================
        # BUILD RESPONSE
        # ==========================================
        
        response = ComprehensiveResponse(
            player_id=request.player_id,
            line=request.current_line,
            predicted_value=ai_result.get("predicted_value", 0),
            recommendation=final_recommendation,
            ai_score=ai_score,
            confidence=confidence,
            expected_value=ai_result.get("expected_value", 0),
            probability=ai_result.get("probability", 0.5),
            kelly_bet_size=ai_result.get("kelly_bet_size", 0),
            signals={
                "total": total_signals,
                "over": all_over_signals,
                "under": all_under_signals
            },
            signal_count=total_signals,
            signals_agreeing=signals_agreeing,
            ai_models=ai_models,
            esoteric_signals=esoteric_signals,
            external_data=external_data,
            factors=ai_result.get("factors", {}),
            reasoning=reasoning
        )
        
        logger.success(f"✅ {request.player_id}: {final_recommendation} @ {ai_score}/10 ({confidence})")
        
        return response
        
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


# ============================================
# LIVE DATA ENDPOINTS (NEW)
# ============================================

@app.get("/odds")
async def get_live_odds(sport: str = "basketball_nba"):
    """Get live odds from 20+ sportsbooks"""
    try:
        odds = odds_service.get_odds(sport=sport)
        line_value = odds_service.analyze_line_value(odds)
        key_numbers = odds_service.detect_key_numbers(odds)
        
        return {
            "status": "success",
            "sport": sport,
            "games_count": len(odds),
            "odds": odds,
            "analysis": {
                "line_value": line_value,
                "key_numbers": key_numbers
            }
        }
    except Exception as e:
        logger.error(f"Odds fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/splits/{player_id}")
async def get_player_splits(
    player_id: str,
    stat_type: str = "points",
    line: float = 25.5,
    opponent_id: str = None,
    is_home: bool = True,
    days_rest: int = 1
):
    """Get player splits and prop analysis"""
    try:
        splits = playbook_service.get_player_splits(player_id)
        analysis = playbook_service.analyze_splits_for_prop(
            player_id=player_id,
            stat_type=stat_type,
            line=line,
            opponent_id=opponent_id,
            is_home=is_home,
            days_rest=days_rest
        )
        
        return {
            "status": "success",
            "player_id": player_id,
            "splits": splits,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Splits fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/betting-action/{game_id}")
async def get_betting_action(game_id: str):
    """Get public vs sharp money analysis"""
    try:
        percentages = playbook_service.get_betting_percentages(game_id)
        sharp_money = playbook_service.detect_sharp_money(percentages)
        public_fade = playbook_service.detect_public_fade(percentages)
        
        return {
            "status": "success",
            "game_id": game_id,
            "percentages": percentages,
            "sharp_money_analysis": sharp_money,
            "public_fade_analysis": public_fade
        }
    except Exception as e:
        logger.error(f"Betting action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/injuries")
async def get_injuries(sport: str = "nba", team_id: str = None):
    """Get current injury report"""
    try:
        injuries = playbook_service.get_injuries(sport=sport, team_id=team_id)
        
        return {
            "status": "success",
            "sport": sport,
            "injuries": injuries,
            "count": len(injuries)
        }
    except Exception as e:
        logger.error(f"Injuries fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# EXISTING ENDPOINTS (Keep these)
# ============================================

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "online",
        "message": "Bookie-o-em AI Sports Betting API",
        "version": "6.3.0",
        "signals": {
            "total": 17,
            "ai_models": 8,
            "esoteric": 4,
            "external_data": 5
        },
        "endpoints": [
            "/predict",
            "/odds",
            "/splits/{player_id}",
            "/betting-action/{game_id}",
            "/injuries",
            "/simulate-game",
            "/analyze-line",
            "/calculate-edge",
            "/health",
            "/model-status",
            "/docs"
        ]
    }


@app.post("/simulate-game")
async def simulate_game(
    team_a_stats: Dict,
    team_b_stats: Dict,
    num_simulations: int = 10000
):
    """Run Monte Carlo game simulation"""
    try:
        results = predictor.monte_carlo.simulate_game(
            team_a_stats,
            team_b_stats,
            num_simulations
        )
        return {"status": "success", "simulations": num_simulations, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-line")
async def analyze_line(
    game_id: str,
    current_line: float,
    opening_line: float,
    time_until_game: float,
    betting_percentages: Dict
):
    """Analyze line movement for sharp money indicators"""
    try:
        analysis = predictor.line_analyzer.analyze_line_movement(
            game_id, current_line, opening_line,
            time_until_game, betting_percentages
        )
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate-edge")
async def calculate_edge(your_probability: float, betting_odds: float):
    """Calculate EV and Kelly criterion bet size"""
    try:
        edge = predictor.edge_calculator.calculate_ev(your_probability, betting_odds)
        return {"status": "success", "edge_analysis": edge}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "6.3.0",
        "services": {
            "ai_models": True,
            "esoteric": True,
            "odds_api": not odds_service.demo_mode,
            "playbook_api": not playbook_service.demo_mode
        }
    }


@app.get("/model-status")
async def model_status():
    """Check status of all 17 signals"""
    return {
        "ai_models": {
            "ensemble": predictor.ensemble.is_trained if hasattr(predictor, 'ensemble') else True,
            "lstm": predictor.lstm.model is not None if hasattr(predictor, 'lstm') else True,
            "monte_carlo": "ready",
            "matchup": "ready",
            "line_analyzer": "ready",
            "rest_fatigue": "ready",
            "injury_impact": "ready",
            "edge_calculator": "ready"
        },
        "esoteric": {
            "gematria": "ready",
            "numerology": "ready",
            "sacred_geometry": "ready",
            "moon_zodiac": "ready"
        },
        "external_data": {
            "odds_api": "live" if not odds_service.demo_mode else "demo",
            "playbook_api": "live" if not playbook_service.demo_mode else "demo",
            "sharp_money": "ready",
            "public_fade": "ready",
            "splits": "ready"
        },
        "total_signals": 17
    }


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    logger.info("🚀 Starting Bookie-o-em v6.3.0 - 17 Signal AI Sports Betting API")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )
