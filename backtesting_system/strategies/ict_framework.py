from __future__ import annotations

from datetime import datetime
from typing import List

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle
from backtesting_system.utils.timezones import ASIA, LONDON, NY


class KillzoneValidator:
    KILLZONES = {
        "london_open": (2, 5),
        "ny_am": (8, 11),
        "ny_pm": (13, 16),
    }

    def is_valid_killzone(
        self,
        dt: datetime,
        timezone_offset: int = -5,
        allow_monday: bool = False,
    ) -> bool:
        est_hour = (dt.hour + timezone_offset) % 24
        if dt.weekday() == 0 and not allow_monday:
            return False
        for _zone, (start, end) in self.KILLZONES.items():
            if start <= est_hour < end:
                return True
        return False


class PDAArrayDetector:
    def identify_fair_value_gaps(self, candles: List[Candle]) -> List[dict]:
        fvgs: List[dict] = []
        if len(candles) < 3:
            return fvgs
        for i in range(2, len(candles)):
            c1 = candles[i - 2]
            c3 = candles[i]
            if c1.high < c3.low:
                fvgs.append({
                    "type": "bullish",
                    "low": c1.high,
                    "high": c3.low,
                    "mid": (c1.high + c3.low) / 2,
                    "size_pips": (c3.low - c1.high) * 10000,
                    "index": i,
                })
            elif c1.low > c3.high:
                fvgs.append({
                    "type": "bearish",
                    "low": c3.high,
                    "high": c1.low,
                    "mid": (c3.high + c1.low) / 2,
                    "size_pips": (c1.low - c3.high) * 10000,
                    "index": i,
                })
        return fvgs

    def identify_order_blocks(self, candles: List[Candle]) -> List[dict]:
        obs: List[dict] = []
        if len(candles) < 2:
            return obs
        for i in range(1, len(candles)):
            prev = candles[i - 1]
            curr = candles[i]
            if prev.close < prev.open and curr.close > curr.open:
                obs.append({
                    "type": "bullish",
                    "low": prev.low,
                    "high": prev.close,
                    "reversal_index": i,
                    "liquidity_level": prev.close,
                })
            elif prev.close > prev.open and curr.close < curr.open:
                obs.append({
                    "type": "bearish",
                    "low": prev.close,
                    "high": prev.high,
                    "reversal_index": i,
                    "liquidity_level": prev.close,
                })
        return obs

    def validate_entry_at_pda(self, entry_price: float, arrays: dict, tolerance_pips: float = 5.0) -> tuple[bool, str | None]:
        tolerance = tolerance_pips / 10000
        for fvg in arrays.get("fvgs", []):
            if fvg["low"] - tolerance <= entry_price <= fvg["high"] + tolerance:
                return True, "fvg"
        for ob in arrays.get("order_blocks", []):
            if ob["low"] - tolerance <= entry_price <= ob["high"] + tolerance:
                return True, "order_block"
        return False, None


class CISDValidator:
    def detect_cisd(self, daily_candles: List[Candle], h1_candles: List[Candle]) -> dict:
        if len(daily_candles) < 2 or len(h1_candles) < 5:
            return {"detected": False}
        prev_daily = daily_candles[-2]
        curr_daily = daily_candles[-1]
        swing_high_prev = prev_daily.high
        swing_low_prev = prev_daily.low
        broke_above = curr_daily.high > swing_high_prev
        broke_below = curr_daily.low < swing_low_prev
        if not (broke_above or broke_below):
            return {"detected": False, "reason": "no_range_break"}
        recent_h1 = h1_candles[-3:]
        closes_above = sum(1 for c in recent_h1 if c.close > swing_high_prev)
        closes_below = sum(1 for c in recent_h1 if c.close < swing_low_prev)
        latest_h1 = recent_h1[-1]
        if broke_above and closes_above >= 2:
            wick_rejection = latest_h1.low <= swing_high_prev < latest_h1.close
            return {
                "detected": True,
                "type": "bullish",
                "breaker_level": swing_high_prev,
                "strength": "strong" if wick_rejection or closes_above == 3 else "weak",
                "closes_confirmed": closes_above,
            }
        if broke_below and closes_below >= 2:
            wick_rejection = latest_h1.high >= swing_low_prev > latest_h1.close
            return {
                "detected": True,
                "type": "bearish",
                "breaker_level": swing_low_prev,
                "strength": "strong" if wick_rejection or closes_below == 3 else "weak",
                "closes_confirmed": closes_below,
            }
        return {"detected": False, "reason": "h1_no_confirmation"}


