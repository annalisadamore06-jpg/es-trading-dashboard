# es-trading-dashboard
Real-time ES/SPX options trading dashboard with Interactive Brokers integration

---

## 📋 Project Plan

### 🎯 Obiettivo
Creare una dashboard di trading real-time per ES/SPX options che:
- Si connette a Interactive Brokers via `ib_insync`
- Mostra catena opzioni SPX con Greeks
- Calcola ATM range basato su OPEN SPX
- Visualizza VWAP e altri indicatori
- Gestisce correttamente la convivenza con ATAS (porta 7496, clientId 100-999)

### 🏗️ Architettura

```
es-trading-dashboard/
├── src/es_trading_dashboard/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Configurazione centralizzata
│   │   ├── connection.py      # Gestione connessione IB
│   │   └── exceptions.py      # Custom exceptions
│   ├── data/
│   │   ├── __init__.py
│   │   ├── collector.py       # Raccolta dati options
│   │   ├── market_data.py     # Sottoscrizioni market data
│   │   └── cache.py           # Caching locale
│   ├── calculations/
│   │   ├── __init__.py
│   │   ├── greeks.py          # Calcolo Greeks
│   │   ├── vwap.py            # Calcolo VWAP
│   │   └── atm_range.py       # Calcolo ATM range
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── app.py             # Dash main app
│   │   ├── components/        # UI components riutilizzabili
│   │   └── styles.py          # Styling dashboard
│   └── utils/
│       ├── __init__.py
│       ├── logging.py         # Logging configurato
│       └── helpers.py         # Funzioni utility
├── tests/
│   ├── __init__.py
│   ├── test_connection.py
│   ├── test_collector.py
│   └── test_calculations.py
├── scripts/
│   └── START_DASHBOARD.ps1    # Launcher one-command
├── pyproject.toml
├── README.md
└── .gitignore
```

### 📦 Dipendenze Principali
- `ib_insync` - Connessione Interactive Brokers
- `dash` - Dashboard UI (Plotly)
- `dash-bootstrap-components` - UI components
- `pandas` - Data manipulation
- `numpy` - Calcoli numerici
- `pydantic` - Validazione config
- `openpyxl` - Export Excel
- `pytest` - Testing

### ⚙️ Configurazione IB
- **Porta:** 7496 (TWS paper/live)
- **ClientId range:** 100-999 (evita conflitto con ATAS su ID 1)
- **Timeout:** 10 secondi
- **Auto-reconnect:** Sì

---

## ⛔ REGOLA CRITICA: NO SNAPSHOT!

```python
# ═══════════════════════════════════════════════════════════════════
# ⛔ VIETATO - COSTA SOLDI:
#   snapshot=True           → $0.01/richiesta
#   regulatorySnapshot=True → $0.03/richiesta
#
# ✅ OBBLIGATORIO - GRATIS CON SOTTOSCRIZIONE:
#   snapshot=False
#   regulatorySnapshot=False
# ═══════════════════════════════════════════════════════════════════

ticker = ib.reqMktData(
    contract,
    genericTickList="233",   # RTVolume → VWAP
    snapshot=False,          # ✅ SEMPRE FALSE!
    regulatorySnapshot=False # ✅ SEMPRE FALSE!
)
```

---

## 🧮 CALCOLI BLINDATI

### Straddle & IV
```
Straddle ASK ATM = Call ASK + Put ASK
IV% Straddle = (Straddle ASK × 100) / VWAP
```

### Range R1 (IV%)
```
R1 UP   = VWAP + (VWAP × IV%)
R1 DOWN = VWAP - (VWAP × IV%)
```

### Range R2 (Straddle)
```
R2 UP   = VWAP + (VWAP × IV% Straddle)
R2 DOWN = VWAP - (VWAP × IV% Straddle)
```

### DVS
```
DVS = (Punti Straddle / Punti VI) × 100
```

### Estensioni Fibonacci
```
FIBO EST UP   = VWAP + (Punti × 161.8%)
FIBO EST DOWN = VWAP - (Punti × 61.8%)
```

---

## ⏰ AUTO-SALVATAGGIO

| Orario | Azione |
|--------|--------|
| 10:00 CET | Salva ES RANGE 10:00 |
| 15:30 CET | Salva RANGE SPX + ES 15:30 |
| 15:45 CET | Salva snapshot 15 min dopo apertura |

---

## 🚀 Fasi di Sviluppo

#### Fase 1: Foundation ✅
- [x] Setup progetto (pyproject.toml)
- [x] Struttura cartelle
- [x] Config centralizzata
- [x] README con piano

#### Fase 2: Connessione IB ✅
- [x] Modulo connection.py
- [x] Gestione errori IB
- [x] Custom exceptions

#### Fase 3: Data Collection
- [ ] Market data subscriptions (NO SNAPSHOT!)
- [ ] Options chain fetcher
- [ ] Caching dati

#### Fase 4: Calcoli
- [ ] Range R1/R2 calculation
- [ ] DVS calculation
- [ ] Fibonacci extensions

#### Fase 5: Dashboard UI (Dash)
- [ ] Layout Dash
- [ ] Components range
- [ ] Real-time updates (10 sec)

#### Fase 6: Polish
- [ ] Launcher script
- [ ] Excel export
- [ ] Documentazione

---

## 🛠️ Setup & Run

```bash
# Install dependencies
pip install -e .

# Run dashboard
python -m es_trading_dashboard
```
