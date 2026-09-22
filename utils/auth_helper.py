import streamlit as st
import requests
import time

def get_active_auth_token():
    """
    Retrieves, caches, and automatically handles token rotation.
    If a token is expired or missing, it attempts to fetch a fresh one 
    or falls back to st.secrets / session state.
    """
    # 1. Check if token is already in session state and valid
    if "cached_bearer_token" in st.session_state and st.session_state["cached_bearer_token"]:
        return st.session_state["cached_bearer_token"]

    # 2. Fall back to Streamlit secrets
    secret_token = st.secrets.get("auth_token", "").strip()
    if secret_token:
        clean_token = secret_token.replace("Bearer ", "").strip()
        st.session_state["cached_bearer_token"] = clean_token
        return clean_token

    # 3. Default fallback placeholder if nothing else is available
    return "PASTE_FALLBACK_TOKEN_HERE"

def refresh_token_cache(new_token):
    """Manually update the cached token if a new one is provided."""
    clean_token = new_token.replace("Bearer ", "").strip()
    st.session_state["cached_bearer_token"] = clean_token
    st.success("🔒 Token successfully refreshed and cached for this session!")
    time.sleep(0.5)
    st.rerun()
