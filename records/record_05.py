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


# -------------------------------------------------------------
    # TAB 2: 7-DAY SPLIT-CELL AUDIT GRID
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
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: {page_dates[0].strftime('%d/%m/%Y')} to {page_dates[-1].strftime('%d/%m/%Y')} (Page {st.session_state.rec05_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.write("")

        # 8 Columns: 1 for Kitchen Area title + 7 for Dates
        cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])

        # Header row
        cols[0].markdown("""
        <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.85rem; padding:10px; border-radius:6px; text-align:center;">
            Kitchen Area
        </div>
        """, unsafe_allow_html=True)

        for i, d in enumerate(page_dates):
            cols[i+1].markdown(f"""
            <div style="background:#1e293b; color:#ffffff; font-weight:700; font-size:0.8rem; padding:10px 4px; border-radius:6px; text-align:center;">
                {d.strftime('%d/%m (%a)')}
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # Data rows per kitchen
        all_kitchens = sorted(list(range_df["Location"].unique())) if not range_df.empty and "Location" in range_df.columns else RECORD_05_KITCHENS

        for kitchen in all_kitchens:
            row_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1, 1])

            # Column 1: Kitchen Name
            row_cols[0].markdown(f"""
            <div style="background:#ffffff; border:1px solid #94a3b8; border-radius:8px; padding:14px 10px; font-weight:700; color:#0f172a; font-size:0.9rem; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,0.05); min-height:105px; display:flex; align-items:center; justify-content:center;">
                {kitchen}
            </div>
            """, unsafe_allow_html=True)

            k_df = range_df[range_df["Location"] == kitchen] if not range_df.empty else pd.DataFrame()

            # Columns 2 to 8: Days
            for i, d in enumerate(page_dates):
                d_str = d.strftime("%d/%m/%Y")
                matches = k_df[k_df["Date_Str"] == d_str] if not k_df.empty else pd.DataFrame()

                if matches.empty:
                    row_cols[i+1].markdown("""
                    <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:10px; text-align:center; min-height:105px; display:flex; align-items:center; justify-content:center;">
                        <span style="color:#94a3b8; font-weight:600; font-size:1.1rem;">—</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    count = len(matches)
                    foods_list = matches["Food"].dropna().tolist()
                    foods_text = ", ".join(foods_list)

                    # High-contrast 2-tier card: Top number, divider, bottom foods
                    row_cols[i+1].markdown(f"""
                    <div style="background:#ffffff; border:1.5px solid #0f172a; border-radius:8px; padding:8px 6px; text-align:center; min-height:105px; box-shadow:0 2px 4px rgba(0,0,0,0.06);">
                        <div style="font-size:1.25rem; font-weight:800; color:#0f172a; line-height:1.1;">{count}</div>
                        <div style="height:1px; background:#e2e8f0; margin:6px 0;"></div>
                        <div style="font-size:0.75rem; font-weight:600; color:#1e293b; line-height:1.25; word-wrap:break-word;">
                            {foods_text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

        st.divider()

        # Detailed expandable raw list
        with st.expander("📋 View All Individual Chilling Records (Selected Window)"):
            if not range_df.empty:
                show_cols = [
                    c for c in [
                        "Date_Str", "Time", "Location", "Food", "Start_Temp", "End_Temp", "Sign"
                    ] if c in range_df.columns
                ]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
