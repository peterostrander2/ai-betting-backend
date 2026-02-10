#!/usr/bin/env python3
"""
Training Store Audit Utility
v20.17.2: Mechanically verifiable audit of training data store.

This script reads /data/grader/predictions.jsonl and computes:
- Counts by pick_type, sport, market, grade_status
- Counts of rows missing ai_breakdown.raw_inputs.model_preds.values
- Counts of rows with model_preds.values length != required length
- Counts of rows missing result, missing grade, missing required fields
- Attribution buckets for missing model_preds (old_schema, non_game_market, error_path, unknown)
- Earliest/latest timestamp among eligible rows

Designed for:
1) Direct CLI execution: python scripts/audit_training_store.py
2) Import by training-status endpoint: from scripts.audit_training_store import audit_store
3) Fast streaming: no loading entire file into memory

Usage:
    python scripts/audit_training_store.py [--json] [--path /data/grader/predictions.jsonl]
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from collections import defaultdict

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Required model_preds length for ensemble training
REQUIRED_MODEL_PREDS_LENGTH = 4

# Markets supported for ensemble training
SUPPORTED_GAME_MARKETS = {'SPREAD', 'TOTAL', 'MONEYLINE', 'SPREADS', 'TOTALS'}

# Date when model_preds was introduced (approximate - records before this are "old_schema")
MODEL_PREDS_INTRODUCTION_DATE = "2026-02-01"


def audit_store(store_path: str = None) -> Dict[str, Any]:
    """
    Audit the training store and return mechanically verifiable counts.

    Args:
        store_path: Path to predictions.jsonl. If None, uses default Railway volume path.

    Returns:
        Dict with:
        - store_provenance: path, volume_mount, exists, mtime, line_count, size_bytes
        - counts_by_grade_status: {GRADED: N, PENDING: M, ...}
        - counts_by_pick_type: {SPREAD: N, TOTAL: M, ...}
        - counts_by_sport: {NBA: N, NCAAB: M, ...}
        - counts_by_market: {game: N, prop: M, ...}
        - missing_model_preds: total count
        - missing_model_preds_by_pick_type: {SPREAD: N, PLAYER_POINTS: M, ...}
        - missing_model_preds_by_market: {game: N, prop: M}
        - missing_model_preds_attribution: {old_schema: N, non_game_market: M, error_path: K, unknown: J}
        - insufficient_model_preds: count of rows with values length < required
        - missing_result: count
        - missing_grade_status: count
        - missing_required_fields: {home_team: N, away_team: M, ...}
        - eligible_timestamp_range: {earliest: iso, latest: iso}
        - reconciliation: {total_lines, parsed_ok, parse_errors, reconciled: bool}
    """
    volume_mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data")

    if store_path is None:
        store_path = os.path.join(volume_mount, "grader", "predictions.jsonl")

    result = {
        "store_provenance": {
            "path": store_path,
            "volume_mount_path": volume_mount,
            "exists": False,
            "mtime_iso": None,
            "line_count": 0,
            "size_bytes": 0,
            "store_schema_version": "1.0",
        },
        "counts_by_grade_status": defaultdict(int),
        "counts_by_pick_type": defaultdict(int),
        "counts_by_sport": defaultdict(int),
        "counts_by_market": defaultdict(int),
        "missing_model_preds": 0,
        "missing_model_preds_by_pick_type": defaultdict(int),
        "missing_model_preds_by_market": defaultdict(int),
        "missing_model_preds_attribution": {
            "old_schema": 0,
            "non_game_market": 0,
            "error_path": 0,
            "heuristic_fallback": 0,
            "empty_raw_inputs": 0,
            "unknown": 0,
        },
        "insufficient_model_preds": 0,
        "insufficient_model_preds_by_length": defaultdict(int),
        "missing_result": 0,
        "missing_grade_status": 0,
        "missing_required_fields": {
            "home_team": 0,
            "away_team": 0,
            "sport": 0,
            "pick_type": 0,
            "date_et": 0,
        },
        "eligible_timestamp_range": {
            "earliest": None,
            "latest": None,
        },
        "reconciliation": {
            "total_lines": 0,
            "parsed_ok": 0,
            "parse_errors": 0,
            "reconciled": False,
        },
        "audit_timestamp": datetime.now().isoformat(),
    }

    if not os.path.exists(store_path):
        result["reconciliation"]["reconciled"] = True  # Empty is consistent
        return _finalize_result(result)

    # Get file metadata
    try:
        stat = os.stat(store_path)
        result["store_provenance"]["exists"] = True
        result["store_provenance"]["size_bytes"] = stat.st_size
        result["store_provenance"]["mtime_iso"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except Exception as e:
        logger.warning(f"Failed to stat store file: {e}")

    # Stream through file
    total_lines = 0
    parsed_ok = 0
    parse_errors = 0
    earliest_ts = None
    latest_ts = None

    try:
        with open(store_path, 'r') as f:
            for line in f:
                total_lines += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    parsed_ok += 1
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue

                # Extract fields
                grade_status = record.get("grade_status", "MISSING").upper()
                pick_type = record.get("pick_type", "MISSING").upper()
                sport = record.get("sport", "MISSING").upper()
                result_field = record.get("result", "")
                date_et = record.get("date_et") or record.get("created_at", "")[:10]

                # Classify market type
                if pick_type in SUPPORTED_GAME_MARKETS:
                    market_type = "game"
                elif pick_type.startswith("PLAYER_") or "PROP" in pick_type:
                    market_type = "prop"
                else:
                    market_type = "other"

                # Count by category
                result["counts_by_grade_status"][grade_status] += 1
                result["counts_by_pick_type"][pick_type] += 1
                result["counts_by_sport"][sport] += 1
                result["counts_by_market"][market_type] += 1

                # Check missing fields
                if grade_status == "MISSING" or not record.get("grade_status"):
                    result["missing_grade_status"] += 1

                if not result_field or result_field.upper() not in ("WIN", "LOSS", "PUSH"):
                    result["missing_result"] += 1

                if not record.get("home_team"):
                    result["missing_required_fields"]["home_team"] += 1
                if not record.get("away_team"):
                    result["missing_required_fields"]["away_team"] += 1
                if not record.get("sport"):
                    result["missing_required_fields"]["sport"] += 1
                if not record.get("pick_type"):
                    result["missing_required_fields"]["pick_type"] += 1
                if not date_et:
                    result["missing_required_fields"]["date_et"] += 1

                # Check model_preds
                ai_breakdown = record.get("ai_breakdown", {})
                raw_inputs = ai_breakdown.get("raw_inputs", {})
                model_preds = raw_inputs.get("model_preds", {})
                values = model_preds.get("values", [])

                has_model_preds = bool(model_preds and "values" in model_preds)
                has_sufficient_values = len(values) >= REQUIRED_MODEL_PREDS_LENGTH

                if not has_model_preds:
                    result["missing_model_preds"] += 1
                    result["missing_model_preds_by_pick_type"][pick_type] += 1
                    result["missing_model_preds_by_market"][market_type] += 1

                    # Attribution bucket
                    attribution = _attribute_missing_model_preds(record, date_et, pick_type, market_type)
                    result["missing_model_preds_attribution"][attribution] += 1

                elif not has_sufficient_values:
                    result["insufficient_model_preds"] += 1
                    result["insufficient_model_preds_by_length"][len(values)] += 1

                # Track timestamp range for graded, eligible records
                if grade_status == "GRADED" and result_field.upper() in ("WIN", "LOSS"):
                    try:
                        record_ts = record.get("created_at") or record.get("persisted_at") or date_et
                        if record_ts:
                            if earliest_ts is None or record_ts < earliest_ts:
                                earliest_ts = record_ts
                            if latest_ts is None or record_ts > latest_ts:
                                latest_ts = record_ts
                    except Exception:
                        pass

    except Exception as e:
        logger.error(f"Failed to read store file: {e}")
        result["reconciliation"]["error"] = str(e)

    # Finalize
    result["store_provenance"]["line_count"] = total_lines
    result["reconciliation"]["total_lines"] = total_lines
    result["reconciliation"]["parsed_ok"] = parsed_ok
    result["reconciliation"]["parse_errors"] = parse_errors
    result["reconciliation"]["reconciled"] = (parsed_ok + parse_errors == total_lines)
    result["eligible_timestamp_range"]["earliest"] = earliest_ts
    result["eligible_timestamp_range"]["latest"] = latest_ts

    return _finalize_result(result)


def _attribute_missing_model_preds(record: dict, date_et: str, pick_type: str, market_type: str) -> str:
    """
    Attribute why a record is missing model_preds.

    Attribution buckets:
    - old_schema: Record predates model_preds introduction
    - non_game_market: Record is a prop/other market (not scored by game ensemble)
    - error_path: Record contains error indicators suggesting fallback/timeout
    - unknown: Cannot determine reason

    Returns bucket name.
    """
    # Check 1: Old schema (before model_preds was added)
    try:
        if date_et and date_et < MODEL_PREDS_INTRODUCTION_DATE:
            return "old_schema"
    except Exception:
        pass

    # Check 2: Non-game market (props don't go through ensemble)
    if market_type in ("prop", "other"):
        return "non_game_market"

    # Check 3: Error path indicators
    ai_breakdown = record.get("ai_breakdown", {})
    if ai_breakdown.get("error") or ai_breakdown.get("fallback"):
        return "error_path"

    # Check for timeout/error in scoring breakdown
    scoring_breakdown = record.get("scoring_breakdown", {})
    if scoring_breakdown.get("timeout") or scoring_breakdown.get("error"):
        return "error_path"

    # Check for explicit model failure indicators
    model_status = ai_breakdown.get("model_status", "")
    if model_status in ("FALLBACK", "ERROR", "TIMEOUT"):
        return "error_path"

    # Check 4: HEURISTIC_FALLBACK mode (MPS unavailable or failed)
    # When ai_mode is HEURISTIC_FALLBACK, model_preds won't be available
    ai_mode = ai_breakdown.get("ai_mode", record.get("ai_mode", ""))
    if ai_mode == "HEURISTIC_FALLBACK":
        return "heuristic_fallback"

    # Check 5: Empty raw_inputs for game market after model_preds introduction
    # This catches cases where ai_breakdown exists but raw_inputs wasn't populated
    raw_inputs = ai_breakdown.get("raw_inputs", {})
    if market_type == "game" and not raw_inputs:
        return "empty_raw_inputs"

    # Cannot determine
    return "unknown"


def _finalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert defaultdicts to regular dicts for JSON serialization."""
    result["counts_by_grade_status"] = dict(result["counts_by_grade_status"])
    result["counts_by_pick_type"] = dict(result["counts_by_pick_type"])
    result["counts_by_sport"] = dict(result["counts_by_sport"])
    result["counts_by_market"] = dict(result["counts_by_market"])
    result["missing_model_preds_by_pick_type"] = dict(result["missing_model_preds_by_pick_type"])
    result["missing_model_preds_by_market"] = dict(result["missing_model_preds_by_market"])
    result["insufficient_model_preds_by_length"] = dict(result["insufficient_model_preds_by_length"])
    return result


