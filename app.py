import os
import json
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st

# -------------------------------------------------------------
# 1. PAGE SETUP & EDITORIAL STYLING
# -------------------------------------------------------------
st.set_page_config(
    page_title="Kitchen Safety Core",
    page_icon="🛡️",
    layout="wide"
)

# Custom CSS for the clean, publication-style UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Inter:wght@400;500;600&display=swap');

    .stApp {
        background-color: #fcfbf9;
        font-family: 'Inter', sans-serif;
        color: #2b2b2b;
    }

    .editorial-headline {
        font-family: 'Newsreader', serif;
        font-size: 2.2rem;
        font-weight: 400;
        color: #1f1f1f;
        margin-bottom: 0.2rem;
    }

    .editorial-sub {
        font-size: 0.8rem;
        color: #8c8983;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }

    .metric-card {
        padding: 0.8rem 0;
        border-bottom: 1px solid #e8e5e0;
    }
    .metric-val {
        font-family: 'Newsreader', serif;
        font-size: 2.2rem;
        font-weight: 500;
        line-height: 1.1;
    }
    .metric-lbl {
        font-size: 0.72rem;
        color: #8c8983;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.2rem;
    }

    .kanban-lane {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.2rem;
        border: 1px solid #ede9e1;
        min-height: 420px;
    }
    .kanban-title {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid #f2eee9;
        margin-bottom: 1rem;
    }
    .item-card {
        padding: 0.85rem;
        border-radius: 8px;
        background: #ffffff;
        border: 1px solid #ede9e1;
        margin-bottom: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. LOCAL CATALOGUE MANAGEMENT (SAVES IN-APP CONFIG)
# -------------------------------------------------------------
CATALOGUE_FILE = "units_catalogue.csv"

DEFAULT_CATALOGUE = [
    {"Kitchen": "Main Kitchen", "Unit": "Walk-in Chiller 1", "Category": "Cold Storage", "Target_Freq": 2, "Limit": 4.0},
    {"Kitchen": "Main Kitchen", "Unit": "Walk-in Freezer 1", "Category": "Freezer", "Target_Freq": 2, "Limit": -18.0},
    {"Kitchen": "Kitchen B", "Unit": "Line Chiller", "Category": "Cold Storage", "Target_Freq": 2, "Limit": 4.0},
    {"Kitchen": "Kitchen B", "Unit": "Cooking Batch Log", "Category": "Cooking Temp", "Target_Freq": 3, "Limit": 75.0},
    {"Kitchen": "Pastry", "Unit": "Pastry Chiller", "Category": "Cold Storage", "Target_Freq": 2, "Limit": 4.0},
]

def load_catalogue():
    if os.path.exists(CATALOGUE_FILE):
        return pd.read_csv(CATALOGUE_FILE)
    df = pd.DataFrame(DEFAULT_CATALOGUE)
    df.to_csv(CATALOGUE_FILE, index=False)
    return df

def save_catalogue(df):
    df.to_csv(CATALOGUE_FILE, index=False)

if "catalogue" not in st.session_state:
    st.session_state.catalogue = load_catalogue()

# -------------------------------------------------------------
# 3. API DATA FETCHER
# -------------------------------------------------------------
def fetch_safety_records(api_url, token):
    if not api_url or not token:
        return pd.DataFrame()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    try:
        res = requests.get(api_url, headers=headers, timeout=12)
        if res.status_code == 200:
            payload = res.json()
            submissions = payload.get("submissions", [])
            df = pd.json_normalize(submissions)
            return df
        else:
            st.sidebar.error(f"API Error {res.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.sidebar.error(f"Connection failed: {e}")
        return pd.DataFrame()

# -------------------------------------------------------------
# 4. SIDEBAR CONFIGURATION
# -------------------------------------------------------------
st.sidebar.title("⚙️ Operations Panel")

target_date = st.sidebar.date_input("Audit Date", value=datetime.now(timezone.utc).date())
date_str = target_date.strftime("%Y-%m-%d")

api_token = st.sidebar.text_input("Cognito Bearer Token", type="password", help="Paste your session token")
api_endpoint = st.sidebar.text_input("Endpoint URL", value="https://example.com/form-store")

if st.sidebar.button("🔄 Sync Live Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# -------------------------------------------------------------
# 5. HEADER & ADD TO CATALOGUE MODAL
# -------------------------------------------------------------
col_h1, col_h2 = st.columns([4, 1])

with col_h1:
    st.markdown('<div class="editorial-sub">Today • Food-Safety Core</div>', unsafe_allow_html=True)
    st.markdown('<div class="editorial-headline">Daily safety checks and compliance.</div>', unsafe_allow_html=True)

with col_h2:
    st.write("")
    if st.button("➕ Add to catalogue", use_container_width=True):
        st.session_state.show_add_modal = True

@st.dialog("Add to the catalogue.")
def add_modal_dialog():
    item_name = st.text_input("ITEM / UNIT NAME", placeholder="e.g. Line Chiller 2")
    kitchen = st.text_input("KITCHEN", placeholder="e.g. Main Kitchen")
    category = st.selectbox("CATEGORY", ["Cold Storage", "Freezer", "Cooking Temp", "Hot Holding", "Sanitation / PPM"])
    
    c_f, c_l = st.columns(2)
    with c_f:
        freq = st.number_input("DAILY FREQUENCY", min_value=1, max_value=10, value=2)
    with c_l:
        limit = st.number_input("CRITICAL LIMIT (°C)", value=4.0)

    if st.button("Save to Catalogue", type="primary", use_container_width=True):
        if item_name.strip() and kitchen.strip():
            new_row = pd.DataFrame([{
                "Kitchen": kitchen.strip(),
                "Unit": item_name.strip(),
                "Category": category,
                "Target_Freq": freq,
                "Limit": limit
            }])
            updated_cat = pd.concat([st.session_state.catalogue, new_row], ignore_index=True)
            save_catalogue(updated_cat)
            st.session_state.catalogue = updated_cat
            st.success(f"Added {item_name}!")
            st.rerun()
        else:
            st.warning("Please specify both a unit name and kitchen.")

if st.session_state.get("show_add_modal", False):
    add_modal_dialog()

# -------------------------------------------------------------
# 6. RECONCILIATION AUDIT LOGIC
# -------------------------------------------------------------
catalogue_df = st.session_state.catalogue.copy()
raw_df = fetch_safety_records(api_endpoint, api_token)

# Parse raw submissions if present
completed_logs = []
excursions = []

if not raw_df.empty:
    raw_df["Date"] = pd.to_datetime(raw_df.get("createdAt"), errors="coerce").dt.strftime("%Y-%m-%d")
    today_records = raw_df[raw_df["Date"] == date_str].copy()

    for _, row in today_records.iterrows():
        unit_name = str(row.get("submission.Entry.Coolroom") or row.get("submission.Entry.Freezer") or "").strip()
        temp_val = pd.to_numeric(
            str(row.get("submission.Entry.CRTemperature") or row.get("submission.Entry.FreezerTemp") or "")
            .replace("°C", "").strip(), 
            errors="coerce"
        )
        inspector = row.get("user.email", "Staff")

        if unit_name:
            completed_logs.append(unit_name)
            # Find matching catalogue rule
            matched = catalogue_df[catalogue_df["Unit"].str.lower() == unit_name.lower()]
            if not matched.empty:
                rule_limit = matched.iloc[0]["Limit"]
                if pd.notna(temp_val) and temp_val > rule_limit:
                    excursions.append({
                        "Kitchen": matched.iloc[0]["Kitchen"],
                        "Unit": unit_name,
                        "Temp": temp_val,
                        "Limit": rule_limit,
                        "Inspector": inspector
                    })

# Identify pending units
audit_summary = []
for _, rule in catalogue_df.iterrows():
    logged_count = completed_logs.count(rule["Unit"])
    req = int(rule["Target_Freq"])
    audit_summary.append({
        "Kitchen": rule["Kitchen"],
        "Unit": rule["Unit"],
        "Category": rule["Category"],
        "Required": req,
        "Logged": logged_count,
        "Remaining": max(0, req - logged_count),
        "Is_Pending": logged_count < req,
        "Limit": rule["Limit"]
    })

audit_df = pd.DataFrame(audit_summary)

# -------------------------------------------------------------
# 7. METRIC STRIP
# -------------------------------------------------------------
total_units = len(catalogue_df)
pending_total = len(audit_df[audit_df["Is_Pending"]])
excursion_total = len(excursions)
done_total = total_units - pending_total

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-val text-neutral-900">{total_units}</div><div class="metric-lbl">Registered Units</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#b91c1c;">{excursion_total}</div><div class="metric-lbl">Excursions / Breach</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#d97706;">{pending_total}</div><div class="metric-lbl">Pending Submission</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#15803d;">{done_total}</div><div class="metric-lbl">Verified Complete</div></div>', unsafe_allow_html=True)

st.write("")

# -------------------------------------------------------------
# 8. KITCHEN FILTER PILLS
# -------------------------------------------------------------
kitchen_options = ["All"] + sorted(catalogue_df["Kitchen"].unique().tolist())
selected_k = st.segmented_control("KITCHEN FILTER", kitchen_options, default="All")

filtered_audit = audit_df if selected_k == "All" else audit_df[audit_df["Kitchen"] == selected_k]
filtered_excursions = [e for e in excursions if selected_k == "All" or e["Kitchen"] == selected_k]

st.write("")

# -------------------------------------------------------------
# 9. THREE-COLUMN STATUS VIEW
# -------------------------------------------------------------
c_left, c_mid, c_right = st.columns(3)

# 1. Overdue / Excursions
with c_left:
    st.markdown(f'<div class="kanban-lane"><div class="kanban-title" style="color:#b91c1c;">🔴 Excursions ({len(filtered_excursions)})</div>', unsafe_allow_html=True)
    if filtered_excursions:
        for exc in filtered_excursions:
            st.markdown(f"""
            <div class="item-card" style="border-left: 4px solid #b91c1c;">
                <div style="font-weight:600; font-size: 0.85rem;">{exc['Kitchen']}</div>
                <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{exc['Unit']}</div>
                <div style="font-size:0.75rem; color:#b91c1c; margin-top:4px;">Logged: <b>{exc['Temp']}°C</b> (Limit ≤ {exc['Limit']}°C)</div>
                <div style="font-size:0.7rem; color:#8c8983; margin-top:2px;">Inspector: {exc['Inspector']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No temperature excursions logged.")
    st.markdown('</div>', unsafe_allow_html=True)

# 2. Pending Checks
with c_mid:
    pending_items = filtered_audit[filtered_audit["Is_Pending"]]
    st.markdown(f'<div class="kanban-lane"><div class="kanban-title" style="color:#d97706;">🟡 Pending Checklist ({len(pending_items)})</div>', unsafe_allow_html=True)
    if not pending_items.empty:
        for _, item in pending_items.iterrows():
            st.markdown(f"""
            <div class="item-card" style="border-left: 4px solid #d97706;">
                <div style="font-weight:600; font-size: 0.85rem;">{item['Kitchen']}</div>
                <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{item['Unit']}</div>
                <div style="font-size:0.75rem; color:#8c8983; margin-top:4px;">Progress: {item['Logged']}/{item['Required']} checks submitted</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("All scheduled checks completed for this selection!")
    st.markdown('</div>', unsafe_allow_html=True)

# 3. Verified Complete
with c_right:
    completed_items = filtered_audit[~filtered_audit["Is_Pending"]]
    st.markdown(f'<div class="kanban-lane"><div class="kanban-title" style="color:#15803d;">🟢 Completed Today ({len(completed_items)})</div>', unsafe_allow_html=True)
    if not completed_items.empty:
        for _, item in completed_items.iterrows():
            st.markdown(f"""
            <div class="item-card" style="border-left: 4px solid #15803d;">
                <div style="font-weight:600; font-size: 0.85rem;">{item['Kitchen']}</div>
                <div style="font-size:0.8rem; color:#403d39; margin-top:2px;">{item['Unit']}</div>
                <div style="font-size:0.75rem; color:#15803d; margin-top:4px;">✓ Complete ({item['Logged']}/{item['Required']} logs)</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No completed logs yet.")
    st.markdown('</div>', unsafe_allow_html=True)
