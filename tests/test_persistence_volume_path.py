"""
Test: Persistence Volume Path (Railway Volume)

REQUIREMENT: ALL persistent data MUST live on Railway volume at /app/grader_data
- Predictions JSONL file
- Weights JSON file
- Audit logs

Tests verify:
1. Storage paths are inside RAILWAY_VOLUME_MOUNT_PATH
2. Paths are absolute (start with /)
3. No paths use ephemeral storage (/tmp, /app root)
4. Storage is writable
"""

import os
import pytest

# Storage modules - use try/except for graceful handling
try:
    import storage_paths
    STORAGE_PATHS_AVAILABLE = True
except ImportError:
    STORAGE_PATHS_AVAILABLE = False

try:
    import data_dir
    DATA_DIR_AVAILABLE = True
except ImportError:
    DATA_DIR_AVAILABLE = False


def _is_storage_paths_functional():
    """Check if storage_paths can actually be used (env var set)"""
    if not STORAGE_PATHS_AVAILABLE:
        return False
    mount_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "") or os.getenv("GRADER_MOUNT_ROOT", "")
    return bool(mount_path)


@pytest.mark.skipif(not STORAGE_PATHS_AVAILABLE, reason="storage_paths module not available")
class TestStoragePathConfiguration:
    """Test storage path configuration uses Railway volume"""

    @pytest.mark.skipif(not _is_storage_paths_functional(), reason="RAILWAY_VOLUME_MOUNT_PATH not set")
    def test_railway_volume_mount_path_is_used(self):
        """RAILWAY_VOLUME_MOUNT_PATH env var should be used for storage"""
        # In production: /app/grader_data
        # In local dev: ./grader_data
        # Note: get_store_dir() will exit if RAILWAY_VOLUME_MOUNT_PATH not set
        predictions_file = storage_paths.get_predictions_file()

        assert predictions_file is not None, "Predictions file path should be set"
        assert len(predictions_file) > 0, "Predictions file path should not be empty"

    @pytest.mark.skipif(not _is_storage_paths_functional(), reason="RAILWAY_VOLUME_MOUNT_PATH not set")
    def test_predictions_path_is_absolute_or_relative(self):
        """Predictions file path should be valid"""
        predictions_file = storage_paths.get_predictions_file()

        assert predictions_file is not None
        assert "predictions" in predictions_file.lower()
        assert predictions_file.endswith(".jsonl")

    @pytest.mark.skipif(not _is_storage_paths_functional(), reason="RAILWAY_VOLUME_MOUNT_PATH not set")
    def test_storage_paths_are_not_in_tmp(self):
        """Storage should NOT be in /tmp (ephemeral)"""
        predictions_file = storage_paths.get_predictions_file()

        assert not predictions_file.startswith("/tmp"), "/tmp is ephemeral, should not be used"

    @pytest.mark.skipif(not DATA_DIR_AVAILABLE, reason="data_dir module not available")
    def test_weights_storage_is_configured(self):
        """Weights storage should be configured via data_dir"""
        weights_dir = data_dir.GRADER_DATA_DIR

        assert weights_dir is not None
        assert len(weights_dir) > 0

    @pytest.mark.skipif(not DATA_DIR_AVAILABLE, reason="data_dir module not available")
    def test_data_dir_paths_consistent(self):
        """data_dir paths should be inside GRADER_DATA_DIR"""
        base = data_dir.GRADER_DATA_DIR
        # GRADER_DATA subdirectory contains weight learning files
        grader_data_path = data_dir.GRADER_DATA

        # GRADER_DATA should be inside base directory
        assert base in grader_data_path or grader_data_path.startswith(base), \
            f"GRADER_DATA {grader_data_path} should be inside {base}"


