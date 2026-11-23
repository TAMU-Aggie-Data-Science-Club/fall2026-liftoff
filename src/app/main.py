
import json
import math
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
# ICON SYSTEM
# ============================================================

ICONS = {
    "rocket": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.69-2.13-.09-2.91a2 2 0 0 0-2.91-.09Z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6.05 11A22 22 0 0 1 12 15Z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><circle cx="15" cy="9" r="1"/>',
    "alert": '<path d="m10.29 3.86-8.82 15.3A2 2 0 0 0 3.2 22h17.6a2 2 0 0 0 1.73-2.84l-8.82-15.3a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "wind": '<path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8A2.5 2.5 0 1 1 20 10.5H2"/><path d="M9.8 4.4A2 2 0 1 1 11 8H2"/>',
    "layers": '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
    "box": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "mountain": '<path d="m8 3 4 8 3-3 7 13H2L8 3Z"/>',
    "gauge": '<path d="M12 14l4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/><path d="M12 2v2"/><path d="m4.93 4.93 1.42 1.42"/><path d="M2 12h2"/><path d="m19.07 4.93-1.42 1.42"/><path d="M20 12h2"/>',
    "pin": '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
}


def icon(name, size=28):
    return (
        f'<svg width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'{ICONS[name]}</svg>'
    )


# ============================================================
# DESIGN SYSTEM
# ============================================================

