from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records.record_03 import render_record_03_view, parse_record_03_submissions, UNIT_CATALOG, clean_unit_token
from records.record_04 import render_record_04_view, parse_all_record_04_dishes
from records.record_05 import render_record_05_view, parse_record_05_submissions
from records.record_06 import render_record_06_view, parse_record_06_submissions
from records.record_13 import render_record_13_view, parse_record_13_submissions
from records.record_15 import render_record_15_view, parse_record_15_submissions
from records.record_21 import render_record_21_view, parse_record_21_submissions
from records.record_25 import render_record_25_view, parse_record_25_submissions

st.set_page_config(
    page_title="Roswyn - EHCO Status",
    page_icon="🛡️",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    .stApp { background-color: #f8fafc; font-family: 'Plus Jakarta Sans', sans-serif; color: #0f172a; }
    
    /* Roswyn Monochrome Luxury Header */
    .executive-header {
        background: #000000;
        border: 1px solid #1e293b;
        border-radius: 14px;
        padding: 22px 30px;
        margin-bottom: 22px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15);
    }
    .serif-title { 
        font-size: 2rem; 
        font-weight: 800; 
        letter-spacing: -0.03em; 
        margin: 0; 
        color: #ffffff;
    }
    
    /* Deep Black Luxury Compliance Cards */
    .exec-card {
        background: #0b0f19;
        border: 1px solid #1e293b;
        border-top: 3px solid #38bdf8;
        border-radius: 12px;
        padding: 16px 18px;
        color: #ffffff;
        margin-bottom: 6px;
        min-height: 195px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .exec-card:hover {
        border-color: #38bdf8;
        box-shadow: 0 8px 24px rgba(56, 189, 248, 0.15);
        transform: translateY(-2px);
    }

    /* Sleek Open Button */
    .stButton > button {
        background: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #ffffff !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 0.72rem !important;
        padding: 5px 12px !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: none !important;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .stButton > button:hover {
        background: #38bdf8 !important;
        border-color: #38bdf8 !important;
        color: #0f172a !important;
        transform: translateY(-1px);
    }

    /* Hides default Streamlit multi-page navigation links in the sidebar */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    
    /* High-Contrast Luxury Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] .stMarkdown, 
    section[data-testid="stSidebar"] span {
        color: #0f172a !important;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

FORM_MAPPING = {
    "🏠 Roswyn - EHCO Status Overview": 0,
    "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD": 31373,
    "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD": 31374,
    "RECORD 05 - COOLING OF FOOD RECORD": 31375,
    "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD": 31376,
    "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD": 31382,
    "RECORD 15 - PESTICIDE USAGE RECORD": 31384,
    "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH": 31390,
    "RECORD 25 - ICE MACHINE CLEANING RECORD": 31393,
}

if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = "🏠 Roswyn - EHCO Status Overview"

def navigate_to(target_nav):
    st.session_state.nav_choice = target_nav
    st.session_state.nav_selectbox = target_nav

def go_to_overview():
    st.session_state.nav_choice = "🏠 Roswyn - EHCO Status Overview"
    st.session_state.nav_selectbox = "🏠 Roswyn - EHCO Status Overview"

# --- CLEANED SIDEBAR: INSPECTION CONTROLS ONLY ---
st.sidebar.markdown("""
<div style="padding: 8px 0; border-bottom: 1px solid #cbd5e1; margin-bottom: 12px;">
    <span style="font-size: 1rem; font-weight: 800; color: #000000; letter-spacing: -0.02em;">🛡️ EXECUTIVE CONTROLS</span>
</div>
""", unsafe_allow_html=True)

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

DEFAULT_TOKEN = st.secrets.get("auth_token", "").strip()
if not DEFAULT_TOKEN:
    DEFAULT_TOKEN = "PASTE_FALLBACK_TOKEN_HERE"

if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = DEFAULT_TOKEN

with st.sidebar.expander("🛠️ Advanced API & Token Settings"):
    api_url = st.text_input(
        "Endpoint URL", value="https://auth-api.blinkm.io/form-store", key="sb_api_endpoint_input"
    )

    token_input = st.text_area(
        "Bearer Token", 
        value=st.session_state["auth_token"], 
        height=70, 
        key="sb_bearer_token_input"
    )

    if token_input != st.session_state["auth_token"]:
        st.session_state["auth_token"] = token_input.strip()

active_token = st.session_state.get("auth_token", DEFAULT_TOKEN).strip()
clean_token = active_token.replace("Bearer ", "").strip()

nav_options = list(FORM_MAPPING.keys())
current_nav_index = nav_options.index(st.session_state.nav_choice) if st.session_state.nav_choice in nav_options else 0

st.sidebar.write("")
selected_record = st.sidebar.selectbox(
    "SELECT FOOD SAFETY RECORD", 
    options=nav_options, 
    index=current_nav_index,
    key="nav_selectbox"
)

if selected_record != st.session_state.nav_choice:
    st.session_state.nav_choice = selected_record
    st.rerun()

active_form_id = FORM_MAPPING[st.session_state.nav_choice]

# --- LIGHTNING FAST CACHED API FETCHER ---
@st.cache_data(ttl=600, show_spinner=False)
def fetch_incremental_persistent_data_cached(url, token, form_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://tehc-roswyn.data-manager.oneblink.io",
        "Referer": "https://tehc-roswyn.data-manager.oneblink.io/",
    }
    new_rows = []
    base_url = url.strip()
    for page in range(8):
        payload = {
            "formId": form_id,
            "paging": {"limit": 50, "offset": page * 50},
            "sorting": [{"property": "dateTimeSubmitted", "direction": "descending"}],
            "unwindRepeatableSets": True,
        }
        try:
            res = requests.post(base_url, headers=headers, json=payload, timeout=10)
            if res.status_code != 200:
                break
            data = res.json()
            items = data.get("submissions", []) if isinstance(data, dict) else data
            if not items:
                break
            new_rows.extend(items)
            if len(items) < 50:
                break
        except Exception:
            break
    return new_rows

force_refresh = st.sidebar.button("🔄 Sync Live Feed", key="sync_live_feed_btn", use_container_width=True)
if force_refresh:
    st.cache_data.clear()
    st.toast("⚡ Cache cleared and live feed resynced!", icon="🔄")

raw_records_df = fetch_incremental_persistent_data_cached(api_url, clean_token, active_form_id) if active_form_id != 0 else []
if isinstance(raw_records_df, list):
    raw_records_df = pd.DataFrame({"raw_record": raw_records_df})

def get_day_df(df, date_variants, target_date_obj):
    if df is None or df.empty:
        return pd.DataFrame()
    for col in ["Date_Str", "Date", "Audit_Date", "submissionDate", "Date_Display"]:
        if col in df.columns:
            m = df[df[col].astype(str).isin(date_variants)]
            if not m.empty:
                return m
    if "Date_Obj" in df.columns:
        m = df[df["Date_Obj"] == target_date_obj]
        if not m.empty:
            return m
    return pd.DataFrame()

def filter_by_focus_date(df, selected_day_str):
    if df is None or df.empty:
        return pd.DataFrame()

    date_col = next(
        (c for c in ["Date_Str", "Date", "date", "Audit_Date", "submissionDate", "Date_Display", "Timestamp_DT", "createdAt", "dateTimeSubmitted"]
         if c in df.columns),
        None
    )

    if date_col is None:
        return df.iloc[0:0]

    df_filtered = df.copy()
    
    df_filtered["_filter_date"] = pd.to_datetime(
        df_filtered[date_col],
        errors="coerce",
        dayfirst=True
    ).dt.date

    try:
        focus_date = pd.to_datetime(selected_day_str, format="%d/%m/%Y", errors="coerce").date()
        if pd.isna(focus_date):
            focus_date = pd.to_datetime(selected_day_str, errors="coerce").date()
    except Exception:
        focus_date = pd.to_datetime(selected_day_str, errors="coerce").date()

    if pd.isna(focus_date):
        return df.iloc[0:0]

    result = df_filtered[df_filtered["_filter_date"] == focus_date].copy()
    return result.drop(columns=["_filter_date"])

if st.session_state.nav_choice == "🏠 Roswyn - EHCO Status Overview":
    if "dashboard_view_mode" not in st.session_state:
        st.session_state.dashboard_view_mode = "📊 Overview Cards"

    # --- TOP HEADER ---
    st.markdown(f"""
    <div class="executive-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8; font-weight: 700; margin-bottom: 2px;">🏨 Roswyn • Mumbai</div>
                <div class="serif-title">EHCO Executive Compliance Dashboard</div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: #111827; border: 1px solid #374151; padding: 6px 14px; border-radius: 8px; text-align: right;">
                    <div style="font-size: 0.65rem; color: #9ca3af;">SYSTEM TIME (IST)</div>
                    <div style="font-size: 0.88rem; font-weight: 700; color: #ffffff;">{ist_now.strftime("%I:%M:%S %p")}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    mode_cols = st.columns([6, 3])
    with mode_cols[0]:
        selected_site = st.selectbox(
            "Select Site Portal",
            options=["🏨 Roswyn Mumbai", "🏰 Fairmont Mumbai"],
            index=0,
            label_visibility="collapsed",
            key="global_site_switcher_select"
        )
        if selected_site.startswith("🏰"):
            st.switch_page("pages/fairmont.py")

    with mode_cols[1]:
        view_choice = st.radio(
            "Dashboard Display Mode", 
            ["📊 Overview Cards", "🏢 Department-Wise Cards"], 
            horizontal=True,
            label_visibility="collapsed",
            key="dashboard_view_mode_radio"
        )
        if view_choice != st.session_state.dashboard_view_mode:
            st.session_state.dashboard_view_mode = view_choice
            st.rerun()

    st.write("")
    st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; padding: 10px 16px; border-radius: 10px; font-weight: 600; font-size: 0.88rem; color: #0f172a; display: inline-flex; align-items:center; gap:8px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
            <span style="font-size:1.1rem;">📅</span> Focus Audit Date: <span style="color:#000000; font-weight:700;">{selected_day_str}</span>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    @st.cache_data(ttl=600, show_spinner=False)
    def load_all_roswyn_records(token, endpoint):
        return {
            31373: parse_record_03_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31373)})),
            31374: parse_all_record_04_dishes(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31374)})),
            31375: parse_record_05_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31375)})),
            31376: parse_record_06_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31376)})),
            31382: parse_record_13_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31382)})),
            31384: parse_record_15_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31384)})),
            31390: parse_record_21_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31390)})),
            31393: parse_record_25_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(endpoint, token, 31393)})),
        }

    cache = load_all_roswyn_records(clean_token, api_url)
    df_03_parsed = cache.get(31373, pd.DataFrame())
    df_04_parsed = cache.get(31374, pd.DataFrame())
    df_05_parsed = cache.get(31375, pd.DataFrame())
    df_06_parsed = cache.get(31376, pd.DataFrame())
    df_13_parsed = cache.get(31382, pd.DataFrame())
    df_15_parsed = cache.get(31384, pd.DataFrame())
    df_21_parsed = cache.get(31390, pd.DataFrame())
    df_25_parsed = cache.get(31393, pd.DataFrame())

    target_date_obj = datetime.strptime(selected_day_str, "%d/%m/%Y").date()
    next_date_obj = target_date_obj + timedelta(days=1)

    if not df_03_parsed.empty and "Timestamp_DT" in df_03_parsed.columns:
        df_03_parsed["Timestamp_DT"] = pd.to_datetime(df_03_parsed["Timestamp_DT"], errors="coerce")

    day_03 = df_03_parsed[
        (df_03_parsed["Date_Obj"] == target_date_obj) |
        ((df_03_parsed["Date_Obj"] == next_date_obj) & (df_03_parsed["Timestamp_DT"].dt.hour < 5))
    ] if not df_03_parsed.empty and "Date_Obj" in df_03_parsed.columns else filter_by_focus_date(df_03_parsed, selected_day_str)

    # --- RECORD 03 STATS ---
    global_opening_logged = 0
    global_closing_logged = 0
    global_total_units = 0

    for loc_name, units in UNIT_CATALOG.items():
        for u in units:
            global_total_units += 1
            u_id = u["Unit_ID"]
            clean_target = clean_unit_token(u_id)
            unit_logs = day_03[day_03["Clean_Unit"] == clean_target] if not day_03.empty and "Clean_Unit" in day_03.columns else pd.DataFrame()
            n_logs = len(unit_logs)
            if n_logs == 1:
                global_opening_logged += 1
            elif n_logs >= 2:
                global_opening_logged += 1
                global_closing_logged += 1

    is_op_complete = (global_opening_logged >= global_total_units)
    is_cl_complete = (global_closing_logged >= global_total_units)

    stat_03_op_str = f"Completed - {global_opening_logged}/{global_total_units}" if is_op_complete else f"Pending - {global_opening_logged}/{global_total_units}"
    stat_03_cl_str = f"Completed - {global_closing_logged}/{global_total_units}" if is_cl_complete else f"Pending - {global_closing_logged}/{global_total_units}"
    html_03 = f'Opening: <span style="color: {"#4ade80" if is_op_complete else "#fbbf24"}; font-weight: 600;">{stat_03_op_str}</span><br>Closing: <span style="color: {"#4ade80" if is_cl_complete else "#fbbf24"}; font-weight: 600;">{stat_03_cl_str}</span>'

    # --- RECORD 04 EXACT RULES (Filia: B, L, D | Black Lacquer: D) ---
    ROSWYN_KITCHEN_RULES = {
        "Filia Kitchen": ["Breakfast", "Lunch", "Dinner"],
        "Black Lacquer Kitchen": ["Dinner"]
    }
    
    day_04 = filter_by_focus_date(df_04_parsed, selected_day_str)
    r04_completed_shifts = 0
    r04_total_shifts = 4
    r04_status_lines = []

    for kitchen, meals in ROSWYN_KITCHEN_RULES.items():
        k_df = day_04[day_04["Location"].str.strip().str.lower() == kitchen.lower()] if not day_04.empty else pd.DataFrame()
        for meal in meals:
            m_df = k_df[k_df["Meal_Service"].str.strip().str.lower() == meal.lower()] if not k_df.empty else pd.DataFrame()
            if not m_df.empty:
                r04_completed_shifts += 1
                r04_status_lines.append(f'{meal} ({kitchen.split()[0]}): <span style="color: #4ade80; font-weight: 600;">Completed</span>')
            else:
                r04_status_lines.append(f'{meal} ({kitchen.split()[0]}): <span style="color: #fbbf24; font-weight: 600;">Pending</span>')

    html_04 = "<br>".join(r04_status_lines)
    is_04_complete = (r04_completed_shifts >= r04_total_shifts)

    # --- TRUE-DATA METRICS FOR 05, 13, 15, 21, 25 (STRICTLY FOCUS DAY) ---
    day_05 = filter_by_focus_date(df_05_parsed, selected_day_str)
    if not day_05.empty:
        stat_05 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_05)} items cooled</span>'
    else:
        stat_05 = '<span style="color: #fbbf24; font-weight: 600;">Pending - No Cooling Logged</span>'

    day_06 = filter_by_focus_date(df_06_parsed, selected_day_str)
    is_06_complete = not day_06.empty
    stat_06 = f'<span style="color: {"#4ade80" if is_06_complete else "#fbbf24"}; font-weight: 600;">{"Completed" if is_06_complete else "Pending"} - {1 if is_06_complete else 0}/1</span>'
    
    day_13 = filter_by_focus_date(df_13_parsed, selected_day_str)
    if not day_13.empty:
        unit_col = next((c for c in ["Unit_ID", "Machine_Name", "Equipment", "Name"] if c in day_13.columns), None)
        units_logged = day_13[unit_col].dropna().unique().tolist() if unit_col else []
        logged_13_count = min(11, len(units_logged))
        is_13_complete = (logged_13_count >= 11)
        stat_13 = f'<span style="color: {"#4ade80" if is_13_complete else "#fbbf24"}; font-weight: 600;">{"Completed" if is_13_complete else "Pending"} - {logged_13_count}/11 unique machines</span>'
    else:
        stat_13 = '<span style="color: #fbbf24; font-weight: 600;">Pending - 0/11 unique machines</span>'
    
    day_15 = filter_by_focus_date(df_15_parsed, selected_day_str)
    if not day_15.empty:
        stat_15 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_15)} entries</span>'
    else:
        stat_15 = '<span style="color: #fbbf24; font-weight: 600;">Pending - 0 entries</span>'
    
    day_21 = filter_by_focus_date(df_21_parsed, selected_day_str)
    if not day_21.empty:
        stat_21 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_21)} areas</span>'
    else:
        stat_21 = '<span style="color: #fbbf24; font-weight: 600;">Pending - 0 areas</span>'
    
    day_25 = filter_by_focus_date(df_25_parsed, selected_day_str)
    if not day_25.empty:
        stat_25 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_25)} entries</span>'
    else:
        stat_25 = '<span style="color: #fbbf24; font-weight: 600;">Pending - 0 entries</span>'

    completed_cats = sum([
        1 if is_op_complete and is_cl_complete else 0,
        1 if is_04_complete else 0,
        1 if not day_05.empty else 0,
        1 if is_06_complete else 0,
        1 if is_13_complete else 0,
        1 if not day_15.empty else 0,
        1 if not day_21.empty else 0,
        1 if not day_25.empty else 0
    ])
    total_cats = 8
    progress_pct = int((completed_cats / total_cats) * 100)
    bar_color = "#4ade80" if progress_pct > 70 else ("#38bdf8" if progress_pct > 30 else "#fbbf24")

    if st.session_state.dashboard_view_mode == "📊 Overview Cards":
        st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 700; font-size: 0.9rem; color: #0f172a; display:flex; align-items:center; gap:8px;">📊 Daily Compliance & Progression Tracker</span>
                <span style="font-weight: 800; font-size: 0.88rem; color: {bar_color}; background: #f1f5f9; padding: 3px 10px; border-radius: 6px; border: 1px solid #cbd5e1;">{progress_pct}% Completed ({completed_cats}/{total_cats} Categories)</span>
            </div>
            <div style="width: 100%; background: #e2e8f0; border-radius: 6px; height: 8px; overflow: hidden;">
                <div style="width: {progress_pct}%; background: linear-gradient(90deg, {bar_color} 0%, #000000 100%); height: 100%; border-radius: 6px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        def render_executive_tile(col, title, status_html, target_nav, unique_key):
            with col:
                card_html = f"""
                <div class="exec-card">
                    <div>
                        <div style="font-size: 0.82rem; font-weight: 700; line-height: 1.3; margin-bottom: 6px; letter-spacing: -0.01em; color: #ffffff;">{title}</div>
                        <div style="font-size: 0.74rem; color: #94a3b8; font-weight: 500; line-height: 1.4;">{status_html}</div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button("Open ➔", key=f"tile_btn_{unique_key}", use_container_width=True):
                    navigate_to(target_nav)
                    st.rerun()

        with col1:
            render_executive_tile(col1, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", html_03, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", "r03")
            render_executive_tile(col1, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", html_04, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", "r04")

        with col2:
            render_executive_tile(col2, "RECORD 05 - COOLING OF FOOD RECORD", stat_05, "RECORD 05 - COOLING OF FOOD RECORD", "r05")
            render_executive_tile(col2, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", stat_06, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", "r06")

        with col3:
            render_executive_tile(col3, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", stat_13, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", "r13")
            render_executive_tile(col3, "RECORD 15 - PESTICIDE USAGE RECORD", stat_15, "RECORD 15 - PESTICIDE USAGE RECORD", "r15")

        col4, col5, col6 = st.columns(3)
        with col4:
            render_executive_tile(col4, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", stat_21, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", "r21")
        with col5:
            render_executive_tile(col5, "RECORD 25 - ICE MACHINE CLEANING RECORD", stat_25, "RECORD 25 - ICE MACHINE CLEANING RECORD", "r25")
    else:
        st.markdown(f"<h3 style='color:#0f172a; margin-top:0.5rem;'>🏢 Department-Wise Compliance Cards ({selected_day_str})</h3>", unsafe_allow_html=True)
        st.write("Department-wise overview for Roswyn")

        dept_cols = st.columns(3)
        def render_dept_card(col, dept_name, rec_tuples):
            items_html = ""
            for r_title, r_status in rec_tuples:
                items_html += f"""
                <div style="background: #0b0f19; padding: 10px 12px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #1e293b;">
                    <div style="font-weight: 600; font-size: 0.85rem; color: #ffffff; margin-bottom: 2px;">{r_title}</div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">{r_status}</div>
                </div>
                """
            col.markdown(f"""
            <div style="background: #ffffff; border-radius: 14px; padding: 20px; color: #0f172a; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; border-top: 3px solid #000000;">
                <div style="font-size: 1.1rem; font-weight: 800; color: #000000; margin-bottom: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px;">🏢 {dept_name}</div>
                {items_html}
            </div>
            """, unsafe_allow_html=True)

        with dept_cols[0]:
            render_dept_card(dept_cols[0], "Purchase", [("RECORD 03 - TEMPERATURE RECORD", html_03.replace("<br>", " | "))])
        with dept_cols[1]:
            render_dept_card(dept_cols[1], "Stewarding", [("RECORD 13 - DISHWASHER", stat_13), ("RECORD 25 - ICE MACHINE", stat_25)])
        with dept_cols[2]:
            render_dept_card(dept_cols[2], "Housekeeping", [("RECORD 13 - DISHWASHER", stat_13), ("RECORD 15 - PESTICIDE USAGE", stat_15)])
else:
    # --- DRILL-DOWN VIEWS HEADER ---
    hdr_cols = st.columns([3, 4, 3])
    with hdr_cols[0]:
        selected_site_sub = st.selectbox(
            "Select Site Portal",
            options=["🏨 Roswyn Mumbai", "🏰 Fairmont Mumbai"],
            index=0,
            label_visibility="collapsed",
            key="global_site_switcher_select_sub"
        )
        if selected_site_sub.startswith("🏰"):
            st.switch_page("pages/fairmont.py")

    with hdr_cols[1]:
        st.markdown(f'<div class="serif-title" style="font-size:1.4rem;">{st.session_state.nav_choice}</div>', unsafe_allow_html=True)

    with hdr_cols[2]:
        st.markdown(f"""
            <div style="background: #000000; color: white; padding: 8px 14px; border-radius: 10px; font-weight: 500; font-size: 0.78rem; text-align: right; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: 1px solid #334155;">
                <div>🕒 IST: <span style="color: #ffffff; font-weight:700;">{ist_now.strftime("%I:%M:%S %p")}</span></div>
                <div style="color: #94a3b8; font-size: 0.7rem; margin-top: 2px;">Status: <span style="color:#4ade80; font-weight:600;">Live Synced</span></div>
            </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.button("← Back to EHCO Status Overview", key="back_to_overview_top_btn", on_click=go_to_overview)
    st.write("")

    if st.session_state.nav_choice == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
        render_record_03_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.nav_choice == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
        render_record_04_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.nav_choice == "RECORD 05 - COOLING OF FOOD RECORD":
        render_record_05_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.nav_choice == "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD":
        render_record_06_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.nav_choice == "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD":
        render_record_13_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.nav_choice == "RECORD 15 - PESTICIDE USAGE RECORD":
        render_record_15_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.nav_choice == "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH":
        render_record_21_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.nav_choice == "RECORD 25 - ICE MACHINE CLEANING RECORD":
        render_record_25_view(raw_records_df, selected_day_str, start_date, end_date)