def get_store_audit_summary(store_path: str = None) -> Dict[str, Any]:
    """
    Get a condensed summary suitable for the training-status endpoint.

    Returns bounded output without exposing sensitive data.
    """
    full_audit = audit_store(store_path)

    return {
        "store_provenance": full_audit["store_provenance"],
        "data_quality": {
            "total_records": full_audit["reconciliation"]["parsed_ok"],
            "graded_count": full_audit["counts_by_grade_status"].get("GRADED", 0),
            "ungraded_count": sum(
                v for k, v in full_audit["counts_by_grade_status"].items()
                if k not in ("GRADED", "MISSING")
            ),
            "missing_grade_status": full_audit["missing_grade_status"],
            "missing_result": full_audit["missing_result"],
            "missing_model_preds_total": full_audit["missing_model_preds"],
            "missing_model_preds_attribution": full_audit["missing_model_preds_attribution"],
            "missing_model_preds_by_market": full_audit["missing_model_preds_by_market"],
            "insufficient_model_preds": full_audit["insufficient_model_preds"],
        },
        "distribution": {
            "by_sport": full_audit["counts_by_sport"],
            "by_market": full_audit["counts_by_market"],
            "by_pick_type_top5": dict(
                sorted(full_audit["counts_by_pick_type"].items(), key=lambda x: -x[1])[:5]
            ),
        },
        "eligible_timestamp_range": full_audit["eligible_timestamp_range"],
        "reconciliation": full_audit["reconciliation"],
        "audit_timestamp": full_audit["audit_timestamp"],
    }


