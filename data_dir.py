"""
DATA_DIR - Single source of truth for all persistent storage paths.

On Railway, set RAILWAY_VOLUME_MOUNT_PATH to the mounted volume.
Locally, falls back to current directory.
"""

import os
import logging

logger = logging.getLogger("data_dir")

DATA_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", os.getenv("DATA_DIR", "."))

PICK_LOGS = os.path.join(DATA_DIR, "pick_logs")
GRADED_PICKS = os.path.join(DATA_DIR, "graded_picks")
GRADER_DATA = os.path.join(DATA_DIR, "grader_data")
AUDIT_LOGS = os.path.join(DATA_DIR, "audit_logs")

# Single source of truth for supported sports (used by grader, scheduler, audit, warm)
SUPPORTED_SPORTS = ["NBA", "NHL", "NFL", "MLB", "NCAAB"]


def ensure_dirs():
    """Create all data subdirectories. Call once at startup."""
    for d in [PICK_LOGS, GRADED_PICKS, GRADER_DATA, AUDIT_LOGS]:
        os.makedirs(d, exist_ok=True)
    logger.info("DATA_DIR=%s (subdirs ensured)", DATA_DIR)
