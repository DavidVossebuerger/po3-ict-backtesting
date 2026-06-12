from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from backtesting_system.core.event_bus import Event, EventBus
from backtesting_system.interfaces.execution import ExecutionBroker
from backtesting_system.interfaces.strategy import StrategyInterface
from backtesting_system.models.analytics import EquityPoint, TradeRecord
from backtesting_system.models.orders import Order, OrderSide, OrderType, Position
from backtesting_system.core.risk_manager import RiskManager
from backtesting_system.utils.symbol_specs import get_pip_size


@dataclass
class BacktestEngine:
    initial_capital: float
    broker: ExecutionBroker
    strategy: StrategyInterface
    risk_manager: RiskManager | None = None
    risk_per_trade: float = 0.01
    partial_exit_enabled: bool = True
    stop_slippage_pips: float = 0.5
    intrabar_exit_policy: str = "stop_first"
    max_daily_risk: float | None = None
    max_weekly_risk: float | None = None
    # Ruin-stop: if the mark-to-market equity drops to or below
    # `ruin_floor` (default 0.0), the engine force-closes all open
    # positions, marks the account as ruined, and stops processing
    # further bars. Default disabled to preserve backward compatibility
    # with results produced before the stop was introduced.
    ruin_stop_enabled: bool = False
    ruin_floor: float = 0.0
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
    _ruined: bool = field(init=False, default=False)
    _ruin_time: object = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.cash = self.initial_capital

    def run_backtest(self, data, symbol: str, show_progress: bool = False, progress_every: int = 5000) -> None:
        self.event_bus.register("MarketEvent", self._on_market_event)
        for idx, bar in enumerate(data, start=1):
            if self._ruined:
                break
            self.history.append(bar)
            self.event_bus.emit(Event(type="MarketEvent", payload={"bar": bar, "symbol": symbol}))
            if show_progress and idx % progress_every == 0:
                print(f"Processed {idx} bars...")
        # Force-close any still-open positions at end of data so the report
        # reflects realised PnL. Without this, Buy & Hold and other "hold
        # to expiry" benchmarks would show unrealised mark-to-market only.
        # Skipped if the ruin-stop already closed everything.
        if self.positions and self.history and not self._ruined:
            last_bar = self.history[-1]
            self._force_close_open_positions(last_bar)

    def _force_close_open_positions(self, bar) -> None:
        for position in list(self.positions):
            exit_price = bar.close
            exit_price = self._apply_exit_costs(exit_price, position)
            size = position.remaining_size or position.size
            pnl = self._calculate_pnl(position, exit_price, size)
            self.cash += pnl
            self._daily_pnl += pnl
            self._weekly_pnl += pnl
            position.close_time = bar.time
            position.exit_price = exit_price
            risk_per_unit = abs(position.entry - position.stop) if position.stop is not None else None
            risk_amount = (risk_per_unit * size) if risk_per_unit is not None else None
            r_multiple = (pnl / risk_amount) if risk_amount else None
            self.trades.append(
                TradeRecord(
                    symbol=position.symbol,
                    entry_time=position.open_time,
                    exit_time=position.close_time,
                    entry_price=position.entry,
                    exit_price=exit_price,
                    size=size,
                    pnl=pnl,
                    side=position.side.value,
                    stop=position.stop,
                    target=position.target,
                    r_multiple=r_multiple,
                    confluence=getattr(position, "confluence", None),
                )
            )
        self.positions = []

    def process_signal(self, signal: dict, current_price: float, bar_index: int) -> None:
        # Once the ruin-stop has triggered, do not open any further
        # positions. Late signals from the strategy are ignored.
        if self._ruined:
            return
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
        # Strategies can opt out of partial exits via this flag (see
        # BuyHoldStrategy). We copy it onto the Position so the partial-
        # exit check in _maybe_partial_exit can honour it.
        position.partial_exit_blocked = bool(signal.get("partial_exit_blocked", False))  # type: ignore[attr-defined]
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

        # If the ruin-stop has already triggered, the outer loop will
        # break on the next iteration. We still process the bar so the
        # equity curve has a flat-floor point that documents the ruin.
        self._rollover_timeframes(bar.time)

        self._update_positions(bar)
        if not self._ruined:
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

        # Ruin-stop check. If the mark-to-market equity has fallen to
        # or below the configured floor, force-close all open positions
        # at the bar's close (with exit costs applied) and mark the
        # account as ruined. The outer loop will then stop processing
        # further bars.
        if (
            self.ruin_stop_enabled
            and not self._ruined
            and equity <= self.ruin_floor
        ):
            self._force_close_open_positions(bar)
            # Clamp cash to the floor so that the equity curve does not
            # continue to produce negative values for subsequent bars.
            self.cash = max(self.cash, self.ruin_floor)
            self._ruined = True
            self._ruin_time = bar.time
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
            strategy_params = getattr(self.strategy, "params", {})
            pip_size = get_pip_size(strategy_params if isinstance(strategy_params, dict) else None, position.symbol)
            slippage = self.stop_slippage_pips * pip_size
            if side == OrderSide.BUY:
                return stop_price - slippage
            return stop_price + slippage

        def resolve_both_hit(target_price: float | None) -> Optional[float]:
            policy = (self.intrabar_exit_policy or "stop_first").lower()
            if policy == "target_first" and target_price is not None:
                return target_price
            return apply_stop_slippage(position.stop, position.side)

        if position.side == OrderSide.BUY:
            stop_hit = bar.low <= position.stop
            target_hit = position.target is not None and bar.high >= position.target
            if stop_hit and target_hit:
                return resolve_both_hit(position.target)
            if stop_hit:
                return apply_stop_slippage(position.stop, position.side)
            if target_hit:
                return position.target
        else:
            stop_hit = bar.high >= position.stop
            target_hit = position.target is not None and bar.low <= position.target
            if stop_hit and target_hit:
                return resolve_both_hit(position.target)
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
        # Strategies that opt out of partial exits (e.g. Buy & Hold) set
        # this flag on the originating signal. Without honoring it, the
        # engine splits the position at 1R and closes the remaining size
        # at the same bar's stop, which is exactly what produced the
        # 99.97% drawdown bug in report_buy_hold.json.
        if getattr(position, "partial_exit_blocked", False):
            return

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
