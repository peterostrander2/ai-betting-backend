"""
Pick Converter - Transforms internal PublishedPick to API output schema
Handles backfill logic for old picks missing new fields.
"""
from typing import List, Optional
from models.pick_schema import PickOutputSchema, MarketType, GameStatus, TierLevel


def compute_description(pick) -> str:
    """
    Compute human-readable description from pick primitives.
    Used for backfill when description field is empty.

    Examples:
    - "Jamal Murray Assists Over 3.5"
    - "Bucks @ 76ers — Total Under 246.5"
    - "Kings ML +135"
    """
    if pick.player_name:
        # Prop pick
        prop_name = pick.prop_type.title() if pick.prop_type else "Prop"
        return f"{pick.player_name} {prop_name} {pick.side} {pick.line}"
    else:
        # Game pick
        matchup = pick.matchup or f"{pick.away_team} @ {pick.home_team}"
        pick_type = pick.pick_type or pick.market or "Pick"

        if "MONEYLINE" in pick_type.upper() or "ML" in pick_type.upper():
            # Moneyline: show team + odds
            odds_display = f"{pick.odds:+d}" if pick.odds else ""
            return f"{matchup} — {pick.side} ML {odds_display}"
        elif pick.side:
            # Has side (Total Over/Under, Spread with team)
            return f"{matchup} — {pick_type} {pick.side} {pick.line}"
        else:
            # Fallback
            return f"{matchup} — {pick_type} {pick.line}"


def compute_pick_detail(pick) -> str:
    """
    Compute compact bet string from pick primitives.
    Used for backfill when pick_detail field is empty.

    Examples:
    - "Assists Over 3.5"
    - "Total Under 246.5"
    - "Spread 76ers +6.5"
    """
    if pick.player_name:
        # Prop pick
        prop_name = pick.prop_type.title() if pick.prop_type else "Prop"
        return f"{prop_name} {pick.side} {pick.line}"
    else:
        # Game pick
        pick_type = pick.pick_type or pick.market or "Pick"

        if "MONEYLINE" in pick_type.upper() or "ML" in pick_type.upper():
            odds_display = f"{pick.odds:+d}" if pick.odds else ""
            return f"{pick.side} ML {odds_display}"
        elif pick.side:
            return f"{pick_type} {pick.side} {pick.line}"
        else:
            return f"{pick_type} {pick.line}"


def infer_side_for_totals(pick) -> str:
    """
    Infer Over/Under for totals if side is missing.
    Uses result + actual value to determine what was picked.

    Only works for graded picks. Returns empty string if can't infer.
    """
    if pick.side:
        return pick.side

    # Check if this is a total (line > 50 suggests total, not spread)
    if pick.line < 50:
        return ""

    # Need result and actual to infer
    if not pick.result or pick.actual_value is None:
        return ""

    # Infer from grading logic
    if pick.result == "WIN":
        # Won - if actual > line, we picked Over; if actual < line, we picked Under
        return "Over" if pick.actual_value > pick.line else "Under"
    elif pick.result == "LOSS":
        # Lost - opposite of WIN logic
        return "Under" if pick.actual_value > pick.line else "Over"
    else:
        # PUSH or unknown
        return "Push"


def normalize_market_type(pick) -> MarketType:
    """Convert pick_type or market string to MarketType enum"""
    market_str = (pick.market or pick.pick_type or "").upper()

    if "SPREAD" in market_str:
        return MarketType.SPREAD
    elif "TOTAL" in market_str:
        return MarketType.TOTAL
    elif "MONEYLINE" in market_str or "ML" in market_str:
        return MarketType.MONEYLINE
    elif "PROP" in market_str or pick.player_name:
        return MarketType.PROP
    else:
        # Default to PROP if player_name exists, else TOTAL (most common)
        return MarketType.PROP if pick.player_name else MarketType.TOTAL


def normalize_game_status(pick) -> GameStatus:
    """Convert event_status or status to GameStatus enum"""
    status_str = (pick.game_status or pick.event_status or pick.status or "").upper()

    if "LIVE" in status_str or "IN_PROGRESS" in status_str or "INPROGRESS" in status_str:
        return GameStatus.LIVE
    elif "FINAL" in status_str or "COMPLETED" in status_str or "ENDED" in status_str:
        return GameStatus.FINAL
    else:
        return GameStatus.SCHEDULED


def normalize_tier(pick) -> TierLevel:
    """Convert tier string to TierLevel enum"""
    tier_str = (pick.tier or "").upper()

    if "TITANIUM" in tier_str or "SMASH" in tier_str:
        return TierLevel.TITANIUM_SMASH
    elif "GOLD" in tier_str:
        return TierLevel.GOLD_STAR
    elif "EDGE" in tier_str or "LEAN" in tier_str:
        return TierLevel.EDGE_LEAN
    elif "MONITOR" in tier_str:
        return TierLevel.MONITOR
    else:
        return TierLevel.PASS


