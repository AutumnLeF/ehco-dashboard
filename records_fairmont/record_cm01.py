from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_CM01_FORM_ID = 24144

RECORD_CM01_LOCATIONS = [
    "Banquet",
    "Bombay Café",
    "Merchants",
    "Grand Terminus",
    "Samaa",
    "IRD",
    "Gold Lounge",
    "Madeleine de Proust",
]


def parse_record_cm01_submissions(raw_df):
  """Robustly parses Record CM01 Coffee Machine Cleaning submissions."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_CM01_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  rows = []
  for _, record in df.iterrows():
    rec = record.get("raw_record") if "raw_record" in record.to_dict() else record.to_dict()
    if not isinstance(rec, dict):
      rec = record.to_dict()

    sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
    loc_parent = sub.get("Locations") if isinstance(sub.get("Locations"), dict) else {}

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

    time_raw = str(sub.get("Time") or rec.get("dateTimeSubmitted") or "")
    if "T" in time_raw:
      try:
        dt_time = pd.to_datetime(time_raw, errors="coerce")
        if pd.notna(dt_time):
          dt_time_ist = dt_time + timedelta(hours=5, minutes=30)
          time_str = dt_time_ist.strftime("%I:%M %p")
        else:
          time_str = time_raw.split("T")[1][:5]
      except:
        time_str = time_raw[:8]
    else:
      time_str = time_raw[:8]

    location = str(
        loc_parent.get("Location")
        or sub.get("Location")
        or rec.get("Location")
        or "Banquet"
    ).strip()

    sub_loc = str(loc_parent.get("Location_B") or sub.get("Location_B") or "").strip()
    shift = str(sub.get("Shift") or sub.get("Shift_Name") or "Shift AM").strip()
    sign = str(sub.get("Sign_initial") or sub.get("Sign") or rec.get("user.email") or "Staff").strip()

    # Checklist items
    bean_dispenser = str(loc_parent.get("Coffee_bean_dispenser") or "No")
    refrigerator = str(loc_parent.get("Refrigerator_unit") or "No")
    sink_tray = str(loc_parent.get("Sink_tray") or "No")
    steam_pipe = str(loc_parent.get("Steam_pipe_sanitation") or "No")
    suma_vend = str(loc_parent.get("Suma_vend_tab") or "No")
    waste_col = str(loc_parent.get("Waste_collector") or "No")
    chemical = str(loc_parent.get("Name_of_Chemical_") or "Cafetto")

    rows.append({
        "Date_Str": date_str,
        "Date_Obj": date_obj,
        "Time": time_str,
        "Location": location,
        "Sub_Location": sub_loc,
        "Shift": shift,
        "Sign": sign,
        "Chemical": chemical,
        "Bean_Dispenser": bean_dispenser,
        "Refrigerator": refrigerator,
        "Sink_Tray": sink_tray,
        "Steam_Pipe": steam_pipe,
        "Suma_Vend": suma_vend,
        "Waste_Collector": waste_col,
    })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Sign"], keep="first")
  return df_out


def render_record_cm01_view(raw_df, selected_day_str, start_date, end_date):
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

  df_items = parse_record_cm01_submissions(raw_df)

  with st.expander("🔍 Record CM01 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed coffee machine cleaning records: **{len(df_items)}**")
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
      f"📅 Daily Cleaning Audit ({selected_day_str})",
      "📈 7-Day Matrix",
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    total_cleaned = len(day_df)
    unique_locations = day_df["Location"].nunique() if not day_df.empty else 0

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{total_cleaned}</div>
                <div class="kpi-lbl">Total Cleaning Logs</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0284c7;">
                <div class="kpi-num" style="color:#0284c7;">{unique_locations}</div>
                <div class="kpi-lbl">Active Locations Logged</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0f172a;">
                <div class="kpi-num" style="color:#0f172a;">{len(RECORD_CM01_LOCATIONS)}</div>
                <div class="kpi-lbl">Catalog Locations</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")
    st.markdown(
        "<h4 style='color:#16a34a; margin-top:1.5rem; margin-bottom:1rem;'>✅"
        f" Coffee Machine Cleaning Entries ({selected_day_str})</h4>",
        unsafe_allow_html=True,
    )

    if day_df.empty:
      st.info("No coffee machine cleaning logs submitted for this date.")
    else:
      c_cols = st.columns(3, gap="small")
      for idx, (_, r) in enumerate(day_df.iterrows()):
        col_target = c_cols[idx % 3]
        card_html = textwrap.dedent(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #16a34a; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
                    <span style="font-size:0.9rem; font-weight:700; color:#0f172a;">📍 {r["Location"]} {f"({r['Sub_Location']})" if r['Sub_Location'] else ""}</span>
                    <span style="color:#0284c7; font-weight:700; font-size:0.75rem;">{r["Shift"]}</span>
                </div>
                <div style="margin-top:6px; font-size:0.75rem; color:#334155;">
                    <div><b>Time:</b> {r["Time"]}</div>
                    <div><b>Chemical:</b> {r["Chemical"]}</div>
                    <div style="margin-top:4px; color:#64748b;">
                        Sanitation: Bean Dispenser ({r["Bean_Dispenser"]}) | Refrigerator ({r["Refrigerator"]}) | Steam Pipe ({r["Steam_Pipe"]})
                    </div>
                </div>
                <div style="font-size:0.68rem; color:#64748b; margin-top:8px; border-top:1px solid #f1f5f9; padding-top:4px;">
                    <b>Signed By:</b> {r["Sign"]}
                </div>
            </div>
        """).strip()
        col_target.markdown(card_html, unsafe_allow_html=True)

  with tab_matrix:
    st.subheader("7-Day Coffee Machine Cleaning Matrix")
    if not range_df.empty:
      st.dataframe(range_df, use_container_width=True, hide_index=True)
    else:
      st.info("No records found in the selected date range.")
