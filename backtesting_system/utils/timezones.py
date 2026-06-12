from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from backtesting_system.core.clock import SessionWindow


NEW_YORK = ZoneInfo("America/New_York")

# Windows are expressed in NY local time and therefore DST-aware once timestamps
# are converted to NEW_YORK before comparisons.
ASIA = SessionWindow("Asia", time(19, 0), time(4, 0))
LONDON = SessionWindow("London", time(3, 0), time(12, 0))
NY = SessionWindow("NY", time(8, 0), time(17, 0))


def to_new_york(dt: datetime) -> datetime:
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)
	return dt.astimezone(NEW_YORK)


def is_in_ny_session(dt: datetime, session: SessionWindow) -> bool:
	local = to_new_york(dt)
	local_time = local.time()
	if session.start <= session.end:
		return session.start <= local_time <= session.end
	return local_time >= session.start or local_time <= session.end
