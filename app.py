from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
import streamlit as st

# Import the Record 04 module
from records.record_04 import render_record_04_view
from records.record_05 import render_record_05_view

st.set_page_config(
    page_title="Kitchen Safety Core", page_icon="🛡️", layout="wide"
)

# Custom Editorial Styling
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# Top Bar
st.markdown(
    '<div class="sub-head">Today • Food-Safety Core</div>',
    unsafe_allow_html=True,
)

# Record Switcher
selected_record = st.selectbox(
    "SELECT FOOD SAFETY RECORD",
    [
        "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD",
        "RECORD 02 - FOOD DELIVERY RECORD",
        "RECORD 03 - FOOD STORAGE TEMPERATURE RECORD",
        "RECORD 05 - COOLING OF FOOD RECORD",
        "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD",
        "RECORD 12 - DEFROSTING RECORD",
        "RECORD 13 - DISHWASHER / GLASSWASHER TEMPERATURE RECORD",
        "RECORD 15 - PESTICIDE USAGE RECORD",
        "RECORD 21 - FOOD WASHING RECORD",
        "RECORD 25 - ICE MACHINE CLEANING RECORD",
    ],
)

from datetime import datetime, timedelta, timezone

# -------------------------------------------------------------
# SIDEBAR DATE RANGE PICKER (DEFAULT: LAST 14 DAYS)
# -------------------------------------------------------------
st.sidebar.title("⚙️ Inspection Controls")

today = datetime.now(timezone.utc).date()
default_start = today - timedelta(days=14)

# Passing a 2-element list creates a date range picker
date_selection = st.sidebar.date_input(
    "Audit Date Range (10-15 Days)",
    value=[default_start, today],
    max_value=today,
)

# Handle selection: user may click only 1 date while selecting the range
if isinstance(date_selection, (list, tuple)) and len(date_selection) == 2:
    start_date, end_date = date_selection
elif isinstance(date_selection, (list, tuple)) and len(date_selection) == 1:
    start_date = end_date = date_selection[0]
else:
    start_date = end_date = date_selection

# Single-day drilldown selector within the chosen range
delta_days = (end_date - start_date).days
day_options = [
    (start_date + timedelta(days=i)).strftime("%d/%m/%Y")
    for i in range(delta_days + 1)
]

selected_day_str = st.sidebar.selectbox(
    "Focus Day for Drill-down",
    options=list(reversed(day_options)),  # Most recent first
)

if "raw_records_df" not in locals():
    raw_records_df = pd.DataFrame()

api_token = st.sidebar.text_input("Cognito Bearer Token", type="password")
api_url = st.sidebar.text_input(
    "Endpoint URL", value="https://example.com/form-store"
)

# DATA SOURCE: Replace with live API call or test with current screenshot data
# Sample data reconstructed directly from your screenshot:
sample_data = pd.DataFrame(
    [
        {
            "Date": "19/09/2026",
            "Time": "8:14 PM",
            "Location": "Filia Kitchen",
            "Meal Service": "Dinner",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Polpette di carne",
            "Food Temperature °C (Cooking)": 78.6,
            "Sign (Initial)": "Yashika",
        },
        {
            "Date": "19/09/2026",
            "Time": "8:14 PM",
            "Location": "Filia Kitchen",
            "Meal Service": "Dinner",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Pancia di maile",
            "Food Temperature °C (Cooking)": 79.2,
            "Sign (Initial)": "Yashika",
        },
        {
            "Date": "19/09/2026",
            "Time": "8:14 PM",
            "Location": "Filia Kitchen",
            "Meal Service": "Dinner",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Gamberi",
            "Food Temperature °C (Cooking)": 76.4,
            "Sign (Initial)": "Yashika",
        },
        {
            "Date": "19/09/2026",
            "Time": "8:00 PM",
            "Location": "Black Lacquer Kitchen",
            "Meal Service": "Dinner",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Shrimp tempura",
            "Food Temperature °C (Cooking)": 76.8,
            "Sign (Initial)": "Manish Sawant",
        },
        {
            "Date": "19/09/2026",
            "Time": "8:00 PM",
            "Location": "Black Lacquer Kitchen",
            "Meal Service": "Dinner",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Katsu curry",
            "Food Temperature °C (Cooking)": 80.9,
            "Sign (Initial)": "Manish Sawant",
        },
        {
            "Date": "19/09/2026",
            "Time": "8:00 PM",
            "Location": "Black Lacquer Kitchen",
            "Meal Service": "Dinner",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Tori tatsuta",
            "Food Temperature °C (Cooking)": 79.1,
            "Sign (Initial)": "Manish Sawant",
        },
        {
            "Date": "19/09/2026",
            "Time": "3:34 PM",
            "Location": "Filia Kitchen",
            "Meal Service": "Lunch",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Pappardelle al ragout",
            "Food Temperature °C (Cooking)": 75.8,
            "Sign (Initial)": "Vidya",
        },
        {
            "Date": "19/09/2026",
            "Time": "3:34 PM",
            "Location": "Filia Kitchen",
            "Meal Service": "Lunch",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Fritto misto",
            "Food Temperature °C (Cooking)": 76.4,
            "Sign (Initial)": "Vidya",
        },
        {
            "Date": "19/09/2026",
            "Time": "3:34 PM",
            "Location": "Filia Kitchen",
            "Meal Service": "Lunch",
            "Type of Heat Treatment": "Cooking",
            "Name of Food": "Asparagus soup",
            "Food Temperature °C (Cooking)": 76.4,
            "Sign (Initial)": "Vidya",
        },
    ]
)

# -------------------------------------------------------------
# DATA RETRIEVAL / FALLBACK DEFINITION
# -------------------------------------------------------------
# 1. Initialize raw_records_df as an empty DataFrame by default
raw_records_df = pd.DataFrame()

# 2. If API token & URL are entered, fetch live submissions
if api_token and api_url:
    try:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(api_url, headers=headers, timeout=12)
        if res.status_code == 200:
            submissions = res.json().get("submissions", [])
            raw_records_df = pd.json_normalize(submissions)
        else:
            st.sidebar.error(f"API Error: HTTP {res.status_code}")
    except Exception as e:
        st.sidebar.error(f"Fetch failed: {e}")

# -------------------------------------------------------------
# ROUTE TO RECORD MODULES
# -------------------------------------------------------------
if selected_record == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
    st.markdown(
        '<div class="serif-title">Record 04: Cooking & Reheating Shift Audit</div>',
        unsafe_allow_html=True,
    )

with st.expander("🛠️ Raw Data & Date Diagnostic (Click to inspect)"):
    st.write(f"Total raw records loaded: {len(raw_records_df)}")
    if not raw_records_df.empty:
        # Check potential formId columns
        id_cols = [c for c in raw_records_df.columns if "formid" in c.lower()]
        st.write("Form ID columns found:", id_cols)
        if id_cols:
            st.write("Unique Form IDs present:", raw_records_df[id_cols[0]].unique())

        # Check potential Date columns and raw sample values
        date_cols = [c for c in raw_records_df.columns if "date" in c.lower() or "created" in c.lower()]
        st.write("Date columns found:", date_cols)
        st.dataframe(raw_records_df[date_cols + id_cols].head(5), use_container_width=True)
        
    render_record_04_view(
        raw_records_df, selected_day_str, start_date, end_date
    )
elif selected_record == "RECORD 05 - COOLING OF FOOD RECORD":
    st.markdown('<div class="serif-title">Blast Chiller & Cooling Audit</div>', unsafe_allow_html=True)
    render_record_05_view(raw_records_df)

else:
    st.info(f"Module for {selected_record} is currently in progress.")
