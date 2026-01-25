from __future__ import annotations

from typing import Protocol

from backtesting_system.models.orders import Position


class RiskModel(Protocol):
    def size_position(self, account_size: float, entry: float, stop: float) -> float:
        ...

    def apply_trade_rules(self, position: Position) -> Position:
        ...
