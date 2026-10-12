from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_CM01_FORM_ID = 24144

# Explicit unit/sub-location names mapped per multi-unit location
CM01_LOCATION_CATALOG = {
    "Banquet": ["North", "West"],
    "Bombay Café": ["Machine 1", "Machine 2"],
    "Merchants": ["Machine 1", "Machine 2", "Machine 3"],
    "Gold Lounge": ["Main Unit"],
    "Grand Terminus": ["Main Unit"],
    "Hedonist": ["Main Unit"],
    "IRD": ["Main Unit"],
    "Madeleine de Proust": ["Main Unit"],
    "Samaa": ["Main Unit"],
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
    loc_parent = sub.get("Locations") if isinstance(sub.get("Locations"), dict) else sub

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

    # Extract exact unit/sub-location name from schema keys
    raw_sub_loc = str(
        loc_parent.get("Location_B")
        or loc_parent.get("Location_B_copy")
        or loc_parent.get("Location_M")
        or sub.get("Location_B")
        or sub.get("Location_B_copy")
        or sub.get("Location_M")
        or ""
    ).strip()

    # Normalize unit name to match catalog if needed
    sub_loc = raw_sub_loc if raw_sub_loc else ("Main Unit" if len(CM01_LOCATION_CATALOG.get(location, [])) == 1 else "Unknown Unit")

    shift_raw = str(sub.get("Shift") or sub.get("Shift_Name") or "Shift AM").strip()
    if "pm" in shift_raw.lower() or "2" in shift_raw.lower():
      shift = "PM"
    else:
      shift = "AM"

    sign = str(sub.get("Sign_initial") or sub.get("Sign") or rec.get("user.email") or "Staff").strip()

    rows.append({
        "Date_Str": date_str,
        "Date_Obj": date_obj,
        "Time": time_str,
        "Location": location,
        "Sub_Location": sub_loc,
        "Shift": shift,
        "Sign": sign,
        "Chemical": str(loc_parent.get("Name_of_Chemical_") or "Cafetto"),
    })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Sub_Location", "Shift"], keep="first")
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
      "📈 7-Day Shift Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    total_logs = len(day_df)
    completed_locations = 0
    total_locations = len(CM01_LOCATION_CATALOG)

    location_cards = []

    for loc_name, expected_units in CM01_LOCATION_CATALOG.items():
      loc_logs = day_df[day_df["Location"].str.strip().str.lower() == loc_name.lower()] if not day_df.empty else pd.DataFrame()
      
      logged_am_units = loc_logs[loc_logs["Shift"] == "AM"]["Sub_Location"].str.strip().str.lower().tolist()
      logged_pm_units = loc_logs[loc_logs["Shift"] == "PM"]["Sub_Location"].str.strip().str.lower().tolist()

      expected_lower = [str(u).strip().lower() for u in expected_units]

      # Check if all expected units for this location have logs in AM and PM
      am_complete = all(any(eu in lu for lu in logged_am_units) for eu in expected_lower)
      pm_complete = all(any(eu in lu for lu in logged_pm_units) for eu in expected_lower)

      is_loc_complete = am_complete and pm_complete
      if is_loc_complete:
        completed_locations += 1

      location_cards.append({
          "Location": loc_name,
          "Expected_Units": expected_units,
          "AM_Logged": logged_am_units,
          "PM_Logged": logged_pm_units,
          "Logs": loc_logs.to_dict("records"),
          "Complete": is_loc_complete,
      })

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{completed_locations}/{total_locations}</div>
                <div class="kpi-lbl">Fully Compliant Locations</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0284c7;">
                <div class="kpi-num" style="color:#0284c7;">{total_logs}</div>
                <div class="kpi-lbl">Total Shift Logs Submitted</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0f172a;">
                <div class="kpi-num" style="color:#0f172a;">{total_locations}</div>
                <div class="kpi-lbl">Active F&B Areas</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")
    st.markdown(
        "<h4 style='color:#0f172a; margin-top:1.5rem; margin-bottom:1rem;'>📍"
        f" Coffee Machine Cleaning Status ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )

    grid_cols = st.columns(3, gap="small")
    for idx, card in enumerate(location_cards):
      col_target = grid_cols[idx % 3]
      status_color = "#16a34a" if card["Complete"] else "#d97706"
      status_text = "✓ Fully Completed" if card["Complete"] else "⏳ Pending Shifts/Units"

      logs_html = ""
      if card["Logs"]:
        for l in card["Logs"]:
          unit_display = f" ({l['Sub_Location']})" if len(card["Expected_Units"]) > 1 and l["Sub_Location"] else ""
          logs_html += f'<div style="font-size:0.73rem; border-top:1px solid #e2e8f0; padding:3px 0; display:flex; justify-content:space-between;"><span><b>Shift {l["Shift"]}</b>{unit_display}</span><span style="color:#0284c7;">{l["Time"]}</span></div>'
      else:
        logs_html = '<div style="font-size:0.72rem; color:#b45309; font-style:italic;">No logs submitted today.</div>'

      expected_str = ", ".join(card["Expected_Units"])

      card_html = textwrap.dedent(f"""
          <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid {status_color}; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
              <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
                  <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {card["Location"]}</span>
                  <span style="color:{status_color}; font-weight:700; font-size:0.72rem;">{status_text}</span>
              </div>
              <div style="margin-top:6px; font-size:0.72rem; color:#64748b;">
                  <b>Required Units:</b> {expected_str}
              </div>
              <div style="margin-top:6px;">
                  {logs_html}
              </div>
          </div>
      """).strip()
      col_target.markdown(card_html, unsafe_allow_html=True)

  with tab_matrix:
    st.subheader("7-Day Coffee Machine Cleaning Shift Matrix")
    st.caption("Overview of cleaning logs across the selected date window grouped by unit/sub-location.")

    if range_df.empty:
      st.info("No records found for this date range.")
    else:
      total_days = max(1, (end_date - start_date).days + 1)
      matrix_dates = [start_date + timedelta(days=i) for i in range(total_days)]

      for loc_name, expected_units in CM01_LOCATION_CATALOG.items():
        st.markdown(f"""
            <div style="background:#0f172a; color:#ffffff; padding:8px 12px; border-radius:6px; margin-top:1.2rem; margin-bottom:0.5rem; font-weight:700; font-size:0.95rem;">
                📍 {loc_name}
            </div>
        """, unsafe_allow_html=True)

        num_dates = len(matrix_dates)
        col_ratios = [1.5] + [1.0] * num_dates
        cols = st.columns(col_ratios)

        cols[0].markdown('<div style="font-weight:700; font-size:0.78rem; color:#475569; padding:4px;">Unit & Shift</div>', unsafe_allow_html=True)
        for i, d in enumerate(matrix_dates):
          cols[i + 1].markdown(f'<div style="background:#f1f5f9; font-weight:700; font-size:0.75rem; text-align:center; padding:4px; border-radius:4px; color:#0f172a;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

        for unit_name in expected_units:
          for shift in ["AM", "PM"]:
            row_label = f"{unit_name} ({shift})" if len(expected_units) > 1 else f"Shift {shift}"
            row_cols = st.columns(col_ratios)
            row_cols[0].markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:4px; padding:6px; min-height:45px; display:flex; align-items:center;"><b style="font-size:0.76rem; color:#0f172a;">{row_label}</b></div>', unsafe_allow_html=True)

            for i, d in enumerate(matrix_dates):
              d_str = d.strftime("%d/%m/%Y")
              matches = range_df[
                  (range_df["Date_Str"] == d_str)
                  & (range_df["Location"].str.strip().str.lower() == loc_name.lower())
                  & (range_df["Shift"] == shift)
              ]
              if len(expected_units) > 1:
                matches = matches[matches["Sub_Location"].str.strip().str.lower().str.contains(unit_name.lower(), na=False)]

              if matches.empty:
                row_cols[i + 1].markdown('<div style="background:#fef2f2; border:1px solid #dc2626; border-radius:4px; padding:4px; min-height:45px; display:flex; justify-content:center; align-items:center;"><span style="color:#dc2626; font-weight:700; font-size:0.65rem;">Pending</span></div>', unsafe_allow_html=True)
              else:
                row_cols[i + 1].markdown('<div style="background:#f0fdf4; border:1.5px solid #16a34a; border-radius:4px; padding:4px; min-height:45px; display:flex; justify-content:center; align-items:center;"><span style="color:#16a34a; font-weight:800; font-size:0.68rem;">✓ Done</span></div>', unsafe_allow_html=True)

        st.write("")
