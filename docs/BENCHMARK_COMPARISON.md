# Benchmark Comparison

This framework compares ICT-style strategies against baseline benchmarks to test for abnormal returns.

## Benchmarks
1) Buy & Hold
- Implemented in backtesting_system/strategies/benchmark_buy_hold.py.
- Baseline for market exposure without tactical timing.

2) Random Trading (Planned)
2) Random Trading
- Implemented in backtesting_system/strategies/benchmark_random.py.
- Purpose: establish a null model for win-rate and risk-adjusted returns.

3) Simple Technical Indicators
- Implemented in backtesting_system/strategies/benchmark_ma_crossover.py.
- Purpose: compare ICT to common, transparent technical baselines.

## Reporting Template
| Strategy | Ann. Return | Sharpe | Max DD | Win% | Win-Rate P-Value |
|----------|-------------|--------|--------|------|------------------|
| Buy & Hold |            |        |        |      | N/A              |
| Random    |            |        |        |      |                  |
| MA Cross  |            |        |        |      |                  |
| ICT       |            |        |        |      |                  |

## Interpretation Rules
- If ICT underperforms Buy & Hold, the strategy has no practical advantage.
- If win-rate p-value is above 0.05, the win-rate is not statistically significant.
- If results change materially across parameter choices, treat any apparent edge as fragile.
