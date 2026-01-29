"""
DATA_DIR - Single source of truth for all persistent storage paths (FIX 3)

GRADER STORAGE RULES:
- Use GRADER_DATA_DIR env var (Railway volume mount)
- Default: /data/grader_data (Railway volume)
- Fail fast on startup if not writable
- Log resolved path
"""

import os
import sys
import logging

logger = logging.getLogger("data_dir")

# FIX 3: Use GRADER_DATA_DIR env var, default to Railway volume
# CRITICAL: NEVER use /app path - it's ephemeral and wiped on redeploy
# Railway volume should be mounted at /data (or custom path via GRADER_DATA_DIR)
_railway_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
if _railway_path and not _railway_path.startswith("/app"):
    GRADER_DATA_DIR = _railway_path
else:
    # Default to /data or explicit override (never /app)
    GRADER_DATA_DIR = os.getenv("GRADER_DATA_DIR", "/data/grader_data")

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
    # FIX 3: Log resolved path and block /app usage
    logger.info("GRADER_DATA_DIR=%s", GRADER_DATA_DIR)

    if GRADER_DATA_DIR.startswith("/app"):
        logger.error("FATAL: Storage path %s is under /app (ephemeral, will be wiped on redeploy)", GRADER_DATA_DIR)
        logger.error("Set GRADER_DATA_DIR env var to Railway volume mount path (e.g., /data)")
        sys.exit(1)

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
        logger.info("✓ Storage verified on persistent volume (not /app)")
    except Exception as e:
        logger.error("FATAL: Storage not writable %s: %s", GRADER_DATA_DIR, e)
        sys.exit(1)
