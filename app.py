from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
import streamlit as st

# Import the Record 04 module
from records.record_04 import render_record_04_view

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

# Sidebar for date & token
st.sidebar.title("⚙️ Inspection Controls")
target_date = st.sidebar.date_input(
    "Audit Date", value=datetime.now(timezone.utc).date()
)
date_str = target_date.strftime("%d/%m/%Y")  # Matches 19/09/2026 format

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

# Route to the appropriate record module
if (
    selected_record
    == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD"
):
    st.markdown(
        '<div class="serif-title">Cooking & Reheating Shift Audit</div>',
        unsafe_allow_html=True,
    )
    render_record_04_view(sample_data)
else:
    st.info(f"Module for {selected_record} will load here.")
