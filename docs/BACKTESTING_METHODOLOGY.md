# Backtesting Methodology & Bias Controls

## 1) Data Snooping Protection

### Data Splits (Configured in Code)
The default calibration, validation, and forward windows are defined in backtesting_system/config/trading_parameters.py:
- Calibration (train): 2007-01-01 to 2020-12-31
- Out-of-sample validation: 2021-01-01 to 2023-12-31
- Forward window: 2024-01-01 to 2025-04-07

### Implementation Notes
- Backtests are run separately for each window in backtesting_system/main.py.
- Walk-forward validation is implemented in backtesting_system/pipelines/walk_forward.py.

## 2) Transaction Costs & Slippage

### Modeled Costs
Costs are applied through SimulatedBroker (backtesting_system/adapters/execution/simulated_broker.py):
- Slippage: slippage_bps (default 1.0 bps in backtesting_system/config/trading_parameters.py)
- Spread: spread_bps (default 2.0 bps)
- Commission: fee_per_trade (default 0.0, configurable)

### Exit Cost Handling
Exit prices are adjusted for slippage and spread in backtesting_system/core/backtest_engine.py. Commissions are deducted on entry and exit.

### Interpretation
All reported returns are net of modeled slippage, spread, and commissions.

## 3) Statistical Significance Testing

### Win Rate (Binomial Test)
The win-rate p-value is computed via backtesting_system/analytics/statistics.py and included in report outputs (backtesting_system/analytics/reporting.py). This tests the null hypothesis that win rate equals 50%.

### Multiple Testing
When testing many parameter combinations, a stricter significance threshold should be used (e.g., Bonferroni correction). Results files should document the number of parameter sets evaluated.

## 4) Survivorship & Selection Bias

### FX Data
The default dataset is EURUSD spot FX data from local CSV files under data/processed. FX does not suffer from equity survivorship bias, but selection bias is still possible if the dataset is curated.

### Equity Data (If Added)
If equities are used, results must document whether delisted/failed instruments are included. Using only current constituents introduces survivorship bias and inflates performance.

## 5) Reproducibility

- All parameters used in the backtest are stored in backtesting_system/config/trading_parameters.py.
- Output artifacts are written to results/ with summary CSVs and JSON reports.
