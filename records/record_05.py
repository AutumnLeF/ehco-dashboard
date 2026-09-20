from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

RECORD_05_FORM_ID = 31375
CRITICAL_LIMIT_2HR = 5.0  # Blast chiller target: <= 5.0°C after 2 hours

RECORD_05_KITCHENS = ["Filia Kitchen"]


def find_val(row_dict, keywords):
    """Finds the first matching non-null value for loose key names."""
    for k, v in row_dict.items():
        k_clean = k.lower().replace("_", "").replace(" ", "").replace(".", "")
        for kw in keywords:
            kw_clean = kw.lower().replace("_", "").replace(" ", "")
            if kw_clean in k_clean:
                if pd.notna(v) and str(v).strip() != "":
                    return v
    return None


def parse_record_05_submissions(raw_df):
    """Parses Record 05 blast chiller submissions with clean date objects."""
    if raw_df.empty:
        return pd.DataFrame()

    df = raw_df.copy()

    form_col = next((c for c in df.columns if "formid" in c.lower()), None)
    if form_col:
        df = df[df[form_col].astype(str) == str(RECORD_05_FORM_ID)]

    rows = []
    for _, record in df.iterrows():
        rec = record.to_dict()

        # Date normalization
        raw_date = find_val(rec, ["startdate", "date", "createdat"]) or ""
        parsed_dt = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_dt):
            parsed_dt = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")

        if pd.notna(parsed_dt):
            norm_date = parsed_dt.strftime("%d/%m/%Y")
            date_obj = parsed_dt.date()
        else:
            norm_date = str(raw_date)[:10]
            date_obj = None

        time_str = str(find_val(rec, ["starttime", "time"]) or "")[:19]
        location = find_val(rec, ["location"]) or "Filia Kitchen"
        method = find_val(rec, ["method"]) or "Blast Chiller"
        food = find_val(rec, ["nameoffood", "fooditem", "food"]) or "Batch Item"

        # Temperatures
        start_raw = find_val(rec, ["starttemperature", "starttemp", "tempstart"])
        start_temp = pd.to_numeric(
            str(start_raw).replace("°C", "").strip(), errors="coerce"
        )

        end_raw = find_val(
            rec,
            [
                "temperatureafter2hours",
                "after2hours",
                "2hours",
                "tempafter2",
                "endtemp",
            ],
        )
        end_temp = pd.to_numeric(
            str(end_raw).replace("°C", "").strip(), errors="coerce"
        )

        sign = find_val(rec, ["sign", "initial", "user.email"]) or "Staff"

        rows.append(
            {
                "Date_Str": norm_date,
                "Date_Obj": date_obj,
                "Time": time_str,
                "Location": location,
                "Method": method,
                "Food": food,
                "Start_Temp": start_temp,
                "End_Temp": end_temp,
                "Sign": sign,
            }
        )

    return pd.DataFrame(rows)


def render_record_05_view(raw_df, selected_day_str, start_date, end_date):
    """Renders single-day drilldown and a 7-day chronological area compliance matrix."""
    df_items = parse_record_05_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date) & 
            (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([f"📅 Daily Pull-Down ({selected_day_str})", "📈 7-Day Matrix (1-Month Browser)"])

    # -------------------------------------------------------------
    # TAB 1: DAILY DRILLDOWN
    # -------------------------------------------------------------
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

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Core Temp Breaches ({len(excursions)})</div>', unsafe_allow_html=True)
            if excursions:
                for exc in excursions:
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{exc['Food']} • {exc['Location']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            Start: {exc['Start_Temp']}°C &nbsp;➔&nbsp; After 2h: {exc['End_Temp']}°C (Limit ≤ 5.0°C)
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:3px;">Time: {exc['Time']} | Sign: {exc['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No cooling excursions on this day.")
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Verified Pulled-Down ({len(compliant_logs)})</div>', unsafe_allow_html=True)
            if compliant_logs:
                for ok in compliant_logs:
                    temp_txt = f"{ok['End_Temp']}°C" if pd.notna(ok['End_Temp']) else "Done"
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Food']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Start: <b>{ok['Start_Temp']}°C</b> &nbsp;➔&nbsp; After 2h: <b style="color:#16a34a;">{temp_txt}</b>
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:3px;">Method: {ok['Method']} | Sign: {ok['Sign']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("No blast chiller records for this day.")
            st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: 7-DAY SPLIT-CELL AUDIT TABLE
    # -------------------------------------------------------------
    with tab_matrix:
        st.subheader("7-Day Kitchen Completion Matrix")

        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec05_page" not in st.session_state:
            st.session_state.rec05_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        # Navigation Bar
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
        page_dates = all_dates[p_start_idx:p_start_idx + 7]

        with col_status:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:600; color:#0f172a; padding-top:6px;'>"
                    f"Showing: {page_dates[0].strftime('%d/%m/%Y')} to {page_dates[-1].strftime('%d/%m/%Y')} (Block {st.session_state.rec05_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True
                )

        # Render custom bordered HTML table matching the 2-tier design
        all_kitchens = sorted(list(range_df["Location"].unique())) if not range_df.empty and "Location" in range_df.columns else RECORD_05_KITCHENS

        table_html = ['<table class="audit-table">']
        
        # Header Row
        table_html.append('<thead><tr>')
        table_html.append('<th style="width: 14%; text-align: left;">Kitchen Area</th>')
        for d in page_dates:
            table_html.append(f'<th>{d.strftime("%d/%m (%a)")}</th>')
        table_html.append('</tr></thead><tbody>')

        # Data Rows
        for kitchen in all_kitchens:
            table_html.append('<tr>')
            table_html.append(f'<td style="font-weight: 700; background: #f8fafc;">{kitchen}</td>')
            k_df = range_df[range_df["Location"] == kitchen] if not range_df.empty else pd.DataFrame()

            for d in page_dates:
                d_str = d.strftime("%d/%m/%Y")
                matches = k_df[k_df["Date_Str"] == d_str] if not k_df.empty else pd.DataFrame()

                if matches.empty:
                    table_html.append('<td><div class="cell-empty">—</div></td>')
                else:
                    count = len(matches)
                    foods_list = matches["Food"].dropna().tolist()
                    foods_formatted = ", ".join(foods_list)
                    
                    # Exact 2-tier card: Top = count, Bottom = food names
                    table_html.append(f'''
                    <td>
                        <div class="cell-count">{count}</div>
                        <div class="cell-foods">{foods_formatted}</div>
                    </td>
                    ''')
            table_html.append('</tr>')

        table_html.append('</tbody></table>')
        st.markdown(''.join(table_html), unsafe_allow_html=True)
        st.write("")
