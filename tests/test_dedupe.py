"""
Tests for v15.3 pick deduplication logic.
"""
import hashlib
import pytest


# Replicate the dedupe helpers from live_data_router.py
PREFERRED_BOOKS = ["draftkings", "fanduel", "betmgm", "caesars", "pinnacle"]
SPORT = "NHL"


def _make_pick_id(p: dict) -> str:
    canonical = (
        f"{SPORT}"
        f"|{p.get('event_id', p.get('game_id', p.get('matchup', '')))}"
        f"|{p.get('market', p.get('prop_type', p.get('pick_type', '')))}"
        f"|{p.get('side', p.get('direction', p.get('pick_side', ''))).upper()}"
        f"|{round(float(p.get('line', p.get('prop_line', 0))), 2)}"
        f"|{p.get('player', p.get('player_name', ''))}"
    )
    return hashlib.sha1(canonical.encode()).hexdigest()[:12]


def _book_priority(p: dict) -> int:
    bk = (p.get("book_key") or p.get("book") or "").lower()
    try:
        return PREFERRED_BOOKS.index(bk)
    except ValueError:
        return len(PREFERRED_BOOKS)


def _dedupe_picks(picks: list) -> tuple:
    groups = {}
    for p in picks:
        pid = _make_pick_id(p)
        p["pick_id"] = pid
        groups.setdefault(pid, []).append(p)
    kept = []
    dupe_groups = []
    total_dropped = 0
    for pid, dupes in groups.items():
        dupes.sort(key=lambda x: (-x.get("total_score", 0), _book_priority(x)))
        winner = dupes[0]
        kept.append(winner)
        if len(dupes) > 1:
            total_dropped += len(dupes) - 1
            dupe_groups.append({
                "pick_id": pid,
                "count": len(dupes),
                "kept_book": winner.get("book_key", ""),
                "dropped_books": [d.get("book_key", "") for d in dupes[1:]],
            })
    return kept, total_dropped, dupe_groups


def _make_prop(player, market, line, side, score, book_key="draftkings", event_id="TeamA@TeamB"):
    return {
        "player": player,
        "market": market,
        "line": line,
        "side": side,
        "total_score": score,
        "book_key": book_key,
        "event_id": event_id,
    }


def test_exact_duplicates_reduced():
    """Identical bets from same book should dedupe to 1."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 8.0),
        _make_prop("Player A", "points", 25.5, "Over", 8.0),
        _make_prop("Player A", "points", 25.5, "Over", 8.0),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 1
    assert dropped == 2


def test_different_books_keep_highest_score():
    """Same bet from 3 books → keep highest score."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 7.5, "betmgm"),
        _make_prop("Player A", "points", 25.5, "Over", 8.2, "fanduel"),
        _make_prop("Player A", "points", 25.5, "Over", 7.9, "draftkings"),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 1
    assert dropped == 2
    assert kept[0]["total_score"] == 8.2
    assert kept[0]["book_key"] == "fanduel"


def test_tied_score_prefers_book_priority():
    """Same score → prefer draftkings > fanduel > betmgm."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 8.0, "betmgm"),
        _make_prop("Player A", "points", 25.5, "Over", 8.0, "draftkings"),
        _make_prop("Player A", "points", 25.5, "Over", 8.0, "fanduel"),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 1
    assert kept[0]["book_key"] == "draftkings"


def test_different_sides_not_deduped():
    """Over and Under for same player/market are different bets."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 8.0),
        _make_prop("Player A", "points", 25.5, "Under", 7.5),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 2
    assert dropped == 0


def test_different_lines_not_deduped():
    """Same player/market but different lines are different bets."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 8.0),
        _make_prop("Player A", "points", 26.5, "Over", 7.5),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 2
    assert dropped == 0


def test_different_players_not_deduped():
    """Different players are never deduped."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 8.0),
        _make_prop("Player B", "points", 25.5, "Over", 7.5),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 2


def test_different_events_not_deduped():
    """Same player in different games are different bets."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 8.0, event_id="Game1"),
        _make_prop("Player A", "points", 25.5, "Over", 7.5, event_id="Game2"),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 2


def test_pick_id_stable():
    """Same input always produces the same pick_id."""
    p1 = _make_prop("Player A", "points", 25.5, "Over", 8.0)
    p2 = _make_prop("Player A", "points", 25.5, "Over", 7.0)
    id1 = _make_pick_id(p1)
    id2 = _make_pick_id(p2)
    assert id1 == id2  # Same bet semantics, different score → same pick_id


def test_dupe_groups_reported():
    """Debug output should report which dupes were dropped."""
    picks = [
        _make_prop("Player A", "points", 25.5, "Over", 8.0, "draftkings"),
        _make_prop("Player A", "points", 25.5, "Over", 7.0, "fanduel"),
        _make_prop("Player A", "points", 25.5, "Over", 6.5, "betmgm"),
        _make_prop("Player B", "assists", 5.5, "Over", 7.0, "draftkings"),
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 2
    assert dropped == 2
    assert len(groups) == 1
    assert groups[0]["count"] == 3
    assert groups[0]["kept_book"] == "draftkings"
    assert "fanduel" in groups[0]["dropped_books"]
    assert "betmgm" in groups[0]["dropped_books"]


def test_empty_input():
    """Empty list should return empty."""
    kept, dropped, groups = _dedupe_picks([])
    assert kept == []
    assert dropped == 0
    assert groups == []


def test_game_picks_dedupe():
    """Game picks (no player field) should dedupe by matchup+market+side."""
    picks = [
        {"event_id": "TeamA@TeamB", "market": "spreads", "side": "Home", "line": -1.5,
         "total_score": 7.5, "book_key": "draftkings", "player": ""},
        {"event_id": "TeamA@TeamB", "market": "spreads", "side": "Home", "line": -1.5,
         "total_score": 7.2, "book_key": "fanduel", "player": ""},
    ]
    kept, dropped, groups = _dedupe_picks(picks)
    assert len(kept) == 1
    assert dropped == 1
    assert kept[0]["book_key"] == "draftkings"


def test_float_line_normalization():
    """Lines 25.50 and 25.5 should be treated as the same."""
    p1 = _make_prop("Player A", "points", 25.50, "Over", 8.0)
    p2 = _make_prop("Player A", "points", 25.5, "Over", 7.0)
    assert _make_pick_id(p1) == _make_pick_id(p2)
