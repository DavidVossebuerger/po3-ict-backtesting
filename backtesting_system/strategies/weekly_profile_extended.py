from __future__ import annotations

from backtesting_system.strategies.weekly_profiles import WeeklyProfileStrategy


class WeeklyProfileExtendedStrategy(WeeklyProfileStrategy):
    """Weekly Profile with relaxed Monday filter and extended hold semantics."""

    def __init__(self, params: dict):
        extended = dict(params)
        extended["allow_monday"] = True
        super().__init__(extended)

    def identify_ny_reversal(self, data) -> dict:
        return {}

    def rhrl_protocol(self, daily_candles) -> dict:
        return {}
