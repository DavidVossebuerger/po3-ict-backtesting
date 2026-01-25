# Quantitatives Backtesting System für Akademische Forschung
## Modular Framework für Price Action & Weekly Profile Trading Strategien

---

## EXECUTIVE SUMMARY

Dieses Dokument beschreibt ein modulares Backtesting-Framework zur Evaluierung von Price Action- und Market-Profile-basierten Handelsstrategien. Das System integriert Weekly Profile Analyse (nach ICT-Mentorship) mit quantitativer Performance-Analyse und statistischer Signifikanzprüfung.

**Studien-Kontext:** Untersuchung der Profitabilität und Risiko-charakteristika von regelgestützten, diskretionären Handelsstrategien auf FX-Märkten.

---

## 1. FORSCHUNGSFRAGEN & HYPOTHESEN

### 1.1 Primäre Forschungsfrage
*Können Weekly Market Profiles als regelgestützte Handelssignale systematisch rentable und risikoadjustierte Returns generieren?*

### 1.2 Sekundäre Forschungsfragen
1. Welche Weekly Profile-Typen (Classic Expansion, Midweek Reversal, Consolidation Reversal) erzeugen die höchsten Sharpe Ratios?
2. Wie wirkt sich Confluence-Scoring (Multi-Factor Confirmations) auf Trade-Qualität aus?
3. Können sessionsbasierte Entry-Signale (NY Reversal, RHRL Protocol) die Win Rate erhöhen?
4. Ist die Strategie robust über verschiedene Timeframes und Currency Pairs?

### 1.3 Hypothesen

**H1 (Primary):** Weekly Profile-basierte Strategien generieren statistisch signifikant höhere Risk-Adjusted Returns (Sharpe Ratio > 1.0) als Buy-and-Hold Benchmark.

**H2:** Setups mit hohem Confluence Score (≥4.0/5.0) haben signifikant höhere Win Rates als Low-Confluence Setups (p < 0.05).

**H3:** Midweek Reversals zeigen konsistentere Performance (niedrigere Volatilität der Monthly Returns) als Classic Expansions.

**H4:** Out-of-Sample Performance (Walk-Forward Test) korreliert stark mit In-Sample Performance (Korrelation > 0.7).

**H5:** Partial Exit Systems (75% Exit at 1R, Runner with Trail) erzeugen höhere Recovery Factors als Fixed Exit Systems.

---

## 2. LITERATURÜBERSICHT & THEORETISCHER RAHMEN

### 2.1 Market Microstructure & Institutional Order Flow
- **Relevanz:** Weekly Profiles basieren auf Order Flow und Liquidity Distribution
- **Key Concept:** Market Maker Behavior und Stop-Loss Hunting (Gagnon & Karolyi, 2010)
- **Verbindung:** Supply/Demand Imbalance → Breakouts/Reversals

### 2.2 Technical Analysis Efficacy
- **De Bondt & Thaler (1985):** Mean Reversion Patterns
- **Shiller (1989):** Irrational Exuberance & Price Overextension
- **Neely et al. (2014):** Profitabilität von technischen Strategien auf FX-Märkten

### 2.3 Rule-Based vs Discretionary Trading
- **Problematik:** Selection Bias in diskretionären Strategien
- **Lösung:** Vollständige Mechanisierung der Entry/Exit Logik
- **Referenz:** Alkhoury et al. (2019) - Quantitative vs Discretionary Performance

### 2.4 Performance Attribution & Risk Management
- **Sharpe Ratio (Sharpe 1966):** Risk-Adjusted Return Standard
- **Sortino Ratio (Sortino & Van der Meer 1991):** Downside Risk Focus
- **Calmar Ratio (Young 1991):** Return vs Maximum Drawdown
- **Recovery Factor:** Gagnon & Karolyi (2010)

---

## 3. METHODOLOGIE

### 3.1 Forschungsdesign
**Typ:** Quantitatives Backtesting-Experiment mit Walk-Forward Validation  
**Zeitraum:** 3 Jahre historische Daten (2022-2025)  
**Sample:** 5 Major FX Pairs (EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD)  
**Frequenz:** Intraday (H1, H4, D Timeframes)

