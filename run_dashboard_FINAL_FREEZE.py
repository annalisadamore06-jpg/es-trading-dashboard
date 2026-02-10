#!/usr/bin/env python3
"""
ES/SPX Trading Dashboard - FINAL FREEZE
Real-time options trading dashboard with Interactive Brokers integration.
Premium dark UI with glass-morphism design.
"""

# ============================================================================
# IMPORTS
# ============================================================================
from ib_insync import IB, util, Future, Index, FuturesOption
import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import pandas as pd
import math, csv, os, threading, datetime, logging, time
from collections import OrderedDict

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("dashboard")

# ============================================================================
# COSTANTI E CONFIG
# ============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 7496
CLIENT_ID = 30
DASH_HOST = "127.0.0.1"
DASH_PORT = 8050
UPDATE_SEC = 10
UPDATE_MS = 10000
RESELECT_POINTS = 10
SQRT_252 = 252 ** 0.5
FIB_UP = 1.618
FIB_DN = 0.618
T_1000 = (10, 0)
T_1530 = (15, 30)
T_1545 = (15, 45)

ORDER_KEYS = [
    "FIBO EST R1 UP",
    "FIBO EST R2 UP",
    "R1 UP",
    "R2 UP",
    "CENTER",
    "R2 DOWN",
    "R1 DOWN",
    "FIBO EST R2 DOWN",
    "FIBO EST R1 DOWN"
]

# ============================================================================
# GLOBAL STATE
# ============================================================================
STATE = {
    "es_last": None, "spx_last": None, "es_vwap_live": None,
    "spx_open_official": None, "spread_live": None,
    "iv_daily_pct_live": None, "iv_straddle_pct_live": None,
    "str_bid": None, "str_mid": None, "str_ask": None,
    "str_spread": None, "dvs": None, "pcr": None,
    "mode": "MORNING_ES_VWAP", "base_label_live": "VWAP",
    "base_live": None, "strike": None, "exchange": None,
    "expiry": None, "trading_class": None,
    "call_contract": None, "put_contract": None,
    "snap_1000": None, "snap_1530_spx": None, "snap_1530_es": None,
    "snap_1545_spx": None, "snap_1545_es": None,
    "live_panels": {},
    "log_rows": [],
    "connected": False, "last_update": None,
}

CSV_LOG = "live_log_10s.csv"
CSV_SNAP = "snapshots_fixed.csv"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def nn(v):
    """Return value if it's a valid number, else None."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None

def fmt(v, decimals=2):
    """Format number for display."""
    if v is None:
        return "---"
    return f"{v:,.{decimals}f}"

def fmt_pct(v):
    """Format percentage."""
    if v is None:
        return "---"
    return f"{v:.4f}%"

def time_ge(t_tuple):
    """Check if current CET time >= (hour, minute)."""
    now = datetime.datetime.now()
    return (now.hour, now.minute) >= t_tuple

def calc_ranges(base, iv_daily_frac, iv_straddle_frac):
    """Calculate R1, R2, FIBO ranges from base."""
    if base is None or iv_daily_frac is None or iv_straddle_frac is None:
        return {}
    r1_pts = base * iv_daily_frac
    r2_pts = base * iv_straddle_frac
    return OrderedDict([
        ("FIBO EST R1 UP", base + r1_pts * FIB_UP),
        ("FIBO EST R2 UP", base + r2_pts * FIB_UP),
        ("R1 UP", base + r1_pts),
        ("R2 UP", base + r2_pts),
        ("CENTER", base),
        ("R2 DOWN", base - r2_pts),
        ("R1 DOWN", base - r1_pts),
        ("FIBO EST R2 DOWN", base - r2_pts * FIB_DN),
        ("FIBO EST R1 DOWN", base - r1_pts * FIB_DN),
    ])

def to_es(x, spread):
    """Convert SPX level to ES level."""
    if x is None or spread is None:
        return None
    return x + spread

# ============================================================================
# CSV FUNCTIONS
# ============================================================================
def init_csv():
    """Initialize CSV files with headers if they don't exist."""
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp","mode","es_last","es_vwap_live","spx_last",
                         "spx_open_official","spread_live","iv_daily_pct_live",
                         "iv_straddle_pct_live","str_bid","str_mid","str_ask",
                         "str_spread","dvs","pcr"])
    if not os.path.exists(CSV_SNAP):
        with open(CSV_SNAP, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp","slot","date","base_label","base_value",
                         "spx_open_official","spread_fixed",
                         "iv_daily_pct_fixed","iv_straddle_pct_fixed",
                         "R1_UP","R2_UP","CENTER","R2_DN","R1_DN",
                         "FIB_R1_UP","FIB_R2_UP","FIB_R2_DN","FIB_R1_DN"])

