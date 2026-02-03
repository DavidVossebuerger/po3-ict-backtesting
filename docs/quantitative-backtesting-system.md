# Modulares Quantitatives Backtesting System

Ein professionelles Framework für systematisches Backtesting und Performance-Analyse von Handelsstrategien basierend auf ICT-Frameworks, Weekly Profiles und Price Action.

---

## 1. Projektstruktur & Architektur

```
backtesting_system/
├── core/
│   ├── data_handler.py           # Datenbeschaffung & Preprocessing
│   ├── strategy_base.py          # Abstrakte Strategie-Klasse
│   ├── backtest_engine.py        # Backtesting-Motor
│   ├── risk_manager.py           # Risikomanagement-Module
│   ├── event_bus.py              # Event Routing
│   └── clock.py                  # Session/Time Abstraktion
├── interfaces/
│   ├── data_source.py            # DataSource Protocol
│   ├── execution.py              # Execution/Broker Protocol
│   ├── strategy.py               # Strategy Protocol
│   └── risk_model.py             # RiskModel Protocol
├── models/
│   ├── market.py                 # Candle, Tick, VolumeProfile
│   ├── orders.py                 # Order, Fill, Position
│   └── analytics.py              # EquityPoint, TradeRecord
├── strategies/
│   ├── weekly_profiles.py        # Weekly Profile Implementierung
│   ├── ict_framework.py          # ICT-Framework Module
│   ├── price_action.py           # Price Action Patterns
│   ├── composite_strategies.py   # Kombinierte Strategien
│   └── benchmark_buy_hold.py     # Benchmark Strategy
├── adapters/
│   ├── data_sources/
│   │   └── csv_source.py          # CSV-Adapter
│   └── execution/
│       └── simulated_broker.py   # Simulierter Broker
├── analytics/
│   ├── performance_metrics.py    # KPI-Berechnung
│   ├── portfolio_analysis.py     # Portfolio-Statistiken
│   ├── visualizations.py         # Plot & Chart-Generation
│   ├── reporting.py              # Report/CSV-Exports
│   ├── statistics.py             # Signifikanztests
│   └── monte_carlo.py            # Robustness Checks
├── pipelines/
│   ├── backtest_pipeline.py      # Backtest Orchestration
│   ├── csv_resample_pipeline.py  # M30→H1/H4/D Resampling
│   ├── walk_forward.py           # Walk-Forward Tests
│   └── parameter_sensitivity.py  # Sensitivity Runs
├── utils/
│   ├── validation.py             # Datenvalidierung
│   ├── logging.py                # Logging-Konfiguration
│   ├── timezones.py              # Sessions
│   └── hashing.py                # Checksums
├── config/
│   ├── settings.py               # Globale Konfiguration
│   └── trading_parameters.py     # Strategy-Parameter
└── main.py                       # Entry Point
```

### 1.1 Datenlayout (CSV)

**Input (RAW/PROCESSED):**
- Pflichtspalten: `time_utc, open, high, low, close`
- Zeitzone: UTC, ISO‑8601 (`YYYY-MM-DDTHH:MM:SSZ`)
- Beispiel: `2003-05-04T21:00:00Z,1.12284,1.12338,1.12242,1.12297`

**Resampled Outputs:**
- `data/processed/resampled/eurusd_h1.csv`
- `data/processed/resampled/eurusd_h4.csv`
- `data/processed/resampled/eurusd_d.csv`

### 1.2 Research Pipelines (Akademisch)

- **Walk‑Forward**: Train/Test Reports je Fenster, Korrelation IS/OOS
- **Monte‑Carlo**: Drawdown‑Distribution & Ruin‑Wahrscheinlichkeit
- **Parameter Sensitivity**: Robustheit vs `risk_per_trade`, Exit‑System

### 1.3 Ergebnis‑Outputs

- `results/report_*.json` (Strategie‑Reports)
- `results/trades_*.csv` (Trade‑Log inkl. Confluence)
- `results/summary.csv` (Vergleichstabelle)
- `results/statistical_tests.json` (T‑Test, Binomial, ANOVA)
- `results/walk_forward.json` + `results/walk_forward.csv`
- `results/parameter_sensitivity.json` + `results/parameter_sensitivity.csv`
- `results/monte_carlo.json` + `results/monte_carlo.csv`
- `results/metadata.json` (Checksum + Setup)

