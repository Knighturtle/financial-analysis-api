import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import os
import json
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="SEC XBRL AI Analyst",
    page_icon=None,
    layout="wide"
)

# === sidebar ===
st.sidebar.title("Financial Analyst")
st.sidebar.markdown("---")
ticker = st.sidebar.text_input("Ticker Symbol", value="AAPL").upper()
years = st.sidebar.slider("Analysis Years", min_value=1, max_value=10, value=4)
lang = st.sidebar.selectbox("Output Language", ["en", "ja"], index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("### Backend Status")
try:
    health = requests.get(f"{API_BASE_URL}/health", timeout=2)
    if health.status_code == 200:
        st.sidebar.success(f"API Connected: {API_BASE_URL}")
    else:
        st.sidebar.error(f"API Error: {health.status_code}")
except Exception as e:
    st.sidebar.error(f"API Disconnected: {e}")

# === Main ===
st.title(f"Financial Analysis: {ticker}")

col1, col2 = st.columns([1, 1])

with col1:
    fetch_btn = st.button("1. Fetch XBRL Data", type="primary", use_container_width=True)

with col2:
    analyze_btn = st.button("2. Run AI Analysis", type="primary", use_container_width=True)

# Session State for Data
if "metrics_data" not in st.session_state:
    st.session_state.metrics_data = None
if "ai_report" not in st.session_state:
    st.session_state.ai_report = None

# --- Action: Fetch Data ---
if fetch_btn:
    with st.spinner(f"Fetching SEC XBRL Company Facts for {ticker}..."):
        try:
            url = f"{API_BASE_URL}/sec/xbrl/metrics"
            params = {"ticker": ticker, "years": years}
            
            # Dev Info
            with st.expander("[Dev] API Request Details"):
                st.code(f"GET {url}\nParams: {params}", language="http")

            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.metrics_data = data
                st.success(f"Successfully retrieved {len(data.get('years', []))} years of data.")
            else:
                st.error(f"Failed to fetch data: {resp.text}")
                
        except Exception as e:
            st.error(f"Connection Error: {e}")

# --- Action: Analyze ---
if analyze_btn:
    if not st.session_state.metrics_data:
        st.warning("Please fetch XBRL data first.")
    else:
        with st.spinner(f"Running AI Analysis on Local LLM (This might take a moment)..."):
            try:
                url = f"{API_BASE_URL}/ai/analyze/xbrl"
                payload = {
                    "ticker": ticker,
                    "years": years,
                    "output_lang": lang
                }
                
                # Dev Info
                with st.expander("[Dev] AI Request Details"):
                    st.code(f"POST {url}\nBody: {json.dumps(payload, indent=2)}", language="json")

                resp = requests.post(url, json=payload, timeout=300)
                
                if resp.status_code == 200:
                    report = resp.json()
                    st.session_state.ai_report = report
                else:
                    st.error(f"AI Analysis Failed: {resp.text}")
            except Exception as e:
                st.error(f"AI Request Error: {e}")

# --- Visualization ---
if st.session_state.metrics_data:
    data = st.session_state.metrics_data
    years_list = sorted(data.get("years", []))
    annual_data = data.get("data", {})
    
    # Prepare DataFrame
    df_data = []
    for y in years_list:
        row = annual_data.get(str(y), {})
        row["year"] = y
        df_data.append(row)
    
    if df_data:
        df = pd.DataFrame(df_data)
        
        st.markdown("### Key Metrics Trend")
        
        # Tabs for charts
        tab1, tab2, tab3 = st.tabs(["Revenue & Net Income", "Margins (Net/ROE)", "Cash Flow"])
        
        with tab1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['year'], y=df['revenue'], name='Revenue', marker_color='#2E86C1'))
            fig.add_trace(go.Bar(x=df['year'], y=df['net_income'], name='Net Income', marker_color='#28B463'))
            fig.update_layout(title="Revenue vs Net Income", barmode='group')
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df['year'], y=df['net_margin'], name='Net Margin', mode='lines+markers', line=dict(color='#E74C3C')))
            fig.add_trace(go.Scatter(x=df['year'], y=df['roe'], name='ROE', mode='lines+markers', line=dict(color='#8E44AD')))
            fig.update_layout(title="Profitability Margins", yaxis_tickformat='.1%')
            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['year'], y=df['operating_cash_flow'], name='Operating CF', marker_color='#D35400'))
            fig.add_trace(go.Bar(x=df['year'], y=df['fcf'], name='Free Cash Flow', marker_color='#F39C12'))
            fig.update_layout(title="Cash Flow Analysis", barmode='group')
            st.plotly_chart(fig, use_container_width=True)

        with st.expander("View Raw XBRL Data (JSON)"):
            st.json(data)

# --- AI Report Display ---
if st.session_state.ai_report:
    report = st.session_state.ai_report
    st.markdown("### AI Analysis Report")
    
    # Display keys as sections
    if "executive_summary" in report:
        st.info(f"**Executive Summary**\n\n{report['executive_summary']}")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Key Metrics Commentary")
        st.write(report.get("key_metrics_commentary", "N/A"))
        
        st.markdown("#### Growth Drivers")
        st.write(report.get("growth_drivers", "N/A"))
        
    with c2:
        st.markdown("#### Risks Summary")
        st.warning(report.get("risks_summary", "N/A"))
        
        st.markdown("#### Red Flags")
        st.error(report.get("red_flags", "N/A"))

    with st.expander("[Dev] AI Response JSON"):
        st.json(report)
