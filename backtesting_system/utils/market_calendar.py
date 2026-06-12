from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from backtesting_system.models.market import Candle
from backtesting_system.utils.timezones import to_new_york


def ny_week_key(dt: datetime) -> tuple[int, int]:
    iso = to_new_york(dt).isocalendar()
    return iso.year, iso.week


def ny_weekday(dt: datetime) -> int:
    return to_new_york(dt).weekday()


def ny_date_key(dt: datetime) -> tuple[int, int, int]:
    local = to_new_york(dt)
    return local.year, local.month, local.day


def aggregate_daily_by_ny(history: Iterable[Candle]) -> List[Candle]:
    buckets: dict[tuple[int, int, int], list[Candle]] = {}
    for candle in history:
        buckets.setdefault(ny_date_key(candle.time), []).append(candle)

    result: List[Candle] = []
    for key in sorted(buckets.keys()):
        chunk = sorted(buckets[key], key=lambda c: c.time)
        day_time = datetime(key[0], key[1], key[2], tzinfo=timezone.utc)
        result.append(
            Candle(
                time=day_time,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=None,
            )
        )
    return result