---

## 2. Core Module Beschreibungen

### 2.1 Data Handler (`data_handler.py`)

**Anforderungen:**
- Multi-Timeframe Daten laden (M5, M15, H1, H4, D, W)
- OHLCV + Volume Profile Daten
- Economic Calendar Integration
- News Events als separate Layer
- Daten normalisieren & validieren
- Fehlerbehandlung für fehlende Daten

**Key Functions:**
```python
class DataHandler:
    load_ohlcv(symbol, timeframe, start_date, end_date)
    get_volume_profile(candles, levels)
    fetch_economic_calendar(dates, importance)
    validate_data_integrity()
    align_timeframes(primary_tf, secondary_tfs)
    add_market_regime(data, regime_type='atr_deviation')
    get_intraday_sessions(data)  # Asia, London, NY sessions
```

### 2.2 Strategy Base (`strategy_base.py`)

**Abstrakte Klasse für alle Strategien:**
```python
class Strategy(ABC):
    def __init__(self, params: dict):
        # params: risk_per_trade, atr_period, timeframes
        self.params = params
        self.positions = []
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> dict:
        """Gibt LONG/SHORT/NEUTRAL + Entry/Stop/Target zurück"""
        pass
    
    @abstractmethod
    def identify_setup(self, data: pd.DataFrame) -> bool:
        """Prüft ob Setup vorhanden ist"""
        pass
    
    @abstractmethod
    def validate_context(self, data: pd.DataFrame) -> bool:
        """Context-Validierung (News, Volatility, Session)"""
        pass
    
    def calculate_position_size(self, account_size, risk_per_trade, stop_distance):
        pass
    
    def get_confluences(self, data: pd.DataFrame) -> dict:
        """Returns confluence score 1-5"""
        pass
```

### 2.3 Backtest Engine (`backtest_engine.py`)

**Der Motor für Simulationen:**

**Features:**
- Bar-by-Bar Simulation
- Slippage & Spread berücksichtigung
- Commission Berechnung
- Multiple Entry/Exit Logik
- Partial Profit Taking (z.B. 75% Trail to 1R)
- Daily/Weekly/Monthly P&L
- Drawdown Tracking
- Win Rate & Trade Statistics
- Equity Curve Generation

```python
class BacktestEngine:
    def __init__(self, initial_capital, strategy, risk_params):
        pass
    
    def run_backtest(self, data: pd.DataFrame, start_date, end_date):
        """Führt komplette Backtesting aus"""
        pass
    
    def process_signal(self, signal: dict, current_price, bar_index):
        """Verarbeitet Ein- und Ausgänge"""
        pass
    
    def apply_risk_management(self, position):
        """Trail Stops, Partial Exits, etc."""
        pass
    
    def calculate_returns(self):
        """Returns, Drawdown, Recovery"""
        pass
    
    def generate_report(self) -> dict:
        """Kompletter Backtesting Report"""
        pass
```

### 2.4 Risk Manager (`risk_manager.py`)

**Riskomanagement-Module:**

```python
class RiskManager:
    # Fixed Risk Management
    def calculate_1r_system(self, entry, stop_loss, target):
        """1:2 RR oder 1:3 RR"""
        pass
    
    # Partial Exit System (deine Methode)
    def partial_exit_trail_stop(self, entry, stop_loss, target, trail_percentage=0.75):
        """75% Exit bei 1R, Runner bleibt mit Trailing Stop"""
        pass
    
    # Daily/Weekly Stop Outs
    def apply_daily_drawdown_limit(self, daily_loss, max_daily_risk):
        pass
    
    def apply_weekly_risk_limit(self, weekly_loss, max_weekly_risk):
        pass
    
    # Position Sizing
    def calculate_position_size(self, account_size, risk_per_trade, entry, stop):
        """Berechnet volumen basierend auf Risk"""
        pass
    
    # Portfolio Risk
    def check_correlation_risk(self, positions):
        """Prüft korrelierte Positionen"""
        pass
    
    # Volatility Adjustment
    def adjust_risk_for_volatility(self, atr, average_atr):
        """Erhöhe/Senke Risk bei extremen Volatilität"""
        pass
```

