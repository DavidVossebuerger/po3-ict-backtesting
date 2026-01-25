from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy


class BuyHoldStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self._entered = False

    def identify_setup(self, data) -> bool:
        return not self._entered

    def generate_signals(self, data) -> dict:
        if self._entered:
            return {}
        bar = data["bar"]
        self._entered = True
        return {
            "direction": "long",
            "entry": bar.close,
            "stop": bar.close * 0.95,
            "target": None,
            "size": 1.0,
        }

    def validate_context(self, data) -> bool:
        return True
