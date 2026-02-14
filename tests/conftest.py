"""
tests/conftest.py - Pytest configuration and fixtures

v20.28.4: Makes test suite environment-agnostic by:
- Setting RAILWAY_VOLUME_MOUNT_PATH to a temp directory
- Ensuring all volume-dependent tests can run locally
"""

import os
import pytest
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def set_volume_path(tmp_path_factory):
    """
    Automatically set RAILWAY_VOLUME_MOUNT_PATH to a temp directory for all tests.

    This fixture runs once per test session and ensures:
    - Tests don't require /data to exist
    - Tests don't pollute the local filesystem
    - Tests are isolated from production paths
    """
    # Create a session-scoped temp directory
    volume_dir = tmp_path_factory.mktemp("railway_volume")

    # Create expected subdirectories
    (volume_dir / "models").mkdir(exist_ok=True)
    (volume_dir / "grader").mkdir(exist_ok=True)
    (volume_dir / "grader_data").mkdir(exist_ok=True)
    (volume_dir / "audit_logs").mkdir(exist_ok=True)
    (volume_dir / "trap_learning").mkdir(exist_ok=True)
    (volume_dir / "shadow").mkdir(exist_ok=True)

    # Set the env var BEFORE any imports that might read it
    old_value = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = str(volume_dir)

    yield volume_dir

    # Restore original value
    if old_value is not None:
        os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = old_value
    elif "RAILWAY_VOLUME_MOUNT_PATH" in os.environ:
        del os.environ["RAILWAY_VOLUME_MOUNT_PATH"]


@pytest.fixture
def volume_path(set_volume_path):
    """Provide the volume path to individual tests that need it."""
    return set_volume_path


@pytest.fixture
def models_dir(volume_path):
    """Provide the models directory path."""
    models = volume_path / "models"
    models.mkdir(exist_ok=True)
    return models


@pytest.fixture
def grader_dir(volume_path):
    """Provide the grader directory path."""
    grader = volume_path / "grader"
    grader.mkdir(exist_ok=True)
    return grader


@pytest.fixture
def grader_data_dir(volume_path):
    """Provide the grader_data directory path."""
    grader_data = volume_path / "grader_data"
    grader_data.mkdir(exist_ok=True)
    return grader_data
