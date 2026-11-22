"""
Sample-value checks for src/physics/trajectory.py.

Run from the repo root, either way:
    python -m tests.test_trajectory  (no pytest needed)
    python -m pytest tests/          (if pytest is installed)
"""

import numpy as np

from src.physics.constants import G0
from src.physics.trajectory import FALCON9, OUTPUT_COLUMNS, simulate_trajectory

PAYLOAD = 10_000.0  # kg


def expect_value_error(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ---- output format ----
def test_columns_and_time_grid():
    df = simulate_trajectory(PAYLOAD, 0.0)
    assert list(df.columns) == OUTPUT_COLUMNS
    assert len(df) == 501  # t = 0, 1, ..., 500 s
    assert np.allclose(np.diff(df["time_sec"]), 1.0)
    assert not df.isna().any().any()


def test_starts_at_rest_on_the_pad():
    first = simulate_trajectory(PAYLOAD, 0.0).iloc[0]
    assert first["time_sec"] == 0.0
    assert first["altitude_km"] == 0.0
    assert first["downrange_km"] == 0.0
    assert first["velocity_mps"] == 0.0


def test_dt_and_t_end():
    df = simulate_trajectory(PAYLOAD, 0.0, t_end=60.0, dt=0.5)
    assert len(df) == 121
    assert df["time_sec"].iloc[-1] == 60.0


# ---- physics sanity ----
def test_climbs_and_moves_downrange_while_burning():
    df = simulate_trajectory(PAYLOAD, 0.0, t_end=120.0)
    assert np.all(np.diff(df["altitude_km"]) > 0)
    assert np.all(np.diff(df["velocity_mps"]) > 0)
    assert df["downrange_km"].iloc[-1] > 0


def test_burnout_time_matches_propellant_over_mass_flow():
    events = simulate_trajectory(PAYLOAD, 0.0).attrs["events"]
    m_dot = FALCON9["thrust_vac"] / (G0 * FALCON9["isp_vac"])
    assert np.isclose(events["burnout_time_s"], FALCON9["stage1_prop_mass"] / m_dot)


def test_speed_drops_after_burnout():
    df = simulate_trajectory(PAYLOAD, 0.0)
    burnout = df.attrs["events"]["burnout_time_s"]
    after = df[df["time_sec"] > burnout]
    assert after["velocity_mps"].iloc[5] < after["velocity_mps"].iloc[0]


def test_vertical_launch_matches_hand_calculation():
    # No kick, no drag (cd = 0): a = T/m - g with T and m known, so check the first
    # second against v = a0 * t using the pad values (mass barely changes in 1 s).
    vehicle = {**FALCON9, "cd": 0.0}
    df = simulate_trajectory(PAYLOAD, 0.0, vehicle=vehicle, kick_angle_deg=0.0, t_end=1.0)
    m0 = (FALCON9["stage1_dry_mass"] + FALCON9["stage1_prop_mass"]
          + FALCON9["upper_stage_mass"] + PAYLOAD)
    a0 = FALCON9["thrust_sl"] / m0 - G0
    assert np.isclose(df["velocity_mps"].iloc[-1], a0, rtol=0.01)
    assert abs(df["downrange_km"].iloc[-1]) < 1e-9


def test_heavier_payload_is_slower():
    light = simulate_trajectory(1_000.0, 0.0, t_end=140.0)
    heavy = simulate_trajectory(20_000.0, 0.0, t_end=140.0)
    assert heavy["velocity_mps"].iloc[-1] < light["velocity_mps"].iloc[-1]


def test_tailwind_carries_the_rocket_downrange():
    calm = simulate_trajectory(PAYLOAD, 0.0, t_end=60.0)
    tailwind = simulate_trajectory(PAYLOAD, 20.0, t_end=60.0)
    headwind = simulate_trajectory(PAYLOAD, -20.0, t_end=60.0)
    assert tailwind["downrange_km"].iloc[-1] > calm["downrange_km"].iloc[-1]
    assert headwind["downrange_km"].iloc[-1] < calm["downrange_km"].iloc[-1]


def test_events_are_reported():
    events = simulate_trajectory(PAYLOAD, 0.0).attrs["events"]
    assert 0 < events["max_q_time_s"] < events["burnout_time_s"]
    assert events["max_q_pa"] > 0
    assert events["apogee_time_s"] > events["burnout_time_s"]


# ---- input checks ----
def test_rejects_negative_payload():
    expect_value_error(lambda: simulate_trajectory(-1.0, 0.0))


def test_rejects_vehicle_too_heavy_to_lift_off():
    expect_value_error(lambda: simulate_trajectory(500_000.0, 0.0))


def test_rejects_bad_time_settings():
    expect_value_error(lambda: simulate_trajectory(PAYLOAD, 0.0, t_end=0.0))
    expect_value_error(lambda: simulate_trajectory(PAYLOAD, 0.0, dt=0.0))


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