def append_log_csv(row):
    """Append a row to the live log CSV."""
    with open(CSV_LOG, "a", newline="") as f:
        csv.writer(f).writerow(row)

def append_snap_csv(row):
    """Append a row to the snapshot CSV."""
    with open(CSV_SNAP, "a", newline="") as f:
        csv.writer(f).writerow(row)

  # ============================================================================
# IB WORKER (Thread 1)
# ============================================================================
def ib_worker():
    """Main IB data collection loop. Runs in a separate thread."""
    global STATE
    init_csv()
    today = datetime.date.today().strftime("%Y%m%d")
    snap_done = {"1000": False, "1530": False, "1545": False}
    anchor = None

    while True:
        try:
            ib = IB()
            ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, readonly=True)
            log.info("Connected to IB")
            STATE["connected"] = True

            # --- ES Future (front month) ---
            cds = ib.reqContractDetails(Future("ES", "", "CME"))
            cds = sorted(cds, key=lambda x: x.contract.lastTradeDateOrContractMonth)
            es = cds[0].contract
            ib.qualifyContracts(es)
            log.info(f"ES contract: {es.localSymbol}")

            # --- ES Market Data (VWAP + IV) ---
            t_es = ib.reqMktData(es, genericTickList="233,106", snapshot=False)

            # --- SPX Index ---
            spx = Index("SPX", "CBOE")
            ib.qualifyContracts(spx)
            t_spx = ib.reqMktData(spx, snapshot=False)

            # --- Options Chain 0DTE ---
            chains = ib.reqSecDefOptParams("ES", "CME", "FUT", es.conId)
            chain = next(c for c in chains if c.tradingClass == "E2B" and today in c.expirations)
            expiry = today
            STATE["expiry"] = expiry
            STATE["trading_class"] = chain.tradingClass
            log.info(f"0DTE chain: {chain.tradingClass} exp={expiry}")

            ib.sleep(2)

            # --- ATM Strike ---
            es_last = nn(t_es.last) or nn(t_es.close)
            if es_last is None:
                ib.sleep(5)
                es_last = nn(t_es.last) or nn(t_es.close)
            strike = min(chain.strikes, key=lambda k: abs(k - (es_last or 0)))
            anchor = es_last
            STATE["strike"] = strike

            # --- Options ATM ---
            tc, tp = None, None
            for exch in ("CME", "GLOBEX"):
                call = FuturesOption("ES", expiry, strike, "C", exch, tradingClass=chain.tradingClass)
                put = FuturesOption("ES", expiry, strike, "P", exch, tradingClass=chain.tradingClass)
                qc = ib.qualifyContracts(call, put)
                if qc:
                    tc = ib.reqMktData(call, genericTickList="101,106", snapshot=False)
                    tp = ib.reqMktData(put, genericTickList="101,106", snapshot=False)
                    STATE["exchange"] = exch
                    STATE["call_contract"] = str(call.localSymbol)
                    STATE["put_contract"] = str(put.localSymbol)
                    log.info(f"Options qualified on {exch}: strike={strike}")
                    break

            ib.sleep(3)

            # === MAIN DATA LOOP ===
            while ib.isConnected():
                ib.sleep(UPDATE_SEC)
                now = datetime.datetime.now()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")

                # --- Collect live data ---
                es_last = nn(t_es.last) or nn(t_es.close)
                es_vwap_live = nn(getattr(t_es, "vwap", None))
                spx_last = nn(t_spx.last)
                spread_live = (es_last - spx_last) if (es_last and spx_last) else None

                # --- SPX OPEN official (once after 15:30) ---
                spx_open_off = STATE["spx_open_official"]
                if spx_open_off is None and time_ge(T_1530):
                    spx_open_off = nn(t_spx.open)
                    if spx_open_off is None:
                        try:
                            bars = ib.reqHistoricalData(spx, endDateTime="",
                                durationStr="1 D", barSizeSetting="1 day",
                                whatToShow="TRADES", useRTH=True)
                            if bars:
                                spx_open_off = nn(bars[-1].open)
                        except Exception:
                            pass
                    if spx_open_off:
                        STATE["spx_open_official"] = spx_open_off
                        log.info(f"SPX OPEN official: {spx_open_off}")

                # --- IV% Daily (tick 106) ---
                iv_raw = nn(getattr(t_es, "impliedVolatility", None))
                iv_annual_pct = (iv_raw * 100.0) if (iv_raw and iv_raw < 1.0) else iv_raw
                iv_daily_pct = (iv_annual_pct / SQRT_252) if iv_annual_pct else None
                iv_daily_frac = (iv_daily_pct / 100.0) if iv_daily_pct else None

                # --- Straddle ATM ---
                call_bid = nn(tc.bid) if tc else None
                call_ask = nn(tc.ask) if tc else None
                put_bid = nn(tp.bid) if tp else None
                put_ask = nn(tp.ask) if tp else None
                call_mid = ((call_bid + call_ask) / 2.0) if (call_bid and call_ask) else None
                put_mid = ((put_bid + put_ask) / 2.0) if (put_bid and put_ask) else None
                str_bid = (call_bid + put_bid) if (call_bid and put_bid) else None
                str_ask = (call_ask + put_ask) if (call_ask and put_ask) else None
                str_mid = ((str_bid + str_ask) / 2.0) if (str_bid and str_ask) else None
                str_spread = (str_ask - str_bid) if (str_ask and str_bid) else None
                pcr = (put_mid / call_mid) if (put_mid and call_mid and call_mid != 0) else None

                # --- MODE ---
                mode = "MORNING_ES_VWAP"
                base_live = es_vwap_live
                base_label_live = "VWAP"
                if time_ge(T_1530) and spx_open_off not in (None, 0) and spread_live is not None:
                    mode = "AFTERNOON_SPX_OPEN"
                    base_live = spx_open_off
                    base_label_live = "OPEN"

                # --- IV% Straddle ---
                iv_straddle_pct = ((str_ask / base_live) * 100.0) if (str_ask and base_live) else None
                iv_straddle_frac = (iv_straddle_pct / 100.0) if iv_straddle_pct else None

                # --- DVS ---
                r1_pts_live = (base_live * iv_daily_frac) if (base_live and iv_daily_frac) else None
                dvs = ((str_mid / r1_pts_live) * 100.0) if (str_mid and r1_pts_live and r1_pts_live != 0) else None

                # --- RESELECT strike ---
                if es_last and anchor and abs(es_last - anchor) >= RESELECT_POINTS:
                    new_strike = min(chain.strikes, key=lambda k: abs(k - es_last))
                    if new_strike != strike:
                        strike = new_strike
                        anchor = es_last
                        STATE["strike"] = strike
                        ib.cancelMktData(tc.contract)
                        ib.cancelMktData(tp.contract)
                        for exch in ("CME", "GLOBEX"):
                            call = FuturesOption("ES", expiry, strike, "C", exch, tradingClass=chain.tradingClass)
                            put = FuturesOption("ES", expiry, strike, "P", exch, tradingClass=chain.tradingClass)
                            qc = ib.qualifyContracts(call, put)
                            if qc:
                                tc = ib.reqMktData(call, genericTickList="101,106", snapshot=False)
                                tp = ib.reqMktData(put, genericTickList="101,106", snapshot=False)
                                STATE["exchange"] = exch
                                log.info(f"Reselected ATM strike={strike}")
                                break

                # --- Live ranges ---
                live_ranges = calc_ranges(base_live, iv_daily_frac, iv_straddle_frac) if base_live else {}

                # --- Update STATE ---
                STATE.update({
                    "es_last": es_last, "spx_last": spx_last,
                    "es_vwap_live": es_vwap_live, "spread_live": spread_live,
                    "iv_daily_pct_live": iv_daily_pct, "iv_straddle_pct_live": iv_straddle_pct,
                    "str_bid": str_bid, "str_mid": str_mid, "str_ask": str_ask,
                    "str_spread": str_spread, "dvs": dvs, "pcr": pcr,
                    "mode": mode, "base_label_live": base_label_live,
                    "base_live": base_live, "last_update": now_str,
                    "live_panels": live_ranges,
                })

                # --- SNAPSHOT 10:00 ---
                if time_ge(T_1000) and not snap_done["1000"]:
                    if base_live and iv_daily_frac and iv_straddle_frac:
                        ranges = calc_ranges(base_live, iv_daily_frac, iv_straddle_frac)
                        STATE["snap_1000"] = {"base": base_live, "label": "VWAP",
                            "iv_daily": iv_daily_pct, "iv_straddle": iv_straddle_pct, "ranges": ranges}
                        append_snap_csv([now_str, "ES_10:00", today, "VWAP", base_live,
                            spx_open_off, spread_live, iv_daily_pct, iv_straddle_pct] +
                            [ranges.get(k) for k in ORDER_KEYS])
                        snap_done["1000"] = True
                        log.info("Snapshot 10:00 saved")

                # --- SNAPSHOT 15:30 ---
                if time_ge(T_1530) and not snap_done["1530"]:
                    if spx_open_off and spread_live and iv_daily_frac and iv_straddle_frac:
                        spx_ranges = calc_ranges(spx_open_off, iv_daily_frac, iv_straddle_frac)
                        STATE["snap_1530_spx"] = {"base": spx_open_off, "label": "OPEN",
                            "iv_daily": iv_daily_pct, "iv_straddle": iv_straddle_pct, "ranges": spx_ranges}
                        append_snap_csv([now_str, "SPX_15:30", today, "OPEN", spx_open_off,
                            spx_open_off, spread_live, iv_daily_pct, iv_straddle_pct] +
                            [spx_ranges.get(k) for k in ORDER_KEYS])
                        es_ranges = OrderedDict([(k, to_es(v, spread_live)) for k, v in spx_ranges.items()])
                        STATE["snap_1530_es"] = {"base": to_es(spx_open_off, spread_live), "label": "OPEN+SPR",
                            "iv_daily": iv_daily_pct, "iv_straddle": iv_straddle_pct, "ranges": es_ranges,
                            "spread": spread_live}
                        append_snap_csv([now_str, "ES_15:30", today, "OPEN+SPR",
                            to_es(spx_open_off, spread_live), spx_open_off, spread_live,
                            iv_daily_pct, iv_straddle_pct] + [es_ranges.get(k) for k in ORDER_KEYS])
                        snap_done["1530"] = True
                        log.info("Snapshot 15:30 saved")

                # --- SNAPSHOT 15:45 ---
                if time_ge(T_1545) and not snap_done["1545"]:
                    if spx_open_off and spread_live and iv_daily_frac and iv_straddle_frac:
                        spx_ranges = calc_ranges(spx_open_off, iv_daily_frac, iv_straddle_frac)
                        STATE["snap_1545_spx"] = {"base": spx_open_off, "label": "OPEN",
                            "iv_daily": iv_daily_pct, "iv_straddle": iv_straddle_pct, "ranges": spx_ranges}
                        append_snap_csv([now_str, "SPX_15:45", today, "OPEN", spx_open_off,
                            spx_open_off, spread_live, iv_daily_pct, iv_straddle_pct] +
                            [spx_ranges.get(k) for k in ORDER_KEYS])
                        es_ranges = OrderedDict([(k, to_es(v, spread_live)) for k, v in spx_ranges.items()])
                        STATE["snap_1545_es"] = {"base": to_es(spx_open_off, spread_live), "label": "OPEN+SPR",
                            "iv_daily": iv_daily_pct, "iv_straddle": iv_straddle_pct, "ranges": es_ranges,
                            "spread": spread_live}
                        append_snap_csv([now_str, "ES_15:45", today, "OPEN+SPR",
                            to_es(spx_open_off, spread_live), spx_open_off, spread_live,
                            iv_daily_pct, iv_straddle_pct] + [es_ranges.get(k) for k in ORDER_KEYS])
                        snap_done["1545"] = True
                        log.info("Snapshot 15:45 saved")

                # --- CSV Log ---
                log_row = [now_str, mode, es_last, es_vwap_live, spx_last,
                           spx_open_off, spread_live, iv_daily_pct, iv_straddle_pct,
                           str_bid, str_mid, str_ask, str_spread, dvs, pcr]
                append_log_csv(log_row)
                STATE["log_rows"].append(log_row)
                if len(STATE["log_rows"]) > 300:
                    STATE["log_rows"] = STATE["log_rows"][-300:]

        except Exception as e:
            log.error(f"IB Worker error: {e}")
            STATE["connected"] = False
            time.sleep(30)

