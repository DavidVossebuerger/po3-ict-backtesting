from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy


class BuyHoldStrategy(Strategy):
    """One-position-long benchmark. ``stop`` is set far enough OTM that it
    never gets hit on the test window; ``target`` is None so the engine
    will only close on stop (or backtest end via risk manager). The signal
    is also marked with ``partial_exit_blocked=True`` so the engine will
    not split the position at 1R."""

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
            # -50% stop keeps the position open through any single-year
            # move in our universe. It is intentionally unreachable.
            "stop": bar.close * 0.50,
            "target": None,
            "size": 1.0,
            "partial_exit_blocked": True,
        }

    def validate_context(self, data) -> bool:
        return True
