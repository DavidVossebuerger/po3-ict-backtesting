# PO3 ICT Backtesting Framework

## Disclaimer
This repository implements Inner Circle Trader (ICT) concepts for empirical testing only. ICT is not an academically validated trading methodology, and this project does not claim that ICT is profitable. The goal is to measure whether ICT produces statistically significant, risk-adjusted returns after controlling for bias, costs, and data-snooping effects.

## Research Hypothesis
ICT-based strategies do not produce risk-adjusted returns that are significantly different from market benchmarks once the following are included:
- Transaction costs and slippage
- Overfitting and multiple testing bias
- Out-of-sample validation

## What This Framework Does
- Encodes ICT-style entry/exit rules in reproducible Python code
- Runs backtests with explicit bias controls
- Generates statistical summaries and p-values for win-rate significance
- Produces benchmark and strategy comparison reports

## Data Sources
- Primary market data is loaded from CSV files under data/processed (see backtesting_system/adapters/data_sources/csv_source.py).
- The default main script expects data/processed/eurusd_m30_bid_formatted.csv.

## Bias Controls (Summary)
- Fixed calibration, validation, and forward windows in backtesting_system/config/trading_parameters.py
- Slippage, spread, and commissions in backtesting_system/adapters/execution/simulated_broker.py
- Binomial significance testing in backtesting_system/analytics/statistics.py

Full methodology: docs/BACKTESTING_METHODOLOGY.md

## Limitations
- Results depend on the chosen parameterization of ICT rules.
- Data availability and quality can introduce survivorship and selection bias.
- Statistical significance does not imply economic significance.

## License
This project is released under the MIT License. See LICENSE for details.

## Key Docs
- docs/BACKTESTING_METHODOLOGY.md
- docs/BIAS_CONTROLS.md
- docs/ICT_RULES_IMPLEMENTATION.md
- docs/BENCHMARK_COMPARISON.md
- docs/RESULTS.md
