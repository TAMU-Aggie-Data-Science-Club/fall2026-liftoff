import time
import streamlit as st
from components.charts import (
    create_3d_trajectory_figure,
    create_altitude_distance_figure,
    create_speed_time_figure,
    generate_mock_trajectory,
)

# --- Page Configuration ---
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
    wind_speed = st.number_input("Enter Wind Speed (mph)", min_value=0.0, max_value=100.0, value=10.0)

    st.subheader("Launch Site Selection")
    launch_site = st.selectbox("Select Launch Site", ["Cape Canaveral (SLC-40)", "Vandenberg (SLC-4E)", "Boca Chica (Starbase)"])

with st.sidebar:
    st.subheader("Launch!")
    launch_button = st.button("Launch Rocket", use_container_width=True)

# Input state dictionary for downstream model consumption
input_data = {
    "rocket": rocket,
    "mass": mass,
    "weather": weather,
    "wind": wind_speed,
    "launch_site": launch_site,
}

# --- Validation & Processing ---
if launch_button:
    if wind_speed < 0 or wind_speed > 100:
        st.error("Wind speed must be between 0 and 100 mph.")
    else:
        with st.spinner("Processing Trajectory & Risk Models..."):
            time.sleep(1)  # Simulated execution pause

# --- Visualizations & Navigation ---
tab1, tab2, tab3 = st.tabs(["Flight Simulation", "ML Analytics", "Telemetry Comparison"])

trajectory = generate_mock_trajectory()

# Tab 1: Flight Simulation
with tab1:
    st.subheader("Flight Simulation")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric(label="Max Altitude (m)", value="250,000", delta="Nominal")
    with col2:
        with st.container(border=True):
            st.metric(label="Max Velocity (m/s)", value="7,800", delta="+120 m/s")
    with col3:
        with st.container(border=True):
            st.metric(label="Flight Time (s)", value="540", delta="T+00:09:00")

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

# Tab 2: ML Analytics
with tab2:
    st.subheader("ML Analytics")
    st.write("Machine learning predictive models for launch delays and risk analysis.")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.metric(label="Model ROC-AUC Score", value="0.89", delta="+0.04")
    with col2:
        with st.container(border=True):
            st.metric(label="Predicted Delay Risk", value="12%", delta="-3%")

# Tab 3: Telemetry Comparison
with tab3:
    st.subheader("Telemetry Comparison")
    st.write("Compare simulated trajectory parameters against historical reference telemetry.")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.metric(label="Sim vs Real Deviation (RMSE)", value="1.4%", delta="Low Error")
    with col2:
        with st.container(border=True):
            st.metric(label="Sample Drift", value="0.02", delta="Stable")