"""
Unit tests for best-bets response contract (FIX 1)

GUARANTEES: props, games, meta keys ALWAYS present (no KeyError possible)
"""

import pytest
from models.best_bets_response import build_best_bets_response


def test_empty_response_has_all_keys():
    """Empty response must have props, games, meta keys"""
    response = build_best_bets_response(
        sport="NHL",
        props_picks=[],
        game_picks=[],
        total_props_analyzed=0,
        total_games_analyzed=0
    )

    # REQUIRED KEYS (FIX 1)
    assert "props" in response, "props key missing"
    assert "games" in response, "games key missing"
    assert "meta" in response, "meta key missing"

    # Verify structure
    assert response["props"]["count"] == 0
    assert response["props"]["picks"] == []
    assert response["games"]["count"] == 0
    assert response["games"]["picks"] == []
    assert isinstance(response["meta"], dict)


def test_response_with_props_only():
    """Response with props but no games"""
    props = [{"player": "LeBron", "line": 25.5}]

    response = build_best_bets_response(
        sport="NBA",
        props_picks=props,
        game_picks=[],
        total_props_analyzed=10,
        total_games_analyzed=0
    )

    assert "props" in response
    assert "games" in response
    assert "meta" in response

    assert response["props"]["count"] == 1
    assert response["games"]["count"] == 0


def test_response_with_games_only():
    """Response with games but no props"""
    games = [{"matchup": "LAL @ BOS", "pick": "Over 220.5"}]

    response = build_best_bets_response(
        sport="NHL",
        props_picks=[],
        game_picks=games,
        total_props_analyzed=0,
        total_games_analyzed=5
    )

    assert "props" in response
    assert "games" in response
    assert "meta" in response

    assert response["props"]["count"] == 0
    assert response["games"]["count"] == 1


def test_all_sports_return_same_keys():
    """All sports must return props, games, meta"""
    for sport in ["NBA", "NHL", "NFL", "MLB", "NCAAB"]:
        response = build_best_bets_response(
            sport=sport,
            props_picks=[],
            game_picks=[],
        )

        assert "props" in response, f"{sport} missing props key"
        assert "games" in response, f"{sport} missing games key"
        assert "meta" in response, f"{sport} missing meta key"


def test_response_always_valid_json():
    """Response must always be dict with required keys"""
    response = build_best_bets_response(
        sport="NBA",
        props_picks=[],
        game_picks=[]
    )

    # Must be dict
    assert isinstance(response, dict)

    # Must have required keys
    required_keys = ["sport", "props", "games", "meta"]
    for key in required_keys:
        assert key in response, f"Missing required key: {key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
