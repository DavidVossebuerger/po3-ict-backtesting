#!/usr/bin/env bash
# Quick health check: how far has the multi-asset backtest gotten?
#
# Usage:
#   ./scripts/check_status.sh
#
# Reads the most recent log file in backtest_logs/ and prints the
# last few summary lines plus a per-symbol progress table.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG_DIR="$REPO_DIR/backtest_logs"
LATEST="$(ls -t "$LOG_DIR"/po3_*.log 2>/dev/null | head -1 || true)"

if [ -z "$LATEST" ]; then
  echo "No log file found in $LOG_DIR. Start the backtest first:"
  echo "    ./scripts/run_in_tmux.sh all"
  exit 1
fi

echo "Latest log: $LATEST"
echo "Size:       $(du -h "$LATEST" | cut -f1)"
echo "Last mod:   $(stat -c '%y' "$LATEST" 2>/dev/null || stat -f '%Sm' "$LATEST")"
echo "Exit file:  $(cat "$LATEST.exit" 2>/dev/null || echo 'in progress')"
echo
echo "--- Tail of log ---"
tail -30 "$LATEST"

echo
echo "--- Progress (per-strategy lines) ---"
grep -E "progress \[" "$LATEST" 2>/dev/null | tail -8 || echo "  (no progress lines yet)"

echo
echo "--- Per-symbol progress ---"
grep -E "Symbol .* done in" "$LATEST" 2>/dev/null | tail -6 || echo "  (no symbols done yet)"

if grep -qE "multi-asset progress [0-9]+/[0-9]+" "$LATEST" 2>/dev/null; then
  echo
  echo "--- Multi-asset ETA ---"
  grep -E "multi-asset progress [0-9]+/[0-9]+" "$LATEST" | tail -1
fi

if command -v tmux >/dev/null && tmux has-session -t po3 2>/dev/null; then
  echo
  echo "--- tmux session 'po3' is RUNNING ---"
  echo "Re-attach with:  tmux attach -t po3"
fi

echo
echo "--- Per-symbol reports so far ---"
for d in "$REPO_DIR/results" "$REPO_DIR/results/multi_asset"/*; do
  [ -d "$d" ] || continue
  sym="$(basename "$d")"
  [ -f "$d/summary.csv" ] && {
    echo
    echo "== $sym =="
    head -1 "$d/summary.csv" 2>/dev/null
    tail -n +2 "$d/summary.csv" 2>/dev/null | head -8 | awk -F, '{
      printf "  %-32s trades=%-4s final=%-10s pf=%s\n", $1, $2, $3, $4
    }'
  }
done
