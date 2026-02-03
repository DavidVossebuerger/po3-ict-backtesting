from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle
from backtesting_system.strategies.ict_framework import ICTFramework, PDAArrayDetector


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
        self._daily_cache: Dict[datetime, List[Candle]] = {}
        self._daily_series: List[Candle] = []
        self._last_hist_len: int = 0

    def identify_setup(self, data) -> bool:
        return True

    def identify_daily_swing_framework(self, daily_candles: List[Candle]) -> dict:
        if len(daily_candles) < 2:
            return {"type": "neutral"}

        prev = daily_candles[-2]
        curr = daily_candles[-1]

        prev_body_high = max(prev.open, prev.close)
        prev_body_low = min(prev.open, prev.close)
        prev_range = prev.high - prev.low
        if prev_range <= 0:
            return {"type": "neutral"}

        prev_upper_quarter = prev.high - (prev_range * 0.25)
        prev_lower_quarter = prev.low + (prev_range * 0.25)

        if curr.low <= prev_body_low and curr.close > prev_body_low:
            return {
                "type": "reversal",
                "bias": "long",
                "prev_wick_level": prev_body_low,
            }
        if curr.high >= prev_body_high and curr.close < prev_body_high:
            return {
                "type": "reversal",
                "bias": "short",
                "prev_wick_level": prev_body_high,
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
        daily_candles = self._aggregate_daily(history)
        framework = self.identify_daily_swing_framework(daily_candles)
        if framework.get("type") == "neutral":
            return {}

        h1_arrays = {
            "fvgs": self.pda_detector.identify_fair_value_gaps(history[-50:]),
            "order_blocks": self.pda_detector.identify_order_blocks(history[-50:]),
            "breakers": self._stop_helper.identify_breaker_blocks(history[-50:]),
        }
        entry_ok, pda_type = self.pda_detector.validate_entry_at_pda(bar.close, h1_arrays)
        if not entry_ok:
            return {}

        direction = framework.get("bias", "long")
        entry = bar.close
        stop = self._stop_helper.calculate_stop_loss(direction, entry, h1_arrays, daily_candles)

        if len(daily_candles) >= 2:
            prev = daily_candles[-2]
            target = prev.high if direction == "long" else prev.low
        else:
            target = self.project_target(entry, stop, direction)

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
