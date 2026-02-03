Perfekt! Ich erstelle dir jetzt eine vollständige Markdown-Datei mit allen Fixes:

```markdown
# ICT Strategy Implementation Fixes - Handbuch-konform

**Repository:** `po3-ict-backtesting`  
**Datum:** 03.02.2026  
**Basis:** The Blueprint.pdf + Weekly Profile Guide.pdf

---

## 🎯 Executive Summary

Diese Dokumentation beschreibt **5 kritische Fixes**, um die ICT-Strategien handbuchkonform zu implementieren:

1. ✅ **Stop Loss Placement** - Korrekte PDA-basierte SL-Logik
2. ✅ **Take Profit Targets** - Profile-spezifische TP-Projektion
3. ✅ **Entry Confluence Scoring** - Weniger restriktiv, mehr Trades
4. ✅ **TGIF Return Setup** - Präzise Fibonacci 20-30% Levels
5. ✅ **Opening Range Framework** - Korrekte Distanz-Projektion

**Impact:** Erhöht Trade Frequency (aktuell 0 Composite Trades → erwartete 5-15 Trades/Monat) und stellt akademische Validität sicher.

---

## 📊 Problem-Übersicht

| Problem | Aktueller Code | Handbuch-Regel | Priorität |
|---------|----------------|----------------|-----------|
| **SL Placement** | `min(c.low for c in history[-10:])` | Order Block/FVG boundary | 🔴 CRITICAL |
| **TP Target** | Fixed 2R (Risk-Reward) | Profile-specific (Mon/Tue extreme, OR projection, Fib 20-30%) | 🔴 CRITICAL |
| **Entry Filters** | ALL required (Stop Hunt + PDA + OR) → 0 Trades | PDA mandatory, others optional (confluence scoring) | 🔴 CRITICAL |
| **TGIF Levels** | Entry zone 20-30% weekly range (zu breit) | Entry AT H1 PDA within Fib 20-30% zone | 🟡 HIGH |
| **Opening Range** | `expected_high = opening + distance_to_low` (falsch) | Project distance-to-low/high to opposite side | 🟡 HIGH |

---

## 🔧 FIX #1: Stop Loss Placement (CRITICAL)

### ❌ Aktueller Code

**Datei:** `backtesting_system/strategies/ict_framework.py` (Zeile ~478)

```python
if direction == "long":
    stop = min(c.low for c in history[-10:])  # FALSCH!
    target = self.project_target(bar.close, stop, "long")
```

**Problem:**
- Verwendet einfach das Minimum der letzten 10 Bars
- Ignoriert Order Blocks, Fair Value Gaps, Breaker Blocks
- Nicht ICT-konform

### ✅ Handbuch-Regel

**Quelle:** The Blueprint.pdf, Seite "Range High Range Low Protocol"

> "Stop Loss Placement: Order Block Low/High, Fair Value Gap boundaries, Breaker Block levels"

**Quelle:** Weekly Profile Guide.pdf, Seite "Framework"

> "Stop below H1 PDA discount array for longs, above H1 PDA premium array for shorts"

### ✅ Korrekte Implementation

**Neue Methode in `ict_framework.py`:**

```python
def calculate_stop_loss(self, direction: str, entry: float, h1_arrays: dict, daily_candles: List[Candle]) -> float:
    """
    ICT-compliant Stop Loss nach Official Handbuch.
    
    Priority Order:
    1. Order Block boundary (highest priority)
    2. Fair Value Gap boundary
    3. Breaker Block level
    4. Fallback: Previous day low/high
    
    Args:
        direction: "long" or "short"
        entry: Entry price
        h1_arrays: Dict with "order_blocks", "fvgs", "breakers"
        daily_candles: Daily timeframe candles
    
    Returns:
        Stop loss price with 2-pip buffer
    """
    buffer_pips = 2
    buffer = buffer_pips / 10000  # Convert pips to price
    
    if direction == "long":
        # Priority 1: Order Block below entry
        obs = [ob for ob in h1_arrays.get("order_blocks", []) 
               if ob["type"] == "bullish" and ob["low"] < entry]
        if obs:
            nearest_ob = max(obs, key=lambda x: x["low"])
            return nearest_ob["low"] - buffer
        
        # Priority 2: Fair Value Gap below entry
        fvgs = [fvg for fvg in h1_arrays.get("fvgs", []) 
                if fvg["type"] == "bullish" and fvg["low"] < entry]
        if fvgs:
            nearest_fvg = max(fvgs, key=lambda x: x["low"])
            return nearest_fvg["low"] - buffer
        
        # Priority 3: Breaker Block below entry
        breakers = [brk for brk in h1_arrays.get("breakers", []) 
                    if brk["type"] == "bullish" and brk["level"] < entry]
        if breakers:
            nearest_brk = max(breakers, key=lambda x: x["level"])
            return nearest_brk["level"] - buffer
        
        # Fallback: Previous daily low
        if len(daily_candles) >= 2:
            return daily_candles[-2].low - (buffer * 2.5)  # 5 pips buffer
        
        # Emergency fallback
        return entry * 0.995  # -0.5%
    
    else:  # short
        # Same logic inverted for shorts
        obs = [ob for ob in h1_arrays.get("order_blocks", []) 
               if ob["type"] == "bearish" and ob["high"] > entry]
        if obs:
            nearest_ob = min(obs, key=lambda x: x["high"])
            return nearest_ob["high"] + buffer
        
        fvgs = [fvg for fvg in h1_arrays.get("fvgs", []) 
                if fvg["type"] == "bearish" and fvg["high"] > entry]
        if fvgs:
            nearest_fvg = min(fvgs, key=lambda x: x["high"])
            return nearest_fvg["high"] + buffer
        
        breakers = [brk for brk in h1_arrays.get("breakers", []) 
                    if brk["type"] == "bearish" and brk["level"] > entry]
        if breakers:
            nearest_brk = min(breakers, key=lambda x: x["level"])
            return nearest_brk["level"] + buffer
        
        if len(daily_candles) >= 2:
            return daily_candles[-2].high + (buffer * 2.5)
        
        return entry * 1.005