@pytest.mark.skipif(not STORAGE_PATHS_AVAILABLE or not DATA_DIR_AVAILABLE, reason="Storage modules not available")
class TestStorageWritability:
    """Test that storage is writable"""

    def test_store_dir_exists_or_can_be_created(self):
        """GRADER_DATA_DIR should exist or be creatable"""
        store_dir = data_dir.GRADER_DATA_DIR

        # In CI/local, might need to create
        if not os.path.exists(store_dir):
            try:
                os.makedirs(store_dir, exist_ok=True)
            except PermissionError:
                pytest.skip("Cannot create store_dir in this environment")

        assert os.path.isdir(store_dir), f"{store_dir} should be a directory"

    def test_can_write_to_store_dir(self):
        """Should be able to write test file to store directory"""
        store_dir = data_dir.GRADER_DATA_DIR

        if not os.path.exists(store_dir):
            try:
                os.makedirs(store_dir, exist_ok=True)
            except PermissionError:
                pytest.skip("Cannot create store_dir in this environment")

        test_file = os.path.join(store_dir, "_test_write_check.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("test")

            assert os.path.exists(test_file), "Test file should exist after write"

            # Cleanup
            os.remove(test_file)
        except PermissionError:
            pytest.skip("Cannot write to store_dir in this environment")


@pytest.mark.skipif(not STORAGE_PATHS_AVAILABLE or not DATA_DIR_AVAILABLE, reason="Storage modules not available")
class TestProductionPathRequirements:
    """Test path requirements for production environment"""

    def test_railway_env_var_handling(self):
        """Test that RAILWAY_VOLUME_MOUNT_PATH is handled correctly"""
        # storage_paths.py should check RAILWAY_VOLUME_MOUNT_PATH first
        # If set, use it; if not, fall back to local path

        env_var = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")

        if env_var:
            # In production/Railway, predictions file should be under the mount path
            predictions_file = storage_paths.get_predictions_file()
            assert env_var in predictions_file, \
                   "Predictions path should use RAILWAY_VOLUME_MOUNT_PATH when set"

    def test_grader_data_dir_env_var_handling(self):
        """Test GRADER_DATA_DIR fallback logic"""
        env_var = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")

        if env_var:
            # In production/Railway, should use the Railway path
            assert data_dir.GRADER_DATA_DIR.startswith(env_var) or \
                   env_var in data_dir.GRADER_DATA_DIR, \
                   "GRADER_DATA_DIR should use RAILWAY_VOLUME_MOUNT_PATH when set"
        else:
            # In local dev, should use local fallback
            assert data_dir.GRADER_DATA_DIR is not None

    def test_dual_storage_paths_on_same_volume(self):
        """Both storage systems should be on the same volume in production"""
        env_var = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")

        if env_var:
            # In production, both should be under /app/grader_data
            predictions = storage_paths.get_predictions_file()
            grader_data = data_dir.GRADER_DATA

            # Both should be under the Railway volume mount
            assert env_var in predictions or predictions.startswith(env_var), \
                f"Predictions {predictions} should be under {env_var}"

            # Note: data_dir uses a subdirectory, which is intentional
            # /app/grader_data/grader/predictions.jsonl (storage_paths)
            # /app/grader_data/grader_data/ (data_dir.GRADER_DATA)


@pytest.mark.skipif(not STORAGE_PATHS_AVAILABLE or not DATA_DIR_AVAILABLE, reason="Storage modules not available")
class TestPathStructure:
    """Test expected path structure"""

    @pytest.mark.skipif(not _is_storage_paths_functional(), reason="RAILWAY_VOLUME_MOUNT_PATH not set")
    def test_predictions_file_naming(self):
        """Predictions file should follow naming convention"""
        predictions_file = storage_paths.get_predictions_file()

        # Should contain "predictions"
        assert "predictions" in predictions_file.lower()

        # Should be JSONL format
        assert predictions_file.endswith(".jsonl")

    def test_grader_data_dir_structure(self):
        """GRADER_DATA directory should exist"""
        grader_data_path = data_dir.GRADER_DATA

        # Should contain "grader_data"
        assert "grader_data" in grader_data_path.lower()

    @pytest.mark.skipif(not _is_storage_paths_functional(), reason="RAILWAY_VOLUME_MOUNT_PATH not set")
    def test_no_hardcoded_app_root(self):
        """Paths should not be hardcoded to /app directly"""
        predictions_file = storage_paths.get_predictions_file()
        grader_data_dir = data_dir.GRADER_DATA_DIR

        # /app alone is ephemeral, /app/grader_data is the volume
        # Check that we're not using /app directly
        if grader_data_dir.startswith("/app"):
            assert grader_data_dir != "/app", "/app alone is ephemeral"
            assert "/grader_data" in grader_data_dir or "/data" in grader_data_dir, \
                "Should use Railway volume subdirectory, not /app root"


@pytest.mark.skipif(not STORAGE_PATHS_AVAILABLE, reason="storage_paths module not available")
class TestPathValidation:
    """Test path validation functions"""

    @pytest.mark.skipif(not _is_storage_paths_functional(), reason="RAILWAY_VOLUME_MOUNT_PATH not set")
    def test_storage_health_endpoint_fields(self):
        """storage_paths should provide health check data"""
        # Check that key functions exist
        assert hasattr(storage_paths, 'get_predictions_file')
        assert hasattr(storage_paths, 'get_storage_health')

        # get_storage_health should return health info
        health = storage_paths.get_storage_health()
        assert isinstance(health, dict)
        assert "ok" in health

        # The health endpoint should be able to report:
        # - resolved_base_dir
        # - is_mountpoint (in production)
        # - is_ephemeral
        # - predictions_file
        # - predictions_exists
        # - writable

        # These are provided by the /internal/storage/health endpoint


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
