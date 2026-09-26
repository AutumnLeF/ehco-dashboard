from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

RECORD_25_FORM_ID = 23727  # Record 25 Form ID

# Master catalog of Ice Machines grouped by exact location
ICE_MACHINE_CATALOG = {
    "Banquet Show Kitchen": [
        {"Unit_ID": "Ice Cube-FM/ICM/BSK 05-240kg", "Name": "Ice Cube 05"},
    ],
    "Banquet Support Kitchen": [
        {"Unit_ID": "Ice Cube-FM/ICM/BSK 02-580kg", "Name": "Ice Cube 02"},
        {"Unit_ID": "Ice Cube-FM/ICM/IPA03-580kg", "Name": "Ice Cube 03"},
        {"Unit_ID": "Ice Flake-FM/ICM/BSK 04-290kg", "Name": "Ice Flake 04"},
    ],
    "IRD": [
        {"Unit_ID": "Ice cube-FM/ICM/IRD24", "Name": "IRD Ice Cube 24"},
        {"Unit_ID": "Ice cube-FM/ICM/IRD25", "Name": "IRD Ice Cube 25"},
    ],
    "Oryn Pantry": [
        {"Unit_ID": "Undercounter ice cube-FM/ICM/OP 07-28kg", "Name": "Oryn Ice Cube 20"},
    ],
    "The Hedonist Pantry": [
        {"Unit_ID": "Undercounter ice cube-FM/ICM/THP 10-28kg", "Name": "THP 10-28kg"},
        {"Unit_ID": "Ice cube-FM/ICM/THP 08-100kg", "Name": "THP 08-100kg"},
        {"Unit_ID": "Ice flake-FM/ICM/THP 09-53kg", "Name": "THP 09-53kg"},
    ],
    "The Merchants": [
        {"Unit_ID": "Ice Cube-FM/ICM/TM 12-580kg", "Name": "TM 12-580kg"},
        {"Unit_ID": "Ice flake-FM/ICM/TM 13-290kg", "Name": "TM 13-290kg"},
        {"Unit_ID": "Ice Cube-FM/ICM/TM 11-580kg", "Name": "TM 11-580kg"},
    ],
    "Madeleine De Proust Pantry": [
        {"Unit_ID": "Ice Cube-FM/ICM/MDP 06-100kg", "Name": "MDP Cube 06"},
    ],
    "Vantge": [
        {"Unit_ID": "Ice Cube machine - FM/ICM/VANT1", "Name": "Vantge Cube 1"},
        {"Unit_ID": "Ice Flake machine - FM/ICM/VANT2", "Name": "Vantge Flake 2"},
    ],
}


def clean_str(val):
  """Normalizes string for comparison."""
  if not val or pd.isna(val):
    return ""
  return (
      str(val)
      .replace("/", "")
      .replace("_", "")
      .replace(" ", "")
      .replace("-", "")
      .strip()
      .upper()
  )


