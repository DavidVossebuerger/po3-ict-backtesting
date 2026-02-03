# Fixes für akademische Robustheit

Dieses Dokument listet alle verbleibenden Punkte, die ich **vor Abgabe einer akademischen Arbeit** entweder
(a) im Code/Setup verbessere oder  
(b) explizit als Limitationen dokumentiere.

---

## 1. Statistische Robustheit

### 1.1 Weekly Profile: zu wenige Trades

- Aktuell: 18 Trades über den gesamten Zeitraum, Win-Rate 55.6 %, Profit Factor 0.94, p‑Value ≈ 0.41 → statistisch nicht von Zufall unterscheidbar.[^wp_stats]  
- Ziel: **mindestens 100–200 Trades** für Weekly Profile, damit die Aussagen akademisch belastbar sind.  

**To‑Dos:**

- CISD und Stop Hunt **von harten Filtern in Confluence‑Bias umwandeln**:
  - Statt `if not cisd.get("detected"): return {}` → bei detected nur Confluence erhöhen.
  - Statt `if not stop_hunt.get("detected"): return {}` → Stop‑Hunt als Bonus, nicht als Pflichtbedingung.  
- `MIN_CONFLUENCE` für Weekly Profile von aktuell 0.40 auf ca. **0.20–0.30** senken (siehe unten bei Logic).  
- Ziel‑Tradefrequenz: ungefähr **3–10 Trades pro Jahr** (nicht 0.8/Jahr).

### 1.2 ICT Framework: Edge zu dünn

- Aktuell: 512 Trades, Win‑Rate 63.5 %, Profit Factor 1.016, Sharpe < 0, t‑Test vs. Buy&Hold nicht signifikant besser.[^ict_stats]  
- Statistische Signifikanz der Win‑Rate ist gegeben, aber ökonomische Edge ist sehr dünn.

**To‑Dos:**

- Exit-/Risk‑Regeln so anpassen, dass das **Risikoverhältnis (Avg Win / Avg Loss)** steigt:
  - Engere Stops oder leicht größere Targets testen.
  - Teilgewinnmitnahmen so kalibrieren, dass PF Richtung **≥ 1.3** geht.
- In der Arbeit explizit schreiben: „Die Win‑Rate ist signifikant > 50 %, aber der ökonomische Nutzen nach Kosten ist fraglich.“

### 1.3 Out‑of‑Sample/Robustheit

- Walk‑Forward‑Korrelation zwischen In‑Sample‑ und Out‑of‑Sample‑Sharpe ist ≈ 0.07 (p≈0.53) → **keine Evidenz für Robustheit**.[^wf_stats]  

**To‑Dos:**

- Eine **echte Out‑of‑Sample‑Periode** definieren, z.B.:
  - Kalibrierung: 2003–2018
  - OOS‑Test: 2019–2025, **ohne** Parameter‑Nachjustierung.
- In der Thesis klar kennzeichnen: In‑Sample vs. Out‑of‑Sample Abschnitt und die Ergebnisse getrennt diskutieren.

---

## 2. Strategy Logic & Code‑Fixes

### 2.1 WeeklyProfileStrategy: Filter weicher machen

Aktueller Stand (vereinfacht):

```python
cisd = self.cisd_validator.detect_cisd(...)
if not cisd.get("detected"):
    return {}

if signal_direction != cisd_direction:
    return {}

stop_hunt = self.stop_hunt_detector.detect_stop_hunt(...)
if not stop_hunt.get("detected"):
    return {}

confluence_score = ctx.confidence if ctx.confidence else 0.5
if opening_range and self.opening_range.is_entry_in_zone(...):
    confluence_score += 0.15
elif opening_range:
    confluence_score -= 0.10

if confluence_score < 0.40:
    return {}
```

**Fix‑Plan:**

1. **CISD als Bias statt Muss‑Bedingung:**

```python
cisd = self.cisd_validator.detect_cisd(daily_candles, history[-20:])
cisd_type = cisd.get("type", "").lower()

confluence_score = ctx.confidence if ctx.confidence else 0.5

if cisd.get("detected"):
    # Richtung passend?
    cisd_dir = "long" if cisd_type == "bullish" else "short"
    signal_dir = "long" if ctx.profile_type.endswith("long") else "short"
    if signal_dir == cisd_dir:
        confluence_score += 0.15
    else:
        confluence_score -= 0.10
```

2. **Stop Hunt als optionaler Bonus:**

```python
stop_hunt = self.stop_hunt_detector.detect_stop_hunt(history[-20:], swing_level)
if stop_hunt.get("detected"):
    confluence_score += 0.10
```

3. **Opening Range weiterhin nur als Bias, aber Schwelle senken:**

```python
if opening_range and self.opening_range.is_entry_in_zone(bar.close, opening_range):
    confluence_score += 0.10
elif opening_range:
    confluence_score -= 0.05

MIN_CONFLUENCE = self.params.get("min_confluence", 0.25)  # statt hart 0.40
if confluence_score < MIN_CONFLUENCE:
    return {}
```

Erwartung: Mehr Trades, aber weiterhin qualitativ selektiv.

### 2.2 Confluence‑Parameter konfigurierbar machen

