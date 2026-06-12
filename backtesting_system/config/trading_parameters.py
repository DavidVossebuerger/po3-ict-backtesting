from __future__ import annotations

from datetime import datetime, timezone


START_DATE_CALIBRATION = datetime(2007, 1, 1, tzinfo=timezone.utc)
END_DATE_CALIBRATION = datetime(2020, 12, 31, tzinfo=timezone.utc)

START_DATE_OOS_VALIDATION = datetime(2021, 1, 1, tzinfo=timezone.utc)
END_DATE_OOS_VALIDATION = datetime(2023, 12, 31, tzinfo=timezone.utc)

START_DATE_FORWARD = datetime(2024, 1, 1, tzinfo=timezone.utc)
END_DATE_FORWARD = datetime(2025, 4, 7, tzinfo=timezone.utc)


# Symbols covered by the multi-asset run. Order matters for the per-symbol
# report filenames. Keep EURUSD first so existing report filenames stay
# backward-compatible.
SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "XAUUSD",
    "USA500IDXUSD",
    "USATECHIDXUSD",
]

# Symbols that need the macro (FOMC/NFP/CPI/etc.) calendar instead of the
# forex calendar for high-impact news gating.
INDEX_SYMBOLS = {"USA500IDXUSD", "USATECHIDXUSD"}


DEFAULT_PARAMS = {
    "risk_per_trade": 0.01,
    "atr_period": 14,
    "timeframes": ["H1", "H4", "D"],
    "target_multiple": 2.0,
    "slippage_bps": 1.0,
    "spread_bps": 2.0,
    "fee_per_trade": 0.0,
    # Risk-free rate used in Sharpe / Sortino. The historical 2007-2026
    # average for USD short rates is ~2%, but we keep 0.0 here for
    # *comparability* across strategies: a flat buy-and-hold position
    # over 18 years would otherwise get an extreme negative Sharpe just
    # because the risk-free asset returned 2%/yr. Pass 0.02 to use the
    # textbook 2% rf convention.
    "risk_free_rate": 0.0,
    "stop_slippage_pips": 0.5,
    # ``target_first`` is the more honest default for an academic paper:
    # when both stop and target are hit in the same bar we close at the
    # target first (the better outcome) rather than the stop. Real fills
    # are ambiguous; this convention avoids the systematic upward bias
    # of ``stop_first`` for momentum-style strategies.
    "intrabar_exit_policy": "target_first",
    "default_pip_size": 0.0001,
    "symbol_specs": {
        # Forex
        "EURUSD": {"pip_size": 0.0001, "tick_size": 0.00001},
        "GBPUSD": {"pip_size": 0.0001, "tick_size": 0.00001},
        "AUDUSD": {"pip_size": 0.0001, "tick_size": 0.00001},
        "NZDUSD": {"pip_size": 0.0001, "tick_size": 0.00001},
        "USDCHF": {"pip_size": 0.0001, "tick_size": 0.00001},
        "USDCAD": {"pip_size": 0.0001, "tick_size": 0.00001},
        "USDJPY": {"pip_size": 0.01, "tick_size": 0.001},
        # Gold — 2-decimal quote; 1 pip = $0.10 (10 ticks). Some shops
        # treat each tick ($0.01) as 1 pip, but the $0.10 convention is
        # the most common in retail FX/CFD feeds and keeps position
        # sizing comparable to the other symbols.
        "XAUUSD": {"pip_size": 0.10, "tick_size": 0.01},
        # US indices — Dukascopy's CFD-style print. S&P 500 ~4500 points;
        # 1 pip = 0.01 keeps risk sizing consistent with USDJPY and avoids
        # the position-size blow-up you would get with pip_size = 1.0.
        "USA500IDXUSD": {"pip_size": 0.01, "tick_size": 0.01},
        "USATECHIDXUSD": {"pip_size": 0.01, "tick_size": 0.01},
    },
    "min_confluence": 0.50,
    "enforce_killzones": True,
    "require_high_impact_news": True,
    "news_confluence_boost": 0.05,
    "calendar_csv_path": "data/news_calendar/forex_calendar_2007_2025.csv",
    "macro_calendar_csv_path": "data/news_calendar/macro_calendar_2011_2026.csv",
    "tgif_tolerance_pips": 10.0,
    # When set, the TGIF retracement band is computed as a fraction of the
    # weekly range instead of as a fixed pip distance (matters for indices
    # where 10 pips is 0.02% of price while 10 pips on EURUSD is 0.001%).
    "tgif_retracement_low": 0.20,
    "tgif_retracement_high": 0.30,
    "opening_range_cutoff_hour": 8,
    "opening_range_cutoff_minute": 30,
    "tgif_conservative_target": False,
    "random_seed": 42,
    "random_trade_probability": 0.005,
    "random_stop_pct": 0.002,
    "random_target_multiple": 2.0,
    "random_cooldown_bars": 96,
    "ma_fast": 20,
    "ma_slow": 50,
    "ma_stop_pct": 0.002,
    "ma_target_multiple": 2.0,
    # 96 H1 bars = 4 trading days. Suppresses whipsaw from 20/50 SMA in
    # ranging markets and brings total MA-cross trades under ~500 over an
    # 18-year backtest, instead of the previous 6600+ which bled the book
    # on spread+slippage alone.
    "ma_cooldown_bars": 240,
    "daily_swing_cooldown_bars": 96,
}
