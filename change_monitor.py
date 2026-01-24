"""
Change Monitor v10.73
=====================
Tracks changes between pull snapshots for community alerts.

Diff rules:
- Odds change >= 15 cents → ODDS_MOVE
- Line change >= 0.5 spread/total → LINE_MOVE
- Props disappear → PROP_REMOVED
- Injury flips OUT/DOUBTFUL → INJURY_FLIP
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "./pull_snapshots"


class ChangeType(str, Enum):
    ODDS_MOVE = "ODDS_MOVE"        # Odds changed >= 15 cents
    LINE_MOVE = "LINE_MOVE"        # Spread/total moved >= 0.5
    PROP_REMOVED = "PROP_REMOVED"  # Prop no longer available
    PROP_ADDED = "PROP_ADDED"      # New prop appeared
    INJURY_FLIP = "INJURY_FLIP"    # Injury status changed
    TIER_CHANGE = "TIER_CHANGE"    # Pick tier upgraded/downgraded
    PICK_REMOVED = "PICK_REMOVED"  # Pick no longer qualifies
    PICK_ADDED = "PICK_ADDED"      # New pick qualified
    # NHL-specific
    PROP_LINE_MOVE = "PROP_LINE_MOVE"      # NHL prop line moved >= 0.5 (shots/goals/points/saves)
    GOALIE_STATUS_CHANGE = "GOALIE_STATUS_CHANGE"  # NHL goalie starter confirmed/changed


@dataclass
class Change:
    """A detected change between snapshots."""
    change_type: ChangeType
    pick_id: str
    description: str
    old_value: str
    new_value: str
    severity: str  # "info", "warning", "alert"
    detected_at: str = ""

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "change_type": self.change_type.value,
            "pick_id": self.pick_id,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "severity": self.severity,
            "detected_at": self.detected_at
        }


@dataclass
class ChangeReport:
    """Summary of all changes between snapshots."""
    sport: str
    old_snapshot_time: str
    new_snapshot_time: str
    changes: List[Change]
    alerts_count: int = 0
    warnings_count: int = 0

    def to_dict(self) -> dict:
        return {
            "sport": self.sport,
            "old_snapshot_time": self.old_snapshot_time,
            "new_snapshot_time": self.new_snapshot_time,
            "changes": [c.to_dict() for c in self.changes],
            "total_changes": len(self.changes),
            "alerts_count": self.alerts_count,
            "warnings_count": self.warnings_count,
            "has_alerts": self.alerts_count > 0
        }


def ensure_snapshot_dir():
    """Create snapshot directory if it doesn't exist."""
    if not os.path.exists(SNAPSHOT_DIR):
        os.makedirs(SNAPSHOT_DIR)


def get_snapshot_path(sport: str) -> str:
    """Get path to latest snapshot for a sport."""
    return os.path.join(SNAPSHOT_DIR, f"{sport.lower()}_latest.json")


def save_snapshot(sport: str, picks: List[Dict], metadata: Dict = None) -> str:
    """
    Save a pull snapshot for later comparison.

    Returns the snapshot path.
    """
    ensure_snapshot_dir()

    snapshot = {
        "sport": sport.upper(),
        "timestamp": datetime.now().isoformat(),
        "picks_count": len(picks),
        "picks": picks,
        "metadata": metadata or {}
    }

    path = get_snapshot_path(sport)

    # Archive previous snapshot
    if os.path.exists(path):
        archive_path = path.replace("_latest.json", f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            os.rename(path, archive_path)
        except:
            pass

    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2)

    logger.info(f"Saved snapshot for {sport}: {len(picks)} picks")
    return path


def load_snapshot(sport: str) -> Optional[Dict]:
    """Load the latest snapshot for a sport."""
    path = get_snapshot_path(sport)

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load snapshot: {e}")
        return None


def generate_pick_id(pick: Dict) -> str:
    """Generate a unique ID for a pick for comparison."""
    # For props
    if pick.get("player_name") or pick.get("selection_name"):
        player = pick.get("player_name") or pick.get("selection_name") or ""
        stat = pick.get("stat_type") or pick.get("selection_detail") or ""
        game = pick.get("game") or ""
        return f"{player}:{stat}:{game}".lower().replace(" ", "_")

    # For game picks
    game = pick.get("game") or ""
    market = pick.get("market_type") or pick.get("pick_type") or ""
    return f"{game}:{market}".lower().replace(" ", "_")


