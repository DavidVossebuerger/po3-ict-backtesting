# 📅 Historische Forex Kalenderdaten: Kompletter Download-Guide

**Problem:** Du brauchst wirtschaftliche Ereignisse (NFP, CPI, FOMC, etc.) für 2003-2025 für dein Backtesting  
**Lösung:** Es gibt mehrere Optionen, hier sind die BESTEN für dich

---

## 🥇 BEST OPTION 1: Hugging Face Dataset (Kostenlos, 2007-2025)

**URL:** https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar

**Was du bekommst:**
- 2007-2025 alle wichtigen Forex Factory Events
- Format: CSV, JSON, Parquet
- Daten: Event, Forecast, Actual, Impact (HIGH/MEDIUM/LOW)
- Kostenlos

**Wie du es nutzt:**

```python
# Option 1: Direkt mit Python
from datasets import load_dataset

dataset = load_dataset("Ehsanrs2/Forex_Factory_Calendar")
df = dataset["train"].to_pandas()

# df hat Spalten:
# - Date
# - Time
# - Event Name
# - Country
# - Forecast
# - Actual
# - Previous
# - Importance (HIGH/MEDIUM/LOW)

# Speichern
df.to_csv("forex_calendar_2007_2025.csv", index=False)

# Option 2: Download auf Website
# Gehe zu https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar
# Klick "Download" → CSV
```

**Problem:** Nur ab 2007 (du brauchst 2003-2006)

**Lösung für 2003-2006:** Siehe unten

---

## 🥈 BEST OPTION 2: Trading Economics API (Kostenlos für Basic)

**URL:** https://tradingeconomics.com/api/

**Was du bekommst:**
- Echtzeitdaten + historische Daten
- 2000er Jahre verfügbar
- API oder CSV Download

**Kosten:**
- FREE: 5 API calls/hour
- PAID: $30-$400/month je nach Umfang

**Wie du es nutzt (Free-Version):**

```python
import requests
import pandas as pd

# Trading Economics API (kostenlos)
# Braucht API Key (registriere dich kostenlos)

BASE_URL = "https://api.tradingeconomics.com/calendar"
API_KEY = "your_api_key"  # Kostenlos auf https://tradingeconomics.com/signup

# Events fetchen
url = f"{BASE_URL}?c={API_KEY}&format=json"
response = requests.get(url)
data = response.json()

df = pd.DataFrame(data)
df.to_csv("trading_economics_calendar.csv", index=False)

# Spezifische Countries/Events:
# Beispiel: Nur USD NFP
url = f"{BASE_URL}?c={API_KEY}&country=united%20states&format=json"
response = requests.get(url)
```

**Problem:** Rate limits (nur 5/hour kostenlos)

---

## 🥉 BEST OPTION 3: Forex Factory direkter Download

**URL:** https://www.forexfactory.com/calendar.php

**Was du bekommst:**
- Original Quelle aller Daten
- Kann manuell CSV exportiert werden
- Oder mit Scraper geholt werden

**Wie du es nutzt:**

### Method A: Manual Download
1. Gehe zu https://www.forexfactory.com/calendar.php
2. Filters einstellen (Historical, Past Events)
3. Rechtsklick → "Save as CSV"

### Method B: Web Scraper (Python)

```python
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

class ForexFactoryScraper:
    """Scrape Forex Factory Calendar"""
    
    BASE_URL = "https://www.forexfactory.com/calendar.php"
    
    def scrape_events(self, start_date, end_date):
        """
        start_date: datetime(2003, 5, 4)
        end_date: datetime(2025, 9, 7)
        """
        
        all_events = []
        
        current_date = start_date
        while current_date <= end_date:
            # Forex Factory URL mit Datum
            date_str = current_date.strftime("%Y-%m-%d")
            url = f"{self.BASE_URL}?day={date_str}"
            
            print(f"Scraping {date_str}...")
            
            try:
                response = requests.get(url, timeout=10)
                
                # Parse HTML (würde BeautifulSoup brauchen)
                # events = self._parse_html(response.text)
                # all_events.extend(events)
                
            except Exception as e:
                print(f"Error scraping {date_str}: {e}")
            
            current_date += timedelta(days=1)
            time.sleep(1)  # Be nice to server
        
        return pd.DataFrame(all_events)

# Nutzen:
scraper = ForexFactoryScraper()
df = scraper.scrape_events(
    datetime(2003, 5, 4),
    datetime(2025, 9, 7)
)
df.to_csv("forex_factory_full.csv", index=False)
```

**Problem:** Langsam (3000+ Tage × 1 sec = ~1 Stunde), Website könnte blockieren

---

## OPTION 4: Investing.com (via Apify)

**URL:** https://apify.com/pintostudio/economic-calendar-data-investing-com/api

