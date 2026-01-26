from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Iterable, List, Optional

from backtesting_system.models.market import Candle


def validate_ohlcv(data) -> bool:
    required = {"open", "high", "low", "close"}
    columns = set(getattr(data, "columns", []))
    return required.issubset(columns) if columns else True


def validate_candles(candles: Iterable[Candle]) -> bool:
    last_time = None
    for candle in candles:
        if candle.high < max(candle.open, candle.close):
            return False
        if candle.low > min(candle.open, candle.close):
            return False
        if last_time and candle.time <= last_time:
            return False
        last_time = candle.time
    return True


@dataclass
class DataValidationReport:
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    row_count: int = 0
    invalid_ohlc: int = 0
    large_gaps: int = 0
    spikes: int = 0
    completeness_pct: float = 0.0
    quality_score: float = 0.0
    checksum: Optional[str] = None
    validation_log: List[str] = field(default_factory=list)
    report_path: Optional[str] = None
    validation_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class DataValidator:
    def __init__(
        self,
        gap_threshold_pct: float = 2.0,
        spike_zscore: float = 3.0,
        save_report: bool = False,
        report_dir: str = "validation_reports",
    ):
        self.gap_threshold_pct = gap_threshold_pct
        self.spike_zscore = spike_zscore
        self.save_report = save_report
        self.report_dir = report_dir

    def validate_candles(
        self,
        candles: List[Candle],
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        save_report: Optional[bool] = None,
    ) -> tuple[List[Candle], DataValidationReport]:
        report = DataValidationReport(symbol=symbol, timeframe=timeframe)
        validation_log: List[str] = []
        if not candles:
            return candles, report

        cleaned: List[Candle] = []
        invalid_ohlc = 0
        for candle in candles:
            if candle.high < candle.low or candle.high < candle.open or candle.high < candle.close:
                invalid_ohlc += 1
                continue
            cleaned.append(candle)

        report.invalid_ohlc = invalid_ohlc
        if invalid_ohlc:
            validation_log.append(f"OHLC invalid: {invalid_ohlc}")

        gaps = 0
        returns = []
        for i in range(1, len(cleaned)):
            prev = cleaned[i - 1]
            curr = cleaned[i]
            if prev.close != 0:
                gap_pct = abs((curr.open - prev.close) / prev.close) * 100
                if gap_pct > self.gap_threshold_pct:
                    gaps += 1
            if prev.close != 0:
                returns.append((curr.close - prev.close) / prev.close)

        report.large_gaps = gaps
        if gaps:
            validation_log.append(f"Large gaps: {gaps}")

        spikes = 0
        if len(returns) > 20:
            mean = sum(returns) / len(returns)
            variance = sum((r - mean) ** 2 for r in returns) / len(returns)
            std = variance ** 0.5
            if std > 0:
                for r in returns:
                    if abs((r - mean) / std) > self.spike_zscore:
                        spikes += 1
        report.spikes = spikes
        if spikes:
            validation_log.append(f"Spikes: {spikes}")

        report.row_count = len(cleaned)
        report.completeness_pct = (len(cleaned) / len(candles)) * 100 if candles else 0.0
        report.validation_log = validation_log
        report.quality_score = self._calculate_quality_score(report)
        report.checksum = self._calculate_checksum(cleaned)

        should_save = self.save_report if save_report is None else save_report
        if should_save:
            report.report_path = self._write_report(report)
        return cleaned, report

    def _calculate_quality_score(self, report: DataValidationReport) -> float:
        score = 1.0
        score -= len(report.validation_log) * 0.05
        missing_pct = max(0.0, 100.0 - report.completeness_pct)
        score -= (missing_pct / 100.0) * 0.2
        return max(score, 0.0)

    def _calculate_checksum(self, candles: List[Candle]) -> str:
        digest = hashlib.md5()
        for candle in candles:
            payload = f"{candle.time.isoformat()}|{candle.open}|{candle.high}|{candle.low}|{candle.close}|{candle.volume}\n"
            digest.update(payload.encode("utf-8"))
        return digest.hexdigest()

    def _write_report(self, report: DataValidationReport) -> str:
        Path(self.report_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{report.symbol or 'DATA'}_{report.timeframe or 'NA'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        path = Path(self.report_dir) / filename
        with path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(report), handle, indent=2, default=str)
        return str(path)


def summarize_validation_reports(report_dir: str, output_path: str | Path) -> dict:
    report_path = Path(report_dir)
    files = sorted(report_path.glob("*.json")) if report_path.exists() else []
    summary = {
        "report_count": 0,
        "unique_checksums": 0,
        "quality_score_avg": 0.0,
        "quality_score_min": 0.0,
        "quality_score_max": 0.0,
        "rows_avg": 0.0,
        "rows_min": 0,
        "rows_max": 0,
        "invalid_ohlc_total": 0,
        "large_gaps_total": 0,
        "spikes_total": 0,
        "latest_report": None,
    }
    if not files:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with Path(output_path).open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        return summary

    reports = []
    for file in files:
        try:
            with file.open("r", encoding="utf-8") as handle:
                reports.append(json.load(handle))
        except Exception:
            continue

    if not reports:
        return summary

    quality_scores = [r.get("quality_score", 0.0) for r in reports]
    rows = [r.get("row_count", 0) for r in reports]
    checksums = {r.get("checksum") for r in reports if r.get("checksum")}

    summary.update({
        "report_count": len(reports),
        "unique_checksums": len(checksums),
        "quality_score_avg": sum(quality_scores) / len(quality_scores),
        "quality_score_min": min(quality_scores),
        "quality_score_max": max(quality_scores),
        "rows_avg": sum(rows) / len(rows),
        "rows_min": min(rows),
        "rows_max": max(rows),
        "invalid_ohlc_total": sum(r.get("invalid_ohlc", 0) for r in reports),
        "large_gaps_total": sum(r.get("large_gaps", 0) for r in reports),
        "spikes_total": sum(r.get("spikes", 0) for r in reports),
        "latest_report": reports[-1],
    })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(output_path).open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)
    return summary
