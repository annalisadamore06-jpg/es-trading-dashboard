# DATA_CATALOG.md
## Catalogo Dati ES/SPX Trading Dashboard
**Versione**: 1.0 | **Data**: 2026-02-11

---

## 1. Directory Sorgenti

### 1.1 OPRA (Options Price Reporting Authority)
```
Path: C:\Users\annal\Desktop\OPRA
```
- **Contenuto**: Dati opzioni grezzi da OPRA feed
- **Formato**: `.csv.zst` (compressed zstandard)
- **Utilizzo**: OI (Open Interest), pricing opzioni

### 1.2 GEX / Databento
```
Path: C:\Users\annal\Desktop\GEX\quant-historical\data\ES_SPX\ES_SPX
```
- **Contenuto**: Dati storici ES/SPX da Databento
- **Formato**: `.dbn.zst` (Databento binary compressed)
- **Utilizzo**: OHLCV 1-minute, calcolo RV

---

## 2. Directory Output

### 2.1 Output Principale
```
Path: C:\Users\annal\Desktop\DATA
```
- **Contenuto**: CSV puliti e validati
- **Struttura**:
  ```
  DATA/
  ├── MASTER_OUTPUT/
  │   ├── MASTER_OUTPUT_2026_01.csv
  │   ├── MASTER_OUTPUT_2026_02.csv
  │   └── ...
  ├── ranges/
  │   ├── ranges_2026_01.csv
  │   └── ...
  ├── iv_rv/
  │   ├── iv_rv_2026_01.csv
  │   └── ...
  ├── oi/
  │   ├── oi_2026_01.csv
  │   └── ...
  └── gex/
      ├── gex_2026_01.csv
      └── ...
  ```

---

## 3. Formati File Input

### 3.1 CSV Zstandard (.csv.zst)
- **Decompressione**: `zstd -d file.csv.zst`
- **Python**: `pandas.read_csv("file.csv.zst", compression="zstd")`
- **Encoding**: UTF-8
- **Delimiter**: `,` (comma)

### 3.2 Databento Binary (.dbn.zst)
- **Libreria**: `databento` Python SDK
- **Decompressione**: automatica via SDK
- **Schema**: OHLCV-1m, trades, mbp-1

### 3.3 CSV Standard (.csv)
- **Encoding**: UTF-8
- **Delimiter**: `,` (comma)
- **Header**: sempre presente
- **Newline**: `\n` (Unix-style)

---

## 4. Formati File Output

### 4.1 MASTER_OUTPUT.csv
```csv
trade_date,vwap_es,spx_open,morning_high,morning_low,afternoon_high,afternoon_low,iv_atm,rv_overnight,rv_morning,rv_afternoon,rv_full,iv_percentile_60d,iv_percentile_120d,oi_call_max,oi_put_max,zero_gamma,call_wall,put_wall,gamma_regime,max_10_22,min_10_22,MODEL_VERSION,CONFIG_HASH,ENGINE_START_TIME
```

### 4.2 Schema Colonne

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| trade_date | DATE | YYYY-MM-DD (02:15-22:00 Zurich) |
| vwap_es | FLOAT | VWAP ES da IB tick 233 |
| spx_open | FLOAT | Primo prezzo SPX post-15:30, congelato |
| morning_high/low | FLOAT | Range mattina VWAP-based |
| afternoon_high/low | FLOAT | Range pomeriggio OPEN-based |
| iv_atm | FLOAT | IV ATM straddle 0DTE |
| rv_* | FLOAT | Realized Vol per finestra |
| iv_percentile_* | INT | Percentile 0-100 |
| oi_call_max/oi_put_max | INT | Strike con max OI |
| zero_gamma | FLOAT | Livello zero gamma |
| call_wall/put_wall | FLOAT | Muri gamma |
| gamma_regime | STRING | POSITIVE/NEGATIVE |
| max_10_22/min_10_22 | FLOAT | Estremi 10:00-22:00 Zurich |
| MODEL_VERSION | STRING | es. RANGE_ENGINE_v1 |
| CONFIG_HASH | STRING | SHA256 del config |
| ENGINE_START_TIME | DATETIME | Timestamp avvio engine |

---

## 5. Validazione Dati

### 5.1 Controlli Obbligatori
- [ ] trade_date univoco per file mensile
- [ ] vwap_es NOT NULL se sessione attiva
- [ ] spx_open NOT NULL dopo 15:30
- [ ] Range: high >= low sempre
- [ ] IV > 0 se calcolato
- [ ] CONFIG_HASH matching config attuale

### 5.2 Controlli Qualita'
- [ ] No duplicati per trade_date
- [ ] Continuita' date (no buchi trading days)
- [ ] RV coerente con IV (no outlier >3 sigma)
- [ ] OI strike entro ±100 da ATM

---

## 6. Note Importanti

1. **Pulizia da grezzi**: Ignorare dataset vecchi con value area sbagliata
2. **Append mensile**: Nuovi dati aggiunti a fine mese
3. **Read-only**: File finalizzati dopo 22:01 sono immutabili
4. **Backup**: Sync automatico OneDrive
5. **Versioning**: Ogni riga ha MODEL_VERSION e CONFIG_HASH
