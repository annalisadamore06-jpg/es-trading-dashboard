# ARCHITECTURE.md
## Architettura Sistema ES/SPX Trading Dashboard
**Versione**: 1.0 | **Data**: 2026-02-11

---

## 1. Overview

```
+------------------+     +------------------+     +------------------+
|   DATA SOURCES   | --> |  MASTER_OUTPUT   | --> |    DASHBOARD     |
|  (OPRA/GEX/IB)   |     |    (Storico)     |     |   (Streamlit)    |
+------------------+     +------------------+     +------------------+
         |                        |                        |
         v                        v                        v
    [Grezzi]              [CSV Validati]           [Visualizzazione]
```

---

## 2. Moduli Principali

### 2.1 MASTER_OUTPUT Builder (Priorita' 1 - Statistica)
```
src/es_trading_dashboard/
├── master_output/
│   ├── __init__.py
│   ├── builder.py          # Orchestratore principale
│   ├── range_engine.py     # Calcolo range mattina/pomeriggio
│   ├── iv_engine.py        # Calcolo IV da OPRA
│   ├── rv_engine.py        # Calcolo RV da 1m bars
│   ├── oi_engine.py        # Aggregazione OI 0DTE
│   ├── gex_engine.py       # Import dati GEXBot
│   ├── validators.py       # Controlli qualita'
│   └── exporters.py        # Export CSV con versioning
```

### 2.2 Data Loaders
```
src/es_trading_dashboard/
├── loaders/
│   ├── __init__.py
│   ├── opra_loader.py      # Carica .csv.zst da OPRA
│   ├── databento_loader.py # Carica .dbn.zst da Databento
│   ├── gexbot_loader.py    # Carica CSV da GEXBot
│   └── ib_loader.py        # Carica da IB (solo live)
```

### 2.3 Live Collector (Priorita' 2 - Dopo Statistica)
```
src/es_trading_dashboard/
├── collector/
│   ├── __init__.py
│   ├── ib_connection.py    # Connessione IB con asyncio fix
│   ├── vwap_collector.py   # VWAP tick 233 streaming
│   ├── snapshot_manager.py # Foto fisse 10:00, 15:30, 15:45
│   ├── daily_writer.py     # Scrittura CSV giornalieri
│   └── health_monitor.py   # Health check panel
```

### 2.4 Dashboard (Priorita' 3)
```
src/es_trading_dashboard/
├── dashboard/
│   ├── __init__.py
│   ├── app.py              # Streamlit main app
│   ├── pages/
│   │   ├── live_morning.py # Vista mattina (VWAP-based)
│   │   ├── live_afternoon.py # Vista pomeriggio (OPEN-based)
│   │   ├── historical.py   # Analisi storica
│   │   ├── events.py       # Calendario macro/earnings
│   │   └── health.py       # Health panel
│   └── components/
│       ├── range_card.py
│       ├── iv_chart.py
│       └── oi_heatmap.py
```

---

## 3. Flusso Dati

### 3.1 MASTER_OUTPUT (Storico)
```
[OPRA .csv.zst] ---> opra_loader ---> iv_engine --+
                                                   |
[Databento .dbn.zst] -> databento_loader -> rv_engine --+-> builder -> MASTER_OUTPUT.csv
                                                   |
[GEXBot CSV] -----> gexbot_loader ---> gex_engine -+
```

### 3.2 Live Collection
```
[IB TWS] ---> ib_connection ---> vwap_collector ---> snapshot_manager
                    |                                       |
                    +-- asyncio.set_event_loop() fix        |
                                                            v
                                              daily_writer ---> DATA/daily/
```

---

## 4. Configurazione

### 4.1 config.yaml
```yaml
timezone: Europe/Zurich
trade_date:
  start: "02:15"
  end: "22:00"
  previous_session: "00:00-02:14"

paths:
  opra: "C:\\Users\\annal\\Desktop\\OPRA"
  gex: "C:\\Users\\annal\\Desktop\\GEX\\quant-historical\\data\\ES_SPX\\ES_SPX"
  output: "C:\\Users\\annal\\Desktop\\DATA"

ranges:
  morning:
    reference: vwap_es
    end_time: "15:30"
  afternoon:
    reference: spx_open_projected
    start_time: "15:30"
    end_time: "22:00"

touch:
  buffer: 0.25
  cooldown_seconds: 30
  breakout_minutes: 5

atm:
  step: 5
  reselect_trigger: price_move

oi:
  strike_range: 100
  expirations: ["0DTE"]
  snapshots: ["02:15", "10:00", "15:30", "22:00"]

iv_rv:
  iv_source: opra
  rv_bars: 1m_external
  windows:
    - overnight: "22:00-09:30"
    - morning: "09:30-15:30"
    - afternoon: "15:30-22:00"
    - full: "22:00-22:00"
  percentiles: [60, 120, "full"]

versioning:
  model_version: "RANGE_ENGINE_v1"
  config_hash: auto  # SHA256
```

---

## 5. Fix Tecnici Implementati

### 5.1 IB Thread Event Loop
```python
# In ib_connection.py - worker thread
import asyncio

def _run_ib_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)  # FIX CRITICO
    # ... rest of IB connection
```

### 5.2 VWAP Solo IB
```python
# VWAP sempre da IB tick 233, MAI ricalcolato
vwap = ib.reqMktData(contract, genericTickList="233")
```

### 5.3 SPX OPEN Congelato
```python
# Primo prezzo post-15:30, poi immutabile per la sessione
if spx_open is None and current_time >= "15:30":
    spx_open = get_spx_price()  # Congelato
```

---

## 6. Deployment

### 6.1 Directory Locale
```
C:\ES_DASHBOARD\collector_v1\
├── config.yaml
├── run_collector.py
├── run_dashboard.py
└── logs/
```

### 6.2 Backup
- Sync automatico OneDrive
- Nessun snapshot IB pagato
- File read-only dopo 22:01 finalize

### 6.3 Avvio
```bash
# 1-click start
python run_collector.py  # Background
python run_dashboard.py  # Foreground Streamlit
```

---

## 7. Priorita' Sviluppo

1. **MASTER_OUTPUT storico** - Pulire dati grezzi, creare CSV validati
2. **Live Collector** - Solo dopo storico funzionante
3. **Dashboard** - Visualizzazione finale
4. **Automazione Algo Studio** - Ricerca pattern su storico
