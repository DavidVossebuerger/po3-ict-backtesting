from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from backtesting_system.core.event_bus import Event, EventBus
from backtesting_system.interfaces.execution import ExecutionBroker
from backtesting_system.interfaces.strategy import StrategyInterface
from backtesting_system.models.analytics import EquityPoint, TradeRecord
from backtesting_system.models.orders import Order, OrderSide, OrderType, Position
from backtesting_system.core.risk_manager import RiskManager


@dataclass
class BacktestEngine:
    initial_capital: float
    broker: ExecutionBroker
    strategy: StrategyInterface
    risk_manager: RiskManager | None = None
    risk_per_trade: float = 0.01
    partial_exit_enabled: bool = True
    stop_slippage_pips: float = 0.5
    max_daily_risk: float | None = None
    max_weekly_risk: float | None = None
    event_bus: EventBus = field(default_factory=EventBus)
    positions: List[Position] = field(default_factory=list)
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[EquityPoint] = field(default_factory=list)
    cash: float = field(init=False)
    history: List = field(default_factory=list)
    _current_day: tuple | None = None
    _current_week: tuple | None = None
    _daily_pnl: float = 0.0
    _weekly_pnl: float = 0.0

    def __post_init__(self) -> None:
        self.cash = self.initial_capital

    def run_backtest(self, data, symbol: str, show_progress: bool = False, progress_every: int = 5000) -> None:
        self.event_bus.register("MarketEvent", self._on_market_event)
        for idx, bar in enumerate(data, start=1):
            self.history.append(bar)
            self.event_bus.emit(Event(type="MarketEvent", payload={"bar": bar, "symbol": symbol}))
            if show_progress and idx % progress_every == 0:
                print(f"Processed {idx} bars...")

    def process_signal(self, signal: dict, current_price: float, bar_index: int) -> None:
        direction = signal.get("direction")
        if direction not in {"long", "short"}:
            return

        entry = float(signal.get("entry", current_price))
        stop = float(signal.get("stop", entry))
        size = signal.get("size")
        if size is None:
            if self.risk_manager:
                size = self.risk_manager.calculate_position_size(
                    account_size=self.cash,
                    risk_per_trade=self.risk_per_trade,
                    entry=entry,
                    stop=stop,
                )
            else:
                size = 1.0
        if self.risk_manager and "atr" in signal and "average_atr" in signal:
            volatility_multiplier = self.risk_manager.adjust_risk_for_volatility(
                atr=float(signal["atr"]),
                average_atr=float(signal["average_atr"]),
            )
            size = float(size) / max(volatility_multiplier, 0.0001)
        size = float(size)
        target = signal.get("target")
        symbol = signal.get("symbol")
        confluence = signal.get("confluence")

        side = OrderSide.BUY if direction == "long" else OrderSide.SELL
        order = Order(
            symbol=symbol,
            side=side,
            quantity=size,
            order_type=OrderType.MARKET,
            limit_price=entry,
            time=signal.get("time"),
        )
        self.broker.place_order(order)
        fills = self.broker.fetch_fills()
        if not fills:
            return
        fill = fills[-1]
        self.cash -= fill.fees
        position = Position(
            symbol=symbol,
            side=side,
            entry=fill.price,
            stop=stop,
            target=target,
            size=size,
            open_time=fill.time,
        )
        position.confluence = confluence  # type: ignore[attr-defined]
        self.positions.append(position)

    def apply_risk_management(self, position: Position) -> Position:
        return position

    def calculate_returns(self):
        if not self.equity_curve:
            return []
        daily = {}
        for point in self.equity_curve:
            key = (point.time.year, point.time.month, point.time.day)
            daily.setdefault(key, []).append(point.equity)
        returns = []
        for key in sorted(daily.keys()):
            values = daily[key]
            if len(values) < 2:
                returns.append(0.0)
            else:
                start, end = values[0], values[-1]
                returns.append(0.0 if start == 0 else (end - start) / start)
        return returns

    def generate_report(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "final_equity": self.equity_curve[-1].equity if self.equity_curve else self.initial_capital,
            "trades": len(self.trades),
        }

    def _on_market_event(self, event: Event) -> None:
        bar = event.payload["bar"]
        symbol = event.payload["symbol"]

        self._rollover_timeframes(bar.time)

        self._update_positions(bar)
        signal = self.strategy.generate_signals({
            "bar": bar,
            "symbol": symbol,
            "history": self.history,
        })
        if signal and self._risk_limits_ok():
            signal.setdefault("symbol", symbol)
            signal.setdefault("time", bar.time)
            self.process_signal(signal, bar.close, 0)

        equity = self._mark_to_market(bar)
        self.equity_curve.append(EquityPoint(time=bar.time, equity=equity, drawdown=0.0))

    def _update_positions(self, bar) -> None:
        remaining: List[Position] = []
        for position in self.positions:
            if self.partial_exit_enabled:
                self._maybe_partial_exit(position, bar)
            exit_price = self._check_exit(position, bar)
            if exit_price is None:
                remaining.append(position)
                continue
            exit_price = self._apply_exit_costs(exit_price, position)
            pnl = self._calculate_pnl(position, exit_price, position.remaining_size or position.size)
            self.cash += pnl
            self._daily_pnl += pnl
            self._weekly_pnl += pnl
            exit_fee = getattr(self.broker, "fee_per_trade", 0.0)
            self.cash -= exit_fee
            position.close_time = bar.time
            position.exit_price = exit_price
            risk_per_unit = abs(position.entry - position.stop) if position.stop is not None else None
            risk_amount = (risk_per_unit * (position.remaining_size or position.size)) if risk_per_unit is not None else None
            r_multiple = (pnl / risk_amount) if risk_amount else None
            self.trades.append(
                TradeRecord(
                    symbol=position.symbol,
                    entry_time=position.open_time,
                    exit_time=position.close_time,
                    entry_price=position.entry,
                    exit_price=exit_price,
                    size=position.remaining_size or position.size,
                    pnl=pnl,
                    side=position.side.value,
                    stop=position.stop,
                    target=position.target,
                    r_multiple=r_multiple,
                    confluence=getattr(position, "confluence", None),
                )
            )
        self.positions = remaining

    def _check_exit(self, position: Position, bar) -> Optional[float]:
        def apply_stop_slippage(stop_price: float, side: OrderSide) -> float:
            slippage = self.stop_slippage_pips * stop_price / 10000
            if side == OrderSide.BUY:
                return stop_price - slippage
            return stop_price + slippage

        if position.side == OrderSide.BUY:
            stop_hit = bar.low <= position.stop
            target_hit = position.target is not None and bar.high >= position.target
            if stop_hit and target_hit:
                return apply_stop_slippage(position.stop, position.side)
            if stop_hit:
                return apply_stop_slippage(position.stop, position.side)
            if target_hit:
                return position.target
        else:
            stop_hit = bar.high >= position.stop
            target_hit = position.target is not None and bar.low <= position.target
            if stop_hit and target_hit:
                return apply_stop_slippage(position.stop, position.side)
            if stop_hit:
                return apply_stop_slippage(position.stop, position.side)
            if target_hit:
                return position.target
        return None

    def _calculate_pnl(self, position: Position, exit_price: float, size: float) -> float:
        if position.side == OrderSide.BUY:
            return (exit_price - position.entry) * size
        return (position.entry - exit_price) * size

    def _apply_exit_costs(self, exit_price: float, position: Position) -> float:
        slippage_bps = float(getattr(self.broker, "slippage_bps", 0.0) or 0.0)
        spread_bps = float(getattr(self.broker, "spread_bps", 0.0) or 0.0)
        total_bps = slippage_bps + spread_bps
        if total_bps <= 0:
            return exit_price
        adjustment = exit_price * (total_bps / 10000.0)
        if position.side == OrderSide.BUY:
            return exit_price - adjustment
        return exit_price + adjustment

    def _mark_to_market(self, bar) -> float:
        unrealized = 0.0
        for position in self.positions:
            size = position.remaining_size or position.size
            if position.side == OrderSide.BUY:
                unrealized += (bar.close - position.entry) * size
            else:
                unrealized += (position.entry - bar.close) * size
        return self.cash + unrealized

    def _rollover_timeframes(self, timestamp) -> None:
        day_key = (timestamp.year, timestamp.month, timestamp.day)
        week_key = timestamp.isocalendar()[:2]
        if self._current_day != day_key:
            self._current_day = day_key
            self._daily_pnl = 0.0
        if self._current_week != week_key:
            self._current_week = week_key
            self._weekly_pnl = 0.0

    def _risk_limits_ok(self) -> bool:
        if not self.risk_manager:
            return True
        daily_loss = max(0.0, -self._daily_pnl)
        weekly_loss = max(0.0, -self._weekly_pnl)
        if self.max_daily_risk is not None:
            if not self.risk_manager.apply_daily_drawdown_limit(daily_loss, self.max_daily_risk):
                return False
        if self.max_weekly_risk is not None:
            if not self.risk_manager.apply_weekly_risk_limit(weekly_loss, self.max_weekly_risk):
                return False
        return True

    def _maybe_partial_exit(self, position: Position, bar) -> None:
        if position.partial_exit_done:
            self._trail_stop(position, bar)
            return
        if position.remaining_size is None:
            position.remaining_size = position.size

        risk = abs(position.entry - position.stop)
        if risk <= 0:
            return

        one_r_target = position.entry + risk if position.side == OrderSide.BUY else position.entry - risk
        hit_one_r = bar.high >= one_r_target if position.side == OrderSide.BUY else bar.low <= one_r_target
        if not hit_one_r:
            return

        trail_percentage = 0.75
        if self.risk_manager:
            cfg = self.risk_manager.partial_exit_trail_stop(position.entry, position.stop, position.target or one_r_target)
            trail_percentage = float(cfg.get("trail_percentage", trail_percentage))

        partial_size = (position.initial_size or position.size) * trail_percentage
        partial_size = min(partial_size, position.remaining_size or position.size)
        if partial_size <= 0:
            return

        exit_price = self._apply_exit_costs(one_r_target, position)
        pnl = self._calculate_pnl(position, exit_price, partial_size)
        self.cash += pnl
        self._daily_pnl += pnl
        self._weekly_pnl += pnl
        exit_fee = getattr(self.broker, "fee_per_trade", 0.0)
        self.cash -= exit_fee
        self.trades.append(
            TradeRecord(
                symbol=position.symbol,
                entry_time=position.open_time,
                exit_time=bar.time,
                entry_price=position.entry,
                exit_price=exit_price,
                size=partial_size,
                pnl=pnl,
                side=position.side.value,
                stop=position.stop,
                target=position.target,
                confluence=getattr(position, "confluence", None),
            )
        )

        position.remaining_size = (position.remaining_size or position.size) - partial_size
        position.partial_exit_done = True
        position.stop = position.entry
        position.trail_stop = bar.low if position.side == OrderSide.BUY else bar.high

    def _trail_stop(self, position: Position, bar) -> None:
        if position.trail_stop is None:
            return
        if position.side == OrderSide.BUY:
            position.trail_stop = max(position.trail_stop, bar.low)
            position.stop = max(position.stop, position.trail_stop)
        else:
            position.trail_stop = min(position.trail_stop, bar.high)
            position.stop = min(position.stop, position.trail_stop)
