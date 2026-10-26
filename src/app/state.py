
import streamlit as st


DEFAULT_STATE = {
    "selected_rocket": None,
    "payload_mass": 0.0,
    "wind_speed": 0.0,
    "trajectory_data": None,
}


def initialize_session_state():
    """Initialize session values without overwriting existing values."""
    for key, default_value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def update_trajectory_data(data):
    """Save calculated trajectory data for reuse across tabs."""
    st.session_state["trajectory_data"] = data


def get_trajectory_data():
    """Retrieve previously calculated trajectory data."""
    return st.session_state.get("trajectory_data")
