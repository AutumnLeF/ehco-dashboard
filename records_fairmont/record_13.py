from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

WASH_MIN_TEMP = 55.0   # Wash Cycle >= 55°C
RINSE_MIN_TEMP = 82.0  # Final Rinse Cycle >= 82°C
RECORD_13_FORM_ID = 23715

# Master catalog with all housekeeping units clubbed under "Housekeeping"
LOCATION_CATALOG = {
    "Banquet Support Kitchen": [
        {"Unit_ID": "BQT/SK/DW/03", "Type": "Dishwasher"},
        {"Unit_ID": "BQT/SK/DW/04", "Type": "Dishwasher"},
    ],
    "IRD": [
        {"Unit_ID": "IRD/DW/09", "Type": "Dishwasher"},
        {"Unit_ID": "IRD/DW/10", "Type": "Dishwasher"},
    ],
    "The Merchants": [
        {"Unit_ID": "TM/DW/05", "Type": "Dishwasher"},
        {"Unit_ID": "TM/DW/06", "Type": "Dishwasher"},
        {"Unit_ID": "FM/TM/GW/06", "Type": "Glasswasher"},
        {"Unit_ID": "FM/TM/GW/07", "Type": "Glasswasher"},
    ],
    "Main Kitchen": [
        {"Unit_ID": "MK/PW/02", "Type": "Dishwasher"},
    ],
    "Gold Lounge Pantry": [
        {"Unit_ID": "GLP/DW/07", "Type": "Dishwasher"},
        {"Unit_ID": "FM/GL/GW/09", "Type": "Glasswasher"},
    ],
    "Cafeteria": [
        {"Unit_ID": "CK/DW/01", "Type": "Dishwasher"},
        {"Unit_ID": "FM/CK/GW/01", "Type": "Glasswasher"},
    ],
    "Vantaj Roof Top": [
        {"Unit_ID": "VRT/DW/08", "Type": "Dishwasher"},
        {"Unit_ID": "VRT/GW/11", "Type": "Glasswasher"},
        {"Unit_ID": "VRT/GW/12", "Type": "Glasswasher"},
    ],
    "The Hedonist Kitchen Pantry": [
        {"Unit_ID": "FM/THB/KIT/GW/03", "Type": "Glasswasher"},
    ],
    "The Hedonist Undercounter": [
        {"Unit_ID": "FM/THB/GW/02", "Type": "Glasswasher"},
    ],
    "Madeleine De Proust Pantry": [
        {"Unit_ID": "FM/MDP/GW/04", "Type": "Glasswasher"},
        {"Unit_ID": "FM/MDP/GW/05", "Type": "Glasswasher"},
    ],
    "EON Banquet": [
        {"Unit_ID": "FM/EON/BQT/GW/21", "Type": "Glasswasher"},
    ],
    "Samaa - Pool Bar": [
        {"Unit_ID": "FM/SPB/GW/10", "Type": "Glasswasher"},
    ],
    "Oryn Bar": [
        {"Unit_ID": "FM/OB/GW/08", "Type": "Glasswasher"},
    ],
    "Housekeeping": [
        {"Unit_ID": "FMHKPGW13", "Type": "Glasswasher"},
        {"Unit_ID": "FMHKPGW14", "Type": "Glasswasher"},
        {"Unit_ID": "FMHKPGW15", "Type": "Glasswasher"},
        {"Unit_ID": "FMHKPGW16", "Type": "Glasswasher"},
        {"Unit_ID": "FMHKPGW17", "Type": "Glasswasher"},
        {"Unit_ID": "FMHKPGW18", "Type": "Glasswasher"},
        {"Unit_ID": "FMHKPGW19", "Type": "Glasswasher"},
        {"Unit_ID": "FMHKPGW20", "Type": "Glasswasher"},
    ],
}


def clean_unit_str(val):
  if not val or pd.isna(val):
    return ""
  return str(val).replace("/", "").replace("_", "").replace(" ", "").strip().upper()