---

## 3. Strategie Module

### 3.1 Weekly Profiles (`weekly_profiles.py`)

Basierend auf deinen PDFs implementieren:

**Profile Types:**
1. **Classic Bullish Expansion**: MON-TUE engagement auf Discount Array → WED-THU Expansion
2. **Classic Bearish Expansion**: MON-TUE engagement auf Premium Array → WED-THU Expansion
3. **Midweek Reversal (Bullish)**: MON-TUE Bearish → WED Reversal auf Discount → THU-FRI Bullish
4. **Midweek Reversal (Bearish)**: MON-TUE Bullish → WED Reversal auf Premium → THU-FRI Bearish
5. **Consolidation Reversal**: WED-THU externe Range Reversal → FRI Continuation
6. **Seek & Destroy**: Low Probability, Skip

```python
class WeeklyProfileStrategy(Strategy):
    def __init__(self, params):
        super().__init__(params)
        self.profile_type = None
        self.dol = None  # Day of Low
        self.doh = None  # Day of High
    
    def identify_weekly_profile(self, weekly_data, daily_data) -> str:
        """Identifiziert Weekly Profile basierend auf MON-TUE Setup"""
        # Returns: "classic_expansion_long", "classic_expansion_short", 
        #         "midweek_reversal_long", "midweek_reversal_short",
        #         "consolidation_reversal_long/short", None
        pass
    
    def analyze_mon_tue(self, daily_candles) -> dict:
        """MON-TUE Analyse für Profile Identification"""
        # Returns: {"type": "expansion"/"reversal", 
        #          "direction": "long"/"short",
        #          "engagement_level": h1_pda,
        #          "dol": date}
        pass
    
    def identify_setup(self, data) -> bool:
        """Prüft ob Weekly Profile Setup aktiv ist"""
        pass
    
    def generate_signals(self, data) -> dict:
        """Generiert TUE/WED/THU-FRI Signals je nach Profile"""
        pass
    
    def validate_pda_array(self, price, h1_pda) -> bool:
        """Prüft ≥H1 PDA Engagement"""
        pass
    
    def calculate_dol_doh(self, daily_data) -> tuple:
        """Berechnet Day of Low / Day of High"""
        pass
    
    def check_negative_conditions(self, daily_data) -> bool:
        """Filtert Low-Probability Setups"""
        pass
```

### 3.2 ICT Framework (`ict_framework.py`)

**Key Components:**

```python
class ICTFramework(Strategy):
    """
    Implementiert ICT Market Profile Trading:
    - Supply/Demand Imbalance
    - Fair Value Gaps (FVG)
    - Order Blocks (OB)
    - Breaker Blocks (BRK)
    - Range High Range Low Protocol (RHRL)
    - Asian/London/NY Session Profiles
    """
    
    def __init__(self, params):
        super().__init__(params)
        self.fvg_detector = FairValueGapDetector()
        self.ob_detector = OrderBlockDetector()
        self.session_profiler = SessionProfiler()
    
    # === LIQUIDITY TARGETING ===
    def identify_fvg(self, candles: List[Candle]) -> List[dict]:
        """Fair Value Gaps: Lücken zwischen Candles die gefüllt werden"""
        # Returns: [{"level": price, "type": "bullish"/"bearish", "candle_idx": idx}]
        pass
    
    def identify_order_blocks(self, candles: List[Candle], lookback=10) -> List[dict]:
        """Order Blocks: Bereich wo große Orders platziert"""
        pass
    
    def identify_breaker_blocks(self, candles, lookback=5) -> List[dict]:
        """Breaker: Höher High mit Bearish Close oder Lower Low mit Bullish Close"""
        pass
    
    # === SESSION ANALYSIS ===
    def analyze_asia_session(self, hourly_data) -> dict:
        """Analysiert 00:00-09:00 UTC (0:00-9:00 London)"""
        pass
    
    def analyze_london_session(self, hourly_data) -> dict:
        """Analysiert 08:00-17:00 UTC (London Session)"""
        pass
    
    def analyze_ny_session(self, hourly_data) -> dict:
        """Analysiert 13:00-22:00 UTC (NY Session)"""
        pass
    
    def identify_ny_reversal(self, data) -> dict:
        """NY Reversal: Asia/London trend lower → NY reversal + expansion"""
        pass
    
    # === RANGE HIGH RANGE LOW PROTOCOL ===
    def rhrl_protocol(self, daily_candles) -> dict:
        """
        RHRL Setup:
        1. Daily drops into key level
        2. Hourly bounces off level
        3. Market wird 2-sided
        4. Run Range Low dann Range High (oder vice versa)
        """
        pass
    
    # === CONTEXT & PROBABILITY ===
    def check_adrs_remaining(self, daily_adr, price_moved_today) -> float:
        """ADR Remaining nach NY Open"""
        pass
    
    def identify_high_resistance_swing(self, lowerTF_data) -> dict:
        """Stop Hunt vor Expansion"""
        pass
    
    def get_stop_hunt_confirmation(self, swing_type: str, signal_type: str) -> bool:
        """No Stop Hunt = No Trade"""
        pass
```

