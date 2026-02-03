from __future__ import annotations

import logging
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
    pearson_correlation,
    t_test_independent,
)
from backtesting_system.config.trading_parameters import (
    DEFAULT_PARAMS,
    END_DATE_CALIBRATION,
    END_DATE_FORWARD,
    END_DATE_OOS_VALIDATION,
    START_DATE_CALIBRATION,
    START_DATE_FORWARD,
    START_DATE_OOS_VALIDATION,
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
from backtesting_system.strategies.weekly_profile_extended import WeeklyProfileExtendedStrategy
from backtesting_system.strategies.daily_swing_framework import DailySwingFrameworkStrategy
from backtesting_system.strategies.weekly_profiles import WeeklyProfileStrategy
from backtesting_system.utils.hashing import md5_file
from backtesting_system.utils.logging import configure_logging
from backtesting_system.utils.validation import DataValidator, summarize_validation_reports


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)

    base_path = Path("data/processed")
    input_file = base_path / "eurusd_m30_bid_formatted.csv"
    if not input_file.exists():
        logger.info("CSV not found at %s. Skipping resample.", input_file)
        return

    data_source = CSVDataSource(base_path=base_path, file_map={"EURUSD": input_file})
    resample_pipeline = CSVResamplePipeline(
        data_source=data_source,
        output_dir=base_path / "resampled",
    )
    outputs = resample_pipeline.run("EURUSD", ["H1", "H4", "D"])
    for path in outputs:
        logger.info("Resampled CSV written: %s", path)

        handler = DataHandler(data_source=data_source, validator=DataValidator(save_report=True))
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "dataset": str(input_file),
        "dataset_md5": md5_file(input_file),
        "timeframe_base": "M30",
        "resampled_timeframes": ["H1", "H4", "D"],
        "symbol": "EURUSD",
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
    write_report(metadata, results_dir / "metadata.json")

    def run_strategy(strategy, label: str, start_date: datetime, end_date: datetime, partial_exits: bool = True):
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
            )
            backtest = BacktestPipeline(data_handler=handler, engine=engine)
            backtest.run(
                symbol="EURUSD",
                timeframe="H1",
                start_date=start_date,
                end_date=end_date,
                show_progress=True,
            )
            try:
                report = build_report(engine)
            except Exception as exc:
                logger.error("%s report failed: %s", label, exc)
                report = {}
            logger.info("%s report: %s", label, report)
            write_report(report, results_dir / f"report_{label}.json")
            try:
                write_pdf_report(report, results_dir / "pdf_reports", label)
            except ImportError as exc:
                logger.warning("PDF report skipped: %s", exc)
            write_trades(engine, results_dir / f"trades_{label}.csv")
            write_trades_detailed(engine, results_dir / f"trades_{label}_detailed.csv")
            charts_dir = results_dir / "charts" / label
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
            return engine, report
        except Exception as exc:
            logger.error("%s failed: %s", label, exc)
            return BacktestEngine(0.0, SimulatedBroker(), strategy), {}

    base_params = dict(DEFAULT_PARAMS)
    buy_hold_engine, buy_hold_report = run_strategy(
        BuyHoldStrategy(params=base_params),
        "buy_hold",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
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
    weekly_engine, weekly_report = run_strategy(
        WeeklyProfileStrategy(params=base_params),
        "weekly_profile",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
    )
    weekly_fixed_engine, weekly_fixed_report = run_strategy(
        WeeklyProfileStrategy(params=base_params),
        "weekly_profile_fixed_exit",
        START_DATE_CALIBRATION,
        END_DATE_FORWARD,
        partial_exits=False,
    )
    ict_engine, ict_report = run_strategy(
        WeeklyProfileExtendedStrategy(params=base_params),
        "weekly_profile_extended",
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
        "weekly_profile": weekly_report,
        "weekly_profile_fixed_exit": weekly_fixed_report,
        "weekly_profile_extended": ict_report,
        "daily_swing_framework": daily_swing_report,
        "composite": composite_report,
    }
    write_summary_csv(summary_reports, results_dir / "summary.csv")
    logger.info("Results written to %s", results_dir)

    weekly_cal_engine, weekly_cal_report = run_strategy(
        WeeklyProfileStrategy(params=base_params),
        "weekly_profile_calibration",
        START_DATE_CALIBRATION,
        END_DATE_CALIBRATION,
    )
    weekly_oos_engine, weekly_oos_report = run_strategy(
        WeeklyProfileStrategy(params=base_params),
        "weekly_profile_oos",
        START_DATE_OOS_VALIDATION,
        END_DATE_OOS_VALIDATION,
    )
    weekly_forward_engine, weekly_forward_report = run_strategy(
        WeeklyProfileStrategy(params=base_params),
        "weekly_profile_forward",
        START_DATE_FORWARD,
        END_DATE_FORWARD,
    )
    write_report(
        {
            "calibration": weekly_cal_report,
            "oos_validation": weekly_oos_report,
            "forward": weekly_forward_report,
        },
        results_dir / "weekly_profile_phase_comparison.json",
    )

    walk_forward = WalkForwardPipeline(
        data_handler=handler,
        strategy_factory=lambda: WeeklyProfileStrategy(params=dict(DEFAULT_PARAMS)),
        engine_factory=lambda strat: BacktestEngine(
            initial_capital=10000.0,
            broker=SimulatedBroker(
                slippage_bps=DEFAULT_PARAMS.get("slippage_bps", 0.0),
                spread_bps=DEFAULT_PARAMS.get("spread_bps", 0.0),
                fee_per_trade=DEFAULT_PARAMS.get("fee_per_trade", 0.0),
            ),
            strategy=strat,
            risk_manager=RiskManager(),
            risk_per_trade=DEFAULT_PARAMS.get("risk_per_trade", 0.01),
            stop_slippage_pips=DEFAULT_PARAMS.get("stop_slippage_pips", 0.5),
        ),
    )
    wf_payload = walk_forward.run(
        symbol="EURUSD",
        timeframe="H1",
        start_date=START_DATE_OOS_VALIDATION,
        end_date=END_DATE_OOS_VALIDATION,
    )
    write_report({"walk_forward": wf_payload}, results_dir / "walk_forward.json")
    write_walk_forward_csv(wf_payload.get("windows", []), results_dir / "walk_forward.csv")
    logger.info("Walk-forward results written: %s", results_dir / "walk_forward.json")

    sensitivity = ParameterSensitivityPipeline(
        data_handler=handler,
        strategy_factory=lambda params: WeeklyProfileStrategy(params=params),
        engine_factory=lambda strat, params: BacktestEngine(
            initial_capital=10000.0,
            broker=SimulatedBroker(
                slippage_bps=params.get("slippage_bps", DEFAULT_PARAMS.get("slippage_bps", 0.0)),
                spread_bps=params.get("spread_bps", DEFAULT_PARAMS.get("spread_bps", 0.0)),
                fee_per_trade=params.get("fee_per_trade", DEFAULT_PARAMS.get("fee_per_trade", 0.0)),
            ),
            strategy=strat,
            risk_manager=RiskManager(),
            risk_per_trade=params.get("risk_per_trade", 0.01),
            partial_exit_enabled=params.get("partial_exit_enabled", True),
            stop_slippage_pips=params.get("stop_slippage_pips", DEFAULT_PARAMS.get("stop_slippage_pips", 0.5)),
        ),
    )
    sensitivity_results = sensitivity.run(
        symbol="EURUSD",
        timeframe="H1",
        start_date=START_DATE_CALIBRATION,
        end_date=END_DATE_CALIBRATION,
        param_grid={
            "risk_per_trade": [0.005, 0.01, 0.02],
            "partial_exit_enabled": [True, False],
            "slippage_bps": [DEFAULT_PARAMS.get("slippage_bps", 0.0)],
            "spread_bps": [DEFAULT_PARAMS.get("spread_bps", 0.0)],
            "fee_per_trade": [DEFAULT_PARAMS.get("fee_per_trade", 0.0)],
            "stop_slippage_pips": [DEFAULT_PARAMS.get("stop_slippage_pips", 0.5)],
        },
    )
    write_report({"parameter_sensitivity": sensitivity_results}, results_dir / "parameter_sensitivity.json")
    write_parameter_sensitivity_csv(sensitivity_results, results_dir / "parameter_sensitivity.csv")

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
            "buy_hold": {"report": buy_hold_report},
            "weekly_profile": summarize("weekly_profile", weekly_engine, weekly_report),
            "weekly_profile_fixed_exit": summarize(
                "weekly_profile_fixed_exit",
                weekly_fixed_engine,
                weekly_fixed_report,
            ),
            "weekly_profile_extended": summarize("weekly_profile_extended", ict_engine, ict_report),
            "daily_swing_framework": summarize(
                "daily_swing_framework",
                daily_swing_engine,
                daily_swing_report,
            ),
            "composite": summarize("composite", composite_engine, composite_report),
        }
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
        stats_report["partial_exit_comparison"] = {
            "strategy": "weekly_profile",
            "partial_exit_recovery_factor": weekly_report.get("recovery_factor"),
            "fixed_exit_recovery_factor": weekly_fixed_report.get("recovery_factor"),
        }
        try:
            train_sharpes = [row["train_report"]["sharpe"] for row in wf_payload.get("windows", [])]
            test_sharpes = [row["test_report"]["sharpe"] for row in wf_payload.get("windows", [])]
            r_val, p_val = pearson_correlation(train_sharpes, test_sharpes)
            stats_report["walk_forward_correlation"] = {
                "metric": "sharpe",
                "r_value": r_val,
                "p_value": p_val,
            }
        except Exception as exc:
            stats_report["walk_forward_correlation"] = {"error": str(exc)}
        write_report(stats_report, results_dir / "statistical_tests.json")
        logger.info("Statistical tests written: %s", results_dir / "statistical_tests.json")
    except Exception as exc:
        logger.warning("Statistical tests skipped: %s", exc)

    mc_runs = monte_carlo_resample(
        pnls=[t.pnl for t in weekly_engine.trades],
        initial_capital=weekly_engine.initial_capital,
        iterations=1000,
        seed=42,
    )
    mc_payload = [{"max_drawdown": r.max_drawdown, "final_equity": r.final_equity} for r in mc_runs]
    write_report({"monte_carlo": mc_payload}, results_dir / "monte_carlo.json")
    write_monte_carlo_csv(mc_payload, results_dir / "monte_carlo.csv")

    try:
        summarize_validation_reports("validation_reports", results_dir / "validation_summary.json")
        logger.info("Validation summary written: %s", results_dir / "validation_summary.json")
    except Exception as exc:
        logger.error("Validation summary failed: %s", exc)

    stress_test = StrategyStressTest(
        data_handler=handler,
        engine_factory=lambda: BacktestEngine(
            initial_capital=10000.0,
            broker=SimulatedBroker(
                slippage_bps=DEFAULT_PARAMS.get("slippage_bps", 0.0),
                spread_bps=DEFAULT_PARAMS.get("spread_bps", 0.0),
                fee_per_trade=DEFAULT_PARAMS.get("fee_per_trade", 0.0),
            ),
            strategy=WeeklyProfileStrategy(params=dict(DEFAULT_PARAMS)),
            risk_manager=RiskManager(),
            risk_per_trade=DEFAULT_PARAMS.get("risk_per_trade", 0.01),
            stop_slippage_pips=DEFAULT_PARAMS.get("stop_slippage_pips", 0.5),
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
    try:
        stress_results = stress_test.run_scenarios("EURUSD", "H1", scenarios)
        write_report({"stress_tests": stress_results}, results_dir / "stress_tests.json")
    except Exception as exc:
        logger.error("Stress testing failed: %s", exc)

    multi_asset_symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    multi_asset_results = {}
    for symbol in multi_asset_symbols:
        engine, report = run_strategy(
            WeeklyProfileStrategy(params=base_params),
            f"weekly_profile_{symbol.lower()}",
            START_DATE_OOS_VALIDATION,
            END_DATE_OOS_VALIDATION,
        )
        multi_asset_results[symbol] = report
    write_report({"multi_asset_validation": multi_asset_results}, results_dir / "multi_asset_validation.json")


if __name__ == "__main__":
    main()
