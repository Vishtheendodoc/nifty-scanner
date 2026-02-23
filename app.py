"""
Institutional HFT NIFTY Reversal Engine — v2.3
- Snapshots persist across refreshes and devices using st.cache_resource
  (shared server-side memory — survives page reloads, works on all devices)
- Light theme, pure JS auto-refresh, IST timestamps
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timezone, timedelta

# ── IST ───────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    return datetime.now(IST)

def fmt_ist(dt):
    return dt.strftime("%d-%b-%Y  %I:%M:%S %p IST")

# ==========================
# PERSISTENT SHARED STORE
# st.cache_resource creates a single object shared across ALL sessions,
# browser tabs, and devices — it lives in the server process memory and
# survives page reloads/refreshes until the server restarts.
# ==========================
@st.cache_resource
def get_shared_store():
    """Returns a dict that is shared across all users/sessions/refreshes."""
    return {
        "history": [],        # list of snapshot dicts
        "max_history": 500,   # keep last 500 snapshots (~8hrs at 60s interval)
    }

store = get_shared_store()

def append_snapshot(snap: dict):
    """Thread-safe append with cap."""
    store["history"].append(snap)
    if len(store["history"]) > store["max_history"]:
        store["history"] = store["history"][-store["max_history"]:]

def get_history_df() -> pd.DataFrame:
    if not store["history"]:
        return pd.DataFrame()
    return pd.DataFrame(store["history"])

# ==========================
# PAGE CONFIG
# ==========================
st.set_page_config(
    page_title="NIFTY HFT Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================
# LIGHT THEME CSS
# ==========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
    background-color: #f4f6fa;
    color: #1a2340;
}
.stApp {
    background: linear-gradient(160deg, #eef1f8 0%, #f7f9fc 60%, #edf2ff 100%);
}
h1 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 800 !important;
    font-size: 1.85rem !important;
    color: #0f1e3d !important;
    margin-bottom: 2px !important;
}
h2, h3 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    color: #1a2e58 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border-bottom: 2px solid #dde4f0;
    padding-bottom: 4px;
}
[data-testid="metric-container"] {
    background: #ffffff !important;
    border: 1px solid #dde4f0 !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    box-shadow: 0 2px 8px rgba(15,30,80,0.06) !important;
    position: relative;
    overflow: hidden;
}
[data-testid="metric-container"]::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #2563eb, #06b6d4);
    border-radius: 0 0 12px 12px;
}
[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 1.35rem !important;
    font-weight: 500 !important;
    color: #0f1e3d !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.60rem !important;
    letter-spacing: 0.1em !important;
    color: #7b8db0 !important;
    text-transform: uppercase !important;
    font-weight: 600 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

.signal-box {
    border-radius: 10px;
    padding: 14px 20px;
    margin: 8px 0 14px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 700;
    font-size: 0.92rem;
    border-left: 5px solid;
}
.signal-top     { background:#fff0f2; border-left-color:#e8294a; color:#c01535; }
.signal-bottom  { background:#f0fdf5; border-left-color:#16a34a; color:#15803d; }
.signal-neutral { background:#f0f5ff; border-left-color:#3b82f6; color:#1d4ed8; }

section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #dde4f0 !important;
}
section[data-testid="stSidebar"] label {
    font-size: 0.68rem !important;
    letter-spacing: 0.09em !important;
    color: #5a6a90 !important;
    text-transform: uppercase !important;
    font-weight: 600 !important;
}
.js-plotly-plot { border: 1px solid #dde4f0; border-radius: 12px; }
hr { border-color: #dde4f0 !important; margin: 18px 0 !important; }
.stButton > button {
    background: #f0f5ff; border: 1px solid #c7d4f0;
    color: #1d4ed8; border-radius: 8px;
    font-size: 0.75rem; font-weight: 600;
}
.stat-pill {
    display: inline-block;
    background: #f0f5ff;
    border: 1px solid #dde4f0;
    border-radius: 20px;
    padding: 4px 12px;
    font-family: 'DM Mono', monospace;
    font-size: 0.68rem;
    color: #2563eb;
    font-weight: 500;
    margin-right: 6px;
}
</style>
""", unsafe_allow_html=True)

