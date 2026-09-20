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


def clean_unit_token(val):
    """Aggressively strips slashes, spaces, hyphens, and casing."""
    if val is None or pd.isna(val):
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


def extract_field(rec, keywords):
    """Deep search for matching keywords across flat or nested keys."""
    if not isinstance(rec, dict):
        return None
    clean_targets = [
        k.lower().replace("_", "").replace(" ", "").replace(".", "")
        for k in keywords
    ]
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


def parse_record_25_submissions(raw_df):
    """Parses Record 25 Ice Machine cleaning submissions."""
    if raw_df.empty:
        return pd.DataFrame()

    flat_master = []
    for loc, units in ICE_MACHINE_CATALOG.items():
        for u in units:
            flat_master.append({"Location": loc, "Unit_ID": u["Unit_ID"]})

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()

        # 1. Date normalization (Try all date keys)
        raw_date = (
            rec.get("submission.Date")
            or rec.get("Date")
            or (rec.get("submission") or {}).get("Date")
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

        # 2. Location
        location = str(
            rec.get("submission.Location")
            or rec.get("Location")
            or (rec.get("submission") or {}).get("Location")
            or extract_field(rec, ["locationother", "location"])
            or ""
        ).strip()

        # 3. Ice Machine Number
        raw_unit = (
            rec.get("submission.Ice_Machine_Number")
            or rec.get("submission.Ice Machine Number")
            or rec.get("Ice Machine Number")
            or rec.get("Ice_Machine_Number")
            or extract_field(
                rec, ["icemachinenumber", "machinenumber", "unitid", "machine"]
            )
            or ""
        )

        clean_raw_unit = clean_unit_token(raw_unit)
        matched_id = None
        matched_loc = location

        # Direct map against catalog
        for m in flat_master:
            if clean_raw_unit == clean_unit_token(m["Unit_ID"]):
                matched_id = m["Unit_ID"]
                matched_loc = m["Location"]
                break

        final_unit = matched_id if matched_id else str(raw_unit).strip()

        # 4. In Use / Not In Use
        status_raw = str(
            rec.get("submission.In_Use_Not_In_Use")
            or rec.get("In Use / Not In Use")
            or extract_field(rec, ["inusenotinuse", "inuse", "status"])
            or "IN USE"
        ).strip().upper()
        is_in_use = "NOT" not in status_raw

        sign = (
            rec.get("submission.Sign")
            or rec.get("Sign (Initial)")
            or rec.get("Sign")
            or extract_field(rec, ["signinitial", "sign", "initial"])
            or "Staff"
        )

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Location": matched_loc,
            "Unit_ID": final_unit,
            "Clean_Unit": clean_unit_token(final_unit),
            "In_Use": is_in_use,
            "Status_Text": status_raw,
            "Sign": str(sign).strip(),
        })

    return pd.DataFrame(rows)


def render_record_25_view(raw_df, selected_day_str, start_date, end_date):
    """Renders Record 25 daily audit and 7-day grouped cleaning matrix."""
    df_items = parse_record_25_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Cleaning Audit ({selected_day_str})",
        "📈 7-Day Grouped Location Matrix",
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

        cleaned_units = []
        inactive_units = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if not r["In_Use"]:
                    inactive_units.append(r.to_dict())
                else:
                    cleaned_units.append(r.to_dict())

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(cleaned_units)}</div><div class="kpi-lbl">Cleaned & Verified</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#64748b;">{len(inactive_units)}</div><div class="kpi-lbl">Standby / Not In Use</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Audited</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Cleaned & Signed ({len(cleaned_units)})</div>',
                unsafe_allow_html=True,
            )
            if cleaned_units:
                for ok in cleaned_units:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Unit_ID']}</div>
                        <div style="font-size:0.8rem; color:#16a34a; font-weight:600; margin-top:3px;">
                            ✓ Cleaned & Sanitized
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Location: {ok['Location']} | Initial: {ok['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No ice machine cleaning logged for this date.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#64748b;">⚪ Inactive / Standby ({len(inactive_units)})</div>',
                unsafe_allow_html=True,
            )
            if inactive_units:
                for off in inactive_units:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #94a3b8;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{off['Unit_ID']}</div>
                        <div style="font-size:0.8rem; color:#64748b; margin-top:3px;">Status: <b>NOT IN USE</b></div>
                        <div style="font-size:0.75rem; color:#94a3b8; margin-top:2px;">Location: {off['Location']} | Sign: {off['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No machines logged as standby.")
            st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: LOCATION-GROUPED 7-DAY MATRIX
    # -------------------------------------------------------------
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

        # Area Quick Filter Pills
        filter_options = ["All Areas"] + list(ICE_MACHINE_CATALOG.keys())
        selected_filter = (
            st.segmented_control(
                "Filter Ice Machine Area",
                options=filter_options,
                default="All Areas",
                label_visibility="collapsed",
            )
            or "All Areas"
        )

        locations_to_show = (
            list(ICE_MACHINE_CATALOG.keys())
            if selected_filter == "All Areas"
            else [selected_filter]
        )

        for location in locations_to_show:
            units = ICE_MACHINE_CATALOG[location]
            unit_tokens = [clean_unit_token(u["Unit_ID"]) for u in units]

            # Filter by matching any unit assigned to this location
            if not range_df.empty and "Clean_Unit" in range_df.columns:
                loc_df = range_df[range_df["Clean_Unit"].isin(unit_tokens)]
            else:
                loc_df = pd.DataFrame()

            total_units = len(units)
            logs_count = len(loc_df) if not loc_df.empty else 0
            badge_color = "#16a34a" if logs_count > 0 else "#64748b"
            badge_text = (
                f"{logs_count} Cleaning Logs"
                if logs_count > 0
                else "No Logs In Window"
            )

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
                unit_token = clean_unit_token(unit_id)

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

                # Direct match using normalized unit ID
                u_df = (
                    loc_df[loc_df["Clean_Unit"] == unit_token]
                    if not loc_df.empty
                    else pd.DataFrame()
                )

                for i, d in enumerate(page_dates):
                    d_str = d.strftime("%d/%m/%Y")

                    # Match by Date_Obj OR formatted Date_Str
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
                            <span style="color:#94a3b8; font-weight:600; font-size:0.8rem;">— Not Logged</span>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    else:
                        latest = matches.iloc[-1]
                        if not latest["In_Use"]:
                            status_badge = '<span style="color:#64748b; font-weight:700; font-size:0.82rem;">STANDBY</span>'
                            detail_txt = "Not In Use"
                            card_border = "1.5px solid #94a3b8"
                        else:
                            status_badge = '<span style="color:#16a34a; font-weight:800; font-size:0.85rem;">✓ CLEANED</span>'
                            detail_txt = "Sanitized"
                            card_border = "1.5px solid #0f172a"

                        row_cols[i + 1].markdown(
                            f"""
                        <div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:6px 3px; text-align:center; min-height:105px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                            <div>{status_badge}</div>
                            <div style="height:1px; background:#e2e8f0; margin:4px 0;"></div>
                            <div style="font-size:0.78rem; font-weight:700; color:#0f172a;">
                                {detail_txt}
                            </div>
                            <div style="font-size:0.68rem; color:#64748b; margin-top:4px;">By: {latest['Sign']}</div>
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