- Aktuell: Confluence‑Gewichte und `MIN_CONFLUENCE` sind hardcoded in `weekly_profiles.py`.  
- Fix:
  - In `__init__` von `WeeklyProfileStrategy` Parameter übernehmen:
    ```python
    self.min_confluence = params.get("min_confluence", 0.25)
    self.cisd_weight = params.get("cisd_weight", 0.15)
    self.stop_hunt_weight = params.get("stop_hunt_weight", 0.10)
    self.opening_range_weight = params.get("opening_range_weight", 0.10)
    ```
  - Diese Werte statt fester Literale in `generate_signals` verwenden.  

Vorteil: In der Arbeit kannst du sauber zeigen, wie Sensitivität auf diese Parameter getestet wurde.

### 2.3 Dead Code entfernen

- `_is_day_open(self, dt: datetime) -> bool` ist definiert, wird aber nicht verwendet.[^wp_code]  
- Fix:
  - Methode aus `weekly_profiles.py` löschen.
  - In der Thesis kurz erwähnen, dass der Code von Legacy‑Checks bereinigt wurde.

### 2.4 Price Action & Composite Strategy

- Price Action: 80k Trades, vollständige Kontovernichtung → für die Arbeit eher als **negatives Beispiel**/Ablage in Anhang verwenden.[^summary_stats]  
- Composite: 0 Trades, Confluence‑Threshold offenbar zu hoch.[^summary_stats]  

**To‑Dos:**

- Entweder:
  - Composite für die aktuelle Thesis deaktivieren, **oder**
  - Min‑Confluence‑Level deutlich senken und neu testen.
- Price‑Action‑Strategie in der Arbeit als „Baseline‑Experiment, das Overtrading demonstriert“ beschreiben, aber nicht als ernsthaften Kandidaten.

---

## 3. Dokumentation & Präsentation

### 3.1 README / Methodik‑Kapitel

Es fehlt noch eine zentrale **Methodologie‑Beschreibung** im Repo.

**To‑Dos:**

- `README.md` (oder Kapitel "Methodik" in der Arbeit) mit:
  - Ziel der Arbeit und Forschungsfragen.
  - Beschreibung der Strategien (Weekly Profile, ICT, Price Action, Composite).
  - Datensatz (EURUSD H1, Zeitraum, Quelle, Validierungsergebnisse).[^validation]
  - Pipeline: Daten → Backtest → Analytics (Monte Carlo, Walk‑Forward, Stats‑Tests).
  - Klaren Hinweis auf Limitierungen (wenige Trades, dünne Edge, kein echtes OOS).

### 3.2 Statistische Tests dokumentieren

Du hast bereits:
- Binomial‑Tests, t‑Tests, Monte‑Carlo, Walk‑Forward‑Korrelationen etc.[^stat_tests]  

**To‑Dos:**

- Eigenes Unterkapitel „Statistische Validierung“ mit:
  - Tabelle: Strategie, Trades, Win‑Rate, p‑Value (Binomial), PF, Max DD.
  - Kurztext pro Strategie, z.B.:  
    - „Weekly Profile: p=0.41, daher keine statistisch signifikante Abweichung von 50 %.“  
    - „ICT: Win‑Rate signifikant, aber PF≈1.02, ökonomisch fraglich.“  
  - Erklärung, warum Walk‑Forward‑Korrelation ≈ 0.07 auf mangelnde Generalisierbarkeit hindeutet.

### 3.3 Negative Ergebnisse bewusst nutzen

- Wichtig für akademische Arbeiten:
  - Klar schreiben, dass die Experimente **keinen robust profitablen Edge** gefunden haben.
  - Fokus auf: „Was sagen diese Ergebnisse über ICT/Weekly‑Profile‑Konzepte aus?“ statt „Wie baue ich ein Live‑System?“.

---

## 4. Wie ich das in der Arbeit formuliere

Wenn nicht genug Zeit für alle Code‑Fixes bleibt:

- Weekly Profile:  
  - „Nach Integration zusätzlicher Filter (CISD, Stop‑Hunt, Opening Range) bricht die Tradefrequenz auf 18 Trades ein; die statistische Power reicht nicht aus, um eine Aussage zu treffen.“  
- ICT Framework:  
  - „Signifikante Trefferquote, aber ökonomisch schwache Performance und aus akademischer Sicht keine ausreichende Robustheit über Walk‑Forward/OOS.“  
- Gesamtfazit:  
  - „Die Arbeit zeigt, dass die untersuchten ICT/Weekly‑Profile‑Konzepte auf EURUSD‑H1 unter strengen Tests keine robuste, akademisch überzeugende Überrendite liefern.“

---

[^wp_stats]: Kennzahlen aus `report_weekly_profile.json` und `summary.csv` (Trades=18, Win‑Rate≈55.6 %, PF≈0.94, p‑Value≈0.41).  
[^ict_stats]: Kennzahlen aus `report_ict_framework.json` und `summary.csv` (Trades=512, Win‑Rate≈63.5 %, PF≈1.016, Sharpe<0).  
[^wf_stats]: Walk‑Forward‑Auswertung (`walk_forward.json`), Korrelation In‑Sample/Out‑of‑Sample‑Sharpe ≈0.07, p≈0.53.  
[^wp_code]: Implementierung in `backtesting_system/strategies/weekly_profiles.py`.  
[^summary_stats]: Gesamtübersicht `summary.csv` für Price Action und Composite.  
[^validation]: Datenvalidierung aus `validation_summary.json` (100 % Completeness, Quality‑Score≈0.95).  
[^stat_tests]: Auswertung `statistical_tests.json` (t‑Tests, Binomial, ANOVA, Walk‑Forward‑Korrelation).