def compare_odds(old_odds: int, new_odds: int) -> Optional[Change]:
    """Check if odds changed significantly (>= 15 cents)."""
    # Convert American odds to implied probability for comparison
    def to_prob(odds):
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)

    old_prob = to_prob(old_odds)
    new_prob = to_prob(new_odds)

    # 15 cents is roughly 1.5% probability change
    if abs(old_prob - new_prob) >= 0.015:
        severity = "alert" if abs(old_prob - new_prob) >= 0.03 else "warning"
        return Change(
            change_type=ChangeType.ODDS_MOVE,
            pick_id="",  # Will be set by caller
            description=f"Odds moved from {old_odds} to {new_odds}",
            old_value=str(old_odds),
            new_value=str(new_odds),
            severity=severity
        )
    return None


def compare_line(old_line: float, new_line: float, line_type: str) -> Optional[Change]:
    """Check if spread/total moved >= 0.5."""
    diff = abs(old_line - new_line)

    if diff >= 0.5:
        severity = "alert" if diff >= 1.0 else "warning"
        return Change(
            change_type=ChangeType.LINE_MOVE,
            pick_id="",
            description=f"{line_type} moved from {old_line} to {new_line}",
            old_value=str(old_line),
            new_value=str(new_line),
            severity=severity
        )
    return None


def compare_tier(old_tier: str, new_tier: str) -> Optional[Change]:
    """Check if tier changed."""
    if old_tier != new_tier:
        tier_ranks = {"GOLD_STAR": 4, "EDGE_LEAN": 3, "MONITOR": 2, "PASS": 1}
        old_rank = tier_ranks.get(old_tier, 0)
        new_rank = tier_ranks.get(new_tier, 0)

        if new_rank > old_rank:
            desc = f"Upgraded from {old_tier} to {new_tier}"
            severity = "info"
        else:
            desc = f"Downgraded from {old_tier} to {new_tier}"
            severity = "warning"

        return Change(
            change_type=ChangeType.TIER_CHANGE,
            pick_id="",
            description=desc,
            old_value=old_tier,
            new_value=new_tier,
            severity=severity
        )
    return None


def compare_nhl_prop_line(old_line: float, new_line: float, prop_type: str) -> Optional[Change]:
    """
    Check if NHL prop line moved >= 0.5.

    NHL props: shots_on_goal, goals, points, assists, saves
    """
    diff = abs(old_line - new_line)

    if diff >= 0.5:
        severity = "alert" if diff >= 1.0 else "warning"
        return Change(
            change_type=ChangeType.PROP_LINE_MOVE,
            pick_id="",
            description=f"NHL {prop_type} line moved from {old_line} to {new_line}",
            old_value=str(old_line),
            new_value=str(new_line),
            severity=severity
        )
    return None


def check_goalie_status_change(old_pick: Dict, new_pick: Dict) -> Optional[Change]:
    """
    Check if NHL goalie starter status changed.
    """
    old_goalie = old_pick.get("goalie_starter") or old_pick.get("starter")
    new_goalie = new_pick.get("goalie_starter") or new_pick.get("starter")

    if old_goalie and new_goalie and old_goalie != new_goalie:
        return Change(
            change_type=ChangeType.GOALIE_STATUS_CHANGE,
            pick_id="",
            description=f"Goalie changed from {old_goalie} to {new_goalie}",
            old_value=str(old_goalie),
            new_value=str(new_goalie),
            severity="alert"
        )
    return None


# NHL prop types that should use prop line comparison
NHL_PROP_TYPES = [
    "player_shots_on_goal", "player_goals", "player_points",
    "player_assists", "goalie_saves", "player_blocked_shots",
    "player_power_play_points", "shots_on_goal", "goals", "points", "saves"
]


