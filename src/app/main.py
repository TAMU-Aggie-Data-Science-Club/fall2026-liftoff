# placeholder for streamlit connection
import streamlit as st

from components.charts import (
    create_3d_trajectory_figure,
    create_altitude_distance_figure,
    create_speed_time_figure,
    generate_mock_trajectory,
)

st.set_page_config(page_title="Liftoff Trajectory Dashboard", layout="wide")
st.title("Rocket Trajectory")

with st.sidebar:
    st.subheader("Rocket Selection")
    rocket = st.selectbox("Select Rocket", ["Rocket a", "Rocket b", "Rocket c"])
    mass = st.slider("Payload Mass", min_value=10, max_value=1000)
    weather = st.selectbox(
        "Weather Condition", ["Option a", "Option b", "Option c"]
    )
    fuel = st.slider("Fuel Amount", min_value=0, max_value=100)

trajectory = generate_mock_trajectory()
altitude_column, speed_column = st.columns(2, gap="large")

with altitude_column:
    st.plotly_chart(
        create_altitude_distance_figure(trajectory),
        width="stretch",
        config={"responsive": True},
        key="altitude-distance-chart",
    )

with speed_column:
    st.plotly_chart(
        create_speed_time_figure(trajectory),
        width="stretch",
        config={"responsive": True},
        key="speed-time-chart",
    )

st.plotly_chart(
    create_3d_trajectory_figure(trajectory),
    width="stretch",
    config={"responsive": True},
    key="3d-trajectory-chart",
)
