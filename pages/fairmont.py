from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records_fairmont.record_02 import render_record_02_view, parse_record_02_submissions
from records_fairmont.record_03 import render_record_03_view, parse_record_03_submissions, UNIT_CATALOG, clean_unit_token
from records_fairmont.record_04 import render_record_04_view, parse_all_record_04_dishes, KITCHEN_MEAL_RULES as KITCHEN_MEAL_RULES_04
from records_fairmont.record_05 import render_record_05_view, parse_record_05_submissions, RECORD_05_KITCHENS
from records_fairmont.record_06 import render_record_06_view, parse_record_06_submissions, RECORD_06_MEAL_RULES
from records_fairmont.record_12 import render_record_12_view, parse_record_12_submissions, RECORD_12_AREAS
from records_fairmont.record_13 import render_record_13_view, parse_record_13_submissions
from records_fairmont.record_15 import render_record_15_view, parse_record_15_submissions
from records_fairmont.record_21 import render_record_21_view, parse_record_21_submissions, RECORD_21_AREAS
from records_fairmont.record_25 import render_record_25_view, parse_record_25_submissions
from records_fairmont.record_cm01 import render_record_cm01_view, parse_record_cm01_submissions, CM01_LOCATION_UNITS, CM01_LOCATION_RULES
from records_fairmont.record_ph01 import render_record_ph01_view, parse_record_ph01_submissions

