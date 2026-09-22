from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_04_FORM_ID = 23706
TEMP_THRESHOLD = 75.0  # Minimum required core temp (°C)

KITCHEN_MEAL_RULES = {
    "Bakery/Pastry": ["Lunch", "Dinner"],
    "Banquet Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Cafeteria Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Gold Lounge Kitchen": ["Breakfast", "Dinner"],
    "Hedonist Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Indian Sweet / Halwai Kitchen": ["Lunch", "Dinner"],
    "IRD Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Madeleine de Proust": ["Breakfast", "Lunch", "Dinner"],
    "Merchant Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Oryn Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Samaa Kitchen": ["Lunch", "Dinner"],
}


def parse_all_record_04_dishes(raw_df):
  if raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_04_FORM_ID), na=False)
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
        or "Unknown"
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
      parsed_dt_ist = datetime.now()

    raw_time = sub.get("Time") or sub.get("time") or entry_parent.get("Time") or ""
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
    if isinstance(entries, dict):
      entries = [entries]
    if not entries and isinstance(sub, dict):
      entries = [sub]

    for entry in entries:
      if not isinstance(entry, dict):
        continue

      meal = (
          entry.get("Meal_Service")
          or entry.get("Meal")
          or entry.get("Meal Service")
          or "Unassigned"
      )

      food = (
          entry.get("Name_of_Food_Other")
          if str(entry.get("Food", "")).strip().lower() == "other"
          and entry.get("Name_of_Food_Other")
          else (
              entry.get("Food")
              or entry.get("Name_of_Food_Other")
              or entry.get("Name_of_Food")
              or "Food Item"
          )
      )

      temp_raw = (
          entry.get("Temperature")
          if pd.notna(entry.get("Temperature"))
          and str(entry.get("Temperature")).strip()
          not in ["", "nan", "None", "null"]
          else entry.get("Temperature_copy")
      )
      if (
          pd.isna(temp_raw)
          or str(temp_raw).strip() in ["", "nan", "None", "null"]
      ):
        temp_raw = (
            entry.get("Temperature_Cooking")
            or entry.get("Temperature_Reheating")
            or entry.get("Food Temperature °C (Cooking)")
            or entry.get("Food Temperature °C (Reheating)")
        )

      temp_val = pd.to_numeric(
          str(temp_raw).replace("°C", "").replace("°", "").strip(),
          errors="coerce",
      )
      heat_treatment = (
          entry.get("Heat_Treatment")
          or entry.get("Type_of_Heat_Treatment")
          or (
              "Reheating"
              if pd.notna(entry.get("Temperature_copy"))
              else "Cooking"
          )
      )
      corrective = (
          entry.get("Corrective_Actions_cooking")
          or entry.get("Corrective_Action")
          or ""
      )

      rows.append({
          "Date_Str": date_str,
          "Date_Obj": date_obj,
          "Timestamp_DT": parsed_dt_ist,
          "Time": time_str,
          "Location": str(location).strip(),
          "Meal_Service": str(meal).strip(),
          "Heat_Treatment": str(heat_treatment).strip(),
          "Food": str(food).strip(),
          "Temp": temp_val,
          "Corrective_Action": str(corrective),
          "Sign": str(sign).strip(),
      })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(
        subset=[
            "Date_Str",
            "Time",
            "Location",
            "Meal_Service",
            "Food",
            "Temp",
        ],
        keep="first",
    )
  return df_out


