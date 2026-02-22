import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime
from sklearn.linear_model import LogisticRegression
import os
import time

# ==========================
# CONFIG
# ==========================

DHAN_CLIENT_ID = "1100244268"
DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzcxODY3MDEzLCJpYXQiOjE3NzE3ODA2MTMsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAwMjQ0MjY4In0.nbBZwb0biSwbXIB9S5eg0CzrlMBqLSv9_NrWH_6BluzNawV6P4hP-nbLhUN1vmW4cF176_c6t31w5oRVAvsbyQ"

NIFTY_SECURITY_ID = "13"  # Dhan Nifty index ID
EXCHANGE_SEGMENT = "IDX_I"
STRIKE_RANGE = 10
REFRESH_INTERVAL = 30

HEADERS = {
    'client-id': DHAN_CLIENT_ID,
    'access-token': DHAN_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

st.set_page_config(
    page_title="Institutional HFT NIFTY Scanner",
    layout="wide"
)

# ==========================
# DHAN OPTION CHAIN FETCH
# ==========================

def fetch_option_chain():

    url = "https://api.dhan.co/v2/optionchain"

    headers = HEADERS

    payload = {
        "UnderlyingScrip": NIFTY_SECURITY_ID,
        "UnderlyingSeg": EXCHANGE_SEGMENT,
        "Expiry": "expiry"  # ⚠️ CHANGE to current weekly expiry
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code != 200:
            st.error(f"Dhan API error: {response.text}")
            return None, None

        data = response.json()

        underlying_price = float(data["underlyingPrice"])

        records = []

        for strike_data in data["data"]:
            strike = strike_data["strikePrice"]

            ce = strike_data.get("CE", {})
            pe = strike_data.get("PE", {})

            records.append({
                "strike": strike,
                "call_oi": ce.get("openInterest", 0),
                "put_oi": pe.get("openInterest", 0),
                "call_iv": ce.get("impliedVolatility", 0),
                "put_iv": pe.get("impliedVolatility", 0),
                "call_delta": ce.get("delta", 0),
                "put_delta": pe.get("delta", 0),
                "call_gamma": ce.get("gamma", 0),
                "put_gamma": pe.get("gamma", 0)
            })

        df = pd.DataFrame(records)

        return df, underlying_price

    except Exception as e:
        st.error(f"Exception: {e}")
        return None, None

expiry = st.sidebar.text_input("Expiry (YYYY-MM-DD)", "2026-02-26")

# ==========================
# CORE MODELS
# ==========================

def calculate_gamma(df):
    df["gamma_exposure"] = (
        df["call_gamma"] * df["call_oi"] +
        df["put_gamma"] * df["put_oi"]
    )
    return df["gamma_exposure"].sum()


def calculate_net_flow(df):
    call_pressure = (df["call_delta"] * df["call_oi"]).sum()
    put_pressure = (df["put_delta"] * df["put_oi"]).sum()
    return put_pressure - call_pressure


def oi_acceleration(df):
    df["oi_diff"] = df["call_oi"].diff().fillna(0)
    slope = np.polyfit(range(len(df)), df["oi_diff"], 1)[0]
    return slope


def iv_trap_detector(df):
    iv_change = np.mean(df["call_iv"] + df["put_iv"])
    return iv_change > 25


# ==========================
# ML REVERSAL CLASSIFIER
# ==========================

def ml_reversal_probability(net_gamma, net_flow, oi_slope, iv_trap):
    X = np.array([[net_gamma, net_flow, oi_slope, int(iv_trap)]])
    y = np.array([0, 1])

    model = LogisticRegression()
    model.fit([[1,1,1,0],[0,0,0,1]], y)

    prob = model.predict_proba(X)[0][1]
    return prob * 100


# ==========================
# HEATMAP
# ==========================

def create_heatmap(df):
    df["pressure"] = (df["put_delta"] * df["put_oi"]) - (df["call_delta"] * df["call_oi"])

    fig = go.Figure(data=go.Heatmap(
        z=df["pressure"],
        x=df["strike"],
        y=["Pressure"] * len(df),
        colorscale="RdYlGn"
    ))

    fig.update_layout(height=250)
    return fig


# ==========================
# STREAMLIT DASHBOARD
# ==========================

st.title("🚀 Institutional HFT NIFTY Reversal Engine")

refresh = st.button("Refresh Now")

if "history" not in st.session_state:
    st.session_state.history = []

df, price = fetch_option_chain()

if df is not None:

    net_gamma = calculate_gamma(df)
    net_flow = calculate_net_flow(df)
    oi_slope = oi_acceleration(df)
    iv_trap = iv_trap_detector(df)
    reversal_prob = ml_reversal_probability(net_gamma, net_flow, oi_slope, iv_trap)

    gamma_regime = "LONG GAMMA" if net_gamma > 0 else "SHORT GAMMA"

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Underlying", f"{price}")
    col2.metric("Gamma Regime", gamma_regime)
    col3.metric("Net Flow", int(net_flow))
    col4.metric("Reversal Probability", f"{reversal_prob:.2f}%")

    st.markdown("---")

    # Heatmap
    st.subheader("Strike Pressure Heatmap")
    st.plotly_chart(create_heatmap(df), use_container_width=True)

    st.markdown("---")

    # Store history
    st.session_state.history.append({
        "time": datetime.now(),
        "price": price,
        "prob": reversal_prob
    })

    hist = pd.DataFrame(st.session_state.history)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["time"], y=hist["price"], name="Price"))
    fig.add_trace(go.Scatter(x=hist["time"], y=hist["prob"], name="Reversal %", yaxis="y2"))

    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right"),
        height=500
    )

    st.subheader("Intraday Reversal Chart")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    if reversal_prob > 80:
        if net_flow < 0:
            st.error("🔴 HIGH TOP PROBABILITY")
        else:
            st.success("🟢 HIGH BOTTOM PROBABILITY")
    else:
        st.info("No extreme reversal")


st.sidebar.header("⚙️ Settings")

refresh_interval = st.sidebar.slider(
    "Auto Refresh Interval (seconds)",
    min_value=5,
    max_value=120,
    value=30,
    step=5
)
# ---------------------------
# Safe Auto Refresh Logic
# ---------------------------

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > refresh_interval:
    st.session_state.last_refresh = time.time()
    st.rerun()