# ============================================================================
# PREMIUM CSS STYLES
# ============================================================================
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-primary: #0a0e17;
    --bg-secondary: #111827;
    --bg-card: rgba(17, 24, 39, 0.8);
    --bg-glass: rgba(255, 255, 255, 0.03);
    --border-glass: rgba(255, 255, 255, 0.06);
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --accent-amber: #f59e0b;
    --accent-purple: #8b5cf6;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --glow-blue: 0 0 20px rgba(59, 130, 246, 0.15);
    --glow-green: 0 0 20px rgba(16, 185, 129, 0.15);
    --glow-red: 0 0 20px rgba(239, 68, 68, 0.15);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
}

/* Animated background gradient */
body::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(139,92,246,0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(6,182,212,0.05) 0%, transparent 50%);
    z-index: -1;
    animation: bgPulse 15s ease-in-out infinite alternate;
}

@keyframes bgPulse {
    0% { opacity: 0.6; }
    100% { opacity: 1; }
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}

.header {
    background: linear-gradient(135deg, rgba(17,24,39,0.95), rgba(17,24,39,0.8));
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border-glass);
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
}

.header-title {
    font-size: 20px;
    font-weight: 700;
    background: linear-gradient(135deg, #3b82f6, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
}

.header-status {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 12px;
    color: var(--text-secondary);
}

.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
    animation: pulse 2s infinite;
}

