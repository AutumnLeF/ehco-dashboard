from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records_fairmont.record_02 import render_record_02_view, parse_record_02_submissions
from records_fairmont.record_03 import render_record_03_view, parse_record_03_submissions, UNIT_CATALOG as FAIRMONT_UNITS, clean_unit_token
from records_fairmont.record_04 import render_record_04_view, parse_all_record_04_dishes

st.set_page_config(
    page_title="Fairmont Mumbai - EHCO Status",
    page_icon="🏨",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #0f172a; }
    .serif-title { font-size: 2.1rem; font-weight: 700; color: #0f172a; margin-bottom: 0.2rem; }
    .sub-head { font-size: 0.85rem; color: #475569; font-weight: 600; }
    .record-header-box { background-color: #0b192c; padding: 18px 24px; border-radius: 10px; color: white; margin-bottom: 1.5rem; font-size: 1.6rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

if st.sidebar.button("← Back to Landing Portal", use_container_width=True):
    st.switch_page("app.py")

st.sidebar.title("⚙️ Fairmont Controls")
st.sidebar.markdown("**Site:** Fairmont Mumbai (Site 2)")

ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
today = ist_now.date()
default_start_7d = today - timedelta(days=6)

date_selection = st.sidebar.date_input(
    "Audit Date Range (7 Days)",
    value=[default_start_7d, today],
    max_value=today,
    key="fairmont_date_picker"
)

selected_day_str = st.sidebar.selectbox(
    "Focus Day for Drill-down", options=[today.strftime("%d/%m/%Y")], key="fairmont_day_select"
)

FAIRMONT_FORM_MAPPING = {
    "🏠 Fairmont - EHCO Status Overview": 0,
    "RECORD 02 - FOOD DELIVERY RECORD": 23703,  # Fairmont Form ID from your network logs
    "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD": 31373,
    "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD": 31374,
}

if "fairmont_nav" not in st.session_state:
    st.session_state.fairmont_nav = "🏠 Fairmont - EHCO Status Overview"

selected_record = st.sidebar.selectbox(
    "SELECT FOOD SAFETY RECORD", 
    options=list(FAIRMONT_FORM_MAPPING.keys()), 
    key="fairmont_selectbox"
)

if selected_record != st.session_state.fairmont_nav:
    st.session_state.fairmont_nav = selected_record
    st.rerun()

active_form_id = FAIRMONT_FORM_MAPPING[st.session_state.fairmont_nav]

# Fairmont API Endpoint & Token Handling
fairmont_api_url = st.sidebar.text_input(
    "Endpoint URL", value="https://auth-api.blinkm.io/form-store", key="fairmont_endpoint"
)
token_input = st.sidebar.text_area("Bearer Token", value=st.secrets.get("auth_token", ""), height=90, key="fairmont_token_input")
clean_token = token_input.replace("Bearer ", "").strip()

def fetch_fairmont_submissions(url, token, form_id):
    if not form_id or form_id == 0 or not token:
        return []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://tehc-fairmont-mumbai.data-manager.oneblink.io",
        "Referer": "https://tehc-fairmont-mumbai.data-manager.oneblink.io/",
    }
    payload = {
        "formId": form_id,
        "paging": {"limit": 50, "offset": 0},
        "sorting": [{"property": "dateTimeSubmitted", "direction": "descending"}],
        "unwindRepeatableSets": True,
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            return data.get("submissions", []) if isinstance(data, dict) else data
    except Exception:
        pass
    return []

items = fetch_fairmont_submissions(fairmont_api_url, clean_token, active_form_id)
raw_records_df = pd.DataFrame({"raw_record": items}) if items else pd.DataFrame()

if st.session_state.fairmont_nav == "🏠 Fairmont - EHCO Status Overview":
    st.markdown(f"""
        <div style="margin-bottom: 1.5rem;">
            <div class="serif-title">Fairmont Mumbai - EHCO Status</div>
            <div class="sub-head">Site 2 Operations &nbsp;|&nbsp; Date: <b>{selected_day_str}</b></div>
        </div>
    """, unsafe_allow_html=True)
    st.success("Connected to Fairmont Mumbai data stream successfully.")
else:
    if st.button("← Back to Fairmont Overview"):
        st.session_state.fairmont_nav = "🏠 Fairmont - EHCO Status Overview"
        st.rerun()
    st.write("")
    
    if st.session_state.fairmont_nav == "RECORD 02 - FOOD DELIVERY RECORD":
        st.markdown(f'<div class="record-header-box">🚚 {st.session_state.fairmont_nav}</div>', unsafe_allow_html=True)
        render_record_02_view(raw_records_df, selected_day_str, default_start_7d, today)
    elif st.session_state.fairmont_nav == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
        st.markdown(f'<div class="record-header-box">❄️ {st.session_state.fairmont_nav}</div>', unsafe_allow_html=True)
        render_record_03_view(raw_records_df, selected_day_str, default_start_7d, today)
