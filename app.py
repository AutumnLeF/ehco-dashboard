from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records.record_02 import render_record_02_view, parse_record_02_submissions
from records.record_03 import render_record_03_view, parse_record_03_submissions
from records.record_04 import render_record_04_view, parse_all_record_04_dishes
from records.record_05 import render_record_05_view, parse_record_05_submissions
from records.record_06 import render_record_06_view, parse_record_06_submissions
from records.record_12 import render_record_12_view
from records.record_13 import render_record_13_view, parse_record_13_submissions
from records.record_15 import render_record_15_view, parse_record_15_submissions
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
    
    .center-header {
        text-align: center;
        margin-bottom: 1.2rem;
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
st.sidebar.markdown("**Site:** Roswyn (Site 1)")

ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
today = ist_now.date()
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

def get_date_variants(d_str):
    variants = {d_str, d_str.replace("/", "-")}
    try:
        d_obj = datetime.strptime(d_str, "%d/%m/%Y")
        variants.add(d_obj.strftime("%Y-%m-%d"))
        variants.add(d_obj.strftime("%d-%m-%Y"))
    except Exception:
        pass
    return list(variants)

selected_day_variants = get_date_variants(selected_day_str)

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

nav_options = list(FORM_MAPPING.keys())
current_nav_index = nav_options.index(st.session_state.nav_choice) if st.session_state.nav_choice in nav_options else 0

selected_record = st.sidebar.selectbox(
    "SELECT FOOD SAFETY RECORD", 
    options=nav_options, 
    index=current_nav_index,
    key="nav_selectbox"
)

if selected_record != st.session_state.nav_choice:
    st.session_state.nav_choice = selected_record
    st.session_state.pop("nav_selectbox", None)
    st.rerun()

active_form_id = FORM_MAPPING[st.session_state.nav_choice]

# -------------------------------------------------------------
# 3. UNIFIED MASTER DATA FETCHING & CACHING
# -------------------------------------------------------------
def fetch_submissions(url, token, form_id, start_dt, end_dt, unwind=True):
    if not form_id or form_id == 0:
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

    for page in range(15):
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
            "unwindRepeatableSets": unwind,
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

if "master_data_cache" not in st.session_state:
    st.session_state["master_data_cache"] = {}

force_refresh = st.sidebar.button("🔄 Sync Live Feed", key="sync_live_feed_btn", use_container_width=True)
if force_refresh:
    st.session_state["master_data_cache"] = {}

def get_master_df(form_id, unwind=True):
    cache_key = f"{form_id}_unwind_{unwind}"
    if cache_key not in st.session_state["master_data_cache"]:
        items = fetch_submissions(api_url, clean_token, form_id, start_date, end_date, unwind=unwind)
        st.session_state["master_data_cache"][cache_key] = pd.DataFrame({"raw_record": items}) if items else pd.DataFrame()
    return st.session_state["master_data_cache"][cache_key]

def filter_by_focus_date(df, date_variants):
    if df is None or df.empty:
        return pd.DataFrame()
    for col in ["Date_Str", "Date", "Audit_Date", "submissionDate", "Date_Display"]:
        if col in df.columns:
            m = df[df[col].astype(str).isin(date_variants)]
            if not m.empty:
                return m
    try:
        m = df[df.apply(lambda r: any(v in str(r.to_dict()) for v in date_variants), axis=1)]
        if not m.empty:
            return m
    except Exception:
        pass
    return pd.DataFrame()

raw_records_df = get_master_df(active_form_id, unwind=True) if active_form_id != 0 else pd.DataFrame()

# -------------------------------------------------------------
# 4. ROUTE TO OVERVIEW OR INDIVIDUAL RECORD VIEW
# -------------------------------------------------------------
if st.session_state.nav_choice == "🏠 Roswyn - EHCO Status Overview":
    st.markdown("""
        <div class="center-header">
            <div class="serif-title">Roswyn - EHCO Status</div>
            <div class="sub-head">Date: <b>{date_str}</b> &nbsp;|&nbsp; IST Time: <b>{time_str}</b></div>
        </div>
    """.format(date_str=selected_day_str, time_str=ist_now.strftime("%H:%M:%S")), unsafe_allow_html=True)

    # Master Data parsing
    raw_03 = get_master_df(31373, unwind=True)
    raw_04 = get_master_df(31374, unwind=True)
    df_03_parsed = parse_record_03_submissions(raw_03)
    df_04_parsed = parse_all_record_04_dishes(raw_04)
    df_05 = parse_record_05_submissions(get_master_df(31375, unwind=True))
    df_06 = parse_record_06_submissions(get_master_df(31376, unwind=True))
    df_13 = parse_record_13_submissions(get_master_df(31382, unwind=True))
    df_21 = parse_record_21_submissions(get_master_df(31390, unwind=True))
    df_25 = parse_record_25_submissions(get_master_df(31393, unwind=True))

    # Record 03 Unit Counter Calculation (Out of 35 total units)
    day_03 = filter_by_focus_date(df_03_parsed, selected_day_variants)
    op_units = 0
    cl_units = 0
    if not day_03.empty and "Shift" in day_03.columns:
        op_df = day_03[day_03["Shift"].astype(str).str.lower().str.contains("open", na=False)]
        cl_df = day_03[day_03["Shift"].astype(str).str.lower().str.contains("clos", na=False)]
        # Count unique units logged across locations
        op_units = len(op_df) if "Unit_Name" not in op_df.columns else op_df["Unit_Name"].nunique()
        cl_units = len(cl_df) if "Unit_Name" not in cl_df.columns else cl_df["Unit_Name"].nunique()

    stat_03_op_str = f"Completed - {op_units}/35" if op_units > 0 else "Pending - 0/35"
    stat_03_cl_str = f"Completed - {cl_units}/35" if cl_units > 0 else "Pending - 0/35"
    html_03 = f'Opening: <span style="color: {"#4ade80" if op_units > 0 else "#fbbf24"}; font-weight: 600;">{stat_03_op_str}</span><br>Closing: <span style="color: {"#4ade80" if cl_units > 0 else "#fbbf24"}; font-weight: 600;">{stat_03_cl_str}</span>'

    # Record 04 Evaluation
    day_04 = filter_by_focus_date(df_04_parsed, selected_day_variants)
    bf_count, ln_count, dn_count = 0, 0, 0
    if not day_04.empty and "Meal_Shift" in day_04.columns:
        bf_shifts = day_04[day_04["Meal_Shift"].astype(str).str.lower().str.contains("break", na=False)]
        ln_shifts = day_04[day_04["Meal_Shift"].astype(str).str.lower().str.contains("lunch", na=False)]
        dn_shifts = day_04[day_04["Meal_Shift"].astype(str).str.lower().str.contains("dinner", na=False)]
        bf_count = 1 if not bf_shifts.empty else 0
        ln_count = 1 if not ln_shifts.empty else 0
        dn_count = dn_shifts["Kitchen"].nunique() if ("Kitchen" in dn_shifts.columns and not dn_shifts.empty) else 0

    stat_04_bf_str = f"Completed - {bf_count}/1" if bf_count > 0 else "Pending - 0/1"
    stat_04_ln_str = f"Completed - {ln_count}/1" if ln_count > 0 else "Pending - 0/1"
    stat_04_dn_str = f"Completed - {dn_count}/2" if dn_count > 0 else "Pending - 0/2"
    html_04 = f'Breakfast: <span style="color: {"#4ade80" if bf_count > 0 else "#fbbf24"}; font-weight: 600;">{stat_04_bf_str}</span><br>Lunch: <span style="color: {"#4ade80" if ln_count > 0 else "#fbbf24"}; font-weight: 600;">{stat_04_ln_str}</span><br>Dinner: <span style="color: {"#4ade80" if dn_count > 0 else "#fbbf24"}; font-weight: 600;">{stat_04_dn_str}</span>'

    # Record 05
    day_05 = filter_by_focus_date(df_05, selected_day_variants)
    stat_05 = f'<span style="color: {"#4ade80" if not day_05.empty else "#fbbf24"}; font-weight: 600;">{"Completed" if not day_05.empty else "Pending"} - {len(day_05)} batches</span>'

    # Record 06
    day_06 = filter_by_focus_date(df_06, selected_day_variants)
    stat_06 = f'<span style="color: {"#4ade80" if not day_06.empty else "#fbbf24"}; font-weight: 600;">{"Completed" if not day_06.empty else "Pending"} - 1/1</span>'

    # Record 13
    day_13 = filter_by_focus_date(df_13, selected_day_variants)
    logged_13 = len(day_13["Unit_ID"].dropna().unique()) if (not day_13.empty and "Unit_ID" in day_13.columns) else 0
    is_13_complete = (logged_13 >= 11)
    stat_13 = f'<span style="color: {"#4ade80" if is_13_complete else "#fbbf24"}; font-weight: 600;">{"Completed" if is_13_complete else "Pending"} - {logged_13}/11</span>'

    # Record 15
    day_15_raw = get_master_df(31384, unwind=True)
    logged_15 = 0
    if not day_15_raw.empty:
        for _, row in day_15_raw.iterrows():
            r_str = str(row.get("raw_record", {})).lower()
            if any(v in r_str for v in selected_day_variants):
                logged_15 += 1
    stat_15 = f'<span style="color: {"#4ade80" if logged_15 > 0 else "#fbbf24"}; font-weight: 600;">{"Completed" if logged_15 > 0 else "Pending"} - {logged_15}/1</span>'

    # Record 21
    day_21 = filter_by_focus_date(df_21, selected_day_variants)
    stat_21 = f'<span style="color: {"#4ade80" if not day_21.empty else "#fbbf24"}; font-weight: 600;">{"Completed" if not day_21.empty else "Pending"} - {len(day_21)} batches</span>'

    # Record 25
    day_25 = filter_by_focus_date(df_25, selected_day_variants)
    logged_25 = len(day_25["Clean_Unit"].dropna().unique()) if (not day_25.empty and "Clean_Unit" in day_25.columns) else 0
    stat_25 = f'<span style="color: {"#4ade80" if logged_25 > 0 else "#fbbf24"}; font-weight: 600;">{"Completed" if logged_25 > 0 else "Pending"} - {logged_25}/1</span>'

    # Daily Compliance Tracker calculation
    completed_cats = sum([
        1 if op_units > 0 else 0,
        1 if bf_count > 0 else 0,
        1 if not day_05.empty else 0,
        1 if not day_06.empty else 0,
        1 if is_13_complete else 0,
        1 if logged_15 > 0 else 0,
        1 if not day_21.empty else 0,
        1 if logged_25 > 0 else 0
    ])
    total_cats = 9
    progress_pct = int((completed_cats / total_cats) * 100)
    bar_color = "#4ade80" if progress_pct > 70 else ("#3b82f6" if progress_pct > 30 else "#fbbf24")

    st.markdown(f"""
    <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 14px 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-weight: 700; font-size: 0.88rem; color: #0f172a;">📊 Daily Compliance & Progression Tracker</span>
            <span style="font-weight: 700; font-size: 0.88rem; color: {bar_color};">{progress_pct}% Completed ({completed_cats}/{total_cats} Categories)</span>
        </div>
        <div style="width: 100%; background: #e2e8f0; border-radius: 8px; height: 12px; overflow: hidden;">
            <div style="width: {progress_pct}%; background: {bar_color}; height: 100%; border-radius: 8px; transition: width 0.5s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    def render_theme_card(col, title, status_html, target_nav, unique_key):
        col.markdown(f"""
        <div style="background-color: #0b192c; border-radius: 10px; padding: 16px; color: white; margin-bottom: 6px; min-height: 115px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="font-size: 0.88rem; font-weight: 600; line-height: 1.3; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 0.78rem; color: #cbd5e1; font-weight: 500; line-height: 1.4;">{status_html}</div>
        </div>
        """, unsafe_allow_html=True)
        if col.button("Open ➔", use_container_width=True, key=f"btn_theme_{unique_key}"):
            st.session_state.nav_choice = target_nav
            st.session_state.pop("nav_selectbox", None)
            st.rerun()

    with col1:
        render_theme_card(col1, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", html_03, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", "r03")
        render_theme_card(col1, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", html_04, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", "r04")

    with col2:
        render_theme_card(col2, "RECORD 05 - COOLING OF FOOD RECORD", stat_05, "RECORD 05 - COOLING OF FOOD RECORD", "r05")
        render_theme_card(col2, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", stat_06, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", "r06")
        render_theme_card(col2, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", stat_13, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", "r13")

    with col3:
        render_theme_card(col3, "RECORD 15 - PESTICIDE USAGE RECORD", stat_15, "RECORD 15 - PESTICIDE USAGE RECORD", "r15")
        render_theme_card(col3, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", stat_21, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", "r21")
        render_theme_card(col3, "RECORD 25 - ICE MACHINE CLEANING RECORD", stat_25, "RECORD 25 - ICE MACHINE CLEANING RECORD", "r25")

else:
    # Individual drill-down page view
    if st.button("← Back to EHCO Status Overview", key="back_to_overview_top_btn"):
        st.session_state.nav_choice = "🏠 Roswyn - EHCO Status Overview"
        st.session_state.pop("nav_selectbox", None)
        st.rerun()
    st.write("")

    if st.session_state.nav_choice == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
        st.markdown(f'<div class="record-header-box">❄️ {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_03_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 02 - FOOD DELIVERY RECORD":
        st.markdown(f'<div class="record-header-box">🚚 {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_02_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
        st.markdown(f'<div class="record-header-box">🔥 {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_04_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 05 - COOLING OF FOOD RECORD":
        st.markdown(f'<div class="record-header-box">🧊 {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_05_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD":
        st.markdown(f'<div class="record-header-box">🍲 {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_06_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 12 - DEFROSTING TEMPERATURE RECORD":
        st.markdown(f'<div class="record-header-box">🌡️ {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_12_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD":
        st.markdown(f'<div class="record-header-box">🍽️ {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_13_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 15 - PESTICIDE USAGE RECORD":
        st.markdown(f'<div class="record-header-box">🌿 {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_15_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH":
        st.markdown(f'<div class="record-header-box">🥗 {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_21_view(raw_records_df, selected_day_str, start_date, end_date)

    elif st.session_state.nav_choice == "RECORD 25 - ICE MACHINE CLEANING RECORD":
        st.markdown(f'<div class="record-header-box">🧊 {st.session_state.nav_choice}</div>', unsafe_allow_html=True)
        render_record_25_view(raw_records_df, selected_day_str, start_date, end_date)

# -------------------------------------------------------------
# 5. LIVE MULTI-FORM DIAGNOSTIC MATRIX
# -------------------------------------------------------------
st.divider()
with st.expander("🛠️ Live Form Ingestion & Memory Diagnostic Matrix", expanded=False):
    st.markdown(f"**Focus Day Selected:** `{selected_day_str}` (Searching formats: `{selected_day_variants}`)")
    st.markdown(f"**Current Navigation Choice:** `{st.session_state.nav_choice}` (Form ID: `{active_form_id}`)")

    diag_data = []
    for form_name, fid in FORM_MAPPING.items():
        if fid == 0:
            continue
        df_cached = get_master_df(fid, unwind=True)
        total_rows = len(df_cached)
        matching_rows = 0
        if total_rows > 0:
            for _, r in df_cached.iterrows():
                r_str = str(r.get("raw_record", {}))
                if any(v in r_str for v in selected_day_variants):
                    matching_rows += 1

        diag_data.append({
            "Form Name": form_name.split(" - ")[0],
            "Form ID": fid,
            "Total Ingested": total_rows,
            f"Logs on {selected_day_str}": matching_rows,
            "Memory Status": "✅ Loaded" if total_rows > 0 else "⚠️ Empty"
        })

    st.dataframe(pd.DataFrame(diag_data), use_container_width=True, hide_index=True)