### 3.2 Datenquellen & Qualität
```
Primäre Quellen:
- EODHD (End of Day Historical Data) - Adjusted OHLCV
- Alpha Vantage - Real-time Validation
- Forex Factory - Economic Calendar (High-Impact Events)

Datenvalidierung:
- Gap Detection (> 2% intraday)
- Spike Detection (> 3σ)
- Liquidity Checks (Volume > Median)
- Missing Data Handling (Linear Interpolation)

Qualitätsmetriken:
- Fehlerquote < 0.1%
- Completeness > 99.5%
- Timeliness: Real-time + EOD verification
```

### 3.3 Strategiebeschreibung

#### 3.3.1 Weekly Profile Detection (Dependent Variable)
**Input:** Weekly OHLC + Daily H1-H4 PD Arrays  
**Output:** Profile Type (0-5) + Signal Strength (0-100)

**Classification Rules:**

| Profile | MON-TUE Behavior | WED Behavior | THU-FRI Expected |
|---------|-----------------|--------------|------------------|
| Classic Bullish (1) | Engagement auf Discount | Continuation Higher | Expansion to Target |
| Classic Bearish (2) | Engagement auf Premium | Continuation Lower | Expansion to Target |
| Midweek Reversal Up (3) | Consolidation/Retracement | Reversal auf Discount | Bullish Expansion |
| Midweek Reversal Down (4) | Consolidation/Retracement | Reversal auf Premium | Bearish Expansion |
| Consolidation Reversal (5) | Internal Range | External Range Test | Directional Break |
| Seek & Destroy (0) | Choppy/Trapped | Random | Skip (Low Prob) |

#### 3.3.2 Signal Generation (Independent Variable)
```python
SIGNAL_RULES = {
    "confluence_score": [
        "+1.0 wenn Weekly Profile aktiv",
        "+0.5 wenn ≥H1 PDA Alignment",
        "+0.5 wenn Session Quality (NY Reversal Pattern)",
        "+0.5 wenn RHRL Protocol Triggered",
        "+0.5 wenn Stop Hunt Confirmed (LTF)",
        "+0.5 wenn News Driver High-Impact (≤4h)"
    ],
    "entry_conditions": [
        "Confluence Score ≥ 4.0/5.0",
        "Close über Breaker Block (für Long)",
        "ADR Remaining > 1.5x Expected Risk",
        "Daily Swing Context Aligned"
    ],
    "exit_conditions": [
        "Partial Exit bei 1R Target (75% size)",
        "Trailing Stop bei 1R for Runner (25% size)",
        "Time-based Exit bei EOD/EOW",
        "Economic Event Stop-Out"
    ]
}
```

### 3.4 Performance Metrics (Abhängige Variablen)

#### 3.4.1 Primary Metrics
| Metrik | Formel | Interpretation |
|--------|--------|-----------------|
| **Sharpe Ratio** | (Rp - Rf) / σp | Risk-Adjusted Return (Target: >1.0) |
| **Win Rate (Daily)** | Profitable Days / Total Days | Consistency (Target: >55%) |
| **Profit Factor** | Gross Profit / Gross Loss | Overall Profitability (Target: >1.5) |
| **Recovery Factor** | Total Profit / Max Drawdown | Recoverability (Target: >1.0) |
| **Max Drawdown** | (Peak - Trough) / Peak | Worst-Case Loss (Target: <20%) |

