from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle
from backtesting_system.strategies.ict_framework import ICTFramework, KillzoneValidator, PDAArrayDetector
from backtesting_system.utils.market_calendar import aggregate_daily_by_ny, ny_date_key


@dataclass
class DailySwingFrameworkStrategy(Strategy):
    """
    ICT Daily Swing Framework Strategy (Blueprint compliant).

    - Reversal when price trades into prior-day wick
    - Continuation when price trades into prior-day 0.25 quadrant
    """

    def __init__(self, params: dict):
        super().__init__(params)
        self.pda_detector = PDAArrayDetector()
        self._stop_helper = ICTFramework(params)
        self.killzone_validator = KillzoneValidator()
        self.enforce_killzones = params.get("enforce_killzones", True)
        # Without a cooldown, this strategy would enter a new position on
        # virtually every H1 bar in a killzone (whenever the prior-day
        # wick condition is met). 24 H1 bars = 1 trading day.
        self._cooldown_bars = int(params.get("daily_swing_cooldown_bars", 24))
        self._last_signal_index = -10_000
        self._daily_cache: Dict[datetime, List[Candle]] = {}
        self._daily_series: List[Candle] = []
        self._last_hist_len: int = 0
        self._last_history_idx: int = -1

    def identify_setup(self, data) -> bool:
        return True

    def identify_daily_swing_framework(self, daily_candles: List[Candle]) -> dict:
        if len(daily_candles) < 2:
            return {"type": "neutral"}

        prev = daily_candles[-2]
        curr = daily_candles[-1]

        prev_wick_high = prev.high
        prev_wick_low = prev.low
        prev_range = prev.high - prev.low
        if prev_range <= 0:
            return {"type": "neutral"}

        prev_upper_quarter = prev.high - (prev_range * 0.25)
        prev_lower_quarter = prev.low + (prev_range * 0.25)

        if curr.low <= prev_wick_low and curr.close > prev_wick_low:
            return {
                "type": "reversal",
                "bias": "long",
                "prev_wick_level": prev_wick_low,
            }
        if curr.high >= prev_wick_high and curr.close < prev_wick_high:
            return {
                "type": "reversal",
                "bias": "short",
                "prev_wick_level": prev_wick_high,
            }

        if prev.close > prev.open:
            if prev_upper_quarter <= curr.low <= prev.high:
                return {
                    "type": "continuation",
                    "bias": "long",
                    "prev_quarter_level": prev_upper_quarter,
                }
        else:
            if prev.low <= curr.high <= prev_lower_quarter:
                return {
                    "type": "continuation",
                    "bias": "short",
                    "prev_quarter_level": prev_lower_quarter,
                }

        return {"type": "neutral"}

    def generate_signals(self, data) -> dict:
        history: List[Candle] = data.get("history", [])
        if len(history) < 50:
            return {}

        bar = data["bar"]
        symbol = data.get("symbol", "")
        bar_index = len(history)
        if bar_index - self._last_signal_index < self._cooldown_bars:
            return {}
        if self.enforce_killzones and not self.killzone_validator.is_valid_killzone(bar.time):
            return {}
        daily_candles = self._aggregate_daily(history)
        framework = self.identify_daily_swing_framework(daily_candles)
        if framework.get("type") == "neutral":
            return {}

        h1_arrays = {
            "fvgs": self.pda_detector.identify_fair_value_gaps(history[-50:], pip_size=self.get_pip_size(symbol)),
            "order_blocks": self.pda_detector.identify_order_blocks(history[-50:]),
            "breakers": self._stop_helper.identify_breaker_blocks(history[-50:]),
        }
        entry_ok, pda_type = self.pda_detector.validate_entry_at_pda(
            bar.close,
            h1_arrays,
            pip_size=self.get_pip_size(symbol),
        )
        if not entry_ok:
            return {}

        direction = framework.get("bias", "long")
        entry = bar.close
        stop = self._stop_helper.calculate_stop_loss(direction, entry, h1_arrays, daily_candles, symbol=symbol)

        if len(daily_candles) >= 2:
            prev = daily_candles[-2]
            target = prev.high if direction == "long" else prev.low
        else:
            target = self.project_target(entry, stop, direction)

        # Block further entries for the configured cooldown. Set here (and
        # not at risk-check time) so it is enforced regardless of whether
        # the engine actually opens the position.
        self._last_signal_index = bar_index
        return {
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "framework_type": framework.get("type"),
            "pda_type": pda_type,
        }

    def validate_context(self, data) -> bool:
        return True

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