### 3.3 Price Action (`price_action.py`)

```python
class PriceActionStrategy(Strategy):
    """
    Implementiert Price Action Patterns:
    - Daily Swing Framework
    - Intraday Reversals
    - Consolidation Raids
    - Buy Day Profiles
    """
    
    def identify_daily_swing_framework(self, daily_candles) -> dict:
        """
        Respecting Previous Day's Wick vs Quadrant
        - Reversal: Trade gegen Previous Day Wick
        - Continuation: Trade mit Previous Day Quadrant
        """
        pass
    
    def identify_intraday_reversal_setup(self, hourly_data) -> dict:
        """
        Early reversal signal:
        - Multiple rejections off level
        - Change in rate of price delivery
        - LTF confirmation
        """
        pass
    
    def identify_consolidation_raid(self, hourly_data, news_time: datetime) -> dict:
        """
        Market konsolidiert vor News → News manipuliert false direction 
        → schnelle Reversal in korrekten Direction
        """
        pass
    
    def identify_buy_day(self, daily_candle, hourly_data) -> bool:
        """
        Buy Day Profile:
        - Reversal early overnight (Asia/London)
        - Aggressive trend bis NY
        - Minimal Daily Wick
        - Little Retracements
        """
        pass
    
    def detect_wicks_vs_bodies(self, candles) -> dict:
        """Analysiert Wick-Struktur für Stop Hunts"""
        pass
    
    def identify_expansion_day(self, daily_candle) -> bool:
        """High Range mit wenig Retracements = Expansion Day"""
        pass
```

### 3.4 Composite Strategies (`composite_strategies.py`)

```python
class CompositeStrategy(Strategy):
    """
    Kombiniert mehrere Strategien mit Confluence Scoring:
    
    Setup Confluence Score (1-5):
    - 5/5: Best Confluence
    - 4.5/5: Very High
    - 4/5: High
    - 3.5/5: Medium-High (Nur bei großen Edges)
    - 3/5 und unter: Skip
    """
    
    def __init__(self, params):
        self.weekly_profile_strategy = WeeklyProfileStrategy(params)
        self.ict_strategy = ICTFramework(params)
        self.pa_strategy = PriceActionStrategy(params)
        self.min_confluence_level = 4.0
    
    def calculate_confluence_score(self, data, context) -> float:
        """
        Confluence Factors:
        - Weekly Profile Type: +1.0 (wenn aktiv)
        - HTF PDA Alignment: +0.5
        - Session Quality: +0.5
        - RHRL Protocol: +0.5
        - Stop Hunt Confirmed: +0.5
        - News Driver: +0.5
        - ADR Remaining: +0.5 (when favorable)
        - Daily Swing Context: +0.25
        """
        pass
    
    def generate_signals(self, data) -> dict:
        """Kombiniert Signale nur bei hoher Confluence"""
        pass
    
    def rank_trading_days(self, data) -> dict:
        """
        Nach deinen Frameworks:
        - 5/5 Rating: WED (Midweek Reversal), Best Expansion Days
        - 4.5/5 Rating: THU bei Weekly Profiles
        - 4/5 Rating: FRI bei richtigem Context
        - 3/5 und unter: Skip (Monday meist, low probability)
        """
        pass
```