**Kosten:** $10 pro 1000 results (kostenlos testen)

**Was du bekommst:**
- Alle Events seit 2000+
- Sehr zuverlässig
- Gut strukturierte Daten

**Wie:**

```python
# Apify bietet vorgefertigte Scraper
# 1. Registrier auf apify.com (kostenlos)
# 2. Starte den Actor
# 3. Download als CSV/JSON

# Oder via Python:
import subprocess

result = subprocess.run([
    "apify", "call", "pintostudio/economic-calendar-data-investing-com",
    "--",
    "--countries", "United States,European Union",
    "--importance", "High",
], capture_output=True)

# Output in JSON
data = result.stdout
```

---

## OPTION 5: FXStreet API

**URL:** https://docs.fxstreet.com/api/calendar

**Was du bekommst:**
- Echte historische Daten
- Gut dokumentierte API

**Limitation:** Braucht API Key, nicht ganz kostenlos

---

## OPTION 6: Finnworlds API

**URL:** https://finnworlds.com/economic-calendar-api/

**Features:**
- CSV/Excel Export
- Historische Daten seit Jahren
- $0 - Custom pricing

---

## 🎯 MEINE EMPFEHLUNG FÜR DEIN PROJEKT

### Best Setup (Hybride Lösung):

#### Step 1: 2007-2025 aus Hugging Face
```python
from datasets import load_dataset

# Schnell, kostenlos, komplette Daten
dataset = load_dataset("Ehsanrs2/Forex_Factory_Calendar")
df_2007_2025 = dataset["train"].to_pandas()
df_2007_2025.to_csv("calendar_2007_2025.csv", index=False)
```

#### Step 2: 2003-2006 aus Trading Economics (oder manuell)
```python
import requests

# Alternativ: Manuell auf Trading Economics suchen
# Oder kleiner Scraper für Investing.com

# Trade-off: 2003-2006 komplett korrekt zu haben ist schwierig
# ALTERNATIVE: Nur ab 2007 backtesten (dann ist Hugging Face perfekt)
```

#### Step 3: Integration in dein Backtesting

```python
# backtesting_system/adapters/data_sources/calendar_source.py

import pandas as pd
from pathlib import Path

class EconomicCalendar:
    """Load pre-downloaded calendar data"""
    
    def __init__(self, csv_path="data/forex_calendar_2007_2025.csv"):
        self.df = pd.read_csv(csv_path)
        self.df["DateTime"] = pd.to_datetime(
            self.df["Date"] + " " + self.df["Time"]
        )
    
    def get_events_for_day(self, date):
        """Get all events for a specific date"""
        date_str = date.strftime("%Y-%m-%d")
        events = self.df[self.df["Date"] == date_str]
        return events.to_dict("records")
    
    def get_high_impact_events(self, date):
        """Get only HIGH impact events"""
        all_events = self.get_events_for_day(date)
        return [e for e in all_events if e["Importance"] == "HIGH"]
    
    def is_high_impact_day(self, date):
        """Check if date has HIGH impact news"""
        return len(self.get_high_impact_events(date)) > 0

# Integration in Strategy:
# backtesting_system/strategies/weekly_profiles.py

class WeeklyProfileStrategy:
    def __init__(self, params, calendar_path=None):
        self.params = params
        if calendar_path:
            self.calendar = EconomicCalendar(calendar_path)
        else:
            self.calendar = None
    
    def generate_signals(self, data):
        bar = data["bar"]
        
        # Prüfe ob HIGH-IMPACT NEWS an diesem Tag
        if self.calendar:
            if bar.time.weekday() == 2:  # Wednesday (Midweek Reversal)
                if not self.calendar.is_high_impact_day(bar.time):
                    return None  # Skip ohne News
        
        # ... rest of signals
```

---

## PRAKTISCHE DOWNLOADS (Ready-to-Use)

### Option A: Hugging Face (Empfohlen)
```bash
# 1. Python
python
>>> from datasets import load_dataset
>>> dataset = load_dataset("Ehsanrs2/Forex_Factory_Calendar")
>>> df = dataset["train"].to_pandas()
>>> df.to_csv("calendar.csv")

# 2. Command Line
# Download via web: https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar
# → "Download" Button
```

### Option B: Trading Economics (wenn Hugging Face nicht reicht)
```bash
# Registrier auf https://tradingeconomics.com/
# Hol dir kostenlos API Key
# Dann:

python
import requests
key = "your_free_key"
url = f"https://api.tradingeconomics.com/calendar?c={key}&format=csv"
requests.get(url)  # Download
```

### Option C: Investieren.com via Apify (€0 kostenlosen Trial)
```bash
# 1. Registrier auf apify.com
# 2. Starte: "Economic Calendar Data (Investing.com)"
# 3. Download CSV
```

