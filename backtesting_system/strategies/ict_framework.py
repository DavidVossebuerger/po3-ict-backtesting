from __future__ import annotations

from typing import List

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle
from backtesting_system.utils.timezones import ASIA, LONDON, NY


class ICTFramework(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)

    def identify_fvg(self, candles: List[Candle]) -> List[dict]:
        gaps: List[dict] = []
        if len(candles) < 3:
            return gaps
        for i in range(2, len(candles)):
            c1 = candles[i - 2]
            c3 = candles[i]
            if c1.high < c3.low:
                gaps.append({"type": "bullish", "low": c1.high, "high": c3.low, "index": i})
            if c1.low > c3.high:
                gaps.append({"type": "bearish", "low": c3.high, "high": c1.low, "index": i})
        return gaps

    def identify_order_blocks(self, candles: List[Candle], lookback: int = 10) -> List[dict]:
        blocks: List[dict] = []
        if len(candles) < lookback + 1:
            return blocks
        recent = candles[-(lookback + 1) :]
        for i in range(len(recent) - 1):
            c = recent[i]
            nxt = recent[i + 1]
            if c.close < c.open and nxt.close > nxt.open:
                blocks.append({"type": "bullish", "low": c.low, "high": c.open, "index": i})
            if c.close > c.open and nxt.close < nxt.open:
                blocks.append({"type": "bearish", "low": c.open, "high": c.high, "index": i})
        return blocks

    def identify_breaker_blocks(self, candles: List[Candle], lookback: int = 5) -> List[dict]:
        breakers: List[dict] = []
        if len(candles) < lookback + 2:
            return breakers
        recent = candles[-(lookback + 2) :]
        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]
            if curr.high > prev.high and curr.close < curr.open:
                breakers.append({"type": "bearish", "level": curr.high, "index": i})
            if curr.low < prev.low and curr.close > curr.open:
                breakers.append({"type": "bullish", "level": curr.low, "index": i})
        return breakers

    def analyze_asia_session(self, hourly_data) -> dict:
        if not hourly_data:
            return {}
        low = min(c.low for c in hourly_data)
        high = max(c.high for c in hourly_data)
        return {"low": low, "high": high}

    def analyze_london_session(self, hourly_data) -> dict:
        if not hourly_data:
            return {}
        low = min(c.low for c in hourly_data)
        high = max(c.high for c in hourly_data)
        return {"low": low, "high": high}

    def analyze_ny_session(self, hourly_data) -> dict:
        if not hourly_data:
            return {}
        low = min(c.low for c in hourly_data)
        high = max(c.high for c in hourly_data)
        return {"low": low, "high": high}

    def identify_ny_reversal(self, data) -> dict:
        history = data.get("history", [])
        if len(history) < 30:
            return {}
        day = history[-1].time.date()
        asia = [c for c in history if c.time.date() == day and ASIA.start <= c.time.time() <= ASIA.end]
        london = [c for c in history if c.time.date() == day and LONDON.start <= c.time.time() <= LONDON.end]
        ny = [c for c in history if c.time.date() == day and NY.start <= c.time.time() <= NY.end]
        if not asia or not london or not ny:
            return {}
        asia_trend_down = asia[-1].close < asia[0].open
        london_trend_down = london[-1].close < london[0].open
        ny_reversal = ny[-1].close > ny[0].open
        if asia_trend_down and london_trend_down and ny_reversal:
            return {"direction": "long"}
        asia_trend_up = asia[-1].close > asia[0].open
        london_trend_up = london[-1].close > london[0].open
        ny_reversal_down = ny[-1].close < ny[0].open
        if asia_trend_up and london_trend_up and ny_reversal_down:
            return {"direction": "short"}
        return {}

    def rhrl_protocol(self, daily_candles) -> dict:
        if len(daily_candles) < 3:
            return {}
        prev = daily_candles[-2]
        curr = daily_candles[-1]
        if curr.low < prev.low and curr.close > prev.open:
            return {"direction": "long"}
        if curr.high > prev.high and curr.close < prev.open:
            return {"direction": "short"}
        return {}

    def check_adrs_remaining(self, daily_adr: float, price_moved_today: float) -> float:
        if daily_adr <= 0:
            return 0.0
        return max(daily_adr - price_moved_today, 0.0)

    def identify_high_resistance_swing(self, lower_tf_data) -> dict:
        return {}

    def get_stop_hunt_confirmation(self, swing_type: str, signal_type: str) -> bool:
        return False

    def identify_setup(self, data) -> bool:
        history = data.get("history", [])
        if len(history) < 50:
            return False
        fvg = self.identify_fvg(history[-50:])
        ny_rev = self.identify_ny_reversal(data)
        return len(fvg) > 0 or bool(ny_rev)

    def generate_signals(self, data) -> dict:
        bar = data["bar"]
        history: List[Candle] = data.get("history", [])
        if len(history) < 20:
            return {}

        fvg_list = self.identify_fvg(history[-50:])
        if not fvg_list:
            ny_rev = self.identify_ny_reversal(data)
            if not ny_rev:
                return {}
            direction = ny_rev["direction"]
            if direction == "long":
                stop = min(c.low for c in history[-10:])
                target = self.project_target(bar.close, stop, "long")
                return {"direction": "long", "entry": bar.close, "stop": stop, "target": target}
            stop = max(c.high for c in history[-10:])
            target = self.project_target(bar.close, stop, "short")
            return {"direction": "short", "entry": bar.close, "stop": stop, "target": target}

        last_fvg = fvg_list[-1]
        if last_fvg["type"] == "bullish" and bar.close > bar.open:
            stop = min(c.low for c in history[-10:])
            target = self.project_target(bar.close, stop, "long")
            return {"direction": "long", "entry": bar.close, "stop": stop, "target": target}
        if last_fvg["type"] == "bearish" and bar.close < bar.open:
            stop = max(c.high for c in history[-10:])
            target = self.project_target(bar.close, stop, "short")
            return {"direction": "short", "entry": bar.close, "stop": stop, "target": target}
        return {}

    def validate_context(self, data) -> bool:
        return True