---

## 4. Analytics Module

### 4.1 Performance Metrics (`performance_metrics.py`)

```python
class PerformanceMetrics:
    """
    Berechnet alle wichtigen Backtest Metriken:
    """
    
    # === RETURN METRICS ===
    def total_return(self, equity_curve) -> float:
        pass
    
    def compound_annual_growth_rate(self, equity_curve, days_traded) -> float:
        pass
    
    def daily_returns(self, equity_curve) -> List[float]:
        pass
    
    def monthly_returns(self, equity_curve, dates) -> Dict[str, float]:
        pass
    
    def weekly_returns(self, equity_curve, dates) -> Dict[str, float]:
        pass
    
    # === RISK METRICS ===
    def max_drawdown(self, equity_curve) -> Tuple[float, int, int]:
        """(max_dd_pct, start_idx, end_idx)"""
        pass
    
    def drawdown_duration(self, equity_curve) -> int:
        """Tage bis Recovery"""
        pass
    
    def volatility(self, daily_returns) -> float:
        """Annualized Volatility"""
        pass
    
    def value_at_risk(self, daily_returns, confidence=0.95) -> float:
        pass
    
    def conditional_value_at_risk(self, daily_returns, confidence=0.95) -> float:
        pass
    
    # === TRADE STATISTICS ===
    def total_trades(self, trades: List[Trade]) -> int:
        pass
    
    def winning_trades(self, trades) -> int:
        pass
    
    def losing_trades(self, trades) -> int:
        pass
    
    def win_rate(self, trades) -> float:
        """% Winning Trades"""
        pass
    
    def profit_factor(self, trades) -> float:
        """Gross Profit / Gross Loss"""
        pass
    
    def expectancy_per_trade(self, trades) -> float:
        """Average $ per Trade"""
        pass
    
    def average_win(self, trades) -> float:
        pass
    
    def average_loss(self, trades) -> float:
        pass
    
    def risk_reward_ratio(self, trades) -> float:
        pass
    
    def consecutive_wins(self, trades) -> int:
        pass
    
    def consecutive_losses(self, trades) -> int:
        pass
    
    def largest_win(self, trades) -> float:
        pass
    
    def largest_loss(self, trades) -> float:
        pass
    
    # === QUALITY METRICS (deine Trading Quality) ===
    def day_win_rate(self, trades) -> float:
        """% Days Profitable (wichtiger als Trade Win Rate)"""
        pass
    
    def monthly_win_rate(self, trades) -> float:
        """% Months Profitable"""
        pass
    
    def recovery_factor(self, total_profit, max_drawdown) -> float:
        """Total Profit / Max Drawdown"""
        pass
    
    def calmar_ratio(self, annual_return, max_drawdown) -> float:
        """Return / Max Drawdown (ähnlich Sharpe)"""
        pass
    
    def sharpe_ratio(self, daily_returns, risk_free_rate=0.02) -> float:
        pass
    
    def sortino_ratio(self, daily_returns, risk_free_rate=0.02) -> float:
        """Nur Downside Volatility"""
        pass
    
    def ulcer_index(self, equity_curve) -> float:
        pass
    
    # === BEHAVIORAL METRICS ===
    def average_trade_duration(self, trades) -> timedelta:
        pass
    
    def longest_trade(self, trades) -> timedelta:
        pass
    
    def shortest_trade(self, trades) -> timedelta:
        pass
    
    def average_bars_in_trade(self, trades, timeframe) -> float:
        pass
    
    def average_win_duration(self, trades) -> timedelta:
        pass
    
    def average_loss_duration(self, trades) -> timedelta:
        pass
```

### 4.2 Portfolio Analysis (`portfolio_analysis.py`)

