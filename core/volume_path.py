"""
core/volume_path.py - Centralized volume path management

v20.28.4: Provides environment-agnostic volume path resolution.
- Uses RAILWAY_VOLUME_MOUNT_PATH in production (Railway sets this)
- Falls back to a writable temp directory locally
- Never hardcodes /data directly

Usage:
    from core.volume_path import get_volume_path
    models_dir = get_volume_path() / "models"
"""

import os
import tempfile
from pathlib import Path
from functools import lru_cache


def _is_writable(path: str) -> bool:
    """Check if path exists and is writable."""
    try:
        p = Path(path)
        if not p.exists():
            return False
        # Try to create a test file
        test_file = p / ".write_test"
        test_file.touch()
        test_file.unlink()
        return True
    except (OSError, PermissionError):
        return False


def get_volume_path() -> Path:
    """
    Get the volume mount path for persistent storage.

    Resolution order:
    1. RAILWAY_VOLUME_MOUNT_PATH env var (if set and writable)
    2. ./local_data (for local development, created if needed)
    3. System temp directory (fallback)

    Returns:
        Path object pointing to writable volume directory
    """
    # Check env var first (production)
    env_path = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if env_path and _is_writable(env_path):
        return Path(env_path)

    # If env var set but not writable (e.g., /data locally), use temp
    if env_path and not _is_writable(env_path):
        # Don't use /data if it's not writable - use temp instead
        pass

    # Local development: use ./local_data
    local_data = Path("./local_data")
    try:
        local_data.mkdir(parents=True, exist_ok=True)
        if _is_writable(str(local_data)):
            return local_data.resolve()
    except (OSError, PermissionError):
        pass

    # Final fallback: system temp
    temp_dir = Path(tempfile.gettempdir()) / "bookie_volume"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def get_models_dir() -> Path:
    """Get the models directory path."""
    models_dir = get_volume_path() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_grader_dir() -> Path:
    """Get the grader data directory path."""
    grader_dir = get_volume_path() / "grader"
    grader_dir.mkdir(parents=True, exist_ok=True)
    return grader_dir


def get_grader_data_dir() -> Path:
    """Get the grader_data directory path (weights, predictions)."""
    grader_data_dir = get_volume_path() / "grader_data"
    grader_data_dir.mkdir(parents=True, exist_ok=True)
    return grader_data_dir


def get_audit_logs_dir() -> Path:
    """Get the audit logs directory path."""
    audit_dir = get_volume_path() / "audit_logs"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir
