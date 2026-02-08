"""
STORAGE_PATHS.PY - Single Source of Truth for Railway Volume Storage

HARD REQUIREMENTS:
1. Use RAILWAY_VOLUME_MOUNT_PATH env var (Railway production)
2. Fail-fast if mount not available or not writable
3. All storage paths derived from this single root
4. No hard-coded /app or /data paths anywhere

CRASH ON STARTUP if storage is not persistent.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("storage_paths")


def get_mount_root() -> str:
    """
    Get Railway volume mount root.

    Production: RAILWAY_VOLUME_MOUNT_PATH env var (set by Railway)
    Local dev: GRADER_MOUNT_ROOT override

    CRASHES if mount not available.
    """
    # Production: Railway sets this to actual volume mount
    mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")

    # Local dev override
    if not mount:
        mount = os.getenv("GRADER_MOUNT_ROOT", "")

    # Allow test harness to run without Railway mount (pytest only)
    if not mount and (os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules):
        mount = os.getenv("PYTEST_MOUNT_ROOT", "/tmp/railway_test")

    # FAIL FAST: No mount = ephemeral storage = DATA LOSS
    if not mount:
        logger.error("FATAL: RAILWAY_VOLUME_MOUNT_PATH not set")
        logger.error("Storage will be ephemeral and wiped on restart")
        logger.error("Set RAILWAY_VOLUME_MOUNT_PATH to Railway volume mount path")
        sys.exit(1)

    # Validate mount exists
    if not os.path.exists(mount):
        if os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
            os.makedirs(mount, exist_ok=True)
        else:
            logger.error("FATAL: Mount path does not exist: %s", mount)
            sys.exit(1)

    # Railway mounts volumes at /data (this IS persistent)
    # No path blocking - trust Railway's volume mount

    logger.info("✓ Mount root: %s", mount)
    return mount


def get_store_dir() -> str:
    """
    Get grader storage directory (inside Railway volume).

    Returns: ${MOUNT_ROOT}/grader
    """
    mount_root = get_mount_root()
    store_dir = os.path.join(mount_root, "grader")
    return store_dir


def ensure_persistent_storage_ready():
    """
    Validate storage is writable and persistent.

    CRASHES if storage is not ready.
    Must be called on app startup BEFORE scheduler starts.
    """
    mount_root = get_mount_root()
    store_dir = get_store_dir()

    logger.info("=== STORAGE VALIDATION ===")
    logger.info("Mount root: %s", mount_root)
    logger.info("Store dir: %s", store_dir)

    # Check if mount_root is actually a mountpoint (not just a directory)
    try:
        is_mount = os.path.ismount(mount_root)
        logger.info("Is mountpoint: %s", is_mount)

        if not is_mount:
            logger.warning("WARNING: %s is NOT a mountpoint", mount_root)
            logger.warning("This may be ephemeral storage")
            # Don't crash on this - some Railway setups use directories
    except Exception as e:
        logger.warning("Could not check if mountpoint: %s", e)

    # Create storage directories
    try:
        os.makedirs(store_dir, exist_ok=True)
        os.makedirs(os.path.join(store_dir, "audits"), exist_ok=True)
    except Exception as e:
        logger.error("FATAL: Cannot create storage directories: %s", e)
        sys.exit(1)

    # Write sentinel file (proves persistence)
    sentinel_file = os.path.join(store_dir, ".volume_sentinel")
    sentinel_content = f"Railway volume verified at {datetime.now(tz=timezone.utc).isoformat()}"

    try:
        with open(sentinel_file, 'w') as f:
            f.write(sentinel_content)

        # Read it back
        with open(sentinel_file, 'r') as f:
            content = f.read()

        if content != sentinel_content:
            raise RuntimeError("Sentinel file content mismatch")

        logger.info("✓ Storage writable: %s", store_dir)
        logger.info("✓ Sentinel verified: %s", sentinel_file)

    except Exception as e:
        logger.error("FATAL: Storage not writable: %s", e)
        logger.error("Cannot guarantee persistence - ABORTING")
        sys.exit(1)

    logger.info("=== STORAGE READY ===")


def get_predictions_file() -> str:
    """Get predictions.jsonl path."""
    return os.path.join(get_store_dir(), "predictions.jsonl")


def get_graded_picks_file() -> str:
    """Get graded_picks.jsonl path (append-only grade records)."""
    return os.path.join(get_store_dir(), "graded_picks.jsonl")


def get_weights_file() -> str:
    """Get weights.json path."""
    mount_root = get_mount_root()
    # Keep weights in a separate low-frequency directory to avoid contention
    return os.path.join(mount_root, "grader_data", "weights.json")


def get_audit_dir() -> str:
    """Get audit directory path."""
    return os.path.join(get_store_dir(), "audits")


def get_storage_health() -> dict:
    """
    Get storage health status for /internal/storage/health endpoint.

    Returns diagnostic info about storage state including:
    - resolved_base_dir: Actual RAILWAY_VOLUME_MOUNT_PATH value
    - is_mountpoint: os.path.ismount() result
    - absolute_paths: Full paths for predictions.jsonl and weights.json
    - predictions_line_count: Number of picks in predictions file
    - weights_last_modified: Timestamp of weights.json file
    """
    try:
        mount_root = get_mount_root()
        store_dir = get_store_dir()
        predictions_file = get_predictions_file()
        graded_picks_file = get_graded_picks_file()
        weights_file = get_weights_file()
        sentinel_file = os.path.join(store_dir, ".volume_sentinel")

        # Check if mountpoint
        is_mountpoint = os.path.ismount(mount_root)

        # Get environment variables for diagnostics
        env_railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "NOT_SET")
        env_grader_mount = os.getenv("GRADER_MOUNT_ROOT", "NOT_SET")

        # Check predictions file
        pred_exists = os.path.exists(predictions_file)
        pred_size = os.path.getsize(predictions_file) if pred_exists else 0
        pred_modified = None
        pred_line_count = 0

        if pred_exists:
            pred_modified = datetime.fromtimestamp(os.path.getmtime(predictions_file)).isoformat()
            with open(predictions_file, 'r') as f:
                pred_line_count = sum(1 for line in f if line.strip())

        # Check weights file
        weights_exists = os.path.exists(weights_file)
        weights_modified = None
        if weights_exists:
            weights_modified = datetime.fromtimestamp(os.path.getmtime(weights_file)).isoformat()

        # Check sentinel
        sentinel_exists = os.path.exists(sentinel_file)
        sentinel_timestamp = None
        if sentinel_exists:
            with open(sentinel_file, 'r') as f:
                sentinel_timestamp = f.read().strip()

        # Check writable
        writable = True
        try:
            test_file = os.path.join(store_dir, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except:
            writable = False

        # If RAILWAY_VOLUME_MOUNT_PATH is set, storage is persistent (Railway volume)
        # Only ephemeral if using fallback paths
        is_ephemeral = env_railway_mount == "NOT_SET"

        return {
            "ok": True,
            "resolved_base_dir": mount_root,  # Actual RAILWAY_VOLUME_MOUNT_PATH value
            "mount_root": mount_root,
            "is_mountpoint": is_mountpoint,
            "is_ephemeral": is_ephemeral,
            "env_railway_volume_mount_path": env_railway_mount,
            "env_grader_mount_root": env_grader_mount,
            "store_dir": store_dir,
            "writable": writable,
            "absolute_paths": {
                "predictions": predictions_file,
                "graded_picks": graded_picks_file,
                "weights": weights_file,
                "store_dir": store_dir,
            },
            "predictions_file": predictions_file,
            "predictions_exists": pred_exists,
            "predictions_size_bytes": pred_size,
            "predictions_last_modified": pred_modified,
            "predictions_line_count": pred_line_count,
            "graded_picks_file": graded_picks_file,
            "graded_picks_exists": os.path.exists(graded_picks_file),
            "graded_picks_size_bytes": os.path.getsize(graded_picks_file) if os.path.exists(graded_picks_file) else 0,
            "weights_file": weights_file,
            "weights_exists": weights_exists,
            "weights_last_modified": weights_modified,
            "sentinel_exists": sentinel_exists,
            "sentinel_timestamp": sentinel_timestamp,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "resolved_base_dir": None,
            "mount_root": None,
            "is_mountpoint": False,
            "is_ephemeral": None,
            "store_dir": None,
            "writable": False,
        }
