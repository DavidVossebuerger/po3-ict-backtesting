from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class EquityPoint:
    time: datetime
    equity: float
    drawdown: float


@dataclass(frozen=True)
class TradeRecord:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    r_multiple: Optional[float] = None
    confluence: Optional[float] = None
