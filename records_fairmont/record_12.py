from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_12_FORM_ID = 23714
CRITICAL_LIMIT_DEFROST = 5.0  # Max final temp: <= 5.0°C
RECORD_12_AREAS = ["Butchery", "Main Kitchen"]


def parse_record_12_submissions(raw_df):
  """Parses Record 12 Defrosting Temperature submissions."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_12_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  rows = []
  for _, record in df.iterrows():
    rec = record.get("raw_record") if "raw_record" in df.columns else record.to_dict()
    if not isinstance(rec, dict):
      rec = record.to_dict()

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
    entry_parent = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else sub

    loc_main = (
        sub.get("Location_other_copy")
        or sub.get("Location (Other)")
        or sub.get("Location")
        or rec.get("Location")
        or entry_parent.get("Location")
        or "Butchery"
    )
    if str(loc_main).strip().lower() in ["other", ""] and (
        sub.get("Location_other_copy") or sub.get("Location (Other)")
    ):
      loc_main = str(
          sub.get("Location_other_copy") or sub.get("Location (Other)")
      ).strip()

    food_main = (
        sub.get("Name of food (Other)")
        or sub.get("Food")
        or sub.get("Name of Food")
        or entry_parent.get("Food")
        or "Defrosted Item"
    )
    if str(food_main).strip().lower() in ["other", ""] and sub.get(
        "Name of food (Other)"
    ):
      food_main = str(sub.get("Name of food (Other)")).strip()

    finish_raw = (
        sub.get("End_Date")
        or sub.get("Finish Date")
        or sub.get("EndDate")
        or sub.get("Date")
        or rec.get("createdAt")
        or rec.get("dateTimeSubmitted")
        or ""
    )
    finish_dt = pd.to_datetime(finish_raw, errors="coerce")
    if pd.isna(finish_dt):
      finish_dt = pd.to_datetime(finish_raw, dayfirst=True, errors="coerce")

    if pd.notna(finish_dt):
      if finish_dt.tzinfo is None:
        finish_dt_ist = finish_dt + timedelta(hours=5, minutes=30)
      else:
        finish_dt_ist = finish_dt.tz_convert("Asia/Kolkata")
      finish_str = finish_dt_ist.strftime("%d/%m/%Y")
      finish_date_obj = finish_dt_ist.date()
    else:
      finish_str = str(finish_raw)[:10]
      finish_date_obj = None

    start_raw = sub.get("Start_Date") or sub.get("Start Date") or sub.get("StartDate") or ""
    start_dt = pd.to_datetime(start_raw, errors="coerce")
    if pd.isna(start_dt):
      start_dt = pd.to_datetime(start_raw, dayfirst=True, errors="coerce")

    if pd.notna(start_dt):
      if start_dt.tzinfo is None:
        start_dt_ist = start_dt + timedelta(hours=5, minutes=30)
      else:
        start_dt_ist = start_dt.tz_convert("Asia/Kolkata")
      start_str = start_dt_ist.strftime("%d/%m/%Y")
      start_date_obj = start_dt_ist.date()
    else:
      start_str = str(start_raw)[:10]
      start_date_obj = None

    date_rule_valid = True
    duration_note = "Valid (24h)"
    if start_date_obj and finish_date_obj:
      days_diff = (finish_date_obj - start_date_obj).days
      if days_diff != 1:
        date_rule_valid = False
        duration_note = f"Anomaly: {days_diff}d diff (Expected 1d)"

    start_time_raw = str(sub.get("Start_Time") or sub.get("Start Time") or sub.get("StartTime") or "")
    if "T" in start_time_raw:
      try:
        start_time_str = start_time_raw.split("T")[1][:5]
      except Exception:
        start_time_str = start_time_raw[:8]
    else:
      start_time_str = start_time_raw[:8]

    finish_time_raw = str(sub.get("End_Time") or sub.get("Finish Time") or sub.get("FinishTime") or sub.get("Time") or "")
    if "T" in finish_time_raw:
      try:
        finish_time_str = finish_time_raw.split("T")[1][:5]
      except Exception:
        finish_time_str = finish_time_raw[:8]
    else:
      finish_time_str = finish_time_raw[:8]

    start_temp_raw = sub.get("Start_Temp") or sub.get("Start Temperature °C") or sub.get("Start_Temperature")
    start_temp = pd.to_numeric(
        str(start_temp_raw).replace("°C", "").strip(), errors="coerce"
    )

    final_temp_raw = (
        sub.get("Final_Temperature")
        or sub.get("Final Defrosting Temperature °C")
        or sub.get("Final Defrosting Temperature")
        or sub.get("Final Temperature °C")
        or sub.get("Temperature")
    )
    final_temp = pd.to_numeric(
        str(final_temp_raw).replace("°C", "").strip(), errors="coerce"
    )

    sign = (
        sub.get("Sign")
        or sub.get("Sign (Full Name)")
        or sub.get("sign")
        or rec.get("Sign")
        or rec.get("user.email")
        or "Staff"
    )

    rows.append({
        "Date_Str": finish_str,
        "Date_Obj": finish_date_obj,
        "Start_Date_Str": start_str,
        "Start_Date_Obj": start_date_obj,
        "Date_Rule_Valid": date_rule_valid,
        "Duration_Note": duration_note,
        "Start_Time": start_time_str,
        "Finish_Time": finish_time_str,
        "Location": str(loc_main).strip(),
        "Food": str(food_main).strip(),
        "Start_Temp": start_temp,
        "Final_Temp": final_temp,
        "Sign": str(sign).strip(),
    })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(
        subset=[
            "Date_Str",
            "Finish_Time",
            "Location",
            "Food",
            "Final_Temp",
        ],
        keep="first",
    )
  return df_out


def render_record_12_view(raw_df, selected_day_str, start_date, end_date):
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

  df_items = parse_record_12_submissions(raw_df)

  with st.expander("🔍 Record 12 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed defrost records: **{len(df_items)}**")
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
      f"📅 Daily Defrost Audit ({selected_day_str})",
      "📈 7-Day Completion Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions = 0
    date_anomalies = 0

    active_areas = list(RECORD_12_AREAS)
    if not day_df.empty:
      for loc in day_df["Location"].unique():
        if loc not in active_areas:
          active_areas.append(loc)

    pending_cards = []
    completed_cards = []

    for area in active_areas:
      a_df = (
          day_df[day_df["Location"].str.strip().str.lower() == area.lower()]
          if not day_df.empty
          else pd.DataFrame()
      )
      if a_df.empty:
        pending_cards.append({"Area": area})
      else:
        batches = []
        sign = a_df["Sign"].iloc[0] if not a_df.empty else "Staff"
        for _, r in a_df.iterrows():
          if pd.notna(r["Final_Temp"]) and r["Final_Temp"] > CRITICAL_LIMIT_DEFROST:
            excursions += 1
          if not r["Date_Rule_Valid"]:
            date_anomalies += 1
          batches.append({
              "Food": r["Food"],
              "Start_Temp": r["Start_Temp"],
              "Final_Temp": r["Final_Temp"],
              "Start_Time": r["Start_Time"],
              "Finish_Time": r["Finish_Time"],
              "Start_Date": r["Start_Date_Str"],
              "Duration": r["Duration_Note"],
              "Excursion": pd.notna(r["Final_Temp"])
              and r["Final_Temp"] > CRITICAL_LIMIT_DEFROST,
          })
        completed_cards.append({"Area": area, "Batches": batches, "Sign": sign})

    total_finished = len(day_df)

    # KPI Dashboard
    k1, k2, k3, k4 = st.columns(4)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #dc2626;">
                <div class="kpi-num" style="color:#dc2626;">{excursions}</div>
                <div class="kpi-lbl">Temp Breaches (&gt; 5.0°C)</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #d97706;">
                <div class="kpi-num" style="color:#d97706;">{date_anomalies}</div>
                <div class="kpi-lbl">Date Anomalies</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{len(completed_cards)}/{len(active_areas)}</div>
                <div class="kpi-lbl">Completed Areas</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k4:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0f172a;">
                <div class="kpi-num" style="color:#0f172a;">{total_finished}</div>
                <div class="kpi-lbl">Total Items Defrosted</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")

    # --- SECTION 1: PENDING AREAS (TOP) ---
    st.markdown(
        "<h4 style='color:#b45309; margin-top:1.5rem; margin-bottom:1rem;'>⏳"
        f" Pending / Incomplete Kitchen Areas ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not pending_cards:
      st.success(
          "🎉 All kitchen areas have submitted mandatory defrosting records!"
      )
    else:
      p_cols = st.columns(3, gap="small")
      for idx, p_info in enumerate(pending_cards):
        col_target = p_cols[idx % 3]
        card_html = textwrap.dedent(f"""
                <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #d97706; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size:0.9rem; font-weight:700; color:#0f172a; padding-bottom:6px; border-bottom:1px solid #e2e8f0;">
                        📍 {p_info["Area"]}
                    </div>
                    <div style="font-size:0.75rem; color:#b45309; margin-top:8px; font-style:italic;">
                        ⏳ Mandatory minimum 1 defrost item missing for today.
                    </div>
                </div>
            """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

    st.write("")

    # --- SECTION 2: COMPLETED AREAS (BOTTOM) ---
    st.markdown(
        "<h4 style='color:#16a34a; margin-top:2rem; margin-bottom:1rem;'>✅"
        f" Completed Defrost Audit Entries ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not completed_cards:
      st.info("No completed defrost entries for this date.")
    else:
      c_cols = st.columns(3, gap="small")
      for idx, c_info in enumerate(completed_cards):
        col_target = c_cols[idx % 3]
        area_name = c_info["Area"]
        batches = c_info["Batches"]
        sign = c_info["Sign"]

        batches_html = ""
        for b in batches:
          start_t = f"{b['Start_Temp']}°C" if pd.notna(b["Start_Temp"]) else "—"
          final_t = f"{b['Final_Temp']}°C" if pd.notna(b["Final_Temp"]) else "—"
          temp_color = "#dc2626" if b["Excursion"] else "#16a34a"
          batches_html += textwrap.dedent(f"""
                <div style="background:#f8fafc; border-left:3px solid {temp_color}; border-radius:4px; padding:6px 8px; margin-top:6px; font-size:0.76rem;">
                    <div style="font-weight:700; color:#0f172a;">🧊 {b["Food"]}</div>
                    <div style="color:#475569; margin-top:2px;">Init: <b>{start_t}</b> ({b['Start_Time']}) ➔ Fin: <b style="color:{temp_color};">{final_t}</b> ({b['Finish_Time']})</div>
                    <div style="color:#0284c7; font-size:0.68rem; margin-top:2px;">Start Date: {b['Start_Date']} | Note: {b['Duration']}</div>
                </div>
            """).strip()

        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #16a34a; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
                    <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {area_name}</span>
                    <span style="color:#16a34a; font-weight:700; font-size:0.75rem;">✓ Done ({len(batches)})</span>
                </div>
                <div style="margin-top:6px;">
                    {batches_html}
                </div>
                <div style="font-size:0.68rem; color:#64748b; margin-top:8px; border-top:1px solid #f1f5f9; padding-top:4px;">
                    Signed by: {sign}
                </div>
            </div>
        """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

  # --- TAB 2: 7-DAY MATRIX ---
  with tab_matrix:
    st.subheader("7-Day Defrosting Completion Matrix")

    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec12_page" not in st.session_state:
      st.session_state.rec12_page = max(0, (total_days - 1) // 7)

    max_page = max(0, (total_days - 1) // 7)

    col_prev, col_status, col_next = st.columns([1, 3, 1])
    with col_prev:
      if st.button(
          "⬅️ Previous 7 Days",
          key="r12_prev",
          disabled=(st.session_state.rec12_page <= 0),
          use_container_width=True,
      ):
        st.session_state.rec12_page -= 1
        st.rerun()

    with col_next:
      if st.button(
          "Next 7 Days ➡️",
          key="r12_next",
          disabled=(st.session_state.rec12_page >= max_page),
          use_container_width=True,
      ):
        st.session_state.rec12_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec12_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with col_status:
      if page_dates:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#0f172a;"
            f" font-size:0.95rem; padding-top:6px;'>Showing:"
            f" {page_dates[0].strftime('%d/%m/%Y')} to"
            f" {page_dates[-1].strftime('%d/%m/%Y')} (Block"
            f" {st.session_state.rec12_page + 1} of {max_page + 1})</div>",
            unsafe_allow_html=True,
        )

    st.write("")

    cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
    cols[0].markdown(
        '<div style="background:#0f172a; color:#ffffff; font-weight:700;'
        ' font-size:0.85rem; padding:10px 4px; border-radius:6px;'
        ' text-align:center;">Kitchen Area</div>',
        unsafe_allow_html=True,
    )
    for i, d in enumerate(page_dates):
      cols[i + 1].markdown(
          f'<div style="background:#1e293b; color:#ffffff; font-weight:700;'
          f' font-size:0.8rem; padding:10px 2px; border-radius:6px;'
          f' text-align:center;">{d.strftime("%d/%m (%a)")}</div>',
          unsafe_allow_html=True,
      )

    st.write("")

    all_kitchens = (
        sorted(list(range_df["Location"].unique()))
        if not range_df.empty and "Location" in range_df.columns
        else RECORD_12_AREAS
    )

    for kitchen in all_kitchens:
      row_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
      row_cols[0].markdown(
          f'<div style="background:#ffffff; border:1.5px solid #94a3b8;'
          f' border-radius:8px; padding:12px 6px; font-weight:700;'
          f' color:#0f172a; font-size:0.88rem; text-align:center;'
          ' box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:130px;'
          ' display:flex; align-items:center;'
          f' justify-content:center;">{kitchen}</div>',
          unsafe_allow_html=True,
      )

      k_df = (
          range_df[range_df["Location"] == kitchen]
          if not range_df.empty
          else pd.DataFrame()
      )

      for i, d in enumerate(page_dates):
        d_str = d.strftime("%d/%m/%Y")
        matches = (
            k_df[k_df["Date_Str"] == d_str]
            if not k_df.empty
            else pd.DataFrame()
        )

        if matches.empty:
          row_cols[i + 1].markdown(
              '<div style="background:#ffffff; border:1px dashed #cbd5e1;'
              ' border-radius:8px; padding:8px; text-align:center;'
              ' min-height:130px; display:flex; align-items:center;'
              ' justify-content:center;"><span style="color:#94a3b8;'
              ' font-weight:700; font-size:1.2rem;">—</span></div>',
              unsafe_allow_html=True,
          )
        else:
          count = len(matches)
          items_html = ""
          for _, dish in matches.iterrows():
            start_t = (
                f"{dish['Start_Temp']}°C"
                if pd.notna(dish["Start_Temp"])
                else "—"
            )
            final_t = (
                f"{dish['Final_Temp']}°C"
                if pd.notna(dish["Final_Temp"])
                else "—"
            )
            items_preview_name = (
                dish["Food"][:14] + "..."
                if len(str(dish["Food"])) > 14
                else dish["Food"]
            )
            items_html += (
                "<div style='font-size:0.65rem; color:#334155; margin-top:2px;"
                " text-align:left; border-top:1px solid #f1f5f9;"
                f" padding-top:2px;'><b>{items_preview_name}</b><br/><span"
                f" style='color:#0284c7;'>Init: {start_t} ({dish['Start_Time']})<br/>Fin: {final_t} ({dish['Finish_Time']})</span></div>"
            )

          row_cols[i + 1].markdown(
              f'<div style="background:#ffffff; border:1.5px solid #0f172a;'
              ' border-radius:8px; padding:6px 6px; min-height:130px;'
              ' box-shadow:0 1px 3px rgba(0,0,0,0.08);"><div'
              ' style="font-size:1.1rem; font-weight:800; color:#0f172a;'
              f' text-align:center; line-height:1;">{count}</div>{items_html}</div>',
              unsafe_allow_html=True,
          )

      st.write("")

    st.divider()
    with st.expander("📋 View All Individual Defrosting Records"):
      if not range_df.empty:
        show_cols = [
            c
            for c in [
                "Date_Str",
                "Start_Date_Str",
                "Start_Time",
                "Finish_Time",
                "Location",
                "Food",
                "Start_Temp",
                "Final_Temp",
                "Duration_Note",
                "Sign",
            ]
            if c in range_df.columns
        ]
        st.dataframe(
            range_df[show_cols], use_container_width=True, hide_index=True
        )