class StopHuntDetector:
    def detect_stop_hunt(self, lower_tf_candles: List[Candle], swing_level: float, lookback: int = 20) -> dict:
        recent = lower_tf_candles[-lookback:]
        if not recent:
            return {"detected": False}
        avg_range = sum(c.high - c.low for c in recent) / len(recent)
        for candle in recent:
            body = abs(candle.close - candle.open)
            if candle.low < swing_level < candle.high:
                lower_wick = swing_level - candle.low
                if lower_wick > 0 and body > 0 and lower_wick >= body * 2.5 and lower_wick >= avg_range * 0.5 and candle.close > candle.open:
                    return {
                        "detected": True,
                        "type": "bullish",
                        "level_swept": swing_level,
                        "wick_size": lower_wick,
                        "body_size": body,
                        "wick_ratio": lower_wick / body if body > 0 else 0,
                        "strength": "strong" if (lower_wick / body) > 3.0 else "medium",
                    }
                upper_wick = candle.high - swing_level
                if upper_wick > 0 and body > 0 and upper_wick >= body * 2.5 and upper_wick >= avg_range * 0.5 and candle.close < candle.open:
                    return {
                        "detected": True,
                        "type": "bearish",
                        "level_swept": swing_level,
                        "wick_size": upper_wick,
                        "body_size": body,
                        "wick_ratio": upper_wick / body if body > 0 else 0,
                        "strength": "strong" if (upper_wick / body) > 3.0 else "medium",
                    }
        return {"detected": False}


class SMTDetector:
    """
    Smart Money Techniques (SMT) divergence detector.

    Compares correlated pairs to identify divergence at key levels.
    """

    CORRELATED_PAIRS = {
        "EURUSD": ["GBPUSD", "AUDUSD", "NZDUSD"],
        "GBPUSD": ["EURUSD", "AUDUSD"],
        "USDJPY": ["USDCHF", "USDCAD"],
        "AUDUSD": ["NZDUSD", "EURUSD"],
    }

    def detect_smt_divergence(
        self,
        symbol: str,
        current_data: List[Candle],
        correlated_data: dict[str, List[Candle]],
        lookback: int = 10,
    ) -> dict:
        if len(current_data) < lookback:
            return {"detected": False, "reason": "insufficient_data"}

        base_symbol = symbol[:6]
        correlated_symbols = self.CORRELATED_PAIRS.get(base_symbol, [])
        if not correlated_symbols:
            return {"detected": False, "reason": "no_correlated_pairs"}

        recent = current_data[-lookback:]
        current_high = max(c.high for c in recent)
        current_low = min(c.low for c in recent)
        current_making_higher_high = recent[-1].high >= current_high
        current_making_lower_low = recent[-1].low <= current_low

        divergences: List[dict] = []
        for corr_symbol in correlated_symbols:
            corr_recent = correlated_data.get(corr_symbol, [])[-lookback:]
            if len(corr_recent) < lookback:
                continue

            corr_high = max(c.high for c in corr_recent)
            corr_low = min(c.low for c in corr_recent)
            corr_making_higher_high = corr_recent[-1].high >= corr_high
            corr_making_lower_low = corr_recent[-1].low <= corr_low

            if current_making_higher_high and not corr_making_higher_high:
                divergences.append({
                    "type": "bearish",
                    "symbol": symbol,
                    "correlated": corr_symbol,
                    "current_high": current_high,
                    "corr_high": corr_high,
                })

            if current_making_lower_low and not corr_making_lower_low:
                divergences.append({
                    "type": "bullish",
                    "symbol": symbol,
                    "correlated": corr_symbol,
                    "current_low": current_low,
                    "corr_low": corr_low,
                })

        if divergences:
            return {
                "detected": True,
                "divergences": divergences,
                "count": len(divergences),
                "strength": "strong" if len(divergences) >= 2 else "weak",
            }

        return {"detected": False, "reason": "no_divergence"}


class OpeningRangeFramework:
    def calculate_opening_range(self, daily_candle: Candle, day_low_so_far: float, day_high_so_far: float) -> dict:
        opening_price = daily_candle.open
        distance_to_low = opening_price - day_low_so_far
        distance_to_high = day_high_so_far - opening_price
        if distance_to_low > distance_to_high:
            expected_high = opening_price + distance_to_low
            return {
                "opening_price": opening_price,
                "current_low": day_low_so_far,
                "current_high": day_high_so_far,
                "initial_direction": "down",
                "expected_reversal": "up",
                "expected_target": expected_high,
                "range_size": distance_to_low * 2,
                "entry_zone": (day_low_so_far, opening_price),
                "stop_zone": (opening_price, expected_high),
            }
        expected_low = opening_price - distance_to_high
        return {
            "opening_price": opening_price,
            "current_low": day_low_so_far,
            "current_high": day_high_so_far,
            "initial_direction": "up",
            "expected_reversal": "down",
            "expected_target": expected_low,
            "range_size": distance_to_high * 2,
            "entry_zone": (opening_price, day_high_so_far),
            "stop_zone": (expected_low, opening_price),
        }

    def is_entry_in_zone(self, entry_price: float, or_framework: dict) -> bool:
        zone = or_framework.get("entry_zone", (0, 0))
        return zone[0] <= entry_price <= zone[1]


