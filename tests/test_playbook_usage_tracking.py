"""
Tests for Playbook API usage tracking (v20.28.6).

Verifies that:
1. mark_integration_used() increments used_count
2. record_cache_hit() increments cache_hits
3. Both track Playbook API usage correctly
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPlaybookUsageTracking:
    """Verify Playbook API usage tracking works correctly."""

    def test_mark_integration_used_increments_count(self):
        """mark_integration_used should increment used_count."""
        from integration_registry import (
            mark_integration_used,
            INTEGRATION_USAGE,
            _ensure_usage_registry,
        )

        _ensure_usage_registry()

        # Get initial count
        initial_count = INTEGRATION_USAGE.get("playbook_api", {}).get("used_count", 0)

        # Mark as used
        mark_integration_used("playbook_api")

        # Verify count incremented
        new_count = INTEGRATION_USAGE.get("playbook_api", {}).get("used_count", 0)
        assert new_count == initial_count + 1, f"Expected count to increment from {initial_count} to {initial_count + 1}, got {new_count}"

    def test_mark_integration_used_updates_last_used_at(self):
        """mark_integration_used should update last_used_at."""
        from integration_registry import (
            mark_integration_used,
            INTEGRATION_USAGE,
            _ensure_usage_registry,
        )

        _ensure_usage_registry()

        # Mark as used
        mark_integration_used("playbook_api")

        # Verify last_used_at is set
        last_used = INTEGRATION_USAGE.get("playbook_api", {}).get("last_used_at")
        assert last_used is not None, "last_used_at should be set after marking"

    def test_record_cache_hit_increments_cache_hits(self):
        """record_cache_hit should increment cache_hits in IntegrationHealth."""
        from integration_registry import (
            record_cache_hit,
            _health_tracker,
        )

        # Get initial count
        if "playbook_api" not in _health_tracker:
            initial_hits = 0
        else:
            initial_hits = _health_tracker["playbook_api"].cache_hits

        # Record cache hit
        record_cache_hit("playbook_api")

        # Verify cache_hits incremented
        new_hits = _health_tracker["playbook_api"].cache_hits
        assert new_hits == initial_hits + 1, f"Expected cache_hits to increment from {initial_hits} to {initial_hits + 1}, got {new_hits}"

    def test_record_cache_miss_increments_cache_misses(self):
        """record_cache_miss should increment cache_misses in IntegrationHealth."""
        from integration_registry import (
            record_cache_miss,
            _health_tracker,
        )

        # Get initial count
        if "playbook_api" not in _health_tracker:
            initial_misses = 0
        else:
            initial_misses = _health_tracker["playbook_api"].cache_misses

        # Record cache miss
        record_cache_miss("playbook_api")

        # Verify cache_misses incremented
        new_misses = _health_tracker["playbook_api"].cache_misses
        assert new_misses == initial_misses + 1, f"Expected cache_misses to increment from {initial_misses} to {initial_misses + 1}, got {new_misses}"

    def test_get_cache_hit_rate(self):
        """get_cache_hit_rate should return correct ratio."""
        from integration_registry import (
            record_cache_hit,
            record_cache_miss,
            get_cache_hit_rate,
            _health_tracker,
            IntegrationHealth,
        )

        # Reset the tracker for this test
        _health_tracker["test_api"] = IntegrationHealth()

        # Record 3 hits and 1 miss
        record_cache_hit("test_api")
        record_cache_hit("test_api")
        record_cache_hit("test_api")
        record_cache_miss("test_api")

        # Get hit rate
        hit_rate = get_cache_hit_rate("test_api")
        assert hit_rate == 0.75, f"Expected cache hit rate of 0.75, got {hit_rate}"

    def test_get_usage_snapshot_includes_playbook(self):
        """get_usage_snapshot should include playbook_api usage."""
        from integration_registry import (
            mark_integration_used,
            get_usage_snapshot,
            _ensure_usage_registry,
        )

        _ensure_usage_registry()

        # Mark playbook as used
        mark_integration_used("playbook_api")

        # Get snapshot
        snapshot = get_usage_snapshot()

        # Verify playbook is included
        assert "playbook_api" in snapshot, "playbook_api should be in snapshot"
        assert snapshot["playbook_api"]["used_count"] > 0, "used_count should be > 0 after marking"


class TestFetchWithRetriesTracking:
    """Verify fetch_with_retries tracks Playbook API usage."""

    def test_playbook_url_base_constant_exists(self):
        """PLAYBOOK_API_BASE should be defined for tracking."""
        from live_data_router import PLAYBOOK_API_BASE
        assert PLAYBOOK_API_BASE is not None
        assert "playbook" in PLAYBOOK_API_BASE.lower()

    def test_fetch_with_retries_has_playbook_tracking(self):
        """fetch_with_retries should have Playbook tracking code."""
        import inspect
        from live_data_router import fetch_with_retries

        # Get source code
        source = inspect.getsource(fetch_with_retries)

        # Verify Playbook tracking is present
        assert "PLAYBOOK_API_BASE" in source, "fetch_with_retries should check PLAYBOOK_API_BASE"
        assert "playbook_api" in source, "fetch_with_retries should track playbook_api"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
