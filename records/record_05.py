import pandas as pd
import streamlit as st

RECORD_05_LOCATION = "Filia Kitchen"
MAX_COOLING_2HR_TEMP = 5.0  # Must be <= 5.0°C after 2 hours in blast chiller


def audit_record_05(df_today):
    """Audits Record 05 (Cooling of Food Record) for daily completion and 2-hour limits."""
    if df_today.empty:
        return {
            "status": "empty",
            "pending": [
                {
                    "Kitchen": RECORD_05_LOCATION,
                    "Task": "Daily Blast Chilling Log",
                    "Details": "No cooling cycles logged today",
                }
            ],
            "excursions": [],
            "completed": [],
        }

    df = df_today.copy()
    df.columns = [c.strip() for c in df.columns]

    loc_col = next(
        (c for c in df.columns if c.lower() in ["location", "submission.location"]),
        None,
    )
    food_col = next(
        (c for c in df.columns if "food" in c.lower() or "item" in c.lower()),
        None,
    )
    start_temp_col = next(
        (c for c in df.columns if "start temp" in c.lower()),
        None,
    )
    end_temp_col = next(
        (
            c
            for c in df.columns
            if "after 2 hours" in c.lower() or "blast chiller" in c.lower()
        ),
        None,
    )
    staff_col = next(
        (
            c
            for c in df.columns
            if "sign" in c.lower() or "initial" in c.lower() or "inspector" in c.lower()
        ),
        None,
    )

    if not (loc_col and end_temp_col):
        return {
            "status": "error",
            "message": "Required columns (Location or Temperature after 2 Hours) not found.",
        }

    # Clean numeric 2-hour end temperature
    df["Clean_End_Temp"] = pd.to_numeric(
        df[end_temp_col].astype(str).str.replace("°C", "").str.strip(),
        errors="coerce",
    )

    filia_records = df[df[loc_col].str.strip().str.lower() == RECORD_05_LOCATION.lower()]

    pending = []
    completed = []
    excursions = []

    # 1. Completion Check
    if filia_records.empty:
        pending.append(
            {
                "Kitchen": RECORD_05_LOCATION,
                "Task": "Daily Blast Chilling Log",
                "Details": "Zero cooling cycles logged today",
            }
        )
    else:
        completed.append(
            {
                "Kitchen": RECORD_05_LOCATION,
                "Task": "Blast Chiller Cycle",
                "Items_Logged": len(filia_records),
                "Inspector": (
                    filia_records[staff_col].iloc[0]
                    if staff_col and not filia_records.empty
                    else "Staff"
                ),
            }
        )

    # 2. Temperature Limit Check (> 5.0°C after 2 hours)
    for _, row in filia_records.iterrows():
        end_temp = row["Clean_End_Temp"]
        food_name = row[food_col] if food_col else "Item"
        staff = row[staff_col] if staff_col else "Staff"
        start_temp = row[start_temp_col] if start_temp_col else "N/A"

        if pd.isna(end_temp):
            excursions.append(
                {
                    "Kitchen": RECORD_05_LOCATION,
                    "Food": food_name,
                    "Details": "Missing 2-hour pull-down temperature reading",
                    "Severity": "Warning",
                    "Staff": staff,
                }
            )
        elif end_temp > MAX_COOLING_2HR_TEMP:
            excursions.append(
                {
                    "Kitchen": RECORD_05_LOCATION,
                    "Food": food_name,
                    "Details": f"Failed 2h pull-down: {end_temp}°C (Start: {start_temp}°C, Limit ≤ {MAX_COOLING_2HR_TEMP}°C)",
                    "Severity": "Critical Violation",
                    "Staff": staff,
                }
            )

    return {
        "status": "ok",
        "pending": pending,
        "completed": completed,
        "excursions": excursions,
    }


def render_record_05_view(df_today):
    """Renders the UI for Record 05."""
    results = audit_record_05(df_today)

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
            f'<div class="kpi-box"><div class="kpi-num" style="color:#b91c1c;">{len(excursions)}</div><div class="kpi-lbl">Pull-down Excursions (&gt; 5.0°C)</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{len(pending)}</div><div class="kpi-lbl">Pending Submission</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-num" style="color:#15803d;">{len(completed)}</div><div class="kpi-lbl">Verified Cycles</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # Status Lanes
    c1, c2, c3 = st.columns(3)

    # Lane 1: Excursions
    with c1:
        st.markdown(
            f'<div class="kanban-col"><div class="kanban-h" style="color:#b91c1c;">🔴 Cooling Excursions ({len(excursions)})</div>',
            unsafe_allow_html=True,
        )
        if excursions:
            for exc in excursions:
                st.markdown(
                    f"""
                <div class="check-card" style="border-left: 4px solid #b91c1c;">
                    <div style="font-weight:600; font-size:0.85rem;">{exc['Kitchen']} • {exc['Food']}</div>
                    <div style="font-size:0.75rem; color:#b91c1c; margin-top:3px;">{exc['Details']}</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:3px;">Initial: {exc['Staff']}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("All batches pulled down to safe temperatures within 2 hours.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Lane 2: Pending
    with c2:
        st.markdown(
            f'<div class="kanban-col"><div class="kanban-h" style="color:#d97706;">🟡 Pending Checklist ({len(pending)})</div>',
            unsafe_allow_html=True,
        )
        if pending:
            for item in pending:
                st.markdown(
                    f"""
                <div class="check-card" style="border-left: 4px solid #d97706;">
                    <div style="font-weight:600; font-size:0.85rem;">{item['Kitchen']}</div>
                    <div style="font-size:0.8rem; color:#d97706; margin-top:2px;">{item['Task']}</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:4px;">{item['Details']}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Daily cooling log completed!")
        st.markdown("</div>", unsafe_allow_html=True)

    # Lane 3: Completed
    with c3:
        st.markdown(
            f'<div class="kanban-col"><div class="kanban-h" style="color:#15803d;">🟢 Verified Complete ({len(completed)})</div>',
            unsafe_allow_html=True,
        )
        if completed:
            for item in completed:
                st.markdown(
                    f"""
                <div class="check-card" style="border-left: 4px solid #15803d;">
                    <div style="font-weight:600; font-size:0.85rem;">{item['Kitchen']}</div>
                    <div style="font-size:0.8rem; color:#15803d; margin-top:2px;">{item['Task']}</div>
                    <div style="font-size:0.75rem; color:#403d39; margin-top:2px;">{item['Items_Logged']} batches chilled & verified</div>
                    <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Signed by: {item['Inspector']}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No cooling cycles recorded today.")
        st.markdown("</div>", unsafe_allow_html=True)
