from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

from backtesting_system.analytics.performance_metrics import (
    calmar_ratio,
    cagr,
    k_ratio,
    profit_factor,
    sharpe_ratio_annualized,
    sortino_ratio_annualized,
    ulcer_index,
)
from backtesting_system.analytics.portfolio_analysis import (
    calculate_drawdown,
    daily_returns,
    monthly_returns,
    recovery_factor,
    weekly_returns,
)
from backtesting_system.core.backtest_engine import BacktestEngine


def _years_between(start: datetime, end: datetime) -> float:
    days = (end - start).days
    return max(days / 365.25, 0.0)


def _max_consecutive_losses(pnls: Iterable[float]) -> int:
    max_streak = 0
    current = 0
    for pnl in pnls:
        if pnl < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def build_report(engine: BacktestEngine) -> Dict[str, Any]:
    daily_returns_series = list(daily_returns(equity_points).values())
    returns = daily_returns_series
    gross_profit = sum(trade.pnl for trade in engine.trades if trade.pnl > 0)
    gross_loss = sum(trade.pnl for trade in engine.trades if trade.pnl < 0)
    wins = sum(1 for trade in engine.trades if trade.pnl > 0)
    total = len(engine.trades)
    win_rate = wins / total if total else 0.0
    equity_curve = [point.equity for point in engine.equity_curve]
    equity_points = [(point.time, point.equity) for point in engine.equity_curve]
    month_returns = monthly_returns(equity_points)
    week_returns = weekly_returns(equity_points)
    day_returns = daily_returns(equity_points)
    monthly_win_rate = 0.0
    if month_returns:
        monthly_win_rate = sum(1 for v in month_returns.values() if v > 0) / len(month_returns)
    weekly_avg = sum(week_returns.values()) / len(week_returns) if week_returns else 0.0
    daily_avg = sum(day_returns.values()) / len(day_returns) if day_returns else 0.0
    if engine.equity_curve:
        start_time = engine.equity_curve[0].time
        end_time = engine.equity_curve[-1].time
        years = _years_between(start_time, end_time)
    else:
        years = 0.0
    average_duration = 0.0
    if engine.trades:
        total_seconds = sum(
            (trade.exit_time - trade.entry_time).total_seconds() for trade in engine.trades
        )
        average_duration = total_seconds / len(engine.trades)

    avg_trade = (gross_profit + gross_loss) / total if total else 0.0
    avg_win = (gross_profit / wins) if wins else 0.0
    avg_loss = abs(gross_loss / (total - wins)) if total > wins else 0.0
    win_loss_ratio = (avg_win / avg_loss) if avg_loss else 0.0
    expectancy = avg_trade
    annual_return = cagr(engine.initial_capital, equity_curve[-1], years) if equity_curve and years > 0 else 0.0

    return {
        "initial_capital": engine.initial_capital,
        "final_equity": equity_curve[-1] if equity_curve else engine.initial_capital,
        "trades": total,
        "win_rate": win_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor(gross_profit, gross_loss),
        "max_drawdown": calculate_drawdown(equity_curve),
        "sharpe": sharpe_ratio_annualized(returns),
        "sortino": sortino_ratio_annualized(returns),
        "cagr": annual_return,
        "calmar": calmar_ratio(annual_return, calculate_drawdown(equity_curve)),
        "k_ratio": k_ratio(returns),
        "ulcer_index": ulcer_index(equity_curve),
        "recovery_factor": recovery_factor(sum(t.pnl for t in engine.trades), calculate_drawdown(equity_curve)),
        "monthly_win_rate": monthly_win_rate,
        "daily_avg_return": daily_avg,
        "weekly_avg_return": weekly_avg,
        "avg_trade_pnl": avg_trade,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "expectancy": expectancy,
        "max_consecutive_losses": _max_consecutive_losses([t.pnl for t in engine.trades]),
        "average_trade_duration_seconds": average_duration,
    }


def write_report(report: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        json.dump(report, outfile, indent=2)


def write_trades(engine: BacktestEngine, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow([
            "symbol",
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "size",
            "pnl",
            "confluence",
        ])
        for trade in engine.trades:
            writer.writerow([
                trade.symbol,
                trade.entry_time.isoformat(),
                trade.exit_time.isoformat(),
                f"{trade.entry_price:.5f}",
                f"{trade.exit_price:.5f}",
                f"{trade.size:.4f}",
                f"{trade.pnl:.5f}",
                trade.confluence,
            ])


def write_summary_csv(reports: Dict[str, Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "strategy",
        "initial_capital",
        "final_equity",
        "trades",
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "sharpe",
        "sortino",
        "cagr",
        "calmar",
        "k_ratio",
        "ulcer_index",
        "recovery_factor",
        "monthly_win_rate",
        "daily_avg_return",
        "weekly_avg_return",
        "avg_trade_pnl",
        "avg_win",
        "avg_loss",
        "win_loss_ratio",
        "expectancy",
        "max_consecutive_losses",
        "average_trade_duration_seconds",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(headers)
        for name, report in reports.items():
            writer.writerow([
                name,
                report.get("initial_capital"),
                report.get("final_equity"),
                report.get("trades"),
                report.get("win_rate"),
                report.get("profit_factor"),
                report.get("max_drawdown"),
                report.get("sharpe"),
                report.get("sortino"),
                report.get("cagr"),
                report.get("calmar"),
                report.get("k_ratio"),
                report.get("ulcer_index"),
                report.get("recovery_factor"),
                report.get("monthly_win_rate"),
                report.get("daily_avg_return"),
                report.get("weekly_avg_return"),
                report.get("avg_trade_pnl"),
                report.get("avg_win"),
                report.get("avg_loss"),
                report.get("win_loss_ratio"),
                report.get("expectancy"),
                report.get("max_consecutive_losses"),
                report.get("average_trade_duration_seconds"),
            ])


def write_walk_forward_csv(results: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "train_sharpe",
        "train_profit_factor",
        "train_max_drawdown",
        "train_cagr",
        "test_sharpe",
        "test_profit_factor",
        "test_max_drawdown",
        "test_cagr",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(headers)
        for row in results:
            train_report = row.get("train_report", {})
            test_report = row.get("test_report", {})
            writer.writerow([
                row.get("train_start"),
                row.get("train_end"),
                row.get("test_start"),
                row.get("test_end"),
                train_report.get("sharpe"),
                train_report.get("profit_factor"),
                train_report.get("max_drawdown"),
                train_report.get("cagr"),
                test_report.get("sharpe"),
                test_report.get("profit_factor"),
                test_report.get("max_drawdown"),
                test_report.get("cagr"),
            ])


def write_parameter_sensitivity_csv(results: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "params",
        "final_equity",
        "trades",
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "sharpe",
        "sortino",
        "cagr",
        "ulcer_index",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(headers)
        for row in results:
            writer.writerow([
                row.get("params"),
                row.get("final_equity"),
                row.get("trades"),
                row.get("win_rate"),
                row.get("profit_factor"),
                row.get("max_drawdown"),
                row.get("sharpe"),
                row.get("sortino"),
                row.get("cagr"),
                row.get("ulcer_index"),
            ])


def write_monte_carlo_csv(results: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["iteration", "max_drawdown", "final_equity"]
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(headers)
        for idx, row in enumerate(results, start=1):
            writer.writerow([idx, row.get("max_drawdown"), row.get("final_equity")])
