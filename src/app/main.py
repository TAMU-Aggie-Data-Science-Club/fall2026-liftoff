import streamlit as st
from components.charts import (
    create_3d_trajectory_figure,
    create_altitude_distance_figure,
    create_speed_time_figure,
    generate_mock_trajectory,
)

st.set_page_config(page_title="Liftoff Trajectory Dashboard", layout="wide")
st.title("Rocket Trajectory Dashboard")

# --- Sidebar Controls ---
with st.sidebar.expander("Rocket Configuration", expanded=True):
    st.subheader("Rocket Selection")
    rocket = st.selectbox("Select Rocket", ["Falcon 9", "Falcon Heavy", "Starship"])

    st.subheader("Payload Mass")
    mass = st.slider("Payload Mass (kg)", min_value=10, max_value=1000)

with st.sidebar.expander("Weather and Environment", expanded=True):
    st.subheader("Weather Condition Overrides")
    weather = st.selectbox("Select Weather Condition", ["Clear", "High Winds", "Storm"])

    st.subheader("Wind Speed")
    wind_speed = st.number_input("Enter Wind Speed (mph)", min_value=0.0, value=10.0)

# Input state dictionary for downstream model consumption
input_data = {
    "rocket": rocket,
    "mass": mass,
    "weather": weather,
    "wind": wind_speed,
}

# --- Visualizations ---
trajectory = generate_mock_trajectory()
altitude_column, speed_column = st.columns(2, gap="large")

with altitude_column:
    with st.container(border=True):
        st.plotly_chart(
            create_altitude_distance_figure(trajectory),
            use_container_width=True,
            key="altitude-distance-chart",
        )

with speed_column:
    with st.container(border=True):
        st.plotly_chart(
            create_speed_time_figure(trajectory),
            use_container_width=True,
            key="speed-time-chart",
        )

with st.container(border=True):
    st.plotly_chart(
        create_3d_trajectory_figure(trajectory),
        use_container_width=True,
        key="3d-trajectory-chart",
    )