.status-dot.connected { background: var(--accent-green); box-shadow: 0 0 8px rgba(16,185,129,0.5); }
.status-dot.disconnected { background: var(--accent-red); box-shadow: 0 0 8px rgba(239,68,68,0.5); }

.mode-badge {
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.mode-morning {
    background: rgba(59,130,246,0.15);
    color: #60a5fa;
    border: 1px solid rgba(59,130,246,0.3);
}

.mode-afternoon {
    background: rgba(245,158,11,0.15);
    color: #fbbf24;
    border: 1px solid rgba(245,158,11,0.3);
}

.main-container {
    display: flex;
    gap: 16px;
    padding: 16px;
    min-height: calc(100vh - 56px);
}

.sidebar {
    width: 480px;
    min-width: 480px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    animation: slideIn 0.5s ease;
}

.panels-area {
    flex: 1;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-content: flex-start;
    animation: fadeIn 0.6s ease;
}

.card {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.3s ease;
}

.card:hover {
    border-color: rgba(59,130,246,0.2);
    box-shadow: var(--glow-blue);
}

.card-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.card-title::before {
    content: '';
    width: 3px; height: 14px;
    border-radius: 2px;
    background: linear-gradient(180deg, var(--accent-blue), var(--accent-cyan));
}

.metric-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}

