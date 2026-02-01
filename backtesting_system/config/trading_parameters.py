from __future__ import annotations

from datetime import datetime, timezone


START_DATE_CALIBRATION = datetime(2007, 1, 1, tzinfo=timezone.utc)
END_DATE_CALIBRATION = datetime(2020, 12, 31, tzinfo=timezone.utc)

START_DATE_OOS_VALIDATION = datetime(2021, 1, 1, tzinfo=timezone.utc)
END_DATE_OOS_VALIDATION = datetime(2023, 12, 31, tzinfo=timezone.utc)

START_DATE_FORWARD = datetime(2024, 1, 1, tzinfo=timezone.utc)
END_DATE_FORWARD = datetime(2025, 4, 7, tzinfo=timezone.utc)


DEFAULT_PARAMS = {
    "risk_per_trade": 0.01,
    "atr_period": 14,
    "timeframes": ["H1", "H4", "D"],
    "target_multiple": 2.0,
    "slippage_bps": 1.0,
    "spread_bps": 2.0,
    "fee_per_trade": 0.0,
    "stop_slippage_pips": 0.5,
    "require_high_impact_news": True,
    "news_confluence_boost": 0.05,
    "calendar_csv_path": "data/news_calendar/forex_calendar_2007_2025.csv",
}
