from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.strategies.weekly_profiles import WeeklyProfileStrategy
from backtesting_system.strategies.confluence import ConfluenceScorer
from backtesting_system.strategies.ict_framework import ICTFramework
from backtesting_system.strategies.price_action import PriceActionStrategy


class CompositeStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.weekly_profile_strategy = WeeklyProfileStrategy(params)
        self.ict_strategy = ICTFramework(params)
        self.pa_strategy = PriceActionStrategy(params)
        self.min_confluence_level = 4.0
        self.scorer = ConfluenceScorer()

    def calculate_confluence_score(self, data, context) -> float:
        profile_type = context.get("profile_type", 0)
        profile_confidence = context.get("profile_confidence", 0.0)
        pda_alignment = context.get("pda_alignment", False)
        session_quality = context.get("session_quality", "neutral")
        rhrl_active = context.get("rhrl_active", False)
        stop_hunt_confirmed = context.get("stop_hunt_confirmed", False)
        news_impact = context.get("news_impact", "none")
        adr_remaining_pct = context.get("adr_remaining_pct", 0.0)

        return self.scorer.calculate_score(
            profile_type=profile_type,
            profile_confidence=profile_confidence,
            pda_alignment=pda_alignment,
            session_quality=session_quality,
            rhrl_active=rhrl_active,
            stop_hunt_confirmed=stop_hunt_confirmed,
            news_impact=news_impact,
            adr_remaining_pct=adr_remaining_pct,
        )

    def generate_signals(self, data) -> dict:
        weekly_signal = self.weekly_profile_strategy.generate_signals(data)
        ict_signal = self.ict_strategy.generate_signals(data)
        pa_signal = self.pa_strategy.generate_signals(data)

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

        session_quality = "NY_reversal" if self.ict_strategy.identify_ny_reversal(data) else "neutral"
        rhrl_active = bool(self.ict_strategy.rhrl_protocol(self._daily_from_history(data.get("history", []))))
        adr_remaining_pct = self._adr_remaining_pct(data.get("history", []))

        context = {
            "weekly_profile": bool(weekly_signal),
            "ict_signal": bool(ict_signal),
            "pa_signal": bool(pa_signal),
            "profile_type": profile_type,
            "profile_confidence": profile_confidence,
            "session_quality": session_quality,
            "rhrl_active": rhrl_active,
            "adr_remaining_pct": adr_remaining_pct,
        }
        score = self.calculate_confluence_score(data, context)
        if score < self.min_confluence_level:
            return {}

        if weekly_signal:
            weekly_signal.setdefault("profile_type", "classic_expansion_long")
            weekly_signal["confluence"] = score
            return weekly_signal
        if ict_signal:
            ict_signal["confluence"] = score
            return ict_signal
        if pa_signal:
            pa_signal["confluence"] = score
            return pa_signal
        return {}

    def identify_setup(self, data) -> bool:
        return True

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
