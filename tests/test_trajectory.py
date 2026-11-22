"""
Sample-value checks for src/physics/trajectory.py.

Run from the repo root, either way:
    python -m tests.test_trajectory  (no pytest needed)
    python -m pytest tests/          (if pytest is installed)
"""

import pickle
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.physics.constants import G0
from src.physics.trajectory import (
    FALCON9,
    OUTPUT_COLUMNS,
    predict_success_probability,
    risk_adjustments,
    simulate_trajectory,
    simulate_trajectory_with_risk,
)

PAYLOAD = 10_000.0  # kg


def expect_value_error(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ---- output format ----
def test_columns_and_time_grid():
    df = simulate_trajectory(PAYLOAD, 0.0, t_end=300.0)
    assert list(df.columns) == OUTPUT_COLUMNS
    assert len(df) == 301  # t = 0, 1, ..., 300 s
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
    burned = FALCON9["stage1_prop_mass"] - FALCON9["landing_reserve_mass"]
    assert np.isclose(events["burnout_time_s"], burned / (FALCON9["throttle"] * m_dot))


def test_speed_drops_after_burnout():
    df = simulate_trajectory(PAYLOAD, 0.0)
    burnout = df.attrs["events"]["burnout_time_s"]
    after = df[df["time_sec"] > burnout]
    assert after["velocity_mps"].iloc[5] < after["velocity_mps"].iloc[0]


def test_vertical_launch_matches_hand_calculation():
    # No kick, no drag (cd = 0): a = T/m - g with T and m known, so check the first
    # second against v = a0 * t using the pad values (mass changes by under 1% in 1 s).
    vehicle = {**FALCON9, "cd": 0.0}
    df = simulate_trajectory(PAYLOAD, 0.0, vehicle=vehicle, kick_angle_deg=0.0, t_end=1.0)
    m0 = (FALCON9["stage1_dry_mass"] + FALCON9["stage1_prop_mass"]
          + FALCON9["upper_stage_mass"] + PAYLOAD)
    a0 = FALCON9["throttle"] * FALCON9["thrust_sl"] / m0 - G0
    assert np.isclose(df["velocity_mps"].iloc[-1], a0, rtol=0.03)
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


def test_rows_stop_at_ground_impact():
    df = simulate_trajectory(PAYLOAD, 0.0)
    impact = df.attrs["events"]["impact_time_s"]
    assert impact is not None and impact < 500.0
    assert df["time_sec"].iloc[-1] <= impact < df["time_sec"].iloc[-1] + 1.0
    assert df["altitude_km"].iloc[-1] >= 0.0


def test_default_flight_is_falcon9_like():
    # Tuned defaults (PHYSICS.md section 8): MECO near 147 s, 55-75 km, 1500-1900 m/s.
    df = simulate_trajectory(PAYLOAD, 0.0)
    events = df.attrs["events"]
    at_meco = df.iloc[int(events["burnout_time_s"])]
    assert 140 < events["burnout_time_s"] < 155
    assert 55 < at_meco["altitude_km"] < 75
    assert 1500 < at_meco["velocity_mps"] < 1900
    assert 50 < events["max_q_time_s"] < 90


# ---- input checks ----
def test_rejects_negative_payload():
    expect_value_error(lambda: simulate_trajectory(-1.0, 0.0))


def test_rejects_vehicle_too_heavy_to_lift_off():
    expect_value_error(lambda: simulate_trajectory(500_000.0, 0.0))


def test_rejects_bad_time_settings():
    expect_value_error(lambda: simulate_trajectory(PAYLOAD, 0.0, t_end=0.0))
    expect_value_error(lambda: simulate_trajectory(PAYLOAD, 0.0, dt=0.0))


# ---- edge cases (see also src/physics/solver_benchmark.py) ----
def test_rejects_non_finite_inputs():
    expect_value_error(lambda: simulate_trajectory(float("nan"), 0.0))
    expect_value_error(lambda: simulate_trajectory(PAYLOAD, float("inf")))


def test_rejects_zero_fuel():
    no_fuel = {**FALCON9, "stage1_prop_mass": 0.0, "landing_reserve_mass": 0.0}
    expect_value_error(lambda: simulate_trajectory(PAYLOAD, 0.0, vehicle=no_fuel))


def test_almost_no_fuel_still_returns_rows():
    vehicle = {**FALCON9, "landing_reserve_mass": 395_000.0}  # burns for about 0.3 s
    df = simulate_trajectory(PAYLOAD, 0.0, vehicle=vehicle)
    assert len(df) >= 1 and not df.isna().any().any()


def test_crash_during_burn_stops_cleanly():
    df = simulate_trajectory(PAYLOAD, 0.0, kick_angle_deg=90.0)
    events = df.attrs["events"]
    assert events["impact_time_s"] is not None and events["burnout_time_s"] is None
    assert df["time_sec"].iloc[-1] <= events["impact_time_s"]


def test_extreme_wind_gives_finite_output():
    for wind in (-600.0, -100.0, 100.0, 600.0):
        df = simulate_trajectory(PAYLOAD, wind)
        assert np.isfinite(df.to_numpy()).all()


# ---- ML risk -> solver ----
def test_risk_levels_set_the_drag_multiplier():
    assert risk_adjustments(0.99)["risk_level"] == "low"
    assert risk_adjustments(0.99)["drag_scale"] == 1.0
    assert risk_adjustments(0.90)["risk_level"] == "medium"
    assert risk_adjustments(0.90)["drag_scale"] == 1.10
    assert risk_adjustments(0.50)["risk_level"] == "high"
    assert risk_adjustments(0.50)["drag_scale"] == 1.25
    assert risk_adjustments(None)["risk_level"] == "unknown"
    assert risk_adjustments(None)["drag_scale"] == 1.0
    expect_value_error(lambda: risk_adjustments(1.5))


def test_temperature_sets_the_density_multiplier():
    assert risk_adjustments(temperature_c=15.0)["density_scale"] == 1.0
    assert np.isclose(risk_adjustments(temperature_c=35.0)["density_scale"], 288.15 / 308.15)
    assert risk_adjustments(temperature_c=-5.0)["density_scale"] > 1.0
    assert risk_adjustments(temperature_c=-150.0)["density_scale"] == 1.15  # clamped


def test_low_risk_standard_day_matches_plain_solver():
    plain = simulate_trajectory(PAYLOAD, 0.0, t_end=200.0)
    risky = simulate_trajectory_with_risk(PAYLOAD, 0.0, success_probability=0.99,
                                          temperature_c=15.0, t_end=200.0)
    assert np.allclose(plain.to_numpy(), risky.to_numpy())
    assert risky.attrs["risk"]["risk_level"] == "low"


def test_high_risk_flies_lower_and_slower():
    low = simulate_trajectory_with_risk(PAYLOAD, 0.0, success_probability=0.99, t_end=150.0)
    high = simulate_trajectory_with_risk(PAYLOAD, 0.0, success_probability=0.50, t_end=150.0)
    assert high["altitude_km"].iloc[-1] < low["altitude_km"].iloc[-1]
    assert high["velocity_mps"].iloc[-1] < low["velocity_mps"].iloc[-1]


def test_cold_day_raises_max_q():
    warm = simulate_trajectory_with_risk(PAYLOAD, 0.0, success_probability=0.99, temperature_c=35.0)
    cold = simulate_trajectory_with_risk(PAYLOAD, 0.0, success_probability=0.99, temperature_c=-5.0)
    assert cold.attrs["events"]["max_q_pa"] > warm.attrs["events"]["max_q_pa"]


def test_missing_model_file_is_an_error():
    missing = Path(tempfile.gettempdir()) / "liftoff_no_such_model.pkl"
    for fn in (lambda: predict_success_probability(PAYLOAD, 0.0, model_path=missing),
               lambda: simulate_trajectory_with_risk(PAYLOAD, 0.0, model_path=missing)):
        try:
            fn()
        except FileNotFoundError:
            continue
        raise AssertionError("expected FileNotFoundError")


def test_reads_prediction_from_a_saved_model():
    # A tiny stand-in for models/baseline_model.pkl, built the way train_model.py saves it.
    try:
        from src.models.train_model import FEATURE_COLUMNS, platt, predict_probability, train
    except ImportError:
        return  # xgboost not installed: nothing to check
    rng = np.random.default_rng(0)
    rows = 60
    data = pd.DataFrame({
        "temperature_2m": rng.uniform(5, 35, rows),
        "wind_speed_10m": rng.uniform(0, 35, rows),
        "precipitation": rng.uniform(0, 2, rows),
        "cloud_cover": rng.uniform(0, 100, rows),
        "payload_mass_kg": rng.uniform(1_000, 20_000, rows),
        "rocket_type": ["Falcon 9"] * rows,
        "is_delayed": rng.integers(0, 2, rows),
    })
    # Platt calibration with slope 0.5 shrinks the raw score toward 0.5, so this also
    # checks that the calibrated probability (not the raw score) is what comes out.
    booster = train(data, "is_delayed", ["Falcon 9"])
    calibration = {"method": "platt", "slope": 0.5, "intercept": 0.0}
    saved = {"models": {"delay": {"booster": booster, "calibration": calibration}},
             "feature_columns": FEATURE_COLUMNS, "rocket_categories": ["Falcon 9"]}
    with tempfile.TemporaryDirectory() as folder:
        model_path = Path(folder) / "baseline_model.pkl"
        model_path.write_bytes(pickle.dumps(saved))
        probability = predict_success_probability(PAYLOAD, 5.0, model_path=model_path)
        with_go = predict_success_probability(PAYLOAD, 5.0, model_path=model_path,
                                              weather_go_pct=40)
        df = simulate_trajectory_with_risk(PAYLOAD, 5.0, model_path=model_path, t_end=60.0)
    features = pd.DataFrame([{"temperature_2m": 15.0, "wind_speed_10m": 18.0,
                              "precipitation": 0.0, "cloud_cover": 0.0,
                              "payload_mass_kg": PAYLOAD, "rocket_type": "Falcon 9"}])
    raw = float(predict_probability(booster, features, ["Falcon 9"])[0])
    assert np.isclose(1.0 - probability, platt(np.array([raw]), 0.5, 0.0)[0])
    assert 0.0 <= probability <= 1.0
    assert 0.0 <= with_go <= 1.0
    assert np.isclose(df.attrs["risk"]["failure_probability"], 1.0 - probability)
    assert df.attrs["risk"]["risk_level"] in ("low", "medium", "high")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