def parse_record_13_submissions(raw_df):
  """Robustly parses Record 13 dishwasher/glasswasher submissions from OneBlink nested payloads."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_13_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  flat_master = []
  for loc, units in LOCATION_CATALOG.items():
    for u in units:
      flat_master.append({"Location": loc, "Unit_ID": u["Unit_ID"], "Type": u["Type"]})

  rows = []
  for _, record in df.iterrows():
    rec = record.get("raw_record") if "raw_record" in df.columns else record.to_dict()
    if not isinstance(rec, dict):
      rec = record.to_dict()

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
    entry_parent = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else sub

    raw_loc = str(
        sub.get("Location")
        or rec.get("Location")
        or entry_parent.get("Location")
        or "Main Kitchen"
    ).strip()

    # Club all housekeeping locations under "Housekeeping"
    if "house keeping" in raw_loc.lower() or "housekeeping" in raw_loc.lower():
      location = "Housekeeping"
    else:
      location = raw_loc

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
      if parsed_dt.tzinfo is None:
        parsed_dt_ist = parsed_dt + timedelta(hours=5, minutes=30)
      else:
        parsed_dt_ist = parsed_dt.tz_convert("Asia/Kolkata")
      date_str = parsed_dt_ist.strftime("%d/%m/%Y")
      date_obj = parsed_dt_ist.date()
    else:
      date_str = str(raw_date)[:10]
      date_obj = None

    raw_time = sub.get("Time") or entry_parent.get("Time") or ""
    time_str = str(raw_time).strip()[:8]

    entries = (
        sub.get("set")
        or sub.get("Entry")
        or rec.get("set")
        or rec.get("Entry")
        or []
    )

    if isinstance(entries, dict):
      entries = [entries]
    elif not isinstance(entries, list):
      entries = [sub] if isinstance(sub, dict) else []

    for e in entries:
      if not isinstance(e, dict):
        continue

      machine_type = e.get("Type") or e.get("Dishwasher, Glasswasher") or "Machine"
      raw_unit = (
          e.get("unit_dish")
          or e.get("unit_glass")
          or e.get("unit_id")
          or e.get("Unit ID Dishwasher")
          or e.get("Unit ID Glasswasher")
          or ""
      )

      clean_raw = clean_unit_str(raw_unit)
      matched_master_id = None
      matched_loc = location

      for m in flat_master:
        if clean_raw == clean_unit_str(m["Unit_ID"]):
          matched_master_id = m["Unit_ID"]
          matched_loc = m["Location"]
          break

      final_unit_id = matched_master_id if matched_master_id else (raw_unit or "Unspecified Unit")

      in_use_raw = str(e.get("USE") or e.get("In Use / Not In Use") or "IN USE").strip().upper()
      is_in_use = "NOT" not in in_use_raw

      wash_raw = e.get("washtemp") or e.get("Wash Cycle Temperature °C") or e.get("wash_temp")
      wash_temp = pd.to_numeric(str(wash_raw).replace("°C", "").replace("°", "").strip(), errors="coerce")

      rinse_raw = e.get("finalTemp") or e.get("Final Rinse Cycle Temperature °C") or e.get("rinse_temp")
      rinse_temp = pd.to_numeric(str(rinse_raw).replace("°C", "").replace("°", "").strip(), errors="coerce")

      wash_breach = False
      rinse_breach = False
      if is_in_use:
        if pd.notna(wash_temp) and wash_temp < WASH_MIN_TEMP:
          wash_breach = True
        if pd.notna(rinse_temp) and rinse_temp < RINSE_MIN_TEMP:
          rinse_breach = True

      rows.append({
          "Date_Str": date_str,
          "Date_Obj": date_obj,
          "Time": time_str,
          "Location": matched_loc,
          "Machine_Type": str(machine_type),
          "Unit_ID": final_unit_id,
          "Clean_Unit": clean_unit_str(final_unit_id),
          "In_Use": is_in_use,
          "Status_Text": in_use_raw,
          "Wash_Temp": wash_temp,
          "Rinse_Temp": rinse_temp,
          "Wash_Breach": wash_breach,
          "Rinse_Breach": rinse_breach,
          "Has_Breach": (wash_breach or rinse_breach),
          "Sign": str(sign).strip(),
      })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Unit_ID", "Wash_Temp", "Rinse_Temp"], keep="first")
  return df_out


def render_record_13_view(raw_df, selected_day_str, start_date, end_date):
  df_items = parse_record_13_submissions(raw_df)

  with st.expander("🔍 Record 13 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed warewash records: **{len(df_items)}**")
    if not df_items.empty and "Date_Obj" in df_items.columns:
      date_counts = df_items["Date_Obj"].dropna().value_counts().sort_index(ascending=False).to_dict()
      st.write("Records per date found:", {str(k): v for k, v in date_counts.items()})

  if not df_items.empty and "Date_Obj" in df_items.columns:
    range_df = df_items[
        (df_items["Date_Obj"] >= start_date)
        & (df_items["Date_Obj"] <= end_date)
    ]
  else:
    range_df = df_items.copy()

  tab_day, tab_matrix = st.tabs([
      f"📅 Daily Warewash Audit ({selected_day_str})",
      "📈 Weekly Cleaning & Temp Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions_count = 0
    compliant_count = 0
    pending_count = 0

    location_parsed_data = {}

    for loc_name, units in LOCATION_CATALOG.items():
      loc_day_df = day_df[day_df["Location"].str.lower() == loc_name.lower()] if not day_df.empty else pd.DataFrame()
      loc_pending = []
      loc_compliant = []

      for u in units:
        u_id = u["Unit_ID"]
        u_type = u["Type"]
        u_token = clean_unit_str(u_id)
        
        u_logs = pd.DataFrame()
        if not loc_day_df.empty and "Clean_Unit" in loc_day_df.columns:
          u_logs = loc_day_df[loc_day_df["Clean_Unit"] == u_token]

        if u_logs.empty:
          pending_count += 1
          loc_pending.append({"Unit_ID": u_id, "Type": u_type})
        else:
          latest = u_logs.iloc[-1]
          if latest["Has_Breach"]:
            excursions_count += 1
          else:
            compliant_count += 1
          loc_compliant.append({"Unit_ID": u_id, "Type": u_type, "Log": latest})

      location_parsed_data[loc_name] = {
          "Pending": loc_pending,
          "Compliant": loc_compliant
      }

    k1, k2, k3, k4 = st.columns(4)
    with k1:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #dc2626;"><div class="kpi-num" style="color:#dc2626;">{excursions_count}</div><div class="kpi-lbl">Sanitization Breaches</div></div>', unsafe_allow_html=True)
    with k2:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #16a34a;"><div class="kpi-num" style="color:#16a34a;">{compliant_count}</div><div class="kpi-lbl">Verified Compliant</div></div>', unsafe_allow_html=True)
    with k3:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #d97706;"><div class="kpi-num" style="color:#d97706;">{pending_count}</div><div class="kpi-lbl">Pending / Unlogged Units</div></div>', unsafe_allow_html=True)
    with k4:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #0f172a;"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Audited</div></div>', unsafe_allow_html=True)

    st.write("")
    st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>🏢 Location-wise Unit Audit Summary ({selected_day_str})</h4>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    with col_left:
      st.markdown('<div style="background:#fffbeb; border:1px solid #fde68a; border-left:5px solid #d97706; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#b45309; font-size:0.98rem;">⏳ Pending Units by Area</b></div>', unsafe_allow_html=True)
      
      has_pending = False
      for loc_name, data in location_parsed_data.items():
        p_units = data["Pending"]
        if p_units:
          has_pending = True
          units_html = ""
          for p in p_units:
            units_html += f'<div style="background:#f8fafc; border-left:3px solid #d97706; padding:6px 10px; border-radius:4px; margin-bottom:6px;"><div style="font-size:0.82rem; color:#0f172a; font-weight:700;">⚙️ {p["Unit_ID"]} <span style="font-weight:normal; color:#64748b; font-size:0.72rem;">({p["Type"]})</span><span style="color:#d97706; font-weight:700; float:right;">Pending</span></div><div style="font-size:0.7rem; color:#b45309; margin-top:2px;">Mandatory daily log missing</div></div>'
          
          st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #0f172a; border-radius:6px; padding:10px 14px; margin-bottom:12px;"><div style="font-weight:700; font-size:0.9rem; color:#0f172a; margin-bottom:8px;">📍 {loc_name} <span style="font-size:0.7rem; color:#b45309;">({len(p_units)} pending)</span></div>{units_html}</div>', unsafe_allow_html=True)
      
      if not has_pending:
        st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:12px; border-radius:6px; color:#16a34a; font-size:0.85rem; text-align:center;">All units across all areas have been logged for today!</div>', unsafe_allow_html=True)

    with col_right:
      st.markdown('<div style="background:#f0fdf4; border:1px solid #bbf7d0; border-left:5px solid #16a34a; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#15803d; font-size:0.98rem;">🟢 Logged & Audited Units</b></div>', unsafe_allow_html=True)
      
      has_compliant = False
      for loc_name, data in location_parsed_data.items():
        c_units = data["Compliant"]
        if c_units:
          has_compliant = True
          units_html = ""
          for c in c_units:
            log = c["Log"]
            w_val = f"{int(log['Wash_Temp'])}°C" if pd.notna(log['Wash_Temp']) else "—"
            r_val = f"{int(log['Rinse_Temp'])}°C" if pd.notna(log['Rinse_Temp']) else "—"
            badge_col = "#dc2626" if log["Has_Breach"] else "#16a34a"
            badge_lbl = "Breach" if log["Has_Breach"] else "Compliant"
            units_html += f'<div style="background:#f8fafc; border-left:3px solid {badge_col}; padding:6px 10px; border-radius:4px; margin-bottom:6px;"><div style="font-size:0.82rem; color:#0f172a; font-weight:700;">⚙️ {c["Unit_ID"]} <span style="font-weight:normal; color:#64748b; font-size:0.72rem;">({c["Type"]})</span><span style="color:{badge_col}; font-weight:700; float:right;">{badge_lbl}</span></div><div style="font-size:0.72rem; color:#334155; margin-top:2px;">Wash: {w_val} | Rinse: {r_val} | Sign: {log["Sign"]}</div></div>'
          
          st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #0f172a; border-radius:6px; padding:10px 14px; margin-bottom:12px;"><div style="font-weight:700; font-size:0.9rem; color:#0f172a; margin-bottom:8px;">📍 {loc_name} <span style="font-size:0.7rem; color:#15803d;">({len(c_units)} logged)</span></div>{units_html}</div>', unsafe_allow_html=True)
      
      if not has_compliant:
        st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:12px; border-radius:6px; color:#64748b; font-size:0.85rem; text-align:center;">No unit logs recorded for today.</div>', unsafe_allow_html=True)

  with tab_matrix:
    st.subheader("Weekly Kitchen-Wise Warewash Matrix")
    st.caption("Dishwashers and glasswashers grouped by kitchen area across the 7-day view.")

    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec13_page" not in st.session_state:
      st.session_state.rec13_page = max(0, (total_days - 1) // 7)

    max_page = max(0, (total_days - 1) // 7)

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
      if st.button("⬅️ Previous 7 Days", key="r13_prev", disabled=(st.session_state.rec13_page <= 0), use_container_width=True):
        st.session_state.rec13_page -= 1
        st.rerun()

    with nav3:
      if st.button("Next 7 Days ➡️", key="r13_next", disabled=(st.session_state.rec13_page >= max_page), use_container_width=True):
        st.session_state.rec13_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec13_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with nav2:
      if page_dates:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
            f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec13_page + 1} of {max_page + 1})"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.write("")

    filter_options = ["All Kitchen Areas"] + list(LOCATION_CATALOG.keys())
    selected_location_filter = st.selectbox("📍 Filter Kitchen Area:", options=filter_options, key="r13_matrix_filter")

    locations_to_show = (
        list(LOCATION_CATALOG.keys())
        if selected_location_filter == "All Kitchen Areas"
        else [selected_location_filter]
    )

    for location in locations_to_show:
      units = LOCATION_CATALOG[location]
      loc_df = (
          range_df[range_df["Location"].str.lower() == location.lower()]
          if not range_df.empty
          else pd.DataFrame()
      )

      st.markdown(f"""
          <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 10px 16px; border-radius: 8px; font-weight: 700; font-size: 0.98rem; margin-top: 1.5rem; margin-bottom: 0.8rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
              📍 {location}
          </div>
      """, unsafe_allow_html=True)

      cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])
      cols[0].markdown('<div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.8rem; padding:8px 4px; border-radius:6px; text-align:center;">Unit & Machine</div>', unsafe_allow_html=True)

      for i, d in enumerate(page_dates):
        cols[i + 1].markdown(f'<div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.78rem; padding:8px 2px; border-radius:6px; text-align:center;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

      st.write("")

      for u in units:
        unit = u["Unit_ID"]
        m_type = u["Type"]
        u_token = clean_unit_str(unit)

        row_cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])
        row_cols[0].markdown(f'<div style="background:#ffffff; border:1.5px solid #cbd5e1; border-radius:8px; padding:8px 6px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); min-height:85px; display:flex; flex-direction:column; align-items:center; justify-content:center;"><div style="font-weight:700; color:#0f172a; font-size:0.78rem;">{unit}</div><div style="font-size:0.68rem; color:#64748b; margin-top:2px;">{m_type}</div></div>', unsafe_allow_html=True)

        u_df_unit = loc_df[loc_df["Clean_Unit"] == u_token] if not loc_df.empty else pd.DataFrame()

        for i, d in enumerate(page_dates):
          d_str = d.strftime("%d/%m/%Y")
          matches = pd.DataFrame()
          if not u_df_unit.empty:
            if "Date_Obj" in u_df_unit.columns:
              matches = u_df_unit[u_df_unit["Date_Obj"] == d]
            if matches.empty and "Date_Str" in u_df_unit.columns:
              matches = u_df_unit[u_df_unit["Date_Str"] == d_str]

          if matches.empty:
            row_cols[i + 1].markdown(f'<div style="background:#fef2f2; border:1.5px dashed #dc2626; border-radius:8px; padding:6px; text-align:center; min-height:85px; display:flex; flex-direction:column; justify-content:center; align-items:center;"><span style="color:#dc2626; font-weight:800; font-size:0.72rem;">⏳ PENDING</span><span style="font-size:0.60rem; color:#b91c1c; margin-top:2px;">No log today</span></div>', unsafe_allow_html=True)
          else:
            latest = matches.iloc[-1]
            w_val = f"{int(latest['Wash_Temp'])}°" if pd.notna(latest['Wash_Temp']) else "—"
            r_val = f"{int(latest['Rinse_Temp'])}°" if pd.notna(latest['Rinse_Temp']) else "—"

            if not latest["In_Use"]:
              status_badge = '<span style="color:#64748b; font-weight:700; font-size:0.75rem;">STANDBY</span>'
              temp_detail = 'Not In Use'
              card_bg = "#f8fafc"
              card_border = "1.5px solid #94a3b8"
            elif latest["Has_Breach"]:
              status_badge = '<span style="color:#dc2626; font-weight:800; font-size:0.78rem;">🔴 BREACH</span>'
              temp_detail = f"W: {w_val} | R: {r_val}"
              card_bg = "#fef2f2"
              card_border = "1.5px solid #dc2626"
            else:
              status_badge = '<span style="color:#16a34a; font-weight:800; font-size:0.78rem;">✓ PASS</span>'
              temp_detail = f"W: {w_val} | R: {r_val}"
              card_bg = "#f0fdf4"
              card_border = "1.5px solid #16a34a"

            row_cols[i + 1].markdown(f'<div style="background:{card_bg}; border:{card_border}; border-radius:8px; padding:6px 2px; text-align:center; min-height:85px; box-shadow:0 1px 3px rgba(0,0,0,0.05);"><div>{status_badge}</div><div style="font-size:0.72rem; font-weight:700; color:#0f172a; margin-top:3px;">{temp_detail}</div><div style="font-size:0.62rem; color:#64748b; margin-top:2px;">{latest["Sign"]}</div></div>', unsafe_allow_html=True)

        st.write("")

    st.divider()
    with st.expander("📋 View All Individual Sanitization Records"):
      if not range_df.empty:
        show_cols = [c for c in [
            "Date_Str", "Time", "Location", "Machine_Type", "Unit_ID", "Status_Text", "Wash_Temp", "Rinse_Temp", "Sign"
        ] if c in range_df.columns]
        st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
