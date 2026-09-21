from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

CRITICAL_LIMIT_DEFROST = 5.0  # Max final temp: <= 5.0°C


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


def parse_record_12_submissions(raw_df):
    """Parses Record 12 Defrosting Temperature submissions."""
    if raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()

        # 1. Location (supports standard or 'Location (Other)')
        loc_main = find_val(rec, ["locationother", "location_other"])
        if not loc_main:
            loc_main = find_val(rec, ["location"]) or "Main Kitchen"

        # 2. Food Name (supports Name of Food or Other)
        food_main = find_val(rec, ["nameoffoodother", "foodother"])
        if not food_main:
            food_main = find_val(rec, ["nameoffood", "food"]) or "Defrosted Item"

        # 3. Dates (Finish Date is the official Date of Record)
        finish_raw = find_val(rec, ["finishdate", "enddate", "date", "createdat"]) or ""
        finish_dt = pd.to_datetime(finish_raw, errors="coerce")
        if pd.isna(finish_dt):
            finish_dt = pd.to_datetime(finish_raw, dayfirst=True, errors="coerce")

        if pd.notna(finish_dt):
            finish_str = finish_dt.strftime("%d/%m/%Y")
            finish_date_obj = finish_dt.date()
        else:
            finish_str = str(finish_raw)[:10]
            finish_date_obj = None

        start_raw = find_val(rec, ["startdate"]) or ""
        start_dt = pd.to_datetime(start_raw, errors="coerce")
        if pd.isna(start_dt):
            start_dt = pd.to_datetime(start_raw, dayfirst=True, errors="coerce")

        if pd.notna(start_dt):
            start_str = start_dt.strftime("%d/%m/%Y")
            start_date_obj = start_dt.date()
        else:
            start_str = str(start_raw)[:10]
            start_date_obj = None

        # 4. Start Date Rule Check (Should be 1 day prior)
        date_rule_valid = True
        duration_note = "Valid (24h)"
        if start_date_obj and finish_date_obj:
            days_diff = (finish_date_obj - start_date_obj).days
            if days_diff != 1:
                date_rule_valid = False
                duration_note = f"Anomaly: {days_diff}d diff (Expected 1d)"

        # 5. Times
        start_time = str(find_val(rec, ["starttime"]) or "")[:8]
        finish_time = str(find_val(rec, ["finishtime", "time"]) or "")[:8]

        # 6. Temperatures
        start_temp_raw = find_val(rec, ["starttemperature", "starttemp"])
        start_temp = pd.to_numeric(str(start_temp_raw).replace("°C", "").strip(), errors="coerce")

        final_temp_raw = find_val(rec, [
            "finaldefrostingtemperature", 
            "finaltemperature", 
            "finaltemp", 
            "defrostingtemperature"
        ])
        final_temp = pd.to_numeric(str(final_temp_raw).replace("°C", "").strip(), errors="coerce")

        sign = find_val(rec, ["signfullname", "sign", "initial", "user.email"]) or "Staff"

        rows.append({
            "Date_Str": finish_str,            # Finish Date drives the compliance audit
            "Date_Obj": finish_date_obj,
            "Start_Date_Str": start_str,
            "Start_Date_Obj": start_date_obj,
            "Date_Rule_Valid": date_rule_valid,
            "Duration_Note": duration_note,
            "Start_Time": start_time,
            "Finish_Time": finish_time,
            "Location": loc_main,
            "Food": food_main,
            "Start_Temp": start_temp,
            "Final_Temp": final_temp,
            "Sign": sign
        })

    return pd.DataFrame(rows)


