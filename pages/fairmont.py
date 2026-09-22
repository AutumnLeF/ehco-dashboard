from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

from records_fairmont.record_02 import (
    render_record_02_view,
    parse_record_02_submissions,
)
from records_fairmont.record_03 import (
    render_record_03_view,
    parse_record_03_submissions,
    UNIT_CATALOG,
    clean_unit_token,
)
from records_fairmont.record_04 import (
    render_record_04_view,
    parse_all_record_04_dishes,
)
from records_fairmont.record_05 import (
    render_record_05_view,
    parse_record_05_submissions,
)
from records_fairmont.record_06 import (
    render_record_06_view,
    parse_record_06_submissions,
)
from records_fairmont.record_12 import render_record_12_view
from records_fairmont.record_13 import (
    render_record_13_view,
    parse_record_13_submissions,
)
from records_fairmont.record_15 import (
    render_record_15_view,
    parse_record_15_submissions,
)
from records_fairmont.record_21 import (
    render_record_21_view,
    parse_record_21_submissions,
)
from records_fairmont.record_25 import (
    render_record_25_view,
    parse_record_25_submissions,
)

st.set_page_config(
    page_title="Fairmont Mumbai - EHCO Status",
    page_icon="🛡️",
    layout="wide",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #0f172a; }
    .serif-title { font-size: 2.1rem; font-weight: 700; color: #0f172a; margin-bottom: 0.2rem; letter-spacing: -0.02em; }
    .sub-head { font-size: 0.85rem; color: #475569; font-weight: 600; }
    .record-header-box { background-color: #0b192c; padding: 18px 24px; border-radius: 10px; color: white; margin-bottom: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-size: 1.6rem; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)

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
  st.session_state.fairmont_nav_choice = (
      "🏠 Fairmont Mumbai - EHCO Status Overview"
  )


def navigate_to(target_nav):
  st.session_state.fairmont_nav_choice = target_nav
  st.session_state.fairmont_nav_selectbox = target_nav


def go_to_overview():
  st.session_state.fairmont_nav_choice = (
      "🏠 Fairmont Mumbai - EHCO Status Overview"
  )
  st.session_state.fairmont_nav_selectbox = (
      "🏠 Fairmont Mumbai - EHCO Status Overview"
  )


st.sidebar.title("⚙️ Inspection Controls")
if st.sidebar.button("← Back to Landing Portal", use_container_width=True):
  st.switch_page("app.py")

st.sidebar.markdown("**Site:** Fairmont Mumbai (Site 2)")

ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
today = ist_now.date()
default_start_7d = today - timedelta(days=6)

date_selection = st.sidebar.date_input(
    "Audit Date Range (7 Days)",
    value=[default_start_7d, today],
    max_value=today,
    key="sb_fairmont_date_range_picker",
)
start_date, end_date = (
    date_selection
    if isinstance(date_selection, (list, tuple)) and len(date_selection) == 2
    else (
        (date_selection[0], date_selection[0])
        if isinstance(date_selection, (list, tuple))
        else (date_selection, date_selection)
    )
)

selected_day_str = st.sidebar.selectbox(
    "Focus Day for Drill-down",
    options=list(
        reversed([
            (start_date + timedelta(days=i)).strftime("%d/%m/%Y")
            for i in range((end_date - start_date).days + 1)
        ])
    ),
    key="sb_fairmont_day_focus_select",
)

api_url = st.sidebar.text_input(
    "Endpoint URL",
    value="https://auth-api.blinkm.io/form-store",
    key="sb_fairmont_api_endpoint_input",
)
token_input = st.sidebar.text_area(
    "Bearer Token",
    value=st.secrets.get("auth_token", "PASTE_FALLBACK_TOKEN_HERE").strip(),
    height=90,
    key="sb_fairmont_bearer_token_input",
)
clean_token = token_input.replace("Bearer ", "").strip()

nav_options = list(FORM_MAPPING.keys())
selected_record = st.sidebar.selectbox(
    "SELECT FOOD SAFETY RECORD",
    options=nav_options,
    index=(
        nav_options.index(st.session_state.fairmont_nav_choice)
        if st.session_state.fairmont_nav_choice in nav_options
        else 0
    ),
    key="fairmont_nav_selectbox",
)
if selected_record != st.session_state.fairmont_nav_choice:
  st.session_state.fairmont_nav_choice = selected_record
  st.rerun()

active_form_id = FORM_MAPPING[st.session_state.fairmont_nav_choice]


def fetch_submissions(url, token, form_id, unwind=True):
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
  all_rows, current_offset = [], 0
  for _ in range(15):
    payload = {
        "formId": form_id,
        "paging": {"limit": 50, "offset": current_offset},
        "sorting": [{"property": "dateTimeSubmitted", "direction": "descending"}],
        "unwindRepeatableSets": unwind,
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
      if len(items) < 50:
        break
      current_offset += 50
    except Exception:
      break
  return all_rows


if "fairmont_master_data_cache" not in st.session_state:
  st.session_state["fairmont_master_data_cache"] = {}
if st.sidebar.button(
    "🔄 Sync Live Feed",
    key="sync_fairmont_live_feed_btn",
    use_container_width=True,
):
  st.session_state["fairmont_master_data_cache"] = {}


def get_master_df(form_id, unwind=True):
  cache_key = f"{form_id}_unwind_{unwind}"
  if cache_key not in st.session_state["fairmont_master_data_cache"]:
    items = fetch_submissions(api_url, clean_token, form_id, unwind=unwind)
    st.session_state["fairmont_master_data_cache"][cache_key] = (
        pd.DataFrame({"raw_record": items}) if items else pd.DataFrame()
    )
  return st.session_state["fairmont_master_data_cache"][cache_key]


raw_records_df = (
    get_master_df(active_form_id, unwind=True)
    if active_form_id != 0
    else pd.DataFrame()
)

if (
    st.session_state.fairmont_nav_choice
    == "🏠 Fairmont Mumbai - EHCO Status Overview"
):
  st.markdown(
      f"""
        <div style="margin-bottom: 1rem;">
            <div class="serif-title" style="font-size:1.8rem;">Fairmont Mumbai - EHCO Status</div>
            <div class="sub-head">Date: <b>{selected_day_str}</b> &nbsp;|&nbsp; IST Time: <b>{ist_now.strftime("%H:%M:%S")}</b></div>
        </div>
    """,
      unsafe_allow_html=True,
  )
  st.info(
      "Select a record from the sidebar to inspect detailed logs and"
      " compliance."
  )
else:
  st.button(
      "← Back to EHCO Status Overview",
      key="back_to_fairmont_overview_top_btn",
      on_click=go_to_overview,
  )
  st.write("")
  if st.session_state.fairmont_nav_choice == "RECORD 02 - FOOD DELIVERY RECORD":
    st.markdown(
        f'<div class="record-header-box">🚚 {st.session_state.fairmont_nav_choice}</div>',
        unsafe_allow_html=True,
    )
    render_record_02_view(raw_records_df, selected_day_str, start_date, end_date)
  elif (
      st.session_state.fairmont_nav_choice
      == "RECORD 03 - COOLROOM / FRIDGE / FREEZER TEMPERATURE RECORD"
  ):
    st.markdown(
        f'<div class="record-header-box">❄️ {st.session_state.fairmont_nav_choice}</div>',
        unsafe_allow_html=True,
    )
    render_record_03_view(raw_records_df, selected_day_str, start_date, end_date)
  elif (
      st.session_state.fairmont_nav_choice
      == "RECORD 04 - COOKING/REHEATING TEMPERATURE RECORD"
  ):
    st.markdown(
        f'<div class="record-header-box">🔥 RECORD 04 - COOKING/REHEATING'
        " TEMPERATURE RECORD</div>",
        unsafe_allow_html=True,
    )
    render_record_04_view(raw_records_df, selected_day_str, start_date, end_date)
