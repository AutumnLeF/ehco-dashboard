from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_04_FORM_ID = 23706
TEMP_THRESHOLD = 75.0  # Minimum required core temp (°C)

KITCHEN_MEAL_RULES = {
    "Bakery/Pastry": ["Lunch", "Dinner"],
    "Banquet Kitchen": ["Lunch", "Dinner"],
    "Cafeteria Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Gold Lounge Kitchen": ["Breakfast", "Dinner"],
    "Hedonist Kitchen": ["Lunch", "Dinner"],
    "Indian Sweet / Halwai Kitchen": ["Lunch", "Dinner"],
    "IRD Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Madeleine de Proust": ["Breakfast", "Lunch", "Dinner"],
    "Merchant Kitchen": ["Breakfast", "Lunch", "Dinner"],
    "Oryn Kitchen": ["Lunch", "Dinner"],
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
    rec = row.get("raw_record") if "raw_record" in row.columns else row.to_dict()
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

    if isinstance(entries, bool) or not isinstance(entries, (list, dict)):
      entries = [sub] if isinstance(sub, dict) else []
    elif isinstance(entries, dict):
      entries = [entries]
        
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
      "📈 Last 5-Day Compliance Matrix",
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
    pending_cards = []
    completed_cards = []

    for kitchen, meals in KITCHEN_MEAL_RULES.items():
      k_df = (
          day_df[day_df["Location"].str.strip().str.lower() == kitchen.lower()]
          if not day_df.empty
          else pd.DataFrame()
      )

      pending_meals_list = []
      completed_meals_list = []

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
          completed_meals_list.append({
              "Meal": meal,
              "Status": "Completed",
              "Dishes": m_df.to_dict("records"),
              "Sign": m_df["Sign"].iloc[0],
          })
        else:
          pending_meals_list.append({
              "Meal": meal,
              "Status": "Pending",
              "Dishes": [],
              "Sign": "",
          })

      if pending_meals_list:
        pending_cards.append({"Kitchen": kitchen, "Meals": pending_meals_list})

      if completed_meals_list:
        completed_cards.append({
            "Kitchen": kitchen,
            "Meals": completed_meals_list,
        })

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
            <div class="k