.metric-row:last-child { border-bottom: none; }

.metric-label {
    font-size: 11px;
    color: var(--text-secondary);
    font-weight: 500;
}

.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
}

.metric-value.big {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
}

.metric-value.green { color: var(--accent-green); }
.metric-value.red { color: var(--accent-red); }
.metric-value.blue { color: var(--accent-blue); }
.metric-value.amber { color: var(--accent-amber); }
.metric-value.cyan { color: var(--accent-cyan); }
.metric-value.purple { color: var(--accent-purple); }

.panel-col {
    width: calc(12.5% - 9px);
    min-width: 140px;
    animation: fadeIn 0.5s ease;
}

.panel-card {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--border-glass);
    border-radius: 10px;
    overflow: hidden;
    transition: all 0.3s ease;
}

.panel-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--glow-blue);
    border-color: rgba(59,130,246,0.25);
}

.panel-header {
    padding: 10px 12px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    text-align: center;
    border-bottom: 1px solid var(--border-glass);
}

.panel-header.live {
    background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(6,182,212,0.1));
    color: var(--accent-green);
}

.panel-header.foto {
    background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(59,130,246,0.1));
    color: var(--accent-purple);
}

.panel-body { padding: 6px 0; }

.level-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    transition: background 0.2s;
}

.level-row:hover { background: rgba(255,255,255,0.03); }

