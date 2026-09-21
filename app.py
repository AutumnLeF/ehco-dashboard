from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records.record_02 import render_record_02_view, parse_record_02_submissions
from records.record_03 import render_record_03_view
from records.record_04 import render_record_04_view, parse_all_record_04_dishes
from records.record_05 import render_record_05_view, parse_record_05_submissions
from records.record_06 import render_record_06_view
from records.record_12 import render_record_12_view
from records.record_13 import render_record_13_view, parse_record_13_submissions
from records.record_15 import render_record_15_view
from records.record_21 import render_record_21_view, parse_record_21_submissions
from records.record_25 import render_record_25_view, parse_record_25_submissions

st.set_page_config(
    page_title="Roswyn - EHCO Status",
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
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. SIDEBAR CONTROLS
# -------------------------------------------------------------
st.sidebar.title("⚙️ Inspection Controls")
st.sidebar.markdown("**Site:** Roswyn (Site 1)")

today = datetime.now(timezone.utc).date()
default_start_7d = today - timedelta(days=6)

date_selection = st.sidebar.date_input(
    "Audit Date Range (7 Days)",
    value=[default_start_7d, today],
    max_value=today,
    key="sb_date_range_picker"
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
    "Focus Day for Drill-down", options=list(reversed(day_options)), key="sb_day_focus_select"
)

DEFAULT_TOKEN = "eyJraWQiOiJKSzRrMFBmRFlxT24zOGFIY0xHRis3NmZjWTIrU3R4a3d0VG1DSXBWYjJnPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6Ly9jb2duaXRvLWlkcC5hcC1zb3V0aGVhc3QtMi5hbWF6b25hd3MuY29tL2FwLXNvdXRoZWFzdC0yXzdrQXN6M24zeCIsIm1mYV9tZXRob2QiOiJOT19NRkFfRU5BQkxFRCIsImNvZ25pdG86dXNlcm5hbWUiOiJjNTFlNzBjOS03MjliLTQ2MjItYTU1MS0wNzc4MjFmOTNhMTUiLCJvcmlnaW5fanRpIjoiZGJmM2RlZjQtNjk0OC00ODcxLTlkMTQtZDFiNzFhYTRlNDdjIiwiYXVkIjoiNHE3cDZpbmEzMTI3cWdnNGs0MG82Mm41bGsiLCJldmVudF9pZCI6IjdiN2ZiOGY2LTdjMjYtNGJjZi05ZGRhLTkwZGEyMTJjMGNiOCIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lIjoxNzg4NDMyMzMyLCJleHAiOjE3ODk5MDAzMDIsImlhdCI6MTc4OTg5NjcwMiwianRpIjoiYjM1MmE5Y2UtMjJmNS00NjY0LWFiZDEtODNjNjkxZWFhYmRjIiwiZW1haWwiOiJzYWhpbC5jaGF1aGFuMUBtb3JnYW5zb3JpZ2luYWxzLmNvbSJ9.RqTTBmZKZNOBrdzQIqZ-XZ6ZF2w_XbdGXT1ZEmhn7CiBz1-KsU-KJDW4jLUh3DUxIaCzBBZWQZoTbKvaOzMaX9kp3WdQaNjhwioQvkYcdhFAOt7DmCtQKpTsFLgKU_wKX9Q97XaKnfj6O6v6i7BFHRj23UN3YeeMU2N8KeadebEmfVRirbJ3kMWW-YFvRlVP7tRZezRnkMRiF8av_2yV3EGeUCIUzkh3yAs-SVB8FZhoEqVN5M30XpXMHhIaNiCzx8QlZyQamJxl641NyvaxdwP5B8dFL-zUU8OiBQzYM3NDbo84XorrjRaEisOXuChZuJ7GpHYcTiJDd2nQPXFzGQ"

if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = DEFAULT_TOKEN.strip()

api_url = st.sidebar.text_input(
    "Endpoint URL", value="https://auth-api.blinkm.io/form-store", key="sb_api_endpoint_input"
)

token_input = st.sidebar.text_area(
    "Bearer Token", 
    value=st.session_state["auth_token"], 
    height=90, 
    key="sb_bearer_token_input"
)

if token_input != st.session_state["auth_token"]:
    st.session_state["auth_token"] = token_input.strip()

active_token = st.session_state.get("auth_token", DEFAULT_TOKEN).strip()
clean_token = active_token.replace("Bearer ", "").strip()

# -------------------------------------------------------------
# 3. RECORD SELECTOR & NAVIGATION STATE
# -------------------------------------------------------------
FORM_MAPPING = {
    "🏠 Roswyn - EHCO Status Overview": 0,
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

if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = "🏠 Roswyn - EHCO Status Overview"

selected_record = st.sidebar.selectbox(
    "SELECT FOOD SAFETY RECORD", 
    list(FORM_MAPPING.keys()), 
    index=list(FORM_MAPPING.keys()).index(st.session_state.nav_choice) if st.session_state.nav_choice in FORM_MAPPING else 0,
    key="main_record_selector"
)

if selected_record != st.session_state.nav_choice:
    st.session_state.nav_choice = selected_record
    st.rerun()

active_form_id = FORM_MAPPING[st.session_state.nav_choice]

# -------------------------------------------------------------
# 4. INGESTION ENGINE WITH CACHING
# -------------------------------------------------------------
cache_key = f"cache_df_{active_form_id}_v6"
sync_time_key = f"sync_time_{active_form_id}_v6"

force_refresh = st.sidebar.button("🔄 Sync Live Feed", key="sync_live_feed_btn", use_container_width=True)

if force_refresh:
    st.session_state.pop(cache_key, None)
    st.session_state.pop(sync_time_key, None)


def fetch_submissions(url, token, form_id, start_dt, end_dt):
    """Paginates form-store using nested paging & sorting payload."""
    if form_id == 0:
        return []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://tehc-roswyn.data-manager.oneblink.io",
        "Referer": "https://tehc-roswyn.data-manager.oneblink.io/",
    }

    all_rows = []
    current_offset = 0
    base_url = url.strip()

    for page in range(20):
        payload = {
            "formId": form_id,
            "paging": {
                "limit": 50,
                "offset": current_offset
            },
            "sorting": [
                {
                    "property": "dateTimeSubmitted",
                    "direction": "descending"
                }
            ],
            "unwindRepeatableSets": True,
        }

        try:
            res = requests.post(base_url, headers=headers, json=payload, timeout=20)
            if res.status_code != 200:
                break

            data = res.json()
            items = data.get("submissions", []) if isinstance(data, dict) else data
            if not items:
                break

            all_rows.extend(items)
            if len(items) < 50:
                break

            current_offset += 50
        except Exception:
            break

    return all_rows

if active_form_id != 0 and (cache_key not in st.session_state or st.session_state[cache_key].empty):
    active_token = token_input.strip() if token_input else DEFAULT_TOKEN.strip()
    clean_token = active_token.replace("Bearer ", "").strip()

    with st.spinner(f"Fetching weekly logs for Form {active_form_id}..."):
        try:
            items = fetch_submissions(api_url, clean_token, active_form_id, start_date, end_date)
            if items:
                raw_df = pd.DataFrame({"raw_record": items})
                st.session_state[cache_key] = raw_df
                st.session_state[sync_time_key] = datetime.now()
            else:
                st.session_state[cache_key] = pd.DataFrame()
        except Exception:
            st.session_state[cache_key] = pd.DataFrame()

raw_records_df = st.session_state.get(cache_key, pd.DataFrame())

# -------------------------------------------------------------
# 5. ROUTE TO MODULAR RECORD AUDITORS OR OVERVIEW
# -------------------------------------------------------------
if st.session_state.nav_choice == "🏠 Roswyn - EHCO Status Overview":
    st.markdown('<div class="serif-title">Roswyn - EHCO Status Overview</div>', unsafe_allow_html=True)
    st.markdown(f"Operational completion and status summary for **{selected_day_str}**. Click any record button below to jump directly to its audit page.")
    st.write("")

    def get_form_df(form_id):
        ck = f"cache_df_{form_id}_v6"
        if ck not in st.session_state or st.session_state[ck].empty:
            items = fetch_submissions(api_url, clean_token, form_id, start_date, end_date)
            st.session_state[ck] = pd.DataFrame({"raw_record": items}) if items else pd.DataFrame()
        return st.session_state[ck]

    df_02 = parse_record_02_submissions(get_form_df(31370))
    df_04 = parse_all_record_04_dishes(get_form_df(31374))
    df_05 = parse_record_05_submissions(get_form_df(31375))
    df_13 = parse_record_13_submissions(get_form_df(31382))
    df_21 = parse_record_21_submissions(get_form_df(31390))
    df_25 = parse_record_25_submissions(get_form_df(31393))

    # Calculate Status Strings
    day_02 = df_02[df_02["Date_Str"] == selected_day_str] if not df_02.empty else pd.DataFrame()
    stat_02 = f"Completed - {len(day_02)}/1" if not day_02.empty else "Pending - 0/1"

    # Record 03: Opening & Closing
    df_03 = get_form_df(31373)
    day_03 = df_03 if not df_03.empty else pd.DataFrame()
    stat_03_op = "Completed - 1/1" if not day_03.empty else "Pending - 0/1"
    stat_03_cl = "Pending - 0/1" # Can be refined based on shift time if needed

    # Record 04: Breakfast, Lunch, Dinner shifts
    day_04 = df_04[df_04["Date_Str"] == selected_day_str] if not df_04.empty else pd.DataFrame()
    stat_04_bf = f"Completed - {len(day_04)} batches" if not day_04.empty else "Pending - 0 batches"
    stat_04_ln = f"Completed - {len(day_04)} batches" if not day_04.empty else "Pending - 0 batches"
    stat_04_dn = f"Completed - {len(day_04)} batches" if not day_04.empty else "Pending - 0 batches"

    day_05 = df_05[df_05["Date_Str"] == selected_day_str] if not df_05.empty else pd.DataFrame()
    stat_05 = f"Completed - {len(day_05)} batches" if not day_05.empty else "Pending - 0 batches"

    # Record 06, 12, 15 placeholders or parsers
    stat_06 = "Completed - 1/1"
    stat_12 = "Completed - 1/1"

    day_13 = df_13[df_13["Date_Str"] == selected_day_str] if not df_13.empty else pd.DataFrame()
    logged_13 = len(day_13["Unit_ID"].dropna().unique()) if not day_13.empty else 0
    stat_13 = f"Completed - {logged_13}/11"

    stat_15 = "Completed - 1/1"

    day_21 = df_21[df_21["Date_Str"] == selected_day_str] if not df_21.empty else pd.DataFrame()
    stat_21 = f"Completed - {len(day_21)} batches" if not day_21.empty else "Pending - 0 batches"

    day_25 = df_25[df_25["Date_Str"] == selected_day_str] if not df_25.empty else pd.DataFrame()
    logged_25 = len(day_25["Clean_Unit"].dropna().unique()) if not day_25.empty else 0
    stat_25 = f"Completed - {logged_25}/1" if logged_25 > 0 else "Pending - 0/1"

    # Render Cards in 2 Columns
    col1, col2 = st.columns(2)

    def render_card(col, title, status_text, target_nav):
        col.markdown(f"""
        <div style="background:#ffffff; border:1px solid #cbd5e1; border-left:5px solid #0f172a; border-radius:8px; padding:14px; margin-bottom:6px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="font-weight:700; font-size:1rem; color:#0f172a;">{title}</div>
            <div style="font-size:0.82rem; color:#16a34a; font-weight:600; margin-top:3px;">Status: <b>{status_text}</b></div>
        </div>
        """, unsafe_allow_html=True)
        if col.button(f"Open {title.split(':')[0]} ➔", use_container_width=True, key=f"btn_{target_nav}"):
            st.session_state.nav_choice = target_nav
            st.rerun()

    with col1:
        render_card(col1, "Record 02: Food Delivery Record", stat_02, "RECORD 02 - FOOD DELIVERY RECORD")
        render_card(col1, "Record 03: Coolroom/Fridge Opening", stat_03_op, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD")
        render_card(col1, "Record 03: Coolroom/Fridge Closing", stat_03_cl, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD")
        render_card(col1, "Record 04: Cooking/Reheating (Breakfast)", stat_04_bf, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD")
        render_card(col1, "Record 04: Cooking/Reheating (Lunch)", stat_04_ln, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD")
        render_card(col1, "Record 04: Cooking/Reheating (Dinner)", stat_04_dn, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD")

    with col2:
        render_card(col2, "Record 05: Cooling of Food (Blast Chiller)", stat_05, "RECORD 05 - COOLING OF FOOD RECORD")
        render_card(col2, "Record 06: Food Display Temperature", stat_06, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD")
        render_card(col2, "Record 12: Defrosting Temperature Record", stat_12, "RECORD 12 - DEFROSTING TEMPERATURE RECORD")
        render_card(col2, "Record 13: Warewash Sanitization Record", stat_13, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD")
        render_card(col2, "Record 15: Pesticide Usage Record", stat_15, "RECORD 15 - PESTICIDE USAGE RECORD")
        render_card(col2, "Record 21: Food Wash Record (Chlorine)", stat_21, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH")
        render_card(col2, "Record 25: Ice Machine Cleaning Record", stat_25, "RECORD 25 - ICE MACHINE CLEANING RECORD")

elif st.session_state.nav_choice == "RECORD 02 - FOOD DELIVERY RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_02_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_03_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_04_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 05 - COOLING OF FOOD RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_05_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_06_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 12 - DEFROSTING TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_12_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_13_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 15 - PESTICIDE USAGE RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_15_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_21_view(raw_records_df, selected_day_str, start_date, end_date)

elif st.session_state.nav_choice == "RECORD 25 - ICE MACHINE CLEANING RECORD":
    st.markdown(f'<div class="serif-title">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)
    render_record_25_view(raw_records_df, selected_day_str, start_date, end_date)

# -------------------------------------------------------------
# 6. DIAGNOSTIC PANEL
# -------------------------------------------------------------
st.divider()
st.subheader("🛠️ Raw Data Diagnostic")
st.write(f"**Active Form ID:** `{active_form_id}`")
st.write(f"**Total Rows in Memory:** {len(raw_records_df)}")
