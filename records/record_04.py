import pandas as pd
import streamlit as st

RECORD_04_FORM_ID = 31374

# Kitchen schedule requirements
KITCHEN_MEAL_RULES = {
    "Black Lacquer Kitchen": ["Dinner"],
    "Filia Kitchen": ["Breakfast", "Lunch", "Dinner"],
}

TEMP_THRESHOLD = 75.0


def parse_record_04_submissions(raw_df, target_date_str):
    """Filters formId 31374, unpacks the repeatable 'set' array, and returns a flat dish-level DataFrame."""
    if raw_df.empty:
        return pd.DataFrame()

    # 1. Filter by Record 4 formId or Form Title
    df = raw_df.copy()
    if "formId" in df.columns:
        df = df[df["formId"] == RECORD_04_FORM_ID]
    elif "submission.formId" in df.columns:
        df = df[df["submission.formId"] == RECORD_04_FORM_ID]

    if df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in df.iterrows():
        # Location & Metadata
        location = record.get("submission.Location") or record.get("Location") or "Unknown"
        sign = record.get("submission.Sign") or record.get("Sign") or "Staff"
        sub_date = record.get("submission.Date") or record.get("Date") or str(record.get("createdAt", ""))[:10]
        time_str = record.get("submission.Time") or record.get("Time") or ""

        # Normalize date matching (supports DD/MM/YYYY or YYYY-MM-DD)
        if target_date_str and target_date_str not in str(sub_date):
            continue

        # Extract the repeatable entry set
        entries = record.get("submission.set") or record.get("set") or []
        if isinstance(entries, list):
            for entry in entries:
                meal = entry.get("Meal_Service") or "Unassigned"
                treatment = entry.get("Heat_Treatment") or "Cooking"
                food = entry.get("Food") or entry.get("Name_of_Food_Other") or "Unnamed Food"
                
                # Temp can be under Temperature_Cooking, Temperature, or Temperature_Reheating
                temp_raw = (
                    entry.get("Temperature_Cooking")
                    or entry.get("Temperature")
                    or entry.get("Temperature_Reheating")
                    or entry.get("Temperature_copy")
                )
                temp_val = pd.to_numeric(str(temp_raw).replace("°C", "").strip(), errors="coerce")
                final_temp = pd.to_numeric(str(entry.get("Finaltemp", "")).replace("°C", "").strip(), errors="coerce")
                corrective = entry.get("Corrective_Actions_cooking") or entry.get("Corrective_Action") or ""

                rows.append({
                    "Location": location,
                    "Date": sub_date,
                    "Time": time_str,
                    "Meal_Service": meal,
                    "Treatment": treatment,
                    "Food": food,
                    "Temp": temp_val,
                    "Final_Temp": final_temp,
                    "Corrective_Action": corrective,
                    "Sign": sign
                })

    return pd.DataFrame(rows)


def audit_record_04(dish_df):
    """Evaluates meal completion and critical limits."""
    pending_shifts = []
    completed_shifts = []
    excursions = []

    for kitchen, expected_meals in KITCHEN_MEAL_RULES.items():
        k_dishes = dish_df[dish_df["Location"].str.strip().str.lower() == kitchen.lower()] if not dish_df.empty else pd.DataFrame()

        for meal in expected_meals:
            m_dishes = k_dishes[k_dishes["Meal_Service"].str.strip().str.lower() == meal.lower()] if not k_dishes.empty else pd.DataFrame()
            count = len(m_dishes)

            if count == 0:
                pending_shifts.append({
                    "Kitchen": kitchen,
                    "Meal": meal,
                    "Status": "Pending / Not Logged"
                })
            else:
                completed_shifts.append({
                    "Kitchen": kitchen,
                    "Meal": meal,
                    "Dishes_Count": count,
                    "Signed": m_dishes["Sign"].iloc[0]
                })

    # Flag temperature failures (< 75.0°C without sufficient reheat/final temp)
    if not dish_df.empty:
        for _, row in dish_df.iterrows():
            temp = row["Temp"]
            if pd.notna(temp) and temp < TEMP_THRESHOLD:
                excursions.append({
                    "Kitchen": row["Location"],
                    "Meal": row["Meal_Service"],
                    "Food": row["Food"],
                    "Temp": temp,
                    "Final_Temp": row["Final_Temp"],
                    "Action": row["Corrective_Action"],
                    "Sign": row["Sign"]
                })

    return pending_shifts, completed_shifts, excursions


def render_record_04_view(raw_df, target_date_str):
    """Renders the standalone editorial view for Record 04."""
    dish_df = parse_record_04_submissions(raw_df, target_date_str)
    pending, completed, excursions = audit_record_04(dish_df)

    # 1. Metric Counter
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#b91c1c;">{len(excursions)}</div><div class="kpi-lbl">Excursions (&lt; 75°C)</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{len(pending)}</div><div class="kpi-lbl">Pending Meal Shifts</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#15803d;">{len(completed)}</div><div class="kpi-lbl">Verified Shifts</div></div>', unsafe_allow_html=True)

    st.write("")

    # 2. Three Kanban Status Lanes
    c_left, c_mid, c_right = st.columns(3)

    with c_left:
        st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#b91c1c;">🔴 Core Temp Breaches ({len(excursions)})</div>', unsafe_allow_html=True)
        if excursions:
            for exc in excursions:
                st.markdown(f"""
                <div class="check-card" style="border-left: 4px solid #b91c1c;">
                    <div style="font-weight:600; font-size:0.85rem;">{exc['Kitchen']} • {exc['Meal']}</div>
                    <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{exc['Food']}</div>
                    <div style="font-size:0.75rem; color:#b91c1c; margin-top:3px;">Temp: <b>{exc['Temp']}°C</b> (Limit ≥ 75.0°C)</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Action: {exc['Action'] or 'None recorded'} | Signed: {exc['Sign']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("All food cooked/reheated to ≥ 75°C.")
        st.markdown('</div>', unsafe_allow_html=True)

    with c_mid:
        st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#d97706;">🟡 Pending Shifts ({len(pending)})</div>', unsafe_allow_html=True)
        if pending:
            for p in pending:
                st.markdown(f"""
                <div class="check-card" style="border-left: 4px solid #d97706;">
                    <div style="font-weight:600; font-size:0.85rem;">{p['Kitchen']}</div>
                    <div style="font-size:0.8rem; color:#d97706; margin-top:2px;">{p['Meal']} Service</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:4px;">No dishes submitted yet</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("All expected meal services completed!")
        st.markdown('</div>', unsafe_allow_html=True)

    with c_right:
        st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#15803d;">🟢 Verified Complete ({len(completed)})</div>', unsafe_allow_html=True)
        if completed:
            for c in completed:
                st.markdown(f"""
                <div class="check-card" style="border-left: 4px solid #15803d;">
                    <div style="font-weight:600; font-size:0.85rem;">{c['Kitchen']}</div>
                    <div style="font-size:0.8rem; color:#15803d; margin-top:2px;">{c['Meal']} Service</div>
                    <div style="font-size:0.75rem; color:#403d39; margin-top:2px;">{c['Dishes_Count']} food items logged</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Initial: {c['Signed']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No meal services verified yet.")
        st.markdown('</div>', unsafe_allow_html=True)
