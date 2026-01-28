#!/usr/bin/env python3
"""
Test script to verify auto-grader fix locally before deployment.

Run this to ensure:
1. commence_time_iso field is added to picks
2. /live/grader/status returns correct info
3. /live/smoke-test/alert-status works
4. Railway volume support is configured
"""

import os
import sys
import asyncio
from datetime import datetime

# Set test mode environment
os.environ['TESTING'] = 'true'

def test_pick_logger_fields():
    """Test that PublishedPick has commence_time_iso field."""
    print("Testing pick_logger fields...")
    from pick_logger import PublishedPick
    from dataclasses import fields

    field_names = [f.name for f in fields(PublishedPick)]

    assert 'game_start_time_et' in field_names, "Missing game_start_time_et field"
    assert 'commence_time_iso' in field_names, "Missing commence_time_iso field"

    print("✅ PublishedPick has both game_start_time_et and commence_time_iso fields")
    return True


def test_storage_paths():
    """Test that storage paths support Railway volumes."""
    print("\nTesting storage path configuration...")

    # Test without RAILWAY_VOLUME_MOUNT_PATH (local dev mode)
    if 'RAILWAY_VOLUME_MOUNT_PATH' in os.environ:
        del os.environ['RAILWAY_VOLUME_MOUNT_PATH']

    # Force reload of pick_logger to pick up env changes
    import importlib
    import pick_logger
    importlib.reload(pick_logger)

    assert pick_logger.STORAGE_PATH == "./pick_logs", f"Expected ./pick_logs, got {pick_logger.STORAGE_PATH}"
    assert pick_logger.GRADED_PATH == "./graded_picks", f"Expected ./graded_picks, got {pick_logger.GRADED_PATH}"
    print("✅ Local dev mode: Using ./pick_logs and ./graded_picks")

    # Test with RAILWAY_VOLUME_MOUNT_PATH set
    os.environ['RAILWAY_VOLUME_MOUNT_PATH'] = '/data'
    importlib.reload(pick_logger)

    assert pick_logger.STORAGE_PATH == "/data/pick_logs", f"Expected /data/pick_logs, got {pick_logger.STORAGE_PATH}"
    assert pick_logger.GRADED_PATH == "/data/graded_picks", f"Expected /data/graded_picks, got {pick_logger.GRADED_PATH}"
    print("✅ Railway mode: Using /data/pick_logs and /data/graded_picks")

    # Cleanup
    del os.environ['RAILWAY_VOLUME_MOUNT_PATH']
    importlib.reload(pick_logger)

    return True


def test_auto_grader_storage():
    """Test that auto_grader supports Railway volumes."""
    print("\nTesting auto_grader storage...")
    from auto_grader import AutoGrader

    # Test without RAILWAY_VOLUME_MOUNT_PATH
    if 'RAILWAY_VOLUME_MOUNT_PATH' in os.environ:
        del os.environ['RAILWAY_VOLUME_MOUNT_PATH']

    grader = AutoGrader()
    assert grader.storage_path == "./grader_data", f"Expected ./grader_data, got {grader.storage_path}"
    print("✅ Local dev mode: AutoGrader using ./grader_data")

    # Test with RAILWAY_VOLUME_MOUNT_PATH set
    os.environ['RAILWAY_VOLUME_MOUNT_PATH'] = '/data'
    grader = AutoGrader()
    assert grader.storage_path == "/data/grader_data", f"Expected /data/grader_data, got {grader.storage_path}"
    print("✅ Railway mode: AutoGrader using /data/grader_data")

    # Cleanup
    if 'RAILWAY_VOLUME_MOUNT_PATH' in os.environ:
        del os.environ['RAILWAY_VOLUME_MOUNT_PATH']

    return True


async def test_grader_status_endpoint():
    """Test that /live/grader/status returns correct structure."""
    print("\nTesting /live/grader/status endpoint structure...")

    # Import the endpoint function
    from live_data_router import grader_status

    # Call it (it's async)
    result = await grader_status()

    # Check structure
    assert 'available' in result, "Missing 'available' key"
    assert 'timestamp' in result, "Missing 'timestamp' key"
    assert 'pick_logger' in result, "Missing 'pick_logger' key"
    assert 'weight_learning' in result, "Missing 'weight_learning' key"

    # Check pick_logger structure
    if result['pick_logger'].get('available', False):
        assert 'predictions_logged' in result['pick_logger'], "Missing 'predictions_logged' in pick_logger"
        assert 'pending_to_grade' in result['pick_logger'], "Missing 'pending_to_grade' in pick_logger"
        assert 'graded_today' in result['pick_logger'], "Missing 'graded_today' in pick_logger"
        print("✅ /live/grader/status returns correct pick_logger stats")
    else:
        print("⚠️  pick_logger not available, skipping detailed checks")

    print(f"   - predictions_logged: {result['pick_logger'].get('predictions_logged', 'N/A')}")
    print(f"   - pending_to_grade: {result['pick_logger'].get('pending_to_grade', 'N/A')}")
    print(f"   - graded_today: {result['pick_logger'].get('graded_today', 'N/A')}")

    return True


async def test_smoke_test_endpoint():
    """Test that /live/smoke-test/alert-status works."""
    print("\nTesting /live/smoke-test/alert-status endpoint...")

    from live_data_router import smoke_test_alert_status

    result = await smoke_test_alert_status()

    # Check structure
    assert 'status' in result, "Missing 'status' key"
    assert 'timestamp' in result, "Missing 'timestamp' key"
    assert 'alerts' in result, "Missing 'alerts' key"
    assert 'pick_logger' in result, "Missing 'pick_logger' key"
    assert 'auto_grader' in result, "Missing 'auto_grader' key"
    assert 'api_keys_configured' in result, "Missing 'api_keys_configured' key"

    print(f"✅ /live/smoke-test/alert-status works")
    print(f"   - status: {result['status']}")
    print(f"   - alerts: {len(result['alerts'])} alert(s)")
    print(f"   - pick_logger available: {result['pick_logger'].get('available', False)}")
    print(f"   - auto_grader available: {result['auto_grader'].get('available', False)}")

    return True


def test_railway_toml():
    """Test that railway.toml has volume mount configured."""
    print("\nTesting railway.toml configuration...")

    with open('railway.toml', 'r') as f:
        content = f.read()

    assert '[[deploy.volumeMounts]]' in content, "Missing [[deploy.volumeMounts]] in railway.toml"
    assert 'mountPath = "/data"' in content, "Missing mountPath = \"/data\" in railway.toml"

    print("✅ railway.toml has volume mount configured")
    print('   - [[deploy.volumeMounts]]')
    print('   - mountPath = "/data"')

    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("AUTO-GRADER FIX VERIFICATION")
    print("=" * 60)

    tests = [
        ("Pick Logger Fields", test_pick_logger_fields, False),
        ("Storage Paths", test_storage_paths, False),
        ("Auto-Grader Storage", test_auto_grader_storage, False),
        ("Railway TOML", test_railway_toml, False),
        ("Grader Status Endpoint", test_grader_status_endpoint, True),
        ("Smoke Test Endpoint", test_smoke_test_endpoint, True),
    ]

    passed = 0
    failed = 0

    for name, test_func, is_async in tests:
        try:
            if is_async:
                result = await test_func()
            else:
                result = test_func()

            if result:
                passed += 1
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("✅ All tests passed! Ready to deploy.")
        return 0
    else:
        print("❌ Some tests failed. Fix issues before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
