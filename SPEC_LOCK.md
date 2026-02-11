# SPEC_LOCK - Specifiche Bloccate

**Data blocco:** 11 febbraio 2026
**Versione:** RANGE_ENGINE_v1

Questo documento contiene tutte le specifiche "congelate" del sistema.
**NON MODIFICARE** senza aggiornare `MODEL_VERSION`.

---

## 1. Trade Date (Giorno di Mercato)

- **trade_date** = market date della sessione **02:15-22:00** Europe/Zurich
- Intervallo 00:00-02:14 appartiene alla sessione **precedente**
- Esempio: 01:00 del 12 marzo -> `trade_date = 2026-03-11`

## 2. Switch 0DTE

```python
if now_local >= 22:01:   # Europe/Zurich
    use next_calendar_expiry   # 0DTE domani
else:
    use today_expiry           # 0DTE oggi
```

## 3. VWAP ES (BLINDATO)

- Fonte: **SOLO** `ticker.vwap` da IB (tick 233 RTVolume)
- **MAI** ricalcolato
- Foto 10:00: aspetta fino a 10:05; se None -> anomaly, niente foto valida

## 4. SPX OPEN (BLINDATO)

- Fonte: primo prezzo SPX dopo 15:30 (**non** open candela daily)
- Una volta registrato: **CONGELATO** per tutta la giornata
- Fallback: marketPrice() -> midpoint() -> close -> "non disponibile"

## 5. Range Mattina (10:00-15:30)

- Base = VWAP ES IB (live)
- Foto 10:00: VWAP_ES, IV_daily, IV_straddle, range R1/R2/FIBO (immutabili)
- Live mattina: VWAP/IV in movimento, range dinamici

## 6. Range Pomeriggio (15:30-22:00)

- Base = SPX_OPEN_OFFICIAL (fisso)
- Foto 15:30 e 15:45: OPEN, IV, straddle, spread, range SPX + ES (immutabili)
- Live pomeriggio: OPEN fisso, IV/spread live, range aggiornati

## 7. Range Eventi

### Livelli tracciati
- BASE (CENTER)
- R1_UP, R1_DN
- R2_UP, R2_DN
- FIB_R1_UP, FIB_R1_DN
- FIB_R2_UP, FIB_R2_DN

### Parametri
- buffer: **0.25** punti ES
- cooldown: **30** secondi
- breakout_window: **5** minuti

### Definizioni
- Touch UP: `last >= livello + buffer`
- Touch DOWN: `last <= livello - buffer`
- Breakout: 5 minuti **consecutivi** (ogni campione 10s) oltre il livello
- Reject: ritorno oltre buffer opposto entro 5 minuti

## 8. ATM Straddle

- Strike grid: **5 punti**
- ATM: strike multiplo di 5 piu vicino a ES_last
- Ri-selezione: quando ES passa il midpoint fra strike -> ATM salta di 5
- Straddle: call_ask + put_ask

## 9. IV

```python
iv_raw = ticker.impliedVolatility  # tick 106, annuale
iv_annual_pct = iv_raw * 100 if iv_raw < 1.0 else iv_raw
iv_daily_pct = iv_annual_pct / sqrt(252)  # /15.8745
```

## 10. RV (Offline)

- Fonte: dati 1m esterni (Databento)
- 4 finestre:
  - RV_0215_2200
  - RV_1000_2200
  - RV_1000_1530
  - RV_1530_2200
- Percentili: 60, 120 giorni + full history

## 11. OI

- Fonte: file esterni (OI runner + OPRA)
- Finestra strike: +/- 100 punti
- Snapshot: 02:15, 10:00, 15:30, 22:00
- Delta OI: vs ieri + vs snapshot precedente

## 12. GEX

- Fonte: GEXBot daily profiles
- Output: zero_gamma, call_wall, put_wall, gamma_regime
- Un valore daily valido tutto il trade_date

## 13. Max/Min

- Finestra: **10:00-22:00** Europe/Zurich (unica)
- Campi: MAX_10_22, MIN_10_22, orari UTC e local

## 14. Versioning

Ogni CSV deve avere:
- `MODEL_VERSION` (es. "RANGE_ENGINE_v1")
- `CONFIG_HASH` (SHA256 del config)
- `ENGINE_START_TIME`

## 15. File Immutabili

- Dopo finalize 22:01: file **read-only**
- Correzioni: **solo rebuild da raw**, mai edit manuale

---

**MODIFICHE A QUESTO DOCUMENTO RICHIEDONO BUMP DI MODEL_VERSION**
