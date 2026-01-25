from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass(frozen=True)
class Tick:
    time: datetime
    price: float
    volume: float | None = None


@dataclass(frozen=True)
class VolumeLevel:
    price: float
    volume: float


@dataclass(frozen=True)
class VolumeProfile:
    date: datetime
    levels: List[VolumeLevel]
    poc: Optional[float] = None
    vah: Optional[float] = None
    val: Optional[float] = None

    def total_volume(self) -> float:
        return float(sum(level.volume for level in self.levels))

    def prices(self) -> Iterable[float]:
        return [level.price for level in self.levels]
