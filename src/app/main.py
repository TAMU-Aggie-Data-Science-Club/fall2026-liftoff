import streamlit as st
from components.charts import (
    create_3d_trajectory_figure,
    create_altitude_distance_figure,
    create_speed_time_figure,
    generate_mock_trajectory,
)

st.set_page_config(page_title="Liftoff Trajectory Dashboard", layout="wide")
st.title("Rocket Trajectory Dashboard")

# Mission preset selection
presets = [
    "Custom Mission",
    "Falcon 9 Starlink Ascent",
    "High-Wind Scrub Scenario",
    "Heavy Payload LEO Target",
]

selected_preset = st.sidebar.selectbox("Mission Preset", presets)

# Example mission preset values (not historical launch data)
preset_values = {
    "Falcon 9 Starlink Ascent": {
        "rocket": "Falcon 9",
        "mass": 500,
        "weather": "Clear",
        "wind_speed": 10.0,
    },
    "High-Wind Scrub Scenario": {
        "rocket": "Falcon 9",
        "mass": 500,
        "weather": "High Winds",
        "wind_speed": 50.0,
    },
    "Heavy Payload LEO Target": {
        "rocket": "Falcon Heavy",
        "mass": 900,
        "weather": "Clear",
        "wind_speed": 5.0,
    },
}

# Apply preset values when the mission changes
if "previous_preset" not in st.session_state:
    st.session_state.previous_preset = "Custom Mission"

if selected_preset != st.session_state.previous_preset:
    if selected_preset in preset_values:
        values = preset_values[selected_preset]
        st.session_state["rocket"] = values["rocket"]
        st.session_state["mass"] = values["mass"]
        st.session_state["weather"] = values["weather"]
        st.session_state["wind_speed"] = values["wind_speed"]

    st.session_state.previous_preset = selected_preset

# --- Sidebar Controls ---
with st.sidebar.expander("Rocket Configuration", expanded=True):
    st.subheader("Rocket Selection")
    rocket = st.selectbox("Select Rocket", ["Falcon 9", "Falcon Heavy", "Starship"], key="rocket")

    st.subheader("Payload Mass")
    mass = st.slider("Payload Mass (kg)", min_value=10, max_value=1000, key="mass")

with st.sidebar.expander("Weather and Environment", expanded=True):
    st.subheader("Weather Condition Overrides")
    weather = st.selectbox("Select Weather Condition", ["Clear", "High Winds", "Storm"], key="weather")

    st.subheader("Wind Speed")
    wind_speed = st.number_input("Enter Wind Speed (mph)", min_value=0.0, value=10.0, key="wind_speed")

# Input state dictionary for downstream model consumption
input_data = {
    "rocket": rocket,
    "mass": mass,
    "weather": weather,
    "wind": wind_speed,
}

# Flight Readiness Panel (demo values)
if weather == "High Winds" or weather == "Storm" or wind_speed >= 40:
    launch_status = "NO-GO"
    risk = 85
elif wind_speed >= 25:
    launch_status = "NO-GO"
    risk = 55
else:
    launch_status = "GO"
    risk = 10

max_q = 35.0

st.subheader("Flight Readiness Panel")
st.caption("Demo estimates only — not real ML predictions or physics calculations.")

status_col, risk_col, stress_col = st.columns(3)

with status_col:
    st.metric("Launch Status", launch_status)

with risk_col:
    st.metric("Estimated Failure/Delay Risk", f"{risk}%")

with stress_col:
    st.metric("Max Q (Demo)", f"{max_q} kPa")

if launch_status == "GO":
    st.success("GO — Conditions meet the demo launch criteria.")
else:
    st.error("NO-GO — Conditions exceed the demo launch criteria.")
# Export Flight Briefing
import json
import pandas as pd

flight_briefing = {
    "mission_preset": selected_preset,
    "rocket": rocket,
    "payload_mass_kg": mass,
    "weather": weather,
    "wind_speed_mph": wind_speed,
    "launch_status": launch_status,
    "estimated_risk_percent": risk,
    "max_q_kpa": max_q,
    "data_source": "Demo values only",
}

st.subheader("Export Flight Briefing")

json_col, csv_col = st.columns(2)

with json_col:
    st.download_button(
        "Download JSON Briefing",
        data=json.dumps(flight_briefing, indent=4),
        file_name="flight_briefing.json",
        mime="application/json",
    )

with csv_col:
    st.download_button(
        "Download CSV Briefing",
        data=pd.DataFrame([flight_briefing]).to_csv(index=False),
        file_name="flight_briefing.csv",
        mime="text/csv",
    )
    
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