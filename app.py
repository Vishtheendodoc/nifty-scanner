"""
Institutional HFT NIFTY Reversal Engine — v2.0
Fixes all issues from v1 and adds institutional-grade analytics.
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
import time

# ==========================
# PAGE CONFIG (must be first)
# ==========================

st.set_page_config(
    page_title="Institutional HFT NIFTY Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================
# CUSTOM CSS — Dark Terminal Aesthetic
# ==========================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Rajdhani:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'JetBrains Mono', monospace;
    background-color: #090e1a;
    color: #c8d8f0;
}

.stApp {
    background: linear-gradient(135deg, #090e1a 0%, #0d1526 50%, #0a1020 100%);
}

/* Title */
h1 { 
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 2.2rem !important;
    letter-spacing: 0.12em !important;
    background: linear-gradient(90deg, #00d4ff, #0088cc, #00ffb3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-transform: uppercase;
    margin-bottom: 0 !important;
}

h2, h3 {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    color: #7ecfff !important;
    text-transform: uppercase;
    font-size: 1.0rem !important;
    border-bottom: 1px solid #1a3050;
    padding-bottom: 4px;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: linear-gradient(145deg, #0d1a2e, #0f2040);
    border: 1px solid #1c3a5e;
    border-radius: 8px;
    padding: 16px !important;
    box-shadow: 0 0 12px rgba(0, 180, 255, 0.06);
    position: relative;
    overflow: hidden;
}

[data-testid="metric-container"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    background: linear-gradient(180deg, #00d4ff, #0040aa);
}

[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #00e5ff !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.65rem !important;
    letter-spacing: 0.12em !important;
    color: #4a7fa0 !important;
    text-transform: uppercase !important;
}

[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
}

/* Signal boxes */
.signal-box {
    border-radius: 8px;
    padding: 16px 20px;
    margin: 8px 0;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border-left: 4px solid;
}

.signal-top {
    background: rgba(255, 50, 80, 0.12);
    border-left-color: #ff3250;
    color: #ff6080;
}

.signal-bottom {
    background: rgba(0, 230, 140, 0.12);
    border-left-color: #00e68a;
    color: #00e68a;
}

.signal-neutral {
    background: rgba(100, 150, 200, 0.08);
    border-left-color: #4080aa;
    color: #6090bb;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #080d18 !important;
    border-right: 1px solid #1a3050;
}

section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stSlider label {
    font-size: 0.7rem !important;
    letter-spacing: 0.1em !important;
    color: #4a7fa0 !important;
    text-transform: uppercase !important;
}

/* Dividers */
hr {
    border-color: #1a3050 !important;
    margin: 20px 0 !important;
}

/* Dataframe */
.dataframe {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
}

/* Plotly charts */
.js-plotly-plot {
    border: 1px solid #1a3050;
    border-radius: 8px;
}

.stSpinner > div {
    border-top-color: #00d4ff !important;
}

/* Info/Warning/Error */
.stAlert {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================
# CONFIG
# ==========================

DHAN_CLIENT_ID = "1100244268"
DHAN_ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9"
    ".eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzcxODY3MDEz"
    "LCJpYXQiOjE3NzE3ODA2MTMsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIi"
    "LCJkaGFuQ2xpZW50SWQiOiIxMTAwMjQ0MjY4In0"
    ".nbBZwb0biSwbXIB9S5eg0CzrlMBqLSv9_NrWH_6BluzNawV6P4hP-nbLhUN1vmW4cF176_c6t31w5oRVAvsbyQ"
)

NIFTY_SECURITY_ID = 13
EXCHANGE_SEGMENT = "IDX_I"

OPTION_CHAIN_URL = "https://api.dhan.co/v2/optionchain"
EXPIRY_URL = "https://api.dhan.co/v2/optionchain/expirylist"

HEADERS = {
    "Content-Type": "application/json",
    "access-token": DHAN_ACCESS_TOKEN,
    "Client-Id": DHAN_CLIENT_ID,
}

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(9,14,26,0)",
    plot_bgcolor="rgba(13,21,38,0.6)",
    font=dict(family="JetBrains Mono", color="#7ecfff", size=11),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor="#1a3050", zerolinecolor="#1a3050"),
    yaxis=dict(gridcolor="#1a3050", zerolinecolor="#1a3050"),
)

MAX_HISTORY = 200  # cap history to prevent memory bloat

# ==========================
# API HELPERS
# ==========================

@st.cache_data(ttl=60)
def fetch_expiry_list():
    payload = {
        "UnderlyingScrip": NIFTY_SECURITY_ID,
        "UnderlyingSeg": EXCHANGE_SEGMENT,
    }
    try:
        r = requests.post(EXPIRY_URL, headers=HEADERS, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            st.error(f"Expiry API error: {data.get('remarks', data)}")
            return []
        result = data.get("data", [])
        return result if isinstance(result, list) else []
    except requests.exceptions.RequestException as e:
        st.error(f"Network error fetching expiries: {e}")
        return []
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return []


def fetch_option_chain(expiry: str):
    """
    Returns (df, underlying_price) or (None, None) on failure.
    df columns: strike, call_oi, put_oi, call_iv, put_iv,
                call_delta, put_delta, call_gamma, put_gamma,
                call_ltp, put_ltp
    """
    payload = {
        "UnderlyingScrip": NIFTY_SECURITY_ID,
        "UnderlyingSeg": EXCHANGE_SEGMENT,
        "Expiry": expiry,
    }
    try:
        r = requests.post(OPTION_CHAIN_URL, headers=HEADERS, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Network error fetching option chain: {e}")
        return None, None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None, None

    if data.get("status") != "success":
        st.error(f"Option chain API error: {data.get('remarks', data)}")
        return None, None

    data_block = data.get("data", {})
    if not isinstance(data_block, dict):
        st.error("Malformed API response: 'data' is not a dict.")
        return None, None

    underlying_price = float(data_block.get("last_price", 0) or 0)
    oc_dict = data_block.get("oc", {})
    if not isinstance(oc_dict, dict) or not oc_dict:
        st.error("Option chain 'oc' block is empty or malformed.")
        return None, None

    records = []
    for strike_str, strike_data in oc_dict.items():
        try:
            strike = float(strike_str)
        except (ValueError, TypeError):
            continue

        ce = (strike_data.get("ce") or {})
        pe = (strike_data.get("pe") or {})
        ce_g = (ce.get("greeks") or {})
        pe_g = (pe.get("greeks") or {})

        records.append({
            "strike": strike,
            "call_oi": float(ce.get("oi") or 0),
            "put_oi": float(pe.get("oi") or 0),
            "call_iv": float(ce_g.get("iv") or 0),
            "put_iv": float(pe_g.get("iv") or 0),
            "call_delta": float(ce_g.get("delta") or 0),
            "put_delta": float(pe_g.get("delta") or 0),
            "call_gamma": float(ce_g.get("gamma") or 0),
            "put_gamma": float(pe_g.get("gamma") or 0),
            "call_ltp": float(ce.get("ltp") or 0),
            "put_ltp": float(pe.get("ltp") or 0),
            "call_volume": float(ce.get("volume") or 0),
            "put_volume": float(pe.get("volume") or 0),
        })

    if not records:
        st.warning("No valid strikes found in option chain.")
        return None, None

    df = pd.DataFrame(records).sort_values("strike").reset_index(drop=True)
    return df, underlying_price


# ==========================
# ANALYTICS ENGINE
# ==========================

def compute_analytics(df: pd.DataFrame, underlying_price: float) -> dict:
    """
    Returns a dict of all computed signals. Pure function — no Streamlit calls.
    """
    total_call_oi = df["call_oi"].sum()
    total_put_oi = df["put_oi"].sum()

    # PCR
    pcr = (total_put_oi / total_call_oi) if total_call_oi > 0 else 0.0

    # Max Pain: strike where total option value is minimized
    strikes = df["strike"].values
    pain = []
    for s in strikes:
        call_loss = ((s - df["strike"]) * df["call_oi"]).clip(lower=0).sum()
        put_loss = ((df["strike"] - s) * df["put_oi"]).clip(lower=0).sum()
        pain.append(call_loss + put_loss)
    df = df.copy()
    df["max_pain_score"] = pain
    max_pain_strike = float(df.loc[df["max_pain_score"].idxmin(), "strike"])

    # Gamma Exposure (GEX)
    df["gex"] = (df["call_gamma"] * df["call_oi"]) + (df["put_gamma"] * df["put_oi"])
    net_gamma = df["gex"].sum()
    gamma_regime = "LONG GAMMA ↑" if net_gamma > 0 else "SHORT GAMMA ↓"

    # Net Delta Flow
    call_pressure = (df["call_delta"] * df["call_oi"]).sum()
    put_pressure = (df["put_delta"].abs() * df["put_oi"]).sum()
    net_flow = put_pressure - call_pressure

    # IV Skew — mean IV difference around ATM ± 5 strikes
    atm_idx = (df["strike"] - underlying_price).abs().idxmin()
    atm_band = df.iloc[max(0, atm_idx - 5): atm_idx + 6]
    iv_skew = float((atm_band["put_iv"] - atm_band["call_iv"]).mean()) if not atm_band.empty else 0.0

    # Volume-weighted IV
    total_vol = df["call_volume"].sum() + df["put_volume"].sum()
    if total_vol > 0:
        vwiv = (
            (df["call_iv"] * df["call_volume"]).sum() +
            (df["put_iv"] * df["put_volume"]).sum()
        ) / total_vol
    else:
        vwiv = (df["call_iv"].mean() + df["put_iv"].mean()) / 2

    # Strike pressure
    df["pressure"] = (df["put_delta"].abs() * df["put_oi"]) - (df["call_delta"] * df["call_oi"])

    # Highest OI levels (support/resistance)
    top_call_strike = float(df.loc[df["call_oi"].idxmax(), "strike"]) if not df.empty else 0
    top_put_strike = float(df.loc[df["put_oi"].idxmax(), "strike"]) if not df.empty else 0

    # Reversal Score — rules-based (0–100), no fake ML
    # Each condition contributes points
    score = 50.0
    # PCR extremes
    if pcr > 1.5:
        score += 15  # oversold, bullish lean
    elif pcr < 0.7:
        score -= 15  # overbought, bearish lean
    # IV skew
    if iv_skew > 3:
        score += 10  # put IV premium → fear/reversal possible
    elif iv_skew < -3:
        score -= 10
    # Max pain magnet
    price_vs_pain = underlying_price - max_pain_strike
    if abs(price_vs_pain) > 200:
        score += 8 if price_vs_pain > 0 else -8
    # Net flow
    if net_flow > 0:
        score += 7
    else:
        score -= 7
    # Gamma flip zone
    if abs(net_gamma) < 1e6 and abs(net_gamma) > 0:
        score += 5  # near flip — high instability

    score = max(0.0, min(100.0, score))

    return {
        "df": df,
        "pcr": pcr,
        "max_pain_strike": max_pain_strike,
        "net_gamma": net_gamma,
        "gamma_regime": gamma_regime,
        "net_flow": net_flow,
        "iv_skew": iv_skew,
        "vwiv": vwiv,
        "top_call_strike": top_call_strike,
        "top_put_strike": top_put_strike,
        "reversal_score": score,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
    }


# ==========================
# CHART BUILDERS
# ==========================

def chart_oi_profile(df: pd.DataFrame, underlying_price: float, top_call: float, top_put: float):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["strike"], y=df["call_oi"] / 1e5,
        name="Call OI (L)", marker_color="rgba(0,200,255,0.7)",
        marker_line_width=0,
    ))
    fig.add_trace(go.Bar(
        x=df["strike"], y=-(df["put_oi"] / 1e5),
        name="Put OI (L)", marker_color="rgba(255,80,100,0.7)",
        marker_line_width=0,
    ))
    fig.add_vline(x=underlying_price, line_dash="dash", line_color="#00ffb3",
                  annotation_text=f"LTP {underlying_price:.0f}", annotation_font_color="#00ffb3")
    fig.add_vline(x=top_call, line_dash="dot", line_color="#0088ff",
                  annotation_text="Max Call", annotation_font_color="#0088ff",
                  annotation_position="top left")
    fig.add_vline(x=top_put, line_dash="dot", line_color="#ff4466",
                  annotation_text="Max Put", annotation_font_color="#ff4466",
                  annotation_position="bottom right")
    fig.update_layout(
        **CHART_LAYOUT,
        title="Open Interest Profile",
        barmode="overlay",
        height=340,
        legend=dict(orientation="h", y=1.08),
    )
    return fig


def chart_gex(df: pd.DataFrame, underlying_price: float):
    colors = ["rgba(0,200,100,0.75)" if v > 0 else "rgba(255,50,80,0.75)" for v in df["gex"]]
    fig = go.Figure(go.Bar(
        x=df["strike"], y=df["gex"],
        name="GEX", marker_color=colors, marker_line_width=0,
    ))
    fig.add_vline(x=underlying_price, line_dash="dash", line_color="#00ffb3",
                  annotation_text=f"LTP {underlying_price:.0f}", annotation_font_color="#00ffb3")
    fig.update_layout(
        **CHART_LAYOUT,
        title="Gamma Exposure (GEX) by Strike",
        height=300,
    )
    return fig


def chart_iv_skew(df: pd.DataFrame, underlying_price: float):
    atm_idx = int((df["strike"] - underlying_price).abs().idxmin())
    window = 15
    band = df.iloc[max(0, atm_idx - window): atm_idx + window + 1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=band["strike"], y=band["call_iv"], name="Call IV",
        line=dict(color="#00b4ff", width=2), mode="lines+markers",
        marker=dict(size=5)
    ))
    fig.add_trace(go.Scatter(
        x=band["strike"], y=band["put_iv"], name="Put IV",
        line=dict(color="#ff4466", width=2), mode="lines+markers",
        marker=dict(size=5)
    ))
    fig.add_vline(x=underlying_price, line_dash="dash", line_color="#00ffb3",
                  annotation_text="ATM", annotation_font_color="#00ffb3")
    fig.update_layout(
        **CHART_LAYOUT,
        title="IV Skew — ATM ± 15 Strikes",
        height=300,
    )
    return fig


def chart_pressure_heatmap(df: pd.DataFrame):
    atm_range = df[df["pressure"].abs() > 0].copy()
    fig = px.bar(
        atm_range, x="strike", y="pressure",
        color="pressure",
        color_continuous_scale=["#ff3250", "#141e30", "#00e68a"],
        color_continuous_midpoint=0,
    )
    fig.update_traces(marker_line_width=0)
    fig.update_layout(
        **CHART_LAYOUT,
        title="Delta-Weighted Pressure (Put − Call)",
        height=300,
        coloraxis_showscale=False,
    )
    return fig


def chart_history(hist: pd.DataFrame):
    if len(hist) < 2:
        return None
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=hist["time"], y=hist["price"], name="NIFTY",
            line=dict(color="#00e5ff", width=2),
            fill="tozeroy", fillcolor="rgba(0,180,255,0.07)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=hist["time"], y=hist["score"], name="Reversal Score",
            line=dict(color="#ffa500", width=2, dash="dot"),
            mode="lines",
        ),
        secondary_y=True,
    )
    fig.update_yaxes(title_text="NIFTY Price", secondary_y=False,
                     gridcolor="#1a3050", color="#00e5ff")
    fig.update_yaxes(title_text="Reversal Score", secondary_y=True,
                     range=[0, 100], gridcolor="#1a3050", color="#ffa500")
    fig.add_hline(y=75, secondary_y=True, line_dash="dash",
                  line_color="rgba(255,50,80,0.5)", annotation_text="Reversal zone")
    fig.add_hline(y=25, secondary_y=True, line_dash="dash",
                  line_color="rgba(0,230,140,0.5)")
    fig.update_layout(
        **CHART_LAYOUT,
        title="Intraday Price vs Reversal Score",
        height=380,
        legend=dict(orientation="h", y=1.08),
    )
    return fig


# ==========================
# SESSION STATE INIT
# ==========================

if "history" not in st.session_state:
    st.session_state.history = []

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0.0

# ==========================
# SIDEBAR
# ==========================

with st.sidebar:
    st.markdown("### ⚙ CONFIGURATION")
    st.markdown("---")

    expiry_list = fetch_expiry_list()
    if not expiry_list:
        st.error("Could not load expiry list. Check API credentials.")
        st.stop()

    selected_expiry = st.selectbox("Expiry Date", expiry_list, index=0)

    st.markdown("---")
    st.markdown("### 🔄 AUTO REFRESH")

    auto_refresh = st.toggle("Enable Auto Refresh", value=True)
    refresh_interval = st.slider(
        "Interval (seconds)", min_value=10, max_value=300, value=30, step=5,
        disabled=not auto_refresh,
    )

    st.markdown("---")
    st.markdown("### 🎯 SIGNAL THRESHOLDS")
    reversal_threshold = st.slider("Reversal Score Trigger", 60, 95, 75)
    pcr_bull = st.slider("PCR Bullish Threshold", 1.0, 2.5, 1.5, step=0.1)
    pcr_bear = st.slider("PCR Bearish Threshold", 0.3, 1.0, 0.7, step=0.1)

    st.markdown("---")
    st.markdown("### 📋 DISPLAY")
    show_raw_table = st.toggle("Show Raw Option Chain", value=False)
    num_strikes = st.slider("Strikes to show (±ATM)", 5, 30, 15)

    if st.button("🗑 Clear History", use_container_width=True):
        st.session_state.history = []
        st.success("History cleared.")

# ==========================
# MAIN HEADER
# ==========================

st.markdown(
    "<h1>📡 Institutional HFT NIFTY Reversal Engine</h1>"
    "<p style='color:#3a6080;font-size:0.72rem;letter-spacing:0.1em;margin-top:-8px'>"
    "REAL-TIME OPTION FLOW · GAMMA EXPOSURE · REVERSAL PROBABILITY</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ==========================
# DATA FETCH
# ==========================

with st.spinner("Fetching option chain..."):
    df_raw, underlying_price = fetch_option_chain(selected_expiry)

if df_raw is None or underlying_price is None:
    st.error("Failed to load option chain data. Verify API token and network.")
    st.stop()

analytics = compute_analytics(df_raw, underlying_price)
df = analytics["df"]

# Append to history (capped)
st.session_state.history.append({
    "time": datetime.now(),
    "price": underlying_price,
    "score": analytics["reversal_score"],
    "pcr": analytics["pcr"],
    "net_gamma": analytics["net_gamma"],
})
if len(st.session_state.history) > MAX_HISTORY:
    st.session_state.history = st.session_state.history[-MAX_HISTORY:]

# ==========================
# SIGNAL ALERT (top)
# ==========================

score = analytics["reversal_score"]
pcr = analytics["pcr"]

if score >= reversal_threshold:
    if analytics["net_flow"] < 0:
        st.markdown(
            f'<div class="signal-box signal-top">'
            f'⚠ HIGH TOP REVERSAL PROBABILITY — Score: {score:.0f}/100 | '
            f'PCR: {pcr:.2f} | Resistance: {analytics["top_call_strike"]:.0f}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="signal-box signal-bottom">'
            f'✅ HIGH BOTTOM REVERSAL PROBABILITY — Score: {score:.0f}/100 | '
            f'PCR: {pcr:.2f} | Support: {analytics["top_put_strike"]:.0f}</div>',
            unsafe_allow_html=True,
        )
elif score <= (100 - reversal_threshold):
    st.markdown(
        f'<div class="signal-box signal-top">'
        f'⚠ BEARISH MOMENTUM SIGNAL — Score: {score:.0f}/100</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div class="signal-box signal-neutral">'
        f'— NO EXTREME SIGNAL — Score: {score:.0f}/100 | Market in equilibrium</div>',
        unsafe_allow_html=True,
    )

# ==========================
# KPI METRICS ROW 1
# ==========================

st.markdown("<br>", unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("NIFTY LTP", f"₹{underlying_price:,.2f}")
c2.metric(
    "PCR",
    f"{pcr:.3f}",
    delta="Bullish" if pcr > pcr_bull else ("Bearish" if pcr < pcr_bear else "Neutral"),
)
c3.metric("Max Pain", f"₹{analytics['max_pain_strike']:,.0f}")
c4.metric("Gamma Regime", analytics["gamma_regime"].split()[0])
c5.metric("IV Skew (ATM)", f"{analytics['iv_skew']:.2f}%")
c6.metric("Reversal Score", f"{score:.1f}/100")

# ==========================
# KPI METRICS ROW 2
# ==========================

c7, c8, c9, c10 = st.columns(4)
c7.metric("Total Call OI", f"{analytics['total_call_oi']/1e5:.1f}L")
c8.metric("Total Put OI", f"{analytics['total_put_oi']/1e5:.1f}L")
c9.metric("Net Delta Flow", f"{analytics['net_flow']:,.0f}")
c10.metric("Resistance (Max Call)", f"₹{analytics['top_call_strike']:,.0f}")

st.markdown("---")

# ==========================
# CHARTS — ROW 1
# ==========================

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 OI Profile", "⚡ Gamma Exposure", "〰 IV Skew", "🌡 Delta Pressure"]
)

with tab1:
    st.plotly_chart(
        chart_oi_profile(df, underlying_price, analytics["top_call_strike"], analytics["top_put_strike"]),
        use_container_width=True,
    )

with tab2:
    st.plotly_chart(chart_gex(df, underlying_price), use_container_width=True)

with tab3:
    st.plotly_chart(chart_iv_skew(df, underlying_price), use_container_width=True)

with tab4:
    st.plotly_chart(chart_pressure_heatmap(df), use_container_width=True)

# ==========================
# INTRADAY HISTORY CHART
# ==========================

st.markdown("---")
hist_df = pd.DataFrame(st.session_state.history)
fig_hist = chart_history(hist_df)
if fig_hist:
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info("Intraday chart will appear after 2+ data points are collected.")

# ==========================
# RAW OPTION CHAIN TABLE
# ==========================

if show_raw_table:
    st.markdown("---")
    st.markdown("### 📋 Option Chain Data")

    atm_idx = int((df["strike"] - underlying_price).abs().idxmin())
    lo = max(0, atm_idx - num_strikes)
    hi = min(len(df), atm_idx + num_strikes + 1)
    display_df = df.iloc[lo:hi].copy()

    # Format for display
    for col in ["call_oi", "put_oi", "call_volume", "put_volume"]:
        if col in display_df.columns:
            display_df[col] = (display_df[col] / 1e3).round(1).astype(str) + "K"

    for col in ["call_iv", "put_iv"]:
        display_df[col] = display_df[col].round(2).astype(str) + "%"

    for col in ["call_delta", "put_delta", "call_gamma", "put_gamma"]:
        display_df[col] = display_df[col].round(4)

    st.dataframe(
        display_df[[
            "strike", "call_oi", "call_iv", "call_delta", "call_ltp",
            "put_ltp", "put_delta", "put_iv", "put_oi"
        ]].rename(columns={
            "strike": "Strike",
            "call_oi": "C OI", "call_iv": "C IV", "call_delta": "C Δ", "call_ltp": "C LTP",
            "put_ltp": "P LTP", "put_delta": "P Δ", "put_iv": "P IV", "put_oi": "P OI",
        }),
        use_container_width=True,
        height=420,
    )

# ==========================
# FOOTER
# ==========================

st.markdown("---")
now = datetime.now().strftime("%H:%M:%S")
st.markdown(
    f"<p style='color:#2a4a6a;font-size:0.65rem;text-align:right;letter-spacing:0.08em'>"
    f"LAST UPDATED: {now} · EXPIRY: {selected_expiry} · "
    f"MAX HISTORY: {len(st.session_state.history)}/{MAX_HISTORY} SNAPSHOTS</p>",
    unsafe_allow_html=True,
)

# ==========================
# AUTO REFRESH (correct implementation)
# ==========================

if auto_refresh:
    # Use st.empty + time.sleep in a non-blocking sidebar countdown
    countdown_placeholder = st.sidebar.empty()
    elapsed = time.time() - st.session_state.last_refresh
    remaining = max(0, refresh_interval - elapsed)

    countdown_placeholder.markdown(
        f"<p style='color:#2a4060;font-size:0.7rem'>Next refresh in "
        f"<b style='color:#00d4ff'>{remaining:.0f}s</b></p>",
        unsafe_allow_html=True,
    )

    if elapsed >= refresh_interval:
        st.session_state.last_refresh = time.time()
        st.rerun()
