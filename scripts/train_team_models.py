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


def load_graded_picks(days: int = 7, sport: str = None) -> list:
    """Load recently graded picks from storage."""
    try:
        from grader_store import load_predictions

        picks = load_predictions()

        # Filter to recent days
        cutoff = datetime.now() - timedelta(days=days)

        graded_picks = []
        for pick in picks:
            # Check if graded
            if pick.get('grade_status') not in ['GRADED', 'graded']:
                continue
            if pick.get('result') not in ['WIN', 'LOSS', 'win', 'loss']:
                continue

            # Check date
            pick_date_str = pick.get('date_et') or pick.get('created_at', '')[:10]
            try:
                pick_date = datetime.strptime(pick_date_str, '%Y-%m-%d')
                if pick_date < cutoff:
                    continue
            except:
                continue

            # Check sport filter
            if sport and pick.get('sport', '').upper() != sport.upper():
                continue

            graded_picks.append(pick)

        logger.info(f"Loaded {len(graded_picks)} graded picks from last {days} days")
        return graded_picks

    except Exception as e:
        logger.error(f"Failed to load graded picks: {e}")
        return []


def update_team_cache(picks: list):
    """Update team scoring cache from graded game picks."""
    from team_ml_models import get_team_cache

    cache = get_team_cache()
    updated = 0

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
    return updated


def update_matchup_matrix(picks: list):
    """Update matchup matrix from graded game picks."""
    from team_ml_models import get_team_matchup

    matchup = get_team_matchup()
    updated = 0

    for pick in picks:
        pick_type = pick.get('pick_type', '').upper()
        if pick_type not in ['SPREAD', 'TOTAL', 'MONEYLINE', 'SPREADS', 'TOTALS']:
            continue

        sport = pick.get('sport', 'NBA')
        home_team = pick.get('home_team', '')
        away_team = pick.get('away_team', '')

        if not home_team or not away_team:
            continue

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
    return updated


def update_ensemble_weights(picks: list):
    """Update ensemble weights from graded picks."""
    from team_ml_models import get_game_ensemble

    ensemble = get_game_ensemble()
    updated = 0

    for pick in picks:
        # Get the model predictions that were made
        ai_breakdown = pick.get('ai_breakdown', {})
        model_preds = ai_breakdown.get('raw_inputs', {}).get('model_preds', {})

        if not model_preds or 'values' not in model_preds:
            continue

        # Extract individual model predictions
        values = model_preds.get('values', [])
        if len(values) < 4:
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
            continue

        # Update ensemble weights
        ensemble.update_weights(predictions, actual)
        updated += 1

    # Save weights
    ensemble._save_weights()
    logger.info(f"Updated ensemble weights with {updated} pick outcomes")
    return updated


def train_all(days: int = 7, sport: str = None):
    """Run all training updates."""
    logger.info("=" * 60)
    logger.info("TEAM MODEL TRAINING - v20.16")
    logger.info("=" * 60)

    # Load graded picks
    picks = load_graded_picks(days=days, sport=sport)

    if not picks:
        logger.warning("No graded picks found to train on")
        return {
            'status': 'NO_DATA',
            'picks_found': 0
        }

    # Update all models
    results = {
        'status': 'SUCCESS',
        'picks_found': len(picks),
        'team_cache_updates': update_team_cache(picks),
        'matchup_updates': update_matchup_matrix(picks),
        'ensemble_updates': update_ensemble_weights(picks),
    }

    # Log summary
    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info(f"  Picks processed: {len(picks)}")
    logger.info(f"  Team cache updates: {results['team_cache_updates']}")
    logger.info(f"  Matchup updates: {results['matchup_updates']}")
    logger.info(f"  Ensemble updates: {results['ensemble_updates']}")
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
