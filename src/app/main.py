
import json
import pandas as pd
import streamlit as st

from components.charts import (
    create_3d_trajectory_figure,
    create_altitude_distance_figure,
    create_speed_time_figure,
    generate_mock_trajectory,
)

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="LIFTOFF | Mission Control",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# MISSION CONTROL STYLING
# ============================================================

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: #06111f !important;
    color: #e9f5ff !important;
}

[data-testid="stHeader"] {
    background: #06111f !important;
}

.block-container {
    padding-top: 2.2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1600px !important;
}

html, body, p, label, div, span {
    font-family: 'Inter', sans-serif;
}

h1, h2, h3 {
    font-family: 'Rajdhani', sans-serif !important;
    color: #e9f5ff !important;
}

/* SIDEBAR - KEEP CURRENT APPEARANCE */

section[data-testid="stSidebar"] {
    background: #091b2d !important;
    min-width: 300px !important;
    max-width: 300px !important;
    border-right: 1px solid #21455f !important;
}

section[data-testid="stSidebar"] > div {
    background: #091b2d !important;
}

section[data-testid="stSidebar"] * {
    color: #e9f5ff;
}

section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #45e0f2 !important;
}

section[data-testid="stSidebar"] label {
    color: #c7dce9 !important;
    white-space: normal !important;
}

/* SIDEBAR EXPANDERS */

[data-testid="stExpander"] {
    background: #0d2033 !important;
    border: 1px solid #21455f !important;
    border-radius: 12px !important;
    overflow: hidden;
}

[data-testid="stExpander"] details {
    background: #0d2033 !important;
}

[data-testid="stExpander"] details summary {
    background: #112a40 !important;
    color: #e9f5ff !important;
    padding: 12px !important;
}

[data-testid="stExpander"] details summary * {
    color: #e9f5ff !important;
    background: transparent !important;
}

[data-testid="stExpander"] details summary:hover {
    background: #173850 !important;
}

[data-testid="stExpander"] details > div {
    background: #0d2033 !important;
}

/* INPUT CONTROLS */

div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background: #112a40 !important;
    color: #e9f5ff !important;
    border-color: #37617a !important;
    border-radius: 8px !important;
}

div[data-baseweb="select"] *,
div[data-baseweb="input"] input {
    color: #e9f5ff !important;
}

div[data-baseweb="popover"],
ul[role="listbox"] {
    background: #112a40 !important;
}

li[role="option"] {
    color: #e9f5ff !important;
}

li[role="option"]:hover {
    background: #1b4560 !important;
}

[data-testid="stSlider"] [role="slider"] {
    background: #45e0f2 !important;
}

/* METRIC CARDS */

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #10283d, #0b1c2d);
    border: 1px solid #285775;
    border-radius: 12px;
    padding: 18px 20px;
    min-height: 125px;
    overflow: hidden;
}

[data-testid="stMetricLabel"] {
    color: #a9c8d9 !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.6px;
    white-space: normal !important;
}

[data-testid="stMetricValue"] {
    color: #45e0f2 !important;
    font-size: clamp(22px, 2vw, 34px) !important;
    font-weight: 800 !important;
    overflow: visible !important;
}

[data-testid="stMetricValue"] > div {
    overflow: visible !important;
    text-overflow: clip !important;
}

/* CHART CONTAINERS */

[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: #0a1a2b !important;
    border-color: #1d3c53 !important;
    border-radius: 12px !important;
}

/* DOWNLOAD BUTTONS */

[data-testid="stDownloadButton"] button {
    background: #12354a !important;
    border: 1px solid #24cde4 !important;
    color: #e9f5ff !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    width: 100%;
}

[data-testid="stDownloadButton"] button:hover {
    background: #176078 !important;
    color: white !important;
}

/* SECTION HEADERS */

.section-heading {
    font-family: 'Rajdhani', sans-serif;
    color: #e9f5ff;
    border-left: 3px solid #45e0f2;
    padding-left: 12px;
    margin: 26px 0 16px 0;
    font-size: 21px;
    font-weight: 700;
    letter-spacing: 1px;
}

/* HERO */

.hero-eyebrow {
    color: #45e0f2;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 3px;
}

.hero-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: clamp(36px, 4vw, 60px);
    font-weight: 700;
    line-height: 1.1;
    color: #f0f8ff;
    margin: 12px 0;
}

.hero-title span {
    color: #45e0f2;
}

.hero-subtitle {
    color: #9ab9cc;
    font-size: 14px;
    margin-bottom: 22px;
}

.system-badge {
    display: inline-block;
    color: #45e0f2;
    border: 1px solid #247d93;
    background: #0b2938;
    border-radius: 5px;
    padding: 9px 13px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    margin: 0 8px 8px 0;
}

/* STATUS BANNERS */

