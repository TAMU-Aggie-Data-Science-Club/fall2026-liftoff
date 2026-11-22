
import json

import pandas as pd
import streamlit as st

from components.charts import (
    create_3d_trajectory_figure,
    create_altitude_distance_figure,
    create_speed_time_figure,
    generate_mock_trajectory,
)

# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="LIFTOFF | Mission Control",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================
# MISSION CONTROL THEME
# ==========================================================

st.markdown("""
<style>
:root {
    color-scheme: dark;
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background:
        radial-gradient(ellipse at 75% 0%,
            rgba(0, 180, 220, 0.10), transparent 42%),
        #07111e;
    color: #e8f4ff;
}

[data-testid="stHeader"] {
    background: rgba(7, 17, 30, 0.9);
}

[data-testid="stSidebar"] {
    background: #0b1b2c;
    border-right: 1px solid #24435a;
}

[data-testid="stSidebar"] * {
    color: #e3f2fc;
}

h1, h2, h3, p, label {
    color: #e8f4ff;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #10273c, #0b1b2c);
    border: 1px solid #28516a;
    border-radius: 12px;
    padding: 20px;
    min-height: 115px;
    box-shadow: inset 0 1px rgba(100, 225, 255, 0.08);
}

[data-testid="stMetricLabel"] {
    color: #94b8cb;
    font-size: 0.82rem;
    letter-spacing: 0.5px;
}

[data-testid="stMetricValue"] {
    color: #59e5f5;
    font-weight: 750;
}

[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: rgba(13, 31, 49, 0.85);
    border-color: #28465c !important;
    border-radius: 12px !important;
}

[data-testid="stExpander"] {
    background: #10263a;
    border: 1px solid #294c65;
    border-radius: 10px;
}

div.stDownloadButton > button {
    background: #123a50;
    color: #70edff !important;
    border: 1px solid #2e9db6;
    border-radius: 8px;
    font-weight: 650;
    width: 100%;
}

div.stDownloadButton > button:hover {
    background: #17607a;
    color: white !important;
    border-color: #68e9ff;
}

[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stNumberInput"] input {
    background: #132c40 !important;
    color: #e8f4ff !important;
}

[data-testid="stAlert"] {
    border-radius: 10px;
}

.mc-eyebrow {
    color: #51dff0;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 3px;
    margin-bottom: 10px;
}

.mc-title {
    font-size: clamp(2rem, 4vw, 3.2rem);
    font-weight: 850;
    letter-spacing: 1px;
    color: #f1f9ff;
    line-height: 1.15;
}

.mc-title span {
    color: #50e3f3;
}

.mc-subtitle {
    color: #9bb9cc;
    font-size: 0.95rem;
    margin: 12px 0 22px;
}

.mc-section {
    color: #e7f5ff;
    font-size: 1.12rem;
    font-weight: 750;
    letter-spacing: 1px;
    border-left: 3px solid #46ddec;
    padding-left: 12px;
    margin-top: 24px;
    margin-bottom: 14px;
}

.mc-tag {
    display: inline-block;
    border: 1px solid #297f96;
    color: #63e1f1;
    background: rgba(14, 83, 108, 0.25);
    border-radius: 5px;
    padding: 7px 11px;
    font-size: 0.72rem;
    letter-spacing: 1px;
    font-weight: 700;
    margin-right: 8px;
    margin-bottom: 10px;
}

.mc-banner {
    padding: 15px 18px;
    border-radius: 9px;
    margin-top: 14px;
    margin-bottom: 14px;
    font-weight: 700;
    letter-spacing: 0.4px;
}

.mc-go {
    background: rgba(24, 154, 115, 0.12);
    border: 1px solid #1b9c76;
    color: #65e8b8;
}

.mc-nogo {
    background: rgba(216, 72, 80, 0.12);
    border: 1px solid #c84b59;
    color: #ff8e9b;
}

.mc-panel-label {
    color: #77cfe0;
    font-size: 0.72rem;
    letter-spacing: 1.5px;
    font-weight: 700;
}

.mc-footer {
    border-top: 1px solid #28465c;
    margin-top: 30px;
    padding: 20px;
    text-align: center;
    color: #7899ad;
    font-size: 0.75rem;
    letter-spacing: 1px;
}

[data-testid="stCaptionContainer"] {
    color: #91aec0;
}

hr {
    border-color: #24435a;
}
</style>
""", unsafe_allow_html=True)


