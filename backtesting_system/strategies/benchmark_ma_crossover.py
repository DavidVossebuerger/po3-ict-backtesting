from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy


class MovingAverageCrossoverStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.fast_window = int(params.get("ma_fast", 20))
        self.slow_window = int(params.get("ma_slow", 50))
        self.stop_pct = float(params.get("ma_stop_pct", 0.002))
        self.target_multiple = float(params.get("ma_target_multiple", params.get("target_multiple", 2.0)))
        self._last_signal_index = -10_000
        self._cooldown_bars = int(params.get("ma_cooldown_bars", 1))

    def identify_setup(self, data) -> bool:
        return True

    def generate_signals(self, data) -> dict:
        history = data.get("history", [])
        bar = data["bar"]
        bar_index = len(history)
        if bar_index - self._last_signal_index < self._cooldown_bars:
            return {}

        closes = [c.close for c in history]
        if len(closes) < self.slow_window + 1:
            return {}

        fast_prev = sum(closes[-self.fast_window - 1 : -1]) / self.fast_window
        fast_curr = sum(closes[-self.fast_window :]) / self.fast_window
        slow_prev = sum(closes[-self.slow_window - 1 : -1]) / self.slow_window
        slow_curr = sum(closes[-self.slow_window :]) / self.slow_window

        direction = None
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            direction = "long"
        elif fast_prev >= slow_prev and fast_curr < slow_curr:
            direction = "short"

        if direction is None:
            return {}

        entry = bar.close
        stop_distance = entry * self.stop_pct
        if stop_distance <= 0:
            return {}
        stop = entry - stop_distance if direction == "long" else entry + stop_distance
        target = self.project_target(entry, stop, direction, multiple=self.target_multiple)

        self._last_signal_index = bar_index
        return {
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "size": None,
        }

    def validate_context(self, data) -> bool:
        return True
