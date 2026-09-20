from datetime import datetime
import pandas as pd
import streamlit as st

RECORD_05_FORM_ID = 31375
CRITICAL_LIMIT_2HR = 5.0  # Blast chiller target: <= 5.0°C after 2 hours


def parse_record_05_submissions(raw_df):
    """Parses Record 05 (Blast Chiller / Food Cooling) submissions into a clean DataFrame."""
    if raw_df.empty:
        return pd.DataFrame()

    df = raw_df.copy()

    # Match formId loosely
    form_col = next(
        (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
        None,
    )
    if form_col:
        df = df[df[form_col].astype(str) == str(RECORD_05_FORM_ID)]

    rows = []
    for _, record in df.iterrows():
        # Date parsing
        raw_date = (
            record.get("submission.Start_Date")
            or record.get("Start Date")
            or record.get("submission.Date")
            or record.get("Date")
            or record.get("createdAt")
            or ""
        )

        parsed_dt = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_dt):
            parsed_dt = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")

        if pd.notna(parsed_dt):
            norm_date = parsed_dt.strftime("%d/%m/%Y")
            date_obj = parsed_dt.date()
        else:
            norm_date = str(raw_date)[:10]
            date_obj = None

        time_str = (
            record.get("submission.Start_Time")
            or record.get("Start Time")
            or record.get("submission.Time")
            or ""
        )
        location = (
            record.get("submission.Location")
            or record.get("Location")
            or "Filia Kitchen"
        )
        method = (
            record.get("submission.Method")
            or record.get("Method")
            or "Blast Chiller"
        )
        food = (
            record.get("submission.Name_of_Food")
            or record.get("Name of Food")
            or record.get("Food")
            or "Item"
        )

        # Temperature parsing
        start_temp_raw = (
            record.get("submission.Start_Temperature")
            or record.get("Start Temperature °C")
            or record.get("submission.Start_Temperature_C")
        )
        start_temp = pd.to_numeric(
            str(start_temp_raw).replace("°C", "").strip(), errors="coerce"
        )

        end_temp_raw = (
            record.get("submission.Temperature_after_2_Hours")
            or record.get("Temperature after 2 Hours (°C) - Blast Chiller")
            or record.get("submission.Temp_After_2_Hours")
        )
        end_temp = pd.to_numeric(
            str(end_temp_raw).replace("°C", "").strip(), errors="coerce"
        )

        sign = (
            record.get("submission.Sign")
            or record.get("Sign (Initial)")
            or record.get("Sign")
            or "Staff"
        )

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
    """Renders both 30-day timeline matrix and daily drilldown for Record 05."""
    df_items = parse_record_05_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns:
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_range = st.tabs(
        [f"📅 Daily Pull-Down ({selected_day_str})", "📈 30-Day Completion Matrix"]
    )

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
                if pd.notna(r["End_Temp"]) and r["End_Temp"] > CRITICAL_LIMIT_2HR:
                    excursions.append(r.to_dict())
                else:
                    compliant_logs.append(r.to_dict())

        # KPIs
        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#b91c1c;">{len(excursions)}</div><div class="kpi-lbl">Cooling Excursions (&gt; 5.0°C)</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#15803d;">{len(compliant_logs)}</div><div class="kpi-lbl">Verified Pulled-Down (≤ 5.0°C)</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#1a1a1a;">{len(day_df)}</div><div class="kpi-lbl">Total Batches Chilled</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#b91c1c;">🔴 Excursions (&gt; 5.0°C at 2h) ({len(excursions)})</div>',
                unsafe_allow_html=True,
            )
            if excursions:
                for exc in excursions:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 4px solid #b91c1c;">
                        <div style="font-weight:600; font-size:0.85rem;">{exc['Food']} • {exc['Location']}</div>
                        <div style="font-size:0.75rem; color:#b91c1c; margin-top:2px;">
                            Start: <b>{exc['Start_Temp']}°C</b> &nbsp;➔&nbsp; After 2h: <b>{exc['End_Temp']}°C</b> (Limit ≤ 5.0°C)
                        </div>
                        <div style="font-size:0.7rem; color:#8c8983; margin-top:3px;">Time: {exc['Time']} | Initial: {exc['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No cooling excursions on this day.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#15803d;">🟢 Successfully Chilled ({len(compliant_logs)})</div>',
                unsafe_allow_html=True,
            )
            if compliant_logs:
                for ok in compliant_logs:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 4px solid #15803d;">
                        <div style="font-weight:600; font-size:0.85rem;">{ok['Food']}</div>
                        <div style="font-size:0.75rem; color:#403d39; margin-top:2px;">
                            Start: <b>{ok['Start_Temp']}°C</b> &nbsp;➔&nbsp; After 2h: <b style="color:#15803d;">{ok['End_Temp']}°C</b>
                        </div>
                        <div style="font-size:0.7rem; color:#8c8983; margin-top:3px;">Method: {ok['Method']} | Signed: {ok['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No blast chilling logs recorded for this day.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_range:
        st.subheader(
            f"Blast Chiller Compliance Matrix ({start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')})"
        )
        if range_df.empty:
            st.info("No blast chiller records found for this 30-day window.")
        else:
            # Batch count by food and date
            matrix = range_df.pivot_table(
                index=["Location", "Food"],
                columns="Date_Str",
                values="End_Temp",
                aggfunc="count",
                fill_value=0,
            )
            st.dataframe(matrix, use_container_width=True)

            # High-level full log table
            st.write(f"**Total Cooling Records in Period:** {len(range_df)}")
            display_cols = [
                "Date_Str",
                "Time",
                "Location",
                "Food",
                "Start_Temp",
                "End_Temp",
                "Sign",
            ]
            st.dataframe(
                range_df[display_cols],
                use_container_width=True,
                hide_index=True,
            )