# ==========================================================
# HEADER
# ==========================================================

st.markdown("""
<div class="mc-eyebrow">
    AGGIE DATA SCIENCE CLUB / FALL 2026 / FLIGHT SYSTEMS
</div>
<div class="mc-title">
    LIFTOFF <span>MISSION CONTROL</span>
</div>
<div class="mc-subtitle">
    Rocket Launch Intelligence &nbsp;•&nbsp;
    Flight Readiness &nbsp;•&nbsp;
    Trajectory Analytics
</div>
<div>
    <span class="mc-tag">MISSION SYSTEMS ONLINE</span>
    <span class="mc-tag">SIMULATION / DEMO MODE</span>
</div>
""", unsafe_allow_html=True)


# ==========================================================
# MISSION PRESETS
# ==========================================================

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

st.sidebar.markdown("## 🚀 MISSION SETTINGS")

selected_preset = st.sidebar.selectbox(
    "Mission Preset",
    presets,
)

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


# ==========================================================
# SIDEBAR
# ==========================================================

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

with st.sidebar.expander("🌦 Weather Environment", expanded=True):
    weather = st.selectbox(
        "Weather Condition",
        ["Clear", "High Winds", "Storm"],
        key="weather",
    )

    wind_speed = st.number_input(
        "Surface Wind Speed (m/s)",
        min_value=0.0,
        value=4.47,
        key="wind_speed",
    )

st.sidebar.divider()
st.sidebar.caption(
    "LIFTOFF / FALL 2026\n\n"
    "Mission Control Prototype\n\n"
    "Demonstration data currently active."
)


# ==========================================================
# INPUT DATA
# ==========================================================

input_data = {
    "rocket": rocket,
    "mass": mass,
    "weather": weather,
    "wind": wind_speed,
}


# ==========================================================
# DEMO FLIGHT READINESS
# ==========================================================

if (
    weather in ["High Winds", "Storm"]
    or wind_speed >= 17.88
):
    launch_status = "NO-GO"
    risk = 85

elif wind_speed >= 11.18:
    launch_status = "NO-GO"
    risk = 55

else:
    launch_status = "GO"
    risk = 10

max_q = 35.0


# ==========================================================
# FLIGHT READINESS PANEL
# ==========================================================

st.markdown(
    '<div class="mc-section">FLIGHT READINESS</div>',
    unsafe_allow_html=True,
)

status_col, risk_col, q_col, wind_col = st.columns(4, gap="medium")

with status_col:
    st.metric("LAUNCH STATUS", launch_status)

with risk_col:
    st.metric("DELAY / FAILURE RISK", f"{risk}%")

with q_col:
    st.metric("MAX Q / DEMO", f"{max_q:.1f} kPa")

with wind_col:
    st.metric("SURFACE WIND", f"{wind_speed:.2f} m/s")


if launch_status == "GO":
    st.markdown(
        '<div class="mc-banner mc-go">'
        '● GO — CONDITIONS MEET DEMONSTRATION CRITERIA'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="mc-banner mc-nogo">'
        '● NO-GO — CONDITIONS EXCEED DEMONSTRATION CRITERIA'
        '</div>',
        unsafe_allow_html=True,
    )

st.caption(
    "Readiness status and risk are illustrative estimates, "
    "not actual ML predictions."
)


# ==========================================================
# MISSION INFORMATION
# ==========================================================

st.markdown(
    '<div class="mc-section">ACTIVE MISSION PROFILE</div>',
    unsafe_allow_html=True,
)

profile_col, vehicle_col, payload_col = st.columns(3)

with profile_col:
    st.metric("MISSION PROFILE", selected_preset)

with vehicle_col:
    st.metric("LAUNCH VEHICLE", rocket)

with payload_col:
    st.metric("PAYLOAD MASS", f"{mass} kg")


# ==========================================================
# FLIGHT BRIEFING
# ==========================================================

flight_briefing = {
    "mission_preset": selected_preset,
    "rocket": rocket,
    "payload_mass_kg": mass,
    "weather": weather,
    "wind_speed_mps": wind_speed,
    "launch_status": launch_status,
    "estimated_risk_percent": risk,
    "max_q_kpa": max_q,
    "data_source": "Demo values only",
}

