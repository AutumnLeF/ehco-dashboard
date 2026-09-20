import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

TARGET_PPM = 100.0       # Chlorine PPM must be 100
TARGET_MINUTES = 5.0    # Contact time must be 5 minutes


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


def parse_record_21_submissions(raw_df):
    """Parses Record 21 submissions matching the exact submission.CL payload structure."""
    if raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()

        # 1. Date normalization
        raw_date = (
            rec.get("submission.Date")
            or rec.get("Date")
            or extract_field(rec, ["date", "createdat", "submissiondate"])
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

        time_str = str(rec.get("submission.Time") or rec.get("Time") or extract_field(rec, ["time"]) or "")[:8]
        location = (
            rec.get("submission.Location")
            or rec.get("Location")
            or extract_field(rec, ["locationother", "location"])
            or "Black Lacquer Kitchen"
        ).strip()

        sign = rec.get("submission.Sign") or rec.get("Sign") or extract_field(rec, ["signinitial", "sign", "initial"]) or "Staff"

        # 2. Extract the CL object
        cl_data = rec.get("submission.CL") or rec.get("CL") or {}
        if not isinstance(cl_data, dict):
            # If flattened by pandas normalizer:
            cl_data = {
                "Type": rec.get("submission.CL.Type") or rec.get("CL.Type") or rec.get("Type"),
                "Type_of_food_Other": rec.get("submission.CL.Type_of_food_Other") or rec.get("CL.Type_of_food_Other") or rec.get("Type of food (Other)"),
                "Chemical_ppm_strength": rec.get("submission.CL.Chemical_ppm_strength") or rec.get("CL.Chemical_ppm_strength") or rec.get("Chemical ppm strength"),
                "Contact_Time_in_Minutes": rec.get("submission.CL.Contact_Time_in_Minutes") or rec.get("CL.Contact_Time_in_Minutes") or rec.get("Contact Time in Minutes"),
            }

        # 3. Resolve Food Name
        raw_type = cl_data.get("Type") or extract_field(rec, ["typeoffood", "foodtype", "type"])
        if isinstance(raw_type, list) and len(raw_type) > 0:
            type_str = str(raw_type[0]).strip()
        else:
            type_str = str(raw_type or "").replace("•", "").replace("[", "").replace("]", "").replace("'", "").strip()

        food_other = (
            cl_data.get("Type_of_food_Other")
            or cl_data.get("Type of food (Other)")
            or rec.get("Type of food (Other)")
            or extract_field(rec, ["typeoffoodother", "foodother", "otherfood"])
            or ""
        )
        food_other_clean = str(food_other).replace("•", "").strip()

        if food_other_clean and food_other_clean.lower() not in ["none", "nan", ""]:
            final_food = food_other_clean
        elif type_str and type_str.lower() not in ["other", "none", "nan", ""]:
            final_food = type_str
        else:
            final_food = "Veg Item"

        # 4. Chemical PPM Strength
        ppm_raw = cl_data.get("Chemical_ppm_strength") or extract_field(rec, ["chemicalppmstrength", "ppmstrength", "ppm"])
        ppm_num = pd.to_numeric(str(ppm_raw).replace("ppm", "").strip(), errors="coerce")

        # 5. Contact Time
        time_raw = str(cl_data.get("Contact_Time_in_Minutes") or extract_field(rec, ["contacttimeinminutes", "contacttime", "minutes"]) or "5")
        time_clean = time_raw.lower().replace("minutes", "").replace("minute", "").replace("mins", "").replace("min", "").strip()
        minutes_num = pd.to_numeric(time_clean, errors="coerce")

        # 6. Excursion checks
        ppm_breach = pd.notna(ppm_num) and (ppm_num != TARGET_PPM)
        time_breach = pd.notna(minutes_num) and (minutes_num < TARGET_MINUTES)
        has_breach = ppm_breach or time_breach

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Time": time_str,
            "Location": location,
            "Food": final_food,
            "PPM": ppm_num,
            "PPM_Raw": str(ppm_raw) if ppm_raw else "100",
            "Minutes": minutes_num,
            "Minutes_Raw": f"{time_raw} Min",
            "PPM_Breach": ppm_breach,
            "Time_Breach": time_breach,
            "Has_Breach": has_breach,
            "Sign": sign
        })

    return pd.DataFrame(rows)


