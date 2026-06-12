from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from backtesting_system.adapters.data_sources.csv_source import CSVDataSource
from backtesting_system.adapters.execution.simulated_broker import SimulatedBroker
from backtesting_system.analytics.monte_carlo import monte_carlo_resample
from backtesting_system.analytics.reporting import (
    build_report,
    write_report,
    write_summary_csv,
    write_trades,
    write_trades_detailed,
    write_walk_forward_csv,
    write_parameter_sensitivity_csv,
    write_monte_carlo_csv,
    write_pdf_report,
)
from backtesting_system.analytics.visualizations import (
    plot_drawdown,
    plot_equity_curve,
    plot_pnl_distribution,
    plot_trades_with_levels,
)
from backtesting_system.analytics.statistics import (
    anova_oneway,
    binomial_test,
    t_test_independent,
)
from backtesting_system.config.trading_parameters import (
    DEFAULT_PARAMS,
    END_DATE_CALIBRATION,
    END_DATE_FORWARD,
    END_DATE_OOS_VALIDATION,
    INDEX_SYMBOLS,
    START_DATE_CALIBRATION,
    START_DATE_FORWARD,
    START_DATE_OOS_VALIDATION,
    SYMBOLS,
)
from backtesting_system.core.backtest_engine import BacktestEngine
from backtesting_system.core.data_handler import DataHandler
from backtesting_system.core.risk_manager import RiskManager
from backtesting_system.pipelines.backtest_pipeline import BacktestPipeline
from backtesting_system.pipelines.csv_resample_pipeline import CSVResamplePipeline
from backtesting_system.pipelines.parameter_sensitivity import ParameterSensitivityPipeline
from backtesting_system.pipelines.stress_testing import StrategyStressTest
from backtesting_system.pipelines.walk_forward import WalkForwardPipeline
from backtesting_system.strategies.benchmark_buy_hold import BuyHoldStrategy
from backtesting_system.strategies.benchmark_ma_crossover import MovingAverageCrossoverStrategy
from backtesting_system.strategies.benchmark_random import RandomBaselineStrategy
from backtesting_system.strategies.composite_strategies import CompositeStrategy
from backtesting_system.strategies.daily_swing_framework import DailySwingFrameworkStrategy
from backtesting_system.utils.hashing import md5_file
from backtesting_system.utils.logging import configure_logging
from backtesting_system.utils.validation import DataValidator


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PO3 ICT backtest pipeline")
    parser.add_argument(
        "--symbols",
        default=",".join(SYMBOLS),
        help="Comma-separated list of symbols to backtest. Default: %(default)s",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip the heavy walk-forward / parameter-sensitivity / monte-carlo stages.",
    )
    return parser.parse_args()