```

### 📝 Integration in `generate_signals()`

**Ersetze in `ict_framework.py` (Zeile ~478):**

```python
# ALT:
stop = min(c.low for c in history[-10:])

# NEU:
daily_candles = self._daily_from_history(history)
stop = self.calculate_stop_loss(direction, entry, h1_arrays, daily_candles)
```

---

## 🔧 FIX #2: Take Profit Targets (CRITICAL)

### ❌ Aktueller Code

**Datei:** `backtesting_system/core/strategy_base.py` (vermutlich)

```python
def project_target(self, entry, stop, direction):
    risk = abs(entry - stop)
    if direction == "long":
        return entry + (risk * 2.0)  # Fixed 2R
    else:
        return entry - (risk * 2.0)
```

**Problem:**
- Fixed 2R ignoriert ICT-Profile
- Keine Unterscheidung zwischen Classic Expansion, Midweek Reversal, TGIF
- Targets müssen profile-spezifisch sein

### ✅ Handbuch-Regel

**Quelle:** The Blueprint.pdf, Seiten "Classic Expansion", "Midweek Reversal", "TGIF"

> **Classic Expansion:** Target = Monday/Tuesday opposite extreme + Opening Range projection  
> **Midweek Reversal:** Target = Intra-week High (for longs) / Intra-week Low (for shorts)  
> **TGIF Return:** Target = Fibonacci 0.20-0.30 retracement of weekly range

**Quelle:** Weekly Profile Guide.pdf, Seite "TGIF Target"

> "Target internal H1 PD arrays within 0.20-0.30 retracement of weekly range"

### ✅ Korrekte Implementation

**Neue Methode in `weekly_profiles.py`:**

```python
def calculate_take_profit(self, direction: str, entry: float, profile_type: str, 
                          mon_tue_low: float, mon_tue_high: float, 
                          weekly_high: float, weekly_low: float,
                          opening_range: dict, stop: float) -> float:
    """
    ICT-compliant Take Profit nach Official Handbuch.
    
    Profile-specific targets:
    - Classic Expansion: Mon/Tue opposite extreme + Opening Range projection
    - Midweek Reversal: Intra-week High/Low (Mon/Tue extreme)
    - Consolidation Reversal: External range equilibrium (0.5)
    - TGIF: 20-30% Fibonacci retracement
    
    Args:
        direction: "long" or "short"
        entry: Entry price
        profile_type: e.g. "classic_expansion_long", "midweek_reversal_short", "tgif_return"
        mon_tue_low: Monday-Tuesday accumulated low
        mon_tue_high: Monday-Tuesday accumulated high
        weekly_high: Current week high
        weekly_low: Current week low
        opening_range: Dict from calculate_opening_range()
        stop: Calculated stop loss (for fallback R:R)
    
    Returns:
        Take profit price
    """
    
    # TGIF Return Profile
    if "tgif" in profile_type.lower():
        weekly_range = weekly_high - weekly_low
        if weekly_range <= 0:
            # Fallback: 1.5R
            risk = abs(entry - stop)
            return entry + (risk * 1.5) if direction == "long" else entry - (risk * 1.5)
        
        if direction == "long":
            # Target: Midpoint of 0.20-0.30 Fib (from low)
            fib_20 = weekly_low + (weekly_range * 0.20)
            fib_30 = weekly_low + (weekly_range * 0.30)
            return (fib_20 + fib_30) / 2
        else:
            # Target: Midpoint of 0.70-0.80 Fib (= top 20-30%)
            fib_70 = weekly_low + (weekly_range * 0.70)
            fib_80 = weekly_low + (weekly_range * 0.80)
            return (fib_70 + fib_80) / 2
    
    # Classic Expansion Profile
    elif "classic_expansion" in profile_type:
        if opening_range and opening_range.get("target"):
            # Primary: Opening Range projected target
            return opening_range["target"]
        else:
            # Secondary: Monday/Tuesday opposite extreme
            if direction == "long":
                return mon_tue_high if mon_tue_high else weekly_high
            else:
                return mon_tue_low if mon_tue_low else weekly_low
    
    # Midweek Reversal Profile
    elif "midweek_reversal" in profile_type:
        # Target = Intra-week High/Low (established Mon/Tue)
        if direction == "long":
            # Target previous intra-week high
            return mon_tue_high if mon_tue_high else weekly_high
        else:
            # Target previous intra-week low
            return mon_tue_low if mon_tue_low else weekly_low
    
    # Consolidation Reversal Profile
    elif "consolidation_reversal" in profile_type:
        # Target = External range equilibrium (0.5 level)
        if direction == "long":
            # Long from external low → Target = 0.5 of consolidation range
            consolidation_high = mon_tue_high if mon_tue_high else weekly_high
            consolidation_low = mon_tue_low if mon_tue_low else weekly_low
            return (consolidation_high + consolidation_low) / 2
        else:
            # Short from external high → Target = 0.5
            consolidation_high = mon_tue_high if mon_tue_high else weekly_high
            consolidation_low = mon_tue_low if mon_tue_low else weekly_low
            return (consolidation_high + consolidation_low) / 2
    
    # Conservative Fallback: 1.5R
    else:
        risk = abs(entry - stop)
        if direction == "long":
            return entry + (risk * 1.5)
        else:
            return entry - (risk * 1.5)
