# Results Summary

This document is the canonical location for summarized backtest results and interpretation.

## Required Artifacts
- results/summary.csv
- results/report_*.json
- results/weekly_profile_phase_comparison.json
- results/walk_forward.json

## Summary Table (Fill After Each Run)
| Strategy | Ann. Return | Sharpe | Max DD | Win% | Win-Rate P-Value | Notes |
|----------|-------------|--------|--------|------|------------------|-------|
| Buy & Hold | | | | | N/A | |
| Random Baseline | | | | | | |
| MA Crossover | | | | | | |
| Weekly Profile | | | | | | |
| Weekly Profile (Fixed Exit) | | | | | | |
| Weekly Profile Extended | | | | | | |
| Range Protocol | | | | | | |
| Composite | | | | | | |

## Interpretation Checklist
- Compare each strategy to Buy & Hold.
- Check if win-rate p-values are below 0.05.
- Verify consistency across calibration, OOS, and forward windows.
- Document any parameter sensitivity or fragility.
