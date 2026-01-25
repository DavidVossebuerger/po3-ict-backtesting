from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List


def _max_drawdown(equity_curve: List[float]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            dd = (peak - equity) / peak
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
) -> List[MonteCarloResult]:
    rng = random.Random(seed)
    results: List[MonteCarloResult] = []
    if not pnls:
        return results

    for _ in range(iterations):
        sample = [rng.choice(pnls) for _ in pnls]
        equity = initial_capital
        equity_curve = []
        for pnl in sample:
            equity += pnl
            equity_curve.append(equity)
        results.append(
            MonteCarloResult(
                max_drawdown=_max_drawdown(equity_curve),
                final_equity=equity,
            )
        )
    return results
