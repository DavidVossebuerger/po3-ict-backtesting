# ICT Rules Implementation

## Scope
This repository implements a formalized, code-based interpretation of ICT-style weekly profiles. The core implementation is in backtesting_system/strategies/weekly_profiles.py with supporting logic in backtesting_system/strategies/ict_framework.py.

## Rule Formalization (Weekly Profiles)

### Classic Expansion (Long/Short)
- Detects Monday/Tuesday engagement, Wednesday direction, and Thursday/Friday expectation.
- Implemented in WeeklyProfileDetector.detect_profile.
- Signals are generated only on specified weekday windows (default Wednesday/Thursday).

### Midweek Reversal
- Requires a consolidation/retracement pattern early in the week followed by a directional Wednesday move.
- Signal timing is constrained to Wednesday unless allow_monday is enabled.

### Consolidation Reversal
- Looks for consolidation or choppy Monday/Tuesday behavior and a Wednesday external range test.

## Entry/Exit Rules
- Entry: Current bar close when the weekly profile conditions are met.
- Stop: Monday/Tuesday low for long, Monday/Tuesday high for short (fallback uses recent history).
- Target: Projected using project_target with the configured target_multiple.

## Confluence Filters
Additional filters are applied to reduce false positives:
- CISD validation (CISDValidator)
- Stop hunt detection (StopHuntDetector)
- Opening range framework (OpeningRangeFramework)
- News confluence (EconomicCalendar)
- Intermarket confluence (IntermarketAnalyzer)

## Parameterization and Bias
- Key parameters (e.g., min_confluence, target_multiple, slippage_bps, spread_bps) are configured in backtesting_system/config/trading_parameters.py.
- These parameters materially affect results, so sensitivity analysis is required to reduce data-snooping bias.

## Limitations
- ICT rules are inherently interpretive; this implementation reflects one formalization.
- Different traders may encode different thresholds and filters.
- Performance results should be interpreted as conditional on this specific rule set.
