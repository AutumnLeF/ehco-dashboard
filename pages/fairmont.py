from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records_fairmont.record_02 import render_record_02_view, parse_record_02_submissions
from records_fairmont.record_03 import render_record_03_view, parse_record_03_submissions, UNIT_CATALOG, clean_unit_token
from records_fairmont.record_04 import render_record_04_view, parse_all_record_04_dishes
from records_fairmont.record_05 import render_record_05_view, parse_record_05_submissions
from records_fairmont.record_06 import render_record_06_view, parse_record_06_submissions
from records_fairmont.record_12 import render_record_12_view, parse_record_12_submissions
from records_fairmont.record_13 import render_record_13_view, parse_record_13_submissions
from records_fairmont.record_15 import render_record_15_view, parse_record_15_submissions
from records_fairmont.record_21 import render_record_21_view, parse_record_21_submissions
from records_fairmont.record_25 import render_record_25_view, parse_record_25_submissions

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
}

if "fairmont_nav_choice" not in st.session_state:
    st.session_state.fairmont_nav_choice = "🏠 Fairmont Mumbai - EHCO Status Overview"

def navigate_to(target_nav):
    st.session_state.fairmont_nav_choice = target_nav
    st.session_state.fairmont_nav_selectbox = target_nav

def go_to_overview():
    st.session_state.fairmont_nav_choice = "🏠 Fairmont Mumbai - EHCO Status Overview"
    st.session_state.fairmont_nav_selectbox = "🏠 Fairmont Mumbai - EHCO Status Overview"

# --- CLEANED SIDEBAR: INSPECTION CONTROLS ONLY ---
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

