from datetime import datetime
import pandas as pd
import streamlit as st

RECORD_04_FORM_ID = 31374

KITCHEN_MEAL_RULES = {
    "Black Lacquer Kitchen": ["Dinner"],
    "Filia Kitchen": ["Breakfast", "Lunch", "Dinner"],
}

TEMP_THRESHOLD = 75.0


def parse_all_record_04_dishes(raw_df):
    """Unpacks all dishes from formId 31374 across all dates."""
    if raw_df.empty:
        return pd.DataFrame()

    df = raw_df.copy()

    # Match formId loosely (string or int, or submission.formId)
    form_col = next(
        (c for c in df.columns if c.lower() in ["formid", "submission.formid"]),
        None,
    )
    if form_col:
        df = df[df[form_col].astype(str) == str(RECORD_04_FORM_ID)]

    if df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in df.iterrows():
        location = (
            record.get("submission.Location")
            or record.get("Location")
            or "Unknown"
        )
        sign = (
            record.get("submission.Sign")
            or record.get("Sign")
            or record.get("user.email")
            or "Staff"
        )
        time_str = record.get("submission.Time") or record.get("Time") or ""

        # Normalize submission date
        raw_date = (
            record.get("submission.Date")
            or record.get("Date")
            or record.get("createdAt")
            or record.get("submission.createdAt")
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

        # Handle 'set' whether it is a dict, list, or under submission.set
        entries = (
            record.get("submission.set")
            or record.get("set")
            or record.get("submission.Entry")
            or []
        )

        if isinstance(entries, dict):
            entries = [entries]

        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                meal = entry.get("Meal_Service") or "Unassigned"
                food = (
                    entry.get("Food")
                    or entry.get("Name_of_Food_Other")
                    or "Food Item"
                )
                temp_raw = (
                    entry.get("Temperature_Cooking")
                    or entry.get("Temperature")
                    or entry.get("Temperature_Reheating")
                    or entry.get("Temperature_copy")
                )
                temp_val = pd.to_numeric(
                    str(temp_raw).replace("°C", "").strip(), errors="coerce"
                )
                corrective = (
                    entry.get("Corrective_Actions_cooking")
                    or entry.get("Corrective_Action")
                    or ""
                )

                rows.append(
                    {
                        "Date_Str": norm_date,
                        "Date_Obj": date_obj,
                        "Time": time_str,
                        "Location": location,
                        "Meal_Service": meal,
                        "Food": food,
                        "Temp": temp_val,
                        "Corrective_Action": corrective,
                        "Sign": sign,
                    }
                )

    return pd.DataFrame(rows)


def render_record_04_view(raw_df, selected_day_str, start_date, end_date):
    """Renders both multi-day summary matrix and focused single-day drilldown."""
    all_dishes_df = parse_all_record_04_dishes(raw_df)

    if not all_dishes_df.empty and "Date_Obj" in all_dishes_df.columns:
        range_df = all_dishes_df[
            (all_dishes_df["Date_Obj"] >= start_date)
            & (all_dishes_df["Date_Obj"] <= end_date)
        ]
    else:
        range_df = all_dishes_df.copy()

    tab_day, tab_range = st.tabs(
        [f"📅 Daily Audit ({selected_day_str})", "📈 14-Day Completion Matrix"]
    )

    with tab_day:
        day_df = (
            range_df[range_df["Date_Str"] == selected_day_str]
            if not range_df.empty
            else pd.DataFrame()
        )

        pending = []
        completed = []
        excursions = []

        for kitchen, meals in KITCHEN_MEAL_RULES.items():
            k_df = (
                day_df[
                    day_df["Location"].str.strip().str.lower()
                    == kitchen.lower()
                ]
                if not day_df.empty
                else pd.DataFrame()
            )

            for meal in meals:
                m_df = (
                    k_df[
                        k_df["Meal_Service"].str.strip().str.lower()
                        == meal.lower()
                    ]
                    if not k_df.empty
                    else pd.DataFrame()
                )
                if m_df.empty:
                    pending.append({"Kitchen": kitchen, "Meal": meal})
                else:
                    completed.append(
                        {
                            "Kitchen": kitchen,
                            "Meal": meal,
                            "Count": len(m_df),
                            "Sign": m_df["Sign"].iloc[0],
                        }
                    )

        if not day_df.empty:
            violating = day_df[day_df["Temp"] < TEMP_THRESHOLD]
            for _, r in violating.iterrows():
                excursions.append(
                    {
                        "Kitchen": r["Location"],
                        "Meal": r["Meal_Service"],
                        "Food": r["Food"],
                        "Temp": r["Temp"],
                        "Sign": r["Sign"],
                    }
                )

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#b91c1c;">{len(excursions)}</div><div class="kpi-lbl">Excursions (&lt; 75°C)</div></div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{len(pending)}</div><div class="kpi-lbl">Pending Shifts</div></div>',
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#15803d;">{len(completed)}</div><div class="kpi-lbl">Verified Complete</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#b91c1c;">🔴 Core Temp Breaches ({len(excursions)})</div>',
                unsafe_allow_html=True,
            )
            if excursions:
                for exc in excursions:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 4px solid #b91c1c;">
                        <div style="font-weight:600; font-size:0.85rem;">{exc['Kitchen']} • {exc['Meal']}</div>
                        <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{exc['Food']}</div>
                        <div style="font-size:0.75rem; color:#b91c1c; margin-top:3px;">Temp: <b>{exc['Temp']}°C</b> (Limit ≥ 75.0°C)</div>
                        <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Signed: {exc['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No temperature excursions on this day.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#d97706;">🟡 Pending Shifts ({len(pending)})</div>',
                unsafe_allow_html=True,
            )
            if pending:
                for p in pending:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 4px solid #d97706;">
                        <div style="font-weight:600; font-size:0.85rem;">{p['Kitchen']}</div>
                        <div style="font-size:0.8rem; color:#d97706; margin-top:2px;">{p['Meal']} Service</div>
                        <div style="font-size:0.7rem; color:#8c8983; margin-top:4px;">Missing submission</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("All shifts completed for this day!")
            st.markdown("</div>", unsafe_allow_html=True)

        with c3:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#15803d;">🟢 Verified Shifts ({len(completed)})</div>',
                unsafe_allow_html=True,
            )
            if completed:
                for c in completed:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 4px solid #15803d;">
                        <div style="font-weight:600; font-size:0.85rem;">{c['Kitchen']}</div>
                        <div style="font-size:0.8rem; color:#15803d; margin-top:2px;">{c['Meal']} Service</div>
                        <div style="font-size:0.75rem; color:#403d39; margin-top:2px;">{c['Count']} dishes logged</div>
                        <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Initial: {c['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No completed logs on this day.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_range:
        st.subheader(
            f"Daily Compliance Matrix ({start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')})"
        )
        if range_df.empty:
            st.info("No logs found for this date range.")
        else:
            matrix = range_df.pivot_table(
                index=["Location", "Meal_Service"],
                columns="Date_Str",
                values="Temp",
                aggfunc="count",
                fill_value=0,
            )
            st.dataframe(matrix, use_container_width=True)

            range_violations = range_df[range_df["Temp"] < TEMP_THRESHOLD]
            st.write(
                f"**Total Excursions Across Window:** {len(range_violations)}"
            )
            if not range_violations.empty:
                st.dataframe(
                    range_violations[
                        [
                            "Date_Str",
                            "Time",
                            "Location",
                            "Meal_Service",
                            "Food",
                            "Temp",
                            "Sign",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
