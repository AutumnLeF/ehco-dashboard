from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

WASH_MIN_TEMP = 55.0   # Wash Cycle >= 55°C
RINSE_MIN_TEMP = 82.0  # Final Rinse Cycle >= 82°C

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
    if not val or pd.isna(val):
        return ""
    return str(val).replace("/", "").replace("_", "").replace(" ", "").strip().upper()


def parse_record_13_submissions(raw_df):
    """Robustly parses Record 13 dishwasher/glasswasher submissions from OneBlink nested payloads."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    flat_master = []
    for loc, units in LOCATION_CATALOG.items():
        for u in units:
            flat_master.append({"Location": loc, "Unit_ID": u["Unit_ID"], "Type": u["Type"]})

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.get("raw_record") if "raw_record" in raw_df.columns else record.to_dict()
        if not isinstance(rec, dict):
            rec = record.to_dict()

        sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
        entry_parent = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else sub

        location = (
            sub.get("Location")
            or rec.get("Location")
            or entry_parent.get("Location")
            or "General Kitchen"
        )
        sign = (
            sub.get("Sign")
            or sub.get("sign")
            or rec.get("Sign")
            or rec.get("user.email")
            or "Staff"
        )

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

        raw_time = sub.get("Time") or entry_parent.get("Time") or ""
        time_str = str(raw_time).strip()[:8]

        entries = (
            sub.get("set")
            or sub.get("Entry")
            or rec.get("set")
            or rec.get("Entry")
            or []
        )

        if isinstance(entries, dict):
            entries = [entries]
        elif not isinstance(entries, list):
            entries = [sub] if isinstance(sub, dict) else []

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
            wash_temp = pd.to_numeric(str(wash_raw).replace("°C", "").replace("°", "").strip(), errors="coerce")

            rinse_raw = e.get("finalTemp") or e.get("Final Rinse Cycle Temperature °C") or e.get("rinse_temp")
            rinse_temp = pd.to_numeric(str(rinse_raw).replace("°C", "").replace("°", "").strip(), errors="coerce")

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
                "Machine_Type": str(machine_type),
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

    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Unit_ID", "Wash_Temp", "Rinse_Temp"], keep="first")
    return df_out


def render_record_13_view(raw_df, selected_day_str, start_date, end_date):
    df_items = parse_record_13_submissions(raw_df)

    with st.expander("🔍 Record 13 Diagnostic (Inspect loaded data)"):
        st.write(f"Total parsed warewash records: **{len(df_items)}**")
        if not df_items.empty and "Date_Obj" in df_items.columns:
            date_counts = df_items["Date_Obj"].dropna().value_counts().sort_index(ascending=False).to_dict()
            st.write("Records per date found:", {str(k): v for k, v in date_counts.items()})

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

    with tab_day:
        day_df = (
            range_df[range_df["Date_Str"] == selected_day_str]
            if not range_df.empty
            else pd.DataFrame()
        )

        excursions_count = 0
        compliant_count = 0
        inactive_count = 0
        pending_count = 0

        for loc_name, units in LOCATION_CATALOG.items():
            loc_day_df = day_df[day_df["Location"].str.lower() == loc_name.lower()] if not day_df.empty else pd.DataFrame()
            for u in units:
                u_id = u["Unit_ID"]
                u_logs = loc_day_df[loc_day_df["Unit_ID"] == u_id] if not loc_day_df.empty else pd.DataFrame()
                if u_logs.empty:
                    pending_count += 1
                else:
                    latest = u_logs.iloc[-1]
                    if not latest["In_Use"]:
                        inactive_count += 1
                    elif latest["Has_Breach"]:
                        excursions_count += 1
                    else:
                        compliant_count += 1

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{excursions_count}</div><div class="kpi-lbl">Sanitization Breaches</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{compliant_count}</div><div class="kpi-lbl">Verified Compliant</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{pending_count}</div><div class="kpi-lbl">Pending / Unlogged Units</div></div>', unsafe_allow_html=True)
        with k4:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Audited</div></div>', unsafe_allow_html=True)

        st.write("")
        st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>🏢 Location-wise Unit Audit Summary ({selected_day_str})</h4>", unsafe_allow_html=True)

        loc_cols = st.columns(2)
        for idx, (loc_name, units) in enumerate(LOCATION_CATALOG.items()):
            col_target = loc_cols[idx % 2]
            loc_day_df = day_df[day_df["Location"].str.lower() == loc_name.lower()] if not day_df.empty else pd.DataFrame()

            units_html = ""
            for u in units:
                u_id = u["Unit_ID"]
                u_type = u["Type"]
                u_logs = loc_day_df[loc_day_df["Unit_ID"] == u_id] if not loc_day_df.empty else pd.DataFrame()

                if u_logs.empty:
                    badge = "<span style='color:#d97706; font-weight:700; float:right;'>⏳ Pending</span>"
                    detail = "<div style='font-size:0.72rem; color:#b45309; margin-top:2px;'>No log submitted today</div>"
                    border_c = "#d97706"
                else:
                    latest = u_logs.iloc[-1]
                    if not latest["In_Use"]:
                        badge = "<span style='color:#64748b; font-weight:700; float:right;'>STANDBY</span>"
                        detail = "<div style='font-size:0.72rem; color:#64748b; margin-top:2px;'>Logged: Not In Use</div>"
                        border_c = "#94a3b8"
                    elif latest["Has_Breach"]:
                        badge = "<span style='color:#dc2626; font-weight:700; float:right;'>🔴 BREACH</span>"
                        detail = f"<div style='font-size:0.72rem; color:#dc2626; margin-top:2px; font-weight:700;'>Wash: {latest['Wash_Temp']}°C | Rinse: {latest['Rinse_Temp']}°C</div>"
                        border_c = "#dc2626"
                    else:
                        badge = "<span style='color:#16a34a; font-weight:700; float:right;'>✓ Compliant</span>"
                        detail = f"<div style='font-size:0.72rem; color:#15803d; margin-top:2px;'>Wash: {latest['Wash_Temp']}°C | Rinse: {latest['Rinse_Temp']}°C</div>"
                        border_c = "#16a34a"

                units_html += f'<div style="background:#f8fafc; border-left:3px solid {border_c}; padding:8px 10px; border-radius:4px; margin-bottom:8px;"><div style="font-size:0.85rem; color:#0f172a; font-weight:700;">⚙️ {u_id} <span style="font-weight:normal; color:#64748b; font-size:0.75rem;">({u_type})</span> {badge}</div>{detail}</div>'

            card_html = f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-top:4px solid #0f172a; border-radius:6px; padding:12px 16px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.05);"><div style="font-weight:700; font-size:1rem; color:#0f172a; border-bottom:1px solid #f1f5f9; padding-bottom:6px; margin-bottom:10px;">📍 {loc_name} <span style="font-size:0.75rem; color:#64748b; font-weight:normal;">({len(units)} Units)</span></div>{units_html}</div>'
            col_target.markdown(card_html, unsafe_allow_html=True)

    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec13_page" not in st.session_state:
            st.session_state.rec13_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

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

        filter_options = ["All Kitchen Areas"] + list(LOCATION_CATALOG.keys())
        selected_location_filter = st.selectbox("📍 Filter Kitchen Area:", options=filter_options)

        locations_to_show = (
            list(LOCATION_CATALOG.keys())
            if selected_location_filter == "All Kitchen Areas"
            else [selected_location_filter]
        )

        for location in locations_to_show:
            units = LOCATION_CATALOG[location]
            loc_df = (
                range_df[range_df["Location"].str.lower() == location.lower()]
                if not range_df.empty
                else pd.DataFrame()
            )

            total_units = len(units)
            active_count = len(loc_df) if not loc_df.empty else 0
            badge_color = "#16a34a" if active_count > 0 else "#64748b"
            badge_text = f"{active_count} Logs Recorded" if active_count > 0 else "Standby / No Logs"

            st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:6px solid #0f172a; border-radius:8px; padding:10px 14px; margin-top:1.2rem; margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;"><div style="font-size:1.05rem; font-weight:700; color:#0f172a;">📍 {location} <span style="font-size:0.8rem; font-weight:500; color:#64748b;">({total_units} Assigned Units)</span></div><div style="background:{badge_color}; color:#ffffff; font-size:0.75rem; font-weight:700; padding:3px 10px; border-radius:12px;">{badge_text}</div></div>', unsafe_allow_html=True)

            cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])
            cols[0].markdown('<div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.8rem; padding:8px 4px; border-radius:6px; text-align:center;">Unit & Machine</div>', unsafe_allow_html=True)

            for i, d in enumerate(page_dates):
                cols[i + 1].markdown(f'<div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.78rem; padding:8px 2px; border-radius:6px; text-align:center;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

            st.write("")

            for u in units:
                unit = u["Unit_ID"]
                m_type = u["Type"]

                row_cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])

                row_cols[0].markdown(f'<div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:8px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:105px; display:flex; flex-direction:column; align-items:center; justify-content:center;"><div style="font-weight:700; color:#0f172a; font-size:0.85rem;">{unit}</div><div style="font-size:0.72rem; color:#64748b; margin-top:2px;">{m_type}</div></div>', unsafe_allow_html=True)

                u_df = loc_df[loc_df["Unit_ID"] == unit] if not loc_df.empty else pd.DataFrame()

                for i, d in enumerate(page_dates):
                    d_str = d.strftime("%d/%m/%Y")
                    matches = u_df[u_df["Date_Str"] == d_str] if not u_df.empty else pd.DataFrame()

                    if matches.empty:
                        row_cols[i + 1].markdown('<div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:105px; display:flex; align-items:center; justify-content:center;"><span style="color:#b45309; font-weight:600; font-size:0.8rem;">⏳ Pending</span></div>', unsafe_allow_html=True)
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

                        row_cols[i + 1].markdown(f'<div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:6px 3px; text-align:center; min-height:105px; box-shadow:0 1px 3px rgba(0,0,0,0.08);"><div>{status_badge}</div><div style="height:1px; background:#e2e8f0; margin:4px 0;"></div><div style="font-size:0.8rem; font-weight:700; color:#0f172a; line-height:1.2;">{temp_detail}</div><div style="font-size:0.65rem; color:#64748b; margin-top:3px;">By: {latest['Sign']}</div></div>', unsafe_allow_html=True)

                st.write("")

        st.divider()

        with st.expander("📋 View All Individual Sanitization Records"):
            if not range_df.empty:
                show_cols = [c for c in [
                    "Date_Str", "Time", "Location", "Machine_Type", "Unit_ID", "Status_Text", "Wash_Temp", "Rinse_Temp", "Sign"
                ] if c in range_df.columns]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
