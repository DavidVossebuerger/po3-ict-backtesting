from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional

from backtesting_system.models.market import Candle


def validate_ohlcv(data) -> bool:
    required = {"open", "high", "low", "close"}
    columns = set(getattr(data, "columns", []))
    return required.issubset(columns) if columns else True


def validate_candles(candles: Iterable[Candle]) -> bool:
    last_time = None
    for candle in candles:
        if candle.high < max(candle.open, candle.close):
            return False
        if candle.low > min(candle.open, candle.close):
            return False
        if last_time and candle.time <= last_time:
            return False
        last_time = candle.time
    return True


@dataclass
class DataValidationReport:
    symbol: Optional[str] = None
    row_count: int = 0
    invalid_ohlc: int = 0
    large_gaps: int = 0
    spikes: int = 0
    completeness_pct: float = 0.0
    validation_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class DataValidator:
    def __init__(self, gap_threshold_pct: float = 2.0, spike_zscore: float = 3.0):
        self.gap_threshold_pct = gap_threshold_pct
        self.spike_zscore = spike_zscore

    def validate_candles(self, candles: List[Candle], symbol: Optional[str] = None) -> tuple[List[Candle], DataValidationReport]:
        report = DataValidationReport(symbol=symbol)
        if not candles:
            return candles, report

        cleaned: List[Candle] = []
        invalid_ohlc = 0
        for candle in candles:
            if candle.high < candle.low or candle.high < candle.open or candle.high < candle.close:
                invalid_ohlc += 1
                continue
            cleaned.append(candle)

        report.invalid_ohlc = invalid_ohlc

        gaps = 0
        returns = []
        for i in range(1, len(cleaned)):
            prev = cleaned[i - 1]
            curr = cleaned[i]
            if prev.close != 0:
                gap_pct = abs((curr.open - prev.close) / prev.close) * 100
                if gap_pct > self.gap_threshold_pct:
                    gaps += 1
            if prev.close != 0:
                returns.append((curr.close - prev.close) / prev.close)

        report.large_gaps = gaps

        spikes = 0
        if len(returns) > 20:
            mean = sum(returns) / len(returns)
            variance = sum((r - mean) ** 2 for r in returns) / len(returns)
            std = variance ** 0.5
            if std > 0:
                for r in returns:
                    if abs((r - mean) / std) > self.spike_zscore:
                        spikes += 1
        report.spikes = spikes

        report.row_count = len(cleaned)
        report.completeness_pct = (len(cleaned) / len(candles)) * 100 if candles else 0.0
        return cleaned, report
