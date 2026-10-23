from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records.record_03 import render_record_03_view, parse_record_03_submissions, UNIT_CATALOG, clean_unit_token
from records.record_04 import render_record_04_view, parse_all_record_04_dishes
from records.record_05 import render_record_05_view, parse_record_05_submissions
from records.record_06 import render_record_06_view, parse_record_06_submissions
from records.record_13 import render_record_13_view, parse_record_13_submissions, LOCATION_CATALOG as RECORD_13_CATALOG
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
    
    /* Roswyn Monochrome Luxury Header with Glassmorphism */
    .executive-header {
        background: rgba(0, 0, 0, 0.92);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 14px;
        padding: 22px 30px;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.25);
    }
    .serif-title { 
        font-size: 2rem; 
        font-weight: 800; 
        letter-spacing: -0.03em; 
        margin: 0; 
        color: #ffffff;
    }
    
    /* Completed Cards */
    .exec-card-completed {
        background: rgba(11, 15, 25, 0.95);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(30, 41, 59, 0.8);
        border-top: 4px solid #38bdf8;
        border-radius: 12px;
        padding: 18px 20px;
        color: #ffffff;
        margin-bottom: 12px;
        min-height: 220px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s ease;
    }
    .exec-card-completed:hover {
        border-color: #38bdf8;
        box-shadow: 0 10px 30px rgba(56, 189, 248, 0.25);
        transform: translateY(-3px);
    }

    /* Pending Cards - Highly Visible Amber Tint & Border */
    .exec-card-pending {
        background: rgba(26, 21, 10, 0.95);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(120, 90, 20, 0.8);
        border-top: 4px solid #fbbf24;
        border-radius: 12px;
        padding: 18px 20px;
        color: #ffffff;
        margin-bottom: 12px;
        min-height: 220px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 4px 25px rgba(251, 191, 36, 0.15);
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s ease;
    }
    .exec-card-pending:hover {
        border-color: #fbbf24;
        box-shadow: 0 10px 35px rgba(251, 191, 36, 0.3);
        transform: translateY(-3px);
    }

    /* Executive Typography & Pill Badge Polish */
    .exec-card-title {
        font-size: 0.82rem;
        font-weight: 700;
        line-height: 1.35;
        margin-bottom: 8px;
        letter-spacing: -0.01em;
        color: #ffffff;
    }
    .exec-card-body {
        font-size: 0.74rem;
        color: #cbd5e1;
        font-weight: 500;
        line-height: 1.45;
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(51, 65, 85, 0.5);
        border-radius: 8px;
        padding: 8px 10px;
    }
    .exec-card-body-pending {
        font-size: 0.74rem;
        color: #fef08a;
        font-weight: 500;
        line-height: 1.45;
        background: rgba(40, 30, 10, 0.6);
        border: 1px solid rgba(120, 90, 20, 0.6);
        border-radius: 8px;
        padding: 8px 10px;
    }

    [data-testid="stSidebarNav"] { display: none; }
    
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
    st.rerun()

