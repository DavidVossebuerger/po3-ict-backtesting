from __future__ import annotations

from typing import Protocol

from backtesting_system.models.orders import Order, Fill


class ExecutionBroker(Protocol):
    def place_order(self, order: Order) -> str:
        ...

    def cancel_order(self, order_id: str) -> None:
        ...

    def fetch_fills(self) -> list[Fill]:
        ...
