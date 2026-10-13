from datetime import datetime, timedelta, timezone
import textwrap
import pandas as pd
import streamlit as st

RECORD_PH01_FORM_ID = 24146

# Master catalog of all required personal hygiene inspection locations
PH01_LOCATIONS = [
    "Banquet Kitchen",
    "Banquet Service",
    "Bakery/Pastry/Halwai",
    "Beyond Oryn",
    "Bombay Café",
    "Commissary",
    "Gold lounge Kitchen",
    "Gold lounge Service",
    "Hedonist Kitchen",
    "Hedonist Bar",
    "IRD",
    "IRD Kitchen",
    "Kitchen Stewarding",
    "Madeline De Proust Kitchen",
    "Madeline De Proust",
    "Main Stores",
    "Merchants kitchen",
    "Merchants Service",
    "Oryn Kitchen",
    "Receiving",
    "Samaa Kitchen",
    "Samaa Bar",
]


def parse_record_ph01_submissions(raw_df):
  """Robustly parses Record PH01 Personal Hygiene submissions."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_PH01_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  rows = []
  for _, record in df.iterrows():
    rec = record.get("raw_record") if "raw_record" in record.to_dict() else record.to_dict()
    if not isinstance(rec, dict):
      rec = record.to_dict()

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec

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

    location = str(sub.get("Location") or rec.get("Location") or "General Area").strip()
    sign_staff = str(sub.get("Sign_initial") or sub.get("Sign") or "Staff").strip()
    sign_incharge = str(sub.get("Sign_initial_-_Outlet_Incharge") or sub.get("Sign_Incharge") or "Incharge").strip()

    entries = sub.get("Entry") or sub.get("set") or []
    if isinstance(entries, dict):
      entries = [entries]
    elif not isinstance(entries, list):
      entries = [sub]

    for entry in entries:
      if not isinstance(entry, dict):
        continue

      staff_name = str(entry.get("Staff_Name") or entry.get("Name") or "Staff Member").strip()

      rows.append({
          "Date_Str": date_str,
          "Date_Obj": date_obj,
          "Location": location,
          "Staff_Name": staff_name,
          "Sign_Staff": sign_staff,
          "Sign_Incharge": sign_incharge,
      })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Location", "Staff_Name"], keep="first")
  return df_out


def render_record_ph01_view(raw_df, selected_day_str, start_date, end_date):
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

  df_items = parse_record_ph01_submissions(raw_df)

  with st.expander("🔍 Record PH01 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed staff hygiene records: **{len(df_items)}**")
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
      f"📅 Daily Personal Hygiene Audit ({selected_day_str})",
      "📈 7-Day History Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    total_inspected = len(day_df)

    completed_cards = []
    pending_locs = []

    for master_loc in PH01_LOCATIONS:
      loc_match = day_df[day_df["Location"].str.strip().str.lower() == master_loc.lower()] if not day_df.empty else pd.DataFrame()
      if not loc_match.empty:
        staff_list = loc_match.to_dict("records")
        checked_by = loc_match["Sign_Staff"].iloc[0] if "Sign_Staff" in loc_match.columns else "Staff"
        incharge = loc_match["Sign_Incharge"].iloc[0] if "Sign_Incharge" in loc_match.columns else "Incharge"
        completed_cards.append({
            "Location": master_loc,
            "Staff_List": staff_list,
            "Checked_By": checked_by,
            "Incharge": incharge,
            "Count": len(staff_list),
        })
      else:
        pending_locs.append(master_loc)

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{total_inspected}</div>
                <div class="kpi-lbl">Staff Inspected Today</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0284c7;">
                <div class="kpi-num" style="color:#0284c7;">{len(completed_cards)}/{len(PH01_LOCATIONS)}</div>
                <div class="kpi-lbl">Locations Checked</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #dc2626;">
                <div class="kpi-num" style="color:#dc2626;">{len(pending_locs)}</div>
                <div class="kpi-lbl">Pending Locations</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")

    # --- SECTION 1: PENDING LOCATIONS ---
    st.markdown(
        "<h4 style='color:#b45309; margin-top:1.5rem; margin-bottom:1rem;'>⏳"
        f" Pending / Unchecked Locations ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not pending_locs:
      st.success("🎉 All locations have submitted personal hygiene inspections!")
    else:
      p_cols = st.columns(3, gap="small")
      for idx, p_loc in enumerate(pending_locs):
        col_target = p_cols[idx % 3]
        col_target.markdown(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #d97706; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {p_loc}</span>
                    <span style="color:#d97706; font-weight:700; font-size:0.72rem;">Pending Audit</span>
                </div>
                <div style="margin-top:6px; font-size:0.75rem; color:#b45309; font-style:italic;">No hygiene inspection logged today.</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("")

    # --- SECTION 2: COMPLETED LOCATIONS ---
    st.markdown(
        "<h4 style='color:#16a34a; margin-top:2rem; margin-bottom:1rem;'>✅"
        f" Inspected Locations ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not completed_cards:
      st.info("No personal hygiene inspections recorded for this date.")
    else:
      cols = st.columns(3, gap="small")
      for idx, card in enumerate(completed_cards):
        col_target = cols[idx % 3]

        staff_items_html = ""
        for s in card["Staff_List"]:
          staff_items_html += f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:5px 8px; margin-top:3px; font-size:0.75rem;">👤 <b>{s["Staff_Name"]}</b></div>'

        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #16a34a; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
                    <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {card["Location"]}</span>
                    <span style="color:#16a34a; font-weight:700; font-size:0.72rem;">{card["Count"]} Staff Checked</span>
                </div>
                <div style="margin-top:6px;">
                    {staff_items_html}
                </div>
                <div style="font-size:0.68rem; color:#64748b; margin-top:8px; border-top:1px solid #f1f5f9; padding-top:4px; display:flex; justify-content:space-between;">
                    <span><b>Checked By:</b> {card["Checked_By"]}</span>
                    <span><b>Incharge:</b> {card["Incharge"]}</span>
                </div>
            </div>
        """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

  with tab_matrix:
    st.subheader("7-Day Personal Hygiene History Matrix")
    st.caption("Overview of personal hygiene audit logs across the selected date window grouped by location.")

    if range_df.empty:
      st.info("No records found for this date range.")
    else:
      total_days = max(1, (end_date - start_date).days + 1)
      matrix_dates = [start_date + timedelta(days=i) for i in range(total_days)]
      current_today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()

      num_dates = len(matrix_dates)
      col_ratios = [1.8] + [1.0] * num_dates
      cols = st.columns(col_ratios)

      cols[0].markdown('<div style="font-weight:700; font-size:0.78rem; color:#475569; padding:6px 4px;">Inspection Location</div>', unsafe_allow_html=True)
      for i, d in enumerate(matrix_dates):
        cols[i + 1].markdown(f'<div style="background:#f1f5f9; font-weight:700; font-size:0.75rem; text-align:center; padding:6px 2px; border-radius:4px; color:#0f172a;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

      st.write("")

      for loc_name in PH01_LOCATIONS:
        row_cols = st.columns(col_ratios)
        row_cols[0].markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:4px; padding:8px 6px; min-height:45px; display:flex; align-items:center;"><b style="font-size:0.78rem; color:#0f172a;">📍 {loc_name}</b></div>', unsafe_allow_html=True)

        for i, d in enumerate(matrix_dates):
          d_str = d.strftime("%d/%m/%Y")
          day_matches = range_df[range_df["Date_Str"] == d_str]
          loc_matches = day_matches[day_matches["Location"].str.strip().str.lower() == loc_name.lower()] if not day_matches.empty else pd.DataFrame()

          is_done = not loc_matches.empty
          staff_count = len(loc_matches)

          is_old = (current_today - d).days > 1
          pending_icon = "❌" if is_old else "⏳"

          if is_done:
            cell_bg = "#f0fdf4"
            cell_border = "#16a34a"
            cell_content = f'<span style="color:#16a34a; font-weight:800; font-size:0.7rem;">✓ Inspected</span><br><span style="font-size:0.6rem; color:#15803d;">({staff_count} Staff)</span>'
          else:
            cell_bg = "#fef2f2"
            cell_border = "#dc2626"
            cell_content = f'<span style="color:#dc2626; font-weight:700; font-size:0.7rem;">{pending_icon} Pending</span>'

          row_cols[i + 1].markdown(
              f'<div style="background:{cell_bg}; border:1.5px solid {cell_border}; border-radius:4px; padding:4px; min-height:45px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center;">'
              f'{cell_content}'
              f'</div>',
              unsafe_allow_html=True
          )

        st.write("")
