from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records.record_03 import render_record_03_view
from records.record_04 import render_record_04_view
from records.record_05 import render_record_05_view
from records.record_12 import render_record_12_view
from records.record_13 import render_record_13_view
from records.record_15 import render_record_15_view
from records.record_21 import render_record_21_view
from records.record_25 import render_record_25_view
from records.record_02 import render_record_02_view
from records.record_06 import render_record_06_view

st.set_page_config(
    page_title="Kitchen Safety Core",
    page_icon="🛡️",
    layout="wide",
)

# -------------------------------------------------------------
# 1. EDITORIAL STYLING
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Clean, crisp high-contrast base */
    .stApp { 
        background-color: #f8fafc; 
        font-family: 'Inter', sans-serif; 
        color: #0f172a; 
    }
    
    .serif-title { 
        font-size: 1.85rem; 
        font-weight: 700; 
        color: #0f172a; 
        margin-bottom: 0.4rem; 
        letter-spacing: -0.02em;
    }
    .sub-head { 
        font-size: 0.75rem; 
        color: #475569; 
        text-transform: uppercase; 
        letter-spacing: 0.08em; 
        font-weight: 700; 
        margin-bottom: 0.4rem; 
    }
    
    /* Solid KPI stat cards */
    .kpi-box { 
        background: #ffffff;
        padding: 1rem 1.2rem; 
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-num { 
        font-size: 2.2rem; 
        font-weight: 700; 
        line-height: 1; 
    }
    .kpi-lbl { 
        font-size: 0.75rem; 
        color: #475569; 
        text-transform: uppercase; 
        font-weight: 600;
        letter-spacing: 0.05em; 
        margin-top: 0.35rem; 
    }
    
    /* Solid Kanban columns */
    .kanban-col { 
        background: #ffffff; 
        border-radius: 10px; 
        padding: 1.2rem; 
        border: 1px solid #cbd5e1; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        min-height: 380px; 
    }
    .kanban-h { 
        font-size: 0.82rem; 
        font-weight: 700; 
        text-transform: uppercase; 
        letter-spacing: 0.06em; 
        padding-bottom: 0.6rem; 
        border-bottom: 2px solid #e2e8f0; 
        margin-bottom: 1rem; 
    }
    .check-card { 
        padding: 0.85rem; 
        border-radius: 8px; 
        background: #f8fafc; 
        border: 1px solid #cbd5e1; 
        margin-bottom: 0.65rem; 
    }

    /* Structured Matrix Table Styles */
    .audit-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.75rem;
        background: #ffffff;
        border: 2px solid #334155;
    }
    .audit-table th {
        background-color: #f1f5f9;
        color: #0f172a;
        font-weight: 700;
        font-size: 0.85rem;
        text-align: center;
        padding: 10px 8px;
        border: 1px solid #334155;
    }
    .audit-table td {
        border: 1px solid #334155;
        padding: 8px;
        vertical-align: top;
        font-size: 0.82rem;
        color: #0f172a;
    }
    .cell-count {
        text-align: center;
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
        padding-bottom: 6px;
        border-bottom: 1px solid #cbd5e1;
        margin-bottom: 6px;
    }
    .cell-foods {
        font-size: 0.78rem;
        color: #1e293b;
        line-height: 1.35;
        font-weight: 500;
    }
    .cell-empty {
        text-align: center;
        color: #94a3b8;
        font-weight: 600;
        padding-top: 12px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. SIDEBAR CONTROLS (1-MONTH DATE RANGE)
# -------------------------------------------------------------
st.sidebar.title("⚙️ Inspection Controls")

today = datetime.now(timezone.utc).date()
default_start_30d = today - timedelta(days=30)

date_selection = st.sidebar.date_input(
    "Audit Date Range (1 Month)",
    value=[default_start_30d, today],
    max_value=today,
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
    "Focus Day for Drill-down", options=list(reversed(day_options))
)

# Active Bearer Token
DEFAULT_TOKEN = "eyJraWQiOiJKSzRrMFBmRFlxT24zOGFIY0xHRis3NmZjWTIrU3R4a3d0VG1DSXBWYjJnPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6Ly9jb2duaXRvLWlkcC5hcC1zb3V0aGVhc3QtMi5hbWF6b25hd3MuY29tL2FwLXNvdXRoZWFzdC0yXzdrQXN6M24zeCIsIm1mYV9tZXRob2QiOiJOT19NRkFfRU5BQkxFRCIsImNvZ25pdG86dXNlcm5hbWUiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJvcmlnaW5fanRpIjoiZGJmM2RlZjQtNjk0OC00ODcxLTlkMTQtZDFiNzFhYTRlNDdjIiwiYXVkIjoiNHE3cDZpbmEzMTI3cWdnNGs0MG82Mm41bGsiLCJldmVudF9pZCI6IjdiN2ZiOGY2LTdjMjYtNGJjZi05ZGRhLTkwZGEyMTJjMGNiOCIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lIjoxNzg4NDMyMzMyLCJleHAiOjE3ODk5MDAzMDIsImlhdCI6MTc4OTg5NjcwMiwianRpIjoiYjM1MmE5Y2UtMjJmNS00NjY0LWFiZDEtODNjNjkxZWFhYmRjIiwiZW1haWwiOiJzYWhpbC5jaGF1aGFuMUBtb3JnYW5zb3JpZ2luYWxzLmNvbSJ9.RqTTBmZKZNOBrdzQIqZ-XZ6ZF2w_XbdGXT1ZEmhn7CiBz1-KsU-KJDW4jLUh3DUxIaCzBBZWQZoTbKvaOzMaX9kp3WdQaNjhwioQvkYcdhFAOt7DmCtQKpTsFLgKU_wKX9Q97XaKnfj6O6v6i7BFHRj23UN3YeeMU2N8KeadebEmfVRirbJ3kMWW-YFvRlVP7tRZezRnkMRiF8av_2yV3EGeUCIUzkh3yAs-SVB8FZhoEqVN5M30XpXMHhIaNiCzx8QlZyQamJxl641NyvaxdwP5B8dFL-zUU8OiBQzYM3NDbo84XorrjRaEisOXuChZuJ7GpHYcTiJDd2nQPXFzGQ"

api_url = st.sidebar.text_input(
    "Endpoint URL", value="https://auth-api.blinkm.io/form-store"
)
token_input = st.sidebar.text_area(
    "Bearer Token", value=DEFAULT_TOKEN, height=90
)
sync_button = st.sidebar.button("🔄 Sync Live Feed", use_container_width=True)

# -------------------------------------------------------------
# 3. RECORD SELECTOR & DYNAMIC FORM ID
# -------------------------------------------------------------
st.markdown(
    '<div class="sub-head">Today • Food-Safety Core</div>',
    unsafe_allow_html=True,
)

FORM_MAPPING = {
    "RECORD 02 - FOOD DELIVERY RECORD": 31370,
    "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD": 31373,
    "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD": 31374,
    "RECORD 05 - COOLING OF FOOD RECORD": 31375,
    "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD": 31376,
    "RECORD 12 - DEFROSTING TEMPERATURE RECORD": 31381,
    "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD": 31382,
    "RECORD 15 - PESTICIDE USAGE RECORD": 31384,
    "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH": 31390,
    "RECORD 25 - ICE MACHINE CLEANING RECORD": 31393,
}

selected_record = st.selectbox(
    "SELECT FOOD SAFETY RECORD", list(FORM_MAPPING.keys())
)
active_form_id = FORM_MAPPING[selected_record]

# -------------------------------------------------------------
# 4. LIVE INGESTION (POST TO BLINKM FORM-STORE)
# -------------------------------------------------------------
raw_records_df = pd.DataFrame()
api_status_code = None
api_response_text = ""

active_token = token_input.strip() if token_input else DEFAULT_TOKEN.strip()

if active_token:
    clean_token = active_token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://tehc-roswyn.data-manager.oneblink.io",
        "Referer": "https://tehc-roswyn.data-manager.oneblink.io/",
    }

    # Query up to 500 records to cover the full 30-day window
    post_payload = {
    "formId": active_form_id,
    "limit": 250,
    "offset": 0,
    "unwindRepeatableSets": True, # Required by OneBlink to separate repeatable entries
}

    try:
        res = requests.post(
            api_url.strip(), headers=headers, json=post_payload, timeout=15
        )
        api_status_code = res.status_code
        api_response_text = res.text

        if res.status_code == 200:
            data = res.json()
            items = (
                data.get("submissions", [])
                if isinstance(data, dict)
                else data
            )
            if items:
                raw_records_df = pd.json_normalize(items)
                st.sidebar.success(
                    f"✓ Retrieved {len(raw_records_df)} records for Form {active_form_id}"
                )
            else:
                st.sidebar.warning(f"Form {active_form_id} returned 0 submissions.")
        else:
            st.sidebar.error(f"API Error HTTP {res.status_code}")
    except Exception as e:
        st.sidebar.error(f"Connection failed: {e}")

