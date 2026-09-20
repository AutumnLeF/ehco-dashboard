from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

MAX_FRIDGE_TEMP = 4.0     # Coolroom/Fridge must be <= 4.0°C
MAX_FREEZER_TEMP = -18.0  # Freezer must be <= -18.0°C
MIN_GAP_HOURS = 5.0       # Minimum 5 hours gap between 2 daily entries


def format_unit_id(raw_val):
    """Standardizes unit ID formats (e.g. RMOBLKUC01 -> RMO/BLK/UC/01)."""
    if not raw_val or pd.isna(raw_val):
        return "Unknown Unit"
    s = str(raw_val).strip().upper()
    if "/" not in s and len(s) >= 9 and s.startswith("RMO"):
        # Auto-format RMOBLKUC01 to RMO/BLK/UC/01
        return f"{s[:3]}/{s[3:6]}/{s[6:8]}/{s[8:]}"
    return s


def extract_field(rec, keywords):
    """Deep search for matching keywords across flat or nested keys."""
    if not isinstance(rec, dict):
        return None
    clean_targets = [k.lower().replace("_", "").replace(" ", "").replace(".", "") for k in keywords]
    for k, v in rec.items():
        if v is None:
            continue
        k_norm = k.lower().replace("_", "").replace(" ", "").replace(".", "")
        for target in clean_targets:
            if target in k_norm:
                if not isinstance(v, (dict, list)):
                    s_val = str(v).strip()
                    if s_val and s_val.lower() not in ["none", "nan", ""]:
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
            or extract_field(rec, ["date", "createdat"])
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

        # 2. Time parsing for datetime gap calculation
        time_raw = str(
            sub.get("Time")
            or sub.get("time")
            or rec.get("submission.Time")
            or rec.get("submission.time")
            or extract_field(rec, ["time"])
            or ""
        ).strip()
        time_str = time_raw[:8]

        # Datetime timestamp for exact hour difference calculation
        timestamp_dt = pd.to_datetime(f"{date_str} {time_raw}", format="%d/%m/%Y %I:%M %p", errors="coerce")
        if pd.isna(timestamp_dt):
            timestamp_dt = pd.to_datetime(f"{date_str} {time_raw}", errors="coerce")

        # 3. Main Location Grouping
        location = str(
            sub.get("Location")
            or sub.get("location")
            or rec.get("submission.Location")
            or rec.get("Location")
            or extract_field(rec, ["locationother", "location"])
            or "Main Kitchen"
        ).strip()

        # 4. Appliance Type & Unit ID
        unit_type = str(
            sub.get("Coolroom/Fridge/Freezer")
            or rec.get("submission.Coolroom/Fridge/Freezer")
            or extract_field(rec, ["coolroomfridgefreezer", "appliancetype"])
            or "Fridge"
        ).strip().capitalize()

        raw_unit_id = (
            sub.get("Fridge")
            or sub.get("Coolroom")
            or sub.get("Freezer")
            or rec.get("submission.Fridge")
            or rec.get("submission.Coolroom")
            or rec.get("submission.Freezer")
            or extract_field(rec, ["fridge", "coolroom", "freezer", "unitid", "unit"])
            or "Unit"
        )
        if isinstance(raw_unit_id, list) and len(raw_unit_id) > 0:
            raw_unit_id = raw_unit_id[0]

        unit_id = format_unit_id(raw_unit_id)

        # 5. Status: IN USE vs NOT IN USE
        status_raw = str(
            sub.get("In Use / Not In Use")
            or rec.get("submission.In Use / Not In Use")
            or extract_field(rec, ["inusenotinuse", "inuse", "status"])
            or "IN USE"
        ).strip().upper()
        is_in_use = "NOT" not in status_raw

        # 6. Temperature Check
        fridge_temp_raw = (
            sub.get("Temperature °C (Coolroom 4°C or below / Fridge 4°C or below)")
            or rec.get("submission.Temperature °C (Coolroom 4°C or below / Fridge 4°C or below)")
            or extract_field(rec, ["temperatureccoolroom", "fridgetemp", "coolroomtemp"])
        )
        freezer_temp_raw = (
            sub.get("Temperature °C (Freezer -18°C or colder)")
            or rec.get("submission.Temperature °C (Freezer -18°C or colder)")
            or extract_field(rec, ["temperaturecfreezer", "freezertemp"])
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
            or extract_field(rec, ["signinitial", "sign", "initial"])
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
    """Renders Record 03 Daily Audit and Grouped Hierarchy Matrix."""
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
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">Temperature Breaches</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_logs)}</div><div class="kpi-lbl">Compliant Checks</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#64748b;">{len(standby_logs)}</div><div class="kpi-lbl">Standby / Off</div></div>',
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Audited</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Temp Breaches ({len(excursions)})</div>',
                unsafe_allow_html=True,
            )
            if excursions:
                for exc in excursions:
                    limit_txt = "<= 4°C" if "freezer" not in exc["Unit_Type"].lower() else "<= -18°C"
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{exc['Unit_ID']} • {exc['Location']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            Reading: {exc['Temp_Disp']} (Exceeds {limit_txt})
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Type: {exc['Unit_Type']} | By: {exc['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No temperature excursions logged on this date.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Verified Compliant ({len(compliant_logs)})</div>',
                unsafe_allow_html=True,
            )
            if compliant_logs:
                for ok in compliant_logs:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Unit_ID']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Temp: <b style="color:#16a34a;">{ok['Temp_Disp']}</b> &nbsp;|&nbsp; Location: <b>{ok['Location']}</b>
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Time: {ok['Time']} | By: {ok['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No compliant logs recorded for this day.")
            st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: LOCATION-GROUPED 7-DAY MATRIX (~40 UNITS)
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
                    unsafe_allow_html=True,
                )

        st.write("")

        # Discover all Main Locations with submissions
        if not range_df.empty and "Location" in range_df.columns:
            all_locations = sorted([loc for loc in range_df["Location"].dropna().unique() if str(loc).strip() != ""])
        else:
            all_locations = ["Black Lacquer Kitchen", "Filia Kitchen - Bakery", "Filia Show Kitchen", "Black Lacquer Bar"]

        filter_options = ["All Locations"] + all_locations
        selected_location = st.segmented_control(
            "Filter Kitchen Location",
            options=filter_options,
            default="All Locations",
            label_visibility="collapsed",
        ) or "All Locations"

        locations_to_show = all_locations if selected_location == "All Locations" else [selected_location]

        for location in locations_to_show:
            loc_df = range_df[range_df["Location"].str.lower() == location.lower()] if not range_df.empty else pd.DataFrame()
            units_in_loc = sorted(list(loc_df["Unit_ID"].dropna().unique())) if not loc_df.empty else []

            st.markdown(f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-left:6px solid #0f172a; border-radius:8px; padding:10px 14px; margin-top:1.2rem; margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:1.05rem; font-weight:700; color:#0f172a;">❄️ {location} <span style="font-size:0.8rem; font-weight:500; color:#64748b;">({len(units_in_loc)} Monitored Units)</span></div>
                <div style="background:#16a34a; color:#ffffff; font-size:0.75rem; font-weight:700; padding:3px 10px; border-radius:12px;">{len(loc_df)} Total Checks</div>
            </div>
            """, unsafe_allow_html=True)

            cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])
            cols[0].markdown("""
            <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.8rem; padding:8px 4px; border-radius:6px; text-align:center;">
                Unit ID / Type
            </div>
            """, unsafe_allow_html=True)

            for i, d in enumerate(page_dates):
                cols[i + 1].markdown(f"""
                <div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.78rem; padding:8px 2px; border-radius:6px; text-align:center;">
                    {d.strftime('%d/%m (%a)')}
                </div>
                """, unsafe_allow_html=True)

            st.write("")

            for unit in units_in_loc:
                u_df = loc_df[loc_df["Unit_ID"] == unit]
                unit_type = u_df["Unit_Type"].iloc[0] if not u_df.empty else "Unit"

                row_cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])

                row_cols[0].markdown(f"""
                <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:8px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:115px; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                    <div style="font-weight:700; color:#0f172a; font-size:0.82rem;">{unit}</div>
                    <div style="font-size:0.7rem; color:#64748b; margin-top:2px;">{unit_type}</div>
                </div>
                """, unsafe_allow_html=True)

                for i, d in enumerate(page_dates):
                    d_str = d.strftime("%d/%m/%Y")
                    matches = pd.DataFrame()
                    if "Date_Obj" in u_df.columns:
                        matches = u_df[u_df["Date_Obj"] == d]
                    if matches.empty and "Date_Str" in u_df.columns:
                        matches = u_df[u_df["Date_Str"] == d_str]

                    if matches.empty:
                        row_cols[i + 1].markdown("""
                        <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:115px; display:flex; align-items:center; justify-content:center;">
                            <span style="color:#94a3b8; font-weight:600; font-size:0.8rem;">— Not Logged</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        entries = matches.sort_values(by="Time").to_dict("records")
                        has_day_breach = any(e["Has_Breach"] for e in entries)

                        # Gap calculation between Entry 1 and Entry 2
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
                            badge = '<span style="color:#dc2626; font-weight:800; font-size:0.85rem;">🔴 BREACH</span>'
                            border_style = "2px solid #dc2626"
                        elif gap_warning:
                            badge = '<span style="color:#f59e0b; font-weight:800; font-size:0.82rem;">⚠️ &lt;5H GAP</span>'
                            border_style = "2px solid #f59e0b"
                        elif len(entries) == 1:
                            badge = '<span style="color:#0284c7; font-weight:800; font-size:0.82rem;">1 of 2 Done</span>'
                            border_style = "1.5px solid #0284c7"
                        else:
                            badge = '<span style="color:#16a34a; font-weight:800; font-size:0.85rem;">✓ 2/2 PASSED</span>'
                            border_style = "1.5px solid #0f172a"

                        # Clean single-line entries (no Python indentation whitespace inside markdown)
                        lines = []
                        for idx, ent in enumerate(entries[:2]):
                            temp_color = "#dc2626" if ent["Has_Breach"] else "#0f172a"
                            lines.append(
                                f'<div style="display:flex; justify-content:space-between; font-size:0.72rem; margin-top:2px;">'
                                f'<span style="color:#64748b;">#{idx+1}: <b>{ent["Time"][:5]}</b></span>'
                                f'<span style="font-weight:700; color:{temp_color};">{ent["Temp_Disp"]}</span>'
                                f'</div>'
                            )
                        shifts_html = "".join(lines)
                        sub_txt = gap_txt if gap_txt else f"By: {entries[0]['Sign']}"

                        card_html = (
                            f'<div style="background:#ffffff; border:{border_style}; border-radius:8px; padding:6px 4px; text-align:center; min-height:115px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">'
                            f'<div>{badge}</div>'
                            f'<div style="height:1px; background:#e2e8f0; margin:4px 0;"></div>'
                            f'{shifts_html}'
                            f'<div style="font-size:0.65rem; color:#64748b; margin-top:4px;">{sub_txt}</div>'
                            f'</div>'
                        )

                        row_cols[i + 1].markdown(card_html, unsafe_allow_html=True)

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
