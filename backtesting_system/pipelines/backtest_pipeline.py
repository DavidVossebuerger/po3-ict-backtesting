from __future__ import annotations

from dataclasses import dataclass

from backtesting_system.core.backtest_engine import BacktestEngine
from backtesting_system.core.data_handler import DataHandler


@dataclass
class BacktestPipeline:
    data_handler: DataHandler
    engine: BacktestEngine

    def run(self, symbol: str, timeframe: str, start_date, end_date, show_progress: bool = False) -> None:
        data = self.data_handler.load_ohlcv(symbol, timeframe, start_date, end_date)
        self.engine.run_backtest(data, symbol, show_progress=show_progress)