def go_to_overview():
    st.session_state.nav_choice = "🏠 Roswyn - EHCO Status Overview"
    st.rerun()

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

    st.markdown(f"""
    <div class="executive-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8; font-weight: 700; margin-bottom: 2px;">🏨 Roswyn • Mumbai</div>
                <div class="serif-title">EHCO Executive Compliance Dashboard</div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: rgba(17, 24, 39, 0.8); border: 1px solid rgba(55, 65, 81, 0.8); padding: 6px 14px; border-radius: 8px; text-align: right;">
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
    pending_locs_03_opening = []
    pending_locs_03_closing = []

    for loc_name, units in UNIT_CATALOG.items():
        loc_op_missing = False
        loc_cl_missing = False
        for u in units:
            global_total_units += 1
            u_id = u["Unit_ID"]
            clean_target = clean_unit_token(u_id)
            unit_logs = day_03[day_03["Clean_Unit"] == clean_target] if not day_03.empty and "Clean_Unit" in day_03.columns else pd.DataFrame()
            n_logs = len(unit_logs)
            if n_logs == 1:
                global_opening_logged += 1
                loc_cl_missing = True
            elif n_logs >= 2:
                global_opening_logged += 1
                global_closing_logged += 1
            else:
                loc_op_missing = True
                loc_cl_missing = True
        if loc_op_missing and loc_name not in pending_locs_03_opening:
            pending_locs_03_opening.append(loc_name)
        if loc_cl_missing and loc_name not in pending_locs_03_closing:
            pending_locs_03_closing.append(loc_name)

    is_op_complete = (global_opening_logged >= global_total_units)
    is_cl_complete = (global_closing_logged >= global_total_units)
    is_03_complete = is_op_complete and is_cl_complete

    if is_03_complete:
        html_03 = '<span style="color: #4ade80; font-weight: 600;">Completed - All shifts logged</span>'
    else:
        op_str = f"Completed - {global_opening_logged}/{global_total_units}" if is_op_complete else f"Pending ({global_opening_logged}/{global_total_units})<br><span style='font-size:0.65rem; color:#cbd5e1;'>Opening Missing: {', '.join(pending_locs_03_opening)}</span>"
        cl_str = f"Completed - {global_closing_logged}/{global_total_units}" if is_cl_complete else f"Pending ({global_closing_logged}/{global_total_units})<br><span style='font-size:0.65rem; color:#cbd5e1;'>Closing Missing: {', '.join(pending_locs_03_closing)}</span>"
        html_03 = f'Opening: <span style="color: {"#4ade80" if is_op_complete else "#fde047"}; font-weight: 600;">{op_str}</span><br>Closing: <span style="color: {"#4ade80" if is_cl_complete else "#fde047"}; font-weight: 600;">{cl_str}</span>'

    # --- RECORD 04 EXACT RULES ---
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
                r04_status_lines.append(f'{meal} ({kitchen.split()[0]}): <span style="color: #fde047; font-weight: 600;">Pending</span>')

    html_04 = "<br>".join(r04_status_lines)
    is_04_complete = (r04_completed_shifts >= r04_total_shifts)

    # --- RECORD 05 METRICS ---
    day_05 = filter_by_focus_date(df_05_parsed, selected_day_str)
    is_05_complete = not day_05.empty
    if is_05_complete:
        stat_05 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_05)} items cooled</span>'
    else:
        stat_05 = '<span style="color: #fde047; font-weight: 600;">Pending - No Cooling Logged</span>'

    # --- RECORD 06 METRICS ---
    day_06 = filter_by_focus_date(df_06_parsed, selected_day_str)
    is_06_complete = not day_06.empty
    stat_06 = f'<span style="color: {"#4ade80" if is_06_complete else "#fde047"}; font-weight: 600;">{"Completed" if is_06_complete else "Pending"} - {1 if is_06_complete else 0}/1</span>'
    
    # --- RECORD 13 METRICS (DYNAMIC CATALOG EXTRACTION) ---
    day_13 = filter_by_focus_date(df_13_parsed, selected_day_str)
    
    flat_master_13 = []
    for loc, units in RECORD_13_CATALOG.items():
        for u in units:
            flat_master_13.append({"Unit_ID": u["Unit_ID"], "Type": u["Type"]})

    logged_machines_clean = set()
    if not day_13.empty and "Unit_ID" in day_13.columns:
        for _, r in day_13.iterrows():
            m_id = r.get("Unit_ID") or ""
            if m_id:
                logged_machines_clean.add(clean_unit_token(m_id))

    master_machine_ids = [m["Unit_ID"] for m in flat_master_13]
    pending_machines = [m for m in master_machine_ids if clean_unit_token(m) not in logged_machines_clean]
    logged_13_count = min(len(master_machine_ids), len(logged_machines_clean))
    total_13_units = len(master_machine_ids)
    is_13_complete = (logged_13_count >= total_13_units or len(pending_machines) == 0)

    if is_13_complete:
        stat_13 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {total_13_units}/{total_13_units} machines</span>'
    else:
        pending_str_13 = ", ".join(pending_machines[:3]) + ("..." if len(pending_machines) > 3 else "")
        stat_13 = f'<span style="color: #fde047; font-weight: 600;">Pending ({logged_13_count}/{total_13_units} machines)</span><br><span style="font-size:0.65rem; color:#cbd5e1;">Missing: {pending_str_13}</span>'
    
    day_15 = filter_by_focus_date(df_15_parsed, selected_day_str)
    is_15_complete = not day_15.empty
    if is_15_complete:
        stat_15 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_15)} entries</span>'
    else:
        stat_15 = '<span style="color: #fde047; font-weight: 600;">Pending - 0 entries</span>'
    
    day_21 = filter_by_focus_date(df_21_parsed, selected_day_str)
    is_21_complete = not day_21.empty
    if is_21_complete:
        stat_21 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_21)} areas</span>'
    else:
        stat_21 = '<span style="color: #fde047; font-weight: 600;">Pending - 0 areas</span>'
    
    day_25 = filter_by_focus_date(df_25_parsed, selected_day_str)
    is_25_complete = not day_25.empty
    if is_25_complete:
        stat_25 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {len(day_25)} entries</span>'
    else:
        stat_25 = '<span style="color: #fde047; font-weight: 600;">Pending - 0 entries</span>'

    completed_cats = sum([
        1 if is_03_complete else 0,
        1 if is_04_complete else 0,
        1 if is_05_complete else 0,
        1 if is_06_complete else 0,
        1 if is_13_complete else 0,
        1 if is_15_complete else 0,
        1 if is_21_complete else 0,
        1 if is_25_complete else 0
    ])
    total_cats = 8
    progress_pct = int((completed_cats / total_cats) * 100)
    bar_color = "#4ade80" if progress_pct > 70 else ("#38bdf8" if progress_pct > 30 else "#fde047")

    if st.session_state.dashboard_view_mode == "📊 Overview Cards":
        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px 24px; margin-bottom: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-weight: 700; font-size: 0.95rem; color: #0f172a; display:flex; align-items:center; gap:8px;">📊 Daily Compliance & Progression Tracker</span>
                <span style="font-weight: 800; font-size: 0.92rem; color: #0f172a; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); padding: 4px 12px; border-radius: 8px; border: 1px solid #cbd5e1;">{progress_pct}% Completed ({completed_cats}/{total_cats} Categories)</span>
            </div>
            <div style="width: 100%; background: #f1f5f9; border-radius: 10px; height: 12px; overflow: hidden; border: 1px solid #e2e8f0; padding: 1px;">
                <div style="width: {progress_pct}%; background: linear-gradient(90deg, #000000 0%, #38bdf8 50%, #4ade80 100%); height: 100%; border-radius: 8px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 2px 6px rgba(56, 189, 248, 0.3);"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        def render_executive_tile(col, title, status_html, is_complete):
            with col:
                card_class = "exec-card-completed" if is_complete else "exec-card-pending"
                body_class = "exec-card-body" if is_complete else "exec-card-body-pending"
                badge_html = '<div style="font-size:0.65rem; font-weight:800; color:#4ade80; text-transform:uppercase; margin-bottom:4px; letter-spacing:0.05em;">✓ COMPLETED</div>' if is_complete else '<div style="font-size:0.65rem; font-weight:800; color:#fde047; text-transform:uppercase; margin-bottom:4px; letter-spacing:0.05em;">⏳ PENDING ACTION</div>'
                
                card_html = f"""
                <div class="{card_class}">
                    <div>
                        {badge_html}
                        <div class="exec-card-title">{title}</div>
                        <div class="{body_class}">{status_html}</div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

        with col1:
            render_executive_tile(col1, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", html_03, is_03_complete)
            render_executive_tile(col1, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", stat_13, is_13_complete)

        with col2:
            render_executive_tile(col2, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", html_04, is_04_complete)
            render_executive_tile(col2, "RECORD 15 - PESTICIDE USAGE RECORD", stat_15, is_15_complete)

        with col3:
            render_executive_tile(col3, "RECORD 05 - COOLING OF FOOD RECORD", stat_05, is_05_complete)
            render_executive_tile(col3, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", stat_21, is_21_complete)

        with col4:
            render_executive_tile(col4, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", stat_06, is_06_complete)
            render_executive_tile(col4, "RECORD 25 - ICE MACHINE CLEANING RECORD", stat_25, is_25_complete)
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