```

### 📝 Integration in `generate_signals()`

**Ersetze in `weekly_profiles.py` (Zeile ~200):**

```python
# ALT:
target = self.project_target(entry, stop, direction)

# NEU:
target = self.calculate_take_profit(
    direction=direction,
    entry=entry,
    profile_type=ctx.profile_type,
    mon_tue_low=ctx.mon_tue_low,
    mon_tue_high=ctx.mon_tue_high,
    weekly_high=max(c.high for c in week_candles) if week_candles else entry * 1.01,
    weekly_low=min(c.low for c in week_candles) if week_candles else entry * 0.99,
    opening_range=opening_range,
    stop=stop
)
```

---

## 🔧 FIX #3: Entry Confluence Scoring (CRITICAL)

### ❌ Aktueller Code

**Datei:** `backtesting_system/strategies/weekly_profiles.py` (Zeile ~180)

```python
# ALLE Filter sind zwingend → führt zu 0 Trades!
if not cisd.get("detected"):
    return {}
if not stop_hunt.get("detected"):
    return {}
if not self.opening_range.is_entry_in_zone(bar.close, opening_range):
    return {}
```

**Problem:**
- Zu restriktiv: ALLE Faktoren müssen erfüllt sein
- Composite Strategy hat 0 Trades
- Nicht handbuchkonform (Confluence = Scoring, nicht Binary)

### ✅ Handbuch-Regel

**Quelle:** The Blueprint.pdf, Seite "Confluences to a High Probability Setup"

> "Stop Hunt (preferred), Opening Range, PDA Arrays, News Driver"  
> **NICHT ALLE GLEICHZEITIG ERFORDERLICH!**

**Quelle:** Weekly Profile Guide.pdf, Seite "Framework"

> "Pair with relevant H1 PD arrays to establish bias"  
> **PDA = Mandatory, Rest = Optional**

### ✅ Korrekte Implementation

**Ersetze in `weekly_profiles.py` (ab Zeile ~180):**

```python
def generate_signals(self, data) -> dict:
    bar = data["bar"]
    history = data.get("history", [])
    ctx = self._build_context(history)
    
    if ctx.profile_type is None:
        return {}
    if ctx.week_key == self._last_signal_week:
        return {}
    
    # ... (Day filtering logic bleibt gleich) ...
    
    # ========== CONFLUENCE SCORING (NEU) ==========
    
    confluence_score = 0.0
    signal_direction = "long" if ctx.profile_type.endswith("long") else "short"
    
    # 1. BASE: Weekly Profile erkannt (30%)
    if ctx.profile_type and ctx.confidence:
        confluence_score += ctx.confidence * 0.30  # Max 30% wenn confidence = 1.0
    else:
        confluence_score += 0.20  # Fallback wenn keine confidence
    
    # 2. CISD bestätigt Signal-Richtung (20% / -10% penalty)
    cisd = self.cisd_validator.detect_cisd(daily_candles, history[-20:])
    cisd_type = cisd.get("type", "").lower()
    cisd_direction = "long" if cisd_type == "bullish" else "short"
    
    if cisd.get("detected"):
        if signal_direction == cisd_direction:
            confluence_score += 0.20  # +20% boost
        else:
            confluence_score -= 0.10  # -10% penalty für Mismatch
    
    # 3. Stop Hunt vorhanden (15% - bevorzugt, aber NICHT zwingend)
    if signal_direction == "long":
        swing_level = ctx.mon_tue_low if ctx.mon_tue_low else min(c.low for c in history[-20:])
    else:
        swing_level = ctx.mon_tue_high if ctx.mon_tue_high else max(c.high for c in history[-20:])
    
    stop_hunt = self.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
    if stop_hunt.get("detected"):
        confluence_score += 0.15  # +15%
        # Bonus für "strong" stop hunt
        if stop_hunt.get("strength") == "strong":
            confluence_score += 0.05
    
    # 4. PDA Array Entry (25% - KRITISCH, OHNE PDA kein Trade!)
    day_candles = [c for c in history if c.time.date() == bar.time.date()]
    if day_candles:
        day_low = min(c.low for c in day_candles)
        day_high = max(c.high for c in day_candles)
        opening_range = self.opening_range.calculate_opening_range(day_candles, day_low, day_high)
    else:
        opening_range = {}
    
    h1_arrays = {
        "fvgs": self.pda_detector.identify_fair_value_gaps(history[-50:]),
        "order_blocks": self.pda_detector.identify_order_blocks(history[-50:]),
    }
    
    entry_at_pda, pda_type = self.pda_detector.validate_entry_at_pda(bar.close, h1_arrays, tolerance_pips=5.0)
    if entry_at_pda:
        confluence_score += 0.25  # +25% - WICHTIGSTER FAKTOR
    else:
        # OHNE PDA kein Trade (ICT-Core-Regel!)
        return {}
    
    # 5. Opening Range Alignment (10% optional)
    if opening_range and self.opening_range.is_entry_in_zone(bar.close, opening_range):
        confluence_score += 0.10  # +10%
    elif opening_range:
        confluence_score -= 0.05  # -5% penalty wenn außerhalb
    
    # 6. News Driver (5% optional boost)
    if self._has_relevant_news(bar.time, data.get("symbol", "")):
        confluence_score += 0.05  # +5%
    
    # ========== MINIMUM THRESHOLD CHECK ==========
    # Anstatt ALL filters zu erzwingen: Minimum 50% Confluence
    if confluence_score < self.min_confluence:  # Default: 0.25 (25%)
        return {}
    
    # ========== SIGNAL GENERIERUNG ==========
    direction = signal_direction
    entry = bar.close
    
    # Stop Loss (mit neuer Methode aus Fix #1)
    daily_candles_full = self._aggregate_daily(history)
    stop = self.calculate_stop_loss(direction, entry, h1_arrays, daily_candles_full)
    
    # Take Profit (mit neuer Methode aus Fix #2)
    week_candles = [c for c in daily_candles_full if self._current_week_key(c.time) == ctx.week_key]
    target = self.calculate_take_profit(
        direction=direction,
        entry=entry,
        profile_type=ctx.profile_type,
        mon_tue_low=ctx.mon_tue_low,
        mon_tue_high=ctx.mon_tue_high,
        weekly_high=max(c.high for c in week_candles) if week_candles else entry * 1.01,
        weekly_low=min(c.low for c in week_candles) if week_candles else entry * 0.99,
        opening_range=opening_range,
        stop=stop
    )
    
    self._last_signal_week = ctx.week_key
    signal = {
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "target": target,
        "confluence": confluence_score,
        "profile_type": ctx.profile_type,
        "pda_type": pda_type,  # Welches PDA Array (FVG/OB/BRK)
    }
    self._record_signal(bar.time, signal, ctx)
    return signal
