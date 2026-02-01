from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List


@dataclass
class EconomicCalendar:
    """Load a pre-downloaded economic calendar CSV (Forex Factory format)."""

    csv_path: Path
    _events: List[dict] | None = None

    def _load_events(self) -> List[dict]:
        if self._events is not None:
            return self._events
        if not self.csv_path.exists():
            self._events = []
            return self._events
        events: List[dict] = []
        with self.csv_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                # Forex Factory CSV uses "DateTime" in ISO format (e.g. 2007-01-01T04:30:00+03:30)
                datetime_str = row.get("DateTime") or row.get("Date") or row.get("date")
                if not datetime_str:
                    continue
                try:
                    dt = datetime.fromisoformat(datetime_str)
                except ValueError:
                    # Fallback for other formats
                    try:
                        dt = datetime.strptime(datetime_str[:19], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # Impact column contains "High Impact Expected", "Medium Impact Expected", etc.
                impact_raw = row.get("Impact") or row.get("Importance") or ""
                impact = "HIGH" if "high" in impact_raw.lower() else impact_raw.upper()
                
                events.append(
                    {
                        "datetime": dt,
                        "date": dt.date().isoformat(),
                        "time": dt.strftime("%H:%M"),
                        "event": row.get("Event") or row.get("Event Name") or "",
                        "currency": row.get("Currency") or row.get("Country") or "",
                        "impact": impact,
                    }
                )
        self._events = events
        return self._events

    def get_events_for_date(self, date: datetime) -> List[dict]:
        target = date.date()
        events = self._load_events()
        return [event for event in events if event["datetime"].date() == target]

    def get_high_impact_events(self, date: datetime, currencies: set[str] | None = None) -> List[dict]:
        """Get high-impact events for a date, optionally filtered by currencies."""
        events = [e for e in self.get_events_for_date(date) if e.get("impact") == "HIGH"]
        if currencies:
            events = [e for e in events if e.get("currency") in currencies]
        return events

    def is_high_impact_day(self, date: datetime) -> bool:
        return bool(self.get_high_impact_events(date))

    def has_relevant_event_near(self, timestamp: datetime, window_minutes: int = 30) -> bool:
        events = self.get_high_impact_events(timestamp)
        if not events:
            return False
        window = timedelta(minutes=window_minutes)
        for event in events:
            if abs(event["datetime"] - timestamp) <= window:
                return True
        return False
