from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class ForexFactoryCalendar:
    """Fetch high-impact economic events from a local calendar file."""

    data_dir: Path = Path("data/news_calendar")
    file_name: str = "forexfactory.json"

    _events: List[dict] | None = None

    def _load_events(self) -> List[dict]:
        if self._events is not None:
            return self._events
        calendar_path = self.data_dir / self.file_name
        if not calendar_path.exists():
            self._events = []
            return self._events
        try:
            payload = json.loads(calendar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = []
        if isinstance(payload, dict):
            payload = payload.get("events", [])
        self._events = payload if isinstance(payload, list) else []
        return self._events

    def get_events_for_date(self, date: datetime) -> List[dict]:
        events = self._load_events()
        target = date.date().isoformat()
        return [
            event
            for event in events
            if str(event.get("date", ""))[:10] == target
        ]