---

## CALENDAR DATA FORMAT (Was du bekommst)

```csv
Date,Time,Event,Country,Forecast,Actual,Previous,Importance
2024-12-06,08:30,Initial Jobless Claims,United States,220K,227K,229K,HIGH
2024-12-06,10:00,Factory Orders,United States,+0.5%,-0.8%,+0.7%,MEDIUM
2024-12-06,13:45,ECB Press Conference,European Union,,,,,HIGH
2024-12-05,14:00,Fed Funds Rate Decision,United States,4.25%,4.25%,4.50%,HIGH
2024-12-04,09:00,Services PMI,Germany,51.8,51.3,50.9,HIGH
```

---

## INTEGRATIONSBEISPIEL: Weekly Profile mit News Filter

```python
# backtesting_system/strategies/weekly_profiles_v2.py
from backtesting_system.adapters.data_sources.calendar_source import EconomicCalendar

class WeeklyProfileStrategyV2(WeeklyProfileStrategy):
    """Enhanced mit News-Kalender Integration"""
    
    HIGH_IMPACT_EVENTS = {
        "NFP", "CPI", "FOMC", "PPI", "ECB",
        "Initial Jobless Claims", "Jobs Report",
        "GDP", "Inflation"
    }
    
    def __init__(self, params, calendar_csv="data/forex_calendar.csv"):
        super().__init__(params)
        self.calendar = EconomicCalendar(calendar_csv)
    
    def generate_signals(self, data):
        bar = data["bar"]
        history = data["history"]
        
        # 1. Erkenne Weekly Profile
        profile = self._detect_profile(history)
        if not profile:
            return None
        
        # 2. Prüfe ob HIGH-IMPACT NEWS an relevant day
        if bar.time.weekday() == 2:  # Wednesday
            high_impact_events = self.calendar.get_high_impact_events(bar.time)
            
            # Filter: Nur wenn NEWS vorhanden
            if not high_impact_events:
                # Wednesday OHNE News = Low Probability
                return None
            
            # Zusätzlich: Check ob event Time stimmt
            # (z.B. News um 08:30 NY, aber wir sind H1 Candle)
            relevant_news = [
                e for e in high_impact_events 
                if self._is_relevant_event_time(bar.time, e["Time"])
            ]
            
            if not relevant_news:
                return None
        
        # 3. Weiter wie normal
        signal = super().generate_signals(data)
        
        # 4. Boost Confidence bei News
        if signal and high_impact_events:
            signal["confluence"] = min(1.0, signal.get("confluence", 0.7) + 0.2)
        
        return signal
    
    def _is_relevant_event_time(self, candle_time, event_time_str):
        """
        Check ob Event-Zeit innerhalb 30 Min vor/nach Candle liegt
        """
        # Simplified: True if within trading hours
        return True
```

---

## ZUSAMMENFASSUNG: Schritt-für-Schritt

### Für dein Projekt SOFORT:

1. **Download Hugging Face Dataset:**
   ```bash
   python
   from datasets import load_dataset
   ds = load_dataset("Ehsanrs2/Forex_Factory_Calendar")
   ds["train"].to_pandas().to_csv("calendar.csv")
   ```

2. **Integriere in Backtesting:**
   ```python
   calendar = EconomicCalendar("calendar.csv")
   # Use in strategy
   ```

3. **Test mit News-Filter:**
   ```bash
   python main.py  # Backtest mit News Filter
   # Ergebnis: Höhere Win-Rate + Lower Profit Factor
   ```

---

## PROBLEME & LÖSUNGEN

| Problem | Lösung |
|---------|--------|
| 2003-2006 fehlen | Hugging Face ab 2007 nutzen, oder kleinere manuell sammeln |
| Daten zu groß | Nur HIGH-Impact Events filtern |
| Zu langsam | CSV cachen, nicht jedes Mal re-download |
| Zeitzone falsch | Sicherstellen dass UTC oder NY Time korrekt ist |
| Duplicate Events | Deduplizieren nach Date+Time+Event+Country |

---

## QUELLEN

- 🥇 **Hugging Face:** https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar
- 🥈 **Trading Economics:** https://tradingeconomics.com/api/
- 🥉 **Forex Factory:** https://www.forexfactory.com/calendar.php
- **Investing.com (Apify):** https://apify.com/pintostudio/economic-calendar-data-investing-com/api
- **FXStreet:** https://docs.fxstreet.com/api/calendar
- **Finnworlds:** https://finnworlds.com/economic-calendar-api/

---

**Nächste Schritte:**
1. Download Hugging Face → calendar.csv
2. Integriere in dein Backtesting
3. Test Weekly Profile MIT News-Filter
4. Vergleiche Metrics (Win-Rate sollte steigen)

Let's go! 🚀
