from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# Master catalog of 7 Ice Machines across 3 Locations
ICE_MACHINE_CATALOG = {
    "Filia Kitchen": [
        {"Unit_ID": "RMO/FK/IM/01", "Name": "Ice Machine 01"},
        {"Unit_ID": "RMO/FK/IM/02", "Name": "Ice Machine 02"},
        {"Unit_ID": "RMO/FK/IM/03", "Name": "Ice Machine 03"},
    ],
    "Third Room Kitchen": [
        {"Unit_ID": "RMO/TRK/IM/01", "Name": "Ice Machine 01"},
        {"Unit_ID": "RMO/TRK/IM/02", "Name": "Ice Machine 02"},
    ],
    "Black Lacquer": [
        {"Unit_ID": "RMO/BL/IM/01", "Name": "Ice Machine 01"},
        {"Unit_ID": "RMO/BL/IM/02", "Name": "Ice Machine 02"},
    ],
}


def clean_str(val):
    """Normalizes string for comparison."""
    if not val or pd.isna(val):
        return ""
    return (
        str(val)
        .replace("/", "")
        .replace("_", "")
        .replace(" ", "")
        .replace("-", "")
        .strip()
        .upper()
    )


def parse_record_25_submissions(raw_df):
    """Parses Record 25 Ice Machine cleaning submissions targeting the exact schema."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    flat_master = []
    for loc, units in ICE_MACHINE_CATALOG.items():
        for u in units:
            flat_master.append({"Location": loc, "Unit_ID": u["Unit_ID"]})

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.get("raw_record") if "raw_record" in raw_df.columns else record.to_dict()
        if not isinstance(rec, dict):
            rec = record.to_dict()

        sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec

        raw_date = (
            sub.get("date")
            or rec.get("submission.date")
            or sub.get("Date")
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
            if parsed_dt.tzinfo is None:
                parsed_dt_ist = parsed_dt + timedelta(hours=5, minutes=30)
            else:
                parsed_dt_ist = parsed_dt.tz_convert("Asia/Kolkata")
            date_str = parsed_dt_ist.strftime("%d/%m/%Y")
            date_obj = parsed_dt_ist.date()
        else:
            date_str = str(raw_date)[:10]
            date_obj = None

        kitchen_location = str(
            sub.get("Ice_Machine_Location")
            or rec.get("submission.Ice_Machine_Location")
            or sub.get("Location")
            or rec.get("submission.Location")
            or rec.get("Location")
            or ""
        ).strip()

        raw_unit = (
            sub.get("location")
            or rec.get("submission.location")
            or sub.get("Ice_Machine_Number")
            or rec.get("submission.Ice_Machine_Number")
            or rec.get("Ice Machine Number")
            or ""
        )

        clean_raw_unit = clean_str(raw_unit)
        matched_id = None
        matched_loc = kitchen_location

        for m in flat_master:
            if clean_raw_unit == clean_str(m["Unit_ID"]):
                matched_id = m["Unit_ID"]
                matched_loc = m["Location"]
                break

        final_unit = matched_id if matched_id else str(raw_unit).strip()

        status_raw = str(
            sub.get("USE")
            or rec.get("submission.USE")
            or sub.get("In_Use_Not_In_Use")
            or rec.get("In Use / Not In Use")
            or "IN USE"
        ).strip().upper()
        is_in_use = "NOT" not in status_raw

        sign = (
            sub.get("sign")
            or rec.get("submission.sign")
            or sub.get("Sign")
            or rec.get("submission.Sign")
            or rec.get("Sign (Initial)")
            or "Staff"
        )

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Location": matched_loc or "General Area",
            "Unit_ID": final_unit,
            "Clean_Unit": clean_str(final_unit),
            "In_Use": is_in_use,
            "Status_Text": status_raw,
            "Sign": str(sign).strip(),
        })

    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out = df_out.drop_duplicates(subset=["Date_Str", "Location", "Unit_ID"], keep="first")
    return df_out


def render_record_25_view(raw_df, selected_day_str, start_date, end_date):
    df_items = parse_record_25_submissions(raw_df)

    with st.expander("🔍 Record 25 Diagnostic (Inspect loaded data)"):
        st.write(f"Total parsed ice machine records: **{len(df_items)}**")
        if not df_items.empty and "Date_Obj" in df_items.columns:
            date_counts = df_items["Date_Obj"].dropna().value_counts().sort_index(ascending=False).to_dict()
            st.write("Records per date found:", {str(k): v for k, v in date_counts.items()})

    if not df_items.empty and "Date_Obj" in df_items.columns and df_items["Date_Obj"].notna().any():
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"Today - {selected_day_str}",
        "Weekly",
    ])

    with tab_day:
        day_df = (
            range_df[range_df["Date_Str"] == selected_day_str]
            if not range_df.empty
            else pd.DataFrame()
        )

        cleaned_count = 0
        inactive_count = 0
        pending_count = 0

        location_parsed_data = {}

        for loc_name, units in ICE_MACHINE_CATALOG.items():
            loc_day_df = day_df[day_df["Location"].str.lower() == loc_name.lower()] if not day_df.empty else pd.DataFrame()
            loc_pending = []
            loc_cleaned = []

            for u in units:
                u_id = u["Unit_ID"]
                u_name = u["Name"]
                u_token = clean_str(u_id)

                u_logs = pd.DataFrame()
                if not loc_day_df.empty and "Clean_Unit" in loc_day_df.columns:
                    u_logs = loc_day_df[loc_day_df["Clean_Unit"] == u_token]

                if u_logs.empty:
                    pending_count += 1
                    loc_pending.append({"Unit_ID": u_id, "Name": u_name})
                else:
                    latest = u_logs.iloc[-1]
                    if not latest["In_Use"]:
                        inactive_count += 1
                    else:
                        cleaned_count += 1
                        loc_cleaned.append({"Unit_ID": u_id, "Name": u_name, "Log": latest})

            location_parsed_data[loc_name] = {
                "Pending": loc_pending,
                "Cleaned": loc_cleaned
            }

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{cleaned_count}</div><div class="kpi-lbl">Cleaned & In Use</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{pending_count}</div><div class="kpi-lbl">Pending / Unlogged Units</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Audited</div></div>', unsafe_allow_html=True)

        st.write("")
        st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>🧊 Ice Machine Cleaning Summary ({selected_day_str})</h4>", unsafe_allow_html=True)

        # 2-Side Layout: Left = Pending, Right = Cleaned
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown('<div style="background:#fffbeb; border:1px solid #fde68a; border-left:5px solid #d97706; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#b45309; font-size:0.98rem;">⏳ Pending Ice Machines by Area</b></div>', unsafe_allow_html=True)
            
            has_pending = False
            for loc_name, data in location_parsed_data.items():
                p_units = data["Pending"]
                if p_units:
                    has_pending = True
                    units_html = ""
                    for p in p_units:
                        units_html += f'<div style="background:#f8fafc; border-left:3px solid #d97706; padding:6px 10px; border-radius:4px; margin-bottom:6px;"><div style="font-size:0.82rem; color:#0f172a; font-weight:700;">🧊 {p["Unit_ID"]} <span style="font-weight:normal; color:#64748b; font-size:0.72rem;">({p["Name"]})</span><span style="color:#d97706; font-weight:700; float:right;">Pending</span></div><div style="font-size:0.7rem; color:#b45309; margin-top:2px;">No cleaning log submitted today</div></div>'
                    
                    st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #0f172a; border-radius:6px; padding:10px 14px; margin-bottom:12px;"><div style="font-weight:700; font-size:0.9rem; color:#0f172a; margin-bottom:8px;">📍 {loc_name} <span style="font-size:0.7rem; color:#b45309;">({len(p_units)} pending)</span></div>{units_html}</div>', unsafe_allow_html=True)

            if not has_pending:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:12px; border-radius:6px; color:#16a34a; font-size:0.85rem; text-align:center;">All ice machines across all areas have been cleaned and logged!</div>', unsafe_allow_html=True)

        with col_right:
            st.markdown('<div style="background:#f0fdf4; border:1px solid #bbf7d0; border-left:5px solid #16a34a; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#15803d; font-size:0.98rem;">🟢 Cleaned Units by Area</b></div>', unsafe_allow_html=True)
            
            has_cleaned = False
            for loc_name, data in location_parsed_data.items():
                c_units = data["Cleaned"]
                if c_units:
                    has_cleaned = True
                    units_html = ""
                    for c in c_units:
                        log = c["Log"]
                        units_html += f'<div style="background:#f8fafc; border-left:3px solid #16a34a; padding:6px 10px; border-radius:4px; margin-bottom:6px;"><div style="font-size:0.82rem; color:#0f172a; font-weight:700;">🧊 {c["Unit_ID"]} <span style="font-weight:normal; color:#64748b; font-size:0.72rem;">({c["Name"]})</span><span style="color:#16a34a; font-weight:700; float:right;">✓ Cleaned</span></div><div style="font-size:0.72rem; color:#15803d; margin-top:2px;">Status: In Use | Sign: {log["Sign"]}</div></div>'
                    
                    st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-top:3px solid #0f172a; border-radius:6px; padding:10px 14px; margin-bottom:12px;"><div style="font-weight:700; font-size:0.9rem; color:#0f172a; margin-bottom:8px;">📍 {loc_name} <span style="font-size:0.7rem; color:#15803d;">({len(c_units)} cleaned)</span></div>{units_html}</div>', unsafe_allow_html=True)

            if not has_cleaned:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:12px; border-radius:6px; color:#64748b; font-size:0.85rem; text-align:center;">No cleaning logs recorded for today.</div>', unsafe_allow_html=True)

    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec25_page" not in st.session_state:
            st.session_state.rec25_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button(
                "⬅️ Previous 7 Days",
                key="r25_prev",
                disabled=(st.session_state.rec25_page <= 0),
                use_container_width=True,
            ):
                st.session_state.rec25_page -= 1
                st.rerun()

        with nav3:
            if st.button(
                "Next 7 Days ➡️",
                key="r25_next",
                disabled=(st.session_state.rec25_page >= max_page),
                use_container_width=True,
            ):
                st.session_state.rec25_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec25_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with nav2:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec25_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.write("")

        filter_options = ["All Areas"] + list(ICE_MACHINE_CATALOG.keys())
        selected_filter = (
            st.selectbox("📍 Filter Ice Machine Area:", options=filter_options)
            or "All Areas"
        )

        locations_to_show = (
            list(ICE_MACHINE_CATALOG.keys())
            if selected_filter == "All Areas"
            else [selected_filter]
        )

        for location in locations_to_show:
            units = ICE_MACHINE_CATALOG[location]
            unit_tokens = [clean_str(u["Unit_ID"]) for u in units]

            if not range_df.empty and "Clean_Unit" in range_df.columns:
                loc_df = range_df[range_df["Clean_Unit"].isin(unit_tokens)]
            else:
                loc_df = pd.DataFrame()

            total_units = len(units)
            logs_count = len(loc_df) if not loc_df.empty else 0
            badge_color = "#16a34a" if logs_count > 0 else "#64748b"
            badge_text = f"{logs_count} Cleaning Logs" if logs_count > 0 else "No Logs In Window"

            st.markdown(
                f"""
            <div style="background:#ffffff; border:1px solid #cbd5e1; border-left:6px solid #0f172a; border-radius:8px; padding:10px 14px; margin-top:1.2rem; margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:1.05rem; font-weight:700; color:#0f172a;">🧊 {location} <span style="font-size:0.8rem; font-weight:500; color:#64748b;">({total_units} Assigned Ice Machines)</span></div>
                <div style="background:{badge_color}; color:#ffffff; font-size:0.75rem; font-weight:700; padding:3px 10px; border-radius:12px;">{badge_text}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])
            cols[0].markdown(
                """
            <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.8rem; padding:8px 4px; border-radius:6px; text-align:center;">
                Ice Machine ID
            </div>
            """,
                unsafe_allow_html=True,
            )

            for i, d in enumerate(page_dates):
                cols[i + 1].markdown(
                    f"""
                <div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.78rem; padding:8px 2px; border-radius:6px; text-align:center;">
                    {d.strftime('%d/%m (%a)')}
                </div>
                """,
                    unsafe_allow_html=True,
                )

            st.write("")

            for u in units:
                unit_id = u["Unit_ID"]
                unit_token = clean_str(unit_id)

                row_cols = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1])

                row_cols[0].markdown(
                    f"""
                <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:8px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:105px; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                    <div style="font-weight:700; color:#0f172a; font-size:0.85rem;">{unit_id}</div>
                    <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">{location}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                u_df = loc_df[loc_df["Clean_Unit"] == unit_token] if not loc_df.empty else pd.DataFrame()

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
                            """
                        <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:105px; display:flex; align-items:center; justify-content:center;">
                            <span style="color:#b45309; font-weight:600; font-size:0.8rem;">⏳ Pending</span>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    else:
                        latest = matches.iloc[-1]
                        if latest["In_Use"]:
                            status_badge = '<span style="color:#16a34a; font-weight:800; font-size:0.85rem;">✓ CLEANED</span>'
                            detail_txt = '<span style="color:#16a34a; font-weight:600;">IN USE</span>'
                            card_border = "1.5px solid #0f172a"
                        else:
                            status_badge = '<span style="color:#64748b; font-weight:700; font-size:0.82rem;">STANDBY</span>'
                            detail_txt = '<span style="color:#64748b; font-weight:600;">NOT IN USE</span>'
                            card_border = "1.5px solid #94a3b8"

                        row_cols[i + 1].markdown(
                            f"""
                        <div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:6px 3px; text-align:center; min-height:105px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                            <div>{status_badge}</div>
                            <div style="height:1px; background:#e2e8f0; margin:4px 0;"></div>
                            <div style="font-size:0.75rem; color:#0f172a; margin-top:2px;">
                                {detail_txt}
                            </div>
                            <div style="font-size:0.68rem; color:#64748b; font-weight:600; margin-top:4px;">By: {latest['Sign']}</div>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )

                st.write("")

        st.divider()

        with st.expander("📋 View All Individual Ice Machine Cleaning Records"):
            if not range_df.empty:
                show_cols = [
                    c
                    for c in [
                        "Date_Str",
                        "Location",
                        "Unit_ID",
                        "Status_Text",
                        "Sign",
                    ]
                    if c in range_df.columns
                ]
                st.dataframe(
                    range_df[show_cols],
                    use_container_width=True,
                    hide_index=True,
                )