```python
class PortfolioAnalysis:
    """Multi-Symbol & Multi-Timeframe Analyse"""
    
    def correlation_matrix(self, symbols: List[str], returns) -> np.ndarray:
        """Korrelation zwischen Symbols"""
        pass
    
    def portfolio_volatility(self, positions, covariance_matrix) -> float:
        pass
    
    def diversification_ratio(self, positions, volatilities, covariance) -> float:
        pass
    
    def generate_portfolio_report(self, backtest_results) -> dict:
        pass
    
    # === MONTE CARLO SIMULATION ===
    def monte_carlo_analysis(self, trades: List[Trade], iterations=1000) -> dict:
        """
        Simuliert verschiedene Trade-Reihenfolgen um worst-case zu verstehen
        Returns: {"min_equity", "max_equity", "percentiles", "prob_ruin"}
        """
        pass
    
    def calculate_probability_of_ruin(self, trades, account_size) -> float:
        pass
    
    def walk_forward_analysis(self, data, strategy, window_size=252, step=63):
        """Out-of-sample Test: Training auf T-252 Tage, Test auf T+63"""
        pass
    
    def parameter_sensitivity_analysis(self, strategy_params: dict):
        """Teste verschiedene Parameter-Kombinationen"""
        pass
```

### 4.3 Visualizations (`visualizations.py`)

```python
class Backtester Visualizations:
    """Generiert professionelle Trading Charts"""
    
    # === EQUITY CURVE ===
    def plot_equity_curve(self, equity_data, trades=None, save_path=None):
        """Equity Line mit Trade Markers"""
        pass
    
    def plot_drawdown(self, equity_curve, save_path=None):
        pass
    
    def plot_monthly_returns(self, trades, save_path=None):
        """Heatmap: Monate vs Jahre"""
        pass
    
    # === TRADE ANALYSIS ===
    def plot_price_action_with_trades(self, ohlcv_data, trades, 
                                     signals, weekly_profile_type=None):
        """OHLCV Chart mit:
        - Entry/Exit Points
        - Stop Loss / Take Profit
        - Weekly Profile Overlay
        - Session Coloring
        """
        pass
    
    def plot_trade_statistics(self, trades):
        """Win/Loss Distribution, Risk/Reward Scatter"""
        pass
    
    # === PERFORMANCE DASHBOARD ===
    def generate_performance_dashboard(self, metrics: dict, save_path=None):
        """
        4-Panel Dashboard:
        1. Equity Curve + Drawdown
        2. Monthly Returns Heatmap
        3. Trade Distribution
        4. Key Metrics Table
        """
        pass
    
    # === WALK-FORWARD & MONTE CARLO ===
    def plot_walk_forward_results(self, wf_results):
        pass
    
    def plot_monte_carlo_distribution(self, mc_results):
        pass
```

---

## 5. Configuration Module

### 5.1 Settings (`settings.py`)

```python
# Global Constants
TRADING_SESSIONS = {
    "ASIA": (0, 9),           # UTC Hours
    "LONDON": (8, 17),
    "NY": (13, 22)
}

MARKET_OPEN_TIMES = {
    "GBPJPYeuro": {
        "asia_high_zone": (9, 13),  # London Open Window
        "ny_session": (13, 22)
    }
}

DEFAULT_PARAMS = {
    "initial_capital": 10000,
    "risk_per_trade": 0.02,  # 2% pro Trade
    "max_daily_risk": 0.05,  # 5% pro Tag
    "max_weekly_risk": 0.1,  # 10% pro Woche
    "atr_period": 14,
    "atr_multiplier": 1.5,  # For Stop Loss distance
    "timeframes": ["M5", "M15", "H1", "H4", "D", "W"],
    "slippage_pips": 2,
    "commission_pct": 0.0001,
    "leverage": 1
}

CONFLUENCE_THRESHOLDS = {
    "min_trading_confluence": 4.0,
    "min_expansion_day_confluence": 4.5,
    "max_seek_destroy_confluence": 2.5
}
```

### 5.2 Trading Parameters (`trading_parameters.py`)