.level-label {
    color: var(--text-muted);
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
}

.level-value { font-weight: 600; }
.level-up { color: var(--accent-green); }
.level-down { color: var(--accent-red); }
.level-center { color: var(--accent-cyan); font-weight: 700; }

.panel-footer {
    padding: 6px 10px;
    border-top: 1px solid var(--border-glass);
    font-size: 9px;
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
}

.log-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
}

.log-table thead th {
    position: sticky;
    top: 0;
    background: var(--bg-secondary);
    color: var(--text-muted);
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 6px 4px;
    text-align: right;
    border-bottom: 1px solid var(--border-glass);
}

.log-table thead th:first-child { text-align: left; }

.log-table tbody td {
    padding: 4px;
    text-align: right;
    color: var(--text-secondary);
    border-bottom: 1px solid rgba(255,255,255,0.02);
}

.log-table tbody td:first-child {
    text-align: left;
    color: var(--text-muted);
}

.log-table tbody tr:hover td {
    background: rgba(59,130,246,0.05);
    color: var(--text-primary);
}

.log-scroll {
    max-height: 340px;
    overflow-y: auto;
    border-radius: 8px;
}

.log-scroll::-webkit-scrollbar { width: 4px; }
.log-scroll::-webkit-scrollbar-track { background: transparent; }
.log-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

.tag-live {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 700;
    background: rgba(16,185,129,0.15);
    color: var(--accent-green);
    border: 1px solid rgba(16,185,129,0.3);
}

