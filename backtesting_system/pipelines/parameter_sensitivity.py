from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Dict, Iterable, List

from backtesting_system.analytics.reporting import build_report
from backtesting_system.core.backtest_engine import BacktestEngine
from backtesting_system.core.data_handler import DataHandler
from backtesting_system.interfaces.strategy import StrategyInterface


@dataclass
class ParameterSensitivityPipeline:
    data_handler: DataHandler
    strategy_factory: Callable[[dict], StrategyInterface]
    engine_factory: Callable[[StrategyInterface, dict], BacktestEngine]

    def run(
        self,
        symbol: str,
        timeframe: str,
        start_date,
        end_date,
        param_grid: Dict[str, Iterable],
    ) -> List[Dict[str, object]]:
        keys = list(param_grid.keys())
        results: List[Dict[str, object]] = []
        for values in product(*[param_grid[k] for k in keys]):
            params = dict(zip(keys, values))
            strategy = self.strategy_factory(params)
            engine = self.engine_factory(strategy, params)
            data = self.data_handler.load_ohlcv(symbol, timeframe, start_date, end_date)
            engine.run_backtest(data, symbol)
            report = build_report(engine)
            report.update({"params": params})
            results.append(report)
        return results
