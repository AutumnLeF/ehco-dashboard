from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_05_FORM_ID = 23707
CRITICAL_LIMIT_2HR = 5.0  # Limit: <= 5.0°C after 2 hours

RECORD_05_KITCHENS = [
    "Bakery/Pastry",
    "Banquet Kitchen",
    "Garde Manger",
    "Hedonist Kitchen",
    "Indian Sweet / Halwai Kitchen",
    "IRD Kitchen",
    "Madeleine de Proust",
    "Merchant Kitchen",
    "Oryn Kitchen",
    "Samaa Kitchen",
    "The Bombay Café",
]


def parse_record_05_submissions(raw_df):
  """Robustly parses Record 05 blast chiller submissions from OneBlink nested payloads."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_05_FORM_ID), na=False)
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
        or "Bakery/Pastry"
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
        or sub.get("StartDate")
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
      norm_date = parsed_dt_ist.strftime("%d/%m/%Y")
      date_obj = parsed_dt_ist.date()
    else:
      norm_date = str(raw_date)[:10]
      date_obj = None

    raw_time = (
        sub.get("Time")
        or sub.get("StartTime")
        or entry_parent.get("Time")
        or ""
    )
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

    if isinstance(entries, bool) or not isinstance(entries, (list, dict)):
      entries = [sub] if isinstance(sub, dict) else []
    elif isinstance(entries, dict):
      entries = [entries]

    for entry in entries:
      if not isinstance(entry, dict):
        continue

      method = entry.get("Method") or sub.get("Method") or "Blast Chiller"
      food = (
          entry.get("Name_of_Food")
          or entry.get("Food")
          or entry.get("Food_Item")
          or entry.get("Dish")
          or "Batch Item"
      )

      start_raw = (
          entry.get("Start_Temperature")
          or entry.get("StartTemp")
          or entry.get("Temp_Start")
          or entry.get("Temperature_Start")
      )
      start_temp = pd.to_numeric(
          str(start_raw).replace("°C", "").replace("°", "").strip(),
          errors="coerce",
      )

      end_raw = (
          entry.get("Temperature_After_2_Hours")
          or entry.get("After_2_Hours")
          or entry.get("Temp_After_2")
          or entry.get("End_Temp")
          or entry.get("Temperature")
          or entry.get("Temperature_2_Hours")
          or entry.get("Temperature_after_2_hours")
      )

      if (
          pd.isna(
              pd.to_numeric(
                  str(end_raw).replace("°C", "").strip(), errors="coerce"
              )
          )
          or str(end_raw).strip() == ""
      ):
        for k, v in entry.items():
          k_lower = str(k).lower()
          if any(term in k_lower for term in ["2", "after", "end", "hr"]):
            if v is not None and str(v).strip() not in ["", "None", "nan"]:
              end_raw = v
              break

      end_temp = pd.to_numeric(
          str(end_raw).replace("°C", "").replace("°", "").strip(),
          errors="coerce",
      )

      rows.append({
          "Date_Str": norm_date,
          "Date_Obj": date_obj,
          "Time": time_str,
          "Location": str(location).strip(),
          "Method": str(method).strip(),
          "Food": str(food).strip(),
          "Start_Temp": start_temp,
          "End_Temp": end_temp,
          "Sign": str(sign).strip(),
      })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(
        subset=[
            "Date_Str",
            "Time",
            "Location",
            "Food",
            "Start_Temp",
            "End_Temp",
        ],
        keep="first",
    )
  return df_out


def render_record_05_view(raw_df, selected_day_str, start_date, end_date):
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

  df_items = parse_record_05_submissions(raw_df)

  with st.expander("🔍 Record 05 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed cooling records: **{len(df_items)}**")
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
      f"📅 Daily Pull-Down Audit ({selected_day_str})",
      "📈 7-Day Matrix (1-Month Browser)",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions = 0
    compliant_count = 0

    kitchen_status_list = []
    for kitchen in RECORD_05_KITCHENS:
      k_df = (
          day_df[day_df["Location"].str.strip().str.lower() == kitchen.lower()]
          if not day_df.empty
          else pd.DataFrame()
      )

      is_completed = not k_df.empty
      batches = []
      sign = ""
      if is_completed:
        sign = k_df["Sign"].iloc[0]
        for _, r in k_df.iterrows():
          is_exc = pd.notna(r["End_Temp"]) and r["End_Temp"] > CRITICAL_LIMIT_2HR
          if is_exc:
            excursions += 1
          else:
            compliant_count += 1
          batches.append({
              "Food": r["Food"],
              "Start": r["Start_Temp"],
              "End": r["End_Temp"],
              "Excursion": is_exc,
          })

      kitchen_status_list.append({
          "Kitchen": kitchen,
          "Status": "Completed" if is_completed else "Pending",
          "Batches": batches,
          "Sign": sign,
      })

    # KPI Dashboard
    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #dc2626;">
                <div class="kpi-num" style="color:#dc2626;">{excursions}</div>
                <div class="kpi-lbl">Excursions (&gt; 5.0°C)</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{compliant_count}</div>
                <div class="kpi-lbl">Verified Pulled-Down (≤ 5.0°C)</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      total_batches = len(day_df)
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0f172a;">
                <div class="kpi-num" style="color:#0f172a;">{total_batches}</div>
                <div class="kpi-lbl">Total Batches Chilled</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    pending_cards = [k for k in kitchen_status_list if k["Status"] == "Pending"]
    completed_cards = [
        k for k in kitchen_status_list if k["Status"] == "Completed"
    ]

    # --- SECTION 1: PENDING KITCHENS (TOP) ---
    st.markdown(
        "<h4 style='color:#b45309; margin-top:1.5rem; margin-bottom:1rem;'>⏳"
        f" Pending / Incomplete Kitchen Areas ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not pending_cards:
      st.success("🎉 All kitchen areas have submitted blast chiller logs!")
    else:
      p_cols = st.columns(3, gap="small")
      for idx, k_info in enumerate(pending_cards):
        col_target = p_cols[idx % 3]
        card_html = textwrap.dedent(f"""
                <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #d97706; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size:0.9rem; font-weight:700; color:#0f172a; padding-bottom:6px; border-bottom:1px solid #e2e8f0;">
                        📍 {k_info["Kitchen"]}
                    </div>
                    <div style="font-size:0.75rem; color:#b45309; margin-top:8px; font-style:italic;">
                        ⏳ No cooling records submitted yet.
                    </div>
                </div>
            """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

    st.write("")

    # --- SECTION 2: COMPLETED KITCHENS (BOTTOM) ---
    st.markdown(
        "<h4 style='color:#16a34a; margin-top:2rem; margin-bottom:1rem;'>✅"
        f" Completed Kitchen Audit Entries ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not completed_cards:
      st.info("No completed kitchen entries for this date.")
    else:
      c_cols = st.columns(3, gap="small")
      for idx, k_info in enumerate(completed_cards):
        col_target = c_cols[idx % 3]
        k_name = k_info["Kitchen"]
        batches = k_info["Batches"]
        sign = k_info["Sign"]

        batches_html = ""
        for b in batches:
          end_str = f"{b['End']}°C" if pd.notna(b["End"]) else "—"
          temp_color = "#dc2626" if b["Excursion"] else "#16a34a"
          batches_html += textwrap.dedent(f"""
                <div style="background:#f8fafc; border-left:3px solid {temp_color}; border-radius:4px; padding:6px 8px; margin-top:6px; font-size:0.76rem;">
                    <div style="font-weight:700; color:#0f172a;">🍲 {b["Food"]}</div>
                    <div style="color:#475569; margin-top:2px;">Start: {b["Start"]}°C ➔ <b style="color:{temp_color};">{end_str}</b></div>
                </div>
            """).strip()

        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #16a34a; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
                    <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {k_name}</span>
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

  with tab_matrix:
    st.subheader("7-Day Kitchen Completion Matrix")

    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec05_page" not in st.session_state:
      st.session_state.rec05_page = max(0, (total_days - 1) // 7)

    max_page = max(0, (total_days - 1) // 7)

    col_prev, col_status, col_next = st.columns([1, 3, 1])
    with col_prev:
      if st.button(
          "⬅️ Previous 7 Days",
          disabled=(st.session_state.rec05_page <= 0),
          use_container_width=True,
          key="r05_prev",
      ):
        st.session_state.rec05_page -= 1
        st.rerun()

    with col_next:
      if st.button(
          "Next 7 Days ➡️",
          disabled=(st.session_state.rec05_page >= max_page),
          use_container_width=True,
          key="r05_next",
      ):
        st.session_state.rec05_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec05_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with col_status:
      if page_dates:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#0f172a;"
            f" font-size:0.95rem; padding-top:6px;'>Showing:"
            f" {page_dates[0].strftime('%d/%m/%Y')} to"
            f" {page_dates[-1].strftime('%d/%m/%Y')} (Block"
            f" {st.session_state.rec05_page + 1} of {max_page + 1})</div>",
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
        else RECORD_05_KITCHENS
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
            end_t = (
                f"{dish['End_Temp']}°C" if pd.notna(dish["End_Temp"]) else "—"
            )
            items_preview_name = (
                dish["Food"][:16] + "..."
                if len(str(dish["Food"])) > 16
                else dish["Food"]
            )
            items_html += (
                "<div style='font-size:0.68rem; color:#334155; margin-top:2px;"
                " text-align:left; border-top:1px solid #f1f5f9;"
                f" padding-top:2px;'><b>{items_preview_name}</b><br/><span"
                f" style='color:#0284c7;'>{start_t} ➔ {end_t}</span></div>"
            )

          row_cols[i + 1].markdown(
              f'<div style="background:#ffffff; border:1.5px solid #0f172a;'
              f' border-radius:8px; padding:6px 6px; min-height:130px;'
              ' box-shadow:0 1px 3px rgba(0,0,0,0.08);"><div'
              ' style="font-size:1.1rem; font-weight:800; color:#0f172a;'
              f' text-align:center; line-height:1;">{count}</div>{items_html}</div>',
              unsafe_allow_html=True,
          )

      st.write("")

    st.divider()
    with st.expander("📋 View All Individual Chilling Records (Selected Window)"):
      if not range_df.empty:
        show_cols = [
            c
            for c in [
                "Date_Str",
                "Time",
                "Location",
                "Food",
                "Start_Temp",
                "End_Temp",
                "Sign",
            ]
            if c in range_df.columns
        ]
        st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
