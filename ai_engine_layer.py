# ai_engine_layer.py v1.0 - 8 AI Engine Layer
# Phase 1: Structured heuristics as placeholders for ML models
# Upgradeable to real ML (XGBoost, LSTM, Monte Carlo) in v10.25+

from typing import Dict, Any, List, Optional
import logging
import math

logger = logging.getLogger("ai_engine_layer")

# ============================================================================
# AI ENGINE CONFIGURATION
# ============================================================================

# Model weights for combining 8 AI engines into single ai_score
AI_MODEL_WEIGHTS = {
    "ensemble": 0.20,        # Primary predictive model (XGBoost/LGBM/RF placeholder)
    "lstm": 0.15,            # Sequence/trend prediction
    "monte_carlo": 0.10,     # Probability simulation
    "line_movement": 0.15,   # Sharp line analysis (uses existing sharp signals)
    "rest_fatigue": 0.10,    # Rest advantage / B2B penalty
    "injury_impact": 0.10,   # Key player availability
    "matchup_model": 0.10,   # Head-to-head analysis
    "edge_calculator": 0.10  # Kelly sizing / value identification
}

# Baseline scores when no signal data available
BASELINE_SCORE = 5.0


def calculate_ai_engine_score(
    prediction_data: Dict[str, Any],
    sharp_signal: Optional[Dict] = None,
    context_data: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Calculate 8 AI Engine scores and combine into single ai_score.

    Phase 1: Uses structured heuristics based on available data.
    Phase 2 (v10.25+): Will plug in real ML models.

    Args:
        prediction_data: Pick data including odds, line, market, player, teams
        sharp_signal: Sharp money / RLM signal data
        context_data: Additional context (rest days, injuries, etc.)

    Returns:
        {
            "ai_score": float (0-10),
            "ai_breakdown": {model_name: score for each of 8 models},
            "ai_reasons": [str]
        }
    """
    sharp_signal = sharp_signal or {}
    context_data = context_data or {}

    ai_reasons = []
    ai_breakdown = {}

    # Extract common fields
    odds = prediction_data.get("odds", -110)
    line = prediction_data.get("line", 0)
    market = prediction_data.get("market", "")
    player_name = prediction_data.get("player_name", "")
    home_team = prediction_data.get("home_team", "")
    away_team = prediction_data.get("away_team", "")
    is_home = prediction_data.get("is_home", False)

    # ========================================================================
    # MODEL 1: ENSEMBLE (XGBoost/LGBM/RF placeholder)
    # Phase 1: Uses odds + line quality heuristics
    # ========================================================================
    ensemble_score = BASELINE_SCORE

    # Favorable odds boost
    if odds and isinstance(odds, (int, float)):
        if -130 <= odds <= -100:
            ensemble_score += 0.5
            ai_reasons.append("AI ENGINE: Ensemble (favorable juice -130 to -100) +0.5")
        elif odds > 100 and odds <= 150:
            ensemble_score += 0.3
            ai_reasons.append("AI ENGINE: Ensemble (plus money value +100 to +150) +0.3")
        elif odds < -200:
            ensemble_score -= 0.3
            ai_reasons.append("AI ENGINE: Ensemble (heavy favorite tax) -0.3")

    ai_breakdown["ensemble"] = round(min(10, max(0, ensemble_score)), 2)

    # ========================================================================
    # MODEL 2: LSTM (Sequence/trend prediction placeholder)
    # Phase 1: Uses momentum heuristics
    # ========================================================================
    lstm_score = BASELINE_SCORE

    # Line movement as proxy for trend detection
    line_variance = sharp_signal.get("line_variance", 0)
    if line_variance > 1.5:
        lstm_score += 0.6
        ai_reasons.append("AI ENGINE: LSTM (strong line movement trend) +0.6")
    elif line_variance > 0.5:
        lstm_score += 0.3
        ai_reasons.append("AI ENGINE: LSTM (moderate line movement) +0.3")

    ai_breakdown["lstm"] = round(min(10, max(0, lstm_score)), 2)

    # ========================================================================
    # MODEL 3: MONTE CARLO (Probability simulation placeholder)
    # Phase 1: Uses implied probability vs baseline
    # ========================================================================
    monte_carlo_score = BASELINE_SCORE

    # Calculate implied probability from odds
    if odds and isinstance(odds, (int, float)):
        if odds < 0:
            implied_prob = abs(odds) / (abs(odds) + 100)
        else:
            implied_prob = 100 / (odds + 100)

        # Sweet spot: 45-55% implied (competitive lines)
        if 0.45 <= implied_prob <= 0.55:
            monte_carlo_score += 0.4
            ai_reasons.append(f"AI ENGINE: Monte Carlo (competitive line {implied_prob:.0%}) +0.4")
        elif implied_prob > 0.70:
            monte_carlo_score -= 0.3
            ai_reasons.append(f"AI ENGINE: Monte Carlo (heavy favorite {implied_prob:.0%}) -0.3")

    ai_breakdown["monte_carlo"] = round(min(10, max(0, monte_carlo_score)), 2)

    # ========================================================================
    # MODEL 4: LINE MOVEMENT (Sharp line analysis - uses existing sharp signals)
    # Phase 1: Direct mapping from sharp_signal data
    # ========================================================================
    line_movement_score = BASELINE_SCORE

    sharp_strength = sharp_signal.get("signal_strength", "NONE")
    sharp_diff = sharp_signal.get("diff", 0) or 0

    if sharp_strength == "STRONG" or sharp_diff >= 15:
        line_movement_score += 1.5
        ai_reasons.append("AI ENGINE: Line Movement (STRONG sharp signal) +1.5")
    elif sharp_strength == "MODERATE" or sharp_diff >= 10:
        line_movement_score += 0.8
        ai_reasons.append("AI ENGINE: Line Movement (MODERATE sharp signal) +0.8")
    elif sharp_diff >= 5:
        line_movement_score += 0.3
        ai_reasons.append("AI ENGINE: Line Movement (slight sharp lean) +0.3")

    # RLM bonus
    if line_variance > 1.0:
        line_movement_score += 0.5
        ai_reasons.append("AI ENGINE: Line Movement (RLM detected) +0.5")

    ai_breakdown["line_movement"] = round(min(10, max(0, line_movement_score)), 2)

    # ========================================================================
    # MODEL 5: REST/FATIGUE (Rest advantage / B2B penalty)
    # Phase 1: Uses context_data if available
    # ========================================================================
    rest_fatigue_score = BASELINE_SCORE

    team_rest_days = context_data.get("team_rest_days", 1)
    opp_rest_days = context_data.get("opp_rest_days", 1)
    rest_diff = team_rest_days - opp_rest_days

    if rest_diff >= 2:
        rest_fatigue_score += 0.8
        ai_reasons.append(f"AI ENGINE: Rest/Fatigue (+{rest_diff} rest advantage) +0.8")
    elif rest_diff == 1:
        rest_fatigue_score += 0.4
        ai_reasons.append("AI ENGINE: Rest/Fatigue (+1 rest advantage) +0.4")
    elif rest_diff <= -2:
        rest_fatigue_score -= 0.5
        ai_reasons.append(f"AI ENGINE: Rest/Fatigue ({rest_diff} rest disadvantage) -0.5")

    # B2B penalty
    if team_rest_days == 0:
        rest_fatigue_score -= 0.6
        ai_reasons.append("AI ENGINE: Rest/Fatigue (B2B penalty) -0.6")

    ai_breakdown["rest_fatigue"] = round(min(10, max(0, rest_fatigue_score)), 2)

    # ========================================================================
    # MODEL 6: INJURY IMPACT (Key player availability)
    # Phase 1: Uses context_data injury flags
    # ========================================================================
    injury_impact_score = BASELINE_SCORE

    key_player_out = context_data.get("key_player_out", False)
    opp_key_player_out = context_data.get("opp_key_player_out", False)
    injury_count = context_data.get("injury_count", 0)
    opp_injury_count = context_data.get("opp_injury_count", 0)

    # Hospital fade logic
    if opp_key_player_out:
        injury_impact_score += 0.7
        ai_reasons.append("AI ENGINE: Injury Impact (opponent key player OUT) +0.7")

    if key_player_out:
        injury_impact_score -= 0.7
        ai_reasons.append("AI ENGINE: Injury Impact (team key player OUT) -0.7")

    # Injury differential
    injury_diff = opp_injury_count - injury_count
    if injury_diff >= 2:
        injury_impact_score += 0.3
        ai_reasons.append("AI ENGINE: Injury Impact (opponent more banged up) +0.3")

    ai_breakdown["injury_impact"] = round(min(10, max(0, injury_impact_score)), 2)

    # ========================================================================
    # MODEL 7: MATCHUP MODEL (Head-to-head analysis placeholder)
    # Phase 1: Uses home/away + market type heuristics
    # ========================================================================
    matchup_model_score = BASELINE_SCORE

    # Home advantage (slight)
    if is_home:
        matchup_model_score += 0.3
        ai_reasons.append("AI ENGINE: Matchup Model (home advantage) +0.3")

    # Market-specific adjustments
    if market == "spreads":
        abs_line = abs(line) if line else 0
        if 3 <= abs_line <= 7:
            matchup_model_score += 0.3
            ai_reasons.append("AI ENGINE: Matchup Model (competitive spread 3-7) +0.3")
    elif market == "totals":
        matchup_model_score += 0.2
        ai_reasons.append("AI ENGINE: Matchup Model (totals market preference) +0.2")

    ai_breakdown["matchup_model"] = round(min(10, max(0, matchup_model_score)), 2)

    # ========================================================================
    # MODEL 8: EDGE CALCULATOR (Kelly sizing / value identification)
    # Phase 1: Uses implied probability edge calculation
    # ========================================================================
    edge_calculator_score = BASELINE_SCORE

    # Assume model probability is baseline + sharp signal boost
    model_prob = 0.50  # baseline
    if sharp_strength == "STRONG":
        model_prob = 0.58
    elif sharp_strength == "MODERATE":
        model_prob = 0.54

    # Calculate implied probability
    if odds and isinstance(odds, (int, float)):
        if odds < 0:
            implied_prob = abs(odds) / (abs(odds) + 100)
        else:
            implied_prob = 100 / (odds + 100)

        edge = model_prob - implied_prob

        if edge >= 0.08:
            edge_calculator_score += 1.0
            ai_reasons.append(f"AI ENGINE: Edge Calculator (strong edge +{edge:.1%}) +1.0")
        elif edge >= 0.04:
            edge_calculator_score += 0.5
            ai_reasons.append(f"AI ENGINE: Edge Calculator (moderate edge +{edge:.1%}) +0.5")
        elif edge <= -0.05:
            edge_calculator_score -= 0.5
            ai_reasons.append(f"AI ENGINE: Edge Calculator (negative edge {edge:.1%}) -0.5")

    ai_breakdown["edge_calculator"] = round(min(10, max(0, edge_calculator_score)), 2)

    # ========================================================================
    # COMBINE: Weighted average of all 8 models
    # ========================================================================
    ai_score = sum(
        ai_breakdown[model] * weight
        for model, weight in AI_MODEL_WEIGHTS.items()
    )
    ai_score = round(min(10, max(0, ai_score)), 2)

    # Add summary reason if meaningful deviation from baseline
    if ai_score >= 6.0:
        ai_reasons.insert(0, f"AI ENGINE: Combined Score {ai_score}/10 (8-model weighted average)")
    elif ai_score <= 4.0:
        ai_reasons.insert(0, f"AI ENGINE: Combined Score {ai_score}/10 (8-model weighted average - caution)")

    return {
        "ai_score": ai_score,
        "ai_breakdown": ai_breakdown,
        "ai_reasons": ai_reasons
    }


def get_ai_engine_defaults() -> Dict[str, Any]:
    """
    Return default AI engine values when calculation fails.
    Used by enforcement guardrail.
    """
    return {
        "ai_score": BASELINE_SCORE,
        "ai_breakdown": {
            "ensemble": BASELINE_SCORE,
            "lstm": BASELINE_SCORE,
            "monte_carlo": BASELINE_SCORE,
            "line_movement": BASELINE_SCORE,
            "rest_fatigue": BASELINE_SCORE,
            "injury_impact": BASELINE_SCORE,
            "matchup_model": BASELINE_SCORE,
            "edge_calculator": BASELINE_SCORE
        },
        "ai_reasons": ["AI ENGINE: Baseline defaults applied (no signals available)"]
    }