```python
WEEKLY_PROFILE_PARAMS = {
    "classic_expansion": {
        "tuesday_engagement_pips": 50,
        "wed_thu_target_extension": 1.5,  # 1.5x MON-TUE Range
        "friday_retracement_pct": 0.20  # 20% Fibonacci
    },
    "midweek_reversal": {
        "wed_engagement_pips": 30,
        "thu_fri_target_extension": 2.0,  # 2.0x MON-TUE Range
        "friday_target_pct": 0.30
    }
}

ICT_FRAMEWORK_PARAMS = {
    "fvg_size_pips": 10,
    "ob_confirmation_bars": 3,
    "session_analysis_enabled": True,
    "ny_reversal_ma_lookback": 50,
    "rhrl_protocol_enabled": True
}

RISK_MANAGEMENT_PARAMS = {
    "risk_reward_minimum": 1.0,  # 1:1 min (aber 1:2 bevorzugt)
    "partial_exit_percentage": 0.75,  # 75% at 1R
    "trail_stop_to_breakeven": True,
    "max_position_size_pct": 0.05  # 5% Account Risk Max
}
```

---

## 6. Main Execution Script

### 6.1 Main Entry Point (`main.py`)

```python
def main():
    # 1. Load Configuration
    config = load_config("config/settings.py")
    
    # 2. Fetch & Prepare Data
    data_handler = DataHandler()
    ohlcv_data = data_handler.load_ohlcv(
        symbol="GBPJPY",
        timeframe="H1",
        start_date="2024-01-01",
        end_date="2025-01-25"
    )
    
    # 3. Initialize Strategy
    strategy = CompositeStrategy(config.TRADING_PARAMETERS)
    
    # 4. Run Backtest
    engine = BacktestEngine(
        initial_capital=config.INITIAL_CAPITAL,
        strategy=strategy,
        risk_params=config.RISK_MANAGEMENT_PARAMS
    )
    
    results = engine.run_backtest(
        data=ohlcv_data,
        start_date="2024-01-01",
        end_date="2025-01-25"
    )
    
    # 5. Analyze Results
    metrics = PerformanceMetrics()
    performance = {
        "total_return": metrics.total_return(results.equity_curve),
        "win_rate": metrics.win_rate(results.trades),
        "max_drawdown": metrics.max_drawdown(results.equity_curve),
        "day_win_rate": metrics.day_win_rate(results.trades),
        "sharpe_ratio": metrics.sharpe_ratio(results.daily_returns),
        "profit_factor": metrics.profit_factor(results.trades),
        "recovery_factor": metrics.recovery_factor(
            results.total_profit, 
            results.max_drawdown
        )
    }
    
    # 6. Monte Carlo Analysis
    portfolio = PortfolioAnalysis()
    mc_results = portfolio.monte_carlo_analysis(results.trades, iterations=1000)
    wf_results = portfolio.walk_forward_analysis(
        ohlcv_data, strategy, window_size=252, step=63
    )
    
    # 7. Generate Reports & Visualizations
    visualizer = Visualizations()
    visualizer.generate_performance_dashboard(performance)
    visualizer.plot_equity_curve(results.equity_curve, results.trades)
    visualizer.plot_monthly_returns(results.trades)
    visualizer.plot_monte_carlo_distribution(mc_results)
    
    # 8. Save Results
    results.to_csv("backtest_results.csv")
    save_report(performance, "backtest_report.json")
    
    return results, performance, mc_results

if __name__ == "__main__":
    main()
```

---

## 7. Example Usage mit Claude/AI Copilot

**Prompt 1: New Strategy Implementation**
```
"Implementiere die Weekly Profile Classic Bullish Expansion Strategie. 
Nutze die folgende Logik:
1. MON-TUE: Prüfe ob Market auf ≥H1 Discount PDA engaged
2. TUE: Identifiziere Reversal (Close über Breaker Block)
3. WED-THU: Trade Expansion towards Weekly Draw
4. FRI: Erwarte TGIF Retracement

Gib mir:
- detect_classic_bullish_setup(daily_data, hourly_data) function
- generate_tuesday_signals(data) für Entry
- calculate_weekly_targets(dol, expansion_days)
- Confluence scoring für jedes Signal"
```

