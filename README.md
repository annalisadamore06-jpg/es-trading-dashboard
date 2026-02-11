# ES/SPX Trading Dashboard - Sistema Istituzionale

**Data aggiornamento:** 11 febbraio 2026
**Versione specifica:** SPEC_LOCKED (vedi SPEC_LOCK.md)

Sistema di trading istituzionale per ES/SPX con:
- Dashboard real-time IB (02:15-22:00 Europe/Zurich)
- MASTER_OUTPUT storico unico da dati Databento/GLBX, OI, GEXBot
- Analisi statistica sui range (VWAP/OPEN) + IV/RV + OI + Gamma
- Automazione setup via Algo Studio Pro (dopo ricerca su storico)

---

## Filosofia: Statistica Prima, Collector Dopo

**Non siamo schiavi del collector.** Priorita:
1. Costruire **MASTER_OUTPUT storico unico** da tutti i dati acquistati
2. Analisi statistica robusta: range behavior, IV/RV, OI, gamma regime
3. Identificare setup ad alto hedge su dati storici
4. **Solo dopo:** costruire collector live che alimenta lo stesso schema dati
5. Tradurre i setup migliori in regole deterministiche per **Algo Studio Pro**

---

## Trade Date e Orari (Europe/Zurich - Ora Italia)

Tutti gli orari sono in **Europe/Zurich (ora Italia)**:
- **02:15** = 02:15 di notte (apertura chain ES 0DTE)
- **10:00** = 10:00 mattina (foto VWAP ES)
- **15:30** = 15:30 pomeriggio (open cash USA/SPX)
- **22:00** = 22:00 sera (fine sessione operativa)
- **22:01** = switch logico alla 0DTE del giorno successivo

### Definizione trade_date
- `trade_date` = market date della sessione **02:15-22:00**
- Intervallo 00:00-02:14 appartiene ancora alla sessione precedente
- Esempio: dati a 01:00 del 12 marzo -> trade_date = 2026-03-11

### 0DTE Selection Logic (robusta ai riavvii)
```python
if now_local >= 22:01:   # Europe/Zurich
    use next calendar expiry   # 0DTE di domani
else:
    use today's expiry         # 0DTE di oggi
```

---

## Sorgenti Dati

### 1. IB Live (Collector)
- ES future front-month rolling + SPX index
- Frequenza: ogni 10 secondi
- VWAP IB (tick 233), IV (tick 106), straddle ATM, range/touch

### 2. Databento / GLBX
- **ES 1m OHLCV** (GLBX-MDP3): verita prezzi per RV e max/min 10-22
- **ES OI EOD** (statistics): `.csv.zst`
- **SPX options OI EOD** (OPRA pillar): `.csv.zst`
- **SPX options CBBO 1m**: `.csv.zst` e `.dbn.zst`

### 3. GEXBot quant-historical
- Cartelle: `gamma_one`, `gamma_zero`, `delta_one`, `delta_zero`, `gex_full`, `vanna_*`, `charm_*`
- CSV giornalieri (ES/SPX) ~60 giorni
- Output: zero gamma, call/put walls, gamma regime

### 4. OI Runner (ES options)
- `ES_OI_RAW_YYYY-MM-DD.csv`
- `ES_OI_SUMMARY_YYYY-MM-DD.csv`
- `ES_OI_DELTA_YYYY-MM-DD_vs_YYYY-MM-DD.csv`
- `ES_OI_MASTER_RAW.csv` / `ES_OI_MASTER_SUMMARY.csv`

### Formati File
- **Databento**: CSV compressi Zstandard `.csv.zst` + DBN `.dbn.zst`
- **GEXBot**: CSV per giorno per metrica
- **OI runner**: CSV daily + master

### Path Sorgenti
- **OPRA grezzo**: `C:\Users\annal\Desktop\OPRA`
- **GEXBot storico**: `C:\Users\annal\Desktop\GEX\quant-historical\data\ES_SPX\ES_SPX`
- **Output pulito**: `C:\Users\annal\Desktop\DATA`

---

## Specifiche VWAP e OPEN (REGOLE BLINDATE)

