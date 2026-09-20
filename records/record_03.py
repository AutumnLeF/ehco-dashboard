from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

MAX_FRIDGE_TEMP = 4.0     # Coolroom / Fridge must be <= 4.0°C
MAX_FREEZER_TEMP = -18.0  # Freezer must be <= -18.0°C
MIN_GAP_HOURS = 5.0       # At least 5 hours between shift checks

# Full 49-Unit Catalog across all locations
UNIT_CATALOG = {
    "Filia Kitchen": [
        {"Unit_ID": "RMO/FK/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/FK/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/FK/CR/01", "Type": "Coolroom"},
        {"Unit_ID": "RMO/FK/CR/02", "Type": "Coolroom"},
        {"Unit_ID": "RMO/FK/WF/01", "Type": "Freezer"},
        {"Unit_ID": "RMO/FK/UF/01", "Type": "Freezer"},
    ],
    "Filia Kitchen - Bakery": [
        {"Unit_ID": "RMO/FKB/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/FKB/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/FKB/UC/03", "Type": "Fridge"},
        {"Unit_ID": "RMO/FKB/VF/01", "Type": "Freezer"},
    ],
    "Filia Show Kitchen": [
        {"Unit_ID": "RMO/FSK/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/FSK/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/FSK/UC/03", "Type": "Fridge"},
        {"Unit_ID": "RMO/FSK/UC/04", "Type": "Fridge"},
    ],
    "Filia Restaurant": [
        {"Unit_ID": "RMO/FR/VR/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/FR/VR/02", "Type": "Fridge"},
    ],
    "Filia Bar": [
        {"Unit_ID": "RMO/FB/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/FB/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/FB/UC/03", "Type": "Fridge"},
        {"Unit_ID": "RMO/FB/UC/04", "Type": "Fridge"},
        {"Unit_ID": "RMO/FB/UF/01", "Type": "Freezer"},
        {"Unit_ID": "RMO/FB/UF/02", "Type": "Freezer"},
    ],
    "Third Room Kitchen": [
        {"Unit_ID": "RMO/TRK/VR/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/TRK/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/TRK/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/TRK/UC/03", "Type": "Fridge"},
        {"Unit_ID": "RMO/TRK/VF/01", "Type": "Freezer"},
    ],
    "Third Room": [
        {"Unit_ID": "RMO/TRB/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/TRB/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/TRB/UC/03", "Type": "Fridge"},
        {"Unit_ID": "RMO/TR/UF/01",  "Type": "Freezer"},
    ],
    "Black Lacquer Kitchen": [
        {"Unit_ID": "RMO/BLK/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/BLK/VR/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/BLK/UF/01", "Type": "Freezer"},
    ],
    "Black Lacquer Bar": [
        {"Unit_ID": "RMO/BL/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/UC/03", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/UC/04", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/UC/05", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/VR/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/VR/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/VR/03", "Type": "Fridge"},
        {"Unit_ID": "RMO/BL/UF/01", "Type": "Freezer"},
        {"Unit_ID": "RMO/BL/UF/02", "Type": "Freezer"},
        {"Unit_ID": "RMO/BL/UF/03", "Type": "Freezer"},
        {"Unit_ID": "RMO/BL/UF/04", "Type": "Freezer"},
    ],
    "Black Lacquer Speakeasy": [
        {"Unit_ID": "RMO/BLS/UC/01", "Type": "Fridge"},
        {"Unit_ID": "RMO/BLS/UC/02", "Type": "Fridge"},
        {"Unit_ID": "RMO/BLS/UF/01", "Type": "Freezer"},
    ],
}


def clean_unit_token(val):
    if not val or pd.isna(val):
        return ""
    return str(val).replace("/", "").replace("_", "").replace(" ", "").replace("-", "").strip().upper()


def extract_val(d, keys):
    """Searches a dictionary for any matching key variant."""
    if not isinstance(d, dict):
        return None
    for k, v in d.items():
        if any(k.lower() == target.lower() for target in keys):
            if v is not None and str(v).strip() != "":
                return v
    return None


def parse_record_03_submissions(raw_df):
    """Parses Record 03 submissions targeting the nested submission.Entry schema."""
    if raw_df.empty:
        return pd.DataFrame()

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
    for _, record in raw_df.iterrows():
        rec = record.to_dict()
        sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else {}
        entry = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else {}

        # 1. Date: From submission.Date or root
        raw_date = (
            sub.get("Date")
            or sub.get("date")
            or rec.get("submission.Date")
            or rec.get("submission.date")
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

        # 2. Time: From submission.Time
        raw_time_iso = str(
            sub.get("Time")
            or sub.get("time")
            or rec.get("submission.Time")
            or ""
        ).strip()

        time_dt = pd.to_datetime(raw_time_iso, errors="coerce")
        if pd.notna(time_dt):
            time_clean = time_dt.strftime("%I:%M %p")
            ts_dt = time_dt
        else:
            time_clean = raw_time_iso[:8]
            ts_dt = pd.to_datetime(f"{date_str} {time_clean}", errors="coerce")

        # 3. Location: From submission.Location
        location = str(
            sub.get("Location")
            or rec.get("submission.Location")
            or rec.get("Location")
            or ""
        ).strip()

        # 4. Unit ID: Inside submission.Entry (Fridge, Coolroom, Freezer) or flat
        raw_unit = (
            entry.get("Fridge")
            or entry.get("Coolroom")
            or entry.get("Freezer")
            or rec.get("submission.Entry.Fridge")
            or rec.get("submission.Entry.Coolroom")
            or rec.get("submission.Entry.Freezer")
            or sub.get("Fridge")
            or sub.get("Coolroom")
            or sub.get("Freezer")
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

        # 5. In Use: From Entry.USE
        status_raw = str(
            entry.get("USE")
            or sub.get("USE")
            or rec.get("submission.Entry.USE")
            or sub.get("In Use / Not In Use")
            or "IN USE"
        ).strip().upper()
        is_in_use = "NOT" not in status_raw

        # 6. Temperature: In JSON it is 'CRTemperature' or 'FZTemperature' or 'Temperature'
        temp_val_raw = (
            entry.get("CRTemperature")
            or entry.get("FZTemperature")
            or entry.get("Temperature")
            or entry.get("temperature")
            or rec.get("submission.Entry.CRTemperature")
            or rec.get("submission.Entry.FZTemperature")
            or sub.get("Temperature °C (Coolroom 4°C or below / Fridge 4°C or below)")
            or sub.get("Temperature °C (Freezer -18°C or colder)")
        )

        num_temp = pd.to_numeric(str(temp_val_raw).replace("°C", "").strip(), errors="coerce")

        has_breach = False
        temp_disp = "—"

        if is_in_use and pd.notna(num_temp):
            temp_disp = f"{num_temp}°C"
            if "freezer" in matched_type.lower():
                if num_temp > MAX_FREEZER_TEMP:
                    has_breach = True
            else:
                if num_temp > MAX_FRIDGE_TEMP:
                    has_breach = True

        # 7. Sign: From submission.Sign
        sign = (
            sub.get("Sign")
            or sub.get("sign")
            or rec.get("submission.Sign")
            or "Staff"
        )

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Timestamp_DT": ts_dt,
            "Time": time_clean,
            "Location": matched_loc,
            "Unit_ID": final_unit,
            "Clean_Unit": clean_unit_token(final_unit),
            "Unit_Type": matched_type,
            "In_Use": is_in_use,
            "Temp": num_temp,
            "Temp_Disp": temp_disp,
            "Has_Breach": has_breach,
            "Sign": str(sign).strip(),
        })

    return pd.DataFrame(rows)


def render_record_03_view(raw_df, selected_day_str, start_date, end_date):
    """Renders Record 03 with master catalog and clean 7-day grid."""
    df_items = parse_record_03_submissions(raw_df)

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Unit Temperature Audit ({selected_day_str})",
        "📈 7-Day Grouped Location Matrix (49 Units)"
    ])

    # -------------------------------------------------------------
    # TAB 1: DAILY DRILLDOWN
    # -------------------------------------------------------------
    with tab_day:
        day_df = (
            df_items[df_items["Date_Str"] == selected_day_str]
            if not df_items.empty
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
    # TAB 2: HIGH-READABILITY 7-DAY MATRIX (49 UNITS)
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
                    f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec03_page + 1} of {max_page + 1})"
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
            cols[0].markdown('<div style="font-weight:700; font-size:0.8rem; color:#475569; padding:6px 2px;">Appliance Unit</div>', unsafe_allow_html=True)
            for i, d in enumerate(page_dates):
                cols[i + 1].markdown(f'<div style="background:#f1f5f9; font-weight:700; font-size:0.8rem; text-align:center; padding:6px 2px; border-radius:4px; color:#0f172a;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

            st.write("")

            for u in units:
                unit_id = u["Unit_ID"]
                unit_type = u["Type"]
                clean_target = clean_unit_token(unit_id)

                row_cols = st.columns(col_ratios)

                # Unit ID Label Card
                row_cols[0].markdown(f"""
                <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:8px 8px; min-height:82px; display:flex; flex-direction:column; justify-content:center;">
                    <div style="font-weight:700; font-size:0.84rem; color:#0f172a;">{unit_id}</div>
                    <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">{unit_type}</div>
                </div>
                """, unsafe_allow_html=True)

                # Filter directly by normalized unit token
                u_df = df_items[df_items["Clean_Unit"] == clean_target] if not df_items.empty else pd.DataFrame()

                for i, d in enumerate(page_dates):
                    d_str = d.strftime("%d/%m/%Y")
                    matches = pd.DataFrame()
                    if not u_df.empty:
                        if "Date_Obj" in u_df.columns:
                            matches = u_df[u_df["Date_Obj"] == d]
                        if matches.empty and "Date_Str" in u_df.columns:
                            matches = u_df[u_df["Date_Str"] == d_str]

                    if matches.empty:
                        row_cols[i + 1].markdown(
                            '<div style="background:#f8fafc; border:1px dashed #cbd5e1; border-radius:6px; padding:6px; min-height:82px; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:0.75rem;">— Not Logged</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        entries = matches.sort_values(by="Time").to_dict("records")
                        has_day_breach = any(e["Has_Breach"] for e in entries)

                        # Gap calculation
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

                        readings_str = ""
                        for idx, ent in enumerate(entries[:2]):
                            t_color = "#dc2626" if ent["Has_Breach"] else "#0f172a"
                            t_val = ent["Temp_Disp"]
                            t_time = ent["Time"][:8]
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