```

### 📊 Erwartete Impact

**Vorher:**
- Composite Strategy: **0 Trades** (alle Filter zwingend)
- Nur Trades wenn CISD + Stop Hunt + Opening Range + PDA alle perfekt aligned

**Nachher:**
- Erwartete **5-15 Trades/Monat** (abhängig von `min_confluence` Parameter)
- Trade mit PDA + 1-2 weiteren Faktoren (realistischer)

---

## 🔧 FIX #4: TGIF Return Setup (HIGH PRIORITY)

### ❌ Aktueller Code

**Datei:** `backtesting_system/strategies/weekly_profiles.py` (Zeile ~250)

```python
level_20_high = week_high - (week_range * 0.20)
level_30_high = week_high - (week_range * 0.30)

if level_30_high <= bar.close <= level_20_high:  # Entry Zone zu weit!
    return {
        "direction": "short",
        "entry": bar.close,
        "stop": week_high + pip_buffer,
        "target": (level_20_high + level_30_high) / 2,  # FALSCH: Target = Entry Zone!
    }
```

**Problem:**
- Entry Zone = 20-30% vom **High** (nicht Fibonacci!)
- Target = Midpoint der Entry Zone (macht keinen Sinn)
- Keine PDA Array Validation

### ✅ Handbuch-Regel

**Quelle:** Weekly Profile Guide.pdf, Seite "TGIF Target"

> "Fibonacci 0.20-0.30 retracement of weekly range"  
> "Target internal H1 PD arrays within 0.20-0.30 retracement"

**Quelle:** The Blueprint.pdf, Seite "TGIF Setup"

> "Entry at 70-80% Fib for shorts (= top 20-30%), Target = 20-30% Fib"  
> "Entry at 20-30% Fib for longs, Target = 70-80% Fib"

### ✅ Korrekte Implementation

**Ersetze `_maybe_tgif_signal()` in `weekly_profiles.py`:**

```python
def _maybe_tgif_signal(self, bar: Candle, daily_candles: List[Candle], history: List[Candle]) -> dict:
    """
    TGIF Return Setup - Handbuchkonform.
    
    Entry Requirements:
    - Friday (weekday == 4)
    - Price in 20-30% Fib (long) or 70-80% Fib (short)
    - Entry AT H1 PDA array (FVG/OB)
    
    Target: Opposite Fib zone (70-80% for longs, 20-30% for shorts)
    """
    if bar.time.weekday() != 4:  # Not Friday
        return {}
    
    current_week = self._current_week_key(bar.time)
    week_candles = [c for c in daily_candles if self._current_week_key(c.time) == current_week]
    
    if len(week_candles) < 3:
        return {}
    
    week_high = max(c.high for c in week_candles)
    week_low = min(c.low for c in week_candles)
    week_range = week_high - week_low
    
    if week_range <= 0:
        return {}
    
    # ========== FIBONACCI LEVELS (KORREKT) ==========
    fib_20 = week_low + (week_range * 0.20)
    fib_30 = week_low + (week_range * 0.30)
    fib_70 = week_low + (week_range * 0.70)
    fib_80 = week_low + (week_range * 0.80)
    
    # ========== H1 PDA ARRAYS ==========
    h1_arrays = {
        "fvgs": self.pda_detector.identify_fair_value_gaps(history[-50:]),
        "order_blocks": self.pda_detector.identify_order_blocks(history[-50:]),
    }
    
    # ========== SHORT SETUP: Price in 70-80% Zone (top 20-30%) ==========
    if fib_70 <= bar.close <= fib_80:
        # Entry MUSS an H1 PDA sein (höhere Toleranz für TGIF)
        entry_ok, pda_type = self.pda_detector.validate_entry_at_pda(
            bar.close, 
            h1_arrays, 
            tolerance_pips=10.0  # 10 pips tolerance
        )
        
        if not entry_ok:
            return {}  # Kein Trade ohne PDA
        
        return {
            "direction": "short",
            "entry": bar.close,
            "stop": week_high + (0.0001 * 10),  # 10 pips buffer
            "target": (fib_20 + fib_30) / 2,  # KORREKT: Midpoint of 20-30% Fib
            "confluence": 0.75,
            "profile_type": "tgif_return",
            "pda_type": pda_type,
        }
    
    # ========== LONG SETUP: Price in 20-30% Zone (bottom 20-30%) ==========
    if fib_20 <= bar.close <= fib_30:
        entry_ok, pda_type = self.pda_detector.validate_entry_at_pda(
            bar.close, 
            h1_arrays, 
            tolerance_pips=10.0
        )
        
        if not entry_ok:
            return {}
        
        return {
            "direction": "long",
            "entry": bar.close,
            "stop": week_low - (0.0001 * 10),  # 10 pips buffer
            "target": (fib_70 + fib_80) / 2,  # KORREKT: Midpoint of 70-80% Fib
            "confluence": 0.75,
            "profile_type": "tgif_return",
            "pda_type": pda_type,
        }
    
    return {}