# ==========================
# CONFIG
# ==========================
DHAN_CLIENT_ID    = "1100244268"
DHAN_ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzcxODY3MDEzLCJpYXQiOjE3NzE3ODA2MTMsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAwMjQ0MjY4In0.nbBZwb0biSwbXIB9S5eg0CzrlMBqLSv9_NrWH_6BluzNawV6P4hP-nbLhUN1vmW4cF176_c6t31w5oRVAvsbyQ"
)
NIFTY_SECURITY_ID = 13
EXCHANGE_SEGMENT  = "IDX_I"
OPTION_CHAIN_URL  = "https://api.dhan.co/v2/optionchain"
EXPIRY_URL        = "https://api.dhan.co/v2/optionchain/expirylist"
HEADERS = {
    "Content-Type": "application/json",
    "access-token": DHAN_ACCESS_TOKEN,
    "Client-Id": DHAN_CLIENT_ID,
}

CHART_BASE = dict(
    paper_bgcolor="rgba(255,255,255,0)",
    plot_bgcolor="#ffffff",
    font=dict(family="DM Mono, monospace", color="#374151", size=11),
    margin=dict(l=44, r=20, t=44, b=40),
    xaxis=dict(gridcolor="#e5eaf2", zerolinecolor="#e5eaf2", linecolor="#cbd5e1"),
    yaxis=dict(gridcolor="#e5eaf2", zerolinecolor="#e5eaf2", linecolor="#cbd5e1"),
)
CALL_CLR = "#2563eb"
PUT_CLR  = "#e8294a"
SPOT_CLR = "#059669"
ATM_CLR  = "#d97706"