st.set_page_config(
    page_title="Fairmont Mumbai - EHCO Status",
    page_icon="🛡️",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #0f172a; }
    .serif-title { font-size: 1.8rem; font-weight: 700; color: #0f172a; text-align: center; letter-spacing: -0.02em; margin: 0; }
    .sub-head { font-size: 0.82rem; color: #475569; font-weight: 600; text-align: center; }
    .record-header-box { background-color: #0b192c; padding: 18px 24px; border-radius: 10px; color: white; margin-bottom: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-size: 1.6rem; font-weight: 700; }
    
    [data-testid="stSidebarNav"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

FORM_MAPPING = {
    "🏠 Fairmont Mumbai - EHCO Status Overview": 0,
    "RECORD 02 - FOOD DELIVERY RECORD": 23703,
    "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD": 23705,
    "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD": 23706,
    "RECORD 05 - COOLING OF FOOD RECORD": 23707,
    "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD": 23708,
    "RECORD 12 - DEFROSTING TEMPERATURE RECORD": 23714,
    "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD": 23715,
    "RECORD 15 - PESTICIDE USAGE RECORD": 23717,
    "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH": 23723,
    "RECORD 25 - ICE MACHINE CLEANING RECORD": 23727,
    "RECORD CM01 - COFFEE MACHINE CLEANING RECORD": 24144,
    "RECORD PH01 - PERSONAL HYGIENE RECORD": 24146,
}

if "fairmont_nav_choice" not in st.session_state:
    st.session_state.fairmont_nav_choice = "🏠 Fairmont Mumbai - EHCO Status Overview"

def navigate_to(target_nav):
    st.session_state.fairmont_nav_choice = target_nav
    st.session_state.fairmont_nav_selectbox = target_nav

def go_to_overview():
    st.session_state.fairmont_nav_choice = "🏠 Fairmont Mumbai - EHCO Status Overview"
    st.session_state.fairmont_nav_selectbox = "🏠 Fairmont Mumbai - EHCO Status Overview"

st.sidebar.title("⚙️ Inspection Controls")

ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
today = ist_now.date()
default_start_7d = today - timedelta(days=6)

date_selection = st.sidebar.date_input(
    "Audit Date Range (7 Days)",
    value=[default_start_7d, today],
    max_value=today,
    key="sb_fairmont_date_range_picker"
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
    "Focus Day for Drill-down", options=list(reversed(day_options)), key="sb_fairmont_day_focus_select"
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

DEFAULT_TOKEN = st.secrets.get("auth_token", "").strip()
if not DEFAULT_TOKEN:
    DEFAULT_TOKEN = "PASTE_FALLBACK_TOKEN_HERE"

if "fairmont_auth_token" not in st.session_state:
    st.session_state["fairmont_auth_token"] = DEFAULT_TOKEN

api_url = st.sidebar.text_input(
    "Endpoint URL", value="https://auth-api.blinkm.io/form-store", key="sb_fairmont_api_endpoint_input"
)

token_input = st.sidebar.text_area(
    "Bearer Token", 
    value=st.session_state["fairmont_auth_token"], 
    height=90, 
    key="sb_fairmont_bearer_token_input"
)

if token_input != st.session_state["fairmont_auth_token"]:
    st.session_state["fairmont_auth_token"] = token_input.strip()

active_token = st.session_state.get("fairmont_auth_token", DEFAULT_TOKEN).strip()
clean_token = active_token.replace("Bearer ", "").strip()

nav_options = list(FORM_MAPPING.keys())
current_nav_index = nav_options.index(st.session_state.fairmont_nav_choice) if st.session_state.fairmont_nav_choice in nav_options else 0

selected_record = st.sidebar.selectbox(
    "SELECT FOOD SAFETY RECORD", 
    options=nav_options, 
    index=current_nav_index,
    key="fairmont_nav_selectbox"
)

if selected_record != st.session_state.fairmont_nav_choice:
    st.session_state.fairmont_nav_choice = selected_record
    st.rerun()

active_form_id = FORM_MAPPING[st.session_state.fairmont_nav_choice]

cache_key_df = f"fairmont_persistent_records_df_{active_form_id}"
cache_key_time = f"fairmont_last_sync_timestamp_{active_form_id}"

if cache_key_df not in st.session_state:
    st.session_state[cache_key_df] = pd.DataFrame()

if cache_key_time not in st.session_state:
    st.session_state[cache_key_time] = "No sync performed yet"

@st.cache_data(ttl=300, show_spinner=False)
def fetch_incremental_persistent_data_cached(url, token, form_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://tehc-fairmont-mumbai.data-manager.oneblink.io",
        "Referer": "https://tehc-fairmont-mumbai.data-manager.oneblink.io/",
    }
    new_rows = []
    base_url = url.strip()
    for page in range(5):  # Limit initial fetch pages for speed
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

force_refresh = st.sidebar.button("🔄 Sync Live Feed", key="sync_fairmont_live_feed_btn", use_container_width=True)
if force_refresh:
    st.cache_data.clear()
    for k in list(st.session_state.keys()):
        if k.startswith("parsed_cache_") or k.startswith("fairmont_persistent_"):
            st.session_state.pop(k, None)

raw_records_df = fetch_incremental_persistent_data_cached(api_url, clean_token, active_form_id) if active_form_id != 0 else pd.DataFrame()
if isinstance(raw_records_df, list):
    raw_records_df = pd.DataFrame({"raw_record": raw_records_df})

last_sync_display = st.session_state[cache_key_time]

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

if st.session_state.fairmont_nav_choice == "🏠 Fairmont Mumbai - EHCO Status Overview":
    if "fairmont_dashboard_view_mode" not in st.session_state:
        st.session_state.fairmont_dashboard_view_mode = "📊 Overview Cards"

    hdr_cols = st.columns([3, 4, 3])
    with hdr_cols[0]:
        selected_site = st.selectbox(
            "Select Site Portal",
            options=["🏰 Fairmont Mumbai", "🏨 Roswyn Mumbai"],
            index=0,
            label_visibility="collapsed",
            key="global_site_switcher_select_fairmont"
        )
        if selected_site.startswith("🏨"):
            st.switch_page("pages/roswyn.py")

    with hdr_cols[1]:
        st.markdown('<div class="serif-title">Fairmont Mumbai - EHCO Status</div>', unsafe_allow_html=True)

    with hdr_cols[2]:
        st.markdown(f"""
            <div style="background: #0b192c; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 500; font-size: 0.78rem; text-align: right; box-shadow: 0 1px 2px rgba(0,0,0,0.04);">
                <div>🕒 IST: <span style="color: #38bdf8;">{ist_now.strftime("%I:%M:%S %p")}</span></div>
                <div style="color: #94a3b8; font-size: 0.72rem; margin-top: 2px;">Last Sync: Live Cached</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("")
    mode_cols = st.columns([6, 3])
    with mode_cols[0]:
        st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #cbd5e1; padding: 8px 14px; border-radius: 8px; font-weight: 600; font-size: 0.88rem; color: #0f172a; display: inline-block; box-shadow: 0 1px 2px rgba(0,0,0,0.04);">
                📅 Focus Date: <span style="color:#0284c7;">{selected_day_str}</span>
            </div>
        """, unsafe_allow_html=True)
    with mode_cols[1]:
        view_choice = st.radio(
            "Dashboard Display Mode", 
            ["📊 Overview Cards", "🏢 Department-Wise Cards"], 
            horizontal=True,
            label_visibility="collapsed",
            key="fairmont_dashboard_view_mode_radio"
        )
        if view_choice != st.session_state.fairmont_dashboard_view_mode:
            st.session_state.fairmont_dashboard_view_mode = view_choice
            st.rerun()

    # --- LAZY & FAST CACHED PARSING FOR ALL RECORDS ---
    @st.cache_data(show_spinner=False)
    def load_all_parsed_records(token):
        return {
            23703: parse_record_02_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23703)})),
            23705: parse_record_03_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23705)})),
            23706: parse_all_record_04_dishes(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23706)})),
            23707: parse_record_05_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23707)})),
            23708: parse_record_06_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23708)})),
            23714: parse_record_12_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23714)})),
            23715: parse_record_13_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23715)})),
            23717: parse_record_15_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23717)})),
            23723: parse_record_21_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23723)})),
            23727: parse_record_25_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 23727)})),
            24144: parse_record_cm01_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 24144)})),
            24146: parse_record_ph01_submissions(pd.DataFrame({"raw_record": fetch_incremental_persistent_data_cached(api_url, token, 24146)})),
        }

    cache = load_all_parsed_records(clean_token)
    df_02_parsed = cache.get(23703, pd.DataFrame())
    df_03_parsed = cache.get(23705, pd.DataFrame())
    df_04_parsed = cache.get(23706, pd.DataFrame())
    df_05_parsed = cache.get(23707, pd.DataFrame())
    df_06_parsed = cache.get(23708, pd.DataFrame())
    df_12_parsed = cache.get(23714, pd.DataFrame())
    df_13_parsed = cache.get(23715, pd.DataFrame())
    df_15_parsed = cache.get(23717, pd.DataFrame())
    df_21_parsed = cache.get(23723, pd.DataFrame())
    df_25_parsed = cache.get(23727, pd.DataFrame())
    df_cm01_parsed = cache.get(24144, pd.DataFrame())
    df_ph01_parsed = cache.get(24146, pd.DataFrame())

    target_date_obj = datetime.strptime(selected_day_str, "%d/%m/%Y").date()
    next_date_obj = target_date_obj + timedelta(days=1)

    # --- RECORD 02 METRICS ---
    day_02 = get_day_df(df_02_parsed, selected_day_variants, target_date_obj)
    stat_02 = f'<span style="color: {"#4ade80" if not day_02.empty else "#fbbf24"}; font-weight: 600;">{"Completed" if not day_02.empty else "Pending"} - {len(day_02)} entries</span>'

    # --- RECORD 03 METRICS ---
    if not df_03_parsed.empty and "Date_Obj" in df_03_parsed.columns:
        if "Timestamp_DT" in df_03_parsed.columns:
            df_03_parsed["Timestamp_DT"] = pd.to_datetime(df_03_parsed["Timestamp_DT"], errors="coerce")
            night_owl_mask = (df_03_parsed["Date_Obj"] == next_date_obj) & (df_03_parsed["Timestamp_DT"].dt.hour < 5)
        else:
            night_owl_mask = False
        day_03 = df_03_parsed[
            (df_03_parsed["Date_Obj"] == target_date_obj) | night_owl_mask
        ]
    else:
        day_03 = get_day_df(df_03_parsed, selected_day_variants, target_date_obj)

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

    # --- RECORD 04 METRICS ---
    day_04 = get_day_df(df_04_parsed, selected_day_variants, target_date_obj)
    shift_totals_04 = {"Breakfast": {"req": 0, "done": 0}, "Lunch": {"req": 0, "done": 0}, "Dinner": {"req": 0, "done": 0}}

    for kitchen, meals in KITCHEN_MEAL_RULES_04.items():
        k_df = day_04[day_04["Location"].str.strip().str.lower() == kitchen.lower()] if not day_04.empty else pd.DataFrame()
        for meal in meals:
            if meal in shift_totals_04:
                shift_totals_04[meal]["req"] += 1
            m_df = k_df[k_df["Meal_Service"].str.strip().str.lower() == meal.lower()] if not k_df.empty else pd.DataFrame()
            if not m_df.empty and meal in shift_totals_04:
                shift_totals_04[meal]["done"] += 1

    b_done_04, b_req_04 = shift_totals_04["Breakfast"]["done"], shift_totals_04["Breakfast"]["req"]
    l_done_04, l_req_04 = shift_totals_04["Lunch"]["done"], shift_totals_04["Lunch"]["req"]
    d_done_04, d_req_04 = shift_totals_04["Dinner"]["done"], shift_totals_04["Dinner"]["req"]

    html_04 = (
        f'Breakfast: <span style="color: {"#4ade80" if b_req_04 > 0 and b_done_04 >= b_req_04 else "#fbbf24"}; font-weight: 600;">{"Completed" if b_req_04 > 0 and b_done_04 >= b_req_
