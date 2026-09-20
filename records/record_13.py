from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

WASH_MIN_TEMP = 55.0   # Wash Cycle >= 55°C
RINSE_MIN_TEMP = 82.0  # Final Rinse Cycle >= 82°C

# Grouped Master Catalog by Location
LOCATION_CATALOG = {
    "Filia Kitchen": [
        {"Unit_ID": "RMO/FK/DW/01", "Type": "Dishwasher"},
        {"Unit_ID": "RMO/FK/GW/01", "Type": "Glasswasher"},
        {"Unit_ID": "RMO/FK/GW/02", "Type": "Glasswasher"},
    ],
    "Third Room Kitchen": [
        {"Unit_ID": "RMO/TRK/DW/01", "Type": "Dishwasher"},
        {"Unit_ID": "RMO/TRK/GW/01", "Type": "Glasswasher"},
    ],
    "Maid Pantry HK": [
        {"Unit_ID": "RMO/MP/GW/01", "Type": "Glasswasher"},
        {"Unit_ID": "RMO/MP/GW/02", "Type": "Glasswasher"},
        {"Unit_ID": "RMO/MP/GW/03", "Type": "Glasswasher"},
        {"Unit_ID": "RMO/MP/GW/04", "Type": "Glasswasher"},
        {"Unit_ID": "RMO/MP/GW/05", "Type": "Glasswasher"},
        {"Unit_ID": "RMO/MP/GW/06", "Type": "Glasswasher"},
        {"Unit_ID": "RMO/MP/GW/07", "Type": "Glasswasher"},
    ],
}


def clean_unit_str(val):
    if not val:
        return ""
    return str(val).replace("/", "").replace("_", "").replace(" ", "").strip().upper()


