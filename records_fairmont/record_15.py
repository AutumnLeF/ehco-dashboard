from datetime import datetime, timedelta
import textwrap
import pandas as pd
import streamlit as st

RECORD_15_FORM_ID = 23717  # Form ID for Pesticide Usage Record


def parse_record_15_submissions(raw_df):
  """Parses Record 15 Pesticide Usage submissions into a normalized DataFrame."""
  if raw_df is None or raw_df.empty:
    return pd.DataFrame()

  df = raw_df.copy()
  form_col = next(
      (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
      None,
  )
  if form_col:
    df = df[
        df[form_col].astype(str).str.contains(str(RECORD_15_FORM_ID), na=False)
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

    raw_date = (
        sub.get("Date of Visit")
        or sub.get("DateOfVisit")
        or sub.get("Date")
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

    company = (
        sub.get("Company")
        or sub.get("Vendor")
        or rec.get("Company")
        or "Rentokil PCI"
    )
    tech_name = (
        sub.get("Technician Name")
        or sub.get("TechnicianName")
        or sub.get("Technician")
        or "Technician"
    )
    areas_treated = (
        sub.get("Areas Treated")
        or sub.get("AreasTreated")
        or sub.get("Location")
        or "General Areas"
    )
    chemical = (
        sub.get("Chemical Used")
        or sub.get("ChemicalUsed")
        or sub.get("Chemical")
        or "Chemical"
    )
    amount = (
        sub.get("Amount of Chemical Used")
        or sub.get("AmountOfChemicalUsed")
        or sub.get("Amount")
        or "—"
    )
    method = (
        sub.get("Method of Application")
        or sub.get("MethodOfApplication")
        or sub.get("Method")
        or "Spray"
    )
    batch = (
        sub.get("Batch Codes of Chemical")
        or sub.get("BatchCodesOfChemical")
        or sub.get("Batch")
        or "—"
    )
    sign = (
        sub.get("Sign (Initial)")
        or sub.get("Sign")
        or sub.get("sign")
        or tech_name
    )

    rows.append({
        "Date_Str": date_str,
        "Date_Obj": date_obj,
        "Company": str(company).strip(),
        "Technician": str(tech_name).strip(),
        "Areas_Treated": str(areas_treated).strip(),
        "Chemical": str(chemical).strip(),
        "Amount": str(amount).strip(),
        "Method": str(method).strip(),
        "Batch": str(batch).strip(),
        "Sign": str(sign).strip(),
    })

  df_out = pd.DataFrame(rows)
  if not df_out.empty:
    df_out = df_out.drop_duplicates(
        subset=[
            "Date_Str",
            "Company",
            "Technician",
            "Areas_Treated",
            "Chemical",
            "Batch",
        ],
        keep="first",
    )
  return df_out


def render_record_15_view(raw_df, selected_day_str, start_date, end_date):
  """Renders Record 15 single-day service visit audit and 7-day facility matrix."""
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

  df_items = parse_record_15_submissions(raw_df)

  with st.expander("🔍 Record 15 Diagnostic (Inspect loaded data)"):
    st.write(f"Total parsed pesticide records: **{len(df_items)}**")
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
      f"📅 Daily Service Visit ({selected_day_str})",
      "📈 7-Day Treatment Matrix",
  ])

  # -------------------------------------------------------------
  # TAB 1: DAILY DRILLDOWN
  # -------------------------------------------------------------
  with tab_day:
    day_df = (
        range_df[range_df["Date_Str"] == selected_day_str]
        if not range_df.empty
        else pd.DataFrame()
    )

    k1, k2, k3 = st.columns(3)
    with k1:
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #0f172a;">
                <div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div>
                <div class="kpi-lbl">Applications Logged</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k2:
      tech_count = day_df["Technician"].nunique() if not day_df.empty else 0
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #16a34a;">
                <div class="kpi-num" style="color:#16a34a;">{tech_count}</div>
                <div class="kpi-lbl">Technicians On Site</div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with k3:
      chem_count = day_df["Chemical"].nunique() if not day_df.empty else 0
      st.markdown(
          f"""
            <div class="kpi-container" style="border-top-color: #2563eb;">
                <div class="kpi-num" style="color:#2563eb;">{chem_count}</div>
                <div class="kpi-lbl">Chemicals Applied</div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.write("")

    if not day_df.empty:
      for _, r in day_df.iterrows():
        st.markdown(
            textwrap.dedent(f"""
                <div style="background:#ffffff; border:1px solid #cbd5e1; border-left:5px solid #0f172a; border-radius:6px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; font-size:0.95rem; color:#0f172a;">🏢 {r['Areas_Treated']}</span>
                        <span style="background:#f1f5f9; color:#475569; padding:2px 8px; border-radius:4px; font-weight:600; font-size:0.75rem;">{r['Method']}</span>
                    </div>
                    <div style="font-size:0.85rem; color:#1e293b; margin-top:5px;">
                        Chemical: <b>{r['Chemical']}</b> ({r['Amount']}) &nbsp;|&nbsp; Batch: <code style="font-size:0.78rem;">{r['Batch']}</code>
                    </div>
                    <div style="font-size:0.75rem; color:#64748b; margin-top:4px;">
                        Contractor: <b>{r['Company']}</b> &nbsp;|&nbsp; Technician: {r['Technician']} &nbsp;|&nbsp; Initial: {r['Sign']}
                    </div>
                </div>
            """).strip(),
            unsafe_allow_html=True,
        )
    else:
      st.info("No pest control treatment logged for this date.")

  # -------------------------------------------------------------
  # TAB 2: 7-DAY FULL-WIDTH DAILY TREATMENT CARDS
  # -------------------------------------------------------------
  with tab_matrix:
    total_days = (end_date - start_date).days + 1
    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if "rec15_page" not in st.session_state:
      st.session_state.rec15_page = max(0, (total_days - 1) // 7)

    max_page = max(0, (total_days - 1) // 7)

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
      if st.button(
          "⬅️ Previous 7 Days",
          key="r15_prev",
          disabled=(st.session_state.rec15_page <= 0),
          use_container_width=True,
      ):
        st.session_state.rec15_page -= 1
        st.rerun()

    with nav3:
      if st.button(
          "Next 7 Days ➡️",
          key="r15_next",
          disabled=(st.session_state.rec15_page >= max_page),
          use_container_width=True,
      ):
        st.session_state.rec15_page += 1
        st.rerun()

    p_start_idx = st.session_state.rec15_page * 7
    page_dates = all_dates[p_start_idx : p_start_idx + 7]

    with nav2:
      if page_dates:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#0f172a;"
            f" font-size:0.95rem; padding-top:6px;'>Showing:"
            f" <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to"
            f" <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block"
            f" {st.session_state.rec15_page + 1} of {max_page + 1})</div>",
            unsafe_allow_html=True,
        )

    st.write("")

    cols = st.columns(7)
    for i, d in enumerate(page_dates):
      cols[i].markdown(
          textwrap.dedent(f"""
            <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.82rem; padding:10px 2px; border-radius:6px; text-align:center; margin-bottom:8px;">
                {d.strftime('%d/%m (%a)')}
            </div>
        """).strip(),
          unsafe_allow_html=True,
      )

    for i, d in enumerate(page_dates):
      d_str = d.strftime("%d/%m/%Y")
      matches = (
          range_df[range_df["Date_Str"] == d_str]
          if not range_df.empty
          else pd.DataFrame()
      )

      with cols[i]:
        if matches.empty:
          st.markdown(
              textwrap.dedent("""
                <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:12px 6px; text-align:center; min-height:160px; display:flex; align-items:center; justify-content:center;">
                    <span style="color:#94a3b8; font-weight:600; font-size:0.82rem;">— No Service</span>
                </div>
            """).strip(),
              unsafe_allow_html=True,
          )
        else:
          count = len(matches)
          chem_summary = []
          for _, r in matches.iterrows():
            chem_summary.append(f"{r['Chemical']} ({r['Method']})")
          chem_text = "<br>".join(list(dict.fromkeys(chem_summary)))

          areas_list = list(
              dict.fromkeys(matches["Areas_Treated"].dropna().tolist())
          )
          areas_html = ""
          for a in areas_list:
            areas_html += f"<div style='font-size:0.72rem; color:#1e293b; background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:3px 5px; margin-top:4px; word-wrap:break-word; text-align:left;'>📍 {a}</div>"

          tech_names = ", ".join(
              list(dict.fromkeys(matches["Technician"].dropna().tolist()))
          )

          st.markdown(
              textwrap.dedent(f"""
                <div style="background:#ffffff; border:1.5px solid #0f172a; border-radius:8px; padding:10px 6px; text-align:center; min-height:160px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size:1.15rem; font-weight:800; color:#16a34a; line-height:1;">✓ {count} Done</div>
                    <div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>
                    <div style="font-size:0.78rem; font-weight:700; color:#0f172a; line-height:1.25;">
                        {chem_text}
                    </div>
                    <div style="margin-top:6px;">
                        {areas_html}
                    </div>
                    <div style="font-size:0.68rem; color:#64748b; margin-top:6px;">By: {tech_names}</div>
                </div>
            """).strip(),
              unsafe_allow_html=True,
          )

    st.divider()
    with st.expander("📋 View All Individual Pest Treatment Records (Table View)"):
      if not range_df.empty:
        show_cols = [
            c
            for c in [
                "Date_Str",
                "Company",
                "Technician",
                "Areas_Treated",
                "Chemical",
                "Amount",
                "Method",
                "Batch",
                "Sign",
            ]
            if c in range_df.columns
        ]
        st.dataframe(
            range_df[show_cols], use_container_width=True, hide_index=True
        )
