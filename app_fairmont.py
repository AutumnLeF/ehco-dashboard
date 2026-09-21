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
# 1. FAIRMONT SPECIFIC STYLING & THEME
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
        background-color: #1e293b;
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
# 2. FAIRMONT UNIQUE UNITS & LOCATIONS CATALOG
# -------------------------------------------------------------
FAIRMONT_UNIT_CATALOG = {
    "Fairmont Main Kitchen": [
        {"Unit_ID": "FM/MK/UC/01", "Type": "Fridge"},
        {"Unit_ID": "FM/MK/CR/01", "Type": "Coolroom"},
        {"Unit_ID": "FM/MK/WF/01", "Type": "Freezer"},
    ],
    "Fairmont Bakery Kitchen": [
        {"Unit_ID": "FM/FBK/UC/01", "Type": "Fridge"},
        {"Unit_ID": "FM/FBK/VF/01", "Type": "Freezer"},
    ],
    "Fairmont Pool Bar": [
        {"Unit_ID": "FM/PB/UC/01", "Type": "Fridge"},
    ]
}

FAIRMONT_FORM_MAPPING = {
    "🏠 Fairmont - EHCO Status Overview": 0,
    "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD": 0, # Update with Fairmont Form ID
    "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD": 0,          # Update with Fairmont Form ID
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

st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <div class="serif-title">Fairmont Mumbai - EHCO Status</div>
        <div class="sub-head">Site 2 Active Operations &nbsp;|&nbsp; Date: <b>{selected_day_str}</b></div>
    </div>
""", unsafe_allow_html=True)

st.info("Fairmont site configuration is active. You can add Fairmont-specific API endpoints, record keywords, and form store mappings directly into this file.")

col1, col2 = st.columns(2)
with col1:
    st.metric(label="Configured Kitchen Locations", value=str(len(FAIRMONT_UNIT_CATALOG)))
with col2:
    total_fairmont_units = sum(len(units) for units in FAIRMONT_UNIT_CATALOG.values())
    st.metric(label="Total Tracked Units", value=str(total_fairmont_units))
