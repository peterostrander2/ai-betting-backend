"""
Tests for best-bets error safety and cache pre-warm logic.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Skip if fastapi isn't available in this environment
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def test_error_returns_500_without_request_id():
    """best-bets crash returns HTTP 500 without request_id in non-debug."""
    # Patch _best_bets_inner to raise before importing app
    with patch("live_data_router._best_bets_inner", new_callable=AsyncMock) as mock_inner:
        mock_inner.side_effect = RuntimeError("scoring engine exploded")

        # Import after patch so the module picks it up
        from main import app
        client = TestClient(app)

        resp = client.get(
            "/live/best-bets/nba",
            headers={"X-API-Key": "test-key"}
        )

        assert resp.status_code == 500
        body = resp.json()
        detail = body.get("detail", {})
        assert "request_id" not in detail
        assert detail["message"] == "best-bets failed"
        # Must NOT contain traceback
        assert "traceback" not in str(body).lower() or "Traceback" not in str(body)
        assert "scoring engine exploded" not in str(detail)


def test_warm_skips_cache_hot():
    """warm_best_bets_cache skips sports with warm cache."""
    import asyncio

    with patch("daily_scheduler.WARM_AVAILABLE", True), \
         patch("daily_scheduler.api_cache") as mock_cache, \
         patch("daily_scheduler._best_bets_inner", new_callable=AsyncMock) as mock_inner:

        # Simulate cache hot for nba
        def fake_get(key):
            if key == "best-bets:nba":
                return {"cached": True}
            return None
        mock_cache.get.side_effect = fake_get
        mock_cache.acquire_lock.return_value = True
        mock_cache.release_lock.return_value = None

        from daily_scheduler import warm_best_bets_cache

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(warm_best_bets_cache())
        finally:
            loop.close()

        # _best_bets_inner should NOT have been called for nba (cache hot)
        for call in mock_inner.call_args_list:
            assert call[0][0].lower() != "nba", \
                "_best_bets_inner should not be called for nba when cache is hot"
