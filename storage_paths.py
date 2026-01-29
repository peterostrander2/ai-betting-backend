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
from datetime import datetime

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

    # FAIL FAST: No mount = ephemeral storage = DATA LOSS
    if not mount:
        logger.error("FATAL: RAILWAY_VOLUME_MOUNT_PATH not set")
        logger.error("Storage will be ephemeral and wiped on restart")
        logger.error("Set RAILWAY_VOLUME_MOUNT_PATH to Railway volume mount path")
        sys.exit(1)

    # Validate mount exists
    if not os.path.exists(mount):
        logger.error("FATAL: Mount path does not exist: %s", mount)
        sys.exit(1)

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

    # Create storage directories
    try:
        os.makedirs(store_dir, exist_ok=True)
        os.makedirs(os.path.join(store_dir, "audits"), exist_ok=True)
    except Exception as e:
        logger.error("FATAL: Cannot create storage directories: %s", e)
        sys.exit(1)

    # Write sentinel file (proves persistence)
    sentinel_file = os.path.join(store_dir, ".volume_sentinel")
    sentinel_content = f"Railway volume verified at {datetime.utcnow().isoformat()}"

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


def get_weights_file() -> str:
    """Get weights.json path."""
    return os.path.join(get_store_dir(), "weights.json")


def get_audit_dir() -> str:
    """Get audit directory path."""
    return os.path.join(get_store_dir(), "audits")


def get_storage_health() -> dict:
    """
    Get storage health status for /internal/storage/health endpoint.

    Returns diagnostic info about storage state.
    """
    try:
        mount_root = get_mount_root()
        store_dir = get_store_dir()
        predictions_file = get_predictions_file()
        sentinel_file = os.path.join(store_dir, ".volume_sentinel")

        # Check predictions file
        pred_exists = os.path.exists(predictions_file)
        pred_size = os.path.getsize(predictions_file) if pred_exists else 0
        pred_modified = None
        pred_line_count = 0

        if pred_exists:
            pred_modified = datetime.fromtimestamp(os.path.getmtime(predictions_file)).isoformat()
            with open(predictions_file, 'r') as f:
                pred_line_count = sum(1 for line in f if line.strip())

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

        return {
            "ok": True,
            "mount_root": mount_root,
            "store_dir": store_dir,
            "writable": writable,
            "predictions_file": predictions_file,
            "predictions_exists": pred_exists,
            "predictions_size_bytes": pred_size,
            "predictions_last_modified": pred_modified,
            "predictions_line_count": pred_line_count,
            "sentinel_exists": sentinel_exists,
            "sentinel_timestamp": sentinel_timestamp,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "mount_root": None,
            "store_dir": None,
            "writable": False,
        }
