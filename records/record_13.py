from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

WASH_MIN_TEMP = 55.0   # Wash Cycle >= 55°C
RINSE_MIN_TEMP = 82.0  # Final Rinse Cycle >= 82°C


def find_val(row_dict, keywords):
    """Finds first matching non-null value for loose key names."""
    for k, v in row_dict.items():
        k_clean = k.lower().replace("_", "").replace(" ", "").replace(".", "")
        for kw in keywords:
            kw_clean = kw.lower().replace("_", "").replace(" ", "")
            if kw_clean in k_clean:
                if pd.notna(v) and str(v).strip() != "":
                    return v
    return None


def parse_record_13_submissions(raw_df):
    """Parses Record 13 Dishwasher and Glasswasher temperature logs."""
    if raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()

        # Date normalization
        raw_date = find_val(rec, ["date", "createdat", "submissiondate"]) or ""
        parsed_dt = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_dt):
            parsed_dt = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")

        if pd.notna(parsed_dt):
            date_str = parsed_dt.strftime("%d/%m/%Y")
            date_obj = parsed_dt.date()
        else:
            date_str = str(raw_date)[:10]
            date_obj = None

        time_str = str(find_val(rec, ["time", "submissiontime"]) or "")[:8]
        location = find_val(rec, ["locationother", "location"]) or "General Kitchen"
        machine_type = find_val(rec, ["dishwasherglasswasher", "machinetype", "type"]) or "Machine"

        # Unit ID resolution
        unit_id = (
            find_val(rec, ["unitiddishwasher", "unitidglasswasher", "unitid", "unit_id"])
            or "Unspecified Unit"
        )

        in_use_raw = str(find_val(rec, ["inusenotinuse", "inuse", "status"]) or "IN USE").strip().upper()
        is_in_use = "NOT" not in in_use_raw

        # Temperatures
        wash_temp_raw = find_val(rec, ["washcycletemperature", "washtemperature", "washtemp"])
        wash_temp = pd.to_numeric(str(wash_temp_raw).replace("°C", "").strip(), errors="coerce")

        rinse_temp_raw = find_val(rec, ["finalrinsecycletemperature", "rinsetemperature", "rinsetemp"])
        rinse_temp = pd.to_numeric(str(rinse_temp_raw).replace("°C", "").strip(), errors="coerce")

        sign = find_val(rec, ["signinitial", "sign", "initial", "user.email"]) or "Staff"

        # Excursion checks
        wash_breach = is_in_use and pd.notna(wash_temp) and (wash_temp < WASH_MIN_TEMP)
        rinse_breach = is_in_use and pd.notna(rinse_temp) and (rinse_temp < RINSE_MIN_TEMP)
        has_breach = wash_breach or rinse_breach

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Time": time_str,
            "Location": location,
            "Machine_Type": machine_type,
            "Unit_ID": unit_id,
            "In_Use": is_in_use,
            "Status_Text": in_use_raw,
            "Wash_Temp": wash_temp,
            "Rinse_Temp": rinse_temp,
            "Wash_Breach": wash_breach,
            "Rinse_Breach": rinse_breach,
            "Has_Breach": has_breach,
            "Sign": sign,
        })

    return pd.DataFrame(rows)


