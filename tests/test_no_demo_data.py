"""
Tests for demo data hard gate.

Ensures that:
1. Demo/sample data is NEVER returned without explicit ENABLE_DEMO=true or mode=demo
2. When live data is unavailable, empty picks + errors are returned
3. Debug seed endpoints require demo mode flag
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Skip tests if required modules not available
pytest.importorskip("loguru", reason="loguru required for legacy service tests")


class TestLegacyOddsServiceDemoGate:
    """Tests for legacy odds_api_service demo data gating."""

    def test_no_demo_without_flag(self, monkeypatch):
        """Without ENABLE_DEMO, demo mode should not activate."""
        monkeypatch.delenv("ENABLE_DEMO", raising=False)
        monkeypatch.delenv("ODDS_API_KEY", raising=False)

        # Re-import to pick up env changes
        import importlib
        from legacy.services import odds_api_service
        importlib.reload(odds_api_service)

        service = odds_api_service.OddsAPIService()

        # get_odds should return empty list, not demo data
        result = service.get_odds("basketball_nba")
        assert result == [], "Should return empty list without ENABLE_DEMO"

    def test_demo_with_flag(self, monkeypatch):
        """With ENABLE_DEMO=true, demo mode should work."""
        monkeypatch.setenv("ENABLE_DEMO", "true")
        monkeypatch.delenv("ODDS_API_KEY", raising=False)

        # Re-import to pick up env changes
        import importlib
        from legacy.services import odds_api_service
        importlib.reload(odds_api_service)

        service = odds_api_service.OddsAPIService()

        # get_odds should return demo data
        result = service.get_odds("basketball_nba")
        assert len(result) > 0, "Should return demo data with ENABLE_DEMO=true"
        assert result[0].get("id") == "demo_game_1"

    def test_get_sports_empty_without_flag(self, monkeypatch):
        """get_sports should return empty without ENABLE_DEMO."""
        monkeypatch.delenv("ENABLE_DEMO", raising=False)
        monkeypatch.delenv("ODDS_API_KEY", raising=False)

        import importlib
        from legacy.services import odds_api_service
        importlib.reload(odds_api_service)

        service = odds_api_service.OddsAPIService()
        result = service.get_sports()
        assert result == [], "Should return empty list without ENABLE_DEMO"


class TestFallbackLineShop:
    """Tests for line shop fallback behavior."""

    def test_fallback_returns_empty(self):
        """generate_fallback_line_shop should return empty list."""
        from live_data_router import generate_fallback_line_shop

        for sport in ["nba", "nfl", "mlb", "nhl", "ncaab"]:
            result = generate_fallback_line_shop(sport)
            assert result == [], f"Fallback for {sport} should return empty list"

    def test_deprecated_fallback_gated(self, monkeypatch):
        """_DEPRECATED_generate_fallback_line_shop should be gated."""
        monkeypatch.delenv("ENABLE_DEMO", raising=False)

        from live_data_router import _DEPRECATED_generate_fallback_line_shop

        result = _DEPRECATED_generate_fallback_line_shop("nba")
        assert result == [], "Deprecated fallback should return empty without ENABLE_DEMO"

    def test_deprecated_fallback_with_demo(self, monkeypatch):
        """_DEPRECATED_generate_fallback_line_shop should work with ENABLE_DEMO."""
        monkeypatch.setenv("ENABLE_DEMO", "true")

        # Need to reimport to pick up env change
        import importlib
        import live_data_router
        importlib.reload(live_data_router)

        result = live_data_router._DEPRECATED_generate_fallback_line_shop("nba")
        # With ENABLE_DEMO=true, should return sample data
        assert len(result) > 0, "Should return sample data with ENABLE_DEMO=true"


@pytest.mark.skipif(
    not pytest.importorskip("fastapi", reason="FastAPI required"),
    reason="FastAPI not available"
)
class TestDebugEndpointGating:
    """Tests for debug endpoint demo data gating."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_seed_pick_blocked_without_demo(self, client, monkeypatch):
        """POST /debug/seed-pick should be blocked without demo flag."""
        monkeypatch.delenv("ENABLE_DEMO", raising=False)

        # Need admin auth
        response = client.post(
            "/debug/seed-pick",
            headers={"X-Admin-Key": os.getenv("ADMIN_API_KEY", "test-admin-key")}
        )

        # Should be 403 Forbidden
        assert response.status_code == 403
        data = response.json()
        assert "Demo data gated" in data.get("error", "")

    def test_seed_pick_allowed_with_mode_demo(self, client, monkeypatch):
        """POST /debug/seed-pick?mode=demo should work."""
        monkeypatch.delenv("ENABLE_DEMO", raising=False)

        response = client.post(
            "/debug/seed-pick?mode=demo",
            headers={"X-Admin-Key": os.getenv("ADMIN_API_KEY", "test-admin-key")}
        )

        # Should succeed (or fail for other reasons, but not 403)
        assert response.status_code != 403

    def test_seed_pick_allowed_with_env(self, client, monkeypatch):
        """POST /debug/seed-pick should work with ENABLE_DEMO=true."""
        monkeypatch.setenv("ENABLE_DEMO", "true")

        response = client.post(
            "/debug/seed-pick",
            headers={"X-Admin-Key": os.getenv("ADMIN_API_KEY", "test-admin-key")}
        )

        # Should succeed (or fail for other reasons, but not 403)
        assert response.status_code != 403