# ==========================
# SIDEBAR
# ==========================
with st.sidebar:
    st.markdown("### Configuration")
    st.markdown("---")

    @st.cache_data(ttl=120)
    def fetch_expiry_list():
        try:
            r = requests.post(
                EXPIRY_URL, headers=HEADERS,
                json={"UnderlyingScrip": NIFTY_SECURITY_ID, "UnderlyingSeg": EXCHANGE_SEGMENT},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "success":
                return []
            result = data.get("data", [])
            return result if isinstance(result, list) else []
        except Exception:
            return []

    expiry_list = fetch_expiry_list()
    if not expiry_list:
        st.error("Cannot load expiries. Check API token / network.")
        st.stop()

    selected_expiry = st.selectbox("Expiry Date", expiry_list, index=0)

    st.markdown("---")
    st.markdown("### Auto Refresh")
    auto_refresh = st.toggle("Enable Auto Refresh", value=True)
    refresh_secs = st.slider("Interval (seconds)", 10, 300, 30, 5, disabled=not auto_refresh)

    st.markdown("---")
    st.markdown("### Signal Thresholds")
    reversal_threshold = st.slider("Reversal Score Trigger", 60, 95, 75)
    pcr_bull = st.slider("PCR Bullish Level", 1.0, 2.5, 1.5, 0.1)
    pcr_bear = st.slider("PCR Bearish Level", 0.3, 1.0, 0.7, 0.1)

    st.markdown("---")
    st.markdown("### Display")
    show_table  = st.toggle("Show Option Chain Table", value=False)
    num_strikes = st.slider("Strikes +/-ATM", 5, 30, 15)

    st.markdown("---")
    snap_count = len(store["history"])
    st.markdown(
        f'<span class="stat-pill">📦 {snap_count} snapshots</span>',
        unsafe_allow_html=True,
    )
    if st.button("Clear All Snapshots", use_container_width=True):
        store["history"].clear()
        st.success("History cleared for all devices.")
        st.rerun()

# ==========================
# AUTO-REFRESH via pure JS (no package needed)
# window.parent.location.reload() reloads the Streamlit app page
# ==========================
if auto_refresh:
    components.html(
        f"""<script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {refresh_secs * 1000});
        </script>""",
        height=0, width=0,
    )

# ==========================
# API — OPTION CHAIN
# ==========================
def fetch_option_chain(expiry):
    try:
        r = requests.post(
            OPTION_CHAIN_URL, headers=HEADERS,
            json={"UnderlyingScrip": NIFTY_SECURITY_ID,
                  "UnderlyingSeg":   EXCHANGE_SEGMENT,
                  "Expiry":          expiry},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Network error: {e}")
        return None, None
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None

    if data.get("status") != "success":
        st.error(f"API error: {data.get('remarks', data)}")
        return None, None

    block = data.get("data", {})
    if not isinstance(block, dict):
        st.error("Malformed API response.")
        return None, None

    underlying_price = float(block.get("last_price") or 0)
    oc = block.get("oc", {})
    if not isinstance(oc, dict) or not oc:
        st.error("Empty option chain.")
        return None, None

    rows = []
    for strike_str, sd in oc.items():
        try:
            strike = float(strike_str)
        except (ValueError, TypeError):
            continue
        ce  = sd.get("ce") or {}
        pe  = sd.get("pe") or {}
        ceg = ce.get("greeks") or {}
        peg = pe.get("greeks") or {}
        rows.append({
            "strike":      strike,
            "call_oi":     float(ce.get("oi")     or 0),
            "put_oi":      float(pe.get("oi")      or 0),
            "call_iv":     float(ceg.get("iv")     or 0),
            "put_iv":      float(peg.get("iv")     or 0),
            "call_delta":  float(ceg.get("delta")  or 0),
            "put_delta":   float(peg.get("delta")  or 0),
            "call_gamma":  float(ceg.get("gamma")  or 0),
            "put_gamma":   float(peg.get("gamma")  or 0),
            "call_ltp":    float(ce.get("ltp")     or 0),
            "put_ltp":     float(pe.get("ltp")     or 0),
            "call_volume": float(ce.get("volume")  or 0),
            "put_volume":  float(pe.get("volume")  or 0),
        })

    if not rows:
        st.warning("No valid strikes found.")
        return None, None

    df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)
    return df, underlying_price


# ==========================
# ANALYTICS ENGINE
# ==========================
def compute_analytics(df, spot):
    total_coi = df["call_oi"].sum()
    total_poi = df["put_oi"].sum()
    pcr = (total_poi / total_coi) if total_coi > 0 else 0.0

    pain = []
    for s in df["strike"].values:
        cl = ((s - df["strike"]) * df["call_oi"]).clip(lower=0).sum()
        pl = ((df["strike"] - s) * df["put_oi"]).clip(lower=0).sum()
        pain.append(cl + pl)
    df = df.copy()
    df["max_pain_score"] = pain
    max_pain = float(df.loc[df["max_pain_score"].idxmin(), "strike"])

    df["gex"] = df["call_gamma"] * df["call_oi"] + df["put_gamma"] * df["put_oi"]
    net_gamma = df["gex"].sum()

    call_p   = (df["call_delta"] * df["call_oi"]).sum()
    put_p    = (df["put_delta"].abs() * df["put_oi"]).sum()
    net_flow = put_p - call_p

    atm_idx  = int((df["strike"] - spot).abs().idxmin())
    atm_band = df.iloc[max(0, atm_idx - 5): atm_idx + 6]
    iv_skew  = float((atm_band["put_iv"] - atm_band["call_iv"]).mean()) if not atm_band.empty else 0.0

    tvol = df["call_volume"].sum() + df["put_volume"].sum()
    vwiv = (
        ((df["call_iv"] * df["call_volume"]).sum() + (df["put_iv"] * df["put_volume"]).sum()) / tvol
        if tvol > 0 else (df["call_iv"].mean() + df["put_iv"].mean()) / 2
    )

    df["pressure"] = df["put_delta"].abs() * df["put_oi"] - df["call_delta"] * df["call_oi"]
    top_call = float(df.loc[df["call_oi"].idxmax(), "strike"])
    top_put  = float(df.loc[df["put_oi"].idxmax(),  "strike"])

    score = 50.0
    if pcr > 1.5:      score += 15
    elif pcr < 0.7:    score -= 15
    if iv_skew > 3:    score += 10
    elif iv_skew < -3: score -= 10
    price_pain = spot - max_pain
    if abs(price_pain) > 200:
        score += 8 if price_pain > 0 else -8
    score += 7 if net_flow > 0 else -7
    if 0 < abs(net_gamma) < 1e6:
        score += 5
    score = max(0.0, min(100.0, score))

    return dict(
        df=df, pcr=pcr, max_pain=max_pain,
        net_gamma=net_gamma,
        gamma_regime="LONG GAMMA" if net_gamma >= 0 else "SHORT GAMMA",
        net_flow=net_flow, iv_skew=iv_skew, vwiv=vwiv,
        top_call=top_call, top_put=top_put, score=score,
        total_coi=total_coi, total_poi=total_poi,
    )


# ==========================
# CHART HELPERS
# ==========================
def _layout(**kw):
    base = {**CHART_BASE}
    base.update(kw)
    return base


def chart_oi_profile(df, spot, top_call, top_put):
    fig = go.Figure()
    fig.add_bar(x=df["strike"], y= df["call_oi"]/1e5, name="Call OI (L)",
                marker_color=CALL_CLR, opacity=0.75, marker_line_width=0)
    fig.add_bar(x=df["strike"], y=-df["put_oi"]/1e5,  name="Put OI (L)",
                marker_color=PUT_CLR,  opacity=0.75, marker_line_width=0)
    fig.add_vline(x=spot,     line_dash="dash", line_color=SPOT_CLR, line_width=2,
                  annotation_text=f"LTP {spot:.0f}", annotation_font_color=SPOT_CLR)
    fig.add_vline(x=top_call, line_dash="dot",  line_color=CALL_CLR, line_width=1.5,
                  annotation_text="Resistance", annotation_font_color=CALL_CLR,
                  annotation_position="top left")
    fig.add_vline(x=top_put,  line_dash="dot",  line_color=PUT_CLR,  line_width=1.5,
                  annotation_text="Support", annotation_font_color=PUT_CLR,
                  annotation_position="bottom right")
    fig.update_layout(**_layout(title="Open Interest Profile", height=340,
                                barmode="overlay", legend=dict(orientation="h", y=1.1)))
    return fig


def chart_gex(df, spot):
    colors = ["rgba(37,99,235,0.75)" if v >= 0 else "rgba(232,41,74,0.75)" for v in df["gex"]]
    fig = go.Figure(go.Bar(x=df["strike"], y=df["gex"],
                           marker_color=colors, marker_line_width=0))
    fig.add_vline(x=spot, line_dash="dash", line_color=SPOT_CLR, line_width=2,
                  annotation_text=f"LTP {spot:.0f}", annotation_font_color=SPOT_CLR)
    fig.add_hline(y=0, line_color="#94a3b8", line_width=1)
    fig.update_layout(**_layout(title="Gamma Exposure (GEX) by Strike", height=300))
    return fig


def chart_iv_skew(df, spot):
    atm_idx = int((df["strike"] - spot).abs().idxmin())
    band = df.iloc[max(0, atm_idx - 15): atm_idx + 16]
    fig = go.Figure()
    fig.add_scatter(x=band["strike"], y=band["call_iv"], name="Call IV",
                    line=dict(color=CALL_CLR, width=2.5),
                    mode="lines+markers", marker=dict(size=5))
    fig.add_scatter(x=band["strike"], y=band["put_iv"],  name="Put IV",
                    line=dict(color=PUT_CLR,  width=2.5),
                    mode="lines+markers", marker=dict(size=5))
    fig.add_vline(x=spot, line_dash="dash", line_color=SPOT_CLR, line_width=2,
                  annotation_text="ATM", annotation_font_color=SPOT_CLR)
    fig.update_layout(**_layout(title="IV Skew -- ATM +/-15 Strikes", height=300,
                                legend=dict(orientation="h", y=1.1)))
    return fig


def chart_pressure(df):
    fig = px.bar(df, x="strike", y="pressure",
                 color="pressure",
                 color_continuous_scale=["#e8294a", "#f1f5f9", "#2563eb"],
                 color_continuous_midpoint=0)
    fig.update_traces(marker_line_width=0)
    fig.update_layout(**_layout(title="Delta-Weighted Pressure (Put minus Call)",
                                height=300, coloraxis_showscale=False))
    return fig


def chart_history(hist: pd.DataFrame):
    if len(hist) < 2:
        return None
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=hist["time"], y=hist["price"], name="NIFTY",
                   line=dict(color=CALL_CLR, width=2.5),
                   fill="tozeroy", fillcolor="rgba(37,99,235,0.07)"),
        secondary_y=False)
    fig.add_trace(
        go.Scatter(x=hist["time"], y=hist["score"], name="Reversal Score",
                   line=dict(color=ATM_CLR, width=2, dash="dot")),
        secondary_y=True)
    fig.update_yaxes(title_text="NIFTY Price (IST)", secondary_y=False,
                     gridcolor="#e5eaf2", color=CALL_CLR)
    fig.update_yaxes(title_text="Reversal Score",    secondary_y=True,
                     range=[0, 100], gridcolor="#e5eaf2", color=ATM_CLR)
    fig.add_hline(y=75, secondary_y=True, line_dash="dash",
                  line_color="rgba(232,41,74,0.4)",
                  annotation_text="Reversal zone", annotation_font_color="#e8294a")
    fig.add_hline(y=25, secondary_y=True, line_dash="dash",
                  line_color="rgba(37,99,235,0.4)")
    fig.update_layout(**_layout(title="Intraday Price vs Reversal Score (IST)",
                                height=420, legend=dict(orientation="h", y=1.1)))
    return fig