def render_record_13_view(raw_df, selected_day_str, start_date, end_date):
    """Renders Record 13 daily audit and 7-day paginated matrix."""
    df_items = parse_record_13_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Sanitization Audit ({selected_day_str})",
        "📈 7-Day Matrix (1-Month Browser)"
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

        excursions = []
        verified_units = []
        inactive_units = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if not r["In_Use"]:
                    inactive_units.append(r.to_dict())
                elif r["Has_Breach"]:
                    excursions.append(r.to_dict())
                else:
                    verified_units.append(r.to_dict())

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">Sanitization Breaches</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(verified_units)}</div><div class="kpi-lbl">Verified Compliant</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#64748b;">{len(inactive_units)}</div><div class="kpi-lbl">Units Not In Use</div></div>',
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Audited</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Temp Breaches ({len(excursions)})</div>',
                unsafe_allow_html=True,
            )
            if excursions:
                for exc in excursions:
                    errs = []
                    if exc["Wash_Breach"]:
                        errs.append(f"Wash: {exc['Wash_Temp']}°C (&lt; 55°C)")
                    if exc["Rinse_Breach"]:
                        errs.append(f"Rinse: {exc['Rinse_Temp']}°C (&lt; 82°C)")
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{exc['Unit_ID']} • {exc['Location']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            {' | '.join(errs)}
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Type: {exc['Machine_Type']} | Sign: {exc['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("All active units met sanitization thresholds.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Verified Units ({len(verified_units)})</div>',
                unsafe_allow_html=True,
            )
            if verified_units:
                for ok in verified_units:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Unit_ID']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Wash: <b>{ok['Wash_Temp']}°C</b> &nbsp;|&nbsp; Rinse: <b style="color:#16a34a;">{ok['Rinse_Temp']}°C</b>
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Area: {ok['Location']} | Sign: {ok['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No verified wash cycles recorded for this day.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c3:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#64748b;">⚪ Inactive / Standby ({len(inactive_units)})</div>',
                unsafe_allow_html=True,
            )
            if inactive_units:
                for off in inactive_units:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #94a3b8;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{off['Unit_ID']} • {off['Location']}</div>
                        <div style="font-size:0.8rem; color:#64748b; margin-top:3px;">Logged as: <b>NOT IN USE</b></div>
                        <div style="font-size:0.75rem; color:#94a3b8; margin-top:2px;">Sign: {off['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No machines logged as inactive.")
            st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: 7-DAY SPLIT-CELL AUDIT GRID
    # -------------------------------------------------------------
    with tab_matrix:
        st.subheader("7-Day Wash & Rinse Completion Matrix")

        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec13_page" not in st.session_state:
            st.session_state.rec13_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        col_prev, col_status, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("⬅️ Previous 7 Days", key="r13_prev", disabled=(st.session_state.rec13_page <= 0), use_container_width=True):
                st.session_state.rec13_page -= 1
                st.rerun()

        with col_next:
            if st.button("Next 7 Days ➡️", key="r13_next", disabled=(st.session_state.rec13_page >= max_page), use_container_width=True):
                st.session_state.rec13_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec13_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with col_status:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: {page_dates[0].strftime('%d/%m/%Y')} to {page_dates[-1].strftime('%d/%m/%Y')} (Block {st.session_state.rec13_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.write("")

        # 8 Columns (1 for Unit/Location + 7 Days)
        cols = st.columns([2.0, 1, 1, 1, 1, 1, 1, 1])
        cols[0].markdown("""
        <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.85rem; padding:10px 4px; border-radius:6px; text-align:center;">
            Location & Unit ID
        </div>
        """, unsafe_allow_html=True)

        for i, d in enumerate(page_dates):
            cols[i + 1].markdown(f"""
            <div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.8rem; padding:10px 2px; border-radius:6px; text-align:center;">
                {d.strftime('%d/%m (%a)')}
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # Discovers all locations and units dynamically (supports Maid Pantry HK and future additions)
        if not range_df.empty and "Unit_ID" in range_df.columns:
            unit_pairs = range_df[["Location", "Unit_ID"]].drop_duplicates().sort_values(by=["Location", "Unit_ID"]).values.tolist()
        else:
            unit_pairs = [("Filia Kitchen", "RMO/FK/DW/01"), ("Third Room Kitchen", "RMO/TRK/DW/01")]

        for location, unit in unit_pairs:
            row_cols = st.columns([2.0, 1, 1, 1, 1, 1, 1, 1])

            row_cols[0].markdown(f"""
            <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:10px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:115px; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                <div style="font-weight:700; color:#0f172a; font-size:0.85rem;">{unit}</div>
                <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">{location}</div>
            </div>
            """, unsafe_allow_html=True)

            u_df = range_df[(range_df["Location"] == location) & (range_df["Unit_ID"] == unit)] if not range_df.empty else pd.DataFrame()

            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                matches = u_df[u_df["Date_Str"] == d_str] if not u_df.empty else pd.DataFrame()

                if matches.empty:
                    row_cols[i + 1].markdown("""
                    <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:115px; display:flex; align-items:center; justify-content:center;">
                        <span style="color:#94a3b8; font-weight:700; font-size:1.2rem;">—</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    latest = matches.iloc[-1]
                    if not latest["In_Use"]:
                        status_badge = '<span style="color:#64748b; font-weight:700; font-size:0.85rem;">STANDBY</span>'
                        temp_detail = 'Not In Use'
                        card_border = "1.5px solid #94a3b8"
                    elif latest["Has_Breach"]:
                        status_badge = '<span style="color:#dc2626; font-weight:800; font-size:0.9rem;">🔴 BREACH</span>'
                        temp_detail = f"W: {latest['Wash_Temp']}° | R: {latest['Rinse_Temp']}°"
                        card_border = "2px solid #dc2626"
                    else:
                        status_badge = '<span style="color:#16a34a; font-weight:800; font-size:0.9rem;">✓ PASS</span>'
                        temp_detail = f"W: {latest['Wash_Temp']}° | R: {latest['Rinse_Temp']}°"
                        card_border = "1.5px solid #0f172a"

                    row_cols[i + 1].markdown(f"""
                    <div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:8px 4px; text-align:center; min-height:115px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div style="margin-top:2px;">{status_badge}</div>
                        <div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>
                        <div style="font-size:0.75rem; font-weight:600; color:#0f172a; line-height:1.25;">
                            {temp_detail}
                        </div>
                        <div style="font-size:0.68rem; color:#64748b; margin-top:4px;">By: {latest['Sign']}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

        st.divider()

        with st.expander("📋 View All Individual Sanitization Records"):
            if not range_df.empty:
                show_cols = [c for c in [
                    "Date_Str", "Time", "Location", "Machine_Type", "Unit_ID", "Status_Text", "Wash_Temp", "Rinse_Temp", "Sign"
                ] if c in range_df.columns]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