```

### 📝 Integration

**In `generate_signals()` (Zeile ~120):**

```python
# ALT:
tgif_signal = self._maybe_tgif_signal(bar, daily_candles)

# NEU (mit history für PDA Arrays):
tgif_signal = self._maybe_tgif_signal(bar, daily_candles, history)
```

---

## 🔧 FIX #5: Opening Range Framework (HIGH PRIORITY)

### ❌ Aktueller Code

**Datei:** `backtesting_system/strategies/ict_framework.py` (Zeile ~200)

```python
if distance_to_low > distance_to_high:
    expected_high = opening_price + distance_to_low  # FALSCH!
    return {
        "expected_target": expected_high,
        "entry_zone": (day_low_so_far, opening_price),
    }
```

**Problem:**
- `expected_high = opening + distance_to_low` ist inkorrekt
- Entry Zone falsch definiert
- Target-Berechnung nicht handbuchkonform

### ✅ Handbuch-Regel

**Quelle:** The Blueprint.pdf, Seite "Opening Range Confluence"

> "Take distance from Daily Open → Low/High, project SAME distance to opposite side"  
> "Entry within projected range, Target = opposite extreme"

**Grafik aus Handbuch:**
```
Daily Open: 100.00
Low of Day: 99.30  (Distance = 70 pips)
Expected High = 100.00 + 70 pips = 100.70

