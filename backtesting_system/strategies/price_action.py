from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy


class PriceActionStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        raise RuntimeError(
            "PriceActionStrategy is deprecated and not ICT-compliant. "
            "Use DailySwingFrameworkStrategy or ICT-based strategies instead."
        )

    def identify_setup(self, data) -> bool:
        return False

    def generate_signals(self, data) -> dict:
        return {}

    def validate_context(self, data) -> bool:
        return False
