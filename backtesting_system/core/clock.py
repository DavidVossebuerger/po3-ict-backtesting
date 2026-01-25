from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start: time
    end: time


class Clock:
    def now(self) -> datetime:
        return datetime.utcnow()

    def is_in_session(self, now: datetime, session: SessionWindow) -> bool:
        t = now.time()
        if session.start <= session.end:
            return session.start <= t <= session.end
        return t >= session.start or t <= session.end