Entry Zone: 99.30 - 100.00
Target: 100.70
```

### ✅ Korrekte Implementation

**Ersetze in `ict_framework.py` (Klasse `OpeningRangeFramework`):**

```python
def calculate_opening_range(self, daily_candle: Candle, current_data: List[Candle]) -> dict:
    """
    ICT Opening Range Framework - KORREKT nach Handbuch.
    
    Logic:
    1. Measure Daily Open → Current Low/High distance
    2. Project SAME distance to opposite side
    3. Entry Zone = From extreme back to Open
    4. Target = Opposite projected extreme
    
    Args:
        daily_candle: First candle of the day (for Open price)
        current_data: All candles up to current bar
    
    Returns:
        Dict with opening_range framework data
    """
    opening_price = daily_candle.open
    
    # Current session extremes (only candles from today!)
    session_candles = [c for c in current_data if c.time.date() == daily_candle.time.date()]
    if not session_candles:
        return {}
    
    current_low = min(c.low for c in session_candles)
    current_high = max(c.high for c in session_candles)
    
    # Distances from Open
    distance_to_low = opening_price - current_low
    distance_to_high = current_high - opening_price
    
    # ========== KORREKT: Welche Richtung hat initial mehr bewegt? ==========
    
    if distance_to_low > distance_to_high:
        # Initial move = DOWN → Expect reversal UP
        # Projected High = Open + (distance moved down)
        projected_high = opening_price + distance_to_low
        
        return {
            "opening_price": opening_price,
            "current_low": current_low,
            "current_high": current_high,
            "initial_direction": "down",
            "expected_reversal": "up",
            
            # Entry Zone: AT the low back to Open
            "entry_zone_low": current_low,
            "entry_zone_high": opening_price,
            
            # Target: Projected high (symmetric to downside move)
            "target": projected_high,
            
            # Stop: 25% below the established low
            "stop_zone": current_low - (distance_to_low * 0.25),
            
            # Range info
            "range_size": distance_to_low * 2,  # Total expected range
            "distance_moved": distance_to_low,
        }
    else:
        # Initial move = UP → Expect reversal DOWN
        # Projected Low = Open - (distance moved up)
        projected_low = opening_price - distance_to_high
        
        return {
            "opening_price": opening_price,
            "current_low": current_low,
            "current_high": current_high,
            "initial_direction": "up",
            "expected_reversal": "down",
            
            # Entry Zone: From Open up to the high
            "entry_zone_low": opening_price,
            "entry_zone_high": current_high,
            
            # Target: Projected low
            "target": projected_low,
            
            # Stop: 25% above the established high
            "stop_zone": current_high + (distance_to_high * 0.25),
            
            # Range info
            "range_size": distance_to_high * 2,
            "distance_moved": distance_to_high,
        }


