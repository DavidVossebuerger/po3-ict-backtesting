from __future__ import annotations

from pathlib import Path
from typing import Iterable


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
