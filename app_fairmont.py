from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Fairmont Mumbai - EHCO Status",
    page_icon="🏨",
    layout="wide",
)

# -------------------------------------------------------------
# 1. EDITORIAL STYLING & THEME
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp { 
        background-color: #f8fafc; 
        font-family: 'Inter', sans-serif; 
        color: #0f172a; 
    }
    
    .serif-title { 
        font-size: 2.1rem; 
        font-weight: 700; 
        color: #0f172a; 
        margin-bottom: 0.2rem; 
        letter-spacing: -0.02em;
    }
    .sub-head { 
        font-size: 0.85rem; 
        color: #475569; 
        font-weight: 600; 
    }
    .record-header-box {
        background-color: #0b192c;
        padding: 18px 24px;
        border-radius: 10px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        font-size: 1.6rem;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. SIDEBAR CONTROLS & NAVIGATION ROUTING
# -------------------------------------------------------------
st.sidebar.title("⚙️ Inspection Controls")
st.sidebar.markdown("**Site:** Fairmont Mumbai (Site 2)")

if st.sidebar.button("🏠 Return to Site Selection Portal", use_container_width=True):
    st.switch_page("landing.py")

ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
today = ist_now.date()
default_start_7d = today - timedelta(days=6)

date_selection = st.sidebar.date_input(
    "Audit Date Range (7 Days)",
    value=[default_start_7d, today],
    max_value=today,
    key="sb_fairmont_date_range"
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
    "Focus Day for Drill-down", options=list(reversed(day_options)), key="sb_fairmont_day_select"
)

FORM_MAPPING = {
    "🏠 Fairmont - EHCO Status Overview": 0,
    "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD": 0,  # Update with Fairmont Form ID
    "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD": 0,
    "RECORD 05 - COOLING OF FOOD RECORD": 0,
    "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD": 0,
}

if "fairmont_nav_choice" not in st.session_state:
    st.session_state.fairmont_nav_choice = "🏠 Fairmont - EHCO Status Overview"

nav_options = list(FORM_MAPPING.keys())
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

# -------------------------------------------------------------
# 3. FAIRMONT OVERVIEW DASHBOARD VIEW
# -------------------------------------------------------------
if st.session_state.fairmont_nav_choice == "🏠 Fairmont - EHCO Status Overview":
    st.markdown(f"""
        <div style="margin-bottom: 1.5rem;">
            <div class="serif-title">Fairmont Mumbai - EHCO Status</div>
            <div class="sub-head">Date: <b>{selected_day_str}</b> &nbsp;|&nbsp; IST Time: <b>{ist_now.strftime("%H:%M:%S")}</b></div>
        </div>
    """, unsafe_allow_html=True)

    st.info("Fairmont Mumbai site connected. Configure specific kitchen units and Form IDs inside `app_fairmont.py` to activate live data streams.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Active Kitchen Units", value="0 Units", delta="Pending Configuration")
    with col2:
        st.metric(label="Daily Compliance Rate", value="0%", delta="--")