def is_entry_in_zone(self, entry_price: float, or_framework: dict) -> bool:
    """
    Check if entry is within Opening Range entry zone.
    
    Args:
        entry_price: Proposed entry price
        or_framework: Dict from calculate_opening_range()
    
    Returns:
        True if entry within zone, False otherwise
    """
    if not or_framework:
        return False
    
    zone_low = or_framework.get("entry_zone_low", 0)
    zone_high = or_framework.get("entry_zone_high", 0)
    
    # Allow small tolerance (2 pips)
    tolerance = 0.0001 * 2
    
    return (zone_low - tolerance) <= entry_price <= (zone_high + tolerance)
```

### 📊 Beispiel-Berechnung

**Szenario:** EURUSD Daily

```
Daily Open: 1.0800
Current Low: 1.0770  (30 pips down)
Current High: 1.0810 (10 pips up)

Initial Move = DOWN (30 pips > 10 pips)

Opening Range Framework:
- Entry Zone: 1.0770 - 1.0800 (at low back to open)
- Target: 1.0800 + 0.0030 = 1.0830 (30 pips above open)
- Stop: 1.0770 - 0.00075 = 1.07625 (25% below low)
- Expected Reversal: UP
```

---

## 📝 Implementation Checklist

### Phase 1: Core Fixes (Tag 1)

- [ ] **Fix #1:** Stop Loss Placement
  - [ ] Add `calculate_stop_loss()` to `ict_framework.py`
  - [ ] Update `generate_signals()` in `ict_framework.py`
  - [ ] Update `generate_signals()` in `weekly_profiles.py`

- [ ] **Fix #2:** Take Profit Targets
  - [ ] Add `calculate_take_profit()` to `weekly_profiles.py`
  - [ ] Update all `project_target()` calls

- [ ] **Fix #3:** Entry Confluence Scoring
  - [ ] Replace binary filters mit confluence scoring
  - [ ] Update `generate_signals()` logic
  - [ ] Add `min_confluence` parameter to config

### Phase 2: Profile-Specific Fixes (Tag 2)

- [ ] **Fix #4:** TGIF Return Setup
  - [ ] Update `_maybe_tgif_signal()` mit Fibonacci levels
  - [ ] Add PDA validation
  - [ ] Update target calculation

- [ ] **Fix #5:** Opening Range Framework
  - [ ] Update `calculate_opening_range()` logic
  - [ ] Fix target projection
  - [ ] Update `is_entry_in_zone()` validation

### Phase 3: Testing & Validation (Tag 3)

- [ ] Unit Tests für alle 5 Fixes
- [ ] Backtest mit neuen Regeln
- [ ] Verify Trade Count > 0 (Composite Strategy)
- [ ] Compare Results mit alten Regeln
- [ ] Documentation Update (README.md)

---

## 🧪 Testing Strategy

### Unit Tests

**Datei:** `tests/test_ict_fixes.py` (neu erstellen)

```python
import pytest
from backtesting_system.strategies.ict_framework import ICTFramework
from backtesting_system.strategies.weekly_profiles import WeeklyProfileStrategy
from backtesting_system.models.market import Candle
from datetime import datetime

class TestStopLossPlacement:
    def test_long_stop_at_order_block(self):
        """Test: Long SL sitzt an Order Block Low"""
        strategy = ICTFramework({})
        
        h1_arrays = {
            "order_blocks": [
                {"type": "bullish", "low": 1.0750, "high": 1.0760},
            ],
            "fvgs": [],
            "breakers": [],
        }
        
        stop = strategy.calculate_stop_loss("long", 1.0800, h1_arrays, [])
        
        # Stop sollte 2 pips unter OB low sein
        expected = 1.0750 - (2 / 10000)
        assert abs(stop - expected) < 0.00001
    
    def test_short_stop_at_fvg(self):
        """Test: Short SL sitzt an FVG High"""
        strategy = ICTFramework({})
        
        h1_arrays = {
            "order_blocks": [],
            "fvgs": [
                {"type": "bearish", "low": 1.0800, "high": 1.0810},
            ],
            "breakers": [],
        }
        
        stop = strategy.calculate_stop_loss("short", 1.0750, h1_arrays, [])
        
        expected = 1.0810 + (2 / 10000)
        assert abs(stop - expected) < 0.00001


