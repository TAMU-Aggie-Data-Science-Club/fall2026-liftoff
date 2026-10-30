
import streamlit as st

from src.app.state import (
    initialize_session_state,
    update_trajectory_data,
    get_trajectory_data,
)

st.set_page_config(page_title="Session State Test")

initialize_session_state()

st.title("Liftoff Session State Test")

inputs_tab, results_tab = st.tabs(["Inputs", "Results"])

with inputs_tab:
    st.selectbox(
        "Rocket",
        ["Falcon 9", "Starship", "Atlas V"],
        key="selected_rocket",
    )

    st.number_input(
        "Payload Mass (kg)",
        min_value=0.0,
        key="payload_mass",
    )

    st.number_input(
        "Wind Speed (m/s)",
        min_value=0.0,
        key="wind_speed",
    )

    if st.button("Save Test Trajectory"):
        update_trajectory_data({
            "rocket": st.session_state["selected_rocket"],
            "payload_mass": st.session_state["payload_mass"],
            "wind_speed": st.session_state["wind_speed"],
        })
        st.success("Trajectory data saved!")

with results_tab:
    st.subheader("Saved Trajectory Data")

    data = get_trajectory_data()

    if data is None:
        st.info("No trajectory data saved yet.")
    else:
        st.json(data)