class ICTFramework(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.killzone = KillzoneValidator()
        self.pda_detector = PDAArrayDetector()
        self.cisd_validator = CISDValidator()
        self.stop_hunt_detector = StopHuntDetector()
        self.opening_range = OpeningRangeFramework()
        self.smt_detector = SMTDetector()

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

    def calculate_stop_loss(
        self,
        direction: str,
        entry: float,
        h1_arrays: dict,
        daily_candles: List[Candle],
        buffer_pips: float = 2.0,
    ) -> float:
        buffer = buffer_pips / 10000
        if direction == "long":
            obs = [
                ob for ob in h1_arrays.get("order_blocks", [])
                if ob.get("type") == "bullish" and ob.get("low", entry) < entry
            ]
            if obs:
                nearest_ob = max(obs, key=lambda x: x.get("low", entry))
                return float(nearest_ob["low"]) - buffer

            fvgs = [
                fvg for fvg in h1_arrays.get("fvgs", [])
                if fvg.get("type") == "bullish" and fvg.get("low", entry) < entry
            ]
            if fvgs:
                nearest_fvg = max(fvgs, key=lambda x: x.get("low", entry))
                return float(nearest_fvg["low"]) - buffer

            breakers = [
                brk for brk in h1_arrays.get("breakers", [])
                if brk.get("type") == "bullish" and brk.get("level", entry) < entry
            ]
            if breakers:
                nearest_brk = max(breakers, key=lambda x: x.get("level", entry))
                return float(nearest_brk["level"]) - buffer

            if len(daily_candles) >= 3:
                recent_lows = [c.low for c in daily_candles[-5:]]
                swing_low = min(recent_lows)
                if swing_low < daily_candles[-1].low:
                    return swing_low - (buffer * 2.5)

            if len(daily_candles) >= 5:
                week_low = min(c.low for c in daily_candles[-5:])
                return week_low - (buffer * 3.0)

            if len(daily_candles) >= 2:
                avg_range = sum(c.high - c.low for c in daily_candles[-5:]) / 5
                return entry - (avg_range * 1.5)

            return entry - (entry * 0.01)

        obs = [
            ob for ob in h1_arrays.get("order_blocks", [])
            if ob.get("type") == "bearish" and ob.get("high", entry) > entry
        ]
        if obs:
            nearest_ob = min(obs, key=lambda x: x.get("high", entry))
            return float(nearest_ob["high"]) + buffer

        fvgs = [
            fvg for fvg in h1_arrays.get("fvgs", [])
            if fvg.get("type") == "bearish" and fvg.get("high", entry) > entry
        ]
        if fvgs:
            nearest_fvg = min(fvgs, key=lambda x: x.get("high", entry))
            return float(nearest_fvg["high"]) + buffer

        breakers = [
            brk for brk in h1_arrays.get("breakers", [])
            if brk.get("type") == "bearish" and brk.get("level", entry) > entry
        ]
        if breakers:
            nearest_brk = min(breakers, key=lambda x: x.get("level", entry))
            return float(nearest_brk["level"]) + buffer

        if len(daily_candles) >= 3:
            recent_highs = [c.high for c in daily_candles[-5:]]
            swing_high = max(recent_highs)
            if swing_high > daily_candles[-1].high:
                return swing_high + (buffer * 2.5)

        if len(daily_candles) >= 5:
            week_high = max(c.high for c in daily_candles[-5:])
            return week_high + (buffer * 3.0)

        if len(daily_candles) >= 2:
            avg_range = sum(c.high - c.low for c in daily_candles[-5:]) / 5
            return entry + (avg_range * 1.5)

        return entry + (entry * 0.01)

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
        if not self.killzone.is_valid_killzone(data["bar"].time):
            return False
        fvg = self.identify_fvg(history[-50:])
        ny_rev = self.identify_ny_reversal(data)
        return len(fvg) > 0 or bool(ny_rev)

    def generate_signals(self, data) -> dict:
        bar = data["bar"]
        history: List[Candle] = data.get("history", [])
        if len(history) < 20:
            return {}
        if not self.killzone.is_valid_killzone(bar.time):
            return {}

        daily = self._daily_from_history(history)
        cisd = self.cisd_validator.detect_cisd(daily, history)
        if not cisd.get("detected"):
            return {}

        day_candles = [c for c in history if c.time.date() == bar.time.date()]
        if day_candles:
            day_low = min(c.low for c in day_candles)
            day_high = max(c.high for c in day_candles)
            opening_range = self.opening_range.calculate_opening_range(day_candles[0], day_low, day_high)
        else:
            opening_range = {}

        h1_arrays = {
            "fvgs": self.pda_detector.identify_fair_value_gaps(history[-50:]),
            "order_blocks": self.pda_detector.identify_order_blocks(history[-50:]),
            "breakers": self.identify_breaker_blocks(history[-50:]),
        }

        fvg_list = self.identify_fvg(history[-50:])
        if not fvg_list:
            ny_rev = self.identify_ny_reversal(data)
            if not ny_rev:
                return {}
            direction = ny_rev["direction"]
            if direction == "long":
                stop = self.calculate_stop_loss("long", bar.close, h1_arrays, daily)
                target = self.project_target(bar.close, stop, "long")
                entry_ok, _source = self.pda_detector.validate_entry_at_pda(bar.close, h1_arrays)
                if not entry_ok:
                    return {}
                if opening_range and not self.opening_range.is_entry_in_zone(bar.close, opening_range):
                    return {}
                swing_level = daily[-2].low if len(daily) >= 2 else stop
                stop_hunt = self.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
                if not stop_hunt.get("detected"):
                    return {}
                return {"direction": "long", "entry": bar.close, "stop": stop, "target": target}
            stop = self.calculate_stop_loss("short", bar.close, h1_arrays, daily)
            target = self.project_target(bar.close, stop, "short")
            entry_ok, _source = self.pda_detector.validate_entry_at_pda(bar.close, h1_arrays)
            if not entry_ok:
                return {}
            if opening_range and not self.opening_range.is_entry_in_zone(bar.close, opening_range):
                return {}
            swing_level = daily[-2].high if len(daily) >= 2 else stop
            stop_hunt = self.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
            if not stop_hunt.get("detected"):
                return {}
            return {"direction": "short", "entry": bar.close, "stop": stop, "target": target}

        last_fvg = fvg_list[-1]
        if last_fvg["type"] == "bullish" and bar.close > bar.open:
            stop = self.calculate_stop_loss("long", bar.close, h1_arrays, daily)
            target = self.project_target(bar.close, stop, "long")
            entry_ok, _source = self.pda_detector.validate_entry_at_pda(bar.close, h1_arrays)
            if not entry_ok:
                return {}
            if opening_range and not self.opening_range.is_entry_in_zone(bar.close, opening_range):
                return {}
            swing_level = daily[-2].low if len(daily) >= 2 else stop
            stop_hunt = self.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
            if not stop_hunt.get("detected"):
                return {}
            return {"direction": "long", "entry": bar.close, "stop": stop, "target": target}
        if last_fvg["type"] == "bearish" and bar.close < bar.open:
            stop = self.calculate_stop_loss("short", bar.close, h1_arrays, daily)
            target = self.project_target(bar.close, stop, "short")
            entry_ok, _source = self.pda_detector.validate_entry_at_pda(bar.close, h1_arrays)
            if not entry_ok:
                return {}
            if opening_range and not self.opening_range.is_entry_in_zone(bar.close, opening_range):
                return {}
            swing_level = daily[-2].high if len(daily) >= 2 else stop
            stop_hunt = self.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
            if not stop_hunt.get("detected"):
                return {}
            return {"direction": "short", "entry": bar.close, "stop": stop, "target": target}
        return {}

    def _daily_from_history(self, history: List[Candle]) -> List[Candle]:
        if not history:
            return []
        daily = {}
        for c in history:
            key = (c.time.year, c.time.month, c.time.day)
            daily.setdefault(key, []).append(c)
        result = []
        for key in sorted(daily.keys()):
            chunk = daily[key]
            result.append(
                Candle(
                    time=chunk[0].time.replace(hour=0, minute=0, second=0, microsecond=0),
                    open=chunk[0].open,
                    high=max(x.high for x in chunk),
                    low=min(x.low for x in chunk),
                    close=chunk[-1].close,
                    volume=None,
                )
            )
        return result

    def validate_context(self, data) -> bool:
        return True
