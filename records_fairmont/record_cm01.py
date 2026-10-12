from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_CM01_FORM_ID = 24144

# Catalog with exact required unit counts per location
CM01_LOCATION_RULES = {
    "Banquet": 3,
    "Bombay Café": 2,
    "Merchants": 3,
    "Gold Lounge": 1,
    "Grand Terminus": 1,
    "Hedonist": 1,
    "IRD": 1,
    "Madeleine de Proust": 1,
    "Samaa": 1,
}


def parse_record_cm01_submissions(raw_df):
  """Robustly parses Record CM01 Coffee Machine Cleaning submissions."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_CM01_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  rows = []
  for _, record in df.iterrows():
    rec = record.get("raw_record") if "raw_record" in record.to_dict() else record.to_dict()
    if not isinstance(rec, dict):
      rec = record.to_dict()

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
    loc_parent = sub.get("Locations") if isinstance(sub.get("Locations"), dict) else {}

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
      if parsed_dt.tzinfo is None:
        parsed_dt_ist = parsed_dt + timedelta(hours=5, minutes=30)
      else:
        parsed_dt_ist = parsed_dt.tz_convert("Asia/Kolkata")
      date_str = parsed_dt_ist.strftime("%d/%m/%Y")
      date_obj = parsed_dt_ist.date()
    else:
      date_str = str(raw_date)[:10]
      date_obj = None

    time_raw = str(sub.get("Time") or rec.get("dateTimeSubmitted") or "")
    if "T" in time_raw:
      try:
        dt_time = pd.to_datetime(time_raw, errors="coerce")
        if pd.notna(dt_time):
          dt_time_ist = dt_time + timedelta(hours=5, minutes=30)
          time_str = dt_time_ist.strftime("%I:%M %p")
        else:
          time_str = time_raw.split("T")[1][:5]
      except:
        time_str = time_raw[:8]
    else:
      time_str = time_raw[:8]

    location = str(
        loc_parent.get("Location")
        or sub.get("Location")
        or rec.get("Location")
        or "Banquet"
    ).strip()

    shift_raw = str(sub.get("Shift") or sub.get("Shift_Name") or "Shift AM").strip()
    if "pm" in shift_raw.lower() or "2" in shift_raw.lower():
      shift = "PM"
    else:
      shift = "AM"

    sign = str(sub.get("Sign_initial") or sub.get("Sign") or rec.get("user.email") or "Staff").strip()

    bean_dispenser = str(loc_parent.get("Coffee_bean_dispenser") or "No")
    refrigerator = str(loc_parent.get("Refrigerator_unit") or "No")
    sink_tray = str(loc_parent.get("Sink_tray") or "No")
    steam_pipe = str(loc_parent.get("Steam_pipe_sanitation") or "No")
    suma_vend = str(loc_parent.get("Suma_vend_tab") or "No")
    waste_col = str(loc_parent.get("Waste_collector") or "No")
    chemical = str(loc_parent.get("Name_of_Chemical_") or "Cafetto")

    rows.append({
        "Date_Str": date_str,
        "Date_Obj": date_obj,
        "Time": time_str,
        "Location": location,
        "Shift": shift,
        "Sign": sign,
        "Chemical": chemical,
        "Bean_Dispenser": bean_dispenser,
        "Refrigerator": refrigerator,
        "Sink_Tray": sink_tray,
        "Steam_Pipe": steam_pipe,
        "Suma_Vend": suma_vend,
        "Waste_Collector": waste_col,
    })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Shift", "Sign"], keep="first")
  return df_out


def render_record_cm01_view(raw_df, selected_day_str, start_date, end_date):
  st.markdown(
      """
    <style>
    .kpi-container {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-top: 4px solid #0f172a;
        border-radius: 8px;
        padding: 14px 18px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 10px;
    }
    .kpi-num {
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    .kpi-lbl {
        font-size: 0.78rem;
        color: #64748b;
        font-weight: 700;
        text-transform: uppercase;
        margin-top: 2px;
    }
    </style>
    """,
      unsafe_allow_html=True,
  )

  df_items = parse_record_cm01_submissions(raw_df)

  with st.expander("🔍 Record CM01 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed coffee machine cleaning records: **{len(df_items)}**")
    if not df_items.empty:
      st.dataframe(df_items.head(10), use_container_width=True)

  if not df_items.empty and "Date_Obj" in df_items.columns:
    range_df = df_items[
        (df_items["Date_Obj"] >= start_date)
        & (df_items["Date_Obj"] <= end_date)
    ]
  else:
    range_df = df_items.copy()

  tab_day, tab_matrix = st.tabs([
      f"📅 Daily Cleaning Audit ({selected_day_str})",
      "📈 7-Day Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    completed_shifts_count = len(day_df)
    
    # Evaluate AM / PM compliance per location unit requirement
    loc_status_summary = []
    total_required_logs = 0

    for loc_name, required_units in CM01_LOCATION_RULES.items():
      total_required_logs += (required_units * 2) # AM and PM for each required unit
      loc_logs = day_df[day_df["Location"].str.strip().str.lower() == loc_name.lower()] if not day_df.empty else pd.DataFrame()
      
      am_logs = loc_logs[loc_logs["Shift"] == "AM"]
      pm_logs = loc_logs[loc_logs["Shift"] == "PM"]

      loc_status_summary.append({
          "Location": loc_name,
          "Required_Units": required_units,
          "AM_Count": len(am_logs),
          "PM_Count": len(pm_logs),
          "Logs": loc_logs.to_dict("records"),
      })

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{completed_shifts_count}</div>
                <div class="kpi-lbl">Total Shift Logs Submitted</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0284c7;">
                <div class="kpi-num" style="color:#0284c7;">{total_required_logs}</div>
                <div class="kpi-lbl">Total Required Shift Logs</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0f172a;">
                <div class="kpi-num" style="color:#0f172a;">{len(CM01_LOCATION_RULES)}</div>
                <div class="kpi-lbl">Active Locations</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")
    st.markdown(
        "<h4 style='color:#0f172a; margin-top:1.5rem; margin-bottom:1rem;'>🏢"
        f" Location Shift Status ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns(2)

    with col_left:
      st.markdown('<div style="background:#f0fdf4; border:1px solid #bbf7d0; border-left:5px solid #16a34a; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#15803d; font-size:0.98rem;">🟢 Completed Locations</b></div>', unsafe_allow_html=True)
      completed_locs = [l for l in loc_status_summary if l["AM_Count"] >= l["Required_Units"] and l["PM_Count"] >= l["Required_Units"]]
      
      if completed_locs:
        for loc in completed_locs:
          st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:4px solid #16a34a; padding:10px; border-radius:6px; margin-bottom:8px;"><div style="font-weight:700; color:#0f172a;">📍 {loc["Location"]}</div><div style="font-size:0.75rem; color:#15803d; margin-top:2px;">AM Logs: {loc["AM_Count"]}/{loc["Required_Units"]} | PM Logs: {loc["PM_Count"]}/{loc["Required_Units"]} (Fully Compliant)</div></div>', unsafe_allow_html=True)
      else:
        st.info("No fully completed locations for both shifts yet.")

    with col_right:
      st.markdown('<div style="background:#fffbeb; border:1px solid #fde68a; border-left:5px solid #d97706; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#b45309; font-size:0.98rem;">⏳ Pending / Incomplete Shifts</b></div>', unsafe_allow_html=True)
      pending_locs = [l for l in loc_status_summary if l["AM_Count"] < l["Required_Units"] or l["PM_Count"] < l["Required_Units"]]

      if pending_locs:
        for loc in pending_locs:
          st.markdown(f'<div style="background:#ffffff; border:1px solid #fca5a5; border-left:4px solid #d97706; padding:10px; border-radius:6px; margin-bottom:8px;"><div style="font-weight:700; color:#0f172a;">📍 {loc["Location"]}</div><div style="font-size:0.75rem; color:#b45309; margin-top:2px;">AM Logs: {loc["AM_Count"]}/{loc["Required_Units"]} | PM Logs: {loc["PM_Count"]}/{loc["Required_Units"]} (Pending)</div></div>', unsafe_allow_html=True)
      else:
        st.success("🎉 All locations have completed their AM and PM shift logs!")

  with tab_matrix:
    st.subheader("7-Day Coffee Machine Cleaning Matrix")
    if not range_df.empty:
      st.dataframe(range_df, use_container_width=True, hide_index=True)
    else:
      st.info("No records found in the selected date range.")
