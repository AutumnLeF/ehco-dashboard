import streamlit as st

st.set_page_config(
    page_title="EHCO Compliance Dashboard Portal",
    page_icon="🛡️",
    layout="wide",
)

# -------------------------------------------------------------
# LUXURY BLACK PORTAL THEME STYLING
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp { 
        background-color: #0b192c; 
        font-family: 'Inter', sans-serif; 
        color: #ffffff; 
    }
    
    .portal-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 75vh;
        text-align: center;
    }
    
    .portal-title {
        font-size: 3rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: #ffffff;
        margin-bottom: 0.5rem;
    }
    
    .portal-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        font-weight: 500;
        margin-bottom: 3rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="portal-container">
    <div class="portal-title">EHCO Compliance Dashboard</div>
    <div class="portal-subtitle">Select an operational site to launch the audit portal</div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# DUAL BRAND GATEWAY CARDS
# -------------------------------------------------------------
col_spacer1, col_roswyn, col_spacer2, col_fairmont, col_spacer3 = st.columns([1.5, 3, 1, 3, 1.5])

with col_roswyn:
    st.markdown("""
    <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 30px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <div style="font-size: 2.2rem; margin-bottom: 10px;">🏠</div>
        <div style="font-size: 1.4rem; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Roswyn</div>
        <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 20px;">Site 1 Operations & EHCO Compliance</div>
    </div>
    """, unsafe_allow_html=True)
    
    # ADD/UPDATE SWITCH LINE HERE:
    if st.button("Launch Roswyn Portal ➔", use_container_width=True, key="btn_launch_roswyn"):
        st.switch_page("app_roswyn.py")

with col_fairmont:
    st.markdown("""
    <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 30px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <div style="font-size: 2.2rem; margin-bottom: 10px;">🏨</div>
        <div style="font-size: 1.4rem; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Fairmont Mumbai</div>
        <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 20px;">Site 2 Operations & EHCO Compliance</div>
    </div>
    """, unsafe_allow_html=True)
    
    # ADD/UPDATE SWITCH LINE HERE:
    if st.button("Launch Fairmont Portal ➔", use_container_width=True, key="btn_launch_fairmont"):
        st.switch_page("app_fairmont.py")
