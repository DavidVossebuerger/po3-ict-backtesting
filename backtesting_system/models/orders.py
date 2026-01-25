from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass(frozen=True)
class Order:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time: Optional[datetime] = None


@dataclass(frozen=True)
class Fill:
    order: Order
    price: float
    fees: float
    slippage: float
    time: datetime


@dataclass
class Position:
    symbol: str
    side: OrderSide
    entry: float
    stop: float
    target: float | None
    size: float
    open_time: datetime
    close_time: datetime | None = None
    exit_price: float | None = None
    initial_size: float | None = None
    remaining_size: float | None = None
    partial_exit_done: bool = False
    trail_stop: float | None = None
    confluence: float | None = None

    def __post_init__(self) -> None:
        if self.initial_size is None:
            self.initial_size = self.size
        if self.remaining_size is None:
            self.remaining_size = self.size

    @property
    def is_open(self) -> bool:
        return self.close_time is None
