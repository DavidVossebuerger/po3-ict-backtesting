from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.models.market import Candle
from backtesting_system.strategies.ict_framework import (
    CISDValidator,
    OpeningRangeFramework,
    PDAArrayDetector,
    StopHuntDetector,
)


@dataclass
class WeeklyProfileContext:
    profile_type: Optional[str]
    confidence: float | None
    mon_tue_low: Optional[float]
    mon_tue_high: Optional[float]
    week_key: Optional[tuple]


class WeeklyProfileStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.profile_type = None
        self.dol = None
        self.doh = None
        self._last_signal_week = None
        self._daily_cache: Dict[datetime, List[Candle]] = {}
        self._daily_series: List[Candle] = []
        self._last_hist_len: int = 0
        self.detector = WeeklyProfileDetector()
        self.pda_detector = PDAArrayDetector()
        self.cisd_validator = CISDValidator()
        self.stop_hunt_detector = StopHuntDetector()
        self.opening_range = OpeningRangeFramework()
        self._signal_log: List[Dict[str, object]] = []
        self._signal_log_path: Path | None = None

    def identify_weekly_profile(self, weekly_data, daily_data) -> str | None:
        profile_type, confidence, _details = self.detector.detect_profile(daily_data, weekly_data, {})
        return profile_type

    def analyze_mon_tue(self, daily_candles: List[Candle]) -> Dict[str, float]:
        mon_tue = [c for c in daily_candles if c.time.weekday() in (0, 1)]
        if len(mon_tue) < 2:
            return {}
        low = min(c.low for c in mon_tue)
        high = max(c.high for c in mon_tue)
        direction = "long" if mon_tue[-1].close >= mon_tue[0].open else "short"
        return {"low": low, "high": high}

    def identify_setup(self, data) -> bool:
        bar = data["bar"]
        history = data.get("history", [])
        ctx = self._build_context(history)
        if ctx.profile_type is None:
            return False
        allowed_days = {
            "classic_expansion_long": {2, 3},
            "classic_expansion_short": {2, 3},
            "midweek_reversal_long": {2},
            "midweek_reversal_short": {2},
            "consolidation_reversal_long": {3, 4},
            "consolidation_reversal_short": {3, 4},
        }
        if bar.time.weekday() not in allowed_days.get(ctx.profile_type, set()):
            return False
        return ctx.week_key != self._last_signal_week

    def generate_signals(self, data) -> dict:
        bar = data["bar"]
        history = data.get("history", [])
        ctx = self._build_context(history)
        if ctx.profile_type is None:
            return {}
        if ctx.week_key == self._last_signal_week:
            return {}

        day = bar.time.weekday()
        allowed_days = {
            "classic_expansion_long": {2, 3},
            "classic_expansion_short": {2, 3},
            "midweek_reversal_long": {2},
            "midweek_reversal_short": {2},
            "consolidation_reversal_long": {3, 4},
            "consolidation_reversal_short": {3, 4},
        }
        if day not in allowed_days.get(ctx.profile_type, set()):
            return {}

        daily_candles = self._aggregate_daily(history)
        cisd = self.cisd_validator.detect_cisd(daily_candles, history[-20:])
        if not cisd.get("detected"):
            return {}

        signal_direction = "long" if ctx.profile_type.endswith("long") else "short"
        cisd_direction = "long" if cisd.get("type", "").lower() == "bullish" else "short"
        if signal_direction != cisd_direction:
            return {}

        if signal_direction == "long":
            swing_level = ctx.mon_tue_low if ctx.mon_tue_low is not None else min(c.low for c in history[-20:])
        else:
            swing_level = ctx.mon_tue_high if ctx.mon_tue_high is not None else max(c.high for c in history[-20:])
        stop_hunt = self.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
        if not stop_hunt.get("detected"):
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
        }

        confluence_score = ctx.confidence if ctx.confidence else 0.5
        if opening_range and self.opening_range.is_entry_in_zone(bar.close, opening_range):
            confluence_score += 0.15
        elif opening_range:
            confluence_score -= 0.10
        if confluence_score < 0.40:
            return {}

        direction = signal_direction
        entry = bar.close
        if direction == "long":
            stop = ctx.mon_tue_low if ctx.mon_tue_low is not None else bar.close * 0.99
            target = self.project_target(entry, stop, direction)
        else:
            stop = ctx.mon_tue_high if ctx.mon_tue_high is not None else bar.close * 1.01
            target = self.project_target(entry, stop, direction)

        if not self.validate_pda_array(entry, h1_arrays):
            return {}

        self._last_signal_week = ctx.week_key
        signal = {
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "confluence": confluence_score,
            "profile_type": ctx.profile_type,
        }
        self._record_signal(bar.time, signal, ctx)
        return signal

    def validate_pda_array(self, price, h1_pda) -> bool:
        if not h1_pda:
            return True
        entry_ok, _source = self.pda_detector.validate_entry_at_pda(price, h1_pda)
        return entry_ok

    def validate_context(self, data) -> bool:
        return True

    def calculate_dol_doh(self, daily_data) -> tuple:
        if not daily_data:
            return None, None
        dol = min(daily_data, key=lambda c: c.low).time.date()
        doh = max(daily_data, key=lambda c: c.high).time.date()
        return dol, doh

    def check_negative_conditions(self, daily_data) -> bool:
        return False

    def _build_context(self, history: List[Candle]) -> WeeklyProfileContext:
        daily = self._aggregate_daily(history)
        if len(daily) < 10:
            return WeeklyProfileContext(None, None, None, None, None)

        current_week = self._current_week_key(daily[-1].time)
        prev_week_key = self._previous_week_key(current_week)

        prev_week = [c for c in daily if self._current_week_key(c.time) == prev_week_key]
        prev_week = sorted([c for c in prev_week if c.time.weekday() <= 4], key=lambda c: c.time)
        this_week = [c for c in daily if self._current_week_key(c.time) == current_week]
        this_week = sorted([c for c in this_week if c.time.weekday() <= 4], key=lambda c: c.time)
        this_week_no_mon = [c for c in this_week if c.time.weekday() != 0]
        mon_tue_current = [c for c in this_week if c.time.weekday() in (0, 1)]
        if not prev_week or len(this_week_no_mon) < 2:
            return WeeklyProfileContext(None, None, None, None, current_week)

        prev_low = min(c.low for c in prev_week)
        prev_high = max(c.high for c in prev_week)
        mid = (prev_low + prev_high) / 2
        weekly_ohlc = {
            "open": prev_week[0].open,
            "high": max(c.high for c in prev_week),
            "low": min(c.low for c in prev_week),
            "close": prev_week[-1].close,
        }
        profile_type, confidence, _details = self.detector.detect_profile(prev_week, weekly_ohlc, {})

        if mon_tue_current:
            mon_tue_low = min(c.low for c in mon_tue_current)
            mon_tue_high = max(c.high for c in mon_tue_current)
        else:
            mon_tue_low = min(c.low for c in prev_week)
            mon_tue_high = max(c.high for c in prev_week)

        return WeeklyProfileContext(profile_type, confidence, mon_tue_low, mon_tue_high, current_week)

    def _aggregate_daily(self, history: List[Candle]) -> List[Candle]:
        if not history:
            return []
        if len(history) == self._last_hist_len:
            return self._daily_series

        for candle in history[self._last_hist_len :]:
            day_key = datetime(
                candle.time.year,
                candle.time.month,
                candle.time.day,
                tzinfo=timezone.utc,
            )
            self._daily_cache.setdefault(day_key, []).append(candle)
        self._last_hist_len = len(history)

        result: List[Candle] = []
        for day in sorted(self._daily_cache.keys()):
            chunk = self._daily_cache[day]
            result.append(
                Candle(
                    time=day,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=None,
                )
            )
        self._daily_series = result
        return result

    def _current_week_key(self, dt: datetime) -> tuple:
        iso = dt.isocalendar()
        return iso.year, iso.week

    def _previous_week_key(self, week_key: tuple) -> tuple:
        year, week = week_key
        if week > 1:
            return year, week - 1
        return year - 1, 52

    def _is_day_open(self, dt: datetime) -> bool:
        return dt.hour == 0 and dt.minute == 0

    def _record_signal(self, timestamp: datetime, signal: dict, ctx: WeeklyProfileContext) -> None:
        entry = {
            "time": timestamp.isoformat(),
            "profile_type": ctx.profile_type,
            "confidence": ctx.confidence,
            "direction": signal.get("direction"),
            "entry": signal.get("entry"),
            "stop": signal.get("stop"),
            "target": signal.get("target"),
            "mon_tue_low": ctx.mon_tue_low,
            "mon_tue_high": ctx.mon_tue_high,
            "week_key": ctx.week_key,
        }
        self._signal_log.append(entry)
        if self._signal_log_path is None:
            Path("backtest_logs").mkdir(parents=True, exist_ok=True)
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self._signal_log_path = Path("backtest_logs") / f"weekly_profile_signals_{stamp}.json"
        with self._signal_log_path.open("w", encoding="utf-8") as handle:
            json.dump(self._signal_log, handle, indent=2, default=str)

