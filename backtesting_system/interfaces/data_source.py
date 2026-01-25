from __future__ import annotations

from typing import Protocol


class DataSource(Protocol):
    def load_ohlcv(self, symbol: str, timeframe: str, start_date, end_date):
        """Return OHLCV data in a DataFrame-like structure."""
        ...

    def load_volume_profile(self, symbol: str, date):
        """Return a volume profile for the given date."""
        ...

    def fetch_economic_calendar(self, start_date, end_date, importance: str = "high"):
        """Return economic calendar events."""
        ...
