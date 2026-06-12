#!/usr/bin/env bash
# Run the multi-asset backtest inside a tmux session.
#
# Usage:
#   ./scripts/run_in_tmux.sh                 # default: all 6 symbols
#   ./scripts/run_in_tmux.sh eurusd          # one symbol
#   ./scripts/run_in_tmux.sh "eurusd,xauusd" # comma-separated subset
#   ./scripts/run_in_tmux.sh eurusd --quick  # forward flags to main.py
#
# Attaches to the session at the end so you can watch live progress
# (Ctrl-B D to detach without killing the backtest).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SYMS="${1:-all}"
shift || true
EXTRA_FLAGS=("$@")

if [ "$SYMS" = "all" ]; then
  SYMS="EURUSD,GBPUSD,USDJPY,XAUUSD,USA500IDXUSD,USATECHIDXUSD"
fi

SESSION="po3"
LOG_DIR="$REPO_DIR/backtest_logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/po3_${SYMS//,/_}_${STAMP}.log"

# Reuse the existing session if one is already running for this
# script. Otherwise create a fresh one.
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already exists; attaching."
  tmux attach -t "$SESSION"
  exit 0
fi

cd "$REPO_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate

CMD=(python -u -m backtesting_system.main --symbols "$SYMS" "${EXTRA_FLAGS[@]}")
echo "Launching: ${CMD[*]}"
echo "Log: $LOG_FILE"

tmux new-session -d -s "$SESSION" -c "$REPO_DIR" \
  "${CMD[*]} 2>&1 | tee '$LOG_FILE'; echo EXIT_STATUS=\$? > '$LOG_FILE.exit'"

echo "Session '$SESSION' started. Attaching now."
tmux attach -t "$SESSION"
