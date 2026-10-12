from datetime import datetime, timedelta, timezone
import textwrap
import pandas as pd
import streamlit as st

RECORD_CM01_FORM_ID = 24144

# Master machine/unit definitions per location
CM01_LOCATION_UNITS = {
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

# Alias for compatibility with overview controller imports
CM01_LOCATION_RULES = CM01_LOCATION_UNITS


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

    raw_sub_loc = str(
        loc_parent.get("Location_B")
        or loc_parent.get("Location_B_copy")
        or loc_parent.get("Location_M")
        or sub.get("Location_B")
        or sub.get("Location_B_copy")
        or sub.get("Location_M")
        or ""
    ).strip()

    expected_units = CM01_LOCATION_UNITS.get(location, ["Main Unit"])
    if len(expected_units) == 1:
      sub_loc = expected_units[0]
    else:
      sub_loc = raw_sub_loc if raw_sub_loc else expected_units[0]

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
    total_locations = len(CM01_LOCATION_UNITS)

    location_cards = []

    for loc_name, expected_units in CM01_LOCATION_UNITS.items():
      loc_logs = day_df[day_df["Location"].str.strip().str.lower() == loc_name.lower()] if not day_df.empty else pd.DataFrame()
      
      unit_statuses = []
      loc_fully_complete = True

      for u_name in expected_units:
        if not loc_logs.empty and "Sub_Location" in loc_logs.columns and "Shift" in loc_logs.columns:
          u_logs = loc_logs[loc_logs["Sub_Location"].str.strip().str.lower() == u_name.lower()]
          am_done = not u_logs[u_logs["Shift"] == "AM"].empty
          pm_done = not u_logs[u_logs["Shift"] == "PM"].empty
        else:
          am_done = False
          pm_done = False
          u_logs = pd.DataFrame()
        
        if not (am_done and pm_done):
          loc_fully_complete = False

        unit_statuses.append({
            "Unit_Name": u_name,
            "AM": am_done,
            "PM": pm_done,
            "Logs": u_logs.to_dict("records"),
        })

      if loc_fully_complete:
        completed_locations += 1

      location_cards.append({
          "Location": loc_name,
          "Units": unit_statuses,
          "Complete": loc_fully_complete,
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

    pending_cards = [c for c in location_cards if not c["Complete"]]
    completed_cards = [c for c in location_cards if c["Complete"]]

    # --- SECTION 1: PENDING / INCOMPLETE LOCATIONS ---
    st.markdown(
        "<h4 style='color:#b45309; margin-top:1.5rem; margin-bottom:1rem;'>⏳"
        f" Pending / Incomplete Locations ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not pending_cards:
      st.success("🎉 All locations have completed their AM and PM cleaning shifts!")
    else:
      p_cols = st.columns(3, gap="small")
      for idx, card in enumerate(pending_cards):
        col_target = p_cols[idx % 3]
        
        units_html = ""
        for u in card["Units"]:
          am_badge = '<span style="color:#16a34a;">✓ AM</span>' if u["AM"] else '<span style="color:#dc2626;">⏳ AM</span>'
          pm_badge = '<span style="color:#16a34a;">✓ PM</span>' if u["PM"] else '<span style="color:#dc2626;">⏳ PM</span>'
          units_html += f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:6px; margin-top:4px; font-size:0.75rem; display:flex; justify-content:space-between;"><span><b>{u["Unit_Name"]}</b></span><span>{am_badge} | {pm_badge}</span></div>'

        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #d97706; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
                    <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {card["Location"]}</span>
                    <span style="color:#d97706; font-weight:700; font-size:0.72rem;">Pending Shifts</span>
                </div>
                <div style="margin-top:6px;">
                    {units_html}
                </div>
            </div>
        """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

    st.write("")

    # --- SECTION 2: COMPLETED & COMPLIANT LOCATIONS ---
    st.markdown(
        "<h4 style='color:#16a34a; margin-top:2rem; margin-bottom:1rem;'>✅"
        f" Completed & Compliant Locations ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not completed_cards:
      st.info("No fully completed locations available yet.")
    else:
      c_cols = st.columns(3, gap="small")
      for idx, card in enumerate(completed_cards):
        col_target = c_cols[idx % 3]

        units_html = ""
        for u in card["Units"]:
          units_html += f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:6px; margin-top:4px; font-size:0.75rem; display:flex; justify-content:space-between;"><span><b>{u["Unit_Name"]}</b></span><span style="color:#16a34a; font-weight:700;">✓ AM & PM Done</span></div>'

        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #16a34a; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
                    <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {card["Location"]}</span>
                    <span style="color:#16a34a; font-weight:700; font-size:0.72rem;">✓ Fully Completed</span>
                </div>
                <div style="margin-top:6px;">
                    {units_html}
                </div>
            </div>
        """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

  with tab_matrix:
    st.subheader("7-Day Coffee Machine Cleaning Shift Matrix")
    st.caption("Overview of cleaning logs across the selected date window grouped by machine unit.")

    if range_df.empty:
      st.info("No records found for this date range.")
    else:
      total_days = max(1, (end_date - start_date).days + 1)
      matrix_dates = [start_date + timedelta(days=i) for i in range(total_days)]
      current_today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()

      for loc_name, expected_units in CM01_LOCATION_UNITS.items():
        st.markdown(f"""
            <div style="background:#0f172a; color:#ffffff; padding:8px 12px; border-radius:6px; margin-top:1.2rem; margin-bottom:0.5rem; font-weight:700; font-size:0.95rem;">
                📍 {loc_name}
            </div>
        """, unsafe_allow_html=True)

        num_dates = len(matrix_dates)
        col_ratios = [1.5] + [1.0] * num_dates
        cols = st.columns(col_ratios)

        cols[0].markdown('<div style="font-weight:700; font-size:0.78rem; color:#475569; padding:4px;">Machine Unit</div>', unsafe_allow_html=True)
        for i, d in enumerate(matrix_dates):
          cols[i + 1].markdown(f'<div style="background:#f1f5f9; font-weight:700; font-size:0.75rem; text-align:center; padding:4px; border-radius:4px; color:#0f172a;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

        for unit_name in expected_units:
          row_cols = st.columns(col_ratios)
          row_cols[0].markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:4px; padding:6px; min-height:50px; display:flex; align-items:center;"><b style="font-size:0.76rem; color:#0f172a;">{unit_name}</b></div>', unsafe_allow_html=True)

          for i, d in enumerate(matrix_dates):
            d_str = d.strftime("%d/%m/%Y")
            day_matches = range_df[range_df["Date_Str"] == d_str]
            loc_matches = day_matches[day_matches["Location"].str.strip().str.lower() == loc_name.lower()] if not day_matches.empty else pd.DataFrame()

            if len(expected_units) > 1 and not loc_matches.empty:
              u_matches = loc_matches[loc_matches["Sub_Location"].str.strip().str.lower().str.contains(unit_name.lower(), na=False)]
            else:
              u_matches = loc_matches

            am_done = not u_matches[u_matches["Shift"] == "AM"].empty if not u_matches.empty else False
            pm_done = not u_matches[u_matches["Shift"] == "PM"].empty if not u_matches.empty else False

            is_old = (current_today - d).days > 1  # More than 1 day old (2+ days in the past)
            pending_icon = "❌" if is_old else "⏳"

            am_str = '<span style="color:#16a34a; font-weight:700;">✓ AM</span>' if am_done else f'<span style="color:#dc2626; font-weight:700;">{pending_icon} AM</span>'
            pm_str = '<span style="color:#16a34a; font-weight:700;">✓ PM</span>' if pm_done else f'<span style="color:#dc2626; font-weight:700;">{pending_icon} PM</span>'

            all_done = am_done and pm_done
            box_bg = "#f0fdf4" if all_done else "#fef2f2"
            box_border = "#16a34a" if all_done else "#dc2626"

            row_cols[i + 1].markdown(
                f'<div style="background:{box_bg}; border:1.5px solid {box_border}; border-radius:4px; padding:6px; min-height:50px; display:flex; flex-direction:column; justify-content:center; align-items:center; font-size:0.68rem;">'
                f'<div>{am_str}</div>'
                f'<div style="margin-top:2px;">{pm_str}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.write("")
