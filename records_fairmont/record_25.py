from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# Master catalog of 7 Ice Machines with their scheduled day index (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun)
ICE_MACHINE_CATALOG = {
    "Filia Kitchen": [
        {"Unit_ID": "RMO/FK/IM/01", "Name": "Ice Machine 01", "Day_Idx": 0},  # Monday
        {"Unit_ID": "RMO/FK/IM/02", "Name": "Ice Machine 02", "Day_Idx": 1},  # Tuesday
        {"Unit_ID": "RMO/FK/IM/03", "Name": "Ice Machine 03", "Day_Idx": 2},  # Wednesday
    ],
    "Black Lacquer": [
        {"Unit_ID": "RMO/BL/IM/01", "Name": "Ice Machine 01", "Day_Idx": 3},  # Thursday
        {"Unit_ID": "RMO/BL/IM/02", "Name": "Ice Machine 02", "Day_Idx": 4},  # Friday
    ],
    "Third Room Kitchen": [
        {"Unit_ID": "RMO/TRK/IM/01", "Name": "Ice Machine 01", "Day_Idx": 5},  # Saturday
        {"Unit_ID": "RMO/TRK/IM/02", "Name": "Ice Machine 02", "Day_Idx": 6},  # Sunday
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
            flat_master.append({"Location": loc, "Unit_ID": u["Unit_ID"], "Day_Idx": u["Day_Idx"]})

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

    selected_dt = pd.to_datetime(selected_day_str, format="%d/%m/%Y", errors="coerce")
    selected_day_idx = selected_dt.weekday() if pd.notna(selected_dt) else datetime.now().date().weekday()

    with tab_day:
        day_df = (
            range_df[range_df["Date_Str"] == selected_day_str]
            if not range_df.empty
            else pd.DataFrame()
        )

        scheduled_units_today = []
        for loc_name, units in ICE_MACHINE_CATALOG.items():
            for u in units:
                if u["Day_Idx"] == selected_day_idx:
                    scheduled_units_today.append({"Location": loc_name, **u})

        cleaned_count = 0
        pending_count = 0
        scheduled_status_list = []

        for sch in scheduled_units_today:
            u_id = sch["Unit_ID"]
            u_token = clean_str(u_id)
            u_logs = pd.DataFrame()
            if not day_df.empty and "Clean_Unit" in day_df.columns:
                u_logs = day_df[day_df["Clean_Unit"] == u_token]

            if u_logs.empty:
                pending_count += 1
                scheduled_status_list.append({"Unit": sch, "Status": "Pending", "Log": None})
            else:
                cleaned_count += 1
                scheduled_status_list.append({"Unit": sch, "Status": "Cleaned", "Log": u_logs.iloc[-1]})

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{cleaned_count}</div><div class="kpi-lbl">Scheduled Machine Cleaned</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{pending_count}</div><div class="kpi-lbl">Scheduled Machine Pending</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Logs Submitted Today</div></div>', unsafe_allow_html=True)

        st.write("")
        day_name = selected_dt.strftime("%A") if pd.notna(selected_dt) else "Today"
        st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>🧊 Ice Machine Cleaning Schedule Audit ({day_name} — {selected_day_str})</h4>", unsafe_allow_html=True)
        st.caption("Tracking mandatory daily cleaning compliance as per the weekly cleaning schedule.")

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown('<div style="background:#fffbeb; border:1px solid #fde68a; border-left:5px solid #d97706; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#b45309; font-size:0.98rem;">⏳ Pending Scheduled Ice Machine</b></div>', unsafe_allow_html=True)
            
            if pending_count > 0:
                for item in scheduled_status_list:
                    if item["Status"] == "Pending":
                        sch = item["Unit"]
                        st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:4px solid #d97706; padding:12px; border-radius:6px; margin-bottom:8px;"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🧊 {sch["Unit_ID"]} <span style="font-size:0.8rem; color:#64748b;">({sch["Name"]})</span></div><div style="font-size:0.8rem; color:#b45309; font-weight:700; margin-top:2px;">📍 {sch["Location"]}</div><div style="font-size:0.75rem; color:#b45309; margin-top:2px; font-style:italic;">Mandatory cleaning log not yet submitted for today.</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:14px; border-radius:6px; color:#16a34a; font-size:0.85rem; text-align:center;">✓ Today\'s scheduled ice machine has been successfully cleaned and logged!</div>', unsafe_allow_html=True)

        with col_right:
            st.markdown('<div style="background:#f0fdf4; border:1px solid #bbf7d0; border-left:5px solid #16a34a; padding:10px 14px; border-radius:6px; margin-bottom:12px;"><b style="color:#15803d; font-size:0.98rem;">🟢 Cleaned Ice Machine</b></div>', unsafe_allow_html=True)
            
            if cleaned_count > 0:
                for item in scheduled_status_list:
                    if item["Status"] == "Cleaned":
                        sch = item["Unit"]
                        log = item["Log"]
                        st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:4px solid #16a34a; padding:12px; border-radius:6px; margin-bottom:8px;"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🧊 {sch["Unit_ID"]} <span style="font-size:0.8rem; color:#64748b;">({sch["Name"]})</span></div><div style="font-size:0.8rem; color:#15803d; font-weight:700; margin-top:2px;">📍 {sch["Location"]}</div><div style="font-size:0.75rem; color:#15803d; margin-top:2px;">Status: <b>{log["Status_Text"]}</b> | Signed: {log["Sign"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; padding:14px; border-radius:6px; color:#64748b; font-size:0.85rem; text-align:center;">No cleaning logged yet for today\'s scheduled unit.</div>', unsafe_allow_html=True)

    with tab_matrix:
        st.subheader("Weekly Ice Machine Cleaning Schedule Matrix")
        st.caption("Overview mapping each ice machine to its mandatory cleaning day of the week.")

        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec25_page" not in st.session_state:
            st.session_state.rec25_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("⬅️ Previous 7 Days", key="r25_prev", disabled=(st.session_state.rec25_page <= 0), use_container_width=True):
                st.session_state.rec25_page -= 1
                st.rerun()

        with nav3:
            if st.button("Next 7 Days ➡️", key="r25_next", disabled=(st.session_state.rec25_page >= max_page), use_container_width=True):
                st.session_state.rec25_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec25_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with nav2:
            if page_dates:
                st.markdown(f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec25_page + 1} of {max_page + 1})</div>", unsafe_allow_html=True)

        st.write("")

        cols = st.columns([2.0, 1, 1, 1, 1, 1, 1, 1])
        cols[0].markdown('<div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.85rem; padding:10px 4px; border-radius:6px; text-align:center;">Ice Machine Unit</div>', unsafe_allow_html=True)
        
        for i, d in enumerate(page_dates):
            day_short = d.strftime("%a").upper()
            cols[i + 1].markdown(f'<div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.8rem; padding:10px 2px; border-radius:6px; text-align:center;">{d.strftime("%d/%m")} ({day_short})</div>', unsafe_allow_html=True)

        st.write("")

        all_scheduled_units = []
        for loc_name, units in ICE_MACHINE_CATALOG.items():
            for u in units:
                all_scheduled_units.append({"Location": loc_name, **u})

        for sch in all_scheduled_units:
            unit_id = sch["Unit_ID"]
            unit_name = sch["Name"]
            loc = sch["Location"]
            sched_day = sch["Day_Idx"]
            unit_token = clean_str(unit_id)

            row_cols = st.columns([2.0, 1, 1, 1, 1, 1, 1, 1])
            row_cols[0].markdown(f'<div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:8px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:85px; display:flex; flex-direction:column; align-items:center; justify-content:center;"><div style="font-weight:700; color:#0f172a; font-size:0.85rem;">{unit_id}</div><div style="font-size:0.7rem; color:#64748b; margin-top:2px;">{loc} ({unit_name})</div></div>', unsafe_allow_html=True)

            u_df = range_df[range_df["Clean_Unit"] == unit_token] if not range_df.empty else pd.DataFrame()

            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                col_day_idx = d.weekday()
                is_scheduled_day = (col_day_idx == sched_day)

                matches = pd.DataFrame()
                if not u_df.empty:
                    if "Date_Obj" in u_df.columns:
                        matches = u_df[u_df["Date_Obj"] == d]
                    if matches.empty and "Date_Str" in u_df.columns:
                        matches = u_df[u_df["Date_Str"] == d_str]

                if not matches.empty:
                    latest = matches.iloc[-1]
                    row_cols[i + 1].markdown(f'<div style="background:#f0fdf4; border:1.5px solid #16a34a; border-radius:8px; padding:6px; text-align:center; min-height:85px; display:flex; flex-direction:column; justify-content:center; align-items:center;"><span style="color:#16a34a; font-weight:800; font-size:0.78rem;">✓ CLEANED</span><span style="font-size:0.65rem; color:#15803d; margin-top:3px;">By: {latest["Sign"]}</span></div>', unsafe_allow_html=True)
                elif is_scheduled_day:
                    row_cols[i + 1].markdown(f'<div style="background:#fffbeb; border:1.5px dashed #d97706; border-radius:8px; padding:6px; text-align:center; min-height:85px; display:flex; flex-direction:column; justify-content:center; align-items:center;"><span style="color:#b45309; font-weight:800; font-size:0.78rem;">⏳ SCHEDULED</span><span style="font-size:0.65rem; color:#b45309; margin-top:3px;">Pending Log</span></div>', unsafe_allow_html=True)
                else:
                    row_cols[i + 1].markdown(f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:6px; text-align:center; min-height:85px; display:flex; align-items:center; justify-content:center;"><span style="color:#cbd5e1; font-size:0.8rem;">—</span></div>', unsafe_allow_html=True)

            st.write("")

        st.divider()
        with st.expander("📋 View All Individual Ice Machine Cleaning Records"):
            if not range_df.empty:
                show_cols = [c for c in ["Date_Str", "Location", "Unit_ID", "Status_Text", "Sign"] if c in range_df.columns]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
