# PO3 ICT Backtesting Framework
[![SSRN](https://img.shields.io/badge/SSRN-German-blue?logo=ssrn&logoColor=white)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6410578)
[![SSRN](https://img.shields.io/badge/SSRN-English-blue?logo=ssrn&logoColor=white)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6700099)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

A modular Python backtesting framework for the empirical evaluation of ICT (Inner Circle Trader) / PO3 trading strategies. The project translates discretionary ICT concepts — killzones, fair value gaps, order blocks, breaker blocks, CISD — into deterministic, reproducible algorithms and tests them across six instruments over 18 years of M30 data.

**Key finding:** Across all six instruments and 108 parameter configurations, no combination produces a positive risk-adjusted return under realistic retail transaction costs.

## Instruments

| Symbol | Type | Data Source |
|--------|------|------------|
| EURUSD | Forex Major | Dukascopy M30 bid |
| GBPUSD | Forex Major | Dukascopy M30 bid |
| USDJPY | Forex Major | Dukascopy M30 bid |
| XAUUSD | Gold | Dukascopy M30 bid |
| USA500IDXUSD | S&P 500 CFD | Dukascopy M30 bid |
| USATECHIDXUSD | Nasdaq CFD | Dukascopy M30 bid |

## Strategies

- **Daily Swing Framework** — Primary strategy. Reversal/continuation signals based on prior-day wick levels, gated by PDA confluence (FVG, Order Block, Breaker) and killzone filters.
- **Composite** — Signal aggregator combining daily-swing signals with an ICT confluence scorer.
- **Buy & Hold, MA Crossover, Random Baseline** — Benchmark strategies for comparison.

## Diagnostics

The pipeline runs the following per-symbol diagnostics (unless `--quick`):

| Diagnostic | Scope | Output |
|---|---|---|
| Main strategies (5) | Full period + per-phase | `report_*.json`, `trades_*.csv` |
| Walk-forward (7 windows) | OOS phase 2021–2023 | `walk_forward.json` |
| Parameter sensitivity (18 configs) | Full period | `parameter_sensitivity.json` |
| Cost sensitivity (3 scenarios) | Full period | `cost_sensitivity.json` |
| Monte Carlo (1000 iterations) | EURUSD trades | `monte_carlo.json` |
| Stress tests (3 scenarios) | EURUSD sub-windows | `stress_tests.json` |
| Phase comparison | Cal / OOS / Forward | `daily_swing_phase_comparison.json` |
| Statistical tests | vs. Buy & Hold | `statistical_tests.json` |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/DavidVossebuerger/po3-ict-backtesting.git
cd po3-ict-backtesting
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Single-asset quick run (no heavy diagnostics)
python -m backtesting_system.main --symbols EURUSD --quick

# Full multi-asset run (all diagnostics, ~3h on 4-core VPS)
python -m backtesting_system.main --symbols EURUSD,GBPUSD,USDJPY,XAUUSD,USA500IDXUSD,USATECHIDXUSD

# Overnight VPS run (tmux)
bash scripts/run_full_overnight.sh
```

## Data Requirements

- `data/raw/eurusd-m30-bid-*.csv` — EURUSD M30 (included)
- `dukascopy_data/*.csv` — Other symbols (quarterly M30 bid files from Dukascopy)
- `data/news_calendar/forex_calendar_2007_2025.csv` — Forex news calendar
- `data/news_calendar/macro_calendar_2011_2026.csv` — Macro calendar for indices

## Output Structure

```
results/
├── report_*.json              # Per-strategy reports (EURUSD)
├── walk_forward.json          # Walk-forward results
├── parameter_sensitivity.json # Parameter grid results
├── cost_sensitivity.json      # Cost scenario comparison
├── monte_carlo.json           # MC resampling results
├── daily_swing_phase_comparison.json
├── statistical_tests.json
├── multi_asset_validation.json
├── multi_asset/
│   ├── GBPUSD/                # Same structure per symbol
│   ├── USDJPY/
│   ├── XAUUSD/
│   ├── USA500IDXUSD/
│   └── USATECHIDXUSD/
└── resampled/                 # H1/H4/D resampled CSVs
```

## Scripts

- `scripts/run_full_overnight.sh` — Full multi-asset run with logging
- `scripts/compute_dsr.py` — Deflated Sharpe Ratio calculation
- `scripts/generate_macro_calendar.py` — Regenerate macro news calendar

## Configuration

All parameters are defined in `backtesting_system/config/trading_parameters.py`:

- **Backtest windows:** Calibration 2007–2020, OOS 2021–2023, Forward 2024–2025
- **Risk per trade:** 1% (default), tested at 0.5% / 1% / 2%
- **Cost model:** Spread 2 bps, slippage 1 bps (retail); 2.5 + 2.5 bps (conservative)
- **Intrabar exit:** `target_first` (favorable fill assumption)
- **Ruin stop:** Enabled, floor at 0 EUR

## License

MIT License. See [LICENSE](LICENSE).

## Disclaimer

For educational and research purposes only. Not financial advice. The implementation of ICT concepts is based on public interpretations and does not claim to represent the definitive or official methodology.
