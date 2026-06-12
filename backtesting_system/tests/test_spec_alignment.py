from __future__ import annotations

from datetime import datetime, timezone

from backtesting_system.adapters.execution.simulated_broker import SimulatedBroker
from backtesting_system.core.backtest_engine import BacktestEngine
from backtesting_system.models.market import Candle
from backtesting_system.models.orders import OrderSide, Position
from backtesting_system.strategies.composite_strategies import CompositeStrategy
from backtesting_system.strategies.daily_swing_framework import DailySwingFrameworkStrategy


class _NoopStrategy:
    def __init__(self) -> None:
        self.params = {}

    def identify_setup(self, data) -> bool:
        return False

    def generate_signals(self, data) -> dict:
        return {}

    def validate_context(self, data) -> bool:
        return True


def _candle(ts: datetime, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=ts, open=o, high=h, low=l, close=c, volume=None)


def test_adr_remaining_is_normalized_remaining_not_inverse_ratio() -> None:
    strategy = CompositeStrategy(params={})
    history = []
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # 14 prior days with range 2.0 => ADR = 2.0
    for i in range(14):
        day = base.replace(day=base.day + i)
        history.append(_candle(day.replace(hour=10), 100, 101, 99, 100.5))

    # Today range 1.5 => remaining 0.5 => normalized 0.25
    today = base.replace(day=15)
    history.append(_candle(today.replace(hour=10), 100, 101.0, 99.5, 100.2))

    remaining = strategy._adr_remaining_pct(history)
    assert 0.24 <= remaining <= 0.26


def test_daily_swing_reversal_uses_wick_not_body() -> None:
    strategy = DailySwingFrameworkStrategy(params={"enforce_killzones": False})
    prev = _candle(datetime(2024, 1, 2, tzinfo=timezone.utc), 100.0, 110.0, 95.0, 105.0)
    # Dips into wick (95) and closes back above wick level
    curr = _candle(datetime(2024, 1, 3, tzinfo=timezone.utc), 104.0, 106.0, 94.8, 95.3)

    framework = strategy.identify_daily_swing_framework([prev, curr])
    assert framework["type"] == "reversal"
    assert framework["bias"] == "long"


def test_intrabar_exit_policy_target_first() -> None:
    engine = BacktestEngine(
        initial_capital=10000.0,
        broker=SimulatedBroker(),
        strategy=_NoopStrategy(),
        intrabar_exit_policy="target_first",
    )
    position = Position(
        symbol="EURUSD",
        side=OrderSide.BUY,
        entry=1.1000,
        stop=1.0900,
        target=1.1200,
        size=1.0,
        open_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    bar = _candle(datetime(2024, 1, 1, 1, tzinfo=timezone.utc), 1.10, 1.125, 1.085, 1.11)

    exit_price = engine._check_exit(position, bar)
    assert exit_price == position.target
