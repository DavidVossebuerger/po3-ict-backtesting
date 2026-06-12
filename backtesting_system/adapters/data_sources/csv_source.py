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
    """Parse an ISO-8601 timestamp or a Unix epoch value (seconds or ms).

    Dukascopy CSVs ship numeric Unix-millisecond timestamps under the
    ``timestamp`` column. Our internal formatted CSVs use ISO strings under
    ``time_utc``. We accept both transparently.
    """
    raw = str(value).strip()
    # Numeric: auto-detect seconds vs milliseconds.
    if raw.isdigit():
        epoch = int(raw)
        if epoch > 10**11:  # > year 5138 in seconds → treat as ms
            epoch = epoch / 1000.0
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    # ISO fallback
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_placeholder(candle: "Candle") -> bool:
    """Detect Dukascopy placeholder bars (flat-line with no real activity)."""
    if candle.high < candle.low:
        return True
    flat = candle.high == candle.low == candle.open == candle.close
    if not flat:
        return False
    # Many real quiet-market bars can be flat for one period; require the
    # open to be a "round" value with suspiciously few decimals and the
    # surrounding context (set by caller) to be flat. We keep this minimal
    # so the caller's price-range / variance filter can do its job later.
    return abs(candle.close) > 0 and float(candle.close).is_integer()


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
        if not chunk:
            continue
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
    file_map: Dict[str, object]  # Path | List[Path] per symbol
    base_timeframe: str = "M30"
    # Symbols that contain a known flat-line placeholder window. Values are
    # inclusive (start, end) UTC datetimes of synthetic bars to drop.
    placeholder_windows: Dict[str, tuple] = None

    def __post_init__(self) -> None:
        if self.placeholder_windows is None:
            self.placeholder_windows = {
                "USA500IDXUSD": (
                    datetime(2011, 9, 19, tzinfo=timezone.utc),
                    datetime(2011, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                ),
                "USATECHIDXUSD": (
                    datetime(2011, 9, 19, tzinfo=timezone.utc),
                    datetime(2011, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                ),
            }

    def _paths_for(self, symbol: str) -> List[Path]:
        entry = self.file_map.get(symbol)
        if entry is None:
            # Convention: symbol-m30-bid-*.csv glob inside base_path
            return sorted(self.base_path.glob(f"{symbol.lower()}-m30-bid-*.csv"))
        if isinstance(entry, (list, tuple)):
            return sorted(Path(p) for p in entry)
        return [Path(entry)]

    def _resolve_path(self, symbol: str) -> Path:
        entry = self.file_map.get(symbol)
        if entry is None:
            return self.base_path / f"{symbol.lower()}_{self.base_timeframe.lower()}_formatted.csv"
        if isinstance(entry, (list, tuple)):
            return Path(entry[0])
        return Path(entry)

    def load_ohlcv(self, symbol: str, timeframe: str, start_date=None, end_date=None):
        candles: List[Candle] = []
        for path in self._paths_for(symbol):
            candles.extend(self._read_candles(path))
        # Sort by time (multi-file merges need this) and de-dup.
        candles.sort(key=lambda c: c.time)
        seen = set()
        deduped: List[Candle] = []
        for c in candles:
            if c.time in seen:
                continue
            seen.add(c.time)
            deduped.append(c)
        # Drop known placeholder windows first (cheaper than per-bar check).
        window = self.placeholder_windows.get(symbol)
        if window is not None:
            ws, we = window
            deduped = [c for c in deduped if not (ws <= c.time <= we)]
        deduped = self._filter_date_range(deduped, start_date, end_date)
        if timeframe == self.base_timeframe:
            return deduped
        if timeframe not in _TIMEFRAME_MINUTES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return _resample(deduped, timeframe)

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
                # Accept either ISO-formatted 'time_utc' or Dukascopy's
                # 'timestamp' (numeric Unix seconds or milliseconds).
                if "time_utc" in row:
                    dt = _parse_iso_utc(row["time_utc"])
                elif "timestamp" in row:
                    dt = _parse_iso_utc(row["timestamp"])
                else:
                    raise KeyError(
                        f"CSV {path} must contain a 'time_utc' or 'timestamp' column"
                    )
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
