# es-trading-dashboard

Real-time ES/SPX options trading dashboard with Interactive Brokers integration

---

## COSTANTI E CONFIG (da run_dashboard_FINAL_FREEZE.py)

```python
IB_HOST = "127.0.0.1"
IB_PORT = 7496
CLIENT_ID = 30
DASH_HOST = "127.0.0.1"
DASH_PORT = 8050
UPDATE_SEC = 10          # loop IB ogni 10 secondi
UPDATE_MS = 10000        # refresh UI ogni 10 secondi
RESELECT_POINTS = 10     # ricalcola strike ATM se ES si muove di 10+ punti
SQRT_252 = 252**0.5      # = 15.8745 (radice quadrata giorni trading)
FIB_UP = 1.618           # Fibonacci estensione UP
FIB_DN = 0.618           # Fibonacci estensione DOWN
T_1000 = (10, 0)         # snapshot ore 10:00 CET
T_1530 = (15, 30)        # snapshot ore 15:30 CET (apertura US)
T_1545 = (15, 45)        # snapshot ore 15:45 CET (15 min dopo apertura)
```

---

## CONNESSIONE IB E CONTRATTI

### ES Future (front month)
```python
cds = ib.reqContractDetails(Future("ES", "", "CME"))
cds = sorted(cds, key=lambda x: x.contract.lastTradeDateOrContractMonth)
es = cds[0].contract    # primo contratto = front month
ib.qualifyContracts(es)
```

### ES Market Data (VWAP + IV)
```python
t_es = ib.reqMktData(es, genericTickList="233,106", snapshot=False)
# 233 = RTVolume -> popola ticker.vwap
# 106 = impliedVolatility (IV% ANNUALE)
# snapshot=False SEMPRE! (NO SNAPSHOT = GRATIS)
```

### SPX Index
```python
spx = Index("SPX", "CBOE")
ib.qualifyContracts(spx)
t_spx = ib.reqMktData(spx, snapshot=False)
```

### Options Chain 0DTE (automatica)
```python
chains = ib.reqSecDefOptParams("ES", "CME", "FUT", es.conId)
chain = next(c for c in chains if c.tradingClass == "E2B" and today in c.expirations)
expiry = today  # 0DTE = scadenza oggi
```
- **TradingClass:** E2B (opzioni 0DTE su ES)
- Il sistema trova automaticamente la scadenza di oggi nella chain

### ATM Strike Selection
```python
es_last = nn(t_es.last) or nn(t_es.close)
strike = min(chain.strikes, key=lambda k: abs(k - es_last))
anchor = es_last
```
- Strike ATM = la strike piu vicina a ES Last
- **RESELECTION:** se ES si muove di 10+ punti dall'anchor, ricalcola strike ATM

### Options ATM (Call + Put)
```python
for exch in ("CME", "GLOBEX"):  # prova entrambi gli exchange
    call = FuturesOption("ES", expiry, strike, "C", exch, tradingClass=chain.tradingClass)
    put  = FuturesOption("ES", expiry, strike, "P", exch, tradingClass=chain.tradingClass)
    ib.qualifyContracts(call, put)
    tc = ib.reqMktData(call, genericTickList="101,106", snapshot=False)
    tp = ib.reqMktData(put,  genericTickList="101,106", snapshot=False)
    # 101 = option computed greeks
    # 106 = impliedVolatility
```

---

## DATI LIVE RACCOLTI OGNI 10 SECONDI

```python
es_last = nn(t_es.last) or nn(t_es.close)       # ES Last price
es_vwap_live = nn(getattr(t_es, "vwap", None))   # ES VWAP (da tick 233)
spx_last = nn(t_spx.last)                        # SPX Last price
spread_live = es_last - spx_last                  # SPREAD = ES - SPX
```

### SPX OPEN Ufficiale (immutabile al giorno)
```python
# Dopo le 15:30 CET, UNA SOLA VOLTA al giorno:
# 1) Prova ticker.open
# 2) Fallback: reqHistoricalData daily bar useRTH=True -> bars[-1].open
# Una volta registrato, NON cambia piu per tutto il giorno
spx_open_official = STATE["spx_open_official"]
```