st.markdown(
    '<div class="mc-section">FLIGHT BRIEFING EXPORT</div>',
    unsafe_allow_html=True,
)

json_col, csv_col = st.columns(2)

with json_col:
    st.download_button(
        "⬇ EXPORT JSON BRIEFING",
        data=json.dumps(flight_briefing, indent=4),
        file_name="flight_briefing.json",
        mime="application/json",
        width="stretch",
    )

with csv_col:
    st.download_button(
        "⬇ EXPORT CSV BRIEFING",
        data=pd.DataFrame([flight_briefing]).to_csv(index=False),
        file_name="flight_briefing.csv",
        mime="text/csv",
        width="stretch",
    )


# ==========================================================
# CHART THEME
# ==========================================================

def style_mission_chart(fig):
    fig.update_layout(
        paper_bgcolor="#0d2032",
        plot_bgcolor="#0d2032",
        font=dict(
            color="#bcd9e8",
            family="Arial",
            size=12,
        ),
        title_font=dict(
            color="#e7f5ff",
            size=15,
        ),
        margin=dict(l=25, r=25, t=55, b=40),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#bcd9e8"),
        ),
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="#24435a",
        zerolinecolor="#24435a",
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="#24435a",
        zerolinecolor="#24435a",
    )

    if "scene" in fig.layout:
        fig.update_layout(
            scene=dict(
                bgcolor="#0d2032",
                xaxis=dict(
                    backgroundcolor="#0d2032",
                    gridcolor="#29475d",
                    color="#bcd9e8",
                    showbackground=True,
                ),
                yaxis=dict(
                    backgroundcolor="#0d2032",
                    gridcolor="#29475d",
                    color="#bcd9e8",
                    showbackground=True,
                ),
                zaxis=dict(
                    backgroundcolor="#0d2032",
                    gridcolor="#29475d",
                    color="#bcd9e8",
                    showbackground=True,
                ),
            )
        )

    return fig


# ==========================================================
# TRAJECTORY ANALYTICS
# ==========================================================

st.markdown(
    '<div class="mc-section">FLIGHT TELEMETRY ANALYTICS</div>',
    unsafe_allow_html=True,
)

st.caption(
    "Trajectory visualizations currently use mock data "
    "rather than live physics simulation outputs."
)

trajectory = generate_mock_trajectory()

altitude_col, speed_col = st.columns(2, gap="medium")

with altitude_col:
    with st.container(border=True):
        st.markdown(
            '<div class="mc-panel-label">ALTITUDE PROFILE</div>',
            unsafe_allow_html=True,
        )

        altitude_fig = create_altitude_distance_figure(trajectory)
        altitude_fig = style_mission_chart(altitude_fig)

        st.plotly_chart(
            altitude_fig,
            width="stretch",
            key="altitude-distance-chart",
        )

with speed_col:
    with st.container(border=True):
        st.markdown(
            '<div class="mc-panel-label">VELOCITY PROFILE</div>',
            unsafe_allow_html=True,
        )

        speed_fig = create_speed_time_figure(trajectory)
        speed_fig = style_mission_chart(speed_fig)

        st.plotly_chart(
            speed_fig,
            width="stretch",
            key="speed-time-chart",
        )


# ==========================================================
# 3D TRAJECTORY
# ==========================================================

st.markdown(
    '<div class="mc-section">3D FLIGHT PATH TRACKING</div>',
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.markdown(
        '<div class="mc-panel-label">'
        'TRAJECTORY VISUALIZATION / SIMULATED'
        '</div>',
        unsafe_allow_html=True,
    )

    trajectory_fig = create_3d_trajectory_figure(trajectory)
    trajectory_fig = style_mission_chart(trajectory_fig)

    trajectory_fig.update_layout(height=440)

    st.plotly_chart(
        trajectory_fig,
        width="stretch",
        key="3d-trajectory-chart",
    )


# ==========================================================
# FOOTER
# ==========================================================

st.markdown("""
<div class="mc-footer">
    LIFTOFF MISSION CONTROL / AGGIE DATA SCIENCE CLUB / 2026
    <br>
    ROCKET LAUNCH INTELLIGENCE & TRAJECTORY VISUALIZATION
    <br>
    PROTOTYPE SYSTEM — DEMONSTRATION DATA
</div>
""", unsafe_allow_html=True)
