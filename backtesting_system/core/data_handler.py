from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from backtesting_system.interfaces.data_source import DataSource
from backtesting_system.models.market import Candle
from backtesting_system.utils.timezones import ASIA, LONDON, NY
from backtesting_system.utils.validation import DataValidator, validate_candles


@dataclass
class DataHandler:
    data_source: DataSource
    validator: DataValidator | None = None

    def load_ohlcv(self, symbol: str, timeframe: str, start_date, end_date):
        candles = self.data_source.load_ohlcv(symbol, timeframe, start_date, end_date)
        if self.validator:
            candles, report = self.validator.validate_candles(list(candles), symbol=symbol)
        return candles

    def get_volume_profile(self, symbol: str, date):
        return self.data_source.load_volume_profile(symbol, date)

    def fetch_economic_calendar(self, start_date, end_date, importance: str = "high"):
        return self.data_source.fetch_economic_calendar(start_date, end_date, importance)

    def validate_data_integrity(self, candles: Iterable[Candle]) -> bool:
        return validate_candles(candles)

    def align_timeframes(
        self,
        primary: List[Candle],
        secondary: Dict[str, List[Candle]],
    ) -> Dict[str, Dict]:
        primary_index = {c.time: c for c in primary}
        aligned: Dict[str, Dict] = {}
        for tf, candles in secondary.items():
            aligned[tf] = {c.time: c for c in candles if c.time in primary_index}
        return aligned

    def add_market_regime(self, candles: List[Candle], atr_period: int = 14, threshold: float = 1.5):
        if len(candles) < atr_period + 1:
            return []
        trs = []
        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]
            tr = max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
            trs.append(tr)
        atrs = []
        for i in range(atr_period, len(trs) + 1):
            atrs.append(sum(trs[i - atr_period : i]) / atr_period)
        avg_atr = sum(atrs) / len(atrs) if atrs else 0.0
        regimes = []
        for idx, atr in enumerate(atrs, start=atr_period):
            regime = "high_vol" if avg_atr and atr > avg_atr * threshold else "normal"
            regimes.append({"time": candles[idx].time, "atr": atr, "regime": regime})
        return regimes

    def get_intraday_sessions(self, candles: List[Candle]) -> Dict[str, List[Candle]]:
        sessions = {"asia": [], "london": [], "ny": []}
        for candle in candles:
            t = candle.time.time()
            if ASIA.start <= t <= ASIA.end:
                sessions["asia"].append(candle)
            if LONDON.start <= t <= LONDON.end:
                sessions["london"].append(candle)
            if NY.start <= t <= NY.end:
                sessions["ny"].append(candle)
        return sessions
