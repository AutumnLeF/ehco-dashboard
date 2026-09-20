from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

HOT_MIN_TEMP = 70.0   # Hot food display limit >= 70.0°C
COLD_MAX_TEMP = 5.0   # Cold food display limit <= 5.0°C


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


def parse_record_06_submissions(raw_df):
    """Parses Record 06 Food Display Temperature submissions."""
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

        time_str = str(
            sub.get("Time")
            or sub.get("time")
            or rec.get("submission.Time")
            or rec.get("submission.time")
            or extract_field(rec, ["time"])
            or ""
        )[:8]

        # 2. Location
        location = str(
            sub.get("Location")
            or sub.get("location")
            or rec.get("submission.Location")
            or rec.get("Location")
            or "Filia Restaurant"
        ).strip()

        # 3. Buffet Status: "Buffet operational / No buffet"
        buffet_status = str(
            sub.get("Buffet operational / No buffet")
            or rec.get("submission.Buffet operational / No buffet")
            or extract_field(rec, ["buffetoperational", "nobuffet", "buffet"])
            or "Operational"
        ).strip()
        is_no_buffet = "no buffet" in buffet_status.lower()

        # 4. Meal Service & Holding Type
        meal_service = str(
            sub.get("Meal Service")
            or rec.get("submission.Meal Service")
            or extract_field(rec, ["mealservice", "meal"])
            or ""
        ).strip()

        hot_or_cold = str(
            sub.get("Hot or Cold")
            or rec.get("submission.Hot or Cold")
            or extract_field(rec, ["hotorcold", "hotcold"])
            or ""
        ).strip().capitalize()

        # 5. Food Name Resolution
        hot_name = str(sub.get("Name of Food (Hot)") or rec.get("submission.Name of Food (Hot)") or "").replace("•", "").strip()
        cold_name = str(sub.get("Name of Food (Cold)") or rec.get("submission.Name of Food (Cold)") or "").replace("•", "").strip()
        other_name = str(sub.get("Other Food") or rec.get("submission.Other Food") or extract_field(rec, ["otherfood", "foodname"]) or "").strip()

        if other_name and other_name.lower() not in ["none", "nan", ""]:
            final_food = other_name
        elif hot_name and hot_name.lower() not in ["other", "none", "nan", ""]:
            final_food = hot_name
        elif cold_name and cold_name.lower() not in ["other", "none", "nan", ""]:
            final_food = cold_name
        else:
            final_food = "Buffet Item" if not is_no_buffet else "No Buffet Service"

        # 6. Temperature Declarations & Validation
        hot_temp_raw = (
            sub.get("Food Temperature °C (Hot)")
            or rec.get("submission.Food Temperature °C (Hot)")
            or extract_field(rec, ["foodtemperaturechot", "foodtemperaturehot", "temphot"])
        )
        cold_temp_raw = (
            sub.get("Food Temperature °C (Cold)")
            or rec.get("submission.Food Temperature °C (Cold)")
            or extract_field(rec, ["foodtemperatureccold", "foodtemperaturecold", "tempcold"])
        )

        hot_temp = pd.to_numeric(str(hot_temp_raw).replace("°C", "").strip(), errors="coerce")
        cold_temp = pd.to_numeric(str(cold_temp_raw).replace("°C", "").strip(), errors="coerce")

        has_breach = False
        temp_disp = "—"
        if not is_no_buffet:
            if hot_or_cold.lower() == "hot" or pd.notna(hot_temp):
                temp_disp = f"{hot_temp}°C (Hot)" if pd.notna(hot_temp) else "Hot"
                if pd.notna(hot_temp) and hot_temp < HOT_MIN_TEMP:
                    has_breach = True
            elif hot_or_cold.lower() == "cold" or pd.notna(cold_temp):
                temp_disp = f"{cold_temp}°C (Cold)" if pd.notna(cold_temp) else "Cold"
                if pd.notna(cold_temp) and cold_temp > COLD_MAX_TEMP:
                    has_breach = True

        # 7. Sign
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
            "Time": time_str,
            "Location": location,
            "Is_No_Buffet": is_no_buffet,
            "Meal_Service": meal_service,
            "Type": hot_or_cold,
            "Food": final_food,
            "Hot_Temp": hot_temp,
            "Cold_Temp": cold_temp,
            "Temp_Disp": temp_disp,
            "Has_Breach": has_breach,
            "Sign": str(sign).strip(),
        })

    return pd.DataFrame(rows)