def _build_data_source(symbol: str) -> CSVDataSource:
    """Return a ``CSVDataSource`` for ``symbol``.

    For EURUSD we use the pre-formatted ISO-timestamped file in
    ``data/processed`` (preserved for backward compatibility). For all
    other symbols we glob ``dukascopy_data/<symbol>-m30-bid-*.csv``
    directly — the file_map dispatch in ``CSVDataSource`` handles
    either a single Path or an iterable of Paths.

    On the VPS the repo lives at ``$HOME/ICT-Po3/po3-ict-backtesting``
    but the dukascopy_data directory may have been placed at any of
    several locations. We probe the most likely candidates in order:
        1. ``../dukascopy_data`` (sibling of the repo, workstation layout)
        2. ``../Research-Paper-Po3/dukascopy_data`` (parent project layout)
        3. ``$HOME/dukascopy_data`` (default VPS layout)
        4. ``/data/dukascopy_data`` (system-wide mount)
        5. ``/home/davidv/Dokumente/Research/Research-Paper-Po3/dukascopy_data``
           (the original workstation absolute path, kept as a last-resort
           fallback so the workstation continues to work without env
           variables)
    """
    if symbol == "EURUSD":
        formatted = Path("data/processed") / f"{symbol.lower()}_m30_bid_formatted.csv"
        if formatted.exists():
            return CSVDataSource(
                base_path=Path("data/processed"),
                file_map={symbol: formatted},
            )
        # Fall back to the raw Dukascopy-format file shipped in the
        # repo at data/raw/. The updated CSV reader accepts the
        # ``timestamp`` column and auto-detects ms vs s, so the same
        # data works without a pre-processing step.
        raw = Path("data/raw") / f"{symbol.lower()}-m30-bid-2003-05-04T21-2025-09-07.csv"
        if raw.exists():
            return CSVDataSource(
                base_path=Path("data/raw"),
                file_map={symbol: raw},
            )

    repo_dir = Path.cwd()
    home = Path.home()
    candidates = [
        repo_dir.parent / "dukascopy_data",
        repo_dir.parent / "Research-Paper-Po3" / "dukascopy_data",
        home / "dukascopy_data",
        Path("/data/dukascopy_data"),
        Path("/home/davidv/Dokumente/Research/Research-Paper-Po3/dukascopy_data"),
    ]
    for cand in candidates:
        if cand.is_dir():
            return CSVDataSource(base_path=cand, file_map={})
    # Final fallback: original workstation absolute path. CSVDataSource
    # will glob there and return 0 bars if the directory is missing.
    return CSVDataSource(
        base_path=Path("/home/davidv/Dokumente/Research/Research-Paper-Po3/dukascopy_data"),
        file_map={},
    )


def _symbol_params(base: dict, symbol: str) -> dict:
    """Return a copy of ``base`` with per-symbol overrides applied.

    For ``INDEX_SYMBOLS`` we drop the high-impact news gate (the forex
    calendar does not cover FOMC/NFP/CPI in a way the strategy can use)
    and disable ``allow_monday`` for indices that don't trade Mondays.
    """
    params = dict(base)
    if symbol in INDEX_SYMBOLS:
        params["require_high_impact_news"] = False
    return params


def main(argv: list[str] | None = None) -> None:
    args = _parse_args() if argv is None else _parse_args_from(argv)
    configure_logging()
    logger = logging.getLogger(__name__)

    symbols_to_run = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    unknown = [s for s in symbols_to_run if s not in SYMBOLS]
    if unknown:
        logger.warning("Unknown symbols (no data): %s. They will be skipped.", unknown)
        symbols_to_run = [s for s in symbols_to_run if s in SYMBOLS]
    if not symbols_to_run:
        logger.error("No symbols to run. Aborting.")
        return

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    multi_asset_results: dict[str, dict] = {}
    _run_t0 = time.monotonic()
    _symbol_durations: list[tuple[str, float]] = []

    for symbol in symbols_to_run:
        logger.info("=" * 60)
        logger.info("Running backtest for %s", symbol)
        logger.info("=" * 60)
        sym_t0 = time.monotonic()
        symbol_results = _run_for_symbol(
            symbol=symbol,
            results_dir=results_dir,
            logger=logger,
            quick=args.quick,
        )
        multi_asset_results[symbol] = symbol_results
        dur = time.monotonic() - sym_t0
        _symbol_durations.append((symbol, dur))
        done = len(_symbol_durations)
        total = len(symbols_to_run)
        avg = (time.monotonic() - _run_t0) / done
        eta = avg * (total - done)
        logger.info("=" * 60)
        logger.info(
            "Symbol %s done in %s | multi-asset progress %d/%d | elapsed=%s ETA=%s",
            symbol, _fmt_duration(dur), done, total,
            _fmt_duration(time.monotonic() - _run_t0), _fmt_duration(eta),
        )
        logger.info("=" * 60)

    # Aggregate multi-asset validation summary
    write_report(
        {
            "multi_asset_validation": {
                "status": "completed",
                "symbols": list(multi_asset_results.keys()),
                "per_symbol": multi_asset_results,
            }
        },
        results_dir / "multi_asset_validation.json",
    )
    logger.info(
        "Multi-asset validation complete for %d symbols; results under %s",
        len(multi_asset_results),
        results_dir,
    )