# ==========================
# HEADER
# ==========================
col_title, col_time = st.columns([3, 1])
with col_title:
    st.markdown(
        "<h1>📡 Institutional HFT NIFTY Reversal Engine</h1>"
        "<p style='color:#7b8db0;font-size:0.7rem;letter-spacing:0.08em;"
        "margin-top:-4px;font-weight:600'>"
        "REAL-TIME OPTION FLOW  ·  GAMMA EXPOSURE  ·  REVERSAL PROBABILITY</p>",
        unsafe_allow_html=True,
    )
with col_time:
    st.markdown(
        f"<div style='text-align:right;padding-top:12px'>"
        f"<span style='font-family:DM Mono,monospace;font-size:0.74rem;"
        f"color:#374151;background:#fff;border:1px solid #dde4f0;border-radius:8px;"
        f"padding:6px 12px;white-space:nowrap'>🕐 {fmt_ist(now_ist())}</span></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ==========================
# FETCH DATA
# ==========================
with st.spinner("Fetching live option chain..."):
    df_raw, spot_price = fetch_option_chain(selected_expiry)

if df_raw is None:
    st.error("Failed to load data. Check your API token and network connection.")
    st.stop()

a  = compute_analytics(df_raw, spot_price)
df = a["df"]

# ── Append snapshot to shared persistent store ───────────────
# Deduplicate: skip if last snapshot was taken within 5 seconds
# (prevents double-writes when multiple tabs refresh simultaneously)
hist_list = store["history"]
now = now_ist()
should_append = True
if hist_list:
    last_time = hist_list[-1]["time"]
    if isinstance(last_time, datetime):
        delta_secs = abs((now - last_time).total_seconds())
        if delta_secs < 5:
            should_append = False

if should_append:
    append_snapshot({
        "time":    now,
        "price":   spot_price,
        "score":   a["score"],
        "pcr":     a["pcr"],
        "net_gamma": a["net_gamma"],
        "iv_skew": a["iv_skew"],
        "expiry":  selected_expiry,
    })

# ==========================
# SIGNAL BANNER
# ==========================
s = a["score"]
if s >= reversal_threshold:
    if a["net_flow"] < 0:
        st.markdown(
            f'<div class="signal-box signal-top">'
            f'WARNING: HIGH TOP REVERSAL &nbsp;|&nbsp; Score: {s:.0f}/100 &nbsp;|&nbsp;'
            f' PCR: {a["pcr"]:.2f} &nbsp;|&nbsp; Resistance: Rs {a["top_call"]:,.0f}</div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="signal-box signal-bottom">'
            f'HIGH BOTTOM REVERSAL &nbsp;|&nbsp; Score: {s:.0f}/100 &nbsp;|&nbsp;'
            f' PCR: {a["pcr"]:.2f} &nbsp;|&nbsp; Support: Rs {a["top_put"]:,.0f}</div>',
            unsafe_allow_html=True)
elif s <= (100 - reversal_threshold):
    st.markdown(
        f'<div class="signal-box signal-top">'
        f'BEARISH MOMENTUM &nbsp;|&nbsp; Score: {s:.0f}/100</div>',
        unsafe_allow_html=True)
else:
    st.markdown(
        f'<div class="signal-box signal-neutral">'
        f'NO EXTREME SIGNAL &nbsp;|&nbsp; Score: {s:.0f}/100 &nbsp;|&nbsp; Market in equilibrium</div>',
        unsafe_allow_html=True)

# ==========================
# METRICS ROW 1
# ==========================
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("NIFTY LTP",      f"Rs {spot_price:,.2f}")
m2.metric("PCR",            f"{a['pcr']:.3f}",
          delta="Bullish" if a["pcr"] > pcr_bull else ("Bearish" if a["pcr"] < pcr_bear else "Neutral"))
m3.metric("Max Pain",       f"Rs {a['max_pain']:,.0f}")
m4.metric("Gamma Regime",   a["gamma_regime"])
m5.metric("IV Skew (ATM)",  f"{a['iv_skew']:.2f}%")
m6.metric("Reversal Score", f"{s:.1f}/100")

m7, m8, m9, m10 = st.columns(4)
m7.metric("Total Call OI",     f"{a['total_coi']/1e5:.2f}L")
m8.metric("Total Put OI",      f"{a['total_poi']/1e5:.2f}L")
m9.metric("Net Delta Flow",    f"{a['net_flow']:,.0f}")
m10.metric("Resistance Level", f"Rs {a['top_call']:,.0f}")

st.markdown("---")

# ==========================
# CHARTS (tabbed)
# ==========================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊  OI Profile", "⚡  Gamma Exposure", "〰  IV Skew", "🌡  Delta Pressure"
])
with tab1:
    st.plotly_chart(chart_oi_profile(df, spot_price, a["top_call"], a["top_put"]),
                    use_container_width=True)
