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
st.markdown(
    """
    <style>
    :root {
        --space-ink: #070b17;
        --space-panel: rgba(18, 27, 47, 0.68);
        --space-border: rgba(154, 178, 221, 0.18);
        --space-text: #e6eeff;
        --space-muted: #9cacc9;
        --space-cyan: #37d7ff;
        --space-violet: #9b8cff;
    }

    .stApp,
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse at 12% 0%, rgba(52, 77, 151, 0.22), transparent 40%),
            radial-gradient(ellipse at 88% 18%, rgba(113, 63, 168, 0.16), transparent 34%),
            var(--space-ink);
        color: var(--space-text);
    }

    [data-testid="stHeader"] {
        background: rgba(7, 11, 23, 0.55);
    }

    [data-testid="stMainBlockContainer"] {
        padding-top: 2.5rem;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(20, 30, 53, 0.96), rgba(9, 14, 29, 0.96));
        border-right: 1px solid var(--space-border);
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(215, 229, 255, 0.075);
        border: 1px solid rgba(220, 235, 255, 0.22);
        border-radius: 20px;
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.26),
            inset 0 1px 0 rgba(255, 255, 255, 0.24),
            inset 0 -1px 0 rgba(255, 255, 255, 0.08),
            inset 0 0 28px rgba(114, 167, 255, 0.07);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }

    [data-testid="stMetric"] {
        background: rgba(215, 229, 255, 0.055);
        border: 1px solid rgba(220, 235, 255, 0.18);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.2),
            inset 0 -1px 0 rgba(255, 255, 255, 0.06),
            inset 0 0 24px rgba(114, 167, 255, 0.06);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
    }

    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stMetric"] {
        position: relative;
        isolation: isolate;
        transition:
            transform 180ms ease,
            border-color 180ms ease,
            box-shadow 180ms ease;
    }

    [data-testid="stVerticalBlockBorderWrapper"]::before,
    [data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        inset: 0 0 auto;
        height: 1px;
        border-radius: inherit;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.78),
            transparent
        );
        pointer-events: none;
        z-index: 2;
    }

    [data-testid="stVerticalBlockBorderWrapper"]::after,
    [data-testid="stMetric"]::after {
        content: "";
        position: absolute;
        inset: 0;
        border-radius: inherit;
        background:
            radial-gradient(
                260px circle at var(--pointer-x, 50%) var(--pointer-y, 50%),
                rgba(87, 211, 255, 0.24),
                rgba(155, 140, 255, 0.1) 38%,
                transparent 72%
            ),
            linear-gradient(
                180deg,
                rgba(255, 255, 255, 0.16),
                transparent 30%,
                rgba(255, 255, 255, 0.04)
            );
        background-size: 100% 100%, 1px 100%;
        background-position: center, left;
        background-repeat: no-repeat;
        opacity: 0;
        transition: opacity 180ms ease;
        pointer-events: none;
        z-index: 0;
    }

    [data-testid="stVerticalBlockBorderWrapper"]:hover,
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: rgba(148, 222, 255, 0.42);
        box-shadow:
            0 12px 38px rgba(0, 0, 0, 0.3),
            0 0 24px rgba(55, 215, 255, 0.1),
            inset 0 1px 0 rgba(255, 255, 255, 0.3),
            inset 0 -1px 0 rgba(255, 255, 255, 0.1),
            inset 0 0 32px rgba(114, 167, 255, 0.1);
    }

    [data-testid="stVerticalBlockBorderWrapper"]:hover::after,
    [data-testid="stMetric"]:hover::after {
        opacity: 0.8;
    }

    [data-testid="stVerticalBlockBorderWrapper"] > div,
    [data-testid="stMetric"] > div {
        position: relative;
        z-index: 1;
    }

    [data-testid="stMetricLabel"],
    [data-testid="stCaptionContainer"] {
        color: var(--space-muted);
    }

    [data-testid="stMetricValue"] {
        color: var(--space-text);
    }

    [data-testid="stTabs"] [role="tablist"] {
        gap: 0.5rem;
        border-bottom: 1px solid var(--space-border);
    }

    [data-testid="stTabs"] button[role="tab"] {
        color: var(--space-muted);
    }

    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: var(--space-cyan);
        border-bottom-color: var(--space-cyan);
    }

    [data-testid="stPlotlyChart"] {
        border-radius: 14px;
        overflow: hidden;
    }

    .stButton > button {
        color: #07101f;
        font-weight: 700;
        background: linear-gradient(110deg, var(--space-cyan), var(--space-violet));
        border: 0;
        border-radius: 10px;
        transition: filter 150ms ease, transform 150ms ease;
    }

    .stButton > button:hover {
        color: #07101f;
        filter: brightness(1.12);
        transform: translateY(-1px);
    }

    h1, h2, h3 {
        letter-spacing: 0.02em;
    }

    h1 {
        text-shadow: 0 0 28px rgba(55, 215, 255, 0.2);
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.html(
    """
    <script>
    (() => {
        if (window.__liftoffGlassPointerTracking) return;
        window.__liftoffGlassPointerTracking = true;

        const cardSelector =
            '[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stMetric"]';

        document.addEventListener("pointermove", (event) => {
            const card = event.target instanceof Element
                ? event.target.closest(cardSelector)
                : null;

            if (!card) return;

            const bounds = card.getBoundingClientRect();
            const x = ((event.clientX - bounds.left) / bounds.width) * 100;
            const y = ((event.clientY - bounds.top) / bounds.height) * 100;
            card.style.setProperty("--pointer-x", `${x}%`);
            card.style.setProperty("--pointer-y", `${y}%`);
        }, { passive: true });
    })();
    </script>
    """,
    unsafe_allow_javascript=True,
)
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