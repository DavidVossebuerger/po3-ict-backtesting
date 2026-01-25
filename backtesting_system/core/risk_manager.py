from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskManager:
    def calculate_1r_system(self, entry: float, stop_loss: float, target: float) -> dict:
        return {"entry": entry, "stop": stop_loss, "target": target}

    def partial_exit_trail_stop(self, entry: float, stop_loss: float, target: float, trail_percentage: float = 0.75) -> dict:
        return {
            "entry": entry,
            "stop": stop_loss,
            "target": target,
            "trail_percentage": trail_percentage,
        }

    def apply_daily_drawdown_limit(self, daily_loss: float, max_daily_risk: float) -> bool:
        return daily_loss <= max_daily_risk

    def apply_weekly_risk_limit(self, weekly_loss: float, max_weekly_risk: float) -> bool:
        return weekly_loss <= max_weekly_risk

    def calculate_position_size(self, account_size: float, risk_per_trade: float, entry: float, stop: float) -> float:
        stop_distance = abs(entry - stop)
        if stop_distance <= 0:
            return 0.0
        return (account_size * risk_per_trade) / stop_distance

    def check_correlation_risk(self, positions) -> bool:
        symbols = [p.symbol for p in positions]
        return len(symbols) != len(set(symbols))

    def adjust_risk_for_volatility(self, atr: float, average_atr: float) -> float:
        if average_atr <= 0:
            return 1.0
        return atr / average_atr