def render_record_06_view(raw_df, selected_day_str, start_date, end_date):
    """Renders Record 06 Daily Audit and 7-Day Matrix."""
    df_items = parse_record_06_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns and df_items["Date_Obj"].notna().any():
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Display Audit ({selected_day_str})",
        "📈 7-Day Display Matrix (1-Month Browser)"
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

        breaches = []
        compliant_items = []
        no_buffet_logs = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if r["Is_No_Buffet"]:
                    no_buffet_logs.append(r.to_dict())
                elif r["Has_Breach"]:
                    breaches.append(r.to_dict())
                else:
                    compliant_items.append(r.to_dict())

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(breaches)}</div><div class="kpi-lbl">Holding Breaches</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_items)}</div><div class="kpi-lbl">Compliant Items</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#64748b;">{len(no_buffet_logs)}</div><div class="kpi-lbl">No Buffet Logs</div></div>',
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Audit Entries</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Temp Breaches ({len(breaches)})</div>',
                unsafe_allow_html=True,
            )
            if breaches:
                for b in breaches:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{b['Food']} • {b['Meal_Service']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            Reading: {b['Temp_Disp']} (Hot must be >= 70°C, Cold <= 5°C)
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Time: {b['Time']} | By: {b['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No hot or cold holding temperature breaches on this date.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Verified Compliant ({len(compliant_items)})</div>',
                unsafe_allow_html=True,
            )
            if compliant_items:
                for ok in compliant_items:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Food']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Meal: <b>{ok['Meal_Service']}</b> &nbsp;|&nbsp; Temp: <b style="color:#16a34a;">{ok['Temp_Disp']}</b>
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Type: {ok['Type']} | By: {ok['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            elif no_buffet_logs:
                st.caption("Buffet logged as 'No Buffet' on this date.")
            else:
                st.caption("No display logs recorded for this day.")
            st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: 7-DAY FULL-WIDTH MATRIX
    # -------------------------------------------------------------
    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec06_page" not in st.session_state:
            st.session_state.rec06_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("⬅️ Previous 7 Days", key="r06_prev", disabled=(st.session_state.rec06_page <= 0), use_container_width=True):
                st.session_state.rec06_page -= 1
                st.rerun()

        with nav3:
            if st.button("Next 7 Days ➡️", key="r06_next", disabled=(st.session_state.rec06_page >= max_page), use_container_width=True):
                st.session_state.rec06_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec06_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with nav2:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec06_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.write("")

        cols = st.columns(7)

        # Date Headers
        for i, d in enumerate(page_dates):
            cols[i].markdown(f"""
            <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.82rem; padding:10px 2px; border-radius:6px; text-align:center; margin-bottom:8px;">
                {d.strftime('%d/%m (%a)')}
            </div>
            """, unsafe_allow_html=True)

        # Daily Display Cards
        for i, d in enumerate(page_dates):
            d_str = d.strftime("%d/%m/%Y")
            matches = pd.DataFrame()
            if not range_df.empty:
                if "Date_Obj" in range_df.columns:
                    matches = range_df[range_df["Date_Obj"] == d]
                if matches.empty and "Date_Str" in range_df.columns:
                    matches = range_df[range_df["Date_Str"] == d_str]

            with cols[i]:
                if matches.empty:
                    st.markdown("""
                    <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:12px 6px; text-align:center; min-height:160px; display:flex; align-items:center; justify-content:center;">
                        <span style="color:#94a3b8; font-weight:600; font-size:0.82rem;">— Not Logged</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    is_all_no_buffet = all(matches["Is_No_Buffet"])
                    signs = ", ".join(list(dict.fromkeys(matches["Sign"].dropna().tolist())))

                    if is_all_no_buffet:
                        st.markdown(f"""
                        <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:10px 6px; text-align:center; min-height:160px; box-shadow:0 1px 2px rgba(0,0,0,0.05);">
                            <div style="color:#64748b; font-weight:800; font-size:0.85rem;">STANDBY</div>
                            <div style="height:1px; background:#e2e8f0; margin:6px 0;"></div>
                            <div style="font-size:0.82rem; font-weight:700; color:#0f172a; margin-top:6px;">
                                No Buffet
                            </div>
                            <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">Filia Restaurant</div>
                            <div style="font-size:0.68rem; color:#94a3b8; margin-top:8px;">By: {signs}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        active_matches = matches[~matches["Is_No_Buffet"]]
                        batch_count = len(active_matches)
                        has_day_breach = any(active_matches["Has_Breach"])

                        foods = list(dict.fromkeys(active_matches["Food"].dropna().tolist()))
                        foods_txt = ", ".join(foods[:3]) + ("..." if len(foods) > 3 else "")

                        meals = list(dict.fromkeys(active_matches["Meal_Service"].dropna().tolist()))
                        meals_txt = " / ".join(meals) if meals else "Service"

                        if has_day_breach:
                            badge = '<span style="color:#dc2626; font-weight:800; font-size:0.9rem;">🔴 BREACH</span>'
                            card_border = "2px solid #dc2626"
                        else:
                            badge = f'<span style="color:#16a34a; font-weight:800; font-size:0.95rem;">✓ {batch_count} Passed</span>'
                            card_border = "1.5px solid #0f172a"

                        st.markdown(f"""
                        <div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:10px 6px; text-align:center; min-height:160px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                            <div>{badge}</div>
                            <div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>
                            <div style="font-size:0.75rem; font-weight:700; color:#0f172a; line-height:1.25; word-wrap:break-word;">
                                {foods_txt}
                            </div>
                            <div style="font-size:0.7rem; color:#475569; margin-top:3px;">
                                {meals_txt}
                            </div>
                            <div style="height:1px; background:#f1f5f9; margin:5px 0;"></div>
                            <div style="font-size:0.68rem; color:#64748b; margin-top:4px;">By: {signs}</div>
                        </div>
                        """, unsafe_allow_html=True)

        st.divider()

        with st.expander("📋 View All Individual Food Display Records"):
            if not range_df.empty:
                show_cols = [
                    c for c in [
                        "Date_Str", "Time", "Location", "Meal_Service", "Type", "Food", "Temp_Disp", "Sign"
                    ] if c in range_df.columns
                ]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
