from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict

from backtesting_system.core.backtest_engine import BacktestEngine
from backtesting_system.core.data_handler import DataHandler


@dataclass
class StrategyStressTest:
    data_handler: DataHandler
    engine_factory: Callable[[], BacktestEngine]

    def run_scenarios(self, symbol: str, timeframe: str, scenarios: Dict[str, Dict]) -> Dict[str, dict]:
        results: Dict[str, dict] = {}
        for name, params in scenarios.items():
            engine = self.engine_factory()
            data = self.data_handler.load_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                start_date=params["start"],
                end_date=params["end"],
            )
            engine.run_backtest(data, symbol)
            results[name] = {
                "description": params.get("description", ""),
                "start": params["start"].isoformat(),
                "end": params["end"].isoformat(),
                "report": engine.generate_report(),
            }
        return results