def parse_record_25_submissions(raw_df):
  """Parses Record 25 Ice Machine cleaning submissions targeting the exact schema."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  flat_master = []
  for loc, units in ICE_MACHINE_CATALOG.items():
    for u in units:
      flat_master.append({"Location": loc, "Unit_ID": u["Unit_ID"]})

  rows = []
  for _, record in raw_df.iterrows():
    rec = record.get("raw_record") if "raw_record" in raw_df.columns else record.to_dict()
    if not isinstance(rec, dict):
      rec = record.to_dict()

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec

    raw_date = (
        sub.get("date")
        or sub.get("Date")
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

    kitchen_location = str(
        sub.get("Ice_Machine_Location")
        or sub.get("Location")
        or rec.get("Location")
        or "Kitchen Area"
    ).strip()

    raw_unit = (
        sub.get("location")
        or sub.get("Ice_Machine_Number")
        or sub.get("Ice Machine Number")
        or ""
    )

    clean_raw_unit = clean_str(raw_unit)
    matched_id = None
    matched_loc = kitchen_location

    for m in flat_master:
      if clean_raw_unit == clean_str(m["Unit_ID"]):
        matched_id = m["Unit_ID"]
        matched_loc = m["Location"]
        break

    final_unit = matched_id if matched_id else str(raw_unit).strip()

    status_raw = str(
        sub.get("USE")
        or sub.get("In_Use_Not_In_Use")
        or "IN USE"
    ).strip().upper()
    is_in_use = "NOT" not in status_raw

    sign = (
        sub.get("sign")
        or sub.get("Sign")
        or sub.get("Sign (Initial)")
        or "Staff"
    )

    rows.append({
        "Date_Str": date_str,
        "Date_Obj": date_obj,
        "Location": matched_loc or "Kitchen Area",
        "Unit_ID": final_unit,
        "Clean_Unit": clean_str(final_unit),
        "In_Use": is_in_use,
        "Status_Text": status_raw,
        "Sign": str(sign).strip(),
    })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Location", "Unit_ID"], keep="first")
  return df_out


def render_record_25_view(raw_df, selected_day_str, start_date, end_date):
  df_items = parse_record_25_submissions(raw_df)

  with st.expander("🔍 Record 25 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed ice machine records: **{len(df_items)}**")
    if not df_items.empty and "Date_Obj" in df_items.columns:
      date_counts = df_items["Date_Obj"].dropna().value_counts().sort_index(ascending=False).to_dict()
      st.write("Records per date found:", {str(k): v for k, v in date_counts.items()})

  selected_dt = pd.to_datetime(selected_day_str, format="%d/%m/%Y", errors="coerce")
  if pd.isna(selected_dt):
    selected_dt = datetime.now().date()
  else:
    selected_dt = selected_dt.date()

  window_start_dt = selected_dt - timedelta(days=6)

  if not df_items.empty and "Date_Obj" in df_items.columns and df_items["Date_Obj"].notna().any():
    range_df = df_items[
        (df_items["Date_Obj"] >= start_date)
        & (df_items["Date_Obj"] <= end_date)
    ]
    history_df = df_items[df_items["Date_Obj"] <= selected_dt]
  else:
    range_df = df_items.copy()
    history_df = df_items.copy()

  tab_day, tab_matrix = st.tabs([
      f"📅 Daily Ice Machine Audit ({selected_day_str})",
      "📈 Weekly Cleaning Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    all_units_flat = []
    for loc_name, units in ICE_MACHINE_CATALOG.items():
      for u in units:
        all_units_flat.append({"Location": loc_name, **u})

    cleaned_count = 0
    pending_count = 0
    unit_status_list = []

    for sch in all_units_flat:
      u_id = sch["Unit_ID"]
      u_token = clean_str(u_id)
      u_loc = sch["Location"]
      
      today_log = pd.DataFrame()
      if not day_df.empty and "Clean_Unit" in day_df.columns:
        today_log = day_df[(day_df["Clean_Unit"] == u_token) & (day_df["Location"].str.strip().str.lower() == u_loc.lower())]
        if today_log.empty:
          today_log = day_df[day_df["Clean_Unit"] == u_token]

      if not today_log.empty:
        cleaned_count += 1
        unit_status_list.append({"Unit": sch, "Status": "Cleaned", "Log": today_log.iloc[-1], "Days_Since": 0})
      else:
        recent_logs = pd.DataFrame()
        unit_history = pd.DataFrame()
        if not history_df.empty and "Date_Obj" in history_df.columns:
          unit_history = history_df[history_df["Clean_Unit"] == u_token]
          recent_logs = unit_history[
              (unit_history["Date_Obj"] >= window_start_dt)
              & (unit_history["Date_Obj"] <= selected_dt)
          ]

        if recent_logs.empty:
          pending_count += 1
          # Calculate exact days since last clean
          days_since = None
          if not unit_history.empty and "Date_Obj" in unit_history.columns:
            last_clean_date = unit_history["Date_Obj"].max()
            if pd.notna(last_clean_date):
              days_since = (selected_dt - last_clean_date).days
          unit_status_list.append({"Unit": sch, "Status": "Pending", "Log": None, "Days_Since": days_since})
        else:
          unit_status_list.append({"Unit": sch, "Status": "Recent", "Log": recent_logs.iloc[-1], "Days_Since": 0})

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #16a34a;"><div class="kpi-num" style="color:#16a34a;">{cleaned_count}</div><div class="kpi-lbl">Cleaned Today</div></div>', unsafe_allow_html=True)
    with k2:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #dc2626;"><div class="kpi-num" style="color:#dc2626;">{pending_count}</div><div class="kpi-lbl">Pending (>6 Days Overdue)</div></div>', unsafe_allow_html=True)
    with k3:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #0f172a;"><div class="kpi-num" style="color:#0f172a;">{len(all_units_flat)}</div><div class="kpi-lbl">Total F&B Ice Machines</div></div>', unsafe_allow_html=True)

    st.write("")
    day_name = selected_dt.strftime("%A")
    st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>🧊 Ice Machine Cleaning Audit ({day_name} — {selected_day_str})</h4>", unsafe_allow_html=True)
    st.caption("Mandatory compliance: Machines not cleaned in the last 6 days are flagged as pending/overdue with exact days elapsed.")

    col_left, col_right = st.columns(2)

    with col_left:
      st.markdown('<div style="background:#fffbeb; border:1px solid #fde68a; border-left:5px solid #dc2626; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#b91c1c; font-size:0.98rem;">⏳ Pending / Overdue (>6 Days)</b></div>', unsafe_allow_html=True)
      
      if pending_count > 0:
        for item in unit_status_list:
          if item["Status"] == "Pending":
            sch = item["Unit"]
            days_val = item["Days_Since"]
            if days_val is not None:
              overdue_str = f"Not cleaned for **{days_val} days** (Overdue!)"
            else:
              overdue_str = "No prior cleaning record found (Overdue!)"

            st.markdown(f'<div style="background:#ffffff; border:1px solid #fca5a5; border-left:4px solid #dc2626; padding:12px; border-radius:6px; margin-bottom:8px;"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🧊 {sch["Unit_ID"]}</div><div style="font-size:0.8rem; color:#dc2626; font-weight:700; margin-top:2px;">📍 {sch["Location"]}</div><div style="font-size:0.75rem; color:#dc2626; margin-top:4px; font-style:italic;">{overdue_str}</div></div>', unsafe_allow_html=True)
      else:
        st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:14px; border-radius:6px; color:#16a34a; font-size:0.85rem; text-align:center;">✓ No overdue ice machines! All units have been cleaned within the 6-day window.</div>', unsafe_allow_html=True)

    with col_right:
      st.markdown('<div style="background:#f0fdf4; border:1px solid #bbf7d0; border-left:5px solid #16a34a; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#15803d; font-size:0.98rem;">🟢 Cleaned & Compliant</b></div>', unsafe_allow_html=True)
      
      cleaned_or_recent = [item for item in unit_status_list if item["Status"] in ["Cleaned", "Recent"]]
      if cleaned_or_recent:
        for item in cleaned_or_recent:
          sch = item["Unit"]
          log = item["Log"]
          status_tag = "Cleaned Today" if item["Status"] == "Cleaned" else f"Cleaned on {log['Date_Str']}"
          st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:4px solid #16a34a; padding:12px; border-radius:6px; margin-bottom:8px;"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🧊 {sch["Unit_ID"]}</div><div style="font-size:0.8rem; color:#15803d; font-weight:700; margin-top:2px;">📍 {sch["Location"]}</div><div style="font-size:0.75rem; color:#15803d; margin-top:2px;">{status_tag} | Signed: {log["Sign"]}</div></div>', unsafe_allow_html=True)
      else:
        st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:14px; border-radius:6px; color:#64748b; font-size:0.85rem; text-align:center;">No cleaning records found in the recent window.</div>', unsafe_allow_html=True)

  with tab_matrix:
    st.subheader("Kitchen-Wise Weekly Ice Machine Cleaning Matrix")
    st.caption("Ice machines grouped separately by kitchen area with 6-day compliance tracking.")

    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec25_page" not in st.session_state:
      st.session_state.rec25_page = max(0, (total_days - 1) // 7)

    max_page = max(0, (total_days - 1) // 7)

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
      if st.button("⬅️ Previous 7 Days", key="r25_prev", disabled=(st.session_state.rec25_page <= 0), use_container_width=True):
        st.session_state.rec25_page -= 1
        st.rerun()

    with nav3:
      if st.button("Next 7 Days ➡️", key="r25_next", disabled=(st.session_state.rec25_page >= max_page), use_container_width=True):
        st.session_state.rec25_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec25_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with nav2:
      if page_dates:
        st.markdown(f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec25_page + 1} of {max_page + 1})</div>", unsafe_allow_html=True)

    st.write("")

    cols_header = st.columns([2.0, 1, 1, 1, 1, 1, 1, 1])
    cols_header[0].markdown('<div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.85rem; padding:10px 4px; border-radius:6px; text-align:center;">Ice Machine Unit</div>', unsafe_allow_html=True)
    
    for i, d in enumerate(page_dates):
      day_short = d.strftime("%a").upper()
      cols_header[i + 1].markdown(f'<div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.8rem; padding:10px 2px; border-radius:6px; text-align:center;">{d.strftime("%d/%m")} ({day_short})</div>', unsafe_allow_html=True)

    st.write("")

    for kitchen_name, units in ICE_MACHINE_CATALOG.items():
      st.markdown(f"""
          <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 10px 16px; border-radius: 8px; font-weight: 700; font-size: 0.98rem; margin-top: 1.5rem; margin-bottom: 0.8rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
              📍 {kitchen_name}
          </div>
      """, unsafe_allow_html=True)

      for sch in units:
        unit_id = sch["Unit_ID"]
        unit_token = clean_str(unit_id)

        row_cols = st.columns([2.0, 1, 1, 1, 1, 1, 1, 1])
        row_cols[0].markdown(f'<div style="background:#ffffff; border:1.5px solid #cbd5e1; border-radius:8px; padding:10px 8px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); min-height:75px; display:flex; flex-direction:column; align-items:center; justify-content:center;"><div style="font-weight:700; color:#0f172a; font-size:0.78rem;">{unit_id}</div></div>', unsafe_allow_html=True)

        u_df = range_df[range_df["Clean_Unit"] == unit_token] if not range_df.empty else pd.DataFrame()
        u_history = df_items[df_items["Clean_Unit"] == unit_token] if not df_items.empty else pd.DataFrame()

        for i, d in enumerate(page_dates):
          d_str = d.strftime("%d/%m/%Y")
          matches = pd.DataFrame()
          if not u_df.empty:
            if "Date_Obj" in u_df.columns:
              matches = u_df[u_df["Date_Obj"] == d]
            if matches.empty and "Date_Str" in u_df.columns:
              matches = u_df[u_df["Date_Str"] == d_str]

          if not matches.empty:
            latest = matches.iloc[-1]
            row_cols[i + 1].markdown(f'<div style="background:#f0fdf4; border:1.5px solid #16a34a; border-radius:8px; padding:6px; text-align:center; min-height:75px; display:flex; flex-direction:column; justify-content:center; align-items:center;"><span style="color:#16a34a; font-weight:800; font-size:0.75rem;">✓ CLEANED</span><span style="font-size:0.62rem; color:#15803d; margin-top:2px;">{latest["Sign"]}</span></div>', unsafe_allow_html=True)
          else:
            d_window_start = d - timedelta(days=6)
            recent_past = pd.DataFrame()
            if not u_history.empty and "Date_Obj" in u_history.columns:
              recent_past = u_history[
                  (u_history["Date_Obj"] >= d_window_start)
                  & (u_history["Date_Obj"] <= d)
              ]

            if recent_past.empty:
              row_cols[i + 1].markdown(f'<div style="background:#fef2f2; border:1.5px solid #dc2626; border-radius:8px; padding:6px; text-align:center; min-height:75px; display:flex; flex-direction:column; justify-content:center; align-items:center;"><span style="color:#dc2626; font-weight:800; font-size:0.72rem;">⏳ PENDING</span><span style="font-size:0.60rem; color:#b91c1c; margin-top:2px;">Overdue >6d</span></div>', unsafe_allow_html=True)
            else:
              row_cols[i + 1].markdown(f'<div style="background:#ffffff; border:1.0px solid #e2e8f0; border-radius:8px; padding:6px; text-align:center; min-height:75px; display:flex; align-items:center; justify-content:center;"><span style="color:#94a3b8; font-size:0.75rem;">—</span></div>', unsafe_allow_html=True)

        st.write("")

    st.divider()
    with st.expander("📋 View All Individual Ice Machine Cleaning Records"):
      if not range_df.empty:
        show_cols = [c for c in ["Date_Str", "Location", "Unit_ID", "Status_Text", "Sign"] if c in range_df.columns]
        st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
