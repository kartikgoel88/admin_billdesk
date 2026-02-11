#!/usr/bin/env bash
#
# Run BillDesk app with correct PYTHONPATH.
# Usage: ./scripts/run_app.sh [args...]
# Example: ./scripts/run_app.sh --resources-dir resources
#          ./scripts/run_app.sh --employee IIIPL-1000_naveen_oct_amex --category commute
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src"
exec python3 src/app.py "$@"
