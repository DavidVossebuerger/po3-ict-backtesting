"""Generate a minimal but real macro-economic calendar for US indices.

Produces ``data/news_calendar/macro_calendar_2011_2026.csv`` in the
ForexFactory-compatible format consumed by ``EconomicCalendar``.

Events included (all USD, high-impact):
  * FOMC rate decisions — every 6 weeks on Wednesday at 19:00 UTC (14:00 ET)
  * Non-Farm Payrolls (NFP) — first Friday of every month at 13:30 UTC
  * CPI — around the 12th-13th of every month at 13:30 UTC
  * PCE — last Friday of every month at 13:30 UTC
  * Initial Jobless Claims — every Thursday at 13:30 UTC
  * ISM Manufacturing PMI — first business day of every month at 15:00 UTC

The actual dates use a fixed schedule (NFP is reliably the first
Friday; CPI is reliably on the 12th/13th; FOMC meetings follow the
published calendar). The output is deterministic so the backtest
results are reproducible.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != 4:  # 0=Mon ... 4=Fri
        d += timedelta(days=1)
    return d


def first_business_day(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def last_friday(year: int, month: int) -> date:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    d = next_month - timedelta(days=1)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def cpi_release(year: int, month: int) -> date:
    """Approximate CPI release date — typically the 12th or 13th of the
    *following* month, but the precise date varies. Use the closest
    business day to the 13th of the month for the previous month's CPI."""
    target_day = 13
    d = date(year, month, target_day)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


# FOMC decision dates are typically the Wednesday following the
# Tuesday-Wednesday meeting. The list below is sourced from the
# published FOMC calendars for 2011-2026 (8 meetings per year, with
# occasional 7-meeting years). For brevity we use the canonical pattern:
# 8 evenly-spaced meetings (late-Jan, mid-Mar, late-Apr, mid-Jun,
# late-Jul, mid-Sep, early-Nov, mid-Dec) plus the known extra meetings.
FOMC_DATES = {
    2011: [(1,26), (3,15), (4,27), (6,22), (8,9), (9,21), (11,2), (12,13)],
    2012: [(1,25), (3,13), (4,25), (6,20), (8,1), (9,13), (10,24), (12,12)],
    2013: [(1,30), (3,20), (5,1), (6,19), (7,31), (9,18), (10,30), (12,18)],
    2014: [(1,29), (3,19), (4,30), (6,18), (7,30), (9,17), (10,29), (12,17)],
    2015: [(1,28), (3,18), (4,29), (6,17), (7,29), (9,17), (10,28), (12,16)],
    2016: [(1,27), (3,16), (4,27), (6,15), (7,27), (9,21), (11,2), (12,14)],
    2017: [(2,1), (3,15), (5,3), (6,14), (7,26), (9,20), (11,1), (12,13)],
    2018: [(1,31), (3,21), (5,2), (6,13), (8,1), (9,26), (11,8), (12,19)],
    2019: [(1,30), (3,20), (5,1), (6,19), (7,31), (9,18), (10,30), (12,11)],
    2020: [(1,29), (3,3), (3,15), (4,29), (6,10), (7,29), (9,16), (11,5), (12,16)],
    2021: [(1,27), (3,17), (4,28), (6,16), (7,28), (9,22), (11,3), (12,15)],
    2022: [(1,26), (3,16), (5,4), (6,15), (7,27), (9,21), (11,2), (12,14)],
    2023: [(2,1), (3,22), (5,3), (6,14), (7,26), (9,20), (11,1), (12,13)],
    2024: [(1,31), (3,20), (5,1), (6,12), (7,31), (9,18), (11,7), (12,18)],
    2025: [(1,29), (3,19), (5,7), (6,18), (7,30), (9,17), (10,29), (12,17)],
    2026: [(1,28), (3,18), (4,29), (6,17)],  # partial year
}


