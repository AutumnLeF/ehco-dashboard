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
    .portal-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding-top: 4vh; text-align: center; }
    .portal-title { font-size: 2.6rem; font-weight: 700; letter-spacing: -0.03em; color: #ffffff; margin-bottom: 0.4rem; }
    .portal-subtitle { font-size: 1rem; color: #94a3b8; font-weight: 500; margin-bottom: 2rem; }
</style>
<div class="portal-container">
    <div class="portal-title">EHCO Compliance Dashboard</div>
    <div class="portal-subtitle">Select an operational site to launch the audit portal</div>
</div>
""", unsafe_allow_html=True)

col_spacer1, col_roswyn, col_spacer2, col_fairmont, col_spacer3 = st.columns([1, 4, 1, 4, 1])

with col_roswyn:
    st.markdown("""
    <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 25px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); min-height: 160px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
        <div style="font-size: 2.5rem; line-height: 1; margin-bottom: 12px;">🏠</div>
        <div style="font-size: 1.3rem; font-weight: 700; color: #ffffff; margin-bottom: 6px;">Roswyn</div>
        <div style="font-size: 0.8rem; color: #94a3b8;">Site 1 Operations & EHCO Compliance</div>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    if st.button("Launch Roswyn Portal ➔", use_container_width=True, key="btn_roswyn"):
        st.switch_page("pages/ros_overview.py")

with col_fairmont:
    st.markdown("""
    <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 25px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); min-height: 160px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
        <div style="font-size: 2.5rem; line-height: 1; margin-bottom: 12px;">🏰</div>
        <div style="font-size: 1.3rem; font-weight: 700; color: #ffffff; margin-bottom: 6px;">Fairmont Mumbai</div>
        <div style="font-size: 0.8rem; color: #94a3b8;">Site 2 Operations & EHCO Compliance</div>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    if st.button("Launch Fairmont Portal ➔", use_container_width=True, key="btn_fairmont"):
        st.switch_page("pages/fairmont.py")
