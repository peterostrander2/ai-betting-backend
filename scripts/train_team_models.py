#!/usr/bin/env python3
"""
Team Model Training Script
v20.16: Trains LSTM, Matchup, and Ensemble models from graded picks

This script:
1. Loads graded picks from /data/grader/predictions.jsonl
2. Updates team scoring cache (for LSTM)
3. Updates matchup matrix (for Matchup model)
4. Updates ensemble weights (learns what works)

Run daily after grading to make models grow stronger over time.

Usage:
    python scripts/train_team_models.py [--days 7] [--sport NBA]
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_graded_picks(days: int = 7, sport: str = None) -> tuple:
    """Load recently graded picks from storage with mechanically checkable filter telemetry.

    Returns:
        tuple: (graded_picks, filter_telemetry) where filter_telemetry is a dict with:
            Summable counts (mutually exclusive, sum to graded_loaded_total):
            - graded_loaded_total: Total picks loaded from storage
            - drop_no_grade: Missing grade_status (not GRADED)
            - drop_no_result: Missing result (not WIN/LOSS)
            - drop_wrong_market: Wrong pick_type for model (not game picks)
            - drop_missing_required_fields: Missing home_team/away_team
            - drop_outside_time_window: Outside the date range
            - drop_wrong_sport: Filtered by sport parameter
            - eligible_total: Passed all filters
            - used_for_training_total: Actually used (may differ from eligible)

            Assertions (verified in-code):
            - eligible_total + sum(drops) == graded_loaded_total
            - used_for_training_total <= eligible_total

            Audit trail:
            - sample_pick_ids: First 10 pick IDs used
            - filter_version: Schema version for tracking changes
    """
    telemetry = {
        'graded_loaded_total': 0,
        'drop_no_grade': 0,
        'drop_no_result': 0,
        'drop_wrong_market': 0,
        'drop_missing_required_fields': 0,
        'drop_outside_time_window': 0,
        'drop_wrong_sport': 0,
        'eligible_total': 0,
        'used_for_training_total': 0,
        'sample_pick_ids': [],
        'filter_version': '2.0',  # Bump when filter logic changes
        'assertion_passed': False,
    }

    try:
        from grader_store import load_predictions

        picks = load_predictions()
        telemetry['graded_loaded_total'] = len(picks)

        # Filter to recent days
        cutoff = datetime.now() - timedelta(days=days)

        graded_picks = []
        for pick in picks:
            # Check 1: grade_status present
            if pick.get('grade_status') not in ['GRADED', 'graded']:
                telemetry['drop_no_grade'] += 1
                continue

            # Check 2: result present (separate from grade_status)
            if pick.get('result') not in ['WIN', 'LOSS', 'win', 'loss']:
                telemetry['drop_no_result'] += 1
                continue

            # Check 3: pick_type is game pick (not prop)
            pick_type = pick.get('pick_type', '').upper()
            if pick_type not in ['SPREAD', 'TOTAL', 'MONEYLINE', 'SPREADS', 'TOTALS']:
                telemetry['drop_wrong_market'] += 1
                continue

            # Check 4: required fields present
            if not pick.get('home_team') or not pick.get('away_team'):
                telemetry['drop_missing_required_fields'] += 1
                continue

            # Check 5: date within window
            pick_date_str = pick.get('date_et') or pick.get('created_at', '')[:10]
            try:
                pick_date = datetime.strptime(pick_date_str, '%Y-%m-%d')
                if pick_date < cutoff:
                    telemetry['drop_outside_time_window'] += 1
                    continue
            except:
                telemetry['drop_outside_time_window'] += 1
                continue

            # Check 6: sport filter (optional)
            if sport and pick.get('sport', '').upper() != sport.upper():
                telemetry['drop_wrong_sport'] += 1
                continue

            graded_picks.append(pick)

        telemetry['eligible_total'] = len(graded_picks)
        telemetry['used_for_training_total'] = len(graded_picks)
        telemetry['sample_pick_ids'] = [
            p.get('pick_id', p.get('prediction_id', 'unknown'))[:12]
            for p in graded_picks[:10]
        ]

        # HARD ASSERTION: Verify filter math is correct
        sum_of_drops = (
            telemetry['drop_no_grade'] +
            telemetry['drop_no_result'] +
            telemetry['drop_wrong_market'] +
            telemetry['drop_missing_required_fields'] +
            telemetry['drop_outside_time_window'] +
            telemetry['drop_wrong_sport']
        )
        expected_total = telemetry['eligible_total'] + sum_of_drops

        if expected_total != telemetry['graded_loaded_total']:
            logger.error(
                f"FILTER MATH BUG: eligible({telemetry['eligible_total']}) + "
                f"drops({sum_of_drops}) = {expected_total} != loaded({telemetry['graded_loaded_total']})"
            )
            telemetry['assertion_passed'] = False
            telemetry['assertion_error'] = f"sum mismatch: {expected_total} != {telemetry['graded_loaded_total']}"
        elif telemetry['used_for_training_total'] > telemetry['eligible_total']:
            logger.error(
                f"FILTER MATH BUG: used({telemetry['used_for_training_total']}) > "
                f"eligible({telemetry['eligible_total']})"
            )
            telemetry['assertion_passed'] = False
            telemetry['assertion_error'] = "used > eligible"
        else:
            telemetry['assertion_passed'] = True
            logger.info(
                f"Filter assertion PASSED: {telemetry['eligible_total']} + {sum_of_drops} = "
                f"{telemetry['graded_loaded_total']}"
            )

        logger.info(
            f"Training filter telemetry v{telemetry['filter_version']}: "
            f"loaded={telemetry['graded_loaded_total']}, "
            f"drops=[grade:{telemetry['drop_no_grade']}, result:{telemetry['drop_no_result']}, "
            f"market:{telemetry['drop_wrong_market']}, fields:{telemetry['drop_missing_required_fields']}, "
            f"window:{telemetry['drop_outside_time_window']}, sport:{telemetry['drop_wrong_sport']}], "
            f"eligible={telemetry['eligible_total']}, used={telemetry['used_for_training_total']}"
        )
        return graded_picks, telemetry

    except Exception as e:
        logger.error(f"Failed to load graded picks: {e}")
        return [], telemetry


def _compute_schema_hash(feature_names: list) -> str:
    """Compute a hash of ordered feature names for train/inference consistency check."""
    import hashlib
    schema_str = '|'.join(sorted(feature_names))
    return hashlib.sha256(schema_str.encode()).hexdigest()[:16]


def update_team_cache(picks: list) -> dict:
    """Update team scoring cache from graded game picks.

    Returns training signature for audit.
    """
    from team_ml_models import get_team_cache

    cache = get_team_cache()
    updated = 0
    teams_seen = set()
    sports_seen = set()

    for pick in picks:
        # Only process game picks (spreads, totals, moneyline)
        pick_type = pick.get('pick_type', '').upper()
        if pick_type not in ['SPREAD', 'TOTAL', 'MONEYLINE', 'SPREADS', 'TOTALS']:
            continue

        sport = pick.get('sport', 'NBA')
        home_team = pick.get('home_team', '')
        away_team = pick.get('away_team', '')

        if not home_team or not away_team:
            continue

        sports_seen.add(sport)
        teams_seen.add(f"{sport}_{home_team}")
        teams_seen.add(f"{sport}_{away_team}")

        # Try to extract actual scores from the pick
        home_score = pick.get('home_score') or pick.get('actual_home_score')
        away_score = pick.get('away_score') or pick.get('actual_away_score')

        # If we don't have scores, estimate from line and result
        if home_score is None or away_score is None:
            line = pick.get('line', 0)
            result = pick.get('result', '').upper()

            # Rough estimation based on typical game scores
            base_score = 105 if sport == 'NBA' else 100
            margin = abs(line) if line else 5

            if result == 'WIN':
                # Pick was right - assume margin was covered
                home_score = base_score + margin / 2
                away_score = base_score - margin / 2
            else:
                # Pick was wrong
                home_score = base_score - margin / 2
                away_score = base_score + margin / 2

        # Update cache
        cache.update_team(sport, home_team, {
            'score': home_score,
            'is_home': True,
            'won': home_score > away_score
        })
        cache.update_team(sport, away_team, {
            'score': away_score,
            'is_home': False,
            'won': away_score > home_score
        })
        updated += 1

    # Save cache
    cache._save_cache()
    logger.info(f"Updated team cache with {updated} game results")

    # Compute training signature
    all_teams = cache.data.get("teams", {})
    games_per_team = [len(t.get("recent_scores", [])) for t in all_teams.values()]

    return {
        'games_processed': updated,
        'teams_updated_this_run': len(teams_seen),
        'sports_included': sorted(list(sports_seen)),
        'teams_cached_total': len(all_teams),
        'games_per_team_avg': round(sum(games_per_team) / len(games_per_team), 2) if games_per_team else 0,
        'feature_schema_hash': _compute_schema_hash(['score', 'is_home', 'won']),
    }


def update_matchup_matrix(picks: list) -> dict:
    """Update matchup matrix from graded game picks.

    Returns training signature for audit.
    """
    from team_ml_models import get_team_matchup

    matchup = get_team_matchup()
    updated = 0
    sports_seen = set()

    for pick in picks:
        pick_type = pick.get('pick_type', '').upper()
        if pick_type not in ['SPREAD', 'TOTAL', 'MONEYLINE', 'SPREADS', 'TOTALS']:
            continue

        sport = pick.get('sport', 'NBA')
        home_team = pick.get('home_team', '')
        away_team = pick.get('away_team', '')

        if not home_team or not away_team:
            continue

        sports_seen.add(sport)

        # Get or estimate scores
        home_score = pick.get('home_score') or pick.get('actual_home_score')
        away_score = pick.get('away_score') or pick.get('actual_away_score')

        if home_score is None or away_score is None:
            # Estimate from line
            line = pick.get('line', 0)
            base = 105 if sport == 'NBA' else 100
            home_score = base + line / 2 if line else base + 3
            away_score = base - line / 2 if line else base - 3

        matchup.record_matchup(sport, home_team, away_team, home_score, away_score)
        updated += 1

    # Save matchups
    matchup._save_matchups()
    logger.info(f"Updated matchup matrix with {updated} game results")

    # Compute training signature
    all_matchups = matchup.matchups
    games_per_matchup = [len(m.get("games", [])) for m in all_matchups.values()]

    return {
        'games_processed': updated,
        'sports_included': sorted(list(sports_seen)),
        'matchups_tracked_total': len(all_matchups),
        'games_per_matchup_avg': round(sum(games_per_matchup) / len(games_per_matchup), 2) if games_per_matchup else 0,
        'feature_schema_hash': _compute_schema_hash(['home', 'away', 'home_score', 'away_score', 'date']),
    }


def update_ensemble_weights(picks: list) -> dict:
    """Update ensemble weights from graded picks.

    Returns training signature for audit.
    """
    from team_ml_models import get_game_ensemble

    ensemble = get_game_ensemble()
    updated = 0
    sports_seen = set()
    markets_seen = set()
    skip_no_model_preds = 0
    skip_insufficient_values = 0
    skip_no_result = 0

    # Define feature schema for training (what we train on)
    training_features = ['ensemble', 'lstm', 'matchup', 'monte_carlo']

    for pick in picks:
        # Get the model predictions that were made
        ai_breakdown = pick.get('ai_breakdown', {})
        model_preds = ai_breakdown.get('raw_inputs', {}).get('model_preds', {})

        if not model_preds or 'values' not in model_preds:
            skip_no_model_preds += 1
            continue

        # Extract individual model predictions
        values = model_preds.get('values', [])
        if len(values) < 4:
            skip_insufficient_values += 1
            continue

        predictions = {
            'ensemble': values[0] if len(values) > 0 else None,
            'lstm': values[1] if len(values) > 1 else None,
            'matchup': values[2] if len(values) > 2 else None,
            'monte_carlo': values[3] if len(values) > 3 else None,
        }

        # Get actual outcome
        result = pick.get('result', '').upper()
        line = pick.get('line', 0)

        # Determine actual value based on result
        # For now, use a simple approach: WIN means prediction was right direction
        if result == 'WIN':
            actual = line + 5  # We beat the line
        elif result == 'LOSS':
            actual = line - 5  # We didn't beat the line
        else:
            skip_no_result += 1
            continue

        sports_seen.add(pick.get('sport', 'UNKNOWN'))
        markets_seen.add(pick.get('pick_type', 'UNKNOWN').upper())

        # Update ensemble weights
        ensemble.update_weights(predictions, actual)
        updated += 1

    # Save weights
    ensemble._save_weights()
    logger.info(f"Updated ensemble weights with {updated} pick outcomes")

    # Compute training signature
    return {
        'samples_used': updated,
        'samples_skipped': {
            'no_model_preds': skip_no_model_preds,
            'insufficient_values': skip_insufficient_values,
            'no_result': skip_no_result,
        },
        'sports_included': sorted(list(sports_seen)),
        'markets_included': sorted(list(markets_seen)),
        # Feature schema hash - must match inference schema
        'training_feature_schema': training_features,
        'training_feature_schema_hash': _compute_schema_hash(training_features),
        # Label definition - what counts as "hit"
        'label_definition': 'WIN: actual = line + 5; LOSS: actual = line - 5',
        'label_type': 'regression_target',
        # Current weights after training
        'weights_after': {k: round(v, 4) for k, v in ensemble.weights.items() if not k.startswith("_")},
        'total_samples_trained': ensemble.weights.get("_trained_samples", 0),
    }


def train_all(days: int = 7, sport: str = None):
    """Run all training updates with mechanically checkable telemetry."""
    logger.info("=" * 60)
    logger.info("TEAM MODEL TRAINING - v20.17.0")
    logger.info("=" * 60)

    # Load graded picks with filter telemetry
    picks, filter_telemetry = load_graded_picks(days=days, sport=sport)

    if not picks:
        logger.warning("No graded picks found to train on")
        return {
            'status': 'NO_DATA',
            'picks_found': 0,
            'filter_telemetry': filter_telemetry
        }

    # Update all models - now return training signatures
    team_cache_sig = update_team_cache(picks)
    matchup_sig = update_matchup_matrix(picks)
    ensemble_sig = update_ensemble_weights(picks)

    results = {
        'status': 'SUCCESS',
        'picks_found': len(picks),
        'filter_telemetry': filter_telemetry,
        'training_signatures': {
            'team_cache': team_cache_sig,
            'matchup_matrix': matchup_sig,
            'ensemble': ensemble_sig,
        },
    }

    # Record training run with full telemetry (proves pipeline executed)
    try:
        from team_ml_models import get_game_ensemble
        ensemble = get_game_ensemble()
        ensemble.record_training_run(
            graded_samples_seen=filter_telemetry['graded_loaded_total'],
            samples_used=ensemble_sig['samples_used'],
            filter_telemetry=filter_telemetry,
            training_signatures=results['training_signatures']
        )
        results['telemetry_recorded'] = True
    except Exception as e:
        logger.error(f"Failed to record training telemetry: {e}")
        results['telemetry_recorded'] = False

    # Log summary with training signatures
    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info(f"  Filter assertion: {'PASSED' if filter_telemetry.get('assertion_passed') else 'FAILED'}")
    logger.info(f"  Team cache: {team_cache_sig['games_processed']} games, {team_cache_sig['teams_cached_total']} teams")
    logger.info(f"  Matchup matrix: {matchup_sig['games_processed']} games, {matchup_sig['matchups_tracked_total']} matchups")
    logger.info(f"  Ensemble: {ensemble_sig['samples_used']} samples, schema={ensemble_sig['training_feature_schema_hash']}")
    logger.info(f"  Telemetry recorded: {results.get('telemetry_recorded', False)}")
    logger.info("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(description='Train team ML models from graded picks')
    parser.add_argument('--days', type=int, default=7, help='Days of history to process')
    parser.add_argument('--sport', type=str, default=None, help='Filter to specific sport')
    args = parser.parse_args()

    results = train_all(days=args.days, sport=args.sport)

    # Print results as JSON for scripting
    print(json.dumps(results, indent=2))

    return 0 if results['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())