---

## CALCOLI BLINDATI

### IV% Daily (da tick 106 IB)
```python
# IB fornisce IV% ANNUALE (tick 106 = impliedVolatility)
# Se iv_raw < 1.0 -> moltiplica x100 (IB restituisce 0.xx)
# Se iv_raw >= 1.0 -> gia in percentuale
iv_raw = nn(getattr(t_es, "impliedVolatility", None))
iv_annual_pct = (iv_raw * 100.0) if iv_raw < 1.0 else iv_raw
iv_daily_pct = iv_annual_pct / SQRT_252   # /15.8745
iv_daily_frac = iv_daily_pct / 100.0      # per calcoli
```

### Straddle ATM (opzioni Call+Put sulla strike piu vicina)
```python
str_bid = call_bid + put_bid
str_ask = call_ask + put_ask
str_mid = (str_bid + str_ask) / 2.0
str_spread = str_ask - str_bid
pcr = put_mid / call_mid   # Put/Call Ratio
```

### IV% Straddle
```python
# MATTINA: base = ES VWAP
# POMERIGGIO: base = SPX OPEN official
iv_straddle_pct = (str_ask / base_live) * 100.0
iv_straddle_frac = iv_straddle_pct / 100.0
```

### MODE (Mattina vs Pomeriggio)
```python
# DEFAULT = MORNING (VWAP ES)
mode = "MORNING_ES_VWAP"
base_live = es_vwap_live
base_label_live = "VWAP"

# Dopo 15:30 CET + SPX open disponibile + spread disponibile:
if time_ge(T_1530) and spx_open_off not in (None,0) and spread_live is not None:
    mode = "AFTERNOON_SPX_OPEN"
    base_live = spx_open_off
    base_label_live = "OPEN"
```

### Range R1 (basato su IV% Daily)
```python
r1_pts = base * iv_daily_frac
R1_UP  = base + r1_pts
R1_DN  = base - r1_pts
```

### Range R2 (basato su IV% Straddle)
```python
r2_pts = base * iv_straddle_frac
R2_UP  = base + r2_pts
R2_DN  = base - r2_pts
```

### Estensioni Fibonacci
```python
FIB_R1_UP = base + (r1_pts * 1.618)
FIB_R1_DN = base - (r1_pts * 0.618)
FIB_R2_UP = base + (r2_pts * 1.618)
FIB_R2_DN = base - (r2_pts * 0.618)
```

### DVS (Dollar Value of Spread)
```python
dvs = (str_mid / r1_pts) * 100.0
```

### Conversione SPX -> ES (pomeriggio)
```python
def to_es(x, spread):
    return x + spread   # livello_ES = livello_SPX + SPREAD
```

---

## PANNELLI UI - ORDINE LIVELLI

```python
ORDER_KEYS = [
    "FIBO EST R1 UP",
    "FIBO EST R2 UP",
    "R1 UP",
    "R2 UP",
    "CENTER",         # = VWAP (mattina) o OPEN (pomeriggio)
    "R2 DOWN",
    "R1 DOWN",
    "FIBO EST R2 DOWN",
    "FIBO EST R1 DOWN"
]
```

### 8 Colonne nella Dashboard

| # | Pannello | Tipo | Base | Dati |
|---|----------|------|------|------|
| 1 | ES RANGE 10:00 | FOTO | VWAP ES (ore 10) | IV+Straddle congelati ore 10 |
| 2 | ES LIVE MATTINA | LIVE | VWAP ES (live) | IV+Straddle live |
| 3 | SPX LIVE | LIVE | OPEN SPX | IV+Straddle live |
| 4 | SPX 15:30 | FOTO | OPEN SPX | IV+Straddle congelati 15:30 |
| 5 | ES 15:30 | FOTO | OPEN SPX + spread | IV+Straddle congelati 15:30 |
| 6 | SPX 15:45 | FOTO | OPEN SPX | IV+Straddle congelati 15:45 |
| 7 | ES 15:45 | FOTO | OPEN SPX + spread | IV+Straddle congelati 15:45 |
| 8 | ES LIVE POMERIGGIO | LIVE | OPEN SPX + spread live | IV+Straddle live |