def _parse_args_from(argv: list[str]) -> argparse.Namespace:
    return argparse.ArgumentParser(description="PO3 ICT backtest pipeline").parse_args(argv)


def _fmt_duration(seconds: float) -> str:
    """Format a duration in seconds as ``Hh Mm Ss`` (or ``Mm Ss`` / ``Ss``)."""
    s = int(max(0, seconds))
    h, rem = divmod(s, 3600)
    m, s2 = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s2:02d}s"
    if m:
        return f"{m}m{s2:02d}s"
    return f"{s2}s"


def _run_for_symbol(
    symbol: str,
    results_dir: Path,
    logger: logging.Logger,
    quick: bool = False,
) -> dict:
    """Run the full strategy suite for a single symbol and write per-symbol reports."""
    data_source = _build_data_source(symbol)
    resample_pipeline = CSVResamplePipeline(
        data_source=data_source,
        output_dir=results_dir / "resampled" / symbol,
    )
    try:
        outputs = resample_pipeline.run(symbol, ["H1", "H4", "D"])
        for path in outputs:
            logger.info("Resampled CSV written: %s", path)
    except Exception as exc:
        logger.warning("Resample step failed for %s: %s (continuing with M30)", symbol, exc)

    handler = DataHandler(data_source=data_source, validator=DataValidator(save_report=True))
    # For backward compatibility, EURUSD reports land in results/ at the
    # top level. Other symbols land in results/multi_asset/<SYMBOL>/.
    if symbol == "EURUSD":
        out_dir = results_dir
    else:
        out_dir = results_dir / "multi_asset" / symbol
        out_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "dataset": f"dukascopy/{symbol} M30 bid (auto)",
        "timeframe_base": "M30",
        "resampled_timeframes": ["H1", "H4", "D"],
        "symbol": symbol,
        "volume_included": False,
        "backtest_window": {
            "start": START_DATE_CALIBRATION.isoformat(),
            "end": END_DATE_FORWARD.isoformat(),
        },
        "calibration_window": {
            "start": START_DATE_CALIBRATION.isoformat(),
            "end": END_DATE_CALIBRATION.isoformat(),
        },
        "oos_validation_window": {
            "start": START_DATE_OOS_VALIDATION.isoformat(),
            "end": END_DATE_OOS_VALIDATION.isoformat(),
        },
        "forward_window": {
            "start": START_DATE_FORWARD.isoformat(),
            "end": END_DATE_FORWARD.isoformat(),
        },
    }
    try:
        # Try to capture the MD5 of the resolved input file.
        first_path = data_source._paths_for(symbol)[0]
        if first_path.exists():
            metadata["dataset"] = str(first_path)
            metadata["dataset_md5"] = md5_file(first_path)
    except Exception:
        pass
    write_report(metadata, out_dir / "metadata.json")

    base_params = _symbol_params(dict(DEFAULT_PARAMS), symbol)

    # ---- progress / ETA tracking ----
    # The 8 main strategies are always run; the 3 phase-comparison
    # strategies (calibration / OOS / forward) are added on top of
    # that in non-quick mode. Pre-populating the plan up-front lets us
    # report a meaningful percentage complete + ETA from the very first
    # run_strategy() call.
    _plan: list[str] = [
        "buy_hold",
        "random_baseline",
        "ma_crossover",
        "daily_swing_framework",
        "composite",
    ]
    _done: list[tuple[str, float]] = []
    _symbol_t0 = time.monotonic()
    _counter = {"n": 0}

    def _record_done(label: str, duration: float) -> None:
        _counter["n"] += 1
        _done.append((label, duration))
        elapsed = time.monotonic() - _symbol_t0
        avg = elapsed / _counter["n"]
        remaining = max(0, len(_plan) - _counter["n"])
        eta = avg * remaining
        bar_total = max(len(_plan), 1)
        bar_width = 24
        filled = int(bar_width * _counter["n"] / bar_total)
        bar = "[" + "=" * filled + " " * (bar_width - filled) + "]"
        logger.info(
            "  %s %d/%d %-30s %6.1fs | elapsed=%s ETA=%s",
            bar, _counter["n"], len(_plan), label, duration,
            _fmt_duration(elapsed), _fmt_duration(eta),
        )

    def run_strategy(strategy, label: str, start_date: datetime, end_date: datetime, partial_exits: bool = True):
        t0 = time.monotonic()
        try:
            broker = SimulatedBroker(
                slippage_bps=DEFAULT_PARAMS.get("slippage_bps", 0.0),
                spread_bps=DEFAULT_PARAMS.get("spread_bps", 0.0),
                fee_per_trade=DEFAULT_PARAMS.get("fee_per_trade", 0.0),
            )
            engine = BacktestEngine(
                initial_capital=10000.0,
                broker=broker,
                strategy=strategy,
                risk_manager=RiskManager(),
                risk_per_trade=DEFAULT_PARAMS.get("risk_per_trade", 0.01),
                partial_exit_enabled=partial_exits,
                stop_slippage_pips=DEFAULT_PARAMS.get("stop_slippage_pips", 0.5),
                intrabar_exit_policy=DEFAULT_PARAMS.get("intrabar_exit_policy", "stop_first"),
                ruin_stop_enabled=DEFAULT_PARAMS.get("ruin_stop_enabled", True),
                ruin_floor=DEFAULT_PARAMS.get("ruin_floor", 0.0),
            )
            backtest = BacktestPipeline(data_handler=handler, engine=engine)
            backtest.run(
                symbol=symbol,
                timeframe="H1",
                start_date=start_date,
                end_date=end_date,
                show_progress=False,  # Multi-asset is too noisy with progress bars
            )
            try:
                report = build_report(engine, risk_free_rate=base_params.get("risk_free_rate", 0.0))
            except Exception as exc:
                logger.error("%s report failed: %s", label, exc)
                report = {}
            logger.info("%s: trades=%s final=%.2f mdd=%.2f%% sharpe=%.3f",
                        label, report.get("trades"), report.get("final_equity", 0.0),
                        report.get("max_drawdown", 0.0) * 100, report.get("sharpe", 0.0))
            write_report(report, out_dir / f"report_{label}.json")
            try:
                write_pdf_report(report, out_dir / "pdf_reports", label)
            except ImportError:
                pass
            write_trades(engine, out_dir / f"trades_{label}.csv")
            write_trades_detailed(engine, out_dir / f"trades_{label}_detailed.csv", risk_free_rate=base_params.get("risk_free_rate", 0.0))
            charts_dir = out_dir / "charts" / label
            equity_values = [p.equity for p in engine.equity_curve]
            drawdowns = []
            peak = float("-inf")
            for value in equity_values:
                peak = max(peak, value)
                drawdowns.append(0.0 if peak <= 0 else (peak - value) / peak)
            plot_equity_curve(equity_values, charts_dir / "equity_curve.png")
            plot_drawdown(drawdowns, charts_dir / "drawdown.png")
            plot_pnl_distribution([t.pnl for t in engine.trades], charts_dir / "pnl_distribution.png")
            plot_trades_with_levels(engine.history, engine.trades, charts_dir / "trades_plotly.html")
            _record_done(label, time.monotonic() - t0)
            return engine, report
        except Exception as exc:
            logger.error("%s failed: %s", label, exc)
            _record_done(label, time.monotonic() - t0)
            return BacktestEngine(0.0, SimulatedBroker(), strategy), {}

    # NOTE on partial exits: BuyHoldStrategy now sets
    # ``partial_exit_blocked=True`` on its signal, so this flag does not
    # matter for it. We still pass partial_exits=False explicitly for
    # the Buy & Hold run as a belt-and-braces guarantee that the position
    # is never split at 1R.
    buy_hold_engine, buy_hold_report = run_strategy(
        BuyHoldStrategy(params=base_params),
        "buy_hold",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
        partial_exits=False,
    )
    random_engine, random_report = run_strategy(
        RandomBaselineStrategy(params=base_params),
        "random_baseline",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
    )
    ma_engine, ma_report = run_strategy(
        MovingAverageCrossoverStrategy(params=base_params),
        "ma_crossover",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
    )
    daily_swing_engine, daily_swing_report = run_strategy(
        DailySwingFrameworkStrategy(params=base_params),
        "daily_swing_framework",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
    )
    composite_engine, composite_report = run_strategy(
        CompositeStrategy(params=base_params),
        "composite",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
    )
    summary_reports = {
        "buy_hold": buy_hold_report,
        "random_baseline": random_report,
        "ma_crossover": ma_report,
        "daily_swing_framework": daily_swing_report,
        "composite": composite_report,
    }
    write_summary_csv(summary_reports, out_dir / "summary.csv")

    # Statistical tests — t-test vs buy & hold, ANOVA across confluences,
    # walk-forward correlation. Reuse the same code path as before, just
    # pointed at the per-symbol results.
    stats_report = _run_stats_section(buy_hold_engine, composite_engine, daily_swing_report, composite_report, walk_forward_payload=None if quick else None, symbol=symbol, out_dir=out_dir, logger=logger)

    if not quick:
        # Walk-forward + parameter sensitivity + Monte Carlo + cost scenarios
        # + stress tests. We scope each to the current symbol to keep
        # runtime manageable.
        try:
            walk_forward = WalkForwardPipeline(
                data_handler=handler,
                strategy_factory=lambda: DailySwingFrameworkStrategy(params=base_params),
                engine_factory=lambda strat: BacktestEngine(
                    initial_capital=10000.0,
                    broker=SimulatedBroker(
                        slippage_bps=base_params.get("slippage_bps", 0.0),
                        spread_bps=base_params.get("spread_bps", 0.0),
                        fee_per_trade=base_params.get("fee_per_trade", 0.0),
                    ),
                    strategy=strat,
                    risk_manager=RiskManager(),
                    risk_per_trade=base_params.get("risk_per_trade", 0.01),
                    stop_slippage_pips=base_params.get("stop_slippage_pips", 0.5),
                    intrabar_exit_policy=base_params.get("intrabar_exit_policy", "stop_first"),
                    ruin_stop_enabled=base_params.get("ruin_stop_enabled", True),
                    ruin_floor=base_params.get("ruin_floor", 0.0),
                ),
            )
            wf_payload = walk_forward.run(
                symbol=symbol,
                timeframe="H1",
                start_date=START_DATE_OOS_VALIDATION,
                end_date=END_DATE_OOS_VALIDATION,
            )
            write_report({"walk_forward": wf_payload}, out_dir / "walk_forward.json")
            write_walk_forward_csv(wf_payload.get("windows", []), out_dir / "walk_forward.csv")
        except Exception as exc:
            logger.warning("Walk-forward failed for %s: %s", symbol, exc)

        # Parameter sensitivity (Daily Swing, per-symbol)
        try:
            param_grid = {
                "risk_per_trade": [0.005, 0.01, 0.02],
                "partial_exit_enabled": [True, False],
                "daily_swing_cooldown_bars": [48, 96, 192],
            }
            ps_pipeline = ParameterSensitivityPipeline(
                data_handler=handler,
                strategy_factory=lambda p: DailySwingFrameworkStrategy(
                    params={**base_params, **p}
                ),
                engine_factory=lambda strat, p: BacktestEngine(
                    initial_capital=10000.0,
                    broker=SimulatedBroker(
                        slippage_bps=base_params.get("slippage_bps", 0.0),
                        spread_bps=base_params.get("spread_bps", 0.0),
                        fee_per_trade=base_params.get("fee_per_trade", 0.0),
                    ),
                    strategy=strat,
                    risk_manager=RiskManager(),
                    risk_per_trade=p.get("risk_per_trade", 0.01),
                    partial_exit_enabled=p.get("partial_exit_enabled", True),
                    stop_slippage_pips=base_params.get("stop_slippage_pips", 0.5),
                    intrabar_exit_policy=base_params.get("intrabar_exit_policy", "stop_first"),
                    ruin_stop_enabled=base_params.get("ruin_stop_enabled", True),
                    ruin_floor=base_params.get("ruin_floor", 0.0),
                ),
            )
            ps_results = ps_pipeline.run(
                symbol=symbol,
                timeframe="H1",
                start_date=START_DATE_CALIBRATION,
                end_date=END_DATE_FORWARD,
                param_grid=param_grid,
            )
            write_report({"parameter_sensitivity": ps_results}, out_dir / "parameter_sensitivity.json")
            write_parameter_sensitivity_csv(ps_results, out_dir / "parameter_sensitivity.csv")
        except Exception as exc:
            logger.warning("Parameter sensitivity failed for %s: %s", symbol, exc)

        # Phase comparison (Daily Swing)
        cal_engine, cal_report = run_strategy(
            DailySwingFrameworkStrategy(params=base_params),
            "daily_swing_calibration",
            START_DATE_CALIBRATION,
            END_DATE_CALIBRATION,
            partial_exits=False,
        )
        oos_engine, oos_report = run_strategy(
            DailySwingFrameworkStrategy(params=base_params),
            "daily_swing_oos",
            START_DATE_OOS_VALIDATION,
            END_DATE_OOS_VALIDATION,
            partial_exits=False,
        )
        fwd_engine, fwd_report = run_strategy(
            DailySwingFrameworkStrategy(params=base_params),
            "daily_swing_forward",
            START_DATE_FORWARD,
            END_DATE_FORWARD,
            partial_exits=False,
        )
        write_report(
            {
                "calibration": cal_report,
                "oos_validation": oos_report,
                "forward": fwd_report,
            },
            out_dir / "daily_swing_phase_comparison.json",
        )

        # Monte Carlo
        try:
            mc_runs = monte_carlo_resample(
                pnls=[t.pnl for t in daily_swing_engine.trades],
                initial_capital=daily_swing_engine.initial_capital,
                iterations=1000,
                seed=42,
                equity_floor=0.0,
                stop_on_ruin=True,
            )
            mc_payload = [{"max_drawdown": r.max_drawdown, "final_equity": r.final_equity} for r in mc_runs]
            write_report({"monte_carlo": mc_payload}, out_dir / "monte_carlo.json")
            write_monte_carlo_csv(mc_payload, out_dir / "monte_carlo.csv")
        except Exception as exc:
            logger.warning("Monte Carlo failed for %s: %s", symbol, exc)

        # Cost sensitivity (Daily Swing, per-symbol)
        try:
            cost_reports = {}
            for label, cfg in _cost_scenarios().items():
                broker = SimulatedBroker(
                    slippage_bps=cfg["slippage_bps"],
                    spread_bps=cfg["spread_bps"],
                    fee_per_trade=cfg["fee_per_trade"],
                )
                engine = BacktestEngine(
                    initial_capital=10000.0,
                    broker=broker,
                    strategy=DailySwingFrameworkStrategy(params=dict(base_params)),
                    risk_manager=RiskManager(),
                    risk_per_trade=base_params.get("risk_per_trade", 0.01),
                    partial_exit_enabled=True,
                    stop_slippage_pips=cfg["stop_slippage_pips"],
                    intrabar_exit_policy=base_params.get("intrabar_exit_policy", "stop_first"),
                    ruin_stop_enabled=base_params.get("ruin_stop_enabled", True),
                    ruin_floor=base_params.get("ruin_floor", 0.0),
                )
                BacktestPipeline(data_handler=handler, engine=engine).run(
                    symbol=symbol,
                    timeframe="H1",
                    start_date=START_DATE_CALIBRATION,
                    end_date=END_DATE_FORWARD,
                    show_progress=False,
                )
                r = build_report(engine, risk_free_rate=base_params.get("risk_free_rate", 0.0))
                r["label"] = label
                r["costs"] = cfg
                cost_reports[label] = r
            gross = cost_reports.get("idealized_gross", {})
            cost_comparison = {
                "retail_vs_gross": {
                    "sharpe_delta": cost_reports.get("retail_net", {}).get("sharpe", 0.0) - gross.get("sharpe", 0.0),
                    "cagr_delta": cost_reports.get("retail_net", {}).get("cagr", 0.0) - gross.get("cagr", 0.0),
                    "max_drawdown_delta": cost_reports.get("retail_net", {}).get("max_drawdown", 0.0) - gross.get("max_drawdown", 0.0),
                    "turnover": cost_reports.get("retail_net", {}).get("turnover", 0.0),
                },
                "conservative_vs_gross": {
                    "sharpe_delta": cost_reports.get("conservative_net", {}).get("sharpe", 0.0) - gross.get("sharpe", 0.0),
                    "cagr_delta": cost_reports.get("conservative_net", {}).get("cagr", 0.0) - gross.get("cagr", 0.0),
                    "max_drawdown_delta": cost_reports.get("conservative_net", {}).get("max_drawdown", 0.0) - gross.get("max_drawdown", 0.0),
                    "turnover": cost_reports.get("conservative_net", {}).get("turnover", 0.0),
                },
            }
            write_report({"cost_scenarios": cost_reports, "gross_vs_net": cost_comparison}, out_dir / "cost_sensitivity.json")
        except Exception as exc:
            logger.warning("Cost sensitivity failed for %s: %s", symbol, exc)

        # Stress tests
        try:
            stress_test = StrategyStressTest(
                data_handler=handler,
                engine_factory=lambda: BacktestEngine(
                    initial_capital=10000.0,
                    broker=SimulatedBroker(
                        slippage_bps=base_params.get("slippage_bps", 0.0),
                        spread_bps=base_params.get("spread_bps", 0.0),
                        fee_per_trade=base_params.get("fee_per_trade", 0.0),
                    ),
                    strategy=DailySwingFrameworkStrategy(params=dict(base_params)),
                    risk_manager=RiskManager(),
                    risk_per_trade=base_params.get("risk_per_trade", 0.01),
                    stop_slippage_pips=base_params.get("stop_slippage_pips", 0.5),
                    intrabar_exit_policy=base_params.get("intrabar_exit_policy", "stop_first"),
                    ruin_stop_enabled=base_params.get("ruin_stop_enabled", True),
                    ruin_floor=base_params.get("ruin_floor", 0.0),
                ),
            )
            scenarios = {
                "crisis_2008": {
                    "start": datetime(2008, 9, 1, tzinfo=timezone.utc),
                    "end": datetime(2009, 3, 31, tzinfo=timezone.utc),
                    "description": "Financial Crisis",
                },
                "covid_2020": {
                    "start": datetime(2020, 2, 15, tzinfo=timezone.utc),
                    "end": datetime(2020, 5, 31, tzinfo=timezone.utc),
                    "description": "COVID Crash + Recovery",
                },
                "normal_uptrend": {
                    "start": datetime(2019, 1, 1, tzinfo=timezone.utc),
                    "end": datetime(2020, 1, 1, tzinfo=timezone.utc),
                    "description": "Normal Bull Market",
                },
            }
            stress_results = stress_test.run_scenarios(symbol, "H1", scenarios)
            write_report({"stress_tests": stress_results}, out_dir / "stress_tests.json")
        except Exception as exc:
            logger.warning("Stress testing failed for %s: %s", symbol, exc)

    return {
        "summary": summary_reports,
        "stats": stats_report,
    }


