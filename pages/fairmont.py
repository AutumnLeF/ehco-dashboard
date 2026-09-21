from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import requests
import streamlit as st

# Import other available records safely
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

# Correct Fairmont Mumbai Form Mapping IDs
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

# --- DIRECT EMBEDDED RECORD 04 LOGIC TO AVOID IMPORT ERRORS ---
RECORD_04_FORM_ID = 23706
TEMP_THRESHOLD = 75.0

KITCHEN_MEAL_RULES = {
    "Bakery/Pastry": ["Lunch", "Dinner"],
    "Banquet Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Cafeteria Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Gold Lounge Kitchen": ["Breakfast", "Dinner"],
    "Hedonist Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Indian Sweet / Halwai Kitchen": ["Lunch", "Dinner"],
    "IRD Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Madeleine de Proust": ["Breakfast", "Lunch", "Dinner"],
    "Merchant Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Oryn Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Samaa Kitchen": ["Lunch", "Dinner"],
}


def parse_all_record_04_dishes(raw_df):
  if raw_df.empty:
    return pd.DataFrame()
  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_04_FORM_ID), na=False)
    ]
  if df.empty:
    df = raw_df.copy()

  rows = []
  for _, row in df.iterrows():
    rec = row.get("raw_record") if "raw_record" in df.columns else row.to_dict()
    if not isinstance(rec, dict):
      rec = row.to_dict()
    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
    entry_parent = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else sub

    location = (
        sub.get("Location")
        or rec.get("Location")
        or entry_parent.get("Location")
        or "Unknown"
    )
    sign = (
        sub.get("Sign")
        or sub.get("sign")
        or rec.get("Sign")
        or rec.get("user.email")
        or "Staff"
    )
    raw_date = (
        sub.get("Date")
        or sub.get("date")
        or rec.get("createdAt")
        or rec.get("dateTimeSubmitted")
        or ""
    )
    parsed_dt = pd.to_datetime(raw_date, errors="coerce")
    if pd.isna(parsed_dt):
      parsed_dt = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")

    if pd.notna(parsed_dt):
      parsed_dt_ist = (
          parsed_dt + timedelta(hours=5, minutes=30)
          if parsed_dt.tzinfo is None
          else parsed_dt.tz_convert("Asia/Kolkata")
      )
      date_str = parsed_dt_ist.strftime("%d/%m/%Y")
      date_obj = parsed_dt_ist.date()
    else:
      date_str = str(raw_date)[:10]
      date_obj = None
      parsed_dt_ist = datetime.now()

    raw_time = sub.get("Time") or sub.get("time") or entry_parent.get("Time") or ""
    time_str = str(raw_time).strip()
    if "T" in time_str:
      try:
        time_str = time_str.split("T")[1][:5]
      except Exception:
        pass

    entries = (
        sub.get("set")
        or sub.get("Entry")
        or rec.get("set")
        or rec.get("Entry")
        or []
    )
    if isinstance(entries, dict):
      entries = [entries]
    if not entries and isinstance(sub, dict):
      entries = [sub]

    for entry in entries:
      if not isinstance(entry, dict):
        continue
      meal = (
          entry.get("Meal_Service")
          or entry.get("Meal")
          or entry.get("Meal Service")
          or "Unassigned"
      )
      food = entry.get("Name_of_Food") or entry.get("Food") or ""
      other_food = entry.get("Name_of_Food_Other") or ""

      if str(food).strip().lower() in ["other", ""] and str(other_food).strip():
        food_name = str(other_food).strip()
      elif str(food).strip() and str(food).strip().lower() != "other":
        food_name = str(food).strip()
      elif str(other_food).strip():
        food_name = str(other_food).strip()
      else:
        food_name = "Food Item"

      temp_cooking = entry.get("Temperature_Cooking") or entry.get(
          "Food Temperature °C (Cooking)"
      )
      temp_reheating = entry.get("Temperature_Reheating") or entry.get(
          "Food Temperature °C (Reheating)"
      )
      temp_raw = temp_cooking if pd.notna(temp_cooking) else temp_reheating
      heat_treatment = entry.get("Type_of_Heat_Treatment") or (
          "Reheating" if pd.notna(temp_reheating) else "Cooking"
      )
      temp_val = pd.to_numeric(
          str(temp_raw).replace("°C", "").replace("°", "").strip(),
          errors="coerce",
      )
      corrective = (
          entry.get("Corrective_Actions_cooking")
          or entry.get("Corrective_Action")
          or ""
      )

      rows.append({
          "Date_Str": date_str,
          "Date_Obj": date_obj,
          "Timestamp_DT": parsed_dt_ist,
          "Time": time_str,
          "Location": str(location).strip(),
          "Meal_Service": str(meal).strip(),
          "Heat_Treatment": str(heat_treatment).strip(),
          "Food": food_name,
          "Temp": temp_val,
          "Corrective_Action": str(corrective),
          "Sign": str(sign).strip(),
      })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(
        subset=[
            "Date_Str",
            "Time",
            "Location",
            "Meal_Service",
            "Food",
            "Temp",
        ],
        keep="first",
    )
  return df_out


