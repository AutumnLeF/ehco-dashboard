from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_06_FORM_ID = 23708  # Form ID for Food Display Temperature Record
HOT_MIN_TEMP = 70.0  # Hot display limit >= 70.0°C
COLD_MAX_TEMP = 5.0  # Cold display limit <= 5.0°C

# Required meal frequencies per location based on compliance rules
RECORD_06_MEAL_RULES = {
    "Gold Lounge": ["Breakfast", "Dinner"],
    "The Bombay Café": ["Breakfast", "Lunch", "Dinner"],
    "The Merchants": ["Breakfast", "Lunch", "Dinner"],
}


def parse_record_06_submissions(raw_df):
  """Robustly parses Record 06 Food Display submissions from OneBlink nested payloads."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_06_FORM_ID), na=False)
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

    loc_raw = (
        sub.get("Location")
        or rec.get("Location")
        or entry_parent.get("Location")
        or "The Bombay Café"
    )
    if str(loc_raw).strip().lower() in ["other", ""] and (
        sub.get("Location_other_copy") or sub.get("Location (Other)")
    ):
      location = str(
          sub.get("Location_other_copy") or sub.get("Location (Other)")
      ).strip()
    else:
      location = str(loc_raw).strip()

    sign = (
        sub.get("Sign")
        or sub.get("sign")
        or sub.get("Sign (Initial)")
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

      meal = (
          entry.get("Meal_Service")
          or entry.get("Meal Service")
          or entry.get("Meal")
          or "Lunch"
      )
      treatment = (
          entry.get("Treatment")
          or entry.get("Hot or Cold")
          or entry.get("Type")
          or "Hot"
      )

      food_other = entry.get("Other") or entry.get("Other Food") or ""
      food_hot = entry.get("FoodHot") or entry.get("Name of Food (Hot)") or ""
      food_cold = (
          entry.get("FoodCold") or entry.get("Name of Food (Cold)") or ""
      )

      if (
          str(food_hot).strip().lower() not in ["", "none", "nan", "other"]
          and str(food_hot).strip()
      ):
        food_name = str(food_hot).strip()
      elif (
          str(food_cold).strip().lower() not in ["", "none", "nan", "other"]
          and str(food_cold).strip()
      ):
        food_name = str(food_cold).strip()
      elif str(food_other).strip():
        food_name = str(food_other).strip()
      else:
        food_name = "Display Item"

      temp_raw = (
          entry.get("HotTemp")
          or entry.get("ColdTemp")
          or entry.get("Food Temperature °C (Hot)")
          or entry.get("Food Temperature °C (Cold)")
          or entry.get("Temperature")
      )
      temp_val = pd.to_numeric(
          str(temp_raw).replace("°C", "").replace("°", "").strip(),
          errors="coerce",
      )

      has_breach = False
      if pd.notna(temp_val):
        if str(treatment).strip().lower() == "hot" and temp_val < HOT_MIN_TEMP:
          has_breach = True
        elif (
            str(treatment).strip().lower() == "cold" and temp_val > COLD_MAX_TEMP
        ):
          has_breach = True

      rows.append({
          "Date_Str": norm_date,
          "Date_Obj": date_obj,
          "Time": time_str,
          "Location": location,
          "Meal_Service": str(meal).strip(),
          "Treatment": str(treatment).strip(),
          "Food": food_name,
          "Temp": temp_val,
          "Has_Breach": has_breach,
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


def render_record_06_view(raw_df, selected_day_str, start_date, end_date):
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

  df_items = parse_record_06_submissions(raw_df)

  with st.expander("🔍 Record 06 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed display records: **{len(df_items)}**")
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
      f"📅 Daily Display Audit ({selected_day_str})",
      "📈 7-Day Compliance Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions = 0
    kitchen_status_list = []

    for kitchen, meals in RECORD_06_MEAL_RULES.items():
      k_df = (
          day_df[day_df["Location"].str.strip().str.lower() == kitchen.lower()]
          if not day_df.empty
          else pd.DataFrame()
      )

      meal_statuses = []
      for meal in meals:
        m_df = (
            k_df[k_df["Meal_Service"].str.strip().str.lower() == meal.lower()]
            if not k_df.empty
            else pd.DataFrame()
        )
        if not m_df.empty:
          for _, r in m_df.iterrows():
            if r["Has_Breach"]:
              excursions += 1
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

    # Additional dynamic locations found in day_df that aren't in fixed rules
    if not day_df.empty:
      known_locs = [k.lower() for k in RECORD_06_MEAL_RULES.keys()]
      other_locs = day_df[
          ~day_df["Location"].str.strip().str.lower().isin(known_locs)
      ]["Location"].unique()
      for loc in other_locs:
        k_df = day_df[day_df["Location"].str.strip().str.lower() == loc.lower()]
        meals_found = k_df["Meal_Service"].unique()
        meal_statuses = []
        for meal in meals_found:
          m_df = k_df[
              k_df["Meal_Service"].str.strip().str.lower() == meal.lower()
          ]
          for _, r in m_df.iterrows():
            if r["Has_Breach"]:
              excursions += 1
          meal_statuses.append({
              "Meal": meal,
              "Status": "Completed",
              "Dishes": m_df.to_dict("records"),
              "Sign": m_df["Sign"].iloc[0],
          })
        kitchen_status_list.append({"Kitchen": loc, "Meals": meal_statuses})

    pending_cards = [
        k for k in kitchen_status_list if any(m["Status"] == "Pending" for m in k["Meals"])
    ]
    completed_cards = [
        k for k in kitchen_status_list if all(m["Status"] == "Completed" for m in k["Meals"])
    ]

    total_kitchens = len(kitchen_status_list)
    completed_count_k = len(completed_cards)
    pending_count_k = len(pending_cards)
    completion_pct = (
        int((completed_count_k / total_kitchens) * 100)
        if total_kitchens > 0
        else 0
    )

    # KPI Dashboard
    k1, k2, k3, k4 = st.columns(4)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #dc2626;">
                <div class="kpi-num" style="color:#dc2626;">{excursions}</div>
                <div class="kpi-lbl">Holding Breaches</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{completed_count_k}/{total_kitchens}</div>
                <div class="kpi-lbl">Completed Kitchens</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #d97706;">
                <div class="kpi-num" style="color:#d97706;">{pending_count_k}/{total_kitchens}</div>
                <div class="kpi-lbl">Pending Kitchens</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k4:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #2563eb;">
                <div class="kpi-num" style="color:#2563eb;">{completion_pct}%</div>
                <div class="kpi-lbl">Compliance Progress</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.progress(
        completion_pct / 100.0,
        text=f"Daily Display Compliance Progress: {completed_count_k} of {total_kitchens} Areas Completed ({completion_pct}%)",
    )
    st.write("")

    # --- SECTION 1: PENDING CARDS (TOP) ---
    st.markdown(
        "<h4 style='color:#b45309; margin-top:1.5rem; margin-bottom:1rem;'>⏳"
        f" Pending / Incomplete Shift Cards ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )
    if not pending_cards:
      st.success("🎉 All display shifts for today are fully completed!")
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
              dishes_html += f"""
                    <div style="display:flex; justify-content:space-between; gap:6px; font-size:0.76rem; padding:4px 0; border-top:1px solid #e2e8f0;">
                        <span style="color:#334155;">• {dish["Food"]} ({dish["Treatment"]})</span>
                        <b style="color:#0f172a; white-space:nowrap;">{temp_text}</b>
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

    # --- SECTION 2: COMPLETED CARDS (BOTTOM) ---
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
              dishes_html += f"""
                    <div style="display:flex; justify-content:space-between; gap:6px; font-size:0.76rem; padding:4px 0; border-top:1px solid #e2e8f0;">
                        <span style="color:#334155;">• {dish["Food"]} ({dish["Treatment"]})</span>
                        <b style="color:#0f172a; white-space:nowrap;">{temp_text}</b>
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

  with tab_matrix:
    st.subheader("7-Day Compliance Matrix")
    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec06_page" not in st.session_state:
      st.session_state.rec06_page = max(0, (total_days - 1) // 7)
    max_page = max(0, (total_days - 1) // 7)

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
      if st.button(
          "⬅️ Previous 7 Days",
          key="r06_prev",
          disabled=(st.session_state.rec06_page <= 0),
          use_container_width=True,
      ):
        st.session_state.rec06_page -= 1
        st.rerun()
    with nav3:
      if st.button(
          "Next 7 Days ➡️",
          key="r06_next",
          disabled=(st.session_state.rec06_page >= max_page),
          use_container_width=True,
      ):
        st.session_state.rec06_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec06_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with nav2:
      if page_dates:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#0f172a;"
            f" font-size:0.95rem; padding-top:6px;'>Showing:"
            f" <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to"
            f" <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block"
            f" {st.session_state.rec06_page + 1} of {max_page + 1})</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    cols = st.columns(7)
    for i, d in enumerate(page_dates):
      cols[i].markdown(
          f"""
            <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.82rem; padding:10px 2px; border-radius:6px; text-align:center; margin-bottom:8px;">
                {d.strftime('%d/%m (%a)')}
            </div>
            """,
          unsafe_allow_html=True,
      )

    for i, d in enumerate(page_dates):
      d_str = d.strftime("%d/%m/%Y")
      matches = (
          range_df[range_df["Date_Obj"] == d]
          if not range_df.empty and "Date_Obj" in range_df.columns
          else pd.DataFrame()
      )
      if matches.empty and not range_df.empty:
        matches = range_df[range_df["Date_Str"] == d_str]

      with cols[i]:
        if matches.empty:
          st.markdown(
              """
                <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:12px 6px; text-align:center; min-height:160px; display:flex; align-items:center; justify-content:center;">
                    <span style="color:#94a3b8; font-weight:600; font-size:0.82rem;">— Not Logged</span>
                </div>
                """,
              unsafe_allow_html=True,
          )
        else:
          batch_count = len(matches)
          has_day_breach = any(matches["Has_Breach"])
          foods = list(dict.fromkeys(matches["Food"].dropna().tolist()))
          foods_txt = ", ".join(foods[:3]) + (
              "..." if len(foods) > 3 else ""
          )
          signs = ", ".join(
              list(dict.fromkeys(matches["Sign"].dropna().tolist()))
          )

          badge = (
              '<span style="color:#dc2626; font-weight:800;'
              ' font-size:0.9rem;">🔴 BREACH</span>'
              if has_day_breach
              else (
                  '<span style="color:#16a34a; font-weight:800;'
                  f' font-size:0.95rem;">✓ {batch_count} Passed</span>'
              )
          )
          card_border = "2px solid #dc2626" if has_day_breach else "1.5px solid #0f172a"

          st.markdown(
              f"""
            <div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:10px 6px; text-align:center; min-height:160px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                <div>{badge}</div>
                <div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>
                <div style="font-size:0.75rem; font-weight:700; color:#0f172a; line-height:1.25; word-wrap:break-word;">
                    {foods_txt}
                </div>
                <div style="height:1px; background:#f1f5f9; margin:5px 0;"></div>
                <div style="font-size:0.68rem; color:#64748b; margin-top:4px;">By: {signs}</div>
            </div>
            """,
              unsafe_allow_html=True,
          )

    st.divider()
    with st.expander("📋 View All Individual Food Display Records"):
      if not range_df.empty:
        show_cols = [
            c
            for c in [
                "Date_Str",
                "Time",
                "Location",
                "Meal_Service",
                "Treatment",
                "Food",
                "Temp",
                "Sign",
            ]
            if c in range_df.columns
        ]
        st.dataframe(
            range_df[show_cols], use_container_width=True, hide_index=True
        )
