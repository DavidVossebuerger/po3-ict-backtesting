from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from backtesting_system.adapters.data_sources.csv_source import CSVDataSource
from backtesting_system.models.market import Candle
from backtesting_system.utils.validation import validate_candles


@dataclass
class CSVResamplePipeline:
    data_source: CSVDataSource
    output_dir: Path

    def run(self, symbol: str, timeframes: Iterable[str]) -> List[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        outputs: List[Path] = []

        for timeframe in timeframes:
            candles = self.data_source.load_ohlcv(symbol, timeframe, None, None)
            if not validate_candles(candles):
                raise ValueError(f"Candle validation failed for {symbol} {timeframe}")
            out_path = self.output_dir / f"{symbol.lower()}_{timeframe.lower()}.csv"
            self._write_candles(out_path, candles)
            outputs.append(out_path)

        return outputs

    def _write_candles(self, path: Path, candles: List[Candle]) -> None:
        with path.open("w", newline="", encoding="utf-8") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(["time_utc", "open", "high", "low", "close"])
            for c in candles:
                writer.writerow([
                    c.time.isoformat().replace("+00:00", "Z"),
                    f"{c.open:.5f}",
                    f"{c.high:.5f}",
                    f"{c.low:.5f}",
                    f"{c.close:.5f}",
                ])
