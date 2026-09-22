from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

RECORD_12_FORM_ID = 23714
CRITICAL_LIMIT_DEFROST = 5.0  # Max final temp: <= 5.0°C


def find_val(row_dict, keywords):
  """Finds first matching non-null value for loose key names."""
  if not isinstance(row_dict, dict):
    return None
  for k, v in row_dict.items():
    k_clean = k.lower().replace("_", "").replace(" ", "").replace(".", "")
    for kw in keywords:
      kw_clean = kw.lower().replace("_", "").replace(" ", "")
      if kw_clean in k_clean:
        if pd.notna(v) and str(v).strip() != "":
          return v
  return None


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

    # 1. Location (supports standard, other copy, or nested)
    loc_main = (
        sub.get("Location_other_copy")
        or sub.get("Location (Other)")
        or sub.get("Location")
        or rec.get("Location")
        or entry_parent.get("Location")
        or "Main Kitchen"
    )
    if str(loc_main).strip().lower() in ["other", ""] and (
        sub.get("Location_other_copy") or sub.get("Location (Other)")
    ):
      loc_main = str(
          sub.get("Location_other_copy") or sub.get("Location (Other)")
      ).strip()

    # 2. Food Name (supports Name of Food or Other)
    food_main = (
        sub.get("Name of food (Other)")
        or sub.get("Name of Food")
        or sub.get("Food")
        or entry_parent.get("Name of Food")
        or "Defrosted Item"
    )
    if str(food_main).strip().lower() in ["other", ""] and sub.get(
        "Name of food (Other)"
    ):
      food_main = str(sub.get("Name of food (Other)")).strip()

    # 3. Dates (Finish Date is the official Date of Record)
    finish_raw = (
        sub.get("Finish Date")
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

    start_raw = sub.get("Start Date") or sub.get("StartDate") or ""
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

    # 4. Start Date Rule Check
    date_rule_valid = True
    duration_note = "Valid (24h)"
    if start_date_obj and finish_date_obj:
      days_diff = (finish_date_obj - start_date_obj).days
      if days_diff != 1:
        date_rule_valid = False
        duration_note = f"Anomaly: {days_diff}d diff (Expected 1d)"

    # 5. Times
    start_time = str(sub.get("Start Time") or sub.get("StartTime") or "")[:8]
    finish_time = str(sub.get("Finish Time") or sub.get("FinishTime") or sub.get("Time") or "")[:8]

    # 6. Temperatures
    start_temp_raw = sub.get("Start Temperature °C") or sub.get("Start_Temperature")
    start_temp = pd.to_numeric(
        str(start_temp_raw).replace("°C", "").strip(), errors="coerce"
    )

    final_temp_raw = (
        sub.get("Final Defrosting Temperature °C")
        or sub.get("Final Defrosting Temperature")
        or sub.get("Final Temperature °C")
        or sub.get("Temperature")
    )
    final_temp = pd.to_numeric(
        str(final_temp_raw).replace("°C", "").strip(), errors="coerce"
    )

    sign = (
        sub.get("Sign (Full Name)")
        or sub.get("Sign")
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
        "Start_Time": start_time,
        "Finish_Time": finish_time,
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
  """Renders single-day drilldown and 7-day paginated matrix for Record 12."""
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
      f"📅 Daily Defrost ({selected_day_str})",
      "📈 7-Day Matrix (1-Month Browser)",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions = []
    date_anomalies = []
    compliant_logs = []

    if not day_df.empty:
      for _, r in day_df.iterrows():
        if pd.notna(r["Final_Temp"]) and r["Final_Temp"] > CRITICAL_LIMIT_DEFROST:
          excursions.append(r.to_dict())
        elif not r["Date_Rule_Valid"]:
          date_anomalies.append(r.to_dict())
        else:
          compliant_logs.append(r.to_dict())

    k1, k2, k3, k4 = st.columns(4)
    with k1:
      st.markdown(
          f'<div class="kpi-box"><div class="kpi-num"'
          f' style="color:#dc2626;">{len(excursions)}</div><div'
          ' class="kpi-lbl">Temp Breaches (&gt; 5.0°C)</div></div>',
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f'<div class="kpi-box"><div class="kpi-num"'
          f' style="color:#d97706;">{len(date_anomalies)}</div><div'
          ' class="kpi-lbl">Date Anomalies (≠ 1 Day)</div></div>',
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f'<div class="kpi-box"><div class="kpi-num"'
          f' style="color:#16a34a;">{len(compliant_logs)}</div><div'
          ' class="kpi-lbl">Verified Defrosted</div></div>',
          unsafe_allow_html=True,
      )
    with k4:
      st.markdown(
          f'<div class="kpi-box"><div class="kpi-num"'
          f' style="color:#0f172a;">{len(day_df)}</div><div'
          ' class="kpi-lbl">Total Items Finished</div></div>',
          unsafe_allow_html=True,
      )

    st.write("")

    c1, c2, c3 = st.columns(3)
    with c1:
      st.markdown(
          '<div style="font-weight:700; color:#dc2626; margin-bottom:8px;">🔴'
          f" Core Temp Breaches ({len(excursions)})</div>",
          unsafe_allow_html=True,
      )
      if excursions:
        for exc in excursions:
          st.markdown(
              f'<div style="background:#ffffff; border:1px solid #fca5a5;'
              ' border-left:4px solid #dc2626; padding:12px; border-radius:6px;'
              ' margin-bottom:10px;"><div style="font-weight:700;'
              f' font-size:0.95rem; color:#0f172a;">{exc["Food"]} •'
              f' {exc["Location"]}</div><div style="font-size:0.85rem;'
              ' color:#dc2626; font-weight:700; margin-top:4px;">Final Temp:'
              f' {exc["Final_Temp"]}°C (Limit ≤ 5.0°C)</div><div'
              ' style="font-size:0.75rem; color:#64748b; margin-top:4px;">Started:'
              f' {exc["Start_Date_Str"]} | Sign: {exc["Sign"]}</div></div>',
              unsafe_allow_html=True,
          )
      else:
        st.markdown(
            '<div style="background:#ffffff; border:1px solid #cbd5e1;'
            ' border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem;'
            ' text-align:center;">No temperature excursions on this day.</div>',
            unsafe_allow_html=True,
        )

    with c2:
      st.markdown(
          '<div style="font-weight:700; color:#d97706; margin-bottom:8px;">🟡'
          f" Date Anomalies ({len(date_anomalies)})</div>",
          unsafe_allow_html=True,
      )
      if date_anomalies:
        for anom in date_anomalies:
          st.markdown(
              f'<div style="background:#ffffff; border:1px solid #fde68a;'
              ' border-left:4px solid #d97706; padding:12px; border-radius:6px;'
              ' margin-bottom:10px;"><div style="font-weight:700;'
              f' font-size:0.95rem; color:#0f172a;">{anom["Food"]} •'
              f' {anom["Location"]}</div><div style="font-size:0.85rem;'
              ' color:#d97706; font-weight:700; margin-top:4px;">'
              f' {anom["Duration_Note"]}</div><div style="font-size:0.75rem;'
              ' color:#64748b; margin-top:4px;">Start:'
              f' {anom["Start_Date_Str"]} ➔ Finish:'
              f' {anom["Date_Str"]}</div></div>',
              unsafe_allow_html=True,
          )
      else:
        st.markdown(
            '<div style="background:#ffffff; border:1px solid #cbd5e1;'
            ' border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem;'
            ' text-align:center;">All batches follow standard 1-day defrost.</div>',
            unsafe_allow_html=True,
        )

    with c3:
      st.markdown(
          '<div style="font-weight:700; color:#16a34a; margin-bottom:8px;">🟢'
          f" Verified Defrosted ({len(compliant_logs)})</div>",
          unsafe_allow_html=True,
      )
      if compliant_logs:
        for ok in compliant_logs:
          st.markdown(
              f'<div style="background:#ffffff; border:1px solid #cbd5e1;'
              ' border-left:4px solid #16a34a; padding:12px; border-radius:6px;'
              ' margin-bottom:10px;"><div style="font-weight:700;'
              f' font-size:0.95rem; color:#0f172a;">{ok["Food"]}</div><div'
              ' style="font-size:0.85rem; color:#334155; margin-top:4px;">Final:'
              f' <b style="color:#16a34a;">{ok["Final_Temp"]}°C</b> (Start:'
              f' {ok["Start_Temp"]}°C)</div><div style="font-size:0.75rem;'
              ' color:#64748b; margin-top:4px;">Area: {ok["Location"]} | Sign:'
              f' {ok["Sign"]}</div></div>',
              unsafe_allow_html=True,
          )
      else:
        st.markdown(
            '<div style="background:#ffffff; border:1px solid #cbd5e1;'
            ' border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem;'
            ' text-align:center;">No completed defrost logs for this day.</div>',
            unsafe_allow_html=True,
        )

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
        else ["Butchery", "Main Kitchen"]
    )

    for kitchen in all_kitchens:
      row_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
      row_cols[0].markdown(
          f'<div style="background:#ffffff; border:1.5px solid #94a3b8;'
          f' border-radius:8px; padding:12px 6px; font-weight:700;'
          f' color:#0f172a; font-size:0.88rem; text-align:center;'
          ' box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:115px;'
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
              ' min-height:115px; display:flex; align-items:center;'
              ' justify-content:center;"><span style="color:#94a3b8;'
              ' font-weight:700; font-size:1.2rem;">—</span></div>',
              unsafe_allow_html=True,
          )
        else:
          count = len(matches)
          foods_list = matches["Food"].dropna().tolist()
          foods_text = ", ".join(foods_list)

          row_cols[i + 1].markdown(
              f'<div style="background:#ffffff; border:1.5px solid #0f172a;'
              f' border-radius:8px; padding:8px 4px; text-align:center;'
              ' min-height:115px; box-shadow:0 1px 3px rgba(0,0,0,0.08);"><div'
              ' style="font-size:1.3rem; font-weight:800; color:#0f172a;'
              f' line-height:1;">{count}</div><div style="height:1px;'
              ' background:#cbd5e1; margin:6px 0;"></div><div'
              ' style="font-size:0.75rem; font-weight:600; color:#0f172a;'
              f' line-height:1.3; word-wrap:break-word;">{foods_text}</div></div>',
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
