"""
Trap Learning Loop API Router (v19.0)
=====================================
Endpoints for managing pre-game traps and viewing post-game evaluations.

Endpoints:
- POST /live/traps/           - Create a new trap
- GET  /live/traps/           - List all traps
- GET  /live/traps/{trap_id}  - Get trap details + history
- PUT  /live/traps/{trap_id}/status - Update trap status
- POST /live/traps/evaluate/dry-run - Test trap without applying
- GET  /live/traps/history/{engine} - Get adjustment history
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

trap_router = APIRouter(prefix="/live/traps", tags=["Trap Learning Loop"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ConditionItem(BaseModel):
    """Single condition in a trap."""
    field: str = Field(..., description="Field to check (result, margin, numerology_day, etc.)")
    comparator: str = Field(..., description="Comparison operator (==, >=, <=, >, <, IN, BETWEEN)")
    value: Any = Field(..., description="Value to compare against")


class TrapCondition(BaseModel):
    """Condition structure for a trap."""
    operator: str = Field("AND", description="Logical operator (AND/OR)")
    conditions: List[ConditionItem] = Field(..., description="List of conditions")


class TrapAction(BaseModel):
    """Action to take when trap fires."""
    type: str = Field("WEIGHT_ADJUST", description="Action type (WEIGHT_ADJUST, AUDIT_TRIGGER, ALERT_ONLY)")
    delta: Optional[float] = Field(None, description="Adjustment amount (for WEIGHT_ADJUST)")
    direction: Optional[str] = Field(None, description="Direction (increase/decrease)")
    audit_type: Optional[str] = Field(None, description="Audit type (for AUDIT_TRIGGER)")


class CreateTrapRequest(BaseModel):
    """Request to create a new trap."""
    trap_id: Optional[str] = Field(None, description="Unique trap ID (auto-generated if not provided)")
    name: str = Field(..., description="Human-readable trap name")
    sport: str = Field(..., description="Sport (NBA, NFL, MLB, NHL, NCAAB, ALL)")
    team: Optional[str] = Field(None, description="Specific team or None for all")
    condition: TrapCondition = Field(..., description="Condition to evaluate")
    action: TrapAction = Field(..., description="Action when triggered")
    target_engine: str = Field(..., description="Engine to adjust (research, esoteric, jarvis, context, ai)")
    target_parameter: str = Field(..., description="Parameter to adjust")
    adjustment_cap: float = Field(0.05, description="Max adjustment per trigger (0-0.05)")
    cooldown_hours: int = Field(24, description="Hours between triggers")
    max_triggers_per_week: int = Field(3, description="Max triggers per week")
    description: Optional[str] = Field(None, description="Detailed description")


class TrapResponse(BaseModel):
    """Response for trap operations."""
    success: bool
    trap_id: str
    message: Optional[str] = None


class TrapSummary(BaseModel):
    """Summary of a trap for listing."""
    trap_id: str
    name: str
    sport: str
    target_engine: str
    target_parameter: str
    status: str
    created_at: str
    team: Optional[str] = None


class TrapDetail(BaseModel):
    """Detailed trap info including history."""
    trap_id: str
    name: str
    sport: str
    team: Optional[str]
    condition: Dict[str, Any]
    action: Dict[str, Any]
    target_engine: str
    target_parameter: str
    adjustment_cap: float
    cooldown_hours: int
    max_triggers_per_week: int
    status: str
    created_at: str
    description: Optional[str]
    # Stats
    total_evaluations: int
    times_triggered: int
    times_applied: int
    cumulative_adjustment: float
    last_triggered: Optional[str]
    recent_adjustments: List[Dict[str, Any]]


class DryRunRequest(BaseModel):
    """Request for dry-run evaluation."""
    trap_id: str = Field(..., description="Trap ID to evaluate")
    game_result: Dict[str, Any] = Field(..., description="Simulated game result")


class DryRunResponse(BaseModel):
    """Response for dry-run evaluation."""
    condition_met: bool
    condition_values: Dict[str, Any]
    would_apply: bool
    proposed_adjustment: float
    safety_check: str


class AdjustmentHistoryResponse(BaseModel):
    """Response for adjustment history."""
    engine: str
    days_back: int
    adjustments: List[Dict[str, Any]]
    net_change: float


# ============================================
# ENDPOINTS
# ============================================

@trap_router.post("/", response_model=TrapResponse)
async def create_trap(request: CreateTrapRequest):
    """
    Create a new pre-game trap.

    Example:
    ```json
    {
        "name": "Dallas Blowout Public Fade",
        "sport": "NBA",
        "team": "Dallas Mavericks",
        "condition": {
            "operator": "AND",
            "conditions": [
                {"field": "result", "comparator": "==", "value": "win"},
                {"field": "margin", "comparator": ">=", "value": 20}
            ]
        },
        "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
        "target_engine": "research",
        "target_parameter": "weight_public_fade"
    }
    ```
    """
    try:
        from trap_learning_loop import get_trap_loop

        trap_loop = get_trap_loop()

        # Convert Pydantic models to dicts
        trap_data = request.dict()
        trap_data["condition"] = trap_data["condition"]
        trap_data["action"] = trap_data["action"]

        trap = trap_loop.create_trap(trap_data)

        return TrapResponse(
            success=True,
            trap_id=trap.trap_id,
            message=f"Trap '{trap.name}' created successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create trap: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to create trap: {str(e)}")


@trap_router.get("/", response_model=List[TrapSummary])
async def list_traps(
    sport: Optional[str] = Query(None, description="Filter by sport"),
    status: str = Query("ACTIVE", description="Filter by status (ACTIVE, PAUSED, RETIRED)")
):
    """List all traps, optionally filtered by sport and status."""
    try:
        from trap_learning_loop import get_trap_loop

        trap_loop = get_trap_loop()
        traps = trap_loop.get_traps(sport=sport, status=status if status != "ALL" else None)

        return [
            TrapSummary(
                trap_id=t.trap_id,
                name=t.name,
                sport=t.sport,
                team=t.team,
                target_engine=t.target_engine,
                target_parameter=t.target_parameter,
                status=t.status,
                created_at=t.created_at
            )
            for t in traps
        ]

    except Exception as e:
        logger.error("Failed to list traps: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@trap_router.get("/{trap_id}", response_model=TrapDetail)
async def get_trap(trap_id: str):
    """Get trap details including evaluation history."""
    try:
        from trap_learning_loop import get_trap_loop
        from dataclasses import asdict

        trap_loop = get_trap_loop()
        trap = trap_loop.get_trap(trap_id)

        if not trap:
            raise HTTPException(status_code=404, detail=f"Trap '{trap_id}' not found")

        stats = trap_loop.get_trap_stats(trap_id)

        return TrapDetail(
            trap_id=trap.trap_id,
            name=trap.name,
            sport=trap.sport,
            team=trap.team,
            condition=trap.condition,
            action=trap.action,
            target_engine=trap.target_engine,
            target_parameter=trap.target_parameter,
            adjustment_cap=trap.adjustment_cap,
            cooldown_hours=trap.cooldown_hours,
            max_triggers_per_week=trap.max_triggers_per_week,
            status=trap.status,
            created_at=trap.created_at,
            description=trap.description,
            total_evaluations=stats.get("total_evaluations", 0),
            times_triggered=stats.get("times_triggered", 0),
            times_applied=stats.get("times_applied", 0),
            cumulative_adjustment=stats.get("cumulative_adjustment", 0.0),
            last_triggered=stats.get("last_triggered"),
            recent_adjustments=stats.get("adjustments", [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get trap %s: %s", trap_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@trap_router.put("/{trap_id}/status")
async def update_trap_status(trap_id: str, status: str = Query(..., description="New status")):
    """Update trap status (ACTIVE, PAUSED, RETIRED)."""
    try:
        from trap_learning_loop import get_trap_loop

        if status not in ["ACTIVE", "PAUSED", "RETIRED"]:
            raise HTTPException(status_code=400, detail="Invalid status. Use ACTIVE, PAUSED, or RETIRED")

        trap_loop = get_trap_loop()
        success = trap_loop.update_status(trap_id, status)

        if not success:
            raise HTTPException(status_code=404, detail=f"Trap '{trap_id}' not found")

        return {"success": True, "trap_id": trap_id, "new_status": status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update trap status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@trap_router.post("/evaluate/dry-run", response_model=DryRunResponse)
async def dry_run_evaluation(request: DryRunRequest):
    """
    Test trap evaluation without applying changes.

    Useful for validating trap conditions before real games.

    Example game_result:
    ```json
    {
        "game_date": "2026-02-03",
        "home_team": "Dallas Mavericks",
        "away_team": "Boston Celtics",
        "home_score": 120,
        "away_score": 95,
        "result": "win",
        "margin": 25
    }
    ```
    """
    try:
        from trap_learning_loop import get_trap_loop, enrich_game_result

        trap_loop = get_trap_loop()
        trap = trap_loop.get_trap(request.trap_id)

        if not trap:
            raise HTTPException(status_code=404, detail=f"Trap '{request.trap_id}' not found")

        # Enrich game result with calculated fields
        enriched_result = enrich_game_result(request.game_result)

        # Evaluate (dry run)
        evaluation = trap_loop.evaluate_trap(trap, enriched_result, dry_run=True)

        # Check safety
        valid, safety_reason = trap_loop._validate_adjustment_safety(trap)

        return DryRunResponse(
            condition_met=evaluation.condition_met,
            condition_values=evaluation.condition_values,
            would_apply=evaluation.condition_met and valid,
            proposed_adjustment=evaluation.adjustment_applied or 0.0,
            safety_check=safety_reason if valid else f"BLOCKED: {safety_reason}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Dry run failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@trap_router.get("/history/{engine}", response_model=AdjustmentHistoryResponse)
async def get_adjustment_history(
    engine: str,
    days_back: int = Query(30, description="Days of history to return")
):
    """Get adjustment history for an engine."""
    try:
        from trap_learning_loop import get_trap_loop, SUPPORTED_ENGINES

        if engine not in SUPPORTED_ENGINES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid engine. Supported: {list(SUPPORTED_ENGINES.keys())}"
            )

        trap_loop = get_trap_loop()
        history = trap_loop.get_adjustment_history(engine=engine, days_back=days_back)

        net_change = sum(h.get("delta", 0) for h in history)

        return AdjustmentHistoryResponse(
            engine=engine,
            days_back=days_back,
            adjustments=history,
            net_change=net_change
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@trap_router.get("/stats/summary")
async def get_traps_summary():
    """Get summary statistics for all traps."""
    try:
        from trap_learning_loop import get_trap_loop

        trap_loop = get_trap_loop()
        all_traps = trap_loop.get_traps(status=None)  # All statuses

        by_status = {}
        by_engine = {}
        by_sport = {}

        for trap in all_traps:
            by_status[trap.status] = by_status.get(trap.status, 0) + 1
            by_engine[trap.target_engine] = by_engine.get(trap.target_engine, 0) + 1
            by_sport[trap.sport] = by_sport.get(trap.sport, 0) + 1

        # Recent activity
        recent_evaluations = trap_loop.get_evaluations(days_back=7)
        triggered = [e for e in recent_evaluations if e.condition_met]
        applied = [e for e in recent_evaluations if e.action_taken == "APPLIED"]

        return {
            "total_traps": len(all_traps),
            "by_status": by_status,
            "by_engine": by_engine,
            "by_sport": by_sport,
            "last_7_days": {
                "evaluations": len(recent_evaluations),
                "triggered": len(triggered),
                "applied": len(applied),
            }
        }

    except Exception as e:
        logger.error("Failed to get summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
