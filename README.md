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
│   │   ├── app.py             # Streamlit main app
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
- `streamlit` - Dashboard UI
- `pandas` - Data manipulation
- `numpy` - Calcoli numerici
- `pydantic` - Validazione config
- `pytest` - Testing

### ⚙️ Configurazione IB
- **Porta:** 7496 (TWS paper/live)
- **ClientId range:** 100-999 (evita conflitto con ATAS su ID 1)
- **Timeout:** 10 secondi
- **Auto-reconnect:** Sì

### 🚀 Fasi di Sviluppo

#### Fase 1: Foundation ✅
- [x] Setup progetto (pyproject.toml)
- [x] Struttura cartelle
- [x] Config centralizzata
- [x] README con piano

#### Fase 2: Connessione IB
- [ ] Modulo connection.py
- [ ] Gestione errori IB
- [ ] Test connessione

#### Fase 3: Data Collection
- [ ] Market data subscriptions
- [ ] Options chain fetcher
- [ ] Caching dati

#### Fase 4: Calcoli
- [ ] Greeks calculation
- [ ] VWAP calculation
- [ ] ATM range logic

#### Fase 5: Dashboard UI
- [ ] Layout Streamlit
- [ ] Options chain table
- [ ] Real-time updates

#### Fase 6: Polish
- [ ] Launcher script
- [ ] Documentazione
- [ ] CI/CD

---

## 🛠️ Setup & Run

```bash
# Install dependencies
pip install -e .

# Run dashboard
python -m es_trading_dashboard
```

---

## 📝 Note Tecniche

### Convivenza con ATAS
- ATAS usa clientId=1 sulla porta 7496
- Questa dashboard usa clientId nel range 100-999
- Se errore 326 (clientId in uso), il sistema prova automaticamente il prossimo ID

### Struttura Codice
- **Type hints** ovunque
- **Docstrings** per ogni funzione pubblica
- **Logging** strutturato
- **Tests** per ogni modulo
