from __future__ import annotations

import random
from datetime import date

from backtesting_system.core.strategy_base import Strategy


class RandomBaselineStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        seed = params.get("random_seed", 42)
        self._rng = random.Random(seed)
        self.trade_probability = float(params.get("random_trade_probability", 0.02))
        self.stop_pct = float(params.get("random_stop_pct", 0.002))
        self.target_multiple = float(params.get("random_target_multiple", params.get("target_multiple", 2.0)))
        self.cooldown_bars = int(params.get("random_cooldown_bars", 24))
        self._last_entry_index = -10_000
        self._last_signal_day: date | None = None

    def identify_setup(self, data) -> bool:
        return True

    def generate_signals(self, data) -> dict:
        history = data.get("history", [])
        bar = data["bar"]
        bar_index = len(history)
        if bar_index - self._last_entry_index < self.cooldown_bars:
            return {}
        if self._last_signal_day == bar.time.date():
            return {}
        if self._rng.random() > self.trade_probability:
            return {}

        direction = "long" if self._rng.random() >= 0.5 else "short"
        entry = bar.close
        stop_distance = entry * self.stop_pct
        if stop_distance <= 0:
            return {}
        stop = entry - stop_distance if direction == "long" else entry + stop_distance
        target = self.project_target(entry, stop, direction, multiple=self.target_multiple)

        self._last_entry_index = bar_index
        self._last_signal_day = bar.time.date()
        return {
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "size": None,
        }

    def validate_context(self, data) -> bool:
        return True