class WeeklyProfileDetector:
    def __init__(self):
        self.profiles = {
            0: "Seek & Destroy",
            1: "Classic Bullish Expansion",
            2: "Classic Bearish Expansion",
            3: "Midweek Reversal Up",
            4: "Midweek Reversal Down",
            5: "Consolidation Reversal",
        }

    def detect_profile(self, daily_candles: list[Candle], weekly_ohlc: dict, htf_array: dict) -> tuple[str | None, float, dict]:
        if len(daily_candles) < 3:
            return None, 0.0, {}

        mon_tue = daily_candles[0:2]
        wed = daily_candles[2]
        thu_fri = daily_candles[3:5] if len(daily_candles) >= 5 else []

        mon_tue_engagement = self._analyze_engagement(mon_tue) if len(mon_tue) == 2 else {"type": "insufficient"}
        wed_behavior = self._analyze_wednesday(wed)
        if len(thu_fri) == 2:
            thu_fri_expected = self._analyze_expectation(thu_fri, weekly_ohlc)
        else:
            expected_move = "neutral"
            if wed_behavior["direction"] == "higher":
                expected_move = "expansion_higher"
            elif wed_behavior["direction"] == "lower":
                expected_move = "expansion_lower"
            thu_fri_expected = {
                "expected_move": expected_move,
                "weekly_target": weekly_ohlc.get("high", 0.0),
                "confidence": 0.5,
            }

        if (
            mon_tue_engagement["type"] == "discount_engagement"
            and wed_behavior["direction"] == "higher"
            and thu_fri_expected["expected_move"] == "expansion_higher"
        ):
            return "classic_expansion_long", 0.85, self._details(mon_tue_engagement, wed_behavior, thu_fri_expected)
        if (
            mon_tue_engagement["type"] == "premium_engagement"
            and wed_behavior["direction"] == "lower"
            and thu_fri_expected["expected_move"] == "expansion_lower"
        ):
            return "classic_expansion_short", 0.85, self._details(mon_tue_engagement, wed_behavior, thu_fri_expected)
        if (
            mon_tue_engagement["type"] in {"consolidation", "retracement"}
            and wed_behavior["direction"] == "higher"
            and thu_fri_expected["expected_move"] == "expansion_higher"
        ):
            return "midweek_reversal_long", 0.75, self._details(mon_tue_engagement, wed_behavior, thu_fri_expected)
        if (
            mon_tue_engagement["type"] in {"consolidation", "retracement"}
            and wed_behavior["direction"] == "lower"
            and thu_fri_expected["expected_move"] == "expansion_lower"
        ):
            return "midweek_reversal_short", 0.75, self._details(mon_tue_engagement, wed_behavior, thu_fri_expected)
        if (
            mon_tue_engagement["type"] in {"consolidation", "choppy"}
            and wed_behavior["type"] == "external_range_test"
        ):
            return "consolidation_reversal_long", 0.70, self._details(mon_tue_engagement, wed_behavior, thu_fri_expected)

        return None, 0.30, self._details(mon_tue_engagement, wed_behavior, thu_fri_expected)

    def _details(self, engagement: dict, wed: dict, expectation: dict) -> dict:
        return {"engagement": engagement, "wednesday": wed, "expectation": expectation}

    def _analyze_engagement(self, mon_tue_candles: list[Candle]) -> dict:
        mon, tue = mon_tue_candles
        avg_price = (mon.close + tue.close) / 2
        price_range = max(mon.high, tue.high) - min(mon.low, tue.low)

        if avg_price and price_range < avg_price * 0.005:
            engagement_type = "consolidation"
        elif mon.close < mon.open and tue.close > tue.open:
            engagement_type = "discount_engagement"
        elif mon.close > mon.open and tue.close < tue.open:
            engagement_type = "premium_engagement"
        elif mon.close < mon.open and tue.close < tue.open:
            engagement_type = "retracement"
        else:
            engagement_type = "choppy"

        return {
            "type": engagement_type,
            "range_pips": price_range * 10000,
            "avg_price": avg_price,
        }

    def _analyze_wednesday(self, wed_candle: Candle) -> dict:
        if wed_candle.close > wed_candle.open:
            direction = "higher"
        elif wed_candle.close < wed_candle.open:
            direction = "lower"
        else:
            direction = "neutral"
        return {
            "direction": direction,
            "body_size": abs(wed_candle.close - wed_candle.open),
            "wick_ratio": (wed_candle.high - wed_candle.low) / max(abs(wed_candle.close - wed_candle.open), 0.0001),
            "type": "external_range_test" if abs(wed_candle.close - wed_candle.open) < (wed_candle.high - wed_candle.low) * 0.25 else "normal",
        }

    def _analyze_expectation(self, thu_fri_candles: list[Candle], weekly_ohlc: dict) -> dict:
        weekly_range = weekly_ohlc["high"] - weekly_ohlc["low"]
        return {
            "expected_move": "expansion_higher" if thu_fri_candles[-1].close >= thu_fri_candles[0].open else "expansion_lower",
            "weekly_target": weekly_ohlc["high"] + weekly_range * 0.1,
            "confidence": 0.7,
        }
