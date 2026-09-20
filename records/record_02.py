from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

MAX_FRIDGE_TEMP = 4.0     # Coolroom/Fridge must be <= 4.0°C
MAX_FREEZER_TEMP = -18.0  # Freezer must be <= -18.0°C
MIN_GAP_HOURS = 5.0       # At least 5 hours gap between checks


def format_unit_id(raw_val):
    """Standardizes unit ID formats (e.g. RMOBLKUC01 -> RMO/BLK/UC/01)."""
    if not raw_val or pd.isna(raw_val):
        return "Unit"
    s = str(raw_val).strip().upper()
    if "/" not in s and len(s) >= 9 and s.startswith("RMO"):
        return f"{s[:3]}/{s[3:6]}/{s[6:8]}/{s[8:]}"
    return s


def parse_record_03_submissions(raw_df):
    """Parses Record 03 Coolroom/Fridge/Freezer submissions."""
    if raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()
        sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else {}

        # 1. Date normalization
        raw_date = (
            sub.get("date")
            or sub.get("Date")
            or rec.get("submission.date")
            or rec.get("submission.Date")
            or rec.get("Date")
            or rec.get("createdAt")
            or rec.get("dateTimeSubmitted")
            or ""
        )
        parsed_dt = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_dt):
            parsed_dt = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")

        if pd.notna(parsed_dt):
            date_str = parsed_dt.strftime("%d/%m/%Y")
            date_obj = parsed_dt.date()
        else:
            date_str = str(raw_date)[:10]
            date_obj = None

        # 2. Time parsing
        time_raw = str(
            sub.get("Time")
            or sub.get("time")
            or rec.get("submission.Time")
            or rec.get("submission.time")
            or ""
        ).strip()
        time_str = time_raw[:8]

        # Datetime object for exact elapsed time calculation
        timestamp_dt = pd.to_datetime(f"{date_str} {time_raw}", format="%d/%m/%Y %I:%M %p", errors="coerce")
        if pd.isna(timestamp_dt):
            timestamp_dt = pd.to_datetime(f"{date_str} {time_raw}", errors="coerce")

        # 3. Main Location Grouping
        location = str(
            sub.get("Location")
            or sub.get("location")
            or rec.get("submission.Location")
            or rec.get("Location")
            or "Main Kitchen"
        ).strip()

        # 4. Appliance Type & Unit ID
        unit_type = str(
            sub.get("Coolroom/Fridge/Freezer")
            or rec.get("submission.Coolroom/Fridge/Freezer")
            or "Fridge"
        ).strip().capitalize()

        raw_unit_id = (
            sub.get("Fridge")
            or sub.get("Coolroom")
            or sub.get("Freezer")
            or rec.get("submission.Fridge")
            or rec.get("submission.Coolroom")
            or rec.get("submission.Freezer")
            or "Unit"
        )
        if isinstance(raw_unit_id, list) and len(raw_unit_id) > 0:
            raw_unit_id = raw_unit_id[0]

        unit_id = format_unit_id(raw_unit_id)

        # 5. Status: IN USE vs NOT IN USE
        status_raw = str(
            sub.get("In Use / Not In Use")
            or rec.get("submission.In Use / Not In Use")
            or "IN USE"
        ).strip().upper()
        is_in_use = "NOT" not in status_raw

        # 6. Temperature Check
        fridge_temp_raw = (
            sub.get("Temperature °C (Coolroom 4°C or below / Fridge 4°C or below)")
            or rec.get("submission.Temperature °C (Coolroom 4°C or below / Fridge 4°C or below)")
        )
        freezer_temp_raw = (
            sub.get("Temperature °C (Freezer -18°C or colder)")
            or rec.get("submission.Temperature °C (Freezer -18°C or colder)")
        )

        f_temp = pd.to_numeric(str(fridge_temp_raw).replace("°C", "").strip(), errors="coerce")
        fz_temp = pd.to_numeric(str(freezer_temp_raw).replace("°C", "").strip(), errors="coerce")

        has_breach = False
        final_temp = None
        temp_disp = "—"

        if is_in_use:
            if "freezer" in unit_type.lower() or pd.notna(fz_temp):
                final_temp = fz_temp
                temp_disp = f"{fz_temp}°C" if pd.notna(fz_temp) else "—"
                if pd.notna(fz_temp) and fz_temp > MAX_FREEZER_TEMP:
                    has_breach = True
            else:
                final_temp = f_temp
                temp_disp = f"{f_temp}°C" if pd.notna(f_temp) else "—"
                if pd.notna(f_temp) and f_temp > MAX_FRIDGE_TEMP:
                    has_breach = True

        sign = (
            sub.get("Sign (Initial)")
            or sub.get("Sign")
            or sub.get("sign")
            or rec.get("submission.Sign (Initial)")
            or "Staff"
        )

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Timestamp_DT": timestamp_dt,
            "Time": time_str,
            "Location": location,
            "Unit_Type": unit_type,
            "Unit_ID": unit_id,
            "In_Use": is_in_use,
            "Temp": final_temp,
            "Temp_Disp": temp_disp,
            "Has_Breach": has_breach,
            "Sign": str(sign).strip(),
        })

    return pd.DataFrame(rows)