#### 3.4.2 Secondary Metrics
| Metrik | Berechnung |
|--------|-----------|
| **Sortino Ratio** | (Rp - Rf) / σdown | Nur Downside Volatilität |
| **Calmar Ratio** | Annual Return / Max DD | Return pro Drawdown Unit |
| **CAGR** | (Final Value / Initial)^(1/Years) - 1 | Compound Annual Growth |
| **Ulcer Index** | √(Avg(DD²)) | Drawdown Intensity |
| **K-Ratio** | (Return / # of Wins) / (Drawdown Volatility) | Consistency |
| **Consecutive Losses** | Max Losing Streak | Psychological Robustness |
| **Average Trade Duration** | Σ(Exit - Entry) / # Trades | Holding Period |

### 3.5 Validierungsmethoden

#### 3.5.1 Walk-Forward Analysis (Out-of-Sample Test)
```
Methode: Rolling Window Optimization
┌─────────────────────────────────────────────────────────────┐
│ Full Dataset (36 Monate)                                   │
├─────────────────────────────────────────────────────────────┤
│ [TRAIN 12M] [TEST 3M] [TRAIN 12M] [TEST 3M] ... [TEST 3M] │
│  (Jan-Dec)  (Jan-Mar)  (Feb-Jan)  (Apr-Jun)                │
└─────────────────────────────────────────────────────────────┘

Step: 3 Monate (Quarterly Roll-Forward)
In-Sample: 12 Monate Optimization
Out-of-Sample: 3 Monate Validation
```

**Validierungskriterien:**
- OOS Performance ≥ 80% von IS Performance
- OOS Sharpe Ratio > 0.8
- OOS Drawdown < 1.5x IS Drawdown
- Korrelation (IS ↔ OOS) > 0.7

#### 3.5.2 Monte Carlo Resampling
```
Methode: Trade Sequence Randomization
Iterationen: 5000
Output: Drawdown Distribution & Probability of Ruin

H0: Gewinne sind zufällig
H1: Gewinne sind systematisch

Reject H0 wenn: 95% der MC Runs < Actual Drawdown
```

#### 3.5.3 Parameter Sensitivity Analysis
```
Variablen zur Variation:
- atr_multiplier: [1.0, 1.5, 2.0, 2.5, 3.0]
- confluence_threshold: [3.5, 4.0, 4.5, 5.0]
- risk_per_trade: [0.5%, 1%, 2%, 3%, 5%]
- session_filter: [Asia, London, NY, All]

Robustheit-Test: Performance > 90% über alle Kombinationen?
```

### 3.6 Statistical Significance Testing

#### 3.6.1 Hypothesis Testing (T-Tests)
```python
# H1: Weekly Profiles vs Buy-Hold
from scipy import stats

t_stat, p_value = stats.ttest_ind(
    strategy_returns, 
    buy_hold_returns
)

if p_value < 0.05:
    print("H1: REJECTED - Strategy outperforms Buy-Hold")
else:
    print("H1: NOT REJECTED - No statistical difference")
```

#### 3.6.2 Win Rate Significance (Binomial Test)
```python
# H2: Win Rate > 50%
from scipy.stats import binom_test

n_wins = 127  # Winning Trades
n_total = 200  # Total Trades

p_value = binom_test(n_wins, n_total, 0.5, alternative='greater')
# p < 0.05 → Signifikant besser als Zufall
```

#### 3.6.3 Sharpe Ratio Significance (Dirichlet Test)
```python
# H1: Sharpe Ratio > 1.0 (Statistically Significant)

def sharpe_significance(returns, sharpe, periods=252):
    """
    Teste ob Sharpe Ratio statistisch signifikant ist
    (nicht nur Glück basierend auf endlicher Sample)
    """
    n = len(returns)
    se_sharpe = np.sqrt((1 + 0.5*sharpe**2) / n)
    t_stat = sharpe / se_sharpe
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n-1))
    return p_value < 0.05
```

#### 3.6.4 Confluence Score Effect (ANOVA)
```python
# H2: Confluence Level beeinflusst Win Rate

confluence_groups = {
    "low": [0.30, 0.25, 0.35],      # 3-3.5/5 Confluence
    "medium": [0.52, 0.48, 0.50],   # 4-4.5/5 Confluence
    "high": [0.68, 0.65, 0.70]      # 4.5-5.0/5 Confluence
}

f_stat, p_value = stats.f_oneway(
    confluence_groups["low"],
    confluence_groups["medium"],
    confluence_groups["high"]
)

if p_value < 0.05:
    print("Confluence Level significantly affects Win Rate")
```

### 3.7 Robustness & Reproducibility

#### 3.7.1 Code & Data Documentation
```
Repository Structure:
├── data/
│   ├── raw/                    # Original EODHD/AV Files
│   ├── processed/              # Cleaned & Validated
│   └── checksums.md5           # Data Integrity Verification
├── src/
│   ├── __init__.py
│   ├── strategies/
│   ├── backtester/
│   └── analysis/
├── notebooks/
│   ├── 01_data_preparation.ipynb
│   ├── 02_strategy_development.ipynb
│   ├── 03_backtesting.ipynb
│   ├── 04_statistical_analysis.ipynb
│   └── 05_results_visualization.ipynb
├── tests/
│   ├── test_data_integrity.py
│   ├── test_signal_generation.py
│   └── test_performance_metrics.py
├── results/
│   ├── backtest_results_[symbol]_[dates].csv
│   ├── performance_metrics.json
│   ├── statistical_tests.json
│   └── charts/
└── README.md                   # Vollständige Dokumentation
```

#### 3.7.2 Reproducibility Checklist
- [ ] Random Seeds festgelegt (np.random.seed(42))
- [ ] Alle Abhängigkeiten in requirements.txt dokumentiert
- [ ] Daten-Hashes (MD5) für Integritätsprüfung
- [ ] Version Control (Git) mit vollständiger Historie
- [ ] Docker Container für exakte Replikation
- [ ] Jupyter Notebooks mit ausgefüllten Results
- [ ] Parameter & Konfiguration in JSON/YAML

---

## 4. ERWARTETE ERGEBNISSE & BENCHMARKS

### 4.1 Hypothesis Validation Matrix

| Hypothesis | Test Methode | Success Criteria | Expected p-value |
|-----------|--------------|-----------------|------------------|
| H1: Outperformance vs B&H | T-Test | Sharpe > 1.0 | p < 0.05 |
| H2: Confluence Effect | ANOVA | Win Rate linear mit Confluence | p < 0.05 |
| H3: Midweek > Expansion | T-Test | MR Volatility < CE | p < 0.10 |
| H4: OOS Correlation | Pearson | r > 0.7 | p < 0.01 |
| H5: Partial Exits > Fixed | T-Test | Recovery Factor > 1.0 | p < 0.05 |

### 4.2 Performance Benchmarks

**Target Metriken für "Successful" Strategy:**
```
├─ Sharpe Ratio: 1.0 - 2.5      ← "Good" Risk-Adjusted Return
├─ Win Rate (Daily): 55% - 65%  ← Consistent Edge
├─ Profit Factor: 1.5 - 3.0     ← Healthy Asymmetry
├─ Max Drawdown: 10% - 20%      ← Acceptable Risk
├─ Recovery Factor: 1.0 - 2.0   ← Quick Recovery from Drawdowns
├─ Consecutive Losses: < 10     ← Psychological Sustainability
└─ Monthly Wins: 65% - 75%      ← Monthly Consistency
```

**Minimum Acceptable Performance:**
- Sharpe Ratio > 0.5
- Win Rate (Daily) > 50%
- Profit Factor > 1.0
- Max Drawdown < 30%

---

## 5. IMPLEMENTIERUNGSDETAILS

### 5.1 Python Framework Stack
```
Data Management:
├─ pandas (1.5+)           # Data Manipulation
├─ numpy (1.24+)           # Numerical Computing
└─ polars (0.18+)          # High-Performance Backend

Backtesting:
├─ custom backtest_engine  # Bar-by-Bar Simulation
└─ zipline/backtrader      # Alternative Libraries

Analysis & Statistics:
├─ scipy (1.10+)           # Statistical Tests
├─ scikit-learn (1.3+)     # ML for Parameter Optimization
└─ statsmodels (0.14+)     # Time Series Analysis

Visualization:
├─ matplotlib (3.7+)       # Core Plotting
├─ plotly (5.17+)          # Interactive Charts
└─ seaborn (0.12+)         # Statistical Visualizations
```

### 5.2 Core Algorithms

#### 5.2.1 Weekly Profile Detection Algorithm
```python
def detect_weekly_profile(weekly_candle, daily_candles):
    """
    Input: Weekly OHLC + 5 Daily Candles (MON-FRI)
    Output: Profile Type (0-5), Confidence Score (0-100)
    
    Algorithm:
    1. Berechne DOL/DOH der Woche
    2. Analysiere MON-TUE Engagement Pattern
    3. Prüfe WED Behavior
    4. Klassifiziere THU-FRI Expected Move
    5. Berechne Confluence Score
    6. Filtere Seek & Destroy
    
    Complexity: O(n) where n = 5 daily candles
    """
    pass
```

#### 5.2.2 Confluence Scoring Algorithm
```python
def calculate_confluence_score(data, context):
    """
    Confluence Factors (Each 0-1.0):
    
    1. Weekly Profile (0-1.0)
       ├─ Profile Aktiv: +1.0
       └─ Profile Aktiv aber Low Prob: +0.5
    
    2. HTF PDA Alignment (0-0.5)
       ├─ ≥H1 PDA Engagement: +0.5
       ├─ HTF Array Aligned: +0.25
       └─ No Alignment: 0
    
    3. Session Quality (0-0.5)
       ├─ NY Reversal Pattern: +0.5
       ├─ London Premium/Discount: +0.25
       └─ Asia Volatile: 0
    
    4. RHRL Protocol (0-0.5)
       ├─ RHRL Setup Active: +0.5
       └─ Not Active: 0
    
    5. Stop Hunt Confirmation (0-0.5)
       ├─ High Resistance Swing: +0.5
       └─ No Swing: 0
    
    6. News Driver (0-0.5)
       ├─ High-Impact News ≤4h: +0.5
       └─ No News: 0
    
    7. ADR Remaining (0-0.5)
       ├─ Remaining > 1.5x Risk: +0.5
       ├─ Remaining > 1.0x Risk: +0.25
       └─ Remaining < 1.0x Risk: 0
    
    Total Score = Sum(All Factors)
    Range: 0 - 5.0
    """
    pass
```

### 5.3 Testing Framework

```python
# Unit Tests für Strategy Logic
def test_weekly_profile_detection():
    """Test accuracy gegen manuell klassifizierte Wochen"""
    assert accuracy > 0.95
    
def test_signal_generation():
    """Test Entry/Exit Logik unter verschiedenen Szenarien"""
    assert all_signals_valid()
    
def test_performance_metrics():
    """Test Metrik-Berechnung gegen Excel Baseline"""
    assert metrics_match_baseline()

# Integration Tests für kompletten Flow
def test_backtest_execution():
    """End-to-End Backtest mit bekanntem Result"""
    assert final_equity == expected_equity
    
def test_monte_carlo_reproducibility():
    """Monte Carlo mit fester Seed liefert gleiche Results"""
    assert mc_run_1 == mc_run_2
```

---

## 6. HYPOTHESEN-TESTING RESULTS (Templateformat)

### 6.1 Hypothesis 1: Outperformance vs Buy-Hold

| Test | Value | p-value | Result |
|------|-------|---------|--------|
| **Sharpe Ratio** | 1.24 | 0.003 | ✅ REJECTED H0 |
| **Annual Return** | 18.5% | 0.012 | ✅ Significant |
| **Max Drawdown** | -14.2% | 0.045 | ✅ Acceptable |
| **Conclusion** | Strategy outperforms with 99% confidence (p<0.01) |

### 6.2 Hypothesis 2: Confluence Effect

| Confluence Level | Sample Size | Win Rate | p-value | Effect Size |
|-----------------|------------|----------|---------|-------------|
| Low (3.0-3.5) | 45 trades | 48.9% | - | - |
| Medium (4.0) | 78 trades | 55.1% | 0.18 | 0.12 |
| High (4.5-5.0) | 92 trades | 63.4% | **0.008** | 0.29 |
| **ANOVA Result** | F=7.82 | **p=0.006** | ✅ Significant Effect |

---

## 7. DISKUSSION & INTERPRETATION

### 7.1 Interpretation der Ergebnisse
- Bestätigung/Ablehnung jeder Hypothese
- Vergleich mit theoretischen Erwartungen
- Konforme/nicht-konforme Ergebnisse erklären

### 7.2 Limitationen der Studie
1. **Data Limitations**
   - Nur 3 Jahre Daten (möglicherweise zu kurz für Markt-Regime)
   - Nur FX-Paare (Generalisierbarkeit auf andere Assets?)
   - Keine Consideration für Black Swan Events

2. **Methodological Limitations**
   - Simplified Order Execution Model
   - Keine echten Slippage/Spread-Variationen
   - Discretionary Elements (News-Timing) nicht vollständig automatisiert

3. **Statistical Limitations**
   - Begrenzte Stichprobengröße für manche Profile-Typen
   - Potential Overfitting trotz Walk-Forward
   - p-hacking Risk bei multiplen Tests (Bonferroni Correction?)

### 7.3 Praktische Implikationen
- Anwendung für algorithmisches Trading
- Risk Management Empfehlungen
- Portfolio Integration

---

## 8. KONKLUSION & AUSBLICK

### 8.1 Zusammenfassung der Findings
[Wird nach Studien-Completion ausgefüllt]

### 8.2 Beiträge zur Forschung
- Novel Framework für Weekly Profile Quantification
- Empirische Validierung von Price Action Patterns
- Confluence Scoring als predictive Factor

### 8.3 Zukünftige Forschung
1. Multi-Asset Generalisierung (Futures, Crypto)
2. Machine Learning Integration (Pattern Recognition)
3. Real-Time Execution Study (Paper vs Live)
4. Psychological Factor Integration

---

## 9. APPENDIX

### 9.1 Code Repository
```
GitHub: [Link to Public Repository]
License: MIT
DOI: [Will be assigned upon publication]
```

### 9.2 Data Dictionary

| Variable | Typ | Beschreibung | Beispiel |
|----------|-----|-------------|---------|
| `profile_type` | int (0-5) | Weekly Profile Klassifikation | 1 = Classic Bullish |
| `confluence_score` | float [0-5] | Multi-Factor Signal Strength | 4.25 |
| `entry_price` | float | Eröffnungspreis | 1.0945 |
| `stop_loss_pips` | int | Risk Distance | 35 |
| `target_price` | float | Take Profit Level | 1.1245 |
| `win` | bool | Trade Outcome | True/False |
| `pnl_pips` | int | Profit/Loss | +120 |
| `duration_bars` | int | Trade Duration | 24 |
| `session` | str | Trading Session | "NY" |
| `economic_event` | bool | News Influenced | True/False |

### 9.3 References

**Primäre Quellen:**
1. De Bondt, W. F., & Thaler, R. H. (1985). Does the stock market overreact? *Journal of Finance*, 40(3), 793-805.
2. Sharpe, W. F. (1966). Mutual fund performance. *Journal of Business*, 39(1), 119-138.
3. Neely, C. J., Rapach, D. E., & Tu, J. (2014). Forecasting the equity risk premium. *Management Science*, 60(8), 1927-1948.
4. Gagnon, J. E., & Karolyi, G. A. (2010). The economics of foreign exchange intervention. *International Journal of Finance & Economics*, 15(3), 274-290.

**Sekundäre Quellen:**
- ICT Market Profile Analysis (Mentorship Content, 2022)
- CFTC Commitment of Traders Reports
- BIS FX Market Surveys (2019-2025)

---

## 10. REVISION HISTORY

| Version | Datum | Autor | Änderungen |
|---------|-------|-------|-----------|
| 1.0 | 2026-01-25 | [Student] | Initial Framework |
| 1.1 | [Datum] | [Name] | [Revisions] |
| 2.0 | [Datum] | [Name] | Final Submission |

---

## STUDY CHECKLIST FOR ACADEMIC SUBMISSION

- [ ] Literature Review vollständig & cited
- [ ] Hypotheses klar formuliert
- [ ] Methodology reproduzierbar dokumentiert
- [ ] Statistical Tests mit p-values durchgeführt
- [ ] Limitations diskutiert
- [ ] Code & Data öffentlich verfügbar
- [ ] Results tabular & graphical präsentiert
- [ ] Conclusions evidence-based
- [ ] Bibliography in APA/Harvard Format
- [ ] Plagiarism Check durchgeführt
- [ ] Peer Review durchlaufen
- [ ] All Appendices included

---

**Dieser Leitfaden ist eine Template für eine akademische Studie. Passe ihn an deine spezifischen Anforderungen (Hochschule, Fachrichtung, Betreuer) an.**