**Prompt 2: Parameter Optimization**
```
"Optimize die Weekly Profile Parameter mit Walk-Forward Analysis:
- Test Period: 2023-01-01 bis 2025-01-25
- Training Window: 252 Tage (1 Jahr)
- Test Window: 63 Tage (3 Monate)
- Step: 63 Tage (Roll forward)

Optimiere:
- atr_multiplier: [1.0, 1.5, 2.0, 2.5]
- confluence_threshold: [3.5, 4.0, 4.5, 5.0]
- daily_risk: [1%, 2%, 3%, 5%]

Return: Parameter Set mit bester Sharpe Ratio & Day Win Rate"
```

**Prompt 3: Risk Analysis**
```
"Führe vollständige Risk Analysis durch:
1. Monte Carlo Simulation (5000 iterations)
2. Probability of Ruin bei 50% Drawdown
3. Maximum Consecutive Losses
4. Worst Month Analysis
5. Correlation Risk wenn ich mehrere Pairs handle

Gib detaillierten Report mit Empfehlungen für Risk Management"
```

**Prompt 4: Strategy Improvement**
```
"Analysiere die Backtest Results und identifiziere:
1. Wo die Strategie profitabel ist (nach Month, Session, Profile Type)
2. Wo die Strategie verliert
3. Confluence Levels die zu falschen Signalen führen
4. Verbessere die Filter für Low-Probability Trades

Gib konkrete Verbesserungen an"
```

---

## 8. Best Practices für Backtesting

### 8.1 Datenqualität
- ✅ Nutze VERIFIED Daten von etablierten Quellen (yfinance, EODHD, FMP)
- ✅ Prüfe auf Gaps, Spikes, fehlerhafte Candles
- ✅ Adjustiere für Corporate Actions (Splits, Dividends)
- ✅ Verwende Adjusted Close für Analysen

### 8.2 Simulation Accuracy
- ✅ Realistischer Slippage (2-5 pips je nach Volatilität)
- ✅ Spread berücksichtigung (1-3 pips typisch)
- ✅ Commission für jeden Trade
- ✅ Bar-by-Bar Verarbeitung (nicht nur Close)

### 8.3 Overfitting Prevention
- ✅ Walk-Forward Analysis (nicht nur In-Sample)
- ✅ Parameter Sensitivity Testing
- ✅ Out-of-Sample Period mindestens 20% der Data
- ✅ Vermeid Curve-Fitting an Historische Data

### 8.4 Statistical Significance
- ✅ Mindestens 100 Trades für valide Statistiken
- ✅ Minimum 2-3 Jahre historische Data
- ✅ Multiple Timeframes & Symbols testen
- ✅ Beste Metriken: Day Win Rate > Trade Win Rate

### 8.5 Monitoring & Validation
- ✅ Forward Test nach Live Trading starten
- ✅ Compare Backtest vs Live Performance
- ✅ Adjustiere Parameter bei Markt-Regime Changes
- ✅ Dokumentiere ALLE Trade Decisions

---

## 9. Debugging & Logging

```python
# Setup Logging
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Log Levels:
# DEBUG: Detaillierter Signal-by-Signal Output
# INFO: Weekly Results, Profile Identification
# WARNING: Negative Conditions, Low Confluence
# ERROR: Data Issues, Calculation Failures
# CRITICAL: System Failures
```

---

## 10. Deployment Checklist

- [ ] Alle Module unit-tested
- [ ] Backtest auf Multiple Timeframes laufen
- [ ] Walk-Forward Results validiert
- [ ] Monte Carlo Analysis completo
- [ ] Performance Dashboard generiert
- [ ] Risk Metrics alle im grünen Bereich
- [ ] Paper Trading Phase mindestens 30 Tage
- [ ] Live Trading mit Micro Lots starten
- [ ] Tägliches Monitoring & Logging
- [ ] Quarterly Parameter Review

---

**Autoren-Note:** Dieses System wurde entwickelt für systematisches, quantitatives Backtesting von Price Action und Weekly Profile basierten Strategien. Es kombiniert rigorose statistische Analyse mit praktischen Trading-Framework-Anforderungen.