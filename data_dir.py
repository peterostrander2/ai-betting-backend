"""
DATA_DIR - Single source of truth for all persistent storage paths (FIX 3)

GRADER STORAGE RULES:
- Use RAILWAY_VOLUME_MOUNT_PATH env var (Railway persistent volume)
- Production: /app/grader_data (Railway 5GB volume mount)
- Local dev: ./grader_data (fallback)
- Fail fast on startup if not writable
- Log resolved path
"""

import os
import sys
import logging

logger = logging.getLogger("data_dir")

# FIX 3: Use Railway persistent volume (RAILWAY_VOLUME_MOUNT_PATH)
# IMPORTANT: Railway mounts persistent volume at /app/grader_data
# This IS persistent storage (5GB Railway volume), NOT ephemeral
_railway_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
if _railway_path:
    GRADER_DATA_DIR = _railway_path
else:
    # Fallback for local dev
    GRADER_DATA_DIR = os.getenv("GRADER_DATA_DIR", "./grader_data")

# Legacy DATA_DIR for backward compatibility
DATA_DIR = GRADER_DATA_DIR

PICK_LOGS = os.path.join(GRADER_DATA_DIR, "pick_logs")
GRADED_PICKS = os.path.join(GRADER_DATA_DIR, "graded_picks")
GRADER_DATA = os.path.join(GRADER_DATA_DIR, "grader_data")
AUDIT_LOGS = os.path.join(GRADER_DATA_DIR, "audit_logs")

# Single source of truth for supported sports (used by grader, scheduler, audit, warm)
SUPPORTED_SPORTS = ["NBA", "NHL", "NFL", "MLB", "NCAAB"]


def ensure_dirs():
    """
    Create all data subdirectories. Call once at startup.

    FIX 3: Fail fast if directory not writable.
    """
    # FIX 3: Log resolved path
    logger.info("GRADER_DATA_DIR=%s", GRADER_DATA_DIR)

    # Verify it's the Railway persistent volume
    _railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
    if _railway_mount and GRADER_DATA_DIR == _railway_mount:
        logger.info("✓ Using Railway persistent volume: %s", GRADER_DATA_DIR)
    elif _railway_mount:
        logger.warning("WARNING: GRADER_DATA_DIR differs from RAILWAY_VOLUME_MOUNT_PATH")
        logger.warning("  GRADER_DATA_DIR: %s", GRADER_DATA_DIR)
        logger.warning("  RAILWAY_VOLUME_MOUNT_PATH: %s", _railway_mount)

    for d in [PICK_LOGS, GRADED_PICKS, GRADER_DATA, AUDIT_LOGS]:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            logger.error("FATAL: Cannot create directory %s: %s", d, e)
            sys.exit(1)

    # Test write
    test_file = os.path.join(GRADER_DATA_DIR, ".write_test")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        logger.info("✓ Storage writable: %s", GRADER_DATA_DIR)
        logger.info("✓ Storage verified on persistent volume")
    except Exception as e:
        logger.error("FATAL: Storage not writable %s: %s", GRADER_DATA_DIR, e)
        sys.exit(1)
