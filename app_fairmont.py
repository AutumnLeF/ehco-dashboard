from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

# Import from the duplicated Fairmont records folder
from records_fairmont.record_02 import render_record_02_view, parse_record_02_submissions
from records_fairmont.record_03 import render_record_03_view, parse_record_03_submissions, UNIT_CATALOG as FAIRMONT_UNIT_CATALOG, clean_unit_token
from records_fairmont.record_04 import render_record_04_view, parse_all_record_04_dishes
from records_fairmont.record_05 import render_record_05_view, parse_record_05_submissions
from records_fairmont.record_06 import render_record_06_view, parse_record_06_submissions
from records_fairmont.record_12 import render_record_12_view
from records_fairmont.record_13 import render_record_13_view, parse_record_13_submissions
from records_fairmont.record_15 import render_record_15_view, parse_record_15_submissions
from records_fairmont.record_21 import render_record_21_view, parse_record_21_submissions
from records_fairmont.record_25 import render_record_25_view, parse_record_25_submissions

st.set_page_config(
    page_title="Fairmont Mumbai - EHCO Status",
    page_icon="🏨",
    layout="wide",
)

# -------------------------------------------------------------
# FAIRMONT STYLING & ROUTING SETUP
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #0f172a; }
    .serif-title { font-size: 2.1rem; font-weight: 700; color: #0f172a; margin-bottom: 0.2rem; }
    .sub-head { font-size: 0.85rem; color: #475569; font-weight: 600; }
    .record-header-box { background-color: #0b192c; padding: 18px 24px; border-radius: 10px; color: white; margin-bottom: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-size: 1.6rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

FAIRMONT_FORM_MAPPING = {
    "🏠 Fairmont - EHCO Status Overview": 0,
    "RECORD 02 - FOOD DELIVERY RECORD": 0, # Update with Fairmont Form ID
    "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD": 0,
    "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD": 0,
    "RECORD 05 - COOLING OF FOOD RECORD": 0,
    "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD": 0,
    "RECORD 12 - DEFROSTING TEMPERATURE RECORD": 0,
    "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD": 0,
    "RECORD 15 - PESTICIDE USAGE RECORD": 0,
    "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH": 0,
    "RECORD 25 - ICE MACHINE CLEANING RECORD": 0,
}

if "fairmont_nav_choice" not in st.session_state:
    st.session_state.fairmont_nav_choice = "🏠 Fairmont - EHCO Status Overview"

def go_to_portal():
    st.session_state.current_site = "portal"
    st.rerun()

st.sidebar.title("⚙️ Fairmont Controls")
if st.sidebar.button("← Return to Site Portal", use_container_width=True, on_click=go_to_portal):
    pass

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

nav_options = list(FAIRMONT_FORM_MAPPING.keys())
current_nav_index = nav_options.index(st.session_state.fairmont_nav_choice) if st.session_state.fairmont_nav_choice in nav_options else 0

selected_record = st.sidebar.selectbox(
    "SELECT FOOD SAFETY RECORD", 
    options=nav_options, 
    index=current_nav_index,
    key="fairmont_nav_selectbox"
)

if selected_record != st.session_state.fairmont_nav_choice:
    st.session_state.fairmont_nav_choice = selected_record
    st.rerun()

active_form_id = FAIRMONT_FORM_MAPPING[st.session_state.fairmont_nav_choice]

if st.session_state.fairmont_nav_choice == "🏠 Fairmont - EHCO Status Overview":
    st.markdown(f"""
        <div style="margin-bottom: 1.5rem;">
            <div class="serif-title">Fairmont Mumbai - EHCO Status</div>
            <div class="sub-head">Site 2 Operations &nbsp;|&nbsp; Date: <b>{selected_day_str}</b></div>
        </div>
    """, unsafe_allow_html=True)
    st.info("Fairmont site connected to `records_fairmont/`. Update the form IDs in `app_fairmont.py` to stream live data.")
else:
    if st.button("← Back to Fairmont Overview", on_click=lambda: st.session_state.update(fairmont_nav_choice="🏠 Fairmont - EHCO Status Overview")):
        st.rerun()
    st.write("")
    if st.session_state.fairmont_nav_choice == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
        st.markdown(f'<div class="record-header-box">❄️ {st.session_state.fairmont_nav_choice}</div>', unsafe_allow_html=True)
        render_record_03_view(pd.DataFrame(), selected_day_str, default_start_7d, today)
