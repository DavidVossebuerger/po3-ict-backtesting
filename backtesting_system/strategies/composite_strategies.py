from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.strategies.weekly_profiles import WeeklyProfileStrategy
from backtesting_system.strategies.confluence import ConfluenceScorer
from backtesting_system.strategies.ict_framework import ICTFramework


class CompositeStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.weekly_profile_strategy = WeeklyProfileStrategy(params)
        self.ict_strategy = ICTFramework(params)
        self.min_confluence_level = float(params.get("min_confluence", 0.50))
        self.scorer = ConfluenceScorer()

    def calculate_confluence_score(self, data, context) -> float:
        profile_type = context.get("profile_type", "")
        profile_confidence = context.get("profile_confidence", 0.0)
        pda_type = context.get("pda_type", "")
        pda_at_entry = context.get("pda_at_entry", False)
        session_quality = context.get("session_quality", "neutral")
        opening_range_aligned = context.get("opening_range_aligned", False)
        stop_hunt_confirmed = context.get("stop_hunt_confirmed", False)
        news_impact = context.get("news_impact", "none")
        adr_remaining_pct = context.get("adr_remaining_pct", 0.0)

        return self.scorer.calculate_score(
            profile_type=profile_type,
            profile_confidence=profile_confidence,
            pda_type=pda_type,
            pda_at_entry=pda_at_entry,
            session_quality=session_quality,
            opening_range_aligned=opening_range_aligned,
            stop_hunt_confirmed=stop_hunt_confirmed,
            news_impact=news_impact,
            adr_remaining_pct=adr_remaining_pct,
        )

    def generate_signals(self, data) -> dict:
        weekly_signal = self.weekly_profile_strategy.generate_signals(data)
        ict_signal = self.ict_strategy.generate_signals(data)

        profile_type_map = {
            "classic_expansion_long": 1,
            "classic_expansion_short": 2,
            "midweek_reversal_long": 3,
            "midweek_reversal_short": 4,
            "consolidation_reversal_long": 5,
            "consolidation_reversal_short": 5,
        }
        profile_type = 0
        profile_confidence = 0.0
        if weekly_signal:
            profile_type = profile_type_map.get(weekly_signal.get("profile_type", ""), 1)
            profile_confidence = float(weekly_signal.get("confluence", 0.0))

        if weekly_signal:
            weekly_signal.setdefault("profile_type", "classic_expansion_long")
            if weekly_signal.get("confluence", 0.0) >= self.min_confluence_level:
                return weekly_signal
            return {}
        if ict_signal:
            context = self._build_context(data, ict_signal)
            score = self.calculate_confluence_score(data, context)
            if score >= self.min_confluence_level:
                ict_signal["confluence"] = score
                return ict_signal
        return {}

    def identify_setup(self, data) -> bool:
        return True

    def _build_context(self, data, signal) -> dict:
        history = data.get("history", [])
        daily_candles = self._daily_from_history(history)
        bar = data.get("bar")

        h1_arrays = {
            "fvgs": self.ict_strategy.pda_detector.identify_fair_value_gaps(history[-50:]),
            "order_blocks": self.ict_strategy.pda_detector.identify_order_blocks(history[-50:]),
            "breakers": self.ict_strategy.identify_breaker_blocks(history[-50:]),
        }
        entry_price = signal.get("entry") or (bar.close if bar else None)
        pda_at_entry = False
        pda_type = ""
        if entry_price is not None:
            pda_at_entry, pda_type = self.ict_strategy.pda_detector.validate_entry_at_pda(
                float(entry_price),
                h1_arrays,
            )

        opening_range_aligned = False
        if bar is not None:
            day_candles = [c for c in history if c.time.date() == bar.time.date()]
            if day_candles:
                day_low = min(c.low for c in day_candles)
                day_high = max(c.high for c in day_candles)
                opening_range = self.ict_strategy.opening_range.calculate_opening_range(
                    day_candles[0],
                    day_low,
                    day_high,
                )
                opening_range_aligned = self.ict_strategy.opening_range.is_entry_in_zone(
                    float(entry_price) if entry_price is not None else bar.close,
                    opening_range,
                )

        stop_hunt_confirmed = False
        if bar is not None and daily_candles:
            direction = signal.get("direction")
            if direction == "long":
                swing_level = daily_candles[-2].low if len(daily_candles) >= 2 else daily_candles[-1].low
            else:
                swing_level = daily_candles[-2].high if len(daily_candles) >= 2 else daily_candles[-1].high
            stop_hunt = self.ict_strategy.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
            stop_hunt_confirmed = bool(stop_hunt.get("detected"))

        return {
            "profile_type": signal.get("profile_type", ""),
            "profile_confidence": float(signal.get("confidence", 0.0)),
            "pda_type": pda_type,
            "pda_at_entry": pda_at_entry,
            "session_quality": "NY_reversal" if self.ict_strategy.identify_ny_reversal(data) else "neutral",
            "opening_range_aligned": opening_range_aligned,
            "stop_hunt_confirmed": stop_hunt_confirmed,
            "news_impact": self._identify_news_impact(bar, data.get("symbol", "")),
            "adr_remaining_pct": self._adr_remaining_pct(history),
        }

    def _identify_news_impact(self, bar, symbol: str) -> str:
        if bar is None:
            return "none"
        if not self.weekly_profile_strategy.news_calendar:
            return "none"
        currencies = self.weekly_profile_strategy._extract_currencies(symbol)
        if self.weekly_profile_strategy.news_calendar.get_high_impact_events(bar.time, currencies=currencies):
            return "high_impact"
        return "none"

    def _daily_from_history(self, history):
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
                type(chunk[0])(
                    time=chunk[0].time.replace(hour=0, minute=0, second=0, microsecond=0),
                    open=chunk[0].open,
                    high=max(x.high for x in chunk),
                    low=min(x.low for x in chunk),
                    close=chunk[-1].close,
                    volume=None,
                )
            )
        return result

    def _adr_remaining_pct(self, history) -> float:
        daily = self._daily_from_history(history)
        if len(daily) < 2:
            return 0.0
        ranges = [d.high - d.low for d in daily[-15:-1]]
        if not ranges:
            return 0.0
        adr = sum(ranges) / len(ranges)
        today_range = daily[-1].high - daily[-1].low
        if today_range <= 0:
            return 0.0
        return adr / today_range

    def validate_context(self, data) -> bool:
        return True