**FOTO = snapshot immutabile** (congelato una volta al giorno)
**LIVE = aggiornato ogni 10 secondi**

---

## SNAPSHOT FISSI (FOTO)

### 10:00 CET - ES RANGE
- Base = **ES VWAP live** (congelato alle 10:00)
- IV% Daily = congelata alle 10:00
- IV% Straddle = congelata alle 10:00
- Range R1/R2/FIBO calcolati e congelati
- Salvato UNA VOLTA al giorno, immutabile

### 15:30 CET - SPX/ES
- Registra **SPX OPEN ufficiale** (immutabile al giorno)
- **spread_fixed** = spread live al momento dello snap
- **IV% Daily fixed** = IV% live al momento dello snap
- **IV% Straddle fixed** = IV% straddle al momento dello snap
- Calcola range su SPX (base = SPX OPEN)
- Converte su ES con spread_fixed
- Salva DOPPIO snapshot: SPX_15:30 e ES_15:30

### 15:45 CET - SPX/ES (15 min dopo apertura)
- Stessa logica del 15:30 ma con dati aggiornati alle 15:45
- spread_fixed, IV, straddle congelati a quel momento
- Salva DOPPIO snapshot: SPX_15:45 e ES_15:45

---

## SEZIONI UI DASHBOARD

### Sinistra (flex: 520px)
1. **MERCATO LIVE** - ES last, SPX last, VWAP, OPEN, SPREAD, ATM strike, Exchange, Expiry, TradingClass
2. **VOLATILITA LIVE** - IV daily%, IV straddle%, Straddle ASK/BID/MID/SPREAD, DVS, P/C ratio, MODE
3. **LOG (ogni 10 secondi)** - tabella ultimi 40 record con colonne: DATE_TIME, VWAP, IV%, IV% STR, DVS, STR ASK, STR BID, STR SPR, P/C, MODE

### Destra (flex: 1)
- **8 colonne** LIVE e FOTO affiancate (display:flex, flexWrap:wrap)

---

## CSV - STORICIZZAZIONE

### Live Log (ogni 10 secondi)
**File:** `live_log_10s.csv`
```
timestamp, mode, es_last, es_vwap_live, spx_last, spx_open_official,
spread_live, iv_daily_pct_live, iv_straddle_pct_live,
str_bid, str_mid, str_ask, str_spread, dvs, pcr
```
- Max 300 righe in memoria (ultimi 300 record)
- Append continuo su file CSV

### Snapshot (eventi fissi)
**File:** `snapshots_fixed.csv`
```
timestamp, slot, date, base_label, base_value, spx_open_official,
spread_fixed, iv_daily_pct_fixed, iv_straddle_pct_fixed,
R1_UP, R2_UP, CENTER, R2_DN, R1_DN,
FIB_R1_UP, FIB_R2_UP, FIB_R2_DN, FIB_R1_DN
```
- Slot: ES_10:00, SPX_15:30, ES_15:30, SPX_15:45, ES_15:45

---

## REGOLA CRITICA: NO SNAPSHOT IB!

```python
# snapshot=False    SEMPRE! (gratis con sottoscrizione)
# snapshot=True     VIETATO! ($0.01/richiesta)
# regulatorySnapshot=True  VIETATO! ($0.03/richiesta)
```

---

## ARCHITETTURA RUNTIME

- **Thread 1:** `ib_worker()` - loop infinito connessione IB + raccolta dati + calcoli + CSV
- **Thread 2:** `Dash app` - server web UI su porta 8050
- Il worker scrive in `STATE` (dict globale), la UI legge da `STATE`
- Update ogni 10 secondi (UPDATE_SEC=10, UPDATE_MS=10000)

---

## DIPENDENZE

```python
from ib_insync import IB, util, Future, Index, FuturesOption
import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import pandas as pd
import math, csv, os, threading, datetime, logging
from collections import OrderedDict
```

---

## Setup & Run

```bash
pip install -e .
python run_dashboard_FINAL_FREEZE.py
# Dashboard su http://127.0.0.1:8050
```