def render_record_12_view(raw_df, selected_day_str, start_date, end_date):
    """Renders single-day drilldown and 7-day paginated matrix for Record 12."""
    df_items = parse_record_12_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date) & 
            (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([f"📅 Daily Defrost ({selected_day_str})", "📈 7-Day Matrix (1-Month Browser)"])

    # -------------------------------------------------------------
    # TAB 1: DAILY DRILLDOWN
    # -------------------------------------------------------------
    with tab_day:
        day_df = range_df[range_df["Date_Str"] == selected_day_str] if not range_df.empty else pd.DataFrame()

        excursions = []
        date_anomalies = []
        compliant_logs = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if pd.notna(r["Final_Temp"]) and r["Final_Temp"] > CRITICAL_LIMIT_DEFROST:
                    excursions.append(r.to_dict())
                elif not r["Date_Rule_Valid"]:
                    date_anomalies.append(r.to_dict())
                else:
                    compliant_logs.append(r.to_dict())

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">Temp Breaches (&gt; 5.0°C)</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{len(date_anomalies)}</div><div class="kpi-lbl">Date Anomalies (≠ 1 Day)</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_logs)}</div><div class="kpi-lbl">Verified Defrosted</div></div>', unsafe_allow_html=True)
        with k4:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Items Finished</div></div>', unsafe_allow_html=True)

        st.write("")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Core Temp Breaches ({len(excursions)})</div>', unsafe_allow_html=True)
            if excursions:
                for exc in excursions:
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{exc['Food']} • {exc['Location']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            Final Temp: {exc['Final_Temp']}°C (Limit ≤ 5.0°C)
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Started: {exc['Start_Date_Str']} | Initial: {exc['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No temperature excursions on this day.")
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#d97706;">🟡 Date Anomalies ({len(date_anomalies)})</div>', unsafe_allow_html=True)
            if date_anomalies:
                for anom in date_anomalies:
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #d97706;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{anom['Food']} • {anom['Location']}</div>
                        <div style="font-size:0.8rem; color:#d97706; font-weight:600; margin-top:3px;">
                            {anom['Duration_Note']}
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Start: {anom['Start_Date_Str']} ➔ Finish: {anom['Date_Str']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("All batches follow standard 1-day defrost.")
            st.markdown('</div>', unsafe_allow_html=True)

        with c3:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Verified Defrosted ({len(compliant_logs)})</div>', unsafe_allow_html=True)
            if compliant_logs:
                for ok in compliant_logs:
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Food']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Final: <b style="color:#16a34a;">{ok['Final_Temp']}°C</b> (Start: {ok['Start_Temp']}°C)
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Area: {ok['Location']} | Sign: {ok['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No completed defrost logs for this day.")
            st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: 7-DAY SPLIT-CELL AUDIT GRID
    # -------------------------------------------------------------
    with tab_matrix:
        st.subheader("7-Day Defrosting Completion Matrix")

        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec12_page" not in st.session_state:
            st.session_state.rec12_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        col_prev, col_status, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("⬅️ Previous 7 Days", key="r12_prev", disabled=(st.session_state.rec12_page <= 0), use_container_width=True):
                st.session_state.rec12_page -= 1
                st.rerun()

        with col_next:
            if st.button("Next 7 Days ➡️", key="r12_next", disabled=(st.session_state.rec12_page >= max_page), use_container_width=True):
                st.session_state.rec12_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec12_page * 7
        page_dates = all_dates[p_start_idx:p_start_idx + 7]

        with col_status:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: {page_dates[0].strftime('%d/%m/%Y')} to {page_dates[-1].strftime('%d/%m/%Y')} (Block {st.session_state.rec12_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.write("")

        # 8 Columns
        cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
        cols[0].markdown("""
        <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.85rem; padding:10px 4px; border-radius:6px; text-align:center;">
            Kitchen Area
        </div>
        """, unsafe_allow_html=True)

        for i, d in enumerate(page_dates):
            cols[i+1].markdown(f"""
            <div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.8rem; padding:10px 2px; border-radius:6px; text-align:center;">
                {d.strftime('%d/%m (%a)')}
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # Dynamically discovers all locations present in the data
        all_kitchens = sorted(list(range_df["Location"].unique())) if not range_df.empty and "Location" in range_df.columns else ["Filia Kitchen"]

        for kitchen in all_kitchens:
            row_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])

            row_cols[0].markdown(f"""
            <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:12px 6px; font-weight:700; color:#0f172a; font-size:0.88rem; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:115px; display:flex; align-items:center; justify-content:center;">
                {kitchen}
            </div>
            """, unsafe_allow_html=True)

            k_df = range_df[range_df["Location"] == kitchen] if not range_df.empty else pd.DataFrame()

            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                matches = k_df[k_df["Date_Str"] == d_str] if not k_df.empty else pd.DataFrame()

                if matches.empty:
                    row_cols[i+1].markdown("""
                    <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:115px; display:flex; align-items:center; justify-content:center;">
                        <span style="color:#94a3b8; font-weight:700; font-size:1.2rem;">—</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    count = len(matches)
                    foods_list = matches["Food"].dropna().tolist()
                    foods_text = ", ".join(foods_list)

                    row_cols[i+1].markdown(f"""
                    <div style="background:#ffffff; border:1.5px solid #0f172a; border-radius:8px; padding:8px 4px; text-align:center; min-height:115px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div style="font-size:1.3rem; font-weight:800; color:#0f172a; line-height:1;">{count}</div>
                        <div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>
                        <div style="font-size:0.75rem; font-weight:600; color:#0f172a; line-height:1.3; word-wrap:break-word;">
                            {foods_text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

        st.divider()

        with st.expander("📋 View All Individual Defrosting Records"):
            if not range_df.empty:
                show_cols = [c for c in [
                    "Date_Str", "Start_Date_Str", "Start_Time", "Finish_Time", "Location", "Food", "Start_Temp", "Final_Temp", "Duration_Note", "Sign"
                ] if c in range_df.columns]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
