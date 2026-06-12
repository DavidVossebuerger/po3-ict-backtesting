#!/usr/bin/env bash
# run_full_overnight.sh — Full multi-asset backtest with all diagnostics
# Run this in a tmux session on the VPS:
#   tmux new -s ict
#   bash scripts/run_full_overnight.sh 2>&1 | tee backtest_logs/ict_full_$(date -u +%Y%m%dT%H%M%SZ).log
#
# Or via SSH:
#   ssh root@158.220.101.247 "tmux new-session -d -s ict -c /root/ICT-Po3/po3-ict-backtesting 'source .venv/bin/activate && bash scripts/run_full_overnight.sh 2>&1 | tee backtest_logs/ict_full_\$(date -u +%Y%m%dT%H%M%SZ).log; echo EXIT=\$? > backtest_logs/ict_full.exit'"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

# Activate venv if not already active
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

mkdir -p backtest_logs

echo "=============================================="
echo "ICT-Po3 Full Multi-Asset Backtest"
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Commit:  $(git rev-parse --short HEAD)"
echo "=============================================="

# Run all 6 symbols with full diagnostics (no --quick)
# This includes: main strategies + walk-forward + parameter sensitivity
# + monte carlo + cost sensitivity + stress tests
python -u -m backtesting_system.main \
    --symbols EURUSD,GBPUSD,USDJPY,XAUUSD,USA500IDXUSD,USATECHIDXUSD

EXIT_CODE=$?

echo ""
echo "=============================================="
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Exit code: $EXIT_CODE"
echo "=============================================="

exit $EXIT_CODE