def main():
    parser = argparse.ArgumentParser(description='Audit training store for mechanically verifiable counts')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--summary', action='store_true', help='Output condensed summary')
    parser.add_argument('--path', type=str, default=None, help='Path to predictions.jsonl')
    args = parser.parse_args()

    if args.summary:
        result = get_store_audit_summary(args.path)
    else:
        result = audit_store(args.path)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        # Human-readable output
        print("=" * 60)
        print("TRAINING STORE AUDIT")
        print("=" * 60)
        print(f"\nStore Path: {result.get('store_provenance', {}).get('path', 'N/A')}")
        print(f"Exists: {result.get('store_provenance', {}).get('exists', False)}")
        print(f"Size: {result.get('store_provenance', {}).get('size_bytes', 0):,} bytes")
        print(f"Line Count: {result.get('store_provenance', {}).get('line_count', 0):,}")

        recon = result.get("reconciliation", {})
        print(f"\nReconciliation: parsed={recon.get('parsed_ok', 0)}, errors={recon.get('parse_errors', 0)}, reconciled={recon.get('reconciled', False)}")

        if "data_quality" in result:
            dq = result["data_quality"]
            print(f"\nData Quality:")
            print(f"  Total Records: {dq.get('total_records', 0)}")
            print(f"  Graded: {dq.get('graded_count', 0)}")
            print(f"  Ungraded: {dq.get('ungraded_count', 0)}")
            print(f"  Missing Result: {dq.get('missing_result', 0)}")
            print(f"  Missing Model Preds: {dq.get('missing_model_preds_total', 0)}")
            print(f"    Attribution: {dq.get('missing_model_preds_attribution', {})}")
        else:
            print(f"\nCounts by Grade Status: {result.get('counts_by_grade_status', {})}")
            print(f"Counts by Sport: {result.get('counts_by_sport', {})}")
            print(f"Counts by Market: {result.get('counts_by_market', {})}")
            print(f"\nMissing Model Preds: {result.get('missing_model_preds', 0)}")
            print(f"  Attribution: {result.get('missing_model_preds_attribution', {})}")
            print(f"  By Market: {result.get('missing_model_preds_by_market', {})}")
            print(f"Insufficient Model Preds: {result.get('insufficient_model_preds', 0)}")

        ts_range = result.get("eligible_timestamp_range", {})
        print(f"\nEligible Timestamp Range:")
        print(f"  Earliest: {ts_range.get('earliest', 'N/A')}")
        print(f"  Latest: {ts_range.get('latest', 'N/A')}")

        print("\n" + "=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