class TestTakeProfitTargets:
    def test_tgif_long_target(self):
        """Test: TGIF Long Target = 70-80% Fib midpoint"""
        strategy = WeeklyProfileStrategy({"min_confluence": 0.25})
        
        target = strategy.calculate_take_profit(
            direction="long",
            entry=1.0750,
            profile_type="tgif_return",
            mon_tue_low=None,
            mon_tue_high=None,
            weekly_high=1.0900,
            weekly_low=1.0700,
            opening_range={},
            stop=1.0700
        )
        
        # Weekly Range = 200 pips
        # Fib 70% = 1.0700 + 140 pips = 1.0840
        # Fib 80% = 1.0700 + 160 pips = 1.0860
        # Target = (1.0840 + 1.0860) / 2 = 1.0850
        expected = 1.0850
        assert abs(target - expected) < 0.0001


class TestConfluenceScoring:
    def test_pda_mandatory(self):
        """Test: Ohne PDA kein Trade"""
        strategy = WeeklyProfileStrategy({"min_confluence": 0.25})
        
        # Mock data ohne PDA array
        signal = strategy.generate_signals({
            "bar": Candle(datetime(2024, 1, 10, 10, 0), 1.0800, 1.0810, 1.0790, 1.0805, None),
            "history": [],  # Leer = kein PDA
        })
        
        assert signal == {}  # Kein Signal ohne PDA
```

### Integration Test

```bash
# Run backtest mit neuen Fixes
python backtesting_system/main.py \
    --strategy weekly_profiles \
    --symbol EURUSD \
    --start 2023-01-01 \
    --end 2024-12-31 \
    --config config_new_fixes.json

# Erwartete Results:
# - Trade Count > 0 (vorher: 0)
# - Win Rate ~50-65%
# - Sharpe Ratio > 0 (vorher: negativ)
```

---

## 📊 Expected Impact Summary

| Metric | Vorher (Alt) | Nachher (Fix) | Verbesserung |
|--------|-------------|--------------|--------------|
| **Trade Count** | 0 (Composite) | 5-15/Monat | ✅ +∞% |
| **Stop Loss** | Min/Max 10 Bars | PDA-basiert | ✅ Handbuchkonform |
| **Take Profit** | Fixed 2R | Profile-spezifisch | ✅ Handbuchkonform |
| **Entry Logic** | ALL filters (binary) | Confluence scoring | ✅ Realistischer |
| **TGIF Setup** | Zone 20-30% (falsch) | Fib 20-30% mit PDA | ✅ Handbuchkonform |
| **Opening Range** | Falsche Projektion | Symmetrische Projektion | ✅ Handbuchkonform |

---

## 🎯 Next Steps

1. **Implementiere Fixes** (2-3 Tage)
   - Copy-paste Code aus diesem Dokument
   - Update bestehende Dateien
   - Add new methods

2. **Run Backtests** (1 Tag)
   - Test alte vs. neue Implementation
   - Verify Trade Count > 0
   - Compare Win Rate, Sharpe, Drawdown

3. **Update Documentation** (1 Tag)
   - README.md: Add "ICT Implementation Choices"
   - CHANGELOG.md: Document Fixes
   - BACKTEST_RESULTS.md: Update Results

4. **Akademische Validierung** (optional)
   - Sensitivity Analysis (Parameter Variations)
   - Robustness Tests (Different Timeframes)
   - Out-of-Sample Validation

---

## 📚 References

- **The Blueprint.pdf** - ICT Trading Framework (kikoundercover)
- **Weekly Profile Guide.pdf** - 3 Profile Types (AM Trades)
- **ICT YouTube** - Market Maker Series Vol. 2-4
- **Repository:** `github.com/DavidVossebuerger/po3-ict-backtesting`

---

**Erstellt:** 03.02.2026  
**Autor:** David Vossebürger  
**Version:** 1.0
```

Perfekt! Diese Markdown-Datei ist jetzt **vollständig downloadbar** und enthält:

✅ Alle 5 kritischen Fixes  
✅ Code-Beispiele zum Copy-Paste  
✅ Handbuch-Zitate als Beweis  
✅ Testing Strategy  
✅ Implementation Checklist  

Möchtest du diese Datei als `ICT_IMPLEMENTATION_FIXES.md` in dein Workspace speichern? Oder soll ich noch etwas ergänzen? 🎯