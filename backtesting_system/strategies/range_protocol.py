from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle


@dataclass
class RangeHighRangeLowStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self._daily_cache: Dict[datetime, List[Candle]] = {}
        self._daily_series: List[Candle] = []
        self._last_hist_len: int = 0
        self._current_week_key: tuple | None = None
        self._current_week_key_level: float | None = None

    def identify_setup(self, data) -> bool:
        return True

    def generate_signals(self, data) -> dict:
        bar = data["bar"]
        history: List[Candle] = data.get("history", [])
        if not history:
            return {}

        daily = self._aggregate_daily(history)
        current_week = self._week_key(bar.time)
        if self._current_week_key != current_week:
            self._current_week_key = current_week
            self._current_week_key_level = None

        day = bar.time.weekday()
        if day <= 2:
            self._current_week_key_level = self._identify_key_level(daily)
            return {}

        if self._current_week_key_level is None:
            return {}

        range_high, range_low = self._get_current_range(daily, current_week)
        if range_high is None or range_low is None:
            return {}

        pip_buffer = 0.0001 * 10
        if bar.low <= range_low:
            stop = range_low - pip_buffer
            target = range_high
            return {
                "direction": "long",
                "entry": bar.close,
                "stop": stop,
                "target": target,
                "confluence": 0.85,
            }
        if bar.high >= range_high:
            stop = range_high + pip_buffer
            target = range_low
            return {
                "direction": "short",
                "entry": bar.close,
                "stop": stop,
                "target": target,
                "confluence": 0.85,
            }
        return {}

    def validate_context(self, data) -> bool:
        return True

    def _identify_key_level(self, daily: List[Candle]) -> float | None:
        if len(daily) < 5:
            return None
        prev_week = self._previous_week_key(self._week_key(daily[-1].time))
        prev_week_candles = [c for c in daily if self._week_key(c.time) == prev_week]
        if not prev_week_candles:
            return None
        prev_high = max(c.high for c in prev_week_candles)
        prev_low = min(c.low for c in prev_week_candles)
        return (prev_high + prev_low) / 2

    def _get_current_range(self, daily: List[Candle], week_key: tuple) -> tuple[float | None, float | None]:
        current_week = [c for c in daily if self._week_key(c.time) == week_key]
        if len(current_week) < 2:
            return None, None
        return max(c.high for c in current_week), min(c.low for c in current_week)

    def _aggregate_daily(self, history: List[Candle]) -> List[Candle]:
        if not history:
            return []
        if len(history) == self._last_hist_len:
            return self._daily_series

        for candle in history[self._last_hist_len :]:
            day_key = datetime(
                candle.time.year,
                candle.time.month,
                candle.time.day,
                tzinfo=timezone.utc,
            )
            self._daily_cache.setdefault(day_key, []).append(candle)
        self._last_hist_len = len(history)

        result: List[Candle] = []
        for day in sorted(self._daily_cache.keys()):
            chunk = self._daily_cache[day]
            result.append(
                Candle(
                    time=day,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=None,
                )
            )
        self._daily_series = result
        return result

    def _week_key(self, dt: datetime) -> tuple:
        iso = dt.isocalendar()
        return iso.year, iso.week

    def _previous_week_key(self, week_key: tuple) -> tuple:
        year, week = week_key
        if week > 1:
            return year, week - 1
        return year - 1, 52
