from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records.record_02 import render_record_02_view
from records.record_03 import render_record_03_view
from records.record_04 import render_record_04_view
from records.record_05 import render_record_05_view
from records.record_06 import render_record_06_view
from records.record_12 import render_record_12_view
from records.record_13 import render_record_13_view
from records.record_15 import render_record_15_view
from records.record_21 import render_record_21_view
from records.record_25 import render_record_25_view

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

DEFAULT_TOKEN = "eyJraWQiOiJKSzRrMFBmRFlxT24zOGFIY0xHRis3NmZjWTIrU3R4a3d0VG1DSXBWYjJnPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6Ly9jb2duaXRvLWlkcC5hcC1zb3V0aGVhc3QtMi5hbWF6b25hd3MuY29tL2FwLXNvdXRoZWFzdC0yXzdrQXN6M24zeCIsIm1mYV9tZXRob2QiOiJOT19NRkFfRU5BQkxFRCIsImNvZ25pdG86dXNlcm5hbWUiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJvcmlnaW5fanRpIjoiZGJmM2RlZjQtNjk0OC00ODcxLTlkMTQtZDFiNzFhYTRlNDdjIiwiYXVkIjoiNHE3cDZpbmEzMTI3cWdnNGs0MG82Mm41bGsiLCJldmVudF9pZCI6IjdiN2ZiOGY2LTdjMjYtNGJjZi05ZGRhLTkwZGEyMTJjMGNiOCIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lIjoxNzg4NDMyMzMyLCJleHAiOjE3ODk5MDAzMDIsImlhdCI6MTc4OTg5NjcwMiwianRpIjoiYjM1MmE5Y2UtMjJmNS00NjY0LWFiZDEtODNjNjkxZWFhYmRjIiwiZW1haWwiOiJzYWhpbC5jaGF1aGFuMUBtb3JnYW5zb3JpZ2luYWxzLmNvbSJ9.RqTTBmZKZNOBrdzQIqZ-XZ6ZF2w_XbdGXT1ZEmhn7CiBz1-KsU-KJDW4jLUh3DUxIaCzBBZWQZoTbKvaOzMaX9kp3WdQaNjhwioQvkYcdhFAOt7DmCtQKpTsFLgKU_wKX9Q97XaKnfj6O6v6i7BFHRj23UN3YeeMU2N8KeadebEmfVRirbJ3kMWW-YFvRlVP7tRZezRnkMRiF8av_2yV3EGeUCIUzkh3yAs-SVB8FZhoEqVN5M30XpXMHhIaNiCzx8QlZyQamJxl641NyvaxdwP5B8dFL-zUU8OiBQzYM3NDbo84XorrjRaEisOXuChZuJ7GpHYcTiJDd2nQPXFzGQ"

api_url = st.sidebar.text_input(
    "Endpoint URL", value="https://auth-api.blinkm.io/form-store"
)
token_input = st.sidebar.text_area(
    "Bearer Token", value=DEFAULT_TOKEN, height=90
)

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
# 4. INCREMENTAL CACHING ENGINE
# -------------------------------------------------------------
cache_key = f"cache_df_{active_form_id}"
sync_time_key = f"sync_time_{active_form_id}"

if cache_key not in st.session_state:
    st.session_state[cache_key] = pd.DataFrame()
    st.session_state[sync_time_key] = None

last_sync_display = st.session_state.get(sync_time_key)
if last_sync_display:
    st.sidebar.caption(f"🕒 Cache synched: {last_sync_display.strftime('%H:%M:%S')}")
else:
    st.sidebar.caption("🕒 Cache: Not yet loaded")

force_refresh = st.sidebar.button("🔄 Sync Live Feed", use_container_width=True)

def fetch_submissions(url, token, form_id):
    """Paginates form-store descending (newest first) up to 2000 records."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://tehc-roswyn.data-manager.oneblink.io",
        "Referer": "https://tehc-roswyn.data-manager.oneblink.io/",
    }
    all_rows = []
    page_size = 50
    offset = 0

    while True:
        payload = {
            "formId": form_id,
            "limit": page_size,
            "offset": offset,
            "sort": {"createdAt": -1},  # Force newest records first
            "unwindRepeatableSets": True,
        }
        try:
            res = requests.post(url.strip(), headers=headers, json=payload, timeout=20)
            if res.status_code != 200:
                break
            data = res.json()
            items = data.get("submissions", []) if isinstance(data, dict) else data
            if not items:
                break

            all_rows.extend(items)

            if len(items) < page_size:
                break

            offset += page_size
            if offset >= 2000:
                break
        except Exception:
            break

    return all_rows

# Ingest data only if cache is empty or user manually pressed "Sync Live Feed"
if st.session_state[cache_key].empty or force_refresh:
    active_token = token_input.strip() if token_input else DEFAULT_TOKEN.strip()
    clean_token = active_token.replace("Bearer ", "").strip()

    with st.spinner(f"Fetching records for Form {active_form_id}..."):
        try:
            items = fetch_submissions(api_url, clean_token, active_form_id)
            if items:
                raw_df = pd.json_normalize(items)
                st.session_state[cache_key] = raw_df
                st.session_state[sync_time_key] = datetime.now()
                st.sidebar.success(f"✓ Loaded {len(raw_df)} submissions")
            else:
                st.sidebar.warning(f"Form {active_form_id} returned 0 submissions.")
        except Exception as e:
            st.sidebar.error(f"Sync error: {e}")

raw_records_df = st.session_state[cache_key]

# -------------------------------------------------------------
# 5. ROUTE TO MODULAR RECORD AUDITORS
# -------------------------------------------------------------
if selected_record == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_04_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 05 - COOLING OF FOOD RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_05_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 12 - DEFROSTING TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_12_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_13_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 15 - PESTICIDE USAGE RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_15_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_21_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 25 - ICE MACHINE CLEANING RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_25_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 02 - FOOD DELIVERY RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_02_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_06_view(raw_records_df, selected_day_str, start_date, end_date)

elif selected_record == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{selected_record}</div>', unsafe_allow_html=True)
    render_record_03_view(raw_records_df, selected_day_str, start_date, end_date)

# -------------------------------------------------------------
# 6. DIAGNOSTIC PANEL
# -------------------------------------------------------------
st.divider()
st.subheader("🛠️ Raw Data Diagnostic")
st.write(f"**Active Form ID:** `{active_form_id}`")
st.write(f"**Total Submissions in Memory:** {len(raw_records_df)}")

if not raw_records_df.empty:
    sample_cols = [
        c for c in raw_records_df.columns
        if any(k in c.lower() for k in ["date", "food", "temp", "location", "fridge", "coolroom", "freezer", "sign"])
    ]
    if sample_cols:
        st.dataframe(raw_records_df[sample_cols].head(3), use_container_width=True)
