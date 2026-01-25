from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle


class PriceActionStrategy(Strategy):
    def identify_daily_swing_framework(self, daily_candles) -> dict:
        if len(daily_candles) < 2:
            return {}
        prev = daily_candles[-2]
        curr = daily_candles[-1]
        if curr.close > prev.high:
            return {"bias": "bullish"}
        if curr.close < prev.low:
            return {"bias": "bearish"}
        return {"bias": "neutral"}

    def identify_intraday_reversal_setup(self, hourly_data) -> dict:
        if len(hourly_data) < 5:
            return {}
        last = hourly_data[-1]
        prior = hourly_data[-5:-1]
        rejection = sum(1 for c in prior if c.high < last.high and c.close < c.open)
        if rejection >= 2 and last.close > last.open:
            return {"direction": "long"}
        rejection = sum(1 for c in prior if c.low > last.low and c.close > c.open)
        if rejection >= 2 and last.close < last.open:
            return {"direction": "short"}
        return {}

    def identify_consolidation_raid(self, hourly_data, news_time) -> dict:
        if len(hourly_data) < 6:
            return {}
        recent = hourly_data[-6:]
        rng = max(c.high for c in recent) - min(c.low for c in recent)
        if rng == 0:
            return {}
        last = recent[-1]
        if (last.high - last.low) > 1.5 * rng:
            direction = "long" if last.close > last.open else "short"
            return {"direction": direction}
        return {}

    def identify_buy_day(self, daily_candle, hourly_data) -> bool:
        if not hourly_data:
            return False
        overnight = [c for c in hourly_data if c.time.hour < 8]
        if not overnight:
            return False
        overnight_low = min(c.low for c in overnight)
        return daily_candle.low <= overnight_low and daily_candle.close > daily_candle.open

    def detect_wicks_vs_bodies(self, candles) -> dict:
        if not candles:
            return {}
        last = candles[-1]
        body = abs(last.close - last.open)
        wick = (last.high - max(last.close, last.open)) + (min(last.close, last.open) - last.low)
        return {"body": body, "wick": wick}

    def identify_expansion_day(self, daily_candle) -> bool:
        return (daily_candle.high - daily_candle.low) > (abs(daily_candle.close - daily_candle.open) * 2)

    def identify_setup(self, data) -> bool:
        history = data.get("history", [])
        if len(history) < 3:
            return False
        return True

    def generate_signals(self, data) -> dict:
        history: list[Candle] = data.get("history", [])
        if len(history) < 3:
            return {}
        prev = history[-2]
        curr = history[-1]

        bullish_engulf = curr.close > curr.open and prev.close < prev.open and curr.close > prev.open
        bearish_engulf = curr.close < curr.open and prev.close > prev.open and curr.close < prev.open

        intraday = self.identify_intraday_reversal_setup(history[-24:])
        if intraday.get("direction") == "long":
            stop = min(c.low for c in history[-10:])
            risk = max(curr.close - stop, 0.00001)
            return {"direction": "long", "entry": curr.close, "stop": stop, "target": curr.close + 2 * risk}
        if intraday.get("direction") == "short":
            stop = max(c.high for c in history[-10:])
            risk = max(stop - curr.close, 0.00001)
            return {"direction": "short", "entry": curr.close, "stop": stop, "target": curr.close - 2 * risk}

        if bullish_engulf:
            stop = min(prev.low, curr.low)
            risk = max(curr.close - stop, 0.00001)
            return {"direction": "long", "entry": curr.close, "stop": stop, "target": curr.close + 2 * risk}
        if bearish_engulf:
            stop = max(prev.high, curr.high)
            risk = max(stop - curr.close, 0.00001)
            return {"direction": "short", "entry": curr.close, "stop": stop, "target": curr.close - 2 * risk}
        return {}

    def validate_context(self, data) -> bool:
        return True
