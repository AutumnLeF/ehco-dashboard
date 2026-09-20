import os
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Kitchen Safety Core",
    page_icon="🛡️",
    layout="wide"
)

# Editorial Serif Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #fcfbf9; font-family: 'Inter', sans-serif; color: #2b2b2b; }
    .serif-title { font-family: 'Newsreader', serif; font-size: 2.2rem; font-weight: 400; color: #1a1a1a; margin-bottom: 0.2rem; }
    .sub-head { font-size: 0.78rem; color: #8c8983; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 0.4rem; }
    .kpi-box { padding: 0.6rem 0; border-bottom: 1px solid #e8e5e0; }
    .kpi-num { font-family: 'Newsreader', serif; font-size: 2.2rem; font-weight: 500; line-height: 1.1; }
    .kpi-lbl { font-size: 0.72rem; color: #8c8983; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.2rem; }
    .kanban-col { background: #ffffff; border-radius: 12px; padding: 1.2rem; border: 1px solid #ede9e1; min-height: 420px; }
    .kanban-h { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; padding-bottom: 0.6rem; border-bottom: 1px solid #f2eee9; margin-bottom: 1rem; }
    .check-card { padding: 0.85rem; border-radius: 8px; background: #ffffff; border: 1px solid #ede9e1; margin-bottom: 0.6rem; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 1. YOUR 10 SPECIFIC FOOD SAFETY RECORDS
# -------------------------------------------------------------
RECORD_TYPES = [
    "Record 2: Food Delivery Record",
    "Record 3: Food Storage Temperature Record",
    "Record 4: Cooking/Reheating Temperature Record",
    "Record 5: Cooling of Food Record",
    "Record 6: Food Display Temperature Record",
    "Record 12: Defrosting Record",
    "Record 13: Dishwasher / Glasswasher Temperature Record",
    "Record 15: Pesticide Usage Record",
    "Record 21: Food Washing Record",
    "Record 25: Ice Machine Cleaning Record"
]

CATALOGUE_FILE = "master_records_catalogue.csv"

# Pre-seeded default checklists across standard kitchen outlets
DEFAULT_CATALOGUE = [
    {"Kitchen": "Receiving Bay", "Record_Type": "Record 2: Food Delivery Record", "Task_Unit": "Raw Food Delivery Dock", "Daily_Freq": 1, "Rule_Type": "MAX", "Limit": 4.0},
    {"Kitchen": "Main Kitchen", "Record_Type": "Record 3: Food Storage Temperature Record", "Task_Unit": "Walk-in Chiller 1", "Daily_Freq": 2, "Rule_Type": "MAX", "Limit": 4.0},
    {"Kitchen": "Main Kitchen", "Record_Type": "Record 3: Food Storage Temperature Record", "Task_Unit": "Walk-in Freezer 1", "Daily_Freq": 2, "Rule_Type": "MAX", "Limit": -18.0},
    {"Kitchen": "Main Kitchen", "Record_Type": "Record 4: Cooking/Reheating Temperature Record", "Task_Unit": "Batch Cooking Core Probe", "Daily_Freq": 2, "Rule_Type": "MIN", "Limit": 75.0},
    {"Kitchen": "Main Kitchen", "Record_Type": "Record 5: Cooling of Food Record", "Task_Unit": "Blast Chiller Pull-Down", "Daily_Freq": 1, "Rule_Type": "MAX", "Limit": 21.0},
    {"Kitchen": "Banquet Line", "Record_Type": "Record 6: Food Display Temperature Record", "Task_Unit": "Buffet Bain-Marie Display", "Daily_Freq": 2, "Rule_Type": "MIN", "Limit": 63.0},
    {"Kitchen": "Butchery", "Record_Type": "Record 12: Defrosting Record", "Task_Unit": "Meat Thawing Room", "Daily_Freq": 1, "Rule_Type": "MAX", "Limit": 4.0},
    {"Kitchen": "Stewarding", "Record_Type": "Record 13: Dishwasher / Glasswasher Temperature Record", "Task_Unit": "Flight Conveyor Dishwasher", "Daily_Freq": 2, "Rule_Type": "MIN", "Limit": 82.0},
    {"Kitchen": "Entire Facility", "Record_Type": "Record 15: Pesticide Usage Record", "Task_Unit": "Pest Management Vendor Log", "Daily_Freq": 1, "Rule_Type": "AUDIT", "Limit": 0.0},
    {"Kitchen": "Pastry & Prep", "Record_Type": "Record 21: Food Washing Record", "Task_Unit": "Veg Disinfection Sink (50 PPM)", "Daily_Freq": 2, "Rule_Type": "MIN", "Limit": 50.0},
    {"Kitchen": "Beverage / Stewarding", "Record_Type": "Record 25: Ice Machine Cleaning Record", "Task_Unit": "Main Cube Ice Maker", "Daily_Freq": 1, "Rule_Type": "AUDIT", "Limit": 0.0},
]

def get_catalogue():
    if os.path.exists(CATALOGUE_FILE):
        return pd.read_csv(CATALOGUE_FILE)
    df = pd.DataFrame(DEFAULT_CATALOGUE)
    df.to_csv(CATALOGUE_FILE, index=False)
    return df

def save_catalogue(df):
    df.to_csv(CATALOGUE_FILE, index=False)

if "catalogue" not in st.session_state:
    st.session_state.catalogue = get_catalogue()

# -------------------------------------------------------------
# 2. SIDEBAR CONTROLS
# -------------------------------------------------------------
st.sidebar.title("⚙️ Inspection Controls")
target_date = st.sidebar.date_input("Audit Date", value=datetime.now(timezone.utc).date())
date_str = target_date.strftime("%Y-%m-%d")

api_token = st.sidebar.text_input("Cognito Bearer Token", type="password")
api_url = st.sidebar.text_input("Endpoint URL", value="https://example.com/form-store")

if st.sidebar.button("🔄 Sync Live Feed", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# -------------------------------------------------------------
# 3. HEADER & "ADD RECORD CHECK" MODAL
# -------------------------------------------------------------
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.markdown('<div class="sub-head">Today • Food-Safety Core</div>', unsafe_allow_html=True)
    st.markdown('<div class="serif-title">Daily Food Safety Log Audit</div>', unsafe_allow_html=True)

with col_h2:
    st.write("")
    if st.button("➕ Add Check / Unit", use_container_width=True):
        st.session_state.show_add = True

@st.dialog("Configure Record Requirement")
def modal_add_check():
    kitchen = st.text_input("KITCHEN / SECTION", placeholder="e.g. Pastry Kitchen")
    record_type = st.selectbox("RECORD CATEGORY", RECORD_TYPES)
    task_unit = st.text_input("UNIT / TASK / EQUIPMENT", placeholder="e.g. Walk-in Chiller 2")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        freq = st.number_input("DAILY FREQ", min_value=1, max_value=8, value=2)
    with col2:
        rule_type = st.selectbox("VALIDATION", ["MAX (Must stay ≤)", "MIN (Must reach ≥)", "AUDIT (Entry Check)"])
    with col3:
        lim_val = st.number_input("LIMIT VALUE (°C / PPM)", value=4.0 if "Storage" in record_type or "Delivery" in record_type else 75.0)

    if st.button("Save Record Requirement", type="primary", use_container_width=True):
        if kitchen.strip() and task_unit.strip():
            rule_clean = "MAX" if "MAX" in rule_type else ("MIN" if "MIN" in rule_type else "AUDIT")
            new_row = pd.DataFrame([{
                "Kitchen": kitchen.strip(),
                "Record_Type": record_type,
                "Task_Unit": task_unit.strip(),
                "Daily_Freq": int(freq),
                "Rule_Type": rule_clean,
                "Limit": float(lim_val)
            }])
            updated = pd.concat([st.session_state.catalogue, new_row], ignore_index=True)
            save_catalogue(updated)
            st.session_state.catalogue = updated
            st.success(f"Added {task_unit}!")
            st.rerun()
        else:
            st.warning("Please specify both kitchen and unit/task name.")

if st.session_state.get("show_add", False):
    modal_add_check()

# -------------------------------------------------------------
# 4. API EXTRACTION & RECONCILIATION
# -------------------------------------------------------------
catalogue_df = st.session_state.catalogue.copy()
logged_entries = []
excursions = []

if api_token and api_url:
    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
    try:
        res = requests.get(api_url, headers=headers, timeout=12)
        if res.status_code == 200:
            subs = res.json().get("submissions", [])
            raw_df = pd.json_normalize(subs)
            if not raw_df.empty:
                raw_df["Date"] = pd.to_datetime(raw_df.get("createdAt"), errors="coerce").dt.strftime("%Y-%m-%d")
                today_df = raw_df[raw_df["Date"] == date_str]

                for _, row in today_df.iterrows():
                    # Extract identifying task name
                    unit = str(
                        row.get("submission.Entry.Coolroom") or 
                        row.get("submission.Entry.Freezer") or 
                        row.get("submission.Entry.Equipment") or
                        row.get("submission.Entry.Dishwasher") or
                        row.get("submission.Location") or ""
                    ).strip()
                    
                    # Extract recorded reading
                    val = pd.to_numeric(
                        str(
                            row.get("submission.Entry.CRTemperature") or 
                            row.get("submission.Entry.FreezerTemp") or 
                            row.get("submission.Entry.CoreTemp") or
                            row.get("submission.Entry.RinseTemp") or
                            row.get("submission.Entry.PPM") or ""
                        ).replace("°C","").replace("PPM","").strip(),
                        errors="coerce"
                    )
                    inspector = row.get("user.email", "Staff")

                    if unit:
                        logged_entries.append(unit)
                        # Check threshold limits
                        matched = catalogue_df[catalogue_df["Task_Unit"].str.lower() == unit.lower()]
                        if not matched.empty:
                            rule = matched.iloc[0]
                            limit = rule["Limit"]
                            is_violation = (rule["Rule_Type"] == "MAX" and pd.notna(val) and val > limit) or \
                                           (rule["Rule_Type"] == "MIN" and pd.notna(val) and val < limit)
                            if is_violation:
                                excursions.append({
                                    "Kitchen": rule["Kitchen"],
                                    "Unit": unit,
                                    "Record_Type": rule["Record_Type"],
                                    "Reading": val,
                                    "Limit": limit,
                                    "Rule": rule["Rule_Type"],
                                    "Inspector": inspector
                                })
    except Exception as e:
        st.sidebar.error(f"Fetch error: {e}")

# Audit vs Catalogue Rules
audit_items = []
for _, rule in catalogue_df.iterrows():
    actual_count = logged_entries.count(rule["Task_Unit"])
    target = int(rule["Daily_Freq"])
    audit_items.append({
        "Kitchen": rule["Kitchen"],
        "Record_Type": rule["Record_Type"],
        "Task_Unit": rule["Task_Unit"],
        "Required": target,
        "Logged": actual_count,
        "Is_Pending": actual_count < target,
        "Limit": rule["Limit"],
        "Rule_Type": rule["Rule_Type"]
    })

audit_df = pd.DataFrame(audit_items)

# -------------------------------------------------------------
# 5. METRICS STRIP
# -------------------------------------------------------------
total_checks = int(audit_df["Required"].sum()) if not audit_df.empty else 0
completed_checks = int(audit_df["Logged"].sum()) if not audit_df.empty else 0
pending_count = len(audit_df[audit_df["Is_Pending"]])
excursion_count = len(excursions)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num text-neutral-900">{total_checks}</div><div class="kpi-lbl">Total Logs Expected</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#b91c1c;">{excursion_count}</div><div class="kpi-lbl">Critical Excursions</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#d97706;">{pending_count}</div><div class="kpi-lbl">Pending Submissions</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#15803d;">{completed_checks}</div><div class="kpi-lbl">Verified Completed</div></div>', unsafe_allow_html=True)

st.write("")

# -------------------------------------------------------------
# 6. FILTERS: KITCHEN & RECORD SELECTORS
# -------------------------------------------------------------
c_filter1, c_filter2 = st.columns([1, 2])
with c_filter1:
    kitchen_list = ["All"] + sorted(catalogue_df["Kitchen"].unique().tolist())
    selected_k = st.segmented_control("KITCHEN", kitchen_list, default="All")

with c_filter2:
    record_list = ["All"] + RECORD_TYPES
    selected_r = st.selectbox("FOOD SAFETY RECORD FILTER", record_list)

# Filter logic
f_audit = audit_df.copy()
if selected_k != "All":
    f_audit = f_audit[f_audit["Kitchen"] == selected_k]
if selected_r != "All":
    f_audit = f_audit[f_audit["Record_Type"] == selected_r]

f_excursions = [
    e for e in excursions 
    if (selected_k == "All" or e["Kitchen"] == selected_k) and (selected_r == "All" or e["Record_Type"] == selected_r)
]

st.write("")

# -------------------------------------------------------------
# 7. THREE-COLUMN KANBAN LANES
# -------------------------------------------------------------
col_exc, col_pend, col_done = st.columns(3)

# Excursions / Failures
with col_exc:
    st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#b91c1c;">🔴 Excursions / Violations ({len(f_excursions)})</div>', unsafe_allow_html=True)
    if f_excursions:
        for exc in f_excursions:
            sign = "≤" if exc['Rule'] == "MAX" else "≥"
            st.markdown(f"""
            <div class="check-card" style="border-left: 4px solid #b91c1c;">
                <div style="font-weight:600; font-size:0.85rem;">{exc['Kitchen']}</div>
                <div style="font-size:0.75rem; color:#8c8983;">{exc['Record_Type']}</div>
                <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{exc['Unit']}</div>
                <div style="font-size:0.75rem; color:#b91c1c; margin-top:4px;">Logged: <b>{exc['Reading']}</b> (Standard {sign} {exc['Limit']})</div>
                <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Inspector: {exc['Inspector']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No non-compliant records logged today.")
    st.markdown('</div>', unsafe_allow_html=True)

# Pending Records
with col_pend:
    pending_rows = f_audit[f_audit["Is_Pending"]]
    st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#d97706;">🟡 Pending Records ({len(pending_rows)})</div>', unsafe_allow_html=True)
    if not pending_rows.empty:
        for _, row in pending_rows.iterrows():
            st.markdown(f"""
            <div class="check-card" style="border-left: 4px solid #d97706;">
                <div style="font-weight:600; font-size:0.85rem;">{row['Kitchen']}</div>
                <div style="font-size:0.75rem; color:#8c8983;">{row['Record_Type']}</div>
                <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{row['Task_Unit']}</div>
                <div style="font-size:0.75rem; color:#8c8983; margin-top:4px;">Progress: {row['Logged']}/{row['Required']} logged today</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("All records fully submitted for this filter!")
    st.markdown('</div>', unsafe_allow_html=True)

# Completed & Compliant
with col_done:
    done_rows = f_audit[~f_audit["Is_Pending"]]
    st.markdown(f'<div class="kanban-col"><div class="kanban-h" style="color:#15803d;">🟢 Verified Complete ({len(done_rows)})</div>', unsafe_allow_html=True)
    if not done_rows.empty:
        for _, row in done_rows.iterrows():
            st.markdown(f"""
            <div class="check-card" style="border-left: 4px solid #15803d;">
                <div style="font-weight:600; font-size:0.85rem;">{row['Kitchen']}</div>
                <div style="font-size:0.75rem; color:#8c8983;">{row['Record_Type']}</div>
                <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{row['Task_Unit']}</div>
                <div style="font-size:0.75rem; color:#15803d; margin-top:4px;">✓ Complete ({row['Logged']}/{row['Required']} entries)</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No records marked complete yet.")
    st.markdown('</div>', unsafe_allow_html=True)