.tag-foto {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 700;
    background: rgba(139,92,246,0.15);
    color: var(--accent-purple);
    border: 1px solid rgba(139,92,246,0.3);
}
"""

# ============================================================================
# DASH LAYOUT HELPERS
# ============================================================================
def make_metric(label, value, cls=""):
    """Create a metric row for sidebar cards."""
    return html.Div(className="metric-row", children=[
        html.Span(label, className="metric-label"),
        html.Span(str(value), className=f"metric-value {cls}")
    ])

def make_panel(title, panel_type, snap_data, base_label=""):
    """Create a range panel column (LIVE or FOTO)."""
    is_live = (panel_type == "LIVE")
    header_cls = "panel-header live" if is_live else "panel-header foto"
    tag = html.Span("LIVE" if is_live else "FOTO", className="tag-live" if is_live else "tag-foto")

    if snap_data and isinstance(snap_data, dict) and "ranges" in snap_data:
        ranges = snap_data["ranges"]
        iv_d = snap_data.get("iv_daily")
        iv_s = snap_data.get("iv_straddle")
    elif isinstance(snap_data, OrderedDict):
        ranges = snap_data
        iv_d = STATE.get("iv_daily_pct_live")
        iv_s = STATE.get("iv_straddle_pct_live")
    else:
        ranges = {}
        iv_d = None
        iv_s = None

    level_rows = []
    for key in ORDER_KEYS:
        val = ranges.get(key)
        if "UP" in key:
            cls = "level-up"
        elif "DOWN" in key:
            cls = "level-down"
        else:
            cls = "level-center"
        short = key.replace("FIBO EST ", "F.").replace(" UP", "").replace(" DOWN", "")
        level_rows.append(html.Div(className="level-row", children=[
            html.Span(short, className="level-label"),
            html.Span(fmt(val), className=f"level-value {cls}")
        ]))

    return html.Div(className="panel-col", children=[
        html.Div(className="panel-card", children=[
            html.Div(className=header_cls, children=[title, " ", tag]),
            html.Div(className="panel-body", children=level_rows),
            html.Div(className="panel-footer", children=[
                html.Span(f"IV% {fmt_pct(iv_d)}"),
                html.Span(f"STR {fmt_pct(iv_s)}")
            ])
        ])
    ])

def make_log_table(rows):
    """Create the log table from recent rows."""
    headers = ["TIME", "VWAP", "IV%", "IV% STR", "DVS", "STR ASK", "STR BID", "STR SPR", "P/C", "MODE"]
    thead = html.Thead(html.Tr([html.Th(h) for h in headers]))
    tbody_rows = []
    display_rows = list(reversed(rows[-40:])) if rows else []
    for r in display_rows:
        if len(r) >= 15:
            cells = [
                html.Td(r[0][-8:] if r[0] else "---"),
                html.Td(fmt(r[3])),
                html.Td(fmt_pct(r[7])),
                html.Td(fmt_pct(r[8])),
                html.Td(fmt(r[13])),
                html.Td(fmt(r[11])),
                html.Td(fmt(r[9])),
                html.Td(fmt(r[12])),
                html.Td(fmt(r[14])),
                html.Td(r[1] if r[1] else "---")
            ]
            tbody_rows.append(html.Tr(cells))
    tbody = html.Tbody(tbody_rows)
    return html.Table(className="log-table", children=[thead, tbody])

# ============================================================================
# DASH APP
# ============================================================================
app = dash.Dash(__name__, title="ES Trading Dashboard")
app.index_string = '''<!DOCTYPE html>
<html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<style>''' + CSS + '''</style></head>
<body>{%app_entry%}{%config%}{%scripts%}{%renderer%}</body></html>'''

app.layout = html.Div([
    # --- HEADER ---
    html.Div(className="header", children=[
        html.Div("ES / SPX Trading Dashboard", className="header-title"),
        html.Div(className="header-status", id="header-status")
    ]),
    # --- MAIN ---
    html.Div(className="main-container", children=[
        # --- SIDEBAR ---
        html.Div(className="sidebar", id="sidebar"),
        # --- PANELS ---
        html.Div(className="panels-area", id="panels-area")
    ]),
    # --- INTERVAL ---
    dcc.Interval(id="interval", interval=UPDATE_MS, n_intervals=0)
])


@app.callback(
    [Output("header-status", "children"),
     Output("sidebar", "children"),
     Output("panels-area", "children")],
    [Input("interval", "n_intervals")]
)
def update_ui(n):
    s = STATE

    # === HEADER STATUS ===
    conn_cls = "status-dot connected" if s["connected"] else "status-dot disconnected"
    conn_txt = "Connected" if s["connected"] else "Disconnected"
    mode = s.get("mode", "---")
    mode_cls = "mode-badge mode-morning" if "MORNING" in mode else "mode-badge mode-afternoon"
    mode_short = "AM - VWAP" if "MORNING" in mode else "PM - OPEN"

    header = [
        html.Span([html.Span(className=conn_cls), conn_txt]),
        html.Span(mode_short, className=mode_cls),
        html.Span(f"Updated: {s.get('last_update', '---')}")
    ]

    # === SIDEBAR ===
    # Card 1: MERCATO LIVE
    market_card = html.Div(className="card", children=[
        html.Div("Mercato Live", className="card-title"),
        html.Div(style={"display": "flex", "gap": "20px", "marginBottom": "10px"}, children=[
            html.Div([
                html.Div("ES", style={"fontSize": "10px", "color": "#64748b", "marginBottom": "2px"}),
                html.Div(fmt(s["es_last"]), className="metric-value big cyan")
            ]),
            html.Div([
                html.Div("SPX", style={"fontSize": "10px", "color": "#64748b", "marginBottom": "2px"}),
                html.Div(fmt(s["spx_last"]), className="metric-value big blue")
            ])
        ]),
        make_metric("VWAP (ES)", fmt(s["es_vwap_live"]), "green"),
        make_metric("OPEN (SPX)", fmt(s["spx_open_official"]), "amber"),
        make_metric("SPREAD", fmt(s["spread_live"]), "purple"),
        make_metric("ATM Strike", fmt(s["strike"], 0), "cyan"),
        make_metric("Exchange", s.get("exchange", "---")),
        make_metric("Expiry", s.get("expiry", "---")),
        make_metric("TradingClass", s.get("trading_class", "---")),
    ])

    # Card 2: VOLATILITA LIVE
    vol_card = html.Div(className="card", children=[
        html.Div("Volatilita Live", className="card-title"),
        make_metric("IV% Daily", fmt_pct(s["iv_daily_pct_live"]), "amber"),
        make_metric("IV% Straddle", fmt_pct(s["iv_straddle_pct_live"]), "purple"),
        make_metric("STR ASK", fmt(s["str_ask"]), "red"),
        make_metric("STR BID", fmt(s["str_bid"]), "green"),
        make_metric("STR MID", fmt(s["str_mid"]), "cyan"),
        make_metric("STR Spread", fmt(s["str_spread"])),
        make_metric("DVS", fmt(s["dvs"]), "amber"),
        make_metric("P/C Ratio", fmt(s["pcr"])),
        make_metric("MODE", s.get("mode", "---"), "blue"),
    ])

    # Card 3: LOG
    log_card = html.Div(className="card", style={"flex": "1", "overflow": "hidden"}, children=[
        html.Div("Log (10s)", className="card-title"),
        html.Div(className="log-scroll", children=[make_log_table(s["log_rows"])])
    ])

    sidebar = [market_card, vol_card, log_card]

    # === 8 PANELS ===
    live_ranges = s.get("live_panels", {})
    es_live_pm_ranges = OrderedDict()
    if live_ranges and s.get("spread_live") and s.get("mode") == "AFTERNOON_SPX_OPEN":
        for k, v in live_ranges.items():
            es_live_pm_ranges[k] = v

    panels = [
        make_panel("ES 10:00", "FOTO", s.get("snap_1000")),
        make_panel("ES LIVE AM", "LIVE", live_ranges if "MORNING" in s.get("mode","") else {}),
        make_panel("SPX LIVE", "LIVE", live_ranges if "AFTERNOON" in s.get("mode","") else {}),
        make_panel("SPX 15:30", "FOTO", s.get("snap_1530_spx")),
        make_panel("ES 15:30", "FOTO", s.get("snap_1530_es")),
        make_panel("SPX 15:45", "FOTO", s.get("snap_1545_spx")),
        make_panel("ES 15:45", "FOTO", s.get("snap_1545_es")),
        make_panel("ES LIVE PM", "LIVE", es_live_pm_ranges if es_live_pm_ranges else live_ranges),
    ]

    return header, sidebar, panels


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    log.info("Starting ES Trading Dashboard...")
    t = threading.Thread(target=ib_worker, daemon=True)
    t.start()
    log.info(f"Dashboard: http://{DASH_HOST}:{DASH_PORT}")
    app.run(host=DASH_HOST, port=DASH_PORT, debug=False)