def parse_record_13_submissions(raw_df):
    """Parses Record 13 submissions mapping directly to exact nested Entry fields."""
    if raw_df.empty:
        return pd.DataFrame()

    # Flatten Master lookup
    flat_master = []
    for loc, units in LOCATION_CATALOG.items():
        for u in units:
            flat_master.append({"Location": loc, "Unit_ID": u["Unit_ID"], "Type": u["Type"]})

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()

        raw_date = (
            rec.get("submission.Date")
            or rec.get("Date")
            or rec.get("createdAt")
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

        time_str = str(rec.get("submission.Time") or rec.get("Time") or "")[:8]
        location = rec.get("submission.Location") or rec.get("Location") or "General Kitchen"
        sign = rec.get("submission.Sign") or rec.get("Sign") or "Staff"

        # Check Entry dict or list
        entry = rec.get("submission.Entry") or rec.get("Entry") or {}
        entries = [entry] if isinstance(entry, dict) else (entry if isinstance(entry, list) else [])
        if not entries:
            entries = [rec]

        for e in entries:
            if not isinstance(e, dict):
                continue

            machine_type = e.get("Type") or e.get("Dishwasher, Glasswasher") or "Machine"
            raw_unit = (
                e.get("unit_dish")
                or e.get("unit_glass")
                or e.get("unit_id")
                or e.get("Unit ID Dishwasher")
                or e.get("Unit ID Glasswasher")
                or ""
            )

            clean_raw = clean_unit_str(raw_unit)
            matched_master_id = None
            matched_loc = location

            for m in flat_master:
                if clean_raw == clean_unit_str(m["Unit_ID"]):
                    matched_master_id = m["Unit_ID"]
                    matched_loc = m["Location"]
                    break

            final_unit_id = matched_master_id if matched_master_id else (raw_unit or "Unspecified Unit")

            in_use_raw = str(e.get("USE") or e.get("In Use / Not In Use") or "IN USE").strip().upper()
            is_in_use = "NOT" not in in_use_raw

            wash_raw = e.get("washtemp") or e.get("Wash Cycle Temperature °C") or e.get("wash_temp")
            wash_temp = pd.to_numeric(str(wash_raw).replace("°C", "").strip(), errors="coerce")

            rinse_raw = e.get("finalTemp") or e.get("Final Rinse Cycle Temperature °C") or e.get("rinse_temp")
            rinse_temp = pd.to_numeric(str(rinse_raw).replace("°C", "").strip(), errors="coerce")

            wash_breach = False
            rinse_breach = False
            if is_in_use:
                if pd.notna(wash_temp) and wash_temp < WASH_MIN_TEMP:
                    wash_breach = True
                if pd.notna(rinse_temp) and rinse_temp < RINSE_MIN_TEMP:
                    rinse_breach = True

            rows.append({
                "Date_Str": date_str,
                "Date_Obj": date_obj,
                "Time": time_str,
                "Location": matched_loc,
                "Machine_Type": machine_type,
                "Unit_ID": final_unit_id,
                "In_Use": is_in_use,
                "Status_Text": in_use_raw,
                "Wash_Temp": wash_temp,
                "Rinse_Temp": rinse_temp,
                "Wash_Breach": wash_breach,
                "Rinse_Breach": rinse_breach,
                "Has_Breach": (wash_breach or rinse_breach),
                "Sign": sign,
            })

    return pd.DataFrame(rows)


def render_record_13_view(raw_df, selected_day_str, start_date, end_date):
    """Renders location-grouped warewash audit matrix and daily drilldown."""
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
                        errs.append(f"Wash: {exc['Wash_Temp']}°C (< 55°C)")
                    if exc["Rinse_Breach"]:
                        errs.append(f"Rinse: {exc['Rinse_Temp']}°C (< 82°C)")
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{exc['Unit_ID']} • {exc['Location']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            {' | '.join(errs)}
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Sign: {exc['Sign']}</div>
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
                    w_disp = f"{ok['Wash_Temp']}°C" if pd.notna(ok['Wash_Temp']) else "—"
                    r_disp = f"{ok['Rinse_Temp']}°C" if pd.notna(ok['Rinse_Temp']) else "—"
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Unit_ID']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Wash: <b>{w_disp}</b> &nbsp;|&nbsp; Rinse: <b style="color:#16a34a;">{r_disp}</b>
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
                f'<div class="kanban-col"><div class="kanban-h" style="color:#64748b;">⚪ Standby / Inactive ({len(inactive_units)})</div>',
                unsafe_allow_html=True,
            )
            if inactive_units:
                for off in inactive_units:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #94a3b8;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{off['Unit_ID']} • {off['Location']}</div>
                        <div style="font-size:0.8rem; color:#64748b; margin-top:3px;">Logged: <b>NOT IN USE</b></div>
                        <div style="font-size:0.75rem; color:#94a3b8; margin-top:2px;">Sign: {off['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No machines logged as inactive.")
            st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: LOCATION-GROUPED 7-DAY MATRIX
    # -------------------------------------------------------------
    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec13_page" not in st.session_state:
            st.session_state.rec13_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        # Pagination & Controls
        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("⬅️ Previous 7 Days", key="r13_prev", disabled=(st.session_state.rec13_page <= 0), use_container_width=True):
                st.session_state.rec13_page -= 1
                st.rerun()

        with nav3:
            if st.button("Next 7 Days ➡️", key="r13_next", disabled=(st.session_state.rec13_page >= max_page), use_container_width=True):
                st.session_state.rec13_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec13_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with nav2:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec13_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.write("")

        # Area Quick-Filter Selector
        filter_options = ["All Kitchen Areas"] + list(LOCATION_CATALOG.keys())
        selected_location_filter = st.segmented_control(
            "Filter Kitchen Area",
            options=filter_options,
            default="All Kitchen Areas",
            label_visibility="collapsed",
        ) or "All Kitchen Areas"

        # Determine which locations to display
        locations_to_show = (
            list(LOCATION_CATALOG.keys())
            if selected_location_filter == "All Kitchen Areas"
            else [selected_location_filter]
        )

        # Iterate over each Location as a unified group
        for location in locations_to_show:
            units = LOCATION_CATALOG[location]
            loc_df = (
                range_df[range_df["Location"].str.lower() == location.lower()]
                if not range_df.empty
                else pd.DataFrame()
            )

            # Location Section Header Bar with summary count
            total_units = len(units)
            active_count = len(loc_df) if not loc_df.empty else 0
            badge_color = "#16a34a" if active_count > 0 else "#64748b"
            badge_text = f"{active_count} Logs Recorded" if active_count > 0 else "Standby / No Logs"

            st.markdown(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-left:6px solid #0f172a; border-radius:8px; padding:10px 14px; margin-top:1.2rem; margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:1.05rem; font-weight:700; color:#0f172a;">📍 {location} <span style="font-size:0.8rem; font-weight:500; color:#64748b;">({total_units} Assigned Units)</span></div>
                <div style="background:{badge_color}; color:#ffffff; font-size:0.75rem; font-weight:700; padding:3px 10px; border-radius:12px;">{badge_text}</div>
            </div>
            """, unsafe_allow_html=True)

            # Table Header for this location
            cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])
            cols[0].markdown("""
            <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.8rem; padding:8px 4px; border-radius:6px; text-align:center;">
                Unit & Machine
            </div>
            """, unsafe_allow_html=True)

            for i, d in enumerate(page_dates):
                cols[i + 1].markdown(f"""
                <div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.78rem; padding:8px 2px; border-radius:6px; text-align:center;">
                    {d.strftime('%d/%m (%a)')}
                </div>
                """, unsafe_allow_html=True)

            st.write("")

            # Render each unit in this location
            for u in units:
                unit = u["Unit_ID"]
                m_type = u["Type"]

                row_cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])

                row_cols[0].markdown(f"""
                <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:8px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:105px; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                    <div style="font-weight:700; color:#0f172a; font-size:0.85rem;">{unit}</div>
                    <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">{m_type}</div>
                </div>
                """, unsafe_allow_html=True)

                u_df = loc_df[loc_df["Unit_ID"] == unit] if not loc_df.empty else pd.DataFrame()

                for i, d in enumerate(page_dates):
                    d_str = d.strftime("%d/%m/%Y")
                    matches = u_df[u_df["Date_Str"] == d_str] if not u_df.empty else pd.DataFrame()

                    if matches.empty:
                        row_cols[i + 1].markdown("""
                        <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:105px; display:flex; align-items:center; justify-content:center;">
                            <span style="color:#94a3b8; font-weight:600; font-size:0.8rem;">— Not Logged</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        latest = matches.iloc[-1]
                        w_val = f"{int(latest['Wash_Temp'])}°" if pd.notna(latest['Wash_Temp']) else "—"
                        r_val = f"{int(latest['Rinse_Temp'])}°" if pd.notna(latest['Rinse_Temp']) else "—"

                        if not latest["In_Use"]:
                            status_badge = '<span style="color:#64748b; font-weight:700; font-size:0.82rem;">STANDBY</span>'
                            temp_detail = 'Not In Use'
                            card_border = "1.5px solid #94a3b8"
                        elif latest["Has_Breach"]:
                            status_badge = '<span style="color:#dc2626; font-weight:800; font-size:0.85rem;">🔴 BREACH</span>'
                            temp_detail = f"W: {w_val} | R: {r_val}"
                            card_border = "2px solid #dc2626"
                        else:
                            status_badge = '<span style="color:#16a34a; font-weight:800; font-size:0.85rem;">✓ PASS</span>'
                            temp_detail = f"W: {w_val} | R: {r_val}"
                            card_border = "1.5px solid #0f172a"

                        row_cols[i + 1].markdown(f"""
                        <div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:6px 3px; text-align:center; min-height:105px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                            <div>{status_badge}</div>
                            <div style="height:1px; background:#e2e8f0; margin:4px 0;"></div>
                            <div style="font-size:0.8rem; font-weight:700; color:#0f172a; line-height:1.2;">
                                {temp_detail}
                            </div>
                            <div style="font-size:0.65rem; color:#64748b; margin-top:3px;">By: {latest['Sign']}</div>
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
