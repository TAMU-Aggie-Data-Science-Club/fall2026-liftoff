"""Plotly figures for mock rocket trajectory data."""

from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go


@dataclass(frozen=True)
class TrajectoryData:
    """Trajectory coordinates and derived speed in SI units."""

    time_s: np.ndarray
    downrange_m: np.ndarray
    crossrange_m: np.ndarray
    altitude_m: np.ndarray
    speed_mps: np.ndarray


def generate_mock_trajectory() -> TrajectoryData:
    """Create deterministic sample data for the trajectory charts."""
    time_s = np.linspace(0, 180, 181)
    progress = time_s / time_s[-1]
    downrange_m = 300_000 * progress**1.15
    crossrange_m = 12_000 * np.sin(np.pi * progress / 2)
    altitude_m = 120_000 * (1 - np.exp(-time_s / 42)) * (1 - 0.08 * progress)

    downrange_speed = np.gradient(downrange_m, time_s)
    crossrange_speed = np.gradient(crossrange_m, time_s)
    altitude_speed = np.gradient(altitude_m, time_s)
    speed_mps = np.sqrt(
        downrange_speed**2 + crossrange_speed**2 + altitude_speed**2
    )

    return TrajectoryData(
        time_s=time_s,
        downrange_m=downrange_m,
        crossrange_m=crossrange_m,
        altitude_m=altitude_m,
        speed_mps=speed_mps,
    )


def create_altitude_distance_figure(trajectory: TrajectoryData) -> go.Figure:
    """Build a 2D altitude-versus-downrange figure."""
    distance_km = np.hypot(
        trajectory.downrange_m, trajectory.crossrange_m
    ) / 1_000
    altitude_km = trajectory.altitude_m / 1_000

    figure = go.Figure(
        go.Scatter(
            x=distance_km,
            y=altitude_km,
            mode="lines",
            name="Trajectory",
            line={"color": "#00a6d6", "width": 3},
            hovertemplate="Distance: %{x:.1f} km<br>Altitude: %{y:.1f} km<extra></extra>",
        )
    )
    figure.update_layout(
        title="Altitude vs. Distance",
        title_x=0.5,
        xaxis_title="Distance from launch site (km)",
        yaxis_title="Altitude (km)",
        height=400,
        autosize=True,
        margin={"l": 55, "r": 20, "t": 65, "b": 55},
    )
    return figure


def create_speed_time_figure(trajectory: TrajectoryData) -> go.Figure:
    """Build a 2D speed-versus-time figure."""
    figure = go.Figure(
        go.Scatter(
            x=trajectory.time_s,
            y=trajectory.speed_mps,
            mode="lines",
            name="Speed",
            line={"color": "#f28e2b", "width": 3},
            hovertemplate="Time: %{x:.1f} s<br>Speed: %{y:.0f} m/s<extra></extra>",
        )
    )
    figure.update_layout(
        title="Speed vs. Time",
        title_x=0.5,
        xaxis_title="Time (s)",
        yaxis_title="Speed (m/s)",
        height=400,
        autosize=True,
        margin={"l": 55, "r": 20, "t": 65, "b": 55},
    )
    return figure


def create_3d_trajectory_figure(trajectory: TrajectoryData) -> go.Figure:
    """Build an interactive 3D trajectory figure."""
    figure = go.Figure(
        go.Scatter3d(
            x=trajectory.downrange_m / 1_000,
            y=trajectory.crossrange_m / 1_000,
            z=trajectory.altitude_m / 1_000,
            mode="lines",
            name="Trajectory",
            line={"color": trajectory.time_s, "colorscale": "Viridis", "width": 6},
            customdata=trajectory.time_s,
            hovertemplate=(
                "Downrange: %{x:.1f} km<br>"
                "Crossrange: %{y:.1f} km<br>"
                "Altitude: %{z:.1f} km<br>"
                "Time: %{customdata:.1f} s<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title="3D Flight Trajectory",
        title_x=0.5,
        scene={
            "xaxis_title": "Downrange (km)",
            "yaxis_title": "Crossrange (km)",
            "zaxis_title": "Altitude (km)",
            "aspectmode": "data",
        },
        height=600,
        autosize=True,
        margin={"l": 20, "r": 20, "t": 65, "b": 20},
    )
    return figure