def published_pick_to_output_schema(pick) -> PickOutputSchema:
    """
    Convert PublishedPick to PickOutputSchema.
    Handles backfill for old picks missing new v15.0 fields.

    Args:
        pick: PublishedPick dataclass instance

    Returns:
        PickOutputSchema with all required fields populated
    """

    # Backfill description and pick_detail if missing
    description = pick.description if pick.description else compute_description(pick)
    pick_detail = pick.pick_detail if pick.pick_detail else compute_pick_detail(pick)

    # Backfill side if missing (for totals)
    side = pick.side if pick.side else infer_side_for_totals(pick)

    # Ensure matchup is always populated
    matchup = pick.matchup if pick.matchup else f"{pick.away_team} @ {pick.home_team}"

    # Normalize enums
    market = normalize_market_type(pick)
    game_status = normalize_game_status(pick)
    tier = normalize_tier(pick)

    # Source IDs consolidation
    source_ids = {
        **(pick.provider_event_ids or {}),
        **(pick.provider_player_ids or {})
    }

    # Jason Sim consolidation
    jason_projected_total = getattr(pick, 'jason_projected_total', None)
    jason_variance_flag = getattr(pick, 'jason_variance_flag', pick.variance_flag if hasattr(pick, 'variance_flag') else "")

    # Ensure created_at exists
    created_at = pick.published_at or pick.timestamp_at_bet or ""

    return PickOutputSchema(
        # Human-readable fields
        description=description,
        pick_detail=pick_detail,
        matchup=matchup,
        sport=pick.sport.upper(),
        market=market,
        side=side or "N/A",  # Never empty
        line=pick.line,
        odds_american=pick.odds_american or pick.odds,
        book=pick.book_key or pick.book,
        sportsbook_url=pick.sportsbook_event_url,
        start_time_et=pick.commence_time_iso or pick.game_start_time_et,
        game_status=game_status,
        is_live_bet_candidate=getattr(pick, 'is_live_bet_candidate', pick.is_live if hasattr(pick, 'is_live') else False),
        was_game_already_started=getattr(pick, 'was_game_already_started', pick.already_started),

        # Pick context
        player_name=pick.player_name or None,
        home_team=pick.home_team,
        away_team=pick.away_team,
        prop_type=pick.prop_type or None,

        # Canonical machine fields
        pick_id=pick.pick_id,
        event_id=pick.canonical_event_id or "",
        player_id=pick.canonical_player_id or None,
        team_id=None,  # Not currently tracked
        source_ids=source_ids,

        # Timestamps
        created_at=created_at,
        published_at=pick.published_at or None,
        graded_at=pick.graded_at or None,

        # Scoring & tier
        final_score=pick.final_score,
        base_score=pick.base_score,
        tier=tier,
        units=pick.units,
        titanium_flag=pick.titanium_flag,
        titanium_modules_hit=getattr(pick, 'titanium_modules_hit', []),
        titanium_reasons=pick.titanium_reasons or [],

        # Engine breakdown
        ai_score=pick.ai_score,
        research_score=pick.research_score,
        esoteric_score=pick.esoteric_score,
        jarvis_score=pick.jarvis_score,
        research_breakdown=pick.research_breakdown or {},
        esoteric_breakdown=getattr(pick, 'esoteric_breakdown', {}),
        jarvis_breakdown=getattr(pick, 'jarvis_breakdown', {}),

        # Jason Sim
        jason_ran=pick.jason_ran,
        jason_sim_boost=pick.jason_sim_boost,
        jason_blocked=pick.jason_blocked,
        jason_win_pct_home=pick.jason_win_pct_home,
        jason_win_pct_away=pick.jason_win_pct_away,
        jason_projected_total=jason_projected_total,
        jason_variance_flag=jason_variance_flag,
        jason_injury_state=pick.injury_state if hasattr(pick, 'injury_state') else "CONFIRMED_ONLY",
        jason_sim_count=pick.sim_count if hasattr(pick, 'sim_count') else 0,
        confluence_reasons=pick.confluence_reasons or [],

        # Grading
        result=pick.result,
        actual_value=pick.actual_value,
        units_won_lost=pick.units_won_lost,
        bet_line_at_post=pick.line_at_bet or pick.line,
        closing_line=pick.closing_line,
        clv=pick.clv,
        beat_clv=getattr(pick, 'beat_clv', None),
        process_grade=getattr(pick, 'process_grade', None),

        # Validation
        injury_status=pick.injury_status,
        book_validated=pick.book_validated,
        prop_available_at_books=getattr(pick, 'prop_available_at_books', []),
        validation_errors=pick.validation_errors or [],
        contradiction_blocked=getattr(pick, 'contradiction_blocked', False),

        # Metadata
        date=pick.date,
        run_id=pick.run_id or None,
        pick_hash=pick.pick_hash or None,
        grade_status=pick.grade_status
    )


def convert_picks_batch(picks: List) -> List[PickOutputSchema]:
    """Convert a list of PublishedPick objects to PickOutputSchema"""
    return [published_pick_to_output_schema(pick) for pick in picks]
