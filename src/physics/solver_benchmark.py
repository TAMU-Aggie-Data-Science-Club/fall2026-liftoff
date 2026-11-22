"""
Speed and edge-case benchmark for the trajectory solver.

Runs simulate_trajectory() on 50 extreme parameter combinations and checks that every
run finishes in under one second without crashing. A combination that is physically
impossible (no propellant, too heavy to lift off) must be rejected with a ValueError,
which counts as handled. Anything else that raises is a failure.

Run from the repo root:
    python -m src.physics.solver_benchmark

Also prints the accuracy of the solver tolerances (RTOL, ATOL, MAX_STEP_S in
trajectory.py) against a much tighter reference run.
"""

import sys
import time

import numpy as np

from . import trajectory
from .trajectory import FALCON9, simulate_trajectory

TIME_LIMIT_S = 1.0

PAYLOADS_KG = [0.0, 1_000.0, 22_800.0, 60_000.0, 150_000.0]   # none ... far beyond capacity
WINDS_MPS = [-100.0, -30.0, 0.0, 30.0, 100.0]                 # hurricane-force head/tailwinds

# name -> extra keyword arguments for simulate_trajectory
SPECIAL_CASES = {
    "zero fuel": {"vehicle": {**FALCON9, "stage1_prop_mass": 0.0, "landing_reserve_mass": 0.0}},
    "all fuel held in reserve": {"vehicle": {**FALCON9, "landing_reserve_mass": 395_700.0}},
    "almost no fuel": {"vehicle": {**FALCON9, "landing_reserve_mass": 395_000.0}},
    "full throttle, no reserve": {"vehicle": {**FALCON9, "throttle": 1.0, "landing_reserve_mass": 0.0}},
    "barely lifts off": {"vehicle": {**FALCON9, "throttle": 0.72}},
    "cannot lift off": {"vehicle": {**FALCON9, "throttle": 0.5}},
    "no drag": {"vehicle": {**FALCON9, "cd": 0.0}},
    "huge drag": {"vehicle": {**FALCON9, "cd": 50.0}},
    "no pitch kick": {"kick_angle_deg": 0.0},
    "kick straight to horizontal": {"kick_angle_deg": 90.0},
    "kick past horizontal": {"kick_angle_deg": 120.0},
    "kick at liftoff": {"kick_start_s": 0.0, "kick_duration_s": 1.0},
    "kick after burnout": {"kick_start_s": 400.0},
    "600 m/s tailwind": {"wind_speed": 600.0},
    "600 m/s headwind": {"wind_speed": -600.0},
    "pad at 4 km altitude": {"site_altitude": 4_000.0},
    "pad below sea level": {"site_altitude": -400.0},
    "one hour of flight": {"t_end": 3_600.0},
    "0.05 s output step": {"dt": 0.05},
    "stops during the burn": {"t_end": 30.0},
    "exponential atmosphere": {"atmosphere_model": "exponential"},
    "inverse-square gravity": {"gravity_model": "inverse_square"},
    "max payload, headwind, steep kick": {"payload_mass": 60_000.0, "wind_speed": -100.0,
                                          "kick_angle_deg": 5.0},
    "tiny time window": {"t_end": 0.5, "dt": 0.1},
    "very long kick": {"kick_duration_s": 300.0},
}


def build_cases():
    """The 50 benchmark cases as (name, keyword arguments) pairs."""
    cases = [(f"payload {payload:.0f} kg, wind {wind:+.0f} m/s",
              {"payload_mass": payload, "wind_speed": wind})
             for payload in PAYLOADS_KG for wind in WINDS_MPS]
    for name, extra in SPECIAL_CASES.items():
        cases.append((name, {"payload_mass": 10_000.0, "wind_speed": 0.0, **extra}))
    return cases


def run_case(kwargs):
    """Run one case. Returns (seconds, outcome text, passed)."""
    start = time.perf_counter()
    try:
        df = simulate_trajectory(**kwargs)
    except ValueError as err:
        return time.perf_counter() - start, f"rejected: {err}", True
    except Exception as err:  # anything else is a solver crash
        return time.perf_counter() - start, f"CRASHED: {type(err).__name__}: {err}", False
    seconds = time.perf_counter() - start

    if df.empty or not np.isfinite(df.to_numpy()).all():
        return seconds, "FAILED: empty or non-finite output", False
    events = df.attrs["events"]
    if events["impact_time_s"] is not None:
        outcome = f"hit the ground at {events['impact_time_s']:.0f} s"
    else:
        outcome = f"flew {df['time_sec'].iloc[-1]:.0f} s, {df['altitude_km'].iloc[-1]:.0f} km up"
    return seconds, outcome, True


def tolerance_error():
    """Largest altitude [m] and speed [m/s] difference from a much tighter solver run."""
    current = simulate_trajectory(10_000.0, 0.0)
    saved = trajectory.RTOL, trajectory.ATOL, trajectory.MAX_STEP_S
    trajectory.RTOL, trajectory.ATOL, trajectory.MAX_STEP_S = 1e-12, 1e-9, 0.05
    try:
        reference = simulate_trajectory(10_000.0, 0.0)
    finally:
        trajectory.RTOL, trajectory.ATOL, trajectory.MAX_STEP_S = saved
    n = min(len(current), len(reference))
    altitude = np.abs(current["altitude_km"][:n] - reference["altitude_km"][:n]).max() * 1000.0
    speed = np.abs(current["velocity_mps"][:n] - reference["velocity_mps"][:n]).max()
    return float(altitude), float(speed)


def main():
    cases = build_cases()
    simulate_trajectory(10_000.0, 0.0)  # warm-up so import time is not counted
    slowest, failures = 0.0, 0
    for name, kwargs in cases:
        seconds, outcome, passed = run_case(kwargs)
        passed = passed and seconds < TIME_LIMIT_S
        slowest = max(slowest, seconds)
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'}  {seconds * 1000:6.0f} ms  {name}: {outcome}")

    altitude, speed = tolerance_error()
    print(f"\n{len(cases) - failures}/{len(cases)} cases passed. "
          f"Slowest run: {slowest * 1000:.0f} ms (limit {TIME_LIMIT_S * 1000:.0f} ms).")
    print(f"Tolerances rtol={trajectory.RTOL:g}, atol={trajectory.ATOL:g}, "
          f"max_step={trajectory.MAX_STEP_S:g} s differ from a tight reference run by at most "
          f"{altitude:.1f} m and {speed:.2f} m/s.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
