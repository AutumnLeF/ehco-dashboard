from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

TARGET_PPM = 100.0      # Chlorine PPM must be 100
TARGET_MINUTES = 5.0    # Contact time must be 5 minutes
RECORD_21_FORM_ID = 23723  # Record 21 Form ID
RECORD_21_AREAS = ["Receiving", "Vegetable preparation area"]


def parse_record_21_submissions(raw_df):
  """Robustly parses Record 21 food wash submissions from OneBlink nested payloads."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_21_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  rows = []
  for _, record in df.iterrows():
    rec = record.get("raw_record") if "raw_record" in record.to_dict() else record.to_dict()
    if not isinstance(rec, dict):
      rec = record.to_dict()

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
    entry_parent = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else sub

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

    time_raw = str(sub.get("Time") or entry_parent.get("Time") or "")
    if "T" in time_raw:
      try:
        dt_time = pd.to_datetime(time_raw, errors="coerce")
        if pd.notna(dt_time):
          dt_time_ist = dt_time + timedelta(hours=5, minutes=30)
          time_str = dt_time_ist.strftime("%H:%M")
        else:
          time_str = time_raw.split("T")[1][:5]
      except:
        time_str = time_raw[:8]
    else:
      time_str = time_raw[:8]

    location = str(sub.get("Location") or rec.get("Location") or "Vegetable preparation area").strip()
    sign = str(sub.get("Sign") or sub.get("sign") or rec.get("Sign") or rec.get("user.email") or "Staff").strip()

    cl_obj = sub.get("CL") or rec.get("CL") or sub.get("set") or rec.get("set") or {}
    cl_items = [cl_obj] if isinstance(cl_obj, dict) else (cl_obj if isinstance(cl_obj, list) else [{}])

    for cl in cl_items:
      if not isinstance(cl, dict):
        continue

      ppm_raw = cl.get("Chemical_ppm_strength") or cl.get("Chemical ppm strength") or cl.get("PPM") or "100"
      ppm_num = pd.to_numeric(str(ppm_raw).replace("ppm", "").strip(), errors="coerce")

      time_r = str(cl.get("Contact_Time_in_Minutes") or cl.get("Contact Time in Minutes") or cl.get("Minutes") or "5")
      time_clean = time_r.lower().replace("minutes", "").replace("minute", "").replace("mins", "").replace("min", "").strip()
      minutes_num = pd.to_numeric(time_clean, errors="coerce")

      ppm_breach = pd.notna(ppm_num) and (ppm_num != TARGET_PPM)
      time_breach = pd.notna(minutes_num) and (minutes_num < TARGET_MINUTES)

      raw_type = cl.get("Type") or cl.get("Food") or cl.get("Type_of_food") or ["Salad Item"]
      
      if isinstance(raw_type, str):
        if "[" in raw_type:
          try:
            import ast
            raw_type = ast.literal_eval(raw_type)
          except:
            raw_type = [raw_type.replace("['", "").replace("']", "").strip()]
        else:
          raw_type = [raw_type.strip()]

      if not isinstance(raw_type, list):
        raw_type = [str(raw_type)]

      other_val = str(cl.get("Type_of_food_Other") or cl.get("Type of food (Other)") or "").replace("•", "").strip()
      if other_val and other_val.lower() not in ["none", "nan", ""]:
        raw_type.append(other_val)

      for food_item in raw_type:
        f_name = str(food_item).strip()
        if f_name and f_name.lower() not in ["none", "nan", "other", ""]:
          rows.append({
              "Date_Str": date_str,
              "Date_Obj": date_obj,
              "Time": time_str,
              "Location": location,
              "Food": f_name,
              "PPM": ppm_num,
              "PPM_Raw": str(ppm_raw),
              "Minutes": minutes_num,
              "Minutes_Raw": f"{time_r}m",
              "PPM_Breach": ppm_breach,
              "Time_Breach": time_breach,
              "Has_Breach": (ppm_breach or time_breach),
              "Sign": sign,
          })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Food", "PPM", "Minutes"], keep="first")
  return df_out


def render_record_21_view(raw_df, selected_day_str, start_date, end_date):
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

  df_items = parse_record_21_submissions(raw_df)

  with st.expander("🔍 Record 21 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed food wash records: **{len(df_items)}**")
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
      f"📅 Daily Food Wash ({selected_day_str})",
      "📈 7-Day Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions = 0
    total_washed = len(day_df)

    active_areas = list(RECORD_21_AREAS)
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
          if r["Has_Breach"]:
            excursions += 1
          batches.append({
              "Food": r["Food"],
              "PPM": r["PPM"],
              "PPM_Raw": r["PPM_Raw"],
              "Minutes": r["Minutes"],
              "Minutes_Raw": r["Minutes_Raw"],
              "Time": r["Time"],
              "PPM_Breach": r["PPM_Breach"],
              "Time_Breach": r["Time_Breach"],
              "Has_Breach": r["Has_Breach"]
          })
        completed_cards.append({"Area": area, "Batches": batches, "Sign": sign})

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #dc2626;">
                <div class="kpi-num" style="color:#dc2626;">{excursions}</div>
                <div class="kpi-lbl">PPM / Time Excursions</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{len(completed_cards)}/{len(active_areas)}</div>
                <div class="kpi-lbl">Completed Wash Areas</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0f172a;">
                <div class="kpi-num" style="color:#0f172a;">{total_washed}</div>
                <div class="kpi-lbl">Total Items Washed</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")

    st.markdown(
        "<h4 style='color:#b45309; margin-top:1.5rem; margin-bottom:1rem;'>⏳"
        f" Pending / Incomplete Kitchen Areas ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not pending_cards:
      st.success("🎉 All preparation areas have submitted chlorine wash records!")
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
                        ⏳ Mandatory minimum 1 wash log missing for today.
                    </div>
                </div>
            """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

    st.write("")

    st.markdown(
        "<h4 style='color:#16a34a; margin-top:2rem; margin-bottom:1rem;'>✅"
        f" Completed Food Wash Entries ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not completed_cards:
      st.info("No completed wash entries for this date.")
    else:
      c_cols = st.columns(3, gap="small")
      for idx, c_info in enumerate(completed_cards):
        col_target = c_cols[idx % 3]
        area_name = c_info["Area"]
        batches = c_info["Batches"]
        sign = c_info["Sign"]

        batches_html = ""
        for b in batches:
          ppm_str = f"{b['PPM']} PPM" if pd.notna(b['PPM']) else "—"
          min_str = b['Minutes_Raw']
          
          if b["Has_Breach"]:
            temp_color = "#dc2626"
            errs = []
            if b["PPM_Breach"]: errs.append("PPM < 100")
            if b["Time_Breach"]: errs.append("Time < 5m")
            status_tag = f"<span style='color:#dc2626; font-weight:700;'>({', '.join(errs)})</span>"
          else:
            temp_color = "#16a34a"
            status_tag = ""

          batches_html += textwrap.dedent(f"""
                <div style="background:#f8fafc; border-left:3px solid {temp_color}; border-radius:4px; padding:6px 8px; margin-top:6px; font-size:0.76rem;">
                    <div style="font-weight:700; color:#0f172a;">🥗 {b["Food"]} {status_tag}</div>
                    <div style="color:#475569; margin-top:2px;">Strength: <b style="color:{temp_color};">{ppm_str}</b> | Contact: <b style="color:{temp_color};">{min_str}</b></div>
                    <div style="color:#64748b; font-size:0.68rem; margin-top:2px;">Time Logged: {b['Time']}</div>
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
                    <b>Filled By:</b> {sign}
                </div>
            </div>
        """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

  with tab_matrix:
    st.subheader("7-Day Food Wash Matrix")

    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec21_page" not in st.session_state:
      st.session_state.rec21_page = max(0, (total_days - 1) // 7)

    max_page = max(0, (total_days - 1) // 7)

    col_prev, col_status, col_next = st.columns([1, 3, 1])
    with col_prev:
      if st.button(
          "⬅️ Previous 7 Days",
          key="r21_prev",
          disabled=(st.session_state.rec21_page <= 0),
          use_container_width=True,
      ):
        st.session_state.rec21_page -= 1
        st.rerun()

    with col_next:
      if st.button(
          "Next 7 Days ➡️",
          key="r21_next",
          disabled=(st.session_state.rec21_page >= max_page),
          use_container_width=True,
      ):
        st.session_state.rec21_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec21_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with col_status:
      if page_dates:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#0f172a;"
            f" font-size:0.95rem; padding-top:6px;'>Showing:"
            f" {page_dates[0].strftime('%d/%m/%Y')} to"
            f" {page_dates[-1].strftime('%d/%m/%Y')} (Block"
            f" {st.session_state.rec21_page + 1} of {max_page + 1})</div>",
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

    all_kitchens = RECORD_21_AREAS

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
          has_breach = any(matches["Has_Breach"])
          badge_color = "#dc2626" if has_breach else "#16a34a"
          
          foods_list = list(dict.fromkeys(matches["Food"].dropna().tolist()))
          sign_list = [s for s in dict.fromkeys(matches["Sign"].dropna().tolist()) if s and s != "Staff"]
          sign_str = f"By: {', '.join(sign_list)}" if sign_list else "By: Staff"

          with row_cols[i + 1]:
            with st.container(border=True):
              st.markdown(f"<div style='font-size:1.0rem; font-weight:800; color:{badge_color}; text-align:center;'>{count} Items</div>", unsafe_allow_html=True)
              st.markdown("<div style='font-size:0.62rem; text-align:center; color:#64748b;'>100 PPM • 5m</div>", unsafe_allow_html=True)
              
              with st.expander("View Items"):
                for f in foods_list:
                  st.markdown(f"<div style='font-size:0.7rem; color:#334155;'>• {f}</div>", unsafe_allow_html=True)
                  
              st.markdown(f"<div style='font-size:0.63rem; color:#475569; text-align:center; margin-top:2px; font-weight:600;'>{sign_str}</div>", unsafe_allow_html=True)

      st.write("")

    st.divider()
    with st.expander("📋 View All Individual Chlorine Food Wash Records"):
      if not range_df.empty:
        show_cols = [
            c
            for c in [
                "Date_Str",
                "Time",
                "Location",
                "Food",
                "PPM",
                "Minutes",
                "Has_Breach",
                "Sign",
            ]
            if c in range_df.columns
        ]
        st.dataframe(
            range_df[show_cols], use_container_width=True, hide_index=True
        )
