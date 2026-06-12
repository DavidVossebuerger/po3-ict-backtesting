#!/usr/bin/env bash
# Setup script for Ubuntu Server 22.04 / 24.04
# Idempotent: safe to re-run.

set -euo pipefail

REPO_URL="https://github.com/DavidVossebuerger/po3-ict-backtesting.git"
INSTALL_DIR="${PO3_DIR:-$HOME/ICT-Po3/po3-ict-backtesting}"
# Use whatever Python 3.10+ is available on the system. On Ubuntu
# 22.04 the default is 3.10, on 24.04 (noble) it's 3.12, on older LTS
# it might be 3.8/3.9. We need >= 3.10 for the match-statement-style
# type hints used in the codebase.
PYTHON_BIN="$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)"
if [ -z "$PYTHON_BIN" ]; then
  die "No python3 ≥ 3.10 found on PATH."
fi
PY_MINOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')"
PY_MAJOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  die "Found $PY_BIN with version $PY_MAJOR.$PY_MINOR; need >= 3.10."
fi
PYTHON_VERSION="$PY_MAJOR.$PY_MINOR"

say() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERR\033[0m %s\n' "$*" >&2; exit 1; }

# --- 1. System packages
say "Installing system packages (git, python3-venv, tmux)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  # Try to install python3.x-venv for the resolved version. Fall back
  # to python3-venv (the meta-package) if the specific version isn't
  # packaged in this Ubuntu release.
  if ! sudo apt-get install -y git "python${PYTHON_VERSION}-venv" tmux ca-certificates 2>/dev/null; then
    say "python${PYTHON_VERSION}-venv not packaged; trying python3-venv..."
    sudo apt-get install -y git python3-venv tmux ca-certificates
  fi
else
  die "apt-get not found. This script targets Ubuntu/Debian."
fi

# --- 2. Clone or update the repo
if [ ! -d "$INSTALL_DIR" ]; then
  say "Cloning $REPO_URL into $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
else
  say "Repo already at $INSTALL_DIR; pulling latest..."
  (cd "$INSTALL_DIR" && git pull --ff-only)
fi

# --- 3. Python virtualenv
say "Creating virtualenv at $INSTALL_DIR/.venv using $(basename "$PYTHON_BIN") ..."
"$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv"
# shellcheck disable=SC1091
source "$INSTALL_DIR/.venv/bin/activate"
pip install --upgrade pip wheel setuptools
pip install -r "$INSTALL_DIR/requirements.txt"

# --- 4. Macro calendar (regenerate, idempotent)
say "Regenerating macro calendar at data/news_calendar/macro_calendar_2011_2026.csv ..."
mkdir -p "$INSTALL_DIR/data/news_calendar"
"$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/scripts/generate_macro_calendar.py"

# --- 5. dukascopy_data (not in repo due to size — must be placed manually)
#       We probe the most likely locations and tell the user what to do
#       if none of them is present.
FOUND_DD=""
for candidate in \
  "$INSTALL_DIR/../dukascopy_data" \
  "$INSTALL_DIR/dukascopy_data" \
  "$HOME/dukascopy_data" \
  "/data/dukascopy_data"; do
  if [ -d "$candidate" ]; then
    FOUND_DD="$candidate"
    break
  fi
done
if [ -z "$FOUND_DD" ]; then
  say "dukascopy_data/ is not present yet. Place it in one of:"
  say "  $INSTALL_DIR/../dukascopy_data/"
  say "  $HOME/dukascopy_data/"
  say "The loader also tries \$HOME/dukascopy_data as a fallback."
else
  say "Found dukascopy_data at $FOUND_DD"
fi

# --- 6. Smoke test (data only, no full backtest)
say "Smoke test: load each symbol from dukascopy_data ..."
DD_DIR="\${FOUND_DD:-\$HOME/dukascopy_data}"
"$INSTALL_DIR/.venv/bin/python" -c "
import sys
from pathlib import Path
sys.path.insert(0, '$INSTALL_DIR')
from backtesting_system.adapters.data_sources.csv_source import CSVDataSource
ds = CSVDataSource(base_path=Path('$FOUND_DD') if '$FOUND_DD' else Path.home()/'dukascopy_data', file_map={})
for sym in ['GBPUSD','USDJPY','XAUUSD','USA500IDXUSD','USATECHIDXUSD']:
    c = ds.load_ohlcv(sym, 'M30', None, None)
    if c:
        print(f'  {sym}: {len(c):>7} bars ({c[0].time.date()} -> {c[-1].time.date()})')
    else:
        print(f'  {sym}: 0 bars')
"

cat <<'EOF'

================================================================
Setup complete. To run the multi-asset backtest in tmux:

    cd "$HOME/po3-ict-backtesting"
    ./scripts/run_in_tmux.sh all           # all 6 symbols (slow)
    ./scripts/run_in_tmux.sh eurusd       # one symbol (faster)
    ./scripts/run_in_tmux.sh "eurusd,xauusd"  # custom subset

The runner writes to results/ and results/multi_asset/<SYM>/.
Tail the log with:   tmux attach -t po3
================================================================
EOF
