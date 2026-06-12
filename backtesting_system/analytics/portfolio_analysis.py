from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable, List, Tuple


def calculate_drawdown(equity_curve: Iterable[float]) -> float:
    peak = float("-inf")
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown


def recovery_factor(total_profit: float, max_drawdown: float) -> float:
    if max_drawdown == 0:
        return 0.0
    return total_profit / max_drawdown


def monthly_returns(equity_points: List[Tuple[datetime, float]]) -> dict[str, float]:
    buckets = defaultdict(list)
    for ts, equity in equity_points:
        key = f"{ts.year:04d}-{ts.month:02d}"
        buckets[key].append(equity)
    returns = {}
    for key, values in buckets.items():
        if len(values) < 2:
            returns[key] = 0.0
        else:
            start, end = values[0], values[-1]
            returns[key] = 0.0 if start == 0 else (end - start) / start
    return returns


def weekly_returns(equity_points: List[Tuple[datetime, float]]) -> dict[str, float]:
    buckets = defaultdict(list)
    for ts, equity in equity_points:
        iso = ts.isocalendar()
        key = f"{iso.year:04d}-W{iso.week:02d}"
        buckets[key].append(equity)
    returns = {}
    for key, values in buckets.items():
        if len(values) < 2:
            returns[key] = 0.0
        else:
            start, end = values[0], values[-1]
            returns[key] = 0.0 if start == 0 else (end - start) / start
    return returns


def daily_returns(equity_points: List[Tuple[datetime, float]]) -> dict[str, float]:
    buckets = defaultdict(list)
    for ts, equity in equity_points:
        key = f"{ts.year:04d}-{ts.month:02d}-{ts.day:02d}"
        buckets[key].append(equity)
    returns = {}
    for key, values in buckets.items():
        if len(values) < 2:
            returns[key] = 0.0
        else:
            start, end = values[0], values[-1]
            returns[key] = 0.0 if start == 0 else (end - start) / start
    return returns
