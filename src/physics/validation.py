"""
Benchmark the trajectory solver against real Falcon 9 telemetry (PHYSICS.md section 8).

Compares simulate_trajectory() with the webcast telemetry in data/reference/telemetry/
for three flights, from liftoff to main-engine cutoff (MECO). The model is single-stage
on a flat Earth, so it is only valid for the first-stage burn; the telemetry after MECO
follows the second stage.

Run from the repo root:
    python -m src.physics.validation          compare the current solver defaults
    python -m src.physics.validation --fit    also search for better guidance/vehicle values

Telemetry units: time [s], velocity [m/s], altitude [km] (see data/reference/README.md).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .trajectory import FALCON9, KICK_ANGLE_DEG, simulate_trajectory

REFERENCE_DIR = Path("data/reference/telemetry")

# mission -> (telemetry file, approximate payload mass [kg])
REFERENCE_FLIGHTS = {
    "crs12": ("spacex_crs-12_raw.csv", 8_500.0),             # Dragon 1 + cargo
    "dm1": ("dm-1.csv", 12_055.0),                           # Crew Dragon
    "iridium_next_1": ("iridium_next_1_raw.csv", 9_600.0),   # 10 satellites + dispenser
}


def load_reference(mission):
    """
    Telemetry for one mission on a 1 s grid from liftoff to MECO.

    Returns (DataFrame[time_sec, altitude_km, velocity_mps], meco_time_s).
    """
    filename, _ = REFERENCE_FLIGHTS[mission]
    folder = REFERENCE_DIR / mission
    raw = pd.read_csv(folder / filename).drop_duplicates("time").sort_values("time")
    meco = float(json.loads((folder / "events.json").read_text())["meco"])

    t = np.arange(0.0, meco + 0.5, 1.0)
    return pd.DataFrame({
        "time_sec": t,
        "altitude_km": np.interp(t, raw["time"], raw["altitude"]),
        "velocity_mps": np.interp(t, raw["time"], raw["velocity"]),
    }), meco


def compare_flight(mission, **sim_kwargs):
    """
    Error of the simulation against one reference flight.

    The curves are compared second by second up to whichever comes first, the real
    MECO or the simulated burnout. Returns a dict of error metrics, or None if the
    simulated rocket hit the ground before burning out.
    """
    reference, meco = load_reference(mission)
    payload = REFERENCE_FLIGHTS[mission][1]
    sim = simulate_trajectory(payload, 0.0, t_end=meco + 60.0, **sim_kwargs)
    burnout = sim.attrs["events"]["burnout_time_s"]
    if burnout is None:
        return None

    n = int(min(meco, burnout)) + 1
    sim, reference = sim.iloc[:n], reference.iloc[:n]
    alt_error = sim["altitude_km"].to_numpy() - reference["altitude_km"].to_numpy()
    speed_error = sim["velocity_mps"].to_numpy() - reference["velocity_mps"].to_numpy()
    return {
        "mission": mission,
        "compared_to_s": n - 1,
        "meco_s": meco,
        "burnout_s": burnout,
        "altitude_rmse_km": float(np.sqrt(np.mean(alt_error**2))),
        "altitude_max_error_km": float(np.max(np.abs(alt_error))),
        "speed_rmse_mps": float(np.sqrt(np.mean(speed_error**2))),
        "speed_max_error_mps": float(np.max(np.abs(speed_error))),
        "final_altitude_error_km": float(alt_error[-1]),
        "final_speed_error_mps": float(speed_error[-1]),
        "final_altitude_km": float(reference["altitude_km"].iloc[-1]),
        "final_speed_mps": float(reference["velocity_mps"].iloc[-1]),
    }


def compare_all(**sim_kwargs):
    """Error table (one row per reference flight) for the given solver settings."""
    rows = [compare_flight(mission, **sim_kwargs) for mission in REFERENCE_FLIGHTS]
    if any(row is None for row in rows):
        return None
    return pd.DataFrame(rows).set_index("mission")


def _settings(kick_angle_deg, throttle, landing_reserve_mass):
    return {
        "kick_angle_deg": kick_angle_deg,
        "vehicle": {**FALCON9, "throttle": throttle, "landing_reserve_mass": landing_reserve_mass},
    }


def _cost(params):
    """Single number to minimise: altitude, speed and burn-time error over all flights."""
    kick, throttle, reserve = params
    if not (0 < kick < 20 and 0.5 < throttle <= 1 and 0 <= reserve < 150_000):
        return 1e6
    try:
        table = compare_all(**_settings(kick, throttle, reserve))
    except ValueError:  # e.g. thrust/weight <= 1
        return 1e6
    if table is None:   # crashed during the burn
        return 1e6
    # Scale each error so 5 km, 100 m/s and 10 s of burn time count about the same.
    return float((table["altitude_rmse_km"] / 5 + table["speed_rmse_mps"] / 100
                  + (table["burnout_s"] - table["meco_s"]).abs() / 10).sum())


def fit_parameters():
    """
    Search for the pitch-kick angle, average throttle and landing reserve that best
    match the three reference flights. Returns (kick_angle_deg, throttle, reserve_kg).
    """
    starts = [(k, th, r) for k in (0.3, 1.0, 2.0) for th in (0.85, 0.95) for r in (30_000.0, 60_000.0)]
    best = min(starts, key=_cost)
    result = minimize(_cost, best, method="Nelder-Mead",
                      options={"xatol": 1e-3, "fatol": 1e-3, "maxfev": 250})
    return tuple(float(v) for v in result.x)


def _report(title, table):
    columns = ["compared_to_s", "meco_s", "burnout_s", "altitude_rmse_km", "altitude_max_error_km",
               "speed_rmse_mps", "speed_max_error_mps", "final_altitude_error_km",
               "final_speed_error_mps"]
    print(f"\n{title}")
    print(table[columns].round(1).T.to_string())


if __name__ == "__main__":
    current = compare_all()
    if current is None:
        print("The current defaults fly into the ground before burnout.")
    else:
        _report(f"Current defaults (kick {KICK_ANGLE_DEG} deg, throttle {FALCON9['throttle']}, "
                f"landing reserve {FALCON9['landing_reserve_mass']:.0f} kg)", current)

    if "--fit" in sys.argv:
        kick, throttle, reserve = fit_parameters()
        _report(f"Fitted (kick {kick:.2f} deg, throttle {throttle:.3f}, "
                f"landing reserve {reserve:.0f} kg)", compare_all(**_settings(kick, throttle, reserve)))
