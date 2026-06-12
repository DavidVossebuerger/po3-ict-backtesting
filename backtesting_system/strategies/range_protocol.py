from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle
from backtesting_system.strategies.ict_framework import KillzoneValidator
from backtesting_system.utils.market_calendar import aggregate_daily_by_ny, ny_date_key, ny_week_key, ny_weekday


@dataclass
class RangeHighRangeLowStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.killzone_validator = KillzoneValidator()
        self.enforce_killzones = params.get("enforce_killzones", True)
        self._daily_cache: Dict[datetime, List[Candle]] = {}
        self._daily_series: List[Candle] = []
        self._last_hist_len: int = 0
        self._last_history_idx: int = -1
        self._current_week_key: tuple | None = None
        self._current_week_key_level: float | None = None
        self._last_signal_week: tuple | None = None
        self._state: dict = {}

    def identify_setup(self, data) -> bool:
        return True

    def generate_signals(self, data) -> dict:
        bar = data["bar"]
        symbol = data.get("symbol", "")
        history: List[Candle] = data.get("history", [])
        if not history:
            return {}
        if self.enforce_killzones and not self.killzone_validator.is_valid_killzone(bar.time):
            return {}

        daily = self._aggregate_daily(history)
        current_week = self._week_key(bar.time)
        if self._current_week_key != current_week:
            self._current_week_key = current_week
            self._current_week_key_level = None
            self._state = {
                "key_level_met": False,
                "range_defined": False,
                "range_high": None,
                "range_low": None,
                "manipulation_direction": None,
                "manipulation_extreme": None,
            }

        if self._last_signal_week == current_week:
            return {}

        day = ny_weekday(bar.time)
        if day <= 2:
            self._current_week_key_level = self._identify_key_level(daily)
            if self._current_week_key_level is not None and bar.low <= self._current_week_key_level <= bar.high:
                self._state["key_level_met"] = True
            return {}

        if self._current_week_key_level is None or not self._state.get("key_level_met"):
            return {}

        if not self._state.get("range_defined"):
            setup_candles = [
                c
                for c in daily
                if self._week_key(c.time) == current_week and ny_weekday(c.time) <= 2
            ]
            if len(setup_candles) < 2:
                return {}
            self._state["range_high"] = max(c.high for c in setup_candles)
            self._state["range_low"] = min(c.low for c in setup_candles)
            self._state["range_defined"] = True

        range_high = self._state.get("range_high")
        range_low = self._state.get("range_low")
        if range_high is None or range_low is None:
            return {}

        day_open = self._day_open(history, bar)
        if day_open is None or not (range_low <= day_open <= range_high):
            return {}

        pip_buffer = self.pips_to_price(10.0, symbol)

        manipulation_direction = self._state.get("manipulation_direction")
        manipulation_extreme = self._state.get("manipulation_extreme")
        if manipulation_direction is None:
            if bar.low < range_low and bar.close > range_low:
                self._state["manipulation_direction"] = "long"
                self._state["manipulation_extreme"] = bar.low
                return {}
            if bar.high > range_high and bar.close < range_high:
                self._state["manipulation_direction"] = "short"
                self._state["manipulation_extreme"] = bar.high
                return {}
            return {}

        if manipulation_direction == "long":
            if bar.close <= bar.open or bar.close <= range_low:
                return {}
            stop_anchor = min(manipulation_extreme if manipulation_extreme is not None else range_low, range_low)
            signal = {
                "direction": "long",
                "entry": bar.close,
                "stop": stop_anchor - pip_buffer,
                "target": range_high,
                "confluence": 0.85,
            }
            self._last_signal_week = current_week
            return signal

        if bar.close >= bar.open or bar.close >= range_high:
            return {}
        stop_anchor = max(manipulation_extreme if manipulation_extreme is not None else range_high, range_high)
        signal = {
            "direction": "short",
            "entry": bar.close,
            "stop": stop_anchor + pip_buffer,
            "target": range_low,
            "confluence": 0.85,
        }
        self._last_signal_week = current_week
        return signal

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

    def _day_open(self, history: List[Candle], bar: Candle) -> float | None:
        day_candles = [c for c in history if c.time.date() == bar.time.date()]
        if not day_candles:
            return None
        return day_candles[0].open

    def _aggregate_daily(self, history: List[Candle]) -> List[Candle]:
        """Return the daily NY-time candles for ``history``.

        Index-tracking O(n) pattern:
        cache the aggregated series and only walk the new tail. Bars
        for the same NY trading day are merged into the existing tail
        candle (updating high/low/close) rather than appended as
        duplicates.
        """
        if not history:
            return []
        if self._last_history_idx >= len(history) - 1:
            return self._daily_series
        start = self._last_history_idx + 1
        new_buckets: dict[tuple, list] = {}
        for candle in history[start:]:
            d = ny_date_key(candle.time)
            new_buckets.setdefault(d, []).append(candle)
        # Merge same-day bars into the existing tail candle so we don't
        # append a duplicate when the NY day has not rolled over.
        if self._daily_series and new_buckets:
            tail_day = (
                self._daily_series[-1].time.year,
                self._daily_series[-1].time.month,
                self._daily_series[-1].time.day,
            )
            if tail_day in new_buckets:
                extras = new_buckets.pop(tail_day)
                last = self._daily_series[-1]
                self._daily_series[-1] = Candle(
                    time=last.time,
                    open=last.open,
                    high=max(last.high, max(c.high for c in extras)),
                    low=min(last.low, min(c.low for c in extras)),
                    close=extras[-1].close,
                    volume=None,
                )
        self._last_history_idx = len(history) - 1
        for d in sorted(new_buckets.keys()):
            chunk = sorted(new_buckets[d], key=lambda c: c.time)
            if not chunk:
                continue
            self._daily_series.append(
                Candle(
                    time=datetime(d[0], d[1], d[2], tzinfo=timezone.utc),
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=None,
                )
            )
        return self._daily_series

    def _week_key(self, dt: datetime) -> tuple:
        return ny_week_key(dt)

    def _previous_week_key(self, week_key: tuple) -> tuple:
        year, week = week_key
        if week > 1:
            return year, week - 1
        return year - 1, 52
