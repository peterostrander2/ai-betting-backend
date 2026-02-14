#!/usr/bin/env bash
# =============================================================================
# CI GATE - Environment-Agnostic Test Suite
# =============================================================================
#
# v20.28.4: Runs the full test suite locally or in CI without requiring
# the Railway volume at /data. Tests automatically use a temp directory.
#
# Exit codes:
#   0 = All tests pass (safe to deploy)
#   1 = Test failure (BLOCK DEPLOY)
#
# Usage:
#   ./scripts/ci_gate.sh                     # Full test suite
#   ./scripts/ci_gate.sh tests/test_foo.py   # Specific test file
#
# Environment:
#   - RAILWAY_VOLUME_MOUNT_PATH is set to temp directory via conftest.py
#   - No /data directory required
#   - Works on macOS, Linux, and CI environments
#
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}CI GATE - Environment-Agnostic Test Suite${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""

# Change to project root
cd "$(dirname "$0")/.."

# Check Python is available
if ! command -v python &> /dev/null; then
    echo -e "${RED}ERROR: Python not found${NC}"
    exit 1
fi

# Check pytest is available
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${RED}ERROR: pytest not installed${NC}"
    echo "Install with: pip install pytest"
    exit 1
fi

# Run tests
# Note: conftest.py automatically sets RAILWAY_VOLUME_MOUNT_PATH to temp directory
echo -e "${YELLOW}Running test suite...${NC}"
echo ""

# Use provided test path or default to all tests
TEST_PATH="${1:-tests/}"

if python -m pytest "$TEST_PATH" -v --tb=short 2>&1; then
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}CI GATE PASSED${NC}"
    echo -e "${GREEN}All tests passed - safe to deploy${NC}"
    echo -e "${GREEN}================================================${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}CI GATE FAILED${NC}"
    echo -e "${RED}Tests failed - BLOCK DEPLOY${NC}"
    echo -e "${RED}================================================${NC}"
    exit 1
fi
