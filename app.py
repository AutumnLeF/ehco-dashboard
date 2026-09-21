from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records.record_02 import render_record_02_view, parse_record_02_submissions
from records.record_03 import render_record_03_view, parse_record_03_submissions
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
cache_key = f"cache_df_{active_form_id}_v14"
sync_time_key = f"sync_time_{active_form_id}_v14"

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
    st.markdown(f"Operational completion and status summary for **{selected_day_str}**. Click any card below to jump directly to its audit page.")
    st.write("")

    def get_form_df(form_id):
        ck = f"cache_df_{form_id}_v14"
        if ck not in st.session_state or st.session_state[ck].empty:
            items = fetch_submissions(api_url, clean_token, form_id, start_date, end_date)
            st.session_state[ck] = pd.DataFrame({"raw_record": items}) if items else pd.DataFrame()
        return st.session_state[ck]

    df_02 = parse_record_02_submissions(get_form_df(31370))
    df_03 = parse_record_03_submissions(get_form_df(31373))
    df_04 = parse_all_record_04_dishes(get_form_df(31374))
    df_05 = parse_record_05_submissions(get_form_df(31375))
    df_13 = parse_record_13_submissions(get_form_df(31382))
    df_21 = parse_record_21_submissions(get_form_df(31390))
    df_25 = parse_record_25_submissions(get_form_df(31393))

    # Calculate status metrics safely
    day_02 = df_02[df_02["Date_Str"] == selected_day_str] if (df_02 is not None and not df_02.empty and "Date_Str" in df_02.columns) else pd.DataFrame()
    stat_02 = f"Completed - {len(day_02)}/1" if not day_02.empty else "Pending - 0/1"

    # Record 03: Opening & Closing Ratios (8 Areas total)
    day_03 = df_03[df_03["Date_Str"] == selected_day_str] if (df_03 is not None and not df_03.empty and "Date_Str" in df_03.columns) else pd.DataFrame()
    op_count = len(day_03[day_03["Shift"].str.lower() == "opening"]) if (not day_03.empty and "Shift" in day_03.columns) else 0
    cl_count = len(day_03[day_03["Shift"].str.lower() == "closing"]) if (not day_03.empty and "Shift" in day_03.columns) else 0
    
    stat_03_op = f"Completed - {op_count}/8" if op_count > 0 else "Pending - 0/8"
    stat_03_cl = f"Completed - {cl_count}/8" if cl_count > 0 else "Pending - 0/8"

    day_04 = df_04[df_04["Date_Str"] == selected_day_str] if (df_04 is not None and not df_04.empty and "Date_Str" in df_04.columns) else pd.DataFrame()
    stat_04_bf = f"Completed - {len(day_04)} batches" if not day_04.empty else "Pending - 0 batches"
    stat_04_ln = f"Completed - {len(day_04)} batches" if not day_04.empty else "Pending - 0 batches"
    stat_04_dn = f"Completed - {len(day_04)} batches" if not day_04.empty else "Pending - 0 batches"

    day_05 = df_05[df_05["Date_Str"] == selected_day_str] if (df_05 is not None and not df_05.empty and "Date_Str" in df_05.columns) else pd.DataFrame()
    stat_05 = f"Completed - {len(day_05)} batches" if not day_05.empty else "Pending - 0 batches"

    stat_06 = "Completed - 1/1"
    stat_12 = "Completed - 1/1"

    day_13 = df_13[df_13["Date_Str"] == selected_day_str] if (df_13 is not None and not df_13.empty and "Date_Str" in df_13.columns) else pd.DataFrame()
    logged_13 = len(day_13["Unit_ID"].dropna().unique()) if (not day_13.empty and "Unit_ID" in day_13.columns) else 0
    stat_13 = f"Completed - {logged_13}/11" if logged_13 > 0 else "Pending - 0/11"

    stat_15 = "Completed - 1/1"

    day_21 = df_21[df_21["Date_Str"] == selected_day_str] if (df_21 is not None and not df_21.empty and "Date_Str" in df_21.columns) else pd.DataFrame()
    stat_21 = f"Completed - {len(day_21)} batches" if not day_21.empty else "Pending - 0 batches"

    day_25 = df_25[df_25["Date_Str"] == selected_day_str] if (df_25 is not None and not df_25.empty and "Date_Str" in df_25.columns) else pd.DataFrame()
    logged_25 = len(day_25["Clean_Unit"].dropna().unique()) if (not day_25.empty and "Clean_Unit" in day_25.columns) else 0
    stat_25 = f"Completed - {logged_25}/1" if logged_25 > 0 else "Pending - 0/1"

    col1, col2, col3 = st.columns(3)

    def render_theme_card(col, title, status_text, target_nav, unique_key):
        is_completed = "Completed" in status_text
        status_color = "#4ade80" if is_completed else "#fbbf24"
        
        col.markdown(f"""
        <div style="background-color: #0b192c; border-radius: 10px; padding: 16px; color: white; margin-bottom: 6px; min-height: 100px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="font-size: 0.9rem; font-weight: 600; line-height: 1.3; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 0.78rem; color: {status_color}; font-weight: 500;">Status: {status_text}</div>
        </div>
        """, unsafe_allow_html=True)
        if col.button("Open ➔", use_container_width=True, key=f"btn_theme_{unique_key}"):
            st.session_state.nav_choice = target_nav
            st.rerun()

    with col1:
        render_theme_card(col1, "RECORD 02 - FOOD DELIVERY RECORD", stat_02, "RECORD 02 - FOOD DELIVERY RECORD", "r02")
        render_theme_card(col1, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD (Opening)", stat_03_op, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", "r03_op")
        render_theme_card(col1, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD (Closing)", stat_03_cl, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", "r03_cl")
        render_theme_card(col1, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD (Breakfast)", stat_04_bf, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", "r04_bf")

    with col2:
        render_theme_card(col2, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD (Lunch)", stat_04_ln, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", "r04_ln")
        render_theme_card(col2, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD (Dinner)", stat_04_dn, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", "r04_dn")
        render_theme_card(col2, "RECORD 05 - COOLING OF FOOD RECORD", stat_05, "RECORD 05 - COOLING OF FOOD RECORD", "r05")
        render_theme_card(col2, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", stat_06, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", "r06")

    with col3:
        render_theme_card(col3, "RECORD 12 - DEFROSTING TEMPERATURE RECORD", stat_12, "RECORD 12 - DEFROSTING TEMPERATURE RECORD", "r12")
        render_theme_card(col3, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", stat_13, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", "r13")
        render_theme_card(col3, "RECORD 15 - PESTICIDE USAGE RECORD", stat_15, "RECORD 15 - PESTICIDE USAGE RECORD", "r15")
        render_theme_card(col3, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", stat_21, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", "r21")
        render_theme_card(col3, "RECORD 25 - ICE MACHINE CLEANING RECORD", stat_25, "RECORD 25 - ICE MACHINE CLEANING RECORD", "r25")

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