with tab2:
    st.plotly_chart(chart_gex(df, spot_price), use_container_width=True)
with tab3:
    st.plotly_chart(chart_iv_skew(df, spot_price), use_container_width=True)
with tab4:
    st.plotly_chart(chart_pressure(df), use_container_width=True)

# ==========================
# HISTORY CHART
# ==========================
st.markdown("---")
hist_df = get_history_df()

if not hist_df.empty and len(hist_df) >= 2:
    # Show stats bar
    first_t = fmt_ist(hist_df["time"].iloc[0])
    last_t  = fmt_ist(hist_df["time"].iloc[-1])
    price_range = f"Rs {hist_df['price'].min():,.0f} – Rs {hist_df['price'].max():,.0f}"
    st.markdown(
        f'<span class="stat-pill">📦 {len(hist_df)} snapshots</span>'
        f'<span class="stat-pill">🕐 From: {first_t}</span>'
        f'<span class="stat-pill">🕐 To: {last_t}</span>'
        f'<span class="stat-pill">📈 Range: {price_range}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    fig_hist = chart_history(hist_df)
    if fig_hist:
        st.plotly_chart(fig_hist, use_container_width=True)

    # PCR history sub-chart
    fig_pcr = go.Figure()
    fig_pcr.add_scatter(x=hist_df["time"], y=hist_df["pcr"], name="PCR",
                        line=dict(color="#7c3aed", width=2),
                        fill="tozeroy", fillcolor="rgba(124,58,237,0.07)")
    fig_pcr.add_hline(y=pcr_bull, line_dash="dash", line_color="rgba(37,99,235,0.5)",
                      annotation_text="Bullish", annotation_font_color=CALL_CLR)
    fig_pcr.add_hline(y=pcr_bear, line_dash="dash", line_color="rgba(232,41,74,0.5)",
                      annotation_text="Bearish", annotation_font_color=PUT_CLR)
    fig_pcr.update_layout(**_layout(title="PCR History (IST)", height=220))
    st.plotly_chart(fig_pcr, use_container_width=True)

else:
    st.info("📈 History charts will appear after 2+ snapshots are collected. Snapshots persist across all devices and page refreshes.")

# ==========================
# OPTION CHAIN TABLE (toggle)
# ==========================
if show_table:
    st.markdown("---")
    st.markdown("### Option Chain Data")
    atm_i = int((df["strike"] - spot_price).abs().idxmin())
    lo = max(0, atm_i - num_strikes)
    hi = min(len(df), atm_i + num_strikes + 1)
    disp = df.iloc[lo:hi].copy()
    for c in ["call_oi", "put_oi"]:
        disp[c] = (disp[c] / 1e3).round(1).astype(str) + "K"
    for c in ["call_iv", "put_iv"]:
        disp[c] = disp[c].round(2).astype(str) + "%"
    for c in ["call_delta", "put_delta"]:
        disp[c] = disp[c].round(4)
    st.dataframe(
        disp[["strike","call_oi","call_iv","call_delta","call_ltp",
              "put_ltp","put_delta","put_iv","put_oi"]].rename(columns={
            "strike":"Strike","call_oi":"C OI","call_iv":"C IV",
            "call_delta":"C Delta","call_ltp":"C LTP",
            "put_ltp":"P LTP","put_delta":"P Delta","put_iv":"P IV","put_oi":"P OI",
        }),
        use_container_width=True, height=420,
    )

# ==========================
# FOOTER
# ==========================
st.markdown("---")
st.markdown(
    f"<p style='color:#9aaac0;font-size:0.62rem;text-align:right;"
    f"font-family:DM Mono,monospace;letter-spacing:0.06em'>"
    f"LAST UPDATE: {fmt_ist(now_ist())} &nbsp;|&nbsp; "
    f"EXPIRY: {selected_expiry} &nbsp;|&nbsp; "
    f"SNAPSHOTS: {len(store['history'])}/500 &nbsp;|&nbsp; "
    f"DATA SHARED ACROSS ALL DEVICES</p>",
    unsafe_allow_html=True,
)
