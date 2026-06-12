from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List


def _max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = float("-inf")
    max_dd = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            dd = (peak - equity) / peak
            dd = max(0.0, min(1.0, dd))
            max_dd = max(max_dd, dd)
    return max_dd


@dataclass
class MonteCarloResult:
    max_drawdown: float
    final_equity: float


def monte_carlo_resample(
    pnls: List[float],
    initial_capital: float,
    iterations: int = 1000,
    seed: int = 42,
    equity_floor: float = 0.0,
    stop_on_ruin: bool = True,
) -> List[MonteCarloResult]:
    rng = random.Random(seed)
    results: List[MonteCarloResult] = []
    if not pnls:
        return results

    for _ in range(iterations):
        sample = [rng.choice(pnls) for _ in pnls]
        equity = max(initial_capital, equity_floor)
        equity_curve = []
        for pnl in sample:
            equity = max(equity_floor, equity + pnl)
            equity_curve.append(equity)
            if stop_on_ruin and equity <= equity_floor:
                break
        results.append(
            MonteCarloResult(
                max_drawdown=_max_drawdown(equity_curve),
                final_equity=equity,
            )
        )
    return results