def diff_snapshots(old_snapshot: Dict, new_picks: List[Dict], sport: str) -> ChangeReport:
    """
    Compare old snapshot with new picks and detect changes.
    """
    changes: List[Change] = []

    old_picks = old_snapshot.get("picks", [])
    old_by_id = {generate_pick_id(p): p for p in old_picks}
    new_by_id = {generate_pick_id(p): p for p in new_picks}

    old_ids = set(old_by_id.keys())
    new_ids = set(new_by_id.keys())

    # Check for removed picks
    for pick_id in old_ids - new_ids:
        old_pick = old_by_id[pick_id]
        changes.append(Change(
            change_type=ChangeType.PICK_REMOVED,
            pick_id=pick_id,
            description=f"Pick no longer qualifies: {pick_id}",
            old_value=old_pick.get("tier", ""),
            new_value="REMOVED",
            severity="warning"
        ))

    # Check for new picks
    for pick_id in new_ids - old_ids:
        new_pick = new_by_id[pick_id]
        changes.append(Change(
            change_type=ChangeType.PICK_ADDED,
            pick_id=pick_id,
            description=f"New pick qualified: {pick_id}",
            old_value="",
            new_value=new_pick.get("tier", ""),
            severity="info"
        ))

    # Check for changes in existing picks
    for pick_id in old_ids & new_ids:
        old_pick = old_by_id[pick_id]
        new_pick = new_by_id[pick_id]

        # Odds change
        old_odds = old_pick.get("odds") or old_pick.get("odds_display")
        new_odds = new_pick.get("odds") or new_pick.get("odds_display")
        if old_odds and new_odds:
            try:
                old_odds_int = int(str(old_odds).replace("+", ""))
                new_odds_int = int(str(new_odds).replace("+", ""))
                odds_change = compare_odds(old_odds_int, new_odds_int)
                if odds_change:
                    odds_change.pick_id = pick_id
                    changes.append(odds_change)
            except:
                pass

        # Tier change
        old_tier = old_pick.get("tier", "")
        new_tier = new_pick.get("tier", "")
        tier_change = compare_tier(old_tier, new_tier)
        if tier_change:
            tier_change.pick_id = pick_id
            changes.append(tier_change)

        # Line change (for spreads/totals)
        old_line = old_pick.get("spread") or old_pick.get("line")
        new_line = new_pick.get("spread") or new_pick.get("line")
        if old_line is not None and new_line is not None:
            try:
                line_change = compare_line(float(old_line), float(new_line), "Line")
                if line_change:
                    line_change.pick_id = pick_id
                    changes.append(line_change)
            except:
                pass

        # NHL-specific: Prop line changes for shots/goals/points/saves
        if sport.lower() == "nhl":
            prop_type = old_pick.get("stat_type") or old_pick.get("prop_type") or ""
            if prop_type.lower() in [p.lower() for p in NHL_PROP_TYPES]:
                old_prop_line = old_pick.get("line") or old_pick.get("point")
                new_prop_line = new_pick.get("line") or new_pick.get("point")
                if old_prop_line is not None and new_prop_line is not None:
                    try:
                        prop_change = compare_nhl_prop_line(
                            float(old_prop_line), float(new_prop_line), prop_type
                        )
                        if prop_change:
                            prop_change.pick_id = pick_id
                            changes.append(prop_change)
                    except:
                        pass

            # NHL-specific: Goalie status change
            goalie_change = check_goalie_status_change(old_pick, new_pick)
            if goalie_change:
                goalie_change.pick_id = pick_id
                changes.append(goalie_change)

    # Count by severity
    alerts_count = sum(1 for c in changes if c.severity == "alert")
    warnings_count = sum(1 for c in changes if c.severity == "warning")

    return ChangeReport(
        sport=sport.upper(),
        old_snapshot_time=old_snapshot.get("timestamp", ""),
        new_snapshot_time=datetime.now().isoformat(),
        changes=changes,
        alerts_count=alerts_count,
        warnings_count=warnings_count
    )


def check_for_changes(sport: str, new_picks: List[Dict]) -> Optional[ChangeReport]:
    """
    Compare new picks against last snapshot and return changes.

    Returns None if no previous snapshot exists.
    """
    old_snapshot = load_snapshot(sport)

    if old_snapshot is None:
        logger.info(f"No previous snapshot for {sport}, saving first snapshot")
        save_snapshot(sport, new_picks)
        return None

    report = diff_snapshots(old_snapshot, new_picks, sport)

    # Save new snapshot
    save_snapshot(sport, new_picks)

    return report


def get_change_summary(report: ChangeReport) -> str:
    """Generate a human-readable change summary."""
    if not report.changes:
        return f"No changes detected for {report.sport}"

    lines = [f"📊 {report.sport} Changes Detected:"]

    if report.alerts_count > 0:
        lines.append(f"🚨 {report.alerts_count} alerts")

    if report.warnings_count > 0:
        lines.append(f"⚠️ {report.warnings_count} warnings")

    for change in report.changes[:10]:  # Limit to 10
        emoji = "🚨" if change.severity == "alert" else "⚠️" if change.severity == "warning" else "ℹ️"
        lines.append(f"{emoji} {change.description}")

    if len(report.changes) > 10:
        lines.append(f"... and {len(report.changes) - 10} more changes")

    return "\n".join(lines)
