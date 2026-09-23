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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #0f172a; }
    .serif-title { font-size: 1.8rem; font-weight: 700; color: #0f172a; text-align: center; letter-spacing: -0.02em; margin: 0; }
    .sub-head { font-size: 0.82rem; color: #475569; font-weight: 600; text-align: center; }
    .record-header-box { background-color: #0b192c; padding: 18px 24px; border-radius: 10px; color: white; margin-bottom: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-size: 1.6rem; font-weight: 700; }
    .kpi-card {
        background-color: #0b192c;
        border-radius: 10px;
        padding: 16px;
        color: white;
        margin-bottom: 6px;
        min-height: 125px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .dept-card {
        background-color: #0b192c;
        border-radius: 10px;
        padding: 20px;
        color: white;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-top: 4px solid #38bdf8;
        min-height: 220px;
    }
    
    /* Hides default Streamlit multi-page navigation links in the sidebar */
    [data-testid="stSidebarNav"] {
        display: none;
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
st.sidebar.title("⚙️ Inspection Controls")

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

DEFAULT_TOKEN = st.secrets.get("auth_token", "").strip()
if not DEFAULT_TOKEN:
    DEFAULT_TOKEN = "PASTE_FALLBACK_TOKEN_HERE"

if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = DEFAULT_TOKEN

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
    st.rerun()

active_form_id = FORM_MAPPING[st.session_state.nav_choice]

# --- PERSISTENT SESSION STATE INITIALIZATION ---
cache_key_df = f"roswyn_persistent_records_df_{active_form_id}"
cache_key_time = f"roswyn_last_sync_timestamp_{active_form_id}"

if cache_key_df not in st.session_state:
    st.session_state[cache_key_df] = pd.DataFrame()

if cache_key_time not in st.session_state:
    st.session_state[cache_key_time] = "No sync performed yet"

def fetch_incremental_persistent_data(url, token, form_id):
    existing_df = st.session_state[cache_key_df]
    
    newest_dt = None
    if not existing_df.empty:
        for col in ["dateTimeSubmitted", "CreatedAt", "submissionDate"]:
            if col in existing_df.columns:
                parsed_col = pd.to_datetime(existing_df[col], errors="coerce")
                if not parsed_col.isna().all():
                    newest_dt = parsed_col.max()
                    break

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://tehc-roswyn.data-manager.oneblink.io",
        "Referer": "https://tehc-roswyn.data-manager.oneblink.io/",
    }

    if not token or token == "PASTE_FALLBACK_TOKEN_HERE":
        if not existing_df.empty:
            st.toast("⚠️ Using cached offline data (Bearer token expired or missing).", icon="🔒")
            return existing_df

    new_rows = []
    base_url = url.strip()

    for page in range(15):
        payload = {
            "formId": form_id,
            "paging": {"limit": 50, "offset": page * 50},
            "sorting": [{"property": "dateTimeSubmitted", "direction": "descending"}],
            "unwindRepeatableSets": True,
        }
        try:
            res = requests.post(base_url, headers=headers, json=payload, timeout=15)
            if res.status_code != 200:
                break
            data = res.json()
            items = data.get("submissions", []) if isinstance(data, dict) else data
            if not items:
                break
            
            stop_fetching = False
            filtered_items = []
            for item in items:
                sub_dt = pd.to_datetime(item.get("dateTimeSubmitted"), errors="coerce")
                if newest_dt and sub_dt <= newest_dt:
                    stop_fetching = True
                    break
                filtered_items.append(item)
            
            new_rows.extend(filtered_items)
            if stop_fetching or len(items) < 50:
                break
        except Exception:
            break

    if new_rows:
        new_df = pd.DataFrame({"raw_record": new_rows})
        if not existing_df.empty:
            combined_df = pd.concat([new_df, existing_df]).drop_duplicates().reset_index(drop=True)
            st.session_state[cache_key_df] = combined_df
        else:
            st.session_state[cache_key_df] = new_df
        
        current_time_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d/%m/%Y %I:%M:%S %p")
        st.session_state[cache_key_time] = current_time_str
        st.toast(f"📥 Appended {len(new_rows)} new entries successfully!", icon="🚀")
    elif existing_df.empty:
        st.session_state[cache_key_df] = pd.DataFrame()

    return st.session_state[cache_key_df]

force_refresh = st.sidebar.button("🔄 Sync Live Feed", key="sync_live_feed_btn", use_container_width=True)
if force_refresh:
    st.session_state[cache_key_df] = pd.DataFrame()

raw_records_df = fetch_incremental_persistent_data(api_url, clean_token, active_form_id) if active_form_id != 0 else pd.DataFrame()
last_sync_display = st.session_state[cache_key_time]

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

if st.session_state.nav_choice == "🏠 Roswyn - EHCO Status Overview":
    if "dashboard_view_mode" not in st.session_state:
        st.session_state.dashboard_view_mode = "📊 Overview Cards"

    # --- TOP HEADER ---
    hdr_cols = st.columns([3, 4, 3])
    with hdr_cols[0]:
        selected_site = st.selectbox(
            "Select Site Portal",
            options=["🏨 Roswyn Mumbai", "🏰 Fairmont Mumbai"],
            index=0,
            label_visibility="collapsed",
            key="global_site_switcher_select"
        )
        if selected_site.startswith("🏰"):
            st.switch_page("pages/fairmont.py")

    with hdr_cols[1]:
        st.markdown('<div class="serif-title">Roswyn - EHCO Status</div>', unsafe_allow_html=True)

    with hdr_cols[2]:
        st.markdown(f"""
            <div style="background: #0b192c; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 500; font-size: 0.78rem; text-align: right; box-shadow: 0 1px 2px rgba(0,0,0,0.04);">
                <div>🕒 IST: <span style="color: #38bdf8;">{ist_now.strftime("%I:%M:%S %p")}</span></div>
                <div style="color: #94a3b8; font-size: 0.72rem; margin-top: 2px;">Last Sync: {last_sync_display}</div>
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
            key="dashboard_view_mode_radio"
        )
        if view_choice != st.session_state.dashboard_view_mode:
            st.session_state.dashboard_view_mode = view_choice
            st.rerun()

    raw_03 = fetch_incremental_persistent_data(api_url, clean_token, 31373)
    raw_04 = fetch_incremental_persistent_data(api_url, clean_token, 31374)
    raw_05 = fetch_incremental_persistent_data(api_url, clean_token, 31375)
    raw_06 = fetch_incremental_persistent_data(api_url, clean_token, 31376)
    raw_13 = fetch_incremental_persistent_data(api_url, clean_token, 31382)
    raw_15 = fetch_incremental_persistent_data(api_url, clean_token, 31384)
    raw_21 = fetch_incremental_persistent_data(api_url, clean_token, 31390)
    raw_25 = fetch_incremental_persistent_data(api_url, clean_token, 31393)

    df_03_parsed = parse_record_03_submissions(raw_03)
    df_04_parsed = parse_all_record_04_dishes(raw_04)
    df_05_parsed = parse_record_05_submissions(raw_05)
    df_06_parsed = parse_record_06_submissions(raw_06)
    df_13_parsed = parse_record_13_submissions(raw_13)
    df_15_parsed = parse_record_15_submissions(raw_15)
    df_21_parsed = parse_record_21_submissions(raw_21)
    df_25_parsed = parse_record_25_submissions(raw_25)

    target_date_obj = datetime.strptime(selected_day_str, "%d/%m/%Y").date()
    next_date_obj = target_date_obj + timedelta(days=1)

    if not df_03_parsed.empty and "Timestamp_DT" in df_03_parsed.columns:
        df_03_parsed["Timestamp_DT"] = pd.to_datetime(df_03_parsed["Timestamp_DT"], errors="coerce")

    day_03 = df_03_parsed[
        (df_03_parsed["Date_Obj"] == target_date_obj) |
        ((df_03_parsed["Date_Obj"] == next_date_obj) & (df_03_parsed["Timestamp_DT"].dt.hour < 5))
    ] if not df_03_parsed.empty and "Date_Obj" in df_03_parsed.columns else filter_by_focus_date(df_03_parsed, selected_day_variants)

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
    
    day_04 = filter_by_focus_date(df_04_parsed, selected_day_variants)
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
    # --- STRICT FOCUS-DAY FILTERED METRICS FOR RECORD 05 ---
    day_05 = filter_by_focus_date(df_05_parsed, selected_day_variants)
    
    if not day_05.empty:
        # Extract exact food items cooled strictly on the focus date
        food_col = next((c for c in ["Food", "Item", "Name_of_Food", "Dish"] if c in day_05.columns), None)
        foods_logged = day_05[food_col].dropna().tolist() if food_col else []
        item_count = len(day_05)
        stat_05 = f'<span style="color: #4ade80; font-weight: 600;">Completed - {item_count} items cooled</span>'
    else:
        stat_05 = '<span style="color: #fbbf24; font-weight: 600;">Pending - No Cooling Logged</span>'

    day_06 = filter_by_focus_date(df_06_parsed, selected_day_variants)
    is_06_complete = not day_06.empty
    stat_06 = f'<span style="color: {"#4ade80" if is_06_complete else "#fbbf24"}; font-weight: 600;">{"Completed" if is_06_complete else "Pending"} - {1 if is_06_complete else 0}/1</span>'
    
    day_13 = filter_by_focus_date(df_13_parsed, selected_day_variants)
    if not day_13.empty:
        unit_col = next((c for c in ["Unit_ID", "Machine_Name", "Equipment", "Name"] if c in day_13.columns), None)
        units_logged = day_13[unit_col].dropna().unique().tolist() if unit_col else []
        logged_13_count = len(units_logged)
        is_13_complete = (logged_13_count >= 11)
        stat_13 = f'<span style="color: {"#4ade80" if is_13_complete else "#fbbf24"}; font-weight: 600;">{"Completed" if is_13_complete else "Pending"} - {logged_13_count}/11</span>'
    else:
        stat_13 = '<span style="color: #fbbf24; font-weight: 600;">Pending - 0/11</span>'
    
    day_15 = filter_by_focus_date(df_15_parsed, selected_day_variants)
    if not day_15.empty:
        stat_15 = '<span style="color: #4ade80; font-weight: 600;">Completed</span>'
    else:
        stat_15 = '<span style="color: #fbbf24; font-weight: 600;">Pending</span>'
    
    day_21 = filter_by_focus_date(df_21_parsed, selected_day_variants)
    if not day_21.empty:
        wash_col = next((c for c in ["Location", "Area", "Food", "Item"] if c in day_21.columns), None)
        washes = day_21[wash_col].dropna().unique().tolist() if wash_col else []
        stat_21 = f'<span style="color: #4ade80; font-weight: 600;">Washed: {", ".join(str(w) for w in washes) if washes else f"{len(day_21)} batches"}</span>'
    else:
        stat_21 = '<span style="color: #fbbf24; font-weight: 600;">Pending - No Food Wash Logged</span>'
    
    day_25 = filter_by_focus_date(df_25_parsed, selected_day_variants)
    if not day_25.empty:
        raw_name_col = next((c for c in ["Machine_Name", "Ice_Machine", "Equipment", "Unit_Name", "Name"] if c in day_25.columns), None)
        if raw_name_col:
            machine_names = day_25[raw_name_col].dropna().unique().tolist()
            stat_25 = f'<span style="color: #4ade80; font-weight: 600;">Cleaned: {", ".join(str(m) for m in machine_names) if machine_names else "Not Specified"}</span>'
        else:
            stat_25 = '<span style="color: #4ade80; font-weight: 600;">Cleaned (Name Not Specified by API)</span>'
    else:
        stat_25 = '<span style="color: #fbbf24; font-weight: 600;">Pending - No Ice Machine Logged</span>'

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
    bar_color = "#4ade80" if progress_pct > 70 else ("#3b82f6" if progress_pct > 30 else "#fbbf24")

    if st.session_state.dashboard_view_mode == "📊 Overview Cards":
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

        def render_theme_card(col, title, status_html, target_nav, unique_key):
            col.markdown(f"""
            <div class="kpi-card">
                <div style="font-size: 0.85rem; font-weight: 600; line-height: 1.3; margin-bottom: 4px;">{title}</div>
                <div style="font-size: 0.78rem; color: #cbd5e1; font-weight: 500; line-height: 1.4;">{status_html}</div>
            </div>
            """, unsafe_allow_html=True)
            col.button("Open ➔", use_container_width=True, key=f"btn_theme_{unique_key}", on_click=navigate_to, args=(target_nav,))

        # --- EXACT 3-CARD ROW LAYOUT ---
        # Top Row (3 Cards): Record 03, Record 04, Record 05
        col1, col2, col3 = st.columns(3)
        with col1:
            render_theme_card(col1, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", html_03, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", "card_r03")
        with col2:
            render_theme_card(col2, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", html_04, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", "card_r04")
        with col3:
            render_theme_card(col3, "RECORD 05 - COOLING OF FOOD RECORD", stat_05, "RECORD 05 - COOLING OF FOOD RECORD", "card_r05")

        # Middle Row (3 Cards): Record 06, Completion Card, Record 13
        col4, col5, col6 = st.columns(3)
        with col4:
            render_theme_card(col4, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", stat_06, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", "card_r06")
        with col5:
            latest_04_time = "No timestamp"
            if not day_04.empty and "Timestamp_DT" in day_04.columns:
                try:
                    valid_dt = pd.to_datetime(day_04["Timestamp_DT"], errors="coerce").dropna()
                    if not valid_dt.empty:
                        if valid_dt.dt.tz is not None:
                            valid_dt = valid_dt.dt.tz_localize(None)
                        latest_04_time = valid_dt.max().strftime('%d/%m/%Y %I:%M %p')
                except Exception:
                    pass
            comp_badge = f"✓ Logged at {latest_04_time}" if is_04_complete else "⏳ Shift Pending Completion"
            
            col5.markdown(f"""
            <div class="kpi-card" style="border: 2px dashed #38bdf8; background: #071120;">
                <div style="font-size: 0.85rem; font-weight: 700; color: #38bdf8; margin-bottom: 2px;">🏁 DAILY SHIFT COMPLETION</div>
                <div style="font-size: 0.78rem; color: #ffffff; font-weight: 500;">Status: {comp_badge}</div>
                <div style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; font-size: 0.72rem; padding: 4px 8px; border-radius: 6px; margin-top: 4px; font-weight: 600; text-align: center;">Focus Date: {selected_day_str}</div>
            </div>
            """, unsafe_allow_html=True)
            col5.write("") # placeholder space for grid alignment
        with col6:
            render_theme_card(col6, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", stat_13, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", "card_r13")

        # Last Row (3 Cards): Record 15, Record 21, Record 25
        col7, col8, col9 = st.columns(3)
        with col7:
            render_theme_card(col7, "RECORD 15 - PESTICIDE USAGE RECORD", stat_15, "RECORD 15 - PESTICIDE USAGE RECORD", "card_r15")
        with col8:
            render_theme_card(col8, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", stat_21, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", "card_r21")
        with col9:
            render_theme_card(col9, "RECORD 25 - ICE MACHINE CLEANING RECORD", stat_25, "RECORD 25 - ICE MACHINE CLEANING RECORD", "card_r25")
            
    else:
        st.markdown(f"<h3 style='color:#0f172a; margin-top:0.5rem;'>🏢 Department-Wise Compliance Cards ({selected_day_str})</h3>", unsafe_allow_html=True)
        st.write("Department-wise overview for Roswyn")

        dept_cols = st.columns(3)
        def render_dept_card(col, dept_name, rec_tuples):
            items_html = ""
            for r_title, r_status in rec_tuples:
                items_html += f"""
                <div style="background: rgba(255,255,255,0.06); padding: 10px 12px; border-radius: 6px; margin-bottom: 8px;">
                    <div style="font-weight: 600; font-size: 0.85rem; color: #f8fafc; margin-bottom: 2px;">{r_title}</div>
                    <div style="font-size: 0.75rem; color: #cbd5e1;">{r_status}</div>
                </div>
                """
            col.markdown(f"""
            <div class="dept-card">
                <div style="font-size: 1.1rem; font-weight: 700; color: #38bdf8; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 8px;">🏢 {dept_name}</div>
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
            <div style="background: #0b192c; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 500; font-size: 0.78rem; text-align: right; box-shadow: 0 1px 2px rgba(0,0,0,0.04);">
                <div>🕒 IST: <span style="color: #38bdf8;">{ist_now.strftime("%I:%M:%S %p")}</span></div>
                <div style="color: #94a3b8; font-size: 0.72rem; margin-top: 2px;">Last Sync: {last_sync_display}</div>
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
