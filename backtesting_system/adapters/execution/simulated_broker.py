from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from backtesting_system.interfaces.execution import ExecutionBroker
from backtesting_system.models.orders import Fill, Order, OrderSide


@dataclass
class SimulatedBroker(ExecutionBroker):
    slippage_bps: float = 0.0
    fee_per_trade: float = 0.0
    spread_bps: float = 0.0
    _fills: List[Fill] = field(default_factory=list)

    def place_order(self, order: Order) -> str:
        fill_price = order.limit_price or order.stop_price
        if fill_price is None:
            raise ValueError("Market order requires limit_price for fill simulation.")

        slippage = fill_price * (self.slippage_bps / 10000.0)
        spread = fill_price * (self.spread_bps / 10000.0)
        if order.side == OrderSide.BUY:
            fill_price += slippage + spread
        else:
            fill_price -= slippage + spread

        fill = Fill(
            order=order,
            price=fill_price,
            fees=self.fee_per_trade,
            slippage=slippage + spread,
            time=order.time or datetime.now(timezone.utc),
        )
        self._fills.append(fill)
        return f"sim-{len(self._fills)}"

    def cancel_order(self, order_id: str) -> None:
        return None

    def fetch_fills(self) -> list[Fill]:
        fills = list(self._fills)
        self._fills.clear()
        return fills
