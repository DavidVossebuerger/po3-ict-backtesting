from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List

from backtesting_system.analytics.statistics import pearson_correlation

from backtesting_system.analytics.reporting import build_report
from backtesting_system.core.backtest_engine import BacktestEngine
from backtesting_system.core.data_handler import DataHandler
from backtesting_system.interfaces.strategy import StrategyInterface


def _add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, 28)
    return dt.replace(year=year, month=month, day=day)


def _split_windows(start: datetime, end: datetime, train_months: int, test_months: int, step_months: int):
    cursor = start
    while True:
        train_start = cursor
        train_end = _add_months(train_start, train_months)
        test_end = _add_months(train_end, test_months)
        if test_end > end:
            break
        yield (train_start, train_end, train_end, test_end)
        cursor = _add_months(cursor, step_months)


@dataclass
class WalkForwardPipeline:
    data_handler: DataHandler
    strategy_factory: Callable[[], StrategyInterface]
    engine_factory: Callable[[StrategyInterface], BacktestEngine]

    def run(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        train_months: int = 12,
        test_months: int = 3,
        step_months: int = 3,
    ) -> Dict[str, object]:
        results: List[Dict[str, object]] = []
        for idx, (train_start, train_end, test_start, test_end) in enumerate(
            _split_windows(start_date, end_date, train_months, test_months, step_months), start=1
        ):
            print(f"Walk-forward window {idx}: {train_start.date()} -> {test_end.date()}")
            train_strategy = self.strategy_factory()
            train_engine = self.engine_factory(train_strategy)
            train_data = self.data_handler.load_ohlcv(symbol, timeframe, train_start, train_end)
            train_engine.run_backtest(train_data, symbol, show_progress=True)
            train_report = build_report(train_engine)

            if hasattr(train_strategy, "optimize"):
                try:
                    optimized_params = train_strategy.optimize(train_data)  # type: ignore[attr-defined]
                    if isinstance(optimized_params, dict):
                        train_strategy.params.update(optimized_params)
                except Exception:
                    optimized_params = {}
            else:
                optimized_params = {}

            test_strategy = self.strategy_factory()
            if isinstance(optimized_params, dict):
                test_strategy.params.update(optimized_params)
            test_engine = self.engine_factory(test_strategy)
            test_data = self.data_handler.load_ohlcv(symbol, timeframe, test_start, test_end)
            test_engine.run_backtest(test_data, symbol, show_progress=True)
            test_report = build_report(test_engine)

            results.append(
                {
                    "train_start": train_start.isoformat(),
                    "train_end": train_end.isoformat(),
                    "test_start": test_start.isoformat(),
                    "test_end": test_end.isoformat(),
                    "train_report": train_report,
                    "test_report": test_report,
                    "optimal_params": optimized_params,
                }
            )
        aggregate = self._aggregate(results)
        return {"windows": results, "aggregate": aggregate}

    def _aggregate(self, results: List[Dict[str, object]]) -> Dict[str, object]:
        is_sharpes = [r["train_report"].get("sharpe", 0.0) for r in results]
        oos_sharpes = [r["test_report"].get("sharpe", 0.0) for r in results]
        is_returns = [r["train_report"].get("cagr", 0.0) for r in results]
        oos_returns = [r["test_report"].get("cagr", 0.0) for r in results]
        r_val, p_val = pearson_correlation(is_sharpes, oos_sharpes) if len(results) > 1 else (0.0, 1.0)
        avg_is = sum(is_sharpes) / len(is_sharpes) if is_sharpes else 0.0
        avg_oos = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0.0
        avg_is_ret = sum(is_returns) / len(is_returns) if is_returns else 0.0
        avg_oos_ret = sum(oos_returns) / len(oos_returns) if oos_returns else 0.0
        return {
            "avg_is_sharpe": avg_is,
            "avg_oos_sharpe": avg_oos,
            "avg_is_return": avg_is_ret,
            "avg_oos_return": avg_oos_ret,
            "is_oos_correlation": r_val,
            "correlation_p_value": p_val,
            "consistency_score": "PASS" if r_val > 0.7 else "FAIL",
        }
