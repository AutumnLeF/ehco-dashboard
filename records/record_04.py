import pandas as pd
import streamlit as st

# 1. SHIFT EXPECTATION RULES FOR RECORD 04
RECORD_04_RULES = {
    "Black Lacquer Kitchen": ["Dinner"],
    "Filia Kitchen": ["Breakfast", "Lunch", "Dinner"],
}

CORE_TEMP_LIMIT = 75.0  # Core temp must be >= 75.0°C


def audit_record_04(df_today):
    """Audits Record 04 data for meal shifts, sample counts, and temperature compliance."""
    if df_today.empty:
        return {"status": "empty", "pending": [], "excursions": [], "completed": []}

    # Normalize fields (handles both raw API dumps and direct web tables)
    df = df_today.copy()
    df.columns = [c.strip() for c in df.columns]

    loc_col = next(
        (c for c in df.columns if c.lower() in ["location", "submission.location"]),
        None,
    )
    meal_col = next(
        (
            c
            for c in df.columns
            if "meal" in c.lower() or "service" in c.lower()
        ),
        None,
    )
    temp_col = next(
        (
            c
            for c in df.columns
            if "temp" in c.lower() or "cooking" in c.lower()
        ),
        None,
    )
    food_col = next(
        (c for c in df.columns if "food" in c.lower() or "item" in c.lower()),
        None,
    )
    staff_col = next(
        (
            c
            for c in df.columns
            if "sign" in c.lower()
            or "initial" in c.lower()
            or "inspector" in c.lower()
        ),
        None,
    )

    if not (loc_col and meal_col and temp_col):
        return {
            "status": "error",
            "message": "Missing required columns in dataset.",
        }

    # Clean numeric temperatures
    df["Clean_Temp"] = pd.to_numeric(
        df[temp_col].astype(str).str.replace("°C", "").str.strip(),
        errors="coerce",
    )

    pending_shifts = []
    completed_shifts = []
    excursions = []

    # 1. Reconcile Kitchen Shifts
    for kitchen, expected_meals in RECORD_04_RULES.items():
        k_df = df[df[loc_col].str.strip().str.lower() == kitchen.lower()]

        for meal in expected_meals:
            m_df = k_df[k_df[meal_col].str.strip().str.lower() == meal.lower()]
            items_logged = len(m_df)

            if items_logged == 0:
                pending_shifts.append(
                    {
                        "Kitchen": kitchen,
                        "Meal": meal,
                        "Items_Logged": 0,
                        "Status": "Missing / Not Submitted",
                    }
                )
            else:
                completed_shifts.append(
                    {
                        "Kitchen": kitchen,
                        "Meal": meal,
                        "Items_Logged": items_logged,
                        "Inspector": (
                            m_df[staff_col].iloc[0]
                            if staff_col and not m_df.empty
                            else "Staff"
                        ),
                    }
                )

    # 2. Flag Temperature Violations (< 75°C)
    violating_rows = df[df["Clean_Temp"] < CORE_TEMP_LIMIT]
    for _, row in violating_rows.iterrows():
        excursions.append(
            {
                "Kitchen": row[loc_col],
                "Meal": row[meal_col],
                "Food": (
                    row[food_col] if food_col else "Unspecified Food"
                ),
                "Temp": row["Clean_Temp"],
                "Staff": row[staff_col] if staff_col else "Staff",
            }
        )

    return {
        "status": "ok",
        "pending": pending_shifts,
        "completed": completed_shifts,
        "excursions": excursions,
    }


def render_record_04_view(df_today):
    """Renders the UI for Record 04."""
    results = audit_record_04(df_today)

    if results["status"] == "error":
        st.error(results["message"])
        return

    pending = results["pending"]
    completed = results["completed"]
    excursions = results["excursions"]

    # Metrics Strip
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-num" style="color:#b91c1c;">{len(excursions)}</div><div class="kpi-lbl">Temp Breaches (&lt; 75°C)</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{len(pending)}</div><div class="kpi-lbl">Pending Meal Services</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-num" style="color:#15803d;">{len(completed)}</div><div class="kpi-lbl">Completed Shifts</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # Status Columns
    c1, c2, c3 = st.columns(3)

    # Lane 1: Excursions
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
                    <div style="font-size:0.75rem; color:#b91c1c; margin-top:4px;">Logged: <b>{exc['Temp']}°C</b> (Required ≥ 75.0°C)</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Signed: {exc['Staff']}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("All food items cooked to safe core temp (≥ 75°C).")
        st.markdown("</div>", unsafe_allow_html=True)

    # Lane 2: Pending Shifts
    with c2:
        st.markdown(
            f'<div class="kanban-col"><div class="kanban-h" style="color:#d97706;">🟡 Missing Meal Logs ({len(pending)})</div>',
            unsafe_allow_html=True,
        )
        if pending:
            for item in pending:
                st.markdown(
                    f"""
                <div class="check-card" style="border-left: 4px solid #d97706;">
                    <div style="font-weight:600; font-size:0.85rem;">{item['Kitchen']}</div>
                    <div style="font-size:0.8rem; color:#d97706; margin-top:2px;">{item['Meal']} Service</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:4px;">Status: No items logged yet</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("All expected meal services submitted!")
        st.markdown("</div>", unsafe_allow_html=True)

    # Lane 3: Completed Shifts
    with c3:
        st.markdown(
            f'<div class="kanban-col"><div class="kanban-h" style="color:#15803d;">🟢 Verified Meal Logs ({len(completed)})</div>',
            unsafe_allow_html=True,
        )
        if completed:
            for item in completed:
                st.markdown(
                    f"""
                <div class="check-card" style="border-left: 4px solid #15803d;">
                    <div style="font-weight:600; font-size:0.85rem;">{item['Kitchen']}</div>
                    <div style="font-size:0.8rem; color:#15803d; margin-top:2px;">{item['Meal']} Service</div>
                    <div style="font-size:0.75rem; color:#403d39; margin-top:2px;">{item['Items_Logged']} dishes verified</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Signed by: {item['Inspector']}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No services submitted yet.")
        st.markdown("</div>", unsafe_allow_html=True)