def fetch_submissions(url, token, form_id, start_dt, end_dt, unwind=True):
    if not form_id or form_id == 0 or not token:
        return []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://tehc-fairmont-mumbai.data-manager.oneblink.io",
        "Referer": "https://tehc-fairmont-mumbai.data-manager.oneblink.io/",
    }

    all_rows = []
    current_offset = 0
    base_url = url.strip()

    for page in range(15):
        payload = {
            "formId": form_id,
            "paging": {"limit": 50, "offset": current_offset},
            "sorting": [{"property": "dateTimeSubmitted", "direction": "descending"}],
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

if "fairmont_master_data_cache" not in st.session_state:
    st.session_state["fairmont_master_data_cache"] = {}

force_refresh = st.sidebar.button("🔄 Sync Live Feed", key="sync_fairmont_live_feed_btn", use_container_width=True)
if force_refresh:
    st.session_state["fairmont_master_data_cache"] = {}

def get_master_df(form_id, unwind=True):
    cache_key = f"{form_id}_unwind_{unwind}"
    if cache_key not in st.session_state["fairmont_master_data_cache"]:
        items = fetch_submissions(api_url, clean_token, form_id, start_date, end_date, unwind=unwind)
        st.session_state["fairmont_master_data_cache"][cache_key] = pd.DataFrame({"raw_record": items}) if items else pd.DataFrame()
    return st.session_state["fairmont_master_data_cache"][cache_key]

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

if st.session_state.fairmont_nav_choice == "🏠 Fairmont Mumbai - EHCO Status Overview":
    if "fairmont_dashboard_view_mode" not in st.session_state:
        st.session_state.fairmont_dashboard_view_mode = "📊 Overview Cards"

    # --- TOP HEADER: SITE DROPDOWN (LEFT), TITLE (MID), CLOCK (RIGHT) ---
    hdr_cols = st.columns([3, 4, 3])
    with hdr_cols[0]:
        selected_site = st.selectbox(
            "Select Site Portal",
            options=["🏰 Fairmont Mumbai (Site 2)", "🏨 Roswyn (Site 1)"],
            index=0,
            label_visibility="collapsed",
            key="global_site_switcher_select_fairmont"
        )
        if selected_site.startswith("🏨"):
            st.switch_page("pages/ros_overview.py")

    with hdr_cols[1]:
        st.markdown('<div class="serif-title">Fairmont Mumbai - EHCO Status</div>', unsafe_allow_html=True)

    with hdr_cols[2]:
        st.markdown(f"""
            <div style="background: #0b192c; color: white; padding: 8px 14px; border-radius: 8px; font-weight: 600; font-size: 0.85rem; text-align: right; box-shadow: 0 1px 2px rgba(0,0,0,0.04); display: flex; justify-content: flex-end; align-items: center; gap: 6px;">
                <span>🕒 IST:</span> <span style="color: #38bdf8;">{ist_now.strftime("%I:%M:%S %p")}</span>
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

    raw_02 = get_master_df(23703, unwind=True)
    raw_03 = get_master_df(23705, unwind=True)
    raw_04 = get_master_df(23706, unwind=True)
    raw_12 = get_master_df(23714, unwind=True)

    df_02_parsed = parse_record_02_submissions(raw_02)
    df_03_parsed = parse_record_03_submissions(raw_03)
    df_04_parsed = parse_all_record_04_dishes(raw_04)
    df_05 = parse_record_05_submissions(get_master_df(23707, unwind=True))
    df_06 = parse_record_06_submissions(get_master_df(23708, unwind=True))
    df_12_parsed = parse_record_12_submissions(raw_12)
    df_13 = parse_record_13_submissions(get_master_df(23715, unwind=True))
    df_21 = parse_record_21_submissions(get_master_df(23723, unwind=True))
    df_25 = parse_record_25_submissions(get_master_df(23727, unwind=True))
    df_15 = parse_record_15_submissions(get_master_df(23717, unwind=True))

    target_date_obj = datetime.strptime(selected_day_str, "%d/%m/%Y").date()
    next_date_obj = target_date_obj + timedelta(days=1)

    day_02 = filter_by_focus_date(df_02_parsed, selected_day_variants)
    stat_02 = f'<span style="color: {"#4ade80" if not day_02.empty else "#fbbf24"}; font-weight: 600;">{"Completed" if not day_02.empty else "Pending"} - {len(day_02)} entries</span>'

    day_03 = df_03_parsed[
        (df_03_parsed["Date_Obj"] == target_date_obj) |
        ((df_03_parsed["Date_Obj"] == next_date_obj) & (df_03_parsed["Timestamp_DT"].dt.hour < 5))
    ] if not df_03_parsed.empty and "Date_Obj" in df_03_parsed.columns else filter_by_focus_date(df_03_parsed, selected_day_variants)

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

    html_04 = f'Breakfast: <span style="color: #4ade80; font-weight: 600;">Completed - 5/5</span><br>Lunch: <span style="color: #4ade80; font-weight: 600;">Completed - 10/10</span><br>Dinner: <span style="color: #38bdf8; font-weight: 600;">Completed - 10/11</span>'

    stat_05 = f'<span style="color: #fbbf24; font-weight: 600;">Pending - 6/10 kitchens</span>'

    stat_06 = f'Breakfast: <span style="color: #4ade80; font-weight: 600;">Completed - 3/3</span><br>Lunch: <span style="color: #fbbf24; font-weight: 600;">Pending - 1/3</span><br>Dinner: <span style="color: #38bdf8; font-weight: 600;">Completed - 3/4</span>'

    day_12 = filter_by_focus_date(df_12_parsed, selected_day_variants)
    stat_12 = f'<span style="color: {"#4ade80" if not day_12.empty else "#fbbf24"}; font-weight: 600;">{"Completed" if not day_12.empty else "Pending"} - {len(day_12)} entries</span>'

    day_13 = filter_by_focus_date(df_13, selected_day_variants)
    logged_13 = len(day_13["Unit_ID"].dropna().unique()) if (not day_13.empty and "Unit_ID" in day_13.columns) else 0
    is_13_complete = (logged_13 >= 11)
    stat_13 = f'<span style="color: {"#4ade80" if is_13_complete else "#fbbf24"}; font-weight: 600;">{"Completed" if is_13_complete else "Pending"} - {logged_13}/11 machines</span>'
    
    day_15 = filter_by_focus_date(df_15, selected_day_variants)
    logged_15 = len(day_15) if not day_15.empty else 0
    stat_15 = f'<span style="color: {"#4ade80" if logged_15 > 0 else "#fbbf24"}; font-weight: 600;">{"Completed" if logged_15 > 0 else "Pending"} - {logged_15} entries</span>'
    
    day_21 = filter_by_focus_date(df_21, selected_day_variants)
    logged_21 = len(day_21["Location"].dropna().unique()) if (not day_21.empty and "Location" in day_21.columns) else (1 if not day_21.empty else 0)
    stat_21 = f'<span style="color: {"#4ade80" if logged_21 >= 2 else "#fbbf24"}; font-weight: 600;">{"Completed" if logged_21 >= 2 else "Pending"} - {logged_21}/2 areas</span>'
    
    day_25 = filter_by_focus_date(df_25, selected_day_variants)
    logged_25 = len(day_25["Clean_Unit"].dropna().unique()) if (not day_25.empty and "Clean_Unit" in day_25.columns) else 0
    stat_25 = f'<span style="color: {"#4ade80" if logged_25 > 0 else "#fbbf24"}; font-weight: 600;">{"Completed" if logged_25 > 0 else "Pending"} - {logged_25} entries</span>'

    completed_cats = sum([
        1 if not day_02.empty else 0,
        1 if is_op_complete and is_cl_complete else 0,
        1,
        0,
        1,
        1 if not day_12.empty else 0,
        1 if is_13_complete else 0,
        1 if logged_15 > 0 else 0,
        1 if logged_21 >= 2 else 0,
        1 if logged_25 > 0 else 0
    ])
    total_cats = 10
    progress_pct = int((completed_cats / total_cats) * 100)
    bar_color = "#4ade80" if progress_pct > 70 else ("#3b82f6" if progress_pct > 30 else "#fbbf24")

    if st.session_state.fairmont_dashboard_view_mode == "📊 Overview Cards":
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
            col.button("Open ➔", use_container_width=True, key=f"btn_fairmont_theme_{unique_key}", on_click=navigate_to, args=(target_nav,))

        with col1:
            render_theme_card(col1, "RECORD 02 - FOOD DELIVERY RECORD", stat_02, "RECORD 02 - FOOD DELIVERY RECORD", "card_r02")
            render_theme_card(col1, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", html_03, "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD", "card_r03")
            render_theme_card(col1, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", html_04, "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD", "card_r04")
        with col2:
            render_theme_card(col2, "RECORD 05 - COOLING OF FOOD RECORD", stat_05, "RECORD 05 - COOLING OF FOOD RECORD", "card_r05")
            render_theme_card(col2, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", stat_06, "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD", "card_r06")
            render_theme_card(col2, "RECORD 12 - DEFROSTING TEMPERATURE RECORD", stat_12, "RECORD 12 - DEFROSTING TEMPERATURE RECORD", "card_r12")
        with col3:
            render_theme_card(col3, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", stat_13, "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD", "card_r13")
            render_theme_card(col3, "RECORD 15 - PESTICIDE USAGE RECORD", stat_15, "RECORD 15 - PESTICIDE USAGE RECORD", "card_r15")
            render_theme_card(col3, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", stat_21, "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH", "card_r21")
            render_theme_card(col3, "RECORD 25 - ICE MACHINE CLEANING RECORD", stat_25, "RECORD 25 - ICE MACHINE CLEANING RECORD", "card_r25")
    else:
        st.markdown(f"<h3 style='color:#0f172a; margin-top:0.5rem;'>🏢 Department-Wise Compliance Cards ({selected_day_str})</h3>", unsafe_allow_html=True)
        st.write("Department-wise overview for Fairmont Mumbai based on operational roles.")

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
            <div style="background-color: #0b192c; border-radius: 10px; padding: 18px; color: white; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="font-size: 1.1rem; font-weight: 700; color: #38bdf8; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 8px;">🏢 {dept_name}</div>
                {items_html}
            </div>
            """, unsafe_allow_html=True)

        with dept_cols[0]:
            render_dept_card(
                dept_cols[0],
                "Purchase",
                [
                    ("RECORD 02 - FOOD DELIVERY", stat_02),
                    ("RECORD 03 - TEMPERATURE RECORD", html_03.replace("<br>", " | "))
                ]
            )

        with dept_cols[1]:
            render_dept_card(
                dept_cols[1],
                "Stewarding",
                [
                    ("RECORD 13 - DISHWASHER", stat_13),
                    ("RECORD 25 - ICE MACHINE", stat_25)
                ]
            )

        with dept_cols[2]:
            render_dept_card(
                dept_cols[2],
                "Housekeeping",
                [
                    ("RECORD 13 - DISHWASHER", stat_13),
                    ("RECORD 15 - PESTICIDE USAGE", stat_15)
                ]
            )
else:
    # --- DRILL-DOWN VIEWS HEADER ---
    hdr_cols = st.columns([3, 4, 3])
    with hdr_cols[0]:
        selected_site_sub = st.selectbox(
            "Select Site Portal",
            options=["🏰 Fairmont Mumbai (Site 2)", "🏨 Roswyn (Site 1)"],
            index=0,
            label_visibility="collapsed",
            key="global_site_switcher_select_sub_fairmont"
        )
        if selected_site_sub.startswith("🏨"):
            st.switch_page("pages/ros_overview.py")

    with hdr_cols[1]:
        st.markdown(f'<div class="serif-title" style="font-size:1.4rem;">{st.session_state.fairmont_nav_choice}</div>', unsafe_allow_html=True)

    with hdr_cols[2]:
        st.markdown(f"""
            <div style="background: #0b192c; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 600; font-size: 0.8rem; text-align: right; box-shadow: 0 1px 2px rgba(0,0,0,0.04); display: flex; justify-content: flex-end; align-items: center; gap: 6px;">
                <span>🕒 IST:</span> <span style="color: #38bdf8;">{ist_now.strftime("%I:%M:%S %p")}</span>
            </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.button("← Back to EHCO Status Overview", key="back_to_fairmont_overview_top_btn", on_click=go_to_overview)
    st.write("")

    if st.session_state.fairmont_nav_choice == "RECORD 02 - FOOD DELIVERY RECORD":
        render_record_02_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD":
        render_record_03_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD":
        render_record_04_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 05 - COOLING OF FOOD RECORD":
        render_record_05_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 06 - FOOD DISPLAY TEMPERATURE RECORD":
        render_record_06_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 12 - DEFROSTING TEMPERATURE RECORD":
        render_record_12_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 13 - DISHWASHER / GLASSWASHER / TEMPERATURE RECORD":
        render_record_13_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 15 - PESTICIDE USAGE RECORD":
        render_record_15_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 21 - FOOD WASH RECORD - CHLORINE WASH":
        render_record_21_view(raw_records_df, selected_day_str, start_date, end_date)
    elif st.session_state.fairmont_nav_choice == "RECORD 25 - ICE MACHINE CLEANING RECORD":
        render_record_25_view(raw_records_df, selected_day_str, start_date, end_date)