### VWAP ES (mattina)
- **Sempre e solo** il valore IB ufficiale: `ticker.vwap` (tick 233 RTVolume)
- **Mai** ricalcolato da noi
- Se `None` nei primi minuti: logga `es_vwap_live=None`, ma continua a loggare ES_last/IV/straddle
- Foto 10:00: aspetta fino a **10:05** max; se ancora None -> anomaly, niente foto valida

### SPX OPEN (pomeriggio)
- **Primo prezzo SPX** dopo le 15:30 (non l'open della candela daily)
- Una volta registrato, **congelato per tutta la giornata**
- Gerarchia fallback per SPX last-like:
  1. `ticker.marketPrice()` se > 0
  2. `ticker.midpoint()` se disponibile
  3. `ticker.close` (prev close)
  4. SPX marcato "non disponibile", logghi solo ES

### SPX OPEN Source Tracking
- `SPX_OPEN_SOURCE = REALTIME` -> ticker.open arrivato in tempo
- `SPX_OPEN_SOURCE = HIST_DAILY` -> fallback su daily bar
- `SPX_OPEN_SOURCE = MANUAL` -> emergenza, valore inserito manualmente

---

## Logica Range Mattina vs Pomeriggio

### MATTINA (10:00-15:30)
- **Base** = VWAP ES IB (live, in movimento)
- **Foto 10:00 (IMMUTABILE)**:
  - `VWAP_ES_10:00`
  - `IV_DAILY_10:00`, `IV_STRADDLE_10:00`
  - Range R1/R2/FIBO calcolati e congelati
- **Live Mattina**:
  - VWAP/IV si muovono
  - Range ricalcolati dinamicamente su VWAP live

### POMERIGGIO (15:30-22:00)
- **Base** = SPX OPEN ufficiale (FISSO, non cambia piu)
- **Foto 15:30 e 15:45 (IMMUTABILI)**:
  - Base = SPX_OPEN_OFFICIAL
  - IV, straddle, spread congelati al momento
  - Range SPX calcolati
  - Range ES = Range SPX + spread_fixed
- **Live Pomeriggio**:
  - Base = OPEN SPX (fisso)
  - IV_daily e IV_straddle live
  - Spread live
  - Range SPX live -> proiettati su ES via spread live

### Differenza Concettuale
- **Live Mattina** = VWAP-centrico (ES), range centrati su flusso negoziazione
- **Live Pomeriggio** = OPEN-centrico (SPX), range centrati su prezzo apertura USA

---

## Range Eventi (TOUCH/REJECT/BREAKOUT)

### Livelli Tracciati (tutti)
- `BASE` (CENTER = VWAP o OPEN)
- `R1_UP`, `R1_DN`
- `R2_UP`, `R2_DN`
- `FIB_R1_UP`, `FIB_R1_DN`
- `FIB_R2_UP`, `FIB_R2_DN`

### Parametri
- **Buffer**: 0.25 punti ES (parametrico in config)
- **Cooldown**: 30 secondi (nuovo touch stesso livello solo dopo 30s)
- **Breakout window**: 5 minuti

### Definizioni
- **Touch UP**: `last >= livello + buffer`
- **Touch DOWN**: `last <= livello - buffer`
- **Breakout**: 5 minuti **consecutivi** oltre il livello (ogni campione 10s deve rispettare)
- **Reject**: torna dall'altra parte del livello entro 5 minuti

### Campi Salvati per Ogni Livello
- `touch_flag` (1/0)
- `touch_count`
- `first_touch_time_local`, `first_touch_time_utc`
- `last_touch_time_local`, `last_touch_time_utc`
- `has_reject` (1/0), `reject_time`
- `has_breakout` (1/0), `breakout_time`
- `time_from_range_birth_to_first_touch` (minuti)

---

## ATM Straddle 0DTE

### Strike Grid
- Strike ES = **griglia 5 punti**
- ATM iniziale = strike multiplo di 5 piu vicino a ES_last

### Ri-selezione Dinamica
- ATM si muove **a gradini di 5 punti**
- Quando ES passa il **midpoint** fra due strike -> ATM salta allo strike adiacente
- Non fissiamo ATM alle 10:00: segue il future in modo dinamico

### Straddle
- `straddle = call_ask + put_ask` sullo strike ATM corrente
- IV straddle: `(straddle_ask / base) * 100`

---

## Volatilita (IV & RV)

### IV Daily (da IB)
```python
iv_raw = ticker.impliedVolatility  # tick 106, annuale
iv_annual_pct = iv_raw * 100 if iv_raw < 1.0 else iv_raw
iv_daily_pct = iv_annual_pct / sqrt(252)  # /15.8745
```

### RV (Realized Volatility) - OFFLINE
- Fonte: dati 1m esterni (Databento), **non** IB live
- Calcolata in script notturno separato
- 4 finestre:
  - `RV_0215_2200` (sessione completa)
  - `RV_1000_2200` (operativa)
  - `RV_1000_1530` (morning)
  - `RV_1530_2200` (afternoon)

### Percentili
- Rolling 60 e 120 giorni + full history dal 2024
- IV percentile: su base giornaliera intera
- DVS percentile: separato morning vs afternoon

---

## OI (Open Interest)

### Fonte e Architettura
- Fonte primaria: file esterni (OI runner + OPRA/Databento), **non** IB intraday
- Strumento: ES options (FOP)
- Finestra strike: **+/- 100 punti** attorno al last ES
- Scadenze: 0DTE (fase 1), poi estensione fino a 1 anno

### Snapshot (4 al giorno)
- **02:15** (apertura sessione)
- **10:00** (nascita foto mattina)
- **15:30** (nascita foto pomeriggio)
- **22:00** (chiusura giornata)

### Campi per Snapshot
- `oi_call_sum_100`, `oi_put_sum_100`
- `call_wall_strike`, `call_wall_oi`
- `put_wall_strike`, `put_wall_oi`
- `delta_oi_call_vs_yesterday`, `delta_oi_put_vs_yesterday`
- `delta_oi_call_vs_prev_snapshot`, `delta_oi_put_vs_prev_snapshot`

---

## GEX (Gamma Exposure)

### Fonte
- GEXBot daily profiles da `quant-historical\data\ES_SPX`
- CSV giornalieri per metrica

### Output Operativo
- `zero_gamma_level`
- `call_wall_level`, `put_wall_level`
- `gamma_regime`: "pos" (mean-revert) o "neg" (trend)
- `gamma_major_sign`

### Integrazione
- Un valore daily per trade_date, valido tutto il giorno
- As-of join con daily_summary_master

---

## Max/Min e Finestra Operativa 10-22

### Strumento e Finestra
- Strumento: **ES**
- Finestra: **10:00-22:00** Europe/Zurich (unica, non 10-20)

### Campi
- `MAX_10_22` = massimo ES tra 10:00 e 22:00
- `MIN_10_22` = minimo ES tra 10:00 e 22:00
- `MAX_10_22_TIME_local`, `MAX_10_22_TIME_utc`
- `MIN_10_22_TIME_local`, `MIN_10_22_TIME_utc`

### Uso
- Misurare rotture ed estensioni dei range mattina/pomeriggio
- Calcolare media estensioni nel tempo solo nell'orario operativo

---

## Riquadri Dashboard (8 Colonne)

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

**FOTO** = snapshot immutabile, congelato una volta al giorno
**LIVE** = aggiornato ogni 10 secondi

---

## Schema Dati MASTER_OUTPUT

### 1. futures_1m_ES
- `ts_utc`, `ts_local`, `trade_date`
- `open`, `high`, `low`, `close`, `volume`
- `symbol`

### 2. rv_daily
- `trade_date`
- `RV_0215_2200`, `RV_1000_2200`, `RV_1000_1530`, `RV_1530_2200`
- `RV_PCTL_60D`, `RV_PCTL_120D`, `RV_PCTL_FULL`

### 3. oi_snapshots
- `trade_date`, `snapshot_slot`, `expiry_bucket`
- `oi_call_sum_100`, `oi_put_sum_100`
- `call_wall_strike`, `put_wall_strike`
- `delta_oi_*`

### 4. gex_daily_summary
- `trade_date`, `underlying`
- `zero_gamma_level`, `call_wall_level`, `put_wall_level`
- `gamma_regime`, `gamma_major_sign`

### 5. daily_summary_master
Join as-of di tutte le tabelle con chiave `trade_date`

---

## Pipeline End-to-End

### Fase 1 - Data Foundation (priorita attuale)
1. **Ingest Databento/GLBX 1m** -> `futures_1m_ES`
2. **RV job offline** -> `rv_daily` (4 finestre + percentili)
3. **Ingest OI runner** -> `oi_snapshots` (4 slot, +/-100, delta OI)
4. **Ingest GEXBot** -> `gex_daily_summary` (zero gamma, walls, regime)
5. **Master builder** -> `daily_summary_master` (join as-of)
6. **Export compatibilita** -> CSV per vecchio Excel (opzionale)

### Fase 2 - Research Setup
- Feature engineering su `daily_summary_master`
- Setup candidates: condizioni + contesto + trigger + gestione rischio
- Backtest robusto: hit rate, excursion, tail risk, sensitivity a vol/gamma regime
- Walk-forward 60/120 rolling

### Fase 3 - Collector Live (dopo ricerca)
- Moduli: `ib_live_collector.py`, `range_engine.py`, `snapshot_engine.py`
- Output: `market_10s`, `range_events`, `range_snapshots`
- Stesso schema del MASTER_OUTPUT offline

### Fase 4 - Algo Studio Pro
- Traduzione setup robusti in regole deterministiche
- Filtri: orari, macro day, gamma regime, vol percentile
- Entry/exit basati su eventi range (touch/reject/breakout)

---

## Versioning e Meta

Ogni CSV/Parquet deve avere:
- `MODEL_VERSION` (es. "RANGE_ENGINE_v1", "OFFLINE_MASTER_v1")
- `CONFIG_HASH` (hash SHA256 del file config)
- `ENGINE_START_TIME` (timestamp avvio)
- Opzionalmente: `GIT_COMMIT_HASH`, `PYTHON_VERSION`, `IBINSYNC_VERSION`

---

## Validazione e Qualita

### Quality Score per trade_date
- missing VWAP foto 10:00 -> hard fail
- SPX last not available -> soft warning
- gaps > N minuti nel log 10s -> warning
- OI/RV/GEX snapshot missing -> warning
- config hash mismatch -> hard fail

### File Immutabili
- Dopo finalize 22:01 -> file read-only
- Correzioni: solo via rebuild da raw, mai edit manuale

---

## Macro/Earnings (Step 2)

### Eventi Macro USA
- Solo **high impact** (3 stelline): CPI, NFP, FOMC, ADP, GDP, PCE
- CSV statico `US_MACRO_EVENTS_YYYY-YYYY.csv`
- Aggiornamento manuale ogni trimestre

### Earnings
- Watchlist ristretta: Big 7 + mega cap impattanti
- CSV `BIG_EARNINGS_YYYY-YYYY.csv`

### Scheda Giornaliera
- Pagina nella dashboard (in italiano) con:
  - Eventi macro di oggi
  - Earnings principali
  - Contesto range/vol/OI/GEX
- Live durante la giornata, finalizzata alle 22:01
- Export CSV scaricabile

---

## Health Panel

Monitora:
- Connessione IB (stato, errori)
- Ultimo tick ES/SPX (timestamp, ritardo)
- Scrittura file (timestamp ultima riga)
- Status OI runner, RV script

---

## Config

File `settings.yaml` con parametri:
- `buffer`: 0.25
- `cooldown_seconds`: 30
- `breakout_window_minutes`: 5
- `strike_window_OI_points`: 100
- Path sorgenti/output

---

## Setup & Run

```bash
pip install -e .
python run_dashboard_FINAL_FREEZE.py
# Dashboard su http://127.0.0.1:8050
```

---

## Note Tecniche

### Regola Critica: NO SNAPSHOT IB!
```python
# snapshot=False SEMPRE! (gratis con sottoscrizione)
# snapshot=True VIETATO! ($0.01/richiesta)
# regulatorySnapshot=True VIETATO! ($0.03/richiesta)
```

### Thread Worker IB
Ogni thread con `IB()` deve avere:
```python
import asyncio
def ib_worker():
    asyncio.set_event_loop(asyncio.new_event_loop())
    # ... connect, reqMktData, ecc.
```
Mai `util.startLoop()` negli script (solo notebook Jupyter).

---

**SPEC_LOCKED: 11 febbraio 2026**