def render_record_03_view(raw_df, selected_day_str, start_date, end_date):
    """Renders high-clarity Record 03 temperature monitor."""
    df_items = parse_record_03_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns and df_items["Date_Obj"].notna().any():
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Unit Temperature Audit ({selected_day_str})",
        "📈 7-Day Grouped Location Matrix"
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
        compliant_logs = []
        standby_logs = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if not r["In_Use"]:
                    standby_logs.append(r.to_dict())
                elif r["Has_Breach"]:
                    excursions.append(r.to_dict())
                else:
                    compliant_logs.append(r.to_dict())

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">Temperature Breaches</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_logs)}</div><div class="kpi-lbl">Compliant Checks</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#64748b;">{len(standby_logs)}</div><div class="kpi-lbl">Standby / Off</div></div>', unsafe_allow_html=True)
        with k4:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Audited</div></div>', unsafe_allow_html=True)

        st.write("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Temp Breaches ({len(excursions)})</div>', unsafe_allow_html=True)
            if excursions:
                for exc in excursions:
                    limit_txt = "<= 4°C" if "freezer" not in exc["Unit_Type"].lower() else "<= -18°C"
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626; padding:10px; margin-bottom:8px; background:#ffffff; border-radius:6px; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-weight:700; font-size:0.92rem; color:#0f172a;">{exc['Unit_ID']} • {exc['Location']}</div>
                        <div style="font-size:0.82rem; color:#dc2626; font-weight:700; margin-top:3px;">
                            Reading: {exc['Temp_Disp']} (Breaches {limit_txt})
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Time: {exc['Time']} | By: {exc['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No temperature excursions logged on this date.")
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Verified Compliant ({len(compliant_logs)})</div>', unsafe_allow_html=True)
            if compliant_logs:
                for ok in compliant_logs:
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a; padding:10px; margin-bottom:8px; background:#ffffff; border-radius:6px; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                        <div style="font-weight:700; font-size:0.92rem; color:#0f172a;">{ok['Unit_ID']}</div>
                        <div style="font-size:0.82rem; color:#334155; margin-top:3px;">
                            Temp: <b style="color:#16a34a;">{ok['Temp_Disp']}</b> &nbsp;|&nbsp; Location: <b>{ok['Location']}</b>
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Time: {ok['Time']} | By: {ok['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No compliant logs recorded for this day.")
            st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: HIGH-READABILITY 7-DAY MATRIX
    # -------------------------------------------------------------
    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec03_page" not in st.session_state:
            st.session_state.rec03_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

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

        with nav2:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Audit Period: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec03_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.write("")

        # Discover all active locations
        if not range_df.empty and "Location" in range_df.columns:
            all_locations = sorted([loc for loc in range_df["Location"].dropna().unique() if str(loc).strip() != ""])
        else:
            all_locations = ["Black Lacquer Bar", "Black Lacquer Kitchen", "Filia Kitchen - Bakery", "Filia Show Kitchen"]

        # Clean Location Selector
        sel_loc = st.selectbox("📍 Select Kitchen Area to Audit (~40 Units Total):", ["All Locations"] + all_locations)
        locations_to_show = all_locations if sel_loc == "All Locations" else [sel_loc]

        num_dates = len(page_dates)
        col_ratios = [1.8] + [1.0] * num_dates

        for location in locations_to_show:
            loc_df = range_df[range_df["Location"].str.lower() == location.lower()] if not range_df.empty else pd.DataFrame()
            units_in_loc = sorted(list(loc_df["Unit_ID"].dropna().unique())) if not loc_df.empty else []

            st.markdown(f"""
            <div style="background:#0f172a; color:#ffffff; padding:10px 14px; border-radius:6px; margin-top:1.4rem; margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; font-size:0.98rem;">❄️ {location}</span>
                <span style="font-size:0.8rem; background:#334155; padding:3px 10px; border-radius:12px;">{len(units_in_loc)} Monitored Units</span>
            </div>
            """, unsafe_allow_html=True)

            # Header Row
            cols = st.columns(col_ratios)
            cols[0].markdown('<div style="font-weight:700; font-size:0.8rem; color:#475569; padding:6px 2px;">Appliance Unit</div>', unsafe_allow_html=True)
            for i, d in enumerate(page_dates):
                cols[i + 1].markdown(f'<div style="background:#f1f5f9; font-weight:700; font-size:0.8rem; text-align:center; padding:6px 2px; border-radius:4px; color:#0f172a;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

            st.write("")

            for unit in units_in_loc:
                u_df = loc_df[loc_df["Unit_ID"] == unit]
                unit_type = u_df["Unit_Type"].iloc[0] if not u_df.empty else "Fridge"

                row_cols = st.columns(col_ratios)

                # Unit Label Cell
                row_cols[0].markdown(f"""
                <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:8px 8px; min-height:82px; display:flex; flex-direction:column; justify-content:center;">
                    <div style="font-weight:700; font-size:0.84rem; color:#0f172a;">{unit}</div>
                    <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">{unit_type}</div>
                </div>
                """, unsafe_allow_html=True)

                # Daily Inspection Cells
                for i, d in enumerate(page_dates):
                    d_str = d.strftime("%d/%m/%Y")
                    matches = pd.DataFrame()
                    if "Date_Obj" in u_df.columns:
                        matches = u_df[u_df["Date_Obj"] == d]
                    if matches.empty and "Date_Str" in u_df.columns:
                        matches = u_df[u_df["Date_Str"] == d_str]

                    if matches.empty:
                        row_cols[i + 1].markdown(
                            '<div style="background:#f8fafc; border:1px dashed #cbd5e1; border-radius:6px; padding:6px; min-height:82px; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:0.75rem;">— Off / Empty</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        entries = matches.sort_values(by="Time").to_dict("records")
                        has_day_breach = any(e["Has_Breach"] for e in entries)

                        # Gap calculation between First Check and Second Check
                        gap_warning = False
                        gap_txt = ""
                        if len(entries) >= 2:
                            dt1 = entries[0].get("Timestamp_DT")
                            dt2 = entries[-1].get("Timestamp_DT")
                            if pd.notna(dt1) and pd.notna(dt2):
                                diff_hours = abs((dt2 - dt1).total_seconds()) / 3600.0
                                gap_txt = f"{diff_hours:.1f}h gap"
                                if diff_hours < MIN_GAP_HOURS:
                                    gap_warning = True

                        # Status header tag
                        if has_day_breach:
                            status_tag = '<span style="color:#dc2626; font-weight:800; font-size:0.75rem;">🔴 BREACH</span>'
                            border_color = "#dc2626"
                        elif gap_warning:
                            status_tag = f'<span style="color:#d97706; font-weight:800; font-size:0.74rem;">⚠️ {gap_txt}</span>'
                            border_color = "#d97706"
                        elif len(entries) >= 2:
                            status_tag = f'<span style="color:#16a34a; font-weight:800; font-size:0.75rem;">✓ {gap_txt or "2/2 OK"}</span>'
                            border_color = "#16a34a"
                        else:
                            status_tag = '<span style="color:#0284c7; font-weight:700; font-size:0.74rem;">1 of 2 Logged</span>'
                            border_color = "#94a3b8"

                        # Reading Lines
                        readings_str = ""
                        for idx, ent in enumerate(entries[:2]):
                            t_color = "#dc2626" if ent["Has_Breach"] else "#0f172a"
                            t_val = ent["Temp_Disp"]
                            t_time = ent["Time"][:5]
                            readings_str += f'<div style="display:flex; justify-content:space-between; font-size:0.72rem; margin-top:2px;"><span style="color:#64748b;">#{idx+1} ({t_time})</span><b style="color:{t_color};">{t_val}</b></div>'

                        row_cols[i + 1].markdown(
                            f'<div style="background:#ffffff; border:1.5px solid {border_color}; border-radius:6px; padding:6px 6px; min-height:82px; box-shadow:0 1px 2px rgba(0,0,0,0.05);">'
                            f'<div style="text-align:center; padding-bottom:3px; border-bottom:1px solid #f1f5f9;">{status_tag}</div>'
                            f'{readings_str}'
                            f'<div style="font-size:0.65rem; color:#64748b; text-align:right; margin-top:3px;">By: {entries[0]["Sign"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

            st.write("")

        st.divider()

        with st.expander("📋 View All Individual Temperature Records (Raw Log Table)"):
            if not range_df.empty:
                show_cols = [
                    c for c in [
                        "Date_Str", "Time", "Location", "Unit_Type", "Unit_ID", "Temp_Disp", "Sign"
                    ] if c in range_df.columns
                ]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