def render_record_04_view(raw_df, selected_day_str, start_date, end_date):
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

  all_dishes_df = parse_all_record_04_dishes(raw_df)

  with st.expander("🔍 Record 04 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed cooking records: **{len(all_dishes_df)}**")
    if not all_dishes_df.empty and "Date_Obj" in all_dishes_df.columns:
      date_counts = (
          all_dishes_df["Date_Obj"]
          .dropna()
          .value_counts()
          .sort_index(ascending=False)
          .to_dict()
      )
      st.write(
          "Records per date found:", {str(k): v for k, v in date_counts.items()}
      )

  if not all_dishes_df.empty and "Date_Obj" in all_dishes_df.columns:
    range_df = all_dishes_df[
        (all_dishes_df["Date_Obj"] >= start_date)
        & (all_dishes_df["Date_Obj"] <= end_date)
    ]
  else:
    range_df = all_dishes_df.copy()

  tab_day, tab_matrix = st.tabs([
      f"📅 Daily Cooking & Reheating Audit ({selected_day_str})",
      "📈 14-Day Compliance Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions = []
    shift_counts = {
        "Breakfast": {"req": 0, "done": 0},
        "Lunch": {"req": 0, "done": 0},
        "Dinner": {"req": 0, "done": 0},
    }
    kitchen_status_list = []

    for kitchen, meals in KITCHEN_MEAL_RULES.items():
      k_df = (
          day_df[day_df["Location"].str.strip().str.lower() == kitchen.lower()]
          if not day_df.empty
          else pd.DataFrame()
      )

      meal_statuses = []
      for meal in meals:
        if meal in shift_counts:
          shift_counts[meal]["req"] += 1

        m_df = (
            k_df[k_df["Meal_Service"].str.strip().str.lower() == meal.lower()]
            if not k_df.empty
            else pd.DataFrame()
        )
        if not m_df.empty:
          if meal in shift_counts:
            shift_counts[meal]["done"] += 1
          meal_statuses.append({
              "Meal": meal,
              "Status": "Completed",
              "Dishes": m_df.to_dict("records"),
              "Sign": m_df["Sign"].iloc[0],
          })
        else:
          meal_statuses.append({
              "Meal": meal,
              "Status": "Pending",
              "Dishes": [],
              "Sign": "",
          })

      kitchen_status_list.append({"Kitchen": kitchen, "Meals": meal_statuses})

    if not day_df.empty:
      violating = day_df[day_df["Temp"] < TEMP_THRESHOLD]
      for _, r in violating.iterrows():
        excursions.append({
            "Kitchen": r["Location"],
            "Meal": r["Meal_Service"],
            "Food": r["Food"],
            "Temp": r["Temp"],
            "Sign": r["Sign"],
        })

    # KPI Dashboard
    k1, k2, k3, k4 = st.columns(4)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #dc2626;">
                <div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div>
                <div class="kpi-lbl">Core Temp Breaches (&lt; 75°C)</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      b_done, b_req = (
          shift_counts["Breakfast"]["done"],
          shift_counts["Breakfast"]["req"],
      )
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{b_done}/{b_req}</div>
                <div class="kpi-lbl">Breakfast Shift Completed</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      l_done, l_req = (
          shift_counts["Lunch"]["done"],
          shift_counts["Lunch"]["req"],
      )
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #d97706;">
                <div class="kpi-num" style="color:#d97706;">{l_done}/{l_req}</div>
                <div class="kpi-lbl">Lunch Shift Completed</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k4:
      d_done, d_req = (
          shift_counts["Dinner"]["done"],
          shift_counts["Dinner"]["req"],
      )
      pct = int((d_done / d_req) * 100) if d_req > 0 else 0
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #2563eb;">
                <div class="kpi-num" style="color:#2563eb;">{d_done}/{d_req} <span style="font-size:0.9rem; color:#64748b; font-weight:600;">({pct}%)</span></div>
                <div class="kpi-lbl">Dinner Shift Completed</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")

    pending_cards = []
    completed_cards = []

    for k_info in kitchen_status_list:
      k_name = k_info["Kitchen"]
      m_list = k_info["Meals"]
      pending_meals = [m for m in m_list if m["Status"] == "Pending"]

      if pending_meals:
        pending_cards.append({"Kitchen": k_name, "Meals": m_list})
      else:
        completed_cards.append({"Kitchen": k_name, "Meals": m_list})

    # --- SECTION 1: PENDING / INCOMPLETE SHIFT CARDS (TOP) ---
    st.markdown(
        "<h4 style='color:#b45309; margin-top:1.5rem; margin-bottom:1rem;'>⏳"
        f" Pending / Incomplete Shift Cards ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )

    if not pending_cards:
      st.success("🎉 No pending shifts remaining for today!")
    else:
      p_cols = st.columns(3, gap="small")
      for idx, k_info in enumerate(pending_cards):
        col_target = p_cols[idx % 3]
        k_name = k_info["Kitchen"]
        m_list = k_info["Meals"]

        completed_cnt = sum(m["Status"] == "Completed" for m in m_list)
        pending_cnt = len(m_list) - completed_cnt
        meals_html = ""

        for m in m_list:
          is_done = m["Status"] == "Completed"
          status_color = "#16a34a" if is_done else "#d97706"
          status_text = "✓ Done" if is_done else "⏳ Pending"
          dishes_html = ""

          if is_done:
            for dish in m["Dishes"]:
              temp = dish["Temp"]
              temp_text = f"{temp}°C" if pd.notna(temp) else "—"
              temp_color = (
                  "#dc2626"
                  if pd.notna(temp) and temp < TEMP_THRESHOLD
                  else "#0f172a"
              )
              dishes_html += f"""
                    <div style="display:flex; justify-content:space-between; gap:6px; font-size:0.76rem; padding:4px 0; border-top:1px solid #e2e8f0;">
                        <span style="color:#334155; overflow-wrap:anywhere;">• {dish["Food"]}</span>
                        <b style="color:{temp_color}; white-space:nowrap;">{temp_text}</b>
                    </div>
                    """
            details_html = f'<div style="margin-top:5px;">{dishes_html}</div><div style="font-size:0.68rem; color:#64748b; margin-top:5px;">Signed: {m["Sign"]}</div>'
          else:
            details_html = '<div style="font-size:0.72rem; color:#b45309; margin-top:5px;">No records submitted</div>'

          meals_html += textwrap.dedent(f"""
                <div style="background:#f8fafc; border-left:3px solid {status_color}; border-radius:4px; padding:7px 9px; margin-top:7px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:5px; font-size:0.78rem; font-weight:700; color:#0f172a;">
                        <span>🍽️ {m["Meal"]}</span>
                        <span style="color:{status_color}; white-space:nowrap;">{status_text}</span>
                    </div>
                    {details_html}
                </div>
            """).strip()

        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #d97706; border-radius:6px; padding:10px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size:0.88rem; font-weight:700; color:#0f172a; padding-bottom:7px; border-bottom:1px solid #e2e8f0;">
                    📍 {k_name}
                </div>
                <div style="font-size:0.7rem; margin-top:6px; color:#475569;">
                    <span style="color:#16a34a;font-weight:700;">{completed_cnt} completed</span>
                    &nbsp;|&nbsp;
                    <span style="color:#d97706;font-weight:700;">{pending_cnt} pending</span>
                </div>
                {meals_html}
            </div>
        """).strip()

        col_target.markdown(card_html, unsafe_allow_html=True)

    st.write("")

    # --- SECTION 2: COMPLETELY COMPLETED SHIFT CARDS (BOTTOM) ---
    st.markdown(
        "<h4 style='color:#16a34a; margin-top:2rem; margin-bottom:1rem;'>✅"
        f" Completely Completed Shift Cards ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )

    if not completed_cards:
      st.info("No completely completed shift cards available yet.")
    else:
      c_cols = st.columns(3, gap="small")
      for idx, k_info in enumerate(completed_cards):
        col_target = c_cols[idx % 3]
        k_name = k_info["Kitchen"]
        m_list = k_info["Meals"]

        completed_cnt = sum(m["Status"] == "Completed" for m in m_list)
        pending_cnt = len(m_list) - completed_cnt
        meals_html = ""

        for m in m_list:
          is_done = m["Status"] == "Completed"
          status_color = "#16a34a" if is_done else "#d97706"
          status_text = "✓ Done" if is_done else "⏳ Pending"
          dishes_html = ""

          if is_done:
            for dish in m["Dishes"]:
              temp = dish["Temp"]
              temp_text = f"{temp}°C" if pd.notna(temp) else "—"
              temp_color = (
                  "#dc2626"
                  if pd.notna(temp) and temp < TEMP_THRESHOLD
                  else "#0f172a"
              )
              dishes_html += f"""
                    <div style="display:flex; justify-content:space-between; gap:6px; font-size:0.76rem; padding:4px 0; border-top:1px solid #e2e8f0;">
                        <span style="color:#334155; overflow-wrap:anywhere;">• {dish["Food"]}</span>
                        <b style="color:{temp_color}; white-space:nowrap;">{temp_text}</b>
                    </div>
                    """
            details_html = f'<div style="margin-top:5px;">{dishes_html}</div><div style="font-size:0.68rem; color:#64748b; margin-top:5px;">Signed: {m["Sign"]}</div>'
          else:
            details_html = '<div style="font-size:0.72rem; color:#b45309; margin-top:5px;">No records submitted</div>'

          meals_html += textwrap.dedent(f"""
                <div style="background:#f8fafc; border-left:3px solid {status_color}; border-radius:4px; padding:7px 9px; margin-top:7px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:5px; font-size:0.78rem; font-weight:700; color:#0f172a;">
                        <span>🍽️ {m["Meal"]}</span>
                        <span style="color:{status_color}; white-space:nowrap;">{status_text}</span>
                    </div>
                    {details_html}
                </div>
            """).strip()

        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #16a34a; border-radius:6px; padding:10px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size:0.88rem; font-weight:700; color:#0f172a; padding-bottom:7px; border-bottom:1px solid #e2e8f0;">
                    📍 {k_name}
                </div>
                <div style="font-size:0.7rem; margin-top:6px; color:#475569;">
                    <span style="color:#16a34a;font-weight:700;">{completed_cnt} completed</span>
                    &nbsp;|&nbsp;
                    <span style="color:#d97706;font-weight:700;">{pending_cnt} pending</span>
                </div>
                {meals_html}
            </div>
        """).strip()

        col_target.markdown(card_html, unsafe_allow_html=True)

    if excursions:
      st.markdown(
          '<div style="background:#fee2e2; border-left:5px solid #dc2626;'
          ' padding:10px 14px; border-radius:6px; margin-top:1rem;'
          ' margin-bottom:1rem;"><b style="color:#dc2626; font-size:1rem;">🔴'
          ' Core Temperature Excursions (&lt; 75°C)</b></div>',
          unsafe_allow_html=True,
      )
      for exc in excursions:
        st.markdown(
            f'<div style="background:#ffffff; border:1px solid #fca5a5;'
            ' border-left:4px solid #dc2626; padding:10px; border-radius:6px;'
            ' margin-bottom:8px;"><div style="font-weight:700; font-size:0.9rem;'
            f' color:#0f172a;">{exc["Kitchen"]} • {exc["Meal"]} Service</div><div'
            ' style="font-size:0.85rem; color:#dc2626; font-weight:700;'
            f' margin-top:2px;">Dish: {exc["Food"]} | Temp: {exc["Temp"]}°C'
            ' (Required ≥ 75°C)</div><div style="font-size:0.75rem;'
            f' color:#64748b; margin-top:2px;">Signed by: {exc["Sign"]}</div></div>',
            unsafe_allow_html=True,
        )

  # --- TAB 2: 14-DAY COMPLIANCE MATRIX ---
  with tab_matrix:
    st.markdown(
        f"<h4 style='color:#0f172a; margin-top:1.5rem;'>📈 14-Day Compliance"
        f" Matrix ({start_date.strftime('%d/%m/%Y')} to"
        f" {end_date.strftime('%d/%m/%Y')})</h4>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Kitchen names on the left, dates across the columns with shift"
        " breakdown."
    )

    if range_df.empty:
      st.info("No temperature logs found for this date range.")
    else:
      total_days = max(1, (end_date - start_date).days + 1)
      matrix_dates = [
          start_date + timedelta(days=i) for i in range(total_days)
      ]
      today_date_obj = datetime.now().date()

      for kitchen, meals in KITCHEN_MEAL_RULES.items():
        st.markdown(
            f'<div style="background:#0f172a; color:#ffffff; padding:8px'
            ' 12px; border-radius:6px; margin-top:1.2rem;'
            ' margin-bottom:0.5rem; font-weight:700; font-size:0.95rem;">📍'
            f" {kitchen}</div>",
            unsafe_allow_html=True,
        )

        num_dates = len(matrix_dates)
        col_ratios = [1.2] + [1.0] * num_dates
        cols = st.columns(col_ratios)

        cols[0].markdown(
            '<div style="font-weight:700; font-size:0.78rem; color:#475569;'
            ' padding:4px;">Meal Service</div>',
            unsafe_allow_html=True,
        )
        for i, d in enumerate(matrix_dates):
          cols[i + 1].markdown(
              f'<div style="background:#f1f5f9; font-weight:700;'
              ' font-size:0.75rem; text-align:center; padding:4px;'
              f' border-radius:4px; color:#0f172a;">{d.strftime("%d/%m (%a)")}</div>',
              unsafe_allow_html=True,
          )

        for meal in meals:
          row_cols = st.columns(col_ratios)
          row_cols[0].markdown(
              f'<div style="background:#ffffff; border:1px solid #cbd5e1;'
              ' border-radius:4px; padding:6px; min-height:60px; display:flex;'
              f' align-items:center;"><b style="font-size:0.80rem;'
              f' color:#0f172a;">{meal}</b></div>',
              unsafe_allow_html=True,
          )

          for i, d in enumerate(matrix_dates):
            d_str = d.strftime("%d/%m/%Y")
            match_entry = range_df[
                (range_df["Date_Str"] == d_str)
                & (
                    range_df["Location"].str.strip().str.lower()
                    == kitchen.lower()
                )
                & (
                    range_df["Meal_Service"].str.strip().str.lower()
                    == meal.lower()
                )
            ]

            if match_entry.empty:
              is_past = d < today_date_obj
              card_bg = "#fef2f2" if is_past else "#f8fafc"
              border_c = "#dc2626" if is_past else "#d97706"
              tag_txt = "❌ Missing" if is_past else "⏳ Pending"
              tag_color = "#dc2626" if is_past else "#d97706"

              cell_html = (
                  f'<div style="background:{card_bg}; border:1px solid '
                  f'{border_c}; border-radius:4px; padding:6px; '
                  'min-height:60px; display:flex; flex-direction:column; '
                  'justify-content:center; align-items:center;">'
                  f'<span style="color:{tag_color}; font-weight:800; '
                  f'font-size:0.7rem;">{tag_txt}</span></div>'
              )
              row_cols[i + 1].markdown(cell_html, unsafe_allow_html=True)
            else:
              has_exc = any(match_entry["Temp"] < TEMP_THRESHOLD)
              border_c = "#dc2626" if has_exc else "#16a34a"

              items_preview = ""
              for _, dish in match_entry.iterrows():
                t_val = (
                    f"{dish['Temp']}°C" if pd.notna(dish["Temp"]) else "—"
                )
                items_preview += (
                    "<div style='font-size:0.65rem; color:#334155; "
                    "white-space:nowrap; overflow:hidden; "
                    f"text-overflow:ellipsis;'>• {dish['Food']}: "
                    f"<b>{t_val}</b></div>"
                )

              cell_html = (
                  f'<div style="background:#ffffff; border:1.5px solid '
                  f'{border_c}; border-radius:4px; padding:4px; '
                  'min-height:60px; display:flex; flex-direction:column; '
                  'justify-content:flex-start;">'
                  '<div style="font-weight:800; font-size:0.68rem; '
                  f'color:{border_c};">✓ Completed</div>'
                  f'{items_preview}</div>'
              )
              row_cols[i + 1].markdown(cell_html, unsafe_allow_html=True)

          st.write("")
