from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_currency: str = "USD"
    default_timeframe: str = "H1"
    slippage_bps: float = 1.0
    commission_per_trade: float = 0.0
