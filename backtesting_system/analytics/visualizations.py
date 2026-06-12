from __future__ import annotations

from pathlib import Path
from math import ceil
from typing import Iterable, List

from backtesting_system.models.analytics import TradeRecord
from backtesting_system.models.market import Candle


def _safe_import_matplotlib():
    try:
        import matplotlib.pyplot as plt
        return plt
    except Exception:
        return None


def plot_equity_curve(equity_curve: Iterable[float], output_path: Path) -> None:
    plt = _safe_import_matplotlib()
    if plt is None:
        return
    values = list(equity_curve)
    if not values:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 4))
    plt.plot(values, color="blue")
    plt.title("Equity Curve")
    plt.xlabel("Bars")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_drawdown(drawdowns: Iterable[float], output_path: Path) -> None:
    plt = _safe_import_matplotlib()
    if plt is None:
        return
    values = list(drawdowns)
    if not values:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 4))
    plt.plot(values, color="red")
    plt.title("Drawdown")
    plt.xlabel("Bars")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_pnl_distribution(pnls: Iterable[float], output_path: Path) -> None:
    plt = _safe_import_matplotlib()
    if plt is None:
        return
    values = list(pnls)
    if not values:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 4))
    plt.hist(values, bins=50, color="gray")
    plt.title("PnL Distribution")
    plt.xlabel("PnL")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def _safe_import_plotly():
    try:
        import plotly.graph_objects as go
        return go
    except Exception:
        return None


def _downsample_candles(candle_list: List[Candle], max_points: int = 4000) -> List[Candle]:
    if len(candle_list) <= max_points:
        return candle_list

    step = ceil(len(candle_list) / max_points)
    reduced: List[Candle] = []
    for i in range(0, len(candle_list), step):
        block = candle_list[i : i + step]
        if not block:
            continue
        reduced.append(
            Candle(
                time=block[-1].time,
                open=block[0].open,
                high=max(c.high for c in block),
                low=min(c.low for c in block),
                close=block[-1].close,
                volume=sum(c.volume or 0.0 for c in block),
            )
        )
    return reduced


def _render_trade_chart(go, candle_list: List[Candle], trade_list: List[TradeRecord], output_path: Path, title: str) -> None:
    reduced_candles = _downsample_candles(candle_list)
    x = [c.time for c in reduced_candles]
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=x,
                open=[c.open for c in reduced_candles],
                high=[c.high for c in reduced_candles],
                low=[c.low for c in reduced_candles],
                close=[c.close for c in reduced_candles],
                name="Price",
                opacity=0.85,
                increasing_line_color="rgba(16, 185, 129, 0.9)",
                decreasing_line_color="rgba(239, 68, 68, 0.9)",
            )
        ]
    )

    entry_x: List = []
    entry_y: List[float] = []
    entry_text: List[str] = []
    exit_x: List = []
    exit_y: List[float] = []
    exit_text: List[str] = []
    shapes = []

    for trade in trade_list:
        entry_x.append(trade.entry_time)
        entry_y.append(trade.entry_price)
        entry_text.append(
            f"Entry ({trade.side})<br>Price: {trade.entry_price:.5f}<br>Confluence: {trade.confluence}"
        )
        exit_x.append(trade.exit_time)
        exit_y.append(trade.exit_price)
        exit_text.append(f"Exit<br>Price: {trade.exit_price:.5f}<br>PnL: {trade.pnl:.5f}")

        if trade.stop is not None:
            shapes.append(
                dict(
                    type="line",
                    xref="x",
                    yref="y",
                    x0=trade.entry_time,
                    x1=trade.exit_time,
                    y0=trade.stop,
                    y1=trade.stop,
                    line=dict(color="rgba(239, 68, 68, 0.65)", width=1, dash="dot"),
                )
            )
        if trade.target is not None:
            shapes.append(
                dict(
                    type="line",
                    xref="x",
                    yref="y",
                    x0=trade.entry_time,
                    x1=trade.exit_time,
                    y0=trade.target,
                    y1=trade.target,
                    line=dict(color="rgba(16, 185, 129, 0.65)", width=1, dash="dot"),
                )
            )

    if entry_x:
        fig.add_trace(
            go.Scatter(
                x=entry_x,
                y=entry_y,
                mode="markers",
                marker=dict(color="rgba(59, 130, 246, 0.85)", size=8, symbol="triangle-up"),
                name="Entry",
                text=entry_text,
                hoverinfo="text",
            )
        )
    if exit_x:
        fig.add_trace(
            go.Scatter(
                x=exit_x,
                y=exit_y,
                mode="markers",
                marker=dict(color="rgba(17, 24, 39, 0.8)", size=7, symbol="x"),
                name="Exit",
                text=exit_text,
                hoverinfo="text",
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Price",
        shapes=shapes,
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        height=700,
        hovermode="x unified",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        str(output_path),
        include_plotlyjs="cdn",
        full_html=True,
        config={"responsive": True, "displaylogo": False},
    )


def plot_trades_with_levels(candles: Iterable[Candle], trades: Iterable[TradeRecord], output_path: Path) -> None:
    go = _safe_import_plotly()
    if go is None:
        return

    candle_list = list(candles)
    trade_list = list(trades)
    if not candle_list:
        return

    monthly_candles = {}
    for candle in candle_list:
        month_key = (candle.time.year, candle.time.month)
        monthly_candles.setdefault(month_key, []).append(candle)

    for year, month in sorted(monthly_candles):
        month_candle_list = monthly_candles[(year, month)]
        month_start = month_candle_list[0].time
        month_end = month_candle_list[-1].time
        month_trades = [
            trade for trade in trade_list if trade.entry_time <= month_end and trade.exit_time >= month_start
        ]
        month_output_path = output_path.with_name(f"{output_path.stem}_{year}_{month:02d}{output_path.suffix}")
        _render_trade_chart(
            go,
            month_candle_list,
            month_trades,
            month_output_path,
            title=f"Trades with SL/TP ({year}-{month:02d})",
        )
