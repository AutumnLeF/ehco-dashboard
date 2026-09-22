from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

MAX_FRIDGE_TEMP = 4.0     # Coolroom / Fridge <= 4.0°C
MAX_FREEZER_TEMP = -18.0  # Freezer <= -18.0°C
RECORD_03_FORM_ID = 23705

# Comprehensive Catalog mapped from site data (CoolRooms, Freezers & Fridges)
UNIT_CATALOG = {
    # --- COOLROOMS ---
    "Garbage Room Walk-In (Chiller)": [
        {"Unit_ID": "GRB-Cold Room-CR01", "Type": "Coolroom"},
    ],
    "Receiving": [
        {"Unit_ID": "CMM-Cold Room-CR02", "Type": "Coolroom"},
        {"Unit_ID": "CMM/DF/CR03", "Type": "Freezer"},
    ],
    "Commissary": [
        {"Unit_ID": "CMM-Cold Room-CR04", "Type": "Coolroom"},
        {"Unit_ID": "CMM-Cold Room-CR05", "Type": "Coolroom"},
        {"Unit_ID": "VP-Cold Room-CR09", "Type": "Coolroom"},
    ],
    "Butchery": [
        {"Unit_ID": "CMM-Cold Room-CR06", "Type": "Coolroom"},
        {"Unit_ID": "CMM-Cold Room-CR07", "Type": "Coolroom"},
        {"Unit_ID": "CMM/DF/CR08", "Type": "Freezer"},
        {"Unit_ID": "BCH-Cold Room-CR10", "Type": "Coolroom"},
        {"Unit_ID": "SF-Cold Room-CR11", "Type": "Coolroom"},
    ],
    "The Bombay Café": [
        {"Unit_ID": "CK-Cold Room-CR13", "Type": "Coolroom"},
        {"Unit_ID": "TBC/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Banquet Kitchen": [
        {"Unit_ID": "BQT-Cold Room-CR14", "Type": "Coolroom"},
        {"Unit_ID": "BQT-Cold Room-CR15", "Type": "Coolroom"},
        {"Unit_ID": "BQT/DF/CR16", "Type": "Freezer"},
        {"Unit_ID": "BQT-Cold Room-CR17", "Type": "Coolroom"},
        {"Unit_ID": "MKI/UC/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "MKC/UC/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "BQC/VR/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "BQK/UC/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "BQT SER- Cold room - CR26", "Type": "Coolroom"},
    ],
    "Garde Manger": [
        {"Unit_ID": "GM-Cold Room-CR18", "Type": "Coolroom"},
        {"Unit_ID": "GM/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Bakery & Pastry": [
        {"Unit_ID": "BK-Cold Room-CR19", "Type": "Coolroom"},
        {"Unit_ID": "BP/DF/CR20", "Type": "Freezer"},
        {"Unit_ID": "PK-Cold Room-CR21", "Type": "Coolroom"},
        {"Unit_ID": "PS/UC/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "CR/VR/FRZ/01", "Type": "Freezer"},
    ],
    "Banquet - Service": [
        {"Unit_ID": "BQT SER- Cold room - CR261", "Type": "Coolroom"},
        {"Unit_ID": "BQS/VR/FRZ/01", "Type": "Freezer"},
    ],
    "Merchant Chiller": [
        {"Unit_ID": "TM-Cold Room - CR27", "Type": "Coolroom"},
    ],
    "The Merchants Deep Freezer": [
        {"Unit_ID": "TM/DF/CR28", "Type": "Freezer"},
    ],
    "IRD Kitchen": [
        {"Unit_ID": "IRDK/Cold Room/31", "Type": "Coolroom"},
        {"Unit_ID": "IRDK/Cold Room/32", "Type": "Coolroom"},
        {"Unit_ID": "IRDK/DF/33", "Type": "Freezer"},
        {"Unit_ID": "IRDK/UC/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "IRDK/UC/FRZ/02", "Type": "Freezer"},
    ],
    "Oryn Kitchen": [
        {"Unit_ID": "ORN/Cold Room/CR34", "Type": "Coolroom"},
        {"Unit_ID": "OK/VR/FRZ/01", "Type": "Freezer"},
    ],
    "Merchants - Service": [
        {"Unit_ID": "MS/Cold Room/25", "Type": "Coolroom"},
        {"Unit_ID": "MB/UC/FRZ/01", "Type": "Freezer"},
    ],

    # --- FREEZERS ---
    "The Merchants - Chocolate Atelier": [
        {"Unit_ID": "MBP/UC/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "MBP/DIS/FRZ/01", "Type": "Freezer"},
        {"Unit_ID": "MBP/UC/FRZ/03", "Type": "Freezer"},  # Changed from REF/03
        {"Unit_ID": "MCA/UC/FRZ/01", "Type": "Freezer"},
    ],
    "The Merchants - Western Hot": [
        {"Unit_ID": "MWH/UC/FRZ/01", "Type": "Freezer"},
    ],
    "The Merchants - Cold Kitchen": [
        {"Unit_ID": "MCK/VR/FRZ/01", "Type": "Freezer"},
    ],
    "The Merchants Indian Non Veg": [
        {"Unit_ID": "MIN/UC/FRZ/01", "Type": "Freezer"},
    ],
    "The Merchants Indian Veg": [
        {"Unit_ID": "MIV/UC/FRZ/01", "Type": "Freezer"},
    ],
    "The Merchants Japanese Section": [
        {"Unit_ID": "MJ/UC/FRZ/01", "Type": "Freezer"},
    ],
    "The Merchants - Asian Section": [
        {"Unit_ID": "MA/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Beyond Oryn Bar": [
        {"Unit_ID": "BO/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Gold Lounge Kitchen": [
        {"Unit_ID": "GK/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Gold Lounge Service": [
        {"Unit_ID": "GS/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Hedonist Kitchen": [
        {"Unit_ID": "HK/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Hedonist Bar": [
        {"Unit_ID": "HB/UC/FRZ/01", "Type": "Freezer"},
    ],
    "MDP Kitchen": [
        {"Unit_ID": "MDPK/VR/FRZ/01", "Type": "Freezer"},
    ],
    "Halwai Kitchen": [
        {"Unit_ID": "HLK/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Samaa Kitchen": [
        {"Unit_ID": "SK/UC/FRZ/01", "Type": "Freezer"},
    ],
    "Hygiene Office": [
        {"Unit_ID": "HO/VR/FRZ/01", "Type": "Freezer"},
    ],
    "Samaa Bar": [
        {"Unit_ID": "SB/UC/FRZ/01", "Type": "Freezer"},
    ],

    # --- FRIDGES ---
    "The Merchants - Chocolate Atelier (Fridge)": [
        {"Unit_ID": "MBP/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MBP/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MBP/UC/REF/04", "Type": "Fridge"},
        {"Unit_ID": "MCA/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MCA/UC/REF/02", "Type": "Fridge"},
    ],
    "The Merchants - Western Hot (Fridge)": [
        {"Unit_ID": "MWH/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MWH/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MWH/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "MWH/UC/REF/04", "Type": "Fridge"},
        {"Unit_ID": "MWH/UC/REF/05", "Type": "Fridge"},
        {"Unit_ID": "MWH/UC/REF/06", "Type": "Fridge"},
    ],
    "The Merchants - Cold Kitchen (Fridge)": [
        {"Unit_ID": "MCK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MCK/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MCK/UC/REF/03", "Type": "Fridge"},
    ],
    "The Merchants Indian Non Veg (Fridge)": [
        {"Unit_ID": "MIN/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MIN/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MIN/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "MIN/DIS/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MIN/DIS/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MIN/DIS/REF/03", "Type": "Fridge"},
    ],
    "The Merchants Indian Veg (Fridge)": [
        {"Unit_ID": "MIV/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MIV/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MIV/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "MIV/DIS/REF/01", "Type": "Fridge"},
    ],
    "Merchants - Service (Fridge)": [
        {"Unit_ID": "MB/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MB/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MB/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "MBS/VR/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MBS/VR/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MBS/VR/REF/03", "Type": "Fridge"},
    ],
    "The Merchants Japanese Section (Fridge)": [
        {"Unit_ID": "MJ/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MJ/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MJ/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "MJ/UC/REF/04", "Type": "Fridge"},
        {"Unit_ID": "MJ/DIS/REF/01", "Type": "Fridge"},
    ],
    "The Merchants - Asian Section (Fridge)": [
        {"Unit_ID": "MA/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MA/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MA/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "MA/UC/REF/04", "Type": "Fridge"},
        {"Unit_ID": "MA/DIS/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MA/DIS/REF/02", "Type": "Fridge"},
    ],
    "IRD (Fridge)": [
        {"Unit_ID": "IRD/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "IRD/VR/REF/01", "Type": "Fridge"},
        {"Unit_ID": "IRD/VR/REF/02", "Type": "Fridge"},
    ],
    "Oryn kitchen (Fridge)": [
        {"Unit_ID": "OK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "OK/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "OK/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "OK/UC/REF/04", "Type": "Fridge"},
        {"Unit_ID": "OK/VR/REF/01", "Type": "Fridge"},
    ],
    "Beyond Oryn Bar (Fridge)": [
        {"Unit_ID": "BO/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "BO/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "BO/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "BO/UC/REF/04", "Type": "Fridge"},
    ],
    "Gold Lounge Kitchen (Fridge)": [
        {"Unit_ID": "GK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "GK/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "GK/VR/REF/01", "Type": "Fridge"},
    ],
    "Gold Lounge Service (Fridge)": [
        {"Unit_ID": "GS/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "GS/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "GS/DIS/REF/01", "Type": "Fridge"},
        {"Unit_ID": "GS/DIS/REF/02", "Type": "Fridge"},
    ],
    "Hedonist Kitchen (Fridge)": [
        {"Unit_ID": "HK/UC/REF/01", "Type": "Fridge"},
    ],
    "Hedonist Bar (Fridge)": [
        {"Unit_ID": "HB/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "HB/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "HB/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "HB/VR/REF/01", "Type": "Fridge"},
    ],
    "MDP Kitchen (Fridge)": [
        {"Unit_ID": "MDPK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MDPK/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MDPK/VR/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MDPK/VR/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MDPK/VR/REF/03", "Type": "Fridge"},
    ],
    "MDP Service (Fridge)": [
        {"Unit_ID": "MDPS/VR/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MDPS/VR/REF/02", "Type": "Fridge"},
    ],
    "MDP Tea Lounge (Fridge)": [
        {"Unit_ID": "MDPS/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MDPS/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "MDPS/DIS/REF/01", "Type": "Fridge"},
    ],
    "The Bombay Café (Fridge)": [
        {"Unit_ID": "TBC/UC/REF/01", "Type": "Fridge"},
    ],
    "Banquet Kitchen (Fridge)": [
        {"Unit_ID": "MKI/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MKT/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MKA/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "MKC/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "BQC/VR/REF/01", "Type": "Fridge"},
        {"Unit_ID": "BQC/VR/REF/02", "Type": "Fridge"},
        {"Unit_ID": "BQC/VR/REF/03", "Type": "Fridge"},
        {"Unit_ID": "BQK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "BQK/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "BQK/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "BQK/UC/REF/04", "Type": "Fridge"},
    ],
    "Garde Manger (Fridge)": [
        {"Unit_ID": "GM/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "GM/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "GM/UC/REF/03", "Type": "Fridge"},
    ],
    "Halwai Kitchen (Fridge)": [
        {"Unit_ID": "HLK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "HLK/UC/REF/02", "Type": "Fridge"},
    ],
    "Bakery & Pastry (Fridge)": [
        {"Unit_ID": "PS/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "PS/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "PS/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "CR/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "CR/VR/REF/01", "Type": "Fridge"},
    ],
    "Banquets - Grand Terminus (Fridge)": [
        {"Unit_ID": "GT/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "GT/UC/REF/02", "Type": "Fridge"},
    ],
    "Banquet - Service (Fridge)": [
        {"Unit_ID": "BQS/VR/REF/01", "Type": "Fridge"},
        {"Unit_ID": "BQS/VR/REF/02", "Type": "Fridge"},
        {"Unit_ID": "BQS/VR/REF/03", "Type": "Fridge"},
        {"Unit_ID": "BQS/VR/REF/04", "Type": "Fridge"},
        {"Unit_ID": "BQB/UC/REF/01", "Type": "Fridge"},
    ],
    "Samaa Kitchen (Fridge)": [
        {"Unit_ID": "SK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "SK/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "SK/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "SK/UC/REF/04", "Type": "Fridge"},
        {"Unit_ID": "SK/VR/REF/01", "Type": "Fridge"},
    ],
    "Hygiene Office (Fridge)": [
        {"Unit_ID": "HO/VR/REF/01", "Type": "Fridge"},
    ],
    "Samaa Bar (Fridge)": [
        {"Unit_ID": "SB/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "SB/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "SB/UC/REF/03", "Type": "Fridge"},
    ],
    "SPA (Fridge)": [
        {"Unit_ID": "SPA/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "SPA/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "SPA/DIS/REF/01", "Type": "Fridge"},
    ],
    "IRD Kitchen (Fridge)": [
        {"Unit_ID": "IRDK/VR/REF/01", "Type": "Fridge"},
        {"Unit_ID": "IRDK/UC/REF/01", "Type": "Fridge"},
        {"Unit_ID": "IRDK/UC/REF/02", "Type": "Fridge"},
        {"Unit_ID": "IRDK/UC/REF/03", "Type": "Fridge"},
        {"Unit_ID": "IRDK/UC/REF/04", "Type": "Fridge"},
        {"Unit_ID": "IRDK/UC/REF/05", "Type": "Fridge"},
        {"Unit_ID": "IRDK/UC/REF/06", "Type": "Fridge"},
        {"Unit_ID": "IRDK/UC/REF/07", "Type": "Fridge"},
    ],
}


def clean_unit_token(val):
  if not val or pd.isna(val):
    return ""
  return str(val).replace("/", "").replace("_", "").replace(" ", "").replace("-", "").strip().upper()


def extract_temp_value(entry, sub):
  candidates = [
      entry.get("CRTemperature"),
      entry.get("FreezerTemp"),
      entry.get("FZTemperature"),
      entry.get("Temperature"),
      entry.get("temperature"),
      sub.get("Temperature °C (Coolroom 4°C or below / Fridge 4°C or below)"),
      sub.get("Temperature °C (Freezer -18°C or colder)"),
  ]
  for c in candidates:
    if c is not None and str(c).strip() not in ["", "None", "nan"]:
      val_clean = str(c).replace("°C", "").replace("°", "").strip()
      num = pd.to_numeric(val_clean, errors="coerce")
      if pd.notna(num):
        return float(num)
  return None


def parse_record_03_submissions(raw_df):
  """Robustly parses Record 03 Coolroom/Fridge/Freezer temperature records."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_03_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  flat_master = []
  for loc, units in UNIT_CATALOG.items():
    for u in units:
      flat_master.append({
          "Location": loc,
          "Unit_ID": u["Unit_ID"],
          "Type": u["Type"],
          "Clean_ID": clean_unit_token(u["Unit_ID"]),
      })

  rows = []
  for _, row in df.iterrows():
    rec = row.get("raw_record") if "raw_record" in df.columns else row.to_dict()
    if not isinstance(rec, dict):
      continue

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
    entry = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else {}

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

    raw_time = (
        sub.get("Time")
        or sub.get("time")
        or entry.get("Time")
        or ""
    )
    raw_time_str = str(raw_time).strip()
    
    if raw_time_str and len(raw_time_str) >= 3:
      if "T" in raw_time_str:
        try:
          t_part = raw_time_str.split("T")[1][:5]
          t_obj = datetime.strptime(t_part, "%H:%M")
          time_clean = t_obj.strftime("%I:%M %p")
        except Exception:
          time_clean = raw_time_str[-8:]
      else:
        time_clean = raw_time_str
    else:
      if pd.notna(parsed_dt):
        if parsed_dt.tzinfo is None:
          dt_ist = parsed_dt + timedelta(hours=5, minutes=30)
        else:
          dt_ist = parsed_dt.tz_convert("Asia/Kolkata")
        time_clean = dt_ist.strftime("%I:%M %p")
      else:
        time_clean = "Shift Log"

    location = str(sub.get("Location") or entry.get("Location") or "").strip()

    raw_unit = (
        entry.get("Fridge")
        or entry.get("Freezer")
        or entry.get("Coolroom")
        or sub.get("Fridge")
        or sub.get("Freezer")
        or sub.get("Coolroom")
        or ""
    )
    if isinstance(raw_unit, list) and len(raw_unit) > 0:
      raw_unit = raw_unit[0]
    raw_unit_str = str(raw_unit).strip()

    clean_u = clean_unit_token(raw_unit_str)
    matched_id = None
    matched_loc = location
    matched_type = str(entry.get("Type") or sub.get("Coolroom/Fridge/Freezer") or "Fridge").capitalize()

    for m in flat_master:
      if clean_u == m["Clean_ID"]:
        matched_id = m["Unit_ID"]
        matched_loc = m["Location"]
        matched_type = m["Type"]
        break

    final_unit = matched_id if matched_id else raw_unit_str

    status_raw = str(entry.get("USE") or sub.get("USE") or "IN USE").strip().upper()
    is_in_use = "NOT" not in status_raw

    num_temp = extract_temp_value(entry, sub)
    has_breach = False
    temp_disp = "—"

    if is_in_use and num_temp is not None:
      temp_disp = f"{num_temp}°C"
      if "freezer" in matched_type.lower():
        if num_temp > MAX_FREEZER_TEMP:
          has_breach = True
      else:
        if num_temp > MAX_FRIDGE_TEMP:
          has_breach = True

    sign = str(sub.get("Sign") or entry.get("Sign") or sub.get("sign") or "Staff").strip()

    rows.append({
        "Date_Str": date_str,
        "Date_Obj": date_obj,
        "Timestamp_DT": parsed_dt_ist,
        "Time": time_clean,
        "Location": matched_loc,
        "Unit_ID": final_unit,
        "Clean_Unit": clean_unit_token(final_unit),
        "Unit_Type": matched_type,
        "In_Use": is_in_use,
        "Temp": num_temp,
        "Temp_Disp": temp_disp,
        "Has_Breach": has_breach,
        "Sign": sign,
    })

  df = pd.DataFrame(rows)
  if not df.empty:
    df = df.drop_duplicates(subset=["Date_Str", "Time", "Clean_Unit", "Temp", "Sign"], keep="first")
  return df


def render_record_03_view(raw_df, selected_day_str, start_date, end_date):
  df_items = parse_record_03_submissions(raw_df)

  with st.expander("🔍 Date Diagnostic (Inspect dates loaded in memory)"):
    st.write(f"Total parsed records: **{len(df_items)}**")
    if not df_items.empty and "Date_Obj" in df_items.columns:
      date_counts = df_items["Date_Obj"].dropna().value_counts().sort_index(ascending=False).to_dict()
      st.write("Records per date found:", {str(k): v for k, v in date_counts.items()})
    else:
      st.write("No valid dates found in the payload.")

  tab_day, tab_matrix = st.tabs([
      f"📅 Daily Unit Temperature Audit ({selected_day_str})",
      "📈 7-Day Grouped Location Matrix"
  ])

  with tab_day:
    target_date_obj = datetime.strptime(selected_day_str, "%d/%m/%Y").date()
    next_date_obj = target_date_obj + timedelta(days=1)

    if not df_items.empty:
      day_df = df_items[
          (df_items["Date_Obj"] == target_date_obj) |
          ((df_items["Date_Obj"] == next_date_obj) & (df_items["Timestamp_DT"].dt.hour < 5))
      ]
    else:
      day_df = pd.DataFrame()

    total_breaches = 0
    fully_logged_areas = 0
    total_catalog_locations = len(UNIT_CATALOG)

    loc_summary_data = []
    global_opening_logged = 0
    global_closing_logged = 0
    global_total_units = 0

    for loc_name, units in UNIT_CATALOG.items():
      total_u = len(units)
      global_total_units += total_u
      opening_logged = []
      closing_logged = []
      pending_opening = []
      pending_closing = []
      loc_breaches = 0

      for u in units:
        u_id = u["Unit_ID"]
        u_type = u["Type"]
        clean_target = clean_unit_token(u_id)
        unit_logs = day_df[day_df["Clean_Unit"] == clean_target] if not day_df.empty else pd.DataFrame()
        
        if any(unit_logs["Has_Breach"]):
          loc_breaches += 1
          total_breaches += 1

        n_logs = len(unit_logs)
        if n_logs == 0:
          pending_opening.append(f"{u_id} ({u_type})")
          pending_closing.append(f"{u_id} ({u_type})")
        elif n_logs == 1:
          opening_logged.append(u_id)
          global_opening_logged += 1
          pending_closing.append(f"{u_id} ({u_type})")
        else:
          opening_logged.append(u_id)
          closing_logged.append(u_id)
          global_opening_logged += 1
          global_closing_logged += 1

      op_count = len(opening_logged)
      cl_count = len(closing_logged)
      
      if op_count == total_u and cl_count == total_u and loc_breaches == 0:
        fully_logged_areas += 1

      loc_summary_data.append({
          "loc_name": loc_name,
          "units": units,
          "total_u": total_u,
          "op_count": op_count,
          "cl_count": cl_count,
          "pending_opening": pending_opening,
          "pending_closing": pending_closing,
          "loc_breaches": loc_breaches
      })

    k1, k2, k3, k4 = st.columns(4)
    with k1:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #dc2626;"><div class="kpi-num" style="color:#dc2626;">{total_breaches}</div><div class="kpi-lbl">Temperature Breaches</div></div>', unsafe_allow_html=True)
    with k2:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #16a34a;"><div class="kpi-num" style="color:#16a34a;">{fully_logged_areas}/{total_catalog_locations}</div><div class="kpi-lbl">Fully Logged Areas</div></div>', unsafe_allow_html=True)
    with k3:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #d97706;"><div class="kpi-num" style="color:#d97706;">{max(0, global_total_units * 2 - (global_opening_logged + global_closing_logged))}</div><div class="kpi-lbl">Pending Shifts</div></div>', unsafe_allow_html=True)
    with k4:
      st.markdown(f'<div class="kpi-container" style="border-top-color: #0f172a;"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Count</div></div>', unsafe_allow_html=True)

    st.write("")
    st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>📋 Shift Status Across Locations ({selected_day_str})</h4>", unsafe_allow_html=True)

    shift_col1, shift_col2 = st.columns(2)

    with shift_col1:
      op_items_html = ""
      for item in loc_summary_data:
        l_name = item["loc_name"]
        c_op = item["op_count"]
        t_u = item["total_u"]
        if c_op == t_u:
          badge = f"<span style='color:#16a34a; font-weight:700; float:right;'>✓ Completed ({c_op}/{t_u})</span>"
        else:
          badge = f"<span style='color:#d97706; font-weight:700; float:right;'>⏳ Pending ({c_op}/{t_u})</span>"
        op_items_html += f"<div style='padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.85rem;'><b>{l_name}</b> {badge}</div>"

      st.markdown(f"""
      <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:4px solid #16a34a; border-radius:6px; padding:12px 16px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-weight:700; font-size:0.95rem; color:#15803d; margin-bottom:8px; display:flex; justify-content:space-between;">
              <span>🌅 Opening Shift</span>
              <span>{global_opening_logged}/{global_total_units} Units</span>
          </div>
          {op_items_html}
      </div>
      """, unsafe_allow_html=True)

    with shift_col2:
      cl_items_html = ""
      for item in loc_summary_data:
        l_name = item["loc_name"]
        c_cl = item["cl_count"]
        t_u = item["total_u"]
        if c_cl == t_u:
          badge = f"<span style='color:#16a34a; font-weight:700; float:right;'>✓ Completed ({c_cl}/{t_u})</span>"
        else:
          badge = f"<span style='color:#d97706; font-weight:700; float:right;'>⏳ Pending ({c_cl}/{t_u})</span>"
        cl_items_html += f"<div style='padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.85rem;'><b>{l_name}</b> {badge}</div>"

      st.markdown(f"""
      <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:4px solid #0284c7; border-radius:6px; padding:12px 16px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-weight:700; font-size:0.95rem; color:#0369a1; margin-bottom:8px; display:flex; justify-content:space-between;">
              <span>🌙 Closing Shift</span>
              <span>{global_closing_logged}/{global_total_units} Units</span>
          </div>
          {cl_items_html}
      </div>
      """, unsafe_allow_html=True)

    st.write("")
    st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>🏢 Location Summary Blocks ({selected_day_str})</h4>", unsafe_allow_html=True)
    st.caption("Each location summary block tracks Opening & Closing logs and displays pending units.")

    loc_cols = st.columns(2)
    for idx, item in enumerate(loc_summary_data):
      col_target = loc_cols[idx % 2]
      loc_name = item["loc_name"]
      total_u = item["total_u"]
      op_count = item["op_count"]
      cl_count = item["cl_count"]
      pending_opening = item["pending_opening"]
      pending_closing = item["pending_closing"]
      loc_breaches = item["loc_breaches"]

      if loc_breaches > 0:
        compliance_badge = "<span style='color:#dc2626; font-weight:700; font-size:0.75rem; float:right;'>🔴 BREACH</span>"
      elif op_count < total_u or cl_count < total_u:
        compliance_badge = "<span style='color:#d97706; font-weight:700; font-size:0.75rem; float:right;'>⏳ PENDING</span>"
      else:
        compliance_badge = "<span style='color:#16a34a; font-weight:700; font-size:0.75rem; float:right;'>🟢 Fully Compliant</span>"

      pending_op_html = "".join([f"<div style='font-size:0.75rem; color:#b45309; margin-left:8px; margin-top:2px;'>• {p_item}</div>" for p_item in pending_opening]) if pending_opening else "<div style='font-size:0.75rem; color:#16a34a; margin-top:2px; margin-left:8px;'>• All units logged for opening.</div>"
      
      pending_cl_html = "".join([f"<div style='font-size:0.75rem; color:#b45309; margin-left:8px; margin-top:2px;'>• {p_item}</div>" for p_item in pending_closing]) if pending_closing else "<div style='font-size:0.75rem; color:#16a34a; margin-top:2px; margin-left:8px;'>• All units logged for closing.</div>"

      col_target.markdown(f"""
      <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:4px solid #0f172a; border-radius:6px; padding:12px 16px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-weight:700; font-size:1rem; color:#0f172a; border-bottom:1px solid #f1f5f9; padding-bottom:6px; margin-bottom:10px;">
              📍 {loc_name} <span style="font-size:0.75rem; color:#64748b; font-weight:normal; margin-left:6px;">({total_u} Units)</span> {compliance_badge}
          </div>
          <div style="background:#f8fafc; border-left:3px solid #16a34a; padding:8px 10px; border-radius:4px; margin-bottom:8px;">
              <div style="font-size:0.85rem; color:#15803d; font-weight:700; display:flex; justify-content:space-between;">
                  <span>🌅 Opening Shift</span><span>{op_count}/{total_u} Logged</span>
              </div>
              <div style="margin-top:4px;">{pending_op_html}</div>
          </div>
          <div style="background:#f8fafc; border-left:3px solid #0284c7; padding:8px 10px; border-radius:4px; margin-bottom:4px;">
              <div style="font-size:0.85rem; color:#0369a1; font-weight:700; display:flex; justify-content:space-between;">
                  <span>🌙 Closing Shift</span><span>{cl_count}/{total_u} Logged</span>
              </div>
              <div style="margin-top:4px;">{pending_cl_html}</div>
          </div>
      </div>
      """, unsafe_allow_html=True)

  with tab_matrix:
    total_days = max(1, (end_date - start_date).days + 1)
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]
    max_page = max(0, (total_days - 1) // 7)

    if "rec03_page" not in st.session_state or st.session_state.rec03_page > max_page:
      st.session_state.rec03_page = max_page

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
      if st.button("⬅️ Previous 7 Days", key="r03_prev", disabled=(st.session_state.rec03_page <= 0), use_container_width=True):
        st.session_state.rec03_page -= 1
        st.rerun()

    with nav3:
      if st.button("Next 7 Days ➡️", key="r03_next", disabled=(st.session_state.rec03_page >= max_page), use_container_width=True):
        st.session_state.rec03_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec03_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]
    if not page_dates:
      page_dates = all_dates[-7:]

    with nav2:
      st.markdown(
          f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
          f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b>"
          f"</div>",
          unsafe_allow_html=True
      )

    st.write("")
    all_catalog_locs = list(UNIT_CATALOG.keys())
    sel_loc = st.selectbox("📍 Select Kitchen Area to Audit (or view All):", ["All Locations"] + all_catalog_locs)
    locations_to_show = all_catalog_locs if sel_loc == "All Locations" else [sel_loc]

    num_dates = len(page_dates)
    col_ratios = [2.0] + [1.0] * num_dates

    for location in locations_to_show:
      units = UNIT_CATALOG.get(location, [])
      st.markdown(f"""
      <div style="background:#0f172a; color:#ffffff; padding:10px 14px; border-radius:6px; margin-top:1.4rem; margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:700; font-size:0.98rem;">❄️ {location}</span>
          <span style="font-size:0.8rem; background:#334155; padding:3px 10px; border-radius:12px;">{len(units)} Assigned Units</span>
      </div>
      """, unsafe_allow_html=True)

      cols = st.columns(col_ratios)
      cols[0].markdown('<div style="font-weight:700; font-size:0.80rem; color:#475569; padding:6px 2px;">Appliance Unit</div>', unsafe_allow_html=True)
      for i, d in enumerate(page_dates):
        cols[i + 1].markdown(f'<div style="background:#f1f5f9; font-weight:700; font-size:0.80rem; text-align:center; padding:6px 2px; border-radius:4px; color:#0f172a;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

      st.write("")

      for u in units:
        unit_id = u["Unit_ID"]
        unit_type = u["Type"]
        clean_target = clean_unit_token(unit_id)
        row_cols = st.columns(col_ratios)

        row_cols[0].markdown(f"""
        <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:8px 8px; min-height:82px; display:flex; flex-direction:column; justify-content:center;">
            <div style="font-weight:700; font-size:0.84rem; color:#0f172a;">{unit_id}</div>
            <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">{unit_type}</div>
        </div>
        """, unsafe_allow_html=True)

        u_df = df_items[df_items["Clean_Unit"] == clean_target] if not df_items.empty else pd.DataFrame()

        for i, d in enumerate(page_dates):
          matches = pd.DataFrame()
          if not u_df.empty and "Date_Obj" in u_df.columns:
            matches = u_df[u_df["Date_Obj"] == d]

          if matches.empty:
            row_cols[i + 1].markdown(
                '<div style="background:#f8fafc; border:1px dashed #cbd5e1; border-radius:6px; padding:6px; min-height:82px; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:0.75rem;">— Not Logged</div>',
                unsafe_allow_html=True
            )
          else:
            entries = matches.sort_values(by="Time").to_dict("records")
            has_day_breach = any(e["Has_Breach"] for e in entries)

            distinct_shifts = []
            for ent in entries:
              if not distinct_shifts:
                distinct_shifts.append(ent)
              else:
                if ent["Time"] != distinct_shifts[-1]["Time"]:
                  distinct_shifts.append(ent)

            if has_day_breach:
              status_tag = '<span style="color:#dc2626; font-weight:800; font-size:0.75rem;">🔴 BREACH</span>'
              border_color = "#dc2626"
            elif len(distinct_shifts) >= 2:
              status_tag = '<span style="color:#16a34a; font-weight:800; font-size:0.75rem;">✓ 2 of 2 Logged</span>'
              border_color = "#16a34a"
            else:
              status_tag = '<span style="color:#0284c7; font-weight:700; font-size:0.74rem;">1 of 2 Logged</span>'
              border_color = "#94a3b8"

            readings_str = ""
            for idx, ent in enumerate(distinct_shifts[:2]):
              t_color = "#dc2626" if ent["Has_Breach"] else "#0f172a"
              t_val = ent["Temp_Disp"]
              t_time = ent["Time"][:8]
              readings_str += f'<div style="display:flex; justify-content:space-between; font-size:0.72rem; margin-top:2px;"><span style="color:#64748b;">#{idx+1} ({t_time})</span><b style="color:{t_color};">{t_val}</b></div>'

            footer_info = f"By: {distinct_shifts[0]['Sign']}"

            row_cols[i + 1].markdown(
                f'<div style="background:#ffffff; border:1.5px solid {border_color}; border-radius:6px; padding:6px 6px; min-height:82px; box-shadow:0 1px 2px rgba(0,0,0,0.05);">'
                f'<div style="text-align:center; padding-bottom:3px; border-bottom:1px solid #f1f5f9;">{status_tag}</div>'
                f'{readings_str}'
                f'<div style="font-size:0.65rem; color:#64748b; text-align:right; margin-top:3px;">{footer_info}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

      st.write("")