def render_record_04_view(raw_df, selected_day_str, start_date, end_date):
  all_dishes_df = parse_all_record_04_dishes(raw_df)
  range_df = (
      all_dishes_df[
          (all_dishes_df["Date_Obj"] >= start_date)
          & (all_dishes_df["Date_Obj"] <= end_date)
      ]
      if not all_dishes_df.empty and "Date_Obj" in all_dishes_df.columns
      else all_dishes_df.copy()
  )

  tab_day, tab_matrix = st.tabs([
      f"📅 Daily Cooking & Reheating Audit ({selected_day_str})",
      "📈 14-Day Compliance Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )
    excursions, total_meals_required, total_meals_completed = [], 0, 0
    kitchen_status_list = []

    for kitchen, meals in KITCHEN_MEAL_RULES.items():
      k_df = (
          day_df[day_df["Location"].str.strip().str.lower() == kitchen.lower()]
          if not day_df.empty
          else pd.DataFrame()
      )
      meal_statuses = []
      for meal in meals:
        total_meals_required += 1
        m_df = (
            k_df[k_df["Meal_Service"].str.strip().str.lower() == meal.lower()]
            if not k_df.empty
            else pd.DataFrame()
        )
        if not m_df.empty:
          total_meals_completed += 1
          meal_statuses.append({
              "Meal": meal,
              "Status": "Completed",
              "Dishes": m_df.to_dict("records"),
              "Sign": m_df["Sign"].iloc[0],
          })
        else:
          meal_statuses.append({
              "Meal": meal,
              "Status": "Pending",
              "Dishes": [],
              "Sign": "",
          })
      kitchen_status_list.append({"Kitchen": kitchen, "Meals": meal_statuses})

    if not day_df.empty:
      for _, r in day_df[day_df["Temp"] < TEMP_THRESHOLD].iterrows():
        excursions.append({
            "Kitchen": r["Location"],
            "Meal": r["Meal_Service"],
            "Food": r["Food"],
            "Temp": r["Temp"],
            "Sign": r["Sign"],
        })

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Core Temp Breaches (< 75°C)", len(excursions))
    k2.metric("Logged Kitchen Shifts", total_meals_completed)
    k3.metric(
        "Pending Kitchen Shifts", total_meals_required - total_meals_completed
    )
    k4.metric("Total Items Logged", len(day_df))

    st.markdown(
        f"<h4 style='color:#0f172a; margin-top:1.5rem;'>🏢 Kitchen Audit"
        f" Blocks ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )

    for k_info in kitchen_status_list:
      k_name, m_list = k_info["Kitchen"], k_info["Meals"]
      meals_html = ""
      for m in m_list:
        if m["Status"] == "Completed":
          badge = "<span style='color:#16a34a; font-weight:700; float:right;'>✓ Completed</span>"
          dishes_list_html = "".join([
              f'<div style="display:flex; justify-content:space-between;'
              ' font-size:0.85rem; margin-top:6px; background:#ffffff;'
              ' padding:8px 12px; border-radius:6px; border:1px solid'
              f' #e2e8f0;"><span style="color:#0f172a;">🍲'
              f' <b>{dish["Food"]}</b> <span style="color:#64748b;'
              f' font-size:0.75rem; margin-left:8px;">({dish["Heat_Treatment"]})</span></span><span'
              f' style="color:{"#dc2626" if pd.notna(dish["Temp"]) and dish["Temp"] < TEMP_THRESHOLD else "#0f172a"};'
              f' font-weight:700;">{dish["Temp"]}°C</span></div>'
              for dish in m["Dishes"]
          ])
          sub_txt = (
              f'<div style="margin-top:8px;">{dishes_list_html}</div><div'
              ' style="font-size:0.75rem; color:#64748b; margin-top:6px;">Signed'
              f' by: {m["Sign"]}</div>'
          )
        else:
          badge = "<span style='color:#d97706; font-weight:700; float:right;'>⏳ Pending</span>"
          sub_txt = '<div style="font-size:0.8rem; color:#b45309; margin-top:6px; font-style:italic;">No records submitted yet.</div>'
        meals_html += f'<div style="background:#f8fafc; border-left:4px solid {"#16a34a" if m["Status"]=="Completed" else "#d97706"}; padding:12px 16px; border-radius:6px; margin-bottom:12px;"><div style="font-size:0.95rem; color:#0f172a; font-weight:700;">🍽️ {m["Meal"]} Service {badge}</div>{sub_txt}</div>'

      st.markdown(
          f'<div style="background:#ffffff; border:1px solid #cbd5e1;'
          ' border-top:4px solid #0f172a; border-radius:8px; padding:18px 20px;'
          ' margin-bottom:24px;"><div style="font-weight:700; font-size:1.1rem;'
          ' color:#0f172a; border-bottom:1px solid #e2e8f0; padding-bottom:10px;'
          f' margin-bottom:14px;">📍 {k_name}</div>{meals_html}</div>',
          unsafe_allow_html=True,
      )

  with tab_matrix:
    st.markdown(
        f"<h4 style='color:#0f172a; margin-top:1.5rem;'>📈 Compliance Matrix"
        f"</h4>",
        unsafe_allow_html=True,
    )
    if not range_df.empty:
      sel_kitchen = st.selectbox(
          "Filter Matrix by Kitchen", options=list(KITCHEN_MEAL_RULES.keys())
      )
      matrix_dates = [
          start_date + timedelta(days=i)
          for i in range(max(1, (end_date - start_date).days + 1))
      ]
      for meal in KITCHEN_MEAL_RULES[sel_kitchen]:
        st.markdown(
            f"<b style='color:#0f172a; font-size:0.95rem; margin-top:10px;"
            f" display:block;'>🍽️ {meal} Service</b>",
            unsafe_allow_html=True,
        )
        m_cols = st.columns(min(7, len(matrix_dates)))
        for i, d in enumerate(matrix_dates):
          col_target = m_cols[i % len(m_cols)]
          d_str = d.strftime("%d/%m/%Y")
          match_entry = range_df[
              (range_df["Date_Str"] == d_str)
              & (
                  range_df["Location"].str.strip().str.lower()
                  == sel_kitchen.lower()
              )
              & (
                  range_df["Meal_Service"].str.strip().str.lower()
                  == meal.lower()
              )
          ]
          if match_entry.empty:
            col_target.markdown(
                f'<div style="background:#f8fafc; border:1px solid #d97706;'
                ' border-radius:6px; padding:10px; margin-bottom:10px;'
                f' text-align:center;"><div style="font-size:0.75rem;'
                f' color:#64748b;">{d.strftime("%d/%m")}</div><div'
                ' style="color:#d97706; font-weight:800; font-size:0.8rem;'
                ' margin-top:6px;">⏳ Pending</div></div>',
                unsafe_allow_html=True,
            )
          else:
            items_html = "".join([
                f"<div style='font-size:0.75rem; color:#334155;'>•"
                f" <b>{dish['Food']}</b>: {dish['Temp']}°C</div>"
                for _, dish in match_entry.iterrows()
            ])
            col_target.markdown(
                f'<div style="background:#ffffff; border:1.5px solid #16a34a;'
                ' border-radius:6px; padding:10px; margin-bottom:10px;"><div'
                f' style="font-size:0.75rem; color:#64748b;">{d.strftime("%d/%m")}</div><div'
                ' style="font-weight:800; font-size:0.78rem; color:#16a34a;'
                f' margin-bottom:6px;">✓ Completed ({len(match_entry)})</div>{items_html}</div>',
                unsafe_allow_html=True,
            )


# --- STANDARD FAIRMONT NAV & APP STATE ROUTING ---
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


def fetch_submissions(url, token, form_id):
  if not form_id or form_id == 0 or not token:
    return []
  headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json",
      "Accept": "application/json",
      "Origin": "https://tehc-fairmont-mumbai.data-manager.oneblink.io",
  }
  all_rows, current_offset = [], 0
  for _ in range(15):
    payload = {
        "formId": form_id,
        "paging": {"limit": 50, "offset": current_offset},
        "sorting": [{"property": "dateTimeSubmitted", "direction": "descending"}],
        "unwindRepeatableSets": True,
    }
    try:
      res = requests.post(url.strip(), headers=headers, json=payload, timeout=20)
      if res.status_code != 200:
        break
      items = (
          res.json().get("submissions", [])
          if isinstance(res.json(), dict)
          else res.json()
      )
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


def get_master_df(form_id):
  if form_id not in st.session_state["fairmont_master_data_cache"]:
    items = fetch_submissions(api_url, clean_token, form_id)
    st.session_state["fairmont_master_data_cache"][form_id] = (
        pd.DataFrame({"raw_record": items}) if items else pd.DataFrame()
    )
  return st.session_state["fairmont_master_data_cache"][form_id]


raw_records_df = (
    get_master_df(active_form_id) if active_form_id != 0 else pd.DataFrame()
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
      "Select a specific record from the sidebar dropdown to view detailed"
      " logs and compliance matrices."
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
        f'<div class="record-header-box">🔥 {st.session_state.fairmont_nav_choice}</div>',
        unsafe_allow_html=True,
    )
    # Pull master records for Record 04 directly
    raw_04 = get_master_df(23706)
    render_record_04_view(raw_04, selected_day_str, start_date, end_date)
