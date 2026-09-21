from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

RECORD_05_FORM_ID = 31375
CRITICAL_LIMIT_2HR = 5.0  # Limit: <= 5.0°C after 2 hours
RECORD_05_KITCHENS = ["Filia Kitchen"]


def parse_record_05_submissions(raw_df):
    """Robustly parses Record 05 blast chiller submissions from OneBlink nested payloads."""
    if raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in raw_df.iterrows():
        rec = row.get("raw_record") if "raw_record" in raw_df.columns else row.to_dict()
        if not isinstance(rec, dict):
            rec = row.to_dict()

        sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else rec
        entry_parent = sub.get("Entry") if isinstance(sub.get("Entry"), dict) else sub

        location = (
            sub.get("Location")
            or rec.get("Location")
            or entry_parent.get("Location")
            or "Filia Kitchen"
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
            or sub.get("StartDate")
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
            norm_date = parsed_dt_ist.strftime("%d/%m/%Y")
            date_obj = parsed_dt_ist.date()
        else:
            norm_date = str(raw_date)[:10]
            date_obj = None

        raw_time = (
            sub.get("Time")
            or sub.get("StartTime")
            or entry_parent.get("Time")
            or ""
        )
        time_str = str(raw_time).strip()
        if "T" in time_str:
            try:
                time_str = time_str.split("T")[1][:5]
            except Exception:
                pass

        entries = (
            sub.get("set")
            or sub.get("Entry")
            or rec.get("set")
            or rec.get("Entry")
            or []
        )

        if isinstance(entries, dict):
            entries = [entries]

        if not entries and isinstance(sub, dict):
            entries = [sub]

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            method = entry.get("Method") or sub.get("Method") or "Blast Chiller"
            food = (
                entry.get("Name_of_Food")
                or entry.get("Food")
                or entry.get("Food_Item")
                or entry.get("Dish")
                or "Batch Item"
            )

            start_raw = (
                entry.get("Start_Temperature")
                or entry.get("StartTemp")
                or entry.get("Temp_Start")
                or entry.get("Temperature_Start")
            )
            start_temp = pd.to_numeric(
                str(start_raw).replace("°C", "").replace("°", "").strip(),
                errors="coerce",
            )

            end_raw = (
                entry.get("Temperature_After_2_Hours")
                or entry.get("After_2_Hours")
                or entry.get("Temp_After_2")
                or entry.get("End_Temp")
                or entry.get("Temperature")
            )
            end_temp = pd.to_numeric(
                str(end_raw).replace("°C", "").replace("°", "").strip(),
                errors="coerce",
            )

            rows.append({
                "Date_Str": norm_date,
                "Date_Obj": date_obj,
                "Time": time_str,
                "Location": str(location).strip(),
                "Method": str(method).strip(),
                "Food": str(food).strip(),
                "Start_Temp": start_temp,
                "End_Temp": end_temp,
                "Sign": str(sign).strip(),
            })

    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out = df_out.drop_duplicates(subset=["Date_Str", "Time", "Location", "Food", "Start_Temp", "End_Temp"], keep="first")
    return df_out


def render_record_05_view(raw_df, selected_day_str, start_date, end_date):
    df_items = parse_record_05_submissions(raw_df)

    with st.expander("🔍 Record 05 Diagnostic (Inspect loaded data)"):
        st.write(f"Total parsed cooling records: **{len(df_items)}**")
        if not df_items.empty and "Date_Obj" in df_items.columns:
            date_counts = df_items["Date_Obj"].dropna().value_counts().sort_index(ascending=False).to_dict()
            st.write("Records per date found:", {str(k): v for k, v in date_counts.items()})

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[(df_items["Date_Obj"] >= start_date) & (df_items["Date_Obj"] <= end_date)]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Pull-Down ({selected_day_str})",
        "📈 7-Day Matrix (1-Month Browser)",
    ])

    with tab_day:
        day_df = range_df[range_df["Date_Str"] == selected_day_str] if not range_df.empty else pd.DataFrame()

        excursions = []
        compliant_logs = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if pd.notna(r["End_Temp"]) and r["End_Temp"] > CRITICAL_LIMIT_2HR:
                    excursions.append(r.to_dict())
                else:
                    compliant_logs.append(r.to_dict())

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">Excursions (&gt; 5.0°C)</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_logs)}</div><div class="kpi-lbl">Verified Pulled-Down (≤ 5.0°C)</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Batches Chilled</div></div>', unsafe_allow_html=True)

        st.write("")
        st.markdown(f"<h4 style='color:#0f172a; margin-top:1rem;'>❄️ Blast Chiller Audit Cards ({selected_day_str})</h4>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div style="font-weight:700; color:#dc2626; margin-bottom:8px;">🔴 Temperature Breaches (> 5.0°C)</div>', unsafe_allow_html=True)
            if excursions:
                for exc in excursions:
                    st.markdown(f'<div style="background:#ffffff; border:1px solid #fca5a5; border-left:4px solid #dc2626; padding:12px; border-radius:6px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.05);"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🍲 {exc["Food"]} • {exc["Location"]}</div><div style="font-size:0.85rem; color:#dc2626; font-weight:700; margin-top:4px;">Start: {exc["Start_Temp"]}°C ➔ After 2h: {exc["End_Temp"]}°C (Limit ≤ 5.0°C)</div><div style="font-size:0.75rem; color:#64748b; margin-top:4px;">Time: {exc["Time"]} | Signed: {exc["Sign"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem; text-align:center;">No cooling excursions on this day.</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div style="font-weight:700; color:#16a34a; margin-bottom:8px;">🟢 Verified Compliant (≤ 5.0°C)</div>', unsafe_allow_html=True)
            if compliant_logs:
                for ok in compliant_logs:
                    temp_txt = f"{ok['End_Temp']}°C" if pd.notna(ok["End_Temp"]) else "Done"
                    st.markdown(f'<div style="background:#ffffff; border:1px solid #cbd5e1; border-left:4px solid #16a34a; padding:12px; border-radius:6px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.05);"><div style="font-weight:700; font-size:0.95rem; color:#0f172a;">🍲 {ok["Food"]}</div><div style="font-size:0.85rem; color:#334155; margin-top:4px;">Start: <b>{ok["Start_Temp"]}°C</b> ➔ After 2h: <b style="color:#16a34a;">{temp_txt}</b></div><div style="font-size:0.75rem; color:#64748b; margin-top:4px;">Method: {ok["Method"]} | Signed: {ok["Sign"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:14px; color:#64748b; font-size:0.85rem; text-align:center;">No blast chiller records for this day.</div>', unsafe_allow_html=True)

    with tab_matrix:
        st.subheader("7-Day Kitchen Completion Matrix")

        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec05_page" not in st.session_state:
            st.session_state.rec05_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        col_prev, col_status, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("⬅️ Previous 7 Days", disabled=(st.session_state.rec05_page <= 0), use_container_width=True):
                st.session_state.rec05_page -= 1
                st.rerun()

        with col_next:
            if st.button("Next 7 Days ➡️", disabled=(st.session_state.rec05_page >= max_page), use_container_width=True):
                st.session_state.rec05_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec05_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with col_status:
            if page_dates:
                st.markdown(f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>Showing: {page_dates[0].strftime('%d/%m/%Y')} to {page_dates[-1].strftime('%d/%m/%Y')} (Block {st.session_state.rec05_page + 1} of {max_page + 1})</div>", unsafe_allow_html=True)

        st.write("")

        cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
        cols[0].markdown('<div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.85rem; padding:10px 4px; border-radius:6px; text-align:center;">Kitchen Area</div>', unsafe_allow_html=True)
        for i, d in enumerate(page_dates):
            cols[i + 1].markdown(f'<div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.8rem; padding:10px 2px; border-radius:6px; text-align:center;">{d.strftime("%d/%m (%a)")}</div>', unsafe_allow_html=True)

        st.write("")

        all_kitchens = sorted(list(range_df["Location"].unique())) if not range_df.empty and "Location" in range_df.columns else RECORD_05_KITCHENS

        for kitchen in all_kitchens:
            row_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])
            row_cols[0].markdown(f'<div style="background:#ffffff; border:1.5px solid #94a3b8; border-radius:8px; padding:12px 6px; font-weight:700; color:#0f172a; font-size:0.88rem; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:115px; display:flex; align-items:center; justify-content:center;">{kitchen}</div>', unsafe_allow_html=True)

            k_df = range_df[range_df["Location"] == kitchen] if not range_df.empty else pd.DataFrame()

            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                matches = k_df[k_df["Date_Str"] == d_str] if not k_df.empty else pd.DataFrame()

                if matches.empty:
                    row_cols[i + 1].markdown('<div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:8px; text-align:center; min-height:115px; display:flex; align-items:center; justify-content:center;"><span style="color:#94a3b8; font-weight:700; font-size:1.2rem;">—</span></div>', unsafe_allow_html=True)
                else:
                    count = len(matches)
                    foods_list = matches["Food"].dropna().tolist()
                    foods_text = ", ".join(foods_list)
                    row_cols[i + 1].markdown(f'<div style="background:#ffffff; border:1.5px solid #0f172a; border-radius:8px; padding:8px 4px; text-align:center; min-height:115px; box-shadow:0 1px 3px rgba(0,0,0,0.08);"><div style="font-size:1.3rem; font-weight:800; color:#0f172a; line-height:1;">{count}</div><div style="height:1px; background:#cbd5e1; margin:6px 0;"></div><div style="font-size:0.75rem; font-weight:600; color:#0f172a; line-height:1.3; word-wrap:break-word;">{foods_text}</div></div>', unsafe_allow_html=True)

            st.write("")

        st.divider()
        with st.expander("📋 View All Individual Chilling Records (Selected Window)"):
            if not range_df.empty:
                show_cols = [c for c in ["Date_Str", "Time", "Location", "Food", "Start_Temp", "End_Temp", "Sign"] if c in range_df.columns]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
