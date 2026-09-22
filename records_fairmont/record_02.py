from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

CHILLED_MAX_TEMP = 5.0  # Chilled food items must arrive <= 5.0°C
RECORD_02_FORM_ID = 23703


def parse_record_02_submissions(raw_df):
  """Parses Record 02 Food Delivery submissions handling nested repeatable sets for items and top-level supplier info."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_02_FORM_ID), na=False)
    ]

  if df.empty:
    df = raw_df.copy()

  rows = []
  for _, record in df.iterrows():
    rec = record.get("raw_record") if "raw_record" in raw_df.columns else record.to_dict()
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

    location = str(
        sub.get("Location")
        or sub.get("location")
        or "Receiving Area"
    ).strip()

    sup_main = str(
        sub.get("Name_of_Supplier")
        or sub.get("Name of Supplier")
        or ""
    ).strip()

    sup_other = str(
        sub.get("Supplier")
        or sub.get("Name of Supplier (Other)")
        or sub.get("Name_of_Supplier_Other")
        or ""
    ).strip()

    if sup_other and sup_other.lower() not in ["none", "nan", ""]:
      supplier = sup_other
    elif sup_main and sup_main.lower() not in ["other", "none", "nan", ""]:
      supplier = sup_main
    else:
      supplier = "Local Supplier"

    sign = str(
        sub.get("Sign")
        or sub.get("sign")
        or sub.get("Sign (Initial)")
        or "Staff"
    ).strip()

    entries = sub.get("set") or sub.get("Entry") or sub.get("items") or [sub]
    if isinstance(entries, dict):
      entries = [entries]
    elif not isinstance(entries, list):
      entries = [sub] if isinstance(sub, dict) else []

    for e in entries:
      if not isinstance(e, dict):
        e = sub

      delivery_type = str(
          e.get("Delivery_Type")
          or e.get("Delivery Type")
          or "Perishable"
      ).strip()

      food_type = str(
          e.get("Food_Type")
          or e.get("Food Type")
          or "Goods Received"
      ).replace("•", "").strip()

      temp_req_raw = str(
          e.get("Temperaturerq")
          or e.get("Temperature req")
          or e.get("Is a Temperature Required?")
          or "Yes"
      ).strip().upper()
      temp_required = "NO" not in temp_req_raw

      temp_val_raw = (
          e.get("Perishable_Temperature")
          or e.get("Perishable_Temperature_frozen")
          or e.get("Temperature °C")
          or e.get("Temperature")
      )
      temp_num = pd.to_numeric(str(temp_val_raw).replace("°C", "").strip(), errors="coerce")

      limits_raw = str(
          e.get("Packaging_Standards")
          or e.get("Critical Limits")
          or "Yes"
      ).strip().upper()
      condition_ok = "NO" not in limits_raw

      has_temp_breach = temp_required and pd.notna(temp_num) and (temp_num > CHILLED_MAX_TEMP)
      has_breach = has_temp_breach or (not condition_ok)

      rows.append({
          "Date_Str": date_str,
          "Date_Obj": date_obj,
          "Location": location,
          "Supplier": supplier,
          "Delivery_Type": delivery_type,
          "Food_Type": food_type,
          "Temp_Required": temp_required,
          "Temp": temp_num,
          "Temp_Disp": f"{temp_num}°C" if pd.notna(temp_num) else "Ambient",
          "Condition_OK": condition_ok,
          "Has_Breach": has_breach,
          "Sign": sign,
      })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(subset=["Date_Str", "Supplier", "Food_Type", "Temp"], keep="first")
  return df_out


def render_record_02_view(raw_df, selected_day_str, start_date, end_date):
  """Renders Record 02 Daily Audit and Weekly Card Matrix with Supplier grouping & individual item temperatures."""

  df_items = parse_record_02_submissions(raw_df)

  with st.expander("🔍 Record 02 API & Ingestion Diagnostic", expanded=False):
    st.write(f"Total Parsed Delivery Rows: **{len(df_items)}**")
    if not df_items.empty:
      st.dataframe(df_items.head(10), use_container_width=True)

  if not df_items.empty and "Date_Obj" in df_items.columns and df_items["Date_Obj"].notna().any():
    range_df = df_items[
        (df_items["Date_Obj"] >= start_date)
        & (df_items["Date_Obj"] <= end_date)
    ]
  else:
    range_df = df_items.copy()

  tab_day, tab_matrix = st.tabs([
      f"Today - {selected_day_str}",
      "Weekly"
  ])

  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    excursions = []
    compliant_deliveries = []

    if not day_df.empty:
      for _, r in day_df.iterrows():
        if r["Has_Breach"]:
          excursions.append(r.to_dict())
        else:
          compliant_deliveries.append(r.to_dict())

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">Delivery Temp Breaches</div></div>', unsafe_allow_html=True)
    with k2:
      st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_deliveries)}</div><div class="kpi-lbl">Verified Deliveries</div></div>', unsafe_allow_html=True)
    with k3:
      st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Items Received</div></div>', unsafe_allow_html=True)

    st.write("")
    st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>📦 Food Delivery Audit Cards ({selected_day_str})</h4>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
      st.markdown('<div style="font-weight:700; color:#dc2626; margin-bottom:8px;">🔴 Rejected / Excursions</div>', unsafe_allow_html=True)
      if excursions:
        for exc in excursions:
          err_msg = f"Temp: {exc['Temp_Disp']} (> 5°C)" if exc['Temp'] and exc['Temp'] > CHILLED_MAX_TEMP else "Packaging / Label Issue"
          st.markdown(f'<div style="background:#ffffff; border:1px solid #fca5a5; border-left:4px solid #dc2626; padding:12px; border-radius:6px; margin-bottom:10px;"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">📦 {exc["Food_Type"]}</div><div style="font-size:0.8rem; color:#475569;">Supplier: <b>{exc["Supplier"]}</b> | Temp: <b>{exc["Temp_Disp"]}</b></div><div style="font-size:0.85rem; color:#dc2626; font-weight:700; margin-top:4px;">{err_msg}</div><div style="font-size:0.75rem; color:#64748b; margin-top:4px;">Received By: {exc["Sign"]}</div></div>', unsafe_allow_html=True)
      else:
        st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem; text-align:center;">All incoming goods arrived within critical temperature limits.</div>', unsafe_allow_html=True)

    with c2:
      st.markdown('<div style="font-weight:700; color:#16a34a; margin-bottom:8px;">🟢 Accepted Compliant</div>', unsafe_allow_html=True)
      if compliant_deliveries:
        for ok in compliant_deliveries:
          st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:4px solid #16a34a; padding:12px; border-radius:6px; margin-bottom:10px;"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">📦 {ok["Food_Type"]}</div><div style="font-size:0.8rem; color:#334155; margin-top:2px;">Supplier: <b>{ok["Supplier"]}</b> | Temp: <b style="color:#16a34a;">{ok["Temp_Disp"]}</b></div><div style="font-size:0.75rem; color:#64748b; margin-top:4px;">Type: {ok["Delivery_Type"]} | Received By: {ok["Sign"]}</div></div>', unsafe_allow_html=True)
      else:
        st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem; text-align:center;">No deliveries logged for this date.</div>', unsafe_allow_html=True)

  with tab_matrix:
    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec02_page" not in st.session_state:
      st.session_state.rec02_page = max(0, (total_days - 1) // 7)

    max_page = max(0, (total_days - 1) // 7)

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
      if st.button("⬅️ Previous 7 Days", key="r02_prev", disabled=(st.session_state.rec02_page <= 0), use_container_width=True):
        st.session_state.rec02_page -= 1
        st.rerun()

    with nav3:
      if st.button("Next 7 Days ➡️", key="r02_next", disabled=(st.session_state.rec02_page >= max_page), use_container_width=True):
        st.session_state.rec02_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec02_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with nav2:
      if page_dates:
        st.markdown(f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec02_page + 1} of {max_page + 1})</div>", unsafe_allow_html=True)

    st.write("")

    cols = st.columns(7)
    for i, d in enumerate(page_dates):
      cols[i].markdown(f'<div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.82rem; padding:10px 2px; border-radius:6px; text-align:center; margin-bottom:8px;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

    for i, d in enumerate(page_dates):
      d_str = d.strftime("%d/%m/%Y")
      matches = pd.DataFrame()
      if not range_df.empty:
        if "Date_Obj" in range_df.columns:
          matches = range_df[range_df["Date_Obj"] == d]
        if matches.empty and "Date_Str" in range_df.columns:
          matches = range_df[range_df["Date_Str"] == d_str]

      with cols[i]:
        if matches.empty:
          st.markdown('<div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:12px 6px; text-align:center; min-height:160px; display:flex; align-items:center; justify-content:center;"><span style="color:#94a3b8; font-weight:600; font-size:0.82rem;">— No Deliveries</span></div>', unsafe_allow_html=True)
        else:
          batch_count = len(matches)
          has_day_breach = any(matches["Has_Breach"])

          # Group items by Supplier and render clubbed cards
          grouped_suppliers = matches.groupby("Supplier")
          suppliers_html = ""
          for sup_name, group_df in grouped_suppliers:
            items_str = ", ".join(group_df["Food_Type"].tolist())
            t_sample = group_df["Temp_Disp"].iloc[0]
            suppliers_html += f'<div style="background:#f8fafc; border-left:3px solid #0f172a; border-radius:4px; padding:5px 6px; margin-top:4px; text-align:left;"><div style="font-size:0.72rem; font-weight:700; color:#0f172a;">🏢 {sup_name}</div><div style="font-size:0.68rem; color:#334155; margin-top:1px;">📦 {items_str}</div><div style="font-size:0.65rem; color:#16a34a; font-weight:600; margin-top:1px;">Temp: {t_sample}</div></div>'

          signs = ", ".join(list(dict.fromkeys(matches["Sign"].dropna().tolist())))
          badge = f'<span style="color:#dc2626; font-weight:800; font-size:0.85rem;">🔴 {batch_count} Items</span>' if has_day_breach else f'<span style="color:#16a34a; font-weight:800; font-size:0.85rem;">✓ {batch_count} Items</span>'
          card_border = "2px solid #dc2626" if has_day_breach else "1.5px solid #0f172a"

          st.markdown(f'<div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:8px 6px; text-align:center; min-height:160px; box-shadow:0 1px 3px rgba(0,0,0,0.08);"><div>{badge}</div><div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>{suppliers_html}<div style="font-size:0.65rem; color:#64748b; margin-top:6px;">By: {signs}</div></div>', unsafe_allow_html=True)

    st.divider()
    with st.expander("📋 View All Individual Food Delivery Records (Table View)"):
      if not range_df.empty:
        show_cols = [c for c in ["Date_Str", "Supplier", "Food_Type", "Delivery_Type", "Temp_Disp", "Condition_OK", "Sign"] if c in range_df.columns]
        st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
