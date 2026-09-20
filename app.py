import os
import json
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import streamlit as st

# Import the Record 04 and Record 05 modules
from records.record_04 import render_record_04_view
from records.record_05 import render_record_05_view

st.set_page_config(
    page_title="Kitchen Safety Core",
    page_icon="🛡️",
    layout="wide"
)

# -------------------------------------------------------------
# 1. EDITORIAL STYLING
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #fcfbf9; font-family: 'Inter', sans-serif; color: #2b2b2b; }
    .serif-title { font-family: 'Newsreader', serif; font-size: 2.2rem; font-weight: 400; color: #1a1a1a; margin-bottom: 0.2rem; }
    .sub-head { font-size: 0.78rem; color: #8c8983; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 0.4rem; }
    .kpi-box { padding: 0.6rem 0; border-bottom: 1px solid #e8e5e0; }
    .kpi-num { font-family: 'Newsreader', serif; font-size: 2.2rem; font-weight: 500; line-height: 1.1; }
    .kpi-lbl { font-size: 0.72rem; color: #8c8983; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.2rem; }
    .kanban-col { background: #ffffff; border-radius: 12px; padding: 1.2rem; border: 1px solid #ede9e1; min-height: 420px; }
    .kanban-h { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; padding-bottom: 0.6rem; border-bottom: 1px solid #f2eee9; margin-bottom: 1rem; }
    .check-card { padding: 0.85rem; border-radius: 8px; background: #ffffff; border: 1px solid #ede9e1; margin-bottom: 0.6rem; }
</style>
""", unsafe_allow_html=True)

# Top Bar
st.markdown('<div class="sub-head">Today • Food-Safety Core</div>', unsafe_allow_html=True)

# Record Switcher
selected_record = st.selectbox(
    "SELECT FOOD SAFETY RECORD",
    [
        "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD",
        "RECORD 05 - COOLING OF FOOD RECORD"
    ]
)

# -------------------------------------------------------------
# 2. SIDEBAR CONTROLS & DATE RANGE
# -------------------------------------------------------------
st.sidebar.title("⚙️ Inspection Controls")

today = datetime.now(timezone.utc).date()
default_start = today - timedelta(days=14)

date_selection = st.sidebar.date_input(
    "Audit Date Range (10-15 Days)",
    value=[default_start, today],
    max_value=today
)

if isinstance(date_selection, (list, tuple)) and len(date_selection) == 2:
    start_date, end_date = date_selection
elif isinstance(date_selection, (list, tuple)) and len(date_selection) == 1:
    start_date = end_date = date_selection[0]
else:
    start_date = end_date = date_selection

delta_days = (end_date - start_date).days
day_options = [
    (start_date + timedelta(days=i)).strftime("%d/%m/%Y")
    for i in range(delta_days + 1)
]
selected_day_str = st.sidebar.selectbox(
    "Focus Day for Drill-down",
    options=list(reversed(day_options))
)

# Persistent inputs
if "saved_token" not in st.session_state:
    st.session_state.saved_token = ""

DEFAULT_TOKEN = "eyJraWQiOiJKSzRrMFBmRFlxT24zOGFIY0xHRis3NmZjWTIrU3R4a3d0VG1DSXBWYjJnPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6Ly9jb2duaXRvLWlkcC5hcC1zb3V0aGVhc3QtMi5hbWF6b25hd3MuY29tL2FwLXNvdXRoZWFzdC0yXzdrQXN6M24zeCIsIm1mYV9tZXRob2QiOiJOT19NRkFfRU5BQkxFRCIsImNvZ25pdG86dXNlcm5hbWUiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJvcmlnaW5fanRpIjoiZGJmM2RlZjQtNjk0OC00ODcxLTlkMTQtZDFiNzFhYTRlNDdjIiwiYXVkIjoiNHE3cDZpbmEzMTI3cWdnNGs0MG82Mm41bGsiLCJldmVudF9pZCI6IjdiN2ZiOGY2LTdjMjYtNGJjZi05ZGRhLTkwZGEyMTJjMGNiOCIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lIjoxNzg4NDMyMzMyLCJleHAiOjE3ODk5MDAzMDIsImlhdCI6MTc4OTg5NjcwMiwianRpIjoiYjM1MmE5Y2UtMjJmNS00NjY0LWFiZDEtODNjNjkxZWFhYmRjIiwiZW1haWwiOiJzYWhpbC5jaGF1aGFuMUBtb3JnYW5zb3JpZ2luYWxzLmNvbSJ9.RqTTBmZKZNOBrdzQIqZ-XZ6ZF2w_XbdGXT1ZEmhn7CiBz1-KsU-KJDW4jLUh3DUxIaCzBBZWQZoTbKvaOzMaX9kp3WdQaNjhwioQvkYcdhFAOt7DmCtQKpTsFLgKU_wKX9Q97XaKnfj6O6v6i7BFHRj23UN3YeeMU2N8KeadebEmfVRirbJ3kMWW-YFvRlVP7tRZezRnkMRiF8av_2yV3EGeUCIUzkh3yAs-SVB8FZhoEqVN5M30XpXMHhIaNiCzx8QlZyQamJxl641NyvaxdwP5B8dFL-zUU8OiBQzYM3NDbo84XorrjRaEisOXuChZuJ7GpHYcTiJDd2nQPXFzGQ"

api_url = st.sidebar.text_input("Endpoint URL", value="https://auth-api.blinkm.io/form-store")
token_input = st.sidebar.text_area("Bearer Token", value=DEFAULT_TOKEN, height=90) Bearer token here...")

if token_input:
    st.session_state.saved_token = token_input

sync_button = st.sidebar.button("🔄 Sync Live Feed", use_container_width=True)

# -------------------------------------------------------------
# 3. LIVE DATA FETCHER & RESPONSE DEBUGGER
# -------------------------------------------------------------
raw_records_df = pd.DataFrame()
api_status_code = None
api_response_text = ""

active_token = token_input.strip() or st.session_state.saved_token.strip()

if not active_token:
    st.warning("⚠️ No Bearer Token detected. Please paste your Cognito Bearer Token into the sidebar on the left.")
else:
    clean_token = active_token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    # Query parameters - pulling form 31374
    params = {"limit": 250, "formId": 31374}

    try:
        res = requests.get(api_url.strip(), headers=headers, params=params, timeout=15)
        api_status_code = res.status_code
        api_response_text = res.text

        if res.status_code == 200:
            payload = res.json()
            items = []
            if isinstance(payload, list):
                items = payload
            elif isinstance(payload, dict):
                items = (
                    payload.get("submissions")
                    or payload.get("records")
                    or payload.get("data")
                    or payload.get("items")
                    or []
                )
            if items:
                raw_records_df = pd.json_normalize(items)
                st.sidebar.success(f"✓ Retrieved {len(raw_records_df)} records")
            else:
                st.sidebar.warning("API returned 200 OK, but no submissions found inside payload.")
        else:
            st.sidebar.error(f"API Error HTTP {res.status_code}")
    except Exception as e:
        st.sidebar.error(f"Connection failed: {e}")

# -------------------------------------------------------------
# 4. ROUTE TO RECORD MODULES
# -------------------------------------------------------------
if selected_record == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
    st.markdown('<div class="serif-title">Record 04: Cooking & Reheating Shift Audit</div>', unsafe_allow_html=True)
    render_record_04_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 05 - COOLING OF FOOD RECORD":
    st.markdown('<div class="serif-title">Record 05: Blast Chiller & Cooling Audit</div>', unsafe_allow_html=True)
    render_record_05_view(raw_records_df)

else:
    st.info(f"Module for {selected_record} will load here.")

# -------------------------------------------------------------
# 5. DIAGNOSTIC PANEL
# -------------------------------------------------------------
st.divider()
st.subheader("🛠️ Raw Data Diagnostic")
st.write(f"**HTTP Status Code:** {api_status_code}")
st.write(f"**Total raw records loaded into DataFrame:** {len(raw_records_df)}")

if api_response_text:
    with st.expander("🔍 View Raw API Server Response", expanded=(len(raw_records_df) == 0)):
        st.code(api_response_text[:1000], language="json")

if not raw_records_df.empty:
    id_cols = [c for c in raw_records_df.columns if "formid" in c.lower()]
    date_cols = [c for c in raw_records_df.columns if "date" in c.lower() or "created" in c.lower()]
    st.write("Form ID columns found:", id_cols)
    st.write("Date columns found:", date_cols)
    cols_to_show = date_cols + id_cols
    if cols_to_show:
        st.dataframe(raw_records_df[cols_to_show].head(5), use_container_width=True)
