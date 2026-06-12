from __future__ import annotations

from backtesting_system.core.strategy_base import Strategy
from backtesting_system.strategies.confluence import ConfluenceScorer
from backtesting_system.strategies.ict_framework import ICTFramework
from backtesting_system.utils.market_calendar import aggregate_daily_by_ny
from backtesting_system.utils.timezones import to_new_york


class CompositeStrategy(Strategy):
    def __init__(self, params: dict):
        super().__init__(params)
        self.ict_strategy = ICTFramework(params)
        self.min_confluence_level = float(params.get("min_confluence", 0.50))
        self.scorer = ConfluenceScorer()
        # Incremental daily-aggregation cache: track the last history
        # index processed, only walk the new tail, and merge same-NY-day
        # bars into the existing tail candle.
        from datetime import datetime, timezone
        self._daily_series: list = []
        self._last_history_idx: int = -1

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
        ict_signal = self.ict_strategy.generate_signals(data)
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
        symbol = data.get("symbol", "")

        h1_arrays = {
            "fvgs": self.ict_strategy.pda_detector.identify_fair_value_gaps(
                history[-50:],
                pip_size=self.get_pip_size(symbol),
            ),
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
                pip_size=self.get_pip_size(symbol),
            )

        opening_range_aligned = False
        if bar is not None:
            ny_day = to_new_york(bar.time).date()
            day_candles = [c for c in history if to_new_york(c.time).date() == ny_day]
            if day_candles:
                opening_range = self.ict_strategy.opening_range.calculate_static_opening_range(
                    day_candles,
                    cutoff_hour=int(self.params.get("opening_range_cutoff_hour", 8)),
                    cutoff_minute=int(self.params.get("opening_range_cutoff_minute", 30)),
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
        news_calendar = getattr(self.ict_strategy, "news_calendar", None)
        if not news_calendar:
            return "none"
        currencies = self.ict_strategy._extract_currencies(symbol)
        if news_calendar.get_high_impact_events(bar.time, currencies=currencies):
            return "high_impact"
        return "none"

    def _daily_from_history(self, history):
        """Return the daily NY-time candles for ``history``.

        Incremental O(n) pattern: cache the aggregated series and only
        walk the new tail. Bars for the same NY trading day are merged
        into the existing tail candle (updating high/low/close) rather
        than appended as duplicates.
        """
        if not history:
            return []
        if self._last_history_idx >= len(history) - 1:
            return self._daily_series
        from backtesting_system.utils.market_calendar import ny_date_key
        from backtesting_system.models.market import Candle
        from datetime import datetime, timezone
        start = self._last_history_idx + 1
        new_buckets: dict[tuple, list] = {}
        for candle in history[start:]:
            d = ny_date_key(candle.time)
            new_buckets.setdefault(d, []).append(candle)
        # Merge same-day bars into the existing tail candle so we don't
        # append a duplicate when the NY day has not rolled over.
        if self._daily_series and new_buckets:
            tail_day = (
                self._daily_series[-1].time.year,
                self._daily_series[-1].time.month,
                self._daily_series[-1].time.day,
            )
            if tail_day in new_buckets:
                extras = new_buckets.pop(tail_day)
                last = self._daily_series[-1]
                self._daily_series[-1] = Candle(
                    time=last.time,
                    open=last.open,
                    high=max(last.high, max(c.high for c in extras)),
                    low=min(last.low, min(c.low for c in extras)),
                    close=extras[-1].close,
                    volume=None,
                )
        self._last_history_idx = len(history) - 1
        for d in sorted(new_buckets.keys()):
            chunk = sorted(new_buckets[d], key=lambda c: c.time)
            if not chunk:
                continue
            self._daily_series.append(
                Candle(
                    time=datetime(d[0], d[1], d[2], tzinfo=timezone.utc),
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=None,
                )
            )
        return self._daily_series

    def _adr_remaining_pct(self, history) -> float:
        daily = self._daily_from_history(history)
        if len(daily) < 2:
            return 0.0
        ranges = [d.high - d.low for d in daily[-15:-1]]
        if not ranges:
            return 0.0
        adr = sum(ranges) / len(ranges)
        if adr <= 0:
            return 0.0
        today_range = daily[-1].high - daily[-1].low
        remaining = max(adr - max(today_range, 0.0), 0.0)
        return min(remaining / adr, 1.0)

    def validate_context(self, data) -> bool:
        return True
