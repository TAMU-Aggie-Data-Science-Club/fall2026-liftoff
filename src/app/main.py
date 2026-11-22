
import json
import pandas as pd
import streamlit as st

from components.charts import (
    create_3d_trajectory_figure,
    create_altitude_distance_figure,
    create_speed_time_figure,
    generate_mock_trajectory,
)

st.set_page_config(
    page_title="LIFTOFF | Mission Control",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------
# MISSION CONTROL STYLING
# --------------------------------------------------

st.markdown("""
<style>
:root {
    --navy: #061321;
    --sidebar: #071e30;
    --panel: #0c2337;
    --cyan: #43d9eb;
    --border: #28536c;
    --white: #eaf5ff;
}

html, body, .stApp {
    background: var(--navy) !important;
    color: var(--white) !important;
}

/* Remove the white Streamlit header */
[data-testid="stHeader"] {
    background: var(--navy) !important;
    height: 0 !important;
    min-height: 0 !important;
}

[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background: var(--navy) !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
}

[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] * {
    color: var(--white);
}

[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #102b41 !important;
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background: #153149 !important;
}

[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] input {
    background: #102b41 !important;
    color: var(--white) !important;
    border-color: #54758a !important;
}

/* Headings */
.mission-eyebrow {
    color: var(--cyan);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 3px;
    margin-bottom: 12px;
}

.mission-title {
    font-size: clamp(32px, 3.5vw, 54px);
    font-weight: 900;
    letter-spacing: 1px;
    line-height: 1.15;
    color: var(--white);
    margin-bottom: 14px;
}

.mission-title span {
    color: var(--cyan);
}

.mission-subtitle {
    color: #a6c0d1;
    font-size: 15px;
    margin-bottom: 24px;
}

.mission-tag {
    display: inline-block;
    color: var(--cyan);
    border: 1px solid #168ca6;
    background: #082637;
    border-radius: 5px;
    padding: 10px 15px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    margin-right: 10px;
    margin-bottom: 18px;
}

.section-heading {
    color: var(--white);
    font-size: 17px;
    font-weight: 850;
    letter-spacing: 1px;
    border-left: 3px solid var(--cyan);
    padding-left: 13px;
    margin-top: 30px;
    margin-bottom: 18px;
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #102b41, #0a1d2f);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 22px 20px;
    min-height: 120px;
    box-sizing: border-box;
}

.metric-label {
    color: #b8cfdf;
    font-size: 12px;
    font-weight: 750;
    letter-spacing: .5px;
    margin-bottom: 18px;
}

.metric-value {
    color: var(--cyan);
    font-size: clamp(20px, 2vw, 29px);
    font-weight: 850;
    overflow-wrap: anywhere;
}

/* Readiness banner */
.readiness-banner {
    margin-top: 24px;
    margin-bottom: 12px;
    padding: 17px 20px;
    border-radius: 9px;
    font-size: 14px;
    font-weight: 800;
}

.readiness-go {
    color: #65efc6;
    background: #082d2e;
    border: 1px solid #00b98e;
}

.readiness-no-go {
    color: #ff9999;
    background: #331b27;
    border: 1px solid #e45a67;
}

.helper-text {
    color: #91aebf;
    font-size: 13px;
    margin-top: 8px;
    margin-bottom: 22px;
}

/* Chart containers */
.chart-panel {
    background: #091b2c;
    border: 1px solid #193449;
    border-radius: 10px;
    padding: 13px;
    margin-bottom: 12px;
}

.chart-heading {
    color: var(--cyan);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .6px;
    margin-bottom: 8px;
}

/* Download buttons */
.stDownloadButton button {
    background: #10374c !important;
    border: 1px solid #0ba8c5 !important;
    color: var(--white) !important;
    border-radius: 5px !important;
    width: 100%;
}

.stDownloadButton button:hover {
    background: #17516b !important;
    color: white !important;
}

/* Footer */
.mission-footer {
    text-align: center;
    color: #7193a8;
    border-top: 1px solid #28536c;
    padding: 22px 0;
    margin-top: 32px;
    font-size: 11px;
    letter-spacing: 1px;
    line-height: 2;
}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# MISSION PRESETS
# --------------------------------------------------

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


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.markdown("## 🚀 MISSION SETTINGS")

    selected_preset = st.selectbox(
        "Mission Preset",
        presets,
        key="selected_preset",
    )

    if selected_preset != st.session_state.previous_preset:
        if selected_preset in preset_values:
            values = preset_values[selected_preset]

            for key, value in values.items():
                st.session_state[key] = value

        st.session_state.previous_preset = selected_preset

    with st.expander("🚀 Rocket Configuration", expanded=True):
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

    with st.expander("🌤️ Weather Environment", expanded=True):
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

    st.markdown("---")
    st.markdown(
        """
        <div style="color:#9bb9cb;line-height:2">
            LIFTOFF / FALL 2026
            <p>Mission Control System</p>
            <p>Simulation preview active</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------
# FLIGHT READINESS
# --------------------------------------------------

# Preliminary rule-based estimates.
# These values are not outputs from the trained ML model.

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


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown(
    """
    <div class="mission-eyebrow">
        AGGIE DATA SCIENCE CLUB / FALL 2026 / FLIGHT SYSTEMS
    </div>

    <div class="mission-title">
        LIFTOFF <span>MISSION CONTROL</span>
    </div>

    <div class="mission-subtitle">
        Rocket Launch Intelligence • Flight Readiness • Trajectory Analytics
    </div>

    <div>
        <span class="mission-tag">MISSION SYSTEMS ONLINE</span>
        <span class="mission-tag">SIMULATION MODE</span>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# FLIGHT READINESS CARDS
# --------------------------------------------------

st.markdown(
    '<div class="section-heading">FLIGHT READINESS</div>',
    unsafe_allow_html=True,
)

metrics = [
    ("LAUNCH STATUS", launch_status),
    ("DELAY / FAILURE RISK", f"{risk}%"),
    ("MAX DYNAMIC PRESSURE", f"{max_q:.1f} kPa"),
    ("SURFACE WIND", f"{wind_speed:.2f} m/s"),
]

metric_columns = st.columns(4, gap="medium")

for column, (label, value) in zip(metric_columns, metrics):
    with column:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Separate banner from cards with proper spacing
if launch_status == "GO":
    banner_class = "readiness-go"
    banner_text = "● GO — CONDITIONS MEET SIMULATED LAUNCH CRITERIA"
else:
    banner_class = "readiness-no-go"
    banner_text = "● NO-GO — LAUNCH CONDITIONS EXCEED SAFETY THRESHOLDS"

st.markdown(
    f"""
    <div class="readiness-banner {banner_class}">
        {banner_text}
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="helper-text">
        Readiness and risk are preliminary rule-based estimates
        pending integration with the trained prediction model.
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# ACTIVE MISSION PROFILE
# --------------------------------------------------

st.markdown(
    '<div class="section-heading">ACTIVE MISSION PROFILE</div>',
    unsafe_allow_html=True,
)

profile_metrics = [
    ("MISSION PROFILE", selected_preset),
    ("LAUNCH VEHICLE", rocket),
    ("PAYLOAD MASS", f"{mass} kg"),
]

profile_columns = st.columns(3, gap="medium")

for column, (label, value) in zip(profile_columns, profile_metrics):
    with column:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# --------------------------------------------------
# FLIGHT BRIEFING EXPORT
# --------------------------------------------------

flight_briefing = {
    "mission_preset": selected_preset,
    "rocket": rocket,
    "payload_mass_kg": mass,
    "weather": weather,
    "wind_speed_mps": wind_speed,
    "launch_status": launch_status,
    "estimated_risk_percent": risk,
    "max_q_kpa": max_q,
    "prediction_source": "Preliminary rule-based estimates",
    "trajectory_source": "Illustrative generated trajectory",
}

st.markdown(
    '<div class="section-heading">FLIGHT BRIEFING EXPORT</div>',
    unsafe_allow_html=True,
)

json_col, csv_col = st.columns(2, gap="medium")

with json_col:
    st.download_button(
        "⬇ EXPORT JSON BRIEFING",
        data=json.dumps(flight_briefing, indent=4),
        file_name="flight_briefing.json",
        mime="application/json",
        use_container_width=True,
    )

with csv_col:
    st.download_button(
        "⬇ EXPORT CSV BRIEFING",
        data=pd.DataFrame([flight_briefing]).to_csv(index=False),
        file_name="flight_briefing.csv",
        mime="text/csv",
        use_container_width=True,
    )


# --------------------------------------------------
# FLIGHT TELEMETRY ANALYTICS
# --------------------------------------------------

st.markdown(
    '<div class="section-heading">FLIGHT TELEMETRY ANALYTICS</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="helper-text">
        Trajectory visualizations currently use illustrative
        flight paths pending physics integration.
    </div>
    """,
    unsafe_allow_html=True,
)

trajectory = generate_mock_trajectory()


# --------------------------------------------------
# CHART STYLING
# --------------------------------------------------

def style_trajectory_chart(fig):
    fig.update_layout(
        paper_bgcolor="#0c2337",
        plot_bgcolor="#0c2337",
        font=dict(
            color="#d7e9f4",
            size=12,
        ),
        margin=dict(l=20, r=20, t=45, b=20),
    )

    if fig.layout.scene is not None:
        fig.update_layout(
            scene=dict(
                bgcolor="#0c2337",
                xaxis=dict(
                    backgroundcolor="#0c2337",
                    gridcolor="#24435a",
                    color="#b7cfdd",
                ),
                yaxis=dict(
                    backgroundcolor="#0c2337",
                    gridcolor="#24435a",
                    color="#b7cfdd",
                ),
                zaxis=dict(
                    backgroundcolor="#0c2337",
                    gridcolor="#24435a",
                    color="#b7cfdd",
                ),
            )
        )
    else:
        fig.update_xaxes(
            gridcolor="#24435a",
            zerolinecolor="#24435a",
        )

        fig.update_yaxes(
            gridcolor="#24435a",
            zerolinecolor="#24435a",
        )

    return fig


# --------------------------------------------------
# ALTITUDE AND VELOCITY CHARTS
# --------------------------------------------------

altitude_column, speed_column = st.columns(2, gap="large")

with altitude_column:
    st.markdown(
        '<div class="chart-heading">ALTITUDE PROFILE</div>',
        unsafe_allow_html=True,
    )

    altitude_fig = style_trajectory_chart(
        create_altitude_distance_figure(trajectory)
    )

    st.plotly_chart(
        altitude_fig,
        config={"responsive": True},
        key="altitude-distance-chart",
    )

with speed_column:
    st.markdown(
        '<div class="chart-heading">VELOCITY PROFILE</div>',
        unsafe_allow_html=True,
    )

    speed_fig = style_trajectory_chart(
        create_speed_time_figure(trajectory)
    )

    st.plotly_chart(
        speed_fig,
        config={"responsive": True},
        key="speed-time-chart",
    )


# --------------------------------------------------
# 3D FLIGHT PATH TRACKING
# --------------------------------------------------

st.markdown(
    '<div class="section-heading">3D FLIGHT PATH TRACKING</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="chart-heading">TRAJECTORY VISUALIZATION</div>',
    unsafe_allow_html=True,
)

trajectory_fig = style_trajectory_chart(
    create_3d_trajectory_figure(trajectory)
)

st.plotly_chart(
    trajectory_fig,
    config={"responsive": True},
    key="3d-trajectory-chart",
)


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.markdown(
    """
    <div class="mission-footer">
        LIFTOFF MISSION CONTROL / AGGIE DATA SCIENCE CLUB / 2026
        <br>
        ROCKET LAUNCH INTELLIGENCE & TRAJECTORY VISUALIZATION
        <br>
        FLIGHT SYSTEMS / SIMULATION PREVIEW
    </div>
    """,
    unsafe_allow_html=True,
)