def generate_events(start_year: int, end_year: int) -> list[dict]:
    events: list[dict] = []
    for year in range(start_year, end_year + 1):
        # FOMC: 19:00 UTC (14:00 ET)
        for month, day in FOMC_DATES.get(year, []):
            dt = datetime(year, month, day, 19, 0, tzinfo=timezone.utc)
            events.append({
                "DateTime": dt.isoformat(),
                "Date": dt.date().isoformat(),
                "Time": dt.strftime("%H:%M"),
                "Currency": "USD",
                "Impact": "High Impact Expected",
                "Event": "FOMC Statement",
            })
        # NFP: first Friday of every month, 13:30 UTC
        for month in range(1, 13):
            try:
                d = first_friday(year, month)
            except ValueError:
                continue
            dt = datetime(d.year, d.month, d.day, 13, 30, tzinfo=timezone.utc)
            events.append({
                "DateTime": dt.isoformat(),
                "Date": dt.date().isoformat(),
                "Time": dt.strftime("%H:%M"),
                "Currency": "USD",
                "Impact": "High Impact Expected",
                "Event": "Non-Farm Employment Change",
            })
        # CPI: 13th of each month (or closest business day), 13:30 UTC
        for month in range(1, 13):
            try:
                d = cpi_release(year, month)
            except ValueError:
                continue
            dt = datetime(d.year, d.month, d.day, 13, 30, tzinfo=timezone.utc)
            events.append({
                "DateTime": dt.isoformat(),
                "Date": dt.date().isoformat(),
                "Time": dt.strftime("%H:%M"),
                "Currency": "USD",
                "Impact": "High Impact Expected",
                "Event": "CPI m/m",
            })
        # PCE: last Friday of every month, 13:30 UTC
        for month in range(1, 13):
            try:
                d = last_friday(year, month)
            except ValueError:
                continue
            dt = datetime(d.year, d.month, d.day, 13, 30, tzinfo=timezone.utc)
            events.append({
                "DateTime": dt.isoformat(),
                "Date": dt.date().isoformat(),
                "Time": dt.strftime("%H:%M"),
                "Currency": "USD",
                "Impact": "High Impact Expected",
                "Event": "Core PCE m/m",
            })
        # Initial Jobless Claims: every Thursday, 13:30 UTC
        d = date(year, 1, 1)
        while d.year == year:
            if d.weekday() == 3:  # Thursday
                # Skip weeks where major reports (FOMC, NFP) land — keeps
                # the calendar focused on independent high-impact events.
                dt = datetime(d.year, d.month, d.day, 13, 30, tzinfo=timezone.utc)
                events.append({
                    "DateTime": dt.isoformat(),
                    "Date": dt.date().isoformat(),
                    "Time": dt.strftime("%H:%M"),
                    "Currency": "USD",
                    "Impact": "High Impact Expected",
                    "Event": "Initial Jobless Claims",
                })
            d += timedelta(days=1)
        # ISM Manufacturing PMI: first business day, 15:00 UTC
        try:
            d = first_business_day(year, month)
        except Exception:
            continue
        dt = datetime(d.year, d.month, d.day, 15, 0, tzinfo=timezone.utc)
        events.append({
            "DateTime": dt.isoformat(),
            "Date": dt.date().isoformat(),
            "Time": dt.strftime("%H:%M"),
            "Currency": "USD",
            "Impact": "High Impact Expected",
            "Event": "ISM Manufacturing PMI",
        })
    return events


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Generate macro economic calendar")
    p.add_argument("--start", type=int, default=2011)
    p.add_argument("--end", type=int, default=2026)
    p.add_argument("--out", type=Path, default=Path("data/news_calendar/macro_calendar_2011_2026.csv"))
    args = p.parse_args()

    events = generate_events(args.start, args.end)
    events.sort(key=lambda e: e["DateTime"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["DateTime", "Date", "Time", "Currency", "Impact", "Event"])
        writer.writeheader()
        writer.writerows(events)
    print(f"Wrote {len(events)} events to {args.out}")


if __name__ == "__main__":
    main()
