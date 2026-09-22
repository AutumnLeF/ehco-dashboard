import streamlit as st

st.set_page_config(
    page_title="EHCO Compliance Dashboard Portal",
    page_icon="🛡️",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #070f1e 0%, #0b192c 50%, #112238 100%);
        font-family: 'Inter', sans-serif;
        color: #ffffff;
    }
    
    /* Hide default sidebar on landing page for a clean portal look */
    [data-testid="stSidebar"] {
        display: none;
    }

    .portal-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding-top: 8vh;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .portal-badge {
        background: rgba(56, 189, 248, 0.1);
        border: 1px solid rgba(56, 189, 248, 0.3);
        color: #38bdf8;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }

    .portal-title {
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #ffffff;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .portal-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        font-weight: 500;
    }

    /* Card styling */
    .site-card {
        background: linear-gradient(145deg, #132238 0%, #1a2c42 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 40px 20px;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        margin-bottom: 20px;
    }
    
    .site-card:hover {
        transform: translateY(-5px);
        border-color: #38bdf8;
        box-shadow: 0 20px 30px -10px rgba(56, 189, 248, 0.15);
    }

    /* Custom button styling */
    div.stButton > button {
        background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.75rem 1.5rem !important;
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3) !important;
        transition: all 0.2s ease-in-out;
        letter-spacing: 0.02em;
    }
    
    div.stButton > button:hover {
        background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 100%) !important;
        box-shadow: 0 6px 16px rgba(56, 189, 248, 0.4) !important;
        transform: translateY(-2px);
    }
</style>

<div class="portal-container">
    <div class="portal-badge">🛡️Food Safety & Hygiene</div>
    <div class="portal-title">EHCO Compliance Dashboard</div>
    <div class="portal-subtitle">Select an operational site below to launch the portal</div>
</div>
""", unsafe_allow_html=True)

col_spacer1, col_roswyn, col_spacer2, col_fairmont, col_spacer3 = st.columns([1.5, 4, 1, 4, 1.5])

with col_roswyn:
    st.markdown("""
    <div class="site-card">
        <div style="font-size: 3.2rem; line-height: 1; margin-bottom: 16px;">🏠</div>
        <div style="font-size: 1.6rem; font-weight: 700; color: #ffffff; letter-spacing: -0.01em;">Roswyn</div>
        <div style="font-size: 0.85rem; color: #64748b; margin-top: 6px; font-weight: 600;">SITE 1 OPERATIONS</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Launch Roswyn Portal ➔", use_container_width=True, key="btn_roswyn"):
        st.switch_page("pages/roswyn.py")

with col_fairmont:
    st.markdown("""
    <div class="site-card">
        <div style="font-size: 3.2rem; line-height: 1; margin-bottom: 16px;">🏰</div>
        <div style="font-size: 1.6rem; font-weight: 700; color: #ffffff; letter-spacing: -0.01em;">Fairmont Mumbai</div>
        <div style="font-size: 0.85rem; color: #64748b; margin-top: 6px; font-weight: 600;">SITE 2 OPERATIONS</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Launch Fairmont Portal ➔", use_container_width=True, key="btn_fairmont"):
        st.switch_page("pages/fairmont.py")
