import streamlit as st

st.set_page_config(
    page_title="EHCO Compliance Dashboard Portal",
    page_icon="🛡️",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #0b192c; font-family: 'Inter', sans-serif; color: #ffffff; }
    .portal-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding-top: 10vh; text-align: center; }
    .portal-title { font-size: 2.8rem; font-weight: 700; letter-spacing: -0.03em; color: #ffffff; margin-bottom: 0.4rem; }
    .portal-subtitle { font-size: 1.05rem; color: #94a3b8; font-weight: 500; margin-bottom: 3rem; }
    
    /* Ensure Streamlit buttons inside columns are clearly visible */
    div.stButton > button {
        background-color: #38bdf8 !important;
        color: #0f172a !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2) !important;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        background-color: #0ea5e9 !important;
        color: #ffffff !important;
    }
</style>
<div class="portal-container">
    <div class="portal-title">EHCO Compliance Dashboard</div>
    <div class="portal-subtitle">Select an operational site to launch the audit portal</div>
</div>
""", unsafe_allow_html=True)

col_spacer1, col_roswyn, col_spacer2, col_fairmont, col_spacer3 = st.columns([1, 4, 1, 4, 1])

with col_roswyn:
    st.markdown("""
    <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 35px 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); min-height: 150px; display: flex; flex-direction: column; justify-content: center; align-items: center; margin-bottom: 15px;">
        <div style="font-size: 2.8rem; line-height: 1; margin-bottom: 12px;">🏠</div>
        <div style="font-size: 1.4rem; font-weight: 700; color: #ffffff;">Roswyn</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Launch Roswyn Portal ➔", use_container_width=True, key="btn_roswyn"):
        st.switch_page("pages/ros_overview.py")

with col_fairmont:
    st.markdown("""
    <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 35px 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); min-height: 150px; display: flex; flex-direction: column; justify-content: center; align-items: center; margin-bottom: 15px;">
        <div style="font-size: 2.8rem; line-height: 1; margin-bottom: 12px;">🏰</div>
        <div style="font-size: 1.4rem; font-weight: 700; color: #ffffff;">Fairmont Mumbai</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Launch Fairmont Portal ➔", use_container_width=True, key="btn_fairmont"):
        st.switch_page("pages/fairmont.py")
