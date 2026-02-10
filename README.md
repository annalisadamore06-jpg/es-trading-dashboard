# es-trading-dashboard

Real-time ES/SPX options trading dashboard with Interactive Brokers integration

---

## 📋 Project Plan

### 🎯 Obiettivo

Creare una dashboard di trading real-time per ES/SPX options che:
- Si connette a Interactive Brokers via `ib_insync`
- Mostra catena opzioni ES/SPX 0DTE con Greeks
- Calcola ATM range con due logiche: VWAP (mattina) e OPEN SPX (pomeriggio)
- Gestisce correttamente la convivenza con ATAS (porta 7496, clientId 100-999)

---

## ⏰ LOGICA TEMPORALE (ORARIO ROMA/CET)

### 🌅 MATTINA (02:15 - 15:30 CET)
**Range calcolati su VWAP di ES**

- ES è un future → ha volume → ha il **VWAP**
- SPX è un indice → **NON ha VWAP**
- I range della mattina si calcolano direttamente su ES usando il suo VWAP
- Nessuna conversione necessaria, i livelli sono già su ES

### 🌆 POMERIGGIO (dalle 15:30 CET - apertura mercati US)
**Range calcolati su OPEN di SPX**

- Alle 15:30 CET si registra l'**OPEN di SPX**
- I range si calcolano sull'OPEN di SPX
- I livelli vengono poi **convertiti su ES** aggiungendo lo SPREAD
- **SPREAD = ES Last - SPX Last**
- Livello ES = Livello SPX + SPREAD

### 🎰 ES OPTIONS 0DTE
- **Apertura:** 02:15 CET
- **Scadenza:** 22:00 CET
- **Strike spacing:** ogni 5 punti (5900, 5905, 5910...)
- **ATM Strike:** `round(ES_Last / 5) * 5`

### 📊 SPX OPTIONS 0DTE
- **Strike spacing:** ogni 5 punti (6100, 6105, 6110...)
- **ATM Strike:** `round(SPX_Last / 5) * 5`

---

## 🧮 CALCOLI BLINDATI

### Straddle ATM (sempre sulla strike più vicina al prezzo)
```
Straddle ASK = Call ASK + Put ASK
Straddle BID = Call BID + Put BID
Straddle SPREAD = Straddle ASK - Straddle BID
```

### IV% Straddle
```
# MATTINA (su VWAP ES)
IV% Straddle = (Straddle ASK × 100) / ES_VWAP

# POMERIGGIO (su OPEN SPX)
IV% Straddle = (Straddle ASK × 100) / SPX_OPEN
```

### Range R1 (basato su IV%)
```
# MATTINA
R1 UP = ES_VWAP + (ES_VWAP × IV%)
R1 DOWN = ES_VWAP - (ES_VWAP × IV%)

# POMERIGGIO (calcolo su SPX, poi conversione)
R1 UP (SPX) = SPX_OPEN + (SPX_OPEN × IV%)
R1 DOWN (SPX) = SPX_OPEN - (SPX_OPEN × IV%)
R1 UP (ES) = R1 UP (SPX) + SPREAD
R1 DOWN (ES) = R1 DOWN (SPX) + SPREAD
```

### Range R2 (basato su IV% Straddle)
```
# MATTINA
R2 UP = ES_VWAP + (ES_VWAP × IV% Straddle)
R2 DOWN = ES_VWAP - (ES_VWAP × IV% Straddle)

# POMERIGGIO (calcolo su SPX, poi conversione)
R2 UP (SPX) = SPX_OPEN + (SPX_OPEN × IV% Straddle)
R2 DOWN (SPX) = SPX_OPEN - (SPX_OPEN × IV% Straddle)
R2 UP (ES) = R2 UP (SPX) + SPREAD
R2 DOWN (ES) = R2 DOWN (SPX) + SPREAD
```

### DVS
```
DVS = (Punti Straddle / Punti VI) × 100
```

### Estensioni Fibonacci
```
# MATTINA
FIBO EST R1 UP = ES_VWAP + (Punti R1 × 161.8%)
FIBO EST R1 DOWN = ES_VWAP - (Punti R1 × 61.8%)

# POMERIGGIO (su SPX poi convertito)
FIBO EST R1 UP (SPX) = SPX_OPEN + (Punti R1 × 161.8%)
FIBO EST R1 DOWN (SPX) = SPX_OPEN - (Punti R1 × 61.8%)
# Poi + SPREAD per avere su ES
```

---

## ⛔ REGOLA CRITICA: NO SNAPSHOT!

```python
# ═══════════════════════════════════════════════════════════════════
# ⛔ VIETATO - COSTA SOLDI:
# snapshot=True → $0.01/richiesta
# regulatorySnapshot=True → $0.03/richiesta
#
# ✅ OBBLIGATORIO - GRATIS CON SOTTOSCRIZIONE:
# snapshot=False
# regulatorySnapshot=False
# ═══════════════════════════════════════════════════════════════════

ticker = ib.reqMktData(
    contract,
    genericTickList="233",   # RTVolume → VWAP
    snapshot=False,          # ✅ SEMPRE FALSE!
    regulatorySnapshot=False # ✅ SEMPRE FALSE!
)
```

---

## ⏰ AUTO-SALVATAGGIO

| Orario CET | Azione |
|------------|--------|
| 10:00 | Salva ES RANGE 10:00 (basato su VWAP ES) |
| 15:30 | Registra SPX OPEN + Salva RANGE SPX/ES 15:30 |
| 15:45 | Salva snapshot 15 min dopo apertura US |
| Ogni 10s | Log in database (VWAP, IV%, Straddle, DVS, P/C Ratio) |

---

## 🏗️ Architettura

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
│   │   ├── ranges.py          # Calcolo R1/R2/FIBO
│   │   └── atm.py             # Calcolo ATM strike
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

---

## 📦 Dipendenze Principali

- `ib_insync` - Connessione Interactive Brokers
- `dash` - Dashboard UI (Plotly)
- `dash-bootstrap-components` - UI components
- `pandas` - Data manipulation
- `numpy` - Calcoli numerici
- `pydantic` - Validazione config
- `openpyxl` - Export Excel
- `pytest` - Testing

---

## ⚙️ Configurazione IB

- **Porta:** 7496 (TWS paper/live)
- **ClientId range:** 100-999 (evita conflitto con ATAS su ID 1)
- **Timeout:** 30 secondi
- **Auto-reconnect:** Sì
- **Read-only:** Sì (no trading)

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
- [ ] Options chain fetcher (0DTE automatico)
- [ ] ATM tracking dinamico
- [ ] Caching dati

#### Fase 4: Calcoli
- [ ] Range R1/R2 calculation (mattina/pomeriggio)
- [ ] DVS calculation
- [ ] Fibonacci extensions
- [ ] SPREAD ES-SPX tracking

#### Fase 5: Dashboard UI (Dash)
- [ ] Layout Dash (come da foto)
- [ ] Sezione MERCATO LIVE
- [ ] Sezione RANGE (mattina/pomeriggio)
- [ ] Sezione VOLATILITA'
- [ ] Log table (ogni 10 sec)
- [ ] Real-time updates

#### Fase 6: Polish
- [ ] Launcher script
- [ ] Excel export (ogni 10 sec)
- [ ] Documentazione

---

## 🛠️ Setup & Run

```bash
# Install dependencies
pip install -e .

# Run dashboard
python -m es_trading_dashboard
```