def render_record_21_view(raw_df, selected_day_str, start_date, end_date):
    """Renders Record 21 single-day drilldown and 7-day paginated kitchen matrix."""
    df_items = parse_record_21_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date) & 
            (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Veg Sanitization ({selected_day_str})",
        "📈 7-Day Matrix (1-Month Browser)"
    ])

    # -------------------------------------------------------------
    # TAB 1: DAILY DRILLDOWN
    # -------------------------------------------------------------
    with tab_day:
        day_df = range_df[range_df["Date_Str"] == selected_day_str] if not range_df.empty else pd.DataFrame()

        excursions = []
        compliant_logs = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if r["Has_Breach"]:
                    excursions.append(r.to_dict())
                else:
                    compliant_logs.append(r.to_dict())

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">PPM / Time Excursions</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_logs)}</div><div class="kpi-lbl">Verified 100 PPM (5 Min)</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Batches Washed</div></div>', unsafe_allow_html=True)

        st.write("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Chemical / Time Breaches ({len(excursions)})</div>', unsafe_allow_html=True)
            if excursions:
                for exc in excursions:
                    errs = []
                    if exc["PPM_Breach"]:
                        errs.append(f"PPM: {exc['PPM']} (Target 100)")
                    if exc["Time_Breach"]:
                        errs.append(f"Time: {exc['Minutes']}m (< 5 Min)")
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{exc['Food']} • {exc['Location']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            {' | '.join(errs)}
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Time: {exc['Time']} | Initial: {exc['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No PPM or contact time breaches on this date.")
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Verified Sanitized ({len(compliant_logs)})</div>', unsafe_allow_html=True)
            if compliant_logs:
                for ok in compliant_logs:
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Food']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Strength: <b style="color:#16a34a;">100 PPM</b> &nbsp;|&nbsp; Contact: <b>5 Minutes</b>
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Kitchen: {ok['Location']} | Sign: {ok['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No food wash entries recorded for this day.")
            st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: 7-DAY SPLIT-CELL AUDIT GRID
    # -------------------------------------------------------------
    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec21_page" not in st.session_state:
            st.session_state.rec21_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("⬅️ Previous 7 Days", key="r21_prev", disabled=(st.session_state.rec21_page <= 0), use_container_width=True):
                st.session_state.rec21_page -= 1
                st.rerun()

        with nav3:
            if st.button("Next 7 Days ➡️", key="r21_next", disabled=(st.session_state.rec21_page >= max_page), use_container_width=True):
                st.session_state.rec21_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec21_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with nav2:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec21_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.write("")

        # 8 Columns: 1 Location Header + 7 Dates
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

        # Strict Dynamic Kitchen List (no Commissary or other hardcoded strings)
        if not range_df.empty and "Location" in range_df.columns:
            active_kitchens = [k for k in sorted(list(range_df["Location"].dropna().unique())) if k.strip() != ""]
        else:
            active_kitchens = ["Black Lacquer Kitchen"]

        for kitchen in active_kitchens:
            row_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])

            row_cols[0].markdown(f"""
            <div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:12px 6px; font-weight:700; color:#0f172a; font-size:0.88rem; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:115px; display:flex; align-items:center; justify-content:center;">
                {kitchen}
            </div>
            """, unsafe_allow_html=True)

            k_df = range_df[range_df["Location"].str.lower() == kitchen.lower()] if not range_df.empty else pd.DataFrame()

            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                matches = k_df[k_df["Date_Str"] == d_str] if not k_df.empty else pd.DataFrame()

                if matches.empty:
                    row_cols[i+1].markdown("""
                    <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:115px; display:flex; align-items:center; justify-content:center;">
                        <span style="color:#94a3b8; font-weight:600; font-size:0.82rem;">— Not Filled</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    batch_count = len(matches)
                    has_day_breach = any(matches["Has_Breach"])

                    foods_list = list(dict.fromkeys(matches["Food"].dropna().tolist()))
                    foods_formatted = ", ".join(foods_list)

                    if has_day_breach:
                        badge = '<span style="color:#dc2626; font-weight:800; font-size:0.88rem;">🔴 BREACH</span>'
                        border_style = "2px solid #dc2626"
                    else:
                        badge = f'<span style="color:#16a34a; font-weight:800; font-size:1.15rem;">{batch_count}</span>'
                        border_style = "1.5px solid #0f172a"

                    row_cols[i+1].markdown(f"""
                    <div style="background:#ffffff; border:{border_style}; border-radius:8px; padding:8px 4px; text-align:center; min-height:115px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div>{badge}</div>
                        <div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>
                        <div style="font-size:0.75rem; font-weight:600; color:#0f172a; line-height:1.25; word-wrap:break-word;">
                            {foods_formatted}
                        </div>
                        <div style="font-size:0.65rem; color:#64748b; margin-top:4px;">100 PPM • 5m</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

        st.divider()

        with st.expander("📋 View All Individual Chlorine Food Wash Records"):
            if not range_df.empty:
                show_cols = [c for c in [
                    "Date_Str", "Time", "Location", "Food", "PPM_Raw", "Minutes_Raw", "Sign"
                ] if c in range_df.columns]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
