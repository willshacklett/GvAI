#!/usr/bin/env bash
set -euo pipefail

echo "Checking key files..."
test -f README.md
test -f action.yml
test -f .github/workflows/godscore-ci-demo.yml
test -f scripts/run_godscore_action.py
test -f ci/godscore_ci.py

echo "Running core tests..."
PYTHONPATH=. python tests/test_sentinel.py
PYTHONPATH=. python tests/test_api.py
PYTHONPATH=. python tests/test_godscore_ci.py

echo
echo "Release check passed."
