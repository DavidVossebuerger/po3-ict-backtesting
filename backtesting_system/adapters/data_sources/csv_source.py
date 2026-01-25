from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from backtesting_system.interfaces.data_source import DataSource
from backtesting_system.models.market import Candle


_TIMEFRAME_MINUTES: Dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D": 1440,
}


def _parse_iso_utc(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _floor_time(dt: datetime, timeframe: str) -> datetime:
    minutes = _TIMEFRAME_MINUTES[timeframe]
    if timeframe == "D":
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    total_minutes = dt.hour * 60 + dt.minute
    floored = (total_minutes // minutes) * minutes
    hour = floored // 60
    minute = floored % 60
    return datetime(dt.year, dt.month, dt.day, hour, minute, tzinfo=timezone.utc)


def _resample(candles: List[Candle], timeframe: str) -> List[Candle]:
    if not candles:
        return []

    grouped: Dict[datetime, List[Candle]] = {}
    for candle in candles:
        key = _floor_time(candle.time, timeframe)
        grouped.setdefault(key, []).append(candle)

    result: List[Candle] = []
    for bucket_time in sorted(grouped.keys()):
        chunk = grouped[bucket_time]
        chunk_sorted = sorted(chunk, key=lambda c: c.time)
        open_price = chunk_sorted[0].open
        close_price = chunk_sorted[-1].close
        high_price = max(c.high for c in chunk_sorted)
        low_price = min(c.low for c in chunk_sorted)
        result.append(
            Candle(
                time=bucket_time,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=None,
            )
        )
    return result


@dataclass
class CSVDataSource(DataSource):
    base_path: Path
    file_map: Dict[str, Path]
    base_timeframe: str = "M30"

    def _resolve_path(self, symbol: str) -> Path:
        if symbol in self.file_map:
            return self.file_map[symbol]
        return self.base_path / f"{symbol.lower()}_{self.base_timeframe.lower()}_formatted.csv"

    def load_ohlcv(self, symbol: str, timeframe: str, start_date=None, end_date=None):
        path = self._resolve_path(symbol)
        candles = self._read_candles(path)
        candles = self._filter_date_range(candles, start_date, end_date)
        if timeframe == self.base_timeframe:
            return candles
        if timeframe not in _TIMEFRAME_MINUTES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return _resample(candles, timeframe)

    def load_volume_profile(self, symbol: str, date):
        return None

    def fetch_economic_calendar(self, start_date, end_date, importance: str = "high"):
        return []

    def _read_candles(self, path: Path) -> List[Candle]:
        candles: List[Candle] = []
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")
        with path.open("r", newline="", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                dt = _parse_iso_utc(row["time_utc"])
                candles.append(
                    Candle(
                        time=dt,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=None,
                    )
                )
        return candles

    def _filter_date_range(
        self,
        candles: List[Candle],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> List[Candle]:
        if start_date is None and end_date is None:
            return candles

        def in_range(candle: Candle) -> bool:
            if start_date and candle.time < start_date:
                return False
            if end_date and candle.time > end_date:
                return False
            return True

        return [c for c in candles if in_range(c)]
