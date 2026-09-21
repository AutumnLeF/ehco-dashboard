from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

TARGET_PPM = 100.0      # Chlorine PPM must be 100
TARGET_MINUTES = 5.0    # Contact time must be 5 minutes
RECORD_21_FORM_ID = 31379  # Standard form ID for chlorine wash


def parse_record_21_submissions(raw_df):
    """Robustly parses Record 21 food wash submissions from OneBlink nested payloads."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.get("raw_record") if "raw_record" in raw_df.columns else record.to_dict()
        if not isinstance(rec, dict):
            rec = record.to_dict()

        sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
        entry_parent = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else sub

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

        time_str = str(sub.get("Time") or entry_parent.get("Time") or "")[:8]
        location = str(sub.get("Location") or rec.get("Location") or "Black Lacquer Kitchen").strip()
        sign = str(sub.get("Sign") or sub.get("sign") or rec.get("Sign") or rec.get("user.email") or "Staff").strip()

        cl_obj = sub.get("CL") or rec.get("CL") or sub.get("set") or rec.get("set") or {}
        cl_items = [cl_obj] if isinstance(cl_obj, dict) else (cl_obj if isinstance(cl_obj, list) else [{}])

        for cl in cl_items:
            if not isinstance(cl, dict):
                continue

            raw_type = cl.get("Type") or cl.get("Food") or cl.get("Type_of_food") or "Salad Item"
            if isinstance(raw_type, list) and len(raw_type) > 0:
                type_val = str(raw_type[0]).strip()
            else:
                type_val = str(raw_type).replace("['", "").replace("']", "").replace("•", "").strip()

            other_val = str(cl.get("Type_of_food_Other") or cl.get("Type of food (Other)") or "").replace("•", "").strip()

            if other_val and other_val.lower() not in ["none", "nan", ""]:
                food_name = other_val
            elif type_val and type_val.lower() not in ["other", "none", "nan", "cognito", ""]:
                food_name = type_val
            else:
                food_name = "Salad Item"

            ppm_raw = cl.get("Chemical_ppm_strength") or cl.get("Chemical ppm strength") or cl.get("PPM") or "100"
            ppm_num = pd.to_numeric(str(ppm_raw).replace("ppm", "").strip(), errors="coerce")

            time_raw = str(cl.get("Contact_Time_in_Minutes") or cl.get("Contact Time in Minutes") or cl.get("Minutes") or "5")
            time_clean = time_raw.lower().replace("minutes", "").replace("minute", "").replace("mins", "").replace("min", "").strip()
            minutes_num = pd.to_numeric(time_clean, errors="coerce")

            ppm_breach = pd.notna(ppm_num) and (ppm_num != TARGET_PPM)
            time_breach = pd.notna(minutes_num) and (minutes_num < TARGET_MINUTES)

            rows.append({
                "Date_Str": date_str,
                "Date_Obj": date_obj,
                "Time": time_str,
                "Location": location,
                "Food": food_name,
                "PPM": ppm_num,
                "PPM_Raw": str(ppm_raw),
                "Minutes": minutes_num,
                "Minutes_Raw": f"{time_raw}m",
                "PPM_Breach": ppm_breach,
                "Time_Breach": time_breach,
                "Has_Breach": (ppm_breach or time_breach),
                "Sign": sign,
            })

    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Food", "PPM", "Minutes"], keep="first")
    return df_out


def render_record_21_view(raw_df, selected_day_str, start_date, end_date):
    df_items = parse_record_21_submissions(raw_df)

    with st.expander("🔍 Record 21 Diagnostic (Inspect loaded data)"):
        st.write(f"Total parsed food wash records: **{len(df_items)}**")
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
        f"Today - {selected_day_str}",
        "Weekly"
    ])

    with tab_day:
        day_df = (
            range_df[range_df["Date_Str"] == selected_day_str]
            if not range_df.empty
            else pd.DataFrame()
        )

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
        st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>🥗 Chlorine Food Wash Audit Cards ({selected_day_str})</h4>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div style="font-weight:700; color:#dc2626; margin-bottom:8px;">🔴 Chemical / Time Breaches</div>', unsafe_allow_html=True)
            if excursions:
                for exc in excursions:
                    errs = []
                    if exc["PPM_Breach"]:
                        errs.append(f"PPM: {exc['PPM']} (Target 100)")
                    if exc["Time_Breach"]:
                        errs.append(f"Time: {exc['Minutes']}m (< 5 Min)")
                    st.markdown(f'<div style="background:#ffffff; border:1px solid #fca5a5; border-left:4px solid #dc2626; padding:12px; border-radius:6px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.05);"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🥗 {exc["Food"]} • {exc["Location"]}</div><div style="font-size:0.85rem; color:#dc2626; font-weight:700; margin-top:4px;">{" | ".join(errs)}</div><div style="font-size:0.75rem; color:#64748b; margin-top:4px;">Time: {exc["Time"]} | Initial: {exc["Sign"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem; text-align:center;">No PPM or contact time breaches on this date.</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div style="font-weight:700; color:#16a34a; margin-bottom:8px;">🟢 Verified Sanitized</div>', unsafe_allow_html=True)
            if compliant_logs:
                for ok in compliant_logs:
                    st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:4px solid #16a34a; padding:12px; border-radius:6px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.05);"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🥗 {ok["Food"]}</div><div style="font-size:0.85rem; color:#334155; margin-top:4px;">Strength: <b style="color:#16a34a;">100 PPM</b> | Contact: <b>5 Minutes</b></div><div style="font-size:0.75rem; color:#64748b; margin-top:4px;">Kitchen: {ok["Location"]} | Sign: {ok["Sign"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem; text-align:center;">No food wash entries recorded for this day.</div>', unsafe_allow_html=True)

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
                    unsafe_allow_html=True,
                )

        st.write("")

        cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
        cols[0].markdown('<div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.85rem; padding:10px 4px; border-radius:6px; text-align:center;">Kitchen Area</div>', unsafe_allow_html=True)
        for i, d in enumerate(page_dates):
            cols[i + 1].markdown(f'<div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.8rem; padding:10px 2px; border-radius:6px; text-align:center;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

        st.write("")

        if not range_df.empty and "Location" in range_df.columns:
            active_kitchens = [
                loc for loc in range_df["Location"].dropna().unique()
                if str(loc).strip() != "" and len(range_df[range_df["Location"] == loc]) > 0
            ]
        else:
            active_kitchens = ["Black Lacquer Kitchen"]

        if not active_kitchens:
            active_kitchens = ["Black Lacquer Kitchen"]

        for kitchen in active_kitchens:
            row_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
            row_cols[0].markdown(f'<div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:12px 6px; font-weight:700; color:#0f172a; font-size:0.88rem; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:120px; display:flex; align-items:center; justify-content:center;">{kitchen}</div>', unsafe_allow_html=True)

            k_df = range_df[range_df["Location"].str.lower() == str(kitchen).lower()] if not range_df.empty else pd.DataFrame()

            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                matches = k_df[k_df["Date_Str"] == d_str] if not k_df.empty else pd.DataFrame()

                if matches.empty:
                    row_cols[i + 1].markdown('<div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:120px; display:flex; align-items:center; justify-content:center;"><span style="color:#94a3b8; font-weight:600; font-size:0.82rem;">— Not Filled</span></div>', unsafe_allow_html=True)
                else:
                    batch_count = len(matches)
                    has_day_breach = any(matches["Has_Breach"])

                    foods_list = list(dict.fromkeys(matches["Food"].dropna().tolist()))
                    foods_formatted = ", ".join(foods_list)

                    sign_list = [s for s in dict.fromkeys(matches["Sign"].dropna().tolist()) if s and s != "Staff"]
                    sign_display = f"By: {', '.join(sign_list)}" if sign_list else "By: Staff"

                    if has_day_breach:
                        badge = '<span style="color:#dc2626; font-weight:800; font-size:0.88rem;">🔴 BREACH</span>'
                        border_style = "2px solid #dc2626"
                    else:
                        badge = f'<span style="color:#16a34a; font-weight:800; font-size:1.15rem;">{batch_count}</span>'
                        border_style = "1.5px solid #0f172a"

                    row_cols[i + 1].markdown(f'<div style="background:#ffffff; border:{border_style}; border-radius:8px; padding:8px 4px; text-align:center; min-height:120px; box-shadow:0 1px 3px rgba(0,0,0,0.08);"><div>{badge}</div><div style="height:1px; background:#cbd5e1; margin:5px 0;"></div><div style="font-size:0.75rem; font-weight:600; color:#0f172a; line-height:1.25; word-wrap:break-word;">{foods_formatted}</div><div style="font-size:0.65rem; color:#475569; margin-top:3px;">100 PPM • 5m</div><div style="font-size:0.67rem; color:#64748b; font-weight:600; margin-top:3px;">{sign_display}</div></div>', unsafe_allow_html=True)

            st.write("")

        st.divider()

        with st.expander("📋 View All Individual Chlorine Food Wash Records"):
            if not range_df.empty:
                show_cols = [
                    c for c in [
                        "Date_Str", "Time", "Location", "Food", "PPM_Raw", "Minutes_Raw", "Sign"
                    ] if c in range_df.columns
                ]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