# -------------------------------------------------------------
# 5. ROUTE TO MODULAR RECORD AUDITORS (EXACT TITLES)
# -------------------------------------------------------------
if selected_record == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_04_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 05 - COOLING OF FOOD RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_05_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 12 - DEFROSTING TEMPERATURE RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_12_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_13_view(
        raw_records_df, selected_day_str, start_date, end_date
    )
    
elif selected_record == "RECORD 15 - PESTICIDE USAGE RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_15_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_21_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 25 - ICE MACHINE CLEANING RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_25_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 02 - FOOD DELIVERY RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_02_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_06_view(
        raw_records_df, selected_day_str, start_date, end_date
    )

elif selected_record == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
    st.markdown(
        f'<div class="serif-title">{selected_record}</div>',
        unsafe_allow_html=True,
    )
    render_record_03_view(
        raw_records_df, selected_day_str, start_date, end_date
    )
    
# -------------------------------------------------------------
# 6. DIAGNOSTIC PANEL
# -------------------------------------------------------------
st.divider()
st.subheader("🛠️ Raw Data Diagnostic")
st.write(f"**Active Form ID:** `{active_form_id}`")
st.write(f"**HTTP Status Code:** {api_status_code}")
st.write(f"**Total Submissions Loaded:** {len(raw_records_df)}")

if not raw_records_df.empty:
    sample_cols = [
        c
        for c in raw_records_df.columns
        if any(
            k in c.lower()
            for k in [
                "date",
                "food",
                "temp",
                "location",
                "method",
                "sign",
            ]
        )
    ]
    if sample_cols:
        st.dataframe(raw_records_df[sample_cols].head(3), use_container_width=True)

def render_record_21_view(raw_df, selected_day_str, start_date, end_date):
    # --- TEMPORARY DIAGNOSTIC BAR ---
    with st.expander("🛠️ Debug Live Submissions Received from API"):
        st.write(f"Total raw rows received from API: **{len(raw_df)}**")
        if not raw_df.empty:
            # Show raw columns and sample rows
            st.dataframe(raw_df.head(10), use_container_width=True)
    # --------------------------------