st.markdown(
    """
<style>
:root {
    --bg: #031321;
    --panel: #08253a;
    --panel2: #0c3048;
    --cyan: #40e9f7;
    --cyan2: #00cfff;
    --white: #eaf8ff;
    --muted: #a6c6d7;
    --green: #3af5ac;
}

html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: #031321 !important;
    color: var(--white) !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
    height: 1.5rem !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 0.7rem !important;
    padding-bottom: 2rem !important;
    max-width: 1900px !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#061f32,#041827) !important;
    border-right: 1px solid #087da3;
}

[data-testid="stSidebar"] * {
    color: #eaf8ff;
}

[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #0c2b43 !important;
    border: 1px solid #23617e !important;
    border-radius: 11px !important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background: #10344e !important;
    border-radius: 9px;
}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #102e46 !important;
    color: white !important;
    border-color: #4a8aab !important;
}

[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
    background: #123b55 !important;
    color: white !important;
}

h1,h2,h3,h4,p {
    color: #eaf8ff;
}

.mission-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 18px;
}

.mission-eyebrow {
    color: #b3cddd;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1.4px;
}

.mission-title {
    color: #43e5f5;
    font-size: clamp(30px,3vw,48px);
    font-weight: 950;
    line-height: 1.2;
    letter-spacing: .6px;
    text-shadow: 0 0 22px rgba(0,210,255,.16);
}

.mission-subtitle {
    color: #aac7d9;
    font-size: 13px;
    margin-top: 4px;
}

.system-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

.system-tag {
    padding: 13px 17px;
    border: 1px solid #00c9ed;
    border-radius: 9px;
    color: #44e7f5;
    background: linear-gradient(135deg,#073148,#041c30);
    font-size: 12px;
    font-weight: 850;
    box-shadow: inset 0 0 15px rgba(0,200,255,.08);
}

.online-dot {
    display: inline-block;
    height: 10px;
    width: 10px;
    border-radius: 50%;
    background: #30f8a4;
    box-shadow: 0 0 12px #30f8a4;
    margin-right: 7px;
}

.metric-card {
    position: relative;
    display: flex;
    align-items: center;
    gap: 17px;
    padding: 19px;
    min-height: 124px;
    background: linear-gradient(135deg,#0a2b42,#041929);
    border: 1px solid #00c5ed;
    border-radius: 13px;
    box-shadow:
        inset 0 0 20px rgba(0,190,255,.04),
        0 0 15px rgba(0,195,255,.10);
    overflow: hidden;
}

.metric-card:before,
.dashboard-panel:before {
    content: "";
    position: absolute;
    top: 0;
    left: 12%;
    width: 22%;
    height: 2px;
    background: #5befff;
    box-shadow: 0 0 12px #28dfff;
}

.metric-icon {
    flex-shrink: 0;
    color: #43e9fa;
    background: linear-gradient(145deg,#0b3b55,#06283c);
    padding: 13px;
    border-radius: 11px;
    filter: drop-shadow(0 0 7px rgba(0,220,255,.35));
}

.metric-label {
    color: #c6dce8;
    font-size: 11px;
    font-weight: 850;
    letter-spacing: .5px;
}

.metric-value {
    color: #45e7f5;
    font-size: clamp(20px,2vw,33px);
    font-weight: 950;
    margin-top: 6px;
    white-space: nowrap;
}

.status-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    padding: 17px 21px;
    margin: 16px 0 22px;
    border-radius: 12px;
    font-weight: 850;
    font-size: 13px;
}

.status-go {
    background: linear-gradient(90deg,#064538,#05312e);
    border: 1px solid #00df94;
    color: #51ffc1;
    box-shadow: inset 0 0 20px rgba(0,255,150,.05);
}

.status-nogo {
    background: #3c1527;
    border: 1px solid #ff587e;
    color: #ff9cb3;
}

.status-note {
    color: #bce6e6;
    font-size: 11px;
    font-weight: 500;
}

.dashboard-panel {
    position: relative;
    min-height: 365px;
    padding: 18px;
    border: 1px solid #00c5ed;
    border-radius: 13px;
    background: linear-gradient(145deg,#092b42,#041827);
    box-shadow: inset 0 0 22px rgba(0,200,255,.04);
}

.panel-heading {
    color: #43e9fa;
    font-size: 16px;
    font-weight: 900;
    margin-bottom: 12px;
}

.info-row,
.telemetry-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 19px 0;
    border-top: 1px solid #1a526b;
}

.info-icon {
    color: #48e9f9;
    width: 38px;
    flex-shrink: 0;
    filter: drop-shadow(0 0 6px rgba(0,210,255,.25));
}

.info-label {
    color: #c2d8e5;
    font-size: 12px;
}

.info-value {
    color: #5de9f7;
    font-size: 17px;
    font-weight: 850;
    margin-top: 4px;
    overflow-wrap: anywhere;
}

.telemetry-row {
    justify-content: space-between;
}

.telemetry-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
}

.sparkline {
    width: 78px;
    min-width: 48px;
    height: 29px;
}

.section-title {
    color: #47e7f7;
    font-size: 16px;
    font-weight: 900;
    margin: 22px 0 10px;
}

.graph-label {
    color: #43e7f6;
    font-size: 14px;
    font-weight: 900;
    margin-bottom: 8px;
}

.graph-note {
    color: #9dbfd2;
    font-size: 12px;
    margin-bottom: 10px;
}

[data-testid="stPlotlyChart"] {
    border: 1px solid #00a8d3;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 0 15px rgba(0,180,255,.06);
}

.stDownloadButton > button {
    width: 100%;
    background: linear-gradient(135deg,#0b3b55,#09283c) !important;
    border: 1px solid #00c5ed !important;
    color: #eaf8ff !important;
    border-radius: 9px !important;
    font-weight: 800 !important;
}

.stDownloadButton > button:hover {
    border-color: #68f0ff !important;
    box-shadow: 0 0 18px rgba(0,220,255,.20);
}

.footer {
    text-align: center;
    color: #8db2c7;
    font-size: 11px;
    letter-spacing: 1px;
    border-top: 1px solid #22516b;
    padding: 22px;
    margin-top: 28px;
}

@media(max-width:900px) {
    .metric-card {
        min-height: 105px;
        padding: 12px;
    }
    .metric-icon {
        padding: 8px;
    }
    .dashboard-panel {
        min-height: auto;
    }
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
    "mission_preset": "Custom Mission",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def apply_preset():
    selected = st.session_state["mission_preset"]
    if selected in preset_values:
        for key, value in preset_values[selected].items():
            st.session_state[key] = value


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🚀 MISSION SETTINGS")

    selected_preset = st.selectbox(
        "Mission Preset",
        presets,
        key="mission_preset",
        on_change=apply_preset,
    )

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
            step=0.1,
            format="%.2f",
            key="wind_speed",
        )

    st.markdown(
        """
        <div style="
            border-top:1px solid #23516a;
            margin-top:35px;
            padding-top:20px;
            color:#a8c6d8;
            font-size:13px;
            line-height:2.1;
        ">
            LIFTOFF / FALL 2026<br>
            Mission Control System<br>
            Simulation preview active
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# READINESS ESTIMATES
# ============================================================

# Illustrative rules until real ML and physics integration.

if weather in ("High Winds", "Storm") or wind_speed >= 17.88:
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
# COMPONENT HELPERS
# ============================================================

def metric_card(label, value, icon_name):
    return f"""
    <div class="metric-card">
        <div class="metric-icon">{icon(icon_name, 34)}</div>
        <div>
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
    </div>
    """


def info_row(icon_name, label, value):
    return f"""
    <div class="info-row">
        <div class="info-icon">{icon(icon_name, 30)}</div>
        <div>
            <div class="info-label">{label}</div>
            <div class="info-value">{value}</div>
        </div>
    </div>
    """


def sparkline():
    return """
    <svg class="sparkline" viewBox="0 0 90 30">
      <path
        d="M1 25 C12 20 19 21 29 17
           S44 19 54 12 S72 11 89 3"
        stroke="#40e9f7"
        stroke-width="2"
        fill="none"
      />
    </svg>
    """


def telemetry_row(icon_name, label, value):
    return f"""
    <div class="telemetry-row">
        <div class="telemetry-left">
            <div class="info-icon">{icon(icon_name, 30)}</div>
            <div>
                <div class="info-label">{label}</div>
                <div class="info-value">{value}</div>
            </div>
        </div>
        {sparkline()}
    </div>
    """


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="mission-header">
  <div>
    <div class="mission-eyebrow">
      AGGIE DATA SCIENCE CLUB / FALL 2026 / FLIGHT SYSTEMS
    </div>
    <div class="mission-title">
      LIFTOFF MISSION CONTROL
    </div>
    <div class="mission-subtitle">
      Rocket Launch Intelligence • Flight Readiness • Trajectory Analytics
    </div>
  </div>
  <div class="system-tags">
    <div class="system-tag">
      <span class="online-dot"></span>MISSION SYSTEMS ONLINE
    </div>
    <div class="system-tag">
      ◈ &nbsp; SIMULATION MODE
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# FLIGHT READINESS
# ============================================================

metric_columns = st.columns(4, gap="medium")

metrics = [
    ("LAUNCH STATUS", launch_status, "rocket"),
    ("DELAY / FAILURE RISK", f"{risk}%", "alert"),
    ("MAX DYNAMIC PRESSURE", f"{max_q:.1f} kPa", "wind"),
    ("SURFACE WIND", f"{wind_speed:.2f} m/s", "wind"),
]

for column, (label, value, icon_name) in zip(metric_columns, metrics):
    with column:
        st.markdown(
            metric_card(label, value, icon_name),
            unsafe_allow_html=True,
        )

if launch_status == "GO":
    banner_class = "status-go"
    banner_text = "GO — CONDITIONS MEET SIMULATED LAUNCH CRITERIA"
else:
    banner_class = "status-nogo"
    banner_text = "NO-GO — CONDITIONS EXCEED SIMULATED LAUNCH CRITERIA"

st.markdown(
    f"""
    <div class="status-banner {banner_class}">
        <span>● &nbsp;{banner_text}</span>
        <span class="status-note">
            Readiness and risk are preliminary estimates pending model integration.
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ROTATING DIGITAL EARTH
# ============================================================

# Animated illustrative globe, not live orbital tracking.
# Browser-side Canvas keeps the animation smooth.


EARTH_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<style>
* {
    box-sizing: border-box;
}

html, body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: #020c19;
    font-family: Arial, sans-serif;
}

.wrapper {
    position: relative;
    height: 365px;
    overflow: hidden;
    border: 1px solid #00cfff;
    border-radius: 13px;
    background:
        radial-gradient(
            ellipse at 50% 50%,
            #0a3152 0%,
            #041a31 45%,
            #010916 100%
        );
    box-shadow:
        inset 0 0 35px rgba(0, 195, 255, 0.12),
        0 0 18px rgba(0, 195, 255, 0.14);
}

.heading {
    position: absolute;
    top: 14px;
    left: 0;
    right: 0;
    z-index: 10;
    text-align: center;
    font-size: 16px;
    font-weight: 900;
    letter-spacing: 1.2px;
    color: #55edff;
    text-shadow:
        0 0 8px #00cfff,
        0 0 20px rgba(0, 220, 255, 0.45);
    pointer-events: none;
}

canvas {
    display: block;
    width: 100%;
    height: 100%;
}
</style>
</head>

<body>
<div class="wrapper">
    <div class="heading">3D FLIGHT TRAJECTORY</div>
    <canvas id="earth"></canvas>
</div>

<script>
const canvas = document.getElementById("earth");
const ctx = canvas.getContext("2d");
const wrapper = document.querySelector(".wrapper");

let W = 0;
let H = 0;
let tick = 0;

function resize() {
    const rect = wrapper.getBoundingClientRect();
    W = rect.width;
    H = rect.height;

    const dpr = Math.min(
        window.devicePixelRatio || 1,
        2
    );

    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

window.addEventListener("resize", resize);
resize();

function random(seed) {
    let x = Math.sin(seed * 127.1 + 78.233) * 43758.5453;
    return x - Math.floor(x);
}

const continents = [
    [
        [-168,65],[-150,70],[-135,60],[-125,50],
        [-123,40],[-115,32],[-105,30],[-97,25],
        [-90,19],[-82,25],[-80,33],[-70,45],
        [-60,52],[-80,60],[-100,72],[-130,72]
    ],
    [
        [-81,12],[-70,8],[-60,10],[-50,3],
        [-48,-10],[-40,-20],[-47,-30],
        [-55,-40],[-70,-55],[-76,-35],[-80,-10]
    ],
    [
        [-12,36],[-10,55],[0,60],[20,70],
        [40,65],[65,70],[90,75],[120,60],
        [150,60],[170,50],[150,35],[135,25],
        [115,15],[100,5],[80,10],[60,25],
        [45,30],[30,40],[10,35]
    ],
    [
        [-17,35],[5,37],[30,32],[42,12],
        [50,-10],[35,-25],[20,-35],
        [10,-35],[-5,-20],[-15,0]
    ],
    [
        [112,-12],[130,-10],[153,-20],
        [150,-38],[130,-43],[113,-27]
    ],
    [
        [-55,60],[-42,60],[-38,75],
        [-50,83],[-60,80],[-62,68]
    ]
];

function insidePolygon(x, y, polygon) {
    let inside = false;

    for (
        let i = 0, j = polygon.length - 1;
        i < polygon.length;
        j = i++
    ) {
        const xi = polygon[i][0];
        const yi = polygon[i][1];
        const xj = polygon[j][0];
        const yj = polygon[j][1];

        if (
            ((yi > y) !== (yj > y)) &&
            (x < (xj - xi) * (y - yi) /
                ((yj - yi) || 0.00001) + xi)
        ) {
            inside = !inside;
        }
    }

    return inside;
}

function isLand(lon, lat) {
    return continents.some(poly =>
        insidePolygon(lon, lat, poly)
    );
}

const landPoints = [];

for (let lat = -85; lat <= 85; lat += 2.2) {
    for (let lon = -180; lon < 180; lon += 2.2) {
        if (isLand(lon, lat)) {
            landPoints.push([
                lat,
                lon,
                random(lat * 500 + lon)
            ]);
        }
    }
}

const stars = Array.from({length: 190}, (_, i) => ({
    x: random(i + 10),
    y: random(i + 300),
    size: random(i + 600) * 1.3 + .3,
    phase: i * 1.27
}));

const networkNodes = Array.from({length: 52}, (_, i) => ({
    lat: -65 + random(i + 900) * 130,
    lon: -180 + random(i + 1200) * 360,
    phase: i * .73
}));

function project(lat, lon, rotation, cx, cy, r) {
    const phi = lat * Math.PI / 180;
    const lam = (lon + rotation) * Math.PI / 180;

    const depth = Math.cos(phi) * Math.cos(lam);

    return {
        x: cx + r * Math.cos(phi) * Math.sin(lam),
        y: cy - r * Math.sin(phi),
        depth: depth,
        visible: depth > 0
    };
}

function glowDot(x, y, radius, color, blur) {
    ctx.save();
    ctx.shadowColor = color;
    ctx.shadowBlur = blur;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
}

function drawStars() {
    for (const star of stars) {
        const alpha = .15 + .4 *
            Math.abs(
                Math.sin(tick * .012 + star.phase)
            );

        ctx.fillStyle =
            `rgba(125,220,255,${alpha})`;

        ctx.fillRect(
            star.x * W,
            star.y * H,
            star.size,
            star.size
        );
    }
}

function drawGlobe(cx, cy, r, rotation) {
    // Wide atmospheric bloom.
    const halo = ctx.createRadialGradient(
        cx, cy, r * .6,
        cx, cy, r * 1.65
    );

    halo.addColorStop(0, "rgba(0,210,255,.11)");
    halo.addColorStop(.55, "rgba(0,170,255,.18)");
    halo.addColorStop(1, "rgba(0,140,255,0)");

    ctx.beginPath();
    ctx.arc(cx, cy, r * 1.65, 0, Math.PI * 2);
    ctx.fillStyle = halo;
    ctx.fill();

    // Richer ocean colors.
    const ocean = ctx.createRadialGradient(
        cx-r*.36,
        cy-r*.32,
        r*.06,
        cx,
        cy,
        r
    );

    ocean.addColorStop(0, "#117ba6");
    ocean.addColorStop(.28, "#07547f");
    ocean.addColorStop(.62, "#032e54");
    ocean.addColorStop(.86, "#01182f");
    ocean.addColorStop(1, "#000916");

    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = ocean;
    ctx.fill();

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    // Subtle luminous latitude grid.
    for (let lat = -75; lat <= 75; lat += 15) {
        ctx.beginPath();
        let active = false;

        for (let lon = -180; lon <= 180; lon += 3) {
            const p = project(
                lat, lon, rotation, cx, cy, r
            );

            if (p.visible) {
                if (!active) ctx.moveTo(p.x, p.y);
                else ctx.lineTo(p.x, p.y);
                active = true;
            } else {
                active = false;
            }
        }

        ctx.strokeStyle = "rgba(75,221,255,.16)";
        ctx.lineWidth = .7;
        ctx.stroke();
    }

    // Longitude grid.
    for (let lon = -180; lon < 180; lon += 15) {
        ctx.beginPath();
        let active = false;

        for (let lat = -90; lat <= 90; lat += 3) {
            const p = project(
                lat, lon, rotation, cx, cy, r
            );

            if (p.visible) {
                if (!active) ctx.moveTo(p.x, p.y);
                else ctx.lineTo(p.x, p.y);
                active = true;
            } else {
                active = false;
            }
        }

        ctx.strokeStyle = "rgba(75,221,255,.12)";
        ctx.lineWidth = .65;
        ctx.stroke();
    }

    // Detailed digital continents.
    for (const [lat, lon, seed] of landPoints) {
        const p = project(
            lat, lon, rotation, cx, cy, r
        );

        if (!p.visible) continue;

        const pulse = .8 + .2 *
            Math.sin(tick * .025 + seed * 10);

        const brightness =
            (.42 + p.depth * .58) * pulse;

        ctx.fillStyle =
            `rgba(80,237,255,${brightness})`;

        const size = .65 + p.depth * 1.1;

        ctx.fillRect(
            p.x,
            p.y,
            size,
            size
        );
    }

    // Digital connection network.
    const visibleNodes = networkNodes
        .map(node => ({
            ...node,
            p: project(
                node.lat,
                node.lon,
                rotation,
                cx,
                cy,
                r
            )
        }))
        .filter(node => node.p.visible);

    for (let i = 0; i < visibleNodes.length; i++) {
        const a = visibleNodes[i];

        for (
            let j = i + 1;
            j < visibleNodes.length;
            j++
        ) {
            const b = visibleNodes[j];

            const distance = Math.hypot(
                a.p.x - b.p.x,
                a.p.y - b.p.y
            );

            if (distance < r * .58) {
                ctx.beginPath();
                ctx.moveTo(a.p.x, a.p.y);
                ctx.lineTo(b.p.x, b.p.y);

                ctx.strokeStyle =
                    "rgba(45,215,255,.20)";

                ctx.lineWidth = .7;
                ctx.stroke();
            }
        }

        const pulse = 1.5 + 1.5 *
            Math.abs(
                Math.sin(tick*.03+a.phase)
            );

        glowDot(
            a.p.x,
            a.p.y,
            pulse,
            "#8ffaff",
            13
        );
    }

    // Night-side shadow.
    const shadow = ctx.createLinearGradient(
        cx-r, cy,
        cx+r, cy
    );

    shadow.addColorStop(0, "rgba(0,0,15,0)");
    shadow.addColorStop(.52, "rgba(0,0,15,.02)");
    shadow.addColorStop(1, "rgba(0,0,15,.67)");

    ctx.fillStyle = shadow;
    ctx.fillRect(cx-r, cy-r, r*2, r*2);

    ctx.restore();

    // Multiple atmospheric rings.
    for (let i = 0; i < 3; i++) {
        ctx.save();

        ctx.beginPath();
        ctx.arc(
            cx,
            cy,
            r + i * 2,
            0,
            Math.PI * 2
        );

        ctx.strokeStyle =
            `rgba(42,218,255,${.85-i*.24})`;

        ctx.lineWidth = i === 0 ? 2 : 1;
        ctx.shadowColor = "#00cfff";
        ctx.shadowBlur = 12 + i*5;
        ctx.stroke();

        ctx.restore();
    }

    // Illuminated edge highlight.
    ctx.beginPath();
    ctx.arc(
        cx,
        cy,
        r,
        Math.PI * 1.05,
        Math.PI * 1.8
    );

    ctx.strokeStyle = "#a6faff";
    ctx.lineWidth = 2.3;
    ctx.shadowColor = "#00eaff";
    ctx.shadowBlur = 22;
    ctx.stroke();
    ctx.shadowBlur = 0;
}

function drawOrbit(cx, cy, r, phase, tilt, alpha) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(tilt);

    ctx.beginPath();
    ctx.ellipse(
        0, 0,
        r*1.42,
        r*.44,
        0,
        0,
        Math.PI*2
    );

    ctx.strokeStyle =
        `rgba(35,224,255,${alpha})`;

    ctx.lineWidth = 1.2;
    ctx.shadowColor = "#00dfff";
    ctx.shadowBlur = 12;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Moving satellite.
    const angle = tick*.008 + phase;

    const x = Math.cos(angle)*r*1.42;
    const y = Math.sin(angle)*r*.44;

    glowDot(x, y, 3.7, "#baffff", 20);

    // Satellite tracking crosshair.
    ctx.strokeStyle = "rgba(100,240,255,.75)";
    ctx.lineWidth = 1;

    ctx.beginPath();
    ctx.moveTo(x-9,y);
    ctx.lineTo(x-5,y);
    ctx.moveTo(x+5,y);
    ctx.lineTo(x+9,y);
    ctx.moveTo(x,y-9);
    ctx.lineTo(x,y-5);
    ctx.moveTo(x,y+5);
    ctx.lineTo(x,y+9);
    ctx.stroke();

    ctx.restore();
}

function drawScanLine(cx, cy, r) {
    const angle = tick * .008;

    const gradient = ctx.createConicGradient(
        angle,
        cx,
        cy
    );

    gradient.addColorStop(
        0,
        "rgba(0,230,255,.0)"
    );

    gradient.addColorStop(
        .08,
        "rgba(0,230,255,.10)"
    );

    gradient.addColorStop(
        .13,
        "rgba(0,230,255,0)"
    );

    gradient.addColorStop(
        1,
        "rgba(0,230,255,0)"
    );

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx,cy,r,0,Math.PI*2);
    ctx.clip();

    ctx.fillStyle = gradient;
    ctx.fillRect(
        cx-r,
        cy-r,
        r*2,
        r*2
    );

    ctx.restore();
}

function animate() {
    ctx.clearRect(0,0,W,H);

    const cx = W/2;
    const cy = H*.56;
    const r = Math.min(
        W*.30,
        H*.39
    );

    const rotation = tick*.07;

    drawStars();
    drawGlobe(cx,cy,r,rotation);
    drawScanLine(cx,cy,r);

    drawOrbit(
        cx,cy,r,
        0,-.27,.90
    );

    drawOrbit(
        cx,cy,r,
        2.1,.55,.45
    );

    drawOrbit(
        cx,cy,r,
        4.2,-.95,.28
    );

    tick++;
    requestAnimationFrame(animate);
}

animate();
</script>
</body>
</html>
"""



# ============================================================
# MAIN DASHBOARD
# ============================================================

left, center, right = st.columns(
    [1.15, 2.0, 1.15],
    gap="small",
)

with left:
    profile_html = f"""
    <div class="dashboard-panel">
        <div class="panel-heading">
            ACTIVE MISSION PROFILE
        </div>
        {info_row("rocket", "Mission Profile", selected_preset)}
        {info_row("layers", "Launch Vehicle", rocket)}
        {info_row("box", "Payload Mass", f"{mass} kg")}
    </div>
    """
    st.markdown(profile_html, unsafe_allow_html=True)

with center:
    components.html(
        EARTH_HTML,
        height=370,
        scrolling=False,
    )

with right:
    # Placeholder telemetry, pending physics integration.
    telemetry_html = f"""
    <div class="dashboard-panel">
        <div class="panel-heading">
            FLIGHT TELEMETRY
        </div>
        {telemetry_row("mountain", "Altitude / Illustrative", "110.0 km")}
        {telemetry_row("gauge", "Speed / Illustrative", "2,900 m/s")}
        {telemetry_row("pin", "Downrange / Illustrative", "300 km")}
    </div>
    """
    st.markdown(telemetry_html, unsafe_allow_html=True)


# ============================================================
# GRAPH STYLING
# ============================================================

trajectory = generate_mock_trajectory()


def style_plotly(fig, is_3d=False):
    fig.update_layout(
        paper_bgcolor="#061d30",
        plot_bgcolor="#061d30",
        font=dict(color="#c6e2f0", size=12),
        title_font=dict(color="#e9f9ff", size=14),
        margin=dict(l=20, r=20, t=50, b=30),
    )

    if is_3d:
        fig.update_layout(
            scene=dict(
                bgcolor="#061d30",
                xaxis=dict(
                    backgroundcolor="#061d30",
                    gridcolor="#1c4c67",
                    color="#a6cadc",
                ),
                yaxis=dict(
                    backgroundcolor="#061d30",
                    gridcolor="#1c4c67",
                    color="#a6cadc",
                ),
                zaxis=dict(
                    backgroundcolor="#061d30",
                    gridcolor="#1c4c67",
                    color="#a6cadc",
                ),
            )
        )
    else:
        fig.update_xaxes(
            gridcolor="#1d4964",
            zerolinecolor="#1d4964",
            color="#a6cadc",
        )
        fig.update_yaxes(
            gridcolor="#1d4964",
            zerolinecolor="#1d4964",
            color="#a6cadc",
        )

    return fig


altitude_fig = style_plotly(
    create_altitude_distance_figure(trajectory)
)

speed_fig = style_plotly(
    create_speed_time_figure(trajectory)
)

trajectory_fig = style_plotly(
    create_3d_trajectory_figure(trajectory),
    is_3d=True,
)

# ============================================================
# FLIGHT ANALYTICS
# ============================================================

st.markdown(
    '<div class="section-title">FLIGHT TELEMETRY ANALYTICS</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="graph-note">'
    'Illustrative flight profiles; physics integration pending.'
    '</div>',
    unsafe_allow_html=True,
)

altitude_col, speed_col = st.columns(2, gap="medium")

plot_config = {
    "responsive": True,
    "displaylogo": False,
}

with altitude_col:
    st.markdown(
        '<div class="graph-label">ALTITUDE PROFILE</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        altitude_fig,
        config=plot_config,
        key="altitude-distance-chart",
    )

with speed_col:
    st.markdown(
        '<div class="graph-label">VELOCITY PROFILE</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        speed_fig,
        config=plot_config,
        key="speed-time-chart",
    )

st.markdown(
    '<div class="section-title">3D FLIGHT PATH ANALYSIS</div>',
    unsafe_allow_html=True,
)

st.plotly_chart(
    trajectory_fig,
    config=plot_config,
    key="3d-trajectory-chart",
)


# ============================================================
# FLIGHT BRIEFING EXPORTS
# ============================================================

st.markdown(
    '<div class="section-title">FLIGHT BRIEFING EXPORT</div>',
    unsafe_allow_html=True,
)

flight_briefing = {
    "mission_preset": selected_preset,
    "rocket": rocket,
    "payload_mass_kg": mass,
    "weather": weather,
    "wind_speed_mps": wind_speed,
    "launch_status": launch_status,
    "estimated_risk_percent": risk,
    "max_q_kpa": max_q,
    "data_source": "Illustrative estimates; model integration pending",
}

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


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        LIFTOFF MISSION CONTROL / AGGIE DATA SCIENCE CLUB / 2026
        <br>
        ROCKET LAUNCH INTELLIGENCE & TRAJECTORY VISUALIZATION
        <br>
        FLIGHT SYSTEMS / SIMULATION PREVIEW
    </div>
    """,
    unsafe_allow_html=True,
)