.status-banner {
    padding: 16px 18px;
    border-radius: 9px;
    font-weight: 800;
    font-size: 14px;
    margin-top: 16px;
}

.status-go {
    color: #66f2c0;
    background: #092a2b;
    border: 1px solid #13a98b;
}

.status-no-go {
    color: #ff9e9e;
    background: #321b28;
    border: 1px solid #dc5269;
}

.info-note {
    color: #91adc1;
    font-size: 12px;
    margin-top: 12px;
}

.sidebar-title {
    color: #45e0f2;
    font-family: 'Rajdhani', sans-serif;
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 18px;
}

.footer {
    text-align: center;
    color: #7193a9;
    border-top: 1px solid #23445a;
    padding-top: 24px;
    margin-top: 36px;
    font-size: 11px;
    letter-spacing: 1px;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# MISSION PRESETS
# ============================================================

presets = [
    "Custom Mission",
    "Falcon 9 Starlink Ascent",
    "High-Wind Scrub Scenario",
    "Heavy Payload LEO Target",
]

preset_values = {
    "Falcon 9 Starlink Ascent": {
        "rocket": "Falcon 9",
        "mass": 500,
        "weather": "Clear",
        "wind_speed": 4.47,
    },
    "High-Wind Scrub Scenario": {
        "rocket": "Falcon 9",
        "mass": 500,
        "weather": "High Winds",
        "wind_speed": 22.35,
    },
    "Heavy Payload LEO Target": {
        "rocket": "Falcon Heavy",
        "mass": 900,
        "weather": "Clear",
        "wind_speed": 2.24,
    },
}

defaults = {
    "rocket": "Falcon 9",
    "mass": 10,
    "weather": "Clear",
    "wind_speed": 4.47,
    "previous_preset": "Custom Mission",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    '<div class="sidebar-title">🚀 MISSION SETTINGS</div>',
    unsafe_allow_html=True,
)

selected_preset = st.sidebar.selectbox(
    "Mission Preset",
    presets,
    key="selected_preset",
)

if selected_preset != st.session_state.previous_preset:
    if selected_preset in preset_values:
        values = preset_values[selected_preset]

        st.session_state["rocket"] = values["rocket"]
        st.session_state["mass"] = values["mass"]
        st.session_state["weather"] = values["weather"]
        st.session_state["wind_speed"] = values["wind_speed"]

    st.session_state.previous_preset = selected_preset

with st.sidebar.expander("🚀 Rocket Configuration", expanded=True):
    rocket = st.selectbox(
        "Launch Vehicle",
        ["Falcon 9", "Falcon Heavy", "Starship"],
        key="rocket",
    )

    mass = st.slider(
        "Payload Mass (kg)",
        min_value=10,
        max_value=1000,
        key="mass",
    )

with st.sidebar.expander("🌤️ Weather Environment", expanded=True):
    weather = st.selectbox(
        "Weather Condition",
        ["Clear", "High Winds", "Storm"],
        key="weather",
    )

    wind_speed = st.number_input(
        "Surface Wind Speed (m/s)",
        min_value=0.0,
        step=0.5,
        key="wind_speed",
    )

st.sidebar.markdown(
    """
<div style="margin-top:35px; border-top:1px solid #21455f; padding-top:20px;">
    <p style="color:#8aafc4;font-size:12px;">LIFTOFF / FALL 2026</p>
    <p style="color:#8aafc4;font-size:12px;">Mission Control System</p>
    <p style="color:#8aafc4;font-size:12px;">Simulation preview active</p>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================
# INPUT DATA
# ============================================================

input_data = {
    "rocket": rocket,
    "mass": mass,
    "weather": weather,
    "wind": wind_speed,
}

# ============================================================
# FLIGHT READINESS
# ============================================================

if weather in ["High Winds", "Storm"] or wind_speed >= 17.88:
    launch_status = "NO-GO"
    risk = 85
elif wind_speed >= 11.18:
    launch_status = "NO-GO"
    risk = 55
else:
    launch_status = "GO"
    risk = 10

max_q = 35.0

# ============================================================
# HERO
# ============================================================

st.markdown(
    """
<div class="hero-eyebrow">
    AGGIE DATA SCIENCE CLUB / FALL 2026 / FLIGHT SYSTEMS
</div>

<div class="hero-title">
    LIFTOFF <span>MISSION CONTROL</span>
</div>

<div class="hero-subtitle">
    Rocket Launch Intelligence • Flight Readiness • Trajectory Analytics
</div>

<div>
    <span class="system-badge">MISSION SYSTEMS ONLINE</span>
    <span class="system-badge">SIMULATION MODE</span>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================
# FLIGHT READINESS
# ============================================================

st.markdown(
    '<div class="section-heading">FLIGHT READINESS</div>',
    unsafe_allow_html=True,
)

status_col, risk_col, stress_col, wind_col = st.columns(4)

with status_col:
    st.metric("LAUNCH STATUS", launch_status)

with risk_col:
    st.metric("DELAY / FAILURE RISK", f"{risk}%")

with stress_col:
    st.metric("MAX DYNAMIC PRESSURE", f"{max_q:.1f} kPa")

with wind_col:
    st.metric("SURFACE WIND", f"{wind_speed:.2f} m/s")

if launch_status == "GO":
    st.markdown(
        """
<div class="status-banner status-go">
    ● GO — CONDITIONS MEET SIMULATED LAUNCH CRITERIA
</div>
""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
<div class="status-banner status-no-go">
    ● NO-GO — CONDITIONS EXCEED SIMULATED LAUNCH CRITERIA
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="info-note">Readiness and risk are illustrative estimates pending live model integration.</div>',
    unsafe_allow_html=True,
)

# ============================================================
# ACTIVE MISSION PROFILE
# ============================================================

st.markdown(
    '<div class="section-heading">ACTIVE MISSION PROFILE</div>',
    unsafe_allow_html=True,
)

mission_col, rocket_col, payload_col = st.columns(3)

with mission_col:
    st.metric("MISSION PROFILE", selected_preset)

with rocket_col:
    st.metric("LAUNCH VEHICLE", rocket)

with payload_col:
    st.metric("PAYLOAD MASS", f"{mass} kg")

# ============================================================
# FLIGHT BRIEFING EXPORT
# ============================================================

flight_briefing = {
    "mission_preset": selected_preset,
    "rocket": rocket,
    "payload_mass_kg": mass,
    "weather": weather,
    "wind_speed_mps": wind_speed,
    "launch_status": launch_status,
    "estimated_risk_percent": risk,
    "max_q_kpa": max_q,
    "data_source": "Simulated estimates; live models not connected",
}

st.markdown(
    '<div class="section-heading">FLIGHT BRIEFING EXPORT</div>',
    unsafe_allow_html=True,
)

json_col, csv_col = st.columns(2)

with json_col:
    st.download_button(
        "⬇ EXPORT JSON BRIEFING",
        data=json.dumps(flight_briefing, indent=4),
        file_name="liftoff_flight_briefing.json",
        mime="application/json",
        use_container_width=True,
    )

with csv_col:
    st.download_button(
        "⬇ EXPORT CSV BRIEFING",
        data=pd.DataFrame([flight_briefing]).to_csv(index=False),
        file_name="liftoff_flight_briefing.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ============================================================
# FLIGHT TELEMETRY ANALYTICS
# ============================================================

st.markdown(
    '<div class="section-heading">FLIGHT TELEMETRY ANALYTICS</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="info-note">Trajectory visualizations represent simulated flight paths.</div>',
    unsafe_allow_html=True,
)

trajectory = generate_mock_trajectory()

altitude_column, speed_column = st.columns(2, gap="large")

with altitude_column:
    with st.container(border=True):
        st.markdown(
            '<div style="color:#45e0f2;font-size:12px;font-weight:800;letter-spacing:1px;">ALTITUDE PROFILE</div>',
            unsafe_allow_html=True,
        )

        st.plotly_chart(
            create_altitude_distance_figure(trajectory),
            width="stretch",
            key="altitude-distance-chart",
            config={"displaylogo": False},
        )

with speed_column:
    with st.container(border=True):
        st.markdown(
            '<div style="color:#45e0f2;font-size:12px;font-weight:800;letter-spacing:1px;">VELOCITY PROFILE</div>',
            unsafe_allow_html=True,
        )

        st.plotly_chart(
            create_speed_time_figure(trajectory),
            width="stretch",
            key="speed-time-chart",
            config={"displaylogo": False},
        )

# ============================================================
# 3D FLIGHT PATH TRACKING
# ============================================================

st.markdown(
    '<div class="section-heading">3D FLIGHT PATH TRACKING</div>',
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.markdown(
        '<div style="color:#45e0f2;font-size:12px;font-weight:800;letter-spacing:1px;">TRAJECTORY VISUALIZATION / SIMULATED</div>',
        unsafe_allow_html=True,
    )

    st.plotly_chart(
        create_3d_trajectory_figure(trajectory),
        width="stretch",
        key="3d-trajectory-chart",
        config={"displaylogo": False},
    )

# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
<div class="footer">
    LIFTOFF MISSION CONTROL / AGGIE DATA SCIENCE CLUB / 2026
    <div style="margin-top:7px;">
        ROCKET LAUNCH INTELLIGENCE & TRAJECTORY VISUALIZATION
    </div>
    <div style="margin-top:7px;">
        FLIGHT SYSTEMS / SIMULATION PREVIEW
    </div>
</div>
""",
    unsafe_allow_html=True,
)