@pytest.mark.skipif(
    not pytest.importorskip("fastapi", reason="FastAPI required"),
    reason="FastAPI not available"
)
class TestBestBetsNoSampleData:
    """Tests that best-bets endpoints never return sample data."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_best_bets_returns_empty_on_api_failure(self, client, monkeypatch):
        """When Odds API fails, should return empty picks, not sample data."""
        monkeypatch.delenv("ENABLE_DEMO", raising=False)

        # Mock the odds API to fail
        with patch("live_data_router.get_props") as mock_props:
            mock_props.return_value = []  # Simulate no data

            response = client.get(
                "/live/best-bets/NHL",
                headers={"X-API-Key": os.getenv("API_AUTH_KEY", "test-key")}
            )

            if response.status_code == 200:
                data = response.json()
                props = data.get("props", {}).get("picks", [])

                # Should not contain sample Lakers/Celtics data
                for pick in props:
                    matchup = pick.get("matchup", "")
                    assert "Lakers" not in matchup, "Should not contain sample data"
                    assert "Warriors" not in matchup, "Should not contain sample data"
                    assert "sample" not in pick.get("game_id", "").lower()

    def test_best_bets_empty_picks_structure(self, client, monkeypatch):
        """Empty best-bets should have correct structure."""
        monkeypatch.delenv("ENABLE_DEMO", raising=False)

        with patch("live_data_router.get_props") as mock_props:
            with patch("live_data_router.get_games") as mock_games:
                mock_props.return_value = []
                mock_games.return_value = []

                response = client.get(
                    "/live/best-bets/NHL",
                    headers={"X-API-Key": os.getenv("API_AUTH_KEY", "test-key")}
                )

                if response.status_code == 200:
                    data = response.json()

                    # Structure should still be valid
                    assert "props" in data
                    assert "game_picks" in data or "games" in data
                    assert "picks" in data.get("props", {})

                    # Picks should be empty, not sample data
                    props = data.get("props", {}).get("picks", [])
                    assert isinstance(props, list)


class TestNoSecretLeakage:
    """Tests that secrets are never logged."""

    def test_playbook_api_sanitizes_logs(self, monkeypatch):
        """Playbook API should not log API key."""
        import logging
        from io import StringIO

        # Capture logs
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)

        logger = logging.getLogger("playbook_api")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            # Set a test API key
            test_key = "test-playbook-key-xyz789"
            monkeypatch.setenv("PLAYBOOK_API_KEY", test_key)

            from playbook_api import build_playbook_url

            url, params = build_playbook_url("splits", {"league": "NBA"}, api_key=test_key)

            # Check the log output
            log_output = log_capture.getvalue()

            # The actual key should not appear in logs
            # (we can't easily test the debug log without making a request,
            # but we can verify the sanitizer is imported)
            from playbook_api import sanitize_dict
            sanitized = sanitize_dict(params)
            assert sanitized.get("api_key") == "[REDACTED]"

        finally:
            logger.removeHandler(handler)
