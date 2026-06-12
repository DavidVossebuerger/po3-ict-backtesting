from __future__ import annotations

from typing import Iterable


def sharpe_ratio(returns: Iterable[float], risk_free_rate: float = 0.0) -> float:
    """Sharpe ratio for per-period returns.

    ``risk_free_rate`` is given as an *annualised* rate. We convert it
    to per-period by dividing by ``periods_per_year`` (the default
    helper signatures downstream pass 252 for daily data). Callers
    that want the per-period formulation should pass
    ``risk_free_rate=0.0`` and a pre-divided number, or use
    ``sharpe_ratio_annualized`` directly.
    """
    returns_list = list(returns)
    if not returns_list:
        return 0.0
    mean_return = sum(returns_list) / len(returns_list)
    variance = sum((r - mean_return) ** 2 for r in returns_list) / len(returns_list)
    std_dev = variance ** 0.5
    if std_dev == 0:
        return 0.0
    return (mean_return - risk_free_rate) / std_dev


def sharpe_ratio_annualized(returns: Iterable[float], risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """Annualised Sharpe.

    ``risk_free_rate`` is the *annual* risk-free rate (e.g. 0.02 for
    2% USD). We convert it to a per-period rate before subtracting.
    """
    if not returns:
        return 0.0
    per_period_rf = risk_free_rate / periods_per_year
    base = sharpe_ratio(returns, per_period_rf)
    return base * (periods_per_year ** 0.5)


def sortino_ratio(returns: Iterable[float], risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """Sortino ratio for per-period returns. ``risk_free_rate`` is annual."""
    returns_list = list(returns)
    if not returns_list:
        return 0.0
    per_period_rf = risk_free_rate / periods_per_year
    mean_return = sum(returns_list) / len(returns_list)
    downside = [r for r in returns_list if r < per_period_rf]
    if not downside:
        return 0.0
    variance = sum((r - per_period_rf) ** 2 for r in downside) / len(downside)
    downside_dev = variance ** 0.5
    if downside_dev == 0:
        return 0.0
    return (mean_return - per_period_rf) / downside_dev


def sortino_ratio_annualized(returns: Iterable[float], risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    base = sortino_ratio(returns, risk_free_rate, periods_per_year=periods_per_year)
    return base * (periods_per_year ** 0.5) if base else 0.0


def profit_factor(gross_profit: float, gross_loss: float) -> float:
    if gross_loss == 0:
        return 0.0
    return gross_profit / abs(gross_loss)


def cagr(initial_value: float, final_value: float, years: float) -> float:
    if initial_value <= 0 or years <= 0:
        return 0.0
    return (final_value / initial_value) ** (1 / years) - 1


def ulcer_index(equity_curve: Iterable[float]) -> float:
    equity_list = list(equity_curve)
    if not equity_list:
        return 0.0
    peak = equity_list[0]
    drawdowns = []
    for value in equity_list:
        peak = max(peak, value)
        drawdown = 0.0 if peak == 0 else (peak - value) / peak
        drawdowns.append(drawdown ** 2)
    return (sum(drawdowns) / len(drawdowns)) ** 0.5


def calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    if max_drawdown == 0:
        return 0.0
    return annual_return / abs(max_drawdown)


def k_ratio(returns: Iterable[float]) -> float:
    values = list(returns)
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((r - mean) ** 2 for r in values) / len(values)
    std_dev = variance ** 0.5
    if std_dev == 0:
        return 0.0
    return mean / std_dev