def _cost_scenarios() -> dict:
    return {
        "idealized_gross": {"slippage_bps": 0.0, "spread_bps": 0.0, "stop_slippage_pips": 0.0, "fee_per_trade": 0.0},
        "retail_net": {
            "slippage_bps": 1.0,
            "spread_bps": 2.0,
            "stop_slippage_pips": DEFAULT_PARAMS.get("stop_slippage_pips", 0.5),
            "fee_per_trade": DEFAULT_PARAMS.get("fee_per_trade", 0.0),
        },
        "conservative_net": {
            "slippage_bps": 2.5,
            "spread_bps": 2.5,
            "stop_slippage_pips": DEFAULT_PARAMS.get("stop_slippage_pips", 0.5),
            "fee_per_trade": DEFAULT_PARAMS.get("fee_per_trade", 0.0),
        },
    }


def _run_stats_section(
    buy_hold_engine, composite_engine,
    daily_swing_report, composite_report,
    walk_forward_payload, symbol, out_dir, logger,
) -> dict:
    """Re-implement the stats section that lived in main() — now per-symbol."""
    stats_report: dict = {}
    try:
        buy_hold_returns = buy_hold_engine.calculate_returns()

        def summarize(name: str, engine, report):
            returns = engine.calculate_returns()
            t_stat, p_value = t_test_independent(returns, buy_hold_returns)
            win_trades = sum(1 for trade in engine.trades if trade.pnl > 0)
            total_trades = len(engine.trades)
            p_win = binomial_test(win_trades, total_trades, 0.5) if total_trades else 1.0
            return {
                "t_test_vs_buy_hold": {"t_stat": t_stat, "p_value": p_value},
                "binomial_winrate": {"wins": win_trades, "trades": total_trades, "p_value": p_win},
                "report": report,
            }

        stats_report = {
            "buy_hold": {"report": daily_swing_report},
            "daily_swing_framework": summarize("daily_swing_framework", composite_engine, daily_swing_report),
            "composite": summarize("composite", composite_engine, composite_report),
        }
        # Confluence ANOVA
        try:
            confluence_groups = {"low": [], "medium": [], "high": []}
            for trade in composite_engine.trades:
                if trade.confluence is None:
                    continue
                if trade.confluence < 2.0:
                    confluence_groups["low"].append(1.0 if trade.pnl > 0 else 0.0)
                elif trade.confluence < 3.0:
                    confluence_groups["medium"].append(1.0 if trade.pnl > 0 else 0.0)
                else:
                    confluence_groups["high"].append(1.0 if trade.pnl > 0 else 0.0)
            if all(confluence_groups[group] for group in confluence_groups):
                f_stat, p_val = anova_oneway(
                    confluence_groups["low"],
                    confluence_groups["medium"],
                    confluence_groups["high"],
                )
                stats_report["confluence_anova"] = {
                    "f_stat": f_stat,
                    "p_value": p_val,
                    "groups": {k: len(v) for k, v in confluence_groups.items()},
                }
            else:
                stats_report["confluence_anova"] = {
                    "error": "Not enough trades in one or more confluence groups."
                }
        except Exception as exc:
            stats_report["confluence_anova"] = {"error": str(exc)}
    except Exception as exc:
        logger.warning("Stats section failed for %s: %s", symbol, exc)
    write_report(stats_report, out_dir / "statistical_tests.json")
    return stats_report


if __name__ == "__main__":
    main()
