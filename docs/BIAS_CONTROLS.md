# Bias Controls

## Look-Ahead Bias
- Signals are generated from historical candles up to the current bar in backtesting_system/strategies.
- No future bars are referenced for signal generation.

## Data Snooping / Overfitting
- Parameter sensitivity runs are isolated in backtesting_system/pipelines/parameter_sensitivity.py.
- Walk-forward validation is available in backtesting_system/pipelines/walk_forward.py.

## Transaction Cost Bias
- Slippage and spread are modeled in backtesting_system/adapters/execution/simulated_broker.py.
- Exit price adjustments for spread/slippage are applied in backtesting_system/core/backtest_engine.py.

## Survivorship Bias
- Current default is FX data, which has no delisting bias.
- If equities are added, document data source coverage and delisted symbols.

## Selection Bias
- Dataset choice and date range selection are documented in backtesting_system/config/trading_parameters.py and results/metadata.json.

## Multiple Testing Bias
- Parameter sweeps should include correction (e.g., Bonferroni) and document the number of parameter sets tested.
