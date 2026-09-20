from datetime import datetime, timedelta
import pandas as pd
import streamlit as st


def extract_field(rec, keywords):
    """Deep search for matching keywords across flat or nested keys."""
    clean_targets = [k.lower().replace("_", "").replace(" ", "").replace(".", "") for k in keywords]
    if isinstance(rec, dict):
        for k, v in rec.items():
            if v is None:
                continue
            k_norm = k.lower().replace("_", "").replace(" ", "").replace(".", "")
            for target in clean_targets:
                if target in k_norm:
                    if not isinstance(v, (dict, list)):
                        s_val = str(v).strip()
                        if s_val and s_val.lower() not in ["none", "nan"]:
                            return v
            if isinstance(v, dict):
                found = extract_field(v, keywords)
                if found is not None:
                    return found
            elif isinstance(v, list):
                for elem in v:
                    if isinstance(elem, dict):
                        found = extract_field(elem, keywords)
                        if found is not None:
                            return found
    return None


def parse_record_15_submissions(raw_df):
    """Parses Record 15 Pesticide Usage submissions into a normalized DataFrame."""
    if raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()

        # Date of Visit
        raw_date = extract_field(rec, ["dateofvisit", "visitdate", "date", "createdat"]) or ""
        parsed_dt = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_dt):
            parsed_dt = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")

        if pd.notna(parsed_dt):
            date_str = parsed_dt.strftime("%d/%m/%Y")
            date_obj = parsed_dt.date()
        else:
            date_str = str(raw_date)[:10]
            date_obj = None

        company = extract_field(rec, ["company", "vendor"]) or "Rentokil PCI"
        tech_name = extract_field(rec, ["technicianname", "technician", "tech"]) or "Technician"
        areas_treated = extract_field(rec, ["areastreated", "areas", "location", "area"]) or "General Areas"
        chemical = extract_field(rec, ["chemicalused", "chemical", "pesticide"]) or "Chemical"
        amount = extract_field(rec, ["amountofchemicalused", "amountofchemical", "amount", "dosage"]) or "—"
        method = extract_field(rec, ["methodofapplication", "method", "application"]) or "Spray"
        batch = extract_field(rec, ["batchcodesofchemical", "batchcode", "batch"]) or "—"
        sign = extract_field(rec, ["signinitial", "sign", "initial", "user.email"]) or tech_name

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Company": company,
            "Technician": tech_name,
            "Areas_Treated": areas_treated,
            "Chemical": chemical,
            "Amount": str(amount),
            "Method": method,
            "Batch": str(batch),
            "Sign": sign,
        })

    return pd.DataFrame(rows)


def render_record_15_view(raw_df, selected_day_str, start_date, end_date):
    """Renders Record 15 single-day drilldown and 7-day treatment matrix."""
    df_items = parse_record_15_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Service Visit ({selected_day_str})",
        "📈 7-Day Treatment Matrix"
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
                f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Applications Logged</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            tech_count = day_df["Technician"].nunique() if not day_df.empty else 0
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{tech_count}</div><div class="kpi-lbl">Technicians On Site</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            chem_count = day_df["Chemical"].nunique() if not day_df.empty else 0
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#2563eb;">{chem_count}</div><div class="kpi-lbl">Chemicals Applied</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        if not day_df.empty:
            for _, r in day_df.iterrows():
                st.markdown(
                    f"""
                <div class="check-card" style="border-left: 5px solid #0f172a; margin-bottom: 0.75rem;">
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
                </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No pest control treatment logged for this date.")

    # -------------------------------------------------------------
    # TAB 2: 7-DAY BROWSER MATRIX
    # -------------------------------------------------------------
    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec15_page" not in st.session_state:
            st.session_state.rec15_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("⬅️ Previous 7 Days", key="r15_prev", disabled=(st.session_state.rec15_page <= 0), use_container_width=True):
                st.session_state.rec15_page -= 1
                st.rerun()

        with nav3:
            if st.button("Next 7 Days ➡️", key="r15_next", disabled=(st.session_state.rec15_page >= max_page), use_container_width=True):
                st.session_state.rec15_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec15_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with nav2:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec15_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.write("")

        # 8 Columns (1 Area Title + 7 Date Columns)
        cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])
        cols[0].markdown("""
        <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.8rem; padding:8px 4px; border-radius:6px; text-align:center;">
            Treated Area Scope
        </div>
        """, unsafe_allow_html=True)

        for i, d in enumerate(page_dates):
            cols[i + 1].markdown(f"""
            <div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.78rem; padding:8px 2px; border-radius:6px; text-align:center;">
                {d.strftime('%d/%m (%a)')}
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # Extract all distinct target areas present in range
        if not range_df.empty and "Areas_Treated" in range_df.columns:
            distinct_areas = sorted(list(range_df["Areas_Treated"].dropna().unique()))
        else:
            distinct_areas = ["All restaurant, basement, out side area", "Filia kitchen and floor room"]

        for area in distinct_areas:
            row_cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])

            row_cols[0].markdown(f"""
            <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:10px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:105px; display:flex; align-items:center; justify-content:center;">
                <div style="font-weight:700; color:#0f172a; font-size:0.82rem; line-height:1.2;">{area}</div>
            </div>
            """, unsafe_allow_html=True)

            a_df = range_df[range_df["Areas_Treated"] == area] if not range_df.empty else pd.DataFrame()

            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                matches = a_df[a_df["Date_Str"] == d_str] if not a_df.empty else pd.DataFrame()

                if matches.empty:
                    row_cols[i + 1].markdown("""
                    <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:105px; display:flex; align-items:center; justify-content:center;">
                        <span style="color:#94a3b8; font-weight:600; font-size:0.8rem;">—</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    latest = matches.iloc[-1]
                    chem_txt = latest["Chemical"]
                    method_txt = latest["Method"]
                    tech_txt = latest["Technician"]

                    row_cols[i + 1].markdown(f"""
                    <div style="background:#ffffff; border:1.5px solid #0f172a; border-radius:8px; padding:6px 3px; text-align:center; min-height:105px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div style="color:#16a34a; font-weight:800; font-size:0.85rem;">✓ TREATED</div>
                        <div style="height:1px; background:#e2e8f0; margin:4px 0;"></div>
                        <div style="font-size:0.8rem; font-weight:700; color:#0f172a;">{chem_txt}</div>
                        <div style="font-size:0.7rem; color:#475569;">{method_txt} • {latest['Amount']}</div>
                        <div style="font-size:0.65rem; color:#64748b; margin-top:2px;">By: {tech_txt}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

        st.divider()

        with st.expander("📋 View All Detailed Pest Application Records"):
            if not range_df.empty:
                show_cols = [
                    c for c in [
                        "Date_Str", "Company", "Technician", "Areas_Treated", "Chemical", "Amount", "Method", "Batch", "Sign"
                    ] if c in range_df.columns
                ]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
